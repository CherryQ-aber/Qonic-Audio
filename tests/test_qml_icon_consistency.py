import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class QmlIconConsistencyTests(unittest.TestCase):
    def _source(self, path: str) -> str:
        return (PROJECT_ROOT / path).read_text(encoding="utf-8")

    def test_action_icons_are_monochrome_text_glyphs_not_external_icon_assets(self):
        source = self._source("ui_next/qml/components/ActionIcon.qml")
        self.assertIn('"refresh": "↻"', source)
        self.assertIn('"open": "↗"', source)
        self.assertIn('"close": "×"', source)
        self.assertIn("theme.iconSizeNormal", source)
        self.assertNotIn("Image {", source)
        self.assertNotIn("source:", source)

    def test_known_actions_use_a_single_named_icon(self):
        convert = self._source("ui_next/qml/components/ConvertActionBar.qml")
        single = self._source("ui_next/qml/components/SingleFileConvertPanel.qml")
        drawer = self._source("ui_next/qml/components/LogDrawer.qml")
        bottom = self._source("ui_next/qml/components/BottomStatusBar.qml")

        self.assertIn('iconName: "refresh"', convert)
        self.assertIn('iconName: "clear"', single)
        self.assertIn('iconName: "open"', single)
        self.assertIn('? "close"', drawer)
        self.assertIn('iconName: "log"', bottom)

    def test_icon_only_controls_are_not_introduced_without_accessible_text(self):
        button_source = self._source("ui_next/qml/components/WorkstationButton.qml")
        self.assertIn("Accessible.name: text", button_source)
        self.assertIn("ActionIcon", button_source)

        qml_root = PROJECT_ROOT / "ui_next/qml"
        image_uses = [
            path for path in qml_root.rglob("*.qml")
            if "Image {" in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(
            [
                qml_root / "components" / "CoverDraftEditor.qml",
                qml_root / "components" / "CoverPreviewCard.qml",
                qml_root / "components" / "CurrentFileBar.qml",
                qml_root / "components" / "FolderBrowserPane.qml",
            ],
            image_uses,
        )


if __name__ == "__main__":
    unittest.main()
