# Qonic Audio Release and Distribution Policy

Authority: **Source of Truth for release channels, distribution, and gates**

Effective: 2026-08-12

## Current policy

Qonic Audio is a Personal Software Project under active development. The current and default release channel is **Internal Beta**. It may remain in this channel indefinitely regardless of feature count or major version number.

There is currently no Stable, Official Public, Production, or Latest Stable release. Only the project owner can explicitly reactivate a Public Stable process in the future.

## Release flow

```text
Development Build
↓
Internal Validation
↓
Internal Beta Build
↓
GitHub Pre-release (optional)
↓
Personal / limited tester use
↓
Continue iteration
```

## Channels

- `dev`: local development and incomplete validation.
- `internal`: owner/internal validation candidate.
- `beta`: installable Internal Beta candidate for personal or limited tester use.

Current channel: `beta` / **Internal Beta**.

The centralized version source is `app_info.py`. The first build under this policy is `5.0.0-beta.1`; the project is not forced back to 0.x.

## GitHub distribution

GitHub may host source, documentation, issues, roadmap, changelog, tests, build scripts, tags, and Internal Beta artifacts. Every binary Internal Beta release must be marked **Pre-release**.

Allowed artifacts include:

- Windows installer;
- optional portable PyInstaller onedir archive;
- SHA-256 checksum file;
- `LICENSE`, third-party notices/licences, and required source-availability material;
- release notes and known issues.

Required release-note statement:

> Internal Beta Build
>
> This build is part of an ongoing personal software project. It is primarily maintained for personal use and limited testing. It is not an official stable public release.

Internal Beta releases must not use `Latest Stable`, `Official Stable`, `Production Release`, or `Public Stable Release` labels.

## Installer policy

The installer is retained as core infrastructure because the application is a long-lived desktop tool. The existing PyInstaller `onedir` remains the application runtime; the installer only installs that verified tree.

The active installer contract includes:

- installation under Program Files;
- Start Menu entry;
- optional desktop shortcut;
- uninstall support;
- configuration/cache/log/temp outside the program directory;
- preserved LocalAppData during uninstall and upgrades;
- bundled runtime dependencies, licences, and notices.

Unsigned Internal Beta installers may be shared with named testers with clear checksum and SmartScreen expectations. Commercial code signing is optional and not a current blocker.

## Internal Beta Gate — active

A candidate may be installed or optionally published as a GitHub Pre-release only when:

1. centralized version and channel metadata are consistent;
2. PyInstaller onedir and installer builds complete from controlled scripts;
3. package runs without user-installed Python, FFmpeg, ncmdump, or developer tools;
4. install, upgrade-data preservation, and uninstall behavior are verified;
5. config/cache/log/temp remain outside Program Files;
6. source protection, no-clobber, and configuration migration remain valid;
7. complete regression, QML smoke, and installer/package checks pass;
8. licences, notices, runtime inventory, corresponding source, and SHA-256 artifacts are present;
9. P0/P1 defects are closed or explicitly block the candidate.

Detailed statuses are recorded in `TEST_CHECKLIST.md`.

## Public Stable Gate — deferred

Status: **DEFERRED — PUBLIC RELEASE ONLY**.

This future gate includes public brand clearance, trademark decisions, Stable-channel policy, public support commitments, commercial signing if chosen, website/store/marketing work, and applicable public privacy/legal documents. Company formation is not presumed to be necessary unless a future owner decision and distribution model require it.

None of these items blocks Internal Beta development or limited distribution.

## Optional enhancements

Automatic updates, crash reporting, release automation, GitHub Actions builds, signing, file associations, and incremental updates may be developed later. They are not current Internal Beta blockers unless a candidate explicitly depends on them.

## Historical evidence

The 2026-07-30 authority record and r3/r4 public-publication candidate evidence remain intact. They document earlier technical/compliance work but do not establish a current public-release target.
