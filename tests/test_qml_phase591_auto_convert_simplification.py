import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

import watcher
from ui_next.bridge.auto_convert_viewmodel import (
    AutoConvertViewModel,
    ConvertThread,
)
from ui_next.bridge.capabilities import (
    BATCH_CONVERT,
    QUEUE_MUTATION,
    SCAN_PREVIEW,
    CapabilityGate,
)


class Phase591AutoConvertTests(unittest.TestCase):
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

    def _wait_for_scan(self, view_model: AutoConvertViewModel) -> None:
        deadline = time.monotonic() + 5
        while view_model.isDirectoryScanning and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.app.processEvents()
        self.assertFalse(view_model.isDirectoryScanning)

    def test_production_entry_stops_injecting_legacy_cards(self):
        root = Path(__file__).resolve().parents[1]
        main_source = (root / "main_qml.py").read_text(encoding="utf-8")
        page_source = (
            root / "ui_next/qml/pages/AutoConvertPage.qml"
        ).read_text(encoding="utf-8")
        row_source = (
            root / "ui_next/qml/components/TaskRowDelegate.qml"
        ).read_text(encoding="utf-8")

        self.assertNotIn("SingleFileConvertViewModel(", main_source)
        self.assertNotIn("ScanPreviewViewModel(", main_source)
        self.assertNotIn("singleFileConvertViewModel", main_source)
        self.assertNotIn("scanPreviewViewModel", main_source)
        self.assertNotIn("SingleFileConvertPanel {", page_source)
        self.assertNotIn("ScanPreviewPanel {", page_source)
        self.assertIn('text: "转换此文件"', row_source)
        self.assertIn("start_convert_item", (
            root / "ui_next/qml/components/TaskQueueView.qml"
        ).read_text(encoding="utf-8"))

    def test_single_and_multiple_file_import_share_watcher_queue(self):
        gate = CapabilityGate((QUEUE_MUTATION,))
        queue_model = MagicMock()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "one.wav"
            second = root / "two.FLAC"
            lrc = root / "two.LRC"
            first.write_bytes(b"one")
            second.write_bytes(b"two")
            lrc.write_bytes(b"lyrics")
            with patch(
                "ui_next.bridge.auto_convert_viewmodel.load_config",
                return_value={
                    "output_folder": temp_dir,
                    "target_format": "flac",
                    "create_format_subfolder": False,
                },
            ):
                view_model = AutoConvertViewModel(queue_model, capability_gate=gate)
                with patch.object(view_model, "_start_prepare_thread"):
                    view_model.enqueue_files(
                        [str(first), str(second), str(first), str(lrc)]
                    )

            tasks = watcher.get_task_snapshots()
            self.assertEqual(2, len(tasks))
            self.assertEqual(
                {"qml_file"},
                {str(task.get("source")) for task in tasks},
            )
            self.assertTrue(
                all(task["status"] == watcher.QUEUED_STATUS for task in tasks)
            )
            self.assertIn("重复跳过 1 项", view_model.lastOperation)
            self.assertIn("不支持或无效 1 项", view_model.lastOperation)
            self.assertIsNone(view_model._convert_thread)
            view_model.shutdown()

    def test_directory_scan_directly_enqueues_and_keeps_only_summary(self):
        gate = CapabilityGate((SCAN_PREVIEW, QUEUE_MUTATION))
        queue_model = MagicMock()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "song.wav").write_bytes(b"audio")
            (root / "song.LRC").write_bytes(b"lyrics")
            (root / "cover.jpg").write_bytes(b"image")
            with patch(
                "ui_next.bridge.auto_convert_viewmodel.load_config",
                return_value={
                    "output_folder": temp_dir,
                    "target_format": "flac",
                    "create_format_subfolder": False,
                },
            ):
                view_model = AutoConvertViewModel(queue_model, capability_gate=gate)
                with patch.object(view_model, "_start_prepare_thread"):
                    view_model.scan_folder(str(root))
                    self._wait_for_scan(view_model)

            tasks = watcher.get_task_snapshots()
            self.assertEqual(1, len(tasks))
            self.assertEqual("qml_scan", tasks[0]["source"])
            self.assertEqual(3, view_model.scanTotalCount)
            self.assertEqual(1, view_model.scanAddedCount)
            self.assertEqual(0, view_model.scanDuplicateCount)
            self.assertEqual(2, view_model.scanUnsupportedCount)
            self.assertEqual("已完成", view_model.scanStatusLabel)
            self.assertFalse(hasattr(view_model, "items"))
            self.assertIsNone(view_model._convert_thread)
            view_model.shutdown()

    def test_repeated_directory_scan_does_not_duplicate_nonterminal_task(self):
        gate = CapabilityGate((SCAN_PREVIEW, QUEUE_MUTATION))
        queue_model = MagicMock()
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "song.wav"
            source.write_bytes(b"audio")
            with patch(
                "ui_next.bridge.auto_convert_viewmodel.load_config",
                return_value={"output_folder": temp_dir, "target_format": "flac"},
            ):
                view_model = AutoConvertViewModel(queue_model, capability_gate=gate)
                with patch.object(view_model, "_start_prepare_thread"):
                    view_model.scan_folder(temp_dir)
                    self._wait_for_scan(view_model)
                    view_model.scan_folder(temp_dir)
                    self._wait_for_scan(view_model)

            self.assertEqual(1, len(watcher.get_task_snapshots()))
            self.assertEqual(0, view_model.scanAddedCount)
            self.assertEqual(1, view_model.scanDuplicateCount)
            view_model.shutdown()

    def test_file_drop_folder_drop_and_watcher_share_one_queue(self):
        gate = CapabilityGate((SCAN_PREVIEW, QUEUE_MUTATION))
        queue_model = MagicMock()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dropped_file = root / "dropped.wav"
            dropped_file.write_bytes(b"drop")
            scan_folder = root / "album"
            scan_folder.mkdir()
            scanned_file = scan_folder / "scanned.flac"
            scanned_file.write_bytes(b"scan")
            watcher_file = root / "watched.mp3"
            watcher_file.write_bytes(b"watch")
            with patch(
                "ui_next.bridge.auto_convert_viewmodel.load_config",
                return_value={"output_folder": temp_dir, "target_format": "flac"},
            ):
                view_model = AutoConvertViewModel(queue_model, capability_gate=gate)
                with patch.object(view_model, "_start_prepare_thread"):
                    view_model.enqueue_dropped_items(
                        [str(dropped_file), str(scan_folder)]
                    )
                    self._wait_for_scan(view_model)
                    watcher.handle_detected_file(
                        str(watcher_file),
                        source="watcher",
                    )

            tasks = watcher.get_task_snapshots()
            self.assertEqual(3, len(tasks))
            self.assertEqual(
                {"qml_drop", "qml_scan", "watcher"},
                {str(task.get("source")) for task in tasks},
            )
            view_model.shutdown()

    def test_cancelled_scan_keeps_already_discovered_audio(self):
        gate = CapabilityGate((SCAN_PREVIEW, QUEUE_MUTATION))
        queue_model = MagicMock()
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "partial.wav"
            source.write_bytes(b"audio")
            scan_started = threading.Event()

            def cancellable_scan(
                folder_path,
                recursive,
                max_files,
                *,
                stop_event,
                progress_callback,
            ):
                scan_started.set()
                deadline = time.monotonic() + 2
                while not stop_event.is_set() and time.monotonic() < deadline:
                    time.sleep(0.01)
                return {
                    "ok": False,
                    "error": "扫描已取消",
                    "cancelled": True,
                    "scanned_files": 1,
                    "supported_count": 1,
                    "unsupported_count": 0,
                    "lrc_count": 0,
                    "items": [
                        {
                            "path": str(source),
                            "filename": source.name,
                            "is_supported_audio": True,
                        }
                    ],
                }

            with (
                patch(
                    "ui_next.bridge.auto_convert_viewmodel.load_config",
                    return_value={"output_folder": temp_dir, "target_format": "flac"},
                ),
                patch(
                    "ui_next.bridge.auto_convert_viewmodel.scan_directory_preview",
                    side_effect=cancellable_scan,
                ),
            ):
                view_model = AutoConvertViewModel(queue_model, capability_gate=gate)
                with patch.object(view_model, "_start_prepare_thread"):
                    view_model.scan_folder(temp_dir)
                    self.assertTrue(scan_started.wait(2))
                    view_model.cancel_directory_scan()
                    self._wait_for_scan(view_model)

            self.assertEqual(1, len(watcher.get_task_snapshots()))
            self.assertTrue(view_model.scanWasCancelled)
            self.assertEqual("已取消", view_model.scanStatusLabel)
            view_model.shutdown()

    def test_single_task_scheduler_filters_out_other_waiting_tasks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "one.wav"
            second = root / "two.wav"
            first.write_bytes(b"one")
            second.write_bytes(b"two")
            snapshot = {
                "output_directory": temp_dir,
                "target_format": "flac",
                "create_format_subfolder": False,
            }
            watcher.add_pending_file(
                str(first),
                status=watcher.WAITING_STATUS,
                task_snapshot=snapshot,
            )
            watcher.add_pending_file(
                str(second),
                status=watcher.WAITING_STATUS,
                task_snapshot=snapshot,
            )
            thread = ConvertThread(
                "flac",
                selected_paths={os.path.abspath(str(first))},
            )
            with patch(
                "converter.convert_audio",
                return_value={"success": True, "output_path": str(root / "one.flac")},
            ) as convert:
                thread.run()

            self.assertEqual(1, convert.call_count)
            self.assertEqual(
                watcher.COMPLETED_STATUS,
                watcher.get_pending_file_status(str(first)),
            )
            self.assertEqual(
                watcher.WAITING_STATUS,
                watcher.get_pending_file_status(str(second)),
            )
            self.assertTrue(convert.call_args.kwargs["safe_publish"])
            self.assertTrue(convert.call_args.kwargs["preserve_source"])

    def test_single_task_start_rejects_missing_output_directory(self):
        gate = CapabilityGate((BATCH_CONVERT,))
        queue_model = MagicMock()
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "song.wav"
            source.write_bytes(b"audio")
            watcher.add_pending_file(
                str(source),
                status=watcher.WAITING_STATUS,
                task_snapshot={
                    "output_directory": str(Path(temp_dir) / "missing"),
                    "target_format": "flac",
                },
            )
            view_model = AutoConvertViewModel(queue_model, capability_gate=gate)
            with (
                patch(
                    "ui_next.bridge.auto_convert_viewmodel.get_output_folder",
                    return_value="",
                ),
                patch.object(
                    view_model,
                    "_confirm_live_operation",
                    return_value=True,
                ) as confirm,
            ):
                view_model.start_convert_item(str(source))

            self.assertIsNone(view_model._convert_thread)
            self.assertIn("没有有效输出目录", view_model.errorSummary)
            confirm.assert_not_called()
            view_model.shutdown()

    def test_preview_mode_blocks_all_new_queue_entries(self):
        queue_model = MagicMock()
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "song.wav"
            source.write_bytes(b"audio")
            view_model = AutoConvertViewModel(
                queue_model,
                capability_gate=CapabilityGate(),
            )
            view_model.enqueue_files([str(source)])
            view_model.scan_folder(temp_dir)

            self.assertEqual([], watcher.get_task_snapshots())
            self.assertIsNone(view_model._directory_scan_thread)
            self.assertIsNone(view_model._convert_thread)
            view_model.shutdown()


if __name__ == "__main__":
    unittest.main()
