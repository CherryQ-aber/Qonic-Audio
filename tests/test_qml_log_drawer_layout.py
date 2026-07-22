import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, Qt, QUrl
from PySide6.QtQml import QQmlComponent
from PySide6.QtQuick import QQuickItem, QQuickView
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class LogDrawerResponsiveLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.drawer_source = (
            PROJECT_ROOT / "ui_next/qml/components/LogDrawer.qml"
        ).read_text(encoding="utf-8")
        self.shell_source = (PROJECT_ROOT / "ui_next/qml/AppShell.qml").read_text(
            encoding="utf-8"
        )
        self.top_source = (
            PROJECT_ROOT / "ui_next/qml/components/TopStatusBar.qml"
        ).read_text(encoding="utf-8")
        self.log_model_source = (
            PROJECT_ROOT / "ui_next/bridge/log_model.py"
        ).read_text(encoding="utf-8")

        self.view = QQuickView()
        self.component = QQmlComponent(self.view.engine())
        self.component.setData(
            b'''import QtQuick
import "ui_next/qml/components"

Item {
    width: 1280
    height: 720

    LogDrawer {
        id: drawer
        objectName: "drawerUnderTest"
        anchors.fill: parent
        workspaceLeftInset: 218
        workspaceRightInset: 292
        globalStatusSummary: "Watcher off / No tasks / Normal"
    }
}
''',
            QUrl.fromLocalFile(str(PROJECT_ROOT / "log_drawer_layout_probe.qml")),
        )
        self.container = self.component.create()
        self.assertIsNotNone(self.container, self.component.errors())
        self.assertIsInstance(self.container, QQuickItem)
        self.container.setParentItem(self.view.contentItem())
        self.view.setWidth(1280)
        self.view.setHeight(720)
        self.view.show()
        self.app.processEvents()

        self.drawer = self.container.findChild(QObject, "drawerUnderTest")
        self.assertIsNotNone(self.drawer)
        self.panel = self.drawer.findChild(QObject, "logDrawerPanel")
        self.assertIsNotNone(self.panel)

    def tearDown(self):
        self.view.close()
        self.container.deleteLater()
        self.view.deleteLater()

    def _open_drawer(self, width, height, right_inset):
        self.drawer.setProperty("opened", False)
        self.container.setWidth(width)
        self.container.setHeight(height)
        self.drawer.setProperty("workspaceLeftInset", 218)
        self.drawer.setProperty("workspaceRightInset", right_inset)
        self.app.processEvents()
        self.drawer.setProperty("opened", True)
        QTest.qWait(220)
        self.app.processEvents()

    def test_source_defines_compact_overlay_and_bounded_side_widths(self):
        self.assertIn("property bool compactLayout: root.width < 1200", self.drawer_source)
        self.assertIn("property int minimumWorkspaceWidth: 620", self.drawer_source)
        self.assertIn("root.width >= 1600 ? root.wideDrawerMaxWidth", self.drawer_source)
        self.assertIn("root.width >= 1600 ? root.width * 0.35", self.drawer_source)
        self.assertIn("root.width * 0.32", self.drawer_source)
        self.assertIn("workspaceLeftInset", self.drawer_source)
        self.assertIn("workspaceRightInset", self.drawer_source)
        self.assertIn("Shortcut {", self.drawer_source)
        self.assertIn("context: Qt.ApplicationShortcut", self.drawer_source)
        self.assertNotIn("root.width * 0.42", self.drawer_source)

    def test_shell_coordinates_drawer_with_the_global_folder_pane(self):
        self.assertIn("FolderBrowserPane {", self.shell_source)
        self.assertIn(
            "visible: root.folderPaneVisible",
            self.shell_source,
        )
        self.assertIn(
            "workspaceLeftInset: folderBrowserPane.visible ? folderBrowserPane.width : 0",
            self.shell_source,
        )
        self.assertIn("workspaceRightInset: 0", self.shell_source)
        self.assertNotIn("logDrawerOpener", self.shell_source)
        self.assertIn("function openLogDrawer()", self.shell_source)
        self.assertIn("onLogRequested: root.openLogDrawer()", self.shell_source)
        self.assertNotIn("BottomStatusBar {", self.shell_source)
        self.assertIn(
            'globalStatusSummary: appState.statusSummary || "就绪"',
            self.shell_source,
        )
        self.assertNotIn("inspectorPanelVisible", self.shell_source)

    def test_log_opener_and_drawer_controls_are_keyboard_focusable(self):
        self.assertIn('objectName: "openGlobalLogButton"', self.top_source)
        self.assertIn("function focusLogButton()", self.top_source)
        self.assertIn("Qt.callLater(topStatusBar.focusLogButton)", self.shell_source)
        self.assertIn("component DrawerButton: WorkstationButton", self.drawer_source)
        self.assertIn('objectName: "closeLogDrawerButton"', self.drawer_source)
        self.assertIn("drawerPanel.forceActiveFocus()", self.drawer_source)

    def test_global_status_summary_is_available_in_the_log_drawer(self):
        status_summary = self.drawer.findChild(
            QObject, "logDrawerGlobalStatusSummary"
        )
        self.assertIsNotNone(status_summary)
        self.assertEqual(
            "当前状态：Watcher off / No tasks / Normal",
            status_summary.property("text"),
        )

    def test_drawer_stays_singleton_and_keeps_long_log_text_non_disruptive(self):
        self.assertEqual(1, self.shell_source.count("LogDrawer {"))
        self.assertEqual(1, self.shell_source.count("onLogRequested:"))
        self.assertIn("selectByMouse: true", self.drawer_source)
        self.assertIn("textFormat: TextEdit.PlainText", self.drawer_source)
        self.assertNotIn("positionViewAtEnd", self.drawer_source)
        self.assertIn("_cherryq_qml_log_handler", self.log_model_source)
        self.assertIn("return handler", self.log_model_source)

    def test_runtime_layout_uses_bottom_overlay_on_narrow_windows(self):
        self._open_drawer(1100, 720, 0)

        self.assertTrue(self.drawer.property("compactLayout"))
        self.assertEqual(218, self.panel.x())
        self.assertGreaterEqual(self.panel.y(), 0)
        self.assertLess(self.panel.height(), 320)
        self.assertGreaterEqual(self.panel.height(), 220)
        self.assertLessEqual(self.panel.width(), 882)

    def test_runtime_layout_keeps_medium_and_wide_drawers_bounded(self):
        self._open_drawer(1280, 720, 292)
        self.assertFalse(self.drawer.property("compactLayout"))
        self.assertLessEqual(self.panel.width(), 400)
        self.assertLess(self.panel.width(), 1280 * 0.42)
        self.assertEqual(1280 - self.panel.width(), self.panel.x())

        self._open_drawer(1440, 900, 292)
        self.assertLessEqual(self.panel.width(), 400)
        self.assertLessEqual(self.panel.width(), 1440 * 0.32)
        self.assertEqual(1440 - self.panel.width(), self.panel.x())

        self._open_drawer(1920, 1080, 292)
        self.assertLessEqual(self.panel.width(), 560)
        self.assertLessEqual(self.panel.width(), 1920 * 0.35)
        self.assertEqual(1920 - self.panel.width(), self.panel.x())

    def test_escape_emits_close_request_from_the_open_drawer(self):
        self._open_drawer(1280, 720, 292)
        close_requests = []
        self.drawer.closeRequested.connect(lambda: close_requests.append(True))
        self.panel.forceActiveFocus()
        self.app.processEvents()

        QTest.keyClick(self.view, Qt.Key_Escape)
        self.assertEqual([True], close_requests)


if __name__ == "__main__":
    unittest.main()
