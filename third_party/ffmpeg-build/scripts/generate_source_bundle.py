from __future__ import annotations

import argparse
import tarfile
from pathlib import Path

from common import BUILD_ROOT, OUTPUT, SOURCES, sha256, write_json


INCLUDE_DIRS = ("lock", "config", "scripts", "patches", "tests")


def source_bundle_filter(info: tarfile.TarInfo) -> tarfile.TarInfo | None:
    parts = info.name.split("/")
    if "__pycache__" in parts or info.name.endswith((".pyc", ".pyo", ".bak")):
        return None
    return info


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT / "source-bundle" / "qonic-ffmpeg-complete-corresponding-source.tar.gz",
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(args.output, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        for directory in INCLUDE_DIRS:
            archive.add(
                BUILD_ROOT / directory,
                arcname=f"ffmpeg-build/{directory}",
                filter=source_bundle_filter,
            )
        for source in sorted(SOURCES.iterdir()):
            if source.is_file() and source.name != ".gitkeep":
                archive.add(source, arcname=f"ffmpeg-build/sources/{source.name}")
        for document in (
            "README.md",
            "BUILDING.md",
            "LICENSES.md",
            "SOURCE_OFFER.md",
            "build.sh",
            "build.ps1",
            "verify.ps1",
        ):
            path = BUILD_ROOT / document
            if path.is_file():
                archive.add(path, arcname=f"ffmpeg-build/{document}")
    write_json(
        args.output.with_suffix(args.output.suffix + ".json"),
        {
            "file": args.output.name,
            "sha256": sha256(args.output),
            "size": args.output.stat().st_size,
        },
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
