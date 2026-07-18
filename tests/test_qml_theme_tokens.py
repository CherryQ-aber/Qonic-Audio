import os
import re
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QColor
from PySide6.QtQml import QQmlComponent
from PySide6.QtQuick import QQuickItem, QQuickView
from PySide6.QtWidgets import QApplication


PROJECT_ROOT = Path(__file__).resolve().parents[1]
THEME_PATH = PROJECT_ROOT / "ui_next/qml/theme/Theme.qml"


class QmlThemeTokenTests(unittest.TestCase):
    TOKEN_NAMES = (
        "windowBackground", "workspaceBackground", "panelBackground",
        "panelBackgroundRaised", "inputBackground", "overlayBackground",
        "drawerBackground", "textPrimary", "textSecondary", "textMuted",
        "textDisabled", "textInverse", "linkText", "borderSubtle",
        "borderNormal", "borderStrong", "divider", "focusRing",
        "hoverBackground", "pressedBackground", "selectedBackground",
        "selectedIndicator", "disabledBackground", "info", "infoBackground",
        "success", "successBackground", "warning", "warningBackground",
        "error", "errorBackground", "spacingXs", "spacingSm", "spacingMd",
        "spacingLg", "spacingXl", "radiusSmall", "radiusMedium", "radiusLarge",
        "controlHeightSmall", "controlHeightNormal", "controlHeightLarge",
        "sidebarWidth", "inspectorWidth", "fontCaption", "fontBody",
        "fontBodyStrong", "fontSubtitle", "fontTitle", "fontPageTitle",
        "durationFast", "durationNormal", "durationSlow",
    )

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.view = QQuickView()
        self.component = QQmlComponent(self.view.engine())
        self.component.setData(
            b'''import QtQuick
import "ui_next/qml/theme"

Item {
    Theme { id: sessionTheme; objectName: "themeUnderTest" }
}
''',
            QUrl.fromLocalFile(str(PROJECT_ROOT / "theme_token_probe.qml")),
        )
        self.container = self.component.create()
        self.assertIsNotNone(self.container, self.component.errors())
        self.assertIsInstance(self.container, QQuickItem)
        self.theme = self.container.findChild(QObject, "themeUnderTest")
        self.assertIsNotNone(self.theme)

    def tearDown(self):
        self.container.deleteLater()
        self.view.deleteLater()

    def test_theme_declares_the_shared_token_surface(self):
        source = THEME_PATH.read_text(encoding="utf-8")
        for name in self.TOKEN_NAMES:
            self.assertRegex(source, rf"property (?:color|int) {name}:")

    def test_dark_is_default_and_light_switches_runtime_palette(self):
        self.assertEqual("dark", self.theme.property("mode"))
        dark_window = QColor(self.theme.property("windowBackground"))
        dark_text = QColor(self.theme.property("textPrimary"))

        self.theme.setMode("light")
        self.app.processEvents()
        self.assertEqual("light", self.theme.property("mode"))
        light_window = QColor(self.theme.property("windowBackground"))
        light_text = QColor(self.theme.property("textPrimary"))
        self.assertTrue(light_window.isValid())
        self.assertTrue(light_text.isValid())
        self.assertNotEqual(dark_window, light_window)
        self.assertNotEqual(dark_text, light_text)

    def test_unknown_mode_safely_resolves_to_dark(self):
        self.theme.setMode("system")
        self.app.processEvents()
        self.assertEqual("dark", self.theme.property("mode"))

    def test_non_theme_qml_has_no_literal_theme_colours(self):
        qml_root = PROJECT_ROOT / "ui_next/qml"
        literal_pattern = re.compile(r"#[0-9A-Fa-f]{3,8}")
        for qml_path in qml_root.rglob("*.qml"):
            if qml_path == THEME_PATH:
                continue
            self.assertIsNone(
                literal_pattern.search(qml_path.read_text(encoding="utf-8")),
                qml_path.relative_to(PROJECT_ROOT),
            )


if __name__ == "__main__":
    unittest.main()
