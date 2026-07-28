# B4 isolated onedir regression report

Status: **PASS — 55 passed, 0 failed, 0 blocked**

Run date: 2026-07-28

## Tested package

- Authoritative baseline:
  `Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test.7z`
- Fresh isolated onedir:
  `third_party/ffmpeg-build/output/b4-isolated/2026-07-28-verified/Qonic_Audio_v5.0_internal_test`
- Baseline and isolated package file count before launch: `3,006`
- Non-FFmpeg files compared: `3,004`
- Unexpected differences: `0`

Only the two isolated FFmpeg executables differed from the authoritative
expanded release:

- candidate `ffmpeg.exe`:
  `CA2BCCBF1A2A5A379AE484AD127D120CC3E394833B69767694A1E738F2D6BE55`
- candidate `ffprobe.exe`:
  `4EC2AC9385AACBAF927B7E8D031291059CEA2E02EE6BFAE0D708F78E1C528251`

## Media fixture policy

All audio content was generated locally from a three-second, 440 Hz synthetic
tone. No third-party music or unknown copyrighted sample was downloaded.

MP3, FLAC, WAV, AAC, M4A, OGG/Vorbis, Opus, AIFF, ALAC and WMA fixtures were
generated with the frozen Gyan FFmpeg solely as fixture preparation. APE was
generated from the same synthetic WAV with the official Monkey's Audio 13.20
console encoder, extracted without installation from:

- source: `https://monkeysaudio.com/x64`
- installer SHA-256:
  `091931DC828ADE7A7EC3ABB380D8612FCC44E956F9AD1B3BEC227F8A70C492F1`

The fixture encoder, installer and generated media are ignored test evidence
and are not included in the product or release package.

## Passed coverage

- Input decode: MP3, FLAC, WAV, M4A, AAC, OGG, Opus, APE, AIFF, ALAC and WMA.
- Output encode plus candidate ffprobe: MP3, FLAC, WAV, AAC, M4A, OGG and Opus.
- Project single-file conversion: all 11 input formats to FLAC.
- Project queue engine: two-item conversion and active child cancellation.
- Pitch: negative preview plus negative and positive export.
- Preservation: title, artist, album, embedded lyrics and attached cover.
- Failure handling: corrupt input and exclusively locked input.
- Path handling: Unicode, Chinese, spaces, path length 287 and D-to-C drive output.
- Packaged onedir smoke: Audio Editor, Auto Convert and Settings, all exit `0`.

The machine-readable report, including each individual check, is
`b4-regression-report.json`. The reusable runner is
`Tools/compliance/run_b4_regression.py`.

## Frozen boundary verification

The following SHA-256 values were checked before and after B4 and did not
change:

- authoritative archive:
  `649E38524AF2F3DCE33FCBC43AC29B7111623D033F3537DE55EF5CD45994E926`
- formal `Tools/ffmpeg/bin/ffmpeg.exe`:
  `09948D4CDD0650DA6FF5A87577469F2A218DC2615AE379F8F734D24C49DE0F73`
- formal `Tools/ffmpeg/bin/ffprobe.exe`:
  `A6618E99BB58869DED3C6F37B53AA1A8D701C3591DBB7B5B317D47369C112BE2`

## Conclusion and remaining boundary

B4 is complete. The isolated candidate meets the tested Qonic Audio onedir
runtime and real-media requirements.

B5 has not started. This report does not authorize copying the candidate into
`Tools/ffmpeg/bin`, the authoritative expanded release, the authoritative
archive, or any release tag. Formal replacement still requires the project
owner's explicit B5 approval.
