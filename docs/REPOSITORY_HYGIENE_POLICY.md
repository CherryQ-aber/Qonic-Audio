# Qonic Audio Repository Hygiene Policy

This document is the source of truth for what belongs in the public Qonic Audio repository. The local development workspace may contain more data than GitHub; the two are intentionally different.

## Core rule

The public repository contains source code, reproducible automated tests, build and installer scripts, CI, required compliance material, formal documentation, and the smallest documented fixtures needed to reproduce tests.

It is not a backup of the Owner workstation and must not contain private identity data, local runtime state, Agent context, review packages, user media, test output, or build workspaces.

## MUST TRACK

- Application Python source, QML, icons, and other required source assets.
- Dependency declarations, `app_info.py`, and `config.example.json`.
- Automated test code and CI workflows.
- Build scripts, PyInstaller specification, installer scripts, and version metadata.
- `LICENSE`, `LICENSES/`, required notices, manifests, hashes, source-availability records, and other formal compliance evidence.
- `README.md`, `CHANGELOG.md`, release notes, and maintained project documentation under `docs/`.

## TRACK WHEN REQUIRED FOR REPRODUCIBILITY

- Small synthetic or legally safe test fixtures.
- Deterministic schemas, fixture metadata, and CI helper scripts.
- Exact upstream archives or wheels only when a formal compliance record requires them and their location, purpose, and hash are documented.

Automated test code is engineering source. It must not be confused with test artifacts and must not be removed merely to make the repository smaller.

The scanner permits synthetic privacy-pattern fixtures only below `tests/fixtures/synthetic_privacy/`. That narrow exception suppresses fake credential and fake machine-path patterns needed to test the scanner. It never permits the Owner's real private email or real Windows user path.

## LOCAL ONLY — DO NOT TRACK OR DELETE

- `Codex_memory/`, `Codex执行记录/`, `Code_Review_Packages/`, `.reasonix/`, and `.codex/`.
- Codex prompts, Agent execution context, AI conversation exports, temporary plans, review bundles, raw manual-test reports, debug notes, and local TODO dumps.
- `config.json`, `.env`, logs, caches, temporary files, LocalAppData snapshots, user settings, and local application state.
- Real music, downloaded media, converted output, screenshots, manual acceptance images, recordings, benchmark output, and local test results.
- `build/`, `dist/`, `Release/`, installers, executables, symbols, archives, and other generated binaries. Internal Beta binaries belong in GitHub Releases, not the Git source tree.

Local files in these categories may be valuable and should normally remain on the workstation. Removing them from Git tracking does not authorize deleting their local copies.

## Approved narrow exceptions

- `Test_Files/README.md` and `Test_Files/converted/README.md` may document local test-media placement without including media.
- Exact compliance artifacts below `docs/compliance/staging/artifacts/` and `third_party/source-information/` may be tracked when formal evidence requires them.
- Synthetic privacy fixtures are limited to `tests/fixtures/synthetic_privacy/` and must contain only fake, non-operational values.

New exceptions require a documented reproducibility or compliance reason and a corresponding scanner test. Broad path or extension exceptions are prohibited.

## Privacy and credential rules

- Git Author and Committer identity for this repository must use the confirmed GitHub `users.noreply.github.com` address configured in repository-local Git settings.
- A Git noreply identity is not a public contact address. A public contact email may appear in `README.md` only after the Owner explicitly designates a separate project contact.
- Private email addresses, Owner workstation paths, API keys, tokens, passwords, private keys, `.env` files, and private URLs must not be committed.
- Third-party attribution already contained in an upstream licence or translation file is not Owner identity data and must remain intact when required by its licence or provenance record.

## Required pre-commit review

Never use `git add .` or `git add -A` as an unreviewed submission step. Stage task-owned files explicitly, then run:

```powershell
git status --short
git diff --cached --stat
git diff --cached
python scripts/check_repository_hygiene.py
```

Before committing, confirm that the staged set contains no local configuration, logs, user media, Codex/Agent records, review packages, build output, private identity data, machine-specific paths, or credentials.

The Core CI workflow runs the same hygiene scanner and the complete automated pytest suite on pushes and pull requests targeting `main`. A scanner failure blocks the change; tests or assertions must not be weakened to make an unsafe file pass.

## Agent rule

The existence of a file in the local workspace is not a reason to publish it. Codex and other Agents must follow: preserve locally, track intentionally, publish minimally, keep history reviewable, and protect personal information.
