import os
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from ui_next.bridge.capabilities import (
    AUDIO_EXPORT,
    AUDIO_PROCESSING,
    COVER_WRITE,
    LYRICS_WRITE,
    METADATA_WRITE,
    CapabilityGate,
)
from ui_next.bridge.edit_session import EditSessionViewModel


class _RecordingExportService:
    def __init__(self):
        self.requests = []
        self.lrc_requests = []

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

    def export_lrc(self, request):
        self.lrc_requests.append(request)
        return {
            "success": True,
            "message": "LRC exported",
            "output_path": request.output_path,
            "applied_operations": ["lrc"],
            "verification_success": True,
            "sourceUnchanged": True,
        }


class _ProcessingDraft(QObject):
    stateChanged = Signal()

    def __init__(self, semitone=3):
        super().__init__()
        self.semitone = semitone
        self.processingDirty = semitone != 0

    def restoreOriginalProcessing(self):
        self.semitone = 0
        self.processingDirty = False
        self.stateChanged.emit()


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
        assert session.unifiedExportResult["error_code"] == "overwrite_confirmation_required"
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


def test_processing_draft_joins_the_same_preflight_and_export_request():
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        source = root / "source.flac"
        source.write_bytes(b"source")
        service = _RecordingExportService()
        session = EditSessionViewModel(
            CapabilityGate((AUDIO_PROCESSING, AUDIO_EXPORT)),
            export_service=service,
        )
        session.loadMetadataResult(_metadata(str(source)))
        processing = _ProcessingDraft(4)
        session.attach_processing_session(processing)

        assert session.hasUnsavedDrafts
        assert session.unsavedDraftLabels == ["音频处理"]
        preflight = session.unifiedExportPreflight(False, False, False, True)
        assert preflight["selected_operations"] == ["processing"]
        assert preflight["missing_capabilities"] == []

        output = root / "pitch.flac"
        session.openUnifiedExportDialog("processing")
        session.setUnifiedExportOutputPath(str(output))
        session.startUnifiedAudioExport(False, False, False, True, False)
        _wait(app, session)

        assert service.requests[0].pitch_semitone == 4
        assert service.requests[0].requested_operations() == ("pitch",)


def test_source_overwrite_requires_every_dirty_module_after_confirmation():
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as temp_dir:
        source = Path(temp_dir) / "source.flac"
        source.write_bytes(b"source")
        service = _RecordingExportService()
        session = _session(
            CapabilityGate((METADATA_WRITE, LYRICS_WRITE)),
            service,
            source,
        )
        session.openUnifiedExportDialog("auto")
        session.setUnifiedExportOutputPath(str(source))

        session.startUnifiedAudioExport(True, False, False, False, True)
        assert session.unifiedExportResult["error_code"] == (
            "source_overwrite_requires_all_drafts"
        )
        assert service.requests == []

        session.startUnifiedAudioExport(True, True, False, False, True)
        _wait(app, session)
        assert service.requests[0].overwrite_existing is True
        assert service.requests[0].metadata_changes is not None
        assert service.requests[0].lyrics_text == "[00:01.00]Edited"


def test_lrc_save_as_uses_the_same_dialog_state_and_worker_result():
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        source = root / "source.flac"
        source.write_bytes(b"source")
        service = _RecordingExportService()
        session = _session(
            CapabilityGate((METADATA_WRITE, LYRICS_WRITE)),
            service,
            source,
        )
        output = root / "lyrics.lrc"

        session.openUnifiedExportDialog("lyrics")
        session.setUnifiedExportTarget("lrc")
        session.setUnifiedExportOutputPath(str(output))
        session.startUnifiedLrcExport(False)
        _wait(app, session)

        assert service.requests == []
        assert service.lrc_requests[0].output_path == str(output)
        assert service.lrc_requests[0].overwrite_existing is False
        assert session.unifiedExportState == "success"
        assert session.unifiedExportResult["applied_operations"] == ["lrc"]
