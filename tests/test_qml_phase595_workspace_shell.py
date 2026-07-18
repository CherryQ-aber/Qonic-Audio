from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, QObject, Qt, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from shiboken6 import getCppPointer, isValid

from ui_next.bridge.app_state_viewmodel import AppStateViewModel
from ui_next.bridge.audio_player_viewmodel import AudioPlayerViewModel
from ui_next.bridge.audio_processing_session import ProcessingSessionViewModel
from ui_next.bridge.auto_convert_viewmodel import AutoConvertViewModel
from ui_next.bridge.capabilities import CapabilityGate
from ui_next.bridge.cover_viewmodel import CoverViewModel
from ui_next.bridge.edit_session import EditSessionViewModel
from ui_next.bridge.editor_file_browser_viewmodel import EditorFileBrowserViewModel
from ui_next.bridge.file_session_viewmodel import FileSessionViewModel
from ui_next.bridge.log_model import LogModel
from ui_next.bridge.lyrics_viewmodel import LyricsViewModel
from ui_next.bridge.metadata_viewmodel import MetadataViewModel
from ui_next.bridge.runtime_mode import TEST_MODE
from ui_next.bridge.settings_viewmodel import SettingsViewModel
from ui_next.bridge.task_queue_model import TaskQueueModel


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Phase595WorkspaceRouteTests(unittest.TestCase):
    def setUp(self):
        self.state = AppStateViewModel(CapabilityGate((), runtime_mode=TEST_MODE))

    def test_formal_navigation_only_exposes_two_workspaces_and_three_editor_pages(self):
        self.assertEqual(
            ["autoConvert", "audioEditor"],
            [entry["key"] for entry in self.state.workspaces],
        )
        self.assertEqual(
            ["fileInfo", "lyrics", "audioProcessing"],
            [entry["key"] for entry in self.state.editorPages],
        )
        self.assertEqual("all", self.state.currentAutoConvertFilterKey)

    def test_compatibility_routes_map_to_workspace_state_without_duplicate_sessions(self):
        expected = {
            "autoConvert": (
                "autoConvert",
                "fileInfo",
                "autoConvert",
                False,
                False,
            ),
            "audioEditor": (
                "audioEditor",
                "fileInfo",
                "metadata",
                False,
                False,
            ),
            "metadata": (
                "audioEditor",
                "fileInfo",
                "metadata",
                False,
                False,
            ),
            "lyricsCover": (
                "audioEditor",
                "lyrics",
                "lyricsCover",
                False,
                False,
            ),
            "audioProcessing": (
                "audioEditor",
                "audioProcessing",
                "audioProcessing",
                False,
                False,
            ),
            "analysis": (
                "autoConvert",
                "fileInfo",
                "analysis",
                False,
                True,
            ),
        }

        for route, route_state in expected.items():
            with self.subTest(route=route):
                state = AppStateViewModel(
                    CapabilityGate((), runtime_mode=TEST_MODE)
                )
                self.assertTrue(state.setCurrentModule(route))
                self.assertEqual(
                    route_state,
                    (
                        state.currentWorkspaceKey,
                        state.currentEditorPageKey,
                        state.currentModuleKey,
                        state.settingsOverlayOpen,
                        state.legacyAnalysisOpen,
                    ),
                )

        self.assertTrue(self.state.setCurrentModule("lyricsCover"))
        before = (
            self.state.currentWorkspaceKey,
            self.state.currentEditorPageKey,
            self.state.currentModuleKey,
        )
        self.assertTrue(self.state.setCurrentModule("settings"))
        self.assertTrue(self.state.settingsOverlayOpen)
        self.assertEqual(
            before,
            (
                self.state.currentWorkspaceKey,
                self.state.currentEditorPageKey,
                self.state.currentModuleKey,
            ),
        )

    def test_primary_workspace_switch_preserves_last_editor_subpage(self):
        self.assertTrue(self.state.switchEditorPage("lyrics"))
        self.assertTrue(self.state.switchWorkspace("autoConvert"))
        self.assertTrue(self.state.switchWorkspace("audioEditor"))
        self.assertEqual("lyrics", self.state.currentEditorPageKey)

    def test_canonical_file_info_route_is_idempotent_for_formal_navigation(self):
        module_changes = []
        self.state.currentModuleKeyChanged.connect(module_changes.append)

        self.assertTrue(self.state.setCurrentModule("audioEditor"))
        self.assertEqual("metadata", self.state.currentModuleKey)
        module_changes.clear()
        self.assertTrue(self.state.switchWorkspace("audioEditor"))
        self.assertEqual("metadata", self.state.currentModuleKey)
        self.assertEqual([], module_changes)

    def test_unknown_route_is_rejected_without_changing_any_navigation_state(self):
        errors = []
        self.state.errorOccurred.connect(errors.append)
        self.state.setCurrentModule("lyricsCover")
        snapshot = (
            self.state.currentWorkspaceKey,
            self.state.currentEditorPageKey,
            self.state.currentModuleKey,
            self.state.settingsOverlayOpen,
            self.state.legacyAnalysisOpen,
        )

        self.assertFalse(self.state.setCurrentModule("does-not-exist"))
        self.assertEqual(
            snapshot,
            (
                self.state.currentWorkspaceKey,
                self.state.currentEditorPageKey,
                self.state.currentModuleKey,
                self.state.settingsOverlayOpen,
                self.state.legacyAnalysisOpen,
            ),
        )
        self.assertEqual(["未知模块: does-not-exist"], errors)

    def test_unknown_command_line_route_fails_before_loading_the_shell(self):
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "main_qml.py",
                "--qml-smoke-test",
                "--qml-open-module=does-not-exist",
            ],
            cwd=PROJECT_ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=20,
        )

        self.assertEqual(2, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("未知模块: does-not-exist", completed.stderr)


class Phase595RealAppShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _create_real_shell(self):
        gate = CapabilityGate((), runtime_mode=TEST_MODE)
        objects: dict[str, QObject] = {}
        objects["appState"] = AppStateViewModel(gate)
        objects["taskQueueModel"] = TaskQueueModel(gate)
        objects["autoConvertViewModel"] = AutoConvertViewModel(
            objects["taskQueueModel"],
            capability_gate=gate,
        )
        objects["metadataViewModel"] = MetadataViewModel(gate)
        objects["lyricsViewModel"] = LyricsViewModel(gate)
        objects["coverViewModel"] = CoverViewModel(gate)
        objects["fileSessionViewModel"] = FileSessionViewModel(gate)
        objects["fileSessionViewModel"].attach_readers(
            objects["metadataViewModel"],
            objects["lyricsViewModel"],
            objects["coverViewModel"],
        )
        objects["editSessionViewModel"] = EditSessionViewModel(gate)
        objects["fileSessionViewModel"].attach_edit_session(
            objects["editSessionViewModel"]
        )
        objects["fileSessionViewModel"].currentFileChanged.connect(
            objects["editSessionViewModel"].beginCurrentFile
        )
        objects["fileSessionViewModel"].currentFileReloaded.connect(
            objects["editSessionViewModel"].beginCurrentFile
        )
        objects["fileSessionViewModel"].currentFileCleared.connect(
            objects["editSessionViewModel"].clear
        )
        objects["metadataViewModel"].metadataReadApplied.connect(
            objects["editSessionViewModel"].loadMetadataResult
        )
        objects["lyricsViewModel"].lyricsReadApplied.connect(
            objects["editSessionViewModel"].loadLyricsResult
        )
        objects["coverViewModel"].coverReadApplied.connect(
            objects["editSessionViewModel"].loadCoverResult
        )
        objects["fileSessionViewModel"].setUnsavedChangesGuard(
            lambda: objects["editSessionViewModel"].hasUnsavedDrafts
        )
        objects["editSessionViewModel"].stateChanged.connect(
            objects["fileSessionViewModel"].notifyDraftStateChanged
        )
        objects["editorFileBrowserViewModel"] = EditorFileBrowserViewModel(gate)
        objects["editorFileBrowserViewModel"].requestLoadSelected.connect(
            lambda path: objects["fileSessionViewModel"].setCurrentFile(
                path, "file_browser"
            )
        )
        objects["audioPlayerViewModel"] = AudioPlayerViewModel(
            objects["fileSessionViewModel"],
            gate,
        )
        objects["editSessionViewModel"].attach_runtime(
            objects["fileSessionViewModel"],
            objects["audioPlayerViewModel"],
        )
        objects["processingSessionViewModel"] = ProcessingSessionViewModel(
            objects["fileSessionViewModel"],
            objects["audioPlayerViewModel"],
            objects["editSessionViewModel"],
            gate,
        )
        objects["fileSessionViewModel"].setFileChangeBlocker(
            lambda: (
                objects["editSessionViewModel"].anyExporting
                or objects["processingSessionViewModel"].isBusy
                or objects["audioPlayerViewModel"].mediaOperationBusy
            )
        )
        objects["logModel"] = LogModel()
        objects["settingsViewModel"] = SettingsViewModel(
            log_model=objects["logModel"],
            capability_gate=gate,
        )
        objects["capabilityGate"] = gate

        engine = QQmlApplicationEngine()
        qml_root = PROJECT_ROOT / "ui_next" / "qml"
        engine.addImportPath(str(qml_root))
        for key, value in objects.items():
            engine.rootContext().setContextProperty(key, value)
        engine.rootContext().setContextProperty("qmlThemeMode", "dark")
        engine.rootContext().setContextProperty("qmlPreviewMode", True)
        engine.rootContext().setContextProperty("qmlLiveMode", False)
        engine.rootContext().setContextProperty("qmlTestMode", True)
        engine.load(QUrl.fromLocalFile(str(qml_root / "AppShell.qml")))
        self.app.processEvents()
        self.assertTrue(engine.rootObjects())
        return engine, engine.rootObjects()[0], objects

    def _dispose_real_shell(self, engine, root, objects):
        owned_qobjects = [
            value for value in objects.values() if isinstance(value, QObject)
        ]
        root.close()
        refresh_timer = objects["taskQueueModel"]._refresh_timer
        refresh_timer.stop()
        self.assertFalse(refresh_timer.isActive())
        for key in (
            "autoConvertViewModel",
            "editorFileBrowserViewModel",
            "processingSessionViewModel",
            "editSessionViewModel",
            "audioPlayerViewModel",
            "fileSessionViewModel",
        ):
            shutdown = getattr(objects[key], "shutdown", None)
            if shutdown is not None:
                shutdown()
        root.deleteLater()
        engine.deleteLater()
        for obj in reversed(owned_qobjects):
            if isValid(obj):
                obj.deleteLater()
        objects.clear()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()
        self.assertTrue(all(not isValid(obj) for obj in owned_qobjects))

    def _require_child(self, root, object_name):
        child = root.findChild(QObject, object_name)
        self.assertIsNotNone(child, object_name)
        return child

    def test_real_shell_keeps_workspaces_pages_drafts_and_hidden_interactions(self):
        engine, root, objects = self._create_real_shell()
        try:
            app_state = objects["appState"]
            expected_names = (
                "workspaceSwitcher",
                "workspaceSubNavigation",
                "workspaceStack",
                "autoConvertWorkspace",
                "audioEditorWorkspace",
                "editorPageStack",
                "fileInfoPage",
                "lyricsPage",
                "audioProcessingPage",
                "settingsOverlay",
                "folderBrowserPane",
                "logDrawer",
            )
            children = {
                name: self._require_child(root, name) for name in expected_names
            }
            identity_before = {
                name: getCppPointer(children[name])[0]
                for name in (
                    "autoConvertWorkspace",
                    "audioEditorWorkspace",
                    "fileInfoPage",
                    "lyricsPage",
                    "audioProcessingPage",
                )
            }

            queue = self._require_child(root, "autoConvertPrimaryQueue")
            queue.setProperty("selectionAnchorIndex", 4)
            queue.setProperty("selectedPaths", ["alpha.wav", "beta.flac"])
            auto_drop = self._require_child(root, "autoConvertDropArea")
            editor_drop = self._require_child(root, "audioEditorDropArea")
            self.assertTrue(auto_drop.property("enabled"))
            self.assertFalse(editor_drop.property("enabled"))

            app_state.setCurrentModule("lyricsCover")
            self.app.processEvents()
            self.assertFalse(auto_drop.property("enabled"))
            self.assertFalse(editor_drop.property("enabled"))

            app_state.setCurrentModule("audioProcessing")
            self.app.processEvents()
            self.assertFalse(auto_drop.property("enabled"))
            self.assertTrue(editor_drop.property("enabled"))

            app_state.setCurrentModule("autoConvert")
            self.app.processEvents()
            self.assertEqual(4, queue.property("selectionAnchorIndex"))
            self.assertEqual(
                ["alpha.wav", "beta.flac"],
                list(queue.property("selectedPaths")),
            )
            for name, pointer in identity_before.items():
                self.assertEqual(
                    pointer,
                    getCppPointer(self._require_child(root, name))[0],
                    name,
                )

            settings = objects["settingsViewModel"]
            next_density = (
                "compact" if settings.uiDensity != "compact" else "standard"
            )
            settings.updatePendingValue("ui_density", next_density)
            self.assertTrue(settings.hasPendingChanges)
            before_overlay = (
                app_state.currentWorkspaceKey,
                app_state.currentEditorPageKey,
            )
            app_state.openSettings()
            self.app.processEvents()
            self.assertTrue(children["settingsOverlay"].property("opened"))
            QTest.keyClick(root, Qt.Key_Escape)
            QTest.qWait(30)
            self.app.processEvents()
            self.assertFalse(children["settingsOverlay"].property("opened"))
            self.assertFalse(app_state.settingsOverlayOpen)
            self.assertTrue(settings.hasPendingChanges)
            self.assertEqual(
                before_overlay,
                (
                    app_state.currentWorkspaceKey,
                    app_state.currentEditorPageKey,
                ),
            )

            app_state.setCurrentModule("analysis")
            self.app.processEvents()
            self.assertTrue(app_state.legacyAnalysisOpen)
            self.assertFalse(auto_drop.property("enabled"))
            self.assertFalse(editor_drop.property("enabled"))
            app_state.closeLegacyAnalysis()
            self.app.processEvents()
            self.assertFalse(app_state.legacyAnalysisOpen)
            self.assertTrue(auto_drop.property("enabled"))

            root.setProperty("logDrawerOpened", True)
            QTest.qWait(30)
            self.app.processEvents()
            drawer_panel = self._require_child(root, "logDrawerPanel")
            for _index in range(12):
                QTest.keyClick(root, Qt.Key_Tab)
                self.app.processEvents()
                focused = root.activeFocusItem()
                self.assertIsNotNone(focused)
                current = focused
                inside_drawer = False
                while isinstance(current, QQuickItem):
                    if current is drawer_panel:
                        inside_drawer = True
                        break
                    current = current.parentItem()
                self.assertTrue(inside_drawer, focused.objectName())

            QTest.keyClick(root, Qt.Key_Escape)
            QTest.qWait(30)
            self.app.processEvents()
            self.assertFalse(root.property("logDrawerOpened"))
            self.assertEqual(
                before_overlay,
                (
                    app_state.currentWorkspaceKey,
                    app_state.currentEditorPageKey,
                ),
            )

            folder = children["folderBrowserPane"]
            self.assertFalse(folder.property("visible"))
            self.assertFalse(folder.property("enabled"))
            self.assertEqual(0, int(folder.property("width")))
            self.assertIsNone(root.findChild(QObject, "sidebarNavigation"))
            self.assertIsNone(root.findChild(QObject, "rightInspector"))

            task_row_source = (
                PROJECT_ROOT
                / "ui_next"
                / "qml"
                / "components"
                / "TaskRowDelegate.qml"
            ).read_text(encoding="utf-8")
            self.assertIn("onInteractionEnabledChanged", task_row_source)
            self.assertIn("taskMenu.close()", task_row_source)
        finally:
            self._dispose_real_shell(engine, root, objects)


if __name__ == "__main__":
    unittest.main()
