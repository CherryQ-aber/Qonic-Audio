from __future__ import annotations

import os
import shutil
from pathlib import Path

from common import BUILD_ROOT, PREFIX, SOURCE_TREES, WORK, build_env, run


HOST = "x86_64-w64-mingw32"


def autotools(name: str, extra: list[str] | None = None) -> None:
    source = SOURCE_TREES / name
    configure = source / "configure"
    if not configure.is_file():
        run(["autoreconf", "-fiv"], cwd=source)
    command = [
        str(configure),
        f"--host={HOST}",
        f"--prefix={PREFIX}",
        "--disable-shared",
        "--enable-static",
        *(extra or []),
    ]
    run(command, cwd=source, env=build_env())
    run(["make", f"-j{os.cpu_count() or 2}"], cwd=source, env=build_env())
    run(["make", "install"], cwd=source, env=build_env())


def main() -> int:
    if os.environ.get("QONIC_BUILD_CONTAINER") != "1":
        raise SystemExit("dependency build is allowed only inside the pinned container")
    PREFIX.mkdir(parents=True, exist_ok=True)

    zlib_build = WORK / "build-zlib"
    shutil.rmtree(zlib_build, ignore_errors=True)
    run(
        [
            "cmake",
            "-S",
            str(SOURCE_TREES / "zlib"),
            "-B",
            str(zlib_build),
            f"-DCMAKE_INSTALL_PREFIX={PREFIX}",
            "-DCMAKE_SYSTEM_NAME=Windows",
            "-DCMAKE_C_COMPILER=x86_64-w64-mingw32-gcc-win32",
            "-DCMAKE_RC_COMPILER=x86_64-w64-mingw32-windres",
            "-DBUILD_SHARED_LIBS=OFF",
            "-DCMAKE_BUILD_TYPE=Release",
        ],
        env=build_env(),
    )
    run(["cmake", "--build", str(zlib_build), "--parallel"], env=build_env())
    run(["cmake", "--install", str(zlib_build)], env=build_env())
    zlib_static = PREFIX / "lib" / "libzlibstatic.a"
    zlib_link_name = PREFIX / "lib" / "libz.a"
    if zlib_static.is_file() and not zlib_link_name.exists():
        shutil.copy2(zlib_static, zlib_link_name)

    autotools("lame", ["--disable-frontend", "--disable-decoder"])
    autotools("libogg")
    autotools("libvorbis", ["--disable-docs", "--disable-examples", "--disable-oggtest"])
    autotools("opus", ["--disable-doc", "--disable-extra-programs"])

    rubber_build = WORK / "build-rubberband"
    shutil.rmtree(rubber_build, ignore_errors=True)
    env = build_env()
    run(
        [
            "meson",
            "setup",
            str(rubber_build),
            str(SOURCE_TREES / "rubberband"),
            "--cross-file",
            str(BUILD_ROOT / "config" / "mingw64-cross.ini"),
            f"--prefix={PREFIX}",
            "--buildtype=release",
            "-Ddefault_library=static",
            "-Dauto_features=disabled",
            "-Dfft=builtin",
            "-Dresampler=builtin",
            "-Dcmdline=disabled",
            "-Dtests=disabled",
        ],
        env=env,
    )
    run(["meson", "compile", "-C", str(rubber_build)], env=env)
    run(["meson", "install", "-C", str(rubber_build)], env=env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
