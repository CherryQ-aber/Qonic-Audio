import copy
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QModelIndex, QObject, QPointF, Qt, QUrl
from PySide6.QtQml import QQmlComponent
from PySide6.QtQuick import QQuickItem, QQuickView
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import config
from ui_next.bridge.capabilities import (
    AUDIO_PLAYBACK,
    CONFIG_WRITE,
    COVER_READ,
    DEFAULT_USER_MODE,
    FOLDER_BROWSER,
    METADATA_READ,
    QUEUE_MUTATION,
    CapabilityGate,
)
from ui_next.bridge.editor_file_browser_viewmodel import (
    EditorFileBrowserViewModel,
)
from ui_next.bridge.folder_browser_model import FolderBrowserModel
from ui_next.bridge.drop_path_utils import extract_local_drop_paths


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Phase595FolderPaneAndResponsiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _wait_until(self, predicate, timeout=3.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.app.processEvents()
            if predicate():
                return True
            time.sleep(0.01)
        self.app.processEvents()
        return bool(predicate())

    def _live_gate(self, *extra):
        return CapabilityGate(
            (
                FOLDER_BROWSER,
                AUDIO_PLAYBACK,
                METADATA_READ,
                QUEUE_MUTATION,
                *extra,
            ),
            runtime_mode=DEFAULT_USER_MODE,
        )

    def _empty_config(self):
        data = copy.deepcopy(config.DEFAULT_CONFIG)
        data["folder_browser_root"] = ""
        data["folder_browser_favorites"] = []
        data["folder_browser_recent"] = []
        return data

    def test_preview_model_is_independent_and_never_enumerates(self):
        with (
            patch("os.scandir", side_effect=AssertionError("must not scan")),
            patch.object(
                Path,
                "iterdir",
                side_effect=AssertionError("must not enumerate"),
            ),
        ):
            model = FolderBrowserModel()
            self.assertFalse(model.available)
            self.assertEqual(0, model.count)
            self.assertEqual(0, model.rowCount())
            self.assertEqual(0, model.rowCount(QModelIndex()))
            role_names = {
                bytes(value).decode("utf-8")
                for value in model.roleNames().values()
            }
            self.assertTrue(
                {
                    "filePath",
                    "fileName",
                    "fileUrl",
                    "pathIdentity",
                    "treeDepth",
                    "isDirectory",
                    "isAudio",
                    "isPlayable",
                    "canEnqueue",
                    "canEdit",
                }.issubset(role_names)
            )
        self.assertNotIsInstance(model, EditorFileBrowserViewModel)
        model.deleteLater()
        self.app.processEvents()

    def test_live_model_lazily_lists_only_directories_and_supported_audio(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "Album").mkdir()
            (root / "song.flac").write_bytes(b"audio")
            (root / "encrypted.ncm").write_bytes(b"ncm")
            (root / "ignore.txt").write_text("ignore", encoding="utf-8")
            with patch(
                "ui_next.bridge.folder_browser_model.load_config",
                return_value=self._empty_config(),
            ):
                model = FolderBrowserModel(self._live_gate())
            try:
                self.assertTrue(model.available)
                self.assertTrue(model.openDirectory(temp_dir))
                self.assertTrue(self._wait_until(lambda: model.count == 3))
                rows = [
                    model.index(row, 0, model.rootModelIndex)
                    for row in range(model.rowCount(model.rootModelIndex))
                ]
                names = {model.fileName(index) for index in rows}
                self.assertEqual(
                    {"Album", "song.flac", "encrypted.ncm"},
                    names,
                )
                self.assertNotIn("ignore.txt", names)

                by_name = {model.fileName(index): index for index in rows}
                self.assertTrue(
                    model.data(by_name["Album"], model.isDirectoryRole)
                )
                self.assertTrue(
                    model.data(by_name["song.flac"], model.isPlayableRole)
                )
                self.assertTrue(
                    model.data(by_name["song.flac"], model.canEditRole)
                )
                self.assertTrue(
                    model.data(by_name["encrypted.ncm"], model.canEnqueueRole)
                )
                self.assertFalse(
                    model.data(by_name["encrypted.ncm"], model.isPlayableRole)
                )
                file_url = model.data(
                    by_name["song.flac"],
                    model.fileUrlRole,
                )
                dropped_paths, skipped = extract_local_drop_paths(
                    [QUrl(file_url)]
                )
                self.assertEqual([], skipped)
                self.assertEqual(1, len(dropped_paths))
                self.assertTrue(
                    os.path.samefile(root / "song.flac", dropped_paths[0])
                )
            finally:
                model.deleteLater()
                self.app.processEvents()

    def test_selected_audio_cover_preview_loads_off_thread_and_resets(self):
        preview_url = "data:image/png;base64,iVBORw0KGgo="
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "covered.flac"
            source.write_bytes(b"audio")
            album = root / "Album"
            album.mkdir()
            with (
                patch(
                    "ui_next.bridge.folder_browser_model.load_config",
                    return_value=self._empty_config(),
                ),
                patch(
                    "ui_next.bridge.folder_browser_model.read_cover_preview",
                    return_value={
                        "ok": True,
                        "has_cover": True,
                        "preview_data_url": preview_url,
                    },
                ) as cover_reader,
            ):
                model = FolderBrowserModel(
                    self._live_gate(COVER_READ)
                )
                try:
                    self.assertTrue(model.openDirectory(temp_dir))
                    self.assertTrue(
                        self._wait_until(lambda: model.count == 2)
                    )
                    model.selectPath(str(source))
                    self.assertTrue(model.selectedCoverLoading)
                    self.assertTrue(
                        self._wait_until(
                            lambda: not model.selectedCoverLoading
                        )
                    )
                    self.assertTrue(model.selectedHasCover)
                    self.assertEqual(
                        preview_url,
                        model.selectedCoverPreviewUrl,
                    )
                    self.assertEqual(
                        "已读取内嵌封面",
                        model.selectedCoverStatus,
                    )
                    cover_reader.assert_called_once()

                    model.selectPath(str(album))
                    self.assertFalse(model.selectedHasCover)
                    self.assertEqual("", model.selectedCoverPreviewUrl)
                    self.assertEqual(
                        "文件夹没有封面预览",
                        model.selectedCoverStatus,
                    )

                    model.selectPath(str(source))
                    self.assertFalse(model.selectedCoverLoading)
                    self.assertEqual(
                        preview_url,
                        model.selectedCoverPreviewUrl,
                    )
                    cover_reader.assert_called_once()
                finally:
                    model.shutdown()
                    model.deleteLater()
                    self.app.processEvents()

    def test_click_selection_is_passive_and_explicit_actions_emit_once(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "sample.flac"
            source.write_bytes(b"audio")
            with patch(
                "ui_next.bridge.folder_browser_model.load_config",
                return_value=self._empty_config(),
            ):
                model = FolderBrowserModel(self._live_gate())
            playback_requests = []
            editor_requests = []
            queue_requests = []
            model.playbackRequested.connect(
                lambda *args: playback_requests.append(args)
            )
            model.editorRequested.connect(editor_requests.append)
            model.enqueueRequested.connect(queue_requests.append)
            try:
                self.assertTrue(model.openDirectory(temp_dir))
                self.assertTrue(self._wait_until(lambda: model.count == 1))
                model.selectPath(str(source))
                self.assertEqual(str(source), model.selectedPath)
                self.assertEqual([], playback_requests)
                self.assertEqual([], editor_requests)
                self.assertEqual([], queue_requests)

                self.assertTrue(model.requestPlayback(str(source)))
                self.assertTrue(model.requestOpenInEditor(str(source)))
                self.assertTrue(model.requestAddToQueue(str(source)))
                self.assertEqual(
                    (
                        str(source),
                        source.name,
                        "original",
                        "folder_tree",
                    ),
                    playback_requests[0],
                )
                self.assertEqual([str(source)], editor_requests)
                self.assertEqual([str(source)], queue_requests)
            finally:
                model.deleteLater()
                self.app.processEvents()

    def test_search_filter_and_native_directory_refresh_do_not_enqueue(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            alpha = root / "alpha.flac"
            beta = root / "beta.mp3"
            alpha.write_bytes(b"alpha")
            beta.write_bytes(b"beta")
            with patch(
                "ui_next.bridge.folder_browser_model.load_config",
                return_value=self._empty_config(),
            ):
                model = FolderBrowserModel(self._live_gate())
            queue_requests = []
            model.enqueueRequested.connect(queue_requests.append)
            try:
                self.assertTrue(model.openDirectory(temp_dir))
                self.assertTrue(self._wait_until(lambda: model.count == 2))
                model.setSearchText("alpha")
                self.assertTrue(self._wait_until(lambda: model.count == 1))
                visible = model.index(0, 0, model.rootModelIndex)
                self.assertEqual("alpha.flac", model.fileName(visible))

                model.setSearchText("")
                self.assertTrue(self._wait_until(lambda: model.count == 2))
                gamma = root / "gamma.wav"
                gamma.write_bytes(b"gamma")
                self.assertTrue(self._wait_until(lambda: model.count == 3))
                beta.unlink()
                self.assertTrue(self._wait_until(lambda: model.count == 2))
                self.assertEqual([], queue_requests)
            finally:
                model.deleteLater()
                self.app.processEvents()

    def test_root_favorites_recent_visibility_and_width_restore(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            browser_root = root / "音乐 目录"
            browser_root.mkdir()
            config_path = root / "config.json"
            with patch.object(config, "CONFIG_FILE", str(config_path)):
                gate = self._live_gate(CONFIG_WRITE)
                first = FolderBrowserModel(gate)
                self.assertTrue(first.openDirectory(str(browser_root)))
                first.toggleCurrentRootFavorite()
                first.setPaneVisible(False)
                first.setPaneWidth(344)
                first.deleteLater()
                self.app.processEvents()

                second = FolderBrowserModel(gate)
                try:
                    self.assertTrue(
                        os.path.samefile(
                            browser_root,
                            second.currentRootPath,
                        )
                    )
                    self.assertFalse(second.paneVisible)
                    self.assertEqual(344, second.paneWidth)
                    self.assertTrue(second.currentRootFavorite)
                    self.assertTrue(
                        os.path.samefile(
                            browser_root,
                            second.favoriteDirectories[0]["path"],
                        )
                    )
                    self.assertTrue(
                        os.path.samefile(
                            browser_root,
                            second.recentDirectories[0]["path"],
                        )
                    )
                finally:
                    second.deleteLater()
                    self.app.processEvents()

    def test_folder_pane_renders_real_tree_and_controls(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "sample.flac"
            source.write_bytes(b"audio")
            with patch(
                "ui_next.bridge.folder_browser_model.load_config",
                return_value=self._empty_config(),
            ):
                model = FolderBrowserModel(self._live_gate())
            self.assertTrue(model.openDirectory(temp_dir))
            self.assertTrue(self._wait_until(lambda: model.count == 1))

            view = QQuickView()
            view.rootContext().setContextProperty("liveFolderModel", model)
            component = QQmlComponent(view.engine())
            component.setData(
                b'''import QtQuick
import "ui_next/qml/components"

Item {
    width: 320
    height: 640

    FolderBrowserPane {
        objectName: "folderPaneUnderTest"
        anchors.fill: parent
        folderBrowserModel: liveFolderModel
    }
}
''',
                QUrl.fromLocalFile(
                    str(PROJECT_ROOT / "phase595_folder_pane_probe.qml")
                ),
            )
            container = component.create()
            self.assertIsNotNone(container, component.errors())
            self.assertIsInstance(container, QQuickItem)
            container.setParentItem(view.contentItem())
            view.setWidth(320)
            view.setHeight(640)
            view.show()
            self.assertTrue(
                self._wait_until(
                    lambda: container.findChild(
                        QObject, "globalFolderTree"
                    ).property("rows")
                    == 1
                )
            )
            pane = container.findChild(QQuickItem, "folderPaneUnderTest")
            try:
                self.assertTrue(pane.property("available"))
                self.assertEqual(1, int(pane.property("itemCount")))
                self.assertEqual(220, int(pane.property("minimumPaneWidth")))
                self.assertEqual(260, int(pane.property("defaultPaneWidth")))
                self.assertEqual(360, int(pane.property("maximumPaneWidth")))
                for object_name in (
                    "chooseFolderBrowserRootButton",
                    "folderBrowserFavorites",
                    "folderBrowserRecentDirectories",
                    "folderBrowserSearchField",
                    "globalFolderTree",
                    "folderBrowserContextMenu",
                    "folderBrowserSelectionSummary",
                    "folderBrowserCoverThumbnail",
                    "folderBrowserCoverImage",
                ):
                    self.assertIsNotNone(
                        container.findChild(QObject, object_name),
                        object_name,
                    )
            finally:
                view.close()
                container.deleteLater()
                component.deleteLater()
                view.deleteLater()
                model.deleteLater()
                self.app.processEvents()

    def test_qml_tree_arrow_double_click_and_right_click_are_wired(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            album = root / "Album"
            album.mkdir()
            nested = album / "inside.wav"
            nested.write_bytes(b"nested")
            source = root / "sample.flac"
            source.write_bytes(b"audio")
            with patch(
                "ui_next.bridge.folder_browser_model.load_config",
                return_value=self._empty_config(),
            ):
                model = FolderBrowserModel(self._live_gate())
            playback_requests = []
            model.playbackRequested.connect(
                lambda *args: playback_requests.append(args)
            )
            self.assertTrue(model.openDirectory(temp_dir))
            self.assertTrue(self._wait_until(lambda: model.count == 2))

            view = QQuickView()
            view.rootContext().setContextProperty("liveFolderModel", model)
            component = QQmlComponent(view.engine())
            component.setData(
                b'''import QtQuick
import "ui_next/qml/components"

Item {
    width: 320
    height: 640
    FolderBrowserPane {
        anchors.fill: parent
        folderBrowserModel: liveFolderModel
    }
}
''',
                QUrl.fromLocalFile(
                    str(PROJECT_ROOT / "phase595_folder_mouse_probe.qml")
                ),
            )
            container = component.create()
            self.assertIsNotNone(container, component.errors())
            container.setParentItem(view.contentItem())
            view.setWidth(320)
            view.setHeight(640)
            view.show()
            tree = container.findChild(QQuickItem, "globalFolderTree")
            self.assertTrue(
                self._wait_until(lambda: int(tree.property("rows")) == 2)
            )

            def delegate_for(path):
                content_item = tree.childItems()[0]
                for delegate in content_item.childItems():
                    current = str(delegate.property("filePath") or "")
                    try:
                        same_path = os.path.samefile(current, path)
                    except (FileNotFoundError, OSError):
                        same_path = False
                    if (
                        same_path
                        and delegate.isVisible()
                        and delegate.height() > 0
                    ):
                        return delegate
                return None

            def visible_paths():
                content_item = tree.childItems()[0]
                return [
                    str(delegate.property("filePath") or "")
                    for delegate in content_item.childItems()
                    if (
                        delegate.isVisible()
                        and delegate.height() > 0
                        and delegate.property("filePath")
                    )
                ]

            try:
                self.assertTrue(
                    self._wait_until(
                        lambda: delegate_for(album) is not None
                    )
                )
                album_delegate = delegate_for(album)
                self.assertIsNotNone(album_delegate)
                arrow_point = album_delegate.mapToItem(
                    view.contentItem(),
                    QPointF(11, 15),
                )
                QTest.mouseClick(
                    view,
                    Qt.LeftButton,
                    Qt.NoModifier,
                    arrow_point.toPoint(),
                )
                self.assertTrue(
                    self._wait_until(
                        lambda: int(tree.property("rows")) == 3
                        and len(visible_paths()) == 3
                        and len(set(visible_paths())) == 3
                    )
                )
                for _ in range(6):
                    album_delegate = delegate_for(album)
                    arrow_point = album_delegate.mapToItem(
                        view.contentItem(),
                        QPointF(11, 15),
                    )
                    QTest.mouseClick(
                        view,
                        Qt.LeftButton,
                        Qt.NoModifier,
                        arrow_point.toPoint(),
                    )
                    self.assertTrue(
                        self._wait_until(
                            lambda: int(tree.property("rows")) == 2
                            and len(visible_paths()) == 2
                            and len(set(visible_paths())) == 2
                        )
                    )
                    album_delegate = delegate_for(album)
                    arrow_point = album_delegate.mapToItem(
                        view.contentItem(),
                        QPointF(11, 15),
                    )
                    QTest.mouseClick(
                        view,
                        Qt.LeftButton,
                        Qt.NoModifier,
                        arrow_point.toPoint(),
                    )
                    self.assertTrue(
                        self._wait_until(
                            lambda: int(tree.property("rows")) == 3
                            and len(visible_paths()) == 3
                            and len(set(visible_paths())) == 3
                        )
                    )

                source_delegate = delegate_for(source)
                self.assertIsNotNone(source_delegate)
                center = source_delegate.mapToItem(
                    view.contentItem(),
                    QPointF(
                        source_delegate.width() / 2,
                        source_delegate.height() / 2,
                    ),
                )
                QTest.mouseDClick(
                    view,
                    Qt.LeftButton,
                    Qt.NoModifier,
                    center.toPoint(),
                )
                self.assertTrue(
                    self._wait_until(lambda: len(playback_requests) == 1)
                )
                self.assertTrue(
                    os.path.samefile(source, playback_requests[0][0])
                )
                self.assertTrue(
                    self._wait_until(
                        lambda: bool(
                            delegate_for(source).property(
                                "currentSelection"
                            )
                        )
                    )
                )

                QTest.mouseClick(
                    view,
                    Qt.RightButton,
                    Qt.NoModifier,
                    center.toPoint(),
                )
                context_menu = container.findChild(
                    QObject,
                    "folderBrowserContextMenu",
                )
                self.assertTrue(
                    self._wait_until(
                        lambda: bool(context_menu.property("visible"))
                    )
                )
                QTest.keyClick(view, Qt.Key_Escape)
                self.assertTrue(
                    self._wait_until(
                        lambda: not bool(context_menu.property("visible"))
                    )
                )
            finally:
                view.close()
                container.deleteLater()
                component.deleteLater()
                view.deleteLater()
                model.deleteLater()
                self.app.processEvents()

    def test_qml_folder_audio_drag_bridge_emits_one_standard_file_url(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "drag me.flac"
            source.write_bytes(b"audio")
            with patch(
                "ui_next.bridge.folder_browser_model.load_config",
                return_value=self._empty_config(),
            ):
                model = FolderBrowserModel(self._live_gate())
            self.assertTrue(model.openDirectory(temp_dir))
            self.assertTrue(self._wait_until(lambda: model.count == 1))

            view = QQuickView()
            view.rootContext().setContextProperty(
                "liveFolderModel",
                model,
            )
            component = QQmlComponent(view.engine())
            component.setData(
                b'''import QtQuick
import "ui_next/qml/components"

Item {
    width: 600
    height: 640
    property string releasedUrl: ""
    property bool releasedEditable: false
    property bool releasedQueueable: false
    property real releasedX: 0

    FolderBrowserPane {
        width: 320
        height: 640
        folderBrowserModel: liveFolderModel
        onFileDragReleased: function(
            fileUrl,
            editable,
            queueable,
            paneX,
            paneY
        ) {
            parent.releasedUrl = fileUrl
            parent.releasedEditable = editable
            parent.releasedQueueable = queueable
            parent.releasedX = paneX
        }
    }
}
''',
                QUrl.fromLocalFile(
                    str(PROJECT_ROOT / "phase595_folder_drag_probe.qml")
                ),
            )
            container = component.create()
            self.assertIsNotNone(container, component.errors())
            container.setParentItem(view.contentItem())
            view.setWidth(600)
            view.setHeight(640)
            view.show()
            tree = container.findChild(QQuickItem, "globalFolderTree")

            def visible_source_delegate():
                if tree is None or not tree.childItems():
                    return None
                for delegate in tree.childItems()[0].childItems():
                    if (
                        delegate.isVisible()
                        and delegate.height() > 0
                        and delegate.property("filePath")
                    ):
                        return delegate
                return None

            try:
                self.assertTrue(
                    self._wait_until(
                        lambda: int(tree.property("rows")) == 1
                        and visible_source_delegate() is not None
                    )
                )
                delegate = visible_source_delegate()
                self.assertTrue(bool(delegate.property("dragEnabled")))
                self.assertTrue(model.beginInternalDrag(str(source)))
                self.assertTrue(model.internalDragActive)
                QTest.qWait(80)
                self.app.processEvents()
                self.assertTrue(model.internalDragActive)
                self.assertFalse(bool(container.property("releasedUrl")))
                model.finishInternalDrag()
                self.assertTrue(
                    self._wait_until(
                        lambda: bool(container.property("releasedUrl"))
                    ),
                )
                paths, skipped = extract_local_drop_paths(
                    [container.property("releasedUrl")]
                )
                self.assertEqual([], skipped)
                self.assertEqual(1, len(paths))
                self.assertTrue(os.path.samefile(source, paths[0]))
                self.assertTrue(
                    bool(container.property("releasedEditable"))
                )
                self.assertTrue(
                    bool(container.property("releasedQueueable"))
                )
            finally:
                view.close()
                container.deleteLater()
                component.deleteLater()
                view.deleteLater()
                model.shutdown()
                model.deleteLater()
                self.app.processEvents()

    def test_production_wiring_uses_one_capability_gated_global_model(self):
        main_source = (PROJECT_ROOT / "main_qml.py").read_text(
            encoding="utf-8"
        )
        shell_source = (
            PROJECT_ROOT / "ui_next/qml/AppShell.qml"
        ).read_text(encoding="utf-8")
        pane_source = (
            PROJECT_ROOT
            / "ui_next/qml/components/FolderBrowserPane.qml"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "FolderBrowserModel(capability_gate=capability_gate)",
            main_source,
        )
        self.assertIn(
            'setContextProperty(\n        "folderBrowserModel"',
            main_source,
        )
        self.assertIn(
            "folder_browser_model.playbackRequested.connect(",
            main_source,
        )
        self.assertIn(
            "folder_browser_model.editorRequested.connect(",
            main_source,
        )
        self.assertIn(
            "folder_browser_model.enqueueRequested.connect(",
            main_source,
        )
        self.assertIn("property var folderBrowserBridge:", shell_source)
        self.assertIn(
            "folderBrowserModel: root.folderBrowserBridge",
            shell_source,
        )
        self.assertIn("SplitView {", shell_source)
        self.assertIn("TreeView {", pane_source)
        self.assertIn("reuseItems: false", pane_source)
        self.assertIn("required property int treeDepth", pane_source)
        self.assertIn("validTreeDepth", pane_source)
        self.assertIn("beginInternalDrag(", pane_source)
        self.assertIn("rowMouse.drag.active", pane_source)
        self.assertIn("onCanceled:", pane_source)
        self.assertIn("cancelInternalDrag()", pane_source)
        self.assertIn("onInternalDragReleased(", pane_source)
        self.assertIn("signal fileDragReleased(", pane_source)
        self.assertIn(
            'objectName: "folderFileDragIndicator"',
            shell_source,
        )
        self.assertIn('text: "正在拖动 · "', shell_source)
        self.assertIn(
            "root.folderBrowserBridge.internalDragActive",
            shell_source,
        )
        self.assertNotIn("EditorFileBrowser", pane_source)
        self.assertNotIn("功能开发中", pane_source)

        queue_source = (
            PROJECT_ROOT
            / "ui_next/qml/components/TaskQueueView.qml"
        ).read_text(encoding="utf-8")
        editor_source = (
            PROJECT_ROOT
            / "ui_next/qml/components/AudioEditorWorkspace.qml"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "enqueue_dropped_items(drop.urls)",
            queue_source,
        )
        self.assertIn(
            "handleDroppedUrls(drop.urls)",
            editor_source,
        )
        self.assertIn(
            "function handleFolderFileDragRelease(",
            shell_source,
        )
        self.assertIn(
            "autoConvertViewModel.enqueue_dropped_items([fileUrl])",
            shell_source,
        )
        self.assertIn(
            "fileSessionViewModel.handleDroppedUrls([fileUrl])",
            shell_source,
        )

    def test_responsive_thresholds_remain_exact(self):
        shell_source = (
            PROJECT_ROOT / "ui_next/qml/AppShell.qml"
        ).read_text(encoding="utf-8")
        inspector_source = (
            PROJECT_ROOT
            / "ui_next/qml/components/TaskInspectorDrawer.qml"
        ).read_text(encoding="utf-8")

        self.assertIn("minimumWidth: 1080", shell_source)
        self.assertIn("minimumHeight: 680", shell_source)
        self.assertIn("compactMode: root.height < 800", shell_source)
        self.assertIn("narrowMode: root.width < 1320", shell_source)
        self.assertIn(
            "viewportWidth >= 1900 && viewportHeight >= 1200",
            inspector_source,
        )

    def test_qml_smoke_supports_three_scale_factors(self):
        for scale in ("1", "1.25", "1.5"):
            with self.subTest(scale=scale):
                env = os.environ.copy()
                env["QT_QPA_PLATFORM"] = "offscreen"
                env["QT_SCALE_FACTOR"] = scale
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        "main_qml.py",
                        "--qml-smoke-test",
                        "--qml-open-module=autoConvert",
                    ],
                    cwd=PROJECT_ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    timeout=20,
                )
                output = completed.stdout + completed.stderr
                self.assertEqual(0, completed.returncode, output)
                self.assertNotIn("ReferenceError", output)
                self.assertNotIn("binding loop", output.lower())


if __name__ == "__main__":
    unittest.main()
