import array
import io
import subprocess
import wave
from pathlib import Path

import pytest

from single_file_convert import FFMPEG_PATH
from ui_next.bridge import audio_processing_service as processing_module
from ui_next.bridge.audio_processing_service import AudioProcessingService


def _tone(path: Path, frequency: int = 440) -> None:
    subprocess.run([FFMPEG_PATH, "-nostdin", "-f", "lavfi", "-i", f"sine=frequency={frequency}:duration=1", "-c:a", "pcm_s16le", str(path)], check=True, capture_output=True)


def _dominant_frequency_from_zero_crossings(path: Path) -> float:
    with wave.open(str(path), "rb") as media:
        assert media.getnchannels() == 1 and media.getsampwidth() == 2
        sample_rate = media.getframerate()
        values = array.array("h", media.readframes(media.getnframes()))
    start, end = sample_rate // 4, min(len(values), sample_rate * 3 // 4)
    segment = values[start:end]
    crossings = sum(1 for left, right in zip(segment, segment[1:]) if left <= 0 < right)
    return crossings * sample_rate / max(1, len(segment))


def test_rubberband_preview_is_readable_and_duration_preserving(tmp_path):
    source, output = tmp_path / "tone.wav", tmp_path / "preview.wav"
    _tone(source)
    result = AudioProcessingService().render_pitch_shift(str(source), str(output), 12)
    assert result["success"], result
    assert result["command_uses_rubberband"] is True
    assert output.parent == tmp_path
    assert abs(result["output_probe"]["duration"] - result["source_probe"]["duration"]) <= 0.1
    assert result["output_probe"]["channels"] == result["source_probe"]["channels"]


def test_pitch_processing_rejects_zero_and_out_of_range(tmp_path):
    source = tmp_path / "tone.wav"
    _tone(source)
    service = AudioProcessingService()
    assert service.render_pitch_shift(str(source), str(tmp_path / "zero.wav"), 0)["error_code"] == "pitch_zero_no_processing"
    assert service.render_pitch_shift(str(source), str(tmp_path / "bad.wav"), 13)["error_code"] == "pitch_out_of_range"


def test_rubberband_changes_pitch_without_using_playback_speed(tmp_path):
    source = tmp_path / "source.wav"
    subprocess.run([FFMPEG_PATH, "-nostdin", "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-c:a", "pcm_s16le", str(source)], check=True, capture_output=True)
    service = AudioProcessingService()
    up, down = tmp_path / "up.wav", tmp_path / "down.wav"
    assert service.render_pitch_shift(str(source), str(up), 12)["success"]
    assert service.render_pitch_shift(str(source), str(down), -12)["success"]
    assert abs(_dominant_frequency_from_zero_crossings(up) - 880) < 15
    assert abs(_dominant_frequency_from_zero_crossings(down) - 220) < 15


class _FakeProcess:
    def __init__(self, command, *, stdout="", stderr="", returncode=0, write_output=True):
        self.command = command; self.pid = 4242; self.returncode = returncode
        self.stdout = io.StringIO(stdout); self.stderr = io.StringIO(stderr)
        if write_output:
            Path(command[-1]).write_bytes(b"processed")

    def poll(self): return self.returncode
    def wait(self, timeout=None): return self.returncode
    def terminate(self): self.returncode = -15
    def kill(self): self.returncode = -9


def _mockable_service(tmp_path):
    executable = tmp_path / "ffmpeg.exe"; executable.write_bytes(b"stub")
    service = AudioProcessingService(str(executable))
    service.probe = lambda path: {"ok": True, "duration": 1.0, "channels": 1, "sample_rate": 44100, "size": 9, "format": "wav"}
    return service, tmp_path / "source.wav", tmp_path / "preview.wav"


def test_large_stderr_is_drained_and_normal_exit_does_not_require_progress_end(tmp_path, monkeypatch):
    service, source, output = _mockable_service(tmp_path); source.write_bytes(b"source")
    process = _FakeProcess([], stdout="out_time_ms=100\n", stderr=("verbose ffmpeg line\n" * 100_000), write_output=False)
    def fake_popen(command, **_kwargs):
        process.command = command; Path(command[-1]).write_bytes(b"processed"); return process
    monkeypatch.setattr(processing_module.subprocess, "Popen", fake_popen)
    result = service.render_pitch_shift(str(source), str(output), 1, request_id="request-a", source_generation=7)
    assert result["success"], result
    diagnostics = result["diagnostics"]
    assert diagnostics["request_id"] == "request-a" and diagnostics["source_generation"] == 7
    assert diagnostics["returncode"] == 0 and len(diagnostics["stderr_tail"]) <= 60
    assert "-nostdin" in diagnostics["command_summary"] and "-progress" in diagnostics["command_summary"]
    assert "<source>" in diagnostics["command_summary"] and "<temp-output>" in diagnostics["command_summary"]


def test_start_failure_and_callback_failure_always_return_terminal_result(tmp_path, monkeypatch):
    service, source, output = _mockable_service(tmp_path); source.write_bytes(b"source")
    monkeypatch.setattr(processing_module.subprocess, "Popen", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("blocked")))
    result = service.render_pitch_shift(str(source), str(output), 1, progress_callback=lambda _event: (_ for _ in ()).throw(RuntimeError("observer")))
    assert result["success"] is False and result["error_code"] == "processing_start_failed"


def test_cancel_terminates_child_and_cleans_partial_preview(tmp_path, monkeypatch):
    service, source, output = _mockable_service(tmp_path); source.write_bytes(b"source")
    process = _FakeProcess([], stdout="", stderr="", write_output=False)
    process.returncode = None
    def fake_popen(command, **_kwargs):
        process.command = command; Path(command[-1]).write_bytes(b"partial"); return process
    monkeypatch.setattr(processing_module.subprocess, "Popen", fake_popen)
    result = service.render_pitch_shift(str(source), str(output), 1, progress_callback=lambda event: service.cancel() if event["stage"] == "rendering" else None)
    assert result["success"] is False and result["error_code"] == "processing_cancelled"
    assert process.returncode == -15 and not output.exists()


def test_preview_command_is_audio_only_and_reports_monotonic_stage_timings(tmp_path):
    source, output = tmp_path / "source.wav", tmp_path / "preview.wav"
    _tone(source)
    service = AudioProcessingService()
    ratio = 2 ** (1 / 12)
    preview_command = service._build_command(source, output.with_suffix(".wav"), ratio, preview=True)
    export_command = service._build_command(source, output, ratio, preview=False)
    assert "0:v?" not in preview_command and preview_command[preview_command.index("-map_metadata") + 1] == "-1"
    assert "0:v?" in export_command and export_command[export_command.index("-map_metadata") + 1] == "0"

    result = service.render_pitch_shift(str(source), str(output), 1, preview=True)
    assert result["success"], result
    timings = result["diagnostics"]["timings_ms"]
    for key in ("request_validation", "workspace_prepare", "source_probe", "ffmpeg_start", "ffmpeg_render", "output_probe", "preview_validation", "total_to_preview_ready"):
        assert key in timings and timings[key] >= 0
