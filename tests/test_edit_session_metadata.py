import hashlib
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ui_next.bridge.capabilities import METADATA_READ, METADATA_WRITE, CapabilityGate
from ui_next.bridge.edit_session import EditSessionViewModel
from ui_next.bridge.edit_export_service import EditExportService
from ui_next.bridge.metadata_viewmodel import MetadataViewModel


class EditSessionMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def _metadata(path: str) -> dict:
        return {
            "ok": True,
            "path": path,
            "title": "Original title",
            "artist": "Original artist",
            "album": "Original album",
            "albumartist": "Original album artist",
            "date": "2026",
            "genre": "Pop",
            "tracknumber": "2/10",
            "discnumber": "1/1",
            "bpm": "128",
            "initialkey": "Am",
            "comment": "Original comment",
        }

    def _wait_export(self, session: EditSessionViewModel, timeout: float = 2.0):
        deadline = time.monotonic() + timeout
        while session.exporting and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.app.processEvents()
        self.assertFalse(session.exporting)

    def test_creates_draft_updates_only_memory_and_restores_original(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.flac"
            source.write_bytes(b"source-bytes")
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            session = EditSessionViewModel(CapabilityGate((METADATA_READ,)))
            session.loadMetadataResult(self._metadata(str(source)))

            self.assertTrue(session.hasSession)
            self.assertEqual(session.originalMetadata, session.draftMetadata)
            self.assertFalse(session.dirty)
            session.updateField("title", "Draft title")
            session.updateField("albumartist", "Draft album artist")
            self.assertTrue(session.dirty)
            self.assertEqual(["title", "albumartist"], session.changedFields)
            self.assertEqual(source_hash, hashlib.sha256(source.read_bytes()).hexdigest())
            session.saveDraft()
            self.assertIn("内存", session.statusMessage)
            self.assertEqual(source_hash, hashlib.sha256(source.read_bytes()).hexdigest())

            session.restoreOriginal()
            self.assertFalse(session.dirty)
            self.assertEqual(session.originalMetadata, session.draftMetadata)
            self.assertEqual(source_hash, hashlib.sha256(source.read_bytes()).hexdigest())

    def test_metadata_viewmodel_read_result_creates_and_file_change_clears_draft(self):
        session = EditSessionViewModel(CapabilityGate((METADATA_READ,)))
        metadata = MetadataViewModel(CapabilityGate((METADATA_READ,)))
        metadata.metadataReadApplied.connect(session.loadMetadataResult)
        result = self._metadata("D:/CherryQ_Test/source.flac")
        metadata.applySessionReadResult(result)
        self.assertEqual(result["path"], session.sourcePath)
        self.assertEqual("Original title", session.draftMetadata["title"])
        session.updateField("title", "Draft")
        session.beginCurrentFile("D:/CherryQ_Test/new.flac", 2)
        self.assertTrue(session.hasSession)
        self.assertEqual("D:/CherryQ_Test/new.flac", session.sourcePath)
        self.assertEqual(2, session.sessionGeneration)
        self.assertEqual({}, session.draftMetadata)
        self.assertFalse(session.dirty)

    def test_preview_and_metadata_read_only_refuse_export_without_temp_copy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.flac"
            output = root / "edited.flac"
            source.write_bytes(b"source-bytes")
            for gate in (CapabilityGate(), CapabilityGate((METADATA_READ,))):
                session = EditSessionViewModel(gate)
                session.loadMetadataResult(self._metadata(str(source)))
                session.updateField("title", "Draft title")
                with patch("ui_next.bridge.edit_export_service.shutil.copy2") as copy:
                    session.exportDraftToPath(str(output))
                    self._wait_export(session)
                self.assertEqual("capability_denied", session.lastExportResult["error_code"])
                copy.assert_not_called()
                self.assertFalse(output.exists())
                self.assertFalse(list(root.glob(".*.cherryq_edit_*.tmp.flac")))

    def test_authorized_export_preserves_source_and_writes_complete_draft(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.flac"
            output = root / "edited.flac"
            source.write_bytes(b"source-bytes")
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            stored = {"metadata": self._metadata(str(source))}

            def metadata_read(path, include_cover=False):
                return {"ok": True, "path": path, **stored["metadata"]}

            def metadata_write(_path, values, overwrite=True):
                stored["metadata"].update(values)
                return {"success": True}

            session = EditSessionViewModel(
                CapabilityGate((METADATA_READ, METADATA_WRITE)),
                export_service=EditExportService(CapabilityGate((METADATA_WRITE,))),
            )
            session.loadMetadataResult(self._metadata(str(source)))
            session.updateField("title", "Exported title")
            session.updateField("comment", "Exported comment")
            with (
                patch("ui_next.bridge.edit_export_service.read_audio_metadata", side_effect=metadata_read),
                patch("ui_next.bridge.edit_export_service.write_audio_metadata", side_effect=metadata_write),
            ):
                session.exportDraftToPath(str(output))
                self._wait_export(session)

            self.assertTrue(session.lastExportResult["success"], session.lastExportResult)
            self.assertTrue(output.exists())
            self.assertEqual(source_hash, hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual("Exported title", stored["metadata"]["title"])
            self.assertEqual("Exported comment", stored["metadata"]["comment"])
            self.assertEqual("Original artist", stored["metadata"]["artist"])
            self.assertEqual(str(source), session.sourcePath)
            self.assertTrue(session.dirty, "成功导出不会自动替换当前源文件或清空草稿")

    def test_output_conflict_leaves_existing_output_and_source_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.flac"
            output = root / "existing.flac"
            source.write_bytes(b"source-bytes")
            output.write_bytes(b"existing-output")
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            output_hash = hashlib.sha256(output.read_bytes()).hexdigest()
            session = EditSessionViewModel(CapabilityGate((METADATA_WRITE,)))
            session.loadMetadataResult(self._metadata(str(source)))
            session.updateField("title", "Draft title")
            session.exportDraftToPath(str(output))
            self._wait_export(session)
            self.assertEqual(
                "overwrite_confirmation_required",
                session.lastExportResult["error_code"],
            )
            self.assertEqual(source_hash, hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual(output_hash, hashlib.sha256(output.read_bytes()).hexdigest())

    def test_draft_and_preview_export_do_not_change_config_or_watcher(self):
        project = Path(__file__).resolve().parents[1]
        config_path = project / "config.json"
        watcher_path = project / "watcher.py"
        config_hash = hashlib.sha256(config_path.read_bytes()).hexdigest()
        watcher_hash = hashlib.sha256(watcher_path.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.flac"
            source.write_bytes(b"source-bytes")
            session = EditSessionViewModel(CapabilityGate())
            session.loadMetadataResult(self._metadata(str(source)))
            session.updateField("title", "Draft title")
            session.exportDraftToPath(str(Path(temp_dir) / "blocked.flac"))
            self._wait_export(session)
        self.assertEqual(config_hash, hashlib.sha256(config_path.read_bytes()).hexdigest())
        self.assertEqual(watcher_hash, hashlib.sha256(watcher_path.read_bytes()).hexdigest())

    def test_qml_never_imports_or_calls_metadata_writer_directly(self):
        project = Path(__file__).resolve().parents[1]
        source = "\n".join(
            (project / path).read_text(encoding="utf-8")
            for path in (
                "ui_next/qml/pages/MetadataPage.qml",
                "ui_next/qml/components/MetadataForm.qml",
            )
        )
        self.assertNotIn("write_audio_metadata", source)
        self.assertNotIn("import metadata", source)
        self.assertNotIn("EditExportService", source)


if __name__ == "__main__":
    unittest.main()
