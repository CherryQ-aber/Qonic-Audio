"""Run the complete offline-first Qonic Audio compliance evidence collection."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

from collect_ffmpeg_info import collect_ffmpeg
from collect_ncmdump_info import collect_ncmdump
from collect_python_packages import collect_python_packages
from collect_qt_inventory import collect_qt_inventory
from common import (
    ComplianceError,
    display_path,
    load_json,
    parse_app_info,
    run_command,
    sha256_file,
    write_json,
)
from generate_manifest import generate_manifest
from generate_notices import generate_notices
from reporting import generate_audit_report, generate_owner_decisions


def _archive_paths(archive: Path, project_root: Path) -> list[str]:
    seven_zip = shutil.which("7z") or shutil.which("7z.exe")
    if not seven_zip:
        candidate = Path(r"C:\Program Files\7-Zip\7z.exe")
        seven_zip = str(candidate) if candidate.is_file() else None
    if not seven_zip:
        return []
    result = run_command(
        [seven_zip, "l", "-slt", archive],
        cwd=project_root,
        timeout=120,
        project_root=project_root,
    )
    if result.returncode != 0:
        return []
    paths = []
    for line in result.combined_output.splitlines():
        if line.startswith("Path = "):
            value = line[7:].strip()
            if value and value != archive.name:
                paths.append(value.replace("\\", "/"))
    return paths


def collect_release_inventory(
    project_root: Path,
    dist_path: Path,
    dist_archive: Path | None,
    output_path: Path,
) -> dict[str, Any]:
    """Record release directory/archive identities and detect same-version divergence."""

    release_root = project_root / "Release"
    authority_files = sorted(release_root.rglob("RELEASE_AUTHORITY.json"))
    authority_entries = [(path, load_json(path)) for path in authority_files]
    matching_entries = [
        (path, payload)
        for path, payload in authority_entries
        if dist_archive
        and (path.parent / str(payload.get("archive", ""))).resolve()
        == dist_archive.resolve()
        and (path.parent / str(payload.get("expanded_directory", ""))).resolve()
        == dist_path.resolve()
    ]
    active_entries = [
        (path, payload)
        for path, payload in authority_entries
        if payload.get("authority_status") == "AUTHORITATIVE_RELEASE_BASELINE"
    ]
    authority_file, authority = (
        matching_entries[0]
        if len(matching_entries) == 1
        else active_entries[0]
        if len(active_entries) == 1
        else (None, {})
    )
    archive_authority_status = {
        (path.parent / str(payload.get("archive", ""))).resolve(): payload.get(
            "authority_status", "UNCLASSIFIED"
        )
        for path, payload in authority_entries
        if payload.get("archive")
    }
    authoritative_archive = (
        (authority_file.parent / str(authority.get("archive"))).resolve()
        if authority_file and authority.get("archive")
        else None
    )
    authoritative_expanded = (
        (authority_file.parent / str(authority.get("expanded_directory"))).resolve()
        if authority_file and authority.get("expanded_directory")
        else None
    )
    archives = []
    if release_root.is_dir():
        for archive in sorted(release_root.rglob("*.7z"), key=lambda item: str(item).lower()):
            paths = _archive_paths(archive, project_root)
            archives.append(
                {
                    "path": display_path(archive, project_root),
                    "name": archive.name,
                    "size": archive.stat().st_size,
                    "sha256": sha256_file(archive),
                    "contains_ffmpeg": any(
                        item.lower().endswith("tools/ffmpeg/bin/ffmpeg.exe")
                        for item in paths
                    ),
                    "contains_ffprobe": any(
                        item.lower().endswith("tools/ffmpeg/bin/ffprobe.exe")
                        for item in paths
                    ),
                    "contains_ffplay": any(
                        item.lower().endswith("tools/ffmpeg/bin/ffplay.exe")
                        for item in paths
                    ),
                    "contains_ncmdump": any(
                        item.lower().endswith("tools/ncmdump/ncmdump.exe")
                        for item in paths
                    ),
                    "file_count": len(paths),
                    "release_status": (
                        "AUTHORITATIVE"
                        if authoritative_archive
                        and archive.resolve() == authoritative_archive
                        else (
                            "SUPERSEDED_HISTORICAL"
                            if archive_authority_status.get(archive.resolve())
                            == "SUPERSEDED_HISTORICAL_NOT_FOR_RELEASE"
                            else (
                            "NOT_FOR_RELEASE"
                            if (
                                (archive.parent / "NOT_FOR_RELEASE.md").is_file()
                                or "non_authoritative"
                                in {
                                    part.lower()
                                    for part in archive.relative_to(release_root).parts
                                }
                            )
                            else "UNCLASSIFIED"
                            )
                        )
                    ),
                }
            )
    app_info = parse_app_info(project_root)
    package_basename = app_info.get("APP_PACKAGE_BASENAME", "Qonic_Audio")
    qonic_archives = [
        item
        for item in archives
        if item["name"] == f"{package_basename}.7z"
        and item["release_status"] not in {"NOT_FOR_RELEASE", "SUPERSEDED_HISTORICAL"}
    ]
    distinct_hashes = {item["sha256"] for item in qonic_archives}
    tool_signatures = {
        (
            item["contains_ffmpeg"],
            item["contains_ffprobe"],
            item["contains_ffplay"],
            item["contains_ncmdump"],
        )
        for item in qonic_archives
    }
    expanded_tools = {
        "ffmpeg": any(
            path.is_file()
            for path in dist_path.rglob("ffmpeg.exe")
            if "tools" in path.as_posix().lower()
        ),
        "ffprobe": any(
            path.is_file()
            for path in dist_path.rglob("ffprobe.exe")
            if "tools" in path.as_posix().lower()
        ),
        "ffplay": any(
            path.is_file()
            for path in dist_path.rglob("ffplay.exe")
            if "tools" in path.as_posix().lower()
        ),
        "ncmdump": any(
            path.is_file()
            for path in dist_path.rglob("ncmdump.exe")
            if "tools" in path.as_posix().lower()
        ),
    }
    audited_distribution = (
        display_path(dist_archive, project_root)
        if dist_archive
        else display_path(dist_path, project_root, dist_path)
    )
    audited_archive = None
    if dist_archive:
        audited_archive = {
            "path": display_path(dist_archive, project_root),
            "size": dist_archive.stat().st_size,
            "sha256": sha256_file(dist_archive),
        }
    authority_validation = {
        "authority_file_count": len(authority_files),
        "active_authority_count": len(active_entries),
        "authority_file": (
            display_path(authority_file, project_root) if authority_file else None
        ),
        "archive_matches_owner_hash": bool(
            authoritative_archive
            and authoritative_archive.is_file()
            and sha256_file(authoritative_archive)
            == str(authority.get("archive_sha256", "")).upper()
        ),
        "audited_archive_is_authoritative": bool(
            dist_archive
            and authoritative_archive
            and dist_archive.resolve() == authoritative_archive
        ),
        "audited_expanded_is_authoritative": bool(
            authoritative_expanded
            and dist_path.resolve() == authoritative_expanded
        ),
        "non_authoritative_marker_present": (
            release_root
            / "Non_Authoritative"
            / "2026-07-24_pre_freeze"
            / "NOT_FOR_RELEASE.md"
        ).is_file(),
    }
    authority_validation["passed"] = all(
        (
            authority_validation["active_authority_count"] == 1,
            authority_validation["archive_matches_owner_hash"],
            authority_validation["audited_archive_is_authoritative"],
            authority_validation["audited_expanded_is_authoritative"],
            authority_validation["non_authoritative_marker_present"],
        )
    )
    payload = {
        "audited_distribution": audited_distribution,
        "audited_archive": audited_archive,
        "audited_extracted_tools": expanded_tools,
        "release_archives": archives,
        "release_authority": authority,
        "authority_validation": authority_validation,
        "artifact_divergence": len(distinct_hashes) > 1 or len(tool_signatures) > 1,
        "divergence_basis": {
            "same_name_qonic_archive_count": len(qonic_archives),
            "distinct_sha256_count": len(distinct_hashes),
            "distinct_tool_signature_count": len(tool_signatures),
        },
    }
    write_json(output_path, payload)
    return payload


def _copy_if_present(source: Path, destination: Path) -> None:
    if source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def prepare_third_party_tree(
    project_root: Path,
    report_root: Path,
    manifest: dict[str, Any],
) -> None:
    """Create the current third_party evidence tree from verified local files."""

    root = project_root / "third_party"
    licenses = root / "licenses"
    manifests = root / "manifests"
    source_info = root / "source-information"
    for directory in (licenses, manifests, source_info):
        directory.mkdir(parents=True, exist_ok=True)
    license_sources = {
        project_root / "LICENSE": licenses / "GPL-3.0.txt",
        project_root / "LICENSES" / "ncmdump-MIT.txt": licenses / "MIT-ncmdump.txt",
        project_root
        / "LICENSES"
        / "watchdog-Apache-2.0.txt": licenses / "Apache-2.0-watchdog.txt",
        project_root
        / "LICENSES"
        / "mutagen-GPL-2.0.txt": licenses / "GPL-2.0-mutagen.txt",
        project_root
        / "LICENSES"
        / "PyInstaller-GPL-2.0-with-Bootloader-Exception.txt": (
            licenses / "PyInstaller-GPL-2.0-with-Bootloader-Exception.txt"
        ),
        project_root
        / "LICENSES"
        / "PySide6-LicenseRef-Qt-Commercial.txt": (
            licenses / "PySide6-LicenseRef-Qt-Commercial.txt"
        ),
    }
    for source, destination in license_sources.items():
        _copy_if_present(source, destination)
    for name in (
        "ffmpeg/ffmpeg-files.json",
        "ffmpeg/ffmpeg-asset-comparison.json",
        "ffmpeg/ffmpeg-dependency-inventory.json",
        "ncmdump/ncmdump-files.json",
        "ncmdump/ncmdump-asset-comparison.json",
        "qt/qt-runtime-inventory.json",
        "qt/qt-wheel-verification.json",
        "qt/python-packages.json",
        "release-inventory.json",
    ):
        _copy_if_present(report_root / name, manifests / Path(name).name)
    for name in (
        "ffmpeg/ffmpeg-provenance.json",
        "ncmdump/ncmdump-provenance.json",
        "qt/qt-source-requirements.json",
        "qt/qt-upstream-evidence.json",
    ):
        _copy_if_present(report_root / name, source_info / Path(name).name)
    _copy_if_present(
        project_root
        / "Tools"
        / "compliance"
        / "evidence"
        / "ncmdump-1.5.1-release.json",
        source_info / "ncmdump-1.5.1-release.json",
    )
    _copy_if_present(
        project_root
        / "Tools"
        / "compliance"
        / "evidence"
        / "ffmpeg-8.1.1-gyan-release.json",
        source_info / "ffmpeg-provider" / "ffmpeg-8.1.1-gyan-release.json",
    )
    write_json(root / "THIRD_PARTY_MANIFEST.json", manifest)
    generate_notices(manifest, root / "THIRD_PARTY_NOTICES.md")


def collect_all(
    project_root: Path,
    dist_path: Path,
    output: Path,
    dist_archive: Path | None = None,
) -> dict[str, Any]:
    """Run all collectors and generate the current reports and evidence tree."""

    project_root = project_root.resolve()
    dist_path = dist_path.resolve()
    output = output.resolve()
    if not project_root.is_dir():
        raise ComplianceError(f"项目根目录不存在: {project_root}")
    if not dist_path.is_dir():
        raise ComplianceError(f"发行目录不存在: {dist_path}")
    if dist_archive is not None:
        dist_archive = dist_archive.resolve()
        if not dist_archive.is_file():
            raise ComplianceError(f"发行归档不存在: {dist_archive}")
    output.mkdir(parents=True, exist_ok=True)
    collect_release_inventory(
        project_root,
        dist_path,
        dist_archive,
        output / "release-inventory.json",
    )
    collect_ffmpeg(project_root, dist_path, output / "ffmpeg")
    collect_ncmdump(project_root, dist_path, output / "ncmdump")
    collect_python_packages(project_root, dist_path, output / "qt")
    collect_qt_inventory(project_root, dist_path, output / "qt")
    manifest = generate_manifest(
        project_root,
        dist_path,
        output,
        output / "THIRD_PARTY_MANIFEST.json",
    )
    prepare_third_party_tree(project_root, output, manifest)
    generate_audit_report(
        manifest,
        output,
        project_root / "compliance" / "COMPLIANCE_AUDIT_REPORT.md",
    )
    generate_owner_decisions(
        manifest,
        project_root / "compliance" / "OWNER_DECISIONS.md",
    )
    return manifest


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--dist-path", type=Path, required=True)
    parser.add_argument("--dist-archive", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    """Run the complete compliance collection."""

    args = build_parser().parse_args()
    try:
        manifest = collect_all(
            args.project_root,
            args.dist_path,
            args.output,
            args.dist_archive,
        )
    except (ComplianceError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 3
    if manifest.get("blockers"):
        print(
            f"Collection completed with {len(manifest['blockers'])} blocker(s). "
            "See compliance/COMPLIANCE_AUDIT_REPORT.md."
        )
        return 2
    if manifest.get("warnings"):
        print(
            f"Collection completed with {len(manifest['warnings'])} warning(s)."
        )
        return 1
    print("Collection completed without blockers or warnings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
