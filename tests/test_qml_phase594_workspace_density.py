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
from ui_next.bridge.auto_convert_viewmodel import AutoConvertViewModel
from ui_next.bridge.capabilities import CapabilityGate
from ui_next.bridge.cover_viewmodel import CoverViewModel
from ui_next.bridge.edit_session import EditSessionViewModel
from ui_next.bridge.file_session_viewmodel import FileSessionViewModel
from ui_next.bridge.lyrics_viewmodel import LyricsViewModel
from ui_next.bridge.metadata_viewmodel import MetadataViewModel
from ui_next.bridge.settings_viewmodel import SettingsViewModel
from ui_next.bridge.task_queue_model import TaskQueueModel


PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Phase 5.9.5 keeps FolderBrowserPane hidden and lets the workspace fill the
# main area.  These are the measured page viewports after the 58 px top bar,
# 44 px sub-navigation, 82/96 px player dock and 12 px workspace margins.
VIEWPORT_CASES = (
    ("1080x680", 1056, 472),
    ("1280x720", 1256, 512),
    ("1440x900", 1416, 678),
    ("1536x982", 1512, 760),
    ("1900x1200", 1876, 978),
    ("1920x1080", 1896, 858),
)


class Phase594WorkspaceDensityTests(unittest.TestCase):
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
        self.queue_model = TaskQueueModel(capability_gate=gate)
        self.auto_convert = AutoConvertViewModel(
            self.queue_model,
            capability_gate=gate,
        )
        self.context = {
            "fileSessionViewModel": self.file_session,
            "editSessionViewModel": self.edit_session,
            "audioPlayerViewModel": self.audio_player,
            "processingSessionViewModel": self.processing_session,
            "metadataViewModel": MetadataViewModel(),
            "lyricsViewModel": LyricsViewModel(),
            "coverViewModel": CoverViewModel(),
            "settingsViewModel": SettingsViewModel(),
            "taskQueueModel": self.queue_model,
            "autoConvertViewModel": self.auto_convert,
        }

        long_lyrics = "\n".join(
            f"[{index // 60:02d}:{index % 60:02d}.000] line {index}"
            for index in range(260)
        )
        self.edit_session.beginCurrentFile("C:/phase594-scroll-test.flac", 1)
        self.edit_session.loadLyricsResult(
            {
                "ok": True,
                "path": "C:/phase594-scroll-test.flac",
                "session_generation": 1,
                "has_lyrics": True,
                "lyrics_text": long_lyrics,
            }
        )

    def tearDown(self):
        self.auto_convert.shutdown()
        self.processing_session.shutdown()
        self.file_session.shutdown()
        self.audio_player.shutdown()
        self.queue_model.deleteLater()
        self.app.processEvents()

    def _create_page(
        self,
        page_type: str,
        width: int,
        height: int,
        properties: str = "",
        *,
        component_directory: str = "pages",
    ):
        source = f'''import QtQuick
import "ui_next/qml/{component_directory}"

Item {{
    width: {width}
    height: {height}

    {page_type} {{
        objectName: "pageUnderTest"
        anchors.fill: parent
        {properties}
    }}
}}
'''.encode("utf-8")
        view = QQuickView()
        for key, value in self.context.items():
            view.rootContext().setContextProperty(key, value)
        component = QQmlComponent(view.engine())
        component.setData(
            source,
            QUrl.fromLocalFile(
                str(PROJECT_ROOT / f"phase594_{page_type}_probe.qml")
            ),
        )
        container = component.create()
        self.assertIsNotNone(container, component.errors())
        self.assertIsInstance(container, QQuickItem)
        container.setParentItem(view.contentItem())
        view.setWidth(width)
        view.setHeight(height)
        view.show()
        self.app.processEvents()
        return view, component, container

    def _dispose(self, view, component, container):
        view.close()
        container.deleteLater()
        component.deleteLater()
        view.deleteLater()
        self.app.processEvents()

    def _rect(self, item: QQuickItem, root: QQuickItem):
        point = item.mapToItem(root, QPointF(0, 0))
        return point.x(), point.y(), item.width(), item.height()

    def _assert_horizontal_fit(self, item: QQuickItem, root: QQuickItem):
        x, _y, width, _height = self._rect(item, root)
        self.assertGreaterEqual(x, -0.5)
        self.assertLessEqual(x + width, root.width() + 0.5)

    def _assert_no_intersection(
        self,
        first: QQuickItem,
        second: QQuickItem,
        root: QQuickItem,
    ):
        ax, ay, aw, ah = self._rect(first, root)
        bx, by, bw, bh = self._rect(second, root)
        intersects = (
            ax < bx + bw
            and bx < ax + aw
            and ay < by + bh
            and by < ay + ah
        )
        self.assertFalse(intersects, (ax, ay, aw, ah, bx, by, bw, bh))

    def test_auto_convert_queue_is_the_primary_area_at_required_sizes(self):
        for label, width, height in VIEWPORT_CASES:
            with self.subTest(window=label):
                view, component, container = self._create_page(
                    "AutoConvertPage",
                    width,
                    height,
                )
                try:
                    page = container.findChild(QQuickItem, "pageUnderTest")
                    entry = container.findChild(
                        QQuickItem, "autoConvertCompactEntryBar"
                    )
                    queue = container.findChild(
                        QQuickItem, "autoConvertPrimaryQueue"
                    )
                    scan = container.findChild(QQuickItem, "scanSummaryBar")
                    actions = container.findChild(
                        QQuickItem, "convertActionBar"
                    )
                    queue_scrollbar = container.findChild(
                        QQuickItem, "taskQueueVerticalScrollBar"
                    )
                    self.assertTrue(
                        all(
                            (
                                page,
                                entry,
                                queue,
                                scan,
                                actions,
                                queue_scrollbar,
                            )
                        )
                    )
                    self.assertGreaterEqual(queue.height(), height * 0.38)
                    self.assertGreater(queue.height(), entry.height())
                    self.assertGreater(queue.height(), actions.height())
                    for item in (entry, queue, scan, actions):
                        self._assert_horizontal_fit(item, page)
                    action_rect = self._rect(actions, page)
                    self.assertLessEqual(
                        action_rect[1] + action_rect[3],
                        page.height() + 0.5,
                    )
                finally:
                    self._dispose(view, component, container)

    def test_metadata_uses_two_then_three_columns_without_horizontal_overflow(self):
        expected_columns = {
            "1080x680": 3,
            "1280x720": 3,
            "1440x900": 3,
            "1536x982": 3,
            "1900x1200": 3,
            "1920x1080": 3,
        }
        properties = """
        audioPlayer: audioPlayerViewModel
        editSession: editSessionViewModel
"""
        for label, width, height in VIEWPORT_CASES:
            with self.subTest(window=label):
                view, component, container = self._create_page(
                    "MetadataPage",
                    width,
                    height,
                    properties,
                )
                try:
                    page = container.findChild(QQuickItem, "pageUnderTest")
                    cover = container.findChild(
                        QQuickItem, "metadataCoverEditor"
                    )
                    metadata = container.findChild(
                        QQuickItem, "metadataTagSummaryCard"
                    )
                    technical = container.findChild(
                        QQuickItem, "metadataBaseInfoCard"
                    )
                    self.assertTrue(all((page, cover, metadata, technical)))
                    self.assertEqual(
                        expected_columns[label],
                        int(page.property("workspaceColumns")),
                    )
                    for item in (cover, metadata, technical):
                        self._assert_horizontal_fit(item, page)
                    if expected_columns[label] == 2:
                        self.assertAlmostEqual(
                            self._rect(cover, page)[1],
                            self._rect(metadata, page)[1],
                            delta=0.5,
                        )
                        self.assertGreaterEqual(
                            self._rect(technical, page)[1],
                            max(
                                self._rect(cover, page)[1]
                                + self._rect(cover, page)[3],
                                self._rect(metadata, page)[1]
                                + self._rect(metadata, page)[3],
                            ),
                        )
                    else:
                        self.assertEqual(
                            1,
                            len(
                                {
                                    round(self._rect(item, page)[1], 1)
                                    for item in (cover, metadata, technical)
                                }
                            ),
                        )
                        self._assert_no_intersection(cover, metadata, page)
                        self._assert_no_intersection(
                            metadata, technical, page
                        )
                finally:
                    self._dispose(view, component, container)

    def test_lyrics_preview_and_current_editor_scrollbars_remain_accessible(self):
        properties = """
        audioPlayer: audioPlayerViewModel
        editSession: editSessionViewModel
"""
        for label, width, height in VIEWPORT_CASES:
            with self.subTest(window=label):
                view, component, container = self._create_page(
                    "LyricsCoverPage",
                    width,
                    height,
                    properties,
                )
                try:
                    page = container.findChild(QQuickItem, "pageUnderTest")
                    workspace = container.findChild(
                        QQuickItem, "lyricsWorkspaceGrid"
                    )
                    preview = container.findChild(
                        QQuickItem, "lyricsCoverLyricsPreview"
                    )
                    editor = container.findChild(
                        QQuickItem, "lyricsCoverDraftEditor"
                    )
                    current_pane = container.findChild(
                        QQuickItem, "currentLyricsPane"
                    )
                    page_scroll = container.findChild(
                        QQuickItem, "lyricsCoverPageScroll"
                    )
                    page_bar = container.findChild(
                        QQuickItem, "lyricsCoverPageVerticalScrollBar"
                    )
                    preview_scroll = container.findChild(
                        QQuickItem, "lyricsPreviewListView"
                    )
                    preview_bar = container.findChild(
                        QQuickItem, "lyricsPreviewVerticalScrollBar"
                    )
                    draft_scroll = container.findChild(
                        QQuickItem, "lyricsDraftScrollView"
                    )
                    draft_bar = container.findChild(
                        QQuickItem, "draftLyricsVerticalScrollBar"
                    )
                    self.assertTrue(
                        all(
                            (
                                page,
                                workspace,
                                preview,
                                editor,
                                current_pane,
                                page_scroll,
                                page_bar,
                                preview_scroll,
                                preview_bar,
                                draft_scroll,
                                draft_bar,
                            )
                        )
                    )
                    self.assertIsNone(
                        container.findChild(QQuickItem, "originalLyricsPane")
                    )
                    self.assertIsNone(
                        container.findChild(
                            QQuickItem, "originalLyricsScrollView"
                        )
                    )
                    self.assertEqual(2, int(workspace.property("columns")))
                    self.assertGreater(workspace.height(), height * 0.60)
                    if height >= 575:
                        self.assertLessEqual(
                            float(page_scroll.property("contentHeight")),
                            page_scroll.height() + 0.5,
                        )
                    else:
                        self.assertGreater(
                            float(page_scroll.property("contentHeight")),
                            page_scroll.height(),
                        )
                    self.assertAlmostEqual(
                        self._rect(preview, page)[1],
                        self._rect(editor, page)[1],
                        delta=0.5,
                    )
                    self._assert_no_intersection(preview, editor, page)
                    self._assert_horizontal_fit(workspace, page)
                    preview_scroll_rect = self._rect(preview_scroll, page)
                    preview_bar_rect = self._rect(preview_bar, page)
                    preview_right = (
                        self._rect(preview, page)[0]
                        + self._rect(preview, page)[2]
                    )
                    self.assertLessEqual(
                        preview_bar_rect[0] + preview_bar_rect[2],
                        preview_right,
                    )
                    self.assertGreaterEqual(
                        preview_bar_rect[0] + preview_bar_rect[2],
                        preview_right - 24,
                    )
                    self.assertLessEqual(
                        preview_scroll_rect[0] + preview_scroll_rect[2] + 1,
                        preview_bar_rect[0],
                    )
                    scroll_rect = self._rect(draft_scroll, page)
                    bar_rect = self._rect(draft_bar, page)
                    self.assertGreater(
                        float(draft_scroll.property("contentHeight")),
                        draft_scroll.height(),
                    )
                    self.assertAlmostEqual(
                        bar_rect[0] + bar_rect[2],
                        scroll_rect[0] + scroll_rect[2] - 2,
                        delta=0.5,
                    )
                    self.assertLessEqual(
                        bar_rect[0] + bar_rect[2] + 1,
                        self._rect(page_bar, page)[0],
                    )
                finally:
                    self._dispose(view, component, container)

    def test_editor_pages_do_not_force_outer_scroll_when_content_fits(self):
        cases = (
            (
                "MetadataPage",
                "metadataPageScroll",
                """
        audioPlayer: audioPlayerViewModel
        editSession: editSessionViewModel
""",
            ),
            (
                "AudioProcessingPage",
                "audioProcessingPageScroll",
                """
        processingSession: processingSessionViewModel
""",
            ),
        )
        for page_type, scroll_name, properties in cases:
            with self.subTest(page=page_type):
                view, component, container = self._create_page(
                    page_type,
                    1512,
                    760,
                    properties,
                )
                try:
                    scroll = container.findChild(QQuickItem, scroll_name)
                    self.assertIsNotNone(scroll, scroll_name)
                    self.assertLessEqual(
                        float(scroll.property("contentHeight")),
                        scroll.height() + 0.5,
                    )
                    self.assertAlmostEqual(
                        0.0,
                        float(scroll.property("contentY")),
                        delta=0.5,
                    )
                finally:
                    self._dispose(view, component, container)

    def test_pitch_and_settings_follow_required_breakpoints(self):
        pitch_properties = """
        processingSession: processingSessionViewModel
"""
        expected_pitch_columns = {
            "1080x680": 3,
            "1280x720": 3,
            "1440x900": 3,
            "1536x982": 3,
            "1900x1200": 3,
            "1920x1080": 3,
        }
        expected_settings_columns = {
            "1080x680": 2,
            "1280x720": 2,
            "1440x900": 2,
            "1536x982": 2,
            "1900x1200": 2,
            "1920x1080": 2,
        }
        for label, width, height in VIEWPORT_CASES:
            with self.subTest(window=label, page="pitch"):
                view, component, container = self._create_page(
                    "PitchShiftCard",
                    width,
                    height,
                    pitch_properties,
                    component_directory="components",
                )
                try:
                    card = container.findChild(QQuickItem, "pageUnderTest")
                    grid = container.findChild(
                        QQuickItem, "pitchWorkspaceGrid"
                    )
                    panes = [
                        container.findChild(QQuickItem, name)
                        for name in (
                            "pitchParametersPane",
                            "pitchPreviewPane",
                            "pitchExportPane",
                        )
                    ]
                    self.assertTrue(all((card, grid, *panes)))
                    self.assertEqual(
                        expected_pitch_columns[label],
                        int(grid.property("columns")),
                    )
                    for pane in panes:
                        self._assert_horizontal_fit(pane, card)
                    if expected_pitch_columns[label] == 3:
                        self.assertEqual(
                            1,
                            len(
                                {
                                    round(self._rect(pane, card)[1], 1)
                                    for pane in panes
                                }
                            ),
                        )
                    else:
                        positions = [
                            self._rect(pane, card)[1] for pane in panes
                        ]
                        self.assertEqual(positions, sorted(positions))
                finally:
                    self._dispose(view, component, container)

            with self.subTest(window=label, page="settings"):
                view, component, container = self._create_page(
                    "SettingsPage",
                    width,
                    height,
                )
                try:
                    page = container.findChild(QQuickItem, "pageUnderTest")
                    grid = container.findChild(
                        QQuickItem, "settingsSectionsGrid"
                    )
                    self.assertTrue(all((page, grid)))
                    self.assertEqual(
                        expected_settings_columns[label],
                        int(grid.property("columns")),
                    )
                    self._assert_horizontal_fit(grid, page)
                finally:
                    self._dispose(view, component, container)


if __name__ == "__main__":
    unittest.main()
