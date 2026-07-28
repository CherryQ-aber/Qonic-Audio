"""Collect local ncmdump binary, invocation, provenance, and risk evidence."""

from __future__ import annotations

import argparse
import re
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


NCMDUMP_PATTERNS = (
    "ncmdump.exe",
    "ncmdump.dll",
    "libncmdump.dll",
    "tag.dll",
    "taglib*.dll",
)


def _select_ncmdump(paths: list[Path], dist_path: Path) -> Path | None:
    candidates = [path for path in paths if path.name.lower() == "ncmdump.exe"]
    in_dist = [path for path in candidates if is_relative_to(path, dist_path)]
    preferred = [
        path
        for path in in_dist
        if "tools/ncmdump/ncmdump.exe" in path.as_posix().lower()
    ]
    return (preferred or in_dist or candidates or [None])[0]


def collect_ncmdump(
    project_root: Path,
    dist_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Collect ncmdump evidence and write the required report files."""

    project_root = project_root.resolve()
    dist_path = dist_path.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = find_named_files(project_root, dist_path, NCMDUMP_PATTERNS)
    invocation_files = source_contains(project_root, "NCMDUMP_PATH")
    records = []
    selected = _select_ncmdump(paths, dist_path)
    for path in paths:
        pe = pe_metadata(path)
        data = path.read_bytes() if path.stat().st_size <= 20 * 1024 * 1024 else b""
        taglib_strings = data.lower().count(b"taglib")
        records.append(
            {
                "path": display_path(path, project_root, dist_path),
                "name": path.name,
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
                "pe": pe,
                "in_distribution": is_relative_to(path, dist_path),
                "actually_called": path.name.lower() == "ncmdump.exe" and bool(invocation_files),
                "replaceable": is_relative_to(path, dist_path),
                "call_evidence": invocation_files if path.name.lower() == "ncmdump.exe" else [],
                "taglib_string_occurrences": taglib_strings,
            }
        )

    failures: list[str] = []
    version_result = None
    if selected:
        try:
            version_result = run_command(
                [selected, "-v"],
                cwd=selected.parent,
                project_root=project_root,
            )
            if version_result.returncode != 0:
                version_result = run_command(
                    [selected, "--version"],
                    cwd=selected.parent,
                    project_root=project_root,
                )
        except ComplianceError as exc:
            failures.append(str(exc))
    else:
        failures.append("未找到 ncmdump.exe")
    version_text = version_result.combined_output if version_result else ""
    version_match = re.search(r"ncmdump version\s+([^\s]+)", version_text, re.IGNORECASE)
    detected_version = version_match.group(1) if version_match else None
    evidence_path = (
        Path(__file__).resolve().parent
        / "evidence"
        / f"ncmdump-{detected_version or 'UNKNOWN'}-release.json"
    )
    upstream = load_json(evidence_path) if evidence_path.is_file() else {}
    asset = upstream.get("asset", {})
    source = upstream.get("source", {})
    windows_build = upstream.get("windows_build", {})
    comparison_path = output_dir / "ncmdump-asset-comparison.json"
    comparison = load_json(comparison_path) if comparison_path.is_file() else {}
    selected_record = next(
        (
            record
            for record in records
            if selected
            and record["path"] == display_path(selected, project_root, dist_path)
        ),
        None,
    )
    imported_names = {
        name.lower()
        for name in (selected_record or {}).get("pe", {}).get("imports", [])
    }
    contains_taglib = bool((selected_record or {}).get("taglib_string_occurrences"))
    taglib_dll_imported = any("tag" in name for name in imported_names)
    taglib_linkage_inference = (
        "STATIC_LINK_CANDIDATE"
        if contains_taglib and not taglib_dll_imported
        else "DYNAMIC_LINK_CANDIDATE"
        if taglib_dll_imported
        else "UNKNOWN"
    )
    source_path = project_root / str(source.get("local_path", ""))
    asset_path = project_root / str(asset.get("local_path", ""))
    asset_expected_sha256 = (
        str(asset.get("digest", "")).removeprefix("sha256:").upper() or None
    )
    asset_archive_verified = bool(
        asset.get("local_path")
        and asset_path.is_file()
        and asset_path.stat().st_size == asset.get("size")
        and sha256_file(asset_path) == asset_expected_sha256
    )
    source_verified = bool(
        source.get("local_path")
        and source_path.is_file()
        and source_path.stat().st_size == source.get("size")
        and sha256_file(source_path) == source.get("sha256")
    )
    build_materials = []
    vcpkg_path = project_root / str(
        windows_build.get("vcpkg_source_local_path", "")
    )
    if windows_build.get("vcpkg_source_local_path"):
        build_materials.append(
            {
                "name": "vcpkg",
                "version": windows_build.get("vcpkg_baseline"),
                "local_path": windows_build.get("vcpkg_source_local_path"),
                "sha256": windows_build.get("vcpkg_source_sha256"),
                "verified": (
                    vcpkg_path.is_file()
                    and sha256_file(vcpkg_path)
                    == windows_build.get("vcpkg_source_sha256")
                ),
            }
        )
    for dependency in windows_build.get("dependencies", []):
        dependency_path = project_root / str(
            dependency.get("source_local_path", "")
        )
        build_materials.append(
            {
                "name": dependency.get("name"),
                "version": dependency.get("version"),
                "license": dependency.get("license"),
                "local_path": dependency.get("source_local_path"),
                "source_url": dependency.get("source_url"),
                "sha256": dependency.get("source_sha256"),
                "sha512": dependency.get("source_sha512"),
                "verified": bool(
                    dependency.get("source_local_path")
                    and dependency_path.is_file()
                    and sha256_file(dependency_path)
                    == dependency.get("source_sha256")
                ),
            }
        )
    build_materials_closed = bool(build_materials) and all(
        item["verified"] for item in build_materials
    )
    provenance = {
        "selected_binary": (
            display_path(selected, project_root, dist_path) if selected else None
        ),
        "detected_version": detected_version,
        "upstream_repository": "https://github.com/taurusxin/ncmdump",
        "upstream_release": upstream.get("tag"),
        "upstream_commit": upstream.get("tag_commit"),
        "upstream_asset": asset.get("name"),
        "upstream_asset_sha256": asset_expected_sha256,
        "upstream_asset_local": asset.get("local_path"),
        "upstream_asset_archive_verified": asset_archive_verified,
        "source_package": source.get("url"),
        "source_archive_local": source.get("local_path"),
        "source_sha256": source.get("sha256"),
        "source_archive_verified": source_verified,
        "local_binary_sha256": (selected_record or {}).get("sha256"),
        "byte_identical_to_upstream": comparison.get("byte_identical_to_upstream"),
        "asset_comparison_status": comparison.get("status", "NOT_PERFORMED"),
        "provided_asset": comparison.get("asset_file"),
        "provided_asset_sha256": comparison.get("asset_sha256"),
        "provided_asset_members": comparison.get("asset_members", []),
        "usage_mode": "subprocess",
        "build_configuration": windows_build.get("configuration"),
        "build_workflow": windows_build.get("workflow_path"),
        "vcpkg_baseline": windows_build.get("vcpkg_baseline"),
        "build_materials": build_materials,
        "build_materials_closed": build_materials_closed,
        "taglib_linkage": taglib_linkage_inference,
        "taglib_linkage_basis": {
            "embedded_taglib_strings": contains_taglib,
            "imported_taglib_dll": taglib_dll_imported,
            "note": "这是 PE import 与静态字符串推断，不是链接器构建记录。",
        },
        "evidence_files": [
            "ncmdump-version.txt",
            "ncmdump-files.json",
            "tools/compliance/evidence/ncmdump-1.5.1-release.json",
        ],
        "unresolved_questions": [
            "官方 GitHub Actions 的具体 runner 镜像版本与编译器补丁版本未在 Release 元数据中固定",
        ],
    }
    if provenance["asset_comparison_status"] != "BYTE_IDENTICAL":
        provenance["unresolved_questions"].insert(
            0,
            "本地 ncmdump.exe 是否与官方 CLI Windows amd64 Release 资产解压后的文件逐字节一致",
        )
    if not source_verified:
        provenance["unresolved_questions"].insert(
            0, "ncmdump 精确 commit 源码归档缺失或 SHA-256 校验失败"
        )
    if not build_materials_closed:
        provenance["unresolved_questions"].append(
            "ncmdump Windows 静态依赖源码或 vcpkg 构建元数据缺失"
        )
    payload = {
        "selected": provenance["selected_binary"],
        "files": records,
        "duplicate_groups": duplicate_groups(records),
        "invocation_mode": "subprocess" if invocation_files else "UNKNOWN",
        "invocation_evidence": invocation_files,
        "failures": failures,
    }
    write_text(output_dir / "ncmdump-version.txt", version_text or "未取得版本输出。\n")
    write_json(output_dir / "ncmdump-files.json", payload)
    write_json(output_dir / "ncmdump-provenance.json", provenance)
    if not comparison:
        write_text(
            output_dir / "ncmdump-asset-comparison.md",
            "\n".join(
                [
                    "# ncmdump Asset Comparison",
                    "",
                    "- 状态：`NOT_PERFORMED`。",
                    f"- 本地文件 SHA-256：`{provenance['local_binary_sha256'] or 'UNKNOWN'}`。",
                    f"- 官方资产候选：`{provenance['upstream_asset'] or 'UNKNOWN'}`。",
                    f"- 官方资产 SHA-256：`{provenance['upstream_asset_sha256'] or 'UNKNOWN'}`。",
                    "- 事实：尚未提供可用于比对的官方 CLI Release ZIP。",
                    "- 下一步：运行 `verify_ncmdump_asset.py --local-file ... --asset-file ... --output ...`。",
                ]
            )
            + "\n",
        )
    risk_lines = [
        "# ncmdump Risk Analysis",
        "",
        f"- 事实：自报版本为 `{detected_version or 'UNKNOWN'}`。",
        "- 事实：项目通过 `subprocess` 调用独立 `ncmdump.exe`，未发现 ncmdump DLL 调用路径。",
        f"- 推断：TagLib 链接状态为 `{taglib_linkage_inference}`；依据有限，不能当作构建事实。",
        f"- 构建证据：`{provenance['build_configuration'] or 'UNKNOWN'}`。",
        f"- 精确源码：commit `{provenance['upstream_commit'] or 'UNKNOWN'}`，SHA-256 `{provenance['source_sha256'] or 'UNKNOWN'}`，verified=`{source_verified}`。",
        f"- 静态依赖材料：vcpkg baseline `{provenance['vcpkg_baseline'] or 'UNKNOWN'}`，closed=`{build_materials_closed}`。",
    ]
    comparison_status = provenance["asset_comparison_status"]
    if comparison_status == "ASSET_TYPE_MISMATCH":
        risk_lines.extend(
            [
                "- 阻断：已提供的官方资产是 `libncmdump.dll` 库包，不含待比对的 `ncmdump.exe`，不能据此声明一致。",
                "- 所有者约束：已停止 ncmdump 分支；在取得正确 CLI 资产并完成比对前，不替换当前 EXE。",
            ]
        )
    elif comparison_status == "BINARY_MISMATCH":
        risk_lines.extend(
            [
                "- 阻断：本地 ncmdump.exe 与官方 CLI 资产逐字节不一致。",
                "- 所有者约束：不得自行替换，必须等待项目所有者批准。",
            ]
        )
    elif comparison_status == "BYTE_IDENTICAL":
        risk_lines.append("- 已闭合：本地 ncmdump.exe 与官方 CLI 资产逐字节一致。")
    else:
        risk_lines.extend(
            [
                "- 风险：官方 CLI Release ZIP 尚未完成逐字节比对，本地二进制来源链未闭合。",
                "- 下一步：取得正确 CLI 资产后执行比对；若不一致则停止并等待批准。",
            ]
        )
    if failures:
        risk_lines.extend(["", "## Collection Failures", *[f"- {item}" for item in failures]])
    write_text(output_dir / "ncmdump-risk-analysis.md", "\n".join(risk_lines) + "\n")
    return {"files": payload, "provenance": provenance, "version": version_text}


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--dist-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    """Run ncmdump evidence collection."""

    args = build_parser().parse_args()
    collect_ncmdump(args.project_root, args.dist_path, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
