# FFmpeg Audio Runtime Notice

Qonic Audio distributes the following external audio-runtime tools:

- `Tools/ffmpeg/bin/ffmpeg.exe`
- `Tools/ffmpeg/bin/ffprobe.exe`

They are the Qonic-maintained **Qonic Audio Converter Audio Runtime** build of
FFmpeg 8.1.1. This runtime is limited to audio features; a future video feature
requires a separate controlled runtime and review.

## Binary identity

| File | SHA-256 |
| --- | --- |
| `ffmpeg.exe` | `CA2BCCBF1A2A5A379AE484AD127D120CC3E394833B69767694A1E738F2D6BE55` |
| `ffprobe.exe` | `4EC2AC9385AACBAF927B7E8D031291059CEA2E02EE6BFAE0D708F78E1C528251` |

The build is GPL-3.0-or-later and includes the GPL/version3 and Rubber Band
route. The applicable GPLv3 text is the top-level `LICENSE` and is also
included in the corresponding-source bundle.

## Corresponding source

For every publication candidate or release containing these binaries, the
complete corresponding-source archive must be included as
`Corresponding_Source/qonic-ffmpeg-complete-corresponding-source.tar.gz`.

| Archive | SHA-256 |
| --- | --- |
| `qonic-ffmpeg-complete-corresponding-source.tar.gz` | `2B3A9A878B46050CACA71253C1E43F6239DE91C5C5C59DC72F8F2E0306A5C35A` |

It contains the exact FFmpeg and static-dependency sources, build scripts,
patches, locks, configure parameters, licence texts and rebuild instructions.
The same archive is retained in `third_party/ffmpeg-build/output/source-bundle/`
for release assembly.
