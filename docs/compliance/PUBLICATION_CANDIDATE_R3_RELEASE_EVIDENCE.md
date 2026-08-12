# Qonic Audio r3 Publication Candidate — Invalidated Evidence

> **Do not publish r3.** Final source-archive inspection found that its
> application-source tarball still contains the tracked Codex_memory directory.
> The candidate is retained as audit evidence only and has been superseded by
> the r4 rebuild procedure.

## Candidate identity

| Item | Value |
| --- | --- |
| Candidate tree | Release/Publication_Candidates/2026-08-12_r3/Qonic_Audio_v5.0_internal_test/ |
| Candidate archive | Qonic_Audio_v5.0_lgpl_publication_candidate.7z |
| Archive SHA-256 | DDADABB04B51ABAF4B8D0E45E43A713566AA8FB1E394D34C176F21DED316A425 |
| Archive size | 169,479,550 bytes |
| Source commit | 24b407956b8b6f945c9018c5b3b55b28a7c00c6b |
| Candidate static-tree SHA-256 | 03F840AD1942052E4DCA35387EE1C76188622E2D021289682D5F202981D371B7 |
| Candidate status | INVALID_SOURCE_ARCHIVE_EXPOSES_CODEX_MEMORY |

The 2026-07-30 frozen authority archive remains unchanged and is not this
candidate.

## Passing automatic checks

- python -m pytest -q: **620 passed, 2 warnings, 76 subtests passed**.
- Candidate verifier: passed required notices and license bodies, source archive
  hashes, GPL-only Qt absence, static-tree hash, dynamic Qt shared-library
  imports, forbidden-file scan, five packaged QML smoke tests, and 7z t.
- The packaged application directory does not contain a runtime log, local
  configuration, cache/output directories or the removed GPL-only Qt groups.
  This check did not inspect archive members deeply enough and therefore did
  not catch Codex_memory inside the application-source tarball.
- The candidate includes:
  - dynamic LGPLv3 Qt/PySide6/Shiboken6 6.11.1 notice, attribution and exact
    source availability;
  - Qonic FFmpeg Audio Runtime 8.1.1 and its complete corresponding-source
    archive, SHA-256 2B3A9A878B46050CACA71253C1E43F6239DE91C5C5C59DC72F8F2E0306A5C35A;
  - a source archive generated directly from the identified binary source
    commit.

The machine-readable records are
PUBLICATION_CANDIDATE_R3_PREARCHIVE_VERIFICATION.json and
PUBLICATION_CANDIDATE_R3_VERIFICATION.json.

## Existing frozen-baseline strict audit

validate_compliance.py --strict against the historical frozen baseline reported
**0 BLOCKER and 6 WARNING**, so it returned exit code 1. The warnings are the
stale frozen manifest, libffi/PyInstaller evidence warnings, the historical
FFmpeg B5 informational item, and retained/possibly-unused Qt modules in that
historical GPL baseline. They are not a pass/fail validation of the new r3
candidate and must not be represented as a clean strict result.

## Remaining release gates

Before changing the candidate status or publishing it, the project owner must
complete and record the five owner-controlled gates in
PUBLIC_RELEASE_READINESS.md: real desktop acceptance; real-media workflow
acceptance; clean-Windows acceptance; ownership of code/documentation/name/icon
assets; and final public version/name plus archive review decision.
