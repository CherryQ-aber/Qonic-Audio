# Public Release Readiness — Qonic Audio

## Scope and authority

The frozen 2026-07-30 archive remains historical GPL-baseline evidence.  It is
not modified by this procedure.  A public release must be assembled as a new,
independently hashed publication candidate from an identified clean source
commit.

## Automatically verifiable conditions

The publication-candidate assembler and verifier must record all of the
following as passing:

- Qt/PySide6/Shiboken6 6.11.1 dynamic LGPLv3 runtime, with the verified
  GPL-only groups absent;
- recipient-facing LGPL, Qt attribution, third-party notices and exact source
  availability materials;
- Qonic FFmpeg Audio Runtime binary hashes and its complete corresponding
  source bundle;
- an application-source archive matching the binary's source commit;
- SHA-256 static-tree manifest, archive integrity test and forbidden-file scan;
- packaged QML smoke tests and dynamic Qt shared-library import evidence.

## Owner-controlled release gates

The following cannot be inferred or signed by the build process.  A publication
candidate is explicitly **not for public release** until the owner records all
of them as passed:

1. Real desktop acceptance: light/dark themes, practical DPI and multi-display
   layout, Windows Snap, tray behaviour and Widgets fallback.
2. Real-media acceptance: normal conversion, NCM decode chain, metadata,
   lyrics/cover, pitch/editor/player paths, no-clobber and retry behaviour.
3. Clean-Windows acceptance on a machine without Python, FFmpeg, ncmdump or
   development tools installed.
4. Confirmation that the project owner has authority to publish all Qonic
   source, documentation, name and icon/brand assets in the candidate.
5. Selection of the public version/name and a final release decision after
   reviewing the generated archive SHA-256.

When those records are complete, create a final archive only from the verified
candidate tree.  Do not retrofit the historical frozen archive.

## Owner status recorded 2026-08-12

| Gate | Status | Evidence / remaining action |
| --- | --- | --- |
| 1. Real desktop acceptance | OWNER_REPORTED_PASS | The project owner reports the native desktop acceptance passed. |
| 2. Real-media workflow acceptance | OWNER_REPORTED_PASS | The project owner reports the real-media workflow acceptance passed. |
| 3. Clean-Windows / other-machine acceptance | OWNER_REPORTED_PASS | The project owner reports the other-machine test passed without relying on the development environment. |
| 4a. Qonic-owned source and project documentation | PENDING_OWNER_CONFIRMATION | The rights basis may enter owner confirmation; no automated record signs this statement for the owner. |
| 4b. Qonic-owned icon assets | PENDING_OWNER_CONFIRMATION | The rights basis may enter owner confirmation; no automated record signs this statement for the owner. |
| 4c. Third-party dependencies | LICENSE_MANAGED | Third-party components remain governed by their own licences and existing closed compliance evidence. |
| 4d. Qonic brand/name | BLOCKER_TRADEMARK_CLEARANCE_REQUIRED | The owner does not currently assert complete public-release rights. Same-name software companies and software-category trademark records have been identified; target-market clearance is required. |
| 5a. Public version | SELECTED_1.0.0 | The owner selected 1.0.0 as the public version. |
| 5b. Final build and archive decision | PENDING | The current r4 binary still identifies itself as v5.0 Internal Test. Build and verify a new 1.0.0 candidate only after the brand blocker is resolved. |

Overall status: BLOCKED_BY_QONIC_TRADEMARK_CLEARANCE.

The r4 archive remains technical and compliance evidence only. Renaming that
archive or editing its metadata would not create a valid 1.0.0 release.
