# Qonic Audio Project Status

Status date: 2026-08-13
Authority: **Source of Truth for current project status**

## Current position

Qonic Audio is a long-lived **Personal Software Project / Internal Beta** for the developer's own use and limited testing. It keeps release-grade engineering, installation, compliance, build verification, and regression standards without promising a Stable Public Release.

| Field | Current value |
| --- | --- |
| Working/project name | Qonic Audio |
| Current version | `5.0.0-beta.1` |
| Release channel | `Internal Beta` |
| Project classification | `Personal Software Project` |
| Distribution | Personal devices, limited testers, optional GitHub Pre-release |
| Stable Public Release | Does not currently exist |
| Public commercial brand | NOT FROZEN |
| Qonance | NOT ADOPTED |
| Trademark clearance | DEFERRED — PUBLIC RELEASE ONLY |
| Third-party compliance | Mandatory; current final review has 0 blockers and 2 warnings |

## Source-of-truth map

- Current project status: this file.
- Release and distribution policy: `docs/RELEASE_STRATEGY.md`.
- Central application version/channel metadata: `app_info.py`.
- Historical authoritative release baseline: `Release/External_Test/2026-07-30_audio-validation-fix/RELEASE_AUTHORITY.json`.
- Current third-party compliance conclusions: `docs/compliance/FINAL_THIRD_PARTY_COMPLIANCE_REVIEW.md` and `THIRD_PARTY_DEPENDENCY_INVENTORY.json`.
- Active and future release gates: `TEST_CHECKLIST.md`.
- Current known problems: `Known_Issues.md`.

Historical r3/r4 publication-candidate reports remain evidence from the former public-release plan. They do not override this current policy.

## Distribution policy

- Internal Beta installers and optional portable builds may be used on the owner's Windows devices and shared with named/limited testers.
- GitHub releases, if used, must be marked **Pre-release**.
- Release notes must say that the build belongs to an ongoing personal software project and is not an Official Stable Public Release.
- No build may be described as Latest Stable, Production Release, Official Release, or Public Stable Release.
- A 1.x or higher version number never activates Stable status by itself.

## Installer and user data

- The existing PyInstaller `onedir` remains the runtime/build architecture.
- The Inno Setup layer provides Program Files installation, Start Menu entry, optional desktop shortcut, and uninstall capability.
- Frozen builds store configuration, cache, logs, and temporary data under `%LOCALAPPDATA%\Qonic Audio`.
- Default user output is under the user's Music directory, not Program Files.
- Uninstall and upgrade preserve LocalAppData. A former beside-the-executable `config.json` is copied once when the LocalAppData configuration does not yet exist.

## Compliance status

Qt, PySide6, Shiboken6, Qt Multimedia FFmpeg, the Qonic FFmpeg Audio Runtime, ncmdump, CPython/Python dependencies, Microsoft VC Runtime, `LICENSES`, notices, manifests, source-availability records, and SHA-256 evidence remain in force. Internal Beta does not relax redistribution obligations.

The final third-party review currently records:

- CLOSED: Qt/PySide6/Shiboken6 LGPL route, FFmpeg Audio Runtime, ncmdump, Microsoft VC Runtime, and the recorded Python/runtime components.
- WARNING: exact libffi source release is not embedded; exact frozen PyInstaller bootloader version is not embedded.
- BLOCKER: none.

## Active Internal Beta blockers

- Any P0/P1 data-loss, source-overwrite, install/uninstall, runtime-dependency, configuration-migration, or core-workflow regression.
- Failed complete automated regression or packaged QML smoke for a candidate.
- Missing required licences/notices/source-availability material in a distributed candidate.
- A candidate that depends on user-installed Python, FFmpeg, ncmdump, or development tools.
- Installer compilation is PASS for `5.0.0-beta.1`. Actual install, launch, upgrade data-preservation, uninstall, and clean-machine acceptance remain NOT RUN.

## Deferred Public-Release items

Brand freeze, trademark clearance/registration, company formation, commercial signing, Stable channel policy, public support commitments, website/store distribution, marketing, and any commercial privacy/legal program are `DEFERRED — PUBLIC RELEASE ONLY`.

They do not block Internal Beta development, installation, personal use, limited testing, or an optional GitHub Pre-release.

```text
Brand: NOT FROZEN
Qonance: NOT ADOPTED
Formal trademark clearance: DEFERRED
```

## Testing status

The current source passed `636 passed, 2 warnings, 76 subtests`, five source QML smokes, syntax/import checks, and metadata/storage/installer-contract tests. The raw PyInstaller onedir and archive built successfully. The existing Qt LGPL route removed all 687 verified GPL-only files from an independent candidate and passed five packaged smokes.

Current portable candidate:

- `Release/Internal_Beta_Candidates/2026-08-13_5.0.0-beta.1/Qonic_Audio_v5.0.0-beta.1_Internal_Beta_LGPL.7z`
- SHA-256 `6408218ECBC710160A6008CB7999BBD70C8AF0C5A29BDC38119F4807241C8A15`
- Candidate status: build verified; not yet a GitHub Pre-release; manual installed-machine tests remain pending.

Current installer candidate:

- `Release/Installer_Candidates/Qonic_Audio_v5.0.0-beta.1_Setup.exe`
- SHA-256 `544F9762D07B3BEB3FD8C271D4558E6CD084BD3655C4FC631F605BBB97EE225C`
- Build status: PASS with Inno Setup 6.7.3; version resources identify `5.0.0-beta.1` / `Internal Beta`.
- Language policy: Windows UI language auto-detection with no extra selector; `zh-CN` uses Simplified Chinese and other unsupported UI languages fall back to English. Previous installer language is not reused on upgrade.
- Installer compliance material: the Inno Setup licence is included under the installed `LICENSES` directory; the pinned Simplified Chinese message source retains its upstream provenance and licence reference.
- Signature status: WARNING (`NotSigned`); signing remains an optional Internal Beta enhancement.
- Installed-machine acceptance: NOT RUN.

The first English-only installer candidate is preserved under `Release/Non_Authoritative/2026-08-12_5.0.0-beta.1_english-installer-baseline/` with status `NOT FOR RELEASE`.

Strict historical-manifest validation returned 0 blockers and 6 warnings. Two are component evidence warnings (libffi and PyInstaller); the others concern manifest age and the historical/full-PyInstaller baseline. See `TEST_CHECKLIST.md` for exact commands and classifications.

The 2026-07-30 historical baseline and r4 evidence retain their recorded results but do not substitute for current candidate verification.
