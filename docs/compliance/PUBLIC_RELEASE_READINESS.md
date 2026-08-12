# Public Release Readiness — Qonic Audio v5.0

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
