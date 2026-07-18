import hashlib
import os
import tempfile
import time
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ui_next.bridge.capabilities import COVER_READ, COVER_WRITE, LYRICS_WRITE, METADATA_WRITE, CapabilityGate
from ui_next.bridge.cover_validation import MAX_COVER_FILE_BYTES, validate_cover_bytes
from ui_next.bridge.edit_session import EditSessionViewModel
from ui_next.bridge.edit_export_service import EditExportRequest, EditExportService
from ui_next.bridge.file_session_viewmodel import FileSessionViewModel


class EditSessionCoverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def _image_bytes(image_format="PNG", size=(6, 4), color=(10, 40, 80)):
        image = Image.new("RGB", size, color)
        output = BytesIO()
        image.save(output, format=image_format)
        return output.getvalue()

    @classmethod
    def _cover_result(cls, path, data=None, mime="image/png"):
        data = cls._image_bytes() if data is None else data
        checked = validate_cover_bytes(data)
        return {
            "ok": True,
            "path": str(path),
            "has_cover": bool(data),
            "cover_data": data,
            "cover_mime": mime,
            "mime": mime,
            "byte_size": len(data),
            "width": checked.get("width", 0),
            "height": checked.get("height", 0),
            "preview_data_url": checked.get("preview_data_url", ""),
        }

    def _wait_cover(self, session, timeout=2.0):
        deadline = time.monotonic() + timeout
        while session.coverExporting and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.app.processEvents()
        self.assertFalse(session.coverExporting)

    def test_original_replace_remove_restore_are_memory_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.flac"
            source.write_bytes(b"audio")
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            original = self._image_bytes("PNG")
            replacement = self._image_bytes("JPEG", color=(80, 40, 10))
            session = EditSessionViewModel(CapabilityGate((COVER_READ,)))
            session.beginCurrentFile(str(source), 1)
            session.loadCoverResult(self._cover_result(source, original))
            self.assertTrue(session.hasOriginalCover)
            self.assertEqual("keep", session.coverAction)
            self.assertFalse(session.coverDirty)

            with patch("ui_next.bridge.edit_session.QFileDialog.getOpenFileName") as dialog:
                image_path = Path(temp_dir) / "replacement.jpg"
                image_path.write_bytes(replacement)
                dialog.return_value = (str(image_path), "JPEG")
                session.chooseReplacementCover()
            self.assertEqual("replace", session.coverAction)
            self.assertTrue(session.coverDirty)
            self.assertEqual("image/jpeg", session.draftCoverMime)
            self.assertEqual(source_hash, hashlib.sha256(source.read_bytes()).hexdigest())

            session.removeCoverDraft()
            self.assertEqual("remove", session.coverAction)
            self.assertTrue(session.coverDirty)
            session.restoreOriginalCover()
            self.assertEqual("keep", session.coverAction)
            self.assertFalse(session.coverDirty)
            self.assertEqual(source_hash, hashlib.sha256(source.read_bytes()).hexdigest())

    def test_no_cover_and_cover_read_failure_are_distinct(self):
        session = EditSessionViewModel(CapabilityGate((COVER_READ,)))
        session.beginCurrentFile("D:/CherryQ_Test/no-cover.flac", 1)
        session.loadCoverResult({"ok": True, "path": "D:/CherryQ_Test/no-cover.flac", "has_cover": False})
        self.assertEqual("no_cover", session.coverEditState)
        self.assertFalse(session.hasOriginalCover)
        session.removeCoverDraft()
        self.assertFalse(session.coverDirty)
        session.loadCoverResult({"ok": False, "path": "D:/CherryQ_Test/no-cover.flac", "error": "damaged"})
        self.assertEqual("error", session.coverEditState)
        self.assertEqual("damaged", session.coverValidationError)

    def test_image_validation_accepts_jpeg_png_and_rejects_other_or_damaged_content(self):
        self.assertTrue(validate_cover_bytes(self._image_bytes("PNG"))["ok"])
        self.assertTrue(validate_cover_bytes(self._image_bytes("JPEG"))["ok"])
        gif = BytesIO()
        Image.new("RGB", (2, 2)).save(gif, format="GIF")
        self.assertEqual("cover_format_unsupported", validate_cover_bytes(gif.getvalue())["error_code"])
        webp = BytesIO()
        Image.new("RGB", (2, 2)).save(webp, format="WEBP")
        self.assertEqual("cover_format_unsupported", validate_cover_bytes(webp.getvalue())["error_code"])
        self.assertEqual("cover_decode_failed", validate_cover_bytes(b"not an image")["error_code"])
        self.assertEqual("cover_file_too_large", validate_cover_bytes(b"x" * (MAX_COVER_FILE_BYTES + 1))["error_code"])

    def test_content_validation_does_not_trust_filename_extension(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.flac"
            source.write_bytes(b"audio")
            png_named_jpg = root / "photo.jpg"
            png_named_jpg.write_bytes(self._image_bytes("PNG"))
            session = EditSessionViewModel(CapabilityGate((COVER_READ,)))
            session.loadCoverResult(self._cover_result(source, b""))
            with patch("ui_next.bridge.edit_session.QFileDialog.getOpenFileName", return_value=(str(png_named_jpg), "JPEG")):
                session.chooseReplacementCover()
            self.assertEqual("image/png", session.draftCoverMime)

    def test_qml_cover_editor_never_imports_or_calls_writer_directly(self):
        project = Path(__file__).resolve().parents[1]
        source = "\n".join(
            (project / path).read_text(encoding="utf-8")
            for path in (
                "ui_next/qml/pages/MetadataPage.qml",
                "ui_next/qml/components/CoverDraftEditor.qml",
            )
        )
        self.assertNotIn("write_audio_cover", source)
        self.assertNotIn("remove_audio_cover", source)
        self.assertNotIn("EditExportService", source)
        self.assertNotIn("import metadata", source)

    def test_failed_new_image_keeps_previous_valid_draft(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.flac"
            source.write_bytes(b"audio")
            valid = Path(temp_dir) / "valid.png"
            valid.write_bytes(self._image_bytes("PNG"))
            invalid = Path(temp_dir) / "pretend.png"
            invalid.write_bytes(b"not png")
            session = EditSessionViewModel(CapabilityGate((COVER_READ,)))
            session.beginCurrentFile(str(source), 1)
            session.loadCoverResult(self._cover_result(source, b""))
            with patch("ui_next.bridge.edit_session.QFileDialog.getOpenFileName", return_value=(str(valid), "PNG")):
                session.chooseReplacementCover()
            previous = session.draftCoverPreviewUrl
            with patch("ui_next.bridge.edit_session.QFileDialog.getOpenFileName", return_value=(str(invalid), "PNG")):
                session.chooseReplacementCover()
            self.assertTrue(session.coverDirty)
            self.assertEqual(previous, session.draftCoverPreviewUrl)
            self.assertEqual("error", session.coverValidationState)
            self.assertIn("无法解码", session.coverValidationError)

    def test_file_switch_is_protected_by_cover_draft(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first, second = Path(temp_dir) / "a.wav", Path(temp_dir) / "b.wav"
            first.write_bytes(b"a")
            second.write_bytes(b"b")
            file_session = FileSessionViewModel(CapabilityGate())
            file_session.setCurrentFile(str(first))
            session = EditSessionViewModel(CapabilityGate())
            session.beginCurrentFile(str(first), 1)
            session.loadCoverResult(self._cover_result(first, b""))
            image_path = Path(temp_dir) / "draft.png"
            image_path.write_bytes(self._image_bytes())
            with patch("ui_next.bridge.edit_session.QFileDialog.getOpenFileName", return_value=(str(image_path), "PNG")):
                session.chooseReplacementCover()
            file_session.setUnsavedChangesGuard(lambda: session.hasUnsavedDrafts)
            file_session.setCurrentFile(str(second))
            self.assertTrue(file_session.hasPendingFileChange)
            self.assertEqual(str(first.resolve()), file_session.currentFilePath)
            file_session.discardPendingFileChange()
            session.beginCurrentFile(str(second), 2)
            self.assertFalse(session.coverDirty)
            self.assertEqual(str(second.resolve()), file_session.currentFilePath)

    def test_cover_write_denied_before_temporary_copy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source, output = root / "source.flac", root / "edited.flac"
            source.write_bytes(b"audio")
            session = EditSessionViewModel(CapabilityGate((COVER_READ,)))
            session.beginCurrentFile(str(source), 1)
            session.loadCoverResult(self._cover_result(source, b""))
            image_path = root / "draft.png"
            image_path.write_bytes(self._image_bytes())
            with patch("ui_next.bridge.edit_session.QFileDialog.getOpenFileName", return_value=(str(image_path), "PNG")):
                session.chooseReplacementCover()
            with patch("ui_next.bridge.edit_export_service.shutil.copy2") as copy:
                session.exportCoverToAudioPath(str(output))
                self._wait_cover(session)
            self.assertEqual("capability_denied", session.lastCoverExportResult["error_code"])
            copy.assert_not_called()
            self.assertFalse(output.exists())

    def test_cover_export_request_can_include_all_dirty_modules_without_source_replacement(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source, output = root / "source.flac", root / "all.flac"
            source.write_bytes(b"audio")
            requests = []

            class Exporter:
                def export(self, request):
                    requests.append(request)
                    Path(request.output_path).write_bytes(Path(request.source_path).read_bytes())
                    return {"success": True, "output_path": request.output_path, "message": "ok"}

            session = EditSessionViewModel(
                CapabilityGate((COVER_READ, COVER_WRITE, LYRICS_WRITE, METADATA_WRITE)),
                export_service=Exporter(),
            )
            session.loadMetadataResult({"ok": True, "path": str(source), "title": "old"})
            session.updateField("title", "new")
            session.loadLyricsResult({"ok": True, "path": str(source), "has_lyrics": True, "lyrics_text": "old lyric"})
            session.updateLyricsDraft("new lyric")
            image_path = root / "draft.png"
            image_path.write_bytes(self._image_bytes())
            with patch("ui_next.bridge.edit_session.QFileDialog.getOpenFileName", return_value=(str(image_path), "PNG")):
                session.chooseReplacementCover()
            session.exportCoverToAudioPath(str(output), True, True)
            self._wait_cover(session)
            self.assertTrue(session.lastCoverExportResult["success"])
            self.assertEqual("new", requests[0].metadata_changes["title"])
            self.assertEqual("new lyric", requests[0].lyrics_text)
            self.assertEqual("replace", requests[0].cover_action)
            self.assertEqual(str(source), session.sourcePath)
            self.assertTrue(session.dirty)
            self.assertTrue(session.lyricsDirty)
            self.assertTrue(session.coverDirty)

    def test_cover_export_service_rejects_existing_target_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source, output = root / "source.flac", root / "exists.flac"
            source.write_bytes(b"audio")
            output.write_bytes(b"existing")
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            request = {
                "source_path": str(source), "output_path": str(output), "cover_action": "remove",
            }
            result = EditExportService(CapabilityGate((COVER_WRITE,))).export(EditExportRequest(**request))
            self.assertEqual("output_exists", result["error_code"])
            self.assertEqual(source_hash, hashlib.sha256(source.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
