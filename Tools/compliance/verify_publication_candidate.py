"""Verify the automatic release conditions for a Qonic publication candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from assemble_publication_candidate import (
    EXE_NAME,
    FFMPEG_SOURCE_SHA256,
    sha256,
    tree_sha256,
)
from verify_qt_lgpl_route import dynamic_linkage_evidence, run_packaged_smokes, scan_gpl_only_presence


REQUIRED_FILES = (
    "LICENSE",
    "LICENSES/README.md",
    "LICENSES/FFmpeg-NOTICE.md",
    "LICENSES/THIRD_PARTY_NOTICES.md",
    "LICENSES/QT_LGPL_NOTICE.md",
    "LICENSES/QT_SOURCE_AVAILABILITY.md",
    "LICENSES/Third_Party_Licenses/Qt/LGPL-3.0.txt",
    "LICENSES/Third_Party_Licenses/PySide6",
    "LICENSES/Third_Party_Licenses/Shiboken6",
    "Corresponding_Source/qonic-ffmpeg-complete-corresponding-source.tar.gz",
    "Corresponding_Source/SHA256SUMS.txt",
    "Corresponding_Source/SOURCE_CODE_AVAILABILITY.md",
    "PUBLICATION_CANDIDATE_MANIFEST.json",
)


def check_required(root: Path) -> list[str]:
    return [item for item in REQUIRED_FILES if not (root / item).exists()]


def scan_forbidden_paths(root: Path) -> list[str]:
    forbidden: list[str] = []
    blocked_parts = {"codex_memory", "music_input", "music_output", "temp", "cache", "__pycache__"}
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        parts = {part.lower() for part in path.relative_to(root).parts}
        if parts & blocked_parts or path.name.lower() in {"config.json", "cookie.txt"}:
            forbidden.append(relative)
    return sorted(forbidden)


def source_hashes(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    ffmpeg = root / str(manifest["ffmpeg"]["corresponding_source"]["file"])
    app = root / str(manifest["application_source"]["file"])
    return {
        "ffmpeg_source": {"file": str(ffmpeg.relative_to(root)), "actual": sha256(ffmpeg), "expected": FFMPEG_SOURCE_SHA256},
        "application_source": {"file": str(app.relative_to(root)), "actual": sha256(app), "expected": manifest["application_source"]["sha256"]},
    }


def test_archive(seven_zip: Path, archive: Path) -> dict[str, Any]:
    if not archive.is_file():
        return {"requested": False}
    completed = subprocess.run([str(seven_zip), "t", str(archive)], capture_output=True, text=True, check=False)
    listing = subprocess.run([str(seven_zip), "l", str(archive)], capture_output=True, text=True, check=False)
    text = listing.stdout.lower()
    unwanted = [token for token in ("codex_memory", "config.json", "cookie.txt", "logs/runtime.log") if token in text]
    return {
        "requested": True,
        "path": str(archive),
        "sha256": sha256(archive),
        "test_exit_code": completed.returncode,
        "listing_exit_code": listing.returncode,
        "forbidden_members": unwanted,
        "passed": completed.returncode == 0 and listing.returncode == 0 and not unwanted,
    }


def verify(root: Path, timeout: int, run_smokes: bool, seven_zip: Path | None, archive: Path | None) -> dict[str, Any]:
    manifest_path = root / "PUBLICATION_CANDIDATE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_tree = manifest["static_tree_sha256"]
    actual_tree = tree_sha256(root)
    sources = source_hashes(root, manifest)
    smokes = run_packaged_smokes(root, EXE_NAME, timeout) if run_smokes else []
    archive_result = test_archive(seven_zip, archive) if seven_zip and archive else {"requested": False}
    required_missing = check_required(root)
    gpl_only = {name: files for name, files in scan_gpl_only_presence(root).items() if files}
    result: dict[str, Any] = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_root": str(root),
        "manifest_status": manifest.get("status"),
        "source_commit": manifest.get("source_commit"),
        "required_missing": required_missing,
        "gpl_only_qt_files": gpl_only,
        "static_tree_sha256": {"expected": expected_tree, "actual": actual_tree, "passed": expected_tree == actual_tree},
        "source_hashes": sources,
        "dynamic_linkage": dynamic_linkage_evidence(root),
        "qml_smokes": smokes,
        "forbidden_paths": scan_forbidden_paths(root),
        "archive": archive_result,
    }
    result["passed"] = all(
        (
            not required_missing,
            not gpl_only,
            expected_tree == actual_tree,
            all(item["actual"] == item["expected"] for item in sources.values()),
            result["dynamic_linkage"]["dynamic_qt_imports_present"],
            all(item["passed"] for item in smokes),
            not result["forbidden_paths"],
            not archive_result.get("requested") or archive_result["passed"],
        )
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--skip-smokes", action="store_true")
    parser.add_argument("--seven-zip", type=Path)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    root = args.candidate_root.resolve()
    try:
        result = verify(root, args.timeout, not args.skip_smokes, args.seven_zip, args.archive)
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("PASS" if result["passed"] else "FAIL", args.output)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
