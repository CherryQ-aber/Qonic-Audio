"""Compute SHA-256 hashes and duplicate groups for files or directories."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from common import display_path, duplicate_groups, iter_files, sha256_file, write_json


def hash_paths(paths: Sequence[Path], project_root: Path) -> dict:
    """Hash all regular files below the supplied paths."""

    records = []
    for path in sorted(iter_files(paths), key=lambda item: str(item).lower()):
        stat = path.stat()
        records.append(
            {
                "path": display_path(path, project_root),
                "size": stat.st_size,
                "sha256": sha256_file(path),
            }
        )
    return {
        "algorithm": "SHA-256",
        "files": records,
        "duplicate_groups": duplicate_groups(records),
    }


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    """Run the hashing command."""

    args = build_parser().parse_args()
    roots = [path.resolve() for path in args.paths]
    write_json(args.output, hash_paths(roots, args.project_root.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
