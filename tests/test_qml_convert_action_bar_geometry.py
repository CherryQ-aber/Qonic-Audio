import os
import unittest
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, QPointF, QUrl
from PySide6.QtQml import QQmlComponent
from PySide6.QtQuick import QQuickItem, QQuickView
from PySide6.QtWidgets import QApplication


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ConvertActionBarGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _rect(self, item: QQuickItem, root: QQuickItem):
        point = item.mapToItem(root, QPointF(0, 0))
        return point.x(), point.y(), item.width(), item.height()

    def _create_probe(self, width: int):
        source = f'''import QtQuick
import "ui_next/qml/components"

Item {{
    width: {width}
    height: 300

    QtObject {{
        id: viewModel
        property bool previewMode: true
        property bool canBatchConvert: false
        property bool canMutateQueue: false
        property bool hasBackgroundTask: false
        property bool isQueuePreparing: false
        property bool canCancelCurrentTask: false
        property bool canStopAfterCurrentTask: false
        property string lastOperation: "等待操作"
    }}
    QtObject {{
        id: queueModel
        property int clearableCount: 0
        property int retryableCount: 0
    }}

    ConvertActionBar {{
        objectName: "actionBarUnderTest"
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        autoConvertViewModel: viewModel
        taskQueueModel: queueModel
    }}
}}
'''.encode("utf-8")
        view = QQuickView()
        component = QQmlComponent(view.engine())
        component.setData(
            source,
            QUrl.fromLocalFile(str(PROJECT_ROOT / "convert_action_bar_geometry_probe.qml")),
        )
        container = component.create()
        self.assertIsNotNone(container, component.errors())
        self.assertIsInstance(container, QQuickItem)
        container.setParentItem(view.contentItem())
        view.setWidth(width)
        view.setHeight(300)
        view.show()
        self.app.processEvents()
        return view, component, container

    def test_queue_actions_stay_inside_the_compact_action_bar(self):
        view, component, container = self._create_probe(1018)
        try:
            action_bar = container.findChild(QObject, "actionBarUnderTest")
            action_row = container.findChild(QObject, "convertActionRow")
            restriction = container.findChild(QObject, "actionRestrictionText")
            buttons = [
                container.findChild(QObject, name)
                for name in (
                    "queueStartButton",
                    "queueConvertToButton",
                    "queueCancelButton",
                    "queueStopButton",
                    "queueRefreshButton",
                    "queueClearButton",
                    "queueRetryButton",
                )
            ]
            self.assertTrue(all((action_bar, action_row, restriction, *buttons)))
            self.assertEqual(
                ["清除终态", "重试失败"],
                [str(button.property("text")) for button in buttons[-2:]],
            )

            bar = self._rect(action_bar, container)
            row = self._rect(action_row, container)
            note = self._rect(restriction, container)
            self.assertLessEqual(row[1] + row[3], note[1] + 1)
            self.assertLessEqual(row[1] + row[3], bar[1] + bar[3] + 1)

            for index, button in enumerate(buttons):
                button_rect = self._rect(button, container)
                self.assertGreater(button_rect[2], 0)
                self.assertGreaterEqual(button_rect[0], row[0] - 1)
                self.assertLessEqual(button_rect[0] + button_rect[2], row[0] + row[2] + 1)
                self.assertGreaterEqual(button_rect[1], row[1] - 1)
                self.assertLessEqual(button_rect[1] + button_rect[3], row[1] + row[3] + 1)
                self.assertEqual(index == 4, bool(button.property("enabled")))
        finally:
            view.close()
            container.deleteLater()
            component.deleteLater()
            view.deleteLater()
            self.app.processEvents()

    def test_queue_action_flow_wraps_without_horizontal_overflow(self):
        view, component, container = self._create_probe(620)
        try:
            action_row = container.findChild(QObject, "convertActionRow")
            buttons = [
                container.findChild(QObject, name)
                for name in (
                    "queueStartButton",
                    "queueConvertToButton",
                    "queueCancelButton",
                    "queueStopButton",
                    "queueRefreshButton",
                    "queueClearButton",
                    "queueRetryButton",
                )
            ]
            self.assertTrue(all((action_row, *buttons)))
            row = self._rect(action_row, container)
            button_rects = [self._rect(button, container) for button in buttons]
            self.assertGreater(len({round(rect[1], 1) for rect in button_rects}), 1)
            for rect in button_rects:
                self.assertGreaterEqual(rect[0], row[0] - 1)
                self.assertLessEqual(rect[0] + rect[2], row[0] + row[2] + 1)
        finally:
            view.close()
            container.deleteLater()
            component.deleteLater()
            view.deleteLater()
            self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
