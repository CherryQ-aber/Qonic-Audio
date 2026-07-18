import base64
import hashlib
import os
import tempfile
import time
import unittest
import wave
from pathlib import Path
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication

from ui_next.bridge.app_state_viewmodel import AppStateViewModel
from ui_next.bridge.audio_player_viewmodel import AudioPlayerViewModel
from ui_next.bridge.capabilities import (
    AUDIO_PLAYBACK,
    COVER_READ,
    DEFAULT_USER_MODE,
    LYRICS_READ,
    METADATA_READ,
    PREVIEW_MODE,
    CapabilityGate,
)
from ui_next.bridge.edit_session import EditSessionViewModel
from ui_next.bridge.file_session_viewmodel import FileSessionViewModel


_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC"
    "AAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class EditorWorkspacePhase583Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _pump_until(self, predicate, timeout=3.0):
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.app.processEvents()
        self.assertTrue(predicate(), "等待异步编辑会话超时")

    @staticmethod
    def _wire_session(gate=None):
        gate = gate or CapabilityGate()
        file_session = FileSessionViewModel(gate)
        edit_session = EditSessionViewModel(gate)
        file_session.attach_edit_session(edit_session)
        file_session.currentFileChanged.connect(edit_session.beginCurrentFile)
        file_session.currentFileCleared.connect(edit_session.clear)
        file_session.setUnsavedChangesGuard(
            lambda: edit_session.hasUnsavedDrafts
        )
        edit_session.stateChanged.connect(
            file_session.notifyDraftStateChanged
        )
        return file_session, edit_session

    def test_supported_formats_use_registry_and_ncm_is_rejected(self):
        extensions = (
            ".mp3",
            ".flac",
            ".wav",
            ".m4a",
            ".aac",
            ".ogg",
            ".opus",
            ".ape",
            ".aiff",
            ".aif",
            ".alac",
            ".wma",
        )
        session, _edit = self._wire_session()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for extension in extensions:
                source = root / f"sample{extension}"
                source.write_bytes(extension.encode("ascii"))
                self.assertEqual(
                    "loaded",
                    session.setCurrentFile(str(source), "audio_editor"),
                    extension,
                )
                self.assertEqual(extension.lstrip("."), session.currentFileExtension)
                self.assertEqual(str(source.resolve()), session.currentFilePath)

            previous = session.currentFilePath
            ncm = root / "encrypted.ncm"
            ncm.write_bytes(b"ncm")
            self.assertEqual(
                "rejected",
                session.setCurrentFile(str(ncm), "audio_editor"),
            )
            self.assertEqual(previous, session.currentFilePath)
            self.assertIn("不受支持", session.statusMessage)

    def test_drop_decodes_special_local_path_and_rejects_ambiguous_inputs(self):
        session, _edit = self._wire_session()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            special = root / "中文 空格 # 百分% 音频.wav"
            second = root / "第二首.flac"
            unsupported = root / "封面图片.png"
            special.write_bytes(b"special")
            second.write_bytes(b"second")
            unsupported.write_bytes(b"image")

            self.assertEqual(
                "loaded",
                session.handleDroppedUrls([QUrl.fromLocalFile(str(special))]),
            )
            self.assertEqual(str(special.resolve()), session.currentFilePath)

            previous = session.currentFilePath
            self.assertEqual(
                "multiple_files_rejected",
                session.handleDroppedUrls(
                    [
                        QUrl.fromLocalFile(str(special)),
                        QUrl.fromLocalFile(str(second)),
                    ]
                ),
            )
            self.assertEqual(previous, session.currentFilePath)
            self.assertEqual(
                "unsupported_rejected",
                session.handleDroppedUrls(
                    [QUrl.fromLocalFile(str(unsupported))]
                ),
            )
            self.assertEqual(previous, session.currentFilePath)
            self.assertEqual(
                "directory_rejected",
                session.handleDroppedUrls([QUrl.fromLocalFile(str(root))]),
            )
            self.assertEqual(previous, session.currentFilePath)
            self.assertEqual(
                "non_local_rejected",
                session.handleDroppedUrls([QUrl("https://example.com/a.wav")]),
            )
            self.assertEqual(previous, session.currentFilePath)

    def test_lrc_drop_becomes_dirty_memory_draft_without_writing_sources(self):
        gate = CapabilityGate((LYRICS_READ,))
        session, edit = self._wire_session(gate)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "同名 歌曲.wav"
            lyrics = root / "同名 歌曲.lrc"
            audio.write_bytes(b"audio-source")
            lyrics.write_text("[00:01.00]第一行\n[00:02.00]第二行", encoding="utf-8")
            audio_hash = hashlib.sha256(audio.read_bytes()).hexdigest()
            lyrics_hash = hashlib.sha256(lyrics.read_bytes()).hexdigest()

            with (
                patch(
                    "ui_next.bridge.file_session_viewmodel.read_embedded_lyrics",
                    return_value={
                        "ok": True,
                        "has_lyrics": False,
                        "lyrics_text": "",
                    },
                ),
                patch(
                    "ui_next.bridge.file_session_viewmodel.read_lrc_file_preview",
                    return_value={
                        "ok": True,
                        "lyrics_text": "[00:01.00]第一行\n[00:02.00]第二行",
                    },
                ),
            ):
                result = session.handleDroppedUrls(
                    [
                        QUrl.fromLocalFile(str(audio)),
                        QUrl.fromLocalFile(str(lyrics)),
                    ]
                )
                self.assertIn(result, {"deferred", "loading"})
                self._pump_until(
                    lambda: edit.lyricsDirty and not session._lrc_workers
                )

            self.assertEqual(str(audio.resolve()), session.currentFilePath)
            self.assertEqual("manual_lrc", edit.lyricsSource)
            self.assertEqual(str(lyrics.resolve()), edit.externalLrcPath)
            self.assertTrue(edit.hasUnsavedDrafts)
            self.assertEqual(audio_hash, hashlib.sha256(audio.read_bytes()).hexdigest())
            self.assertEqual(lyrics_hash, hashlib.sha256(lyrics.read_bytes()).hexdigest())
            session.shutdown()

    def test_lrc_without_audio_and_mismatched_pair_never_auto_bind(self):
        gate = CapabilityGate((LYRICS_READ,))
        session, edit = self._wire_session(gate)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "audio.wav"
            lyrics = root / "different.lrc"
            audio.write_bytes(b"audio")
            lyrics.write_text("[00:01.00]draft", encoding="utf-8")

            self.assertEqual(
                "audio_session_missing",
                session.handleDroppedUrls([QUrl.fromLocalFile(str(lyrics))]),
            )
            self.assertFalse(session.hasCurrentFile)

            with patch(
                "ui_next.bridge.file_session_viewmodel.read_embedded_lyrics",
                return_value={"ok": True, "has_lyrics": False},
            ):
                self.assertEqual(
                    "audio_loaded_lrc_name_mismatch",
                    session.handleDroppedUrls(
                        [
                            QUrl.fromLocalFile(str(audio)),
                            QUrl.fromLocalFile(str(lyrics)),
                        ]
                    ),
                )
                self._pump_until(lambda: not session.isLoading)
            self.assertEqual(str(audio.resolve()), session.currentFilePath)
            self.assertFalse(edit.lyricsDirty)
            self.assertNotEqual("manual_lrc", edit.lyricsSource)
            session.shutdown()

    def test_dirty_guard_is_unified_and_cancel_or_discard_is_deterministic(self):
        session, edit = self._wire_session()
        confirmations = []
        session.fileChangeConfirmationRequested.connect(
            lambda: confirmations.append(session.pendingFileName)
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "a.wav"
            second = root / "b.wav"
            first.write_bytes(b"source-a")
            second.write_bytes(b"source-b")
            hashes = {
                path: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (first, second)
            }

            self.assertEqual(
                "loaded", session.setCurrentFile(str(first), "audio_editor")
            )
            edit.loadMetadataResult(
                {
                    "ok": True,
                    "path": session.currentFilePath,
                    "session_generation": session.sessionGeneration,
                    "title": "Original",
                }
            )
            edit.updateField("title", "Draft")
            edit.updateLyricsDraft("[00:01.00]Draft")
            edit.loadCoverResult(
                {
                    "ok": True,
                    "path": session.currentFilePath,
                    "session_generation": session.sessionGeneration,
                    "has_cover": True,
                    "cover_data": _ONE_PIXEL_PNG,
                    "cover_mime": "image/png",
                }
            )
            edit.removeCoverDraft()
            self.assertEqual(
                ["Metadata", "Lyrics", "Cover"],
                edit.unsavedDraftLabels,
            )

            self.assertEqual(
                "confirmation_required",
                session.setCurrentFile(str(second), "file_browser"),
            )
            self.assertEqual(1, len(confirmations))
            session.cancelPendingFileChange()
            self.assertEqual(str(first.resolve()), session.currentFilePath)
            self.assertTrue(edit.hasUnsavedDrafts)

            self.assertEqual(
                "confirmation_required",
                session.setCurrentFile(str(second), "file_browser"),
            )
            session.discardPendingFileChange()
            self.assertEqual(str(second.resolve()), session.currentFilePath)
            self.assertFalse(edit.hasUnsavedDrafts)
            self.assertEqual(session.sessionGeneration, edit.sessionGeneration)
            for path, source_hash in hashes.items():
                self.assertEqual(
                    source_hash,
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )

    def test_same_file_noop_preserves_drafts_and_stale_results_are_ignored(self):
        session, edit = self._wire_session()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "a.wav"
            second = root / "b.wav"
            first.write_bytes(b"a")
            second.write_bytes(b"b")
            session.setCurrentFile(str(first), "audio_editor")
            generation_a = session.sessionGeneration
            edit.loadMetadataResult(
                {
                    "ok": True,
                    "path": session.currentFilePath,
                    "session_generation": generation_a,
                    "title": "A",
                }
            )
            edit.updateField("title", "A draft")
            self.assertEqual(
                "unchanged",
                session.setCurrentFile(str(first), "drag_drop"),
            )
            self.assertEqual("A draft", edit.draftMetadata["title"])

            edit.restoreOriginal()
            session.setCurrentFile(str(second), "audio_editor")
            generation_b = session.sessionGeneration
            edit.loadMetadataResult(
                {
                    "ok": True,
                    "path": str(first.resolve()),
                    "session_generation": generation_a,
                    "title": "late A",
                }
            )
            edit.loadLyricsResult(
                {
                    "ok": True,
                    "path": str(first.resolve()),
                    "session_generation": generation_a,
                    "has_lyrics": True,
                    "lyrics_text": "late A",
                }
            )
            self.assertEqual(generation_b, edit.sessionGeneration)
            self.assertEqual(str(second.resolve()), edit.sourcePath)
            self.assertNotEqual("late A", edit.draftMetadata.get("title"))
            self.assertNotEqual("late A", edit.draftLyrics)

    def test_page_switch_preserves_session_and_missing_state_invalidates_workers(self):
        session, edit = self._wire_session()
        app_state = AppStateViewModel(CapabilityGate())
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "page-switch.wav"
            source.write_bytes(b"source")
            session.setCurrentFile(str(source), "audio_editor")
            original_path = session.currentFilePath
            original_generation = session.sessionGeneration

            for module in (
                "metadata",
                "lyricsCover",
                "audioProcessing",
                "settings",
                "autoConvert",
                "audioEditor",
            ):
                app_state.setCurrentModule(module)
                self.assertEqual(original_path, session.currentFilePath)
                self.assertEqual(original_generation, session.sessionGeneration)

            edit.updateLyricsDraft("draft remains in memory")
            source.unlink()
            session.markCurrentFileMissing()
            self.assertEqual("missing", session.sessionState)
            self.assertGreater(session.sessionGeneration, original_generation)
            self.assertTrue(edit.hasUnsavedDrafts)

    def test_real_qt_player_releases_windows_file_handle_and_restores_session(self):
        gate = CapabilityGate(
            (AUDIO_PLAYBACK,),
            runtime_mode=DEFAULT_USER_MODE,
        )
        session = FileSessionViewModel(gate)
        player = AudioPlayerViewModel(session, gate)
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "release test 中文.wav"
            with wave.open(str(source), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(8_000)
                output.writeframes(b"\x00\x00" * 4_000)
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()

            self.assertEqual(
                "loaded",
                session.setCurrentFile(str(source), "audio_editor"),
            )
            self._pump_until(
                lambda: player.playerState in {"ready", "error"},
                timeout=5.0,
            )
            self.assertEqual("ready", player.playerState, player.error)
            self.assertGreater(player.duration, 0)
            self.assertTrue(player.releaseMediaSource())
            self.assertTrue(player.mediaSourceReleased)
            self.app.processEvents()

            moved = source.with_name("renamed while released.wav")
            source.rename(moved)
            moved.rename(source)
            self.assertEqual(str(source.resolve()), session.currentFilePath)
            self.assertTrue(player.restorePlaybackSource())
            self.assertEqual("loading", player.playerState)

            player.shutdown()
            session.shutdown()
            self.app.processEvents()
            moved_after_shutdown = source.with_name("renamed after shutdown.wav")
            source.rename(moved_after_shutdown)
            moved_after_shutdown.rename(source)
            self.assertEqual(
                source_hash,
                hashlib.sha256(source.read_bytes()).hexdigest(),
            )

    def test_preview_mode_never_reads_audio_or_lrc_even_if_caps_are_requested(self):
        gate = CapabilityGate(
            (METADATA_READ, LYRICS_READ, COVER_READ),
            runtime_mode=PREVIEW_MODE,
        )
        session, _edit = self._wire_session(gate)
        with tempfile.TemporaryDirectory() as temp_dir:
            audio = Path(temp_dir) / "preview.wav"
            lyrics = Path(temp_dir) / "preview.lrc"
            audio.write_bytes(b"preview")
            lyrics.write_text("[00:01.00]preview", encoding="utf-8")
            with (
                patch(
                    "ui_next.bridge.file_session_viewmodel.read_audio_metadata"
                ) as metadata,
                patch(
                    "ui_next.bridge.file_session_viewmodel.read_embedded_lyrics"
                ) as embedded,
                patch(
                    "ui_next.bridge.file_session_viewmodel.read_cover_preview"
                ) as cover,
                patch(
                    "ui_next.bridge.file_session_viewmodel.read_lrc_file_preview"
                ) as lrc,
            ):
                self.assertEqual(
                    "loaded",
                    session.setCurrentFile(str(audio), "audio_editor"),
                )
                self.assertEqual(
                    "capability_denied",
                    session.importLyricsFile(str(lyrics)),
                )
                self.app.processEvents()
            metadata.assert_not_called()
            embedded.assert_not_called()
            cover.assert_not_called()
            lrc.assert_not_called()
            self.assertEqual("capability_disabled", session.metadataState)
            self.assertEqual("capability_disabled", session.lyricsState)
            self.assertEqual("capability_disabled", session.coverState)


if __name__ == "__main__":
    unittest.main()
