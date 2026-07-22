from __future__ import annotations

import os
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, QUrl
from PySide6.QtQml import QQmlComponent
from PySide6.QtQuick import QQuickItem, QQuickView
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from shiboken6 import getCppPointer

from ui_next.bridge.audio_player_viewmodel import AudioPlayerViewModel
from ui_next.bridge.audio_processing_session import ProcessingSessionViewModel
from ui_next.bridge.capabilities import CapabilityGate
from ui_next.bridge.cover_viewmodel import CoverViewModel
from ui_next.bridge.edit_session import EditSessionViewModel
from ui_next.bridge.file_session_viewmodel import FileSessionViewModel
from ui_next.bridge.lyrics_viewmodel import LyricsViewModel
from ui_next.bridge.metadata_viewmodel import MetadataViewModel


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Phase595EditorWorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        gate = CapabilityGate()
        self.file_session = FileSessionViewModel(gate)
        self.edit_session = EditSessionViewModel(gate)
        self.file_session.attach_edit_session(self.edit_session)
        self.file_session.currentFileChanged.connect(
            self.edit_session.beginCurrentFile
        )
        self.file_session.currentFileCleared.connect(self.edit_session.clear)
        self.audio_player = AudioPlayerViewModel(self.file_session, gate)
        self.processing_session = ProcessingSessionViewModel(
            self.file_session,
            self.audio_player,
            self.edit_session,
            capability_gate=gate,
        )

        self.view = QQuickView()
        context = self.view.rootContext()
        for name, value in (
            ("fileSessionViewModel", self.file_session),
            ("editSessionViewModel", self.edit_session),
            ("audioPlayerViewModel", self.audio_player),
            ("processingSessionViewModel", self.processing_session),
            ("metadataViewModel", MetadataViewModel()),
            ("lyricsViewModel", LyricsViewModel()),
            ("coverViewModel", CoverViewModel()),
        ):
            context.setContextProperty(name, value)

        self.component = QQmlComponent(self.view.engine())
        self.component.setData(
            b'''import QtQuick
import "ui_next/qml/components"

Item {
    id: host
    width: 1100
    height: 760
    property string pageKey: "fileInfo"
    property string fileBarMode: "fixed"
    property bool fileBarExpanded: false

    QtObject {
        id: settingsStub
        property string editorFileBarMode: host.fileBarMode
    }

    AudioEditorWorkspace {
        objectName: "workspaceUnderTest"
        anchors.fill: parent
        currentEditorPageKey: host.pageKey
        fileSession: fileSessionViewModel
        audioPlayer: audioPlayerViewModel
        editSession: editSessionViewModel
        processingSession: processingSessionViewModel
        settings: settingsStub
        floatingFileBarExpanded: host.fileBarExpanded
    }
}
''',
            QUrl.fromLocalFile(
                str(PROJECT_ROOT / "phase595_editor_workspace_probe.qml")
            ),
        )
        self.container = self.component.create()
        self.assertIsNotNone(self.container, self.component.errors())
        self.assertIsInstance(self.container, QQuickItem)
        self.container.setParentItem(self.view.contentItem())
        self.view.setWidth(1100)
        self.view.setHeight(760)
        self.view.show()
        self.app.processEvents()

    def tearDown(self):
        self.view.close()
        self.container.deleteLater()
        self.component.deleteLater()
        self.view.deleteLater()
        self.processing_session.shutdown()
        self.file_session.shutdown()
        self.audio_player.shutdown()
        self.app.processEvents()

    def _source(self, relative_path: str) -> str:
        return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")

    def _child(self, object_name: str) -> QObject:
        child = self.container.findChild(QObject, object_name)
        self.assertIsNotNone(child, object_name)
        return child

    def _wait_until(self, predicate, timeout=1.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.processEvents()
            if predicate():
                return True
            QTest.qWait(20)
        self.app.processEvents()
        return bool(predicate())

    def test_production_workspace_uses_common_file_bar_and_real_page_stack(self):
        stack = self._source("ui_next/qml/components/WorkspaceStack.qml")
        workspace = self._source(
            "ui_next/qml/components/AudioEditorWorkspace.qml"
        )

        self.assertIn("AudioEditorWorkspace {", stack)
        self.assertNotIn("AudioEditorPage {", stack)
        self.assertEqual(1, workspace.count("CurrentFileBar {"))
        self.assertEqual(1, workspace.count("MetadataPage {"))
        self.assertEqual(1, workspace.count("LyricsCoverPage {"))
        self.assertEqual(1, workspace.count("AudioProcessingPage {"))
        self.assertIn("property var settings: null", workspace)
        self.assertIn('currentFileBarMode === "floating"', workspace)
        self.assertIn("floatingMode: root.floatingFileBar", workspace)
        self.assertIn("clip: true", workspace)
        self.assertIn("-height - root.theme.spacing", workspace)
        self.assertIn(
            "onCollapseRequested: root.floatingFileBarCollapseRequested()",
            workspace,
        )
        for retired_component in (
            "EditorFileBrowser {",
            "WaveformPlaceholder {",
            "PlayerBar {",
            "TabPill",
        ):
            self.assertNotIn(retired_component, workspace)

    def test_page_instances_and_common_file_bar_survive_navigation(self):
        names = (
            "audioEditorCurrentFileCard",
            "editorPageStack",
            "fileInfoPage",
            "lyricsPage",
            "audioProcessingPage",
        )
        pointers = {
            name: getCppPointer(self._child(name))[0] for name in names
        }
        current_file_bar = self._child("audioEditorCurrentFileCard")
        self.container.setProperty("fileBarMode", "floating")
        self.container.setProperty("fileBarExpanded", True)
        QTest.qWait(180)

        for page_key in ("lyrics", "audioProcessing", "fileInfo"):
            self.container.setProperty("pageKey", page_key)
            self.app.processEvents()
            for name, pointer in pointers.items():
                self.assertEqual(pointer, getCppPointer(self._child(name))[0])
            self.assertTrue(current_file_bar.property("expanded"))

        for retired_object in (
            "audioEditorFileBrowser",
            "audioEditorWaveformCard",
            "audioEditorTabsCard",
            "audioEditorPlayerCard",
        ):
            self.assertIsNone(self.container.findChild(QObject, retired_object))

    def test_fixed_layout_is_preserved_and_floating_layout_overlays_page_stack(self):
        workspace = self._child("workspaceUnderTest")
        stack = self._child("editorPageStack")
        current_file_bar = self._child("audioEditorCurrentFileCard")

        self.assertFalse(current_file_bar.property("floatingMode"))
        self.assertAlmostEqual(0.0, float(current_file_bar.property("y")), delta=1.0)
        self.assertGreater(float(stack.property("y")), float(current_file_bar.property("height")))

        self.container.setProperty("fileBarMode", "floating")
        self.assertTrue(
            self._wait_until(
                lambda: (
                    float(current_file_bar.property("y"))
                    + float(current_file_bar.property("height"))
                    <= 0.0
                )
            )
        )

        self.assertTrue(current_file_bar.property("floatingMode"))
        self.assertFalse(current_file_bar.property("expanded"))
        self.assertFalse(current_file_bar.property("enabled"))
        self.assertAlmostEqual(
            0.0,
            float(current_file_bar.property("opacity")),
            delta=0.05,
        )
        self.assertAlmostEqual(0.0, float(stack.property("y")), delta=1.0)
        self.assertAlmostEqual(
            float(workspace.property("height")),
            float(stack.property("height")),
            delta=1.0,
        )
        self.assertLessEqual(
            float(current_file_bar.property("y"))
                + float(current_file_bar.property("height")),
            0.0,
        )

        self.container.setProperty("fileBarExpanded", True)
        QTest.qWait(220)
        self.app.processEvents()

        self.assertTrue(current_file_bar.property("expanded"))
        self.assertTrue(current_file_bar.property("enabled"))
        self.assertAlmostEqual(
            1.0,
            float(current_file_bar.property("opacity")),
            delta=0.05,
        )
        self.assertAlmostEqual(0.0, float(current_file_bar.property("y")), delta=1.0)
        self.assertAlmostEqual(0.0, float(stack.property("y")), delta=1.0)
        self.assertAlmostEqual(
            float(workspace.property("height")),
            float(stack.property("height")),
            delta=1.0,
        )

    def test_workspace_drop_area_follows_workspace_activity(self):
        workspace = self._child("workspaceUnderTest")
        drop_area = self._child("audioEditorDropArea")
        self.assertTrue(drop_area.property("enabled"))

        workspace.setProperty("pageActive", False)
        self.app.processEvents()
        self.assertFalse(drop_area.property("enabled"))

    def test_current_file_bar_owns_editor_file_actions_and_dirty_summary(self):
        current_file = self._source(
            "ui_next/qml/components/CurrentFileBar.qml"
        )
        metadata = self._source("ui_next/qml/pages/MetadataPage.qml")
        lyrics = self._source("ui_next/qml/pages/LyricsCoverPage.qml")

        for object_name in (
            "currentFileBarExpandedContent",
            "collapseCurrentFileBarButton",
            "currentEditCoverThumbnail",
            "editorPlaybackMatchBadge",
            "metadataDirtyBadge",
            "coverDirtyBadge",
            "lyricsDirtyBadge",
            "importEditorAudioButton",
            "openEditorFileLocationButton",
            "exportEditorDraftsButton",
        ):
            self.assertIn(f'objectName: "{object_name}"', current_file)

        self.assertIn('chooseAudioFile("audio_editor")', current_file)
        self.assertIn('openUnifiedExportDialog("auto")', current_file)
        self.assertIn("playbackMatchesEditorFile", current_file)
        self.assertNotIn('objectName: "loadEditorFileInPlayerButton"', current_file)
        self.assertNotIn('text: "载入播放器"', current_file)
        self.assertIn("property bool floatingMode: false", current_file)
        self.assertIn("property bool expanded: false", current_file)
        self.assertIn("signal collapseRequested()", current_file)
        self.assertNotIn('objectName: "currentFileBarCollapsedContent"', current_file)
        self.assertNotIn('objectName: "expandCurrentFileBarButton"', current_file)

        sub_navigation = self._source(
            "ui_next/qml/components/WorkspaceSubNavigation.qml"
        )
        self.assertIn('objectName: "toggleEditorFileBarButton"', sub_navigation)
        self.assertIn('"展开公共文件栏"', sub_navigation)
        self.assertIn('"收起公共文件栏"', sub_navigation)
        self.assertLess(
            sub_navigation.index("Layout.fillWidth: true"),
            sub_navigation.index('objectName: "toggleEditorFileBarButton"'),
        )

        app_shell = self._source("ui_next/qml/AppShell.qml")
        self.assertIn("property bool editorFileBarExpanded: false", app_shell)
        self.assertIn("onEditorFileBarToggleRequested:", app_shell)
        self.assertIn("onEditorFileBarCollapseRequested:", app_shell)

        for page_source in (metadata, lyrics):
            self.assertNotIn("chooseAudioFile(", page_source)
            self.assertNotIn("reloadCurrentFile()", page_source)
            self.assertNotIn("clearCurrentFile()", page_source)


if __name__ == "__main__":
    unittest.main()
