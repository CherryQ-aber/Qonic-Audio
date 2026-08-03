# Microsoft VC Runtime licence confirmation

## Status

**CLOSED — OWNER CONFIRMATION RECORDED**

This record is a technical audit of the current host and the sole authoritative
Qonic Audio v5.0 Internal Test package. On 2026-08-03 the project owner stated
that the required Microsoft VC Runtime licence confirmation is complete for
this unchanged authoritative release. This technical record does not reproduce
or sign the owner's personal legal statement.

## Audited release

| Field | Value |
| --- | --- |
| Authority | `Release/External_Test/2026-07-30_audio-validation-fix/RELEASE_AUTHORITY.json` |
| Application archive | `Qonic_Audio_v5.0_internal_test.7z` |
| Archive SHA-256 | `BB0967E85AF2857C23587F3CEF37C37D14ED4E4106B7261F21E2F247B47F42F4` |
| Release structure | PyInstaller `onedir` |
| Audit date | 2026-08-02 |

## Local Visual Studio and Build Tools detection

Microsoft Visual Studio Community 2026 is installed on this host. `vswhere.exe`
and the Setup Instances registry hives were not available, but the uninstall
registry and the instance state file independently identify the same Community
2026 instance. The MSVC toolset directory is present, so its version is
recorded rather than treated as optional absence.

| Item | Result |
| --- | --- |
| Product name | Microsoft Visual Studio Community 2026 |
| Edition | Community |
| Product version | 18.8.2 |
| Installation version | 18.8.12023.21 |
| Installation path | `C:\Program Files\Microsoft Visual Studio\18\Community` |
| Installation ID | `8754e93d` |
| MSVC toolset version | 14.51.36231 |
| MSVC toolset path | `C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231` |
| Installed VC++ 2015-2022 runtime packages | x64 14.44.35211.0; x86 14.44.35211.0 |

The local Community 2026 installation establishes the applicable product,
licence-terms and REDIST-list evidence for this host. The separate owner
confirmation is now recorded as CLOSED. The complete machine evidence is in
[`MICROSOFT_VC_RUNTIME_TOOLCHAIN_INVENTORY.json`](MICROSOFT_VC_RUNTIME_TOOLCHAIN_INVENTORY.json).

## Authoritative package inventory and classification

The package contains 11 files matching `vcruntime*.dll`, `msvcp*.dll`,
`concrt*.dll`, or `vc_redist*.exe`:

| Classification | Count | Result |
| --- | ---: | --- |
| `permitted_redistributable` | 11 | `MSVCP140*` and `VCRUNTIME140*` files with Microsoft product metadata; all have a valid Authenticode status. They are consistent with the VC++ runtime material in the VS 2026 REDIST scope and remain unmodified. The owner confirmation is recorded as CLOSED. |
| `debug_nonredist` | 0 | No `debug_nonredist`, DebugCRT, DebugCXXAMP, DebugMFC, DebugOpenMP or onecore debug indicator found. |
| `unknown_or_needs_review` | 0 | No matching runtime file outside the reviewed set. |
| `vc_redist*.exe` | 0 | No redistributable installer is embedded. |
| Compiler, Build Tools, or other development tools | 0 | No compiler/linker, `VC\\Tools\\MSVC`, profiler, remote-tools, IntelliTrace, GraphicsDbgRedist or similar development-tool indicator found. |

The exact relative paths, versions, SHA-256 values, signature results and
negative-scan patterns are saved in
[`MICROSOFT_VC_RUNTIME_PACKAGE_INVENTORY.json`](MICROSOFT_VC_RUNTIME_PACKAGE_INVENTORY.json).
No file in the application archive or its authoritative expanded directory was
modified during this audit.

## Microsoft rule applied

Microsoft's VS 2026 redistribution page identifies its Visual Studio 2026
REDIST list as applying to Visual Studio Community, among other editions. It
states that a validly licensed copy is a condition for copying and distributing
the listed files and identifies files under `VC\\Redist` as distributable
subject to the licence terms. It expressly excludes
`VC\\Redist\\MSVC\\[version]\\debug_nonredist` and
`onecore\\debug_nonredist` from distribution. Microsoft also states that
individual VC runtime binaries and redistributable packages obtained from its
distribution channels are limited to licensed Visual Studio users and subject
to their licence terms.

Official sources consulted on 2026-08-02:

- [Visual Studio License Directory](https://visualstudio.microsoft.com/license-terms/)
- [Microsoft Visual Studio Community 2026 License Terms](https://visualstudio.microsoft.com/license-terms/vs2026-ga-community/)
- [Visual Studio 2026 Redistribution / REDIST list](https://learn.microsoft.com/en-us/visualstudio/releases/2026/redistribution)
- [Redistribute Visual C++ Files](https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files?view=msvc-170)

## Closure record

The project owner reported the required Microsoft Visual Studio Community 2026
licence/redistribution confirmation completed on 2026-08-03 for the unchanged
authoritative package. The personal legal statement is deliberately not copied
or signed by this technical audit. If the authority archive or the 11-file
Runtime inventory changes, reopen this item before distribution.

Until that statement is recorded, the technical classification above does not
close the owner-licence condition.

## Microsoft-specific remainder after owner confirmation

For the currently frozen archive, no debug runtime, compiler, Build Tools,
development utility, or unclassified matching VC runtime file remains. After
the owner confirmation, the remaining Microsoft operational obligation is to
repeat this inventory and compatibility check whenever the runtime DLL set,
PySide6/NumPy wheels, or release build changes. This does not resolve separate,
non-Microsoft licence reviews for NumPy, Pillow, charset-normalizer, Qt, or
other dependencies.
