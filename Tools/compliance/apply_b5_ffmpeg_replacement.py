"""Apply the owner-approved B5 runtime replacement with a recoverable backup."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FORMAL = ROOT / "Tools" / "ffmpeg" / "bin"
CANDIDATE = ROOT / "third_party" / "ffmpeg-build" / "output" / "candidate"
APPROVAL = ROOT / "compliance" / "report" / "ffmpeg-self-build" / "b5-owner-approval.json"
REPORT = ROOT / "compliance" / "report" / "ffmpeg-self-build" / "b5-formal-replacement.json"
BACKUP = ROOT / "Release" / "Non_Authoritative" / "2026-07-28_b5-former-gyan"

FORMAL_HASHES = {
    "ffmpeg.exe": "09948D4CDD0650DA6FF5A87577469F2A218DC2615AE379F8F734D24C49DE0F73",
    "ffprobe.exe": "A6618E99BB58869DED3C6F37B53AA1A8D701C3591DBB7B5B317D47369C112BE2",
}
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


def require_hash(path: Path, expected: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    actual = sha256(path)
    if actual != expected:
        raise RuntimeError(f"unexpected SHA-256 for {path}: {actual}")


def copy_verified(source: Path, destination: Path, expected: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    require_hash(destination, expected)


def replace_verified(source: Path, destination: Path, expected: str) -> None:
    temporary = destination.with_name(destination.name + ".b5-new")
    if temporary.exists():
        temporary.unlink()
    copy_verified(source, temporary, expected)
    os.replace(temporary, destination)
    require_hash(destination, expected)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    approval = json.loads(APPROVAL.read_text(encoding="utf-8"))
    if approval.get("approval_status") != "APPROVED":
        raise RuntimeError("B5 replacement requires recorded owner approval")
    if BACKUP.exists():
        raise RuntimeError(f"refusing to overwrite existing B5 backup: {BACKUP}")

    backup_bin = BACKUP / "Tools" / "ffmpeg" / "bin"
    before = {name: sha256(FORMAL / name) for name in FORMAL_HASHES}
    for name, expected in FORMAL_HASHES.items():
        require_hash(FORMAL / name, expected)
        require_hash(CANDIDATE / name, CANDIDATE_HASHES[name])
        copy_verified(FORMAL / name, backup_bin / name, expected)

    (BACKUP / "NOT_FOR_RELEASE").write_text(
        "Former Gyan FFmpeg runtime retained solely for B5 rollback.\n",
        encoding="utf-8",
    )
    write_json(
        BACKUP / "BACKUP_MANIFEST.json",
        {
            "status": "ROLLBACK_ONLY_NOT_FOR_RELEASE",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "approval_record": APPROVAL.relative_to(ROOT).as_posix(),
            "files": before,
        },
    )

    try:
        for name, expected in CANDIDATE_HASHES.items():
            replace_verified(CANDIDATE / name, FORMAL / name, expected)
    except Exception:
        for name, expected in FORMAL_HASHES.items():
            restore = backup_bin / name
            if restore.is_file():
                replace_verified(restore, FORMAL / name, expected)
        raise

    after = {name: sha256(FORMAL / name) for name in FORMAL_HASHES}
    payload = {
        "schema_version": 1,
        "phase": "B5",
        "status": "FORMAL_RUNTIME_REPLACED_PENDING_ONEDIR_REBUILD",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "approval_record": APPROVAL.relative_to(ROOT).as_posix(),
        "backup_directory": BACKUP.relative_to(ROOT).as_posix(),
        "before_sha256": before,
        "after_sha256": after,
        "candidate_sha256": CANDIDATE_HASHES,
        "rollback_verified": all(
            sha256(backup_bin / name) == expected
            for name, expected in FORMAL_HASHES.items()
        ),
    }
    write_json(REPORT, payload)
    print(REPORT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
