# Building

## Prerequisites

Use Docker or Podman with Linux/amd64 container support. Do not install a
toolchain ad hoc and do not run the inner Python builders directly on Windows.

From the repository root:

```powershell
.\third_party\ffmpeg-build\build.ps1
```

The wrapper builds `config/Dockerfile`, mounts the repository at `/repo`, then
runs `build.sh`. Source downloads are accepted only when their SHA-256 values
match `lock/sources.lock.json`.

Expected outputs:

- `output/candidate/ffmpeg.exe`
- `output/candidate/ffprobe.exe`
- `output/candidate/BUILD_MANIFEST.json`
- `output/candidate/capabilities.json`
- `output/candidate/LICENSES/`
- `output/source-bundle/qonic-ffmpeg-complete-corresponding-source.tar.gz`

Run the static and source-cache checks without building:

```powershell
.\third_party\ffmpeg-build\verify.ps1
```

The candidate must pass B4 regression and owner review before any separate
replacement operation is designed. This repository intentionally has no
automatic candidate-to-runtime copy script.
