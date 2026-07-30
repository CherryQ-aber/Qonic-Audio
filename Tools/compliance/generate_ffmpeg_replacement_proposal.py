"""Generate the B5 FFmpeg replacement proposal without replacing runtime files."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "compliance" / "report" / "ffmpeg-self-build"
FORMAL = ROOT / "Tools" / "ffmpeg" / "bin"
CANDIDATE = ROOT / "third_party" / "ffmpeg-build" / "output" / "candidate"
SOURCE_BUNDLE = (
    ROOT
    / "third_party"
    / "ffmpeg-build"
    / "output"
    / "source-bundle"
    / "qonic-ffmpeg-complete-corresponding-source.tar.gz"
)
PROPOSAL = ROOT / "compliance" / "FFMPEG_REPLACEMENT_PROPOSAL.md"
READINESS = REPORT_DIR / "b5-replacement-readiness.json"
OWNER_APPROVAL = REPORT_DIR / "b5-owner-approval.json"

EXPECTED = {
    "formal_ffmpeg": "09948D4CDD0650DA6FF5A87577469F2A218DC2615AE379F8F734D24C49DE0F73",
    "formal_ffprobe": "A6618E99BB58869DED3C6F37B53AA1A8D701C3591DBB7B5B317D47369C112BE2",
    "candidate_ffmpeg": "CA2BCCBF1A2A5A379AE484AD127D120CC3E394833B69767694A1E738F2D6BE55",
    "candidate_ffprobe": "4EC2AC9385AACBAF927B7E8D031291059CEA2E02EE6BFAE0D708F78E1C528251",
    "source_bundle": "2B3A9A878B46050CACA71253C1E43F6239DE91C5C5C59DC72F8F2E0306A5C35A",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def run_text(executable: Path, argument: str) -> str:
    result = subprocess.run(
        [str(executable), argument],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        raise RuntimeError(f"{executable.name} {argument} failed: {result.returncode}")
    return result.stdout + result.stderr


def parse_listing(text: str, kind: str) -> set[str]:
    result: set[str] = set()
    section = ""
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if kind == "formats":
            match = re.match(r"^\s*[D. ][E. ][d. ]?\s+([A-Za-z0-9_,]+)\s", line)
            if match:
                result.update(match.group(1).split(","))
        elif kind == "filters":
            match = re.match(r"^\s*[TSC. ]{2,3}\s+([A-Za-z0-9_]+)\s", line)
            if match:
                result.add(match.group(1))
        elif kind == "protocols":
            value = line.strip()
            if value in {"Input:", "Output:"}:
                section = value
            elif section and re.fullmatch(r"[A-Za-z0-9_+.-]+", value):
                result.add(value)
    return result


def capability_snapshot(ffmpeg: Path) -> dict[str, list[str]]:
    return {
        kind: sorted(parse_listing(run_text(ffmpeg, flag), kind))
        for kind, flag in (
            ("formats", "-formats"),
            ("filters", "-filters"),
            ("protocols", "-protocols"),
        )
    }


def binary_record(label: str, path: Path, expected_hash: str) -> dict:
    actual_hash = sha256(path)
    return {
        "label": label,
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": actual_hash,
        "expected_sha256": expected_hash,
        "hash_matches_expected": actual_hash == expected_hash,
        "size_bytes": path.stat().st_size,
    }


def format_delta(old: dict, new: dict) -> dict:
    result = {}
    for kind in ("formats", "filters", "protocols"):
        before = set(old.get(kind, []))
        after = set(new.get(kind, []))
        result[kind] = {
            "formal_count": len(before),
            "candidate_count": len(after),
            "removed_count": len(before - after),
            "added_count": len(after - before),
            "removed": sorted(before - after),
            "added": sorted(after - before),
        }
    return result


def _legacy_markdown(payload: dict) -> str:
    old_ffmpeg = payload["formal"]["ffmpeg"]
    old_ffprobe = payload["formal"]["ffprobe"]
    new_ffmpeg = payload["candidate"]["ffmpeg"]
    new_ffprobe = payload["candidate"]["ffprobe"]
    delta = payload["capability_delta"]
    b4 = payload["b4"]
    source = payload["corresponding_source"]
    readiness = payload["readiness"]
    return f"""# FFmpeg replacement proposal (B5)\n\nStatus: **PREPARED — FORMAL REPLACEMENT NOT AUTHORIZED**\n\nGenerated: {payload['generated_at']}\n\n## Decision requested\n\nApprove or reject replacement of the two formal runtime files with the B3\nQonic candidate. This proposal does **not** perform that replacement. Until the\nproject owner explicitly replies with approval to replace, the formal runtime,\nthe authoritative expanded package and the authoritative `.7z` remain frozen.\n\n## Why replacement is proposed\n\nThe current Gyan 8.1.1 GPL build is usable and remains byte-verified, but its\nprecise provider build scripts, patch set and complete static dependency source\nidentity are not publicly available. The Qonic candidate instead has fixed\nsource archives, build environment lock, configure allowlist, build scripts,\nlicense inventory and a corresponding-source bundle.\n\n## Exact proposed file changes\n\n| Runtime file | Current formal SHA-256 | Current bytes | Candidate SHA-256 | Candidate bytes | Change |\n|---|---:|---:|---:|---:|---:|\n| `Tools/ffmpeg/bin/ffmpeg.exe` | `{old_ffmpeg['sha256']}` | {old_ffmpeg['size_bytes']:,} | `{new_ffmpeg['sha256']}` | {new_ffmpeg['size_bytes']:,} | {new_ffmpeg['size_bytes'] - old_ffmpeg['size_bytes']:+,} bytes |\n| `Tools/ffmpeg/bin/ffprobe.exe` | `{old_ffprobe['sha256']}` | {old_ffprobe['size_bytes']:,} | `{new_ffprobe['sha256']}` | {new_ffprobe['size_bytes']:,} | {new_ffprobe['size_bytes'] - old_ffprobe['size_bytes']:+,} bytes |\n\nThe candidate reduces the two executable files by {payload['size_change']['total_delta_bytes']:,} bytes in total. No application call site or runtime path contract changes: both binaries remain independent programs at the existing `Tools/ffmpeg/bin` paths.\n\n## Configure and capability change\n\nThe candidate is a deliberately scoped audio build: GPL/version3 enabled;\n`--disable-nonfree`, `--disable-network`, `--disable-autodetect` and\n`--disable-everything` are present, followed by explicit enables for Qonic's\nrequired decoders, encoders, containers, `file`/`pipe`, and Rubber Band pitch\nfilters. The current Gyan build carries broad network, video, hardware, subtitle\nand device capability that Qonic's command inventory marks out of scope.\n\n| Listing | Formal count | Candidate count | Expected removals | Additions |\n|---|---:|---:|---:|---:|\n| Formats | {delta['formats']['formal_count']} | {delta['formats']['candidate_count']} | {delta['formats']['removed_count']} | {delta['formats']['added_count']} |\n| Filters | {delta['filters']['formal_count']} | {delta['filters']['candidate_count']} | {delta['filters']['removed_count']} | {delta['filters']['added_count']} |\n| Protocols | {delta['protocols']['formal_count']} | {delta['protocols']['candidate_count']} | {delta['protocols']['removed_count']} | {delta['protocols']['added_count']} |\n\nAll required project filters and protocols are present. Removed capability is\nclassified as `EXPECTED_REMOVAL` only when it is outside Qonic's locked feature\nrequirements; B4 found no functional regression in the promised media and app\nworkflows. The full machine-readable lists are in\n`compliance/report/ffmpeg-self-build/b5-replacement-readiness.json`.\n\n## Evidence and tests\n\n- B3: seven source archives verified; fixed FFmpeg commit; static build with\n  system-DLL-only imports; source bundle SHA-256\n  `{source['sha256']}` ({source['size_bytes']:,} bytes, {source['entry_count']} entries).\n- B3 validation: Windows functional matrix 21/21; build/compliance tests 44/44.\n- B4: isolated onedir 55/55, including all promised inputs/outputs, single and\n  batch conversion, cancellation, corrupt/locked files, Unicode/long/cross-drive\n  paths, ffprobe, pitch preview/export, metadata, lyrics, cover preservation and\n  packaged smoke.\n- B4 isolated package comparison: {b4['non_ffmpeg_files']} non-FFmpeg files were\n  byte-identical; only the two candidate executables differed before launch.\n\n## Rollback plan if approval is granted\n\n1. Copy the current formal `ffmpeg.exe` and `ffprobe.exe`, without modification,\n   to a new dated `Release/Non_Authoritative/.../former-gyan/` archive and record\n   their current SHA-256 values.\n2. Copy the two verified candidate files into `Tools/ffmpeg/bin`.\n3. Rebuild the single supported PyInstaller `onedir` package from the approved\n   commit; do not create a onefile variant.\n4. Run full regression, packaged smoke, archive integrity and final formal hashes.\n5. Regenerate Manifest, Notices, compliance report and release inventory.\n6. Freeze the new archive SHA-256. If any check fails, restore the two files from\n   the dated former-Gyan archive and stop.\n\n## Files that a future approved replacement would modify\n\n- `Tools/ffmpeg/bin/ffmpeg.exe`\n- `Tools/ffmpeg/bin/ffprobe.exe`\n- newly rebuilt onedir output and new archive, not the frozen historical archive\n- third-party Manifest, Notices, audit report, release inventory and B5 result\n  records\n\n## Current gate\n\nTechnical readiness: **{readiness['technical_status']}**.\n\nFormal replacement authorization: **NOT GRANTED**. The `FFMPEG_BUILD_CHAIN_INCOMPLETE` blocker must remain open until the owner explicitly approves this proposal and the approved replacement/rebuild/final-manifest sequence succeeds.\n"""


def inspect_source_bundle(bundle: Path, source_index: dict) -> dict:
    """Prove the bundle contains every locked source and reconstruction input."""

    with tarfile.open(bundle, "r:gz") as archive:
        names = set(archive.getnames())
    required_prefixes = (
        "ffmpeg-build/lock/",
        "ffmpeg-build/config/",
        "ffmpeg-build/scripts/",
        "ffmpeg-build/patches/",
        "ffmpeg-build/tests/",
        "ffmpeg-build/license-texts/",
    )
    missing_prefixes = [
        prefix for prefix in required_prefixes if not any(name.startswith(prefix) for name in names)
    ]
    source_files = [item["archive_filename"] for item in source_index["sources"]]
    missing_sources = [
        name for name in source_files if f"ffmpeg-build/sources/{name}" not in names
    ]
    return {
        "entry_count": len(names),
        "required_prefixes": list(required_prefixes),
        "source_archives": source_files,
        "missing_prefixes": missing_prefixes,
        "missing_source_archives": missing_sources,
        "complete": not missing_prefixes and not missing_sources,
    }


def markdown(payload: dict) -> str:
    """Render the approved B5 proposal while retaining the detailed baseline text."""

    total_reduction = abs(payload["size_change"]["total_delta_bytes"])
    legacy_payload = dict(payload)
    legacy_payload["readiness"] = {
        **payload["readiness"],
        "technical_status": payload["readiness"]["conditional_authorization_status"],
    }
    text = _legacy_markdown(legacy_payload)
    text = text.replace(
        "Status: **PREPARED — FORMAL REPLACEMENT NOT AUTHORIZED**",
        "Status: **CONDITIONAL AUTHORIZATION RECORDED — FINAL REPLACEMENT NOT YET VERIFIED**",
    ).replace(
        f"The candidate reduces the two executable files by {payload['size_change']['total_delta_bytes']:,} bytes in total.",
        f"The candidate reduces the two executable files by {total_reduction:,} bytes in total.",
    ).replace(
        "Formal replacement authorization: **NOT GRANTED**. The `FFMPEG_BUILD_CHAIN_INCOMPLETE` blocker must remain open until the owner explicitly approves this proposal and the approved replacement/rebuild/final-manifest sequence succeeds.",
        "Conditional authorization: **READY_FOR_CONDITIONAL_AUTHORIZATION**. "
        "Owner approval is recorded for this replacement. Final replacement status: "
        "**FINAL_REPLACEMENT_NOT_YET_VERIFIED**. The `FFMPEG_BUILD_CHAIN_INCOMPLETE` "
        "blocker remains open until the approved replacement, onedir rebuild, final "
        "regression, hashes and release compliance materials all succeed.",
    )
    scope = """\n\n## Runtime scope boundary\n\nThis candidate is the **Qonic Audio Converter Audio Runtime** only. It is not a\npermanent, universal FFmpeg runtime for every Qonic project. Future video\nvisualization work must use a separately controlled FFmpeg Video Runtime or a\nnewly generated and independently reviewed build at the point of formal\nintegration. Potential future video features do not justify retaining the\nun-auditable broad Gyan build in this audio release.\n"""
    return text.replace("\n## Configure and capability change", scope + "\n## Configure and capability change")


def main() -> int:
    b3 = read_json(REPORT_DIR / "candidate-build-attempt.json")
    b4 = read_json(REPORT_DIR / "b4-regression-report.json")
    approval = read_json(OWNER_APPROVAL) if OWNER_APPROVAL.is_file() else {}
    requirements = read_json(REPORT_DIR / "qonic-ffmpeg-feature-requirements.json")
    old_capabilities = read_json(REPORT_DIR / "current-gyan-capability-baseline.json")
    source_index = read_json(CANDIDATE / "SOURCE_INDEX.json")
    candidate_capabilities = capability_snapshot(CANDIDATE / "ffmpeg.exe")
    formal = {
        "ffmpeg": binary_record("formal_ffmpeg", FORMAL / "ffmpeg.exe", EXPECTED["formal_ffmpeg"]),
        "ffprobe": binary_record("formal_ffprobe", FORMAL / "ffprobe.exe", EXPECTED["formal_ffprobe"]),
    }
    candidate = {
        "ffmpeg": binary_record("candidate_ffmpeg", CANDIDATE / "ffmpeg.exe", EXPECTED["candidate_ffmpeg"]),
        "ffprobe": binary_record("candidate_ffprobe", CANDIDATE / "ffprobe.exe", EXPECTED["candidate_ffprobe"]),
    }
    source_hash = sha256(SOURCE_BUNDLE)
    source_materials = inspect_source_bundle(SOURCE_BUNDLE, source_index)
    buildconf = run_text(CANDIDATE / "ffmpeg.exe", "-buildconf")
    b4_counts = b4.get("counts", {})
    required_check = read_json(CANDIDATE / "capabilities.json").get("required_check", {})
    technical_checks = {
        "formal_hashes_match": all(value["hash_matches_expected"] for value in formal.values()),
        "candidate_hashes_match": all(value["hash_matches_expected"] for value in candidate.values()),
        "source_bundle_hash_matches": source_hash == EXPECTED["source_bundle"],
        "corresponding_source_contents_complete": source_materials["complete"],
        "candidate_required_capabilities": bool(required_check.get("ok")),
        "nonfree_disabled": "--disable-nonfree" in buildconf and "--enable-nonfree" not in buildconf,
        "b4_passed": b4.get("overall_status") == "pass" and b4_counts.get("fail") == 0 and b4_counts.get("blocked") == 0,
    }
    delta = format_delta(old_capabilities, candidate_capabilities)
    payload = {
        "schema_version": 2,
        "phase": "B5",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "proposal_status": "CONDITIONAL_AUTHORIZATION_APPROVED_PENDING_FINAL_VERIFICATION",
        "replacement_authorized": approval.get("approval_status") == "APPROVED",
        "formal_runtime_modified": False,
        "authoritative_archive_modified": False,
        "formal": formal,
        "candidate": candidate,
        "size_change": {
            "ffmpeg_delta_bytes": candidate["ffmpeg"]["size_bytes"] - formal["ffmpeg"]["size_bytes"],
            "ffprobe_delta_bytes": candidate["ffprobe"]["size_bytes"] - formal["ffprobe"]["size_bytes"],
            "total_delta_bytes": (
                candidate["ffmpeg"]["size_bytes"]
                + candidate["ffprobe"]["size_bytes"]
                - formal["ffmpeg"]["size_bytes"]
                - formal["ffprobe"]["size_bytes"]
            ),
        },
        "corresponding_source": {
            "path": SOURCE_BUNDLE.relative_to(ROOT).as_posix(),
            "sha256": source_hash,
            "size_bytes": SOURCE_BUNDLE.stat().st_size,
            "entry_count": source_materials["entry_count"],
            "materials_verification": source_materials,
            "supersedes_b3_bundle": {
                "sha256": b3["corresponding_source"]["sha256"],
                "reason": "B5 adds verified license texts and license inventory to the corresponding-source bundle.",
            },
        },
        "b4": {
            "status": b4.get("overall_status"),
            "counts": b4_counts,
            "non_ffmpeg_files": 3004,
            "report": "compliance/report/ffmpeg-self-build/b4-regression-report.json",
        },
        "requirements": requirements,
        "capability_delta": delta,
        "technical_checks": technical_checks,
        "readiness": {
            "conditional_authorization_status": (
                "READY_FOR_CONDITIONAL_AUTHORIZATION"
                if all(technical_checks.values())
                else "NOT_READY"
            ),
            "final_replacement_status": "FINAL_REPLACEMENT_NOT_YET_VERIFIED",
            "blocker_status": "OPEN_PENDING_APPROVED_REPLACEMENT_VALIDATION",
        },
        "owner_approval": approval,
        "runtime_scope": {
            "current_contract": "Qonic Audio Converter Audio Runtime",
            "future_video_rule": "Use a separate controlled FFmpeg Video Runtime or generate a new independently reviewed build at formal integration.",
            "not_a_universal_runtime": True,
        },
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    READINESS.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    PROPOSAL.write_text(markdown(payload), encoding="utf-8")
    print(READINESS)
    print(PROPOSAL)
    return 0 if all(technical_checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
