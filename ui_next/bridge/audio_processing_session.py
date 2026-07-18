"""Per-FileSession Pitch Shift state and bounded background workflow."""
from __future__ import annotations

import logging
import hashlib
import json
import shutil
import tempfile
import time
import uuid
from pathlib import Path

from PySide6.QtCore import Property, QThread, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog

from ui_next.bridge.audio_processing_service import AudioProcessingService
from ui_next.bridge.base_viewmodel import BaseViewModel
from ui_next.bridge.capabilities import AUDIO_EXPORT, AUDIO_PLAYBACK, AUDIO_PROCESSING, CapabilityGate
from ui_next.bridge.processed_audio_export_service import ProcessedAudioExportService


_LOG = logging.getLogger(__name__)


class _ProcessingWorker(QThread):
    """One request worker.  ``result`` is set even if a callback fails."""

    stageChanged = Signal(dict)

    def __init__(self, *, request_id: str, source_generation: int, mode: str, source: str, output: str, semitone: int, source_probe: dict | None = None) -> None:
        super().__init__()
        self.request_id = request_id
        self.source_generation = source_generation
        self.mode, self.source, self.output, self.semitone = mode, source, output, semitone
        self.source_probe = dict(source_probe) if source_probe else None
        self._service = AudioProcessingService()
        self._cancelled = False
        self.result: dict | None = None

    def cancel(self) -> None:
        self._cancelled = True
        self._service.cancel()

    def run(self) -> None:
        try:
            if self.mode == "preview":
                result = self._service.render_pitch_shift(
                    self.source, self.output, self.semitone,
                    request_id=self.request_id,
                    source_generation=self.source_generation,
                    progress_callback=self.stageChanged.emit,
                    preview=True,
                    source_probe=self.source_probe,
                )
            else:
                result = ProcessedAudioExportService(self._service).export(self.source, self.output, self.semitone)
            if self._cancelled and self.mode == "preview":
                if result.get("success"):
                    AudioProcessingService.cleanup_owned(Path(self.output))
                result = {"success": False, "error_code": "processing_cancelled", "message": "处理已取消。", "diagnostics": result.get("diagnostics", {})}
            elif self._cancelled and self.mode == "export" and result.get("success"):
                # Publication has already completed atomically.  Report the
                # verified output instead of claiming a cancelled operation
                # left no formal result.
                result.setdefault("warnings", []).append(
                    "取消请求到达时正式输出已完成发布。"
                )
        except Exception as exc:  # worker completion is part of the state-machine contract
            result = {"success": False, "error_code": "processing_worker_exception", "message": f"处理工作线程异常：{type(exc).__name__}"}
        finally:
            self.result = result


class ProcessingSessionViewModel(BaseViewModel):
    """Non-destructive Pitch Shift state for exactly one FileSession generation."""

    stateChanged = Signal()
    draftWarningRequested = Signal()
    _STATES = {
        "empty", "ready", "preview_required", "validating_request", "preparing_workspace", "starting_process", "rendering",
        "waiting_process_exit", "validating_preview", "loading_player_source", "preview_ready", "playing_preview", "original_playing",
        "exporting", "success", "cancelled", "error",
    }
    player_load_timeout_ms = 10_000
    preview_suffix = ".wav"

    def __init__(self, file_session, audio_player, edit_session=None, capability_gate: CapabilityGate | None = None) -> None:
        super().__init__(capability_gate=capability_gate)
        self._file_session, self._audio_player, self._edit_session = file_session, audio_player, edit_session
        self._session_id = uuid.uuid4().hex
        self._workspace = Path(tempfile.gettempdir()) / "CherryQ_Audio_Converter" / "processing" / self._session_id
        self._source_path = ""; self._source_generation = 0; self._semitone = 0
        self._state = "empty"; self._preview_path = ""; self._preview_generation = 0; self._preview_valid = False
        self._current_playback_source = "original"; self._export_path = ""; self._export_result = {}; self._error_code = ""; self._error_message = ""; self._progress = 0
        self._workers: dict[str, _ProcessingWorker] = {}
        self._active_request_id = ""; self._request_generation = 0; self._request_semitone = 0; self._request_mode = ""
        self._request_diagnostics: dict = {}; self._pending_export_confirmation = False; self._player_load_token = ""
        self._preview_cache: dict[str, dict] = {}; self._source_probe_cache: dict[str, dict] = {}; self._request_context: dict[str, dict] = {}; self._stage_detail = ""
        self._player_load_started_ns: int | None = None; self._preview_ready_ns: int | None = None
        self._player_load_timer = QTimer(self); self._player_load_timer.setSingleShot(True); self._player_load_timer.timeout.connect(self._on_player_load_timeout)
        file_session.currentFileChanged.connect(self.beginCurrentFile)
        file_session.currentFileCleared.connect(self.clear)
        audio_player.stateChanged.connect(self._on_player_state_changed)
        self.set_status_message("等待工作区文件。")

    @Property(str, notify=stateChanged)
    def sourcePath(self): return self._source_path
    @Property(int, notify=stateChanged)
    def sourceGeneration(self): return self._source_generation
    @Property(int, notify=stateChanged)
    def semitone(self): return self._semitone
    @Property(str, notify=stateChanged)
    def processingState(self): return self._state
    @Property(str, notify=stateChanged)
    def previewPath(self): return self._preview_path
    @Property(str, notify=stateChanged)
    def previewPathSummary(self): return Path(self._preview_path).name if self._preview_path else "未生成"
    @Property(int, notify=stateChanged)
    def previewGeneration(self): return self._preview_generation
    @Property(bool, notify=stateChanged)
    def previewValid(self): return self._preview_valid
    @Property(str, notify=stateChanged)
    def currentPlaybackSource(self): return self._current_playback_source
    @Property(str, notify=stateChanged)
    def exportPath(self): return self._export_path
    @Property('QVariantMap', notify=stateChanged)
    def exportResult(self): return self._export_result
    @Property(str, notify=stateChanged)
    def errorCode(self): return self._error_code
    @Property(str, notify=stateChanged)
    def errorMessage(self): return self._error_message
    @Property(int, notify=stateChanged)
    def progress(self): return self._progress
    @Property(bool, notify=stateChanged)
    def isBusy(self): return bool(self._active_request_id and self._active_request_id in self._workers)
    @Property('QVariantMap', notify=stateChanged)
    def requestDiagnostics(self): return self._request_diagnostics
    @Property(str, notify=stateChanged)
    def progressDetail(self): return self._stage_detail
    @Property(bool, notify=stateChanged)
    def previewCacheHit(self): return bool(self._request_diagnostics.get("cache_hit"))
    @Property(str, notify=stateChanged)
    def activeRequestId(self): return self._active_request_id
    @Property(bool, notify=stateChanged)
    def audioProcessingEnabled(self): return self.allows_capability(AUDIO_PROCESSING)
    @Property(bool, notify=stateChanged)
    def audioExportEnabled(self): return self.allows_capability(AUDIO_EXPORT)
    @Property(bool, notify=stateChanged)
    def audioPlaybackEnabled(self): return self.allows_capability(AUDIO_PLAYBACK)
    @Property(bool, notify=stateChanged)
    def hasSource(self): return bool(self._source_path)
    @Property(bool, notify=stateChanged)
    def needsDraftConfirmation(self): return self._pending_export_confirmation
    @Property(bool, notify=stateChanged)
    def canLoadExportResult(self):
        return bool(
            self._export_result.get("success")
            and self._export_path
            and Path(self._export_path).is_file()
            and not self.isBusy
        )
    @Property(str, notify=stateChanged)
    def disabledReason(self):
        if not self.hasSource: return "当前没有音频文件"
        if not self.audioProcessingEnabled: return "未启用 audio_processing"
        if self.isBusy: return "正在处理"
        return ""

    @Slot(str, int)
    def beginCurrentFile(self, path: str, generation: int) -> None:
        self._cancel_active_request()
        # FileSession/AudioPlayer may already be switching to ``path``.  Never
        # restore the previous session's source while disposing its preview.
        self._release_preview_for_cleanup(restore_source=False)
        self._source_path, self._source_generation, self._semitone = str(path), int(generation), 0
        self._state = "ready"; self._current_playback_source = "original"; self._export_path = ""; self._export_result = {}; self._error_code = self._error_message = ""; self._progress = 0
        self.set_status_message("处理会话已创建；原文件未修改。")
        self.stateChanged.emit()

    @Slot()
    def clear(self) -> None:
        self._cancel_active_request()
        # Clearing FileSession must not briefly reload the old source.
        self._release_preview_for_cleanup(restore_source=False)
        self._source_path = ""; self._source_generation = 0; self._semitone = 0; self._state = "empty"; self._current_playback_source = "original"; self._export_path = ""; self._export_result = {}; self._progress = 0
        self.stateChanged.emit()

    @Slot(float)
    def setSemitone(self, value: float) -> None:
        next_value = max(-12, min(12, int(round(value))))
        if next_value == self._semitone: return
        self._cancel_active_request()
        self._semitone = next_value
        if self._preview_valid:
            self._preview_valid = False
            self._state = "preview_required"
        elif self.hasSource:
            self._state = "ready" if next_value == 0 else "preview_required"
        self.set_status_message("半音参数已更新；旧试听缓存不会被静默播放。")
        self.stateChanged.emit()

    @Slot()
    def previewCurrentSetting(self) -> None:
        if not self._require(AUDIO_PROCESSING, "processing_capability_denied") or not self._require(AUDIO_PLAYBACK, "playback_capability_denied"): return
        if not self.hasSource: return self._fail("source_missing", "当前没有音频文件。")
        if self.isBusy: return
        if self._semitone == 0:
            self.returnToOriginal(); return
        cache_key, source_key = self._preview_cache_key()
        cached = self._preview_cache.get(cache_key)
        if cached and Path(cached["path"]).is_file() and Path(cached["path"]).stat().st_size > 0:
            self._use_cached_preview(cache_key, cached); return
        self._workspace.mkdir(parents=True, exist_ok=True)
        output = self._workspace / f"preview_{cache_key}{self.preview_suffix}"
        if output.exists():
            AudioProcessingService.cleanup_owned(output)
        self._start("preview", str(output), cache_key=cache_key, source_key=source_key)

    @Slot()
    def cancelProcessing(self) -> None:
        if self._active_request_id:
            self._cancel_active_request(keep_busy=True)
            self.set_status_message("正在取消处理进程。")
            self.stateChanged.emit()

    @Slot()
    def playPreview(self) -> None:
        if not self._preview_valid or not Path(self._preview_path).is_file() or not self._require(AUDIO_PLAYBACK, "playback_capability_denied"):
            return self._fail("preview_missing", "当前没有可播放的已验证试听缓存。")
        self._player_load_token = uuid.uuid4().hex
        self._state = "loading_player_source"; self._error_code = self._error_message = ""
        self._request_diagnostics["player_load_started_at"] = time.time()
        self._player_load_started_ns = time.perf_counter_ns()
        self.set_status_message("正在加载已验证试听源。")
        self._player_load_timer.start(self.player_load_timeout_ms)
        try:
            self._set_player_source(
                self._preview_path,
                f"Pitch Shift 试听（{self._semitone:+d} 半音）",
                "preview_cache",
                False,
                0,
            )
        except Exception as exc:
            self._player_load_failed("player_load_failed", f"播放器加载试听源失败：{type(exc).__name__}")
        self.stateChanged.emit()

    @Slot()
    def returnToOriginal(self) -> None:
        if not self.hasSource or not self._require(AUDIO_PLAYBACK, "playback_capability_denied"): return
        self._player_load_timer.stop(); self._player_load_token = ""
        self._player_load_started_ns = None
        self._set_player_source(self._source_path, "原音频", "original", False, 0)
        self._current_playback_source = "original"; self._state = "original_playing"; self.set_status_message("已返回原音频；试听缓存仍可复用。")
        self.stateChanged.emit()

    @Slot()
    def requestExport(self) -> None:
        if not self._require(AUDIO_PROCESSING, "processing_capability_denied") or not self._require(AUDIO_EXPORT, "audio_export_capability_denied"): return
        if not self.hasSource: return self._fail("source_missing", "当前没有音频文件。")
        if self._semitone == 0: return self._fail("pitch_zero_no_processing", "0 半音无需导出 Pitch Shift 文件。")
        if self.isBusy: return
        if self._edit_session is not None and self._edit_session.hasUnsavedDrafts:
            self._pending_export_confirmation = True; self.draftWarningRequested.emit(); self.stateChanged.emit(); return
        self._choose_export_path()

    @Slot(bool)
    def confirmDraftWarning(self, continue_export: bool) -> None:
        if not self._pending_export_confirmation: return
        self._pending_export_confirmation = False
        if continue_export: self._choose_export_path()
        else: self.set_status_message("已取消 Pitch Shift 导出；编辑草稿保持不变。")
        self.stateChanged.emit()

    @Slot()
    def cleanPreviewCache(self) -> None:
        self._release_preview_for_cleanup()
        self.set_status_message("试听缓存已清理。" if not self._preview_path else "试听缓存清理失败；不会影响原文件。")
        self.stateChanged.emit()

    @Slot()
    def openExportLocation(self) -> None:
        if self._export_path: QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self._export_path).parent)))

    @Slot()
    def loadExportResultAsCurrent(self) -> None:
        if not self.canLoadExportResult:
            return self._fail("export_result_missing", "当前没有可载入的已验证 Pitch 导出结果。")
        prepare = getattr(self._audio_player, "prepareForFileOperation", None)
        if callable(prepare) and not prepare():
            return self._fail("player_release_failed", "播放器未能释放媒体源，已取消载入导出结果。")
        outcome = self._file_session.setCurrentFile(
            self._export_path,
            "pitch_export_result",
        )
        if outcome not in {"loaded", "unchanged"}:
            return self._fail("export_result_load_failed", "无法载入 Pitch 导出结果。")
        if self._edit_session is not None:
            discard = getattr(self._edit_session, "discardAllDraftsForResultLoad", None)
            if callable(discard):
                discard()
        self.set_status_message("已载入 Pitch 导出结果，并重新读取文件信息。")
        self.stateChanged.emit()

    def shutdown(self) -> None:
        for request_id in list(self._workers):
            self._cancel_request(request_id)
        for worker in list(self._workers.values()):
            worker.wait(3_000)
        self._active_request_id = ""
        self._release_preview_for_cleanup(restore_source=False)

    def _choose_export_path(self) -> None:
        source = Path(self._source_path)
        suggested = str(source.with_name(f"{source.stem} [Pitch {self._semitone:+d}]{source.suffix}"))
        path, _ = QFileDialog.getSaveFileName(None, "导出 Pitch Shift 新文件", suggested, f"{source.suffix.upper().lstrip('.')} 文件 (*{source.suffix})")
        if path: self._start("export", path)
        else: self.set_status_message("已取消选择输出路径。")

    def _start(self, mode: str, output: str, *, cache_key: str = "", source_key: str = "") -> None:
        self._cancel_active_request()
        player_released = False
        if mode == "export":
            prepare = getattr(self._audio_player, "prepareForFileOperation", None)
            if callable(prepare):
                player_released = bool(prepare())
                if not player_released:
                    self._fail(
                        "player_release_failed",
                        "播放器未能释放当前媒体源，已取消 Pitch 导出。",
                    )
                    return
        request_id = uuid.uuid4().hex
        self._active_request_id = request_id; self._request_generation = self._source_generation; self._request_semitone = self._semitone; self._request_mode = mode
        self._state = "validating_request"; self._progress = 0; self._stage_detail = "正在校验请求"; self._error_code = self._error_message = ""
        self._request_context[request_id] = {
            "cache_key": cache_key,
            "source_key": source_key,
            "started_ns": time.perf_counter_ns(),
            "player_released": player_released,
        }
        worker = _ProcessingWorker(request_id=request_id, source_generation=self._source_generation, mode=mode, source=self._source_path, output=output, semitone=self._semitone, source_probe=self._source_probe_cache.get(source_key) if mode == "preview" else None)
        self._workers[request_id] = worker
        worker.stageChanged.connect(lambda event, rid=request_id: self._on_worker_stage(rid, event))
        worker.finished.connect(lambda rid=request_id, current=worker, current_mode=mode, current_output=output: self._on_worker_finished(rid, current_mode, current_output, current))
        worker.finished.connect(worker.deleteLater)
        worker.start(); self.stateChanged.emit()

    def _on_worker_stage(self, request_id: str, event: dict) -> None:
        if request_id != self._active_request_id:
            return
        stage = str(event.get("stage") or "rendering")
        if stage in self._STATES:
            self._state = stage
        percent = event.get("progress_percent")
        if isinstance(percent, (int, float)):
            self._progress = max(0, min(99, int(round(percent))))
        processed = event.get("processed_seconds")
        self._stage_detail = f"已处理 {float(processed):.1f} 秒" if isinstance(processed, (int, float)) else self._stage_label(stage)
        self._request_diagnostics.update(event)
        self.stateChanged.emit()

    def _on_worker_finished(self, request_id: str, mode: str, output: str, worker: _ProcessingWorker) -> None:
        result = worker.result or {"success": False, "error_code": "processing_worker_no_result", "message": "处理线程未返回结果。"}
        self._finish_request(request_id, mode, output, result)

    def _finish_request(self, request_id: str, mode: str, output: str, result: dict) -> None:
        self._workers.pop(request_id, None)
        context = self._request_context.pop(request_id, {})
        diagnostics = dict(result.get("diagnostics") or {})
        diagnostics["final_state"] = ""
        is_active = request_id == self._active_request_id
        stale = not is_active or self._request_generation != self._source_generation or self._request_semitone != self._semitone
        if stale:
            if mode == "preview": diagnostics["cleanup_ok"] = AudioProcessingService.cleanup_owned(Path(output))
            diagnostics["final_state"] = "stale"
            _LOG.info("pitch request finished: %s", diagnostics)
            # Crucially, an old request never clears a newer request's busy flag.
            return

        self._active_request_id = ""
        if mode == "export" and context.get("player_released"):
            restore = getattr(self._audio_player, "restorePlaybackSource", None)
            if callable(restore):
                restore()
        self._request_diagnostics = diagnostics
        timings = self._request_diagnostics.setdefault("timings_ms", {})
        if context.get("started_ns"):
            timings["click_to_preview_ready"] = round((time.perf_counter_ns() - context["started_ns"]) / 1_000_000, 3)
        self._request_diagnostics["cache_hit"] = False
        if not result.get("success"):
            final_state = "cancelled" if result.get("error_code") == "processing_cancelled" else "error"
            self._state = final_state; self._progress = 0
            self._fail(str(result.get("error_code") or "preview_render_failed"), str(result.get("message") or "处理失败。"), emit=False)
        elif mode == "preview":
            self._preview_path = str(result["output_path"]); self._preview_generation = self._source_generation; self._preview_valid = True
            self._state = "preview_ready"; self._progress = 100
            self._preview_ready_ns = time.perf_counter_ns(); self._stage_detail = "试听缓存已就绪"
            if context.get("cache_key"):
                self._preview_cache[context["cache_key"]] = {"path": self._preview_path, "source_generation": self._source_generation, "semitone": self._semitone}
            if context.get("source_key") and result.get("source_probe"):
                self._source_probe_cache[context["source_key"]] = dict(result["source_probe"])
            self.set_status_message("试听缓存已验证；可点击“播放试听”。原文件未修改。")
        else:
            self._export_path = str(result["output_path"]); self._export_result = dict(result); self._state = "success"; self._progress = 100
            self.set_status_message("Pitch Shift 已导出为新文件；当前编辑文件和播放源均未自动替换。")
        self._request_diagnostics["final_state"] = self._state
        _LOG.info("pitch request finished: %s", self._request_diagnostics)
        self.stateChanged.emit()

    def _cancel_request(self, request_id: str) -> None:
        worker = self._workers.get(request_id)
        if worker is not None: worker.cancel()

    def _cancel_active_request(self, *, keep_busy: bool = False) -> None:
        request_id = self._active_request_id
        if not request_id: return
        self._cancel_request(request_id)
        if not keep_busy:
            self._active_request_id = ""

    def _on_player_state_changed(self) -> None:
        player_state = str(getattr(self._audio_player, "playerState", ""))
        if not self._player_load_token:
            if player_state == "playing" and self._current_playback_source == "preview":
                self._state = "playing_preview"
                if self._preview_ready_ns:
                    self._request_diagnostics.setdefault("timings_ms", {})["preview_ready_to_playing"] = round((time.perf_counter_ns() - self._preview_ready_ns) / 1_000_000, 3)
                self.stateChanged.emit()
            return
        if player_state in {"ready", "paused", "stopped", "playing"}:
            self._player_load_timer.stop(); self._player_load_token = ""
            self._request_diagnostics["player_load_finished_at"] = time.time()
            if self._player_load_started_ns:
                self._request_diagnostics.setdefault("timings_ms", {})["player_load"] = round((time.perf_counter_ns() - self._player_load_started_ns) / 1_000_000, 3)
            self._player_load_started_ns = None
            self._current_playback_source = "preview"
            self._state = "playing_preview" if player_state == "playing" else "preview_ready"
            self.set_status_message("试听源已加载。")
            self.stateChanged.emit()
            if player_state != "playing": self._audio_player.play()
        elif player_state == "error":
            self._player_load_failed("player_load_failed", str(getattr(self._audio_player, "error", "播放器无法加载试听源。")))

    def _on_player_load_timeout(self) -> None:
        if self._state == "loading_player_source" and self._player_load_token:
            self._player_load_failed("player_load_timeout", "播放器加载试听源超时。")

    def _player_load_failed(self, code: str, message: str) -> None:
        self._player_load_timer.stop(); self._player_load_token = ""
        self._request_diagnostics["player_load_finished_at"] = time.time()
        if self._player_load_started_ns:
            self._request_diagnostics.setdefault("timings_ms", {})["player_load"] = round((time.perf_counter_ns() - self._player_load_started_ns) / 1_000_000, 3)
        self._player_load_started_ns = None
        try:
            if self._source_path: self._set_player_source(self._source_path, "原音频", "original", False, 0)
            else: self._audio_player.clear()
        except Exception:
            pass
        self._current_playback_source = "original"; self._state = "error"; self._error_code = code; self._error_message = message
        self.set_status_message(message); self.stateChanged.emit()

    def _release_preview_for_cleanup(self, *, restore_source: bool = True) -> None:
        self._player_load_timer.stop(); self._player_load_token = ""
        self._player_load_started_ns = None; self._preview_ready_ns = None; self._preview_cache.clear(); self._source_probe_cache.clear(); self._request_context.clear()
        preview = self._preview_path
        if not preview: return
        player_source_type = str(getattr(self._audio_player, "currentPlaybackSourceType", "") or "")
        preview_is_loaded = player_source_type == "preview_cache" or (
            not player_source_type and self._current_playback_source == "preview"
        )
        if restore_source and preview_is_loaded:
            if self._source_path:
                self._set_player_source(self._source_path, "原音频", "original", False, 0)
            else:
                self._audio_player.clear()
            self._current_playback_source = "original"
        elif not restore_source and preview_is_loaded:
            # Release the preview handle so Windows can delete the cache.  The
            # FileSession transition owns loading the next source (if any).
            self._audio_player.clear()
        for _ in range(5):
            try:
                Path(preview).unlink(missing_ok=True); break
            except OSError: time.sleep(0.05)
        self._preview_path = ""; self._preview_valid = False; self._preview_generation = 0
        try:
            if self._workspace.exists(): shutil.rmtree(self._workspace)
        except OSError:
            pass
        self._workspace = Path(tempfile.gettempdir()) / "CherryQ_Audio_Converter" / "processing" / uuid.uuid4().hex

    def _set_player_source(self, path: str, label: str, source_type: str, autoplay: bool, position: int) -> None:
        """Use the player's explicit source model, with old test doubles supported."""
        typed_setter = getattr(self._audio_player, "setPlaybackSourceWithType", None)
        if callable(typed_setter):
            typed_setter(path, label, source_type, autoplay, position)
            return
        self._audio_player.setPlaybackSource(path, label, autoplay, position)

    def _preview_cache_key(self) -> tuple[str, str]:
        source = Path(self._source_path).resolve(); stat = source.stat()
        source_payload = {"path": str(source), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns, "generation": self._source_generation}
        source_key = hashlib.sha256(json.dumps(source_payload, sort_keys=True).encode("utf-8")).hexdigest()[:20]
        payload = {**source_payload, "semitone": self._semitone, "algorithm": AudioProcessingService.preview_algorithm_version, "encoding": AudioProcessingService.preview_encoding_version}
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:32], source_key

    def _use_cached_preview(self, cache_key: str, cached: dict) -> None:
        started = time.perf_counter_ns()
        self._preview_path = str(cached["path"]); self._preview_generation = self._source_generation; self._preview_valid = True
        self._state = "preview_ready"; self._progress = 100; self._preview_ready_ns = time.perf_counter_ns(); self._stage_detail = "已命中试听缓存"
        self._request_diagnostics = {"cache_hit": True, "cache_key": cache_key, "final_state": "preview_ready", "timings_ms": {"cache_lookup": round((time.perf_counter_ns() - started) / 1_000_000, 3), "click_to_preview_ready": round((time.perf_counter_ns() - started) / 1_000_000, 3)}}
        self.set_status_message("已复用已验证试听缓存；未重新运行 FFmpeg。")
        self.stateChanged.emit()
        self.playPreview()

    @staticmethod
    def _stage_label(stage: str) -> str:
        return {"validating_request": "正在校验请求", "preparing_workspace": "正在准备试听", "starting_process": "正在启动 FFmpeg", "rendering": "正在变调", "waiting_process_exit": "正在等待 FFmpeg 退出", "validating_preview": "正在验证试听文件"}.get(stage, stage)

    def _require(self, capability: str, error_code: str) -> bool:
        if self.allows_capability(capability): return True
        self._fail(error_code, self.capability_gate.blockedMessage(capability)); return False

    def _fail(self, code: str, message: str, *, emit: bool = True) -> None:
        self._error_code, self._error_message = code, message; self.set_status_message(message)
        if emit: self.stateChanged.emit()
