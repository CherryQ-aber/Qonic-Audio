import hashlib
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QObject, QUrl
from PySide6.QtQml import QQmlComponent
from PySide6.QtQuick import QQuickItem, QQuickView
from PySide6.QtWidgets import QApplication

from ui_next.bridge.auto_convert_viewmodel import AutoConvertViewModel
from ui_next.bridge.capabilities import (
    AUDIO_EXPORT,
    AUDIO_PLAYBACK,
    AUDIO_PROCESSING,
    BATCH_CONVERT,
    CACHE_CLEANUP,
    CONFIG_WRITE,
    COVER_READ,
    COVER_WRITE,
    DEFAULT_USER_CAPABILITIES,
    LYRICS_READ,
    LYRICS_WRITE,
    METADATA_READ,
    METADATA_WRITE,
    OVERWRITE_FILE,
    QUEUE_MUTATION,
    SCAN_PREVIEW,
    SINGLE_FILE_CONVERT,
    WATCHER_CONTROL,
)
from ui_next.bridge.runtime_mode import (
    DEFAULT_USER_MODE,
    PREVIEW_MODE,
    TEST_MODE,
    RuntimeModeParseError,
    resolve_runtime_mode,
)
from ui_next.bridge.file_session_viewmodel import FileSessionViewModel
from ui_next.bridge.scan_preview_viewmodel import ScanPreviewViewModel
from ui_next.bridge.settings_viewmodel import SettingsViewModel
from ui_next.bridge.single_file_convert_viewmodel import SingleFileConvertViewModel
from ui_next.bridge.task_queue_model import TaskQueueModel


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config.json"


class RuntimeModeResolutionTests(unittest.TestCase):
    def test_plain_launch_resolves_to_default_user_profile(self):
        runtime = resolve_runtime_mode(["main_qml.py"], {})
        gate = runtime.create_capability_gate()

        self.assertEqual(DEFAULT_USER_MODE, runtime.mode)
        self.assertFalse(gate.previewMode)
        self.assertTrue(gate.defaultUserMode)
        self.assertEqual(set(gate.enabledCapabilities), DEFAULT_USER_CAPABILITIES)
        for capability in (
            METADATA_READ,
            LYRICS_READ,
            COVER_READ,
            SCAN_PREVIEW,
            SINGLE_FILE_CONVERT,
            CONFIG_WRITE,
            WATCHER_CONTROL,
            QUEUE_MUTATION,
            BATCH_CONVERT,
            AUDIO_PLAYBACK,
            AUDIO_PROCESSING,
            AUDIO_EXPORT,
            METADATA_WRITE,
            LYRICS_WRITE,
            COVER_WRITE,
        ):
            self.assertTrue(gate.allows(capability), capability)

    def test_default_user_profile_keeps_dangerous_capabilities_denied(self):
        gate = resolve_runtime_mode(["main_qml.py"], {}).create_capability_gate()

        self.assertFalse(gate.allows(OVERWRITE_FILE))
        self.assertFalse(gate.allows(CACHE_CLEANUP))
        self.assertTrue(gate.sourceFileProtectionEnabled)

    def test_preview_flag_overrides_legacy_environment_requests(self):
        runtime = resolve_runtime_mode(
            ["main_qml.py", "--preview"],
            {
                "CHERRYQ_QML_USER_TEST": "1",
                "CHERRYQ_QML_CAPS": "metadata_write,overwrite_file",
            },
        )
        gate = runtime.create_capability_gate()

        self.assertEqual(PREVIEW_MODE, runtime.mode)
        self.assertTrue(gate.previewMode)
        self.assertEqual([], gate.enabledCapabilities)
        self.assertFalse(gate.allows(OVERWRITE_FILE))

    def test_smoke_test_always_uses_safe_test_mode(self):
        runtime = resolve_runtime_mode(
            ["main_qml.py", "--qml-smoke-test"],
            {"CHERRYQ_QML_USER_TEST": "1"},
        )
        gate = runtime.create_capability_gate()

        self.assertEqual(TEST_MODE, runtime.mode)
        self.assertTrue(runtime.smoke_test)
        self.assertTrue(gate.previewMode)
        self.assertTrue(gate.testMode)
        self.assertEqual([], gate.enabledCapabilities)

    def test_legacy_user_trial_maps_to_default_user_mode(self):
        runtime = resolve_runtime_mode(
            ["main_qml.py"],
            {
                "CHERRYQ_QML_USER_TEST": "1",
                "CHERRYQ_QML_CAPS": "metadata_read,overwrite_file",
            },
        )

        self.assertEqual(DEFAULT_USER_MODE, runtime.mode)
        self.assertTrue(runtime.legacy_user_trial_requested)
        self.assertEqual(
            set(runtime.create_capability_gate().enabledCapabilities),
            DEFAULT_USER_CAPABILITIES,
        )

    def test_legacy_capability_list_remains_a_narrow_compatibility_entry(self):
        runtime = resolve_runtime_mode(
            ["main_qml.py"],
            {"CHERRYQ_QML_CAPS": "metadata_read,lyrics_read,overwrite_file"},
        )
        gate = runtime.create_capability_gate()

        self.assertTrue(runtime.legacy_capabilities_requested)
        self.assertTrue(gate.allows(METADATA_READ))
        self.assertTrue(gate.allows(LYRICS_READ))
        self.assertFalse(gate.allows(OVERWRITE_FILE))

    def test_unknown_qml_argument_fails_before_qapplication_starts(self):
        with self.assertRaisesRegex(RuntimeModeParseError, "不支持的 QML 启动参数"):
            resolve_runtime_mode(["main_qml.py", "--not-a-real-qml-option"], {})


class DefaultStartupSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_default_profile_constructs_without_starting_background_work(self):
        runtime = resolve_runtime_mode(["main_qml.py"], {})
        gate = runtime.create_capability_gate()
        current_config = {
            "watch_folder": "D:/Music/Incoming",
            "output_folder": "D:/Music/Output",
            "editor_output_folder": "D:/Music/Editor",
            "target_format": "flac",
        }

        with (
            patch("ui_next.bridge.auto_convert_viewmodel.WatcherThread") as watcher_thread,
            patch("ui_next.bridge.auto_convert_viewmodel.ConvertThread") as convert_thread,
            patch("ui_next.bridge.auto_convert_viewmodel.ScanThread") as scan_thread,
            patch("ui_next.bridge.settings_viewmodel.load_config", return_value=current_config),
            patch("ui_next.bridge.settings_viewmodel.save_config") as save_config,
        ):
            auto_convert = AutoConvertViewModel(MagicMock(), capability_gate=gate)
            settings = SettingsViewModel(capability_gate=gate)

            self.assertFalse(auto_convert.isMonitoring)
            self.assertFalse(auto_convert.hasBackgroundTask)
            self.assertFalse(settings.hasPendingChanges)
            watcher_thread.assert_not_called()
            convert_thread.assert_not_called()
            scan_thread.assert_not_called()
            save_config.assert_not_called()
            auto_convert.shutdown()

    def test_smoke_subprocess_keeps_config_unchanged_even_with_legacy_user_test_env(self):
        before = hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest()
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        env["CHERRYQ_QML_USER_TEST"] = "1"
        env["CHERRYQ_QML_CAPS"] = "overwrite_file,metadata_write"
        completed = subprocess.run(
            [sys.executable, "-B", "main_qml.py", "--qml-smoke-test"],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("当前模式：QML Test Mode", completed.stdout)
        self.assertIn("可用功能：无", completed.stdout)
        self.assertEqual(before, hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest())


class DefaultUserModeQmlControlTests(unittest.TestCase):
    """Exercise the real page binding rather than only the Python gate."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_default_mode_passes_active_conversion_bridge_to_action_bar(self):
        gate = resolve_runtime_mode(["main_qml.py"], {}).create_capability_gate()
        queue_model = TaskQueueModel(capability_gate=gate)
        auto_convert = AutoConvertViewModel(queue_model, capability_gate=gate)
        idle_prepare_thread = MagicMock()
        idle_prepare_thread.isRunning.return_value = True
        auto_convert._prepare_thread = idle_prepare_thread
        scan_preview = ScanPreviewViewModel(capability_gate=gate)
        single_file = SingleFileConvertViewModel(capability_gate=gate)
        file_session = FileSessionViewModel(capability_gate=gate)
        view = QQuickView()
        component = QQmlComponent(view.engine())
        source = b'''import QtQuick
import "ui_next/qml/pages"

Item {
    width: 1200
    height: 900

    AutoConvertPage {
        anchors.fill: parent
    }
}
'''
        context = view.rootContext()
        context.setContextProperty("taskQueueModel", queue_model)
        context.setContextProperty("autoConvertViewModel", auto_convert)
        context.setContextProperty("scanPreviewViewModel", scan_preview)
        context.setContextProperty("singleFileConvertViewModel", single_file)
        context.setContextProperty("fileSessionViewModel", file_session)
        component.setData(
            source,
            QUrl.fromLocalFile(str(PROJECT_ROOT / "default_user_controls_probe.qml")),
        )
        with patch(
            "ui_next.bridge.auto_convert_viewmodel.watcher.has_preparing_tasks",
            return_value=False,
        ):
            container = component.create()
            self.assertIsNotNone(container, component.errors())
            self.assertIsInstance(container, QQuickItem)
            container.setParentItem(view.contentItem())
            view.setWidth(1200)
            view.setHeight(900)
            view.show()
            self.app.processEvents()

            try:
                action_buttons = {}
                for button in container.findChildren(QObject):
                    text = str(button.property("text") or "")
                    if text:
                        action_buttons[text] = bool(button.property("enabled"))
                self.assertFalse(auto_convert.previewMode)
                self.assertTrue(auto_convert.canBatchConvert)
                self.assertFalse(auto_convert.hasBackgroundTask)
                self.assertTrue(action_buttons["开始监听"])
                self.assertTrue(action_buttons["刷新队列"])
                self.assertTrue(action_buttons["开始转换"])
            finally:
                auto_convert._prepare_thread = None
                auto_convert.shutdown()
                queue_model._refresh_timer.stop()
                view.close()
                container.deleteLater()
                component.deleteLater()
                view.deleteLater()
                self.app.processEvents()

    def test_idle_prepare_service_does_not_disable_batch_conversion(self):
        gate = resolve_runtime_mode(["main_qml.py"], {}).create_capability_gate()
        queue_model = MagicMock()
        auto_convert = AutoConvertViewModel(queue_model, capability_gate=gate)
        idle_prepare_thread = MagicMock()
        idle_prepare_thread.isRunning.return_value = True
        auto_convert._prepare_thread = idle_prepare_thread

        with patch(
            "ui_next.bridge.auto_convert_viewmodel.watcher.has_preparing_tasks",
            return_value=False,
        ):
            self.assertFalse(auto_convert.isQueuePreparing)
            self.assertFalse(auto_convert.hasBackgroundTask)
            self.assertEqual("空闲", auto_convert.backgroundTaskLabel)

        with patch(
            "ui_next.bridge.auto_convert_viewmodel.watcher.has_preparing_tasks",
            return_value=True,
        ):
            self.assertTrue(auto_convert.isQueuePreparing)
            self.assertTrue(auto_convert.hasBackgroundTask)
            self.assertEqual("读取验证中", auto_convert.backgroundTaskLabel)

        auto_convert._prepare_thread = None
        auto_convert.shutdown()


if __name__ == "__main__":
    unittest.main()
