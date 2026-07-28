"""Verify bundled PySide6/shiboken6 files against exact official wheels."""

from __future__ import annotations

import argparse
import hashlib
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from common import ComplianceError, load_json, sha256_file, write_json, write_text


USER_AGENT = "Qonic-Audio-Compliance-Audit"
MICROSOFT_RUNTIME_NAMES = {
    "msvcp140.dll",
    "msvcp140_1.dll",
    "msvcp140_2.dll",
    "vcruntime140.dll",
    "vcruntime140_1.dll",
}


def download_file(url: str, destination: Path) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    digest = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=180) as response:
        with destination.open("wb") as output:
            for chunk in iter(lambda: response.read(1024 * 1024), b""):
                output.write(chunk)
                digest.update(chunk)
    return digest.hexdigest().upper()


def index_wheels(
    wheel_paths: list[tuple[Path, dict[str, Any]]],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    members: dict[str, dict[str, Any]] = {}
    wheel_results = []
    for path, metadata in wheel_paths:
        actual_hash = sha256_file(path)
        hash_match = actual_hash == str(metadata["sha256"]).upper()
        with zipfile.ZipFile(path) as archive:
            for item in archive.infolist():
                if item.is_dir() or not item.filename.startswith(
                    ("PySide6/", "shiboken6/")
                ):
                    continue
                digest = hashlib.sha256()
                with archive.open(item) as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                record = {
                    "wheel": metadata["filename"],
                    "size": item.file_size,
                    "sha256": digest.hexdigest().upper(),
                }
                previous = members.get(item.filename)
                if previous and previous["sha256"] != record["sha256"]:
                    raise ComplianceError(
                        f"不同 wheel 对同一路径提供不同内容: {item.filename}"
                    )
                members[item.filename] = record
        wheel_results.append(
            {
                **metadata,
                "downloaded_sha256": actual_hash,
                "official_hash_match": hash_match,
            }
        )
    return members, wheel_results


def compare_distribution(
    dist_path: Path,
    wheel_members: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    records = []
    for package in ("PySide6", "shiboken6"):
        root = dist_path / "_internal" / package
        if not root.is_dir():
            raise ComplianceError(f"发行目录缺少 {package}: {root}")
        for path in sorted(root.rglob("*"), key=lambda item: str(item).lower()):
            if not path.is_file():
                continue
            relative = f"{package}/{path.relative_to(root).as_posix()}"
            wheel = wheel_members.get(relative)
            digest = sha256_file(path)
            records.append(
                {
                    "path": f"DIST/_internal/{relative}",
                    "size": path.stat().st_size,
                    "sha256": digest,
                    "wheel": wheel["wheel"] if wheel else None,
                    "wheel_sha256": wheel["sha256"] if wheel else None,
                    "byte_identical": bool(wheel)
                    and digest == wheel["sha256"]
                    and path.stat().st_size == wheel["size"],
                }
            )
    missing = [item["path"] for item in records if item["wheel"] is None]
    external_runtime_files = [
        item
        for item in records
        if item["wheel"] is None
        and Path(item["path"]).name.lower() in MICROSOFT_RUNTIME_NAMES
    ]
    unclassified_missing = [
        item["path"]
        for item in records
        if item["wheel"] is None
        and Path(item["path"]).name.lower() not in MICROSOFT_RUNTIME_NAMES
    ]
    mismatches = [
        item["path"]
        for item in records
        if item["wheel"] is not None and not item["byte_identical"]
    ]
    return {
        "distribution_file_count": len(records),
        "wheel_scoped_file_count": len(records) - len(external_runtime_files),
        "matched_file_count": sum(
            1 for item in records if item["byte_identical"]
        ),
        "missing_from_wheels": unclassified_missing,
        "external_runtime_files": external_runtime_files,
        "all_non_wheel_files": missing,
        "hash_mismatches": mismatches,
        "files": records,
    }


def verify_qt_wheels(
    dist_path: Path,
    metadata: dict[str, Any],
    wheel_cache: Path | None = None,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="qonic-qt-wheel-verify-") as temp:
        temp_root = wheel_cache or Path(temp)
        temp_root.mkdir(parents=True, exist_ok=True)
        wheel_paths = []
        for wheel in metadata.get("wheels", []):
            path = temp_root / wheel["filename"]
            existing_hash = sha256_file(path) if path.is_file() else None
            downloaded_hash = (
                existing_hash
                if existing_hash == str(wheel["sha256"]).upper()
                else download_file(wheel["url"], path)
            )
            if downloaded_hash != str(wheel["sha256"]).upper():
                raise ComplianceError(
                    f"下载 wheel SHA-256 与 PyPI 元数据不一致: {wheel['filename']}"
                )
            wheel_paths.append((path, wheel))
        members, wheel_results = index_wheels(wheel_paths)
        distribution = compare_distribution(dist_path, members)
    verified = (
        len(wheel_results) == 4
        and all(item["official_hash_match"] for item in wheel_results)
        and not distribution["missing_from_wheels"]
        and not distribution["hash_mismatches"]
        and distribution["wheel_scoped_file_count"]
        == distribution["matched_file_count"]
    )
    return {
        "status": (
            "BYTE_IDENTICAL_SUBSET_OF_EXACT_WHEELS"
            if verified
            else "WHEEL_OR_DISTRIBUTION_MISMATCH"
        ),
        "byte_identical_to_exact_wheels": verified,
        "wheels": wheel_results,
        **distribution,
    }


def write_verification(result: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "qt-wheel-verification.json", result)
    write_text(
        output_dir / "qt-wheel-verification.md",
        "\n".join(
            [
                "# Qt Wheel Verification",
                "",
                f"- 状态：`{result['status']}`。",
                f"- 精确 wheel 数量：`{len(result['wheels'])}`。",
                f"- 发行 Qt/PySide/shiboken 文件：`{result['distribution_file_count']}`。",
                f"- wheel 范围文件：`{result['wheel_scoped_file_count']}`。",
                f"- 逐字节匹配：`{result['matched_file_count']}`。",
                f"- wheel 中缺失：`{len(result['missing_from_wheels'])}`。",
                f"- 哈希不一致：`{len(result['hash_mismatches'])}`。",
                f"- 另行归类的 Microsoft VC Runtime：`{len(result['external_runtime_files'])}`。",
                "",
                "## Exact Wheels",
                *[
                    (
                        f"- `{item['filename']}`: `{item['sha256']}`, "
                        f"official_hash_match=`{item['official_hash_match']}`"
                    )
                    for item in result["wheels"]
                ],
            ]
        )
        + "\n",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-path", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--wheel-cache",
        type=Path,
        help="Optional retained directory for exact verified wheel archives.",
    )
    parser.add_argument("--allow-download", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.allow_download:
        print("ERROR: wheel 下载默认关闭；需显式传入 --allow-download。")
        return 3
    try:
        result = verify_qt_wheels(
            args.dist_path.resolve(),
            load_json(args.metadata),
            args.wheel_cache.resolve() if args.wheel_cache else None,
        )
        write_verification(result, args.output)
    except (
        ComplianceError,
        OSError,
        ValueError,
        zipfile.BadZipFile,
        urllib.error.URLError,
    ) as exc:
        print(f"ERROR: {exc}")
        return 3
    return 0 if result["byte_identical_to_exact_wheels"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
