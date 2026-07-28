import os
import tempfile
import unittest
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import (
    Q_ARG,
    QMetaObject,
    QObject,
    QPoint,
    QPointF,
    Qt,
    QUrl,
)
from PySide6.QtQml import QQmlComponent
from PySide6.QtQuick import QQuickItem, QQuickView
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from ui_next.bridge.capabilities import LYRICS_READ, CapabilityGate
from ui_next.bridge.edit_session import EditSessionViewModel


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Phase595LyricsTimestampQmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.audio_path = Path(self.temp_dir.name) / "lyrics.wav"
        self.audio_path.write_bytes(b"audio")
        self.edit_session = EditSessionViewModel(
            CapabilityGate((LYRICS_READ,))
        )
        self.view = QQuickView()
        self.view.rootContext().setContextProperty(
            "editSessionUnderTest",
            self.edit_session,
        )
        self.component = QQmlComponent(self.view.engine())
        source = b'''import QtQuick
import "ui_next/qml/components"

Item {
    width: 1000
    height: 620

    QtObject {
        id: playerStub
        objectName: "playerStubUnderTest"
        property bool hasPlaybackSource: true
        property int position: 201450
        property string timestampPrecision: "millisecond"
        property int playCallCount: 0
        function play() { playCallCount += 1 }
    }

    LyricsDraftEditor {
        id: editor
        objectName: "timestampEditorUnderTest"
        anchors.fill: parent
        editSession: editSessionUnderTest
        audioPlayer: playerStub
    }
}
'''
        self.component.setData(
            source,
            QUrl.fromLocalFile(
                str(PROJECT_ROOT / "phase595_lyrics_timestamp_probe.qml")
            ),
        )
        self.container = None

    def tearDown(self):
        self.view.close()
        if self.container is not None:
            self.container.deleteLater()
        self.component.deleteLater()
        self.view.deleteLater()
        self.app.processEvents()
        self.temp_dir.cleanup()

    def _load(self, text: str):
        self.edit_session.loadLyricsResult(
            {
                "ok": True,
                "path": str(self.audio_path),
                "has_lyrics": True,
                "lyrics_text": text,
                "external_lrc_result": {"ok": False},
            }
        )
        self.container = self.component.create()
        self.assertIsNotNone(self.container, self.component.errors())
        self.assertIsInstance(self.container, QQuickItem)
        self.container.setParentItem(self.view.contentItem())
        self.view.setWidth(1000)
        self.view.setHeight(620)
        self.view.show()
        self.app.processEvents()
        editor = self.container.findChild(QQuickItem, "lyricsDraftTextArea")
        button = self.container.findChild(
            QQuickItem,
            "insertCurrentTimestampButton",
        )
        player_stub = self.container.findChild(QObject, "playerStubUnderTest")
        self.assertIsNotNone(editor)
        self.assertIsNotNone(button)
        self.assertIsNotNone(player_stub)
        self.assertTrue(button.property("enabled"))
        return editor, button, player_stub

    def _click(self, button: QQuickItem) -> None:
        scene_point = button.mapToItem(
            self.view.contentItem(),
            QPointF(button.width() / 2, button.height() / 2),
        )
        QTest.mouseClick(
            self.view,
            Qt.LeftButton,
            Qt.NoModifier,
            QPoint(round(scene_point.x()), round(scene_point.y())),
        )
        QTest.qWait(20)
        self.app.processEvents()

    def test_cursor_line_insertion_restores_focus_and_cursor(self):
        original = "first\nsecond\nthird"
        text_area, button, player_stub = self._load(original)
        cursor_position = original.index("second") + 2
        text_area.forceActiveFocus()
        text_area.setProperty("cursorPosition", cursor_position)
        self.app.processEvents()

        self._click(button)

        self.assertEqual(
            "first\n[03:21.450]second\nthird",
            self.edit_session.draftLyrics,
        )
        self.assertEqual(
            cursor_position + len("[03:21.450]"),
            text_area.property("cursorPosition"),
        )
        self.assertTrue(text_area.property("activeFocus"))
        self.assertEqual(2, self.edit_session.draftLyrics.count("\n"))
        self.assertEqual(0, player_stub.property("playCallCount"))

    def test_multiline_selection_uses_start_line_and_keeps_selected_text(self):
        original = "zero\nalpha\nbeta"
        text_area, button, player_stub = self._load(original)
        player_stub.setProperty("timestampPrecision", "centisecond")
        selection_start = original.index("alpha") + 1
        selection_end = original.index("beta") + 2
        selected_text = original[selection_start:selection_end]
        text_area.forceActiveFocus()
        invoked = QMetaObject.invokeMethod(
            text_area,
            "select",
            Qt.DirectConnection,
            Q_ARG(int, selection_start),
            Q_ARG(int, selection_end),
        )
        self.assertTrue(invoked)
        self.app.processEvents()

        self._click(button)

        expected = "zero\n[03:21.45]alpha\nbeta"
        self.assertEqual(expected, self.edit_session.draftLyrics)
        shifted_start = int(text_area.property("selectionStart"))
        shifted_end = int(text_area.property("selectionEnd"))
        self.assertEqual(selected_text, expected[shifted_start:shifted_end])
        self.assertEqual(
            selection_start + len("[03:21.45]"),
            shifted_start,
        )
        self.assertTrue(text_area.property("activeFocus"))
        self.assertEqual(0, player_stub.property("playCallCount"))

    def test_undo_button_restores_text_without_touching_player(self):
        original = "first\nsecond"
        _text_area, insert_button, player_stub = self._load(original)
        undo_button = self.container.findChild(QQuickItem, "undoLyricsButton")
        self.assertIsNotNone(undo_button)
        self.assertFalse(undo_button.property("enabled"))

        self._click(insert_button)
        self.assertTrue(undo_button.property("enabled"))
        self._click(undo_button)

        self.assertEqual(original, self.edit_session.draftLyrics)
        self.assertFalse(undo_button.property("enabled"))
        self.assertEqual(0, player_stub.property("playCallCount"))


class Phase595LyricsTimestampSourceContractTests(unittest.TestCase):
    def test_lyrics_page_uses_real_player_position_without_shortcut(self):
        page = (
            PROJECT_ROOT / "ui_next/qml/pages/LyricsCoverPage.qml"
        ).read_text(encoding="utf-8")
        editor = (
            PROJECT_ROOT / "ui_next/qml/components/LyricsDraftEditor.qml"
        ).read_text(encoding="utf-8")

        self.assertIn("audioPlayer: root.audioPlayer", page)
        self.assertIn('objectName: "insertCurrentTimestampButton"', editor)
        self.assertIn("audioPlayer.position", editor)
        self.assertIn("audioPlayer.timestampPrecision", editor)
        self.assertIn("editSession.insertLyricsTimestamp(", editor)
        self.assertNotIn("Shortcut {", editor)
        self.assertNotIn("Keys.on", editor)

    def test_editor_uses_one_current_lyrics_pane_and_compact_actions(self):
        page = (
            PROJECT_ROOT / "ui_next/qml/pages/LyricsCoverPage.qml"
        ).read_text(encoding="utf-8")
        editor = (
            PROJECT_ROOT / "ui_next/qml/components/LyricsDraftEditor.qml"
        ).read_text(encoding="utf-8")
        current_file = (
            PROJECT_ROOT / "ui_next/qml/components/CurrentFileBar.qml"
        ).read_text(encoding="utf-8")
        export_dialog = (
            PROJECT_ROOT / "ui_next/qml/components/EditExportDialog.qml"
        ).read_text(encoding="utf-8")

        for label in (
            'text: "导入 .lrc"',
            'text: "撤回"',
            'text: "插入时间点"',
            'text: "恢复原始"',
            'text: "当前歌词"',
        ):
            self.assertIn(label, editor)
        for removed in (
            "原始歌词预览",
            "当前草稿",
            "保存内存草稿",
            "恢复原始歌词",
            "清空草稿",
            "选择 .lrc 作为草稿来源",
            "导出到音频副本",
        ):
            self.assertNotIn(removed, editor)
            self.assertNotIn(removed, page)
        self.assertIn('objectName: "currentLyricsPane"', editor)
        self.assertNotIn('objectName: "originalLyricsPane"', editor)
        self.assertNotIn('text: "导出"', editor)
        self.assertIn('objectName: "exportEditorDraftsButton"', current_file)
        self.assertIn('text: "导出"', current_file)
        self.assertIn('objectName: "unifiedEditExportDialog"', export_dialog)
        self.assertIn('text: "LRC 歌词"', export_dialog)
        self.assertIn('"嵌入所选草稿并生成音频"', export_dialog)

    def test_settings_exposes_both_precision_choices_and_runtime_wiring(self):
        settings = (
            PROJECT_ROOT / "ui_next/qml/pages/SettingsPage.qml"
        ).read_text(encoding="utf-8")
        main = (PROJECT_ROOT / "main_qml.py").read_text(encoding="utf-8")

        self.assertIn('"lyricsTimestampPrecisionCombo"', settings)
        self.assertIn('"millisecond", "label": "千分之一秒"', settings)
        self.assertIn('"centisecond", "label": "百分之一秒"', settings)
        self.assertIn("setLyricsTimestampPrecision(value)", settings)
        self.assertIn("settings_view_model.settingsChanged.connect(", main)
        self.assertIn("setTimestampPrecision(", main)


if __name__ == "__main__":
    unittest.main()
