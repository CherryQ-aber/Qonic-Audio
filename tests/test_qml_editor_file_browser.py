import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

from ui_next.bridge.capabilities import (
    DEFAULT_USER_MODE,
    METADATA_READ,
    PREVIEW_MODE,
    CapabilityGate,
)
from ui_next.bridge.editor_file_browser_viewmodel import (
    EditorFileBrowserViewModel,
    enumerate_editor_audio_files,
)


class EditorFileBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def _gate(self, mode=DEFAULT_USER_MODE):
        return CapabilityGate((METADATA_READ,), runtime_mode=mode)

    def _wait_for_scan(self, view_model: EditorFileBrowserViewModel) -> None:
        if not view_model.isLoading:
            return
        loop = QEventLoop()

        def maybe_quit():
            if not view_model.isLoading:
                loop.quit()

        view_model.stateChanged.connect(maybe_quit)
        QTimer.singleShot(3000, loop.quit)
        loop.exec()
        try:
            view_model.stateChanged.disconnect(maybe_quit)
        except (RuntimeError, TypeError):
            pass
        self.assertFalse(view_model.isLoading)

    def test_enumeration_uses_editor_formats_and_excludes_lrc_ncm_and_children(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            supported = (
                "a.mp3",
                "b.flac",
                "c.wav",
                "d.m4a",
                "e.aac",
                "f.ogg",
                "g.opus",
                "h.ape",
                "i.aiff",
                "j.aif",
                "k.wma",
                "l.alac",
            )
            for name in supported:
                (root / name).write_bytes(name.encode("utf-8"))
            (root / "lyrics.lrc").write_text("[00:00.00]test", encoding="utf-8")
            (root / "encrypted.ncm").write_bytes(b"ncm")
            child = root / "child"
            child.mkdir()
            (child / "nested.flac").write_bytes(b"nested")

            items = enumerate_editor_audio_files(str(root))

        names = {str(item["name"]) for item in items}
        self.assertEqual(set(supported), names)
        self.assertNotIn("lyrics.lrc", names)
        self.assertNotIn("encrypted.ncm", names)
        self.assertNotIn("nested.flac", names)
        self.assertTrue(
            all({"name", "path", "format", "extension", "size"} <= set(item) for item in items)
        )

    def test_background_scan_populates_shallow_items(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Song Name.FLAC"
            source.write_bytes(b"audio")
            view_model = EditorFileBrowserViewModel(self._gate())

            view_model.scanFolder(str(root))
            self._wait_for_scan(view_model)

            self.assertEqual("ready", view_model.state)
            self.assertEqual(1, view_model.itemCount)
            self.assertEqual("Song Name.FLAC", view_model.items[0]["name"])
            self.assertEqual("flac", view_model.items[0]["extension"])
            self.assertEqual("FLAC", view_model.items[0]["format"])
            self.assertEqual(5, view_model.items[0]["size"])
            view_model.shutdown()

    def test_selection_does_not_load_until_explicit_action(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "selected.wav"
            source.write_bytes(b"audio")
            view_model = EditorFileBrowserViewModel(self._gate())
            view_model._items = [
                {
                    "name": source.name,
                    "path": str(source),
                    "format": "WAV",
                    "extension": "wav",
                    "size": source.stat().st_size,
                }
            ]
            loaded_paths = []
            view_model.requestLoadSelected.connect(loaded_paths.append)

            view_model.selectFile(str(source))

            self.assertEqual(str(source), view_model.selectedFilePath)
            self.assertEqual([], loaded_paths)

            view_model.loadSelected()

            self.assertEqual([str(source)], loaded_paths)
            self.assertIn("不会自动播放", view_model.statusMessage)

    def test_stale_result_cannot_replace_newer_folder(self):
        view_model = EditorFileBrowserViewModel(self._gate())
        view_model._folder_path = os.path.normpath("D:/new")
        view_model._active_request_generation = 2
        view_model._state = "loading"

        view_model._apply_scan_result(
            1,
            os.path.normpath("D:/old"),
            [{"name": "old.mp3", "path": "D:/old/old.mp3"}],
            "",
        )

        self.assertEqual([], view_model.items)
        self.assertEqual("loading", view_model.state)

    def test_preview_mode_never_starts_real_directory_scan(self):
        view_model = EditorFileBrowserViewModel(self._gate(PREVIEW_MODE))

        with patch(
            "ui_next.bridge.editor_file_browser_viewmodel._EditorFolderScanThread"
        ) as thread_class:
            view_model.scanFolder("D:/Private Music")

        thread_class.assert_not_called()
        self.assertFalse(view_model.browserEnabled)
        self.assertEqual("disabled", view_model.state)
        self.assertEqual([], view_model.items)
        self.assertIn("不会读取真实文件夹", view_model.statusMessage)

    def test_missing_read_capability_never_starts_scan(self):
        gate = CapabilityGate((), runtime_mode=DEFAULT_USER_MODE)
        view_model = EditorFileBrowserViewModel(gate)

        with patch(
            "ui_next.bridge.editor_file_browser_viewmodel._EditorFolderScanThread"
        ) as thread_class:
            view_model.scanFolder("D:/Private Music")

        thread_class.assert_not_called()
        self.assertFalse(view_model.browserEnabled)
        self.assertEqual("disabled", view_model.state)

    def test_choose_folder_uses_native_dialog_and_does_not_save_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            view_model = EditorFileBrowserViewModel(self._gate())
            with patch(
                "ui_next.bridge.editor_file_browser_viewmodel.QFileDialog.getExistingDirectory",
                return_value=temp_dir,
            ) as dialog:
                view_model.chooseFolder()
                self._wait_for_scan(view_model)

            dialog.assert_called_once()
            self.assertTrue(os.path.samefile(temp_dir, view_model.folderPath))
            source = Path(
                "ui_next/bridge/editor_file_browser_viewmodel.py"
            ).read_text(encoding="utf-8")
            self.assertNotIn("save_config", source)
            self.assertNotIn("import config", source)
            view_model.shutdown()


if __name__ == "__main__":
    unittest.main()
