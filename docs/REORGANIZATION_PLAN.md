# Reorganization Plan

Plan date: 2026-08-12
Status: approved by task scope; implementation may proceed after the read-only audit.

## Target state

Qonic Audio remains a working project name for a long-lived Personal Software Project distributed through the `Internal Beta` channel. GitHub builds, if published, are Pre-releases only. There is no current Stable or Official Public Release target.

The first explicit channel build will use `5.0.0-beta.1`, preserving the existing 5.x lineage and avoiding a forced return to 0.x.

## Files to add

- `docs/PROJECT_STATUS.md`: single source of truth for current version, channel, distribution, brand, compliance, blockers, deferred items, and testing status.
- `docs/CURRENT_STATE_AUDIT.md`: pre-change evidence and classification record.
- `docs/REORGANIZATION_PLAN.md`: this controlled implementation plan.
- `installer/Qonic_Audio_Internal_Beta.iss`: reproducible install/uninstall layer for the existing PyInstaller onedir.
- `build_installer.ps1`: validates centralized metadata, invokes the existing application build, then compiles the installer when Inno Setup is available.
- Targeted governance/storage/installer tests under `tests/`.

## Files to modify

### Current policy and status

- `README.md`: identify the project as Personal / Internal Beta and allow only GitHub Pre-release distribution.
- `docs/RELEASE_STRATEGY.md`: become the release/distribution policy source of truth; replace RC1 promotion with Internal Beta and deferred Public Stable gates.
- `docs/compliance/PUBLIC_RELEASE_READINESS.md`: retain the future checklist but mark it `DEFERRED — PUBLIC RELEASE ONLY`.
- `docs/compliance/PUBLIC_RELEASE_OWNER_GATE_STATUS.json`: preserve the prior public-release decision as historical context while making the current policy deferred rather than blocked.
- `docs/compliance/FINAL_THIRD_PARTY_COMPLIANCE_REVIEW.md`: add the current Internal Beta distribution boundary without changing component conclusions.
- `Known_Issues.md`, `TEST_CHECKLIST.md`, `Release_Notes_v5.0_Internal_Test.md`, and `CHANGELOG.md`: align current status and gates.

### Central metadata and UI surfaces

- `app_info.py`: keep the single version source and add version, channel, project classification, package, and installer labels.
- `windows_version_info.txt`: show `5.0.0-beta.1` / Internal Beta in Windows file properties.
- `ui_next/bridge/app_state_viewmodel.py`: expose channel/project classification through the existing About/status surface without redesigning QML.
- Existing metadata tests: update centralized expectations only.

### Installed-data and build infrastructure

- `config.py`: separate runtime files from installed user data in frozen mode; add one-time legacy `config.json` migration; keep source-tree development behavior and existing config schema.
- `logger.py`: use the centralized log directory selected by `config.py`.
- `build_release.ps1`: stop creating mutable user-data directories in the program tree and include current governance documents in the package.
- Installer build tests/config syntax checks: confirm Start Menu, optional desktop shortcut, uninstall, Program Files target, and preservation of LocalAppData.

### Cross-conversation project memory

- Update `Codex_memory/PROJECT_STATUS.md`, `TODO.md`, `CHANGELOG.md`, `NOTES.md`, and `MEMORY.json` after verification, as required by the repository instructions.

## Files not modified

- Audio algorithms and services: `converter.py`, `watcher.py`, metadata/lyrics/audio processing implementations.
- QML layouts, navigation architecture, and player architecture.
- FFmpeg build chain, Qt runtime minimization, third-party binaries, licence texts, notices, source archives, and historical release artifacts.
- Repository name, installation data namespace migration beyond the existing Qonic working name, and all Qonance references (none will be introduced).

## Delete/archive policy

- Delete: none.
- Archive/move: none.
- Historical publication reports and candidates remain in place and are classified as evidence from the former public-release plan.

## Blocker reclassification

- Qonic trademark clearance changes from a current build blocker to `DEFERRED — PUBLIC RELEASE ONLY`.
- Company formation, official branding, commercial signing, website/store, marketing, Stable channel, and public support become deferred Public Stable gates.
- Installer capability and installed-data separation remain active Internal Beta engineering requirements.
- Third-party licence gaps, P0/P1 data-loss defects, missing runtime dependencies, failed regression, or failed packaged smoke remain Internal Beta blockers.

## Build impact

- PyInstaller stays `onedir`; FFmpeg and Qt contents are not changed by policy.
- Package identity changes to the explicit beta label from the centralized metadata source.
- The installer wraps the onedir output; it does not replace or restructure it.
- Existing portable builds remain possible for controlled testing.
- Full installer compilation is expected to be `NOT RUN` in the current environment unless an Inno Setup compiler becomes available; config and metadata checks will still run.

## Acceptance boundary

No business-logic refactor, brand migration, installer-framework replacement, Qt/FFmpeg rebuild, QML redesign, or core workflow change is authorized by this plan.
