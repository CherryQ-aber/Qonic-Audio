from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from build_qt_lgpl_integration_candidate import IMMUTABLE_TREE_EXCLUDES, _tree_digest
from run_qt_windows_native_acceptance import REQUIRED_FILES
from verify_qt_lgpl_route import GPL_ONLY_GROUPS, group_files, remove_group


class QtLgplRouteTests(unittest.TestCase):
    def test_native_acceptance_required_files_cover_runtime_and_lgpl_materials(self):
        self.assertIn("_internal/PySide6/plugins/platforms/qwindows.dll", REQUIRED_FILES)
        self.assertIn("_internal/PySide6/plugins/multimedia/ffmpegmediaplugin.dll", REQUIRED_FILES)
        self.assertIn("LICENSES/Qt/LGPL-3.0.txt", REQUIRED_FILES)
        self.assertIn("LICENSES/Qt/QT_SOURCE_AVAILABILITY.md", REQUIRED_FILES)

    def test_candidate_tree_digest_is_stable_and_can_exclude_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "one.txt").write_text("one", encoding="utf-8")
            (root / "two.txt").write_text("two", encoding="utf-8")
            (root / "COMPLIANCE_INTEGRATION_CANDIDATE.json").write_text("ignored", encoding="utf-8")
            digest, count = _tree_digest(root, exclude={"COMPLIANCE_INTEGRATION_CANDIDATE.json"})
            self.assertEqual(count, 2)
            self.assertEqual(len(digest), 64)
            self.assertEqual(
                (digest, count),
                _tree_digest(root, exclude={"COMPLIANCE_INTEGRATION_CANDIDATE.json"}),
            )

    def test_candidate_tree_excludes_only_known_runtime_artifacts(self):
        self.assertIn("COMPLIANCE_INTEGRATION_CANDIDATE.json", IMMUTABLE_TREE_EXCLUDES)
        self.assertIn("logs/runtime.log", IMMUTABLE_TREE_EXCLUDES)

    def test_gpl_only_groups_do_not_overlap_and_remove_only_their_group(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            graphs = root / "_internal/PySide6/Qt6Graphs.dll"
            quick3d = root / "_internal/PySide6/Qt6Quick3D.dll"
            timeline = root / "_internal/PySide6/qml/QtQuick/Timeline/qmldir"
            virtual_keyboard = root / "_internal/PySide6/qml/QtQuick/VirtualKeyboard/qmldir"
            ordinary = root / "_internal/PySide6/Qt6Core.dll"
            for path in (graphs, quick3d, timeline, virtual_keyboard, ordinary):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(path.name, encoding="utf-8")

            matched = {
                group: {path.relative_to(root).as_posix() for path in group_files(root, patterns)}
                for group, patterns in GPL_ONLY_GROUPS.items()
            }
            self.assertTrue(matched["qtgraphs"])
            self.assertTrue(matched["qtquick3d"])
            self.assertTrue(matched["qtquicktimeline"])
            self.assertTrue(matched["qtvirtualkeyboard"])
            self.assertFalse(set.intersection(*matched.values()))

            removed = remove_group(root, "qtgraphs")
            self.assertEqual(removed, ["_internal/PySide6/Qt6Graphs.dll"])
            self.assertFalse(graphs.exists())
            self.assertTrue(quick3d.exists())
            self.assertTrue(timeline.exists())
            self.assertTrue(virtual_keyboard.exists())
            self.assertTrue(ordinary.exists())


if __name__ == "__main__":
    unittest.main()
