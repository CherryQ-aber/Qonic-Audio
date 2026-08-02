# Microsoft VC Runtime licence confirmation

## Status

**PENDING OWNER CONFIRMATION**

This record is a technical audit of the current host and the sole authoritative
Qonic Audio v5.0 Internal Test package. It does not state or infer that the
project owner holds any Microsoft licence, Visual Studio subscription, or other
redistribution entitlement.

## Audited release

| Field | Value |
| --- | --- |
| Authority | `Release/External_Test/2026-07-30_audio-validation-fix/RELEASE_AUTHORITY.json` |
| Application archive | `Qonic_Audio_v5.0_internal_test.7z` |
| Archive SHA-256 | `BB0967E85AF2857C23587F3CEF37C37D14ED4E4106B7261F21E2F247B47F42F4` |
| Release structure | PyInstaller `onedir` |
| Audit date | 2026-08-02 |

## Local Visual Studio and Build Tools detection

No Visual Studio 2022 product or Visual Studio Build Tools installation was
detected on this host. `vswhere.exe` was absent, neither native nor WOW6432Node
Visual Studio Setup Instances registry hive had an instance, the standard VS
2022 edition paths were absent, and `cl.exe`, `link.exe`, and `msbuild.exe`
were not on `PATH`.

| Item | Result |
| --- | --- |
| Product name | Not detected |
| Product version | Not detected |
| Edition | Not detected |
| MSVC toolset version | Not detected |
| Installed VC++ 2015-2022 runtime packages | x64 14.44.35211.0; x86 14.44.35211.0 |

The installed runtime packages are operating-system inventory only. They are
not evidence of the project owner's Visual Studio licence or redistribution
right. The complete machine evidence is in
[`MICROSOFT_VC_RUNTIME_TOOLCHAIN_INVENTORY.json`](MICROSOFT_VC_RUNTIME_TOOLCHAIN_INVENTORY.json).

## Authoritative package inventory and classification

The package contains 11 files matching `vcruntime*.dll`, `msvcp*.dll`,
`concrt*.dll`, or `vc_redist*.exe`:

| Classification | Count | Result |
| --- | ---: | --- |
| `permitted_redistributable_pending_owner_license` | 11 | `MSVCP140*` and `VCRUNTIME140*` files with Microsoft product metadata; all have a valid Authenticode status. They are consistent with the VC++ runtime material in the VS 2022 REDIST scope, provided the owner has the applicable redistribution right and distributes them unmodified. |
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

Microsoft's VS 2022 redistribution page states that a validly licensed copy of
the relevant Visual Studio software is a condition for copying and distributing
the listed files, and identifies the files under `VC\\Redist` as distributable
subject to the licence terms. It expressly excludes
`VC\\Redist\\MSVC\\[version]\\debug_nonredist` and
`onecore\\debug_nonredist` from distribution. Microsoft also states that
individual VC runtime binaries and redistributable packages obtained from its
distribution channels are limited to licensed Visual Studio users and subject
to their licence terms.

Official sources consulted on 2026-08-02:

- [Visual Studio License Directory](https://visualstudio.microsoft.com/license-terms/)
- [Visual Studio 2022 Redistribution / REDIST list](https://learn.microsoft.com/en-us/visualstudio/releases/2022/redistribution)
- [Redistribute Visual C++ Files](https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files?view=msvc-170)
- [Determine which DLLs to redistribute](https://learn.microsoft.com/en-us/cpp/windows/determining-which-dlls-to-redistribute?view=msvc-170)

## Required owner statement

To close this item, the project owner must record this exact confirmation (or a
legally equivalent statement approved by their counsel):

> I confirm that I am a validly licensed Visual Studio user, or otherwise hold
> the applicable Microsoft redistribution rights, and approve distribution of
> the unmodified VC Runtime files enumerated in
> `docs/compliance/MICROSOFT_VC_RUNTIME_PACKAGE_INVENTORY.json` with the Qonic
> Audio v5.0 Internal Test authoritative release.

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
