# Candidate validation report

Status: **B3 PASS — B4/B5 PENDING**

On 2026-07-26 the pinned Qonic build route completed on Docker Desktop
`linux/amd64`. All seven locked source archives matched their SHA-256 values,
the MinGW-w64 dependency chain and FFmpeg were rebuilt from the prepared source
trees, and the candidate remained isolated under
`third_party/ffmpeg-build/output/candidate/`.

## Candidate identity

- FFmpeg 8.1.1 source commit:
  `239f2c733de417201d7ad3b3b8b0d9b63285b2b1`
- `ffmpeg.exe` SHA-256:
  `CA2BCCBF1A2A5A379AE484AD127D120CC3E394833B69767694A1E738F2D6BE55`
- `ffprobe.exe` SHA-256:
  `4EC2AC9385AACBAF927B7E8D031291059CEA2E02EE6BFAE0D708F78E1C528251`
- imported DLLs: `KERNEL32.dll`, `SHELL32.dll`, `bcrypt.dll`, `msvcrt.dll`
- required filters and protocols: complete (`required_check.ok = true`)

## Validation completed

- Windows synthetic matrix: **21/21 passed**
  - MP3, FLAC, AAC, M4A, OGG/Vorbis and Opus encode plus ffprobe JSON;
  - Unicode input/output paths;
  - Rubber Band pitch +12/-12 semitones with 2.0-second duration retained;
  - `-progress pipe:1`;
  - raw `s16le` file and stdout pipe, both 32,000 bytes for the fixed fixture.
- Final full clean rebuild produced the same candidate hashes as the tested
  candidate; the raw stdout-pipe check was rerun after that build.
- Static build/source tests: **23 passed**.
- Combined compliance/build tests: **44 passed**.
- The generated manifest records the compiler, pinned package versions,
  lockfile hashes, binary hashes and imported DLLs.

## Corresponding Source

`qonic-ffmpeg-complete-corresponding-source.tar.gz`:

- SHA-256:
  `ECC7838B64C530852C766DF55ECC6FC9432FBDA924D229B4497FB6B68C377BB7`
- size: `32,280,949` bytes
- entries: `49`
- Python cache, bytecode and backup entries: `0`

The bundle contains the locked source archives, build configuration, Windows
and Linux entry scripts, verification script, tests, patch directory,
license/source-offer documents and lockfiles tied to this candidate.

## Build issues closed

The run exposed and closed five reproducibility defects: Python 3.11 tar API
compatibility, Opus/MinGW fortify linkage, the internal `pcm_s16le` muxer name,
Windows PowerShell 5.1 native-stderr handling, and source-bundle cache/backup
filtering. Upstream compiler warnings remain recorded, but no warning caused a
build or validation failure.

## Boundary and remaining work

The formal binaries and authoritative release archive were not modified.
`Tools/ffmpeg/bin/ffmpeg.exe`, `Tools/ffmpeg/bin/ffprobe.exe`, and
`Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test.7z`
retain their frozen hashes.

B3 is complete. B4 must still run the candidate inside an isolated PyInstaller
onedir copy with the full automated and real-media matrix. Only after B4 may a
B5 replacement proposal be prepared for the project owner's explicit approval.
`FFMPEG_BUILD_CHAIN_INCOMPLETE` therefore remains open.
