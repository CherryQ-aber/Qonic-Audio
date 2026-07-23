from __future__ import annotations

import os
import shutil
from hashlib import sha256
from pathlib import Path
from uuid import uuid4


def publish_no_clobber(temp_path: Path, output_path: Path) -> dict[str, object]:
    """Publish an owned temp file without ever replacing an existing output."""
    if not temp_path.is_file():
        return _result(False, "finalization_failed", "临时副本在发布前丢失。")
    if output_path.exists():
        return _result(False, "output_exists", "目标文件已存在，未覆盖。")

    identity = _identity(temp_path)
    try:
        os.link(temp_path, output_path)
    except FileExistsError:
        return _failure_with_cleanup(temp_path, identity, "output_conflict", "目标路径在发布时被占用。")
    except OSError:
        return _publish_with_exclusive_copy(temp_path, output_path, identity)

    cleanup_ok = cleanup_owned_temp(temp_path, identity)
    return _result(True, "", "已通过 hardlink 发布新文件。", "hardlink", cleanup_ok, identity)


def publish_confirmed_overwrite(
    temp_path: Path,
    output_path: Path,
    expected_target_sha256: str,
) -> dict[str, object]:
    """Replace one confirmed existing target while retaining a rollback copy.

    The caller must finish with :func:`commit_confirmed_overwrite` after its
    semantic read-back succeeds, or :func:`rollback_confirmed_overwrite` when
    that verification fails.
    """
    if not temp_path.is_file():
        return _result(False, "finalization_failed", "临时副本在覆盖前丢失。")
    if not output_path.is_file():
        return _failure_with_cleanup(
            temp_path,
            _identity(temp_path),
            "overwrite_target_missing",
            "确认覆盖的目标文件已不存在。",
            "confirmed_atomic_replace",
        )
    temp_identity = _identity(temp_path)
    original_target_identity = _identity(output_path)
    try:
        if _sha256(output_path) != str(expected_target_sha256 or ""):
            return _failure_with_cleanup(
                temp_path,
                _identity(temp_path),
                "overwrite_target_changed",
                "目标文件在确认后发生变化，已取消覆盖。",
                "confirmed_atomic_replace",
            )
        replacement_sha256 = _sha256(temp_path)
    except OSError as exc:
        return _failure_with_cleanup(
            temp_path,
            _identity(temp_path),
            "overwrite_target_unreadable",
            f"无法在覆盖前校验目标文件：{exc}",
            "confirmed_atomic_replace",
        )

    backup_path = output_path.parent / (
        f".{output_path.name}.qonic_rollback_{uuid4().hex}.bak"
    )
    backup_identity: tuple[int, int] | None = None
    try:
        try:
            os.link(output_path, backup_path)
        except OSError:
            with output_path.open("rb") as source_handle:
                descriptor = os.open(
                    str(backup_path),
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY
                    | getattr(os, "O_BINARY", 0),
                    0o666,
                )
                with os.fdopen(descriptor, "wb", closefd=True) as backup_handle:
                    shutil.copyfileobj(
                        source_handle,
                        backup_handle,
                        length=1024 * 1024,
                    )
                    backup_handle.flush()
                    os.fsync(backup_handle.fileno())
        backup_identity = _identity(backup_path)
        if backup_identity is None or _sha256(backup_path) != expected_target_sha256:
            raise OSError("回滚备份校验失败")
        os.replace(temp_path, output_path)
        if _sha256(output_path) != replacement_sha256:
            raise OSError("替换后的文件校验失败")
    except OSError as exc:
        restored = False
        try:
            current_output_identity = _identity(output_path)
            safe_to_restore = (
                current_output_identity is None
                or current_output_identity in {
                    original_target_identity,
                    temp_identity,
                }
            )
            if (
                safe_to_restore
                and backup_identity is not None
                and _identity(backup_path) == backup_identity
            ):
                os.replace(backup_path, output_path)
                restored = _sha256(output_path) == expected_target_sha256
        except OSError:
            restored = False
        cleanup_owned_temp(temp_path, _identity(temp_path))
        cleanup_owned_temp(backup_path, backup_identity)
        return _result(
            False,
            "overwrite_failed",
            (
                f"覆盖失败，已恢复原文件：{exc}"
                if restored
                else f"覆盖失败，自动恢复未完成：{exc}"
            ),
            "confirmed_atomic_replace",
            not temp_path.exists() and not backup_path.exists(),
        )

    return {
        **_result(
            True,
            "",
            "已完成确认覆盖，等待最终内容验证。",
            "confirmed_atomic_replace",
            True,
            _identity(output_path),
        ),
        "overwrote_existing": True,
        "rollback_backup_path": str(backup_path),
        "rollback_backup_identity": backup_identity,
        "original_target_sha256": expected_target_sha256,
        "replacement_sha256": replacement_sha256,
    }


def commit_confirmed_overwrite(publication: dict[str, object]) -> bool:
    raw_backup_path = str(publication.get("rollback_backup_path") or "")
    if not raw_backup_path:
        return True
    backup_path = Path(raw_backup_path)
    backup_identity = publication.get("rollback_backup_identity")
    return cleanup_owned_temp(backup_path, backup_identity)


def rollback_confirmed_overwrite(
    output_path: Path,
    publication: dict[str, object],
) -> bool:
    raw_backup_path = str(publication.get("rollback_backup_path") or "")
    if not raw_backup_path:
        return False
    backup_path = Path(raw_backup_path)
    backup_identity = publication.get("rollback_backup_identity")
    expected_sha256 = str(publication.get("original_target_sha256") or "")
    if not backup_path.is_file() or _identity(backup_path) != backup_identity:
        return False
    published_identity = publication.get("output_identity")
    if published_identity is not None and _identity(output_path) != published_identity:
        return False
    expected_replacement_sha256 = str(
        publication.get("replacement_sha256") or ""
    )
    try:
        if (
            expected_replacement_sha256
            and _sha256(output_path) != expected_replacement_sha256
        ):
            return False
    except OSError:
        return False
    try:
        os.replace(backup_path, output_path)
        return _sha256(output_path) == expected_sha256
    except OSError:
        return False


def cleanup_owned_temp(path: Path, identity: tuple[int, int] | None) -> bool:
    """Remove only the file identity created by the current transaction."""
    if not path.exists():
        return True
    if identity is not None and _identity(path) != identity:
        return False
    try:
        path.unlink()
        return True
    except OSError:
        return False


def _publish_with_exclusive_copy(
    temp_path: Path,
    output_path: Path,
    temp_identity: tuple[int, int] | None,
) -> dict[str, object]:
    descriptor: int | None = None
    output_identity: tuple[int, int] | None = None
    try:
        descriptor = os.open(
            str(output_path),
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0),
            0o666,
        )
        with os.fdopen(descriptor, "wb", closefd=True) as output_handle:
            descriptor = None
            with temp_path.open("rb") as input_handle:
                shutil.copyfileobj(input_handle, output_handle, length=1024 * 1024)
            output_handle.flush()
            os.fsync(output_handle.fileno())
        output_identity = _identity(output_path)
    except FileExistsError:
        return _failure_with_cleanup(temp_path, temp_identity, "output_conflict", "目标路径在发布时被占用。", "exclusive_copy")
    except OSError as exc:
        if descriptor is not None:
            os.close(descriptor)
        output_identity = output_identity or _identity(output_path)
        if output_identity is not None:
            cleanup_owned_temp(output_path, output_identity)
        return _failure_with_cleanup(temp_path, temp_identity, "finalization_failed", f"无法独占发布输出文件：{exc}", "exclusive_copy")

    cleanup_ok = cleanup_owned_temp(temp_path, temp_identity)
    return _result(True, "", "已通过独占复制发布新文件。", "exclusive_copy", cleanup_ok, output_identity)


def _failure_with_cleanup(
    temp_path: Path,
    identity: tuple[int, int] | None,
    error_code: str,
    message: str,
    strategy: str = "hardlink",
) -> dict[str, object]:
    return _result(False, error_code, message, strategy, cleanup_owned_temp(temp_path, identity))


def _identity(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
        return stat.st_dev, stat.st_ino
    except OSError:
        return None


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _result(
    success: bool,
    error_code: str,
    message: str,
    strategy: str = "",
    temp_cleanup_success: bool = True,
    output_identity: tuple[int, int] | None = None,
) -> dict[str, object]:
    return {
        "success": success,
        "error_code": error_code,
        "message": message,
        "finalization_strategy": strategy,
        "temp_cleanup_success": temp_cleanup_success,
        "output_identity": output_identity,
    }
