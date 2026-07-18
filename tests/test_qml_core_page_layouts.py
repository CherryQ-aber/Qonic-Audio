import os
import unittest
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, QPointF, QUrl
from PySide6.QtQml import QQmlComponent
from PySide6.QtQuick import QQuickItem, QQuickView
from PySide6.QtWidgets import QApplication

from ui_next.bridge.audio_player_viewmodel import AudioPlayerViewModel
from ui_next.bridge.audio_processing_session import ProcessingSessionViewModel
from ui_next.bridge.capabilities import CapabilityGate
from ui_next.bridge.cover_viewmodel import CoverViewModel
from ui_next.bridge.edit_session import EditSessionViewModel
from ui_next.bridge.file_session_viewmodel import FileSessionViewModel
from ui_next.bridge.lyrics_viewmodel import LyricsViewModel
from ui_next.bridge.metadata_viewmodel import MetadataViewModel
from ui_next.bridge.settings_viewmodel import SettingsViewModel


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class QmlCorePageLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        gate = CapabilityGate()
        file_session = FileSessionViewModel(gate)
        edit_session = EditSessionViewModel(gate)
        file_session.attach_edit_session(edit_session)
        file_session.currentFileChanged.connect(edit_session.beginCurrentFile)
        file_session.currentFileCleared.connect(edit_session.clear)
        audio_player = AudioPlayerViewModel(file_session, gate)
        processing_session = ProcessingSessionViewModel(
            file_session,
            audio_player,
            edit_session,
            capability_gate=gate,
        )
        self._bridge_objects = (
            file_session,
            edit_session,
            audio_player,
            processing_session,
        )
        self.context = {
            "fileSessionViewModel": file_session,
            "editSessionViewModel": edit_session,
            "audioPlayerViewModel": audio_player,
            "processingSessionViewModel": processing_session,
            "metadataViewModel": MetadataViewModel(),
            "lyricsViewModel": LyricsViewModel(),
            "coverViewModel": CoverViewModel(),
            "settingsViewModel": SettingsViewModel(),
        }

    def tearDown(self):
        file_session, _edit, audio_player, processing_session = (
            self._bridge_objects
        )
        processing_session.shutdown()
        file_session.shutdown()
        audio_player.shutdown()

    def _source(self, relative_path: str) -> str:
        return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")

    def _create_page(
        self,
        page_type: str,
        scroll_name: str,
        content_name: str,
        *,
        width: int = 1018,
        height: int = 892,
    ):
        editor_property = ""
        if page_type == "AudioProcessingPage":
            editor_property = """
        processingSession: processingSessionViewModel
"""
        elif page_type in {"MetadataPage", "LyricsCoverPage"}:
            editor_property = """
        audioPlayer: audioPlayerViewModel
        editSession: editSessionViewModel
"""
        source = f'''import QtQuick
import "ui_next/qml/pages"

Item {{
    width: {width}
    height: {height}

    {page_type} {{
        objectName: "pageUnderTest"
        anchors.fill: parent
        {editor_property}
    }}
}}
'''.encode("utf-8")
        view = QQuickView()
        for key, value in self.context.items():
            view.rootContext().setContextProperty(key, value)
        component = QQmlComponent(view.engine())
        component.setData(source, QUrl.fromLocalFile(str(PROJECT_ROOT / f"{page_type}_layout_probe.qml")))
        container = component.create()
        self.assertIsNotNone(container, component.errors())
        self.assertIsInstance(container, QQuickItem)
        container.setParentItem(view.contentItem())
        view.setWidth(width)
        view.setHeight(height)
        view.show()
        self.app.processEvents()

        page = container.findChild(QObject, "pageUnderTest")
        scroll = container.findChild(QObject, scroll_name)
        content = container.findChild(QObject, content_name)
        self.assertIsNotNone(page)
        self.assertIsNotNone(scroll)
        self.assertIsNotNone(content)
        return view, component, container, scroll, content

    def _dispose(self, view, component, container):
        view.close()
        container.deleteLater()
        component.deleteLater()
        view.deleteLater()
        self.app.processEvents()

    def _rect(self, item: QQuickItem, root: QQuickItem):
        point = item.mapToItem(root, QPointF(0, 0))
        return (point.x(), point.y(), item.width(), item.height())

    def _assert_no_intersection(self, first: QQuickItem, second: QQuickItem, root: QQuickItem):
        ax, ay, aw, ah = self._rect(first, root)
        bx, by, bw, bh = self._rect(second, root)
        intersects = ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah
        self.assertFalse(intersects, (ax, ay, aw, ah, bx, by, bw, bh))

    def _assert_viewport_width(
        self,
        scroll: QObject,
        content: QQuickItem,
        *,
        expect_vertical_overflow: bool = True,
    ):
        self.assertGreater(content.width(), 100)
        self.assertLessEqual(content.width(), float(scroll.property("width")) + 0.5)
        self.assertLessEqual(
            float(scroll.property("contentWidth")), float(scroll.property("width")) + 0.5
        )
        if expect_vertical_overflow:
            self.assertGreater(
                float(scroll.property("contentHeight")),
                float(scroll.property("height")),
            )

    def test_audio_processing_page_owns_its_scroll_without_retired_workspace_cards(self):
        workspace = self._source(
            "ui_next/qml/components/AudioEditorWorkspace.qml"
        )
        processing = self._source("ui_next/qml/pages/AudioProcessingPage.qml")
        player = self._source("ui_next/qml/components/GlobalPlayerDock.qml")
        timeline = self._source("ui_next/qml/components/PlayerTimeline.qml")
        device = self._source(
            "ui_next/qml/components/PlaybackDeviceControl.qml"
        )
        pitch = self._source("ui_next/qml/components/PitchShiftCard.qml")
        current_file = self._source("ui_next/qml/components/CurrentFileBar.qml")
        self.assertEqual(1, processing.count("Flickable {"))
        self.assertIn("AudioProcessingPage", workspace)
        self.assertIn("DropArea {", workspace)
        self.assertIn("handleDroppedUrls(drop.urls)", workspace)
        self.assertNotIn("EditorFileBrowser", workspace)
        self.assertNotIn("WaveformPlaceholder", workspace)
        self.assertNotIn("TabPill", workspace)
        self.assertIn("PitchShiftCard", processing)
        self.assertNotIn("PreviewCachePanel", processing)
        self.assertNotIn("ExportResultPanel", processing)
        self.assertNotIn("PlayerBar {", workspace)
        self.assertIn("Layout.minimumWidth: 0", player)
        self.assertIn("refreshOutputDevices()", device)
        self.assertIn("selectOutputDevice", device)
        self.assertIn("onPressedChanged", timeline)
        self.assertIn("载入播放器", current_file)
        self.assertIn("playbackMatchesEditorFile", current_file)
        self.assertNotIn(
            "mock",
            (
                workspace
                + processing
                + player
                + timeline
                + device
                + current_file
            ).lower(),
        )
        self.assertIn("Flow {", pitch)

        view, component, container, scroll, content = self._create_page(
            "AudioProcessingPage",
            "audioProcessingPageScroll",
            "audioProcessingPageContent",
            height=420,
        )
        try:
            self._assert_viewport_width(scroll, content)
            self.assertIsNotNone(
                container.findChild(QObject, "audioEditorPitchCard")
            )
        finally:
            self._dispose(view, component, container)

    def test_metadata_cards_do_not_overlap_and_actions_follow_content(self):
        source = self._source("ui_next/qml/pages/MetadataPage.qml")
        form = self._source("ui_next/qml/components/MetadataForm.qml")
        cover = self._source("ui_next/qml/components/CoverDraftEditor.qml")
        self.assertIn("pageScroll.width >= 880 ? 3", source)
        self.assertIn("pageScroll.width >= 660 ? 2 : 1", source)
        self.assertIn("columns: width >= 420 ? 2 : 1", form)
        self.assertIn("Flow {", cover)
        self.assertEqual(1, cover.count("PreviewPane {"))
        self.assertNotIn('objectName: "metadataStatusCard"', source)

        view, component, container, scroll, content = self._create_page(
            "MetadataPage", "metadataPageScroll", "metadataPageContent"
        )
        try:
            self._assert_viewport_width(
                scroll,
                content,
                expect_vertical_overflow=False,
            )
            cover_editor = container.findChild(QObject, "metadataCoverEditor")
            metadata_form = container.findChild(QObject, "metadataTagSummaryCard")
            base = container.findChild(QObject, "metadataBaseInfoCard")
            actions = container.findChild(QObject, "metadataEditActionsCard")
            self.assertTrue(all((cover_editor, metadata_form, base, actions)))
            self.assertEqual(3, int(container.findChild(
                QObject, "pageUnderTest"
            ).property("workspaceColumns")))
            self._assert_no_intersection(cover_editor, metadata_form, container)
            self._assert_no_intersection(metadata_form, base, container)
            self.assertEqual(
                round(self._rect(cover_editor, container)[1], 1),
                round(self._rect(metadata_form, container)[1], 1),
            )
            self.assertEqual(
                round(self._rect(metadata_form, container)[1], 1),
                round(self._rect(base, container)[1], 1),
            )
            base_rect = self._rect(base, container)
            cover_rect = self._rect(cover_editor, container)
            form_rect = self._rect(metadata_form, container)
            actions_rect = self._rect(actions, container)
            self.assertGreater(form_rect[2], cover_rect[2])
            self.assertGreaterEqual(
                actions_rect[1],
                max(
                    cover_rect[1] + cover_rect[3],
                    form_rect[1] + form_rect[3],
                    base_rect[1] + base_rect[3],
                ),
            )
        finally:
            self._dispose(view, component, container)

    def test_lyrics_page_uses_wrapping_status_and_has_no_cover_editor(self):
        source = self._source("ui_next/qml/pages/LyricsCoverPage.qml")
        self.assertIn('objectName: "lyricsWorkspaceGrid"', source)
        self.assertNotIn("LyricsSourceBadge {", source)
        self.assertNotIn('objectName: "lyricsCoverStatusCard"', source)
        self.assertNotIn("CoverDraftEditor {", source)
        long_lyrics = "\n".join(
            f"[{index // 60:02d}:{index % 60:02d}.000] line {index}"
            for index in range(260)
        )
        edit_session = self.context["editSessionViewModel"]
        edit_session.beginCurrentFile("C:/lyrics-scroll-test.flac", 1)
        edit_session.loadLyricsResult(
            {
                "ok": True,
                "path": "C:/lyrics-scroll-test.flac",
                "session_generation": 1,
                "has_lyrics": True,
                "lyrics_text": long_lyrics,
            }
        )

        view, component, container, scroll, content = self._create_page(
            "LyricsCoverPage", "lyricsCoverPageScroll", "lyricsCoverPageContent"
        )
        try:
            self._assert_viewport_width(
                scroll,
                content,
                expect_vertical_overflow=False,
            )
            lyrics = container.findChild(QObject, "lyricsCoverLyricsPreview")
            actions = container.findChild(QObject, "lyricsCoverDraftEditor")
            cover = container.findChild(QObject, "lyricsCoverCoverPreview")
            self.assertTrue(all((lyrics, actions)))
            self.assertIsNone(cover)
            for scroll_name in ("originalLyricsScrollView", "lyricsDraftScrollView"):
                lyrics_scroll = container.findChild(QObject, scroll_name)
                self.assertIsNotNone(lyrics_scroll)
                self.assertGreater(
                    float(lyrics_scroll.property("contentHeight")),
                    float(lyrics_scroll.property("height")),
                )
            page_scroll_bar = container.findChild(
                QQuickItem, "lyricsCoverPageVerticalScrollBar"
            )
            original_scroll_bar = container.findChild(
                QQuickItem, "originalLyricsVerticalScrollBar"
            )
            draft_scroll_bar = container.findChild(
                QQuickItem, "draftLyricsVerticalScrollBar"
            )
            self.assertTrue(
                all((page_scroll_bar, original_scroll_bar, draft_scroll_bar))
            )
            page_bar_left = self._rect(page_scroll_bar, container)[0]
            for scroll_name, inner_scroll_bar in (
                ("originalLyricsScrollView", original_scroll_bar),
                ("lyricsDraftScrollView", draft_scroll_bar),
            ):
                lyrics_scroll = container.findChild(QQuickItem, scroll_name)
                self.assertIsNotNone(lyrics_scroll)
                scroll_rect = self._rect(lyrics_scroll, container)
                inner_rect = self._rect(inner_scroll_bar, container)
                self.assertAlmostEqual(
                    inner_rect[0] + inner_rect[2],
                    scroll_rect[0] + scroll_rect[2] - 2,
                    delta=0.5,
                )
                self.assertGreaterEqual(
                    inner_rect[3],
                    scroll_rect[3] - 4.5,
                )
                self.assertLessEqual(
                    inner_rect[0] + inner_rect[2] + 1,
                    page_bar_left,
                )
            lyrics_rect = self._rect(lyrics, container)
            actions_rect = self._rect(actions, container)
            self.assertAlmostEqual(actions_rect[1], lyrics_rect[1], delta=0.5)
            self.assertLessEqual(
                lyrics_rect[0] + lyrics_rect[2],
                actions_rect[0] + 0.5,
            )
        finally:
            self._dispose(view, component, container)

    def test_settings_path_cards_and_actions_remain_inside_the_scroll_viewport(self):
        source = self._source("ui_next/qml/pages/SettingsPage.qml")
        path_field = self._source("ui_next/qml/components/PathField.qml")
        self.assertIn("columns: root.width >= 620 ? 3 : 1", path_field)
        self.assertIn("wrapMode: Text.WordWrap", path_field)
        self.assertIn("text: label", source)
        self.assertIn('objectName: "settingsSectionsGrid"', source)
        self.assertIn('objectName: "editorFileBarModeCombo"', source)
        self.assertIn('{"value": "fixed", "label": "固定"}', source)
        self.assertIn('{"value": "floating", "label": "悬浮（可收起）"}', source)
        self.assertNotIn('objectName: "settingsDraftActionsCard"', source)

        view, component, container, scroll, content = self._create_page(
            "SettingsPage", "settingsPageScroll", "settingsPageContent"
        )
        try:
            self._assert_viewport_width(scroll, content)
            header = container.findChild(QObject, "settingsHeaderCard")
            draft_actions = container.findChild(QObject, "settingsDraftActions")
            grid = container.findChild(QObject, "settingsSectionsGrid")
            sections = [
                container.findChild(QObject, name)
                for name in (
                    "settingsPathSection",
                    "settingsAutoConvertSection",
                    "settingsLyricsSection",
                    "settingsPlaybackSection",
                    "settingsThemeSection",
                    "settingsLogCacheSection",
                )
            ]
            self.assertTrue(all((header, draft_actions, grid, *sections)))
            self.assertEqual(2, int(grid.property("columns")))
            header_rect = self._rect(header, container)
            actions_rect = self._rect(draft_actions, container)
            self.assertGreaterEqual(actions_rect[1], header_rect[1] - 0.5)
            self.assertLessEqual(
                actions_rect[1] + actions_rect[3],
                header_rect[1] + header_rect[3] + 0.5,
            )
            for left, right in zip(sections[0::2], sections[1::2]):
                self.assertAlmostEqual(
                    self._rect(left, container)[1],
                    self._rect(right, container)[1],
                    delta=0.5,
                )
                self._assert_no_intersection(left, right, container)
            for action in container.findChildren(QObject, "settingsActionButton"):
                self.assertTrue(str(action.property("text")).strip())
        finally:
            self._dispose(view, component, container)


if __name__ == "__main__":
    unittest.main()
