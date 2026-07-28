"""Compare bundled FFmpeg tools with an exact Gyan Release archive."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path
from typing import Any

from common import ComplianceError, load_json, sha256_file, write_json, write_text


def parse_archive_paths(listing: str) -> list[str]:
    """Return archive member paths from a 7-Zip ``-slt`` listing."""

    paths: list[str] = []
    for line in listing.splitlines():
        if not line.startswith("Path = "):
            continue
        value = line[7:].strip()
        if value:
            paths.append(value)
    return paths[1:] if paths else []


def list_archive_paths(seven_zip: Path, archive: Path) -> list[str]:
    """List one 7-Zip archive without extracting it."""

    completed = subprocess.run(
        [str(seven_zip), "l", "-slt", str(archive)],
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    if completed.returncode != 0:
        raise ComplianceError(
            f"7-Zip 无法列出官方 FFmpeg 资产: {completed.stderr.strip()}"
        )
    return parse_archive_paths(completed.stdout)


def hash_archive_member(
    seven_zip: Path,
    archive: Path,
    member: str,
) -> tuple[str, int]:
    """Stream one archive member through SHA-256 without writing it to disk."""

    process = subprocess.Popen(
        [str(seven_zip), "e", "-so", "-bd", "-y", str(archive), member],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.stdout is None or process.stderr is None:
        process.kill()
        raise ComplianceError("无法读取 7-Zip 二进制输出。")
    digest = hashlib.sha256()
    size = 0
    for chunk in iter(lambda: process.stdout.read(1024 * 1024), b""):
        digest.update(chunk)
        size += len(chunk)
    stderr = process.stderr.read().decode("utf-8", errors="replace")
    returncode = process.wait(timeout=120)
    if returncode != 0:
        raise ComplianceError(
            f"7-Zip 无法读取资产成员 {member}: {stderr.strip()}"
        )
    return digest.hexdigest().upper(), size


def _select_member(paths: list[str], filename: str) -> str:
    candidates = [
        path
        for path in paths
        if path.replace("\\", "/").lower().endswith(f"/bin/{filename.lower()}")
    ]
    if len(candidates) != 1:
        raise ComplianceError(
            f"官方资产中的 {filename} 候选数量不是 1: {len(candidates)}"
        )
    return candidates[0]


def compare_ffmpeg_asset(
    local_ffmpeg: Path,
    local_ffprobe: Path,
    asset_file: Path,
    seven_zip: Path,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Compare ffmpeg.exe and ffprobe.exe with exact release members."""

    for path in (local_ffmpeg, local_ffprobe, asset_file, seven_zip):
        if not path.is_file():
            raise ComplianceError(f"所需文件不存在: {path}")
    expected_asset = metadata.get("asset", {})
    expected_hash = str(expected_asset.get("sha256", "")).upper()
    asset_hash = sha256_file(asset_file)
    paths = list_archive_paths(seven_zip, asset_file)
    tools = []
    for local_file in (local_ffmpeg, local_ffprobe):
        member = _select_member(paths, local_file.name)
        member_hash, member_size = hash_archive_member(
            seven_zip,
            asset_file,
            member,
        )
        local_hash = sha256_file(local_file)
        tools.append(
            {
                "name": local_file.name,
                "local_size": local_file.stat().st_size,
                "local_sha256": local_hash,
                "asset_member": member.replace("\\", "/"),
                "asset_member_size": member_size,
                "asset_member_sha256": member_hash,
                "byte_identical": (
                    local_hash == member_hash
                    and local_file.stat().st_size == member_size
                ),
            }
        )
    asset_identity_verified = bool(expected_hash) and asset_hash == expected_hash
    binary_identity_verified = asset_identity_verified and all(
        item["byte_identical"] for item in tools
    )
    return {
        "status": (
            "BYTE_IDENTICAL"
            if binary_identity_verified
            else "ASSET_OR_BINARY_MISMATCH"
        ),
        "asset_file": asset_file.name,
        "asset_size": asset_file.stat().st_size,
        "asset_sha256": asset_hash,
        "expected_asset_sha256": expected_hash,
        "asset_identity_verified": asset_identity_verified,
        "binary_identity_verified": binary_identity_verified,
        "provider": metadata.get("provider"),
        "provider_release_tag": metadata.get("provider_release_tag"),
        "provider_release_commit": metadata.get("provider_release_commit"),
        "ffmpeg_source": metadata.get("ffmpeg_source"),
        "provider_build_scripts_present": metadata.get(
            "provider_build_scripts_present"
        ),
        "tools": tools,
    }


def write_comparison(
    result: dict[str, Any],
    output_dir: Path,
    provenance_path: Path | None,
) -> None:
    """Write JSON/Markdown evidence and merge verified identity into provenance."""

    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "ffmpeg-asset-comparison.json", result)
    write_text(
        output_dir / "ffmpeg-asset-comparison.md",
        "\n".join(
            [
                "# FFmpeg Gyan Asset Comparison",
                "",
                f"- 状态：`{result['status']}`。",
                f"- 官方资产：`{result['asset_file']}`。",
                f"- 官方资产 SHA-256：`{result['asset_sha256']}`。",
                f"- 官方资产身份通过：`{result['asset_identity_verified']}`。",
                f"- 两个发行二进制逐字节一致：`{result['binary_identity_verified']}`。",
                "",
                "## Tool Members",
                *[
                    (
                        f"- `{item['name']}` → `{item['asset_member']}`："
                        f"`{item['asset_member_sha256']}`，"
                        f"identical=`{item['byte_identical']}`"
                    )
                    for item in result["tools"]
                ],
            ]
        )
        + "\n",
    )
    if provenance_path and provenance_path.is_file():
        provenance = load_json(provenance_path)
        provenance.update(
            {
                "upstream_release": result["provider_release_tag"],
                "upstream_asset": result["asset_file"],
                "upstream_asset_sha256": result["asset_sha256"],
                "upstream_commit": result["ffmpeg_source"]["commit"],
                "byte_identical_to_upstream": result[
                    "binary_identity_verified"
                ],
                "binary_asset_closed": result["binary_identity_verified"],
                "asset_comparison_status": result["status"],
                "provider_release_commit": result["provider_release_commit"],
                "provider_build_scripts_present": result[
                    "provider_build_scripts_present"
                ],
            }
        )
        write_json(provenance_path, provenance)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-ffmpeg", type=Path, required=True)
    parser.add_argument("--local-ffprobe", type=Path, required=True)
    parser.add_argument("--asset-file", type=Path, required=True)
    parser.add_argument("--seven-zip", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provenance", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = compare_ffmpeg_asset(
            args.local_ffmpeg.resolve(),
            args.local_ffprobe.resolve(),
            args.asset_file.resolve(),
            args.seven_zip.resolve(),
            load_json(args.metadata),
        )
        write_comparison(result, args.output, args.provenance)
    except (ComplianceError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 3
    return 0 if result["binary_identity_verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
