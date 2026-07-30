"""Verify the approved B5 runtime replacement and rebuilt onedir release."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SET_ROOT = ROOT / "Release" / "External_Test" / "2026-07-28_b5_final"
PACKAGE = SET_ROOT / "Qonic_Audio_v5.0_internal_test"
ARCHIVE = SET_ROOT / "Qonic_Audio_v5.0_internal_test.7z"
SOURCE = SET_ROOT / "Corresponding_Source" / "qonic-ffmpeg-complete-corresponding-source.tar.gz"
FORMAL = ROOT / "Tools" / "ffmpeg" / "bin"
CANDIDATE = ROOT / "third_party" / "ffmpeg-build" / "output" / "candidate"
READINESS = ROOT / "compliance" / "report" / "ffmpeg-self-build" / "b5-replacement-readiness.json"
REPLACEMENT = ROOT / "compliance" / "report" / "ffmpeg-self-build" / "b5-formal-replacement.json"
REPORT = ROOT / "compliance" / "report" / "ffmpeg-self-build" / "b5-final-release-verification.json"
SEVEN_ZIP = Path(r"C:\Program Files\7-Zip\7z.exe")
SMOKE_PACKAGE = ROOT / "Release" / "Qonic_Audio_v5.0_internal_test"

CANDIDATE_HASHES = {
    "ffmpeg.exe": "CA2BCCBF1A2A5A379AE484AD127D120CC3E394833B69767694A1E738F2D6BE55",
    "ffprobe.exe": "4EC2AC9385AACBAF927B7E8D031291059CEA2E02EE6BFAE0D708F78E1C528251",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def command(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def main() -> int:
    readiness = json.loads(READINESS.read_text(encoding="utf-8"))
    replacement = json.loads(REPLACEMENT.read_text(encoding="utf-8"))
    checks: dict[str, dict[str, object]] = {}

    for name, expected in CANDIDATE_HASHES.items():
        formal = FORMAL / name
        packaged = PACKAGE / "_internal" / "Tools" / "ffmpeg" / "bin" / name
        checks[f"formal_{name}"] = {"actual": sha256(formal), "expected": expected}
        checks[f"packaged_{name}"] = {"actual": sha256(packaged), "expected": expected}

    source_expected = readiness["corresponding_source"]["sha256"]
    checks["corresponding_source"] = {
        "actual": sha256(SOURCE),
        "expected": source_expected,
        "materials_complete": readiness["technical_checks"]["corresponding_source_contents_complete"],
    }
    checks["clean_package"] = {
        "config_json_absent": not (PACKAGE / "config.json").exists(),
        "cache_absent": not (PACKAGE / "Cache").exists(),
        "temp_absent": not (PACKAGE / "Temp").exists(),
        "runtime_log_absent": not (PACKAGE / "logs" / "runtime.log").exists(),
    }

    archive_test = command([str(SEVEN_ZIP), "t", str(ARCHIVE)])
    checks["archive_integrity"] = {"exit_code": archive_test.returncode}
    archive_listing = command([str(SEVEN_ZIP), "l", "-slt", str(ARCHIVE)])
    listing = archive_listing.stdout + archive_listing.stderr
    checks["archive_contents"] = {
        "exit_code": archive_listing.returncode,
        "contains_ffmpeg": "Tools/ffmpeg/bin/ffmpeg.exe" in listing.replace("\\", "/"),
        "contains_ffprobe": "Tools/ffmpeg/bin/ffprobe.exe" in listing.replace("\\", "/"),
        "contains_config_json": "config.json" in listing,
        "contains_cache": "/Cache/" in listing.replace("\\", "/"),
        "contains_temp": "/Temp/" in listing.replace("\\", "/"),
        "contains_runtime_log": "logs/runtime.log" in listing.replace("\\", "/"),
    }

    smoke_results: dict[str, int] = {}
    executable = SMOKE_PACKAGE / "Qonic_Audio_v5.0_internal_test.exe"
    smoke_env = os.environ.copy()
    smoke_env["QT_QPA_PLATFORM"] = "offscreen"
    for module in ("audioEditor", "autoConvert", "settings"):
        try:
            result = subprocess.run(
                [str(executable), "--qml-smoke-test", f"--qml-open-module={module}"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                env=smoke_env,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            smoke_results[module] = result.returncode
        except subprocess.TimeoutExpired:
            smoke_results[module] = -1
    checks["packaged_qml_smoke"] = smoke_results

    regression_attempts = [command(["python", "-m", "pytest", "-q"], timeout=120)]
    if regression_attempts[0].returncode != 0:
        regression_attempts.append(command(["python", "-m", "pytest", "-q"], timeout=120))
    regression = regression_attempts[-1]
    checks["full_regression"] = {
        "exit_code": regression.returncode,
        "summary": regression.stdout.splitlines()[-1] if regression.stdout else "",
        "attempt_count": len(regression_attempts),
        "first_attempt_exit_code": regression_attempts[0].returncode,
    }

    runtime_hash_checks = [
        checks[f"{scope}_{name}"]
        for scope in ("formal", "packaged")
        for name in CANDIDATE_HASHES
    ]
    passed = (
        replacement.get("status") == "FORMAL_RUNTIME_REPLACED_PENDING_ONEDIR_REBUILD"
        and readiness.get("replacement_authorized") is True
        and all(item["actual"] == item["expected"] for item in runtime_hash_checks)
        and checks["corresponding_source"]["actual"] == checks["corresponding_source"]["expected"]
        and checks["corresponding_source"]["materials_complete"] is True
        and all(checks["clean_package"].values())
        and checks["archive_integrity"]["exit_code"] == 0
        and checks["archive_contents"]["exit_code"] == 0
        and checks["archive_contents"]["contains_ffmpeg"] is True
        and checks["archive_contents"]["contains_ffprobe"] is True
        and checks["archive_contents"]["contains_config_json"] is False
        and checks["archive_contents"]["contains_cache"] is False
        and checks["archive_contents"]["contains_temp"] is False
        and checks["archive_contents"]["contains_runtime_log"] is False
        and all(code == 0 for code in smoke_results.values())
        and checks["full_regression"]["exit_code"] == 0
    )
    payload = {
        "schema_version": 1,
        "phase": "B5",
        "status": "PASS" if passed else "FAIL",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "release_set": SET_ROOT.relative_to(ROOT).as_posix(),
        "archive": {
            "path": ARCHIVE.relative_to(ROOT).as_posix(),
            "sha256": sha256(ARCHIVE),
            "size_bytes": ARCHIVE.stat().st_size,
        },
        "checks": checks,
        "runtime_scope": readiness["runtime_scope"],
        "final_replacement_status": "FORMAL_REPLACEMENT_VERIFIED" if passed else "FINAL_REPLACEMENT_NOT_YET_VERIFIED",
    }
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(REPORT)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
