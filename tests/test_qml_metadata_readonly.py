import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import metadata
from ui_next.bridge.capabilities import METADATA_READ, CapabilityGate
from ui_next.bridge.metadata_viewmodel import MetadataViewModel


class MetadataReaderTests(unittest.TestCase):
    def test_readonly_result_has_real_fields_without_extracting_cover_bytes(self):
        class FakeInfo:
            length = 263.4
            bitrate = 914000
            sample_rate = 44100
            channels = 2
            bits_per_sample = 24
            codec = "FLAC"

        class FakePicture:
            @property
            def data(self):
                raise AssertionError("Phase 4.2 must not read cover bytes")

        class FakeAudio:
            info = FakeInfo()
            pictures = [FakePicture()]
            tags = {
                "title": ["Real Title"],
                "artist": ["Real Artist"],
                "album": ["Real Album"],
                "albumartist": ["Album Artist"],
                "date": ["2026"],
                "genre": ["Pop"],
                "tracknumber": ["3/12"],
                "discnumber": ["1/2"],
                "comment": ["Read-only comment"],
                "lyrics": ["lyrics content must not be returned"],
            }

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
                    side_effect=AssertionError("cover extraction is forbidden"),
                ),
            ):
                result = metadata.read_audio_metadata(
                    str(audio_path),
                    include_cover=False,
                )

            self.assertTrue(result["ok"])
            self.assertEqual(result["title"], "Real Title")
            self.assertEqual(result["album_artist"], "Album Artist")
            self.assertEqual(result["duration_text"], "04:23")
            self.assertEqual(result["bitrate_text"], "914 kbps")
            self.assertEqual(result["sample_rate_text"], "44100 Hz")
            self.assertEqual(result["channels_text"], "2")
            self.assertTrue(result["has_cover"])
            self.assertTrue(result["has_lyrics"])
            self.assertIsNone(result["cover_data"])
            self.assertNotIn("lyrics content", str(result))
            self.assertEqual(
                hashlib.sha256(audio_path.read_bytes()).hexdigest(),
                before_hash,
            )

    def test_missing_mutagen_returns_friendly_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "sample.wav"
            audio_path.write_bytes(b"placeholder")

            with patch("metadata.MutagenFile", None):
                result = metadata.read_audio_metadata(
                    str(audio_path),
                    include_cover=False,
                )

        self.assertFalse(result["ok"])
        self.assertIn("mutagen 未安装", result["error"])


class MetadataViewModelReadOnlyTests(unittest.TestCase):
    def test_empty_state_is_explicit_and_read_only(self):
        view_model = MetadataViewModel()

        self.assertTrue(view_model.previewMode)
        self.assertFalse(view_model.metadataReadEnabled)
        self.assertFalse(bool(view_model.currentFilePath))
        self.assertEqual(view_model.readStatus, "无当前文件")
        self.assertIn("手动选择", view_model.statusMessage)

    def test_preview_records_path_without_calling_real_reader(self):
        view_model = MetadataViewModel()

        with patch(
            "ui_next.bridge.metadata_viewmodel.read_audio_metadata"
        ) as reader:
            view_model.loadMetadataReadOnly("D:/Music/Artist - Title.flac")

        reader.assert_not_called()
        self.assertEqual(
            view_model.currentFilePath,
            "D:/Music/Artist - Title.flac",
        )
        self.assertEqual(view_model.currentFileName, "Artist - Title.flac")
        self.assertEqual(view_model.fileFormat, "FLAC")
        self.assertEqual(view_model.fileSizeText, "Preview / 未读取")
        self.assertEqual(view_model.durationText, "Preview / Mock")
        self.assertEqual(
            view_model.statusMessage,
            "当前未启用 metadata_read，只显示 Preview / Mock 信息。",
        )

    def test_enabled_capability_maps_real_readonly_result(self):
        fake_result = {
            "ok": True,
            "path": "",
            "filename": "song.flac",
            "format": "FLAC",
            "file_size_text": "35.2 MB",
            "duration_text": "04:23",
            "bitrate_text": "914 kbps",
            "sample_rate_text": "44100 Hz",
            "channels_text": "2",
            "title": "Title",
            "artist": "Artist",
            "album": "Album",
            "album_artist": "Album Artist",
            "year": "2026",
            "genre": "Pop",
            "track": "3/12",
            "disc": "1/2",
            "comment": "Comment",
            "has_basic_tags": True,
            "has_cover": True,
            "has_lyrics": True,
            "read_backend": "mutagen",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "song.flac"
            original = b"placeholder"
            audio_path.write_bytes(original)
            fake_result["path"] = str(audio_path)

            view_model = MetadataViewModel(
                CapabilityGate(METADATA_READ)
            )
            with patch(
                "ui_next.bridge.metadata_viewmodel.read_audio_metadata",
                return_value=fake_result,
            ) as reader:
                view_model.loadMetadataReadOnly(str(audio_path))

            reader.assert_called_once_with(
                str(audio_path),
                include_cover=False,
            )
            self.assertFalse(view_model.previewMode)
            self.assertEqual(view_model.title, "Title")
            self.assertEqual(view_model.albumArtist, "Album Artist")
            self.assertEqual(view_model.channelsText, "2")
            self.assertEqual(view_model.disc, "1/2")
            self.assertTrue(view_model.hasCover)
            self.assertTrue(view_model.hasLyrics)
            self.assertEqual(view_model.coverImageUrl, "")
            self.assertEqual(view_model.readBackend, "mutagen")
            self.assertEqual(audio_path.read_bytes(), original)

    def test_reader_error_is_reported_without_crashing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "broken.mp3"
            audio_path.write_bytes(b"broken")
            view_model = MetadataViewModel(
                CapabilityGate(METADATA_READ)
            )
            with patch(
                "ui_next.bridge.metadata_viewmodel.read_audio_metadata",
                return_value={
                    "ok": False,
                    "error": "不支持的格式或文件损坏",
                },
            ):
                view_model.loadMetadataReadOnly(str(audio_path))

        self.assertIn("读取失败", view_model.readStatus)
        self.assertIn("文件损坏", view_model.lastReadError)

    def test_choose_file_obeys_capability_gate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "preview.mp3"
            audio_path.write_bytes(b"preview")
            view_model = MetadataViewModel()
            with (
                patch(
                    "ui_next.bridge.metadata_viewmodel.QFileDialog.getOpenFileName",
                    return_value=(str(audio_path), "音频文件"),
                ),
                patch(
                    "ui_next.bridge.metadata_viewmodel.read_audio_metadata"
                ) as reader,
            ):
                view_model.chooseFileForMetadataRead()

        reader.assert_not_called()
        self.assertEqual(view_model.currentFilePath, str(audio_path))
        self.assertIn("未启用 metadata_read", view_model.statusMessage)

    def test_disabled_write_slots_do_not_change_or_create_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio_path = root / "source.mp3"
            original_bytes = b"source-placeholder"
            audio_path.write_bytes(original_bytes)
            before_names = sorted(path.name for path in root.iterdir())

            view_model = MetadataViewModel(
                CapabilityGate(METADATA_READ)
            )
            view_model.loadMetadataReadOnly(str(audio_path))
            view_model.disabledEditMetadata()
            view_model.disabledWriteMetadata()
            view_model.disabledImportCover()
            view_model.disabledRemoveCover()
            view_model.disabledWriteCover()
            view_model.disabledWriteLyrics()
            view_model.disabledSaveLyrics()

            self.assertEqual(audio_path.read_bytes(), original_bytes)
            self.assertEqual(
                sorted(path.name for path in root.iterdir()),
                before_names,
            )
            self.assertEqual(
                view_model.statusMessage,
                "当前操作暂不可用；未修改任何音频文件。",
            )

    def test_reload_and_clear_only_update_summary_state(self):
        view_model = MetadataViewModel()
        view_model.loadMetadataReadOnly("D:/Music/sample.wav")
        view_model.reloadMetadataReadOnly()
        self.assertEqual(view_model.currentFilePath, "D:/Music/sample.wav")

        view_model.clearMetadata()
        self.assertFalse(bool(view_model.currentFilePath))
        self.assertEqual(view_model.readStatus, "无当前文件")


if __name__ == "__main__":
    unittest.main()
