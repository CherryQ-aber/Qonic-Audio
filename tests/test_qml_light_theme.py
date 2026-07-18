import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class QmlLightThemeCoverageTests(unittest.TestCase):
    def _source(self, path: str) -> str:
        return (PROJECT_ROOT / path).read_text(encoding="utf-8")

    def test_settings_switch_is_session_only_and_never_updates_theme_config_draft(self):
        source = self._source("ui_next/qml/pages/SettingsPage.qml")
        self.assertIn('"value": "dark"', source)
        self.assertIn('"value": "light"', source)
        self.assertIn("onFormatSelected: theme.setMode(value)", source)
        self.assertIn("仅本次运行生效", source)
        self.assertNotIn('updatePendingValue("theme_mode"', source)
        self.assertNotIn("save_config", source)

    def test_optional_environment_theme_input_is_limited_to_dark_or_light(self):
        source = self._source("main_qml.py")
        self.assertIn('os.environ.get("CHERRYQ_QML_THEME", "dark")', source)
        self.assertIn('{"dark", "light"}', source)
        self.assertIn('setContextProperty("qmlThemeMode", qml_theme_mode)', source)

    def test_light_critical_controls_use_shared_theme_components(self):
        selector = self._source("ui_next/qml/components/FormatSelector.qml")
        slider = self._source("ui_next/qml/components/ThemedSlider.qml")
        scrollbar = self._source("ui_next/qml/components/ThemeScrollBar.qml")

        self.assertIn("theme.inputBackground", selector)
        self.assertIn("theme.focusRing", selector)
        self.assertIn("theme.selectedBackground", selector)
        self.assertIn("theme.selectedIndicator", slider)
        self.assertIn("theme.disabledBackground", slider)
        self.assertIn("theme.borderNormal", scrollbar)

    def test_scrollbar_and_slider_coverage_includes_primary_workspaces(self):
        for path in (
            "ui_next/qml/components/TaskQueueView.qml",
            "ui_next/qml/pages/SettingsPage.qml",
            "ui_next/qml/components/LogDrawer.qml",
            "ui_next/qml/components/FormatSelector.qml",
        ):
            self.assertIn("ThemeScrollBar", self._source(path), path)

        for path in (
            "ui_next/qml/components/PitchShiftCard.qml",
            "ui_next/qml/components/PlayerBar.qml",
        ):
            self.assertIn("ThemedSlider", self._source(path), path)

    def test_shell_keeps_focus_and_capability_boundaries_outside_theme_switching(self):
        shell = self._source("ui_next/qml/AppShell.qml")
        sidebar = self._source("ui_next/qml/components/SidebarNavigation.qml")
        capabilities = self._source("ui_next/bridge/capabilities.py")

        self.assertIn("Theme {", shell)
        self.assertIn("theme.sidebarWidth", shell)
        self.assertIn("navItem.visualFocus", sidebar)
        self.assertIn("PHASE4_ENABLED_CAPABILITIES", capabilities)
        self.assertNotIn("save_config", self._source("ui_next/qml/theme/Theme.qml"))


if __name__ == "__main__":
    unittest.main()
