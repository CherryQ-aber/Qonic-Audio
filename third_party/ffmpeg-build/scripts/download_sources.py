from __future__ import annotations

import argparse
import re
import shutil
import tempfile
import urllib.request
from pathlib import Path

from common import LOCKS, REPO_ROOT, SOURCES, load_json, sha256


FLOATING_URL_PATTERN = re.compile(
    r"(?:refs/heads/(?:main|master)|/(?:latest|head|rolling|current)(?:/|$)|snapshot)",
    re.IGNORECASE,
)


def validate_source(entry: dict) -> None:
    required = ("name", "version", "filename", "url", "sha256")
    missing = [field for field in required if not entry.get(field)]
    if missing:
        raise ValueError(f"{entry.get('name', '<unknown>')}: missing {missing}")
    url = str(entry["url"])
    if FLOATING_URL_PATTERN.search(url):
        raise ValueError(f"{entry['name']}: floating URL is forbidden: {entry['url']}")
    expected = str(entry["sha256"]).lower()
    if len(expected) != 64 or any(char not in "0123456789abcdef" for char in expected):
        raise ValueError(f"{entry['name']}: invalid SHA-256")


def materialize(entry: dict, *, offline: bool) -> Path:
    validate_source(entry)
    destination = SOURCES / entry["filename"]
    vendored = REPO_ROOT / entry["vendored_path"] if entry.get("vendored_path") else None
    if destination.is_file() and sha256(destination) == entry["sha256"].lower():
        return destination
    if vendored and vendored.is_file():
        if sha256(vendored) != entry["sha256"].lower():
            raise RuntimeError(f"{entry['name']}: vendored source hash mismatch")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(vendored, destination)
        return destination
    if offline:
        raise FileNotFoundError(f"{entry['name']}: source is not cached")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=destination.parent, prefix=f".{destination.name}.", delete=False
    ) as stream:
        temporary = Path(stream.name)
    try:
        request = urllib.request.Request(
            entry["url"], headers={"User-Agent": "Qonic-FFmpeg-Build/1.0"}
        )
        with urllib.request.urlopen(request, timeout=180) as response, temporary.open("wb") as stream:
            shutil.copyfileobj(response, stream)
        actual = sha256(temporary)
        if actual != entry["sha256"].lower():
            raise RuntimeError(
                f"{entry['name']}: SHA-256 mismatch; expected {entry['sha256']}, got {actual}"
            )
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    lock = load_json(LOCKS / "sources.lock.json")
    for entry in lock["sources"]:
        path = materialize(entry, offline=args.offline)
        print(f"verified {entry['name']} {entry['version']}: {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
