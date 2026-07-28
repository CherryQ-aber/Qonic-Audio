from __future__ import annotations

import shutil
import tarfile
from pathlib import PurePosixPath

from common import LOCKS, SOURCE_TREES, SOURCES, load_json


def safe_extract(archive: tarfile.TarFile, destination) -> None:
    for member in archive.getmembers():
        archive_path = PurePosixPath(member.name)
        if archive_path.is_absolute() or ".." in archive_path.parts:
            raise RuntimeError(f"archive path escapes workspace: {member.name}")
        if not (member.isdir() or member.isfile()):
            raise RuntimeError(f"unsupported archive member type: {member.name}")
    # Python 3.11 in the pinned Debian image predates filtered extraction.
    # The checks above provide the required path and member-type restrictions.
    archive.extractall(destination)


def main() -> int:
    if SOURCE_TREES.exists():
        shutil.rmtree(SOURCE_TREES)
    SOURCE_TREES.mkdir(parents=True)
    lock = load_json(LOCKS / "sources.lock.json")
    for entry in lock["sources"]:
        destination = SOURCE_TREES / entry["name"]
        staging = SOURCE_TREES / f".{entry['name']}-extract"
        staging.mkdir()
        with tarfile.open(SOURCES / entry["filename"], "r:*") as archive:
            safe_extract(archive, staging)
        roots = [path for path in staging.iterdir()]
        if len(roots) == 1 and roots[0].is_dir():
            roots[0].replace(destination)
            staging.rmdir()
        else:
            staging.replace(destination)
        print(f"prepared {entry['name']}: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
