import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication

from ui_next.bridge.capabilities import (
    COVER_READ,
    LYRICS_READ,
    METADATA_READ,
    CapabilityGate,
)
from ui_next.bridge.file_session_viewmodel import FileSessionViewModel
from ui_next.bridge.cover_viewmodel import CoverViewModel
from ui_next.bridge.editor_session_viewmodel import EditorSessionViewModel
from ui_next.bridge.lyrics_viewmodel import LyricsViewModel
from ui_next.bridge.metadata_viewmodel import MetadataViewModel


class _Reader:
    def __init__(self):
        self.started = []
        self.results = []
        self.cleared = 0

    def beginSessionRead(self, path, state):
        self.started.append((path, state))

    def applySessionReadResult(self, result):
        self.results.append(result)

    def clearSessionState(self):
        self.cleared += 1


class FileSessionViewModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def _wait_ready(self, session, timeout=2.0):
        deadline = time.monotonic() + timeout
        while session.isLoading and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.app.processEvents()
        self.assertFalse(session.isLoading)

    def test_default_session_is_empty_and_does_not_call_readers(self):
        session = FileSessionViewModel(CapabilityGate())
        readers = (_Reader(), _Reader(), _Reader())
        session.attach_readers(*readers)

        self.assertFalse(session.hasCurrentFile)
        self.assertEqual("empty", session.sessionState)
        self.assertEqual("idle", session.metadataState)
        session.clearCurrentFile()
        self.assertTrue(all(reader.cleared == 1 for reader in readers))

    def test_authorized_readers_share_one_session_and_clear_together(self):
        gate = CapabilityGate((METADATA_READ, LYRICS_READ, COVER_READ))
        session = FileSessionViewModel(gate)
        readers = (_Reader(), _Reader(), _Reader())
        session.attach_readers(*readers)
        metadata_result = {"ok": True, "path": "", "has_basic_tags": True}
        lyrics_result = {"ok": True, "has_lyrics": False}
        cover_result = {"ok": True, "has_cover": False}

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "demo.wav"
            path.write_bytes(b"read-only")
            with (
                patch("ui_next.bridge.file_session_viewmodel.read_audio_metadata", return_value=metadata_result),
                patch("ui_next.bridge.file_session_viewmodel.read_embedded_lyrics", return_value=lyrics_result),
                patch("ui_next.bridge.file_session_viewmodel.read_cover_preview", return_value=cover_result),
            ):
                session.setCurrentFile(str(path), "audio_editor")
                self._wait_ready(session)

            self.assertEqual(str(path.resolve()), session.currentFilePath)
            self.assertEqual("音频编辑", session.currentFileSourceLabel)
            self.assertEqual("ready", session.metadataState)
            self.assertEqual("not_available", session.lyricsState)
            self.assertEqual("not_available", session.coverState)
            self.assertTrue(all(reader.started for reader in readers))
            self.assertTrue(all(reader.results for reader in readers))

            session.clearCurrentFile()
            self.assertFalse(session.hasCurrentFile)
            self.assertTrue(all(reader.cleared == 1 for reader in readers))
            self.assertFalse(path.read_bytes() != b"read-only")

    def test_disabled_capabilities_do_not_start_real_services(self):
        session = FileSessionViewModel(CapabilityGate())
        readers = (_Reader(), _Reader(), _Reader())
        session.attach_readers(*readers)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "preview.wav"
            path.write_bytes(b"preview")
            with (
                patch("ui_next.bridge.file_session_viewmodel.read_audio_metadata") as metadata,
                patch("ui_next.bridge.file_session_viewmodel.read_embedded_lyrics") as lyrics,
                patch("ui_next.bridge.file_session_viewmodel.read_cover_preview") as cover,
            ):
                session.setCurrentFile(str(path), "metadata_page")
                self.app.processEvents()
            metadata.assert_not_called()
            lyrics.assert_not_called()
            cover.assert_not_called()
            self.assertEqual("capability_disabled", session.metadataState)
            self.assertEqual("capability_disabled", session.lyricsState)
            self.assertEqual("capability_disabled", session.coverState)

    def test_editor_and_three_readonly_models_follow_the_same_session_path(self):
        gate = CapabilityGate((METADATA_READ, LYRICS_READ, COVER_READ))
        session = FileSessionViewModel(gate)
        metadata = MetadataViewModel(gate)
        lyrics = LyricsViewModel(gate)
        cover = CoverViewModel(gate)
        editor = EditorSessionViewModel(gate, file_session=session)
        session.attach_readers(metadata, lyrics, cover)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "shared.wav"
            path.write_bytes(b"shared")
            with (
                patch("ui_next.bridge.file_session_viewmodel.read_audio_metadata", return_value={"ok": True, "path": str(path), "filename": path.name}),
                patch("ui_next.bridge.file_session_viewmodel.read_embedded_lyrics", return_value={"ok": True, "path": str(path), "has_lyrics": False}),
                patch("ui_next.bridge.file_session_viewmodel.read_cover_preview", return_value={"ok": True, "path": str(path), "filename": path.name, "has_cover": False}),
            ):
                session.setCurrentFile(str(path), "audio_editor")
                self._wait_ready(session)

            for model_path in (
                editor.currentFilePath,
                metadata.currentFilePath,
                lyrics.currentFilePath,
                cover.currentFilePath,
            ):
                self.assertTrue(os.path.samefile(path, model_path))
            session.clearCurrentFile()
            self.assertFalse(editor.hasCurrentFile)
            self.assertEqual("", metadata.currentFilePath)
            self.assertEqual("", lyrics.currentFilePath)
            self.assertEqual("", cover.currentFilePath)

    def test_late_result_from_a_cannot_replace_newer_b_session(self):
        gate = CapabilityGate((METADATA_READ, LYRICS_READ, COVER_READ))
        session = FileSessionViewModel(gate)
        readers = (_Reader(), _Reader(), _Reader())
        session.attach_readers(*readers)

        def result_for(kind):
            def _read(path, *args, **kwargs):
                if Path(path).name == "a.wav":
                    time.sleep(0.12)
                return {"ok": True, "path": path, "has_basic_tags": True,
                        "has_lyrics": kind == "lyrics", "has_cover": kind == "cover"}
            return _read

        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "a.wav"
            second = Path(temp_dir) / "b.wav"
            first.write_bytes(b"a")
            second.write_bytes(b"b")
            with (
                patch("ui_next.bridge.file_session_viewmodel.read_audio_metadata", side_effect=result_for("metadata")),
                patch("ui_next.bridge.file_session_viewmodel.read_embedded_lyrics", side_effect=result_for("lyrics")),
                patch("ui_next.bridge.file_session_viewmodel.read_cover_preview", side_effect=result_for("cover")),
            ):
                session.setCurrentFile(str(first), "audio_editor")
                session.setCurrentFile(str(second), "lyrics_cover_page")
                self._wait_ready(session)
                time.sleep(0.16)
                self.app.processEvents()

            self.assertEqual(str(second.resolve()), session.currentFilePath)
            self.assertEqual("歌词", session.currentFileSourceLabel)
            for reader in readers:
                self.assertTrue(reader.results)
                self.assertEqual(str(second.resolve()), reader.results[-1]["path"])


if __name__ == "__main__":
    unittest.main()
