"""Isolated, cancellable FFmpeg Rubber Band pitch processing.

The service owns only one FFmpeg child at a time.  Both child pipes are drained
continuously so a verbose real-media render cannot deadlock before ``wait``.
"""
from __future__ import annotations

from collections import deque
import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable

from single_file_convert import FFMPEG_PATH


def _hidden_subprocess_kwargs() -> dict:
    if os.name != "nt":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
    return {"startupinfo": startupinfo, "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}


class AudioProcessingService:
    """Runs a duration-preserving Rubber Band render into an owned temp path."""

    progress_stall_seconds = 60.0
    hard_timeout_minimum_seconds = 120.0
    hard_timeout_duration_multiplier = 4.0
    probe_timeout_seconds = 20.0
    cancel_grace_seconds = 3.0
    preview_algorithm_version = "rubberband-quality-v1"
    preview_encoding_version = "pcm-wav-v1"

    def __init__(self, ffmpeg_path: str = FFMPEG_PATH) -> None:
        self.ffmpeg_path = str(ffmpeg_path)
        self._process: subprocess.Popen | None = None
        self._process_lock = threading.Lock()
        self._cancel_requested = threading.Event()

    def cancel(self) -> None:
        """Request cancellation without blocking the UI thread."""
        self._cancel_requested.set()
        with self._process_lock:
            process = self._process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass

    @property
    def cancel_requested(self) -> bool:
        """Expose cooperative cancellation to the publish transaction."""
        return self._cancel_requested.is_set()

    def render_pitch_shift(
        self,
        source_path: str,
        temp_output_path: str,
        semitone: int,
        *,
        request_id: str = "",
        source_generation: int = 0,
        progress_callback: Callable[[dict], None] | None = None,
        preview: bool = False,
        source_probe: dict | None = None,
    ) -> dict:
        """Render a unique preview/export temp file and always reap FFmpeg.

        ``progress_callback`` is worker-thread only.  It receives sanitized
        diagnostic events; it never contains a user path, lyrics, tags or cover
        data.
        """
        self._cancel_requested.clear()
        source = Path(source_path).resolve()
        output = Path(temp_output_path).resolve()
        started_wall = time.time()
        started = time.perf_counter_ns()
        request_validation_started = started
        diagnostics = {
            "request_id": request_id,
            "source_generation": int(source_generation),
            "semitone": int(semitone),
            "started_at": started_wall,
            "stage": "validating_request",
            "last_progress_at": started_wall,
            "ffmpeg_pid": None,
            "returncode": None,
            "stderr_tail": [],
            "temp_output_exists": False,
            "temp_output_size": 0,
            "validation_started_at": None,
            "validation_finished_at": None,
            "cleanup_ok": None,
            "command_summary": [],
            "preview": bool(preview),
            "timings_ms": {},
        }

        def report(stage: str, **extra) -> None:
            diagnostics["stage"] = stage
            diagnostics.update(extra)
            if progress_callback is not None:
                try:
                    progress_callback({"stage": stage, **extra})
                except Exception:
                    # Observability must not be able to strand the renderer.
                    pass

        if not source.is_file():
            return self._failure("source_missing", "当前源音频不存在。", diagnostics=diagnostics)
        if not Path(self.ffmpeg_path).is_file():
            return self._failure("processing_start_failed", "FFmpeg 不存在，无法处理音频。", diagnostics=diagnostics)
        if not -12 <= int(semitone) <= 12:
            return self._failure("pitch_out_of_range", "半音参数必须在 -12 到 +12 之间。", diagnostics=diagnostics)
        if int(semitone) == 0:
            return self._failure("pitch_zero_no_processing", "0 半音无需生成处理缓存。", diagnostics=diagnostics)
        if output.exists():
            return self._failure("temp_path_conflict", "本次独占临时输出路径已存在。", diagnostics=diagnostics)
        diagnostics["timings_ms"]["request_validation"] = self._elapsed_ms(request_validation_started)

        report("preparing_workspace")
        workspace_started = time.perf_counter_ns()
        output.parent.mkdir(parents=True, exist_ok=True)
        diagnostics["timings_ms"]["workspace_prepare"] = self._elapsed_ms(workspace_started)
        source_probe_started = time.perf_counter_ns()
        before = dict(source_probe) if source_probe else self.probe(source)
        diagnostics["timings_ms"]["source_probe"] = self._elapsed_ms(source_probe_started)
        if not before.get("ok"):
            return self._failure("source_invalid", "无法读取源音频。", probe=before, diagnostics=diagnostics)

        ratio = 2 ** (int(semitone) / 12.0)
        command = self._build_command(source, output, ratio, preview=preview)
        diagnostics["command_summary"] = self._command_summary(command, source, output)
        stderr_tail: deque[str] = deque(maxlen=60)
        stdout_reader_error = ""
        stderr_reader_error = ""
        last_progress = time.monotonic()
        stalled_reported = False
        process: subprocess.Popen | None = None
        readers: list[threading.Thread] = []
        progress_values: dict[str, str] = {}

        def read_stdout(stream) -> None:
            nonlocal last_progress, stdout_reader_error
            try:
                for raw_line in iter(stream.readline, ""):
                    line = raw_line.strip()
                    if not line:
                        continue
                    last_progress = time.monotonic()
                    diagnostics["last_progress_at"] = time.time()
                    key, separator, value = line.partition("=")
                    if separator:
                        progress_values[key] = value
                    if separator and key == "progress":
                        processed_seconds = self._progress_seconds(progress_values)
                        progress_percent = self._progress_percent(processed_seconds, before.get("duration"))
                        report("rendering", progress_marker=value, processed_seconds=processed_seconds, progress_percent=progress_percent)
            except Exception as exc:  # exercised with a broken reader in tests
                stdout_reader_error = type(exc).__name__

        def read_stderr(stream) -> None:
            nonlocal stderr_reader_error
            try:
                for raw_line in iter(stream.readline, ""):
                    stderr_tail.append(raw_line.rstrip())
            except Exception as exc:  # keep worker completion independent of logs
                stderr_reader_error = type(exc).__name__

        try:
            report("starting_process")
            process_starting = time.perf_counter_ns()
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                **_hidden_subprocess_kwargs(),
            )
            diagnostics["ffmpeg_pid"] = process.pid
            with self._process_lock:
                self._process = process
            readers = [
                threading.Thread(target=read_stdout, args=(process.stdout,), name="pitch-stdout", daemon=True),
                threading.Thread(target=read_stderr, args=(process.stderr,), name="pitch-stderr", daemon=True),
            ]
            for reader in readers:
                reader.start()
            diagnostics["timings_ms"]["ffmpeg_start"] = self._elapsed_ms(process_starting)

            report("rendering")
            render_started = time.perf_counter_ns()
            hard_timeout = max(self.hard_timeout_minimum_seconds, float(before["duration"]) * self.hard_timeout_duration_multiplier)
            cancel_started: float | None = None
            timed_out = False
            while process.poll() is None:
                now = time.monotonic()
                if self._cancel_requested.is_set():
                    if cancel_started is None:
                        cancel_started = now
                        try:
                            process.terminate()
                        except OSError:
                            pass
                    elif now - cancel_started >= self.cancel_grace_seconds:
                        try:
                            process.kill()
                        except OSError:
                            pass
                elif (time.perf_counter_ns() - started) / 1_000_000_000 >= hard_timeout:
                    timed_out = True
                    report("waiting_process_exit", timeout_kind="hard", timeout_seconds=hard_timeout)
                    try:
                        process.terminate()
                    except OSError:
                        pass
                    self._cancel_requested.set()
                    cancel_started = now
                elif now - last_progress >= self.progress_stall_seconds and not stalled_reported:
                    stalled_reported = True
                    report("rendering", stalled=True, stalled_seconds=round(now - last_progress, 1))
                time.sleep(0.05)

            diagnostics["timings_ms"]["ffmpeg_render"] = self._elapsed_ms(render_started)
            report("waiting_process_exit")
            exit_wait_started = time.perf_counter_ns()
            diagnostics["returncode"] = process.wait(timeout=2.0)
            diagnostics["timings_ms"]["ffmpeg_exit_wait"] = self._elapsed_ms(exit_wait_started)
        except OSError as exc:
            return self._failure("processing_start_failed", f"处理进程启动失败：{exc}", diagnostics=diagnostics)
        except subprocess.TimeoutExpired:
            return self._failure("processing_exit_timeout", "FFmpeg 退出等待超时。", diagnostics=diagnostics)
        finally:
            if process is not None and process.poll() is None:
                self._terminate_and_reap(process)
            for stream in (getattr(process, "stdout", None), getattr(process, "stderr", None)):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        pass
            for reader in readers:
                reader.join(timeout=2.0)
            with self._process_lock:
                if self._process is process:
                    self._process = None
            diagnostics["stderr_tail"] = list(stderr_tail)
            diagnostics["stdout_reader_error"] = stdout_reader_error
            diagnostics["stderr_reader_error"] = stderr_reader_error

        diagnostics["temp_output_exists"] = output.is_file()
        diagnostics["temp_output_size"] = output.stat().st_size if output.is_file() else 0
        if self._cancel_requested.is_set():
            diagnostics["cleanup_ok"] = self.cleanup_owned(output)
            return self._failure("processing_timeout" if timed_out else "processing_cancelled", "处理超时，已终止 FFmpeg。" if timed_out else "处理已取消。", diagnostics=diagnostics)
        if process is None or process.returncode != 0:
            diagnostics["cleanup_ok"] = self.cleanup_owned(output)
            return self._failure("preview_render_failed", "FFmpeg Pitch Shift 处理失败。", stderr=self._tail_lines(stderr_tail), diagnostics=diagnostics)

        report("validating_preview")
        diagnostics["validation_started_at"] = time.time()
        output_probe_started = time.perf_counter_ns()
        after = self.probe(output)
        diagnostics["timings_ms"]["output_probe"] = self._elapsed_ms(output_probe_started)
        validation_started = time.perf_counter_ns()
        validation = self.validate_render(before, after)
        diagnostics["timings_ms"]["preview_validation"] = self._elapsed_ms(validation_started)
        diagnostics["validation_finished_at"] = time.time()
        if not validation["ok"]:
            diagnostics["cleanup_ok"] = self.cleanup_owned(output)
            return self._failure(validation["error_code"], validation["message"], probe=after, diagnostics=diagnostics)
        diagnostics["stage"] = "preview_ready"
        diagnostics["finished_at"] = time.time()
        diagnostics["timings_ms"]["total_to_preview_ready"] = self._elapsed_ms(started)
        return {
            "success": True,
            "output_path": str(output),
            "semitone": int(semitone),
            "ratio": ratio,
            "source_probe": before,
            "output_probe": after,
            "command_uses_rubberband": True,
            "diagnostics": diagnostics,
        }

    def _build_command(self, source: Path, output: Path, ratio: float, *, preview: bool = False) -> list[str]:
        command = [self.ffmpeg_path, "-nostdin", "-nostats", "-stats_period", "0.5", "-progress", "pipe:1", "-n", "-i", str(source), "-map", "0:a:0?"]
        if preview:
            # Preview is an isolated, disposable playback cache.  Do not pay
            # Export's metadata/cover/lyrics stream-copy cost here.
            command += ["-map_metadata", "-1", "-map_chapters", "-1"]
        else:
            command += ["-map", "0:v?", "-map", "0:s?", "-map", "0:d?", "-map_metadata", "0", "-map_chapters", "0"]
        return command + ["-filter:a", f"rubberband=tempo=1:pitch={ratio:.12f}", *self._audio_encoding_args(output), "-c:v", "copy", "-c:s", "copy", "-c:d", "copy", str(output)]

    @staticmethod
    def _audio_encoding_args(output: Path) -> list[str]:
        suffix = output.suffix.lower()
        codecs = {
            ".wav": ["-c:a", "pcm_s16le"], ".flac": ["-c:a", "flac"], ".mp3": ["-c:a", "libmp3lame", "-q:a", "2"],
            ".m4a": ["-c:a", "aac", "-b:a", "192k"], ".aac": ["-c:a", "aac", "-b:a", "192k"],
            ".ogg": ["-c:a", "libvorbis", "-q:a", "5"], ".opus": ["-c:a", "libopus", "-b:a", "160k"],
        }
        return codecs.get(suffix, ["-c:a", "flac"])

    @staticmethod
    def _command_summary(command: list[str], source: Path, output: Path) -> list[str]:
        return ["<ffmpeg>" if value == command[0] else "<source>" if value == str(source) else "<temp-output>" if value == str(output) else value for value in command]

    @staticmethod
    def _elapsed_ms(started_ns: int) -> float:
        return round((time.perf_counter_ns() - started_ns) / 1_000_000, 3)

    @staticmethod
    def _progress_seconds(values: dict[str, str]) -> float | None:
        for key in ("out_time_us", "out_time_ms"):
            try:
                return round(int(values[key]) / 1_000_000, 3)
            except (KeyError, TypeError, ValueError):
                pass
        return None

    @staticmethod
    def _progress_percent(processed_seconds: float | None, duration: object) -> float | None:
        try:
            return round(max(0.0, min(99.0, float(processed_seconds) / float(duration) * 100)), 1) if processed_seconds is not None and float(duration) > 0 else None
        except (TypeError, ValueError):
            return None

    def _terminate_and_reap(self, process: subprocess.Popen) -> None:
        try:
            process.terminate()
            process.wait(timeout=self.cancel_grace_seconds)
            return
        except (OSError, subprocess.TimeoutExpired):
            pass
        try:
            process.kill()
            process.wait(timeout=2.0)
        except (OSError, subprocess.TimeoutExpired):
            pass

    def probe(self, path: Path) -> dict:
        ffprobe = str(Path(self.ffmpeg_path).with_name("ffprobe.exe"))
        if not Path(ffprobe).is_file() or not path.is_file():
            return {"ok": False, "error": "ffprobe 或音频文件不存在"}
        command = [ffprobe, "-v", "error", "-show_entries", "format=duration,size,format_name", "-show_entries", "stream=codec_type,channels,sample_rate", "-of", "json", str(path)]
        try:
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=self.probe_timeout_seconds, **_hidden_subprocess_kwargs())
            data = json.loads(result.stdout or "{}") if result.returncode == 0 else {}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "ffprobe 超时"}
        except (OSError, json.JSONDecodeError):
            data = {}
        audio = next((item for item in data.get("streams", []) if item.get("codec_type") == "audio"), {})
        fmt = data.get("format", {})
        try:
            duration = float(fmt.get("duration"))
        except (TypeError, ValueError):
            duration = 0.0
        return {"ok": bool(duration > 0 and audio), "duration": duration, "channels": int(audio.get("channels") or 0), "sample_rate": int(audio.get("sample_rate") or 0), "size": int(fmt.get("size") or 0), "format": str(fmt.get("format_name") or "")}

    @staticmethod
    def validate_render(source: dict, output: dict) -> dict:
        if not output.get("ok") or output.get("size", 0) <= 0:
            return {"ok": False, "error_code": "processed_audio_invalid", "message": "处理结果不可读取或为空。"}
        tolerance = max(0.1, float(source["duration"]) * 0.005)
        if abs(float(output["duration"]) - float(source["duration"])) > tolerance:
            return {"ok": False, "error_code": "duration_mismatch", "message": "处理结果时长超出允许误差。"}
        if source.get("channels") and output.get("channels") != source.get("channels"):
            return {"ok": False, "error_code": "processed_audio_invalid", "message": "处理结果声道数不一致。"}
        return {"ok": True}

    @staticmethod
    def cleanup_owned(path: Path) -> bool:
        try:
            if path.exists():
                path.unlink()
            return True
        except OSError:
            return False

    @staticmethod
    def _tail_lines(lines) -> str:
        return "\n".join(list(lines)[-12:])

    @staticmethod
    def _failure(error_code: str, message: str, **extra) -> dict:
        return {"success": False, "error_code": error_code, "message": message, **extra}
