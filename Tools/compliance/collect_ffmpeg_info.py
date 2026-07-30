"""Collect local FFmpeg binary, build, provenance, and risk evidence."""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from common import (
    ComplianceError,
    display_path,
    duplicate_groups,
    find_named_files,
    is_relative_to,
    load_json,
    pe_metadata,
    run_command,
    sha256_file,
    source_contains,
    write_json,
    write_text,
)


FFMPEG_PATTERNS = (
    "ffmpeg.exe",
    "ffprobe.exe",
    "ffplay.exe",
    "avcodec*.dll",
    "avformat*.dll",
    "avutil*.dll",
    "swresample*.dll",
    "swscale*.dll",
)
TRACKED_FLAGS = (
    "--enable-gpl",
    "--enable-version3",
    "--enable-nonfree",
    "--enable-libx264",
    "--enable-libx265",
    "--enable-libxvid",
    "--enable-libfdk-aac",
    "--enable-openssl",
    "--enable-gnutls",
    "--enable-libvmaf",
    "--enable-libaom",
    "--enable-libdav1d",
    "--enable-libmp3lame",
    "--enable-libopus",
    "--enable-libvorbis",
    "--enable-libwebp",
    "--enable-libass",
    "--enable-shared",
    "--enable-static",
    "--disable-debug",
)
VERSION_NAME_ALIASES = {
    "--enable-libaribcaption": "aribcaption",
    "--enable-libcdio": "libcdio-paranoia",
    "--enable-libflite": "flite",
    "--enable-libgme": "libgme",
    "--enable-libilbc": "libilbc",
    "--enable-libjxl": "libjxl",
    "--enable-libmp3lame": "lame",
    "--enable-liboapv": "openapv",
    "--enable-libopencore-amrnb": "libopencore-amrnb",
    "--enable-libopencore-amrwb": "libopencore-amrwb",
    "--enable-libopenmpt": "openmpt",
    "--enable-libplacebo": "libplacebo",
    "--enable-libsoxr": "libsoxr",
    "--enable-libssh": "libssh",
    "--enable-libsvtav1": "SVT-AV1",
    "--enable-libsvtjpegxs": "SVT-JPEG-XS",
    "--enable-libtheora": "libtheora",
    "--enable-libvo-amrwbenc": "vo-amrwbenc",
    "--enable-libvpl": "VPL",
    "--enable-libwebp": "libwebp",
    "--enable-libzmq": "zeromq",
    "--enable-ladspa": "ladspa-sdk",
    "--enable-openal": "openal-soft",
    "--enable-sdl2": "SDL",
    "--enable-vulkan": "vulkan-loader",
}


def _find_seven_zip() -> Path | None:
    """Locate 7-Zip without requiring it to be on PATH."""

    command = shutil.which("7z") or shutil.which("7z.exe")
    if command:
        return Path(command)
    candidate = Path(r"C:\Program Files\7-Zip\7z.exe")
    return candidate if candidate.is_file() else None


def read_package_readme(
    project_root: Path,
    metadata: dict[str, Any],
) -> tuple[bytes, str | None]:
    """Read the exact package README from the retained Gyan asset."""

    asset = metadata.get("asset", {})
    relative_path = asset.get("local_path")
    if not relative_path:
        return b"", "上游证据未记录 Gyan 资产本地路径"
    archive = project_root / str(relative_path)
    seven_zip = _find_seven_zip()
    if not archive.is_file():
        return b"", f"Gyan 资产不存在: {relative_path}"
    if not seven_zip:
        return b"", "未找到 7-Zip，无法读取 Gyan 包内 README"
    expected_hash = str(asset.get("sha256", "")).upper()
    if expected_hash and sha256_file(archive) != expected_hash:
        return b"", "Gyan 资产 SHA-256 与冻结证据不一致"
    member = f"{archive.stem}/README.txt"
    completed = subprocess.run(
        [str(seven_zip), "e", "-so", "-bd", "-y", str(archive), member],
        capture_output=True,
        check=False,
        timeout=120,
    )
    if completed.returncode != 0:
        return (
            b"",
            "无法读取 Gyan 包内 README: "
            + completed.stderr.decode("utf-8", errors="replace").strip(),
        )
    return completed.stdout, None


def parse_package_dependency_versions(text: str) -> dict[str, str]:
    """Parse the external-library version table from a Gyan package README."""

    marker = "release-full external libraries' versions:"
    _, separator, section = text.partition(marker)
    if not separator:
        return {}
    versions: dict[str, str] = {}
    for raw_line in section.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(r"^(\S+)\s+(.+)$", line)
        if match:
            versions[match.group(1)] = match.group(2).strip()
    return versions


def match_configure_flags_to_versions(
    flags: list[str],
    versions: dict[str, str],
) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Match FFmpeg configure flags to package README version records."""

    matches: dict[str, dict[str, str]] = {}
    missing: list[str] = []
    for flag in flags:
        candidate = VERSION_NAME_ALIASES.get(flag)
        if not candidate:
            candidate = flag.removeprefix("--enable-")
            if candidate.startswith("lib"):
                candidate = candidate[3:]
        if candidate in versions:
            matches[flag] = {
                "dependency": candidate,
                "version": versions[candidate],
            }
        else:
            missing.append(flag)
    return matches, missing


def parse_build_configuration(text: str) -> dict[str, Any]:
    """Parse relevant configure switches and classify an FFmpeg build."""

    flags = sorted(set(re.findall(r"--(?:enable|disable)-[A-Za-z0-9_.+-]+", text)))
    tracked = {flag: flag in flags for flag in TRACKED_FLAGS}
    if tracked["--enable-nonfree"]:
        classification = "FFmpeg-NONFREE-BLOCKER"
    elif tracked["--enable-gpl"]:
        classification = "FFmpeg-GPL-CANDIDATE"
    elif flags:
        classification = "FFmpeg-LGPL-CANDIDATE"
    else:
        classification = "FFmpeg-UNKNOWN"
    version_match = re.search(r"\bffmpeg version\s+([^\s]+)", text, re.IGNORECASE)
    compiler_match = re.search(r"\bbuilt with\s+(.+)", text, re.IGNORECASE)
    return {
        "classification": classification,
        "flags": flags,
        "tracked_flags": tracked,
        "detected_version": version_match.group(1) if version_match else None,
        "compiler": compiler_match.group(1).strip() if compiler_match else None,
    }


def _select_binary(paths: list[Path], name: str, dist_path: Path) -> Path | None:
    candidates = [path for path in paths if path.name.lower() == name.lower()]
    in_dist = [path for path in candidates if is_relative_to(path, dist_path)]
    preferred = [
        path
        for path in in_dist
        if "tools/ffmpeg/bin" in path.as_posix().lower()
    ]
    return (preferred or in_dist or candidates or [None])[0]


def collect_ffmpeg(
    project_root: Path,
    dist_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Collect FFmpeg evidence and write the required report files."""

    project_root = project_root.resolve()
    dist_path = dist_path.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = find_named_files(project_root, dist_path, FFMPEG_PATTERNS)
    call_evidence = {
        "ffmpeg.exe": source_contains(project_root, "FFMPEG_PATH"),
        "ffprobe.exe": source_contains(project_root, "ffprobe.exe"),
        "ffplay.exe": source_contains(project_root, "ffplay.exe"),
    }
    records = []
    for path in paths:
        name = path.name.lower()
        record = {
            "path": display_path(path, project_root, dist_path),
            "name": path.name,
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
            "pe": pe_metadata(path),
            "in_distribution": is_relative_to(path, dist_path),
            "actually_called": bool(call_evidence.get(name)) and name != "ffplay.exe",
            "replaceable": is_relative_to(path, dist_path),
            "call_evidence": call_evidence.get(name, []),
        }
        records.append(record)
    selected_ffmpeg = _select_binary(paths, "ffmpeg.exe", dist_path)
    selected_ffprobe = _select_binary(paths, "ffprobe.exe", dist_path)
    version_result = None
    buildconf_result = None
    ffprobe_result = None
    failures: list[str] = []
    if selected_ffmpeg:
        try:
            version_result = run_command(
                [selected_ffmpeg, "-version"],
                cwd=selected_ffmpeg.parent,
                project_root=project_root,
            )
            buildconf_result = run_command(
                [selected_ffmpeg, "-buildconf"],
                cwd=selected_ffmpeg.parent,
                project_root=project_root,
            )
        except ComplianceError as exc:
            failures.append(str(exc))
    else:
        failures.append("未找到 ffmpeg.exe")
    if selected_ffprobe:
        try:
            ffprobe_result = run_command(
                [selected_ffprobe, "-version"],
                cwd=selected_ffprobe.parent,
                project_root=project_root,
            )
        except ComplianceError as exc:
            failures.append(str(exc))
    else:
        failures.append("实际审计发行目录未找到 ffprobe.exe")

    version_text = version_result.combined_output if version_result else ""
    buildconf_text = buildconf_result.combined_output if buildconf_result else ""
    ffprobe_text = ffprobe_result.combined_output if ffprobe_result else ""
    parsed = parse_build_configuration("\n".join((version_text, buildconf_text)))
    provider = (
        "gyan.dev"
        if "gyan.dev" in version_text.lower()
        else "UNKNOWN"
    )
    upstream_metadata_path = (
        project_root
        / "Tools"
        / "compliance"
        / "evidence"
        / "ffmpeg-8.1.1-gyan-release.json"
    )
    upstream_metadata = (
        load_json(upstream_metadata_path)
        if upstream_metadata_path.is_file()
        else {}
    )
    package_readme_bytes, package_readme_error = read_package_readme(
        project_root, upstream_metadata
    )
    package_readme_text = package_readme_bytes.decode(
        "utf-8", errors="replace"
    )
    package_dependency_versions = parse_package_dependency_versions(
        package_readme_text
    )
    package_readme_hash = (
        hashlib.sha256(package_readme_bytes).hexdigest().upper()
        if package_readme_bytes
        else None
    )
    provider_snapshots = []
    for snapshot in upstream_metadata.get("provider_evidence_snapshots", []):
        snapshot_path = project_root / str(snapshot.get("local_path", ""))
        expected_hash = str(snapshot.get("sha256", "")).upper()
        provider_snapshots.append(
            {
                **snapshot,
                "verified": bool(
                    snapshot.get("local_path")
                    and snapshot_path.is_file()
                    and sha256_file(snapshot_path) == expected_hash
                ),
            }
        )
    provider_evidence_closed = bool(provider_snapshots) and all(
        item["verified"] for item in provider_snapshots
    )
    provider_statements = upstream_metadata.get(
        "provider_public_statements", {}
    )
    comparison_path = output_dir / "ffmpeg-asset-comparison.json"
    comparison = load_json(comparison_path) if comparison_path.is_file() else {}
    source_metadata = upstream_metadata.get("ffmpeg_source", {})
    source_archive = (
        project_root
        / "third_party"
        / "source-archives"
        / "ffmpeg"
        / str(source_metadata.get("archive_name", ""))
    )
    source_archive_hash = (
        sha256_file(source_archive)
        if source_metadata.get("archive_name") and source_archive.is_file()
        else None
    )
    source_core_closed = bool(source_archive_hash) and source_archive_hash == str(
        source_metadata.get("archive_sha256", "")
    ).upper()
    binary_asset_closed = comparison.get("binary_identity_verified") is True
    provider_build_scripts_present = upstream_metadata.get(
        "provider_build_scripts_present"
    ) is True
    dependency_sources_closed = False
    exact_source_closed = (
        binary_asset_closed
        and source_core_closed
        and provider_build_scripts_present
        and dependency_sources_closed
    )
    external_library_flags = sorted(
        flag
        for flag in parsed["flags"]
        if flag.startswith("--enable-lib")
        or flag
        in {
            "--enable-cairo",
            "--enable-fontconfig",
            "--enable-frei0r",
            "--enable-gnutls",
            "--enable-ladspa",
            "--enable-openal",
            "--enable-sdl2",
            "--enable-vulkan",
        }
    )
    versioned_configure_flags, configure_flags_without_versions = (
        match_configure_flags_to_versions(
            external_library_flags,
            package_dependency_versions,
        )
    )
    provenance = {
        "selected_binary": (
            display_path(selected_ffmpeg, project_root, dist_path)
            if selected_ffmpeg
            else None
        ),
        "selected_ffprobe": (
            display_path(selected_ffprobe, project_root, dist_path)
            if selected_ffprobe
            else None
        ),
        "detected_version": parsed["detected_version"],
        "build_provider": provider,
        "provider_page": (
            "https://www.gyan.dev/ffmpeg/builds/" if provider == "gyan.dev" else None
        ),
        "upstream_repository": "https://github.com/FFmpeg/FFmpeg",
        "upstream_commit": source_metadata.get("commit"),
        "upstream_release": upstream_metadata.get("provider_release_tag"),
        "upstream_asset": upstream_metadata.get("asset", {}).get("name"),
        "upstream_asset_sha256": upstream_metadata.get("asset", {}).get("sha256"),
        "upstream_asset_url": upstream_metadata.get("asset", {}).get("url"),
        "source_package": source_metadata.get("archive_url"),
        "source_archive_local": (
            display_path(source_archive, project_root)
            if source_archive.is_file()
            else None
        ),
        "source_sha256": source_archive_hash,
        "source_core_closed": source_core_closed,
        "binary_asset_closed": binary_asset_closed,
        "byte_identical_to_upstream": comparison.get(
            "binary_identity_verified"
        ),
        "asset_comparison_status": comparison.get("status", "NOT_PERFORMED"),
        "provider_repository": upstream_metadata.get("provider_repository"),
        "provider_release_commit": upstream_metadata.get(
            "provider_release_commit"
        ),
        "provider_build_scripts_present": provider_build_scripts_present,
        "provider_build_environment": provider_statements.get(
            "build_environment"
        ),
        "provider_script_guidance": provider_statements.get("script_guidance"),
        "provider_dependency_versioning_statement": provider_statements.get(
            "dependency_versioning"
        ),
        "provider_evidence_snapshots": provider_snapshots,
        "provider_evidence_closed": provider_evidence_closed,
        "build_scripts_status": (
            "PUBLISHED"
            if provider_build_scripts_present
            else "NOT_PUBLISHED_IN_PROVIDER_TAG"
        ),
        "patch_set_status": "NOT_PUBLISHED",
        "package_readme_sha256": package_readme_hash,
        "package_readme_member": (
            f"{Path(str(upstream_metadata.get('asset', {}).get('name', ''))).stem}/README.txt"
            if package_readme_bytes
            else None
        ),
        "package_dependency_versions_recovered": bool(
            package_dependency_versions
        ),
        "package_dependency_version_count": len(package_dependency_versions),
        "configure_dependency_flag_count": len(external_library_flags),
        "configure_dependency_flags_with_versions": len(
            versioned_configure_flags
        ),
        "configure_dependency_flags_without_versions": (
            configure_flags_without_versions
        ),
        "dependency_sources_closed": dependency_sources_closed,
        "exact_source_closed": exact_source_closed,
        "classification": parsed["classification"],
        "compiler": parsed["compiler"],
        "evidence_basis": [
            "ffmpeg -version",
            "ffmpeg -buildconf",
            "local SHA-256",
            "project and distribution scan",
            "Gyan GitHub Release API metadata",
            "official Gyan asset byte comparison",
            "FFmpeg exact commit source archive",
            "Gyan provider tag tree inspection",
            "Gyan package README external-library version table",
            "Gyan public issue statements about build environment and script guidance",
        ],
        "unresolved_questions": [
            "Gyan 未公开生成 8.1.1 资产所用的精确脚本 revision、本地修改和补丁集",
            "包内 README 可恢复部分依赖版本，但未随资产发布全部静态依赖的对应源码归档与源码哈希",
            "部分依赖使用 rolling git 描述或 latest 标记，无法仅凭 README 固定完整源码身份",
        ],
    }
    is_qonic_self_build = (
        "--prefix=/opt/qonic" in buildconf_text
        and "--disable-everything" in buildconf_text
        and "--disable-nonfree" in buildconf_text
    )
    if is_qonic_self_build:
        self_build_report_dir = output_dir.parent / "ffmpeg-self-build"
        readiness_path = self_build_report_dir / "b5-replacement-readiness.json"
        final_path = self_build_report_dir / "b5-final-release-verification.json"
        source_index_path = (
            project_root
            / "third_party"
            / "ffmpeg-build"
            / "output"
            / "candidate"
            / "SOURCE_INDEX.json"
        )
        readiness = load_json(readiness_path) if readiness_path.is_file() else {}
        final = load_json(final_path) if final_path.is_file() else {}
        source_index = load_json(source_index_path) if source_index_path.is_file() else {}
        ffmpeg_source = next(
            (
                item
                for item in source_index.get("sources", [])
                if item.get("name") == "ffmpeg"
            ),
            {},
        )
        expected_binaries = {
            "ffmpeg": "CA2BCCBF1A2A5A379AE484AD127D120CC3E394833B69767694A1E738F2D6BE55",
            "ffprobe": "4EC2AC9385AACBAF927B7E8D031291059CEA2E02EE6BFAE0D708F78E1C528251",
        }
        binaries_match = bool(
            selected_ffmpeg
            and selected_ffprobe
            and sha256_file(selected_ffmpeg) == expected_binaries["ffmpeg"]
            and sha256_file(selected_ffprobe) == expected_binaries["ffprobe"]
        )
        source_record = readiness.get("corresponding_source", {})
        source_path = project_root / str(source_record.get("path", ""))
        source_closed = bool(
            source_path.is_file()
            and sha256_file(source_path) == str(source_record.get("sha256", "")).upper()
            and readiness.get("technical_checks", {}).get(
                "corresponding_source_contents_complete"
            )
            is True
        )
        final_verified = final.get("status") == "PASS"
        provenance.update(
            {
                "build_provider": "Qonic controlled self-build",
                "provider_page": None,
                "upstream_commit": ffmpeg_source.get("commit"),
                "upstream_release": ffmpeg_source.get("version"),
                "upstream_asset": None,
                "upstream_asset_sha256": None,
                "upstream_asset_url": None,
                "source_package": source_record.get("path"),
                "source_archive_local": source_record.get("path"),
                "source_sha256": source_record.get("sha256"),
                "source_core_closed": source_closed,
                "binary_asset_closed": binaries_match,
                "byte_identical_to_upstream": None,
                "asset_comparison_status": "QONIC_B5_FORMAL_RUNTIME_MATCHES_APPROVED_CANDIDATE",
                "provider_repository": None,
                "provider_release_commit": None,
                "provider_build_scripts_present": True,
                "provider_build_environment": {
                    "statement": "fixed Docker Desktop linux/amd64 build environment"
                },
                "provider_script_guidance": "third_party/ffmpeg-build/build.ps1",
                "provider_dependency_versioning_statement": "seven exact source archives and SHA-256 lock",
                "provider_evidence_snapshots": [],
                "provider_evidence_closed": True,
                "build_scripts_status": "QONIC_LOCKED_AND_ARCHIVED",
                "patch_set_status": "ARCHIVED_EMPTY_PATCH_SET",
                "package_readme_sha256": None,
                "package_readme_member": None,
                "package_dependency_versions_recovered": True,
                "package_dependency_version_count": len(source_index.get("sources", [])),
                "configure_dependency_flag_count": len(external_library_flags),
                "configure_dependency_flags_with_versions": len(external_library_flags),
                "configure_dependency_flags_without_versions": [],
                "dependency_sources_closed": source_closed,
                "exact_source_closed": binaries_match and source_closed and final_verified,
                "evidence_basis": [
                    "formal ffmpeg/ffprobe SHA-256 against approved candidate",
                    "B5 owner approval and formal replacement record",
                    "B5 final release verification",
                    "Corresponding Source content verification",
                    "locked exact sources, configuration, patches, scripts and license texts",
                ],
                "unresolved_questions": [],
            }
        )
    payload = {
        "selected": provenance["selected_binary"],
        "files": records,
        "duplicate_groups": duplicate_groups(records),
        "configuration": parsed,
        "failures": failures,
    }
    write_text(output_dir / "ffmpeg-version.txt", version_text or "未取得版本输出。\n")
    write_text(
        output_dir / "ffmpeg-buildconf.txt",
        buildconf_text or "未取得构建配置输出。\n",
    )
    if package_readme_bytes:
        (output_dir / "ffmpeg-package-README.txt").write_bytes(
            package_readme_bytes
        )
    elif package_readme_error:
        failures.append(package_readme_error)
    if ffprobe_text:
        write_text(output_dir / "ffprobe-version.txt", ffprobe_text)
    write_json(output_dir / "ffmpeg-files.json", payload)
    write_json(output_dir / "ffmpeg-provenance.json", provenance)
    write_json(
        output_dir / "ffmpeg-dependency-inventory.json",
        {
            "configuration_source": "ffmpeg -buildconf",
            "external_library_flags": external_library_flags,
            "package_readme_source": "ffmpeg-8.1.1-full_build/README.txt",
            "package_readme_sha256": package_readme_hash,
            "package_dependency_versions_recovered": bool(
                package_dependency_versions
            ),
            "package_dependency_version_count": len(
                package_dependency_versions
            ),
            "package_dependency_versions": package_dependency_versions,
            "configure_flag_version_evidence": versioned_configure_flags,
            "configure_flags_without_package_versions": (
                configure_flags_without_versions
            ),
            "configure_flag_version_coverage": {
                "matched": len(versioned_configure_flags),
                "total": len(external_library_flags),
            },
            "exact_versions_available": False,
            "corresponding_source_archives_closed": False,
            "provider_build_scripts_present": provider_build_scripts_present,
            "provider_build_environment": provider_statements.get(
                "build_environment"
            ),
            "provider_script_guidance": provider_statements.get(
                "script_guidance"
            ),
            "unresolved": provenance["unresolved_questions"],
        },
    )
    risk_lines = [
        "# FFmpeg Risk Analysis",
        "",
        f"- 事实：技术分类为 `{parsed['classification']}`。",
        f"- 事实：构建提供者线索为 `{provider}`。",
        f"- 事实：`--enable-gpl` = `{parsed['tracked_flags']['--enable-gpl']}`。",
        f"- 事实：`--enable-version3` = `{parsed['tracked_flags']['--enable-version3']}`。",
        f"- 事实：`--enable-nonfree` = `{parsed['tracked_flags']['--enable-nonfree']}`。",
        "- 推断：当前静态 full build 应按 GPLv3 候选路线继续审核；这不是法律结论。",
        f"- 事实：官方 Gyan 资产与发行 ffmpeg/ffprobe 逐字节一致 = `{binary_asset_closed}`。",
        f"- 事实：FFmpeg commit 源码归档及 SHA-256 已闭合 = `{source_core_closed}`。",
        f"- 事实：包内 README 已恢复 `{len(package_dependency_versions)}` 条外部库版本记录。",
        f"- 事实：提供者公开确认的环境为 `{(provider_statements.get('build_environment') or {}).get('statement', 'UNKNOWN')}`。",
        "- 事实：提供者曾指向 media-autobuild_suite 作为复现候选，但没有声明 8.1.1 使用的精确脚本 revision。",
        "- 事实：项目所有者已决定保留当前 Gyan GPL 构建，禁止未经再次批准替换二进制。",
        "- 阻塞：精确构建脚本 revision、本地修改、补丁集及全部静态依赖对应源码仍未发布；不能将完整构建链标记为已闭合。",
        "- 建议：向构建提供者索取 8.1.1 对应脚本快照、补丁和依赖源码包；MABS 只能作为复现候选，不能冒充原构建证据。",
    ]
    if is_qonic_self_build:
        risk_lines = [
            "# FFmpeg Risk Analysis",
            "",
            "- 事实：正式运行时与获批 Qonic 候选二进制 SHA-256 一致。",
            "- 事实：构建使用 GPL/version3，`--enable-nonfree` 未启用。",
            "- 事实：Corresponding Source 包含 FFmpeg、Rubber Band、全部静态依赖源码、锁文件、配置、脚本、补丁目录、测试和许可证材料。",
            "- 事实：B5 最终 onedir、归档、三个 packaged QML smoke 和完整回归已验证。",
            "- 边界：该二进制仅是 Qonic Audio Converter Audio Runtime；未来视频功能必须使用独立受控运行时或重新生成并审核的新构建。",
        ]
    if failures:
        risk_lines.extend(["", "## Collection Failures", *[f"- {item}" for item in failures]])
    write_text(output_dir / "ffmpeg-risk-analysis.md", "\n".join(risk_lines) + "\n")
    return {"files": payload, "provenance": provenance, "version": version_text}


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--dist-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    """Run FFmpeg evidence collection."""

    args = build_parser().parse_args()
    collect_ffmpeg(args.project_root, args.dist_path, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
