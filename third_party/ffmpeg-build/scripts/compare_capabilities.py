from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

from common import REPO_ROOT, load_json, sha256, write_json


def execute(path: Path, args: list[str]) -> str:
    result = subprocess.run(
        [str(path), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    return (result.stdout + result.stderr).strip()


def names_from_listing(text: str, kind: str) -> list[str]:
    names: set[str] = set()
    if kind == "filters":
        for line in text.splitlines():
            match = re.match(r"^\s*[TSC.]{2}\s+([A-Za-z0-9_]+)\s", line)
            if match:
                names.add(match.group(1))
    elif kind == "codecs":
        for line in text.splitlines():
            match = re.match(r"^\s*[.A-Z]{3,8}\s+([A-Za-z0-9_]+)\s", line)
            if match:
                names.add(match.group(1))
    elif kind == "formats":
        for line in text.splitlines():
            match = re.match(r"^\s*[D.][E.]\s+([A-Za-z0-9_,]+)\s", line)
            if match:
                names.update(match.group(1).split(","))
    elif kind == "protocols":
        section = ""
        for line in text.splitlines():
            value = line.strip()
            if value in {"Input:", "Output:"}:
                section = value[:-1].lower()
            elif section and re.fullmatch(r"[A-Za-z0-9_+.-]+", value):
                names.add(value)
    return sorted(names)


def capture(ffmpeg: Path, ffprobe: Path) -> dict:
    version = execute(ffmpeg, ["-version"])
    buildconf = execute(ffmpeg, ["-buildconf"])
    data = {
        "ffmpeg_path": str(ffmpeg),
        "ffmpeg_sha256": sha256(ffmpeg),
        "ffprobe_path": str(ffprobe),
        "ffprobe_sha256": sha256(ffprobe),
        "version": version.splitlines()[:8],
        "ffprobe_version": execute(ffprobe, ["-version"]).splitlines()[:8],
        "buildconf": buildconf.splitlines(),
    }
    for kind, flag in (
        ("codecs", "-codecs"),
        ("formats", "-formats"),
        ("filters", "-filters"),
        ("protocols", "-protocols"),
    ):
        data[kind] = names_from_listing(execute(ffmpeg, [flag]), kind)
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--ffprobe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compare-required", action="store_true")
    args = parser.parse_args()
    payload = capture(args.ffmpeg.resolve(), args.ffprobe.resolve())
    if args.compare_required:
        requirements = load_json(
            REPO_ROOT
            / "compliance"
            / "report"
            / "ffmpeg-self-build"
            / "qonic-ffmpeg-feature-requirements.json"
        )
        required_filters = set(requirements["required_filters"])
        required_protocols = set(requirements["required_protocols"])
        payload["required_check"] = {
            "missing_filters": sorted(required_filters - set(payload["filters"])),
            "missing_protocols": sorted(required_protocols - set(payload["protocols"])),
        }
        payload["required_check"]["ok"] = not any(payload["required_check"].values())
    write_json(args.output, payload)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
