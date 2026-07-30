# FFmpeg replacement proposal (B5)

Status: **COMPLETED — FORMAL REPLACEMENT VERIFIED**

Generated: 2026-07-28T06:51:16.295874+00:00

## Decision requested

Approve or reject replacement of the two formal runtime files with the B3
Qonic candidate. This proposal does **not** perform that replacement. Until the
project owner explicitly replies with approval to replace, the formal runtime,
the authoritative expanded package and the authoritative `.7z` remain frozen.

## Why replacement is proposed

The current Gyan 8.1.1 GPL build is usable and remains byte-verified, but its
precise provider build scripts, patch set and complete static dependency source
identity are not publicly available. The Qonic candidate instead has fixed
source archives, build environment lock, configure allowlist, build scripts,
license inventory and a corresponding-source bundle.

## Exact proposed file changes

| Runtime file | Current formal SHA-256 | Current bytes | Candidate SHA-256 | Candidate bytes | Change |
|---|---:|---:|---:|---:|---:|
| `Tools/ffmpeg/bin/ffmpeg.exe` | `09948D4CDD0650DA6FF5A87577469F2A218DC2615AE379F8F734D24C49DE0F73` | 227,398,656 | `CA2BCCBF1A2A5A379AE484AD127D120CC3E394833B69767694A1E738F2D6BE55` | 6,362,112 | -221,036,544 bytes |
| `Tools/ffmpeg/bin/ffprobe.exe` | `A6618E99BB58869DED3C6F37B53AA1A8D701C3591DBB7B5B317D47369C112BE2` | 227,193,344 | `4EC2AC9385AACBAF927B7E8D031291059CEA2E02EE6BFAE0D708F78E1C528251` | 6,162,944 | -221,030,400 bytes |

The candidate reduces the two executable files by 442,066,944 bytes in total. No application call site or runtime path contract changes: both binaries remain independent programs at the existing `Tools/ffmpeg/bin` paths.


## Runtime scope boundary

This candidate is the **Qonic Audio Converter Audio Runtime** only. It is not a
permanent, universal FFmpeg runtime for every Qonic project. Future video
visualization work must use a separately controlled FFmpeg Video Runtime or a
newly generated and independently reviewed build at the point of formal
integration. Potential future video features do not justify retaining the
un-auditable broad Gyan build in this audio release.

## Configure and capability change

The candidate is a deliberately scoped audio build: GPL/version3 enabled;
`--disable-nonfree`, `--disable-network`, `--disable-autodetect` and
`--disable-everything` are present, followed by explicit enables for Qonic's
required decoders, encoders, containers, `file`/`pipe`, and Rubber Band pitch
filters. The current Gyan build carries broad network, video, hardware, subtitle
and device capability that Qonic's command inventory marks out of scope.

| Listing | Formal count | Candidate count | Expected removals | Additions |
|---|---:|---:|---:|---:|
| Formats | 131 | 19 | 124 | 12 |
| Filters | 576 | 20 | 556 | 0 |
| Protocols | 44 | 2 | 42 | 0 |

All required project filters and protocols are present. Removed capability is
classified as `EXPECTED_REMOVAL` only when it is outside Qonic's locked feature
requirements; B4 found no functional regression in the promised media and app
workflows. The full machine-readable lists are in
`compliance/report/ffmpeg-self-build/b5-replacement-readiness.json`.

## Evidence and tests

- B3: seven source archives verified; fixed FFmpeg commit; static build with
  system-DLL-only imports; source bundle SHA-256
  `2B3A9A878B46050CACA71253C1E43F6239DE91C5C5C59DC72F8F2E0306A5C35A` (32,321,797 bytes, 63 entries).
- B3 validation: Windows functional matrix 21/21; build/compliance tests 44/44.
- B4: isolated onedir 55/55, including all promised inputs/outputs, single and
  batch conversion, cancellation, corrupt/locked files, Unicode/long/cross-drive
  paths, ffprobe, pitch preview/export, metadata, lyrics, cover preservation and
  packaged smoke.
- B4 isolated package comparison: 3004 non-FFmpeg files were
  byte-identical; only the two candidate executables differed before launch.

## Rollback plan if approval is granted

1. Copy the current formal `ffmpeg.exe` and `ffprobe.exe`, without modification,
   to a new dated `Release/Non_Authoritative/.../former-gyan/` archive and record
   their current SHA-256 values.
2. Copy the two verified candidate files into `Tools/ffmpeg/bin`.
3. Rebuild the single supported PyInstaller `onedir` package from the approved
   commit; do not create a onefile variant.
4. Run full regression, packaged smoke, archive integrity and final formal hashes.
5. Regenerate Manifest, Notices, compliance report and release inventory.
6. Freeze the new archive SHA-256. If any check fails, restore the two files from
   the dated former-Gyan archive and stop.

## Files that a future approved replacement would modify

- `Tools/ffmpeg/bin/ffmpeg.exe`
- `Tools/ffmpeg/bin/ffprobe.exe`
- newly rebuilt onedir output and new archive, not the frozen historical archive
- third-party Manifest, Notices, audit report, release inventory and B5 result
  records

## Current gate

Technical readiness: **READY_FOR_CONDITIONAL_AUTHORIZATION**.

Conditional authorization was recorded as **READY_FOR_CONDITIONAL_AUTHORIZATION**. Owner approval, formal replacement, clean onedir rebuild, archive integrity, Corresponding Source verification, three packaged smoke tests and full regression have now completed. Final replacement status: **FORMAL_REPLACEMENT_VERIFIED**; see `compliance/report/ffmpeg-self-build/b5-final-release-verification.json`.
