# Qt LGPLv3 Route Technical Verification

Scope: the owner-frozen Qonic Audio v5.0 package, Qt/PySide6/shiboken6 6.11.1
only. The authoritative archive was not changed. Its SHA-256 remains
`BB0967E85AF2857C23587F3CEF37C37D14ED4E4106B7261F21E2F247B47F42F4`.

## GPL-only module result

Qt 6.11 licensing lists the following GPL-only module families. The frozen
package was scanned by path, then each included family was removed only from an
isolated onedir staging copy.

| Qt GPL-only family | Frozen-package result | Staging result |
| --- | --- | --- |
| Canvas Painter, CoAP, GRPC, HTTP Server, Lottie, MQTT, Network Authorization, Qml Compiler, Quick 3D Physics, Wayland Compositor | Not present | Not applicable |
| Qt Graphs | 39 files present | Removed; all packaged smokes passed |
| Qt Quick 3D | 556 files present | Removed; all packaged smokes passed |
| Qt Quick Timeline | 8 files present | Removed; all packaged smokes passed |
| Qt Virtual Keyboard | 84 files present | Removed; all packaged smokes passed |

No direct application source reference to any official GPL-only family was
found in `main_qml.py`, `gui.py`, `converter.py`, `watcher.py`, or `ui_next/`.
There are therefore **0 GPL_ONLY_REQUIRED** groups and four
**GPL_ONLY_INCLUDED_UNUSED** groups proven removable in staging.

## Minimalisation evidence

The staging candidate at `Temp/qt-lgpl-route-20260809-r3` is not a release
artifact. It was copied from the frozen onedir and then had only the coherent
GPL-only module groups above removed. Each baseline, each group removal, the
combined candidate, and the replacement check ran these packaged commands with
`QT_QPA_PLATFORM=offscreen`:

```text
Qonic_Audio_v5.0_internal_test.exe --qml-smoke-test
Qonic_Audio_v5.0_internal_test.exe --qml-smoke-test --qml-open-module=autoConvert
Qonic_Audio_v5.0_internal_test.exe --qml-smoke-test --qml-open-module=audioEditor
Qonic_Audio_v5.0_internal_test.exe --qml-smoke-test --qml-open-module=metadata
Qonic_Audio_v5.0_internal_test.exe --qml-smoke-test --qml-open-module=lyricsCover
```

All 25 group/combined smoke commands exited `0`; the five baseline commands
also exited `0`. The resulting classification of the 257 reviewed Qt module
entries is: REQUIRED 19, TRANSITIVE_REQUIRED 0, SAFE_TO_REMOVE 51, UNRESOLVED
187. The 51 removable module entries comprise 687 actual staging files, so the
candidate retains 2,161 of the original 2,848 Qt/PySide/Shiboken runtime files.

The JSON evidence, including every command, stdout/stderr tail, removed path,
classification and SHA-256, is
[QT_LGPL_ROUTE_VERIFICATION.json](QT_LGPL_ROUTE_VERIFICATION.json).

The smoke matrix covers all requested QML workspaces and QML imports. Native
file dialogs, system tray interaction, live multimedia playback, image decoder
coverage and Widgets fallback still require the existing Windows acceptance
test on the future integration candidate; they are not falsely represented as
covered by an offscreen QML smoke.

## Dynamic linking and replacement condition

PE import-table inspection showed that `QtCore.pyd`, `QtGui.pyd`,
`QtMultimedia.pyd`, `QtQml.pyd`, `QtQuick.pyd`, and `QtWidgets.pyd` import the
matching `Qt6*.dll` shared libraries. Qt is not statically linked into the
Qonic executable by this distribution path.

For the staging-only replacement check, `Qt6Core.dll` was renamed, copied back
as an external replacement, and the five packaged smokes all exited `0`. The
original file was restored. This demonstrates normal DLL lookup and no observed
Qonic-side DLL hash/signature gate. It does not substitute for testing an
independently built ABI-compatible modified Qt DLL.

## Result

The LGPLv3 route is technically feasible for a future compliance integration
candidate because no GPL-only module is required by the tested application
paths. It is not a legal closure or a modification of the authoritative
release. Owner confirmation remains pending.
