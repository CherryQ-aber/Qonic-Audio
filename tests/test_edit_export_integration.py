import os
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ui_next.bridge.capabilities import COVER_WRITE, LYRICS_WRITE, METADATA_WRITE, CapabilityGate
from ui_next.bridge.edit_session import EditSessionViewModel


class _RecordingExportService:
    def __init__(self):
        self.requests = []

    def export(self, request):
        self.requests.append(request)
        return {
            "success": True,
            "message": "已安全导出编辑副本；原文件未修改。",
            "output_path": request.output_path,
            "applied_operations": list(request.requested_operations()),
            "finalization_strategy": "exclusive_copy",
            "verification_success": True,
        }


def _metadata(path: str) -> dict:
    return {
        "ok": True,
        "path": path,
        "title": "Original",
        "artist": "Artist",
        "album": "Album",
        "date": "2026",
        "genre": "Pop",
    }


def _wait(app, session, timeout=2.0):
    deadline = time.monotonic() + timeout
    while session.unifiedExporting and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()
    assert not session.unifiedExporting


def _session(gate, service, source):
    session = EditSessionViewModel(gate, export_service=service)
    session.loadMetadataResult(_metadata(str(source)))
    session.updateField("title", "Edited title")
    session.loadLyricsResult({"ok": True, "path": str(source), "lyrics_text": "[00:01.00]Original"})
    session.updateLyricsDraft("[00:01.00]Edited")
    return session


def test_preflight_defaults_to_current_module_and_never_applies_other_dirty_drafts():
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        source = root / "source.flac"
        source.write_bytes(b"source")
        service = _RecordingExportService()
        session = _session(CapabilityGate((METADATA_WRITE, LYRICS_WRITE)), service, source)

        session.openUnifiedExportDialog("lyrics")
        assert session.unifiedExportDialogOpen
        assert session.unifiedExportDefaultModule == "lyrics"
        preflight = session.unifiedExportPreflight(False, True, False)
        assert preflight["selected_operations"] == ["lyrics"]
        assert preflight["missing_capabilities"] == []

        output = root / "lyrics_only.flac"
        session.setUnifiedExportOutputPath(str(output))
        session.startUnifiedAudioExport(False, True, False)
        _wait(app, session)
        assert service.requests[0].metadata_changes is None
        assert service.requests[0].lyrics_text == "[00:01.00]Edited"
        assert service.requests[0].cover_action == "keep"
        assert session.dirty and session.lyricsDirty
        assert session.unifiedExportResult["applied_operations"] == ["lyrics"]
        assert session.sourcePath == str(source)


def test_missing_capability_and_invalid_paths_stop_before_worker_creation():
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        source = root / "source.flac"
        source.write_bytes(b"source")
        service = _RecordingExportService()
        session = _session(CapabilityGate((METADATA_WRITE,)), service, source)

        session.setUnifiedExportOutputPath(str(root / "edited.flac"))
        session.startUnifiedAudioExport(True, True, False)
        assert session.unifiedExportState == "capability_denied"
        assert session.unifiedExportResult["error_code"] == "capability_denied"
        assert service.requests == []

        session.setUnifiedExportOutputPath(str(source))
        session.startUnifiedAudioExport(True, False, False)
        assert session.unifiedExportResult["error_code"] == "output_same_as_source"
        assert service.requests == []

        wrong_extension = root / "wrong.mp3"
        session.setUnifiedExportOutputPath(str(wrong_extension))
        session.startUnifiedAudioExport(True, False, False)
        assert session.unifiedExportResult["error_code"] == "output_extension_mismatch"
        assert service.requests == []


def test_combined_preflight_requires_every_selected_capability():
    with tempfile.TemporaryDirectory() as temp_dir:
        source = Path(temp_dir) / "source.flac"
        source.write_bytes(b"source")
        session = _session(CapabilityGate((METADATA_WRITE, COVER_WRITE)), _RecordingExportService(), source)

        all_selected = session.unifiedExportPreflight(True, True, True)
        assert all_selected["selected_operations"] == ["metadata", "lyrics"]
        assert all_selected["required_capabilities"] == [METADATA_WRITE, LYRICS_WRITE]
        assert all_selected["missing_capabilities"] == [LYRICS_WRITE]
        assert not all_selected["can_export"]
