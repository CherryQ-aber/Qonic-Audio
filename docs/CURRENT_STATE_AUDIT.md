# Current State Audit

Audit date: 2026-08-12
Audit mode: read-only evidence review before reorganization
Scope: project governance, release policy, distribution, version metadata, installer readiness, user-data paths, compliance evidence, and release checks.

## Executive conclusion

The repository already has a strong PyInstaller `onedir` build, automated regression suite, packaged QML smoke, SHA-256 generation, and substantial third-party compliance evidence. It does not currently have a reproducible installer/uninstaller definition, and frozen builds write configuration, cache, temporary data, logs, and default output directories beside the executable. Those two gaps are Internal Beta engineering requirements, not Public Stable branding requirements.

The current documentation is also split between an older `v5.0 Internal Test` position and a later planned `1.0.0` public release blocked by Qonic trademark clearance. The requested policy supersedes the planned public-release path: the active channel must become Internal Beta, while Public Stable and formal brand clearance become deferred future gates.

## Evidence reviewed

- Project and cross-conversation state: `Codex_memory/PROJECT_STATUS.md`, `TODO.md`, `CHANGELOG.md`, `NOTES.md`, and `MEMORY.json`.
- Current public-facing state: `README.md`, `CHANGELOG.md`, `Known_Issues.md`, `TEST_CHECKLIST.md`, `Release_Notes_v5.0_Internal_Test.md`, and `docs/RELEASE_STRATEGY.md`.
- Version and product metadata: `app_info.py`, `windows_version_info.txt`, `ui_next/bridge/app_state_viewmodel.py`, and `Qonic_Audio.spec`.
- Build and distribution: `build_release.ps1`, `.github/workflows/`, `EXTERNAL_TEST_GUIDE.md`, and tracked installer/setup files.
- Runtime storage: `config.py`, `logger.py`, and `cache_manager.py`.
- Compliance: `LICENSE`, `LICENSES/`, `third_party/`, `compliance/`, `docs/compliance/`, and `Tools/compliance/`.
- Release authority: all `RELEASE_AUTHORITY.json` records under `Release/External_Test/`.

## Current authority map

| Topic | Current source | Audit finding |
| --- | --- | --- |
| Historical release baseline | `Release/External_Test/2026-07-30_audio-validation-fix/RELEASE_AUTHORITY.json` | Authoritative historical baseline: `Qonic_Audio_v5.0_internal_test.7z`, SHA-256 `BB0967E85AF2857C23587F3CEF37C37D14ED4E4106B7261F21E2F247B47F42F4`. Must remain unchanged. |
| Version/package name | `app_info.py` | Centralized correctly, but identifies `5.0 Internal Test`, not the new Internal Beta channel. |
| Release strategy | `docs/RELEASE_STRATEGY.md` | Still drives toward RC1 and treats the installer as a later item. This conflicts with the requested long-term Internal Beta model. |
| Public-release gate | `docs/compliance/PUBLIC_RELEASE_READINESS.md` and `PUBLIC_RELEASE_OWNER_GATE_STATUS.json` | Treats trademark clearance as a current public-release blocker and records a selected public version `1.0.0`. It must become a deferred future gate, not an Internal Beta blocker. |
| Third-party compliance | `docs/compliance/FINAL_THIRD_PARTY_COMPLIANCE_REVIEW.md` plus machine inventory | Strong evidence: 0 unknown native owners, 0 compliance blockers, 2 recorded warnings in the final review. Must not be weakened. |
| Installer | No tracked `.iss`, `.nsi`, `.wxs`, MSI, or equivalent definition | No reproducible install/uninstall capability exists. Existing `*_Installer_Test.exe` files are 7z SFX test artifacts, not installers. |
| User-data paths | `config.py`, `logger.py` | Frozen mode resolves `config.json`, `Cache`, `Temp`, `logs`, and default outputs beside `sys.executable`; this is incompatible with a normal Program Files installation. |

## Public-release wording and duplicated responsibilities

The following current materials still point toward a near-term RC/Public Release path:

- `docs/RELEASE_STRATEGY.md`: RC1 promotion is the active target.
- `docs/compliance/PUBLIC_RELEASE_READINESS.md`: public release is actively blocked by trademark clearance.
- `docs/compliance/PUBLIC_RELEASE_OWNER_GATE_STATUS.json`: `overall_status` is `BLOCKED_BY_QONIC_TRADEMARK_CLEARANCE` and public version `1.0.0` is selected.
- `README.md`, `Known_Issues.md`, `TEST_CHECKLIST.md`, and root `CHANGELOG.md`: installer is deferred until after RC.
- `Codex_memory` current state: repeats the planned 1.0.0 and trademark blocker as active work.

The historical r3/r4 publication-candidate evidence is not duplicated current policy. It should be retained unchanged and described as historical evidence produced under the former public-release plan.

## Gate reclassification

### A. Internal Beta requirements

| Requirement | Current result | Evidence / action |
| --- | --- | --- |
| Central version and channel metadata | WARNING | Central version exists; explicit `Internal Beta` channel is missing. |
| PyInstaller onedir build without user Python | PASS | Existing spec/build pipeline and prior packaged smoke evidence. Must be revalidated after metadata changes. |
| Installer/uninstaller, Start Menu, optional desktop shortcut | BLOCKER | No reproducible installer definition is tracked. |
| Program files separated from config/cache/log/temp | BLOCKER | Frozen paths currently point beside the executable. |
| Configuration migration and preservation | WARNING | Atomic save and `.bak` exist; no installed-mode migration from the former portable/executable directory exists. |
| Source-file protection and no-clobber | PASS | Existing implementation and regression evidence; out of scope for modification. |
| Third-party notices/licences/runtime inventory | PASS WITH WARNINGS | Final review records no blocker; libffi and PyInstaller exact-version evidence remain warnings. |
| SHA-256 generation and archive integrity | PASS | Existing release script generates and tests archives. |
| Core automated regression and QML smoke | NOT RUN | Must be rerun after implementation. |
| New installer candidate build | NOT RUN | Inno Setup compiler is not installed in the audited environment. |

### B. Deferred — Public Release only

- Formal public/commercial brand freeze and target-market clearance.
- Trademark registration or formal trademark opinion.
- Company/legal entity creation.
- Stable channel activation and an Official Public Release date.
- Commercial code-signing program.
- Marketing site, store submission, promotion, paid plans, and large-scale support.
- Public-facing privacy/legal program where a future feature or distribution model requires it.

These items must not block Internal Beta use, installer builds, or optional GitHub Pre-releases.

### C. Optional enhancements

- Automatic updates, crash reporting, CI release automation, incremental updates, file associations, and optional signing.

## Brand and legal classification

- Current Qonic name: working/project name only.
- Public commercial brand: NOT FROZEN.
- Qonance: NOT ADOPTED.
- Trademark registration: not required for the current Internal Beta.
- Formal brand clearance: deferred until an Official Public Release is planned.
- Third-party licence compliance: remains mandatory for every distributed Internal Beta build.

## Protected historical evidence

This reorganization must not modify or delete:

- the authoritative 2026-07-30 archive and its `RELEASE_AUTHORITY.json`;
- r3/r4 publication candidates and their verification evidence;
- `LICENSE`, `LICENSES/`, `third_party/`, staged licence/source materials, manifests, notices, or compliance tooling;
- user outputs, test assets, local configuration, or existing historical reports.

## Required minimal implementation

1. Establish a single current project-status source and rewrite the release strategy around Internal Beta and optional GitHub Pre-release distribution.
2. Add explicit release-channel and project-classification constants to the existing version source; do not create a second version module.
3. Add installed-mode LocalAppData storage with a one-time legacy config migration while preserving development-mode paths.
4. Add a reproducible installer layer around the existing PyInstaller `onedir`; do not change the PyInstaller architecture.
5. Split the release checklist into an active Internal Beta Gate and a deferred Public Stable Gate.
6. Update public/current documents and cross-conversation state; retain historical evidence and business logic unchanged.
