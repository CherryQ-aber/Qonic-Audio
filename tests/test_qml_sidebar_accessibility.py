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


class SidebarAccessibilityTests(unittest.TestCase):
    MODULES = [
        {
            "key": "autoConvert",
            "title": "自动转码",
            "description": "任务监控",
        },
        {
            "key": "audioEditor",
            "title": "音频编辑",
            "description": "编辑入口",
        },
        {
            "key": "metadata",
            "title": "文件信息",
            "description": "只读摘要",
        },
    ]

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_sidebar_uses_a_focusable_button_not_a_mouse_area_delegate(self):
        self.assertIn("delegate: Button", self.source)
        self.assertIn("activeFocusOnTab", self.source)
        self.assertIn("focusPolicy: Qt.TabFocus", self.source)
        self.assertNotIn("MouseArea {", self.source)

    def test_keyboard_commands_cover_roving_navigation_and_activation(self):
        for handler in (
            "Keys.onUpPressed",
            "Keys.onDownPressed",
            "Keys.onReturnPressed",
            "Keys.onEnterPressed",
            "Keys.onPressed",
        ):
            self.assertIn(handler, self.source)

        self.assertIn("focusNavigationIndex", self.source)
        self.assertIn("activateNavigationIndex", self.source)
        self.assertIn("Math.max(0, Math.min", self.source)
        self.assertIn("Qt.Key_Home", self.source)
        self.assertIn("Qt.Key_End", self.source)
        self.assertIn("Qt.Key_Space", self.source)

    def test_selected_hover_and_keyboard_focus_are_separate_states(self):
        self.assertIn("property bool selected", self.source)
        self.assertIn("navItem.hovered", self.source)
        self.assertIn("navItem.visualFocus", self.source)
        self.assertIn("border.width: navItem.visualFocus ? 2", self.source)
        self.assertIn("font.weight: navItem.selected", self.source)

    def test_sidebar_exposes_accessible_page_state(self):
        self.assertIn("Accessible.role: Accessible.Button", self.source)
        self.assertIn("Accessible.name: modelData.title", self.source)
        self.assertIn("Accessible.description: selected", self.source)
        self.assertIn("Accessible.checked: selected", self.source)

    def setUp(self):
        self.source = (
            PROJECT_ROOT / "ui_next/qml/components/SidebarNavigation.qml"
        ).read_text(encoding="utf-8")
        self.view = QQuickView()
        self.component = QQmlComponent(self.view.engine())
        self.component.setData(
            b'''import QtQuick
import "ui_next/qml/components"

Item {
    width: 280
    height: 300

    SidebarNavigation {
        id: sidebar
        objectName: "sidebarUnderTest"
        anchors.fill: parent
        modules: [
            { "key": "autoConvert", "title": "\xe8\x87\xaa\xe5\x8a\xa8\xe8\xbd\xac\xe7\xa0\x81", "description": "\xe4\xbb\xbb\xe5\x8a\xa1\xe7\x9b\x91\xe6\x8e\xa7" },
            { "key": "audioEditor", "title": "\xe9\x9f\xb3\xe9\xa2\x91\xe7\xbc\x96\xe8\xbe\x91", "description": "\xe7\xbc\x96\xe8\xbe\x91\xe5\x85\xa5\xe5\x8f\xa3" },
            { "key": "metadata", "title": "\xe6\x96\x87\xe4\xbb\xb6\xe4\xbf\xa1\xe6\x81\xaf", "description": "\xe5\x8f\xaa\xe8\xaf\xbb\xe6\x91\x98\xe8\xa6\x81" }
        ]
        currentModuleKey: "autoConvert"
    }
}
''',
            QUrl.fromLocalFile(str(PROJECT_ROOT / "sidebar_accessibility_probe.qml")),
        )
        self.container = self.component.create()
        self.assertIsNotNone(self.container, self.component.errors())
        self.assertIsInstance(self.container, QQuickItem)
        self.container.setParentItem(self.view.contentItem())
        self.view.setWidth(280)
        self.view.setHeight(300)
        self.view.show()
        self.app.processEvents()

        self.requests = []
        self.root = self.container.findChild(QObject, "sidebarUnderTest")
        self.assertIsNotNone(self.root)
        self.root.moduleRequested.connect(self.requests.append)

    def tearDown(self):
        self.view.close()
        self.container.deleteLater()
        self.view.deleteLater()

    def _focus_item(self, index):
        self.root.focusNavigationIndex(index)
        self.app.processEvents()
        self.assertEqual(index, self.root.property("keyboardFocusIndex"))

    def test_arrow_home_and_end_move_focus_without_activating_pages(self):
        self._focus_item(0)
        QTest.keyClick(self.view, Qt.Key_Down)
        self.assertEqual(1, self.root.property("keyboardFocusIndex"))

        QTest.keyClick(self.view, Qt.Key_End)
        self.assertEqual(len(self.MODULES) - 1, self.root.property("keyboardFocusIndex"))

        QTest.keyClick(self.view, Qt.Key_Up)
        self.assertEqual(1, self.root.property("keyboardFocusIndex"))

        QTest.keyClick(self.view, Qt.Key_Home)
        self.assertEqual(0, self.root.property("keyboardFocusIndex"))
        self.assertEqual([], self.requests)

    def test_return_and_space_activate_once_and_keep_focus_on_item(self):
        self._focus_item(1)
        QTest.keyClick(self.view, Qt.Key_Return)
        self.assertEqual(["audioEditor"], self.requests)
        self.assertEqual(1, self.root.property("keyboardFocusIndex"))

        QTest.keyClick(self.view, Qt.Key_Space)
        self.assertEqual(["audioEditor", "audioEditor"], self.requests)
        self.assertEqual(1, self.root.property("keyboardFocusIndex"))


if __name__ == "__main__":
    unittest.main()
