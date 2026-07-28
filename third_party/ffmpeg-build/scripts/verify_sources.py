from __future__ import annotations

from common import LOCKS, SOURCES, load_json, sha256
from download_sources import validate_source


def main() -> int:
    lock = load_json(LOCKS / "sources.lock.json")
    failures: list[str] = []
    for entry in lock["sources"]:
        validate_source(entry)
        path = SOURCES / entry["filename"]
        if not path.is_file():
            failures.append(f"{entry['name']}: missing {path.name}")
            continue
        actual = sha256(path)
        if actual != entry["sha256"].lower():
            failures.append(
                f"{entry['name']}: expected {entry['sha256']}, got {actual}"
            )
        else:
            print(f"OK {entry['name']} {entry['version']} {actual}")
    if failures:
        raise SystemExit("\n".join(failures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
