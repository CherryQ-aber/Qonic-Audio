from __future__ import annotations

import errno
import logging
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path


SUPPORTED_INPUT_EXTENSIONS = {
    ".mp3": "MP3",
    ".flac": "FLAC",
    ".wav": "WAV",
    ".m4a": "M4A",
    ".aac": "AAC",
    ".ogg": "OGG",
    ".opus": "OPUS",
    ".ape": "APE",
    ".aiff": "AIFF",
    ".aif": "AIFF",
    ".wma": "WMA",
    ".alac": "ALAC",
}

UNSUPPORTED_INPUT_MESSAGES = {
    ".ncm": "Phase 4.5 单文件转换暂不支持 NCM，请继续使用旧 Widgets 自动转码流程。",
}

SUPPORTED_OUTPUT_FORMATS = {
    "mp3": {"label": "MP3", "extension": ".mp3", "ffmpeg_args": []},
    "flac": {"label": "FLAC", "extension": ".flac", "ffmpeg_args": []},
    "wav": {"label": "WAV", "extension": ".wav", "ffmpeg_args": []},
    "aac": {"label": "AAC", "extension": ".aac", "ffmpeg_args": []},
    "ogg": {"label": "OGG", "extension": ".ogg", "ffmpeg_args": []},
    "opus": {"label": "OPUS", "extension": ".opus", "ffmpeg_args": []},
    "m4a": {"label": "M4A", "extension": ".m4a", "ffmpeg_args": ["-c:a", "aac"]},
}

PROJECT_ROOT = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)


def _resolve_app_path(*parts: str) -> Path:
    direct_path = PROJECT_ROOT.joinpath(*parts)
    if direct_path.exists():
        return direct_path

    internal_path = PROJECT_ROOT.joinpath("_internal", *parts)
    if internal_path.exists():
        return internal_path

    return direct_path


FFMPEG_PATH = str(_resolve_app_path("Tools", "ffmpeg", "bin", "ffmpeg.exe"))
logger = logging.getLogger(__name__)

_TEMP_NAME_ATTEMPTS = 8


def convert_single_file_to_new_path(
    input_path: str,
    output_path: str,
    target_format: str | None = None,
) -> dict:
    """Convert one audio file to one new path without touching queue state."""

    started = time.perf_counter()
    validation = validate_single_file_convert_request(
        input_path,
        output_path,
        target_format,
    )
    if not validation["ok"]:
        return validation

    input_file = Path(validation["input_path"])
    final_output = Path(validation["output_path"])
    normalized_target = str(validation["target_format"])
    temp_output = _make_temp_output_path(final_output)
    source_size = _safe_size(input_file)

    if temp_output is None:
        return _base_result(
            False,
            "无法生成唯一临时输出路径，已阻止转换",
            str(input_file),
            str(final_output),
            normalized_target,
            source_size_bytes=source_size,
            error_code="TEMP_PATH_CONFLICT",
        )

    command = [
        FFMPEG_PATH,
        "-nostdin",
        "-n",
        "-i",
        str(input_file),
        "-map_metadata",
        "-1",
        "-map_chapters",
        "-1",
        "-vn",
        *SUPPORTED_OUTPUT_FORMATS[normalized_target]["ffmpeg_args"],
        str(temp_output),
    ]

    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            **_hidden_subprocess_kwargs(),
        )
    except OSError as exc:
        return _base_result(
            False,
            f"FFmpeg 启动失败：{exc}",
            str(input_file),
            str(final_output),
            normalized_target,
            source_size_bytes=source_size,
            temp_path=str(temp_output),
            error_code="FFMPEG_NOT_FOUND",
        )

    stderr_tail = _tail(process.stderr or "")
    duration_ms = int((time.perf_counter() - started) * 1000)

    if process.returncode != 0:
        return _with_temp_cleanup(
            _base_result(
                False,
                "FFmpeg 转换失败",
                str(input_file),
                str(final_output),
                normalized_target,
                source_size_bytes=source_size,
                duration_ms=duration_ms,
                ffmpeg_returncode=process.returncode,
                ffmpeg_stderr_tail=stderr_tail,
                temp_path=str(temp_output),
                error_code="FFMPEG_FAILED",
            ),
            temp_output,
        )

    if final_output.exists():
        return _with_temp_cleanup(
            _base_result(
                False,
                "转换已完成，但目标路径已被其他进程创建；为避免覆盖，结果未写入。",
                str(input_file),
                str(final_output),
                normalized_target,
                source_size_bytes=source_size,
                duration_ms=duration_ms,
                ffmpeg_returncode=process.returncode,
                ffmpeg_stderr_tail=stderr_tail,
                temp_path=str(temp_output),
                error_code="OUTPUT_CONFLICT",
                output_conflict=True,
            ),
            temp_output,
        )

    if not temp_output.is_file():
        return _with_temp_cleanup(
            _base_result(
                False,
                "FFmpeg 未生成临时输出文件",
                str(input_file),
                str(final_output),
                normalized_target,
                source_size_bytes=source_size,
                duration_ms=duration_ms,
                ffmpeg_returncode=process.returncode,
                ffmpeg_stderr_tail=stderr_tail,
                temp_path=str(temp_output),
                error_code="TEMP_OUTPUT_MISSING",
            ),
            temp_output,
        )

    if _safe_size(temp_output) <= 0:
        return _with_temp_cleanup(
            _base_result(
                False,
                "FFmpeg 生成的临时输出文件为空",
                str(input_file),
                str(final_output),
                normalized_target,
                source_size_bytes=source_size,
                duration_ms=duration_ms,
                ffmpeg_returncode=process.returncode,
                ffmpeg_stderr_tail=stderr_tail,
                temp_path=str(temp_output),
                error_code="TEMP_OUTPUT_EMPTY",
            ),
            temp_output,
        )

    finalization = _finalize_no_clobber(temp_output, final_output)
    if not finalization["ok"]:
        return _base_result(
            False,
            str(finalization["error"]),
            str(input_file),
            str(final_output),
            normalized_target,
            source_size_bytes=source_size,
            duration_ms=duration_ms,
            ffmpeg_returncode=process.returncode,
            ffmpeg_stderr_tail=stderr_tail,
            temp_path=str(temp_output),
            error_code=str(finalization["error_code"]),
            finalization_strategy=str(finalization["finalization_strategy"]),
            output_conflict=bool(finalization["output_conflict"]),
            temp_cleanup_ok=bool(finalization["temp_cleanup_ok"]),
            warning=str(finalization["warning"]),
        )

    return _base_result(
        True,
        "",
        str(input_file),
        str(final_output),
        normalized_target,
        source_size_bytes=source_size,
        output_size_bytes=_safe_size(final_output),
        duration_ms=duration_ms,
        ffmpeg_returncode=process.returncode,
        ffmpeg_stderr_tail=stderr_tail,
        temp_path=str(temp_output),
        finalization_strategy=str(finalization["finalization_strategy"]),
        temp_cleanup_ok=bool(finalization["temp_cleanup_ok"]),
        warning=str(finalization["warning"]),
    )


def validate_single_file_convert_request(
    input_path: str,
    output_path: str,
    target_format: str | None = None,
) -> dict:
    input_text = str(input_path or "").strip()
    output_text = str(output_path or "").strip()
    normalized_input = _normalize_path(input_text) if input_text else ""
    normalized_output = _normalize_path(output_text) if output_text else ""
    output_format = _resolve_target_format(output_text, target_format)

    result = _base_result(
        False,
        "",
        normalized_input,
        normalized_output,
        output_format or "",
    )

    if not input_text:
        result["error"] = "输入文件路径为空"
        result["error_code"] = "INVALID_INPUT"
        return result
    if not output_text:
        result["error"] = "输出文件路径为空"
        result["error_code"] = "INVALID_OUTPUT_PATH"
        return result

    input_file = Path(normalized_input)
    final_output = Path(normalized_output)

    if not input_file.exists():
        result["error"] = "输入文件不存在"
        result["error_code"] = "INPUT_NOT_FOUND"
        return result
    if not input_file.is_file():
        result["error"] = "输入路径不是文件"
        result["error_code"] = "INVALID_INPUT"
        return result

    input_extension = input_file.suffix.lower()
    if input_extension in UNSUPPORTED_INPUT_MESSAGES:
        result["error"] = UNSUPPORTED_INPUT_MESSAGES[input_extension]
        result["error_code"] = "NCM_NOT_SUPPORTED"
        return result
    if input_extension not in SUPPORTED_INPUT_EXTENSIONS:
        result["error"] = "输入格式暂不支持"
        result["error_code"] = "INVALID_INPUT"
        return result

    if not final_output.parent.exists():
        result["error"] = "输出目录不存在"
        result["error_code"] = "INVALID_OUTPUT_PATH"
        return result
    if not final_output.parent.is_dir():
        result["error"] = "输出父路径不是目录"
        result["error_code"] = "INVALID_OUTPUT_PATH"
        return result
    if _same_file_path(input_file, final_output):
        result["error"] = "输出路径不能与输入文件相同"
        result["error_code"] = "INVALID_OUTPUT_PATH"
        return result
    if final_output.exists():
        result["error"] = "输出文件已存在，已阻止覆盖"
        result["error_code"] = "OUTPUT_EXISTS"
        return result

    if output_format not in SUPPORTED_OUTPUT_FORMATS:
        result["error"] = "输出格式暂不支持"
        result["error_code"] = "INVALID_OUTPUT_PATH"
        return result

    expected_extension = SUPPORTED_OUTPUT_FORMATS[output_format]["extension"]
    if final_output.suffix.lower() != expected_extension:
        result["error"] = "目标格式与输出文件后缀不一致"
        result["error_code"] = "INVALID_OUTPUT_PATH"
        return result

    if not os.path.isfile(FFMPEG_PATH):
        result["error"] = f"FFmpeg 不存在：{FFMPEG_PATH}"
        result["error_code"] = "FFMPEG_NOT_FOUND"
        return result

    result.update(
        {
            "ok": True,
            "target_format": output_format,
            "source_size_bytes": _safe_size(input_file),
        }
    )
    return result


def format_file_size(size_bytes: int | None) -> str:
    if size_bytes is None:
        return "-"
    try:
        size = float(size_bytes)
    except (TypeError, ValueError):
        return "-"

    units = ("B", "KB", "MB", "GB")
    index = 0
    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1

    if index == 0:
        return f"{int(size)} B"
    return f"{size:.2f} {units[index]}"


def get_output_format_options() -> list[str]:
    return list(SUPPORTED_OUTPUT_FORMATS.keys())


def get_input_format_label(path: str) -> str:
    extension = Path(str(path or "")).suffix.lower()
    if extension == ".ncm":
        return "NCM（暂不支持）"
    return SUPPORTED_INPUT_EXTENSIONS.get(extension, extension.lstrip(".").upper() or "未知")


def _base_result(
    ok: bool,
    error: str,
    input_path: str,
    output_path: str,
    target_format: str,
    *,
    source_size_bytes: int = 0,
    output_size_bytes: int = 0,
    duration_ms: int = 0,
    ffmpeg_returncode: int | None = None,
    ffmpeg_stderr_tail: str = "",
    temp_path: str = "",
    error_code: str = "",
    finalization_strategy: str = "",
    output_conflict: bool = False,
    temp_cleanup_ok: bool = True,
    warning: str = "",
) -> dict:
    return {
        "ok": ok,
        "error": error,
        "input_path": input_path,
        "output_path": output_path,
        "target_format": target_format,
        "source_size_bytes": source_size_bytes,
        "output_size_bytes": output_size_bytes,
        "duration_ms": duration_ms,
        "ffmpeg_returncode": ffmpeg_returncode,
        "ffmpeg_stderr_tail": ffmpeg_stderr_tail,
        "temp_path": temp_path,
        "error_code": error_code,
        "finalization_strategy": finalization_strategy,
        "output_conflict": output_conflict,
        "temp_cleanup_ok": temp_cleanup_ok,
        "warning": warning,
    }


def _resolve_target_format(output_path: str, target_format: str | None) -> str:
    requested = str(target_format or "").strip().lower()
    if requested in SUPPORTED_OUTPUT_FORMATS:
        return requested

    extension = Path(str(output_path or "")).suffix.lower()
    for name, info in SUPPORTED_OUTPUT_FORMATS.items():
        if extension == info["extension"]:
            return name
    return requested


def _normalize_path(path: str) -> str:
    return os.path.abspath(os.path.normpath(os.fspath(path)))


def _same_file_path(first: Path, second: Path) -> bool:
    return os.path.normcase(str(first.resolve(strict=False))) == os.path.normcase(
        str(second.resolve(strict=False))
    )


def _make_temp_output_path(output_path: Path) -> Path | None:
    """Return an unused same-directory temp path that keeps the media suffix."""

    for _ in range(_TEMP_NAME_ATTEMPTS):
        token = uuid.uuid4().hex
        candidate = output_path.with_name(
            f".{output_path.stem}.{token}.cherryq_tmp{output_path.suffix}"
        )
        if not candidate.exists():
            return candidate
    return None


def _finalize_no_clobber(temp_output: Path, final_output: Path) -> dict:
    """Publish a completed temp file without any overwrite-capable operation."""

    temp_identity = _file_identity(temp_output)
    if temp_identity is None:
        return {
            "ok": False,
            "error": "临时输出文件在最终落位前丢失",
            "error_code": "TEMP_OUTPUT_MISSING",
            "finalization_strategy": "",
            "output_conflict": False,
            "temp_cleanup_ok": True,
            "warning": "",
        }

    try:
        # link() atomically fails if final_output already exists and has no
        # overwrite branch.
        os.link(temp_output, final_output)
    except FileExistsError:
        return _finalization_failure_with_cleanup(
            temp_output,
            temp_identity,
            "转换已完成，但目标路径已被其他进程创建；为避免覆盖，结果未写入。",
            "OUTPUT_CONFLICT",
            "hardlink",
            output_conflict=True,
        )
    except OSError:
        return _finalize_with_exclusive_copy(
            temp_output,
            final_output,
            temp_identity,
        )

    cleanup_ok, warning = _cleanup_owned_temp(temp_output, temp_identity)
    return {
        "ok": True,
        "error": "",
        "error_code": "",
        "finalization_strategy": "hardlink",
        "output_conflict": False,
        "temp_cleanup_ok": cleanup_ok,
        "warning": warning,
    }


def _finalize_with_exclusive_copy(
    temp_output: Path,
    final_output: Path,
    temp_identity: tuple[int, int] | None,
) -> dict:
    """Fallback for filesystems without hardlink support, still no-clobber."""

    descriptor: int | None = None
    final_identity: tuple[int, int] | None = None
    try:
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        flags |= getattr(os, "O_BINARY", 0)
        descriptor = os.open(str(final_output), flags, 0o666)
        final_identity = _identity_from_stat(os.fstat(descriptor))
        with os.fdopen(descriptor, "wb") as final_handle:
            descriptor = None
            with temp_output.open("rb") as temp_handle:
                shutil.copyfileobj(temp_handle, final_handle, length=1024 * 1024)
            final_handle.flush()
            os.fsync(final_handle.fileno())
    except FileExistsError:
        return _finalization_failure_with_cleanup(
            temp_output,
            temp_identity,
            "转换已完成，但目标路径已被其他进程创建；为避免覆盖，结果未写入。",
            "OUTPUT_CONFLICT",
            "exclusive_copy",
            output_conflict=True,
        )
    except OSError as exc:
        if descriptor is not None:
            os.close(descriptor)
        final_cleanup_ok, final_warning = _remove_owned_file(
            final_output,
            final_identity,
        )
        result = _finalization_failure_with_cleanup(
            temp_output,
            temp_identity,
            f"最终落位失败：{exc}",
            _error_code_for_os_error(exc),
            "exclusive_copy",
        )
        if not final_cleanup_ok:
            result["warning"] = _join_warning(result["warning"], final_warning)
        return result

    cleanup_ok, warning = _cleanup_owned_temp(temp_output, temp_identity)
    return {
        "ok": True,
        "error": "",
        "error_code": "",
        "finalization_strategy": "exclusive_copy",
        "output_conflict": False,
        "temp_cleanup_ok": cleanup_ok,
        "warning": warning,
    }


def _finalization_failure_with_cleanup(
    temp_output: Path,
    temp_identity: tuple[int, int] | None,
    error: str,
    error_code: str,
    finalization_strategy: str,
    *,
    output_conflict: bool = False,
) -> dict:
    cleanup_ok, warning = _cleanup_owned_temp(temp_output, temp_identity)
    return {
        "ok": False,
        "error": error,
        "error_code": error_code,
        "finalization_strategy": finalization_strategy,
        "output_conflict": output_conflict,
        "temp_cleanup_ok": cleanup_ok,
        "warning": warning,
    }


def _with_temp_cleanup(result: dict, temp_output: Path) -> dict:
    cleanup_ok, warning = _cleanup_owned_temp(
        temp_output,
        _file_identity(temp_output),
    )
    result["temp_cleanup_ok"] = cleanup_ok
    result["warning"] = _join_warning(str(result.get("warning") or ""), warning)
    return result


def _cleanup_owned_temp(
    temp_output: Path,
    expected_identity: tuple[int, int] | None,
) -> tuple[bool, str]:
    if not temp_output.exists():
        return True, ""
    if expected_identity is None or _file_identity(temp_output) != expected_identity:
        warning = "临时文件身份不匹配，未执行清理。"
        logger.warning("%s %s", warning, temp_output)
        return False, warning
    try:
        temp_output.unlink()
        return True, ""
    except OSError as exc:
        warning = f"临时文件清理失败：{exc}"
        logger.warning("%s (%s)", warning, temp_output)
        return False, warning


def _remove_owned_file(
    path: Path,
    expected_identity: tuple[int, int] | None,
) -> tuple[bool, str]:
    if expected_identity is None or not path.exists():
        return True, ""
    if _file_identity(path) != expected_identity:
        warning = "最终输出文件身份不匹配，未删除。"
        logger.warning("%s %s", warning, path)
        return False, warning
    try:
        path.unlink()
        return True, ""
    except OSError as exc:
        warning = f"不完整最终输出清理失败：{exc}"
        logger.warning("%s (%s)", warning, path)
        return False, warning


def _file_identity(path: Path) -> tuple[int, int] | None:
    try:
        return _identity_from_stat(path.stat())
    except OSError:
        return None


def _identity_from_stat(stat_result: os.stat_result) -> tuple[int, int]:
    return (int(stat_result.st_dev), int(stat_result.st_ino))


def _error_code_for_os_error(exc: OSError) -> str:
    if isinstance(exc, PermissionError) or exc.errno in (errno.EACCES, errno.EPERM):
        return "PERMISSION_DENIED"
    if exc.errno == errno.ENOSPC:
        return "DISK_WRITE_FAILED"
    return "FINALIZE_FAILED"


def _join_warning(existing: str, extra: str) -> str:
    return "; ".join(part for part in (existing, extra) if part)


def _safe_size(path: Path) -> int:
    try:
        return int(path.stat().st_size)
    except OSError:
        return 0


def _tail(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def _hidden_subprocess_kwargs() -> dict:
    if not sys.platform.startswith("win"):
        return {}

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
    return {
        "startupinfo": startupinfo,
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
    }
