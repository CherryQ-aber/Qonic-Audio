"""Safely compare the distributed ncmdump.exe with an official Release ZIP."""

from __future__ import annotations

import argparse
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from common import ComplianceError, load_json, pe_metadata, sha256_file, write_json, write_text


def _validated_member_path(root: Path, member: zipfile.ZipInfo) -> Path:
    normalized = member.filename.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or ".." in pure.parts:
        raise ComplianceError(f"ZIP 路径穿越被拒绝: {member.filename}")
    if pure.parts and ":" in pure.parts[0]:
        raise ComplianceError(f"ZIP 驱动器路径被拒绝: {member.filename}")
    mode = (member.external_attr >> 16) & 0o170000
    if mode == 0o120000:
        raise ComplianceError(f"ZIP 符号链接被拒绝: {member.filename}")
    destination = root.joinpath(*pure.parts).resolve()
    try:
        destination.relative_to(root.resolve())
    except ValueError as exc:
        raise ComplianceError(f"ZIP 路径越界被拒绝: {member.filename}") from exc
    return destination


def safe_extract_zip(asset_file: Path, destination: Path) -> list[Path]:
    """Extract a ZIP after rejecting traversal, drive paths, and symlinks."""

    extracted: list[Path] = []
    try:
        archive = zipfile.ZipFile(asset_file)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ComplianceError(f"无法读取 ZIP 资产: {asset_file.name}: {exc}") from exc
    with archive:
        for member in archive.infolist():
            target = _validated_member_path(destination, member)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
            extracted.append(target)
    return extracted


def compare_ncmdump_asset(local_file: Path, asset_file: Path) -> dict[str, Any]:
    """Compare local ncmdump with same-architecture ncmdump files in a ZIP."""

    local_file = local_file.resolve()
    asset_file = asset_file.resolve()
    if not local_file.is_file():
        raise ComplianceError(f"本地 ncmdump 文件不存在: {local_file}")
    if not asset_file.is_file():
        raise ComplianceError(f"官方资产文件不存在: {asset_file}")
    local_hash = sha256_file(local_file)
    local_pe = pe_metadata(local_file)
    with tempfile.TemporaryDirectory(prefix="qonic-ncmdump-verify-") as temp_dir:
        temp_root = Path(temp_dir).resolve()
        extracted = safe_extract_zip(asset_file, temp_root)
        asset_members = [
            {
                "path": path.relative_to(temp_root).as_posix(),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in sorted(extracted, key=lambda item: str(item).lower())
        ]
        candidates = [
            path
            for path in extracted
            if path.name.lower() == "ncmdump.exe" and path.is_file()
        ]
        same_arch = [
            path
            for path in candidates
            if pe_metadata(path).get("machine") == local_pe.get("machine")
        ]
        selected_candidates = same_arch or candidates
        comparisons = []
        for candidate in sorted(selected_candidates, key=lambda item: str(item).lower()):
            digest = sha256_file(candidate)
            comparisons.append(
                {
                    "asset_member": candidate.relative_to(temp_root).as_posix(),
                    "size": candidate.stat().st_size,
                    "sha256": digest,
                    "machine": pe_metadata(candidate).get("machine"),
                    "byte_identical": digest == local_hash
                    and candidate.stat().st_size == local_file.stat().st_size,
                }
            )
    identical = any(item["byte_identical"] for item in comparisons)
    if identical:
        status = "BYTE_IDENTICAL"
    elif not comparisons:
        status = "ASSET_TYPE_MISMATCH"
    else:
        status = "BINARY_MISMATCH"
    return {
        "asset_file": asset_file.name,
        "asset_sha256": sha256_file(asset_file),
        "asset_size": asset_file.stat().st_size,
        "asset_members": asset_members,
        "local_file": local_file.name,
        "local_sha256": local_hash,
        "local_size": local_file.stat().st_size,
        "local_machine": local_pe.get("machine"),
        "candidates": comparisons,
        "byte_identical_to_upstream": identical,
        "status": status,
    }


def write_comparison(result: dict[str, Any], output_dir: Path) -> None:
    """Write JSON/Markdown comparison evidence and update local provenance."""

    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "ncmdump-asset-comparison.json", result)
    candidate_lines = [
        (
            f"- `{item['asset_member']}`: `{item['sha256']}`, "
            f"identical=`{item['byte_identical']}`"
        )
        for item in result["candidates"]
    ] or ["- 未在资产中找到 ncmdump.exe。"]
    write_text(
        output_dir / "ncmdump-asset-comparison.md",
        "\n".join(
            [
                "# ncmdump Asset Comparison",
                "",
                f"- 状态：`{result['status']}`。",
                f"- 官方资产：`{result['asset_file']}`。",
                f"- 官方资产 SHA-256：`{result['asset_sha256']}`。",
                f"- 本地 ncmdump SHA-256：`{result['local_sha256']}`。",
                f"- 逐字节一致：`{result['byte_identical_to_upstream']}`。",
                (
                    "- 差异结论：提供的官方资产不含 `ncmdump.exe`，"
                    "属于库 DLL 资产，不能用于当前 CLI EXE 的逐字节比对。"
                    if result["status"] == "ASSET_TYPE_MISMATCH"
                    else "- 差异结论：见下方候选文件比对。"
                ),
                "",
                "## Candidate Files",
                *candidate_lines,
                "",
                "## Asset Members",
                *[
                    (
                        f"- `{item['path']}`: `{item['sha256']}`, "
                        f"{item['size']} bytes"
                    )
                    for item in result["asset_members"]
                ],
            ]
        )
        + "\n",
    )
    provenance_path = output_dir / "ncmdump-provenance.json"
    if provenance_path.is_file():
        provenance = load_json(provenance_path)
        provenance["byte_identical_to_upstream"] = result["byte_identical_to_upstream"]
        provenance["asset_comparison_status"] = result["status"]
        provenance["provided_asset"] = result["asset_file"]
        provenance["provided_asset_sha256"] = result["asset_sha256"]
        provenance["provided_asset_members"] = result["asset_members"]
        if result["status"] == "BYTE_IDENTICAL":
            provenance["upstream_asset"] = result["asset_file"]
            provenance["upstream_asset_sha256"] = result["asset_sha256"]
        write_json(provenance_path, provenance)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-file", type=Path, required=True)
    parser.add_argument("--asset-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    """Run the safe asset comparison."""

    args = build_parser().parse_args()
    try:
        result = compare_ncmdump_asset(args.local_file, args.asset_file)
        write_comparison(result, args.output)
    except ComplianceError as exc:
        print(f"ERROR: {exc}")
        return 3
    return 0 if result["byte_identical_to_upstream"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
