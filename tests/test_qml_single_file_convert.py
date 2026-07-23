import copy
import errno
import hashlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

import single_file_convert
import config
import converter
import watcher
from ui_next.bridge.capabilities import SINGLE_FILE_CONVERT, CapabilityGate
from ui_next.bridge.single_file_convert_viewmodel import SingleFileConvertViewModel


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SingleFileConvertServiceTests(unittest.TestCase):
    def test_success_writes_new_output_via_temp_without_touching_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ffmpeg = root / "ffmpeg.exe"
            ffmpeg.write_bytes(b"ffmpeg")
            source = root / "源 文件.wav"
            source.write_bytes(b"source-audio")
            output = root / "输出 文件.mp3"
            before_source = file_sha(source)
            commands = []

            def fake_run(command, **kwargs):
                commands.append(command)
                self.assertIn("-n", command)
                self.assertNotIn("-y", command)
                self.assertIn("-map_metadata", command)
                self.assertIn("-map_chapters", command)
                self.assertIn("-vn", command)
                self.assertEqual(command[0], str(ffmpeg))
                self.assertTrue(Path(command[command.index("-i") + 1]).samefile(source))
                temp_output = Path(command[-1])
                self.assertIn(".qonic_tmp", temp_output.name)
                self.assertEqual(temp_output.suffix, ".mp3")
                temp_output.write_bytes(b"converted-audio")
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout="",
                    stderr="conversion ok",
                )

            with (
                patch("single_file_convert.FFMPEG_PATH", str(ffmpeg)),
                patch("single_file_convert.subprocess.run", side_effect=fake_run) as run,
            ):
                result = single_file_convert.convert_single_file_to_new_path(
                    str(source),
                    str(output),
                    "mp3",
                )

            self.assertTrue(result["ok"])
            self.assertTrue(output.exists())
            self.assertEqual(output.read_bytes(), b"converted-audio")
            self.assertEqual(file_sha(source), before_source)
            self.assertEqual(result["output_size_bytes"], len(b"converted-audio"))
            self.assertEqual(result["ffmpeg_returncode"], 0)
            self.assertEqual(result["finalization_strategy"], "hardlink")
            self.assertTrue(result["temp_cleanup_ok"])
            self.assertEqual(len(list(root.glob("*.qonic_tmp.*"))), 0)
            run.assert_called_once()
            self.assertEqual(len(commands), 1)

    def test_existing_output_is_rejected_and_not_modified(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ffmpeg = root / "ffmpeg.exe"
            ffmpeg.write_bytes(b"ffmpeg")
            source = root / "source.wav"
            source.write_bytes(b"source-audio")
            output = root / "out.flac"
            output.write_bytes(b"existing-output")
            before_output = file_sha(output)

            with (
                patch("single_file_convert.FFMPEG_PATH", str(ffmpeg)),
                patch("single_file_convert.subprocess.run") as run,
            ):
                result = single_file_convert.convert_single_file_to_new_path(
                    str(source),
                    str(output),
                    "flac",
                )

            self.assertFalse(result["ok"])
            self.assertIn("已阻止覆盖", result["error"])
            self.assertEqual(file_sha(output), before_output)
            run.assert_not_called()

    def test_failed_ffmpeg_removes_temp_and_leaves_no_final_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ffmpeg = root / "ffmpeg.exe"
            ffmpeg.write_bytes(b"ffmpeg")
            source = root / "source.wav"
            source.write_bytes(b"source-audio")
            output = root / "out.ogg"
            before_source = file_sha(source)

            def fake_run(command, **kwargs):
                Path(command[-1]).write_bytes(b"partial")
                return subprocess.CompletedProcess(
                    command,
                    1,
                    stdout="",
                    stderr="ffmpeg failed",
                )

            with (
                patch("single_file_convert.FFMPEG_PATH", str(ffmpeg)),
                patch("single_file_convert.subprocess.run", side_effect=fake_run),
            ):
                result = single_file_convert.convert_single_file_to_new_path(
                    str(source),
                    str(output),
                    "ogg",
                )

            self.assertFalse(result["ok"])
            self.assertFalse(output.exists())
            self.assertEqual(file_sha(source), before_source)
            self.assertEqual(result["error_code"], "FFMPEG_FAILED")
            self.assertEqual(len(list(root.glob("*.qonic_tmp.*"))), 0)
            self.assertEqual(result["ffmpeg_returncode"], 1)

    def test_ncm_is_rejected_before_ffmpeg(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ffmpeg = root / "ffmpeg.exe"
            ffmpeg.write_bytes(b"ffmpeg")
            source = root / "song.ncm"
            source.write_bytes(b"ncm")
            output = root / "song.flac"

            with (
                patch("single_file_convert.FFMPEG_PATH", str(ffmpeg)),
                patch("single_file_convert.subprocess.run") as run,
            ):
                result = single_file_convert.convert_single_file_to_new_path(
                    str(source),
                    str(output),
                    "flac",
                )

            self.assertFalse(result["ok"])
            self.assertIn("暂不支持 NCM", result["error"])
            self.assertFalse(output.exists())
            run.assert_not_called()

    def test_target_format_must_match_output_suffix(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ffmpeg = root / "ffmpeg.exe"
            ffmpeg.write_bytes(b"ffmpeg")
            source = root / "source.wav"
            source.write_bytes(b"source-audio")
            output = root / "out.mp3"

            with patch("single_file_convert.FFMPEG_PATH", str(ffmpeg)):
                result = single_file_convert.validate_single_file_convert_request(
                    str(source),
                    str(output),
                    "flac",
                )

            self.assertFalse(result["ok"])
            self.assertIn("后缀不一致", result["error"])
            self.assertEqual(result["error_code"], "INVALID_OUTPUT_PATH")

    def test_hardlink_finalization_rejects_external_output_created_in_race(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ffmpeg = root / "ffmpeg.exe"
            ffmpeg.write_bytes(b"ffmpeg")
            source = root / "source.wav"
            source.write_bytes(b"source-audio")
            output = root / "out.flac"

            def fake_run(command, **kwargs):
                Path(command[-1]).write_bytes(b"converted-audio")
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

            def external_process_wins(_temp_path, final_path):
                Path(final_path).write_bytes(b"external-output")
                raise FileExistsError(errno.EEXIST, "already exists", str(final_path))

            with (
                patch("single_file_convert.FFMPEG_PATH", str(ffmpeg)),
                patch("single_file_convert.subprocess.run", side_effect=fake_run),
                patch("single_file_convert.os.link", side_effect=external_process_wins),
            ):
                result = single_file_convert.convert_single_file_to_new_path(
                    str(source),
                    str(output),
                    "flac",
                )

            self.assertFalse(result["ok"])
            self.assertEqual(result["error_code"], "OUTPUT_CONFLICT")
            self.assertTrue(result["output_conflict"])
            self.assertEqual(output.read_bytes(), b"external-output")
            self.assertEqual(len(list(root.glob("*.qonic_tmp.*"))), 0)

    def test_exclusive_copy_fallback_is_no_clobber_when_hardlinks_unavailable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ffmpeg = root / "ffmpeg.exe"
            ffmpeg.write_bytes(b"ffmpeg")
            source = root / "source.wav"
            source.write_bytes(b"source-audio")
            output = root / "out.flac"

            def fake_run(command, **kwargs):
                Path(command[-1]).write_bytes(b"converted-audio")
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

            with (
                patch("single_file_convert.FFMPEG_PATH", str(ffmpeg)),
                patch("single_file_convert.subprocess.run", side_effect=fake_run),
                patch(
                    "single_file_convert.os.link",
                    side_effect=OSError(errno.EOPNOTSUPP, "hardlink unavailable"),
                ),
            ):
                result = single_file_convert.convert_single_file_to_new_path(
                    str(source),
                    str(output),
                    "flac",
                )

            self.assertTrue(result["ok"])
            self.assertEqual(result["finalization_strategy"], "exclusive_copy")
            self.assertEqual(output.read_bytes(), b"converted-audio")
            self.assertEqual(len(list(root.glob("*.qonic_tmp.*"))), 0)

    def test_exclusive_copy_fallback_rejects_external_output_race(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ffmpeg = root / "ffmpeg.exe"
            ffmpeg.write_bytes(b"ffmpeg")
            source = root / "source.wav"
            source.write_bytes(b"source-audio")
            output = root / "out.flac"

            def fake_run(command, **kwargs):
                Path(command[-1]).write_bytes(b"converted-audio")
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

            def external_process_wins(path, flags, mode=0o777):
                self.assertTrue(flags & os.O_EXCL)
                Path(path).write_bytes(b"external-output")
                raise FileExistsError(errno.EEXIST, "already exists", path)

            with (
                patch("single_file_convert.FFMPEG_PATH", str(ffmpeg)),
                patch("single_file_convert.subprocess.run", side_effect=fake_run),
                patch(
                    "single_file_convert.os.link",
                    side_effect=OSError(errno.EOPNOTSUPP, "hardlink unavailable"),
                ),
                patch("single_file_convert.os.open", side_effect=external_process_wins),
            ):
                result = single_file_convert.convert_single_file_to_new_path(
                    str(source), str(output), "flac"
                )

            self.assertFalse(result["ok"])
            self.assertEqual(result["error_code"], "OUTPUT_CONFLICT")
            self.assertEqual(result["finalization_strategy"], "exclusive_copy")
            self.assertEqual(output.read_bytes(), b"external-output")
            self.assertEqual(len(list(root.glob("*.qonic_tmp.*"))), 0)

    def test_empty_temp_output_is_rejected_and_cleaned(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ffmpeg = root / "ffmpeg.exe"
            ffmpeg.write_bytes(b"ffmpeg")
            source = root / "source.wav"
            source.write_bytes(b"source-audio")
            output = root / "out.ogg"

            def fake_run(command, **kwargs):
                Path(command[-1]).write_bytes(b"")
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

            with (
                patch("single_file_convert.FFMPEG_PATH", str(ffmpeg)),
                patch("single_file_convert.subprocess.run", side_effect=fake_run),
            ):
                result = single_file_convert.convert_single_file_to_new_path(
                    str(source), str(output), "ogg"
                )

            self.assertFalse(result["ok"])
            self.assertEqual(result["error_code"], "TEMP_OUTPUT_EMPTY")
            self.assertFalse(output.exists())
            self.assertEqual(len(list(root.glob("*.qonic_tmp.*"))), 0)

    def test_temp_paths_are_unique_keep_audio_extension_and_do_not_touch_similar_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = root / "song.flac"
            first = single_file_convert._make_temp_output_path(output)
            second = single_file_convert._make_temp_output_path(output)
            similar = root / ".song.unrelated.qonic_tmp.flac"
            similar.write_bytes(b"do-not-delete")
            ffmpeg = root / "ffmpeg.exe"
            ffmpeg.write_bytes(b"ffmpeg")
            source = root / "source.wav"
            source.write_bytes(b"source-audio")

            self.assertIsNotNone(first)
            self.assertIsNotNone(second)
            self.assertNotEqual(first, second)
            self.assertEqual(first.suffix, ".flac")
            self.assertIn(".qonic_tmp", first.name)

            def fake_run(command, **kwargs):
                Path(command[-1]).write_bytes(b"partial")
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="failed")

            with (
                patch("single_file_convert.FFMPEG_PATH", str(ffmpeg)),
                patch("single_file_convert.subprocess.run", side_effect=fake_run),
            ):
                result = single_file_convert.convert_single_file_to_new_path(
                    str(source), str(output), "flac"
                )

            self.assertFalse(result["ok"])
            self.assertTrue(similar.exists())
            self.assertEqual(similar.read_bytes(), b"do-not-delete")

    def test_cleanup_failure_is_returned_as_warning_without_deleting_unknown_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ffmpeg = root / "ffmpeg.exe"
            ffmpeg.write_bytes(b"ffmpeg")
            source = root / "source.wav"
            source.write_bytes(b"source-audio")
            output = root / "out.ogg"

            def fake_run(command, **kwargs):
                Path(command[-1]).write_bytes(b"partial")
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="failed")

            with (
                patch("single_file_convert.FFMPEG_PATH", str(ffmpeg)),
                patch("single_file_convert.subprocess.run", side_effect=fake_run),
                patch(
                    "single_file_convert._cleanup_owned_temp",
                    return_value=(False, "临时文件清理失败：测试锁定"),
                ),
            ):
                result = single_file_convert.convert_single_file_to_new_path(
                    str(source), str(output), "ogg"
                )

            self.assertFalse(result["ok"])
            self.assertFalse(result["temp_cleanup_ok"])
            self.assertIn("临时文件清理失败", result["warning"])
            for path in root.glob("*.qonic_tmp.*"):
                path.unlink()

    def test_same_path_case_variant_and_relative_path_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ffmpeg = root / "ffmpeg.exe"
            ffmpeg.write_bytes(b"ffmpeg")
            source = root / "source.wav"
            source.write_bytes(b"source-audio")

            with patch("single_file_convert.FFMPEG_PATH", str(ffmpeg)):
                same_path = single_file_convert.validate_single_file_convert_request(
                    str(source), str(source), "wav"
                )
                case_variant = single_file_convert.validate_single_file_convert_request(
                    str(source), str(source).upper(), "wav"
                )
                original_cwd = Path.cwd()
                try:
                    os.chdir(root)
                    relative_path = single_file_convert.validate_single_file_convert_request(
                        "source.wav", "source.wav", "wav"
                    )
                finally:
                    os.chdir(original_cwd)

            self.assertEqual(same_path["error_code"], "INVALID_OUTPUT_PATH")
            self.assertEqual(case_variant["error_code"], "INVALID_OUTPUT_PATH")
            self.assertEqual(relative_path["error_code"], "INVALID_OUTPUT_PATH")

    def test_service_keeps_config_and_watcher_runtime_state_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ffmpeg = root / "ffmpeg.exe"
            ffmpeg.write_bytes(b"ffmpeg")
            source = root / "source.wav"
            source.write_bytes(b"source-audio")
            output = root / "out.flac"
            source_before = file_sha(source)
            config_before = file_sha(Path(config.CONFIG_FILE))
            pending_before = repr(copy.deepcopy(watcher.pending_files))
            processed_before = repr(copy.deepcopy(watcher.processed_files))
            snapshots_before = repr(watcher.get_task_snapshots())

            def fake_run(command, **kwargs):
                Path(command[-1]).write_bytes(b"converted-audio")
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

            with (
                patch("single_file_convert.FFMPEG_PATH", str(ffmpeg)),
                patch("single_file_convert.subprocess.run", side_effect=fake_run),
                patch.object(converter, "convert_audio", side_effect=AssertionError),
                patch.object(config, "save_config", side_effect=AssertionError),
                patch.object(watcher, "scan_existing_files", side_effect=AssertionError),
                patch.object(watcher, "handle_detected_file", side_effect=AssertionError),
                patch.object(watcher, "add_pending_file", side_effect=AssertionError),
            ):
                result = single_file_convert.convert_single_file_to_new_path(
                    str(source), str(output), "flac"
                )

            self.assertTrue(result["ok"])
            self.assertEqual(file_sha(source), source_before)
            self.assertEqual(file_sha(Path(config.CONFIG_FILE)), config_before)
            self.assertEqual(repr(watcher.pending_files), pending_before)
            self.assertEqual(repr(watcher.processed_files), processed_before)
            self.assertEqual(repr(watcher.get_task_snapshots()), snapshots_before)

    def test_service_sources_do_not_import_forbidden_workflows(self):
        source = Path("single_file_convert.py").read_text(encoding="utf-8")

        self.assertNotIn("import watcher", source)
        self.assertNotIn("import converter", source)
        self.assertNotIn("save_config", source)
        self.assertNotIn("convert_audio", source)
        self.assertNotIn("os.replace", source)


class SingleFileConvertViewModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def wait_for_conversion(self, view_model: SingleFileConvertViewModel) -> None:
        if not view_model.isConverting:
            return
        loop = QEventLoop()

        def maybe_quit():
            if not view_model.isConverting:
                loop.quit()

        view_model.stateChanged.connect(maybe_quit)
        QTimer.singleShot(3000, loop.quit)
        loop.exec()
        try:
            view_model.stateChanged.disconnect(maybe_quit)
        except (RuntimeError, TypeError):
            pass
        self.assertFalse(view_model.isConverting)

    def test_preview_mode_does_not_validate_or_convert(self):
        view_model = SingleFileConvertViewModel()
        view_model.setInputPath("D:/Music/source.wav")
        view_model.setOutputPath("D:/Music/out.flac")

        with (
            patch(
                "ui_next.bridge.single_file_convert_viewmodel.validate_single_file_convert_request"
            ) as validate,
            patch(
                "ui_next.bridge.single_file_convert_viewmodel.convert_single_file_to_new_path"
            ) as convert,
        ):
            view_model.startSingleFileConvert()

        validate.assert_not_called()
        convert.assert_not_called()
        self.assertTrue(view_model.previewMode)
        self.assertIn("单文件转换不可用", view_model.statusMessage)

    def test_enabled_conversion_maps_worker_result(self):
        view_model = SingleFileConvertViewModel(
            CapabilityGate(SINGLE_FILE_CONVERT)
        )
        view_model.setInputPath("D:/Music/source.wav")
        view_model.setOutputPath("D:/Music/out.flac")
        fake_validation = {
            "ok": True,
            "error": "",
            "input_path": "D:/Music/source.wav",
            "output_path": "D:/Music/out.flac",
            "target_format": "flac",
            "source_size_bytes": 12,
        }
        fake_result = {
            "ok": True,
            "error": "",
            "error_code": "",
            "input_path": "D:/Music/source.wav",
            "output_path": "D:/Music/out.flac",
            "target_format": "flac",
            "source_size_bytes": 12,
            "output_size_bytes": 8,
            "duration_ms": 123,
            "ffmpeg_returncode": 0,
            "ffmpeg_stderr_tail": "",
            "finalization_strategy": "hardlink",
            "temp_cleanup_ok": True,
            "warning": "",
        }

        with (
            patch(
                "ui_next.bridge.single_file_convert_viewmodel.validate_single_file_convert_request",
                return_value=fake_validation,
            ) as validate,
            patch(
                "ui_next.bridge.single_file_convert_viewmodel.convert_single_file_to_new_path",
                return_value=fake_result,
            ) as convert,
        ):
            view_model.startSingleFileConvert()
            self.wait_for_conversion(view_model)

        validate.assert_called()
        convert.assert_called_once_with(
            "D:/Music/source.wav",
            "D:/Music/out.flac",
            "flac",
        )
        self.assertFalse(view_model.previewMode)
        self.assertEqual(view_model.convertStatus, "转换成功")
        self.assertEqual(view_model.outputSizeText, "8 B")
        self.assertEqual(view_model.durationMs, 123)
        self.assertEqual(view_model.lastResultPath, "D:/Music/out.flac")
        self.assertEqual(view_model.finalizationStrategy, "hardlink")

    def test_output_conflict_result_maps_to_specific_safe_status(self):
        view_model = SingleFileConvertViewModel(
            CapabilityGate(SINGLE_FILE_CONVERT)
        )
        view_model.setInputPath("D:/Music/source.wav")
        view_model.setOutputPath("D:/Music/out.flac")
        fake_validation = {
            "ok": True,
            "error": "",
            "error_code": "",
            "input_path": "D:/Music/source.wav",
            "output_path": "D:/Music/out.flac",
            "target_format": "flac",
            "source_size_bytes": 12,
        }
        fake_result = {
            "ok": False,
            "error": "转换已完成，但目标路径已被其他进程创建；为避免覆盖，结果未写入。",
            "error_code": "OUTPUT_CONFLICT",
            "input_path": "D:/Music/source.wav",
            "output_path": "D:/Music/out.flac",
            "target_format": "flac",
            "source_size_bytes": 12,
            "output_size_bytes": 0,
            "duration_ms": 123,
            "ffmpeg_returncode": 0,
            "ffmpeg_stderr_tail": "",
            "finalization_strategy": "hardlink",
            "temp_cleanup_ok": True,
            "warning": "",
        }

        with (
            patch(
                "ui_next.bridge.single_file_convert_viewmodel.validate_single_file_convert_request",
                return_value=fake_validation,
            ),
            patch(
                "ui_next.bridge.single_file_convert_viewmodel.convert_single_file_to_new_path",
                return_value=fake_result,
            ),
        ):
            view_model.startSingleFileConvert()
            self.wait_for_conversion(view_model)

        self.assertFalse(view_model.isConverting)
        self.assertEqual(view_model.convertStatus, "并发输出冲突")
        self.assertEqual(view_model.lastErrorCode, "OUTPUT_CONFLICT")
        self.assertEqual(view_model.finalizationStrategy, "hardlink")
        self.assertIn("避免覆盖", view_model.progressText)

    def test_disabled_actions_are_noop_messages(self):
        view_model = SingleFileConvertViewModel(
            CapabilityGate(SINGLE_FILE_CONVERT)
        )

        view_model.disabledAddToQueue()
        view_model.disabledBatchConvert()
        view_model.disabledOverwriteConvert()
        view_model.disabledApplyToWatcher()
        view_model.disabledWriteMetadata()

        self.assertEqual(
            view_model.statusMessage,
            "当前操作仅支持选择全新输出路径；请使用任务队列进行批量转换。"
            "覆盖已有文件和直接写回均不可用。",
        )

    def test_preview_input_requires_capability_and_supported_existing_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "from preview.wav"
            source.write_bytes(b"audio-placeholder")
            ncm_file = root / "from preview.ncm"
            ncm_file.write_bytes(b"ncm-placeholder")
            text_file = root / "from preview.txt"
            text_file.write_text("not audio", encoding="utf-8")

            preview_view_model = SingleFileConvertViewModel()
            preview_view_model.setInputFileFromPreview(str(source))
            self.assertEqual(preview_view_model.inputPath, "")
            self.assertEqual(
                "此操作当前不可用，未执行任何更改。",
                preview_view_model.statusMessage,
            )

            view_model = SingleFileConvertViewModel(
                CapabilityGate(SINGLE_FILE_CONVERT)
            )
            view_model.setInputFileFromPreview(str(root / "missing.flac"))
            self.assertEqual(view_model.inputPath, "")
            self.assertIn("文件不存在", view_model.lastError)

            view_model.setInputFileFromPreview(str(ncm_file))
            self.assertEqual(view_model.inputPath, "")
            self.assertIn("暂不支持 NCM", view_model.lastError)

            view_model.setInputFileFromPreview(str(text_file))
            self.assertEqual(view_model.inputPath, "")
            self.assertIn("格式暂不支持", view_model.lastError)

    def test_viewmodel_does_not_import_forbidden_workflows(self):
        source = Path("ui_next/bridge/single_file_convert_viewmodel.py").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("import watcher", source)
        self.assertNotIn("import converter", source)
        self.assertNotIn("save_config", source)
        self.assertNotIn("convert_audio", source)


if __name__ == "__main__":
    unittest.main()
