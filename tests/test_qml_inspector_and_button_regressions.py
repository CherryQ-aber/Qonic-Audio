import os
import unittest
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, QUrl
from PySide6.QtQml import QQmlComponent
from PySide6.QtQuick import QQuickItem, QQuickView
from PySide6.QtWidgets import QApplication

from ui_next.bridge.settings_viewmodel import SettingsViewModel


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class QmlInspectorAndButtonRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _source(self, relative_path: str) -> str:
        return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")

    def _create_probe(self, source: bytes, name: str, context=None):
        view = QQuickView()
        if context:
            for key, value in context.items():
                view.rootContext().setContextProperty(key, value)
        component = QQmlComponent(view.engine())
        component.setData(source, QUrl.fromLocalFile(str(PROJECT_ROOT / name)))
        container = component.create()
        self.assertIsNotNone(container, component.errors())
        self.assertIsInstance(container, QQuickItem)
        container.setParentItem(view.contentItem())
        view.setWidth(int(container.width()))
        view.setHeight(int(container.height()))
        view.show()
        self.app.processEvents()
        return view, component, container

    def _dispose_probe(self, view, container):
        view.close()
        container.deleteLater()
        view.deleteLater()
        self.app.processEvents()

    def test_runtime_inspector_content_keeps_a_readable_viewport_width(self):
        source = '''import QtQuick
import "ui_next/qml/components"
import "ui_next/qml/theme"

Item {
    width: 292
    height: 800

    Theme { id: probeTheme; objectName: "themeUnderTest" }
    RightInspector {
        objectName: "inspectorUnderTest"
        anchors.fill: parent
        theme: probeTheme
        moduleName: "自动转码"
        moduleDescription: "用于验证检查器内容宽度和纵向滚动。"
    }
}
'''.encode("utf-8")
        view, _component, container = self._create_probe(
            source, "right_inspector_regression_probe.qml"
        )
        try:
            theme = container.findChild(QObject, "themeUnderTest")
            inspector = container.findChild(QObject, "inspectorUnderTest")
            scroll = container.findChild(QObject, "rightInspectorScroll")
            content = container.findChild(QObject, "rightInspectorContent")
            self.assertIsNotNone(theme)
            self.assertIsNotNone(inspector)
            self.assertIsNotNone(scroll)
            self.assertIsNotNone(content)

            minimum = int(theme.property("inspectorMinimumWidth"))
            preferred = int(theme.property("inspectorWidth"))
            maximum = int(theme.property("inspectorMaximumWidth"))
            self.assertGreaterEqual(minimum, 260)
            self.assertLessEqual(minimum, preferred)
            self.assertLessEqual(preferred, maximum)
            self.assertGreaterEqual(inspector.width(), minimum)

            available_width = float(scroll.property("availableWidth"))
            self.assertGreaterEqual(content.width(), 240)
            self.assertLessEqual(content.width(), available_width + 0.5)
            self.assertLessEqual(float(scroll.property("contentWidth")), available_width + 0.5)
        finally:
            self._dispose_probe(view, container)

    def test_runtime_header_omits_status_badges_and_global_actions_have_content(self):
        source = '''import QtQuick
import "ui_next/qml/components"

Item {
    width: 1200
    height: 58

    TopStatusBar {
        objectName: "topBarUnderTest"
        anchors.fill: parent
        workspaces: [
            { "key": "autoConvert", "title": "自动转码", "description": "任务" },
            { "key": "audioEditor", "title": "音频编辑", "description": "编辑" }
        ]
        currentWorkspaceKey: "autoConvert"
    }
}
'''.encode("utf-8")
        view, _component, container = self._create_probe(
            source, "top_status_regression_probe.qml"
        )
        try:
            workspace = container.findChild(QObject, "workspaceSwitcher")
            settings = container.findChild(QObject, "openSettingsButton")
            log = container.findChild(QObject, "openGlobalLogButton")
            self.assertIsNone(
                container.findChild(QObject, "modeStatusBadge")
            )
            self.assertIsNone(
                container.findChild(QObject, "capabilityStatusBadge")
            )
            self.assertEqual(
                "autoConvert",
                workspace.property("currentWorkspaceKey"),
            )
            self.assertEqual("设置", settings.property("text"))
            self.assertTrue(str(settings.property("toolTipText")).strip())
            self.assertEqual("日志", log.property("text"))
            self.assertEqual("log", log.property("iconName"))
            self.assertTrue(str(log.property("toolTipText")).strip())
        finally:
            self._dispose_probe(view, container)

    def test_runtime_settings_actions_keep_their_original_visible_labels(self):
        view_model = SettingsViewModel()
        source = '''import QtQuick
import "ui_next/qml/pages"

Item {
    width: 1000
    height: 900
    SettingsPage { objectName: "settingsUnderTest"; anchors.fill: parent }
}
'''.encode("utf-8")
        view, _component, container = self._create_probe(
            source,
            "settings_button_regression_probe.qml",
            {"settingsViewModel": view_model},
        )
        try:
            actions = container.findChildren(QObject, "settingsActionButton")
            labels = {str(action.property("text")) for action in actions}
            self.assertEqual(8, len(actions))
            self.assertEqual(
                {
                    "模拟保存草稿",
                    "放弃草稿",
                    "重新读取真实配置",
                    "保存设置",
                    "打开日志位置",
                    "复制最近日志",
                    "清空日志抽屉",
                    "清理缓存（当前不可用）",
                },
                labels,
            )
            for action in actions:
                self.assertTrue(str(action.property("text")).strip())
                self.assertGreater(action.width(), 90)
        finally:
            self._dispose_probe(view, container)

    def test_normal_mode_global_actions_stay_inside_the_1080px_window(self):
        source = '''import QtQuick
import "ui_next/qml/components"

Item {
    width: 1080
    height: 58

    TopStatusBar {
        anchors.fill: parent
        versionLabel: "v5.0"
        workspaces: [
            { "key": "autoConvert", "title": "自动转码", "description": "任务" },
            { "key": "audioEditor", "title": "音频编辑", "description": "编辑" }
        ]
        currentWorkspaceKey: "autoConvert"
    }
}
'''.encode("utf-8")
        view, _component, container = self._create_probe(
            source,
            "top_status_normal_mode_geometry_probe.qml",
        )
        try:
            settings = container.findChild(QObject, "openSettingsButton")
            log = container.findChild(QObject, "openGlobalLogButton")
            self.assertIsNone(
                container.findChild(QObject, "capabilityStatusBadge")
            )
            for action in (settings, log):
                self.assertGreaterEqual(action.x(), 0)
                self.assertLessEqual(
                    action.x() + action.width(),
                    container.width() + 0.5,
                )

            container.setWidth(1536)
            view.setWidth(1536)
            self.app.processEvents()
            self.assertLessEqual(
                log.x() + log.width(),
                container.width() + 0.5,
            )
        finally:
            self._dispose_probe(view, container)

    def test_shell_uses_persistent_workspaces_without_the_legacy_inspector(self):
        shell = self._source("ui_next/qml/AppShell.qml")
        inspector = self._source("ui_next/qml/components/RightInspector.qml")
        top = self._source("ui_next/qml/components/TopStatusBar.qml")
        settings = self._source("ui_next/qml/pages/SettingsPage.qml")

        self.assertIn("WorkspaceStack {", shell)
        self.assertIn("FolderBrowserPane {", shell)
        self.assertIn("SettingsOverlay {", shell)
        self.assertNotIn("SidebarNavigation {", shell)
        self.assertNotIn("RightInspector {", shell)
        self.assertNotIn("Loader {", shell)
        self.assertIn("contentWidth: Math.max(0, width - leftPadding - rightPadding", inspector)
        self.assertIn("- inspectorVerticalScrollBar.width)", inspector)
        self.assertIn("ScrollBar.horizontal.policy: ScrollBar.AlwaysOff", inspector)
        self.assertIn('objectName: "openSettingsButton"', top)
        self.assertIn('objectName: "openGlobalLogButton"', top)
        self.assertIn("text: label", settings)


if __name__ == "__main__":
    unittest.main()
