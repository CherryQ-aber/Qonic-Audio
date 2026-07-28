from __future__ import annotations

import os
import shutil
from pathlib import Path

from common import LOCKS, OUTPUT, PREFIX, SOURCE_TREES, WORK, build_env, load_json, run


def main() -> int:
    if os.environ.get("QONIC_BUILD_CONTAINER") != "1":
        raise SystemExit("FFmpeg build is allowed only inside the pinned container")
    build_dir = WORK / "build-ffmpeg"
    shutil.rmtree(build_dir, ignore_errors=True)
    build_dir.mkdir(parents=True)
    configure_lock = load_json(LOCKS.parent / "config" / "feature-profile.json")
    env = build_env()
    run(
        [str(SOURCE_TREES / "ffmpeg" / "configure"), *configure_lock["configure_flags"]],
        cwd=build_dir,
        env=env,
    )
    run(["make", f"-j{os.cpu_count() or 2}"], cwd=build_dir, env=env)

    candidate = OUTPUT / "candidate"
    shutil.rmtree(candidate, ignore_errors=True)
    candidate.mkdir(parents=True)
    for name in ("ffmpeg.exe", "ffprobe.exe"):
        source = build_dir / name
        if not source.is_file():
            raise FileNotFoundError(source)
        target = candidate / name
        shutil.copy2(source, target)
        run(["x86_64-w64-mingw32-strip", str(target)])

    configure_text = (build_dir / "config.h").read_text(
        encoding="utf-8", errors="replace"
    )
    (candidate / "config.h").write_text(configure_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
