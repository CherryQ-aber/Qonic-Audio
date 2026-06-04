import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import converter
import watcher
from config import APP_VERSION


class ConverterSafetyTests(unittest.TestCase):

    def test_same_format_conversion_preserves_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.mp3"
            output_root = root / "output"
            source.write_bytes(b"test audio")

            with (
                patch("converter._validate_audio_file", return_value=True),
                patch("converter.get_output_folder", return_value=str(output_root)),
            ):
                self.assertTrue(converter.convert_audio(str(source), "mp3"))

            self.assertTrue(source.exists())
            self.assertEqual(
                (output_root / "MP3" / "source.mp3").read_bytes(),
                b"test audio",
            )

    def test_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.mp3"
            output_folder = root / "output" / "MP3"
            existing = output_folder / "source.mp3"
            source.write_bytes(b"new audio")
            output_folder.mkdir(parents=True)
            existing.write_bytes(b"existing audio")

            with (
                patch("converter._validate_audio_file", return_value=True),
                patch(
                    "converter.get_output_folder",
                    return_value=str(root / "output"),
                ),
            ):
                self.assertTrue(converter.convert_audio(str(source), "mp3"))

            self.assertEqual(existing.read_bytes(), b"existing audio")
            self.assertEqual(
                (output_folder / "source (1).mp3").read_bytes(),
                b"new audio",
            )


class WatcherTaskTests(unittest.TestCase):

    def setUp(self):
        with watcher.pending_files_lock:
            watcher.pending_files.clear()

        with watcher.processed_files_lock:
            watcher.processed_files.clear()

        with watcher.suppressed_generated_paths_lock:
            watcher.suppressed_generated_paths.clear()

    def tearDown(self):
        self.setUp()

    def test_aac_and_ogg_are_supported_inputs(self):
        self.assertTrue(watcher._is_file_supported("sample.aac"))
        self.assertTrue(watcher._is_file_supported("sample.ogg"))

    def test_task_target_format_can_be_set(self):
        path = "C:/test/sample.mp3"
        self.assertTrue(watcher.add_pending_file(path))
        self.assertTrue(watcher.set_pending_file_target_format(path, "wav"))
        self.assertEqual(watcher.get_task_snapshots()[0]["target_format"], "wav")


class ReleaseConfigurationTests(unittest.TestCase):

    def test_release_version_is_patch_baseline(self):
        self.assertEqual(APP_VERSION, "3.5.1")

    def test_spec_only_packages_required_external_tools(self):
        spec_text = Path("CherryQ Audio Converter.spec").read_text(
            encoding="utf-8"
        )

        self.assertIn("Tools/ffmpeg/bin/ffmpeg.exe", spec_text)
        self.assertIn("Tools/ncmdump/ncmdump.exe", spec_text)
        self.assertNotIn("('Tools', 'Tools')", spec_text)


if __name__ == "__main__":
    unittest.main()
