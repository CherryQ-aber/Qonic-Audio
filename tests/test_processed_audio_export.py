import base64
import hashlib
import subprocess
from pathlib import Path

from single_file_convert import FFMPEG_PATH
from ui_next.bridge.processed_audio_export_service import ProcessedAudioExportService
from mutagen.flac import FLAC, Picture


def _tone(path):
    subprocess.run([FFMPEG_PATH, "-nostdin", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:a", "pcm_s16le", str(path)], check=True, capture_output=True)


def _sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def test_export_is_new_same_extension_and_keeps_source_unchanged(tmp_path):
    source, output = tmp_path / "source.wav", tmp_path / "source [Pitch +1].wav"
    _tone(source); before = _sha(source)
    result = ProcessedAudioExportService().export(str(source), str(output), 1)
    assert result["success"], result
    assert output.is_file() and _sha(source) == before


def test_export_refuses_existing_same_and_different_extension(tmp_path):
    source, exists = tmp_path / "source.wav", tmp_path / "exists.wav"
    _tone(source); exists.write_bytes(b"keep")
    service = ProcessedAudioExportService()
    assert service.export(str(source), str(source), 1)["error_code"] == "output_same_as_source"
    assert service.export(str(source), str(exists), 1)["error_code"] == "output_exists"
    assert service.export(str(source), str(tmp_path / "wrong.flac"), 1)["error_code"] == "output_extension_mismatch"
    assert exists.read_bytes() == b"keep"


def test_flac_export_preserves_disk_tags_lyrics_and_cover(tmp_path):
    source, output = tmp_path / "source.flac", tmp_path / "pitch.flac"
    subprocess.run([FFMPEG_PATH, "-nostdin", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:a", "flac", str(source)], check=True, capture_output=True)
    media = FLAC(source)
    media["TITLE"] = "Source title"; media["ARTIST"] = "Source artist"; media["LYRICS"] = "Saved lyrics"
    cover = Picture(); cover.type = 3; cover.mime = "image/png"; cover.data = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9JmK4AAAAASUVORK5CYII="); cover.width = cover.height = 1; cover.depth = 24
    media.add_picture(cover); media.save()
    result = ProcessedAudioExportService().export(str(source), str(output), 1)
    assert result["success"], result
    assert result["output_path"] == str(output.resolve())
    processed = FLAC(output)
    assert processed["TITLE"] == ["Source title"] and processed["LYRICS"] == ["Saved lyrics"]
    assert len(processed.pictures) == 1


class _CancelledAfterRenderService:
    cancel_requested = True

    def render_pitch_shift(self, _source, output, _semitone):
        Path(output).write_bytes(b"temporary pitch output")
        return {"success": True, "output_path": output}

    def cleanup_owned(self, path):
        Path(path).unlink(missing_ok=True)
        return True


def test_pitch_cancel_after_render_does_not_publish_formal_output(tmp_path):
    source = tmp_path / "source.wav"
    output = tmp_path / "pitch.wav"
    source.write_bytes(b"source")

    result = ProcessedAudioExportService(
        _CancelledAfterRenderService()
    ).export(str(source), str(output), 1)

    assert not result["success"]
    assert result["error_code"] == "processing_cancelled"
    assert not output.exists()
    assert not list(tmp_path.glob(".*.pitch-*"))
