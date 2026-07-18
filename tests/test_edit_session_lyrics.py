import hashlib
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ui_next.bridge.capabilities import LYRICS_READ, LYRICS_WRITE, METADATA_WRITE, CapabilityGate
from ui_next.bridge.edit_session import EditSessionViewModel
from ui_next.bridge.edit_export_service import EditExportService
from ui_next.bridge.file_session_viewmodel import FileSessionViewModel


class EditSessionLyricsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def _result(path: str, *, embedded="[00:01.00]Embedded", external="[00:02.00]Sibling"):
        return {
            "ok": True,
            "path": path,
            "has_lyrics": bool(embedded),
            "lyrics_text": embedded,
            "has_timestamps": True,
            "external_lrc_path": str(Path(path).with_suffix(".lrc")),
            "external_lrc_result": {
                "ok": bool(external), "lyrics_text": external,
                "has_timestamps": bool(external), "encoding": "UTF-8",
            },
        }

    def _wait(self, edit_session, timeout=2.0):
        deadline = time.monotonic() + timeout
        while edit_session.lyricsExporting and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.app.processEvents()
        self.assertFalse(edit_session.lyricsExporting)

    def test_embedded_and_sibling_are_separate_and_embedded_is_default(self):
        session = EditSessionViewModel(CapabilityGate((LYRICS_READ,)))
        session.loadLyricsResult(self._result("D:/CherryQ_Test/demo.flac"))
        self.assertEqual("embedded", session.selectedLyricsSource)
        self.assertEqual("[00:01.00]Embedded", session.originalLyrics)
        self.assertTrue(session.hasEmbeddedLyricsSource)
        self.assertTrue(session.hasSiblingLrcSource)
        self.assertNotEqual(
            session.availableLyricsSources["embedded"]["text"],
            session.availableLyricsSources["sibling_lrc"]["text"],
        )
        self.assertEqual("ok", session.selectLyricsSource("sibling_lrc"))
        self.assertEqual("[00:02.00]Sibling", session.originalLyrics)

    def test_only_sibling_lrc_and_manual_lrc_stay_in_memory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "source.flac"
            original_lrc = root / "source.lrc"
            manual_lrc = root / "manual.lrc"
            audio.write_bytes(b"audio")
            original_lrc.write_text("[00:01.00]Sibling", encoding="utf-8")
            manual_lrc.write_text("manual lyric\n第二行", encoding="utf-8")
            audio_hash = hashlib.sha256(audio.read_bytes()).hexdigest()
            lrc_hash = hashlib.sha256(original_lrc.read_bytes()).hexdigest()
            session = EditSessionViewModel(CapabilityGate((LYRICS_READ,)))
            session.loadLyricsResult(self._result(str(audio), embedded="", external="[00:01.00]Sibling"))
            self.assertEqual("sibling_lrc", session.selectedLyricsSource)
            with patch("ui_next.bridge.edit_session.QFileDialog.getOpenFileName", return_value=(str(manual_lrc), "LRC")):
                self.assertEqual("ok", session.chooseManualLrc())
            self.assertEqual("manual_lrc", session.selectedLyricsSource)
            session.updateLyricsDraft("manual changed")
            self.assertEqual(audio_hash, hashlib.sha256(audio.read_bytes()).hexdigest())
            self.assertEqual(lrc_hash, hashlib.sha256(original_lrc.read_bytes()).hexdigest())

    def test_dirty_restore_clear_and_source_switch_protection(self):
        session = EditSessionViewModel(CapabilityGate((LYRICS_READ,)))
        session.loadLyricsResult(self._result("D:/CherryQ_Test/demo.flac"))
        session.updateLyricsDraft("changed")
        self.assertTrue(session.lyricsDirty)
        self.assertEqual("unsaved_changes", session.selectLyricsSource("sibling_lrc"))
        session.restoreOriginalLyrics()
        self.assertFalse(session.lyricsDirty)
        session.clearLyricsDraft()
        self.assertTrue(session.lyricsDirty)
        self.assertFalse(session._check_lyrics_exportable())
        self.assertEqual("lyrics_draft_empty", session.lastLyricsExportResult["error_code"])

    def test_timestamp_insert_targets_selection_start_line_and_preserves_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "source.flac"
            lrc = root / "source.lrc"
            audio.write_bytes(b"audio")
            original_text = (
                "first\r\n"
                "[00:00.10][00:00.20]second\r\n"
                "third"
            )
            lrc.write_text(original_text, encoding="utf-8", newline="")
            audio_hash = hashlib.sha256(audio.read_bytes()).hexdigest()
            lrc_hash = hashlib.sha256(lrc.read_bytes()).hexdigest()
            session = EditSessionViewModel(CapabilityGate((LYRICS_READ,)))
            session.loadLyricsResult(
                self._result(
                    str(audio),
                    embedded=original_text,
                    external=original_text,
                )
            )
            selection_start = original_text.index("second") + 2
            selection_end = original_text.index("third") + 3

            result = session.insertLyricsTimestamp(
                selection_start,
                selection_end,
                selection_end,
                3_753_450,
                "centisecond",
            )

            expected = (
                "first\r\n"
                "[62:33.45][00:00.20]second\r\n"
                "third"
            )
            self.assertTrue(result["ok"])
            self.assertTrue(result["changed"])
            self.assertEqual("[62:33.45]", result["timestamp"])
            self.assertEqual(expected, session.draftLyrics)
            self.assertTrue(session.lyricsDirty)
            self.assertEqual(
                original_text[selection_start:selection_end],
                expected[result["selection_start"]:result["selection_end"]],
            )
            self.assertEqual(audio_hash, hashlib.sha256(audio.read_bytes()).hexdigest())
            self.assertEqual(lrc_hash, hashlib.sha256(lrc.read_bytes()).hexdigest())
            self.assertIn("仅更新内存歌词草稿", session.statusMessage)

    def test_timestamp_insert_adds_prefix_without_newline(self):
        original_text = "first\nsecond\nthird"
        session = EditSessionViewModel(CapabilityGate((LYRICS_READ,)))
        session.loadLyricsResult(
            self._result(
                "D:/CherryQ_Test/demo.flac",
                embedded=original_text,
                external="",
            )
        )
        cursor_position = original_text.index("second") + 2

        result = session.insertLyricsTimestamp(
            cursor_position,
            cursor_position,
            cursor_position,
            201_450,
        )

        self.assertEqual(
            "first\n[03:21.450]second\nthird",
            session.draftLyrics,
        )
        self.assertEqual(2, session.draftLyrics.count("\n"))
        self.assertEqual(
            cursor_position + len("[03:21.450]"),
            result["cursor_position"],
        )

    def test_timestamp_insert_without_editor_session_is_rejected(self):
        session = EditSessionViewModel(CapabilityGate((LYRICS_READ,)))

        result = session.insertLyricsTimestamp(0, 0, 0, 201_450)

        self.assertFalse(result["ok"])
        self.assertEqual("", session.draftLyrics)
        self.assertIn("没有可插入", session.statusMessage)

    def test_file_session_blocks_dirty_lyrics_switch_until_confirmed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first, second = root / "a.wav", root / "b.wav"
            first.write_bytes(b"a")
            second.write_bytes(b"b")
            dirty = {"value": False}
            session = FileSessionViewModel(CapabilityGate())
            session.setUnsavedChangesGuard(lambda: dirty["value"])
            session.setCurrentFile(str(first), "audio_editor")
            dirty["value"] = True
            session.setCurrentFile(str(second), "lyrics_cover_page")
            self.assertTrue(session.hasPendingFileChange)
            self.assertEqual(str(first.resolve()), session.currentFilePath)
            generation = session.sessionGeneration
            session.reloadCurrentFile()
            self.assertEqual(generation, session.sessionGeneration)
            self.assertIn("已阻止重新读取", session.statusMessage)
            session.cancelPendingFileChange()
            self.assertEqual(str(first.resolve()), session.currentFilePath)
            session.setCurrentFile(str(second), "lyrics_cover_page")
            session.discardPendingFileChange()
            self.assertEqual(str(second.resolve()), session.currentFilePath)

    def test_lyrics_write_denied_creates_no_temp_or_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source, output = root / "source.flac", root / "edited.flac"
            source.write_bytes(b"audio")
            session = EditSessionViewModel(CapabilityGate((LYRICS_READ,)))
            session.loadLyricsResult(self._result(str(source)))
            session.updateLyricsDraft("edited lyric")
            with patch("ui_next.bridge.edit_export_service.shutil.copy2") as copy:
                session.exportLyricsToAudioPath(str(output), False)
                self._wait(session)
            self.assertEqual("capability_denied", session.lastLyricsExportResult["error_code"])
            copy.assert_not_called()
            self.assertFalse(output.exists())

    def test_audio_export_can_combine_metadata_and_lyrics_without_source_replacement(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source, output = root / "source.flac", root / "edited.flac"
            source.write_bytes(b"audio")
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            calls = []

            class Exporter:
                def export(self, request):
                    calls.append(request)
                    Path(request.output_path).write_bytes(Path(request.source_path).read_bytes())
                    return {"success": True, "output_path": request.output_path, "message": "ok"}

            session = EditSessionViewModel(
                CapabilityGate((LYRICS_READ, LYRICS_WRITE, METADATA_WRITE)),
                export_service=Exporter(),
            )
            session.loadMetadataResult({"ok": True, "path": str(source), "title": "Old", "artist": "Artist"})
            session.updateField("title", "New")
            session.loadLyricsResult(self._result(str(source)))
            session.updateLyricsDraft("[00:03.00]Edited")
            session.exportLyricsToAudioPath(str(output), True)
            self._wait(session)
            self.assertTrue(session.lastLyricsExportResult["success"])
            self.assertEqual("New", calls[0].metadata_changes["title"])
            self.assertEqual("[00:03.00]Edited", calls[0].lyrics_text)
            self.assertEqual(source_hash, hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual(str(source), session.sourcePath)

    def test_combined_export_requires_every_write_capability_before_copy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source, output = root / "source.flac", root / "edited.flac"
            source.write_bytes(b"audio")
            session = EditSessionViewModel(
                CapabilityGate((LYRICS_READ, LYRICS_WRITE)),
                export_service=EditExportService(CapabilityGate((LYRICS_WRITE,))),
            )
            session.loadMetadataResult({"ok": True, "path": str(source), "title": "Old"})
            session.updateField("title", "New")
            session.loadLyricsResult(self._result(str(source)))
            session.updateLyricsDraft("edited lyric")
            with patch("ui_next.bridge.edit_export_service.shutil.copy2") as copy:
                session.exportLyricsToAudioPath(str(output), True)
                self._wait(session)
            self.assertEqual("capability_denied", session.lastLyricsExportResult["error_code"])
            copy.assert_not_called()
            self.assertFalse(output.exists())

    def test_lrc_export_is_utf8_no_clobber_and_keeps_original_lrc(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source, original, output = root / "source.flac", root / "source.lrc", root / "new.lrc"
            source.write_bytes(b"audio")
            original.write_text("original", encoding="utf-8")
            original_hash = hashlib.sha256(original.read_bytes()).hexdigest()
            service = EditExportService(CapabilityGate((LYRICS_WRITE,)))
            session = EditSessionViewModel(CapabilityGate((LYRICS_READ, LYRICS_WRITE)), export_service=service)
            session.loadLyricsResult(self._result(str(source), embedded="", external="original"))
            session.updateLyricsDraft("[00:01.00]新的歌词")
            session.exportLyricsToLrcPath(str(output))
            self._wait(session)
            self.assertTrue(session.lastLyricsExportResult["success"], session.lastLyricsExportResult)
            self.assertEqual("[00:01.00]新的歌词", output.read_text(encoding="utf-8"))
            self.assertEqual(original_hash, hashlib.sha256(original.read_bytes()).hexdigest())
            session.exportLyricsToLrcPath(str(output))
            self._wait(session)
            self.assertEqual("lrc_output_exists", session.lastLyricsExportResult["error_code"])


if __name__ == "__main__":
    unittest.main()
