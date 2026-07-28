from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path


BUILD_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BUILD_ROOT.parents[1]
SOURCES = BUILD_ROOT / "sources"
WORK = BUILD_ROOT / "work"
OUTPUT = BUILD_ROOT / "output"
LOCKS = BUILD_ROOT / "lock"
PREFIX = WORK / "prefix"
SOURCE_TREES = WORK / "src"
LOGS = WORK / "logs"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], *, cwd: Path | None = None, env: dict | None = None) -> None:
    rendered = " ".join(command)
    print(f"+ {rendered}", flush=True)
    subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        env=env,
        check=True,
    )


def build_env() -> dict:
    env = os.environ.copy()
    prefix = str(PREFIX)
    env.update(
        {
            "CC": "x86_64-w64-mingw32-gcc-win32",
            "CXX": "x86_64-w64-mingw32-g++-win32",
            "AR": "x86_64-w64-mingw32-ar",
            "RANLIB": "x86_64-w64-mingw32-ranlib",
            "STRIP": "x86_64-w64-mingw32-strip",
            "WINDRES": "x86_64-w64-mingw32-windres",
            "PKG_CONFIG_LIBDIR": f"{prefix}/lib/pkgconfig:{prefix}/share/pkgconfig",
            "PKG_CONFIG_PATH": f"{prefix}/lib/pkgconfig:{prefix}/share/pkgconfig",
            # GNU/Linux fortify wrappers emit glibc-only __memcpy_chk symbols.
            # The MinGW target does not provide them, so keep fortify disabled.
            "CPPFLAGS": f"-D_FORTIFY_SOURCE=0 -I{prefix}/include",
            "CFLAGS": "-O2 -fno-ident -ffile-prefix-map=/repo=/usr/src/qonic",
            "CXXFLAGS": "-O2 -fno-ident -ffile-prefix-map=/repo=/usr/src/qonic",
            "LDFLAGS": f"-L{prefix}/lib -static -static-libgcc -static-libstdc++",
            "SOURCE_DATE_EPOCH": "1777848300",
            "TZ": "UTC",
            "LC_ALL": "C.UTF-8",
        }
    )
    return env
