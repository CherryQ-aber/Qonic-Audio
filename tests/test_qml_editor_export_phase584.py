import hashlib
import subprocess
import time
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication

from lyrics import read_embedded_lyrics
from metadata import read_audio_metadata
from single_file_convert import FFMPEG_PATH
from ui_next.bridge.capabilities import (
    COVER_WRITE,
    LYRICS_WRITE,
    METADATA_WRITE,
    CapabilityGate,
)
from ui_next.bridge.edit_export_service import EditExportRequest, EditExportService
from ui_next.bridge.edit_session import EditSessionViewModel


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _png_bytes() -> bytes:
    image = Image.new("RGB", (8, 8), (30, 80, 120))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _wait_for_unified_export(session: EditSessionViewModel, timeout: float = 3.0) -> None:
    app = QApplication.instance() or QApplication([])
    deadline = time.monotonic() + timeout
    while session.unifiedExporting and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()
    assert not session.unifiedExporting


@pytest.mark.parametrize(
    ("extension", "codec_args"),
    (
        (".mp3", ["-c:a", "libmp3lame", "-q:a", "4"]),
        (".flac", ["-c:a", "flac"]),
        (".m4a", ["-c:a", "aac", "-b:a", "128k"]),
        (".ogg", ["-c:a", "libvorbis", "-q:a", "4"]),
        (".opus", ["-c:a", "libopus", "-b:a", "96k"]),
    ),
)
def test_real_media_all_drafts_export_and_read_back_without_touching_source(
    tmp_path,
    extension,
    codec_args,
):
    source = tmp_path / f"源 音频{extension}"
    output = tmp_path / f"导出 副本{extension}"
    subprocess.run(
        [
            FFMPEG_PATH,
            "-nostdin",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=0.2",
            *codec_args,
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    source_hash = _sha256(source)
    result = EditExportService(
        CapabilityGate((METADATA_WRITE, LYRICS_WRITE, COVER_WRITE))
    ).export(
        EditExportRequest(
            str(source),
            str(output),
            metadata_changes={"title": "CherryQ 测试"},
            lyrics_text="[00:00.00]歌词测试",
            cover_action="replace",
            cover_data=_png_bytes(),
            cover_mime="image/png",
        )
    )

    assert result["success"], result
    assert result["appliedModules"] == ["metadata", "cover", "lyrics"]
    assert result["failedModules"] == []
    assert result["sourceUnchanged"] is True
    assert _sha256(source) == source_hash
    metadata = read_audio_metadata(str(output), include_cover=True)
    lyrics = read_embedded_lyrics(str(output))
    assert metadata["title"] == "CherryQ 测试"
    assert metadata["cover_data"]
    assert lyrics["lyrics_text"] == "[00:00.00]歌词测试"


def test_empty_lyrics_draft_removes_only_exported_copy(tmp_path):
    source = tmp_path / "source.flac"
    first = tmp_path / "with-lyrics.flac"
    cleared = tmp_path / "cleared.flac"
    subprocess.run(
        [
            FFMPEG_PATH,
            "-nostdin",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=0.2",
            "-c:a",
            "flac",
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    service = EditExportService(CapabilityGate((LYRICS_WRITE,)))
    embedded = service.export(
        EditExportRequest(str(source), str(first), lyrics_text="Embedded lyrics")
    )
    assert embedded["success"], embedded
    first_hash = _sha256(first)
    removed = service.export(
        EditExportRequest(str(first), str(cleared), lyrics_text="")
    )
    assert removed["success"], removed
    assert _sha256(first) == first_hash
    assert read_embedded_lyrics(str(first))["lyrics_text"] == "Embedded lyrics"
    assert read_embedded_lyrics(str(cleared))["lyrics_text"] == ""


class _Player:
    def __init__(self):
        self.begin_calls = []
        self.finish_calls = []
        self.active_token = ""

    def beginFileOperation(self, owner):
        if self.active_token:
            return ""
        self.active_token = f"token-{len(self.begin_calls) + 1}"
        self.begin_calls.append((owner, self.active_token))
        return self.active_token

    def finishFileOperation(self, token, restore=True):
        self.finish_calls.append((token, bool(restore)))
        if token != self.active_token:
            return False
        self.active_token = ""
        return True

    def prepareForFileOperation(self):
        raise AssertionError("Phase A export must prefer the token lease API")

    def restorePlaybackSource(self):
        raise AssertionError("Phase A export must finish the token it acquired")


class _FileSession:
    def __init__(self, outcome="confirmation_required"):
        self.loads = []
        self.outcome = outcome

    def setCurrentFile(self, path, source):
        self.loads.append((path, source))
        return self.outcome


class _CopyExporter:
    def export(self, request):
        Path(request.output_path).write_bytes(Path(request.source_path).read_bytes())
        return {
            "success": True,
            "output_path": request.output_path,
            "message": "ok",
            "applied_operations": list(request.requested_operations()),
            "appliedModules": list(request.requested_operations()),
            "skippedModules": [],
            "failedModules": [],
            "warnings": [],
            "sourceUnchanged": True,
        }


def test_unified_export_releases_restores_and_loads_result_only_when_explicit(tmp_path):
    source = tmp_path / "source.flac"
    output = tmp_path / "edited.flac"
    source.write_bytes(b"source")
    player = _Player()
    file_session = _FileSession()
    session = EditSessionViewModel(
        CapabilityGate((METADATA_WRITE,)),
        export_service=_CopyExporter(),
    )
    session.attach_runtime(file_session, player)
    session.beginCurrentFile(str(source), 7)
    session.loadMetadataResult(
        {"ok": True, "path": str(source), "session_generation": 7, "title": "Old"}
    )
    session.updateField("title", "New")
    session.setUnifiedExportOutputPath(str(output))
    session.startUnifiedAudioExport(True, False, False)
    _wait_for_unified_export(session)

    assert len(player.begin_calls) == 1
    assert player.finish_calls == [(player.begin_calls[0][1], True)]
    assert file_session.loads == []
    assert session.hasUnsavedDrafts
    assert session.canLoadUnifiedExportResult

    session.loadUnifiedExportResultAsCurrent()
    assert len(player.begin_calls) == 1
    assert file_session.loads == [(str(output), "edit_export_result")]
    assert session.hasUnsavedDrafts


class _CancellableExporter:
    def export(self, request):
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not request.cancel_event.is_set():
            time.sleep(0.01)
        return {
            "success": False,
            "error_code": "export_cancelled",
            "message": "cancelled",
            "output_path": request.output_path,
            "applied_operations": ["metadata"],
            "appliedModules": ["metadata"],
            "skippedModules": [],
            "failedModules": ["metadata"],
            "warnings": [],
            "sourceUnchanged": True,
            "temp_cleanup_success": True,
        }


def test_unified_export_cancel_is_real_and_keeps_session_draft(tmp_path):
    source = tmp_path / "source.flac"
    output = tmp_path / "edited.flac"
    source.write_bytes(b"source")
    player = _Player()
    session = EditSessionViewModel(
        CapabilityGate((METADATA_WRITE,)),
        export_service=_CancellableExporter(),
    )
    session.attach_runtime(_FileSession(), player)
    session.beginCurrentFile(str(source), 3)
    session.loadMetadataResult(
        {"ok": True, "path": str(source), "session_generation": 3, "title": "Old"}
    )
    session.updateField("title", "New")
    session.setUnifiedExportOutputPath(str(output))
    session.startUnifiedAudioExport(True, False, False)
    session.cancelExport()
    _wait_for_unified_export(session)

    assert session.unifiedExportState == "cancelled"
    assert session.unifiedExportResult["error_code"] == "export_cancelled"
    assert session.hasUnsavedDrafts
    assert not output.exists()
    assert player.finish_calls == [(player.begin_calls[0][1], True)]


def test_unified_worker_start_failure_finishes_media_operation(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "source.flac"
    output = tmp_path / "edited.flac"
    source.write_bytes(b"source")
    player = _Player()
    session = EditSessionViewModel(
        CapabilityGate((METADATA_WRITE,)),
        export_service=_CopyExporter(),
    )
    session.attach_runtime(_FileSession(), player)
    session.beginCurrentFile(str(source), 5)
    session.loadMetadataResult(
        {
            "ok": True,
            "path": str(source),
            "session_generation": 5,
            "title": "Old",
        }
    )
    session.updateField("title", "New")
    session.setUnifiedExportOutputPath(str(output))

    def fail_start(_worker):
        raise RuntimeError("start failed")

    monkeypatch.setattr(
        "ui_next.bridge.edit_session._UnifiedExportWorker.start",
        fail_start,
    )

    session.startUnifiedAudioExport(True, False, False)

    token = player.begin_calls[-1][1]
    assert player.finish_calls == [(token, True)]
    assert player.active_token == ""
    assert session.unifiedExportState == "failed"
    assert session.unifiedExportResult["error_code"] == "export_start_failed"


def test_running_edit_export_cannot_overwrite_its_media_token(tmp_path):
    source = tmp_path / "source.flac"
    first_output = tmp_path / "first.flac"
    second_output = tmp_path / "second.flac"
    source.write_bytes(b"source")
    player = _Player()
    session = EditSessionViewModel(
        CapabilityGate((METADATA_WRITE, LYRICS_WRITE)),
        export_service=_CancellableExporter(),
    )
    session.attach_runtime(_FileSession(), player)
    session.beginCurrentFile(str(source), 8)
    session.loadMetadataResult(
        {
            "ok": True,
            "path": str(source),
            "session_generation": 8,
            "title": "Old",
        }
    )
    session.loadLyricsResult(
        {
            "ok": True,
            "path": str(source),
            "session_generation": 8,
            "lyrics_text": "old lyrics",
            "lyrics_source": "embedded",
        }
    )
    session.updateField("title", "New")
    session.updateLyricsDraft("new lyrics")
    session.setUnifiedExportOutputPath(str(first_output))
    session.startUnifiedAudioExport(True, False, False)
    token = player.begin_calls[-1][1]

    session.exportLyricsToAudioPath(str(second_output))

    assert len(player.begin_calls) == 1
    assert player.active_token == token
    assert session.unifiedExporting
    assert not second_output.exists()
    session.cancelExport()
    _wait_for_unified_export(session)
    assert player.finish_calls == [(token, True)]


def test_phase584_qml_exposes_cancel_result_summary_and_explicit_load():
    root = Path(__file__).resolve().parents[1]
    dialog = (root / "ui_next/qml/components/EditExportDialog.qml").read_text(
        encoding="utf-8"
    )
    pitch = (root / "ui_next/qml/components/PitchShiftCard.qml").read_text(
        encoding="utf-8"
    )
    shell = (root / "ui_next/qml/AppShell.qml").read_text(encoding="utf-8")
    assert "cancelExport()" in dialog
    assert "loadUnifiedExportResultAsCurrent()" in dialog
    assert "sourceUnchanged" in dialog
    assert "failedModules" in dialog
    assert "loadExportResultAsCurrent()" in pitch
    assert "不会自动替换当前文件" in pitch
    assert "needsDraftConfirmation" in shell
    assert "confirmDraftWarning(false)" in shell
    assert "confirmDraftWarning(true)" in shell
    assert "pitchDraftWarningDialog" not in pitch


def test_pending_file_change_offers_discard_export_or_cancel():
    root = Path(__file__).resolve().parents[1]
    shell = (root / "ui_next/qml/AppShell.qml").read_text(encoding="utf-8")
    dialog = (root / "ui_next/qml/components/EditExportDialog.qml").read_text(
        encoding="utf-8"
    )

    assert 'objectName: "unsavedEditDraftsDialog"' in shell
    assert 'text: "取消"' in shell
    assert 'text: "导出"' in shell
    assert '"放弃修改并载入"' in shell
    assert "beginPendingFileExport()" in shell
    assert "pendingFileExportStarted" in shell
    assert "unifiedExportResult.success === true" in shell
    assert "fileSessionViewModel.discardPendingFileChange()" in shell
    assert "selectAllDraftsOnOpen: root.pendingFileExportFlowActive" in shell
    assert "property bool selectAllDraftsOnOpen" in dialog
    assert "root.metadataSelected = root.editSession.dirty" in dialog
    assert "root.lyricsSelected = root.editSession.lyricsDirty" in dialog
    assert "root.coverSelected = root.editSession.coverDirty" in dialog
