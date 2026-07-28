"""Download and verify the exact Qt/PySide source archives in upstream evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _download(url: str, destination: Path, expected_size: int) -> None:
    partial = destination.with_suffix(destination.suffix + ".part")
    offset = partial.stat().st_size if partial.is_file() else 0
    headers = {"User-Agent": "Qonic-Audio-Compliance/1.0"}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=120) as response:
        resumed = offset > 0 and response.status == 206
        mode = "ab" if resumed else "wb"
        if offset and not resumed:
            offset = 0
        with partial.open(mode) as stream:
            downloaded = offset
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                stream.write(chunk)
                downloaded += len(chunk)
                if downloaded % (64 * 1024 * 1024) < len(chunk):
                    print(
                        f"  {destination.name}: {downloaded}/{expected_size} bytes",
                        flush=True,
                    )
    if partial.stat().st_size != expected_size:
        raise ValueError(
            f"{destination.name}: size {partial.stat().st_size} != {expected_size}"
        )
    partial.replace(destination)


def _archives(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        *evidence.get("qt_source_modules", []),
        *evidence.get("qt_internal_third_party_sources", []),
        evidence.get("pyside_source", {}),
    ]


def fetch_sources(evidence_path: Path, output_dir: Path) -> list[Path]:
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    verified: list[Path] = []
    for item in _archives(evidence):
        filename = str(item.get("filename", ""))
        url = str(item.get("package_url", ""))
        expected_hash = str(item.get("sha256", "")).upper()
        expected_size = int(item.get("size", 0))
        if not all((filename, url, expected_hash, expected_size)):
            raise ValueError(f"source archive evidence is incomplete: {item!r}")
        destination = output_dir / filename
        if (
            destination.is_file()
            and destination.stat().st_size == expected_size
            and _sha256(destination) == expected_hash
        ):
            print(f"VERIFIED existing: {filename}")
            verified.append(destination)
            continue
        print(f"DOWNLOAD: {filename}")
        _download(url, destination, expected_size)
        actual_hash = _sha256(destination)
        if actual_hash != expected_hash:
            raise ValueError(
                f"{filename}: SHA-256 {actual_hash} != {expected_hash}"
            )
        print(f"VERIFIED downloaded: {filename}")
        verified.append(destination)
    return verified


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Required explicit acknowledgement before downloading official assets.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.allow_network:
        print("ERROR: --allow-network is required", file=sys.stderr)
        return 3
    try:
        files = fetch_sources(args.evidence.resolve(), args.output.resolve())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"SUMMARY: verified={len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
