# Qt LGPL Integration Candidate — Windows Native Acceptance

Status: **PASS — OWNER-CONFIRMED WINDOWS NATIVE ACCEPTANCE**

## Candidate identity

| Field | Value |
| --- | --- |
| Candidate | `Release/Integration_Candidates/2026-08-09_lgpl-qt-r2/Qonic_Audio_v5.0_internal_test` |
| Candidate type | Non-authoritative LGPL-3.0 Qt integration candidate |
| Parent frozen archive SHA-256 | `BB0967E85AF2857C23587F3CEF37C37D14ED4E4106B7261F21E2F247B47F42F4` |
| Candidate static-content SHA-256 | `E9F2C2CEC4328C97280B4F6CCDAFB4262308BA60B3857434A096E35B81BDF8B9` |
| Static file count | 2,328 |
| Removed GPL-only files | 687: Qt Graphs 39, Qt Quick 3D 556, Qt Quick Timeline 8, Qt Virtual Keyboard 84 |

The candidate identity excludes only `COMPLIANCE_INTEGRATION_CANDIDATE.json`
and `logs/runtime.log`. The latter is an empty runtime log created at first
launch and is not distributed static content.

## Automatic native Windows evidence

The following commands ran with `QT_QPA_PLATFORM=windows` and each exited `0`:

```text
Qonic_Audio_v5.0_internal_test.exe --qml-smoke-test
Qonic_Audio_v5.0_internal_test.exe --qml-smoke-test --qml-open-module=autoConvert
Qonic_Audio_v5.0_internal_test.exe --qml-smoke-test --qml-open-module=audioEditor
Qonic_Audio_v5.0_internal_test.exe --qml-smoke-test --qml-open-module=metadata
Qonic_Audio_v5.0_internal_test.exe --qml-smoke-test --qml-open-module=lyricsCover
```

The candidate also contains `qwindows.dll`, `qjpeg.dll`, the Qt Multimedia
`ffmpegmediaplugin.dll` and `windowsmediaplugin.dll`, all Qt LGPLv3/attribution
materials, and the exact source-availability record. No file from any of the
four removed GPL-only groups remains. The machine-readable command output and
checks are in [QT_WINDOWS_NATIVE_ACCEPTANCE.json](QT_WINDOWS_NATIVE_ACCEPTANCE.json).

## Owner-confirmed human interaction acceptance

On 2026-08-12 (Asia/Shanghai), the project owner confirmed in the Qonic Audio
project task: `r2 Windows 原生验收五项均通过`.

The following visible desktop checks are therefore recorded as passed for r2:

1. Open a known-good audio file through the native Windows file picker.
2. Confirm Qt Multimedia playback is audible; test pause, seek and stop.
3. Open a file containing embedded artwork and confirm the cover renders.
4. Confirm system-tray visibility and hide/restore or close-to-tray behavior.
5. Confirm the available Widgets/native fallback path behaves normally.

Together with the automatic evidence above, this closes the Qt LGPL route for
the identified r2 integration candidate. It does not alter or reclassify the
frozen authoritative GPL baseline archive.
