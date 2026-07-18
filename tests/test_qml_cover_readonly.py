import base64
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import metadata
from ui_next.bridge.capabilities import COVER_READ, CapabilityGate
from ui_next.bridge.cover_viewmodel import CoverViewModel


ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0l"
    "EQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


class CoverPreviewReaderTests(unittest.TestCase):
    def test_read_cover_preview_returns_data_url_without_writing_file(self):
        class FakeAudio:
            def save(self, *_args, **_kwargs):
                raise AssertionError("mutagen save must never be called")

        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "sample.flac"
            original = b"readonly-audio-placeholder"
            audio_path.write_bytes(original)
            before_hash = hashlib.sha256(original).hexdigest()

            with (
                patch("metadata.MutagenFile", return_value=FakeAudio()),
                patch(
                    "metadata.extract_cover_info",
                    return_value=(ONE_PIXEL_PNG, "image/png", "FLAC picture"),
                ),
            ):
                result = metadata.read_cover_preview(str(audio_path))

            self.assertTrue(result["ok"])
            self.assertTrue(result["has_cover"])
            self.assertIn(result["mime"], {"image/png", "image/jpeg"})
            self.assertEqual(result["width"], 1)
            self.assertEqual(result["height"], 1)
            self.assertEqual(result["byte_size"], len(ONE_PIXEL_PNG))
            self.assertTrue(result["preview_data_url"].startswith("data:image/"))
            self.assertNotIn("cover_data", result)
            self.assertEqual(
                hashlib.sha256(audio_path.read_bytes()).hexdigest(),
                before_hash,
            )

    def test_large_cover_skips_preview_data_url(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "large.mp3"
            audio_path.write_bytes(b"placeholder")
            with (
                patch("metadata.MutagenFile", return_value=object()),
                patch(
                    "metadata.extract_cover_info",
                    return_value=(b"12345", "image/jpeg", "APIC:"),
                ),
                patch("metadata.MAX_COVER_RAW_BYTES", 4),
            ):
                result = metadata.read_cover_preview(str(audio_path))

        self.assertTrue(result["ok"])
        self.assertTrue(result["has_cover"])
        self.assertEqual(result["preview_data_url"], "")
        self.assertIn("过大", result["error"])

    def test_missing_mutagen_returns_friendly_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "sample.mp3"
            audio_path.write_bytes(b"placeholder")
            with patch("metadata.MutagenFile", None):
                result = metadata.read_cover_preview(str(audio_path))

        self.assertFalse(result["ok"])
        self.assertIn("mutagen 未安装", result["error"])


class CoverViewModelReadOnlyTests(unittest.TestCase):
    def test_preview_records_path_without_calling_real_reader(self):
        view_model = CoverViewModel()

        with patch("ui_next.bridge.cover_viewmodel.read_cover_preview") as reader:
            view_model.loadCoverReadOnly("D:/Music/Artist - Title.flac")

        reader.assert_not_called()
        self.assertTrue(view_model.previewMode)
        self.assertEqual(view_model.currentFileName, "Artist - Title.flac")
        self.assertEqual(view_model.coverStatus, "Preview / Mock；未读取真实封面")
        self.assertIn("未启用 cover_read", view_model.statusMessage)

    def test_enabled_capability_maps_cover_preview_result(self):
        fake_result = {
            "ok": True,
            "path": "",
            "filename": "song.flac",
            "has_cover": True,
            "mime": "image/png",
            "byte_size_text": "68 B",
            "dimensions_text": "1 x 1",
            "preview_data_url": "data:image/png;base64,AAAA",
            "read_backend": "mutagen",
            "error": "",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "song.flac"
            original = b"placeholder"
            audio_path.write_bytes(original)
            fake_result["path"] = str(audio_path)

            view_model = CoverViewModel(CapabilityGate(COVER_READ))
            with patch(
                "ui_next.bridge.cover_viewmodel.read_cover_preview",
                return_value=fake_result,
            ) as reader:
                view_model.loadCoverReadOnly(str(audio_path))

            reader.assert_called_once_with(str(audio_path))
            self.assertFalse(view_model.previewMode)
            self.assertTrue(view_model.hasCover)
            self.assertEqual(view_model.coverMime, "image/png")
            self.assertEqual(view_model.coverDimensionsText, "1 x 1")
            self.assertTrue(view_model.coverPreviewUrl.startswith("data:image/png"))
            self.assertEqual(view_model.readBackend, "mutagen")
            self.assertEqual(audio_path.read_bytes(), original)

    def test_no_cover_result_is_read_success_without_preview_url(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "song.mp3"
            audio_path.write_bytes(b"placeholder")
            view_model = CoverViewModel(CapabilityGate(COVER_READ))
            with patch(
                "ui_next.bridge.cover_viewmodel.read_cover_preview",
                return_value={
                    "ok": True,
                    "path": str(audio_path),
                    "filename": "song.mp3",
                    "has_cover": False,
                    "read_backend": "mutagen",
                },
            ):
                view_model.loadCoverReadOnly(str(audio_path))

        self.assertFalse(view_model.hasCover)
        self.assertEqual(view_model.coverPreviewUrl, "")
        self.assertEqual(view_model.coverStatus, "未检测到内嵌封面")

    def test_disabled_write_slots_do_not_change_or_create_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio_path = root / "source.mp3"
            original = b"source-placeholder"
            audio_path.write_bytes(original)
            before_names = sorted(path.name for path in root.iterdir())

            view_model = CoverViewModel(CapabilityGate(COVER_READ))
            view_model.loadCoverReadOnly(str(audio_path))
            view_model.disabledImportCover()
            view_model.disabledWriteCover()
            view_model.disabledRemoveCover()
            view_model.disabledRestoreCover()
            view_model.disabledOverwriteCover()

            self.assertEqual(audio_path.read_bytes(), original)
            self.assertEqual(
                sorted(path.name for path in root.iterdir()),
                before_names,
            )
            self.assertEqual(
                view_model.statusMessage,
                "当前操作暂不可用；未修改任何封面或音频文件。",
            )

    def test_reload_and_clear_only_update_memory_state(self):
        view_model = CoverViewModel()
        view_model.loadCoverReadOnly("D:/Music/sample.wav")
        view_model.reloadCoverReadOnly()
        self.assertEqual(view_model.currentFilePath, "D:/Music/sample.wav")

        view_model.clearCoverPreview()
        self.assertFalse(bool(view_model.currentFilePath))
        self.assertEqual(view_model.coverStatus, "未读取")


if __name__ == "__main__":
    unittest.main()
