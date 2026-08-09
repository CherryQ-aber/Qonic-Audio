"""Materialize a non-authoritative Qt LGPL integration candidate.

The candidate is copied from the frozen onedir package, not rebuilt.  Only
GPL-only Qt groups already proven safe in staging are removed.  Recipient
facing Qt LGPLv3, attribution and exact-source material is then placed in the
candidate's ``LICENSES`` directory.  The frozen package is never modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from verify_qt_lgpl_route import GPL_ONLY_GROUPS, remove_group, sha256_file


QT_LICENSE_FILES = {
    "Qt/LGPL-3.0.txt": "docs/compliance/staging/licenses/Qt/LGPL-3.0.txt",
    "Qt/Qt-6.11-Licensing.html": "docs/compliance/staging/licenses/Qt/Qt-6.11-Licensing.html",
    "Qt/Qt-6.11.1-Third-Party-Code.html": "docs/compliance/staging/licenses/Qt/Qt-6.11.1-Third-Party-Code.html",
    "Qt/Qt-6.11-SBOM-Documentation.html": "docs/compliance/staging/licenses/Qt/Qt-6.11-SBOM-Documentation.html",
    "PySide6/LGPL-3.0.txt": "docs/compliance/staging/licenses/PySide6/LGPL-3.0.txt",
    "Shiboken6/LGPL-3.0.txt": "docs/compliance/staging/licenses/Shiboken6/LGPL-3.0.txt",
}
IMMUTABLE_TREE_EXCLUDES = {
    "COMPLIANCE_INTEGRATION_CANDIDATE.json",
    # The packaged app creates this empty log at launch. It is not distributed
    # application content and must not invalidate the static candidate identity.
    "logs/runtime.log",
}


def _assert_child(path: Path, parent: Path) -> None:
    try:
        path.relative_to(parent)
    except ValueError as error:
        raise ValueError(f"path must be below {parent}: {path}") from error


def _copy(project_root: Path, source_relative: str, destination: Path) -> None:
    source = project_root / source_relative
    if not source.is_file():
        raise FileNotFoundError(f"required Qt licence material missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _tree_digest(root: Path, *, exclude: set[str]) -> tuple[str, int]:
    digest = hashlib.sha256()
    count = 0
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.as_posix().lower()):
        relative = path.relative_to(root).as_posix()
        if relative in exclude:
            continue
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(path).encode("ascii"))
        digest.update(b"\n")
        count += 1
    return digest.hexdigest().upper(), count


def _recipient_source_availability(project_root: Path, destination: Path) -> None:
    source_info = project_root / "third_party/source-information/qt-source-requirements.json"
    if not source_info.is_file():
        raise FileNotFoundError(f"Qt source inventory missing: {source_info}")
    records = json.loads(source_info.read_text(encoding="utf-8"))
    _copy(project_root, "docs/compliance/staging/licenses/Qt/LGPL-3.0.txt", destination.parent / "LGPL-3.0.txt")
    _copy(project_root, "docs/compliance/QT_SOURCE_AVAILABILITY.md", destination)
    copied = destination.read_text(encoding="utf-8").replace(
        "[`third_party/source-information/qt-source-requirements.json`](../../third_party/source-information/qt-source-requirements.json)",
        "`QT_SOURCE_REQUIREMENTS.json` in this release",
    )
    destination.write_text(copied, encoding="utf-8")
    (destination.parent / "QT_SOURCE_REQUIREMENTS.json").write_text(
        json.dumps(records, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_candidate_notice(destination: Path, removed: dict[str, list[str]]) -> None:
    groups = ", ".join(sorted(removed))
    destination.write_text(
        "# Qt / PySide6 / Shiboken6 LGPLv3 Notice\n\n"
        "This non-authoritative Qonic Audio integration candidate uses Qt for Python "
        "Community Edition components Qt, PySide6 and Shiboken6 version 6.11.1 "
        "through shared libraries. The selected distribution route is LGPL-3.0.\n\n"
        "The candidate does not contain the staging-verified GPL-only Qt runtime "
        f"groups: {groups}.\n\n"
        "The applicable LGPLv3 text and Qt attribution material are in `Qt/`, "
        "`PySide6/` and `Shiboken6/`. Exact official source URLs, hashes and the "
        "Qt module-source inventory are in `Qt/QT_SOURCE_AVAILABILITY.md` and "
        "`Qt/QT_SOURCE_REQUIREMENTS.json`.\n\n"
        "The user may replace these dynamically linked Qt shared libraries with an "
        "interface-compatible modified version. This package does not apply a Qonic "
        "DLL hash or signature gate.\n",
        encoding="utf-8",
    )


def build_candidate(
    source: Path,
    candidate: Path,
    project_root: Path,
    parent_archive: Path,
    executable_name: str,
) -> dict[str, Any]:
    source = source.resolve()
    candidate = candidate.resolve()
    project_root = project_root.resolve()
    parent_archive = parent_archive.resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"frozen onedir package not found: {source}")
    if not parent_archive.is_file():
        raise FileNotFoundError(f"frozen archive not found: {parent_archive}")
    if candidate.exists():
        raise FileExistsError(f"candidate already exists: {candidate}")
    _assert_child(candidate, project_root)
    if candidate == source or source in candidate.parents:
        raise ValueError("candidate must be outside the frozen package")
    if not (source / executable_name).is_file():
        raise FileNotFoundError(f"frozen executable not found: {source / executable_name}")

    shutil.copytree(source, candidate, copy_function=shutil.copy2)
    removed = {group: remove_group(candidate, group) for group in GPL_ONLY_GROUPS}
    missing_groups = [group for group, files in removed.items() if not files]
    if missing_groups:
        raise RuntimeError("expected GPL-only group not found in frozen package: " + ", ".join(missing_groups))

    license_root = candidate / "LICENSES"
    for target_relative, source_relative in QT_LICENSE_FILES.items():
        _copy(project_root, source_relative, license_root / target_relative)
    _recipient_source_availability(project_root, license_root / "Qt/QT_SOURCE_AVAILABILITY.md")
    _write_candidate_notice(license_root / "QT_LGPL_NOTICE.md", removed)

    manifest_relative = "COMPLIANCE_INTEGRATION_CANDIDATE.json"
    tree_sha256, file_count = _tree_digest(candidate, exclude=IMMUTABLE_TREE_EXCLUDES)
    manifest = {
        "schema_version": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "candidate_type": "non-authoritative LGPL-3.0 Qt integration candidate",
        "parent_authoritative_onedir": str(source),
        "parent_authoritative_archive": str(parent_archive),
        "parent_authoritative_archive_sha256": sha256_file(parent_archive),
        "candidate_qt_version": "6.11.1",
        "candidate_pyside6_version": "6.11.1",
        "candidate_shiboken6_version": "6.11.1",
        "removed_gpl_only_groups": {group: len(files) for group, files in removed.items()},
        "removed_gpl_only_file_count": sum(len(files) for files in removed.values()),
        "recipient_qt_materials": [
            "LICENSES/QT_LGPL_NOTICE.md",
            "LICENSES/Qt/LGPL-3.0.txt",
            "LICENSES/Qt/Qt-6.11-Licensing.html",
            "LICENSES/Qt/Qt-6.11.1-Third-Party-Code.html",
            "LICENSES/Qt/Qt-6.11-SBOM-Documentation.html",
            "LICENSES/Qt/QT_SOURCE_AVAILABILITY.md",
            "LICENSES/Qt/QT_SOURCE_REQUIREMENTS.json",
            "LICENSES/PySide6/LGPL-3.0.txt",
            "LICENSES/Shiboken6/LGPL-3.0.txt",
        ],
        "content_tree_sha256_excluding_manifest": tree_sha256,
        "content_file_count_excluding_manifest": file_count,
    }
    (candidate / manifest_relative).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--parent-archive", type=Path, required=True)
    parser.add_argument("--executable", default="Qonic_Audio_v5.0_internal_test.exe")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build_candidate(
            args.source, args.candidate, args.project_root, args.parent_archive, args.executable
        )
    except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 3
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
