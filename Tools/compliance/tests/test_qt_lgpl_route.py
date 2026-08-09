from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from verify_qt_lgpl_route import GPL_ONLY_GROUPS, group_files, remove_group


class QtLgplRouteTests(unittest.TestCase):
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
