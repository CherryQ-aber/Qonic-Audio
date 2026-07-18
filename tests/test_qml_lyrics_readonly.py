import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

import lyrics
from ui_next.bridge.capabilities import LYRICS_READ, CapabilityGate
from ui_next.bridge.lyrics_viewmodel import LyricsViewModel


class LyricsReadOnlyBackendTests(unittest.TestCase):
    def test_embedded_mp3_uslt_is_read_without_save_or_cover_data(self):
        class FakeUSLT:
            FrameID = "USLT"
            text = "[00:01.00]line one\n[00:02.00]line two"

            def save(self, *_args, **_kwargs):
                raise AssertionError("mutagen save must not be called")

        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "sample.mp3"
            original = b"readonly-audio-placeholder"
            audio_path.write_bytes(original)
            before_hash = hashlib.sha256(original).hexdigest()

            with patch(
                "lyrics.ID3",
                return_value={"USLT::und": FakeUSLT()},
            ):
                result = lyrics.read_embedded_lyrics(str(audio_path))

            self.assertTrue(result["ok"])
            self.assertTrue(result["has_lyrics"])
            self.assertEqual(result["source"], "embedded")
            self.assertEqual(result["line_count"], 2)
            self.assertTrue(result["has_timestamps"])
            self.assertEqual(result["detected_fields"], ["USLT"])
            self.assertNotIn("cover", result)
            self.assertEqual(
                hashlib.sha256(audio_path.read_bytes()).hexdigest(),
                before_hash,
            )

    def test_mp3_sylt_is_detected_without_decoding_content(self):
        class FakeSYLT:
            FrameID = "SYLT"
            text = [(b"hidden", 1000)]

        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "sample.mp3"
            audio_path.write_bytes(b"placeholder")
            with patch(
                "lyrics.ID3",
                return_value={"SYLT::und": FakeSYLT()},
            ):
                result = lyrics.read_embedded_lyrics(str(audio_path))

        self.assertTrue(result["ok"])
        self.assertTrue(result["has_lyrics"])
        self.assertEqual(result["lyrics_text"], "")
        self.assertEqual(result["detected_fields"], ["SYLT"])

    def test_lrc_preview_detects_encoding_lines_and_timestamps(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lrc_path = Path(temp_dir) / "sample.LRC"
            text = "[00:01.00]第一行\n[00:02.50]第二行"
            lrc_path.write_bytes(text.encode("gbk"))
            before_hash = hashlib.sha256(lrc_path.read_bytes()).hexdigest()

            result = lyrics.read_lrc_file_preview(str(lrc_path))

            self.assertTrue(result["ok"])
            self.assertEqual(result["source"], "external_lrc_preview")
            self.assertEqual(result["lyrics_text"], text)
            self.assertEqual(result["line_count"], 2)
            self.assertTrue(result["has_timestamps"])
            self.assertEqual(result["encoding"], "gbk")
            self.assertTrue(result["is_memory_preview"])
            self.assertEqual(
                hashlib.sha256(lrc_path.read_bytes()).hexdigest(),
                before_hash,
            )


class LyricsViewModelReadOnlyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_preview_does_not_call_real_readers(self):
        view_model = LyricsViewModel()

        with (
            patch(
                "ui_next.bridge.lyrics_viewmodel.read_embedded_lyrics"
            ) as embedded_reader,
            patch(
                "ui_next.bridge.lyrics_viewmodel.read_lrc_file_preview"
            ) as lrc_reader,
        ):
            view_model.loadEmbeddedLyricsReadOnly("D:/Music/sample.mp3")
            view_model.loadLrcPreviewReadOnly("D:/Music/sample.lrc")

        embedded_reader.assert_not_called()
        lrc_reader.assert_not_called()
        self.assertTrue(view_model.previewMode)
        self.assertFalse(view_model.hasLyrics)
        self.assertEqual(
            view_model.statusMessage,
            "当前未启用 lyrics_read，只显示 Preview / Mock 信息。",
        )

    def test_enabled_embedded_lyrics_are_mapped_to_readonly_state(self):
        fake_result = {
            "ok": True,
            "has_lyrics": True,
            "lyrics_text": "[00:01.00]line one\nline two",
            "has_timestamps": True,
            "detected_fields": ["USLT"],
            "read_backend": "mutagen",
        }
        view_model = LyricsViewModel(CapabilityGate(LYRICS_READ))
        with patch(
            "ui_next.bridge.lyrics_viewmodel.read_embedded_lyrics",
            return_value=fake_result,
        ) as reader:
            view_model.loadEmbeddedLyricsReadOnly("D:/Music/sample.mp3")

        reader.assert_called_once_with("D:/Music/sample.mp3")
        self.assertFalse(view_model.previewMode)
        self.assertEqual(view_model.lyricsSource, "Embedded")
        self.assertEqual(view_model.lineCount, 2)
        self.assertTrue(view_model.hasTimestamps)
        self.assertEqual(view_model.detectedFields, ["USLT"])
        self.assertEqual(view_model.readBackend, "mutagen")
        self.assertTrue(view_model.isMemoryPreview)

    def test_selected_lrc_stays_in_memory_and_file_is_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lrc_path = Path(temp_dir) / "preview.lrc"
            original_text = "[00:03.00]preview only"
            lrc_path.write_text(original_text, encoding="utf-8")
            before_hash = hashlib.sha256(lrc_path.read_bytes()).hexdigest()

            view_model = LyricsViewModel(CapabilityGate(LYRICS_READ))
            with patch(
                "ui_next.bridge.lyrics_viewmodel.QFileDialog.getOpenFileName",
                return_value=(str(lrc_path), "LRC 歌词 (*.lrc *.LRC)"),
            ):
                view_model.chooseLrcForPreview()

            self.assertEqual(
                view_model.lyricsSource,
                "External LRC Preview",
            )
            self.assertTrue(view_model.isMemoryPreview)
            self.assertEqual(view_model.currentLyricsPath, str(lrc_path))
            self.assertEqual(view_model.originalLrcPath, "")
            self.assertEqual(view_model.lyricsText, original_text)
            self.assertEqual(
                hashlib.sha256(lrc_path.read_bytes()).hexdigest(),
                before_hash,
            )

    def test_all_write_slots_are_noop(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lrc_path = Path(temp_dir) / "preview.lrc"
            original_text = "[00:03.00]preview only"
            lrc_path.write_text(original_text, encoding="utf-8")
            before_names = sorted(path.name for path in Path(temp_dir).iterdir())

            view_model = LyricsViewModel(CapabilityGate(LYRICS_READ))
            view_model.loadLrcPreviewReadOnly(str(lrc_path))
            view_model.edit_lyrics("changed")
            view_model.save_as_lrc()
            view_model.save_to_original_lrc()
            view_model.write_lyrics_to_audio()

            self.assertEqual(
                lrc_path.read_text(encoding="utf-8"),
                original_text,
            )
            self.assertEqual(
                sorted(path.name for path in Path(temp_dir).iterdir()),
                before_names,
            )
            self.assertEqual(
                view_model.statusMessage,
                "当前操作暂不可用；未修改歌词或音频文件。",
            )

    def test_clear_only_clears_in_memory_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lrc_path = Path(temp_dir) / "preview.lrc"
            original_bytes = b"[00:01.00]preview"
            lrc_path.write_bytes(original_bytes)

            view_model = LyricsViewModel(CapabilityGate(LYRICS_READ))
            view_model.loadLrcPreviewReadOnly(str(lrc_path))
            view_model.clearLyricsPreview()

            self.assertFalse(view_model.hasLyrics)
            self.assertFalse(view_model.isMemoryPreview)
            self.assertEqual(view_model.lineCount, 0)
            self.assertEqual(lrc_path.read_bytes(), original_bytes)


if __name__ == "__main__":
    unittest.main()
