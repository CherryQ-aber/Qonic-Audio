import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, QTimer, QUrl
from PySide6.QtWidgets import QApplication

import config
import watcher


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LegacySafeStartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _config_data(self, root: Path, **overrides):
        data = copy.deepcopy(config.DEFAULT_CONFIG)
        data.update(
            {
                "watch_folder": str(root / "watch"),
                "output_folder": str(root / "output"),
                "editor_output_folder": str(root / "editor_output"),
                "editor_temp_folder": str(root / "editor_temp"),
                "editor_project_folders": [],
                "editor_browser_folder": "",
                "first_launch_completed": True,
                "auto_start_monitor": False,
                "scan_existing_on_start": False,
            }
        )
        data.update(overrides)
        return data

    def _make_window(self, root: Path, data: dict, *, safe_start=False):
        import ui.audio_editor as audio_editor
        import ui.main_window as main_window

        config_path = root / "config.json"
        config_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        initial_config_sha = file_sha(config_path)
        save_calls = []
        watcher_calls = {"start": 0, "scan": 0, "convert": 0}

        def tracked_save(value):
            save_calls.append(copy.deepcopy(value))
            return config._merge_with_default(value)

        def watcher_start(*_args, **_kwargs):
            watcher_calls["start"] += 1

        def watcher_scan(*_args, **_kwargs):
            watcher_calls["scan"] += 1
            return {
                "total_count": 0,
                "scanned_count": 0,
                "queued_count": 0,
                "skipped_count": 0,
                "current_file": "",
            }

        def prevent_convert(*_args, **_kwargs):
            watcher_calls["convert"] += 1

        patches = [
            patch.object(config, "CONFIG_FILE", str(config_path)),
            patch.object(main_window, "save_config", side_effect=tracked_save),
            patch.object(audio_editor, "save_config", side_effect=tracked_save),
            patch.object(main_window.cache_manager, "ensure_cache_dirs", return_value=None),
            patch.object(main_window.watcher, "start_watch", side_effect=watcher_start),
            patch.object(main_window.watcher, "scan_existing_files", side_effect=watcher_scan),
            patch.object(main_window.ConvertThread, "start", side_effect=prevent_convert),
            patch.object(
                audio_editor.AudioEditorWorkspace,
                "start_editor_browser_scan",
                return_value=None,
            ),
        ]
        for active_patch in patches:
            active_patch.start()
        self.addCleanup(lambda: [active_patch.stop() for active_patch in reversed(patches)])

        window = main_window.MainWindow(safe_start=safe_start)
        self.addCleanup(self._dispose_window, window)
        return (
            window,
            config_path,
            initial_config_sha,
            save_calls,
            watcher_calls,
            main_window,
        )

    def _dispose_window(self, window):
        window.is_quitting = True
        if window.timer is not None:
            window.timer.stop()
        audio_editor = getattr(window, "audio_editor_workspace", None)
        if audio_editor is not None and getattr(audio_editor, "player", None) is not None:
            audio_editor.player.stop()
            audio_editor.player.setSource(QUrl())
        window.tray_icon.hide()
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()

    def _run_short_event_loop(self):
        QTimer.singleShot(80, self.app.quit)
        self.app.exec()
        self.app.processEvents()

    def test_unchanged_project_folders_do_not_save_on_construction(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "watch").mkdir()
            window, config_path, initial_sha, save_calls, _calls, _module = self._make_window(
                root,
                self._config_data(root),
            )

            self.assertEqual(save_calls, [])
            self.assertEqual(window.audio_editor_workspace.editor_project_folders, [])
            self.assertEqual(file_sha(config_path), initial_sha)

    def test_duplicate_project_folders_are_normalized_and_saved_once(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            watch = root / "watch"
            project = root / "project"
            watch.mkdir()
            project.mkdir()
            data = self._config_data(
                root,
                editor_project_folders=[str(project), str(project)],
                editor_browser_folder=str(project),
            )
            window, _config_path, _initial_sha, save_calls, _calls, _module = self._make_window(
                root,
                data,
            )

            self.assertEqual(len(save_calls), 1)
            self.assertEqual(window.audio_editor_workspace.editor_project_folders, [str(project)])

    def test_safe_start_blocks_config_watcher_scan_convert_and_first_launch_flow(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data = self._config_data(
                root,
                first_launch_completed=False,
                auto_start_monitor=True,
                scan_existing_on_start=True,
            )
            window, config_path, initial_sha, save_calls, calls, _module = self._make_window(
                root,
                data,
                safe_start=True,
            )
            window.show()
            self._run_short_event_loop()
            window.start_monitor()
            window.toggle_monitor_from_tray()
            window.start_scan_existing_files()
            window.start_convert()
            window.retry_failed_items()
            window.auto_start_checkbox.setChecked(False)

            self.assertEqual(save_calls, [])
            self.assertEqual(calls, {"start": 0, "scan": 0, "convert": 0})
            self.assertEqual(file_sha(config_path), initial_sha)
            self.assertFalse(window.config_data["first_launch_completed"])
            self.assertFalse(window.config_data["auto_start_monitor"])
            self.assertIsNone(window.thread)
            self.assertIsNone(window.scan_thread)
            self.assertIsNone(window.convert_thread)
            self.assertIsNone(window.retry_thread)

    def test_normal_auto_start_keeps_watcher_and_scan_behavior(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "watch").mkdir()
            data = self._config_data(
                root,
                auto_start_monitor=True,
                scan_existing_on_start=True,
            )
            window, _config_path, _initial_sha, save_calls, calls, main_window = self._make_window(
                root,
                data,
            )

            with (
                patch.object(main_window.WatcherThread, "start", lambda thread: thread.run()),
                patch.object(main_window.ScanThread, "start", lambda thread: thread.run()),
                patch.object(main_window.QueuePrepareThread, "start", return_value=None),
            ):
                window.show()
                self._run_short_event_loop()

            self.assertEqual(save_calls, [])
            self.assertEqual(calls["start"], 1)
            self.assertEqual(calls["scan"], 1)
            self.assertEqual(calls["convert"], 0)

    def test_normal_user_setting_still_saves(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "watch").mkdir()
            window, _config_path, _initial_sha, save_calls, _calls, _module = self._make_window(
                root,
                self._config_data(root),
            )

            window.auto_start_checkbox.setChecked(True)

            self.assertEqual(len(save_calls), 1)
            self.assertTrue(window.config_data["auto_start_monitor"])

    def test_safe_start_does_not_mutate_watcher_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            before_pending = watcher.get_task_snapshots()
            before_processed = set(watcher.processed_files)
            window, _config_path, _initial_sha, _save_calls, _calls, _module = self._make_window(
                root,
                self._config_data(root),
                safe_start=True,
            )

            window.handle_dropped_files([str(root / "song.wav")])
            window.clear_terminal_items()
            window.change_file_target_format(str(root / "song.wav"), "flac")

            self.assertEqual(watcher.get_task_snapshots(), before_pending)
            self.assertEqual(set(watcher.processed_files), before_processed)

    def test_gui_entry_reads_safe_start_environment_flag(self):
        import gui

        app = MagicMock()
        app.exec.return_value = 0
        with (
            patch.dict(os.environ, {"QONIC_LEGACY_SAFE_START": "1"}, clear=True),
            patch.object(gui, "QApplication", return_value=app),
            patch.object(gui, "apply_theme"),
            patch.object(gui, "MainWindow") as main_window,
        ):
            self.assertEqual(gui.main(), 0)

        main_window.assert_called_once_with(safe_start=True)
        main_window.return_value.show.assert_called_once()

    def test_gui_entry_keeps_cherryq_safe_start_alias_during_migration(self):
        import gui

        app = MagicMock()
        app.exec.return_value = 0
        with (
            patch.dict(os.environ, {"CHERRYQ_LEGACY_SAFE_START": "1"}, clear=True),
            patch.object(gui, "QApplication", return_value=app),
            patch.object(gui, "apply_theme"),
            patch.object(gui, "MainWindow") as main_window,
        ):
            self.assertEqual(gui.main(), 0)

        main_window.assert_called_once_with(safe_start=True)


if __name__ == "__main__":
    unittest.main()
