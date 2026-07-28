#!/usr/bin/env bash
set -euo pipefail

if [[ "${QONIC_BUILD_CONTAINER:-}" != "1" ]]; then
  echo "Refusing to build outside the pinned Qonic container." >&2
  exit 2
fi

python3 third_party/ffmpeg-build/scripts/download_sources.py
python3 third_party/ffmpeg-build/scripts/verify_sources.py
python3 third_party/ffmpeg-build/scripts/prepare_sources.py
python3 third_party/ffmpeg-build/scripts/build_dependencies.py
python3 third_party/ffmpeg-build/scripts/build_ffmpeg.py
python3 third_party/ffmpeg-build/scripts/collect_licenses.py
python3 third_party/ffmpeg-build/scripts/generate_build_manifest.py
python3 third_party/ffmpeg-build/scripts/generate_source_bundle.py
