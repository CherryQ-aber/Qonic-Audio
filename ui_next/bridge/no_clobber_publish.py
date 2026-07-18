from __future__ import annotations

import os
import shutil
from pathlib import Path


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
