from pathlib import Path
import os

from PySide6.QtCore import QObject, Signal

from ui_next.bridge.audio_processing_session import ProcessingSessionViewModel
from ui_next.bridge.capabilities import AUDIO_EXPORT, AUDIO_PLAYBACK, AUDIO_PROCESSING, CapabilityGate


def test_processing_capabilities_are_explicit_and_default_user_mode_is_available():
    assert CapabilityGate.from_environment({"QONIC_QML_LIVE": "1"}).allows(AUDIO_PROCESSING)
    gate = CapabilityGate("audio_playback,audio_processing,audio_export")
    assert gate.allows(AUDIO_PLAYBACK)
    assert gate.allows(AUDIO_PROCESSING)
    assert gate.allows(AUDIO_EXPORT)
    assert not CapabilityGate().allows(AUDIO_EXPORT)


class _FileSession(QObject):
    currentFileChanged = Signal(str, int)
    currentFileReloaded = Signal(str, int)
    currentFileCleared = Signal()
    currentFileMissing = Signal(str, int)
    editorFilePlaybackRequested = Signal(str, int, str)

    def __init__(self, outcome="loaded"):
        super().__init__()
        self.loads = []
        self.outcome = outcome

    def setCurrentFile(self, path, source):
        self.loads.append((path, source))
        return self.outcome


class _Player(QObject):
    stateChanged = Signal()

    def __init__(self):
        super().__init__(); self.playerState = "ready"; self.error = ""; self.position = 0; self.sources = []; self.currentPlaybackSourceType = "none"; self.begin_calls = []; self.finish_calls = []; self.active_token = ""; self.mediaOperationBusy = False

    def setPlaybackSource(self, path, label, autoplay, position):
        self.sources.append((path, label, "inferred", position)); self.playerState = "loading"; self.position = position; self.stateChanged.emit()

    def setPlaybackSourceWithType(self, path, label, source_type, autoplay, position):
        self.sources.append((path, label, source_type, position)); self.currentPlaybackSourceType = source_type
        self.playerState = "loading"; self.position = position; self.stateChanged.emit()

    def clear(self):
        self.playerState = "empty"; self.currentPlaybackSourceType = "none"; self.stateChanged.emit()

    def play(self):
        self.playerState = "playing"; self.stateChanged.emit()

    def beginFileOperation(self, owner):
        if self.active_token:
            return ""
        self.active_token = f"token-{len(self.begin_calls) + 1}"
        self.mediaOperationBusy = True
        self.begin_calls.append((owner, self.active_token))
        return self.active_token

    def finishFileOperation(self, token, restore=True):
        self.finish_calls.append((token, bool(restore)))
        if token != self.active_token:
            return False
        self.active_token = ""
        self.mediaOperationBusy = False
        return True

    def prepareForFileOperation(self):
        raise AssertionError("Phase A export must prefer the token lease API")

    def restorePlaybackSource(self):
        raise AssertionError("Phase A export must finish the token it acquired")


def _session(tmp_path):
    source = tmp_path / "source.wav"; source.write_bytes(b"source")
    view_model = ProcessingSessionViewModel(_FileSession(), _Player(), capability_gate=CapabilityGate((AUDIO_PROCESSING, AUDIO_PLAYBACK, AUDIO_EXPORT)))
    view_model.beginCurrentFile(str(source), 3); view_model.setSemitone(2)
    return view_model, source


def test_success_is_preview_ready_and_busy_is_cleared_without_player_autoplay(tmp_path):
    view_model, _source = _session(tmp_path)
    preview = tmp_path / "preview.wav"; preview.write_bytes(b"preview")
    request_id = "current"; view_model._active_request_id = request_id; view_model._request_generation = 3; view_model._request_semitone = 2; view_model._workers[request_id] = object()
    view_model._finish_request(request_id, "preview", str(preview), {"success": True, "output_path": str(preview), "diagnostics": {"stage": "preview_ready"}})
    assert view_model.processingState == "preview_ready" and not view_model.isBusy
    assert view_model.currentPlaybackSource == "original" and view_model.previewValid


def test_stale_request_cannot_clear_new_request_busy_state(tmp_path):
    view_model, _source = _session(tmp_path)
    old, newest = "old", "new"; old_output = tmp_path / "old.wav"; old_output.write_bytes(b"old")
    view_model._workers[old] = object(); view_model._workers[newest] = object(); view_model._active_request_id = newest
    view_model._finish_request(old, "preview", str(old_output), {"success": True, "output_path": str(old_output)})
    assert view_model.isBusy and view_model.activeRequestId == newest and not old_output.exists()


def test_player_load_timeout_is_terminal_and_restores_original_source(tmp_path):
    view_model, source = _session(tmp_path)
    preview = tmp_path / "preview.wav"; preview.write_bytes(b"preview")
    view_model._preview_path = str(preview); view_model._preview_generation = 3; view_model._preview_valid = True
    view_model.playPreview()
    assert view_model.processingState == "loading_player_source" and not view_model.isBusy
    view_model._on_player_load_timeout()
    assert view_model.processingState == "error" and view_model.errorCode == "player_load_timeout"
    assert view_model.currentPlaybackSource == "original" and Path(view_model._audio_player.sources[-1][0]) == source


def test_same_source_and_pitch_reuses_verified_preview_cache_without_worker(tmp_path):
    view_model, _source = _session(tmp_path)
    preview = tmp_path / "cached.wav"; preview.write_bytes(b"preview")
    cache_key, _source_key = view_model._preview_cache_key()
    view_model._preview_cache[cache_key] = {"path": str(preview), "source_generation": 3, "semitone": 2}
    view_model.previewCurrentSetting()
    assert view_model.previewCacheHit and not view_model.isBusy and not view_model._workers
    assert view_model.previewPath == str(preview) and view_model._audio_player.sources[-1][0] == str(preview)


def test_preview_cache_key_invalidates_for_source_mutation_and_pitch_change(tmp_path):
    view_model, source = _session(tmp_path)
    first, _ = view_model._preview_cache_key()
    source.write_bytes(b"source changed")
    changed, _ = view_model._preview_cache_key()
    view_model.setSemitone(3)
    pitch_changed, _ = view_model._preview_cache_key()
    assert first != changed and changed != pitch_changed
    assert view_model.preview_suffix == ".wav"


def test_preview_cache_key_invalidates_for_mtime_and_algorithm_version_without_entering_project(tmp_path):
    view_model, source = _session(tmp_path)
    first, _ = view_model._preview_cache_key()
    stat = source.stat(); os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    mtime_changed, _ = view_model._preview_cache_key()
    from ui_next.bridge.audio_processing_service import AudioProcessingService
    original = AudioProcessingService.preview_algorithm_version
    try:
        AudioProcessingService.preview_algorithm_version = "test-next"
        algorithm_changed, _ = view_model._preview_cache_key()
    finally:
        AudioProcessingService.preview_algorithm_version = original
    assert first != mtime_changed and mtime_changed != algorithm_changed
    assert Path(view_model._workspace).resolve().is_relative_to(Path(os.getenv("TEMP", ".")).resolve())


def _activate_preview(view_model, tmp_path):
    preview = tmp_path / "active-preview.wav"; preview.write_bytes(b"preview")
    view_model._preview_path = str(preview)
    view_model._preview_generation = view_model.sourceGeneration
    view_model._preview_valid = True
    view_model._current_playback_source = "preview"
    view_model._audio_player.currentPlaybackSourceType = "preview_cache"
    return preview


def test_switch_from_a_preview_to_b_does_not_restore_a(tmp_path):
    view_model, source_a = _session(tmp_path)
    preview = _activate_preview(view_model, tmp_path)
    source_b = tmp_path / "source-b.wav"; source_b.write_bytes(b"source-b")
    source_count = len(view_model._audio_player.sources)

    view_model.beginCurrentFile(str(source_b), 4)

    assert len(view_model._audio_player.sources) == source_count
    assert all(item[0] != str(source_a) for item in view_model._audio_player.sources[source_count:])
    assert view_model.sourcePath == str(source_b)
    assert not preview.exists()


def test_clear_from_a_preview_does_not_restore_a(tmp_path):
    view_model, source_a = _session(tmp_path)
    preview = _activate_preview(view_model, tmp_path)
    source_count = len(view_model._audio_player.sources)

    view_model.clear()

    assert len(view_model._audio_player.sources) == source_count
    assert all(item[0] != str(source_a) for item in view_model._audio_player.sources[source_count:])
    assert view_model.processingState == "empty"
    assert not preview.exists()


def test_manual_preview_cache_cleanup_restores_current_original(tmp_path):
    view_model, source = _session(tmp_path)
    preview = _activate_preview(view_model, tmp_path)

    view_model.cleanPreviewCache()

    assert view_model._audio_player.sources[-1] == (str(source), "原音频", "original", 0)
    assert view_model.currentPlaybackSource == "original"
    assert not preview.exists()


def test_preview_cache_cleanup_is_rejected_during_media_operation(tmp_path):
    view_model, _source = _session(tmp_path)
    preview = _activate_preview(view_model, tmp_path)
    token = view_model._audio_player.beginFileOperation("edit_export")

    view_model.cleanPreviewCache()

    assert preview.exists()
    assert view_model.previewPath == str(preview)
    assert "暂不能清理试听缓存" in view_model.statusMessage
    assert view_model._audio_player.finishFileOperation(token, False)


def test_return_to_original_uses_explicit_source_type_and_starts_at_zero(tmp_path):
    view_model, source = _session(tmp_path)
    view_model._audio_player.position = 42_000
    view_model._audio_player.currentPlaybackSourceType = "preview_cache"
    view_model._current_playback_source = "preview"

    view_model.returnToOriginal()

    assert view_model._audio_player.sources[-1] == (str(source), "原音频", "original", 0)
    assert view_model._audio_player.position == 0
    assert view_model.currentPlaybackSource == "original"


def test_processing_reload_invalidates_preview_without_switching_player(tmp_path):
    view_model, source = _session(tmp_path)
    preview = tmp_path / "preview-before-reload.wav"
    preview.write_bytes(b"preview")
    view_model._preview_path = str(preview)
    view_model._preview_generation = view_model.sourceGeneration
    view_model._preview_valid = True
    view_model._current_playback_source = "preview"
    view_model._audio_player.currentPlaybackSourceType = "preview_cache"
    source_count = len(view_model._audio_player.sources)

    view_model._file_session.currentFileReloaded.emit(str(source), 4)

    assert view_model.sourceGeneration == 4
    assert view_model.sourcePath == str(source)
    assert not view_model.previewValid
    assert view_model.currentPlaybackSource == "preview"
    assert len(view_model._audio_player.sources) == source_count
    assert preview.exists()


def test_pitch_export_result_stays_separate_until_explicit_load(tmp_path):
    view_model, source = _session(tmp_path)
    output = tmp_path / "pitch.wav"
    output.write_bytes(b"pitch")
    view_model._export_path = str(output)
    view_model._export_result = {"success": True, "output_path": str(output)}

    assert view_model.canLoadExportResult
    assert view_model._file_session.loads == []
    assert view_model.sourcePath == str(source)

    view_model.loadExportResultAsCurrent()

    assert view_model._audio_player.begin_calls == []
    assert view_model._file_session.loads == [
        (str(output), "pitch_export_result")
    ]


def test_pitch_export_completion_restores_released_player_for_same_session(tmp_path):
    view_model, _source = _session(tmp_path)
    output = tmp_path / "pitch.wav"
    output.write_bytes(b"pitch")
    request_id = "export"
    view_model._active_request_id = request_id
    view_model._request_generation = view_model.sourceGeneration
    view_model._request_semitone = view_model.semitone
    view_model._workers[request_id] = object()
    token = view_model._audio_player.beginFileOperation("pitch_export")
    view_model._request_context[request_id] = {
        "player_operation_token": token,
        "started_ns": 0,
    }

    view_model._finish_request(
        request_id,
        "export",
        str(output),
        {"success": True, "output_path": str(output), "diagnostics": {}},
    )

    assert view_model._audio_player.finish_calls == [(token, True)]
    assert view_model.exportPath == str(output)


def test_stale_pitch_export_finishes_its_token_without_restoring(tmp_path):
    view_model, _source = _session(tmp_path)
    output = tmp_path / "stale-pitch.wav"
    output.write_bytes(b"pitch")
    request_id = "stale-export"
    view_model._active_request_id = "newer-request"
    view_model._request_generation = view_model.sourceGeneration
    view_model._request_semitone = view_model.semitone
    view_model._workers[request_id] = object()
    view_model._workers["newer-request"] = object()
    token = view_model._audio_player.beginFileOperation("pitch_export")
    view_model._request_context[request_id] = {
        "player_operation_token": token,
        "started_ns": 0,
    }
    view_model._finish_request(
        request_id,
        "export",
        str(output),
        {"success": True, "output_path": str(output), "diagnostics": {}},
    )

    assert view_model._audio_player.finish_calls == [(token, False)]
    assert view_model._audio_player.active_token == ""
    assert view_model.activeRequestId == "newer-request"
    assert view_model.exportPath == ""


def test_pitch_worker_start_failure_finishes_media_operation(
    tmp_path,
    monkeypatch,
):
    view_model, _source = _session(tmp_path)
    output = tmp_path / "never-started.wav"

    def fail_start(_worker):
        raise RuntimeError("start failed")

    monkeypatch.setattr(
        "ui_next.bridge.audio_processing_session._ProcessingWorker.start",
        fail_start,
    )

    view_model._start("export", str(output))

    token = view_model._audio_player.begin_calls[-1][1]
    assert view_model._audio_player.finish_calls == [(token, True)]
    assert not view_model._audio_player.mediaOperationBusy
    assert view_model.errorCode == "processing_start_failed"
    assert view_model.activeRequestId == ""
