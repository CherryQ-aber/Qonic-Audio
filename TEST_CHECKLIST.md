# Qonic Audio 5.0.0-beta.1 Release Gates

Status date: 2026-08-13

Current channel: **Internal Beta**

Status vocabulary: `PASS`, `WARNING`, `BLOCKER`, `NOT RUN`.

## Internal Beta Gate — active

| Check | Status | Evidence / acceptance rule |
| --- | --- | --- |
| Central version/channel metadata consistency | PASS | `app_info.py`, QML bridge, Windows version info, package and installer names agree on `5.0.0-beta.1` / Internal Beta. |
| Python syntax/import sanity | PASS | Explicit `py_compile` and targeted release tests passed. |
| Complete automated tests | PASS | `636 passed, 2 warnings, 76 subtests passed`. |
| QML source smoke | PASS | Default plus `autoConvert`, `audioEditor`, `metadata`, and `lyricsCover`; config SHA-256 unchanged. |
| PyInstaller onedir build | PASS | `build_release.ps1` completed on 2026-08-13; 3,098 files and bundled runtime/material checks passed. |
| Packaged QML smoke | PASS | Build script's packaged `audioEditor` smoke passed; five-smoke LGPL route verification also passed. |
| Portable archive integrity and SHA-256 | PASS | Raw build archive passed `7z t`; LGPL Internal Beta candidate also passed `7z t`, SHA-256 below. |
| Installer config contract | PASS | Automated contract test covers Program Files, Start Menu, optional desktop shortcut, uninstall, Internal Beta label, LocalAppData preservation, and Windows UI language detection. |
| Installer compilation | PASS | Inno Setup 6.7.3 produced the bilingual auto-detect candidate below; version resources and SHA-256 were verified. |
| Install / launch / upgrade data preservation / uninstall | NOT RUN | Must be tested with a built installer candidate. |
| Frozen/source config/cache/log/temp outside Program Files/project tree | PASS | Unified App Paths and isolated frozen-mode tests use per-user Config/Cache/Logs roots; test override prevents developer-profile pollution. |
| Legacy portable config migration | PASS | Automated tests migrate legacy config once, preserve unknown settings and the original file, and mark existing users as First Run completed. |
| Theme / First Run / window state lifecycle | PASS | Theme restart persistence, durable skip/accept, window serialization, centering, multi-screen restore and invalid-screen fallback are automated; installed desktop scenarios remain NOT RUN. |
| Clean Windows without Python/developer tools | NOT RUN | Candidate must run with bundled dependencies. |
| Real desktop/DPI/multi-display/tray | NOT RUN | Candidate-specific manual test. |
| Real media/core workflow/no-clobber | NOT RUN | Candidate-specific manual/automated evidence. |
| Third-party compliance manifest consistency | WARNING | Strict validation: 0 blockers, 6 warnings; manifest age, 2 component evidence warnings, and historical/full-PyInstaller Qt inventory warnings. Separate LGPL candidate removed all 687 verified GPL-only files and passed smoke. |
| Required licences/notices/source availability included | PASS | Candidate carries Qt/PySide6/Shiboken6 LGPL, Qt attribution/source availability, Microsoft material, project licence, and third-party notices. |
| P0/P1 defects | WARNING | No new P0/P1 is known from policy or installer-build work; installed-machine verification is pending. |

## Candidate verification record

Commands and results are filled only after actual execution. Historical v5.0/r4 results are not copied here as new passes.

```text
python -m py_compile app_info.py config.py logger.py ui_next\bridge\app_state_viewmodel.py
PASS

python -m pytest -q
636 passed, 2 warnings, 76 subtests passed

python main_qml.py --qml-smoke-test [five module variants]
PASS; config SHA-256 unchanged

python Tools\compliance\validate_compliance.py ... --strict
WARNING; blockers=0, warnings=6, exit=1

powershell -File .\build_release.ps1
PASS; packaged smoke PASS; 7z integrity PASS

python Tools\compliance\verify_qt_lgpl_route.py ...
PASS; 687 GPL-only Qt files removed in staging; packaged smokes PASS

Internal Beta LGPL portable candidate:
Release\Internal_Beta_Candidates\2026-08-13_5.0.0-beta.1\Qonic_Audio_v5.0.0-beta.1_Internal_Beta_LGPL.7z
SHA-256: 6408218ECBC710160A6008CB7999BBD70C8AF0C5A29BDC38119F4807241C8A15

powershell -NoProfile -ExecutionPolicy Bypass -File .\build_installer.ps1 -ApplicationSource ".\Release\Internal_Beta_Candidates\2026-08-13_5.0.0-beta.1\Qonic_Audio_v5.0.0-beta.1"
PASS; Inno Setup 6.7.3; installer version 5.0.0-beta.1; file version 5.0.0.1
Language contract PASS; uilanguage auto-detection, no language dialog, zh-CN + English fallback

Internal Beta installer candidate:
Release\Installer_Candidates\Qonic_Audio_v5.0.0-beta.1_Setup.exe
SHA-256: 544F9762D07B3BEB3FD8C271D4558E6CD084BD3655C4FC631F605BBB97EE225C
Signature: WARNING / NotSigned

Install / launch / upgrade data preservation / uninstall
NOT RUN
```

## GitHub Pre-release rule

- [x] Internal Beta binary releases are permitted.
- [x] GitHub release must be marked Pre-release.
- [x] Release notes must say this is an ongoing personal project and not an Official Stable Public Release.
- [x] `Latest Stable`, `Official Stable`, `Production Release`, and `Public Stable Release` labels are prohibited.

## Public Stable Gate — deferred

Status: **DEFERRED — PUBLIC RELEASE ONLY**

The following checks are retained for a future explicit owner decision and do not block Internal Beta:

- Brand freeze and target-market brand clearance.
- Trademark decision or registration if applicable.
- Stable-channel/version/support policy.
- Company/legal structure only if a future distribution model requires it.
- Commercial signing/trust program if chosen.
- Website, store submission, marketing, public support, and applicable privacy/legal documents.
- A new clean public candidate with revalidated compliance and SHA-256 evidence.

Current brand record:

```text
Brand: NOT FROZEN
Qonance: NOT ADOPTED
Formal trademark clearance: DEFERRED
```
