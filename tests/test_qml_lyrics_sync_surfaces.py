import os
import unittest
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, QPointF, QUrl
from PySide6.QtQml import QQmlComponent
from PySide6.QtQuick import QQuickItem, QQuickView
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class LyricsSyncQmlSurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _create(self, source: bytes, name: str, width: int, height: int):
        view = QQuickView()
        component = QQmlComponent(view.engine())
        component.setData(
            source,
            QUrl.fromLocalFile(str(PROJECT_ROOT / name)),
        )
        container = component.create()
        self.assertIsNotNone(container, component.errors())
        self.assertIsInstance(container, QQuickItem)
        container.setParentItem(view.contentItem())
        view.setWidth(width)
        view.setHeight(height)
        view.show()
        QTest.qWait(30)
        self.app.processEvents()
        return view, component, container

    def _dispose(self, view, component, container):
        view.close()
        container.deleteLater()
        component.deleteLater()
        view.deleteLater()
        self.app.processEvents()

    def test_preview_tracks_current_line_only_when_follow_is_enabled(self):
        source = '''import QtQuick
import "ui_next/qml/components"

Item {
    id: host
    objectName: "lyricsSyncHost"
    width: 520
    height: 300
    property int activeLine: -1
    property bool followLine: true
    property var lyricLines: []

    Component.onCompleted: {
        var items = []
        for (var index = 0; index < 36; ++index) {
            items.push({
                "index": index + 1,
                "time": "00:" + index,
                "text": "line " + index,
                "translation": "",
                "hasTimestamp": true
            })
        }
        lyricLines = items
    }

    LyricsPreviewList {
        anchors.fill: parent
        lines: host.lyricLines
        currentLineIndex: host.activeLine
        followCurrentLine: host.followLine
        onFollowCurrentLineRequested: function(enabled) {
            host.followLine = enabled
        }
    }
}
'''.encode("utf-8")
        view, component, container = self._create(
            source,
            "lyrics_sync_preview_probe.qml",
            520,
            300,
        )
        try:
            list_view = container.findChild(
                QQuickItem,
                "lyricsPreviewListView",
            )
            toggle = container.findChild(QObject, "lyricsFollowToggle")
            self.assertIsNotNone(list_view)
            self.assertIsNotNone(toggle)
            self.assertEqual("跟随滚动：开", toggle.property("text"))

            container.setProperty("activeLine", 24)
            QTest.qWait(30)
            self.app.processEvents()
            self.assertGreater(float(list_view.property("contentY")), 0)

            container.setProperty("followLine", False)
            list_view.setProperty("contentY", 0.0)
            container.setProperty("activeLine", 30)
            QTest.qWait(30)
            self.app.processEvents()
            self.assertAlmostEqual(
                0.0,
                float(list_view.property("contentY")),
                delta=0.5,
            )
            self.assertEqual("跟随滚动：关", toggle.property("text"))
        finally:
            self._dispose(view, component, container)

    def test_global_strip_stays_single_line_and_compact(self):
        source = '''import QtQuick
import "ui_next/qml/components"

Item {
    width: 1200
    height: 80

    QtObject {
        id: syncStub
        objectName: "syncStub"
        property int currentLineIndex: 2
        property string currentLineTime: "00:12.429"
        property string currentLineText: "Right where? Right here"
        property string currentLineTranslation: "就在这里"
        property string nextLineText: "Next lyric line"
        property string nextLineTranslation: ""
    }

    GlobalLyricsStrip {
        id: strip
        objectName: "stripUnderTest"
        width: parent.width
        height: implicitHeight
        lyricsSync: syncStub
        compactMode: false
    }
}
'''.encode("utf-8")
        view, component, container = self._create(
            source,
            "global_lyrics_strip_probe.qml",
            1200,
            80,
        )
        try:
            strip = container.findChild(QQuickItem, "stripUnderTest")
            current = container.findChild(
                QQuickItem,
                "globalLyricsCurrentLine",
            )
            next_line = container.findChild(
                QObject,
                "globalLyricsNextLine",
            )
            self.assertTrue(all((strip, current, next_line)))
            self.assertLessEqual(strip.height(), 30)
            self.assertIn("Right where? Right here", current.property("text"))
            self.assertIn("就在这里", current.property("text"))
            self.assertTrue(next_line.property("visible"))
            self.assertEqual(1, int(current.property("maximumLineCount")))
            current_origin = current.mapToItem(strip, QPointF(0, 0))
            self.assertAlmostEqual(
                strip.width() / 2,
                current_origin.x() + current.width() / 2,
                delta=1.0,
            )
        finally:
            self._dispose(view, component, container)

    def test_global_dock_adds_only_one_compact_row_when_preview_is_allowed(self):
        source = '''import QtQuick
import "ui_next/qml/components"

Item {
    width: 1200
    height: 180

    QtObject {
        id: syncStub
        property bool availableForPlayback: true
        property int currentLineIndex: 1
        property string currentLineTime: "00:10.307"
        property string currentLineText: "Current lyric"
        property string currentLineTranslation: ""
        property string nextLineText: "Next lyric"
        property string nextLineTranslation: ""
    }

    GlobalPlayerDock {
        id: dock
        objectName: "dockUnderTest"
        width: parent.width
        height: requestedHeight
        lyricsSync: syncStub
        lyricsPreviewAllowed: true
        compactMode: false
    }
}
'''.encode("utf-8")
        view, component, container = self._create(
            source,
            "global_lyrics_dock_probe.qml",
            1200,
            180,
        )
        try:
            dock = container.findChild(QQuickItem, "dockUnderTest")
            preview = container.findChild(
                QQuickItem,
                "globalPlayerLyricsPreview",
            )
            self.assertTrue(all((dock, preview)))
            self.assertTrue(dock.property("lyricsPreviewVisible"))
            self.assertEqual(130, int(dock.property("requestedHeight")))
            self.assertLessEqual(preview.height(), 30)

            dock.setProperty("lyricsPreviewAllowed", False)
            QTest.qWait(20)
            self.app.processEvents()
            self.assertFalse(dock.property("lyricsPreviewVisible"))
            self.assertEqual(96, int(dock.property("requestedHeight")))
        finally:
            self._dispose(view, component, container)

    def test_current_draft_line_highlight_tracks_the_playback_range(self):
        source = '''import QtQuick
import "ui_next/qml/components"

Item {
    width: 800
    height: 520

    QtObject {
        id: editStub
        property bool hasSession: true
        property bool lyricsExporting: false
        property bool anyExporting: false
        property bool lyricsDirty: false
        property bool canUndoLyrics: false
        property bool canOverwriteCurrentLrc: false
        property string lyricsDraftStatusLabel: "原始歌词"
        property string draftLyrics: "Header\\n[00:01.000]Current\\n[00:02.000]Next\\n"
            + Array(80).join("Filler line\\n")
        property string statusMessage: ""
        property string unifiedExportMessage: ""
        property var lastLyricsExportResult: ({})
        property string lastLyricsExportMessage: ""
    }

    QtObject {
        id: syncStub
        objectName: "draftSyncStub"
        property bool availableForPlayback: true
        property int currentLineIndex: 1
        property int currentLineSourceStart: 7
        property int currentLineSourceEnd: 25
    }

    QtObject {
        id: playerStub
        property bool hasPlaybackSource: true
        property int position: 1000
        property string timestampPrecision: "millisecond"
    }

    LyricsDraftEditor {
        anchors.fill: parent
        editSession: editStub
        audioPlayer: playerStub
        lyricsSync: syncStub
    }
}
'''.encode("utf-8")
        view, component, container = self._create(
            source,
            "lyrics_draft_highlight_probe.qml",
            800,
            520,
        )
        try:
            text_area = container.findChild(QQuickItem, "lyricsDraftTextArea")
            scroll_view = container.findChild(
                QQuickItem,
                "lyricsDraftScrollView",
            )
            highlight = container.findChild(
                QQuickItem,
                "draftCurrentLineHighlight",
            )
            sync_stub = container.findChild(QObject, "draftSyncStub")
            self.assertTrue(
                all((text_area, scroll_view, highlight, sync_stub))
            )
            self.assertTrue(highlight.property("visible"))
            self.assertGreater(highlight.height(), 0)
            highlighted_y = highlight.y()

            flickable = scroll_view.property("contentItem")
            self.assertIsInstance(flickable, QQuickItem)
            flickable.setProperty("contentY", 80.0)
            QTest.qWait(20)
            self.app.processEvents()
            actual_content_y = float(flickable.property("contentY"))
            self.assertGreater(actual_content_y, 0)
            self.assertAlmostEqual(
                highlighted_y - actual_content_y,
                highlight.y(),
                delta=1.0,
            )

            sync_stub.setProperty("currentLineSourceStart", 0)
            sync_stub.setProperty("currentLineSourceEnd", 6)
            QTest.qWait(20)
            self.app.processEvents()
            self.assertLess(highlight.y(), highlighted_y)

            sync_stub.setProperty("availableForPlayback", False)
            self.app.processEvents()
            self.assertFalse(highlight.property("visible"))
        finally:
            self._dispose(view, component, container)

    def test_shell_keeps_global_preview_available_on_lyrics_editor_page(self):
        shell = (
            PROJECT_ROOT / "ui_next/qml/AppShell.qml"
        ).read_text(encoding="utf-8")
        dock = (
            PROJECT_ROOT / "ui_next/qml/components/GlobalPlayerDock.qml"
        ).read_text(encoding="utf-8")
        main = (PROJECT_ROOT / "main_qml.py").read_text(encoding="utf-8")

        self.assertIn("lyricsPreviewAllowed: true", shell)
        self.assertNotIn("lyricsPreviewAllowed: !(", shell)
        self.assertIn("lyricsSync: lyricsSyncViewModel", shell)
        self.assertIn("GlobalLyricsStrip {", dock)
        self.assertIn("lyricsPreviewExtraHeight", dock)
        self.assertIn('"lyricsSyncViewModel"', main)


if __name__ == "__main__":
    unittest.main()
