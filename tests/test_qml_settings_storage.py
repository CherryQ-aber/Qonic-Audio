import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config import DEFAULT_CONFIG
from ui_next.bridge.capabilities import CapabilityGate
from ui_next.bridge.settings_storage import clear_log_storage, scan_log_storage
from ui_next.bridge.settings_viewmodel import SettingsViewModel


class SettingsStorageServiceTests(unittest.TestCase):
    def test_log_scan_reports_each_file_and_total_size(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "runtime.log").write_bytes(b"12345")
            (root / "older.log").write_bytes(b"abc")

            result = scan_log_storage(str(root))

        self.assertEqual(2, result["total_files"])
        self.assertEqual(8, result["total_size"])
        self.assertEqual(
            ["older.log", "runtime.log"],
            [item["label"] for item in result["items"]],
        )

    def test_log_cleanup_releases_active_handler_and_restores_it(self):
        root_logger = logging.getLogger()
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)
            active_path = log_dir / "runtime.log"
            old_path = log_dir / "older.log"
            handler = logging.FileHandler(active_path, encoding="utf-8")
            root_logger.addHandler(handler)
            old_path.write_bytes(b"old")
            try:
                handler.emit(
                    logging.LogRecord(
                        "test", logging.INFO, __file__, 1, "active", (), None
                    )
                )
                handler.flush()

                result = clear_log_storage(str(log_dir), str(active_path))

                self.assertEqual(0, result["failed_count"])
                self.assertGreaterEqual(result["deleted_files"], 2)
                self.assertFalse(old_path.exists())
                self.assertTrue(active_path.exists())
                replacement_handlers = [
                    item
                    for item in root_logger.handlers
                    if isinstance(item, logging.FileHandler)
                    and Path(item.baseFilename) == active_path
                ]
                self.assertEqual(1, len(replacement_handlers))
            finally:
                for item in tuple(root_logger.handlers):
                    if isinstance(item, logging.FileHandler) and Path(
                        item.baseFilename
                    ) == active_path:
                        root_logger.removeHandler(item)
                        item.close()


class SettingsStorageViewModelTests(unittest.TestCase):
    def setUp(self):
        self.config = dict(DEFAULT_CONFIG)

    def test_cleanup_plan_uses_scanned_categories_without_clearing(self):
        gate = CapabilityGate.from_environment({"QONIC_QML_USER_TEST": "1"})
        scan = {
            "logs": {
                "total_size": 3,
                "total_size_text": "3 B",
                "total_files": 1,
                "items": [
                    {
                        "id": "runtime.log",
                        "label": "runtime.log",
                        "path": "D:/App/logs/runtime.log",
                        "size": 3,
                        "size_text": "3 B",
                    }
                ],
            },
            "cache": {
                "total_size": 1024,
                "total_files": 2,
                "cleanable_size": 1024,
                "cleanable_files": 2,
                "categories": {
                    "waveform": {
                        "id": "waveform",
                        "label": "波形缓存",
                        "paths": ["D:/App/Cache/Waveform"],
                        "cleanable_size": 1024,
                        "cleanable_files": 2,
                    }
                },
            },
        }
        with (
            patch(
                "ui_next.bridge.settings_viewmodel.load_config",
                return_value=dict(self.config),
            ),
            patch(
                "ui_next.bridge.settings_viewmodel.clear_selected_cache"
            ) as clear_cache,
        ):
            view_model = SettingsViewModel(capability_gate=gate)
            view_model._apply_storage_scan(scan)
            view_model._prepare_cleanup_plan("cache")

        self.assertEqual("1.0 KB", view_model.cacheUsageText)
        self.assertEqual("cache", view_model.cleanupTarget)
        self.assertEqual("waveform", view_model.cleanupItems[0]["id"])
        self.assertIn("2 个文件", view_model.cleanupItems[0]["detail"])
        clear_cache.assert_not_called()

    def test_settings_page_requires_confirmation_before_cleanup(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "ui_next"
            / "qml"
            / "pages"
            / "SettingsPage.qml"
        ).read_text(encoding="utf-8")

        self.assertIn('objectName: "settingsStorageCleanupDialog"', source)
        self.assertIn("settingsViewModel.prepareLogCleanup()", source)
        self.assertIn("settingsViewModel.prepareCacheCleanup()", source)
        self.assertIn("settingsViewModel.confirmPreparedCleanup()", source)
        self.assertNotIn("清理缓存（当前不可用）", source)
        self.assertNotIn("检查当前草稿", source)


if __name__ == "__main__":
    unittest.main()
