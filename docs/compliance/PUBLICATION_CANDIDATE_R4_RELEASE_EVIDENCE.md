# Qonic Audio r4 Publication Candidate — Automatic Evidence

## Candidate identity

| Item | Value |
| --- | --- |
| Candidate tree | Release/Publication_Candidates/2026-08-12_r4/Qonic_Audio_v5.0_internal_test/ |
| Candidate archive | Qonic_Audio_v5.0_lgpl_publication_candidate.7z |
| Archive SHA-256 | CC51CB7B7553821DE644D92C6AD3430F30C404A3F976B19CB6E02028771C2FFE |
| Archive size | 169,347,541 bytes |
| Source commit | eb480c3e5bd235e5088bbbe1bfc0ccb8048d5f08 |
| Candidate static-tree SHA-256 | 9AE16E0975590EC1363C00F08E0BAF77EB48120F3D6E6F06795623B2A418C5B8 |
| Candidate status | NOT_FOR_PUBLIC_RELEASE_UNTIL_OWNER_GATES_CLOSED |

The 2026-07-30 frozen authority archive remains unchanged and is not this
candidate. r3 is retained only as an invalidated local audit artifact.

## Passing automatic checks

- python -m pytest -q: **620 passed, 2 warnings, 76 subtests passed**.
- Candidate verifier: passed required notices and license bodies, source archive
  hashes, deep source-archive inspection, GPL-only Qt absence, static-tree
  hash, dynamic Qt shared-library imports, forbidden-file scan, five packaged
  QML smoke tests, and 7z t.
- The application-source archive contains **0** forbidden Codex_memory
  members. The candidate tree and 7z listing contain no runtime log, local
  configuration, cache/output directories or removed GPL-only Qt groups.
- The candidate includes:
  - dynamic LGPLv3 Qt/PySide6/Shiboken6 6.11.1 notice, attribution and exact
    source availability;
  - Qonic FFmpeg Audio Runtime 8.1.1 and its complete corresponding-source
    archive, SHA-256 2B3A9A878B46050CACA71253C1E43F6239DE91C5C5C59DC72F8F2E0306A5C35A;
  - an application source archive generated directly from the identified
    binary source commit.

The machine-readable records are
PUBLICATION_CANDIDATE_R4_PREARCHIVE_VERIFICATION.json and
PUBLICATION_CANDIDATE_R4_VERIFICATION.json.

## Existing frozen-baseline strict audit

validate_compliance.py --strict against the historical frozen baseline reported
**0 BLOCKER and 6 WARNING**, so it returned exit code 1. The warnings are the
stale frozen manifest, libffi/PyInstaller evidence warnings, the historical
FFmpeg B5 informational item, and retained/possibly-unused Qt modules in that
historical GPL baseline. They are not a pass/fail validation of r4 and must not
be represented as a clean strict result.

## Remaining release gates

Before changing the candidate status or publishing it, the project owner must
complete and record the five owner-controlled gates in
PUBLIC_RELEASE_READINESS.md: real desktop acceptance; real-media workflow
acceptance; clean-Windows acceptance; ownership of code/documentation/name/icon
assets; and final public version/name plus archive review decision.
