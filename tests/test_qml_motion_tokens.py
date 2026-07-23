import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class QmlMotionTokenTests(unittest.TestCase):
    def test_motion_tokens_stay_within_the_phase_limits(self):
        source = (PROJECT_ROOT / "ui_next/qml/theme/Theme.qml").read_text(
            encoding="utf-8"
        )
        values = {
            name: int(value)
            for name, value in re.findall(
                r"readonly property int (duration(?:Fast|Normal|Slow)): (\d+)",
                source,
            )
        }
        self.assertEqual({"durationFast", "durationNormal", "durationSlow"}, set(values))
        self.assertGreaterEqual(values["durationFast"], 80)
        self.assertLessEqual(values["durationFast"], 120)
        self.assertLessEqual(values["durationNormal"], 180)
        self.assertLessEqual(values["durationSlow"], 240)

    def test_component_animations_reference_motion_tokens(self):
        qml_root = PROJECT_ROOT / "ui_next/qml"
        raw_duration_pattern = re.compile(r"duration:\s*\d+")
        animations = []
        for path in qml_root.rglob("*.qml"):
            source = path.read_text(encoding="utf-8")
            if "Animation" in source or "Behavior on" in source:
                animations.append(source)
            if path.name != "Theme.qml":
                self.assertIsNone(raw_duration_pattern.search(source), path)

        self.assertTrue(animations)
        combined = "\n".join(animations)
        self.assertIn("theme.durationFast", combined)
        self.assertIn("theme.durationNormal", combined)


if __name__ == "__main__":
    unittest.main()
