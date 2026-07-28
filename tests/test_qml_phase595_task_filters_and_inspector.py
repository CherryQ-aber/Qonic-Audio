from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QMetaObject, QObject, Qt, QUrl
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent
from PySide6.QtQuick import QQuickItem, QQuickView
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import watcher
from ui_next.bridge.auto_convert_viewmodel import AutoConvertViewModel
from ui_next.bridge.capabilities import CapabilityGate
from ui_next.bridge.runtime_mode import TEST_MODE
from ui_next.bridge.task_queue_filter_proxy_model import (
    TaskQueueFilterProxyModel,
)
from ui_next.bridge.task_queue_model import TaskQueueModel


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Phase595TaskFilterAndPlaybackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.paths = {
            "queued": root / "queued.wav",
            "reading": root / "reading.flac",
            "waiting": root / "waiting.mp3",
            "processing": root / "processing.m4a",
            "completed": root / "completed.ogg",
            "failed": root / "failed.wav",
            "excluded": root / "excluded.wav",
            "skipped": root / "skipped.wav",
            "cancelled": root / "cancelled.wav",
            "ncm": root / "protected.ncm",
            "output": root / "completed-output.flac",
        }
        for path in self.paths.values():
            path.write_bytes(b"phase-e")

        self.tasks = [
            self._task("queued", watcher.QUEUED_STATUS),
            self._task("reading", watcher.READING_STATUS),
            self._task("waiting", watcher.WAITING_STATUS),
            self._task("processing", watcher.PROCESSING_STATUS),
            self._task(
                "completed",
                watcher.COMPLETED_STATUS,
                output_path=str(self.paths["output"]),
                source="qml_scan",
                lyrics_result={
                    "found": True,
                    "embedded": True,
                    "copied": True,
                },
            ),
            self._task("failed", watcher.FAILED_STATUS),
            self._task(
                "excluded",
                watcher.WAITING_STATUS,
                enabled_for_run=False,
            ),
            self._task("skipped", watcher.SKIPPED_STATUS),
            self._task("cancelled", watcher.CANCELLED_STATUS),
            self._task(
                "ncm",
                watcher.WAITING_STATUS,
                is_ncm_task=True,
                source_type="NCM",
            ),
        ]
        self.snapshot_patch = patch(
            "watcher.get_task_snapshots",
            side_effect=lambda: [dict(task) for task in self.tasks],
        )
        self.snapshot_patch.start()
        gate = CapabilityGate((), runtime_mode=TEST_MODE)
        self.queue_model = TaskQueueModel(capability_gate=gate)
        self.queue_model._refresh_timer.stop()
        self.filter_model = TaskQueueFilterProxyModel(self.queue_model)
        self.view_model = AutoConvertViewModel(
            self.queue_model,
            capability_gate=gate,
        )
        self.view_model._state_timer.stop()

    def tearDown(self):
        self.view_model.shutdown()
        self.queue_model._refresh_timer.stop()
        self.snapshot_patch.stop()
        self.temp_dir.cleanup()

    def _task(self, key: str, status: str, **overrides) -> dict:
        path = self.paths[key]
        task = {
            "path": str(path),
            "filename": path.name,
            "format": path.suffix.lstrip(".").upper(),
            "source_type": path.suffix.lstrip(".").upper(),
            "source": "watcher",
            "status": status,
            "enabled_for_run": True,
            "target_format": "mp3",
            "target_format_override": None,
            "output_directory": self.temp_dir.name,
            "output_directory_override": "",
            "relative_output_path": path.name,
            "preserve_relative_structure": False,
            "create_format_subfolder": False,
            "stage": "测试阶段",
            "output_path": "",
            "error_summary": "",
            "lyrics_result": {},
            "can_convert": status == watcher.WAITING_STATUS,
            "can_retry": status == watcher.FAILED_STATUS,
            "can_change_target_format": True,
            "can_change_run_policy": True,
            "can_change_output_directory": True,
            "is_ncm_task": False,
        }
        task.update(overrides)
        return task

    def test_six_filters_are_projections_of_the_single_source_model(self):
        expected = {
            "all": 10,
            "waiting": 4,
            "processing": 1,
            "excluded": 1,
            "completed": 1,
            "failed": 1,
        }

        for filter_key, count in expected.items():
            with self.subTest(filter_key=filter_key):
                self.filter_model.setFilterKey(filter_key)
                self.assertEqual(count, self.filter_model.count)

        self.filter_model.setFilterKey("waiting")
        self.assertTrue(
            self.filter_model.containsPath(str(self.paths["queued"]))
        )
        self.assertTrue(
            self.filter_model.containsPath(str(self.paths["reading"]))
        )
        self.assertFalse(
            self.filter_model.containsPath(str(self.paths["failed"]))
        )
        self.assertIs(self.filter_model.sourceModel(), self.queue_model)

    def test_source_counts_include_enabled_prepare_states_without_partition_assumption(self):
        self.assertEqual(10, self.queue_model.totalCount)
        self.assertEqual(4, self.queue_model.waitingCount)
        self.assertEqual(1, self.queue_model.processingCount)
        self.assertEqual(1, self.queue_model.excludedCount)
        self.assertEqual(1, self.queue_model.completedCount)
        self.assertEqual(1, self.queue_model.failedCount)

    def test_status_refresh_updates_rows_and_proxy_without_model_reset(self):
        resets = []
        data_changes = []
        self.queue_model.modelReset.connect(lambda: resets.append(True))
        self.queue_model.dataChanged.connect(
            lambda *_args: data_changes.append(True)
        )
        self.filter_model.setFilterKey("waiting")
        self.assertEqual(4, self.filter_model.count)

        self.tasks[0]["status"] = watcher.PROCESSING_STATUS
        self.tasks[0]["stage"] = "正在转换"
        self.tasks[0]["can_convert"] = False
        self.queue_model.refresh()
        self.app.processEvents()

        self.assertEqual([], resets)
        self.assertEqual(1, len(data_changes))
        self.assertEqual(3, self.queue_model.waitingCount)
        self.assertEqual(2, self.queue_model.processingCount)
        self.assertEqual(3, self.filter_model.count)

    def test_queue_view_keeps_scroll_position_for_updates_and_unavoidable_reset(self):
        view = QQuickView()
        view.rootContext().setContextProperty(
            "queueSourceUnderTest",
            self.queue_model,
        )
        view.rootContext().setContextProperty(
            "queueFilterUnderTest",
            self.filter_model,
        )
        component = QQmlComponent(view.engine())
        component.setData(
            b'''import QtQuick
import "ui_next/qml/components"

Item {
    width: 1200
    height: 360

    QtObject {
        id: autoConvertStub
        property bool previewMode: true
        property bool canBatchConvert: false
        property bool hasBackgroundTask: false
        property bool canMutateQueue: false
        property var targetFormats: []
    }

    TaskQueueView {
        anchors.fill: parent
        queueModel: queueFilterUnderTest
        sourceModel: queueSourceUnderTest
        autoConvertViewModel: autoConvertStub
    }
}
''',
            QUrl.fromLocalFile(
                str(PROJECT_ROOT / "phase595_queue_scroll_probe.qml")
            ),
        )
        container = component.create()
        self.assertIsNotNone(container, component.errors())
        self.assertIsInstance(container, QQuickItem)
        container.setParentItem(view.contentItem())
        view.setWidth(1200)
        view.setHeight(360)
        view.show()
        self.app.processEvents()
        queue_list = container.findChild(QQuickItem, "taskQueueListView")
        self.assertIsNotNone(queue_list)
        try:
            queue_list.setProperty("contentY", 180.0)
            self.app.processEvents()
            before = float(queue_list.property("contentY"))
            self.assertGreater(before, 100)

            self.tasks[0]["stage"] = "状态已刷新"
            self.queue_model.refresh()
            self.app.processEvents()
            self.assertAlmostEqual(
                before,
                float(queue_list.property("contentY")),
                delta=2,
            )

            added_path = Path(self.temp_dir.name) / "added.wav"
            added_path.write_bytes(b"phase-e-added")
            self.paths["added"] = added_path
            self.tasks.append(
                self._task("added", watcher.WAITING_STATUS)
            )
            self.queue_model.refresh()
            self.app.processEvents()
            QTest.qWait(20)
            self.assertAlmostEqual(
                before,
                float(queue_list.property("contentY")),
                delta=2,
            )
        finally:
            view.close()
            container.deleteLater()
            component.deleteLater()
            view.deleteLater()
            self.app.processEvents()

    def test_player_and_editor_requests_are_explicit_and_validate_real_files(self):
        playback_requests = []
        editor_requests = []
        self.view_model.playbackSourceRequested.connect(
            lambda *values: playback_requests.append(values)
        )
        self.view_model.editorFileRequested.connect(editor_requests.append)

        self.view_model.load_task_source_to_player(
            str(self.paths["queued"])
        )
        self.assertEqual(
            (
                str(self.paths["queued"]),
                "转码源文件",
                "original",
                "transcode_source",
            ),
            playback_requests[-1],
        )

        self.view_model.open_task_in_editor(str(self.paths["queued"]))
        self.assertEqual([str(self.paths["queued"])], editor_requests)

        self.view_model.load_task_source_to_player(str(self.paths["ncm"]))
        self.assertEqual(1, len(playback_requests))
        self.assertIn("NCM", self.view_model.lastOperation)

        self.view_model.load_task_output_to_player(
            str(self.paths["waiting"])
        )
        self.assertEqual(1, len(playback_requests))
        self.assertIn("转换完成后", self.view_model.lastOperation)

        self.view_model.load_task_output_to_player(
            str(self.paths["completed"])
        )
        self.assertEqual(
            (
                str(self.paths["output"]),
                "转码输出结果",
                "export_result",
                "transcode_output",
            ),
            playback_requests[-1],
        )

    def test_task_details_keep_input_type_and_origin_separate(self):
        details = self.queue_model.taskDetails(
            str(self.paths["completed"])
        )

        self.assertEqual("OGG", details["sourceType"])
        self.assertEqual("目录扫描", details["sourceOrigin"])
        self.assertEqual("qml_scan", details["sourceOriginKey"])
        self.assertEqual(
            "已写入内嵌歌词并复制外置 .lrc",
            details["lyricsResult"],
        )
        self.assertEqual(str(self.paths["output"]), details["outputPath"])


class Phase595TaskInspectorQmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_auto_open_threshold_and_manual_overlay_state_are_exact(self):
        engine = QQmlApplicationEngine()
        qml_root = PROJECT_ROOT / "ui_next" / "qml"
        engine.addImportPath(str(qml_root))
        component_url = QUrl.fromLocalFile(
            str(qml_root / "components" / "TaskInspectorDrawer.qml")
        )
        engine.load(component_url)
        self.app.processEvents()
        self.assertTrue(engine.rootObjects())
        drawer = engine.rootObjects()[0]
        self.assertIsInstance(drawer, QObject)
        try:
            for width, height, expected in (
                (1899, 1200, False),
                (1900, 1199, False),
                (1900, 1200, True),
            ):
                with self.subTest(width=width, height=height):
                    drawer.setProperty("manualOverride", False)
                    drawer.setProperty("viewportWidth", width)
                    drawer.setProperty("viewportHeight", height)
                    self.app.processEvents()
                    self.assertEqual(
                        expected,
                        bool(drawer.property("wideViewport")),
                    )
                    self.assertEqual(
                        expected,
                        bool(drawer.property("opened")),
                    )

            drawer.setProperty("manualOverride", False)
            drawer.setProperty("viewportWidth", 1500)
            drawer.setProperty("viewportHeight", 900)
            self.assertTrue(
                QMetaObject.invokeMethod(
                    drawer,
                    "toggle",
                    Qt.ConnectionType.DirectConnection,
                )
            )
            self.assertTrue(drawer.property("manualOverride"))
            self.assertTrue(drawer.property("opened"))
            self.assertTrue(
                QMetaObject.invokeMethod(
                    drawer,
                    "close",
                    Qt.ConnectionType.DirectConnection,
                )
            )
            self.assertFalse(drawer.property("opened"))
        finally:
            drawer.deleteLater()
            engine.deleteLater()
            self.app.processEvents()

    def test_workspace_navigation_counts_follow_source_model_notify(self):
        view = QQuickView()
        component = QQmlComponent(view.engine())
        component.setData(
            b'''import QtQuick
import "ui_next/qml/components"

Item {
    width: 900
    height: 44

    QtObject {
        id: queueCountStub
        objectName: "queueCountStub"
        property int totalCount: 14
        property int waitingCount: 0
        property int processingCount: 0
        property int excludedCount: 0
        property int completedCount: 0
        property int failedCount: 0
    }

    WorkspaceSubNavigation {
        objectName: "workspaceSubNavigationUnderTest"
        anchors.fill: parent
        currentWorkspaceKey: "autoConvert"
        taskQueueModel: queueCountStub
    }
}
''',
            QUrl.fromLocalFile(
                str(PROJECT_ROOT / "phase595_queue_count_probe.qml")
            ),
        )
        container = component.create()
        self.assertIsNotNone(container, component.errors())
        self.assertIsInstance(container, QQuickItem)
        container.setParentItem(view.contentItem())
        view.setWidth(900)
        view.setHeight(44)
        view.show()
        self.app.processEvents()
        queue_stub = container.findChild(QObject, "queueCountStub")
        sub_navigation = container.findChild(
            QObject,
            "workspaceSubNavigationUnderTest",
        )
        self.assertIsNotNone(queue_stub)
        self.assertIsNotNone(sub_navigation)

        def find_quick_item(item, object_name):
            if item.objectName() == object_name:
                return item
            for child in item.childItems():
                result = find_quick_item(child, object_name)
                if result is not None:
                    return result
            return None

        all_button = find_quick_item(
            container,
            "workspaceSubNav_all",
        )
        waiting_button = find_quick_item(
            container,
            "workspaceSubNav_waiting",
        )
        self.assertIsNotNone(all_button)
        self.assertIsNotNone(waiting_button)
        try:
            self.assertEqual("全部 14", all_button.property("text"))
            self.assertEqual("等待处理 0", waiting_button.property("text"))

            queue_stub.setProperty("totalCount", 15)
            queue_stub.setProperty("waitingCount", 14)
            self.app.processEvents()

            self.assertEqual("全部 15", all_button.property("text"))
            self.assertEqual("等待处理 14", waiting_button.property("text"))
        finally:
            view.close()
            container.deleteLater()
            component.deleteLater()
            view.deleteLater()
            self.app.processEvents()

    def test_production_wiring_keeps_filter_source_player_and_editor_boundaries(self):
        main_source = (PROJECT_ROOT / "main_qml.py").read_text(
            encoding="utf-8"
        )
        shell_qml = (
            PROJECT_ROOT / "ui_next/qml/AppShell.qml"
        ).read_text(encoding="utf-8")
        queue_qml = (
            PROJECT_ROOT / "ui_next/qml/components/TaskQueueView.qml"
        ).read_text(encoding="utf-8")
        delegate_qml = (
            PROJECT_ROOT / "ui_next/qml/components/TaskRowDelegate.qml"
        ).read_text(encoding="utf-8")

        self.assertIn(
            'setContextProperty(\n        "taskQueueFilterModel"',
            main_source,
        )
        self.assertIn(
            "playbackSourceRequested.connect",
            main_source,
        )
        self.assertIn(
            'open_source_in_editor(path, "audio_editor")',
            main_source,
        )
        self.assertIn(
            "result = file_session_view_model.setCurrentFile(path, source)",
            main_source,
        )
        self.assertIn("property var taskQueueBridge:", shell_qml)
        self.assertIn(
            "taskQueueModel: root.taskQueueBridge",
            shell_qml,
        )
        self.assertNotIn(
            "taskQueueModel: taskQueueModel",
            shell_qml,
        )
        self.assertIn("onFilterChanged", queue_qml)
        self.assertIn("onDoubleClicked", delegate_qml)
        self.assertIn("载入转换结果到播放器", delegate_qml)
        self.assertIn("在音频编辑中打开", delegate_qml)


if __name__ == "__main__":
    unittest.main()
