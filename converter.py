# 音频转换模块
import os
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path

from config import (
    FFMPEG_PATH,
    get_copy_lrc_to_output,
    get_create_format_subfolder,
    get_embed_lyrics_after_convert,
    get_output_folder,
    get_overwrite_existing_lyrics,
)
from formats import (
    DEFAULT_TARGET_FORMAT,
    get_ffmpeg_args_for_target,
    get_target_extension,
    get_target_label,
    normalize_extension,
    normalize_target_format,
)
from lyrics import process_lyrics_for_output
from logger import logger
from ui_next.bridge.no_clobber_publish import publish_no_clobber

logger.info(f"FFmpeg路径: {FFMPEG_PATH}")
logger.info(
    f"FFmpeg就绪状态: {os.path.exists(FFMPEG_PATH)}"
)
logger.info("当前 converter.py 已加载")


class ConversionCancelled(RuntimeError):
    """Raised only after the FFmpeg child for the current task is reaped."""


def _ensure_output_created(output_path):
    if not os.path.exists(output_path):
        raise FileNotFoundError(
            f"输出文件不存在: {output_path}"
        )

    if os.path.getsize(output_path) <= 0:
        raise ValueError(
            f"输出文件为空: {output_path}"
        )


def get_available_output_path(output_path):
    if not os.path.exists(output_path):
        return output_path

    output_dir = os.path.dirname(output_path)
    stem, extension = os.path.splitext(os.path.basename(output_path))
    suffix = 1

    while True:
        candidate = os.path.join(
            output_dir,
            f"{stem} ({suffix}){extension}"
        )

        if not os.path.exists(candidate):
            logger.info(f"输出文件已存在，自动改名为: {candidate}")
            return candidate

        suffix += 1


def build_output_path(
    input_path,
    target_format,
    output_root,
    create_format_subfolder=True,
):
    target_format = normalize_target_format(target_format, DEFAULT_TARGET_FORMAT)
    target_extension = get_target_extension(target_format)
    filename = os.path.splitext(
        os.path.basename(input_path)
    )[0]

    output_dir = output_root

    if create_format_subfolder:
        output_dir = os.path.join(
            output_root,
            get_target_label(target_format)
        )

    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(
        output_dir,
        f"{filename}{target_extension}"
    )

    return get_available_output_path(output_path)


def _get_hidden_subprocess_kwargs():
    if os.name != "nt":
        return {}

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    return {
        "startupinfo": startupinfo,
        "creationflags": creationflags,
    }


def _run_ffmpeg_command(command, cancel_event: threading.Event | None = None):
    if cancel_event is not None:
        return _run_cancellable_ffmpeg_command(command, cancel_event)
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        **_get_hidden_subprocess_kwargs()
    )


def _run_cancellable_ffmpeg_command(command, cancel_event: threading.Event):
    """Run a conversion child with bounded cancellation and no console window."""
    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **_get_hidden_subprocess_kwargs(),
    )
    while process.poll() is None:
        if cancel_event.is_set():
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
            raise ConversionCancelled("用户已取消当前转换任务")
        time.sleep(0.1)

    return subprocess.CompletedProcess(command, process.returncode, "", "")


def _validate_audio_file(input_path):
    if not os.path.isfile(FFMPEG_PATH):
        raise FileNotFoundError(
            f"FFmpeg不存在: {FFMPEG_PATH}"
        )

    result = _run_ffmpeg_command(
        [
            FFMPEG_PATH,
            "-v",
            "error",
            "-i",
            input_path,
            "-f",
            "null",
            "-"
        ]
    )

    command_output = (
        (result.stdout or "") +
        "\n" +
        (result.stderr or "")
    ).strip()

    if result.returncode != 0:
        logger.error(f"音频文件无效或已损坏: {input_path}")

        if command_output:
            logger.error(f"音频校验失败输出: {command_output}")

        return False

    return True


def _make_task_temp_output_path(output_path: str) -> str:
    final_path = Path(output_path)
    for _ in range(8):
        candidate = final_path.with_name(
            f".{final_path.stem}.{uuid.uuid4().hex}.qonic_tmp{final_path.suffix}"
        )
        if not candidate.exists():
            return str(candidate)
    raise RuntimeError("无法生成唯一临时输出路径")


def _publish_task_temp_output(temp_path: str, output_path: str) -> dict[str, object]:
    result = publish_no_clobber(Path(temp_path), Path(output_path))
    if not result.get("success"):
        raise RuntimeError(str(result.get("message") or "安全发布输出失败"))
    return result


def _cleanup_owned_task_temp_output(temp_path: str) -> None:
    candidate = Path(str(temp_path or ""))
    if ".qonic_tmp" not in candidate.name or not candidate.is_file():
        return
    try:
        identity = (candidate.stat().st_dev, candidate.stat().st_ino)
        if (candidate.stat().st_dev, candidate.stat().st_ino) == identity:
            candidate.unlink()
    except OSError as exc:
        logger.warning("批量转换临时文件清理失败: %s - %s", candidate, exc)


def convert_audio(
    input_path,
    target_format="flac",
    output_root_override=None,
    create_format_subfolder=None,
    preserve_source=True,
    original_source_path=None,
    lyrics_source_paths=None,
    cancel_event: threading.Event | None = None,
    safe_publish: bool = False,
):
    temp_output_path = ""
    try:
        logger.info(f"开始处理文件: {input_path}")

        if not input_path:
            raise ValueError("输入文件路径为空")

        if not os.path.isfile(input_path):
            raise FileNotFoundError(
                f"输入文件不存在: {input_path}"
            )

        if cancel_event is not None and cancel_event.is_set():
            raise ConversionCancelled("用户已取消当前转换任务")

        if not _validate_audio_file(input_path):
            return {
                "success": False,
                "output_path": None,
                "error": "音频文件无效或已损坏",
            }

        output_root = output_root_override or get_output_folder()

        if not output_root:
            raise ValueError("输出目录为空")

        target_format = normalize_target_format(
            target_format,
            DEFAULT_TARGET_FORMAT,
        )
        if create_format_subfolder is None:
            create_format_subfolder = get_create_format_subfolder()

        # 获取源文件格式
        source_ext = normalize_extension(input_path).lstrip(".")
        target_extension = get_target_extension(target_format)
        target_ext = target_extension.lstrip(".")
        ffmpeg_args = get_ffmpeg_args_for_target(target_format)

        output_path = build_output_path(
            input_path,
            target_format,
            output_root,
            create_format_subfolder,
        )

        logger.info(f"当前输出根目录: {output_root}")
        logger.info(
            "按目标格式创建子文件夹: "
            f"{'开启' if create_format_subfolder else '关闭'}"
        )
        logger.info(f"输出路径: {output_path}")
        temp_output_path = (
            _make_task_temp_output_path(output_path) if safe_publish else output_path
        )

        # =========================
        # 相同格式：复制并保留源文件
        # =========================
        if source_ext == target_ext:
            shutil.copy2(input_path, temp_output_path)
            _ensure_output_created(temp_output_path)
            if safe_publish:
                _publish_task_temp_output(temp_output_path, output_path)
            _ensure_output_created(output_path)

            logger.info(
                f"源格式与目标格式相同，已复制到输出目录: {output_path}"
            )

        # =========================
        # 不同格式：FFmpeg 转码
        # =========================
        else:
            command = [
                FFMPEG_PATH,
                "-n",
                "-i",
                input_path,
                *ffmpeg_args,
                temp_output_path,
            ]
            result = (
                _run_ffmpeg_command(command, cancel_event=cancel_event)
                if cancel_event is not None
                else _run_ffmpeg_command(command)
            )

            command_output = (
                (result.stdout or "") +
                "\n" +
                (result.stderr or "")
            ).strip()

            if result.returncode != 0:
                if cancel_event is not None and cancel_event.is_set():
                    raise ConversionCancelled("用户已取消当前转换任务")
                if command_output:
                    logger.error(f"FFmpeg 转码失败输出: {command_output}")

                raise RuntimeError(
                    f"FFmpeg 转码失败，退出码: {result.returncode}"
                )

            if safe_publish:
                _ensure_output_created(temp_output_path)
                _publish_task_temp_output(temp_output_path, output_path)
            else:
                _ensure_output_created(output_path)
            _ensure_output_created(output_path)

            logger.info(
                f"FFmpeg 转码完成: {output_path}"
            )

        lyrics_summary = None
        lyrics_source_path = original_source_path or input_path
        extra_lyrics_sources = []

        if lyrics_source_paths:
            extra_lyrics_sources.extend(lyrics_source_paths)

        extra_lyrics_sources.append(input_path)

        try:
            lyrics_summary = process_lyrics_for_output(
                source_path=lyrics_source_path,
                output_audio_path=output_path,
                extra_source_paths=extra_lyrics_sources,
                embed=get_embed_lyrics_after_convert(),
                copy_external=get_copy_lrc_to_output(),
                overwrite=get_overwrite_existing_lyrics(),
            )
        except Exception as e:
            logger.warning(
                f"歌词处理失败，但音频转换已完成: {e}",
                exc_info=True,
            )

        logger.info(f"转换完成: {output_path}")
        return {
            "success": True,
            "output_path": output_path,
            "lyrics": lyrics_summary,
        }

    except ConversionCancelled as e:
        if safe_publish:
            _cleanup_owned_task_temp_output(temp_output_path)
        logger.info("转换已取消: %s", e)
        return {
            "success": False,
            "cancelled": True,
            "output_path": None,
            "error": str(e),
        }
    except Exception as e:
        if safe_publish:
            _cleanup_owned_task_temp_output(temp_output_path)
        logger.error(f"转换失败: {e}")
        return {
            "success": False,
            "output_path": None,
            "error": str(e),
        }
