import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QApplication

import watcher
from ui_next.bridge.auto_convert_viewmodel import AutoConvertViewModel
from ui_next.bridge.task_queue_model import TaskQueueModel


class TaskQueueReadOnlyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _tasks(self):
        return [
            {
                "path": "D:/Music/waiting.flac",
                "filename": "waiting.flac",
                "format": "FLAC",
                "target_format": None,
                "status": watcher.WAITING_STATUS,
                "can_convert": True,
                "can_retry": False,
                "can_change_target_format": True,
                "is_ncm_task": False,
            },
            {
                "path": "D:/Music/skipped.ncm",
                "filename": "skipped.ncm",
                "format": "NCM",
                "target_format": "mp3",
                "status": watcher.SKIPPED_STATUS,
                "can_convert": False,
                "can_retry": False,
                "can_change_target_format": False,
                "is_ncm_task": True,
            },
        ]

    def test_summary_includes_skipped_and_manual_refresh_keeps_dedup(self):
        tasks = self._tasks()
        with (
            patch(
                "ui_next.bridge.task_queue_model.watcher.get_task_snapshots",
                return_value=tasks,
            ),
            patch(
                "ui_next.bridge.task_queue_model.get_target_format",
                return_value="mp3",
            ),
        ):
            model = TaskQueueModel()
            reset_count = [0]
            model.modelReset.connect(
                lambda: reset_count.__setitem__(0, reset_count[0] + 1)
            )
            model.manualRefresh()
            model.manualRefresh()

        self.assertTrue(model.previewMode)
        self.assertEqual(model.refreshIntervalMs, 3000)
        self.assertEqual(model.totalCount, 2)
        self.assertEqual(model.waitingCount, 1)
        self.assertEqual(model.skippedCount, 1)
        self.assertNotEqual(model.lastRefreshTime, "尚未刷新")
        self.assertEqual(reset_count[0], 0)
        model._refresh_timer.stop()

    def test_queue_roles_expose_source_and_read_only_target_labels(self):
        with (
            patch(
                "ui_next.bridge.task_queue_model.watcher.get_task_snapshots",
                return_value=self._tasks(),
            ),
            patch(
                "ui_next.bridge.task_queue_model.get_target_format",
                return_value="mp3",
            ),
        ):
            model = TaskQueueModel()

        first = model.index(0, 0, QModelIndex())
        second = model.index(1, 0, QModelIndex())
        self.assertIn("跟随全局", model.data(first, model.targetFormatLabelRole))
        self.assertIn("单独指定", model.data(second, model.targetFormatLabelRole))
        self.assertEqual(model.data(first, model.sourceNoteRole), "FLAC 源文件")
        self.assertEqual(model.data(second, model.sourceNoteRole), "NCM 解码产物")
        model._refresh_timer.stop()


class AutoConvertPreviewGuardTests(unittest.TestCase):
    def test_all_real_operations_remain_noop_in_preview(self):
        queue_model = MagicMock()
        queue_model.lastRefreshTime = "12:34:56"

        with (
            patch("ui_next.bridge.auto_convert_viewmodel.watcher.start_watch") as start_watch,
            patch("ui_next.bridge.auto_convert_viewmodel.watcher.scan_existing_files") as scan,
            patch("ui_next.bridge.auto_convert_viewmodel.watcher.get_convertible_tasks") as convertible,
            patch("ui_next.bridge.auto_convert_viewmodel.watcher.clear_terminal_pending_files") as clear,
            patch("ui_next.bridge.auto_convert_viewmodel.watcher.get_retryable_tasks") as retryable,
            patch("ui_next.bridge.auto_convert_viewmodel.watcher.set_pending_file_target_format") as set_target,
            patch("ui_next.bridge.auto_convert_viewmodel.save_config") as save_config,
            patch("ui_next.bridge.auto_convert_viewmodel.QFileDialog.getExistingDirectory") as dialog,
        ):
            view_model = AutoConvertViewModel(queue_model)
            view_model.start_monitor()
            view_model.stop_monitor()
            view_model.scan_existing_files()
            view_model.start_convert()
            view_model.convert_to_placeholder()
            view_model.clear_terminal_items()
            view_model.retry_failed_items()
            view_model.choose_watch_folder()
            view_model.choose_output_folder()
            view_model.set_global_target_format("flac")
            view_model.set_file_target_format("D:/Music/test.flac", "mp3")
            view_model.apply_target_format_placeholder()

        self.assertTrue(view_model.previewMode)
        start_watch.assert_not_called()
        scan.assert_not_called()
        convertible.assert_not_called()
        clear.assert_not_called()
        retryable.assert_not_called()
        set_target.assert_not_called()
        save_config.assert_not_called()
        dialog.assert_not_called()
        view_model.shutdown()

    def test_manual_refresh_only_calls_read_only_queue_refresh(self):
        queue_model = MagicMock()
        queue_model.lastRefreshTime = "12:34:56"
        view_model = AutoConvertViewModel(queue_model)

        view_model.refresh_queue()

        queue_model.manualRefresh.assert_called_once_with()
        self.assertIn("只读队列快照", view_model.lastOperation)
        view_model.shutdown()


if __name__ == "__main__":
    unittest.main()
