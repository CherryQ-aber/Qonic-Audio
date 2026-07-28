from __future__ import annotations

import shutil
from pathlib import Path

from common import OUTPUT, SOURCE_TREES, write_json


LICENSE_CANDIDATES = {
    "ffmpeg": ["COPYING.GPLv3", "COPYING.GPLv2", "COPYING.LGPLv3", "COPYING.LGPLv2.1"],
    "zlib": ["LICENSE"],
    "lame": ["COPYING", "LICENSE"],
    "libogg": ["COPYING"],
    "libvorbis": ["COPYING"],
    "opus": ["COPYING"],
    "rubberband": ["COPYING", "src/ext/kissfft/COPYING"],
}


def main() -> int:
    destination = OUTPUT / "candidate" / "LICENSES"
    destination.mkdir(parents=True, exist_ok=True)
    inventory = []
    for project, candidates in LICENSE_CANDIDATES.items():
        source_root = SOURCE_TREES / project
        copied = []
        for relative in candidates:
            source = source_root / relative
            if not source.is_file():
                continue
            output_name = f"{project}-{relative.replace('/', '-')}"
            shutil.copy2(source, destination / output_name)
            copied.append(output_name)
        if not copied:
            raise FileNotFoundError(f"no license file collected for {project}")
        inventory.append({"component": project, "files": copied})
    write_json(destination / "license-inventory.json", {"components": inventory})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
