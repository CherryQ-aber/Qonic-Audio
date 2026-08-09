"""Run repeatable automatic checks for a Qt LGPL integration candidate on Windows.

The interactive file-dialog, system-tray and real-media checks deliberately
remain marked for a human Windows desktop acceptance.  This tool does not
claim that a non-interactive QML smoke covers those interactions.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_qt_lgpl_integration_candidate import IMMUTABLE_TREE_EXCLUDES, _tree_digest
from verify_qt_lgpl_route import GPL_ONLY_GROUPS, group_files


SMOKE_MODULES = (None, "autoConvert", "audioEditor", "metadata", "lyricsCover")
REQUIRED_FILES = (
    "_internal/PySide6/plugins/platforms/qwindows.dll",
    "_internal/PySide6/plugins/imageformats/qjpeg.dll",
    "_internal/PySide6/plugins/multimedia/ffmpegmediaplugin.dll",
    "_internal/PySide6/plugins/multimedia/windowsmediaplugin.dll",
    "LICENSES/QT_LGPL_NOTICE.md",
    "LICENSES/Qt/LGPL-3.0.txt",
    "LICENSES/Qt/QT_SOURCE_AVAILABILITY.md",
    "LICENSES/Qt/QT_SOURCE_REQUIREMENTS.json",
    "LICENSES/PySide6/LGPL-3.0.txt",
    "LICENSES/Shiboken6/LGPL-3.0.txt",
    "COMPLIANCE_INTEGRATION_CANDIDATE.json",
)


def _smoke(candidate: Path, executable_name: str, module: str | None, timeout: int) -> dict[str, Any]:
    command = [str(candidate / executable_name), "--qml-smoke-test"]
    if module:
        command.append(f"--qml-open-module={module}")
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "windows"
    completed = subprocess.run(
        command,
        cwd=candidate,
        env=environment,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return {
        "command": command,
        "qt_qpa_platform": "windows",
        "exit_code": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
        "passed": completed.returncode == 0,
    }


def run_acceptance(candidate: Path, executable_name: str, timeout: int) -> dict[str, Any]:
    candidate = candidate.resolve()
    manifest_path = candidate / "COMPLIANCE_INTEGRATION_CANDIDATE.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"candidate manifest missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not (candidate / executable_name).is_file():
        raise FileNotFoundError(f"candidate executable missing: {candidate / executable_name}")

    smokes = [_smoke(candidate, executable_name, module, timeout) for module in SMOKE_MODULES]
    required_files = {
        relative: (candidate / relative).is_file() for relative in REQUIRED_FILES
    }
    removed_groups = {
        group: [path.relative_to(candidate).as_posix() for path in group_files(candidate, patterns)]
        for group, patterns in GPL_ONLY_GROUPS.items()
    }
    tree_sha256, tree_file_count = _tree_digest(candidate, exclude=IMMUTABLE_TREE_EXCLUDES)
    automatic_passed = (
        all(item["passed"] for item in smokes)
        and all(required_files.values())
        and not any(removed_groups.values())
        and tree_sha256 == manifest["content_tree_sha256_excluding_manifest"]
        and tree_file_count == manifest["content_file_count_excluding_manifest"]
    )
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate": str(candidate),
        "candidate_manifest": "COMPLIANCE_INTEGRATION_CANDIDATE.json",
        "candidate_tree_sha256": tree_sha256,
        "candidate_tree_file_count": tree_file_count,
        "candidate_manifest_matches": (
            tree_sha256 == manifest["content_tree_sha256_excluding_manifest"]
            and tree_file_count == manifest["content_file_count_excluding_manifest"]
        ),
        "windows_qml_smokes": smokes,
        "required_files": required_files,
        "remaining_gpl_only_group_files": removed_groups,
        "automatic_status": "PASS" if automatic_passed else "FAIL",
        "human_interaction_status": "PENDING",
        "human_interaction_required": [
            "Use the candidate's visible Windows desktop window to choose an audio file with the native file picker.",
            "Play a known-good local audio file and confirm audible Qt Multimedia playback, pause, seek and stop.",
            "Confirm image/cover display for a file with embedded artwork.",
            "Confirm system-tray visibility and hide/restore or close-to-tray behaviour.",
            "Confirm Widgets fallback behaviour if the candidate exposes a legacy/native fallback path.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--executable", default="Qonic_Audio_v5.0_internal_test.exe")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()
    try:
        result = run_acceptance(args.candidate, args.executable, args.timeout)
    except (FileNotFoundError, KeyError, subprocess.TimeoutExpired) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 3
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"automatic_status": result["automatic_status"], "human_interaction_status": result["human_interaction_status"]}))
    return 0 if result["automatic_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
