"""Assemble a reproducible, recipient-facing Qonic Audio publication candidate.

It consumes a newly built onedir tree and never mutates the frozen authority
package or the source build directory.  The result remains a candidate until
the owner-controlled public-release gates are signed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from verify_qt_lgpl_route import GPL_ONLY_GROUPS, remove_group, scan_gpl_only_presence


EXE_NAME = "Qonic_Audio_v5.0_internal_test.exe"
FFMPEG_SHA256 = "CA2BCCBF1A2A5A379AE484AD127D120CC3E394833B69767694A1E738F2D6BE55"
FFPROBE_SHA256 = "4EC2AC9385AACBAF927B7E8D031291059CEA2E02EE6BFAE0D708F78E1C528251"
FFMPEG_SOURCE_SHA256 = "2B3A9A878B46050CACA71253C1E43F6239DE91C5C5C59DC72F8F2E0306A5C35A"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def tree_sha256(root: Path) -> str:
    """Hash paths and contents, excluding generated runtime evidence only."""

    digest = hashlib.sha256()
    excluded = {"PUBLICATION_CANDIDATE_MANIFEST.json", "logs/runtime.log"}
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.as_posix().lower()):
        relative = path.relative_to(root).as_posix()
        if relative in excluded:
            continue
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256(path)))
    return digest.hexdigest().upper()


def copy_file(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def git_value(project_root: Path, *arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=project_root, text=True, encoding="utf-8").strip()


def write_recipient_materials(root: Path, project_root: Path, commit: str, ffmpeg_source: Path) -> None:
    licenses = root / "LICENSES"
    staged = project_root / "docs" / "compliance" / "staging" / "licenses"
    shutil.copytree(staged, licenses / "Third_Party_Licenses", copy_function=shutil.copy2)
    copy_file(project_root / "docs" / "compliance" / "QT_SOURCE_AVAILABILITY.md", licenses / "QT_SOURCE_AVAILABILITY.md")
    (licenses / "THIRD_PARTY_NOTICES.md").write_text(
        "# Third-party notices for this Qonic Audio publication candidate\n\n"
        "This distribution includes Qt 6.11.1, PySide6 6.11.1 and Shiboken6 6.11.1 "
        "under the Qt for Python Community Edition LGPLv3 route and dynamically loads "
        "their shared libraries. Applicable license texts, Qt attribution and source "
        "availability are in Third_Party_Licenses and QT_SOURCE_AVAILABILITY.md.\n\n"
        "It includes Qonic-maintained FFmpeg 8.1.1 GPL runtime binaries. Complete "
        "corresponding source, build scripts, patches, dependency sources and build "
        "instructions are included in ../Corresponding_Source.\n\n"
        "Additional notices and license texts for Python, OpenSSL, NumPy, Pillow, "
        "Mutagen, watchdog, ncmdump, PyInstaller, libffi and Microsoft VC Runtime are "
        "included in Third_Party_Licenses.\n",
        encoding="utf-8",
    )
    (licenses / "QT_LGPL_NOTICE.md").write_text(
        "# Qt / PySide6 LGPLv3 notice\n\n"
        "Qonic Audio uses Qt 6.11.1, PySide6 6.11.1 and Shiboken6 6.11.1 from the "
        "Qt for Python Community Edition under LGPL-3.0. These components are "
        "distributed as dynamic shared libraries under _internal/PySide6. Qonic does "
        "not impose a Qonic-side signature or hash check that prevents a user from "
        "replacing them with ABI-compatible modified libraries.\n\n"
        "The LGPL-3.0 text, attribution material and exact source availability record "
        "are supplied in this LICENSES directory.\n",
        encoding="utf-8",
    )
    source_dir = root / "Corresponding_Source"
    source_dir.mkdir()
    ffmpeg_destination = source_dir / "qonic-ffmpeg-complete-corresponding-source.tar.gz"
    copy_file(ffmpeg_source, ffmpeg_destination)
    app_source = source_dir / f"qonic-audio-source-{commit[:12]}.tar.gz"
    subprocess.run(
        ["git", "archive", "--format=tar.gz", f"--prefix=Qonic_Audio_Source_{commit[:12]}/", commit, "-o", str(app_source)],
        cwd=project_root,
        check=True,
    )
    with tarfile.open(app_source, "r:gz") as archive:
        forbidden = [
            member.name for member in archive.getmembers()
            if any(part.lower() == "codex_memory" for part in Path(member.name).parts)
        ]
    if forbidden:
        app_source.unlink()
        raise RuntimeError("application source archive contains Codex_memory")
    (source_dir / "SHA256SUMS.txt").write_text(
        f"{sha256(ffmpeg_destination)}  {ffmpeg_destination.name}\n"
        f"{sha256(app_source)}  {app_source.name}\n",
        encoding="ascii",
    )
    (source_dir / "SOURCE_CODE_AVAILABILITY.md").write_text(
        "# Corresponding-source material\n\n"
        f"{app_source.name} is the complete Qonic Audio application source for Git commit {commit}.\n\n"
        f"{ffmpeg_destination.name} is the complete corresponding-source bundle for the shipped "
        "Qonic FFmpeg GPL runtime. It contains the exact FFmpeg and static dependency sources, "
        "configure parameters, build scripts, patches, locks, licenses and rebuilding instructions.\n\n"
        "Qt/PySide6/Shiboken6 exact official source routes and hashes are in "
        "../LICENSES/QT_SOURCE_AVAILABILITY.md.\n",
        encoding="utf-8",
    )


def assemble(args: argparse.Namespace) -> dict[str, object]:
    project_root = args.project_root.resolve()
    source = args.built_onedir.resolve()
    target = args.output.resolve()
    ffmpeg_source = args.ffmpeg_source.resolve()
    if target.exists():
        raise FileExistsError(f"output already exists: {target}")
    if not (source / EXE_NAME).is_file():
        raise FileNotFoundError(f"missing built executable: {source / EXE_NAME}")
    if sha256(ffmpeg_source) != FFMPEG_SOURCE_SHA256:
        raise ValueError("FFmpeg corresponding-source SHA-256 does not match the approved record")
    commit = git_value(project_root, "rev-parse", "HEAD")
    if args.source_commit and args.source_commit.upper() != commit.upper():
        raise ValueError(f"requested source commit {args.source_commit} does not equal HEAD {commit}")
    shutil.copytree(source, target, copy_function=shutil.copy2)
    removed = {group: remove_group(target, group) for group in GPL_ONLY_GROUPS}
    remaining_gpl_only = {name: files for name, files in scan_gpl_only_presence(target).items() if files}
    if remaining_gpl_only:
        raise RuntimeError(f"GPL-only Qt files remain: {remaining_gpl_only}")
    for filename in ("README.md", "CHANGELOG.md", "Known_Issues.md", "EXTERNAL_TEST_GUIDE.md", "TEST_CHECKLIST.md", "Release_Notes_v5.0_Internal_Test.md", "LICENSE", "config.example.json"):
        copy_file(project_root / filename, target / filename)
    copy_file(project_root / "docs" / "compliance" / "PUBLIC_RELEASE_READINESS.md", target / "PUBLIC_RELEASE_READINESS.md")
    copy_file(project_root / "LICENSES" / "README.md", target / "LICENSES" / "README.md")
    copy_file(project_root / "LICENSES" / "FFmpeg-NOTICE.md", target / "LICENSES" / "FFmpeg-NOTICE.md")
    write_recipient_materials(target, project_root, commit, ffmpeg_source)
    ffmpeg = target / "_internal" / "Tools" / "ffmpeg" / "bin" / "ffmpeg.exe"
    ffprobe = target / "_internal" / "Tools" / "ffmpeg" / "bin" / "ffprobe.exe"
    if sha256(ffmpeg) != FFMPEG_SHA256 or sha256(ffprobe) != FFPROBE_SHA256:
        raise RuntimeError("built onedir does not contain the approved Qonic FFmpeg runtime")
    manifest: dict[str, object] = {
        "schema_version": "1.0.0",
        "kind": "PUBLICATION_CANDIDATE",
        "status": "NOT_FOR_PUBLIC_RELEASE_UNTIL_OWNER_GATES_CLOSED",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": commit,
        "source_commit_subject": git_value(project_root, "show", "-s", "--format=%s", commit),
        "executable": EXE_NAME,
        "qt_route": {"license": "LGPL-3.0", "versions": {"Qt": "6.11.1", "PySide6": "6.11.1", "Shiboken6": "6.11.1"}, "gpl_only_groups_removed": {key: len(value) for key, value in removed.items()}},
        "ffmpeg": {"ffmpeg_sha256": sha256(ffmpeg), "ffprobe_sha256": sha256(ffprobe), "corresponding_source": {"file": "Corresponding_Source/qonic-ffmpeg-complete-corresponding-source.tar.gz", "sha256": FFMPEG_SOURCE_SHA256}},
        "application_source": {"file": f"Corresponding_Source/qonic-audio-source-{commit[:12]}.tar.gz", "sha256": sha256(target / "Corresponding_Source" / f"qonic-audio-source-{commit[:12]}.tar.gz")},
        "static_tree_sha256": tree_sha256(target),
    }
    (target / "PUBLICATION_CANDIDATE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--built-onedir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ffmpeg-source", type=Path, required=True)
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    try:
        manifest = assemble(args)
    except (FileExistsError, FileNotFoundError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(f"PASS: assembled {args.output}")
    print(f"static_tree_sha256={manifest['static_tree_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
