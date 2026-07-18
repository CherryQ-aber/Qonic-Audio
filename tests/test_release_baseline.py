import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import audio_editor_backend
import cache_manager
import config
import converter
import formats
import lyrics
import metadata
import watcher
from app_info import APP_PACKAGE_BASENAME, APP_RELEASE_NOTES_NAME, APP_WINDOW_TITLE
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
                patch("converter.get_create_format_subfolder", return_value=True),
            ):
                result = converter.convert_audio(str(source), "mp3")

            self.assertTrue(result["success"])
            self.assertEqual(
                Path(result["output_path"]),
                output_root / "MP3" / "source.mp3",
            )
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
                patch("converter.get_create_format_subfolder", return_value=True),
            ):
                result = converter.convert_audio(str(source), "mp3")

            self.assertTrue(result["success"])
            self.assertEqual(existing.read_bytes(), b"existing audio")
            self.assertEqual(
                (output_folder / "source (1).mp3").read_bytes(),
                b"new audio",
            )

    def test_converter_has_no_pitch_shift_backend_hook(self):
        self.assertFalse(hasattr(converter, "apply_pitch_shift"))

    def test_same_format_conversion_ignores_reserved_pitch_shift_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.mp3"
            output_root = root / "output"
            source.write_bytes(b"test audio")

            with (
                patch("converter._validate_audio_file", return_value=True),
                patch("converter.get_output_folder", return_value=str(output_root)),
                patch(
                    "config.load_config",
                    return_value={
                        "pitch_shift_enabled": True,
                        "pitch_shift_semitones": 12,
                    },
                ),
            ):
                result = converter.convert_audio(str(source), "mp3")

            self.assertTrue(result["success"])
            self.assertEqual(
                (output_root / "MP3" / "source.mp3").read_bytes(),
                b"test audio",
            )
            self.assertFalse(
                (output_root / "MP3" / "source [Pitch +12].mp3").exists()
            )

    def test_zero_byte_output_is_not_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "empty.mp3"
            output_path.write_bytes(b"")

            with self.assertRaises(ValueError):
                converter._ensure_output_created(str(output_path))

    def test_build_output_path_can_skip_format_subfolder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.flac"
            source.write_bytes(b"input")

            output_path = converter.build_output_path(
                str(source),
                "mp3",
                str(root / "output"),
                create_format_subfolder=False,
            )

            self.assertEqual(Path(output_path), root / "output" / "source.mp3")

    def test_build_output_path_uses_configured_target_extension(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.flac"
            source.write_bytes(b"input")

            output_path = converter.build_output_path(
                str(source),
                "m4a",
                str(root / "output"),
                create_format_subfolder=True,
            )

            self.assertEqual(Path(output_path), root / "output" / "M4A" / "source.m4a")

    def test_convert_audio_inserts_target_ffmpeg_args(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.flac"
            output_root = root / "output"
            source.write_bytes(b"fake flac")

            def fake_run(command):
                if "-f" in command and "null" in command:
                    return SimpleNamespace(returncode=0, stdout="", stderr="")

                Path(command[-1]).write_bytes(b"converted")
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with (
                patch("converter._run_ffmpeg_command", side_effect=fake_run) as mock_run,
                patch("converter.get_output_folder", return_value=str(output_root)),
            ):
                result = converter.convert_audio(
                    str(source),
                    "m4a",
                    create_format_subfolder=False,
                )

            self.assertTrue(result["success"])
            self.assertEqual(Path(result["output_path"]), output_root / "source.m4a")
            convert_command = mock_run.call_args_list[-1].args[0]
            self.assertIn("-c:a", convert_command)
            self.assertIn("aac", convert_command)
            self.assertLess(
                convert_command.index("aac"),
                convert_command.index(str(output_root / "source.m4a")),
            )

    def test_convert_audio_uses_temporary_output_root_without_config_save(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.flac"
            default_output = root / "default"
            temporary_output = root / "temporary"
            source.write_bytes(b"fake flac")

            with (
                patch("converter._validate_audio_file", return_value=True),
                patch("converter.get_output_folder", return_value=str(default_output)),
                patch("config.save_config") as mock_save_config,
            ):
                result = converter.convert_audio(
                    str(source),
                    "flac",
                    output_root_override=str(temporary_output),
                    create_format_subfolder=False,
                )

            self.assertTrue(result["success"])
            self.assertEqual(
                Path(result["output_path"]),
                temporary_output / "source.flac",
            )
            self.assertTrue((temporary_output / "source.flac").exists())
            self.assertFalse(default_output.exists())
            mock_save_config.assert_not_called()

    def test_get_create_format_subfolder_defaults_true(self):
        with patch("config.load_config", return_value={}):
            self.assertTrue(config.get_create_format_subfolder())

    def test_convert_audio_uses_original_source_for_lyrics_lookup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            original = root / "song.ncm"
            decoded = root / "Temp" / "song.flac"
            output_root = root / "output"
            original.write_bytes(b"fake ncm")
            decoded.parent.mkdir()
            decoded.write_bytes(b"fake decoded")

            with (
                patch("converter._validate_audio_file", return_value=True),
                patch("converter.get_output_folder", return_value=str(output_root)),
                patch(
                    "converter.process_lyrics_for_output",
                    return_value={"found": False},
                ) as mock_lyrics,
            ):
                result = converter.convert_audio(
                    str(decoded),
                    "flac",
                    original_source_path=str(original),
                    lyrics_source_paths=[str(original), str(decoded)],
                )

            self.assertTrue(result["success"])
            mock_lyrics.assert_called_once()
            kwargs = mock_lyrics.call_args.kwargs
            self.assertEqual(kwargs["source_path"], str(original))
            self.assertIn(str(decoded), kwargs["extra_source_paths"])

    def test_lyrics_config_defaults(self):
        with patch("config.load_config", return_value={}):
            self.assertTrue(config.get_embed_lyrics_after_convert())
            self.assertFalse(config.get_copy_lrc_to_output())
            self.assertFalse(config.get_overwrite_existing_lyrics())


class CacheManagerTests(unittest.TestCase):

    def _cache_fixture(self, root):
        categories = {
            "general_temp": {
                "label": "通用临时缓存",
                "path": str(root / "Temp" / "General"),
                "extra_paths": [],
            },
            "waveform": {
                "label": "波形缓存",
                "path": str(root / "Cache" / "Waveform"),
                "extra_paths": [],
            },
        }
        roots = {
            "temp": str(root / "Temp"),
            "cache": str(root / "Cache"),
        }
        return categories, roots

    def test_cache_dirs_are_created_and_scanned(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            categories, roots = self._cache_fixture(root)

            with (
                patch("cache_manager.CACHE_CATEGORIES", categories),
                patch("cache_manager.get_cache_roots", return_value=roots),
                patch("cache_manager._protected_paths", return_value=[]),
            ):
                cache_manager.ensure_cache_dirs()
                (root / "Temp" / "General" / "preview.tmp").write_bytes(b"abc")
                (root / "Cache" / "Waveform" / "wave.bin").write_bytes(b"12345")

                summary = cache_manager.scan_cache()

            self.assertEqual(summary["total_files"], 2)
            self.assertEqual(summary["total_size"], 8)
            self.assertEqual(summary["cleanable_files"], 2)
            self.assertEqual(summary["cleanable_size"], 8)
            self.assertTrue((root / "Temp").is_dir())
            self.assertTrue((root / "Cache").is_dir())

    def test_clear_cache_removes_contents_but_keeps_roots(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            categories, roots = self._cache_fixture(root)
            cache_file = root / "Temp" / "General" / "preview.tmp"

            with (
                patch("cache_manager.CACHE_CATEGORIES", categories),
                patch("cache_manager.get_cache_roots", return_value=roots),
                patch("cache_manager._protected_paths", return_value=[]),
            ):
                cache_manager.ensure_cache_dirs()
                cache_file.write_bytes(b"abc")

                result = cache_manager.clear_cache()

            self.assertEqual(result["deleted_files"], 1)
            self.assertEqual(result["freed_size"], 3)
            self.assertTrue((root / "Temp").is_dir())
            self.assertTrue((root / "Cache").is_dir())
            self.assertTrue((root / "Temp" / "General").is_dir())
            self.assertFalse(cache_file.exists())

    def test_safe_cache_path_rejects_roots_and_protected_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            categories, roots = self._cache_fixture(root)
            protected_dir = root / "Temp" / "General"
            safe_file = root / "Cache" / "Waveform" / "wave.bin"
            outside_file = root / "outside.bin"

            with (
                patch("cache_manager.CACHE_CATEGORIES", categories),
                patch("cache_manager.get_cache_roots", return_value=roots),
                patch("cache_manager._protected_paths", return_value=[str(protected_dir)]),
            ):
                cache_manager.ensure_cache_dirs()
                safe_file.write_bytes(b"abc")
                outside_file.write_bytes(b"abc")

                self.assertFalse(cache_manager.is_safe_cache_path(root / "Temp"))
                self.assertFalse(cache_manager.is_safe_cache_path(protected_dir / "x.tmp"))
                self.assertFalse(cache_manager.is_safe_cache_path(outside_file))
                self.assertTrue(cache_manager.is_safe_cache_path(safe_file))

    def test_scan_distinguishes_cleanable_and_skipped_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            protected_dir = root / "Temp" / "Protected"
            categories = {
                "protected": {
                    "label": "受保护缓存",
                    "path": str(protected_dir),
                    "extra_paths": [],
                },
                "waveform": {
                    "label": "波形缓存",
                    "path": str(root / "Cache" / "Waveform"),
                    "extra_paths": [],
                },
            }
            roots = {
                "temp": str(root / "Temp"),
                "cache": str(root / "Cache"),
            }

            with (
                patch("cache_manager.CACHE_CATEGORIES", categories),
                patch("cache_manager.get_cache_roots", return_value=roots),
                patch("cache_manager._protected_paths", return_value=[str(protected_dir)]),
            ):
                cache_manager.ensure_cache_dirs()
                (protected_dir / "source.flac").write_bytes(b"do not touch")
                (root / "Cache" / "Waveform" / "wave.bin").write_bytes(b"12345")

                summary = cache_manager.scan_cache()

            self.assertEqual(summary["cleanable_files"], 1)
            self.assertEqual(summary["cleanable_size"], 5)
            self.assertEqual(summary["skipped_files"], 1)
            self.assertEqual(
                summary["categories"]["protected"]["cleanable_files"],
                0,
            )
            self.assertEqual(
                summary["categories"]["waveform"]["cleanable_files"],
                1,
            )

    def test_cache_button_state_uses_cleanable_summary_and_conflicts(self):
        from ui.main_window import MainWindow

        class DummyButton:
            def __init__(self):
                self.enabled = None

            def setEnabled(self, enabled):
                self.enabled = enabled

        class DummyWindow:
            cache_scan_summary = {
                "total_files": 2,
                "total_size": 8,
                "cleanable_files": 2,
                "cleanable_size": 8,
            }

            def __init__(self, conflicts=None):
                self.scan_cache_button = DummyButton()
                self.clear_cache_button = DummyButton()
                self.conflicts = conflicts or []

            def _is_cache_scan_thread_running(self):
                return False

            def _is_cache_clear_thread_running(self):
                return False

            def _get_cache_blocking_reasons(self):
                return self.conflicts

            def _get_cache_cleanable_counts(self, summary=None):
                return MainWindow._get_cache_cleanable_counts(self, summary)

        dummy = DummyWindow()
        MainWindow.update_cache_buttons_state(dummy)
        self.assertTrue(dummy.scan_cache_button.enabled)
        self.assertTrue(dummy.clear_cache_button.enabled)

        dummy_with_conflict = DummyWindow(conflicts=["正在转换"])
        MainWindow.update_cache_buttons_state(dummy_with_conflict)
        self.assertTrue(dummy_with_conflict.scan_cache_button.enabled)
        self.assertFalse(dummy_with_conflict.clear_cache_button.enabled)

        dummy_empty = DummyWindow()
        dummy_empty.cache_scan_summary = {
            "total_files": 2,
            "total_size": 8,
            "cleanable_files": 0,
            "cleanable_size": 0,
        }
        MainWindow.update_cache_buttons_state(dummy_empty)
        self.assertFalse(dummy_empty.clear_cache_button.enabled)

    def test_cache_clear_is_blocked_when_waiting_ncm_temp_exists(self):
        from ui.main_window import MainWindow

        class DummyLog:
            def append(self, _message):
                pass

        class DummyWindow:
            log_box = DummyLog()
            audio_editor_workspace = None

            def _is_convert_thread_running(self):
                return False

            def _is_scan_thread_running(self):
                return False

            def _is_retry_thread_running(self):
                return False

            def _is_prepare_thread_running(self):
                return False

        task = {
            "status": watcher.WAITING_STATUS,
            "path": "C:/Music/Song.ncm",
            "temp_work_dir": "D:/App/Temp/NCM/task",
            "decoded_path": "D:/App/Temp/NCM/task/Song.flac",
        }

        with patch("ui.main_window.watcher.get_task_snapshots", return_value=[task]):
            reasons = MainWindow._get_cache_blocking_reasons(DummyWindow())

        self.assertIn("队列中存在待处理的 NCM 临时文件", reasons)


class LyricsProcessingTests(unittest.TestCase):

    def test_find_matching_lrc_supports_uppercase_extension(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "Song.flac"
            lrc = Path(temp_dir) / "Song.LRC"
            source.write_bytes(b"audio")
            lrc.write_text("[00:01.00]Hello", encoding="utf-8")

            found = lyrics.find_matching_lrc(str(source))

            self.assertIsNotNone(found)
            self.assertTrue(os.path.isfile(found))
            self.assertEqual(os.path.splitext(found)[1].lower(), ".lrc")

    def test_find_matching_lrc_checks_extra_source_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            decoded = root / "Temp" / "Song.flac"
            original = root / "CloudMusic" / "Song.ncm"
            lrc = root / "CloudMusic" / "Song.lrc"
            decoded.parent.mkdir()
            original.parent.mkdir()
            decoded.write_bytes(b"decoded")
            original.write_bytes(b"ncm")
            lrc.write_text("[00:01.00]Hello", encoding="utf-8")

            self.assertEqual(
                lyrics.find_matching_lrc(
                    str(decoded),
                    extra_source_paths=[str(original)],
                ),
                str(lrc),
            )

    def test_read_lrc_file_supports_gbk(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lrc = Path(temp_dir) / "song.lrc"
            expected = "[00:01.00]中文歌词"
            lrc.write_bytes(expected.encode("gbk"))

            self.assertEqual(lyrics.read_lrc_file(str(lrc)), expected)

    def test_read_embedded_lyrics_reads_mp3_uslt(self):
        class FakeUSLT:
            text = "[00:01.00]mp3 lyric"

        with tempfile.TemporaryDirectory() as temp_dir:
            audio = Path(temp_dir) / "Song.mp3"
            audio.write_bytes(b"audio")

            with (
                patch("lyrics.USLT", FakeUSLT),
                patch("lyrics.ID3", return_value={"USLT::und": FakeUSLT()}),
            ):
                result = lyrics.read_embedded_lyrics(str(audio))

        self.assertTrue(result["found"])
        self.assertEqual(result["lyrics"], "[00:01.00]mp3 lyric")
        self.assertEqual(result["source_type"], "embedded")
        self.assertEqual(result["field"], "USLT")

    def test_read_embedded_lyrics_reads_flac_lyrics_before_unsynced(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audio = Path(temp_dir) / "Song.flac"
            audio.write_bytes(b"audio")

            with patch(
                "lyrics.FLAC",
                return_value={
                    "UNSYNCEDLYRICS": ["unsynced"],
                    "LYRICS": ["[00:01.00]flac lyric"],
                },
            ):
                result = lyrics.read_embedded_lyrics(str(audio))

        self.assertTrue(result["found"])
        self.assertEqual(result["lyrics"], "[00:01.00]flac lyric")
        self.assertEqual(result["field"], "LYRICS")

    def test_read_embedded_lyrics_reads_m4a_lyrics(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audio = Path(temp_dir) / "Song.m4a"
            audio.write_bytes(b"audio")

            with patch("lyrics.MP4", return_value={"\xa9lyr": ["[00:01.00]m4a lyric"]}):
                result = lyrics.read_embedded_lyrics(str(audio))

        self.assertTrue(result["found"])
        self.assertEqual(result["lyrics"], "[00:01.00]m4a lyric")
        self.assertEqual(result["field"], "\xa9lyr")

    def test_copy_lrc_to_output_does_not_overwrite_existing_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_lrc = root / "Song.lrc"
            output_audio = root / "out" / "Song.flac"
            existing_lrc = root / "out" / "Song.lrc"
            source_lrc.write_text("[00:01.00]new", encoding="utf-8")
            output_audio.parent.mkdir()
            output_audio.write_bytes(b"audio")
            existing_lrc.write_text("[00:01.00]old", encoding="utf-8")

            result = lyrics.copy_lrc_to_output(str(source_lrc), str(output_audio))

            copied_path = root / "out" / "Song (1).lrc"
            self.assertTrue(result["copied"])
            self.assertEqual(Path(result["output_lrc_path"]), copied_path)
            self.assertEqual(existing_lrc.read_text(encoding="utf-8"), "[00:01.00]old")
            self.assertEqual(copied_path.read_text(encoding="utf-8"), "[00:01.00]new")

    def test_process_lyrics_skips_wav_embedding_but_can_copy_lrc(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Song.flac"
            lrc = root / "Song.lrc"
            output_audio = root / "output" / "Song.wav"
            source.write_bytes(b"audio")
            lrc.write_text("[00:01.00]Hello", encoding="utf-8")
            output_audio.parent.mkdir()
            output_audio.write_bytes(b"wav")

            summary = lyrics.process_lyrics_for_output(
                str(source),
                str(output_audio),
                embed=True,
                copy_external=True,
                overwrite=False,
            )

            self.assertTrue(summary["found"])
            self.assertTrue(summary["copied"])
            self.assertFalse(summary["embedded"])
            self.assertEqual(summary["skipped_reason"], "unsupported_wav")
            self.assertTrue((output_audio.parent / "Song.lrc").exists())

    def test_process_lyrics_can_embed_without_copying_lrc(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Song.flac"
            lrc = root / "Song.lrc"
            output_audio = root / "output" / "Song.flac"
            source.write_bytes(b"audio")
            lrc.write_text("[00:01.00]Hello", encoding="utf-8")
            output_audio.parent.mkdir()
            output_audio.write_bytes(b"audio")

            with patch(
                "lyrics.embed_lrc_to_audio",
                return_value={"embedded": True, "skipped_reason": None, "error": None},
            ) as mock_embed:
                summary = lyrics.process_lyrics_for_output(
                    str(source),
                    str(output_audio),
                    embed=True,
                    copy_external=False,
                    overwrite=False,
                )

            self.assertTrue(summary["found"])
            self.assertTrue(summary["embedded"])
            self.assertFalse(summary["copied"])
            self.assertFalse((output_audio.parent / "Song.lrc").exists())
            mock_embed.assert_called_once()

    def test_process_lyrics_can_copy_without_embedding(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Song.flac"
            lrc = root / "Song.lrc"
            output_audio = root / "output" / "Song.flac"
            source.write_bytes(b"audio")
            lrc.write_text("[00:01.00]Hello", encoding="utf-8")
            output_audio.parent.mkdir()
            output_audio.write_bytes(b"audio")

            with patch("lyrics.embed_lrc_to_audio") as mock_embed:
                summary = lyrics.process_lyrics_for_output(
                    str(source),
                    str(output_audio),
                    embed=False,
                    copy_external=True,
                    overwrite=False,
                )

            self.assertTrue(summary["found"])
            self.assertFalse(summary["embedded"])
            self.assertTrue(summary["copied"])
            self.assertTrue((output_audio.parent / "Song.lrc").exists())
            mock_embed.assert_not_called()

    def test_process_lyrics_skips_when_all_lyrics_options_are_disabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Song.flac"
            lrc = root / "Song.lrc"
            output_audio = root / "output" / "Song.flac"
            source.write_bytes(b"audio")
            lrc.write_text("[00:01.00]Hello", encoding="utf-8")
            output_audio.parent.mkdir()
            output_audio.write_bytes(b"audio")

            with (
                patch("lyrics.read_lrc_file") as mock_read,
                patch("lyrics.embed_lrc_to_audio") as mock_embed,
            ):
                summary = lyrics.process_lyrics_for_output(
                    str(source),
                    str(output_audio),
                    embed=False,
                    copy_external=False,
                    overwrite=False,
                )

            self.assertTrue(summary["found"])
            self.assertFalse(summary["embedded"])
            self.assertFalse(summary["copied"])
            self.assertEqual(summary["skipped_reason"], "options_disabled")
            self.assertFalse((output_audio.parent / "Song.lrc").exists())
            mock_read.assert_not_called()
            mock_embed.assert_not_called()


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
        self.assertTrue(watcher._is_file_supported("sample.opus"))
        self.assertTrue(watcher._is_file_supported("sample.ape"))
        self.assertTrue(watcher._is_file_supported("sample.AIFF"))

    def test_lrc_and_txt_are_ignored_case_insensitively(self):
        self.assertTrue(formats.is_ignored_file("sample.lrc"))
        self.assertTrue(formats.is_ignored_file("sample.LRC"))
        self.assertTrue(formats.is_ignored_file("sample.TXT"))

    def test_task_target_format_can_be_set(self):
        path = "C:/test/sample.mp3"
        self.assertTrue(watcher.add_pending_file(path))
        self.assertTrue(watcher.set_pending_file_target_format(path, "opus"))
        self.assertEqual(watcher.get_task_snapshots()[0]["target_format"], "opus")

    def test_invalid_task_target_format_is_rejected(self):
        path = "C:/test/sample.mp3"
        self.assertTrue(watcher.add_pending_file(path))
        self.assertFalse(watcher.set_pending_file_target_format(path, "xyz"))
        self.assertIsNone(watcher.get_task_snapshots()[0]["target_format"])

    def test_detected_file_is_queued_without_blocking_prepare_work(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = str(Path(temp_dir) / "sample.flac")

            with (
                patch("watcher._wait_for_file_ready") as mock_wait,
                patch("watcher._handle_ncm_file") as mock_ncm,
            ):
                self.assertTrue(watcher.handle_detected_file(path, source="test"))

            task = watcher.get_task_snapshots()[0]
            self.assertEqual(task["status"], watcher.QUEUED_STATUS)
            self.assertFalse(task["can_convert"])
            self.assertEqual(watcher.get_convertible_tasks(), [])
            mock_wait.assert_not_called()
            mock_ncm.assert_not_called()

    def test_prepare_pending_file_marks_regular_audio_waiting(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = str(Path(temp_dir) / "sample.flac")
            Path(path).write_bytes(b"fake audio")

            self.assertTrue(watcher.handle_detected_file(path, source="test"))

            with patch("watcher._wait_for_file_ready", return_value=(True, "ready")):
                watcher.prepare_pending_files()

            task = watcher.get_task_snapshots()[0]
            self.assertEqual(task["status"], watcher.WAITING_STATUS)
            self.assertTrue(task["can_convert"])

    def test_retry_failed_files_requeues_without_waiting(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = str(Path(temp_dir) / "broken.flac")
            self.assertTrue(watcher.add_pending_file(path, status=watcher.FAILED_STATUS))

            with patch("watcher._wait_for_file_ready") as mock_wait:
                summary = watcher.retry_failed_files([path])

            task = watcher.get_task_snapshots()[0]
            self.assertEqual(summary["requeued_count"], 1)
            self.assertEqual(task["status"], watcher.QUEUED_STATUS)
            self.assertFalse(task["can_convert"])
            mock_wait.assert_not_called()

    def test_ncm_decode_runs_inside_temp_dir(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(source_dir) / "song.ncm"
            source_path.write_bytes(b"fake ncm")

            def fake_run(command, **kwargs):
                temp_ncm_path = Path(command[1])
                self.assertEqual(Path(kwargs["cwd"]), temp_ncm_path.parent)
                self.assertNotEqual(temp_ncm_path.parent, source_path.parent)
                decoded_path = temp_ncm_path.with_suffix(".flac")
                decoded_path.write_bytes(b"decoded")
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with (
                patch("watcher.NCM_TEMP_DIR", temp_dir),
                patch("watcher.subprocess.run", side_effect=fake_run),
            ):
                self.assertTrue(
                    watcher.add_pending_file(
                        str(source_path),
                        status=watcher.PROCESSING_STATUS,
                    )
                )
                watcher._handle_ncm_file(str(source_path))

            task = watcher.get_task_snapshots()[0]
            self.assertEqual(task["status"], watcher.WAITING_STATUS)
            self.assertTrue(task["decoded_path"].startswith(temp_dir))
            self.assertTrue(Path(task["decoded_path"]).exists())
            self.assertFalse((source_path.parent / "song.flac").exists())

    def test_non_protected_ncm_failure_cleans_temp_dir(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(source_dir) / "fake.ncm"
            source_path.write_bytes(b"not real ncm")

            def fake_run(command, **kwargs):
                temp_ncm_path = Path(command[1])
                temp_ncm_path.with_suffix(".flac").write_bytes(b"decoded")
                return SimpleNamespace(
                    returncode=0,
                    stdout="not netease protected file",
                    stderr="",
                )

            with (
                patch("watcher.NCM_TEMP_DIR", temp_dir),
                patch("watcher.subprocess.run", side_effect=fake_run),
            ):
                self.assertTrue(
                    watcher.add_pending_file(
                        str(source_path),
                        status=watcher.PROCESSING_STATUS,
                    )
                )
                watcher._handle_ncm_file(str(source_path))

            task = watcher.get_task_snapshots()[0]
            self.assertEqual(task["status"], watcher.FAILED_STATUS)
            self.assertIsNone(task["decoded_path"])
            self.assertEqual(task["generated_paths"], [])
            self.assertTrue(source_path.exists())
            self.assertFalse((source_path.parent / "fake.flac").exists())
            self.assertEqual(list(Path(temp_dir).iterdir()), [])

    def test_cleanup_task_runtime_files_removes_only_ncm_temp_dir(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(source_dir) / "song.ncm"
            output_path = Path(source_dir) / "song-output.flac"
            temp_work_dir = Path(temp_dir) / "task"
            temp_ncm_path = temp_work_dir / "song.ncm"
            decoded_path = temp_work_dir / "song.flac"

            source_path.write_bytes(b"source")
            output_path.write_bytes(b"output")
            temp_work_dir.mkdir()
            temp_ncm_path.write_bytes(b"temp ncm")
            decoded_path.write_bytes(b"decoded")

            with patch("watcher.NCM_TEMP_DIR", temp_dir):
                self.assertTrue(
                    watcher.add_pending_file(
                        str(source_path),
                        status=watcher.WAITING_STATUS,
                    )
                )
                self.assertTrue(
                    watcher.set_pending_file_runtime_data(
                        str(source_path),
                        decoded_path=str(decoded_path),
                        generated_paths=[str(temp_ncm_path), str(decoded_path)],
                        temp_work_dir=str(temp_work_dir),
                        temp_ncm_path=str(temp_ncm_path),
                    )
                )
                watcher.cleanup_task_runtime_files(str(source_path))

            self.assertTrue(source_path.exists())
            self.assertTrue(output_path.exists())
            self.assertFalse(temp_work_dir.exists())
            task = watcher.get_task_snapshots()[0]
            self.assertIsNone(task["decoded_path"])
            self.assertEqual(task["generated_paths"], [])

    def test_retry_failed_ncm_cleans_old_temp_runtime_before_requeue(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(source_dir) / "song.ncm"
            temp_work_dir = Path(temp_dir) / "old-task"
            decoded_path = temp_work_dir / "song.flac"

            source_path.write_bytes(b"source")
            temp_work_dir.mkdir()
            decoded_path.write_bytes(b"decoded")

            with patch("watcher.NCM_TEMP_DIR", temp_dir):
                self.assertTrue(
                    watcher.add_pending_file(
                        str(source_path),
                        status=watcher.FAILED_STATUS,
                    )
                )
                self.assertTrue(
                    watcher.set_pending_file_runtime_data(
                        str(source_path),
                        decoded_path=str(decoded_path),
                        generated_paths=[str(decoded_path)],
                        temp_work_dir=str(temp_work_dir),
                    )
                )
                summary = watcher.retry_failed_files([str(source_path)])

            self.assertEqual(summary["requeued_count"], 1)
            self.assertFalse(temp_work_dir.exists())
            task = watcher.get_task_snapshots()[0]
            self.assertEqual(task["status"], watcher.QUEUED_STATUS)
            self.assertIsNone(task["decoded_path"])


class ReleaseConfigurationTests(unittest.TestCase):

    def test_release_version_is_patch_baseline(self):
        self.assertEqual(APP_VERSION, "5.0 Internal Test")
        self.assertEqual(
            APP_WINDOW_TITLE,
            "CherryQ Audio Converter v5.0 Internal Test",
        )

    def test_release_package_basename_is_versioned(self):
        self.assertEqual(
            APP_PACKAGE_BASENAME,
            "CherryQ_Audio_Converter_v5.0_internal_test",
        )

    def test_spec_only_packages_required_external_tools(self):
        spec_text = Path("CherryQ_Audio_Converter.spec").read_text(
            encoding="utf-8"
        )

        self.assertIn("Tools/ffmpeg/bin/ffmpeg.exe", spec_text)
        self.assertIn("Tools/ncmdump/ncmdump.exe", spec_text)
        self.assertIn("name=APP_PACKAGE_BASENAME", spec_text)
        self.assertNotIn("('Tools', 'Tools')", spec_text)

    def test_release_build_script_uses_versioned_outputs_and_required_docs(self):
        build_script = Path("build_release.ps1").read_text(encoding="utf-8")

        self.assertIn('Join-Path $Root "CHANGELOG.md"', build_script)
        self.assertIn('Join-Path $Root "Known_Issues.md"', build_script)
        self.assertIn('Join-Path $Root "config.example.json"', build_script)
        self.assertIn("APP_PACKAGE_BASENAME", build_script)
        self.assertIn("APP_RELEASE_NOTES_NAME", build_script)
        self.assertIn("AudioEditor_Output", build_script)

    def test_release_audit_docs_exist(self):
        self.assertTrue(Path("README.md").is_file())
        self.assertTrue(Path("CHANGELOG.md").is_file())
        self.assertTrue(Path(APP_RELEASE_NOTES_NAME).is_file())
        self.assertTrue(Path("Known_Issues.md").is_file())
        self.assertTrue(Path("config.example.json").is_file())


class ConfigPitchShiftTests(unittest.TestCase):

    def test_string_false_is_false_for_startup_booleans(self):
        with patch(
            "config.load_config",
            return_value={
                "auto_start_monitor": "False",
                "scan_existing_on_start": "False",
            },
        ):
            self.assertFalse(config.get_auto_start_monitor())
            self.assertFalse(config.get_scan_existing_on_start())

    def test_pitch_shift_config_fields_are_ui_reserved_only(self):
        self.assertIn("pitch_shift_enabled", config.DEFAULT_CONFIG)
        self.assertIn("pitch_shift_semitones", config.DEFAULT_CONFIG)
        self.assertFalse(hasattr(config, "get_pitch_shift_enabled"))
        self.assertFalse(hasattr(config, "get_pitch_shift_semitones"))

    def test_audio_output_device_config_fields_are_available(self):
        merged = config._merge_with_default({})
        self.assertIn("audio_output_device_id", merged)
        self.assertIn("audio_output_device_name", merged)

        with patch(
            "config.load_config",
            return_value={
                "audio_output_device_id": "device-1",
                "audio_output_device_name": "扬声器",
            },
        ):
            self.assertEqual(config.get_audio_output_device_id(), "device-1")
            self.assertEqual(config.get_audio_output_device_name(), "扬声器")


class FormatConfigurationTests(unittest.TestCase):

    def test_target_format_options_are_centralized_and_stable(self):
        self.assertEqual(
            formats.get_target_format_options(),
            ["mp3", "flac", "wav", "aac", "m4a", "ogg", "opus"],
        )

    def test_invalid_config_target_format_falls_back_to_flac(self):
        merged = config._merge_with_default({"target_format": "xyz"})
        self.assertEqual(merged["target_format"], "flac")

    def test_editor_output_folder_default_is_independent(self):
        merged = config._merge_with_default({})
        self.assertIn("editor_output_folder", merged)
        self.assertNotEqual(merged["editor_output_folder"], merged["output_folder"])
        self.assertTrue(merged["editor_output_folder"].endswith("AudioEditor_Output"))
        self.assertIn("editor_temp_folder", merged)
        self.assertTrue(merged["editor_temp_folder"].endswith(os.path.join("Temp", "Editor")))
        self.assertIn("editor_browser_folder", merged)
        self.assertEqual(merged["editor_browser_folder"], "")
        self.assertIn("editor_project_folders", merged)
        self.assertEqual(merged["editor_project_folders"], [])
        self.assertFalse(merged["editor_browser_collapsed"])

    def test_legacy_editor_browser_folder_migrates_to_project_folders(self):
        merged = config._merge_with_default({"editor_browser_folder": "D:/Music/House"})
        self.assertEqual(merged["editor_project_folders"], ["D:/Music/House"])

    def test_source_format_labels_are_centralized(self):
        self.assertEqual(formats.get_source_format("song.opus"), "OPUS")
        self.assertEqual(formats.get_source_format("song.NCM"), "NCM")

    def test_editor_audio_formats_exclude_ncm_and_lrc(self):
        self.assertTrue(formats.is_supported_editor_audio_file("song.mp3"))
        self.assertTrue(formats.is_supported_editor_audio_file("song.wma"))
        self.assertTrue(formats.is_supported_editor_audio_file("song.alac"))
        self.assertFalse(formats.is_supported_editor_audio_file("song.ncm"))
        self.assertFalse(formats.is_supported_editor_audio_file("song.lrc"))

    def test_target_format_metadata_for_m4a_and_opus(self):
        self.assertEqual(formats.get_target_extension("m4a"), ".m4a")
        self.assertEqual(formats.get_ffmpeg_args_for_target("m4a"), ["-c:a", "aac"])
        self.assertEqual(formats.get_target_extension("opus"), ".opus")


class LrcTimestampParsingTests(unittest.TestCase):

    def test_parse_lrc_timestamps_supports_common_formats(self):
        from ui.audio_editor import parse_lrc_timestamps

        entries = parse_lrc_timestamps(
            "[ar:artist]\n"
            '{"t":1,"c":[{"tx":"meta"}]}\n'
            "[00:12.34]first\n"
            "[00:12.340]same ms\n"
            "[1:03.20]minute\n"
            "plain text\n"
            "[00:30.00][00:45.500]repeat\n"
            "[00:50.00]\n"
        )

        self.assertEqual(
            [entry["time_ms"] for entry in entries],
            [12340, 12340, 30000, 45500, 50000, 63200],
        )
        self.assertEqual(entries[0]["line_index"], 2)
        self.assertEqual(entries[2]["text"], "repeat")
        self.assertEqual(entries[4]["text"], "")

    def test_parse_lrc_timestamps_returns_empty_for_plain_text(self):
        from ui.audio_editor import parse_lrc_timestamps

        self.assertEqual(
            parse_lrc_timestamps("纯文本歌词\n[ar:metadata]\n{\"t\":1}"),
            [],
        )


class AudioEditorPitchBackendTests(unittest.TestCase):

    def test_process_pitch_shift_uses_explicit_output_path_and_ffmpeg_filter(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ffmpeg = root / "ffmpeg.exe"
            source = root / "source.flac"
            output = root / "out" / "source_pitch+1.flac"
            ffmpeg.write_bytes(b"ffmpeg")
            source.write_bytes(b"audio")

            def fake_run(command):
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with (
                patch("audio_editor_backend.FFMPEG_PATH", str(ffmpeg)),
                patch("audio_editor_backend.read_audio_info", return_value={"sample_rate_hz": 44100}),
                patch("audio_editor_backend._run_ffmpeg_command", side_effect=fake_run) as mock_run,
                patch("audio_editor_backend._ensure_audio_editor_output_created") as mock_ensure,
                patch(
                    "audio_editor_backend.copy_audio_cover",
                    return_value={"success": True, "copied": True, "error": None},
                ) as mock_copy_cover,
            ):
                result = audio_editor_backend.process_pitch_shift(
                    str(source),
                    str(output),
                    1,
                    preserve_metadata=True,
                )

            self.assertTrue(result["success"])
            self.assertEqual(result["output_path"], str(output))
            command = mock_run.call_args.args[0]
            self.assertIn("-y", command)
            self.assertIn("-map_metadata", command)
            self.assertIn("-filter:a", command)
            self.assertIn(str(output), command)
            self.assertTrue(any("asetrate=" in part for part in command))
            mock_ensure.assert_called_once_with(str(output))
            mock_copy_cover.assert_called_once_with(str(source), str(output))
            self.assertTrue(result["cover_copied"])
            self.assertEqual(result["warnings"], [])

    def test_process_pitch_shift_keeps_success_when_cover_copy_warns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ffmpeg = root / "ffmpeg.exe"
            source = root / "source.m4a"
            output = root / "source_pitch+1.m4a"
            ffmpeg.write_bytes(b"ffmpeg")
            source.write_bytes(b"audio")

            with (
                patch("audio_editor_backend.FFMPEG_PATH", str(ffmpeg)),
                patch("audio_editor_backend.read_audio_info", return_value={"sample_rate_hz": 44100}),
                patch(
                    "audio_editor_backend._run_ffmpeg_command",
                    return_value=SimpleNamespace(returncode=0, stdout="", stderr=""),
                ),
                patch("audio_editor_backend._ensure_audio_editor_output_created"),
                patch(
                    "audio_editor_backend.copy_audio_cover",
                    return_value={"success": False, "copied": False, "error": "unsupported"},
                ),
            ):
                result = audio_editor_backend.process_pitch_shift(str(source), str(output), 1)

            self.assertTrue(result["success"])
            self.assertFalse(result["cover_copied"])
            self.assertIn("封面复制失败", result["warnings"][0])

    def test_process_pitch_shift_failure_removes_empty_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ffmpeg = root / "ffmpeg.exe"
            source = root / "source.mp3"
            output = root / "source_pitch-1.mp3"
            ffmpeg.write_bytes(b"ffmpeg")
            source.write_bytes(b"audio")
            output.write_bytes(b"")

            with (
                patch("audio_editor_backend.FFMPEG_PATH", str(ffmpeg)),
                patch("audio_editor_backend.read_audio_info", return_value={"sample_rate_hz": 44100}),
                patch(
                    "audio_editor_backend._run_ffmpeg_command",
                    return_value=SimpleNamespace(returncode=1, stdout="", stderr="boom"),
                ),
            ):
                result = audio_editor_backend.process_pitch_shift(str(source), str(output), -1)

            self.assertFalse(result["success"])
            self.assertFalse(output.exists())
            self.assertIn("boom", result["error"])


class AudioMetadataTests(unittest.TestCase):

    def test_metadata_format_helpers(self):
        self.assertEqual(metadata.format_duration(222), "03:42")
        self.assertEqual(metadata.format_duration(3750), "01:02:30")
        self.assertEqual(metadata.format_duration(None), "-")
        self.assertEqual(metadata.format_file_size(3_690_987), "3.52 MB")
        self.assertEqual(metadata.format_bitrate(320000), "320 kbps")
        self.assertEqual(metadata.format_bitrate(None), "-")
        self.assertEqual(metadata.format_sample_rate(44100), "44.1 kHz")
        self.assertEqual(metadata.format_sample_rate(48000), "48 kHz")
        self.assertEqual(metadata.format_sample_rate(None), "-")
        self.assertEqual(metadata.format_bit_depth(16), "16 bit")
        self.assertEqual(metadata.format_bit_depth(None), "-")
        self.assertEqual(metadata.format_modified_time(None), "-")

    def test_flac_metadata_reads_case_insensitive_tags_and_technical_info(self):
        class FakeAudio:
            tags = {
                "TITLE": ["Song"],
                "ARTIST": ["Artist"],
                "ALBUM": ["Album"],
                "ALBUMARTIST": ["Album Artist"],
                "DATE": ["2026"],
                "GENRE": ["Pop"],
                "TRACKNUMBER": ["2/9"],
                "DISCNUMBER": ["1/2"],
                "BPM": ["128"],
                "INITIALKEY": ["Am"],
                "COMMENT": ["Review note"],
            }
            info = SimpleNamespace(
                length=265.2,
                sample_rate=48000,
                bitrate=None,
                channels=2,
                bits_per_sample=24,
                codec="FLAC",
            )
            pictures = [
                SimpleNamespace(data=b"cover-bytes", mime="image/jpeg"),
            ]

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "song.flac"
            source.write_bytes(b"fake flac")

            with patch("metadata.MutagenFile", return_value=FakeAudio()):
                result = metadata.read_audio_metadata(str(source))

        self.assertTrue(result["success"])
        self.assertEqual(result["format"], "FLAC")
        self.assertEqual(result["title"], "Song")
        self.assertEqual(result["artist"], "Artist")
        self.assertEqual(result["album"], "Album")
        self.assertEqual(result["albumartist"], "Album Artist")
        self.assertEqual(result["date"], "2026")
        self.assertEqual(result["genre"], "Pop")
        self.assertEqual(result["tracknumber"], "2/9")
        self.assertEqual(result["discnumber"], "1/2")
        self.assertEqual(result["bpm"], "128")
        self.assertEqual(result["initialkey"], "Am")
        self.assertEqual(result["comment"], "Review note")
        self.assertEqual(result["duration"], 265.2)
        self.assertEqual(result["sample_rate"], 48000)
        self.assertEqual(result["channels"], 2)
        self.assertEqual(result["bits_per_sample"], 24)
        self.assertEqual(result["codec"], "FLAC")
        self.assertEqual(result["container_format"], "FLAC")
        self.assertIsNotNone(result["modified_time"])
        self.assertEqual(result["cover_data"], b"cover-bytes")
        self.assertEqual(result["cover_mime"], "image/jpeg")
        self.assertEqual(result["cover_source"], "FLAC picture")

    def test_cover_preview_reader_only_reads_cover_data(self):
        class FakeAudio:
            tags = {}
            info = SimpleNamespace(length=1)
            pictures = [
                SimpleNamespace(data=b"preview-cover", mime="image/png"),
            ]

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "song.flac"
            source.write_bytes(b"fake flac")

            with patch("metadata.MutagenFile", return_value=FakeAudio()):
                result = metadata.read_audio_cover_preview(str(source))

        self.assertTrue(result["success"])
        self.assertEqual(result["cover_data"], b"preview-cover")
        self.assertEqual(result["cover_mime"], "image/png")

    def test_write_flac_metadata_updates_vorbis_comments(self):
        class FakeFlac(dict):
            saved = False

            def save(self):
                self.saved = True

        fake_audio = FakeFlac()

        with patch("metadata.FLAC", return_value=fake_audio):
            result = metadata.write_audio_metadata(
                "song.flac",
                {
                    "title": "New Title",
                    "artist": "New Artist",
                    "album": "Album",
                    "date": "2026",
                    "genre": "Pop",
                    "tracknumber": "2/9",
                },
            )

        self.assertTrue(result["success"])
        self.assertEqual(fake_audio["title"], ["New Title"])
        self.assertEqual(fake_audio["artist"], ["New Artist"])
        self.assertEqual(fake_audio["tracknumber"], ["2/9"])
        self.assertTrue(fake_audio.saved)

    def test_write_mp3_metadata_creates_id3_when_missing(self):
        class FakeNoHeader(Exception):
            pass

        class FakeFrame:
            def __init__(self, encoding, text):
                self.encoding = encoding
                self.text = text

        class FakeID3Tags:
            def __init__(self):
                self.deleted = []
                self.added = []
                self.saved_path = None

            def delall(self, frame_id):
                self.deleted.append(frame_id)

            def add(self, frame):
                self.added.append(frame.text)

            def save(self, path):
                self.saved_path = path

        created_tags = FakeID3Tags()

        def fake_id3(path=None):
            if path:
                raise FakeNoHeader("missing header")
            return created_tags

        with (
            patch("metadata.ID3", side_effect=fake_id3),
            patch("metadata.ID3NoHeaderError", FakeNoHeader),
            patch("metadata.TIT2", FakeFrame),
            patch("metadata.TPE1", FakeFrame),
            patch("metadata.TALB", FakeFrame),
            patch("metadata.TDRC", FakeFrame),
            patch("metadata.TCON", FakeFrame),
            patch("metadata.TRCK", FakeFrame),
        ):
            result = metadata.write_audio_metadata(
                "song.mp3",
                {
                    "title": "Title",
                    "artist": "Artist",
                    "album": "Album",
                    "date": "2026",
                    "genre": "Rock",
                    "tracknumber": "1",
                },
            )

        self.assertTrue(result["success"])
        self.assertEqual(created_tags.saved_path, "song.mp3")
        self.assertIn("TIT2", created_tags.deleted)
        self.assertIn("Title", created_tags.added)
        self.assertIn("Artist", created_tags.added)

    def test_write_wav_metadata_returns_unsupported_without_crashing(self):
        result = metadata.write_audio_metadata("song.wav", {"title": "Title"})

        self.assertFalse(result["success"])
        self.assertIn("暂不支持", result["error"])

    def test_write_mp3_cover_replaces_apic(self):
        class FakeAPIC:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class FakeTags:
            def __init__(self):
                self.deleted = []
                self.added = []
                self.saved_path = None

            def delall(self, frame_id):
                self.deleted.append(frame_id)

            def add(self, frame):
                self.added.append(frame)

            def save(self, path):
                self.saved_path = path

        tags = FakeTags()

        with (
            patch("metadata.MutagenFile", object()),
            patch("metadata.ID3", return_value=tags),
            patch("metadata.APIC", FakeAPIC),
        ):
            result = metadata.write_audio_cover("song.mp3", b"jpeg", "image/jpeg")

        self.assertTrue(result["success"])
        self.assertEqual(tags.deleted, ["APIC"])
        self.assertEqual(tags.added[0].kwargs["mime"], "image/jpeg")
        self.assertEqual(tags.added[0].kwargs["data"], b"jpeg")
        self.assertEqual(tags.saved_path, "song.mp3")

    def test_write_flac_cover_replaces_pictures(self):
        class FakePicture:
            pass

        class FakeFlac:
            def __init__(self, _path):
                self.cleared = False
                self.pictures = []
                self.saved = False

            def clear_pictures(self):
                self.cleared = True

            def add_picture(self, picture):
                self.pictures.append(picture)

            def save(self):
                self.saved = True

        fake_audio = FakeFlac("song.flac")

        with (
            patch("metadata.MutagenFile", object()),
            patch("metadata.FLAC", return_value=fake_audio),
            patch("metadata.Picture", FakePicture),
        ):
            result = metadata.write_audio_cover("song.flac", b"png", "image/png")

        self.assertTrue(result["success"])
        self.assertTrue(fake_audio.cleared)
        self.assertEqual(fake_audio.pictures[0].type, 3)
        self.assertEqual(fake_audio.pictures[0].mime, "image/png")
        self.assertEqual(fake_audio.pictures[0].data, b"png")
        self.assertTrue(fake_audio.saved)

    def test_remove_mp4_cover_deletes_covr(self):
        class FakeMP4(dict):
            def __init__(self, _path):
                super().__init__({"covr": [b"old"]})
                self.saved = False

            def save(self):
                self.saved = True

        fake_audio = FakeMP4("song.m4a")

        with (
            patch("metadata.MutagenFile", object()),
            patch("metadata.MP4", return_value=fake_audio),
        ):
            result = metadata.remove_audio_cover("song.m4a")

        self.assertTrue(result["success"])
        self.assertNotIn("covr", fake_audio)
        self.assertTrue(fake_audio.saved)

    def test_ogg_cover_write_reports_missing_file_without_crashing(self):
        with patch("metadata.MutagenFile", object()):
            result = metadata.write_audio_cover("song.ogg", b"cover", "image/jpeg")

        self.assertFalse(result["success"])
        self.assertTrue(result["error"])
        self.assertNotIn("暂不支持", result["error"])

    def test_copy_audio_cover_writes_existing_cover_to_target(self):
        with (
            patch(
                "metadata.read_audio_metadata",
                return_value={
                    "success": True,
                    "cover_data": b"cover",
                    "cover_mime": "image/jpeg",
                    "error": None,
                },
            ) as mock_read,
            patch(
                "metadata.write_audio_cover",
                return_value={"success": True, "error": None},
            ) as mock_write,
        ):
            result = metadata.copy_audio_cover("source.mp3", "target.mp3")

        self.assertTrue(result["success"])
        self.assertTrue(result["copied"])
        mock_read.assert_called_once_with("source.mp3")
        mock_write.assert_called_once_with("target.mp3", b"cover", "image/jpeg")

    def test_copy_audio_cover_noops_when_source_has_no_cover(self):
        with (
            patch(
                "metadata.read_audio_metadata",
                return_value={
                    "success": True,
                    "cover_data": None,
                    "cover_mime": None,
                    "error": None,
                },
            ),
            patch("metadata.write_audio_cover") as mock_write,
        ):
            result = metadata.copy_audio_cover("source.flac", "target.flac")

        self.assertTrue(result["success"])
        self.assertFalse(result["copied"])
        mock_write.assert_not_called()


class AudioEditorWorkspaceBoundaryTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_player_is_unavailable_before_file_selection(self):
        from ui.audio_editor import AudioEditorWorkspace

        widget = AudioEditorWorkspace()
        self.assertFalse(widget.play_pause_button.isEnabled())
        self.assertFalse(widget.stop_button.isEnabled())
        self.assertEqual(widget.file_name_value.text(), "尚未导入音频文件")
        self.assertIn("尚未导入音频文件", widget.stage_note.text())
        self.assertEqual(widget.lyrics_preview.toPlainText(), "未加载歌词。")
        self.assertEqual(widget.workspace_tabs.count(), 3)
        self.assertEqual(
            [widget.workspace_tabs.tabText(index) for index in range(widget.workspace_tabs.count())],
            ["元数据", "歌词编辑", "升降调"],
        )
        self.assertNotIn(
            "文件信息整理",
            [widget.workspace_tabs.tabText(index) for index in range(widget.workspace_tabs.count())],
        )
        self.assertNotIn(
            "音频内容处理",
            [widget.workspace_tabs.tabText(index) for index in range(widget.workspace_tabs.count())],
        )
        self.assertEqual(widget.playback_source_type, "none")
        self.assertEqual(widget.playback_source_value.text(), "未加载")
        self.assertEqual(widget.unsaved_state_value.text(), "暂无未导出修改")
        self.assertFalse(widget.return_current_playback_button.isEnabled())
        self.assertEqual(widget.audio_output_device_combo.itemText(0), "无输出")
        self.assertEqual(widget.audio_output_device_combo.itemText(1), "系统输出")
        self.assertEqual(widget.audio_output_device_combo.itemText(2).strip(), "系统默认输出")
        self.assertFalse(hasattr(widget, "refresh_audio_output_button"))
        widget.deleteLater()

    def test_workspace_export_dialog_uses_clear_radio_and_format_hint(self):
        from ui.audio_editor import AudioEditExportDialog

        default_path = os.path.join(tempfile.gettempdir(), "Song_lyrics.flac")
        browsed_path = os.path.join(tempfile.gettempdir(), "Song_custom.flac")
        dialog = AudioEditExportDialog("Song.flac", ["元数据", "歌词"], default_output_path=default_path)

        try:
            self.assertTrue(dialog.save_as_radio.isChecked())
            self.assertFalse(dialog.overwrite_radio.isChecked())
            self.assertEqual(dialog.export_mode(), "save_as")
            self.assertEqual(dialog.output_path(), default_path)
            self.assertTrue(dialog.output_path_edit.isEnabled())
            self.assertTrue(dialog.browse_output_button.isEnabled())
            self.assertFalse(dialog.export_format_combo.isEnabled())
            self.assertEqual(dialog.export_format_combo.currentText(), "保持原格式")
            self.assertIsNone(dialog.target_format())
            self.assertIn("QRadioButton::indicator:checked", dialog.styleSheet())
            self.assertIn("QComboBox#ExportFormatCombo::down-arrow", dialog.styleSheet())
            self.assertIn("格式转换将在后续版本支持", dialog.findChild(type(dialog.warning_label), "ExportDialogHint").text())

            with patch("ui.audio_editor.QFileDialog.getSaveFileName", return_value=(browsed_path, "")):
                dialog.browse_output_button.click()

            self.assertEqual(dialog.output_path(), os.path.normpath(browsed_path))

            dialog.overwrite_radio.setChecked(True)
            self.assertEqual(dialog.export_mode(), "overwrite")
            self.assertEqual(dialog.warning_label.property("danger"), True)
            self.assertIn("风险提示", dialog.warning_label.text())
            self.assertFalse(dialog.output_path_edit.isEnabled())
            self.assertFalse(dialog.browse_output_button.isEnabled())
            self.assertIn("不使用另存路径", dialog.output_path_hint.text())
        finally:
            dialog.deleteLater()

    def test_show_export_workspace_dialog_uses_dialog_path_without_second_save_dialog(self):
        from PySide6.QtWidgets import QDialog
        from ui.audio_editor import AudioEditorWorkspace

        captured = {}

        class FakeExportDialog:
            def __init__(self, file_name, dirty_labels, default_output_path="", parent=None):
                captured["file_name"] = file_name
                captured["dirty_labels"] = dirty_labels
                captured["default_output_path"] = default_output_path

            def exec(self):
                return QDialog.DialogCode.Accepted

            def export_mode(self):
                return "save_as"

            def target_format(self):
                return None

            def output_path(self):
                return captured["selected_path"]

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Song.flac"
            output_dir = root / "out"
            selected = output_dir / "Song_custom.flac"
            source.write_bytes(b"fake audio")
            widget = AudioEditorWorkspace()
            widget.editor_output_folder = str(output_dir)
            widget.current_audio_path = str(source)
            widget._begin_edit_workspace(str(source))
            widget.edit_workspace.mark_dirty("lyrics", {"text": "[00:01.00]line"})
            captured["selected_path"] = str(selected)

            with (
                patch("ui.audio_editor.AudioEditExportDialog", FakeExportDialog),
                patch("ui.audio_editor.QFileDialog.getSaveFileName") as mock_save_dialog,
                patch.object(widget, "export_current_workspace", return_value={"success": True}) as mock_export,
            ):
                self.assertEqual(widget.show_export_workspace_dialog(), {"success": True})

            mock_save_dialog.assert_not_called()
            mock_export.assert_called_once_with(
                mode="save_as",
                output_path=str(selected),
                target_format=None,
                allow_overwrite_output=False,
            )
            self.assertEqual(captured["file_name"], "Song.flac")
            self.assertEqual(captured["dirty_labels"], ["歌词"])
            self.assertEqual(Path(captured["default_output_path"]), output_dir / "Song_lyrics.flac")
            widget.edit_workspace.clear_changes(remove_pending=True)
            widget.current_audio_path = None
            widget.deleteLater()

    def test_workspace_export_save_as_rejects_source_path(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Song.flac"
            source.write_bytes(b"fake audio")
            widget = AudioEditorWorkspace()
            widget.current_audio_path = str(source)
            widget._begin_edit_workspace(str(source))
            widget.edit_workspace.mark_dirty("metadata", {"fields": {"title": "New"}})

            with (
                patch("ui.audio_editor.QMessageBox.warning") as mock_warning,
                patch("ui.audio_editor.shutil.copy2") as mock_copy,
            ):
                result = widget.export_current_workspace("save_as", output_path=str(source))

            self.assertFalse(result["success"])
            self.assertIn("改用覆盖原文件", result["error"])
            mock_warning.assert_called_once()
            mock_copy.assert_not_called()
            self.assertTrue(widget.edit_workspace.has_unsaved_changes)
            widget.edit_workspace.clear_changes(remove_pending=True)
            widget.current_audio_path = None
            widget.deleteLater()

    def test_workspace_export_save_as_existing_target_requires_explicit_overwrite(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Song.flac"
            output = root / "Song_edited.flac"
            source.write_bytes(b"fake audio")
            output.write_bytes(b"existing target")
            widget = AudioEditorWorkspace()
            widget.current_audio_path = str(source)
            widget._begin_edit_workspace(str(source))
            widget.edit_workspace.mark_dirty("metadata", {"fields": {"title": "New"}})

            with (
                patch("ui.audio_editor.QMessageBox.warning") as mock_warning,
                patch("ui.audio_editor.shutil.copy2") as mock_copy,
            ):
                result = widget.export_current_workspace("save_as", output_path=str(output))

            self.assertFalse(result["success"])
            self.assertIn("目标文件已存在", result["error"])
            mock_warning.assert_called_once()
            mock_copy.assert_not_called()
            self.assertEqual(output.read_bytes(), b"existing target")
            self.assertTrue(widget.edit_workspace.has_unsaved_changes)
            self.assertIn("metadata", widget.edit_workspace.dirty_flags)
            widget.edit_workspace.clear_changes(remove_pending=True)
            widget.current_audio_path = None
            widget.deleteLater()

    def test_workspace_export_save_as_failure_keeps_existing_target(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Song.flac"
            output = root / "Song_edited.flac"
            temp_output = root / ".Song_edited.exporting.tmp.flac"
            source.write_bytes(b"fake audio")
            output.write_bytes(b"existing target")
            widget = AudioEditorWorkspace()
            widget.current_audio_path = str(source)
            widget._begin_edit_workspace(str(source))
            widget.edit_workspace.mark_dirty("metadata", {"fields": {"title": "New"}})

            with (
                patch.object(
                    widget,
                    "_apply_workspace_pending_changes",
                    return_value={"success": False, "error": "write failed"},
                ),
                patch.object(widget, "reload_editor_player_source"),
                patch("ui.audio_editor.QMessageBox.warning") as mock_warning,
            ):
                result = widget.export_current_workspace(
                    "save_as",
                    output_path=str(output),
                    allow_overwrite_output=True,
                )

            self.assertFalse(result["success"])
            self.assertIn("write failed", result["error"])
            mock_warning.assert_called_once()
            self.assertEqual(output.read_bytes(), b"existing target")
            self.assertFalse(temp_output.exists())
            self.assertTrue(widget.edit_workspace.has_unsaved_changes)
            self.assertIn("metadata", widget.edit_workspace.dirty_flags)
            widget.edit_workspace.clear_changes(remove_pending=True)
            widget.current_audio_path = None
            widget.deleteLater()

    def test_workspace_overwrite_uses_source_folder_temp_file(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Song.flac"
            source.write_bytes(b"fake audio")
            widget = AudioEditorWorkspace()
            widget.current_audio_path = str(source)
            widget._begin_edit_workspace(str(source))
            widget.edit_workspace.mark_dirty("metadata", {"fields": {"title": "New"}})
            applied_paths = []

            def fake_apply(path):
                applied_paths.append(Path(path))
                return {"success": True, "error": None}

            with (
                patch.object(widget, "_apply_workspace_pending_changes", side_effect=fake_apply),
                patch.object(widget, "_load_audio_metadata"),
                patch.object(widget, "_load_initial_lyrics_for_audio"),
                patch.object(widget, "reload_editor_player_source"),
            ):
                result = widget.export_current_workspace("overwrite")

            self.assertTrue(result["success"])
            self.assertEqual(applied_paths, [root / ".Song.exporting.tmp.flac"])
            self.assertFalse((root / ".Song.exporting.tmp.flac").exists())
            self.assertTrue(any(Path(widget.edit_workspace.backup_dir).glob("Song.backup.flac")))
            self.assertFalse(widget.edit_workspace.has_unsaved_changes)
            widget.current_audio_path = None
            widget.deleteLater()

    def test_workspace_overwrite_failure_keeps_dirty_and_cleans_temp_file(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Song.flac"
            source.write_bytes(b"fake audio")
            widget = AudioEditorWorkspace()
            widget.current_audio_path = str(source)
            widget._begin_edit_workspace(str(source))
            widget.edit_workspace.mark_dirty("metadata", {"fields": {"title": "New"}})

            with (
                patch.object(
                    widget,
                    "_apply_workspace_pending_changes",
                    return_value={"success": False, "error": "write failed"},
                ),
                patch.object(widget, "reload_editor_player_source"),
                patch("ui.audio_editor.QMessageBox.warning") as mock_warning,
            ):
                result = widget.export_current_workspace("overwrite")

            self.assertFalse(result["success"])
            self.assertIn("write failed", result["error"])
            mock_warning.assert_called_once()
            self.assertTrue(widget.edit_workspace.has_unsaved_changes)
            self.assertIn("metadata", widget.edit_workspace.dirty_flags)
            self.assertFalse((root / ".Song.exporting.tmp.flac").exists())
            self.assertTrue(any(Path(widget.edit_workspace.backup_dir).glob("Song.backup.flac")))
            widget.edit_workspace.clear_changes(remove_pending=True)
            widget.current_audio_path = None
            widget.deleteLater()

    def test_workspace_export_blocks_unknown_dirty_flags_before_copying(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "sample.mp3"
            output = root / "sample_edited.mp3"
            source.write_bytes(b"fake audio")
            widget = AudioEditorWorkspace()
            widget.current_audio_path = str(source)
            widget._begin_edit_workspace(str(source))
            widget.edit_workspace.mark_dirty("future_magic", {"enabled": True})
            widget.refresh_editor_dirty_state()

            self.assertEqual(widget._workspace_dirty_labels(), ["其他修改"])

            with (
                patch("ui.audio_editor.shutil.copy2") as mock_copy,
                patch("ui.audio_editor.QMessageBox.warning") as mock_warning,
            ):
                result = widget.export_current_workspace("save_as", output_path=str(output))

            self.assertFalse(result["success"])
            self.assertIn("其他修改", result["error"])
            self.assertIn("暂未接入实际导出", result["error"])
            mock_copy.assert_not_called()
            mock_warning.assert_called_once()
            self.assertTrue(widget.edit_workspace.has_unsaved_changes)
            self.assertTrue(widget.export_workspace_button.isEnabled())
            widget.edit_workspace.clear_changes(remove_pending=True)
            widget.current_audio_path = None
            widget.deleteLater()

    def test_audio_output_device_refresh_lists_devices_and_restores_selection(self):
        from PySide6.QtCore import Qt
        from ui.audio_editor import AudioEditorWorkspace

        class FakeDevice:
            def __init__(self, device_id, name):
                self._device_id = device_id
                self._name = name

            def id(self):
                return self._device_id.encode("utf-8")

            def description(self):
                return self._name

        first = FakeDevice("speaker", "扬声器")
        second = FakeDevice("headset", "蓝牙耳机")
        widget = AudioEditorWorkspace()
        widget.current_audio_output_device_id = ""
        widget.saved_audio_output_device_id = "headset"

        with (
            patch.object(widget, "_available_audio_output_devices", return_value=[first, second]),
            patch.object(widget, "apply_audio_output_device", return_value=True) as mock_apply,
        ):
            widget.refresh_audio_output_devices()

        self.assertEqual(widget.audio_output_device_combo.itemText(0), "无输出")
        self.assertEqual(widget.audio_output_device_combo.itemText(1), "系统输出")
        self.assertEqual(widget.audio_output_device_combo.itemText(2).strip(), "系统默认输出")
        self.assertEqual(widget.audio_output_device_combo.itemText(3).strip(), "扬声器")
        self.assertEqual(widget.audio_output_device_combo.itemText(4).strip(), "蓝牙耳机")
        self.assertEqual(widget.audio_output_device_combo.itemText(5), "实验 / ASIO")
        self.assertEqual(widget.audio_output_device_combo.itemText(6).strip(), "ASIO 输出后端尚未接入")
        self.assertEqual(widget.audio_output_device_combo.currentIndex(), 4)
        self.assertTrue(widget.audio_output_device_combo.isEnabled())
        self.assertEqual(
            widget.audio_output_device_combo.itemData(4, Qt.ItemDataRole.ToolTipRole),
            "蓝牙耳机",
        )
        self.assertFalse(widget.audio_output_device_combo.model().item(0).isEnabled())
        self.assertFalse(widget.audio_output_device_combo.model().item(1).isEnabled())
        self.assertTrue(widget.audio_output_device_combo.model().item(2).isEnabled())
        self.assertTrue(widget.audio_output_device_combo.model().item(3).isEnabled())
        self.assertFalse(widget.audio_output_device_combo.model().item(5).isEnabled())
        self.assertFalse(widget.audio_output_device_combo.model().item(6).isEnabled())
        self.assertNotIn("headset", widget.audio_output_device_combo.toolTip())
        mock_apply.assert_not_called()
        widget.deleteLater()

    def test_audio_output_device_change_applies_selected_device(self):
        from ui.audio_editor import AudioEditorWorkspace

        class FakeDevice:
            def id(self):
                return b"speaker"

            def description(self):
                return "扬声器"

        device = FakeDevice()
        widget = AudioEditorWorkspace()
        device_index = widget._add_audio_output_combo_item(
            "  扬声器",
            "qt_output",
            device=device,
            enabled=True,
            tooltip="扬声器",
        )

        with patch.object(widget, "apply_audio_output_device", return_value=True) as mock_apply:
            widget.audio_output_device_combo.setCurrentIndex(device_index)

        mock_apply.assert_called_with(device, persist=True)
        widget.deleteLater()

    def test_audio_output_device_disabled_group_items_do_not_apply_device(self):
        from ui.audio_editor import AudioEditorWorkspace

        widget = AudioEditorWorkspace()
        header_index = widget._add_audio_output_combo_item(
            "实验 / ASIO",
            "header",
            enabled=False,
        )

        with patch.object(widget, "apply_audio_output_device", return_value=True) as mock_apply:
            widget.audio_output_device_combo.setCurrentIndex(header_index)
            widget.on_audio_output_device_changed(header_index)

        mock_apply.assert_not_called()
        widget.deleteLater()

    def test_audio_output_device_popup_refreshes_once_without_applying_device(self):
        from ui.audio_editor import AudioEditorWorkspace

        widget = AudioEditorWorkspace()

        with (
            patch.object(widget, "refresh_audio_output_devices") as mock_refresh,
            patch.object(widget, "apply_audio_output_device", return_value=True) as mock_apply,
        ):
            widget.audio_output_device_combo.showPopup()
            widget.audio_output_device_combo.hidePopup()

        mock_refresh.assert_called_once()
        mock_apply.assert_not_called()
        widget.deleteLater()

    def test_audio_output_device_same_selection_does_not_reset_device(self):
        from ui.audio_editor import AudioEditorWorkspace

        class FakeDevice:
            def id(self):
                return b"speaker"

            def description(self):
                return "扬声器"

        class FakeAudioOutput:
            def __init__(self):
                self.set_device_calls = 0
                self._volume = 0.8

            def volume(self):
                return self._volume

            def setVolume(self, volume):
                self._volume = volume

            def setDevice(self, _device):
                self.set_device_calls += 1

        device = FakeDevice()
        widget = AudioEditorWorkspace()
        fake_output = FakeAudioOutput()
        widget.audio_output = fake_output
        widget.audio_output_device_applied = True
        widget.current_audio_output_device_id = "speaker"
        widget.current_audio_output_device_name = "扬声器"

        self.assertTrue(widget.apply_audio_output_device(device, persist=False))
        self.assertEqual(fake_output.set_device_calls, 0)
        widget.deleteLater()

    def test_select_audio_file_loads_preview_without_watcher_queue(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "sample.mp3"
            source.write_bytes(b"fake audio")
            widget = AudioEditorWorkspace()

            with (
                patch(
                    "ui.audio_editor.QFileDialog.getOpenFileName",
                    return_value=(str(source), ""),
                ),
                patch("watcher.add_pending_file") as mock_add_task,
                patch("watcher.handle_detected_file") as mock_handle_detected,
            ):
                widget.select_audio_file()

            self.assertEqual(widget.current_audio_path, str(source))
            self.assertEqual(widget.file_name_value.text(), "sample.mp3")
            self.assertEqual(widget.file_format_value.text(), "MP3")
            self.assertEqual(widget.playback_source_type, "current_file")
            self.assertEqual(widget.playback_source_value.text(), "原音频")
            self.assertFalse(widget.return_current_playback_button.isEnabled())
            self.assertTrue(widget.play_pause_button.isEnabled())
            self.assertTrue(widget.stop_button.isEnabled())
            self.assertIn("编辑文件：sample.mp3", widget.stage_note.text())
            self.assertNotIn("尚未导入音频文件", widget.stage_note.text())
            mock_add_task.assert_not_called()
            mock_handle_detected.assert_not_called()
            widget.clear_current_audio()
            self.app.processEvents()
            self.assertIn("尚未导入音频文件", widget.stage_note.text())
            widget.deleteLater()

    def test_pitch_preview_playback_source_does_not_replace_current_audio(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.mp3"
            preview = root / "source_preview_pitch+1.mp3"
            source.write_bytes(b"audio")
            preview.write_bytes(b"preview")
            widget = AudioEditorWorkspace()
            widget.load_audio_file(str(source))

            try:
                widget.set_pitch_shift_value(1)
                widget.pitch_preview_path = str(preview)
                widget.current_pitch_preview_path = str(preview)
                widget.current_pitch_preview_semitones = 1
                widget.reload_editor_player_source(
                    str(preview),
                    source_type="pitch_preview",
                    source_label="升降调试听缓存（升 1 key）",
                )

                self.assertEqual(widget.current_audio_path, str(source))
                self.assertEqual(widget.playback_source_path, str(preview))
                self.assertEqual(widget.playback_source_type, "pitch_preview")
                self.assertIn("升降调试听缓存", widget.playback_source_value.text())
                self.assertTrue(widget.return_current_playback_button.isEnabled())

                self.assertTrue(widget.return_to_current_audio_playback())
                self.assertEqual(widget.current_audio_path, str(source))
                self.assertEqual(widget.playback_source_type, "current_file")
                self.assertEqual(widget.playback_source_value.text(), "原音频")
            finally:
                widget.clear_current_audio()
                self.app.processEvents()
                widget.deleteLater()

    def test_pitch_export_without_autoload_keeps_current_audio_and_records_export(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.mp3"
            exported = root / "source_pitch+1.mp3"
            source.write_bytes(b"audio")
            exported.write_bytes(b"exported")
            widget = AudioEditorWorkspace()
            widget.load_audio_file(str(source))
            widget.pitch_auto_load_checkbox.setChecked(False)
            widget.pitch_shift_mode = "export"
            widget.pitch_shift_original_path = str(source)
            widget.pitch_shift_output_path = str(exported)
            widget.pitch_shift_player_state = {"position": 0, "volume": 0.8}

            try:
                widget._on_pitch_shift_finished({
                    "success": True,
                    "mode": "export",
                    "output_path": str(exported),
                    "cover_copied": True,
                    "warnings": [],
                })

                self.assertEqual(widget.current_audio_path, str(source))
                self.assertEqual(widget.last_exported_audio_path, str(exported))
                self.assertEqual(widget.playback_source_type, "current_file")
                self.assertEqual(widget.pitch_export_path_value.toolTip(), str(exported))
            finally:
                widget.clear_current_audio()
                self.app.processEvents()
                widget.deleteLater()

    def test_audio_import_displays_metadata_and_cover_without_watcher_queue(self):
        from PySide6.QtCore import QBuffer, QByteArray, QIODevice
        from PySide6.QtGui import QColor, QPixmap
        from ui.audio_editor import AudioEditorWorkspace

        pixmap = QPixmap(1, 1)
        pixmap.fill(QColor("red"))
        png_bytes = QByteArray()
        buffer = QBuffer(png_bytes)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        pixmap.save(buffer, "PNG")
        png_data = bytes(png_bytes)

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "sample.flac"
            source.write_bytes(b"fake audio")
            widget = AudioEditorWorkspace()

            fake_metadata = {
                "success": True,
                "path": str(source),
                "filename": source.name,
                "format": "FLAC",
                "container_format": "FLAC",
                "codec": "FLAC",
                "title": "Title",
                "artist": "Artist A / Artist B",
                "album": "Album",
                "albumartist": "Album Artist",
                "date": "2024",
                "genre": "Dance",
                "tracknumber": "1/10",
                "discnumber": "1/2",
                "bpm": "126",
                "initialkey": "Gm",
                "comment": "Read-only comment",
                "duration": 222,
                "sample_rate": 44100,
                "bitrate": 987000,
                "channels": 2,
                "bits_per_sample": 16,
                "file_size": 3_690_987,
                "modified_time": 1767225600,
                "cover_data": png_data,
                "cover_mime": "image/png",
                "cover_source": "FLAC picture",
                "composer": "Composer A",
                "error": None,
            }

            with (
                patch("ui.audio_editor.read_audio_metadata", return_value=fake_metadata),
                patch("watcher.handle_detected_file") as mock_handle_detected,
            ):
                self.assertTrue(widget.load_audio_file(str(source)))

            try:
                self.assertEqual(widget.metadata_title_value.text(), "Title")
                self.assertEqual(widget.metadata_artist_value.text(), "Artist A / Artist B")
                self.assertEqual(widget.metadata_filename_value.text(), source.name)
                self.assertEqual(widget.metadata_path_value.toolTip(), str(source))
                self.assertEqual(widget.metadata_album_artist_value.text(), "Album Artist")
                self.assertEqual(widget.metadata_disc_value.text(), "1/2")
                self.assertEqual(widget.metadata_bpm_value.text(), "126")
                self.assertEqual(widget.metadata_key_value.text(), "Gm")
                self.assertEqual(widget.metadata_comment_value.text(), "Read-only comment")
                self.assertEqual(widget.metadata_format_value.text(), "FLAC")
                self.assertEqual(widget.metadata_container_value.text(), "FLAC")
                self.assertEqual(widget.metadata_codec_value.text(), "FLAC")
                self.assertEqual(widget.metadata_file_size_value.text(), "3.52 MB")
                self.assertEqual(widget.metadata_duration_value.text(), "03:42")
                self.assertEqual(widget.metadata_sample_rate_value.text(), "44.1 kHz")
                self.assertEqual(widget.metadata_bitrate_value.text(), "987 kbps")
                self.assertEqual(widget.metadata_channels_value.text(), "2")
                self.assertEqual(widget.metadata_bit_depth_value.text(), "16 bit")
                self.assertEqual(widget.metadata_status_value.text(), "已读取")
                self.assertEqual(widget.cover_source_value.text(), "FLAC picture")
                self.assertIn("image/png", widget.cover_label.toolTip())
                self.assertFalse(widget.cover_label.pixmap().isNull())
                self.assertEqual(widget.cover_label.width(), 140)
                self.assertEqual(widget.cover_label.height(), 140)
                self.assertEqual(widget.custom_metadata_tags["composer"], "Composer A")
                self.assertEqual(widget.custom_metadata_tree.topLevelItemCount(), 1)
                mock_handle_detected.assert_not_called()
            finally:
                widget.clear_current_audio()
                self.app.processEvents()
                widget.deleteLater()

    def test_metadata_failure_does_not_block_audio_import_or_lyrics(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "sample.mp3"
            lrc = root / "sample.lrc"
            source.write_bytes(b"fake audio")
            lrc.write_text("[00:01.00]line", encoding="utf-8")
            widget = AudioEditorWorkspace()

            with patch(
                "ui.audio_editor.read_audio_metadata",
                return_value={"success": False, "error": "broken metadata"},
            ):
                self.assertTrue(widget.load_audio_file(str(source)))

            self.assertEqual(widget.current_audio_path, str(source))
            self.assertTrue(widget.play_pause_button.isEnabled())
            self.assertEqual(widget.metadata_status_value.text(), "读取失败")
            self.assertIn("音频信息读取失败：broken metadata", widget.error_status_value.text())
            self.assertEqual(widget.metadata_title_value.text(), "")
            self.assertEqual(widget.metadata_duration_value.text(), "-")
            self.assertEqual(widget.cover_label.text(), "未读取到封面")
            self.assertEqual(widget.pending_lrc_path, str(lrc))
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_switching_audio_clears_stale_metadata_when_new_read_fails(self):
        from PySide6.QtCore import QBuffer, QByteArray, QIODevice
        from PySide6.QtGui import QColor, QPixmap
        from ui.audio_editor import AudioEditorWorkspace

        pixmap = QPixmap(1, 1)
        pixmap.fill(QColor("blue"))
        png_bytes = QByteArray()
        buffer = QBuffer(png_bytes)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        pixmap.save(buffer, "PNG")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first.mp3"
            second = root / "second.flac"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            widget = AudioEditorWorkspace()

            first_metadata = {
                "success": True,
                "path": str(first),
                "filename": first.name,
                "format": "MP3",
                "container_format": "MP3",
                "codec": "MPEG",
                "title": "Old Title",
                "artist": "Old Artist",
                "album": "Old Album",
                "albumartist": "Old Album Artist",
                "date": "2025",
                "genre": "Rock",
                "tracknumber": "1",
                "discnumber": "1/1",
                "bpm": "120",
                "initialkey": "C",
                "comment": "old comment",
                "duration": 180,
                "sample_rate": 44100,
                "bitrate": 320000,
                "channels": 2,
                "bits_per_sample": None,
                "file_size": 1234,
                "modified_time": 1767225600,
                "cover_data": bytes(png_bytes),
                "cover_mime": "image/png",
                "cover_source": "APIC",
                "error": None,
            }
            failed_metadata = {"success": False, "error": "broken metadata"}

            try:
                with patch(
                    "ui.audio_editor.read_audio_metadata",
                    side_effect=[first_metadata, failed_metadata],
                ):
                    self.assertTrue(widget.load_audio_file(str(first)))
                    self.assertEqual(widget.metadata_title_value.text(), "Old Title")
                    self.assertFalse(widget.cover_label.pixmap().isNull())
                    self.assertTrue(widget.load_audio_file(str(second)))

                self.assertEqual(widget.metadata_title_value.text(), "")
                self.assertEqual(widget.metadata_artist_value.text(), "")
                self.assertEqual(widget.metadata_album_value.text(), "")
                self.assertEqual(widget.metadata_filename_value.text(), "-")
                self.assertEqual(widget.metadata_path_value.text(), "-")
                self.assertEqual(widget.metadata_album_artist_value.text(), "")
                self.assertEqual(widget.metadata_disc_value.text(), "")
                self.assertEqual(widget.metadata_bpm_value.text(), "")
                self.assertEqual(widget.metadata_key_value.text(), "")
                self.assertEqual(widget.metadata_comment_value.text(), "")
                self.assertEqual(widget.metadata_container_value.text(), "-")
                self.assertEqual(widget.metadata_codec_value.text(), "-")
                self.assertEqual(widget.metadata_status_value.text(), "读取失败")
                self.assertEqual(widget.cover_label.text(), "未读取到封面")
                self.assertEqual(widget.cover_source_value.text(), "-")
                self.assertIn("音频信息读取失败：broken metadata", widget.error_status_value.text())
            finally:
                widget.clear_current_audio()
                self.app.processEvents()
                widget.deleteLater()

    def test_clear_current_audio_resets_metadata_display(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "sample.wav"
            source.write_bytes(b"fake audio")
            widget = AudioEditorWorkspace()

            with patch(
                "ui.audio_editor.read_audio_metadata",
                return_value={
                    "success": True,
                    "path": str(source),
                    "filename": source.name,
                    "format": "WAV",
                    "container_format": "WAV",
                    "codec": "PCM",
                    "title": "Title",
                    "artist": "",
                    "album": "",
                    "albumartist": "Album Artist",
                    "date": "",
                    "genre": "",
                    "tracknumber": "",
                    "discnumber": "1/1",
                    "bpm": "100",
                    "initialkey": "D",
                    "comment": "temporary",
                    "duration": None,
                    "sample_rate": None,
                    "bitrate": None,
                    "channels": None,
                    "bits_per_sample": None,
                    "file_size": None,
                    "modified_time": 1767225600,
                    "cover_data": None,
                    "cover_mime": None,
                    "cover_source": "",
                    "error": None,
                },
            ):
                self.assertTrue(widget.load_audio_file(str(source)))

            self.assertEqual(widget.metadata_title_value.text(), "Title")
            widget.clear_current_audio()
            self.app.processEvents()
            self.assertEqual(widget.metadata_title_value.text(), "")
            self.assertEqual(widget.metadata_filename_value.text(), "-")
            self.assertEqual(widget.metadata_path_value.text(), "-")
            self.assertEqual(widget.metadata_album_artist_value.text(), "")
            self.assertEqual(widget.metadata_disc_value.text(), "")
            self.assertEqual(widget.metadata_bpm_value.text(), "")
            self.assertEqual(widget.metadata_key_value.text(), "")
            self.assertEqual(widget.metadata_comment_value.text(), "")
            self.assertEqual(widget.metadata_container_value.text(), "-")
            self.assertEqual(widget.metadata_codec_value.text(), "-")
            self.assertEqual(widget.metadata_status_value.text(), "未读取")
            self.assertEqual(widget.cover_label.text(), "未读取到封面")
            self.assertEqual(widget.cover_source_value.text(), "-")
            widget.deleteLater()

    def test_metadata_edit_mode_tracks_dirty_without_writing_file(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "sample.mp3"
            source.write_bytes(b"fake audio")
            widget = AudioEditorWorkspace()

            fake_metadata = {
                "success": True,
                "format": "MP3",
                "title": "Title",
                "artist": "Artist",
                "album": "",
                "date": "",
                "genre": "",
                "tracknumber": "",
                "duration": None,
                "sample_rate": None,
                "bitrate": None,
                "channels": None,
                "bits_per_sample": None,
                "file_size": None,
                "cover_data": None,
                "cover_mime": None,
                "error": None,
            }

            with patch("ui.audio_editor.read_audio_metadata", return_value=fake_metadata):
                self.assertTrue(widget.load_audio_file(str(source)))

            with patch("ui.audio_editor.write_audio_metadata") as mock_write:
                self.assertTrue(widget.metadata_title_value.isReadOnly())
                widget.toggle_metadata_edit_mode()
                self.assertFalse(widget.metadata_title_value.isReadOnly())
                widget.metadata_title_value.setText("New Title")
                self.assertTrue(widget.metadata_dirty)
                self.assertEqual(widget.metadata_status_value.text(), "有未导出修改")
                widget.toggle_metadata_edit_mode()

            self.assertTrue(widget.metadata_title_value.isReadOnly())
            self.assertTrue(widget.metadata_dirty)
            self.assertEqual(widget.metadata_edit_button.text(), "编辑信息")
            mock_write.assert_not_called()
            widget.edit_workspace.clear_changes(remove_pending=True)
            widget.metadata_dirty = False
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_metadata_reverting_to_original_clears_workspace_dirty(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "sample.mp3"
            source.write_bytes(b"fake audio")
            widget = AudioEditorWorkspace()

            fake_metadata = {
                "success": True,
                "format": "MP3",
                "title": "Original Title",
                "artist": "",
                "album": "",
                "albumartist": "",
                "date": "",
                "genre": "",
                "tracknumber": "",
                "discnumber": "",
                "bpm": "",
                "initialkey": "",
                "comment": "",
                "duration": None,
                "sample_rate": None,
                "bitrate": None,
                "channels": None,
                "bits_per_sample": None,
                "file_size": None,
                "cover_data": None,
                "cover_mime": None,
                "error": None,
            }

            with patch("ui.audio_editor.read_audio_metadata", return_value=fake_metadata):
                self.assertTrue(widget.load_audio_file(str(source)))

            widget.toggle_metadata_edit_mode()
            widget.metadata_title_value.setText("Changed Title")
            self.assertTrue(widget.metadata_dirty)
            self.assertIn("metadata", widget.edit_workspace.dirty_flags)
            self.assertTrue(os.path.isfile(widget.edit_workspace.pending_changes_path))
            self.assertTrue(widget.export_workspace_button.isEnabled())

            widget.metadata_title_value.setText("Original Title")
            self.assertFalse(widget.metadata_dirty)
            self.assertNotIn("metadata", widget.edit_workspace.dirty_flags)
            self.assertFalse(widget.edit_workspace.has_unsaved_changes)
            self.assertFalse(os.path.isfile(widget.edit_workspace.pending_changes_path))
            self.assertFalse(widget.export_workspace_button.isEnabled())

            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_extended_metadata_fields_enter_pending_metadata(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "sample.flac"
            source.write_bytes(b"fake audio")
            widget = AudioEditorWorkspace()

            fake_metadata = {
                "success": True,
                "format": "FLAC",
                "title": "Title",
                "artist": "",
                "album": "",
                "albumartist": "Original Album Artist",
                "date": "",
                "genre": "",
                "tracknumber": "",
                "discnumber": "1/1",
                "bpm": "120",
                "initialkey": "C",
                "comment": "old note",
                "duration": None,
                "sample_rate": None,
                "bitrate": None,
                "channels": None,
                "bits_per_sample": None,
                "file_size": None,
                "cover_data": None,
                "cover_mime": None,
                "error": None,
            }

            with patch("ui.audio_editor.read_audio_metadata", return_value=fake_metadata):
                self.assertTrue(widget.load_audio_file(str(source)))

            widget.toggle_metadata_edit_mode()
            widget.metadata_album_artist_value.setText("New Album Artist")
            widget.metadata_disc_value.setText("2/2")
            widget.metadata_bpm_value.setText("128")
            widget.metadata_key_value.setText("Am")
            widget.metadata_comment_value.setPlainText("new note")

            pending_fields = widget.edit_workspace.pending_metadata["fields"]
            self.assertEqual(pending_fields["albumartist"], "New Album Artist")
            self.assertEqual(pending_fields["discnumber"], "2/2")
            self.assertEqual(pending_fields["bpm"], "128")
            self.assertEqual(pending_fields["initialkey"], "Am")
            self.assertEqual(pending_fields["comment"], "new note")

            widget.edit_workspace.clear_changes(remove_pending=True)
            widget.metadata_dirty = False
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_custom_metadata_add_then_remove_clears_workspace_dirty(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "sample.mp3"
            source.write_bytes(b"fake audio")
            widget = AudioEditorWorkspace()

            fake_metadata = {
                "success": True,
                "format": "MP3",
                "title": "",
                "artist": "",
                "album": "",
                "albumartist": "",
                "date": "",
                "genre": "",
                "tracknumber": "",
                "discnumber": "",
                "bpm": "",
                "initialkey": "",
                "comment": "",
                "duration": None,
                "sample_rate": None,
                "bitrate": None,
                "channels": None,
                "bits_per_sample": None,
                "file_size": None,
                "cover_data": None,
                "cover_mime": None,
                "error": None,
            }

            with patch("ui.audio_editor.read_audio_metadata", return_value=fake_metadata):
                self.assertTrue(widget.load_audio_file(str(source)))

            widget.custom_metadata_name_edit.setText("mood")
            widget.custom_metadata_value_edit.setText("warm")
            self.assertTrue(widget.add_custom_metadata_tag())
            self.assertTrue(widget.metadata_dirty)
            self.assertIn("metadata", widget.edit_workspace.dirty_flags)

            widget.custom_metadata_tree.setCurrentItem(widget.custom_metadata_tree.topLevelItem(0))
            self.assertTrue(widget.remove_selected_custom_metadata_tag())
            self.assertFalse(widget.metadata_dirty)
            self.assertNotIn("metadata", widget.edit_workspace.dirty_flags)
            self.assertFalse(widget.edit_workspace.has_unsaved_changes)

            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_custom_metadata_tags_are_editor_state_only(self):
        from PySide6.QtWidgets import QMessageBox
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "sample.m4a"
            source.write_bytes(b"fake audio")
            widget = AudioEditorWorkspace()

            fake_metadata = {
                "success": True,
                "path": str(source),
                "filename": source.name,
                "format": "M4A",
                "container_format": "M4A",
                "codec": "AAC",
                "title": "Title",
                "artist": "",
                "album": "",
                "date": "",
                "genre": "",
                "tracknumber": "",
                "duration": None,
                "sample_rate": None,
                "bitrate": None,
                "channels": None,
                "bits_per_sample": None,
                "file_size": None,
                "cover_data": None,
                "cover_mime": None,
                "error": None,
            }

            with patch("ui.audio_editor.read_audio_metadata", return_value=fake_metadata):
                self.assertTrue(widget.load_audio_file(str(source)))

            self.assertEqual(widget.metadata_format_value.text(), "M4A / AAC")
            widget.custom_metadata_name_edit.setText("mood")
            widget.custom_metadata_value_edit.setText("warmup")
            self.assertTrue(widget.add_custom_metadata_tag())
            self.assertTrue(widget.metadata_dirty)
            self.assertTrue(widget.custom_metadata_dirty)
            self.assertEqual(widget.custom_metadata_tags["mood"], "warmup")
            self.assertEqual(widget.custom_metadata_tree.topLevelItemCount(), 1)

            with patch("ui.audio_editor.write_audio_metadata") as mock_write:
                self.assertTrue(widget.write_current_audio_metadata())

            mock_write.assert_not_called()
            self.assertEqual(widget.metadata_status_value.text(), "音频信息修改已加入统一导出")
            self.assertTrue(widget.edit_workspace.has_unsaved_changes)
            self.assertIn("metadata", widget.edit_workspace.dirty_flags)
            self.assertTrue(os.path.isfile(widget.edit_workspace.pending_changes_path))

            export_path = Path(temp_dir) / "sample_edited.m4a"
            with patch("ui.audio_editor.QMessageBox.warning") as mock_warning:
                result = widget.export_current_workspace("save_as", output_path=str(export_path))

            self.assertFalse(result["success"])
            self.assertIn("自定义标签", result["error"])
            self.assertIn("暂未接入实际导出", result["error"])
            mock_warning.assert_called_once()
            widget.edit_workspace.clear_changes(remove_pending=True)
            widget.metadata_dirty = False
            widget.custom_metadata_dirty = False
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_write_metadata_reloads_player_and_preserves_lyrics_preview(self):
        from PySide6.QtWidgets import QMessageBox
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "sample.flac"
            lrc = root / "sample.lrc"
            source.write_bytes(b"fake audio")
            lrc.write_text("[00:01.00]line", encoding="utf-8")
            widget = AudioEditorWorkspace()

            initial_metadata = {
                "success": True,
                "format": "FLAC",
                "title": "Old",
                "artist": "Artist",
                "album": "",
                "date": "",
                "genre": "",
                "tracknumber": "",
                "duration": None,
                "sample_rate": None,
                "bitrate": None,
                "channels": None,
                "bits_per_sample": None,
                "file_size": None,
                "cover_data": None,
                "cover_mime": None,
                "error": None,
            }
            refreshed_metadata = dict(initial_metadata, title="New")

            with patch("ui.audio_editor.read_audio_metadata", side_effect=[initial_metadata, refreshed_metadata]):
                self.assertTrue(widget.load_audio_file(str(source)))
                widget.sync_pending_lrc()
                widget.toggle_metadata_edit_mode()
                widget.metadata_title_value.setText("New")

                with patch("ui.audio_editor.write_audio_metadata") as mock_write:
                    self.assertTrue(widget.write_current_audio_metadata())

            self.assertTrue(widget.metadata_dirty)
            self.assertTrue(widget.edit_workspace.has_unsaved_changes)
            self.assertIn("metadata", widget.edit_workspace.dirty_flags)
            self.assertEqual(widget.metadata_status_value.text(), "音频信息修改已加入统一导出")
            mock_write.assert_not_called()

            output = root / "sample_edited.flac"
            with (
                patch("ui.audio_editor.write_audio_metadata", return_value={"success": True, "error": None}) as mock_write,
                patch(
                    "ui.audio_editor.embed_lrc_to_audio",
                    return_value={"embedded": True, "skipped_reason": None, "error": None},
                ) as mock_embed,
            ):
                result = widget.export_current_workspace("save_as", output_path=str(output))

            self.assertTrue(result["success"])
            self.assertFalse(widget.metadata_dirty)
            self.assertFalse(widget.lyrics_dirty)
            self.assertEqual(widget.metadata_title_value.text(), "New")
            self.assertEqual(widget.metadata_status_value.text(), "已导出")
            self.assertIn("[00:01.00]line", widget.lyrics_preview.toPlainText())
            self.assertEqual(widget.current_lrc_path, str(lrc))
            self.assertEqual(
                os.path.normcase(os.path.normpath(widget.player.source().toLocalFile())),
                os.path.normcase(os.path.normpath(str(source))),
            )
            mock_write.assert_called_once()
            self.assertEqual(Path(mock_write.call_args.args[0]), root / ".sample_edited.exporting.tmp.flac")
            mock_embed.assert_called_once()
            self.assertEqual(Path(mock_embed.call_args.args[0]), root / ".sample_edited.exporting.tmp.flac")
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_wav_metadata_write_unsupported_keeps_dirty(self):
        from PySide6.QtWidgets import QMessageBox
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "sample.wav"
            source.write_bytes(b"fake audio")
            widget = AudioEditorWorkspace()

            fake_metadata = {
                "success": True,
                "format": "WAV",
                "title": "Old",
                "artist": "",
                "album": "",
                "date": "",
                "genre": "",
                "tracknumber": "",
                "duration": None,
                "sample_rate": None,
                "bitrate": None,
                "channels": None,
                "bits_per_sample": None,
                "file_size": None,
                "cover_data": None,
                "cover_mime": None,
                "error": None,
            }

            with patch("ui.audio_editor.read_audio_metadata", return_value=fake_metadata):
                self.assertTrue(widget.load_audio_file(str(source)))

            widget.toggle_metadata_edit_mode()
            widget.metadata_title_value.setText("New")

            self.assertTrue(widget.write_current_audio_metadata())
            export_path = Path(temp_dir) / "sample_edited.wav"
            with (
                patch(
                    "ui.audio_editor.write_audio_metadata",
                    return_value={"success": False, "error": "当前格式暂不支持写入音频信息。"},
                ),
                patch("ui.audio_editor.QMessageBox.warning") as mock_warning,
            ):
                result = widget.export_current_workspace("save_as", output_path=str(export_path))

            self.assertFalse(result["success"])
            self.assertTrue(widget.metadata_dirty)
            self.assertEqual(widget.metadata_status_value.text(), "音频信息修改已加入统一导出")
            self.assertIn("暂不支持", widget.error_text)
            mock_warning.assert_called_once()
            widget.edit_workspace.clear_changes(remove_pending=True)
            widget.metadata_dirty = False
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_unsaved_metadata_prompt_can_block_new_audio_import(self):
        from PySide6.QtWidgets import QMessageBox
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first.mp3"
            second = root / "second.mp3"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            widget = AudioEditorWorkspace()
            fake_metadata = {
                "success": True,
                "format": "MP3",
                "title": "Old",
                "artist": "",
                "album": "",
                "date": "",
                "genre": "",
                "tracknumber": "",
                "duration": None,
                "sample_rate": None,
                "bitrate": None,
                "channels": None,
                "bits_per_sample": None,
                "file_size": None,
                "cover_data": None,
                "cover_mime": None,
                "error": None,
            }

            with patch("ui.audio_editor.read_audio_metadata", return_value=fake_metadata):
                self.assertTrue(widget.load_audio_file(str(first)))

            widget.toggle_metadata_edit_mode()
            widget.metadata_title_value.setText("Dirty")

            with patch.object(widget, "_ask_workspace_switch_action", return_value="cancel"):
                self.assertFalse(widget.load_audio_file(str(second)))

            self.assertEqual(widget.current_audio_path, str(first))
            widget.edit_workspace.clear_changes(remove_pending=True)
            widget.metadata_dirty = False
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def _make_png_bytes(self):
        from PySide6.QtCore import QBuffer, QByteArray, QIODevice
        from PySide6.QtGui import QColor, QPixmap

        pixmap = QPixmap(1, 1)
        pixmap.fill(QColor("green"))
        png_bytes = QByteArray()
        buffer = QBuffer(png_bytes)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        pixmap.save(buffer, "PNG")
        return bytes(png_bytes)

    def _fake_audio_metadata(self, audio_format="MP3", cover_data=None, cover_mime=None, title="Title"):
        return {
            "success": True,
            "format": audio_format,
            "title": title,
            "artist": "Artist",
            "album": "",
            "date": "",
            "genre": "",
            "tracknumber": "",
            "duration": None,
            "sample_rate": None,
            "bitrate": None,
            "channels": None,
            "bits_per_sample": None,
            "file_size": None,
            "cover_data": cover_data,
            "cover_mime": cover_mime,
            "cover_source": "test cover" if cover_data else "",
            "error": None,
        }

    def test_waveform_generation_starts_after_audio_load_and_accepts_cached_result(self):
        from ui.audio_editor import AudioEditorWorkspace

        class FakeSignal:
            def __init__(self):
                self.callbacks = []

            def connect(self, callback):
                self.callbacks.append(callback)

            def emit(self, payload=None):
                for callback in self.callbacks:
                    if payload is None:
                        callback()
                    else:
                        callback(payload)

        class FakeWaveformThread:
            created = None

            def __init__(self, audio_path, cache_dir, ffmpeg_path, sample_points=2000, parent=None):
                self.audio_path = audio_path
                self.cache_dir = cache_dir
                self.ffmpeg_path = ffmpeg_path
                self.sample_points = sample_points
                self.finished_signal = FakeSignal()
                self.finished = FakeSignal()
                self.started = False
                self.stopped = False
                FakeWaveformThread.created = self

            def start(self):
                self.started = True

            def isRunning(self):
                return self.started and not self.stopped

            def request_stop(self):
                self.stopped = True

            def deleteLater(self):
                pass

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "sample.mp3"
            editor_temp = root / "Temp" / "Editor"
            source.write_bytes(b"fake audio")

            with (
                patch("ui.audio_editor.get_editor_temp_folder", return_value=str(editor_temp)),
                patch("ui.audio_editor.WaveformGenerateThread", FakeWaveformThread),
            ):
                widget = AudioEditorWorkspace()

                with patch("ui.audio_editor.read_audio_metadata", return_value=self._fake_audio_metadata()):
                    self.assertTrue(widget.load_audio_file(str(source)))

                self.assertTrue(FakeWaveformThread.created.started)
                self.assertEqual(FakeWaveformThread.created.audio_path, str(source))
                self.assertTrue(
                    FakeWaveformThread.created.cache_dir.endswith(
                        os.path.join("Temp", "Editor", "WaveformCache")
                    )
                )
                self.assertEqual(widget.waveform_status, "生成中...")

                widget._on_waveform_generated({
                    "success": True,
                    "source_path": str(source),
                    "from_cache": True,
                    "duration_ms": 1000,
                    "sample_points": 3,
                    "peaks": [0.1, 0.8, 0.3],
                })

                self.assertEqual(widget.waveform_status, "已从缓存加载")
                self.assertEqual(widget.waveform_widget.peaks, [0.1, 0.8, 0.3])
                widget.clear_current_audio()
                self.app.processEvents()
                widget.deleteLater()

    def test_waveform_clear_stops_generation_and_stale_result_is_ignored(self):
        from ui.audio_editor import AudioEditorWorkspace

        class FakeSignal:
            def __init__(self):
                self.callbacks = []

            def connect(self, callback):
                self.callbacks.append(callback)

        class FakeWaveformThread:
            def __init__(self, audio_path, cache_dir, ffmpeg_path, sample_points=2000, parent=None):
                self.audio_path = audio_path
                self.cache_dir = cache_dir
                self.ffmpeg_path = ffmpeg_path
                self.finished_signal = FakeSignal()
                self.finished = FakeSignal()
                self.started = False
                self.stopped = False

            def start(self):
                self.started = True

            def isRunning(self):
                return self.started and not self.stopped

            def request_stop(self):
                self.stopped = True

            def deleteLater(self):
                pass

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first.mp3"
            second = root / "second.mp3"
            first.write_bytes(b"first")
            second.write_bytes(b"second")

            with patch("ui.audio_editor.WaveformGenerateThread", FakeWaveformThread):
                widget = AudioEditorWorkspace()

            with (
                patch("ui.audio_editor.read_audio_metadata", return_value=self._fake_audio_metadata()),
                patch("ui.audio_editor.WaveformGenerateThread", FakeWaveformThread),
            ):
                self.assertTrue(widget.load_audio_file(str(first)))
                first_thread = widget.waveform_thread
                self.assertTrue(first_thread.isRunning())
                self.assertTrue(widget.load_audio_file(str(second)))

            self.assertIn(first_thread, widget._stale_waveform_threads)
            widget._on_waveform_generated({
                "success": True,
                "source_path": str(first),
                "from_cache": False,
                "peaks": [1.0],
            })
            self.assertNotEqual(widget.waveform_widget.peaks, [1.0])

            widget.clear_current_audio()
            self.app.processEvents()
            self.assertEqual(widget.waveform_status, "未加载")
            self.assertEqual(widget.waveform_widget.peaks, [])
            widget.deleteLater()

    def test_import_cover_previews_without_writing_audio(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "sample.mp3"
            cover = root / "cover.png"
            source.write_bytes(b"fake audio")
            cover.write_bytes(self._make_png_bytes())
            widget = AudioEditorWorkspace()

            with patch("ui.audio_editor.read_audio_metadata", return_value=self._fake_audio_metadata()):
                self.assertTrue(widget.load_audio_file(str(source)))

            with (
                patch("ui.audio_editor.QFileDialog.getOpenFileName", return_value=(str(cover), "")),
                patch("ui.audio_editor.write_audio_cover") as mock_write,
            ):
                self.assertTrue(widget.select_cover_image())

            self.assertTrue(widget.cover_dirty)
            self.assertFalse(widget.cover_marked_for_removal)
            self.assertEqual(widget.current_cover_mime, "image/png")
            self.assertEqual(widget.cover_status_value.text(), "已导入新封面，待统一导出")
            self.assertFalse(widget.cover_label.pixmap().isNull())
            mock_write.assert_not_called()
            widget.edit_workspace.clear_changes(remove_pending=True)
            widget.cover_dirty = False
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_large_cover_import_can_be_cancelled_before_reading(self):
        from PySide6.QtWidgets import QMessageBox
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "sample.mp3"
            cover = root / "large.png"
            source.write_bytes(b"fake audio")
            cover.write_bytes(b"0" * (10 * 1024 * 1024 + 1))
            widget = AudioEditorWorkspace()

            with patch("ui.audio_editor.read_audio_metadata", return_value=self._fake_audio_metadata()):
                self.assertTrue(widget.load_audio_file(str(source)))

            with (
                patch("ui.audio_editor.QFileDialog.getOpenFileName", return_value=(str(cover), "")),
                patch(
                    "ui.audio_editor.QMessageBox.question",
                    return_value=QMessageBox.StandardButton.No,
                ),
            ):
                self.assertFalse(widget.select_cover_image())

            self.assertFalse(widget.cover_dirty)
            self.assertEqual(widget.cover_status_value.text(), "未读取到封面")
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_write_cover_reloads_player_preserves_lyrics_and_metadata_dirty(self):
        from PySide6.QtWidgets import QMessageBox
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "sample.flac"
            lrc = root / "sample.lrc"
            cover = root / "cover.png"
            source.write_bytes(b"fake audio")
            lrc.write_text("[00:01.00]line", encoding="utf-8")
            png_data = self._make_png_bytes()
            cover.write_bytes(png_data)
            widget = AudioEditorWorkspace()
            initial_metadata = self._fake_audio_metadata("FLAC", title="Old")
            refreshed_metadata = self._fake_audio_metadata("FLAC", cover_data=png_data, cover_mime="image/png", title="File Title")

            with patch("ui.audio_editor.read_audio_metadata", side_effect=[initial_metadata, refreshed_metadata]):
                self.assertTrue(widget.load_audio_file(str(source)))
                widget.sync_pending_lrc()
                widget.toggle_metadata_edit_mode()
                widget.metadata_title_value.setText("Dirty Title")

                with patch("ui.audio_editor.QFileDialog.getOpenFileName", return_value=(str(cover), "")):
                    self.assertTrue(widget.select_cover_image())

                with patch("ui.audio_editor.write_audio_cover") as mock_write:
                    self.assertTrue(widget.write_current_audio_cover())

            self.assertTrue(widget.cover_dirty)
            self.assertTrue(widget.metadata_dirty)
            self.assertEqual(widget.metadata_title_value.text(), "Dirty Title")
            self.assertEqual(widget.cover_status_value.text(), "封面修改已加入统一导出")
            self.assertIn("[00:01.00]line", widget.lyrics_preview.toPlainText())
            self.assertEqual(widget.current_lrc_path, str(lrc))
            mock_write.assert_not_called()

            output = root / "sample_edited.flac"
            with (
                patch("ui.audio_editor.write_audio_metadata", return_value={"success": True, "error": None}),
                patch("ui.audio_editor.write_audio_cover", return_value={"success": True, "error": None}) as mock_write,
                patch(
                    "ui.audio_editor.embed_lrc_to_audio",
                    return_value={"embedded": True, "skipped_reason": None, "error": None},
                ),
            ):
                result = widget.export_current_workspace("save_as", output_path=str(output))

            self.assertTrue(result["success"])
            self.assertFalse(widget.cover_dirty)
            self.assertFalse(widget.metadata_dirty)
            mock_write.assert_called_once_with(str(root / ".sample_edited.exporting.tmp.flac"), png_data, "image/png")
            widget.metadata_dirty = False
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_remove_cover_marks_dirty_and_write_uses_remove_backend(self):
        from PySide6.QtWidgets import QMessageBox
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "sample.mp3"
            source.write_bytes(b"fake audio")
            old_cover = self._make_png_bytes()
            widget = AudioEditorWorkspace()
            initial_metadata = self._fake_audio_metadata("MP3", cover_data=old_cover, cover_mime="image/png")
            refreshed_metadata = self._fake_audio_metadata("MP3", cover_data=None, cover_mime=None)

            with patch("ui.audio_editor.read_audio_metadata", side_effect=[initial_metadata, refreshed_metadata]):
                self.assertTrue(widget.load_audio_file(str(source)))
                self.assertTrue(widget.remove_current_cover())

                with patch("ui.audio_editor.remove_audio_cover") as mock_remove:
                    self.assertTrue(widget.write_current_audio_cover())

            self.assertTrue(widget.cover_dirty)
            self.assertTrue(widget.cover_marked_for_removal)
            self.assertEqual(widget.cover_status_value.text(), "封面修改已加入统一导出")
            self.assertEqual(widget.cover_label.text(), "未读取到封面")
            mock_remove.assert_not_called()

            output = Path(temp_dir) / "sample_edited.mp3"
            with patch("ui.audio_editor.remove_audio_cover", return_value={"success": True, "error": None}) as mock_remove:
                result = widget.export_current_workspace("save_as", output_path=str(output))

            self.assertTrue(result["success"])
            self.assertFalse(widget.cover_dirty)
            self.assertFalse(widget.cover_marked_for_removal)
            mock_remove.assert_called_once_with(str(Path(temp_dir) / ".sample_edited.exporting.tmp.mp3"))
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_wav_cover_write_unsupported_keeps_dirty(self):
        from PySide6.QtWidgets import QMessageBox
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "sample.wav"
            cover = root / "cover.png"
            source.write_bytes(b"fake audio")
            cover.write_bytes(self._make_png_bytes())
            widget = AudioEditorWorkspace()

            with patch("ui.audio_editor.read_audio_metadata", return_value=self._fake_audio_metadata("WAV")):
                self.assertTrue(widget.load_audio_file(str(source)))

            with patch("ui.audio_editor.QFileDialog.getOpenFileName", return_value=(str(cover), "")):
                self.assertTrue(widget.select_cover_image())

            self.assertTrue(widget.write_current_audio_cover())
            export_path = root / "sample_edited.wav"
            with (
                patch(
                    "ui.audio_editor.write_audio_cover",
                    return_value={"success": False, "error": "当前格式暂不支持写入封面。"},
                ),
                patch("ui.audio_editor.QMessageBox.warning") as mock_warning,
            ):
                result = widget.export_current_workspace("save_as", output_path=str(export_path))

            self.assertFalse(result["success"])
            self.assertTrue(widget.cover_dirty)
            self.assertEqual(widget.cover_status_value.text(), "封面修改已加入统一导出")
            self.assertIn("暂不支持", widget.error_text)
            mock_warning.assert_called_once()
            widget.edit_workspace.clear_changes(remove_pending=True)
            widget.cover_dirty = False
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_unsaved_cover_prompt_can_block_new_audio_import(self):
        from PySide6.QtWidgets import QMessageBox
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first.mp3"
            second = root / "second.mp3"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            widget = AudioEditorWorkspace()

            with patch("ui.audio_editor.read_audio_metadata", return_value=self._fake_audio_metadata()):
                self.assertTrue(widget.load_audio_file(str(first)))

            widget.cover_dirty = True
            widget.cover_marked_for_removal = True

            with patch.object(widget, "_ask_workspace_switch_action", return_value="cancel"):
                self.assertFalse(widget.load_audio_file(str(second)))

            self.assertEqual(widget.current_audio_path, str(first))
            widget.edit_workspace.clear_changes(remove_pending=True)
            widget.cover_dirty = False
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_lyrics_area_layout_keeps_controls_readable(self):
        from ui.audio_editor import AudioEditorWorkspace

        widget = AudioEditorWorkspace()

        try:
            self.assertEqual(widget.workspace_tabs.count(), 3)
            self.assertEqual(widget.workspace_tabs.tabText(0), "元数据")
            self.assertEqual(widget.workspace_tabs.tabText(1), "歌词编辑")
            self.assertEqual(widget.workspace_tabs.tabText(2), "升降调")
            self.assertFalse(hasattr(widget, "output_folder_value"))
            self.assertFalse(hasattr(widget, "info_output_folder_value"))
            self.assertGreaterEqual(widget.lyrics_preview.minimumHeight(), 260)
            self.assertGreaterEqual(widget.sync_lyrics_checkbox.minimumWidth(), 132)
            self.assertEqual(widget.import_lrc_button.text(), "导入 .lrc")
            self.assertEqual(widget.write_audio_lyrics_button.text(), "加入导出修改")
            self.assertFalse(hasattr(widget, "import_cover_button"))
            self.assertFalse(hasattr(widget, "remove_cover_button"))
            self.assertFalse(hasattr(widget, "restore_cover_button"))
            self.assertFalse(hasattr(widget, "write_cover_button"))
            self.assertEqual(widget.stage_note.maximumHeight(), 48)
            self.assertEqual(widget.stage_note.wordWrap(), True)
            self.assertEqual(widget.pitch_shift_slider.minimum(), -12)
            self.assertEqual(widget.pitch_shift_slider.maximum(), 12)
            self.assertEqual(widget.pitch_shift_slider.singleStep(), 1)
            self.assertEqual(widget.pitch_shift_slider.pageStep(), 1)
            self.assertEqual(widget.pitch_shift_slider.tickInterval(), 1)
            self.assertEqual(widget.pitch_shift_slider.value(), 0)
            self.assertEqual(widget.get_current_pitch_shift_value(), 0)
            self.assertEqual(widget.pitch_current_value.text(), "当前设置：原调")
            self.assertEqual(widget.pitch_preview_path_value.text(), "未生成")
            self.assertFalse(hasattr(widget, "pitch_down_button"))
            self.assertFalse(hasattr(widget, "pitch_up_button"))
            self.assertFalse(hasattr(widget, "pitch_semitone_spinbox"))
            self.assertEqual(widget.pitch_reset_button.text(), "重置为原调")
            widget.set_pitch_shift_value(-3)
            self.assertEqual(widget.pitch_current_value.text(), "当前设置：降 3 key")
            widget.set_pitch_shift_value(2)
            self.assertEqual(widget.pitch_current_value.text(), "当前设置：升 2 key")
            widget.reset_pitch_shift_to_zero()
            self.assertEqual(widget.pitch_shift_slider.value(), 0)
            self.assertEqual(widget.pitch_current_value.text(), "当前设置：原调")
            self.assertTrue(widget.pitch_auto_load_checkbox.isChecked())
            for button in (
                widget.sync_lrc_button,
                widget.skip_lrc_button,
                widget.choose_other_lrc_button,
                widget.manual_lyrics_button,
                widget.edit_lyrics_button,
                widget.restore_lyrics_button,
                widget.jump_to_body_button,
                widget.save_lrc_as_button,
                widget.save_lrc_original_button,
                widget.write_audio_lyrics_button,
            ):
                self.assertGreaterEqual(button.minimumWidth(), 116)
            for hidden_control in (
                widget.sync_lrc_button,
                widget.skip_lrc_button,
                widget.choose_other_lrc_button,
                widget.manual_lyrics_button,
                widget.edit_lyrics_button,
                widget.restore_lyrics_button,
                widget.jump_to_body_button,
                widget.save_lrc_as_button,
                widget.save_lrc_original_button,
                widget.sync_lyrics_checkbox,
            ):
                self.assertTrue(hidden_control.isHidden())
            self.assertFalse(widget.import_lrc_button.isHidden())
            self.assertFalse(widget.write_audio_lyrics_button.isHidden())

            cover_action_texts = [
                action.text()
                for action in widget.cover_context_menu.actions()
                if action.text()
            ]
            self.assertTrue(any(text.startswith("导入封面...") for text in cover_action_texts))
            self.assertTrue(any(text.startswith("移除封面") for text in cover_action_texts))
            self.assertTrue(any(text.startswith("恢复原封面") for text in cover_action_texts))
            self.assertTrue(any(text.startswith("加入封面到统一导出") for text in cover_action_texts))
            lyrics_action_texts = [
                action.text()
                for action in widget.lyrics_context_menu.actions()
                if action.text()
            ]
            self.assertIn("导入 .lrc...", lyrics_action_texts)
            self.assertTrue(any(text.startswith("手动编辑歌词") for text in lyrics_action_texts))
            self.assertTrue(any(text.startswith("编辑歌词") for text in lyrics_action_texts))
            self.assertTrue(any(text.startswith("另存为 .lrc...") for text in lyrics_action_texts))
            self.assertTrue(any(text.startswith("保存到原 .lrc") for text in lyrics_action_texts))
            self.assertTrue(any(text.startswith("加入歌词到统一导出") for text in lyrics_action_texts))
            self.assertFalse(any("不可用" in text for text in cover_action_texts))
            self.assertFalse(any("不可用" in text for text in lyrics_action_texts))
            self.assertFalse(widget.write_audio_lyrics_button.isEnabled())
            self.assertIn("当前不可用", widget.write_audio_lyrics_button.toolTip())
        finally:
            widget.deleteLater()

    def test_audio_editor_cover_and_lyrics_context_menu_state(self):
        from ui.audio_editor import AudioEditorWorkspace

        widget = AudioEditorWorkspace()

        try:
            widget.update_cover_menu_actions()
            self.assertFalse(widget.import_cover_action.isEnabled())
            self.assertFalse(widget.remove_cover_action.isEnabled())
            self.assertFalse(widget.restore_cover_action.isEnabled())
            self.assertFalse(widget.write_cover_action.isEnabled())
            self.assertIn("请先导入音频", widget.import_cover_action.toolTip())
            self.assertEqual(widget.import_cover_action.text(), "导入封面...")

            widget.current_audio_path = "C:/Music/Song.flac"
            widget.update_cover_menu_actions()
            self.assertTrue(widget.import_cover_action.isEnabled())
            self.assertFalse(widget.remove_cover_action.isEnabled())
            self.assertFalse(widget.restore_cover_action.isEnabled())
            self.assertFalse(widget.write_cover_action.isEnabled())
            self.assertIn("没有可移除的封面", widget.remove_cover_action.toolTip())
            self.assertIn("没有可恢复的原封面", widget.restore_cover_action.toolTip())
            self.assertIn("没有需要导出的封面修改", widget.write_cover_action.toolTip())

            widget.current_cover_data = b"cover"
            widget.original_cover_data = b"original"
            widget.cover_dirty = True
            widget.update_cover_menu_actions()
            self.assertTrue(widget.remove_cover_action.isEnabled())
            self.assertTrue(widget.restore_cover_action.isEnabled())
            self.assertTrue(widget.write_cover_action.isEnabled())

            widget.update_lyrics_menu_actions()
            self.assertTrue(widget.import_lrc_action.isEnabled())
            self.assertTrue(widget.manual_lyrics_action.isEnabled())
            self.assertFalse(widget.edit_lyrics_action.isEnabled())
            self.assertFalse(widget.save_lrc_as_action.isEnabled())
            self.assertFalse(widget.save_lrc_original_action.isEnabled())
            self.assertFalse(widget.write_audio_lyrics_action.isEnabled())
            self.assertFalse(widget.write_audio_lyrics_button.isEnabled())
            self.assertIn("没有可导出的歌词", widget.write_audio_lyrics_action.toolTip())
            self.assertIn("没有可导出的歌词", widget.write_audio_lyrics_button.toolTip())
            self.assertEqual(widget.write_audio_lyrics_action.text(), "加入歌词到统一导出")
            no_lyrics_order = [
                action.text()
                for action in widget.lyrics_context_menu.actions()
                if action.text()
            ]
            self.assertEqual(no_lyrics_order[:3], ["导入 .lrc...", "手动编辑歌词", "编辑歌词"])

            widget.lyrics_status = "已手动导入 .lrc"
            widget.lyrics_preview.setPlainText("[00:01.00]line")
            widget.current_lrc_path = "C:/Music/Song.lrc"
            widget.current_lyrics_source_path = "C:/Music/Song.lrc"
            widget.update_lyrics_menu_actions()
            self.assertTrue(widget.edit_lyrics_action.isEnabled())
            self.assertTrue(widget.restore_lyrics_action.isEnabled())
            self.assertTrue(widget.save_lrc_as_action.isEnabled())
            self.assertTrue(widget.save_lrc_original_action.isEnabled())
            self.assertTrue(widget.write_audio_lyrics_action.isEnabled())
            self.assertTrue(widget.write_audio_lyrics_button.isEnabled())
            loaded_lyrics_order = [
                action.text()
                for action in widget.lyrics_context_menu.actions()
                if action.text()
            ]
            self.assertEqual(loaded_lyrics_order[:3], ["编辑歌词", "恢复原文", "跳到歌词正文"])
            self.assertIn("同步歌词", loaded_lyrics_order)
        finally:
            widget.deleteLater()

    def test_context_menu_disabled_style_is_defined(self):
        from ui.theme import DARK_QSS, LIGHT_QSS

        for qss in (LIGHT_QSS, DARK_QSS):
            self.assertIn("QMenu::item:disabled", qss)
            self.assertIn("QMenu::item:disabled:selected", qss)
            self.assertIn("QMenu::separator", qss)
            self.assertIn("color: #6B7280", qss)
            self.assertIn("background-color: transparent", qss)

    def test_combobox_popup_hover_style_is_defined(self):
        from ui.theme import DARK_QSS, LIGHT_QSS

        for qss in (LIGHT_QSS, DARK_QSS):
            self.assertIn("QComboBox QAbstractItemView::item:hover", qss)
            self.assertIn("QComboBox QAbstractItemView::item:selected", qss)
            self.assertIn("QComboBox QAbstractItemView::item:disabled", qss)
            self.assertIn("min-height: 28px", qss)

    def test_light_theme_visual_hierarchy_style_is_defined(self):
        from ui.theme import DARK_QSS, LIGHT_QSS

        self.assertIn("background: #F3F6FA", LIGHT_QSS)
        self.assertIn("QGroupBox", LIGHT_QSS)
        self.assertIn("QTabBar::tab:selected", LIGHT_QSS)
        self.assertIn("QScrollBar:vertical", LIGHT_QSS)
        self.assertIn("QSlider::groove:horizontal", LIGHT_QSS)
        self.assertIn("QTextEdit,\nQPlainTextEdit", LIGHT_QSS)
        self.assertIn("selection-background-color: #DBEAFE", LIGHT_QSS)
        self.assertIn("#CoverPreview", LIGHT_QSS)
        self.assertIn("#MetadataEdit", LIGHT_QSS)
        self.assertNotIn("QTextEdit {\n    background: #0F172A", LIGHT_QSS)
        self.assertIn("QTextEdit {\n    background: #020617", DARK_QSS)

    def test_settings_page_uses_visual_sections(self):
        import inspect
        from ui.main_window import MainWindow

        source = inspect.getsource(MainWindow._build_settings_page)
        for title in (
            "路径设置",
            "输出设置",
            "歌词 / 元数据选项",
            "主题设置",
            "自动监听",
        ):
            self.assertIn(f'QGroupBox("{title}")', source)

    def test_audio_output_device_combo_uses_list_view_popup(self):
        from PySide6.QtWidgets import QListView
        from ui.audio_editor import AudioDeviceComboBox, AudioEditorWorkspace

        widget = AudioEditorWorkspace()
        self.assertIsInstance(widget.audio_output_device_combo, AudioDeviceComboBox)
        self.assertIsInstance(widget.audio_output_device_combo.view(), QListView)
        self.assertEqual(widget.audio_output_device_combo.view().objectName(), "HardEdgeComboPopup")
        self.assertTrue(widget.audio_output_device_combo.view().hasMouseTracking())
        self.assertTrue(widget.audio_output_device_combo.view().viewport().hasMouseTracking())
        widget.deleteLater()

    def test_player_slider_hover_tips_do_not_change_values(self):
        from PySide6.QtCore import QEvent, QPointF
        from ui.audio_editor import AudioEditorWorkspace

        widget = AudioEditorWorkspace()

        class HoverEvent:
            def __init__(self, x, event_type=QEvent.Type.MouseMove):
                self._position = QPointF(x, 5)
                self._event_type = event_type

            def type(self):
                return self._event_type

            def position(self):
                return self._position

            def globalPosition(self):
                return QPointF(200, 200)

        try:
            widget.current_audio_path = "C:/Music/Song.flac"
            widget.duration_ms = 10000
            widget.position_slider.setRange(0, 10000)
            widget.position_slider.resize(201, 20)
            widget.volume_slider.resize(101, 20)
            widget.position_slider.setValue(1000)
            widget.volume_slider.setValue(80)
            widget.update_player_action_states()
            self.assertEqual(widget.position_slider.toolTip(), "")
            self.assertEqual(widget.volume_slider.toolTip(), "")

            progress_event = HoverEvent(100)
            volume_event = HoverEvent((widget.volume_slider.width() - 1) * 0.75)
            progress_tooltip_event = HoverEvent(100, event_type=QEvent.Type.ToolTip)
            volume_tooltip_event = HoverEvent(
                (widget.volume_slider.width() - 1) * 0.75,
                event_type=QEvent.Type.ToolTip,
            )

            self.assertAlmostEqual(
                widget.get_slider_hover_ratio(widget.position_slider, progress_event),
                0.5,
                places=2,
            )

            with patch("ui.audio_editor.QToolTip.showText") as mock_tip:
                self.assertEqual(widget.show_progress_hover_tip(progress_event), "00:05 / 00:10")
                self.assertEqual(widget.show_volume_hover_tip(volume_event), "音量：75%（-2.5 dB）")
                self.assertTrue(widget.eventFilter(widget.position_slider, progress_tooltip_event))
                self.assertTrue(widget.eventFilter(widget.volume_slider, volume_tooltip_event))

            self.assertEqual(mock_tip.call_count, 4)
            self.assertEqual(widget.position_slider.value(), 1000)
            self.assertEqual(widget.volume_slider.value(), 80)
            self.assertEqual(widget.format_time_ms(3723000), "01:02:03")
            self.assertEqual(widget.percent_to_db(0), "-∞ dB")
            self.assertEqual(widget.format_volume_tip(100), "音量：100%（0.0 dB）")
        finally:
            widget.deleteLater()

    def test_progress_slider_context_menu_copies_timestamps_without_seeking(self):
        from PySide6.QtCore import QPoint
        from ui.audio_editor import AudioEditorWorkspace

        widget = AudioEditorWorkspace()

        def action_by_text(menu, text):
            for action in menu.actions():
                if action.text() == text:
                    return action
            raise AssertionError(f"missing action: {text}")

        try:
            widget.position_slider.resize(201, 20)
            disabled_menu = widget.build_progress_slider_context_menu(QPoint(100, 5))
            self.assertFalse(action_by_text(disabled_menu, "复制当前时间").isEnabled())
            self.assertFalse(action_by_text(disabled_menu, "复制 LRC 时间戳").isEnabled())
            self.assertFalse(action_by_text(disabled_menu, "复制当前播放时间").isEnabled())
            self.assertFalse(any("不可用" in action.text() for action in disabled_menu.actions()))
            disabled_menu.deleteLater()

            widget.current_audio_path = "C:/Music/Song.flac"
            widget.duration_ms = 200000
            widget.position_slider.setRange(0, widget.duration_ms)
            widget.position_slider.setValue(123450)
            enabled_menu = widget.build_progress_slider_context_menu(QPoint(100, 5))
            self.assertTrue(action_by_text(enabled_menu, "复制当前时间").isEnabled())
            self.assertTrue(action_by_text(enabled_menu, "复制 LRC 时间戳").isEnabled())
            self.assertTrue(action_by_text(enabled_menu, "复制当前播放时间").isEnabled())

            self.assertEqual(
                widget.copy_progress_time_at_position(QPoint(100, 5), as_lrc=False),
                "01:40.00",
            )
            self.assertEqual(self.app.clipboard().text(), "01:40.00")
            self.assertEqual(
                widget.copy_progress_time_at_position(QPoint(100, 5), as_lrc=True),
                "[01:40.00]",
            )
            self.assertEqual(self.app.clipboard().text(), "[01:40.00]")
            self.assertEqual(
                widget.copy_progress_time_at_position(
                    QPoint(0, 5),
                    as_lrc=True,
                    use_current_position=True,
                ),
                "[02:03.45]",
            )
            self.assertEqual(widget.position_slider.value(), 123450)
            self.assertEqual(widget.format_time_for_copy(3723450), "01:02:03.45")
            self.assertEqual(widget.format_lrc_timestamp(3753450), "[62:33.45]")
            enabled_menu.deleteLater()
        finally:
            widget.deleteLater()

    def test_double_click_lyrics_body_enters_manual_edit_mode(self):
        from PySide6.QtCore import QEvent, QPointF, Qt
        from PySide6.QtGui import QMouseEvent
        from ui.audio_editor import AudioEditorWorkspace

        widget = AudioEditorWorkspace()
        widget.show()
        self.app.processEvents()

        def double_click_event(button):
            return QMouseEvent(
                QEvent.Type.MouseButtonDblClick,
                QPointF(5, 5),
                button,
                button,
                Qt.KeyboardModifier.NoModifier,
            )

        try:
            self.assertFalse(
                widget.eventFilter(
                    widget.lyrics_preview.viewport(),
                    double_click_event(Qt.MouseButton.RightButton),
                )
            )
            self.assertTrue(widget.lyrics_preview.isReadOnly())

            self.assertTrue(
                widget.eventFilter(
                    widget.lyrics_preview.viewport(),
                    double_click_event(Qt.MouseButton.LeftButton),
                )
            )
            self.assertFalse(widget.lyrics_preview.isReadOnly())
            self.assertTrue(widget.is_manual_lyrics)
            self.assertTrue(widget.is_lyrics_editing)
            self.assertEqual(widget.edit_lyrics_button.text(), "完成编辑")
            self.assertEqual(widget.lyrics_status, "手动编入歌词中")
            widget.lyrics_preview.insertPlainText("[00:01.00]typed")
            self.assertIn("[00:01.00]typed", widget.lyrics_preview.toPlainText())
        finally:
            widget.deleteLater()

    def test_pitch_shift_zero_cancel_does_not_open_save_dialog(self):
        from PySide6.QtWidgets import QMessageBox
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "sample.mp3"
            source.write_bytes(b"fake audio")
            widget = AudioEditorWorkspace()

            with patch("ui.audio_editor.read_audio_metadata", return_value=self._fake_audio_metadata("MP3")):
                self.assertTrue(widget.load_audio_file(str(source)))

            with (
                patch(
                    "ui.audio_editor.QMessageBox.question",
                    return_value=QMessageBox.StandardButton.No,
                ),
                patch("ui.audio_editor.QFileDialog.getSaveFileName") as mock_save,
            ):
                self.assertFalse(widget.export_pitch_shift_audio())

            mock_save.assert_not_called()
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_pitch_shift_export_starts_thread_after_releasing_player(self):
        from PySide6.QtWidgets import QMessageBox
        from ui.audio_editor import AudioEditorWorkspace

        class FakeSignal:
            def __init__(self):
                self.callback = None

            def connect(self, callback):
                self.callback = callback

        class FakePitchThread:
            created = None

            def __init__(self, input_path, output_path, semitones, mode="export", parent=None):
                self.input_path = input_path
                self.output_path = output_path
                self.semitones = semitones
                self.mode = mode
                self.parent = parent
                self.finished_signal = FakeSignal()
                self.started = False
                FakePitchThread.created = self

            def start(self):
                self.started = True

            def isRunning(self):
                return self.started

            def deleteLater(self):
                pass

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "sample.mp3"
            source.write_bytes(b"fake audio")
            widget = AudioEditorWorkspace()
            widget.editor_temp_folder = str(root / "Temp" / "Editor")
            widget.set_pitch_shift_value(1)
            widget.pitch_auto_load_checkbox.setChecked(False)

            with patch("ui.audio_editor.read_audio_metadata", return_value=self._fake_audio_metadata("MP3")):
                self.assertTrue(widget.load_audio_file(str(source)))

            with (
                patch("ui.audio_editor.QFileDialog.getSaveFileName") as mock_save_dialog,
                patch("ui.audio_editor.PitchShiftThread", FakePitchThread),
            ):
                self.assertTrue(widget.export_pitch_shift_audio())

            self.assertTrue(widget.player.source().isEmpty())
            self.assertFalse(widget.export_pitch_button.isEnabled())
            self.assertEqual(FakePitchThread.created.input_path, str(source))
            self.assertIn("sample_workspace_pitch+1.mp3", FakePitchThread.created.output_path)
            self.assertTrue(FakePitchThread.created.output_path.startswith(str(root / "Temp" / "Editor")))
            self.assertEqual(FakePitchThread.created.semitones, 1)
            self.assertEqual(FakePitchThread.created.mode, "workspace_pitch")
            mock_save_dialog.assert_not_called()
            widget._on_pitch_shift_finished({
                "success": True,
                "output_path": FakePitchThread.created.output_path,
                "mode": "workspace_pitch",
            })
            self.assertTrue(widget.export_pitch_button.isEnabled())
            self.assertEqual(widget.current_audio_path, str(source))
            self.assertIn("pitch", widget.edit_workspace.dirty_flags)
            self.assertIn("audio_content", widget.edit_workspace.dirty_flags)
            self.assertEqual(widget.pitch_export_path_value.text(), "待统一导出")
            widget.edit_workspace.clear_changes(remove_pending=True)
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_pitch_shift_preview_uses_temp_file_without_changing_current_audio(self):
        from ui.audio_editor import AudioEditorWorkspace

        class FakeSignal:
            def __init__(self):
                self.callback = None

            def connect(self, callback):
                self.callback = callback

        class FakePitchThread:
            created = None

            def __init__(self, input_path, output_path, semitones, mode="export", parent=None):
                self.input_path = input_path
                self.output_path = output_path
                self.semitones = semitones
                self.mode = mode
                self.parent = parent
                self.finished_signal = FakeSignal()
                self.started = False
                FakePitchThread.created = self

            def isRunning(self):
                return self.started

            def start(self):
                self.started = True

            def deleteLater(self):
                pass

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "sample.flac"
            temp_root = root / "Temp"
            source.write_bytes(b"source")
            widget = AudioEditorWorkspace()

            with patch("ui.audio_editor.read_audio_metadata", return_value=self._fake_audio_metadata("FLAC")):
                self.assertTrue(widget.load_audio_file(str(source)))

            widget.set_pitch_shift_value(1)

            with (
                patch("ui.audio_editor.get_editor_temp_folder", return_value=str(temp_root / "Editor")),
                patch("ui.audio_editor.PitchShiftThread", FakePitchThread),
                patch("ui.audio_editor.QFileDialog.getSaveFileName") as mock_save_dialog,
            ):
                self.assertTrue(widget.preview_pitch_shift_audio())

            self.assertTrue(widget.player.source().isEmpty())
            self.assertFalse(widget.preview_pitch_button.isEnabled())
            self.assertFalse(widget.export_pitch_button.isEnabled())
            self.assertEqual(FakePitchThread.created.input_path, str(source))
            self.assertEqual(FakePitchThread.created.semitones, 1)
            self.assertEqual(FakePitchThread.created.mode, "preview")
            self.assertIn("PitchPreview", FakePitchThread.created.output_path)
            self.assertFalse(str(FakePitchThread.created.output_path).startswith(str(root / "sample")))
            mock_save_dialog.assert_not_called()

            preview_output = Path(FakePitchThread.created.output_path)
            preview_output.parent.mkdir(parents=True, exist_ok=True)
            preview_output.write_bytes(b"preview")
            widget._on_pitch_shift_finished({
                "success": True,
                "output_path": str(preview_output),
                "mode": "preview",
                "cover_copied": True,
            })

            self.assertEqual(widget.current_audio_path, str(source))
            self.assertEqual(
                os.path.normcase(os.path.normpath(widget.player.source().toLocalFile())),
                os.path.normcase(os.path.normpath(str(preview_output))),
            )
            self.assertTrue(widget.is_pitch_preview_loaded)
            self.assertTrue(widget.return_original_pitch_button.isEnabled())
            self.assertIn("正在试听升降调结果", widget.pitch_status_value.text())
            self.assertEqual(widget.pitch_preview_path_value.text(), "升 1 key")

            widget.set_pitch_shift_value(2)
            self.assertEqual(widget.pitch_preview_path_value.text(), "设置已变更，等待试听")
            self.assertTrue(widget.return_original_pitch_button.isEnabled())
            self.assertEqual(FakePitchThread.created.semitones, 1)

            self.assertTrue(widget.return_to_original_pitch_audio())
            self.assertEqual(widget.current_audio_path, str(source))
            self.assertEqual(
                os.path.normcase(os.path.normpath(widget.player.source().toLocalFile())),
                os.path.normcase(os.path.normpath(str(source))),
            )
            self.assertFalse(widget.is_pitch_preview_loaded)
            self.assertFalse(widget.return_original_pitch_button.isEnabled())
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_pitch_shift_success_can_auto_load_result(self):
        from ui.audio_editor import AudioEditorWorkspace

        class FakeThread:
            def deleteLater(self):
                pass

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "sample.flac"
            output = root / "sample_pitch+1.flac"
            source.write_bytes(b"source")
            output.write_bytes(b"shifted")
            widget = AudioEditorWorkspace()

            with patch("ui.audio_editor.read_audio_metadata", return_value=self._fake_audio_metadata("FLAC")):
                self.assertTrue(widget.load_audio_file(str(source)))
                widget.pitch_shift_thread = FakeThread()
                widget.pitch_shift_original_path = str(source)
                widget.pitch_shift_output_path = str(output)
                widget.pitch_shift_player_state = {"position": 0, "volume": 0.8}
                widget._on_pitch_shift_finished({"success": True, "output_path": str(output)})

            self.assertEqual(widget.current_audio_path, str(output))
            self.assertIn("已加载处理结果", widget.pitch_status_value.text())
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_pitch_shift_failure_restores_original_audio(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtWidgets import QMessageBox
        from ui.audio_editor import AudioEditorWorkspace

        class FakeThread:
            def deleteLater(self):
                pass

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "sample.mp3"
            source.write_bytes(b"source")
            widget = AudioEditorWorkspace()

            with patch("ui.audio_editor.read_audio_metadata", return_value=self._fake_audio_metadata("MP3")):
                self.assertTrue(widget.load_audio_file(str(source)))

            widget.player.setSource(QUrl())
            widget.pitch_shift_thread = FakeThread()
            widget.pitch_shift_original_path = str(source)
            widget.pitch_shift_output_path = str(Path(temp_dir) / "failed.mp3")
            widget.pitch_shift_player_state = {"position": 0, "volume": 0.8}

            with patch("ui.audio_editor.QMessageBox.warning") as mock_warning:
                widget._on_pitch_shift_finished({"success": False, "error": "boom"})

            self.assertEqual(
                os.path.normcase(os.path.normpath(widget.player.source().toLocalFile())),
                os.path.normcase(os.path.normpath(str(source))),
            )
            self.assertIn("处理失败", widget.pitch_status_value.text())
            mock_warning.assert_called_once()
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_audio_import_rejects_ncm_and_lrc_without_watcher_queue(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ncm = root / "sample.ncm"
            lrc = root / "sample.lrc"
            ncm.write_bytes(b"fake ncm")
            lrc.write_text("[00:00.00]lyric", encoding="utf-8")
            widget = AudioEditorWorkspace()

            with (
                patch("ui.audio_editor.QMessageBox.information") as mock_message,
                patch("watcher.handle_detected_file") as mock_handle_detected,
            ):
                self.assertFalse(widget.load_audio_file(str(ncm)))
                self.assertFalse(widget.load_audio_file(str(lrc)))

            self.assertIsNone(widget.current_audio_path)
            self.assertEqual(mock_message.call_count, 2)
            mock_handle_detected.assert_not_called()
            widget.deleteLater()

    def test_audio_import_finds_matching_lrc_and_waits_for_confirmation(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Song.mp3"
            lrc = root / "Song.lrc"
            source.write_bytes(b"fake audio")
            lrc.write_text("[00:01.00]hello\n[00:02.00]world", encoding="utf-8")
            widget = AudioEditorWorkspace()

            with patch("watcher.handle_detected_file") as mock_handle_detected:
                self.assertTrue(widget.load_audio_file(str(source)))

            self.assertIsNone(widget.current_lrc_path)
            self.assertEqual(widget.pending_lrc_path, str(lrc))
            self.assertEqual(widget.lyrics_status, "已找到同名 .lrc，等待用户确认")
            self.assertIn("是否同步导入", widget.lyrics_preview.toPlainText())
            self.assertNotIn("[00:01.00]hello", widget.lyrics_preview.toPlainText())
            self.assertTrue(widget.sync_lrc_button.isHidden())
            self.assertTrue(widget.skip_lrc_button.isHidden())
            self.assertTrue(widget.choose_other_lrc_button.isHidden())
            self.assertTrue(widget.sync_pending_lrc_action.isVisible())
            self.assertTrue(widget.sync_pending_lrc_action.isEnabled())
            self.assertEqual(widget.sync_pending_lrc_action.text(), "同步歌词")
            self.assertIsNone(widget.skip_pending_lrc_action)
            self.assertIsNone(widget.choose_other_lrc_action)
            pending_order = [
                action.text()
                for action in widget.lyrics_context_menu.actions()
                if action.text()
            ]
            self.assertEqual(pending_order[:4], ["同步歌词", "手动编辑歌词", "导入 .lrc...", "跳到歌词正文"])
            self.assertIn("歌词状态：已找到同名 .lrc，等待用户确认", widget.stage_note.text())
            mock_handle_detected.assert_not_called()
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_audio_import_prefers_embedded_lyrics_over_matching_lrc(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Song.flac"
            lrc = root / "Song.lrc"
            source.write_bytes(b"fake audio")
            lrc.write_text("[00:01.00]external", encoding="utf-8")
            widget = AudioEditorWorkspace()

            with patch(
                "ui.audio_editor.read_embedded_lyrics",
                return_value={
                    "found": True,
                    "lyrics": "[00:01.00]embedded",
                    "source_type": "embedded",
                    "format": "FLAC",
                    "field": "LYRICS",
                    "error": None,
                },
            ):
                self.assertTrue(widget.load_audio_file(str(source)))

            self.assertIsNone(widget.current_lrc_path)
            self.assertIsNone(widget.current_lyrics_source_path)
            self.assertEqual(widget.current_lyrics_source_type, "embedded")
            self.assertEqual(widget.pending_lrc_path, str(lrc))
            self.assertEqual(widget.lyrics_source_value.text(), "音频内嵌歌词")
            self.assertEqual(widget.lyrics_source_field_value.text(), "LYRICS")
            self.assertIn("[00:01.00]embedded", widget.lyrics_preview.toPlainText())
            self.assertNotIn("external", widget.lyrics_preview.toPlainText())
            self.assertEqual(
                widget.lyrics_status,
                "已读取音频内嵌歌词；同时发现同名 .lrc，可选择导入外置歌词",
            )
            self.assertTrue(widget.sync_lrc_button.isHidden())
            self.assertTrue(widget.sync_pending_lrc_action.isVisible())
            self.assertTrue(widget.sync_pending_lrc_action.isEnabled())
            self.assertEqual(widget.sync_pending_lrc_action.text(), "同步歌词")

            widget.skip_pending_lrc()

            self.assertIsNone(widget.pending_lrc_path)
            self.assertIn("[00:01.00]embedded", widget.lyrics_preview.toPlainText())
            self.assertEqual(widget.current_lyrics_source_type, "embedded")
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_audio_import_uses_matching_lrc_when_no_embedded_lyrics(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Song.flac"
            lrc = root / "Song.lrc"
            source.write_bytes(b"fake audio")
            lrc.write_text("[00:01.00]external", encoding="utf-8")
            widget = AudioEditorWorkspace()

            with patch(
                "ui.audio_editor.read_embedded_lyrics",
                return_value={
                    "found": False,
                    "lyrics": "",
                    "source_type": None,
                    "format": "FLAC",
                    "field": None,
                    "error": None,
                },
            ):
                self.assertTrue(widget.load_audio_file(str(source)))

            self.assertEqual(widget.pending_lrc_path, str(lrc))
            self.assertEqual(widget.lyrics_status, "已找到同名 .lrc，等待用户确认")
            self.assertEqual(widget.lyrics_source_field_value.text(), "同名 .lrc 待确认")
            self.assertIn("是否同步导入", widget.lyrics_preview.toPlainText())
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_embedded_lyrics_source_save_original_and_restore_behaviors(self):
        from PySide6.QtWidgets import QMessageBox
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            audio = Path(temp_dir) / "Song.flac"
            audio.write_bytes(b"fake audio")
            widget = AudioEditorWorkspace()

            with patch(
                "ui.audio_editor.read_embedded_lyrics",
                side_effect=[
                    {
                        "found": True,
                        "lyrics": "[00:01.00]embedded",
                        "source_type": "embedded",
                        "format": "FLAC",
                        "field": "LYRICS",
                        "error": None,
                    },
                    {
                        "found": True,
                        "lyrics": "[00:01.00]restored",
                        "source_type": "embedded",
                        "format": "FLAC",
                        "field": "LYRICS",
                        "error": None,
                    },
                ],
            ):
                self.assertTrue(widget.load_audio_file(str(audio)))

                with patch("ui.audio_editor.QMessageBox.information") as mock_info:
                    self.assertFalse(widget.save_lrc_to_original())

                self.assertTrue(mock_info.called)
                self.assertEqual(
                    widget.lyrics_status,
                    "当前歌词来源为音频内嵌歌词，没有原 .lrc 文件",
                )

                widget.toggle_lyrics_edit_mode()
                widget.lyrics_preview.setPlainText("[00:01.00]edited")
                widget.toggle_lyrics_edit_mode()
                widget.restore_original_lyrics()

            self.assertIn("[00:01.00]restored", widget.lyrics_preview.toPlainText())
            self.assertEqual(widget.current_lyrics_source_type, "embedded")
            self.assertFalse(widget.lyrics_dirty)
            self.assertEqual(widget.lyrics_status, "已从音频内嵌歌词恢复原文")
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_sync_pending_lrc_imports_matching_lyrics(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Song.mp3"
            lrc = root / "Song.lrc"
            source.write_bytes(b"fake audio")
            lrc.write_text("[00:01.00]hello", encoding="utf-8")
            widget = AudioEditorWorkspace()
            widget.load_audio_file(str(source))

            widget.sync_pending_lrc()

            self.assertEqual(widget.current_lrc_path, str(lrc))
            self.assertIsNone(widget.pending_lrc_path)
            self.assertEqual(widget.lyrics_status, "已同步导入同名 .lrc，待统一导出")
            self.assertIn("[00:01.00]hello", widget.lyrics_preview.toPlainText())
            self.assertTrue(widget.sync_lrc_button.isHidden())
            self.assertEqual(len(widget.current_lrc_entries), 1)
            self.assertIn("已解析 1 条时间轴歌词", widget.lyrics_sync_status)
            widget.edit_workspace.clear_changes(remove_pending=True)
            widget.lyrics_dirty = False
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_lyrics_sync_highlights_line_by_player_position(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            lrc = Path(temp_dir) / "manual.lrc"
            lrc.write_text(
                "[00:01.00]first\n[00:03.00]second\n[00:05.00]third",
                encoding="utf-8",
            )
            widget = AudioEditorWorkspace()
            widget.load_lrc_file(str(lrc), source="manual")

            widget._on_position_changed(3200)

            self.assertEqual(widget.current_sync_line_index, 1)
            self.assertIn("当前同步行：第 2 行", widget.lyrics_sync_status)
            self.assertEqual(len(widget.lyrics_preview.extraSelections()), 1)
            widget.deleteLater()

    def test_slider_release_updates_lyrics_sync_immediately(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            lrc = Path(temp_dir) / "manual.lrc"
            lrc.write_text("[00:01.00]first\n[00:08.00]later", encoding="utf-8")
            widget = AudioEditorWorkspace()
            widget.load_lrc_file(str(lrc), source="manual")
            widget.position_slider.setRange(0, 10000)
            widget.position_slider.setValue(8200)

            widget._on_slider_released()

            self.assertEqual(widget.current_sync_line_index, 1)
            self.assertIn("当前同步行：第 2 行", widget.lyrics_sync_status)
            widget.deleteLater()

    def test_disabling_lyrics_sync_clears_highlight_and_stops_updates(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            lrc = Path(temp_dir) / "manual.lrc"
            lrc.write_text("[00:01.00]first\n[00:03.00]second", encoding="utf-8")
            widget = AudioEditorWorkspace()
            widget.load_lrc_file(str(lrc), source="manual")

            widget._on_position_changed(3100)
            self.assertEqual(widget.current_sync_line_index, 1)

            widget.sync_lyrics_checkbox.setChecked(False)
            widget._on_position_changed(1000)

            self.assertIsNone(widget.current_sync_line_index)
            self.assertEqual(widget.lyrics_sync_status, "同步滚动已关闭")
            self.assertEqual(len(widget.lyrics_preview.extraSelections()), 0)
            widget.deleteLater()

    def test_edit_mode_pauses_lyrics_sync_and_finish_reparses(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            lrc = Path(temp_dir) / "manual.lrc"
            lrc.write_text("[00:01.00]first", encoding="utf-8")
            widget = AudioEditorWorkspace()
            widget.load_lrc_file(str(lrc), source="manual")

            widget.toggle_lyrics_edit_mode()
            widget._on_position_changed(1000)

            self.assertEqual(widget.lyrics_sync_status, "编辑模式下已暂停同步滚动")
            self.assertIsNone(widget.current_sync_line_index)

            widget.lyrics_preview.setPlainText("[00:02.00]edited\nplain")
            widget.toggle_lyrics_edit_mode()

            self.assertEqual(len(widget.current_lrc_entries), 1)
            self.assertEqual(widget.current_lrc_entries[0]["time_ms"], 2000)
            self.assertTrue(widget.lyrics_preview.isReadOnly())
            widget.deleteLater()

    def test_skip_pending_lrc_keeps_lyrics_body_unloaded(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Song.mp3"
            lrc = root / "Song.lrc"
            source.write_bytes(b"fake audio")
            lrc.write_text("[00:01.00]hello", encoding="utf-8")
            widget = AudioEditorWorkspace()
            widget.load_audio_file(str(source))

            widget.skip_pending_lrc()

            self.assertEqual(widget.pending_lrc_path, str(lrc))
            self.assertIsNone(widget.current_lrc_path)
            self.assertEqual(widget.lyrics_status, "已找到同名 .lrc，但用户暂未导入")
            self.assertIn("暂未导入", widget.lyrics_preview.toPlainText())
            self.assertNotIn("[00:01.00]hello", widget.lyrics_preview.toPlainText())
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_choose_other_lrc_overrides_pending_lrc(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Song.mp3"
            auto_lrc = root / "Song.lrc"
            other_lrc = root / "Other.lrc"
            source.write_bytes(b"fake audio")
            auto_lrc.write_text("[00:01.00]auto", encoding="utf-8")
            other_lrc.write_text("[00:02.00]other", encoding="utf-8")
            widget = AudioEditorWorkspace()
            widget.load_audio_file(str(source))

            with patch("ui.audio_editor.QFileDialog.getOpenFileName", return_value=(str(other_lrc), "")):
                widget.choose_other_lrc_button.click()

            self.assertEqual(widget.current_lrc_path, str(other_lrc))
            self.assertIsNone(widget.pending_lrc_path)
            self.assertEqual(widget.lyrics_status, "已手动导入 .lrc，待统一导出")
            self.assertIn("other", widget.lyrics_preview.toPlainText())
            self.assertNotIn("auto", widget.lyrics_preview.toPlainText())
            self.assertIn("lyrics", widget.edit_workspace.dirty_flags)
            widget.edit_workspace.clear_changes(remove_pending=True)
            widget.lyrics_dirty = False
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_audio_import_without_matching_lrc_updates_status(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "Song.mp3"
            source.write_bytes(b"fake audio")
            widget = AudioEditorWorkspace()

            self.assertTrue(widget.load_audio_file(str(source)))

            self.assertEqual(widget.lyrics_status, "未找到任何歌词，可手动导入或手动编入")
            self.assertIn("未找到任何歌词", widget.lyrics_preview.toPlainText())
            self.assertIn("手动编入歌词", widget.manual_lyrics_button.text())
            self.assertIn("编辑文件：Song.mp3", widget.stage_note.text())
            self.assertNotIn("尚未导入音频文件", widget.stage_note.text())
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_manual_lrc_import_previews_without_audio_or_watcher_queue(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            lrc = Path(temp_dir) / "manual.lrc"
            lrc.write_text("[00:03.00]manual lyric", encoding="utf-8")
            widget = AudioEditorWorkspace()

            with (
                patch("ui.audio_editor.QFileDialog.getOpenFileName", return_value=(str(lrc), "")),
                patch("ui.audio_editor.QMessageBox.information") as mock_message,
                patch("watcher.handle_detected_file") as mock_handle_detected,
            ):
                widget.select_lrc_file()

            self.assertIsNone(widget.current_audio_path)
            self.assertEqual(widget.current_lrc_path, str(lrc))
            self.assertEqual(widget.lyrics_status, "已手动导入 .lrc")
            self.assertIn("[00:03.00]manual lyric", widget.lyrics_preview.toPlainText())
            mock_message.assert_called_once()
            mock_handle_detected.assert_not_called()
            widget.deleteLater()

    def test_playback_status_refresh_does_not_clear_lyrics(self):
        from PySide6.QtMultimedia import QMediaPlayer
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "sample.mp3"
            lrc = root / "sample.lrc"
            source.write_bytes(b"fake audio")
            lrc.write_text("[00:01.00]line", encoding="utf-8")
            widget = AudioEditorWorkspace()
            widget.load_audio_file(str(source))
            widget.sync_pending_lrc()

            widget._on_playback_state_changed(QMediaPlayer.PlaybackState.PlayingState)
            self.assertIn("播放状态：播放中", widget.stage_note.text())
            self.assertIn("[00:01.00]line", widget.lyrics_preview.toPlainText())

            widget._on_playback_state_changed(QMediaPlayer.PlaybackState.PausedState)
            self.assertIn("播放状态：已暂停", widget.stage_note.text())

            widget._on_playback_state_changed(QMediaPlayer.PlaybackState.StoppedState)
            self.assertIn("播放状态：已停止", widget.stage_note.text())
            widget.edit_workspace.clear_changes(remove_pending=True)
            widget.lyrics_dirty = False
            widget.release_editor_player_source()
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_editor_drop_uses_first_supported_audio_only(self):
        from ui.audio_editor import AudioEditorWorkspace

        messages = []

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            folder = root / "folder"
            lrc = root / "sample.lrc"
            first_audio = root / "first.m4a"
            second_audio = root / "second.flac"
            folder.mkdir()
            lrc.write_text("lyric", encoding="utf-8")
            first_audio.write_bytes(b"audio")
            second_audio.write_bytes(b"audio")
            widget = AudioEditorWorkspace(log_callback=messages.append)

            with patch("watcher.handle_detected_file") as mock_handle_detected:
                self.assertTrue(
                    widget.handle_dropped_files([
                        str(folder),
                        str(lrc),
                        str(first_audio),
                        str(second_audio),
                    ])
                )

            self.assertEqual(widget.current_audio_path, str(first_audio))
            self.assertEqual(widget.current_lrc_path, str(lrc))
            self.assertIn("lyric", widget.lyrics_preview.toPlainText())
            self.assertTrue(
                any("只导入第一个支持" in message for message in messages)
            )
            mock_handle_detected.assert_not_called()
            widget.edit_workspace.clear_changes(remove_pending=True)
            widget.lyrics_dirty = False
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_edit_lyrics_keeps_changes_in_memory_only_and_restore_reads_source(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            lrc = Path(temp_dir) / "manual.lrc"
            lrc.write_text("[00:01.00]original", encoding="utf-8")
            widget = AudioEditorWorkspace()
            widget.load_lrc_file(str(lrc), source="manual")

            widget.toggle_lyrics_edit_mode()
            self.assertFalse(widget.lyrics_preview.isReadOnly())
            widget.lyrics_preview.setPlainText("[00:01.00]edited")
            widget.toggle_lyrics_edit_mode()

            self.assertTrue(widget.lyrics_preview.isReadOnly())
            self.assertEqual(widget.current_lrc_text, "[00:01.00]edited")
            self.assertTrue(widget.lyrics_dirty)
            self.assertEqual(widget.lyrics_status, "歌词已修改，尚未保存")
            self.assertEqual(lrc.read_text(encoding="utf-8"), "[00:01.00]original")

            widget.restore_original_lyrics()
            self.assertIn("original", widget.lyrics_preview.toPlainText())
            self.assertNotIn("edited", widget.lyrics_preview.toPlainText())
            self.assertFalse(widget.lyrics_dirty)
            widget.deleteLater()

    def test_save_lrc_as_writes_new_file_without_touching_original(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "Song.mp3"
            original_lrc = root / "Song.lrc"
            saved_lrc = root / "Edited.lrc"
            audio.write_bytes(b"fake audio")
            original_lrc.write_text("[00:01.00]original", encoding="utf-8")
            widget = AudioEditorWorkspace()
            widget.load_audio_file(str(audio))
            widget.sync_pending_lrc()
            widget.toggle_lyrics_edit_mode()
            widget.lyrics_preview.setPlainText("[00:01.00]edited")
            widget.toggle_lyrics_edit_mode()

            with patch(
                "ui.audio_editor.QFileDialog.getSaveFileName",
                return_value=(str(saved_lrc), ""),
            ):
                self.assertTrue(widget.save_lrc_as())

            self.assertEqual(
                saved_lrc.read_text(encoding="utf-8-sig"),
                "[00:01.00]edited",
            )
            self.assertEqual(
                original_lrc.read_text(encoding="utf-8"),
                "[00:01.00]original",
            )
            self.assertEqual(widget.current_lyrics_source_path, str(saved_lrc))
            self.assertFalse(widget.lyrics_dirty)
            self.assertEqual(widget.lyrics_status, "歌词已另存为 .lrc")
            widget.edit_workspace.clear_changes(remove_pending=True)
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_manual_lyrics_entry_starts_blank_editing_without_creating_lrc(self):
        from PySide6.QtWidgets import QMessageBox
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "Song.flac"
            audio.write_bytes(b"fake audio")
            widget = AudioEditorWorkspace()
            widget.load_audio_file(str(audio))

            self.assertTrue(widget.start_manual_lyrics_entry())

            self.assertEqual(widget.lyrics_preview.toPlainText(), "")
            self.assertFalse(widget.lyrics_preview.isReadOnly())
            self.assertEqual(widget.edit_lyrics_button.text(), "完成编辑")
            self.assertEqual(widget.lyrics_status, "手动编入歌词中")
            self.assertIsNone(widget.current_lyrics_source_path)
            self.assertTrue(widget.lyrics_dirty)
            self.assertFalse((root / "Song.lrc").exists())
            widget.edit_workspace.clear_changes(remove_pending=True)
            widget.lyrics_dirty = False
            widget.release_editor_player_source()
            with patch.object(widget, "_ask_workspace_switch_action", return_value="discard"):
                widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_manual_lyrics_edit_save_as_and_restore_without_source(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "Song.flac"
            saved_lrc = root / "Manual.lrc"
            audio.write_bytes(b"fake audio")
            widget = AudioEditorWorkspace()
            widget.load_audio_file(str(audio))
            widget.start_manual_lyrics_entry()
            widget.lyrics_preview.setPlainText("[00:01.00]manual")
            widget.toggle_lyrics_edit_mode()

            self.assertTrue(widget.lyrics_preview.isReadOnly())
            self.assertEqual(widget.lyrics_status, "手动歌词已编辑，尚未保存")
            self.assertTrue(widget.lyrics_dirty)

            with patch("ui.audio_editor.QMessageBox.information") as mock_info:
                widget.restore_original_lyrics()

            self.assertIn("[00:01.00]manual", widget.lyrics_preview.toPlainText())
            self.assertEqual(widget.lyrics_status, "当前歌词没有原文来源，无法恢复。")
            mock_info.assert_called_once()

            with patch("ui.audio_editor.QMessageBox.information") as mock_info:
                self.assertFalse(widget.save_lrc_to_original())

            self.assertIn("另存为 .lrc", mock_info.call_args.args[2])

            with patch(
                "ui.audio_editor.QFileDialog.getSaveFileName",
                return_value=(str(saved_lrc), ""),
            ) as mock_save_dialog:
                self.assertTrue(widget.save_lrc_as())

            default_path = mock_save_dialog.call_args.args[2]
            self.assertEqual(Path(default_path).name, "Song.lrc")
            self.assertEqual(saved_lrc.read_text(encoding="utf-8-sig"), "[00:01.00]manual")
            self.assertEqual(widget.current_lyrics_source_path, str(saved_lrc))
            self.assertFalse(widget.lyrics_dirty)
            self.assertEqual(widget.lyrics_status, "手动歌词已另存为 .lrc")
            widget.edit_workspace.clear_changes(remove_pending=True)
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_manual_lyrics_can_write_current_audio_without_lrc_source(self):
        from PySide6.QtWidgets import QMessageBox
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "Song.flac"
            audio.write_bytes(b"fake audio")
            widget = AudioEditorWorkspace()
            widget.load_audio_file(str(audio))
            widget.start_manual_lyrics_entry()
            widget.lyrics_preview.setPlainText("[00:01.00]manual")
            widget.toggle_lyrics_edit_mode()

            with patch("ui.audio_editor.embed_lrc_to_audio") as mock_embed:
                self.assertTrue(widget.write_lyrics_to_current_audio())

            mock_embed.assert_not_called()
            self.assertTrue(widget.lyrics_dirty)
            self.assertTrue(widget.edit_workspace.has_unsaved_changes)
            self.assertIn("lyrics", widget.edit_workspace.dirty_flags)
            self.assertIsNone(widget.current_lyrics_source_path)
            self.assertNotEqual(widget.current_lyrics_source_type, "embedded")
            self.assertEqual(
                widget.lyrics_status,
                "歌词已加入统一导出修改",
            )

            output = root / "Song_edited.flac"
            with patch(
                "ui.audio_editor.embed_lrc_to_audio",
                return_value={"embedded": True, "skipped_reason": None, "error": None},
            ) as mock_embed:
                result = widget.export_current_workspace("save_as", output_path=str(output))

            self.assertTrue(result["success"])
            self.assertFalse(widget.lyrics_dirty)
            mock_embed.assert_called_once_with(str(root / ".Song_edited.exporting.tmp.flac"), "[00:01.00]manual", overwrite=True)
            with patch.object(widget, "_ask_workspace_switch_action", return_value="discard"):
                widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_manual_lyrics_can_replace_pending_auto_lrc_without_loading_it(self):
        from PySide6.QtWidgets import QMessageBox
        from ui.audio_editor import AudioEditorWorkspace

        messages = []

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "Song.mp3"
            lrc = root / "Song.lrc"
            audio.write_bytes(b"fake audio")
            lrc.write_text("[00:01.00]auto", encoding="utf-8")
            widget = AudioEditorWorkspace(log_callback=messages.append)
            widget.load_audio_file(str(audio))

            self.assertEqual(widget.pending_lrc_path, str(lrc))
            self.assertTrue(widget.start_manual_lyrics_entry())

            self.assertIsNone(widget.pending_lrc_path)
            self.assertIsNone(widget.current_lyrics_source_path)
            self.assertEqual(widget.lyrics_preview.toPlainText(), "")
            self.assertNotIn("auto", widget.lyrics_preview.toPlainText())
            self.assertTrue(any("放弃自动找到的同名 .lrc" in message for message in messages))
            with patch.object(widget, "_ask_workspace_switch_action", return_value="discard"):
                widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_save_lrc_to_original_requires_confirmation(self):
        from PySide6.QtWidgets import QMessageBox
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            lrc = Path(temp_dir) / "manual.lrc"
            lrc.write_text("[00:01.00]original", encoding="utf-8")
            widget = AudioEditorWorkspace()
            widget.load_lrc_file(str(lrc), source="manual")
            widget.toggle_lyrics_edit_mode()
            widget.lyrics_preview.setPlainText("[00:01.00]edited")
            widget.toggle_lyrics_edit_mode()

            with patch(
                "ui.audio_editor.QMessageBox.question",
                return_value=QMessageBox.StandardButton.No,
            ):
                self.assertFalse(widget.save_lrc_to_original())

            self.assertEqual(lrc.read_text(encoding="utf-8"), "[00:01.00]original")
            self.assertTrue(widget.lyrics_dirty)

            with patch(
                "ui.audio_editor.QMessageBox.question",
                return_value=QMessageBox.StandardButton.Yes,
            ):
                self.assertTrue(widget.save_lrc_to_original())

            self.assertEqual(lrc.read_text(encoding="utf-8-sig"), "[00:01.00]edited")
            self.assertFalse(widget.lyrics_dirty)
            self.assertEqual(widget.lyrics_status, "已保存到原 .lrc")
            widget.deleteLater()

    def test_write_current_audio_confirms_existing_lyrics_before_overwrite(self):
        from PySide6.QtWidgets import QMessageBox
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "Song.mp3"
            lrc = root / "Song.lrc"
            audio.write_bytes(b"fake audio")
            lrc.write_text("[00:01.00]line", encoding="utf-8")
            widget = AudioEditorWorkspace()
            widget.load_audio_file(str(audio))
            widget.sync_pending_lrc()

            with patch("ui.audio_editor.embed_lrc_to_audio") as mock_embed:
                self.assertTrue(widget.write_lyrics_to_current_audio())

            mock_embed.assert_not_called()
            self.assertEqual(
                widget.lyrics_status,
                "歌词已加入统一导出修改",
            )

            output = root / "Song_edited.mp3"
            with patch(
                "ui.audio_editor.embed_lrc_to_audio",
                return_value={"embedded": True, "skipped_reason": None, "error": None},
            ) as mock_embed:
                result = widget.export_current_workspace("save_as", output_path=str(output))

            self.assertTrue(result["success"])
            mock_embed.assert_called_once_with(str(root / ".Song_edited.exporting.tmp.mp3"), "[00:01.00]line", overwrite=True)
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_write_current_audio_keeps_dirty_when_lrc_is_unsaved(self):
        from PySide6.QtWidgets import QMessageBox
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "Song.mp3"
            lrc = root / "Song.lrc"
            audio.write_bytes(b"fake audio")
            lrc.write_text("[00:01.00]line", encoding="utf-8")
            widget = AudioEditorWorkspace()
            widget.load_audio_file(str(audio))
            widget.sync_pending_lrc()
            widget.toggle_lyrics_edit_mode()
            widget.lyrics_preview.setPlainText("[00:01.00]edited")
            widget.toggle_lyrics_edit_mode()

            self.assertTrue(widget.write_lyrics_to_current_audio())

            self.assertTrue(widget.lyrics_dirty)
            self.assertEqual(
                widget.lyrics_status,
                "歌词已加入统一导出修改",
            )
            output = root / "Song_edited.mp3"
            with patch(
                "ui.audio_editor.embed_lrc_to_audio",
                return_value={"embedded": True, "skipped_reason": None, "error": None},
            ):
                result = widget.export_current_workspace("save_as", output_path=str(output))
            self.assertTrue(result["success"])
            with patch(
                "ui.audio_editor.QMessageBox.question",
                return_value=QMessageBox.StandardButton.Yes,
            ):
                widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_write_current_audio_releases_player_source_and_retries_permission_denied(self):
        from PySide6.QtWidgets import QMessageBox
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "Song.flac"
            lrc = root / "Song.lrc"
            audio.write_bytes(b"fake audio")
            lrc.write_text("[00:01.00]line", encoding="utf-8")
            widget = AudioEditorWorkspace()
            widget.load_audio_file(str(audio))
            widget.sync_pending_lrc()
            source_empty_during_write = []

            def fake_embed(*_args, **_kwargs):
                source_empty_during_write.append(widget.player.source().isEmpty())
                return {"embedded": True, "skipped_reason": None, "error": None}

            self.assertTrue(widget.write_lyrics_to_current_audio())
            output = root / "Song_edited.flac"
            with patch("ui.audio_editor.embed_lrc_to_audio", side_effect=fake_embed) as mock_embed:
                result = widget.export_current_workspace("save_as", output_path=str(output))

            self.assertTrue(result["success"])
            self.assertEqual(mock_embed.call_count, 1)
            self.assertEqual(source_empty_during_write, [True])
            self.assertEqual(
                os.path.normcase(os.path.normpath(widget.player.source().toLocalFile())),
                os.path.normcase(os.path.normpath(str(audio))),
            )
            self.assertEqual(widget.current_audio_path, str(audio))
            self.assertIn("[00:01.00]line", widget.lyrics_preview.toPlainText())
            self.assertEqual(
                widget.lyrics_status,
                "已导出",
            )
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_write_current_audio_reloads_player_after_permission_denied_failure(self):
        from PySide6.QtWidgets import QMessageBox
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "Song.flac"
            lrc = root / "Song.lrc"
            audio.write_bytes(b"fake audio")
            lrc.write_text("[00:01.00]line", encoding="utf-8")
            widget = AudioEditorWorkspace()
            widget.load_audio_file(str(audio))
            widget.sync_pending_lrc()

            self.assertTrue(widget.write_lyrics_to_current_audio())
            output = root / "Song_edited.flac"
            with (
                patch(
                    "ui.audio_editor.embed_lrc_to_audio",
                    return_value={
                        "embedded": False,
                        "skipped_reason": None,
                        "error": "[Errno 13] Permission denied",
                    },
                ) as mock_embed,
                patch("ui.audio_editor.QMessageBox.warning") as mock_warning,
            ):
                result = widget.export_current_workspace("save_as", output_path=str(output))

            self.assertFalse(result["success"])
            self.assertEqual(mock_embed.call_count, 1)
            self.assertEqual(
                os.path.normcase(os.path.normpath(widget.player.source().toLocalFile())),
                os.path.normcase(os.path.normpath(str(audio))),
            )
            self.assertEqual(widget.lyrics_status, "歌词已加入统一导出修改")
            self.assertIn("Permission denied", widget.error_text)
            mock_warning.assert_called_once()
            widget.edit_workspace.clear_changes(remove_pending=True)
            widget.lyrics_dirty = False
            widget.clear_current_audio()
            self.app.processEvents()
            widget.deleteLater()

    def test_unsaved_lyrics_prompt_can_block_new_audio_import_and_clear(self):
        from PySide6.QtWidgets import QMessageBox
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first_audio = root / "First.mp3"
            second_audio = root / "Second.mp3"
            lrc = root / "First.lrc"
            first_audio.write_bytes(b"fake audio")
            second_audio.write_bytes(b"fake audio")
            lrc.write_text("[00:01.00]line", encoding="utf-8")
            widget = AudioEditorWorkspace()
            widget.load_audio_file(str(first_audio))
            widget.sync_pending_lrc()
            widget.toggle_lyrics_edit_mode()
            widget.lyrics_preview.setPlainText("[00:01.00]edited")
            widget.toggle_lyrics_edit_mode()

            with patch.object(widget, "_ask_workspace_switch_action", return_value="cancel"):
                self.assertFalse(widget.load_audio_file(str(second_audio)))

            self.assertEqual(widget.current_audio_path, str(first_audio))

            with patch.object(widget, "_ask_workspace_switch_action", return_value="cancel"):
                self.assertFalse(widget.clear_current_audio())

            self.assertEqual(widget.current_audio_path, str(first_audio))
            with patch.object(widget, "_ask_workspace_switch_action", return_value="discard"):
                self.assertTrue(widget.clear_current_audio())
            self.app.processEvents()
            widget.deleteLater()

    def test_netease_metadata_warning_is_shown_without_auto_cleanup(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            lrc = Path(temp_dir) / "netease.lrc"
            content = '{"t":123,"c":[{"tx":"作词"}]}\n[00:01.00]正文'
            lrc.write_text(content, encoding="utf-8")
            widget = AudioEditorWorkspace()
            widget.load_lrc_file(str(lrc), source="manual")

            self.assertFalse(widget.netease_metadata_hint.isHidden())
            self.assertTrue(widget.has_netease_metadata_warning)
            self.assertIn('{"t":123', widget.lyrics_preview.toPlainText())
            self.assertEqual(lrc.read_text(encoding="utf-8"), content)
            widget.deleteLater()

    def test_editor_drop_multiple_lrc_uses_first_only(self):
        from ui.audio_editor import AudioEditorWorkspace

        messages = []

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first_lrc = root / "first.lrc"
            second_lrc = root / "second.lrc"
            first_lrc.write_text("[00:01.00]first", encoding="utf-8")
            second_lrc.write_text("[00:01.00]second", encoding="utf-8")
            widget = AudioEditorWorkspace(log_callback=messages.append)

            with patch("watcher.handle_detected_file") as mock_handle_detected:
                self.assertTrue(widget.handle_dropped_files([str(first_lrc), str(second_lrc)]))

            self.assertIsNone(widget.current_audio_path)
            self.assertEqual(widget.current_lrc_path, str(first_lrc))
            self.assertIn("first", widget.lyrics_preview.toPlainText())
            self.assertNotIn("second", widget.lyrics_preview.toPlainText())
            self.assertTrue(any("多个 .lrc" in message for message in messages))
            mock_handle_detected.assert_not_called()
            widget.deleteLater()

    def test_editor_output_folder_is_saved_independently(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            editor_output = root / "editor"
            auto_output = root / "auto"
            widget = AudioEditorWorkspace()
            widget.config_data = {
                **config.DEFAULT_CONFIG,
                "output_folder": str(auto_output),
                "editor_output_folder": str(root / "old_editor"),
            }
            widget.editor_output_folder = str(root / "old_editor")

            with (
                patch(
                    "ui.audio_editor.QFileDialog.getExistingDirectory",
                    return_value=str(editor_output),
                ),
                patch("ui.audio_editor.load_config", return_value=widget.config_data),
                patch("ui.audio_editor.save_config", side_effect=lambda data: data) as mock_save,
            ):
                widget.select_editor_output_folder()

            saved_config = mock_save.call_args.args[0]
            self.assertEqual(saved_config["editor_output_folder"], str(editor_output))
            self.assertEqual(saved_config["output_folder"], str(auto_output))
            widget.deleteLater()

    def test_audio_browser_scans_current_folder_only(self):
        from ui.audio_editor import scan_audio_folder

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subfolder = root / "nested"
            subfolder.mkdir()
            (root / "Alpha.mp3").write_bytes(b"audio")
            (root / "beta.FLAC").write_bytes(b"audio")
            (root / "gamma.alac").write_bytes(b"audio")
            (root / "notes.txt").write_text("not audio", encoding="utf-8")
            (subfolder / "nested.mp3").write_bytes(b"audio")

            result = scan_audio_folder(str(root))

        self.assertTrue(result["success"])
        self.assertEqual(
            [item["filename"] for item in result["files"]],
            ["Alpha.mp3", "beta.FLAC", "gamma.alac"],
        )
        self.assertEqual([item["ext"] for item in result["files"]], ["MP3", "FLAC", "ALAC"])

    def test_audio_project_browser_scans_recursively(self):
        from ui.audio_editor import scan_audio_project_folders

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            nested = root / "nested"
            nested.mkdir()
            (root / "Alpha.mp3").write_bytes(b"audio")
            (nested / "Beta.FLAC").write_bytes(b"audio")
            (nested / "notes.txt").write_text("not audio", encoding="utf-8")

            result = scan_audio_project_folders([str(root)])

        self.assertTrue(result["success"])
        self.assertEqual(
            [item["filename"] for item in result["files"]],
            ["Alpha.mp3", "Beta.FLAC"],
        )
        self.assertEqual(result["files"][1]["relative_dir_parts"], ["nested"])

    def test_audio_browser_filter_and_load_use_editor_only_flow(self):
        from PySide6.QtCore import QEvent, QPoint, Qt
        from PySide6.QtGui import QKeyEvent
        from ui.audio_editor import (
            AudioEditorWorkspace,
            BrowserTreeChevronStyle,
            NoFocusTreeItemDelegate,
            scan_audio_project_folders,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            nested = root / "Nested"
            nested.mkdir()
            first = root / "first.mp3"
            second = nested / "second.flac"
            first.write_bytes(b"audio")
            second.write_bytes(b"audio")
            with patch(
                "ui.audio_editor.load_config",
                return_value={**config.DEFAULT_CONFIG, "editor_project_folders": [], "editor_browser_folder": ""},
            ):
                widget = AudioEditorWorkspace()

            try:
                with patch("ui.audio_editor.save_config", side_effect=lambda data: data) as mock_save:
                    self.assertTrue(widget.set_editor_browser_folder(str(root), scan=False))

                saved_config = mock_save.call_args.args[0]
                self.assertEqual(saved_config["editor_browser_folder"], os.path.normpath(os.path.abspath(str(root))))
                self.assertEqual(saved_config["editor_project_folders"], [os.path.normpath(os.path.abspath(str(root)))])
                widget.browser_all_files = scan_audio_project_folders([str(root)])["files"]
                with patch("ui.audio_editor.read_audio_cover_preview") as mock_preview:
                    widget.apply_browser_filter()
                mock_preview.assert_not_called()
                self.assertFalse(hasattr(widget, "browser_table"))
                self.assertEqual(widget.browser_tree.topLevelItemCount(), 1)
                root_item = widget.browser_tree.topLevelItem(0)
                self.assertEqual(root_item.text(0), root.name)
                self.assertEqual(root_item.data(0, Qt.ItemDataRole.UserRole + 3), root.name)
                self.assertTrue(root_item.icon(0).isNull())
                self.assertFalse(root_item.isExpanded())
                self.assertLessEqual(root_item.sizeHint(0).height(), 28)
                browser_tree_style = widget.browser_tree.styleSheet()
                self.assertIn("outline: 0", browser_tree_style)
                self.assertIn("QTreeWidget::item:hover", browser_tree_style)
                self.assertIn("QTreeWidget::item:selected", browser_tree_style)
                self.assertNotIn("QTreeView::branch", browser_tree_style)
                self.assertIsInstance(widget.browser_tree_chevron_style, BrowserTreeChevronStyle)
                self.assertIsInstance(widget.browser_tree.itemDelegate(), NoFocusTreeItemDelegate)
                self.assertTrue(widget.browser_tree.rootIsDecorated())
                self.assertTrue(widget.browser_tree.itemsExpandable())
                self.assertFalse(widget.browser_tree.expandsOnDoubleClick())
                self.assertFalse(widget.browser_tree.isAnimated())

                with (
                    patch.object(widget, "start_editor_browser_scan") as mock_scan,
                    patch.object(widget, "load_audio_file") as mock_load,
                    patch("ui.audio_editor.read_audio_cover_preview") as mock_preview,
                ):
                    self.assertFalse(widget.is_browser_folder_arrow_click(root_item, QPoint(160, 4)))
                    self.assertTrue(widget.is_browser_folder_arrow_click(root_item, QPoint(1, 4)))
                    self.assertTrue(widget.toggle_browser_folder_item(root_item))
                    self.assertTrue(root_item.isExpanded())
                    self.assertEqual(root_item.text(0), root.name)
                    self.assertTrue(root_item.icon(0).isNull())
                    expanded_after_click = root_item.isExpanded()
                    self.assertTrue(widget.on_browser_item_double_clicked(root_item))
                    self.assertEqual(root_item.isExpanded(), expanded_after_click)
                    widget.browser_tree.setCurrentItem(root_item)
                    enter_event = QKeyEvent(
                        QEvent.Type.KeyPress,
                        Qt.Key.Key_Return,
                        Qt.KeyboardModifier.NoModifier,
                    )
                    self.assertTrue(widget.eventFilter(widget.browser_tree, enter_event))
                    self.assertEqual(root_item.isExpanded(), expanded_after_click)

                mock_scan.assert_not_called()
                mock_load.assert_not_called()
                mock_preview.assert_not_called()
                self.assertEqual(widget.browser_preview_name.full_text(), root.name)
                self.assertEqual(widget.browser_preview_detail.text(), "1 个文件夹 · 2 个音频")

                widget.browser_filter_edit.setText("second")
                self.app.processEvents()
                self.assertEqual(widget.browser_tree.topLevelItemCount(), 1)

                def find_audio_item(path):
                    expected = os.path.normpath(os.path.abspath(str(path)))
                    for tree_item in widget._iter_browser_tree_items():
                        if tree_item.data(0, Qt.ItemDataRole.UserRole + 1) != "audio":
                            continue
                        if tree_item.data(0, Qt.ItemDataRole.UserRole) == expected:
                            return tree_item
                    return None

                second_item = find_audio_item(second)
                self.assertIsNotNone(second_item)
                self.assertEqual(second_item.text(0), "second.flac")
                self.assertEqual(second_item.data(0, Qt.ItemDataRole.UserRole + 3), "second.flac")
                widget.current_audio_path = os.path.normpath(os.path.abspath(str(second)))
                widget.apply_browser_filter()
                second_item = find_audio_item(second)
                self.assertIsNotNone(second_item)
                self.assertEqual(second_item.text(0), "▶ second.flac")
                self.assertEqual(second_item.data(0, Qt.ItemDataRole.UserRole + 3), "second.flac")
                self.assertIn("当前编辑文件", second_item.toolTip(0))
                widget.current_audio_path = os.path.normpath(os.path.abspath(str(first)))
                widget.apply_browser_filter()
                second_item = find_audio_item(second)
                self.assertIsNotNone(second_item)
                self.assertEqual(second_item.text(0), "second.flac")
                with patch(
                    "ui.audio_editor.read_audio_cover_preview",
                    return_value={
                        "success": True,
                        "cover_data": None,
                        "cover_mime": None,
                        "error": None,
                    },
                ) as mock_preview:
                    widget.browser_tree.setCurrentItem(second_item)

                mock_preview.assert_called_once_with(os.path.normpath(os.path.abspath(str(second))))
                self.assertEqual(widget.browser_selected_file_path, os.path.normpath(os.path.abspath(str(second))))
                self.assertEqual(widget.browser_preview_name.full_text(), "second.flac")
                self.assertFalse(widget.browser_preview_name.wordWrap())
                self.assertLessEqual(widget.browser_preview_frame.maximumHeight(), 96)
                self.assertEqual(widget.browser_preview_detail.text(), "FLAC · 5 B")
                self.assertEqual(widget.browser_preview_cover.text(), "无封面")
                self.assertIn(str(second), widget.browser_preview_name.toolTip())

                with (
                    patch.object(widget, "load_audio_file", return_value=True) as mock_load,
                    patch("watcher.handle_detected_file") as mock_handle_detected,
                ):
                    self.assertTrue(widget.on_browser_item_double_clicked(second_item))

                mock_load.assert_called_once_with(
                    os.path.normpath(os.path.abspath(str(second))),
                    source="browser",
                )
                mock_handle_detected.assert_not_called()

                with (
                    patch.object(widget, "load_audio_file", return_value=True) as mock_load,
                    patch("watcher.handle_detected_file") as mock_handle_detected,
                ):
                    enter_event = QKeyEvent(
                        QEvent.Type.KeyPress,
                        Qt.Key.Key_Return,
                        Qt.KeyboardModifier.NoModifier,
                    )
                    self.assertTrue(widget.eventFilter(widget.browser_tree, enter_event))

                mock_load.assert_called_once_with(
                    os.path.normpath(os.path.abspath(str(second))),
                    source="browser",
                )
                mock_handle_detected.assert_not_called()
                self.assertEqual(widget.browser_selected_file_path, os.path.normpath(os.path.abspath(str(second))))
                self.assertEqual(widget.browser_preview_name.full_text(), "second.flac")

                widget.current_audio_path = os.path.normpath(os.path.abspath(str(first)))
                with patch.object(widget, "confirm_discard_unsaved_changes", return_value=True):
                    self.assertTrue(widget.clear_current_audio())
                self.assertEqual(widget.browser_selected_file_path, os.path.normpath(os.path.abspath(str(second))))
                self.assertEqual(widget.browser_preview_name.full_text(), "second.flac")

                with patch("ui.audio_editor.save_config", side_effect=lambda data: data) as mock_save:
                    self.assertTrue(widget.set_browser_sidebar_collapsed(True))
                    collapsed_config = mock_save.call_args.args[0]

                self.assertTrue(collapsed_config["editor_browser_collapsed"])
                self.assertTrue(widget.browser_content_widget.isHidden())
                self.assertTrue(widget.browser_preview_frame.isHidden())
                self.assertLessEqual(widget.browser_sidebar.maximumWidth(), 42)

                with patch("ui.audio_editor.save_config", side_effect=lambda data: data):
                    self.assertTrue(widget.set_browser_sidebar_collapsed(False))

                self.assertFalse(widget.browser_content_widget.isHidden())
                self.assertFalse(widget.browser_preview_frame.isHidden())
                self.assertGreaterEqual(widget.browser_sidebar.minimumWidth(), 220)

                widget.current_audio_path = str(first)
                with patch("ui.audio_editor.save_config", side_effect=lambda data: data):
                    self.assertTrue(widget.clear_editor_browser_folder())

                self.assertEqual(widget.current_audio_path, str(first))
                self.assertEqual(widget.browser_tree.topLevelItemCount(), 0)
                self.assertEqual(widget.browser_folder_value.text(), "未添加项目文件夹")
            finally:
                widget.clear_current_audio()
                self.app.processEvents()
                widget.deleteLater()

    def test_audio_browser_project_folder_merge_rules(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            house = root / "House"
            tech = house / "Tech House"
            piano = house / "Piano House"
            trance = root / "Trance"
            tech.mkdir(parents=True)
            piano.mkdir()
            trance.mkdir()
            with patch(
                "ui.audio_editor.load_config",
                return_value={**config.DEFAULT_CONFIG, "editor_project_folders": [], "editor_browser_folder": ""},
            ):
                widget = AudioEditorWorkspace()

            try:
                with patch("ui.audio_editor.save_config", side_effect=lambda data: data):
                    self.assertTrue(widget.add_editor_project_folder(str(tech), scan=False))
                    self.assertTrue(widget.add_editor_project_folder(str(piano), scan=False))
                    self.assertEqual(
                        widget.editor_project_folders,
                        [
                            os.path.normpath(os.path.abspath(str(tech))),
                            os.path.normpath(os.path.abspath(str(piano))),
                        ],
                    )
                    self.assertTrue(widget.add_editor_project_folder(str(house), scan=False))

                self.assertEqual(widget.editor_project_folders, [os.path.normpath(os.path.abspath(str(house)))])

                with patch("ui.audio_editor.save_config", side_effect=lambda data: data):
                    self.assertTrue(widget.add_editor_project_folder(str(tech), scan=False))
                self.assertEqual(widget.editor_project_folders, [os.path.normpath(os.path.abspath(str(house)))])

                with patch("ui.audio_editor.save_config", side_effect=lambda data: data):
                    self.assertTrue(widget.add_editor_project_folder(str(trance), scan=False))
                self.assertEqual(
                    widget.editor_project_folders,
                    [
                        os.path.normpath(os.path.abspath(str(house))),
                        os.path.normpath(os.path.abspath(str(trance))),
                    ],
                )
            finally:
                widget.deleteLater()

    def test_audio_browser_dropped_folders_do_not_enter_transcode_queue(self):
        from ui.audio_editor import AudioEditorWorkspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "Project"
            project.mkdir()
            audio_file = root / "loose.flac"
            audio_file.write_bytes(b"audio")
            with patch(
                "ui.audio_editor.load_config",
                return_value={**config.DEFAULT_CONFIG, "editor_project_folders": [], "editor_browser_folder": ""},
            ):
                widget = AudioEditorWorkspace()

            try:
                with (
                    patch.object(widget, "start_editor_browser_scan", return_value=True) as mock_scan,
                    patch("ui.audio_editor.save_config", side_effect=lambda data: data),
                    patch("watcher.handle_detected_file") as mock_handle_detected,
                ):
                    self.assertTrue(widget.add_dropped_project_folders([str(project), str(audio_file)]))

                self.assertEqual(widget.editor_project_folders, [os.path.normpath(os.path.abspath(str(project)))])
                mock_scan.assert_called_once()
                mock_handle_detected.assert_not_called()
            finally:
                widget.deleteLater()


class TaskQueueDropTests(unittest.TestCase):

    def test_transcode_context_menu_state_updates_from_current_tasks(self):
        from PySide6.QtWidgets import QApplication, QWidget
        from ui.main_window import MainWindow

        app = QApplication.instance() or QApplication([])

        class DummyWindow(QWidget):
            def __init__(self, selected_tasks, convert_running=False, retry_running=False):
                super().__init__()
                self.selected_tasks = selected_tasks
                self.convert_running = convert_running
                self.retry_running = retry_running

            def _get_selected_tasks(self):
                return self.selected_tasks

            def _is_convert_thread_running(self):
                return self.convert_running

            def _is_retry_thread_running(self):
                return self.retry_running

            def get_file_table_context_menu_state(self):
                return MainWindow.get_file_table_context_menu_state(self)

            def start_convert_selected(self):
                pass

            def start_convert(self):
                pass

            def _set_selected_target_format_from_menu(self, _target_format):
                pass

            def retry_failed_items(self):
                pass

            def remove_selected_items(self):
                pass

            def clear_terminal_items(self):
                pass

            def open_selected_source_location(self):
                pass

            def copy_selected_source_paths(self):
                pass

            def show_selected_task_status(self):
                pass

        def action_by_text(menu, text):
            for action in menu.actions():
                if action.text() == text:
                    return action
            raise AssertionError(f"missing action: {text}")

        with tempfile.TemporaryDirectory() as temp_dir:
            existing = Path(temp_dir) / "waiting.flac"
            existing.write_bytes(b"audio")
            waiting_task = {"path": str(existing), "status": watcher.WAITING_STATUS}
            processing_task = {"path": str(existing), "status": watcher.PROCESSING_STATUS}
            failed_task = {"path": str(existing), "status": watcher.FAILED_STATUS}
            completed_task = {"path": str(existing), "status": watcher.COMPLETED_STATUS}

            with patch("ui.main_window.watcher.get_task_snapshots", return_value=[]):
                dummy = DummyWindow([])
                state = MainWindow.get_file_table_context_menu_state(dummy)
                self.assertFalse(state["can_start_selected"])
                self.assertFalse(state["can_start_all"])
                self.assertFalse(state["can_set_format"])
                self.assertFalse(state["can_retry_failed"])
                self.assertFalse(state["can_remove_selected"])
                self.assertFalse(state["can_open_source"])

            with patch(
                "ui.main_window.watcher.get_task_snapshots",
                return_value=[waiting_task, completed_task],
            ):
                dummy = DummyWindow([waiting_task])
                menu = MainWindow._build_file_table_context_menu(dummy)

            try:
                self.assertTrue(action_by_text(menu, "开始转换选中条目").isEnabled())
                self.assertTrue(action_by_text(menu, "开始转换全部等待条目").isEnabled())
                self.assertTrue(action_by_text(menu, "设置目标格式").isEnabled())
                self.assertTrue(action_by_text(menu, "清除已完成/失败记录").isEnabled())
                self.assertTrue(action_by_text(menu, "打开源文件位置").isEnabled())
                self.assertFalse(action_by_text(menu, "重试失败条目").isEnabled())
                self.assertFalse(any("不可用" in action.text() for action in menu.actions()))
            finally:
                menu.deleteLater()
                dummy.deleteLater()

            with patch(
                "ui.main_window.watcher.get_task_snapshots",
                return_value=[processing_task, failed_task],
            ):
                dummy = DummyWindow([processing_task])
                menu = MainWindow._build_file_table_context_menu(dummy)

            try:
                self.assertFalse(action_by_text(menu, "开始转换选中条目").isEnabled())
                self.assertFalse(action_by_text(menu, "设置目标格式").isEnabled())
                self.assertFalse(action_by_text(menu, "移除选中条目").isEnabled())
            finally:
                menu.deleteLater()
                dummy.deleteLater()

            with patch(
                "ui.main_window.watcher.get_task_snapshots",
                return_value=[failed_task],
            ):
                dummy = DummyWindow([failed_task])
                menu = MainWindow._build_file_table_context_menu(dummy)

            try:
                self.assertTrue(action_by_text(menu, "重试失败条目").isEnabled())
                self.assertFalse(action_by_text(menu, "开始转换全部等待条目").isEnabled())
            finally:
                menu.deleteLater()
                dummy.deleteLater()

    def test_dropped_files_are_queued_through_watcher(self):
        from ui.main_window import MainWindow

        class DummyLog:
            def __init__(self):
                self.messages = []

            def append(self, message):
                self.messages.append(message)

        class DummyWindow:
            def __init__(self):
                self.log_box = DummyLog()
                self.prepare_calls = 0
                self.refresh_calls = 0
                self.selection_calls = 0

            def start_prepare_thread(self):
                self.prepare_calls += 1

            def refresh_file_table(self):
                self.refresh_calls += 1

            def update_selection_panel(self):
                self.selection_calls += 1

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "sample.flac"
            folder = root / "folder"
            missing = root / "missing.mp3"
            source.write_bytes(b"audio")
            folder.mkdir()
            dummy = DummyWindow()

            with patch(
                "ui.main_window.watcher.handle_detected_file",
                return_value=True,
            ) as mock_handle:
                MainWindow.handle_dropped_files(
                    dummy,
                    [str(source), str(folder), str(missing), ""],
                )

            mock_handle.assert_called_once_with(
                os.path.normpath(os.path.abspath(str(source))),
                source="manual_drop",
            )
            self.assertEqual(dummy.prepare_calls, 1)
            self.assertEqual(dummy.refresh_calls, 1)
            self.assertEqual(dummy.selection_calls, 1)
            self.assertTrue(
                any("暂不支持拖入文件夹" in message for message in dummy.log_box.messages)
            )
            self.assertTrue(
                any("拖入路径不存在" in message for message in dummy.log_box.messages)
            )


if __name__ == "__main__":
    unittest.main()
