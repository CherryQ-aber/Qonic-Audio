from __future__ import annotations

import os
import platform
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from common import LOCKS, OUTPUT, load_json, sha256, write_json


def command_output(command: list[str]) -> str:
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        return (result.stdout + result.stderr).strip()
    except OSError:
        return ""


def imported_dlls(path: Path) -> list[str]:
    output = command_output(["x86_64-w64-mingw32-objdump", "-p", str(path)])
    return sorted(set(re.findall(r"DLL Name:\s*(\S+)", output, flags=re.IGNORECASE)))


def main() -> int:
    candidate = OUTPUT / "candidate"
    binaries = []
    for name in ("ffmpeg.exe", "ffprobe.exe"):
        path = candidate / name
        if not path.is_file():
            raise FileNotFoundError(path)
        binaries.append(
            {
                "name": name,
                "sha256": sha256(path),
                "size": path.stat().st_size,
                "imported_dlls": imported_dlls(path),
            }
        )
    lockfiles = [
        {
            "name": path.name,
            "sha256": sha256(path),
        }
        for path in sorted(LOCKS.glob("*.json"))
    ]
    payload = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "target": "windows-x86_64",
        "candidate_only": True,
        "formal_runtime_modified": False,
        "builder": {
            "platform": platform.platform(),
            "container_marker": os.environ.get("QONIC_BUILD_CONTAINER") == "1",
            "compiler": command_output(["x86_64-w64-mingw32-gcc-win32", "--version"]).splitlines()[:1],
            "packages": command_output(["dpkg-query", "-W", "-f=${Package}=${Version}\\n"]).splitlines(),
        },
        "lockfiles": lockfiles,
        "binaries": binaries,
    }
    write_json(candidate / "BUILD_MANIFEST.json", payload)
    source_lock = load_json(LOCKS / "sources.lock.json")
    write_json(
        candidate / "SOURCE_INDEX.json",
        {
            "schema_version": 1,
            "sources": [
                {
                    "name": item["name"],
                    "version": item["version"],
                    "commit": item.get("commit"),
                    "archive_filename": item["filename"],
                    "sha256": item["sha256"],
                    "license": item["license"],
                    "patches": item["patches"],
                }
                for item in source_lock["sources"]
            ],
        },
    )
    sums = [f"{item['sha256']} *{item['name']}" for item in binaries]
    (candidate / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="ascii")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
