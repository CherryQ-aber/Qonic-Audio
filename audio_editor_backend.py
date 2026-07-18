import os
import re
import subprocess

from config import FFMPEG_PATH, get_output_folder
from metadata import copy_audio_cover


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


def _ensure_audio_editor_output_created(output_path):
    if not os.path.exists(output_path):
        raise FileNotFoundError(f"输出文件不存在: {output_path}")

    if os.path.getsize(output_path) <= 0:
        raise ValueError(f"输出文件为空: {output_path}")


def _format_duration(raw_duration):
    if not raw_duration:
        return "未知"

    return raw_duration.split(".")[0]


def _parse_audio_stream_info(ffmpeg_output):
    stream_match = re.search(r"Audio:\s*([^\n\r]+)", ffmpeg_output)

    if not stream_match:
        return {
            "codec": "未知",
            "sample_rate": "未知",
            "sample_rate_hz": None,
            "channels": "未知",
        }

    stream_text = stream_match.group(1)
    parts = [part.strip() for part in stream_text.split(",")]
    codec = parts[0] if parts else "未知"

    sample_rate_hz = None
    sample_rate = "未知"
    sample_rate_match = re.search(r"(\d+)\s*Hz", stream_text)

    if sample_rate_match:
        sample_rate_hz = int(sample_rate_match.group(1))
        sample_rate = f"{sample_rate_hz} Hz"

    channels = "未知"

    for part in parts:
        normalized = part.lower()

        if normalized in ("mono", "stereo"):
            channels = part
            break

        channel_match = re.search(r"(\d+)\s*channels?", normalized)

        if channel_match:
            channels = f"{channel_match.group(1)} channels"
            break

    return {
        "codec": codec,
        "sample_rate": sample_rate,
        "sample_rate_hz": sample_rate_hz,
        "channels": channels,
    }


def read_audio_info(input_path):
    try:
        if not input_path:
            raise ValueError("输入文件路径为空")

        if not os.path.isfile(input_path):
            raise FileNotFoundError(f"输入文件不存在: {input_path}")

        if not os.path.isfile(FFMPEG_PATH):
            raise FileNotFoundError(f"FFmpeg不存在: {FFMPEG_PATH}")

        result = _run_ffmpeg_command([
            FFMPEG_PATH,
            "-hide_banner",
            "-i",
            input_path,
        ])

        ffmpeg_output = "\n".join(
            part for part in (result.stdout, result.stderr) if part
        )

        duration_match = re.search(
            r"Duration:\s*(\d{2}:\d{2}:\d{2}(?:\.\d+)?)",
            ffmpeg_output,
        )
        stream_info = _parse_audio_stream_info(ffmpeg_output)
        extension = os.path.splitext(input_path)[1].lstrip(".").upper() or "未知"

        if stream_info["codec"] == "未知" and not duration_match:
            raise RuntimeError("未能从 FFmpeg 输出中读取音频信息")

        return {
            "success": True,
            "input_path": input_path,
            "file_name": os.path.basename(input_path),
            "format": extension,
            "duration": _format_duration(
                duration_match.group(1) if duration_match else None
            ),
            "sample_rate": stream_info["sample_rate"],
            "sample_rate_hz": stream_info["sample_rate_hz"],
            "channels": stream_info["channels"],
            "codec": stream_info["codec"],
            "message": "音频信息读取完成",
        }

    except Exception as e:
        return {
            "success": False,
            "input_path": input_path,
            "file_name": os.path.basename(input_path) if input_path else "-",
            "format": os.path.splitext(input_path)[1].lstrip(".").upper()
            if input_path else "-",
            "duration": "读取失败",
            "sample_rate": "读取失败",
            "sample_rate_hz": None,
            "channels": "读取失败",
            "codec": "读取失败",
            "message": str(e),
        }


def _calculate_pitch_ratio(semitones=0, cents=0):
    return 2 ** ((semitones + cents / 100) / 12)


def _build_atempo_chain(factor):
    if factor <= 0:
        raise ValueError("atempo 参数必须大于 0")

    chain = []
    remaining = float(factor)

    while remaining < 0.5:
        chain.append(0.5)
        remaining /= 0.5

    while remaining > 2.0:
        chain.append(2.0)
        remaining /= 2.0

    chain.append(remaining)
    return chain


def _build_pitch_filter(ratio, sample_rate_hz, keep_tempo=True):
    sample_rate = sample_rate_hz or 44100
    filters = [
        f"asetrate={sample_rate}*{ratio:.10f}",
        f"aresample={sample_rate}",
    ]

    if keep_tempo:
        filters.extend(
            f"atempo={value:.10f}"
            for value in _build_atempo_chain(1 / ratio)
        )

    return ",".join(filters)


def _format_pitch_label(semitones=0, cents=0):
    shift = semitones + cents / 100
    return f"{shift:+.2f}"


def _get_available_output_path(output_folder, file_stem, pitch_label, output_format):
    output_path = os.path.join(
        output_folder,
        f"{file_stem} [Pitch {pitch_label}].{output_format}"
    )

    if not os.path.exists(output_path):
        return output_path

    suffix = 1

    while True:
        candidate = os.path.join(
            output_folder,
            f"{file_stem} [Pitch {pitch_label}] ({suffix}).{output_format}"
        )

        if not os.path.exists(candidate):
            return candidate

        suffix += 1


def process_pitch_shift(input_path, output_path, semitones, preserve_metadata=True):
    try:
        if not input_path:
            raise ValueError("输入文件路径为空")

        if not output_path:
            raise ValueError("输出文件路径为空")

        if not os.path.isfile(input_path):
            raise FileNotFoundError(f"输入文件不存在: {input_path}")

        if not os.path.isfile(FFMPEG_PATH):
            raise FileNotFoundError(f"FFmpeg不存在: {FFMPEG_PATH}")

        output_folder = os.path.dirname(os.path.abspath(output_path))

        if output_folder:
            os.makedirs(output_folder, exist_ok=True)

        semitones = int(semitones)
        ratio = _calculate_pitch_ratio(semitones, 0)
        audio_info = read_audio_info(input_path)
        sample_rate_hz = audio_info.get("sample_rate_hz") if audio_info else None
        filter_graph = _build_pitch_filter(ratio, sample_rate_hz, keep_tempo=True)
        command = [
            FFMPEG_PATH,
            "-y",
            "-i",
            input_path,
            "-vn",
        ]

        if preserve_metadata:
            command.extend(["-map_metadata", "0"])

        command.extend([
            "-filter:a",
            filter_graph,
            output_path,
        ])

        result = _run_ffmpeg_command(command)
        command_output = "\n".join(
            part for part in (result.stdout, result.stderr) if part
        ).strip()

        if result.returncode != 0:
            detail = command_output or f"退出码: {result.returncode}"
            raise RuntimeError(f"FFmpeg 升降调导出失败: {detail}")

        _ensure_audio_editor_output_created(output_path)

        warnings = []
        cover_result = copy_audio_cover(input_path, output_path)
        cover_copied = bool(cover_result.get("copied"))

        if not cover_result.get("success"):
            warnings.append(
                f"音频处理完成，但封面复制失败：{cover_result.get('error') or '未知错误'}"
            )

        return {
            "success": True,
            "output_path": output_path,
            "error": None,
            "message": "升降调处理完成",
            "cover_copied": cover_copied,
            "metadata_copied": preserve_metadata,
            "warnings": warnings,
        }

    except Exception as e:
        if output_path and os.path.exists(output_path):
            try:
                if os.path.getsize(output_path) <= 0:
                    os.remove(output_path)
            except OSError:
                pass

        return {
            "success": False,
            "output_path": None,
            "error": str(e),
            "message": str(e),
        }


def export_pitch_shift(
    input_path,
    semitones=0,
    cents=0,
    keep_tempo=True,
    output_format=None,
):
    try:
        if not input_path:
            raise ValueError("输入文件路径为空")

        if not os.path.isfile(input_path):
            raise FileNotFoundError(f"输入文件不存在: {input_path}")

        if not os.path.isfile(FFMPEG_PATH):
            raise FileNotFoundError(f"FFmpeg不存在: {FFMPEG_PATH}")

        source_stem, source_ext = os.path.splitext(os.path.basename(input_path))
        selected_format = (output_format or source_ext.lstrip(".") or "wav").lower()
        output_folder = os.path.join(get_output_folder(), "Edited")
        os.makedirs(output_folder, exist_ok=True)

        ratio = _calculate_pitch_ratio(semitones, cents)
        pitch_label = _format_pitch_label(semitones, cents)
        output_path = _get_available_output_path(
            output_folder,
            source_stem,
            pitch_label,
            selected_format,
        )
        audio_info = read_audio_info(input_path)
        sample_rate_hz = audio_info.get("sample_rate_hz") if audio_info else None
        filter_graph = _build_pitch_filter(
            ratio,
            sample_rate_hz,
            keep_tempo=keep_tempo,
        )

        result = _run_ffmpeg_command([
            FFMPEG_PATH,
            "-n",
            "-i",
            input_path,
            "-vn",
            "-filter:a",
            filter_graph,
            output_path,
        ])

        command_output = "\n".join(
            part for part in (result.stdout, result.stderr) if part
        ).strip()

        if result.returncode != 0:
            detail = command_output or f"退出码: {result.returncode}"
            raise RuntimeError(f"FFmpeg 升降调导出失败: {detail}")

        _ensure_audio_editor_output_created(output_path)

        return {
            "success": True,
            "output_path": output_path,
            "message": "导出完成",
        }

    except Exception as e:
        return {
            "success": False,
            "output_path": None,
            "message": str(e),
        }
