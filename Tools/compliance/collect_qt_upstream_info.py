"""Collect exact PySide6 wheel and Qt source metadata from official endpoints."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import ComplianceError, load_json, write_json


USER_AGENT = "Qonic-Audio-Compliance-Audit"
PYPI_PACKAGES = (
    "PySide6",
    "PySide6_Essentials",
    "PySide6_Addons",
    "shiboken6",
)
LICENSE_DOCUMENTS = {
    "Qt-6.11-Licensing.html": "https://doc.qt.io/qt-6/licensing.html",
    "Qt-6.11.1-Third-Party-Code.html": (
        "https://doc.qt.io/qt-6/licenses-used-in-qt.html"
    ),
    "Qt-6.11.1-WebEngine-Licensing.html": (
        "https://doc.qt.io/qt-6/qtwebengine-licensing.html"
    ),
    "Qt-6.11-SBOM-Documentation.html": "https://doc.qt.io/qt-6/sbom.html",
}
QT_INTERNAL_THIRD_PARTY_SOURCES = {
    "6.11.1": [
        {
            "component": "Qt Multimedia FFmpeg",
            "version": "7.1.3",
            "tag": "n7.1.3",
            "tag_object": "0a9a757e96fdf053697084bbd1f620edeac9d084",
            "commit": "f46e514491172d15bd74b4abb1814cd2f05a763e",
            "filename": (
                "ffmpeg-f46e514491172d15bd74b4abb1814cd2f05a763e.tar.gz"
            ),
            "package_url": (
                "https://codeload.github.com/FFmpeg/FFmpeg/tar.gz/"
                "f46e514491172d15bd74b4abb1814cd2f05a763e"
            ),
            "size": 15926127,
            "sha256": (
                "1FA39B5A6AE9AC02C2CF280EC5CC8321A0DD0B9AB34B6C73133CAFCCAF5DFA79"
            ),
            "license": (
                "LGPL-2.1-or-later AND BSD-3-Clause AND BSD-2-Clause AND "
                "BSD-Source-Code AND ISC AND MIT AND MPL-2.0"
            ),
            "copyright": "Copyright (c) 2000-2023 the FFmpeg developers",
            "attribution_path": (
                "qtmultimedia-everywhere-src-6.11.1/"
                "src/3rdparty/ffmpeg/qt_attribution.json"
            ),
        }
    ]
}


def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def fetch_json(url: str) -> dict[str, Any]:
    return json.loads(fetch_bytes(url).decode("utf-8"))


def parse_mirrorlist(html: str) -> dict[str, Any]:
    """Parse official Qt MirrorBrain file identity metadata."""

    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    patterns = {
        "filename": r"Filename:\s*([^\s]+)",
        "size": r"Size:.*?\((\d+) bytes\)",
        "last_modified": r"Last modified:\s*(.*?)\s*\(Unix time:",
        "sha256": r"SHA-256 Hash\s*:\s*([0-9a-fA-F]{64})",
    }
    values: dict[str, Any] = {}
    for field, pattern in patterns.items():
        match = re.search(pattern, text)
        if not match:
            raise ComplianceError(f"Qt mirrorlist 缺少字段: {field}")
        values[field] = match.group(1)
    values["size"] = int(values["size"])
    values["sha256"] = str(values["sha256"]).upper()
    return values


def collect_wheels(version: str) -> list[dict[str, Any]]:
    wheels = []
    for package in PYPI_PACKAGES:
        metadata = fetch_json(f"https://pypi.org/pypi/{package}/{version}/json")
        candidates = [
            item
            for item in metadata.get("urls", [])
            if str(item.get("filename", "")).endswith("win_amd64.whl")
        ]
        if len(candidates) != 1:
            raise ComplianceError(
                f"{package} {version} Windows x64 wheel 数量不是 1"
            )
        item = candidates[0]
        wheels.append(
            {
                "package": package,
                "filename": item["filename"],
                "size": item["size"],
                "sha256": item["digests"]["sha256"].upper(),
                "url": item["url"],
                "python_version": item["python_version"],
                "upload_time": item["upload_time_iso_8601"],
            }
        )
    return wheels


def source_mirrorlist_url(version: str, module: str) -> str:
    return (
        f"https://download.qt.io/official_releases/qt/6.11/{version}/"
        f"submodules/{module}-everywhere-src-{version}.tar.xz.mirrorlist"
    )


def collect_source_archive(url: str) -> dict[str, Any]:
    identity = parse_mirrorlist(fetch_bytes(url).decode("utf-8", errors="replace"))
    return {
        **identity,
        "mirrorlist_url": url,
        "package_url": url.removesuffix(".mirrorlist"),
    }


def collect_qt_upstream(
    version: str,
    runtime_inventory: dict[str, Any],
    license_output: Path,
) -> dict[str, Any]:
    source_modules = sorted(
        {
            source
            for record in runtime_inventory.get("files", [])
            for source in (
                [record.get("source_module")]
                if record.get("source_module")
                else []
            )
            if not str(source).startswith("pyside-setup/")
        }
    )
    qt_sources = [
        {
            "module": module,
            **collect_source_archive(source_mirrorlist_url(version, module)),
        }
        for module in source_modules
    ]
    pyside_url = (
        "https://download.qt.io/official_releases/QtForPython/pyside6/"
        f"PySide6-{version}-src/"
        f"pyside-setup-everywhere-src-{version}.tar.xz.mirrorlist"
    )
    pyside_source = collect_source_archive(pyside_url)
    license_output.mkdir(parents=True, exist_ok=True)
    license_documents = []
    for filename, url in LICENSE_DOCUMENTS.items():
        content = fetch_bytes(url)
        path = license_output / filename
        path.write_bytes(content)
        license_documents.append(
            {
                "filename": filename,
                "url": url,
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest().upper(),
            }
        )
    wheels = collect_wheels(version)
    return {
        "observed_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "version": version,
        "wheels": wheels,
        "pyside_source": pyside_source,
        "qt_source_modules": qt_sources,
        "qt_internal_third_party_sources": (
            QT_INTERNAL_THIRD_PARTY_SOURCES.get(version, [])
        ),
        "license_documents": license_documents,
        "source_archives_identified": bool(qt_sources)
        and all(item.get("sha256") for item in qt_sources)
        and bool(pyside_source.get("sha256")),
        "license_document_snapshots_complete": len(license_documents)
        == len(LICENSE_DOCUMENTS),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--runtime-inventory", type=Path, required=True)
    parser.add_argument("--license-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-network", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.allow_network:
        print("ERROR: 网络采集默认关闭；需显式传入 --allow-network。")
        return 3
    try:
        payload = collect_qt_upstream(
            args.version,
            load_json(args.runtime_inventory),
            args.license_output,
        )
        write_json(args.output, payload)
    except (ComplianceError, OSError, ValueError, urllib.error.URLError) as exc:
        print(f"ERROR: {exc}")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
