import json
import hashlib
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

import config
import converter
import watcher
from ui_next.bridge.auto_convert_viewmodel import AutoConvertViewModel
from ui_next.bridge.capabilities import (
    BATCH_CONVERT,
    CONFIG_WRITE,
    QUEUE_MUTATION,
    SCAN_PREVIEW,
    WATCHER_CONTROL,
    CapabilityGate,
)
from ui_next.bridge.scan_preview_viewmodel import ScanPreviewViewModel


class Phase57WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        with watcher.pending_files_lock:
            watcher.pending_files.clear()
        with watcher.processed_files_lock:
            watcher.processed_files.clear()

    def tearDown(self):
        with watcher.pending_files_lock:
            watcher.pending_files.clear()
        with watcher.processed_files_lock:
            watcher.processed_files.clear()

    def test_scan_handoff_creates_snapshot_without_starting_conversion(self):
        gate = CapabilityGate.from_environment({"CHERRYQ_QML_USER_TEST": "1"})
        queue_model = MagicMock()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "album" / "song.wav"
            source.parent.mkdir()
            source.write_bytes(b"wav-placeholder")
            output = root / "output"
            output.mkdir()
            config_data = {
                "output_folder": str(output),
                "target_format": "flac",
                "create_format_subfolder": True,
                "preserve_relative_structure": True,
            }

            with patch(
                "ui_next.bridge.auto_convert_viewmodel.load_config",
                return_value=config_data,
            ):
                auto = AutoConvertViewModel(queue_model, capability_gate=gate)
                scan = ScanPreviewViewModel(gate)
                scan.requestQueueAdd.connect(auto.add_scan_candidates)
                auto.scanQueueAccepted.connect(scan.markQueuedPaths)
                scan._folder_path = str(root)
                scan._items = [
                    {
                        "path": str(source),
                        "filename": source.name,
                        "is_supported_audio": True,
                        "can_add_to_queue": True,
                    }
                ]
                scan.selectAudioCandidate(str(source))
                with patch.object(auto, "_start_prepare_thread") as prepare:
                    scan.addSelectedToQueue()

                tasks = watcher.get_task_snapshots()
                self.assertEqual(len(tasks), 1)
                task = tasks[0]
                self.assertEqual(task["status"], watcher.QUEUED_STATUS)
                self.assertEqual(task["target_format"], "flac")
                self.assertEqual(task["output_directory"], str(output))
                self.assertEqual(task["relative_output_path"], "album\\song.wav")
                self.assertTrue(task["preserve_relative_structure"])
                self.assertEqual(task["source_action"], "保留源文件")
                self.assertEqual(task["source"], "qml_scan")
                self.assertEqual(task["stage"], "等待读取验证")
                self.assertEqual(scan.items[0]["queue_status"], "已在任务队列")
                prepare.assert_called_once()
                queue_model.manualRefresh.assert_called()
                auto.shutdown()

    def test_duplicate_scan_handoff_is_rejected_without_second_task(self):
        gate = CapabilityGate((SCAN_PREVIEW, QUEUE_MUTATION))
        queue_model = MagicMock()
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "song.wav"
            source.write_bytes(b"wav-placeholder")
            with patch(
                "ui_next.bridge.auto_convert_viewmodel.load_config",
                return_value={"output_folder": temp_dir, "target_format": "flac"},
            ):
                auto = AutoConvertViewModel(queue_model, capability_gate=gate)
                with patch.object(auto, "_start_prepare_thread"):
                    auto.add_scan_candidates([str(source)], temp_dir, 1)
                    auto.add_scan_candidates([str(source)], temp_dir, 1)
                self.assertEqual(len(watcher.get_task_snapshots()), 1)
                self.assertIn("重复或不可加入 1 项", auto.lastOperation)
                auto.shutdown()

    def test_real_wav_batch_conversion_keeps_source_and_publishes_new_output(self):
        gate = CapabilityGate.from_environment({"CHERRYQ_QML_USER_TEST": "1"})
        queue_model = MagicMock()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.wav"
            output = root / "output"
            output.mkdir()
            subprocess.run(
                [
                    config.FFMPEG_PATH,
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:duration=0.1",
                    str(source),
                ],
                check=True,
                capture_output=True,
            )
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            config_data = {
                "output_folder": str(output),
                "target_format": "flac",
                "create_format_subfolder": False,
                "preserve_relative_structure": False,
            }
            with patch(
                "ui_next.bridge.auto_convert_viewmodel.load_config",
                return_value=config_data,
            ):
                auto = AutoConvertViewModel(queue_model, capability_gate=gate)
                auto.add_scan_candidates([str(source)], str(root), 1)

                deadline = time.monotonic() + 8
                while (
                    watcher.get_pending_file_status(str(source)) != watcher.WAITING_STATUS
                    and time.monotonic() < deadline
                ):
                    self.app.processEvents()
                    time.sleep(0.05)
                self.assertEqual(
                    watcher.get_pending_file_status(str(source)),
                    watcher.WAITING_STATUS,
                )
                self.assertFalse(watcher.has_preparing_tasks())
                self.assertFalse(auto.hasBackgroundTask)
                self.assertEqual("空闲", auto.backgroundTaskLabel)

                with patch.object(auto, "_confirm_live_operation", return_value=True):
                    auto.start_convert()
                self.assertIsNotNone(auto._convert_thread)
                auto._convert_thread.wait(10000)
                self.app.processEvents()

                task = watcher.get_task_snapshots()[0]
                output_path = Path(task["output_path"])
                self.assertEqual(task["status"], watcher.COMPLETED_STATUS)
                self.assertEqual(task["stage"], "已发布输出")
                self.assertTrue(output_path.is_file())
                self.assertGreater(output_path.stat().st_size, 0)
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), source_hash)
                auto.shutdown()

    def test_legacy_live_flag_uses_the_same_default_user_profile(self):
        gate = CapabilityGate.from_environment({"CHERRYQ_QML_LIVE": "1"})

        self.assertFalse(gate.previewMode)
        self.assertTrue(gate.allows(QUEUE_MUTATION))
        self.assertTrue(gate.allows(BATCH_CONVERT))
        self.assertTrue(gate.allows(WATCHER_CONTROL))
        self.assertTrue(gate.allows(CONFIG_WRITE))

    def test_user_trial_mode_can_start_watcher_only_after_explicit_confirmation(self):
        gate = CapabilityGate.from_environment({"CHERRYQ_QML_USER_TEST": "1"})
        queue_model = MagicMock()
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch(
                    "ui_next.bridge.auto_convert_viewmodel.get_watch_folder",
                    return_value=temp_dir,
                ),
                patch(
                    "ui_next.bridge.auto_convert_viewmodel.is_valid_watch_folder",
                    return_value=True,
                ),
                patch(
                    "ui_next.bridge.auto_convert_viewmodel.WatcherThread"
                ) as watcher_thread_class,
                patch.object(AutoConvertViewModel, "_start_prepare_thread"),
            ):
                watcher_thread = MagicMock()
                watcher_thread.isRunning.return_value = False
                watcher_thread_class.return_value = watcher_thread
                auto = AutoConvertViewModel(queue_model, capability_gate=gate)

                with patch.object(auto, "_confirm_live_operation", return_value=False):
                    auto.start_monitor()
                watcher_thread_class.assert_not_called()

                with patch.object(auto, "_confirm_live_operation", return_value=True):
                    auto.start_monitor()
                watcher_thread_class.assert_called_once_with(temp_dir, auto)
                watcher_thread.start.assert_called_once()

                auto._watcher_thread = None
                auto.shutdown()

    def test_batch_cancellation_terminates_the_current_ffmpeg_child(self):
        class FakeProcess:
            def __init__(self):
                self.terminated = False
                self.killed = False

            def poll(self):
                return None if not self.terminated else -15

            def terminate(self):
                self.terminated = True

            def wait(self, timeout):
                return -15

            def kill(self):
                self.killed = True

        stop_event = threading.Event()
        stop_event.set()
        process = FakeProcess()
        with patch("converter.subprocess.Popen", return_value=process):
            with self.assertRaises(converter.ConversionCancelled):
                converter._run_cancellable_ffmpeg_command(["ffmpeg"], stop_event)
        self.assertTrue(process.terminated)
        self.assertFalse(process.killed)

    def test_atomic_config_save_keeps_one_recovery_copy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            original = {"watch_folder": "D:/incoming", "legacy_field": "keep"}
            config_path.write_text(json.dumps(original), encoding="utf-8")
            with patch.object(config, "CONFIG_FILE", str(config_path)):
                saved = config.save_config({"target_format": "mp3", "legacy_field": "keep"})

            backup = Path(str(config_path) + ".bak")
            self.assertTrue(backup.exists())
            self.assertEqual(json.loads(backup.read_text(encoding="utf-8")), original)
            self.assertEqual(saved["target_format"], "mp3")
            self.assertEqual(
                json.loads(config_path.read_text(encoding="utf-8"))["legacy_field"],
                "keep",
            )


if __name__ == "__main__":
    unittest.main()
