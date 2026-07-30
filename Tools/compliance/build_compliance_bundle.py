"""Build a review-only compliance ZIP after blockers are resolved or overridden."""

from __future__ import annotations

import argparse
import re
import shutil
import zipfile
from pathlib import Path

from common import iter_files, load_json, sha256_file, write_text


FORBIDDEN_PATTERNS = (
    re.compile(rb"(?i)(?<![A-Za-z0-9])ghp_[A-Za-z0-9]{20,}"),
    re.compile(rb"(?i)(?<![A-Za-z0-9])github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(rb"(?i)(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}"),
    re.compile(rb"(?i)[A-Z]:\\Users\\[^\\\r\n]+"),
)


def _iter_bundle_files(project_root: Path) -> list[Path]:
    roots = [
        project_root / "third_party",
        project_root / "compliance",
    ]
    self_build_materials = [
        project_root / "third_party" / "ffmpeg-build" / "output" / "source-bundle",
        project_root / "third_party" / "ffmpeg-build" / "output" / "candidate" / "LICENSES",
    ]
    files = list(iter_files(root for root in roots if root.is_dir()))
    files.extend(iter_files(root for root in self_build_materials if root.is_dir()))
    return sorted(set(files), key=lambda item: str(item).lower())


def _contains_forbidden_content(path: Path) -> bool:
    """Scan large evidence archives without loading the whole file into memory."""

    tail = b""
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            data = tail + chunk
            if any(pattern.search(data) for pattern in FORBIDDEN_PATTERNS):
                return True
            tail = data[-512:]
    return False


def build_bundle(
    project_root: Path,
    output: Path,
    *,
    allow_blockers: bool = False,
) -> Path:
    """Build a deterministic review ZIP while rejecting secrets/private paths."""

    manifest_path = project_root / "third_party" / "THIRD_PARTY_MANIFEST.json"
    manifest = load_json(manifest_path)
    if manifest.get("blockers") and not allow_blockers:
        raise ValueError("Manifest 仍有 BLOCKER；未生成最终合规包。")
    files = _iter_bundle_files(project_root)
    for path in files:
        if _contains_forbidden_content(path):
            raise ValueError(f"合规包文件包含敏感或私人路径模式: {path.name}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            relative = path.relative_to(project_root).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            with path.open("rb") as source, archive.open(info, "w") as destination:
                shutil.copyfileobj(source, destination, length=1024 * 1024)
    checksum = sha256_file(output)
    write_text(output.with_suffix(".sha256"), f"{checksum}  {output.name}\n")
    return output


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-blockers", action="store_true")
    return parser


def main() -> int:
    """Build the review-only bundle."""

    args = build_parser().parse_args()
    try:
        build_bundle(
            args.project_root.resolve(),
            args.output.resolve(),
            allow_blockers=args.allow_blockers,
        )
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
