import os
import unittest
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QUrl, qInstallMessageHandler
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtWidgets import QApplication

from ui_next.bridge.auto_convert_viewmodel import AutoConvertViewModel
from ui_next.bridge.capabilities import (
    BATCH_CONVERT,
    QUEUE_MUTATION,
    CapabilityGate,
)
from ui_next.bridge.task_queue_model import TaskQueueModel


class AutoConvertQmlListBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _create_view_model(self, capabilities=()):
        gate = CapabilityGate(capabilities)
        model = TaskQueueModel(capability_gate=gate)
        view_model = AutoConvertViewModel(model, capability_gate=gate)
        return model, view_model

    def _run_qml(self, view_model, body: str):
        messages = []
        previous_handler = qInstallMessageHandler(
            lambda _mode, _context, message: messages.append(message)
        )
        engine = QQmlEngine()
        component = QQmlComponent(engine)
        engine.rootContext().setContextProperty("autoVm", view_model)
        component.setData(
            f"""import QtQuick

Item {{
    property bool probeCompleted: false
    {body}
}}
""".encode("utf-8"),
            QUrl("file:///auto_convert_qml_list_bridge_probe.qml"),
        )
        root = None
        try:
            root = component.create()
            self.app.processEvents()
            self.assertIsNotNone(root, component.errors())
            self.assertTrue(root.property("probeCompleted"), messages)
            return messages
        finally:
            qInstallMessageHandler(previous_handler)
            if root is not None:
                root.deleteLater()
            component.deleteLater()
            engine.deleteLater()
            self.app.processEvents()

    def _dispose_view_model(self, model, view_model):
        view_model.shutdown()
        model._refresh_timer.stop()
        model.deleteLater()
        view_model.deleteLater()
        self.app.processEvents()

    def test_all_qml_list_slots_publish_qvariantlist_signatures(self):
        model, view_model = self._create_view_model()
        try:
            signatures = {
                bytes(view_model.metaObject().method(index).methodSignature()).decode()
                for index in range(view_model.metaObject().methodCount())
            }
            expected = {
                "enqueue_files(QVariantList)",
                "scan_folders(QVariantList)",
                "enqueue_dropped_items(QVariantList)",
                "start_convert_selected(QVariantList)",
                "retry_failed_tasks(QVariantList)",
                "remove_pending_items(QVariantList)",
                "set_tasks_target_format(QVariantList,QString)",
                "set_tasks_enabled_for_run(QVariantList,bool)",
                "reset_tasks_output_directory(QVariantList)",
                "choose_tasks_output_directory(QVariantList)",
                "convert_selected_to_directory(QVariantList)",
            }
            self.assertTrue(expected.issubset(signatures), expected - signatures)
        finally:
            self._dispose_view_model(model, view_model)

    def test_javascript_arrays_reach_every_qml_list_slot_without_type_errors(self):
        model, view_model = self._create_view_model()
        try:
            messages = self._run_qml(
                view_model,
                """
    Component.onCompleted: {
        var paths = ["C:/one.wav", "D:/two.flac"]
        autoVm.enqueue_files(paths)
        autoVm.scan_folders(["C:/music"])
        autoVm.enqueue_dropped_items(["file:///C:/one.wav"])
        autoVm.start_convert_selected(paths)
        autoVm.retry_failed_tasks(paths)
        autoVm.remove_pending_items(paths)
        autoVm.set_tasks_target_format(paths, "mp3")
        autoVm.set_tasks_enabled_for_run(paths, false)
        autoVm.reset_tasks_output_directory(paths)
        autoVm.choose_tasks_output_directory(paths)
        autoVm.convert_selected_to_directory(paths)
        probeCompleted = true
    }
""",
            )
            joined = "\n".join(messages)
            self.assertNotIn("Passing incompatible arguments", joined)
            self.assertNotIn("Could not convert argument", joined)
        finally:
            self._dispose_view_model(model, view_model)

    def test_directory_actions_receive_qml_paths_open_dialog_and_dispatch_once(self):
        model, view_model = self._create_view_model(
            (QUEUE_MUTATION, BATCH_CONVERT)
        )
        normalized_path = os.path.normcase(
            os.path.abspath(os.path.normpath("C:/one.wav"))
        )
        selected_directory = "D:/Selected Output"
        try:
            with (
                patch(
                    "ui_next.bridge.auto_convert_viewmodel."
                    "QFileDialog.getExistingDirectory",
                    return_value=selected_directory,
                ) as dialog,
                patch.object(
                    view_model,
                    "_set_tasks_output_directory",
                    return_value=[normalized_path],
                ) as set_directory,
                patch.object(view_model, "start_convert_selected") as start_selected,
            ):
                messages = self._run_qml(
                    view_model,
                    """
    signal chooseDirectoryRequested(var paths)
    signal convertToDirectoryRequested(var paths)

    onChooseDirectoryRequested: function(paths) {
        autoVm.choose_tasks_output_directory(paths)
    }
    onConvertToDirectoryRequested: function(paths) {
        autoVm.convert_selected_to_directory(paths)
    }

    Component.onCompleted: {
        chooseDirectoryRequested(["C:/one.wav"])
        convertToDirectoryRequested(["C:/one.wav"])
        probeCompleted = true
    }
""",
                )

            joined = "\n".join(messages)
            self.assertNotIn("Passing incompatible arguments", joined)
            self.assertNotIn("Could not convert argument", joined)
            self.assertEqual(2, dialog.call_count)
            self.assertEqual(2, set_directory.call_count)
            for call in set_directory.call_args_list:
                self.assertEqual({normalized_path}, call.args[0])
                self.assertEqual(selected_directory, call.args[1])
            start_selected.assert_called_once_with([normalized_path])
        finally:
            self._dispose_view_model(model, view_model)


if __name__ == "__main__":
    unittest.main()
