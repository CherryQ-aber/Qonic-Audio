import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class QmlLightThemeCoverageTests(unittest.TestCase):
    def _source(self, path: str) -> str:
        return (PROJECT_ROOT / path).read_text(encoding="utf-8")

    def test_settings_switch_persists_through_the_settings_view_model(self):
        source = self._source("ui_next/qml/pages/SettingsPage.qml")
        self.assertIn('"value": "dark"', source)
        self.assertIn('"value": "light"', source)
        self.assertIn('"value": "black"', source)
        self.assertIn('"value": "purple"', source)
        self.assertIn('"value": "system"', source)
        self.assertIn("settingsViewModel.applyThemeMode(value)", source)
        self.assertIn("选择后立即保存", source)
        self.assertNotIn('updatePendingValue("theme_mode"', source)

    def test_optional_environment_theme_input_is_limited_to_supported_palettes(self):
        source = self._source("main_qml.py")
        self.assertIn('"QONIC_QML_THEME"', source)
        self.assertIn('"CHERRYQ_QML_THEME"', source)
        self.assertIn('{"system", "dark", "light", "black", "purple"}', source)
        self.assertIn("raw_requested_theme not in supported_themes", source)
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
            "ui_next/qml/components/PlayerTimeline.qml",
            "ui_next/qml/components/PlaybackDeviceControl.qml",
        ):
            self.assertIn("ThemedSlider", self._source(path), path)

    def test_derived_section_cards_inherit_the_page_theme(self):
        for path in (
            "ui_next/qml/components/TaskQueueView.qml",
            "ui_next/qml/components/ConvertActionBar.qml",
            "ui_next/qml/components/CoverDraftEditor.qml",
            "ui_next/qml/components/EditorFileBrowser.qml",
        ):
            source = self._source(path)
            self.assertIn("SectionCard {", source, path)
            self.assertNotIn("property QtObject theme:", source, path)

        metadata_page = self._source("ui_next/qml/pages/MetadataPage.qml")
        info_panel = metadata_page.split("component InfoPanel: SectionCard {", 1)[1]
        info_panel = info_panel.split("component InfoRow:", 1)[0]
        self.assertIn("theme: root.theme", info_panel)

        lyrics_page = self._source("ui_next/qml/pages/LyricsCoverPage.qml")
        lyrics_header = lyrics_page.split("SectionCard {", 1)[1]
        lyrics_header = lyrics_header.split("GridLayout {", 1)[0]
        self.assertIn("theme: root.theme", lyrics_header)

    def test_shell_keeps_focus_and_capability_boundaries_outside_theme_switching(self):
        shell = self._source("ui_next/qml/AppShell.qml")
        switcher = self._source("ui_next/qml/components/WorkspaceSwitcher.qml")
        capabilities = self._source("ui_next/bridge/capabilities.py")

        self.assertIn("Theme {", shell)
        self.assertIn("FolderBrowserPane {", shell)
        self.assertIn("visible: root.folderPaneVisible", shell)
        self.assertIn("activeFocusOnTab", switcher)
        self.assertIn("Accessible.checked: selected", switcher)
        self.assertIn("PHASE4_ENABLED_CAPABILITIES", capabilities)
        self.assertNotIn("save_config", self._source("ui_next/qml/theme/Theme.qml"))


if __name__ == "__main__":
    unittest.main()
