import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class QmlComponentStateTests(unittest.TestCase):
    def _source(self, path: str) -> str:
        return (PROJECT_ROOT / path).read_text(encoding="utf-8")

    def test_shared_button_covers_interaction_focus_disabled_and_loading_states(self):
        source = self._source("ui_next/qml/components/WorkstationButton.qml")
        for state in (
            "property bool loading", "disabledReason", "root.hovered",
            "root.pressed", "root.visualFocus", "!root.enabled",
            "focusPolicy: enabled ? Qt.TabFocus : Qt.NoFocus",
        ):
            self.assertIn(state, source)

    def test_high_frequency_actions_use_the_shared_button(self):
        for path in (
            "ui_next/qml/components/ConvertActionBar.qml",
            "ui_next/qml/components/ScanPreviewPanel.qml",
            "ui_next/qml/components/SingleFileConvertPanel.qml",
            "ui_next/qml/components/LogDrawer.qml",
            "ui_next/qml/components/PitchShiftCard.qml",
            "ui_next/qml/pages/SettingsPage.qml",
        ):
            self.assertIn("WorkstationButton", self._source(path), path)

    def test_cards_badges_navigation_and_list_rows_have_stable_state_feedback(self):
        section_card = self._source("ui_next/qml/components/SectionCard.qml")
        badge = self._source("ui_next/qml/components/StatusBadge.qml")
        sidebar = self._source("ui_next/qml/components/SidebarNavigation.qml")
        rows = self._source("ui_next/qml/components/ScanPreviewPanel.qml")

        self.assertIn("Behavior on color", section_card)
        self.assertIn("Behavior on border.color", badge)
        self.assertIn("navItem.visualFocus", sidebar)
        self.assertIn("property bool hovered: rowMouse.containsMouse", rows)
        self.assertIn("theme.selectedBackground", rows)


if __name__ == "__main__":
    unittest.main()
