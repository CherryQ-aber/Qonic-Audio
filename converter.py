# 音频转换模块
import os
import shutil
import subprocess

from config import FFMPEG_PATH, get_output_folder
from logger import logger

logger.info(f"FFmpeg路径: {FFMPEG_PATH}")
logger.info(
    f"FFmpeg就绪状态: {os.path.exists(FFMPEG_PATH)}"
)
logger.info("当前 converter.py 已加载")


def _ensure_output_created(output_path):
    if not os.path.exists(output_path):
        raise FileNotFoundError(
            f"输出文件不存在: {output_path}"
        )


def _get_available_output_path(format_folder, filename, target_format):
    output_path = os.path.join(
        format_folder,
        f"{filename}.{target_format}"
    )

    if not os.path.exists(output_path):
        return output_path

    suffix = 1

    while True:
        candidate = os.path.join(
            format_folder,
            f"{filename} ({suffix}).{target_format}"
        )

        if not os.path.exists(candidate):
            return candidate

        suffix += 1


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


def _run_ffmpeg_command(command):
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        **_get_hidden_subprocess_kwargs()
    )

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


def convert_audio(
    input_path,
    target_format="flac"
):
    try:
        logger.info(f"开始处理文件: {input_path}")

        if not input_path:
            raise ValueError("输入文件路径为空")

        if not os.path.isfile(input_path):
            raise FileNotFoundError(
                f"输入文件不存在: {input_path}"
            )

        if not _validate_audio_file(input_path):
            return False

        output_root = get_output_folder()

        if not output_root:
            raise ValueError("输出目录为空")

        # 获取文件名（不含后缀）
        filename = os.path.splitext(
            os.path.basename(input_path)
        )[0]

        # 获取源文件格式
        source_ext = os.path.splitext(
            input_path
        )[1].replace(".", "").lower()

        # 创建输出目录
        format_folder = os.path.join(
            output_root,
            target_format.upper()
        )

        os.makedirs(format_folder, exist_ok=True)

        # 使用不覆盖的输出路径，避免误删已有转换结果。
        output_path = _get_available_output_path(
            format_folder,
            filename,
            target_format
        )

        logger.info(f"输出路径: {output_path}")

        # =========================
        # 相同格式：复制并保留源文件
        # =========================
        if source_ext == target_format.lower():
            shutil.copy2(
                input_path,
                output_path
            )

            _ensure_output_created(output_path)

            logger.info(
                f"文件已直接复制: {output_path}"
            )

        # =========================
        # 不同格式：FFmpeg 转码
        # =========================
        else:
            result = _run_ffmpeg_command(
                [
                    FFMPEG_PATH,
                    "-n",
                    "-i",
                    input_path,
                    output_path
                ]
            )

            command_output = (
                (result.stdout or "") +
                "\n" +
                (result.stderr or "")
            ).strip()

            if result.returncode != 0:
                if command_output:
                    logger.error(f"FFmpeg 转码失败输出: {command_output}")

                raise RuntimeError(
                    f"FFmpeg 转码失败，退出码: {result.returncode}"
                )

            _ensure_output_created(output_path)

            logger.info(
                f"FFmpeg 转码完成: {output_path}"
            )

        logger.info(f"转换完成: {output_path}")
        return True

    except Exception as e:
        logger.error(f"转换失败: {e}")
        return False
