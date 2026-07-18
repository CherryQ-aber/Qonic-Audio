from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
import re
from threading import Event

from PySide6.QtCore import Property, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QFileDialog

from ui_next.bridge.base_viewmodel import BaseViewModel
from ui_next.bridge.capabilities import COVER_WRITE, LYRICS_WRITE, METADATA_WRITE, CapabilityGate
from ui_next.bridge.cover_validation import read_and_validate_cover_file, validate_cover_bytes
from ui_next.bridge.edit_export_service import (
    EditExportRequest,
    EditExportService,
    LrcExportRequest,
    supported_edit_modules,
)

try:
    from lyrics import read_lrc_file_preview
except ImportError:  # pragma: no cover - optional runtime dependency guard
    read_lrc_file_preview = None


class _MetadataExportWorker(QThread):
    resultReady = Signal(dict)

    def __init__(self, service: EditExportService, request: EditExportRequest) -> None:
        super().__init__()
        self._service = service
        self._cancel_event = Event()
        self._request = replace(request, cancel_event=self._cancel_event)

    def cancel(self) -> None:
        self._cancel_event.set()

    def run(self) -> None:
        self.resultReady.emit(self._service.export(self._request))


class _LyricsExportWorker(QThread):
    resultReady = Signal(dict)

    def __init__(self, service: EditExportService, request, *, lrc_only: bool) -> None:
        super().__init__()
        self._service = service
        self._cancel_event = Event()
        self._request = replace(request, cancel_event=self._cancel_event)
        self._lrc_only = lrc_only

    def cancel(self) -> None:
        self._cancel_event.set()

    def run(self) -> None:
        if self._lrc_only:
            self.resultReady.emit(self._service.export_lrc(self._request))
        else:
            self.resultReady.emit(self._service.export(self._request))


class _CoverExportWorker(QThread):
    resultReady = Signal(dict)

    def __init__(self, service: EditExportService, request: EditExportRequest) -> None:
        super().__init__()
        self._service = service
        self._cancel_event = Event()
        self._request = replace(request, cancel_event=self._cancel_event)

    def cancel(self) -> None:
        self._cancel_event.set()

    def run(self) -> None:
        self.resultReady.emit(self._service.export(self._request))


class _UnifiedExportWorker(QThread):
    resultReady = Signal(dict)

    def __init__(self, service: EditExportService, request: EditExportRequest) -> None:
        super().__init__()
        self._service = service
        self._cancel_event = Event()
        self._request = replace(request, cancel_event=self._cancel_event)

    def cancel(self) -> None:
        self._cancel_event.set()

    def run(self) -> None:
        self.resultReady.emit(self._service.export(self._request))


class EditSessionViewModel(BaseViewModel):
    """In-memory metadata draft for one FileSession source file.

    The draft is deliberately independent from FileSession.  A successful
    export leaves the current source file untouched and does not switch the
    shared workspace to the generated copy.
    """

    stateChanged = Signal()

    _FIELDS = (
        "title",
        "artist",
        "album",
        "albumartist",
        "date",
        "genre",
        "tracknumber",
        "discnumber",
        "bpm",
        "initialkey",
        "comment",
    )
    _FIELD_ALIASES = {
        "albumartist": ("albumartist", "album_artist"),
        "date": ("date", "year"),
        "tracknumber": ("tracknumber", "track"),
        "discnumber": ("discnumber", "disc"),
    }
    _TIMESTAMP_RE = re.compile(r"\[\d{1,3}:\d{2}(?:[.:]\d{1,3})?\]")

    def __init__(
        self,
        capability_gate: CapabilityGate | None = None,
        export_service: EditExportService | None = None,
    ) -> None:
        super().__init__(capability_gate=capability_gate)
        # Preview/smoke keeps no real writer object. The service is created
        # lazily only after a capability-gated, explicit export request.
        self._export_service = export_service
        self._source_path = ""
        self._session_generation = 0
        self._original_metadata: dict[str, str] = {}
        self._draft_metadata: dict[str, str] = {}
        self._last_export_result: dict[str, object] = {}
        self._edit_state = "empty"
        self._export_worker: _MetadataExportWorker | None = None
        self._original_lyrics = ""
        self._draft_lyrics = ""
        self._lyrics_source = "none"
        self._selected_lyrics_source = "none"
        self._external_lrc_path = ""
        self._lyrics_sources: dict[str, dict[str, str]] = {}
        self._lyrics_clear_requested = False
        self._lyrics_imported_as_draft = False
        self._lyrics_source_before_import = "none"
        self._lyrics_last_export_result: dict[str, object] = {}
        self._lyrics_state = "empty"
        self._lyrics_export_worker: _LyricsExportWorker | None = None
        self._original_cover_data = b""
        self._original_cover_mime = ""
        self._original_cover_size = 0
        self._original_cover_width = 0
        self._original_cover_height = 0
        self._original_cover_preview_url = ""
        self._has_original_cover = False
        self._draft_cover_data = b""
        self._draft_cover_mime = ""
        self._draft_cover_size = 0
        self._draft_cover_width = 0
        self._draft_cover_height = 0
        self._draft_cover_preview_url = ""
        self._cover_action = "keep"
        self._cover_validation_state = "empty"
        self._cover_validation_error = ""
        self._cover_last_export_result: dict[str, object] = {}
        self._cover_state = "empty"
        self._cover_export_worker: _CoverExportWorker | None = None
        self._unified_export_worker: _UnifiedExportWorker | None = None
        self._unified_export_dialog_open = False
        self._unified_export_default_module = "metadata"
        self._unified_export_state = "idle"
        self._unified_export_output_path = ""
        self._unified_export_result: dict[str, object] = {}
        self._unified_export_validation_message = ""
        self._selected_export_modules: list[str] = []
        self._file_session = None
        self._audio_player = None
        self._active_export_generation = 0
        self._player_released_for_export = False
        self.set_status_message("当前没有文件信息编辑草稿。")

    def attach_runtime(self, file_session, audio_player) -> None:
        self._file_session = file_session
        self._audio_player = audio_player

    @Property(str, notify=stateChanged)
    def sourcePath(self) -> str:
        return self._source_path

    @Property(int, notify=stateChanged)
    def sessionGeneration(self) -> int:
        return self._session_generation

    @Property(bool, notify=stateChanged)
    def hasSession(self) -> bool:
        return bool(self._source_path)

    @Property("QVariantMap", notify=stateChanged)
    def originalMetadata(self) -> dict[str, str]:
        return dict(self._original_metadata)

    @Property("QVariantMap", notify=stateChanged)
    def draftMetadata(self) -> dict[str, str]:
        return dict(self._draft_metadata)

    @Property("QStringList", notify=stateChanged)
    def changedFields(self) -> list[str]:
        return [
            field for field in self._FIELDS
            if self._draft_metadata.get(field, "") != self._original_metadata.get(field, "")
        ]

    @Property(int, notify=stateChanged)
    def changedFieldCount(self) -> int:
        return len(self.changedFields)

    @Property(bool, notify=stateChanged)
    def dirty(self) -> bool:
        return bool(self.changedFields)

    @Property(bool, notify=stateChanged)
    def metadataDirty(self) -> bool:
        return self.dirty

    @Property(bool, notify=stateChanged)
    def metadataWriteEnabled(self) -> bool:
        return self.allows_capability(METADATA_WRITE)

    @Property(bool, notify=stateChanged)
    def canEdit(self) -> bool:
        return self.hasSession and not self.anyExporting

    @Property(bool, notify=stateChanged)
    def exporting(self) -> bool:
        return self._export_worker is not None

    @Property(bool, notify=stateChanged)
    def anyExporting(self) -> bool:
        return self.exporting or self.lyricsExporting or self.coverExporting or self.unifiedExporting

    @Property(bool, notify=stateChanged)
    def unifiedExporting(self) -> bool:
        return self._unified_export_worker is not None

    @Property(bool, notify=stateChanged)
    def unifiedExportDialogOpen(self) -> bool:
        return self._unified_export_dialog_open

    @Property(str, notify=stateChanged)
    def unifiedExportDefaultModule(self) -> str:
        return self._unified_export_default_module

    @Property(str, notify=stateChanged)
    def unifiedExportState(self) -> str:
        return self._unified_export_state

    @Property(str, notify=stateChanged)
    def unifiedExportOutputPath(self) -> str:
        return self._unified_export_output_path

    @Property("QVariantMap", notify=stateChanged)
    def unifiedExportResult(self) -> dict[str, object]:
        return dict(self._unified_export_result)

    @Property(str, notify=stateChanged)
    def unifiedExportMessage(self) -> str:
        return str(self._unified_export_result.get("message") or "")

    @Property(str, notify=stateChanged)
    def unifiedExportTimestamp(self) -> str:
        return str(self._unified_export_result.get("timestamp") or "")

    @Property(str, notify=stateChanged)
    def unifiedExportValidationMessage(self) -> str:
        return self._unified_export_validation_message

    @Property(str, notify=stateChanged)
    def editState(self) -> str:
        return self._edit_state

    @Property("QVariantMap", notify=stateChanged)
    def lastExportResult(self) -> dict[str, object]:
        return dict(self._last_export_result)

    @Property(str, notify=stateChanged)
    def lastExportMessage(self) -> str:
        return str(self._last_export_result.get("message") or "")

    @Property(str, notify=stateChanged)
    def lastExportOutputPath(self) -> str:
        return str(self._last_export_result.get("output_path") or "")

    @Property(str, notify=stateChanged)
    def originalLyrics(self) -> str:
        return self._original_lyrics

    @Property(str, notify=stateChanged)
    def draftLyrics(self) -> str:
        return self._draft_lyrics

    @Property(str, notify=stateChanged)
    def lyricsSource(self) -> str:
        return self._lyrics_source

    @Property(str, notify=stateChanged)
    def selectedLyricsSource(self) -> str:
        return self._selected_lyrics_source

    @Property(str, notify=stateChanged)
    def externalLrcPath(self) -> str:
        return self._external_lrc_path

    @Property("QVariantMap", notify=stateChanged)
    def availableLyricsSources(self) -> dict[str, dict[str, str]]:
        return {key: dict(value) for key, value in self._lyrics_sources.items()}

    @Property(bool, notify=stateChanged)
    def hasEmbeddedLyricsSource(self) -> bool:
        return "embedded" in self._lyrics_sources

    @Property(bool, notify=stateChanged)
    def hasSiblingLrcSource(self) -> bool:
        return "sibling_lrc" in self._lyrics_sources

    @Property(bool, notify=stateChanged)
    def hasManualLrcSource(self) -> bool:
        return "manual_lrc" in self._lyrics_sources

    @Property(bool, notify=stateChanged)
    def lyricsDirty(self) -> bool:
        return (
            self._lyrics_clear_requested
            or self._lyrics_imported_as_draft
            or self._draft_lyrics != self._original_lyrics
        )

    @Property(int, notify=stateChanged)
    def lyricsLineCount(self) -> int:
        return len(self._draft_lyrics.splitlines()) if self._draft_lyrics else 0

    @Property(bool, notify=stateChanged)
    def lyricsHasTimestamps(self) -> bool:
        return bool(self._TIMESTAMP_RE.search(self._draft_lyrics))

    @Property("QVariantList", notify=stateChanged)
    def originalLyricsLines(self) -> list[dict[str, object]]:
        return self._lyrics_lines(self._original_lyrics)

    @Property(str, notify=stateChanged)
    def lyricsEditState(self) -> str:
        return self._lyrics_state

    @Property(bool, notify=stateChanged)
    def lyricsExporting(self) -> bool:
        return self._lyrics_export_worker is not None

    @Property("QVariantMap", notify=stateChanged)
    def lastLyricsExportResult(self) -> dict[str, object]:
        return dict(self._lyrics_last_export_result)

    @Property(str, notify=stateChanged)
    def lastLyricsExportMessage(self) -> str:
        return str(self._lyrics_last_export_result.get("message") or "")

    @Property(bool, notify=stateChanged)
    def hasUnsavedLyricsDraft(self) -> bool:
        return self.lyricsDirty

    @Property(bool, notify=stateChanged)
    def coverWriteEnabled(self) -> bool:
        return self.allows_capability(COVER_WRITE)

    @Property(bool, notify=stateChanged)
    def hasOriginalCover(self) -> bool:
        return self._has_original_cover

    @Property(str, notify=stateChanged)
    def originalCoverMime(self) -> str:
        return self._original_cover_mime

    @Property(int, notify=stateChanged)
    def originalCoverSize(self) -> int:
        return self._original_cover_size

    @Property(str, notify=stateChanged)
    def originalCoverDimensions(self) -> str:
        return self._dimensions_text(self._original_cover_width, self._original_cover_height)

    @Property(str, notify=stateChanged)
    def originalCoverPreviewUrl(self) -> str:
        return self._original_cover_preview_url

    @Property(str, notify=stateChanged)
    def draftCoverMime(self) -> str:
        return self._draft_cover_mime

    @Property(int, notify=stateChanged)
    def draftCoverSize(self) -> int:
        return self._draft_cover_size

    @Property(str, notify=stateChanged)
    def draftCoverDimensions(self) -> str:
        return self._dimensions_text(self._draft_cover_width, self._draft_cover_height)

    @Property(str, notify=stateChanged)
    def draftCoverPreviewUrl(self) -> str:
        return self._draft_cover_preview_url

    @Property(str, notify=stateChanged)
    def coverAction(self) -> str:
        return self._cover_action

    @Property(bool, notify=stateChanged)
    def coverDirty(self) -> bool:
        return self._cover_action in {"replace", "remove"}

    @Property(str, notify=stateChanged)
    def coverValidationState(self) -> str:
        return self._cover_validation_state

    @Property(str, notify=stateChanged)
    def coverValidationError(self) -> str:
        return self._cover_validation_error

    @Property(str, notify=stateChanged)
    def coverEditState(self) -> str:
        return self._cover_state

    @Property(bool, notify=stateChanged)
    def coverExporting(self) -> bool:
        return self._cover_export_worker is not None

    @Property("QVariantMap", notify=stateChanged)
    def lastCoverExportResult(self) -> dict[str, object]:
        return dict(self._cover_last_export_result)

    @Property(str, notify=stateChanged)
    def lastCoverExportMessage(self) -> str:
        return str(self._cover_last_export_result.get("message") or "")

    @Property(bool, notify=stateChanged)
    def hasUnsavedCoverDraft(self) -> bool:
        return self.coverDirty

    @Property(bool, notify=stateChanged)
    def hasUnsavedDrafts(self) -> bool:
        return self.dirty or self.lyricsDirty or self.coverDirty

    @Property(bool, notify=stateChanged)
    def hasAnyDraft(self) -> bool:
        return self.hasUnsavedDrafts

    @Property("QStringList", notify=stateChanged)
    def selectedExportModules(self) -> list[str]:
        return list(self._selected_export_modules)

    @Property("QVariantMap", notify=stateChanged)
    def originalSnapshot(self) -> dict[str, object]:
        return {
            "metadata": dict(self._original_metadata),
            "lyrics": self._original_lyrics,
            "cover_action": "keep",
            "has_cover": self._has_original_cover,
        }

    @Property("QVariantMap", notify=stateChanged)
    def draftSnapshot(self) -> dict[str, object]:
        return {
            "metadata": dict(self._draft_metadata),
            "lyrics": self._draft_lyrics,
            "cover_action": self._cover_action,
            "has_cover": bool(self._draft_cover_data),
        }

    @Property("QStringList", notify=stateChanged)
    def unsavedDraftLabels(self) -> list[str]:
        labels: list[str] = []
        if self.dirty:
            labels.append("Metadata")
        if self.lyricsDirty:
            labels.append("Lyrics")
        if self.coverDirty:
            labels.append("Cover")
        return labels

    @Property(bool, notify=stateChanged)
    def lyricsWriteEnabled(self) -> bool:
        return self.allows_capability(LYRICS_WRITE)

    @Slot(str)
    def openUnifiedExportDialog(self, preferred_module: str = "auto") -> None:
        if not self.hasSession:
            self.set_status_message("当前没有可导出的编辑草稿。")
            return
        if self.anyExporting:
            self.set_status_message("正在导出编辑副本，请等待当前操作完成。")
            return
        if not self.hasUnsavedDrafts:
            self.set_status_message("当前没有可导出的编辑草稿。")
            return
        requested = str(preferred_module or "auto")
        available = {
            "metadata": self.dirty,
            "lyrics": self.lyricsDirty,
            "cover": self.coverDirty,
        }
        if not available.get(requested, False):
            requested = next((key for key, value in available.items() if value), "metadata")
        self._unified_export_default_module = requested
        self._unified_export_dialog_open = True
        self._unified_export_state = "idle"
        self._unified_export_validation_message = ""
        self.stateChanged.emit()

    @Slot()
    def closeUnifiedExportDialog(self) -> None:
        if self.unifiedExporting:
            self.set_status_message("正在导出编辑副本，完成后才能关闭导出对话框。")
            return
        self._unified_export_dialog_open = False
        self.stateChanged.emit()

    @Slot(str)
    def setUnifiedExportOutputPath(self, output_path: str) -> None:
        self._unified_export_output_path = str(output_path or "").strip()
        self._unified_export_state = "validating"
        error = self._validate_unified_output_path(self._unified_export_output_path)
        if error:
            self._unified_export_state = "failed"
            self._unified_export_validation_message = error[1]
        else:
            self._unified_export_state = "ready"
            self._unified_export_validation_message = "输出路径已通过预检；最终 no-clobber 仍会在发布前复核。"
        self.stateChanged.emit()

    @Slot()
    def chooseUnifiedExportOutputPath(self) -> None:
        if not self.hasSession or self.unifiedExporting:
            return
        source = Path(self._source_path)
        suggested = self._unified_export_output_path or str(
            source.with_name(f"{source.stem}_edited{source.suffix}")
        )
        selected_path, _selected_filter = QFileDialog.getSaveFileName(
            None,
            "选择新的编辑音频副本路径",
            suggested,
            f"{source.suffix.upper().lstrip('.')} 文件 (*{source.suffix});;所有文件 (*)",
        )
        if not selected_path:
            self.set_status_message("已取消选择导出路径；草稿保持不变。")
            return
        self.setUnifiedExportOutputPath(selected_path)

    @Slot(bool, bool, bool, result="QVariantMap")
    def unifiedExportPreflight(
        self,
        include_metadata: bool,
        include_lyrics: bool,
        include_cover: bool,
    ) -> dict[str, object]:
        selected = self._selected_operations(include_metadata, include_lyrics, include_cover)
        required = {
            "metadata": METADATA_WRITE,
            "lyrics": LYRICS_WRITE,
            "cover": COVER_WRITE,
        }
        missing = [required[name] for name in selected if not self.allows_capability(required[name])]
        supported = supported_edit_modules(self._source_path)
        unsupported = [name for name in selected if name not in supported]
        return {
            "selected_operations": selected,
            "required_capabilities": [required[name] for name in selected],
            "missing_capabilities": missing,
            "supported_modules": supported,
            "unsupported_modules": unsupported,
            "can_export": (
                bool(selected)
                and not missing
                and not unsupported
                and not self.unifiedExporting
            ),
        }

    @Slot(bool, bool, bool)
    def startUnifiedAudioExport(
        self,
        include_metadata: bool,
        include_lyrics: bool,
        include_cover: bool,
    ) -> None:
        if self.unifiedExporting or self.anyExporting:
            self.set_status_message("正在导出编辑副本，请等待当前操作完成。")
            return
        preflight = self.unifiedExportPreflight(include_metadata, include_lyrics, include_cover)
        selected = list(preflight["selected_operations"])
        if not selected:
            self._set_unified_failure("no_changes", "请至少选择一个存在修改的模块。")
            return
        missing = list(preflight["missing_capabilities"])
        if missing:
            self._unified_export_state = "capability_denied"
            self._set_unified_failure(
                "capability_denied",
                "所选内容当前无法导出。未创建临时副本。",
            )
            return
        unsupported = list(preflight.get("unsupported_modules") or [])
        if unsupported:
            self._set_unified_failure(
                "source_unsupported",
                "当前音频格式不支持所选编辑模块："
                + "、".join(unsupported)
                + "。未创建输出文件。",
            )
            return
        output_error = self._validate_unified_output_path(self._unified_export_output_path)
        if output_error:
            self._set_unified_failure(*output_error)
            return
        if include_cover and self.coverDirty and self._cover_action == "replace":
            validation = validate_cover_bytes(self._draft_cover_data)
            if not validation.get("ok") or validation.get("mime") != self._draft_cover_mime:
                self._set_unified_failure(
                    str(validation.get("error_code") or "cover_write_failed"),
                    str(validation.get("message") or "封面草稿验证失败。"),
                )
                return
        request = EditExportRequest(
            source_path=self._source_path,
            output_path=self._unified_export_output_path,
            metadata_changes=dict(self._draft_metadata) if include_metadata and self.dirty else None,
            lyrics_text=self._draft_lyrics if include_lyrics and self.lyricsDirty else None,
            cover_action=self._cover_action if include_cover and self.coverDirty else "keep",
            cover_data=self._draft_cover_data if include_cover and self._cover_action == "replace" else None,
            cover_mime=self._draft_cover_mime if include_cover and self._cover_action == "replace" else "",
        )
        if not self._prepare_audio_export():
            self._set_unified_failure(
                "player_release_failed",
                "播放器未能释放当前媒体源，已取消导出。",
            )
            return
        self._selected_export_modules = selected
        self._unified_export_state = "exporting"
        self._unified_export_validation_message = "正在创建并验证新的音频副本。"
        self.set_status_message("正在安全导出编辑副本；原文件不会被覆盖。")
        worker = _UnifiedExportWorker(self._service_for_export(), request)
        self._unified_export_worker = worker
        worker.resultReady.connect(self._apply_unified_export_result)
        worker.finished.connect(worker.deleteLater)
        worker.start()
        self.stateChanged.emit()

    @Slot()
    def cancelExport(self) -> None:
        worker = (
            self._unified_export_worker
            or self._export_worker
            or self._lyrics_export_worker
            or self._cover_export_worker
        )
        if worker is None:
            return
        cancel = getattr(worker, "cancel", None)
        if callable(cancel):
            cancel()
        self._unified_export_state = "cancelling"
        self._unified_export_validation_message = "正在取消导出；不会发布正式输出。"
        self.set_status_message("正在取消导出；草稿将继续保留。")
        self.stateChanged.emit()

    @Property(bool, notify=stateChanged)
    def canLoadUnifiedExportResult(self) -> bool:
        path = str(self._unified_export_result.get("output_path") or "")
        return bool(
            self._unified_export_result.get("success")
            and path
            and Path(path).is_file()
            and not self.anyExporting
        )

    @Slot()
    def loadUnifiedExportResultAsCurrent(self) -> None:
        if not self.canLoadUnifiedExportResult or self._file_session is None:
            self.set_status_message("当前没有可载入的已验证导出结果。")
            return
        output_path = str(self._unified_export_result.get("output_path") or "")
        if self._audio_player is not None:
            prepare = getattr(self._audio_player, "prepareForFileOperation", None)
            if callable(prepare) and not prepare():
                self.set_status_message("播放器未能释放媒体源，已取消载入导出结果。")
                return
        outcome = self._file_session.setCurrentFile(
            output_path,
            "edit_export_result",
        )
        if outcome in {"loaded", "unchanged"}:
            self.discardAllDraftsForResultLoad()
        self.set_status_message(
            "已载入导出结果并重新读取文件信息。"
            if outcome in {"loaded", "unchanged"}
            else "无法载入导出结果；请确认文件仍然存在。"
        )

    @Slot()
    def discardAllDraftsForResultLoad(self) -> None:
        self._draft_metadata = dict(self._original_metadata)
        self._draft_lyrics = self._original_lyrics
        self._lyrics_clear_requested = False
        self._lyrics_imported_as_draft = False
        self._restore_original_cover_state()
        self._cover_action = "keep"
        self._edit_state = "loaded" if self.hasSession else "empty"
        self._lyrics_state = "loaded" if self.hasSession else "empty"
        self._cover_state = (
            "loaded" if self._has_original_cover else "no_cover"
        ) if self.hasSession else "empty"
        self.stateChanged.emit()

    @Slot()
    def copyUnifiedExportOutputPath(self) -> None:
        output_path = str(self._unified_export_result.get("output_path") or "")
        if not output_path:
            self.set_status_message("当前没有可复制的导出路径。")
            return
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(output_path)
            self.set_status_message("已复制导出路径。")

    @Slot()
    def openUnifiedExportLocation(self) -> None:
        output_path = str(self._unified_export_result.get("output_path") or "")
        if not output_path:
            self.set_status_message("当前没有可打开的导出位置。")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(output_path).parent)))

    @Slot(str, int)
    def beginCurrentFile(self, path: str, generation: int) -> None:
        self._clear_draft("正在读取新文件的信息；已丢弃上一文件的编辑草稿。")
        self._clear_lyrics_draft()
        self._clear_cover_draft()
        self._reset_unified_export_state()
        self._source_path = str(path or "")
        self._session_generation = int(generation)
        self.stateChanged.emit()

    @Slot()
    def clear(self) -> None:
        self._clear_draft("当前文件已清除；编辑草稿已丢弃，未删除任何磁盘文件。")
        self._clear_lyrics_draft()
        self._clear_cover_draft()
        self._reset_unified_export_state()
        self._session_generation = 0
        self.stateChanged.emit()

    def loadCoverResult(self, result: dict) -> None:
        if not self._result_matches_session(result):
            return
        path = str(result.get("path") or self._source_path or "").strip()
        if path:
            self._source_path = path
        self._cover_last_export_result = {}
        if not result.get("ok", result.get("success", False)):
            self._cover_state = "error"
            self._cover_validation_state = "error"
            self._cover_validation_error = str(result.get("error") or "封面读取失败。")
            self.stateChanged.emit()
            return
        if not bool(result.get("has_cover")):
            self._clear_cover_draft()
            self._cover_state = "no_cover"
            self._cover_validation_state = "ready"
            self.stateChanged.emit()
            return

        raw = bytes(result.get("cover_data") or b"")
        validated = validate_cover_bytes(raw, enforce_size_limit=False) if raw else None
        self._has_original_cover = True
        self._original_cover_data = raw if validated and validated.get("ok") else b""
        self._original_cover_mime = str(
            (validated or {}).get("mime") or result.get("cover_mime") or result.get("mime") or ""
        )
        self._original_cover_size = int((validated or {}).get("byte_size") or result.get("byte_size") or 0)
        self._original_cover_width = int((validated or {}).get("width") or result.get("width") or 0)
        self._original_cover_height = int((validated or {}).get("height") or result.get("height") or 0)
        self._original_cover_preview_url = str(
            (validated or {}).get("preview_data_url") or result.get("preview_data_url") or ""
        )
        self._restore_original_cover_state()
        self._cover_state = "loaded"
        self._cover_validation_state = "ready"
        self._cover_validation_error = ""
        self.stateChanged.emit()

    @Slot()
    def chooseReplacementCover(self) -> None:
        if not self.hasSession or self.anyExporting:
            return
        selected_path, _selected_filter = QFileDialog.getOpenFileName(
            None,
            "选择替换封面（仅 JPEG / PNG）",
            "",
            "图片文件 (*.jpg *.jpeg *.png);;所有文件 (*)",
        )
        if not selected_path:
            self.set_status_message("已取消选择替换封面；当前草稿保持不变。")
            return
        validation = read_and_validate_cover_file(selected_path)
        if not validation.get("ok"):
            self._cover_validation_state = "error"
            self._cover_validation_error = str(validation.get("message") or "封面图片验证失败。")
            self._cover_state = "failed"
            self.set_status_message(self._cover_validation_error)
            self.stateChanged.emit()
            return
        self._set_draft_cover_from_validation(validation)
        self._cover_action = "replace"
        self._cover_state = "modified"
        self._cover_validation_state = "ready"
        self._cover_validation_error = ""
        self._cover_last_export_result = {}
        self.set_status_message("已选择新的封面草稿；尚未写入任何音频文件。")
        self.stateChanged.emit()

    @Slot()
    def removeCoverDraft(self) -> None:
        if not self.hasSession or self.anyExporting:
            return
        if not self._has_original_cover:
            self.set_status_message("源音频当前没有封面，移除操作不会创建修改草稿。")
            return
        self._draft_cover_data = b""
        self._draft_cover_mime = ""
        self._draft_cover_size = 0
        self._draft_cover_width = 0
        self._draft_cover_height = 0
        self._draft_cover_preview_url = ""
        self._cover_action = "remove"
        self._cover_state = "modified"
        self._cover_validation_state = "ready"
        self._cover_validation_error = ""
        self._cover_last_export_result = {}
        self.set_status_message("封面草稿将于导出到新音频副本时移除；源文件未修改。")
        self.stateChanged.emit()

    @Slot()
    def restoreOriginalCover(self) -> None:
        if not self.hasSession or self.anyExporting:
            return
        self._restore_original_cover_state()
        self._cover_action = "keep"
        self._cover_state = "loaded" if self._has_original_cover else "no_cover"
        self._cover_validation_state = "ready"
        self._cover_validation_error = ""
        self._cover_last_export_result = {}
        self.set_status_message("已恢复原始封面状态；未写入任何音频文件。")
        self.stateChanged.emit()

    @Slot(bool, bool)
    def chooseCoverAudioExport(self, include_metadata: bool = False, include_lyrics: bool = False) -> None:
        if not self._check_cover_exportable():
            return
        source = Path(self._source_path)
        selected_path, _selected_filter = QFileDialog.getSaveFileName(
            None,
            "导出封面修改（另存新音频副本）",
            str(source.with_name(f"{source.stem}_cover{source.suffix}")),
            f"{source.suffix.upper().lstrip('.')} 文件 (*{source.suffix});;所有文件 (*)",
        )
        if not selected_path:
            self.set_status_message("已取消封面音频副本导出；草稿仍保留在内存中。")
            return
        self.exportCoverToAudioPath(selected_path, include_metadata, include_lyrics)

    @Slot(str, bool, bool)
    def exportCoverToAudioPath(
        self,
        output_path: str,
        include_metadata: bool = False,
        include_lyrics: bool = False,
    ) -> None:
        if not self._check_cover_exportable():
            return
        request = EditExportRequest(
            source_path=self._source_path,
            output_path=str(output_path or ""),
            metadata_changes=dict(self._draft_metadata) if include_metadata and self.dirty else None,
            lyrics_text=self._draft_lyrics if include_lyrics and self.lyricsDirty else None,
            cover_action=self._cover_action,
            cover_data=self._draft_cover_data if self._cover_action == "replace" else None,
            cover_mime=self._draft_cover_mime if self._cover_action == "replace" else "",
        )
        if not self._prepare_audio_export():
            self._cover_last_export_result = {
                "success": False,
                "error_code": "player_release_failed",
                "message": "播放器未能释放当前媒体源，已取消导出。",
            }
            self.stateChanged.emit()
            return
        self._cover_state = "writing"
        self.set_status_message("正在安全导出含封面草稿的新音频副本；原文件不会被覆盖。")
        worker = _CoverExportWorker(self._service_for_export(), request)
        self._cover_export_worker = worker
        worker.resultReady.connect(self._apply_cover_export_result)
        worker.finished.connect(worker.deleteLater)
        worker.start()
        self.stateChanged.emit()

    def loadMetadataResult(self, result: dict) -> None:
        if not self._result_matches_session(result):
            return
        if not result.get("ok", result.get("success", False)):
            self._original_metadata = {}
            self._draft_metadata = {}
            self._last_export_result = {}
            self._edit_state = "error"
            self.set_status_message("文件信息读取失败；当前文件会话仍然保留。")
            self.stateChanged.emit()
            return

        path = str(result.get("path") or "").strip()
        if not path:
            self._original_metadata = {}
            self._draft_metadata = {}
            self._last_export_result = {}
            self._edit_state = "error"
            self.set_status_message(
                "文件信息读取未返回有效路径；当前文件会话仍然保留。"
            )
            self.stateChanged.emit()
            return

        self._source_path = path
        self._original_metadata = {
            field: self._result_value(result, field) for field in self._FIELDS
        }
        self._draft_metadata = dict(self._original_metadata)
        self._last_export_result = {}
        self._edit_state = "loaded"
        self.set_status_message("已创建内存编辑草稿；修改不会立即写入音频文件。")
        self.stateChanged.emit()

    def loadLyricsResult(self, result: dict) -> None:
        """Create one source-specific lyrics draft without merging sources."""
        if not self._result_matches_session(result):
            return
        path = str(result.get("path") or self._source_path or "").strip()
        if not path:
            return
        self._source_path = path
        sources: dict[str, dict[str, str]] = {}
        embedded_text = str(result.get("lyrics_text") or "")
        if bool(result.get("has_lyrics")) and embedded_text.strip():
            sources["embedded"] = {
                "text": embedded_text,
                "label": "音频内嵌歌词",
                "path": "",
            }
        external = result.get("external_lrc_result") or {}
        external_text = str(external.get("lyrics_text") or "")
        external_path = str(result.get("external_lrc_path") or "")
        if external.get("ok") and external_text.strip():
            sources["sibling_lrc"] = {
                "text": external_text,
                "label": "同名外部 LRC",
                "path": external_path,
            }
        self._lyrics_sources = sources
        self._external_lrc_path = external_path
        self._lyrics_imported_as_draft = False
        self._lyrics_source_before_import = "none"
        if "embedded" in sources:
            self._apply_lyrics_source("embedded")
        elif "sibling_lrc" in sources:
            self._apply_lyrics_source("sibling_lrc")
        else:
            self._selected_lyrics_source = "none"
            self._lyrics_source = "none"
            self._original_lyrics = ""
            self._draft_lyrics = ""
            self._lyrics_clear_requested = False
            self._lyrics_state = "ready"
        self.stateChanged.emit()

    @Slot("QVariantMap", result=bool)
    def applyImportedLyricsDraft(self, result: dict) -> bool:
        """Apply a generation-checked external LRC as an in-memory draft."""
        if not self._result_matches_session(
            {
                "path": result.get("audio_path"),
                "session_generation": result.get("session_generation"),
            }
        ):
            return False
        if not result.get("ok", result.get("success", False)):
            return False
        lyrics_path = str(result.get("path") or "").strip()
        lyrics_text = str(result.get("lyrics_text") or "")
        if not lyrics_path:
            return False
        self._lyrics_source_before_import = self._selected_lyrics_source
        self._lyrics_sources["manual_lrc"] = {
            "text": lyrics_text,
            "label": "手动导入的 LRC 草稿",
            "path": lyrics_path,
        }
        self._selected_lyrics_source = "manual_lrc"
        self._lyrics_source = "manual_lrc"
        self._external_lrc_path = lyrics_path
        self._draft_lyrics = lyrics_text
        self._lyrics_clear_requested = False
        self._lyrics_imported_as_draft = True
        self._lyrics_last_export_result = {}
        self._lyrics_state = "modified"
        self.set_status_message(
            "外置 LRC 已载入内存草稿；原音频和原 .lrc 均未修改。"
        )
        self.stateChanged.emit()
        return True

    @Slot(str)
    def updateLyricsDraft(self, text: str) -> None:
        if not self.hasSession or self.lyricsExporting:
            return
        normalized = str(text or "")
        if normalized == self._draft_lyrics and not self._lyrics_clear_requested:
            return
        self._draft_lyrics = normalized
        self._lyrics_clear_requested = False
        self._lyrics_state = "modified" if self.lyricsDirty else "loaded"
        self.set_status_message(
            "歌词草稿已修改；尚未写入音频或 .lrc 文件。"
            if self.lyricsDirty else "歌词草稿与当前来源一致；尚未写入文件。"
        )
        self.stateChanged.emit()

    @Slot()
    def saveLyricsDraft(self) -> None:
        if not self.hasSession:
            self.set_status_message("当前没有可保存的歌词草稿。")
            return
        self.set_status_message("歌词草稿已保留在本次运行内存中；未写入音频或 .lrc 文件。")

    @Slot()
    def restoreOriginalLyrics(self) -> None:
        if not self.hasSession or self.lyricsExporting:
            return
        self._draft_lyrics = self._original_lyrics
        self._lyrics_clear_requested = False
        self._lyrics_imported_as_draft = False
        if (
            self._selected_lyrics_source == "manual_lrc"
            and self._lyrics_source_before_import in self._lyrics_sources
        ):
            self._selected_lyrics_source = self._lyrics_source_before_import
            self._lyrics_source = self._lyrics_source_before_import
            source_data = self._lyrics_sources[self._lyrics_source_before_import]
            self._original_lyrics = str(source_data.get("text") or "")
            self._draft_lyrics = self._original_lyrics
            self._external_lrc_path = str(source_data.get("path") or "")
        self._lyrics_source_before_import = "none"
        self._lyrics_state = "loaded"
        self._lyrics_last_export_result = {}
        self.set_status_message("已恢复当前歌词来源的原始文本；未写入文件。")
        self.stateChanged.emit()

    @Slot()
    def clearLyricsDraft(self) -> None:
        if not self.hasSession or self.lyricsExporting:
            return
        self._draft_lyrics = ""
        self._lyrics_clear_requested = True
        self._lyrics_state = "modified"
        self.set_status_message("已清空内存歌词草稿；空草稿不会自动解释为删除歌词。")
        self.stateChanged.emit()

    @Slot(str, bool, result=str)
    def selectLyricsSource(self, source: str, discard_dirty: bool = False) -> str:
        source = str(source or "").strip()
        if source not in self._lyrics_sources:
            return "lyrics_source_missing"
        if self.lyricsDirty and not discard_dirty and source != self._selected_lyrics_source:
            self.set_status_message("当前歌词有未导出的修改；请确认放弃草稿后再切换来源。")
            return "unsaved_changes"
        self._apply_lyrics_source(source)
        self.set_status_message("已切换歌词草稿来源；未合并或修改任何磁盘文件。")
        self.stateChanged.emit()
        return "ok"

    @Slot(bool, result=str)
    def chooseManualLrc(self, discard_dirty: bool = False) -> str:
        if not self.hasSession:
            self.set_status_message("当前没有工作区音频文件，无法关联手动 LRC 草稿。")
            return "lyrics_source_missing"
        if self.lyricsDirty and not discard_dirty:
            self.set_status_message("当前歌词有未导出的修改；请确认放弃草稿后再选择 LRC。")
            return "unsaved_changes"
        selected_path, _selected_filter = QFileDialog.getOpenFileName(
            None, "选择 .lrc 作为歌词草稿来源", "", "LRC 歌词 (*.lrc *.LRC)"
        )
        if not selected_path:
            self.set_status_message("已取消选择 .lrc 草稿来源。")
            return "cancelled"
        if not self.allows_capability("lyrics_read"):
            self.set_status_message("当前未启用 lyrics_read，不能读取 .lrc 草稿来源。")
            return "capability_denied"
        if read_lrc_file_preview is None:
            self.set_status_message("LRC 只读接口不可用。")
            return "lrc_read_failed"
        try:
            result = read_lrc_file_preview(selected_path)
        except Exception as exc:
            self.set_status_message(f"LRC 读取异常：{exc}")
            return "lrc_read_failed"
        if not result.get("ok"):
            self.set_status_message(str(result.get("error") or "LRC 读取失败。"))
            return "lrc_read_failed"
        payload = dict(result)
        payload.update(
            {
                "path": str(selected_path),
                "audio_path": self._source_path,
                "session_generation": self._session_generation,
            }
        )
        return "ok" if self.applyImportedLyricsDraft(payload) else "lrc_read_failed"

    @Slot(bool)
    def chooseLyricsAudioExport(self, include_metadata: bool = False) -> None:
        self.chooseLyricsAudioExportWithSelections(include_metadata, False)

    @Slot(bool, bool)
    def chooseLyricsAudioExportWithSelections(
        self,
        include_metadata: bool = False,
        include_cover: bool = False,
    ) -> None:
        if not self._check_lyrics_exportable(allow_empty=True):
            return
        source = Path(self._source_path)
        selected_path, _selected_filter = QFileDialog.getSaveFileName(
            None,
            "导出歌词修改（另存新音频副本）",
            str(source.with_name(f"{source.stem}_lyrics{source.suffix}")),
            f"{source.suffix.upper().lstrip('.')} 文件 (*{source.suffix});;所有文件 (*)",
        )
        if not selected_path:
            self.set_status_message("已取消歌词音频副本导出；草稿仍保留在内存中。")
            return
        self.exportLyricsToAudioPathWithSelections(selected_path, include_metadata, include_cover)

    @Slot(str, bool)
    def exportLyricsToAudioPath(self, output_path: str, include_metadata: bool = False) -> None:
        self.exportLyricsToAudioPathWithSelections(output_path, include_metadata, False)

    @Slot(str, bool, bool)
    def exportLyricsToAudioPathWithSelections(
        self,
        output_path: str,
        include_metadata: bool = False,
        include_cover: bool = False,
    ) -> None:
        if not self._check_lyrics_exportable(allow_empty=True):
            return
        metadata_changes = dict(self._draft_metadata) if include_metadata and self.dirty else None
        request = EditExportRequest(
            source_path=self._source_path,
            output_path=str(output_path or ""),
            metadata_changes=metadata_changes,
            lyrics_text=self._draft_lyrics,
            cover_action=self._cover_action if include_cover and self.coverDirty else "keep",
            cover_data=self._draft_cover_data if include_cover and self._cover_action == "replace" else None,
            cover_mime=self._draft_cover_mime if include_cover and self._cover_action == "replace" else "",
        )
        if not self._prepare_audio_export():
            self._lyrics_last_export_result = {
                "success": False,
                "error_code": "player_release_failed",
                "message": "播放器未能释放当前媒体源，已取消导出。",
            }
            self.stateChanged.emit()
            return
        self._start_lyrics_export(request, lrc_only=False)

    @Slot()
    def chooseLrcExport(self) -> None:
        if not self._check_lyrics_exportable():
            return
        source = Path(self._source_path)
        selected_path, _selected_filter = QFileDialog.getSaveFileName(
            None,
            "另存歌词为新的 .lrc 文件",
            str(source.with_suffix(".lrc")),
            "LRC 歌词 (*.lrc)",
        )
        if not selected_path:
            self.set_status_message("已取消 LRC 导出；草稿仍保留在内存中。")
            return
        self.exportLyricsToLrcPath(selected_path)

    @Slot(str)
    def exportLyricsToLrcPath(self, output_path: str) -> None:
        if not self._check_lyrics_exportable():
            return
        request = LrcExportRequest(
            source_path=self._source_path,
            output_path=str(output_path or ""),
            lyrics_text=self._draft_lyrics,
            original_lrc_path=self._lyrics_sources.get(self._selected_lyrics_source, {}).get("path", ""),
        )
        self._start_lyrics_export(request, lrc_only=True)

    @Slot(str, str)
    def updateField(self, field: str, value: str) -> None:
        if field not in self._FIELDS or not self.hasSession or self.exporting:
            return
        normalized = str(value or "").strip()
        if self._draft_metadata.get(field, "") == normalized:
            return
        self._draft_metadata[field] = normalized
        self._edit_state = "modified" if self.dirty else "loaded"
        self.set_status_message(
            f"编辑草稿已修改 {self.changedFieldCount} 项；尚未写入任何文件。"
            if self.dirty else "编辑草稿与原始信息一致；尚未写入任何文件。"
        )
        self.stateChanged.emit()

    @Slot()
    def saveDraft(self) -> None:
        if not self.hasSession:
            self.set_status_message("没有可保存的编辑草稿。")
            return
        self.set_status_message("编辑草稿已保留在本次运行内存中；未写入音频或配置文件。")

    @Slot()
    def restoreOriginal(self) -> None:
        if not self.hasSession or self.exporting:
            return
        self._draft_metadata = dict(self._original_metadata)
        self._edit_state = "loaded"
        self._last_export_result = {}
        self.set_status_message("已恢复原始文件信息；未修改任何磁盘文件。")
        self.stateChanged.emit()

    @Slot()
    def chooseExportPath(self) -> None:
        self.chooseMetadataAudioExport(False, False)

    @Slot(bool, bool)
    def chooseMetadataAudioExport(self, include_lyrics: bool = False, include_cover: bool = False) -> None:
        if not self._check_exportable():
            return
        source = Path(self._source_path)
        selected_path, _selected_filter = QFileDialog.getSaveFileName(
            None,
            "导出文件信息修改（另存新文件）",
            str(source.with_name(f"{source.stem}_edited{source.suffix}")),
            f"{source.suffix.upper().lstrip('.')} 文件 (*{source.suffix});;所有文件 (*)",
        )
        if not selected_path:
            self.set_status_message("已取消导出；编辑草稿仍仅保存在内存中。")
            return
        self.exportMetadataToAudioPath(selected_path, include_lyrics, include_cover)

    @Slot(str)
    def exportDraftToPath(self, output_path: str) -> None:
        self.exportMetadataToAudioPath(output_path, False, False)

    @Slot(str, bool, bool)
    def exportMetadataToAudioPath(
        self,
        output_path: str,
        include_lyrics: bool = False,
        include_cover: bool = False,
    ) -> None:
        if not self._check_exportable():
            return
        request = EditExportRequest(
            source_path=self._source_path,
            output_path=str(output_path or ""),
            metadata_changes=dict(self._draft_metadata),
            lyrics_text=self._draft_lyrics if include_lyrics and self.lyricsDirty else None,
            cover_action=self._cover_action if include_cover and self.coverDirty else "keep",
            cover_data=self._draft_cover_data if include_cover and self._cover_action == "replace" else None,
            cover_mime=self._draft_cover_mime if include_cover and self._cover_action == "replace" else "",
        )
        if not self._prepare_audio_export():
            self._last_export_result = {
                "success": False,
                "error_code": "player_release_failed",
                "message": "播放器未能释放当前媒体源，已取消导出。",
            }
            self.stateChanged.emit()
            return
        self._edit_state = "writing"
        self.set_status_message("正在安全导出编辑副本；原文件不会被覆盖。")
        worker = _MetadataExportWorker(self._service_for_export(), request)
        self._export_worker = worker
        worker.resultReady.connect(self._apply_export_result)
        worker.finished.connect(worker.deleteLater)
        worker.start()
        self.stateChanged.emit()

    def _check_exportable(self) -> bool:
        if not self.hasSession:
            self.set_status_message("当前没有可导出的编辑草稿。")
            return False
        if self.anyExporting:
            self.set_status_message("正在导出编辑副本，请等待当前操作完成。")
            return False
        if not self.dirty:
            self.set_status_message("编辑草稿没有修改，无需导出。")
            return False
        return True

    def _apply_export_result(self, result: dict) -> None:
        self._export_worker = None
        self._finish_audio_export_transaction()
        self._last_export_result = dict(result or {})
        self._record_unified_export_result(result)
        if result.get("success"):
            self._edit_state = "success"
            self.set_status_message(
                f"已生成新文件：{result.get('output_path')}。当前工作区仍保持原文件。"
            )
        else:
            self._edit_state = "failed"
            self.set_status_message(str(result.get("message") or "编辑副本导出失败。"))
        self.stateChanged.emit()

    def _check_lyrics_exportable(self, *, allow_empty: bool = False) -> bool:
        if not self.hasSession:
            self.set_status_message("当前没有可导出的歌词草稿。")
            return False
        if self.lyricsExporting:
            self.set_status_message("正在导出歌词，请等待当前操作完成。")
            return False
        if not self.lyricsDirty:
            self.set_status_message("歌词草稿没有修改，无需导出。")
            return False
        if not allow_empty and not self._draft_lyrics.strip():
            self._lyrics_last_export_result = {
                "success": False,
                "error_code": "lyrics_draft_empty",
                "message": "空歌词不会自动解释为删除操作；请恢复原始歌词或输入内容。",
            }
            self._lyrics_state = "failed"
            self.set_status_message(str(self._lyrics_last_export_result["message"]))
            self.stateChanged.emit()
            return False
        return True

    def _start_lyrics_export(self, request, *, lrc_only: bool) -> None:
        self._lyrics_state = "writing"
        self.set_status_message(
            "正在安全导出新的 .lrc 文件；不会覆盖原始歌词文件。"
            if lrc_only else "正在安全导出含歌词的新音频副本；原文件不会被覆盖。"
        )
        worker = _LyricsExportWorker(
            self._service_for_export(),
            request,
            lrc_only=lrc_only,
        )
        self._lyrics_export_worker = worker
        worker.resultReady.connect(self._apply_lyrics_export_result)
        worker.finished.connect(worker.deleteLater)
        worker.start()
        self.stateChanged.emit()

    def _apply_lyrics_export_result(self, result: dict) -> None:
        self._lyrics_export_worker = None
        if list(result.get("applied_operations") or []) != ["lrc"]:
            self._finish_audio_export_transaction()
        self._lyrics_last_export_result = dict(result or {})
        if list(result.get("applied_operations") or []) != ["lrc"]:
            self._record_unified_export_result(result)
        if result.get("success"):
            self._lyrics_state = "success"
            self.set_status_message(
                f"已生成新输出：{result.get('output_path')}。当前工作区仍保持原文件。"
            )
        else:
            self._lyrics_state = "failed"
            self.set_status_message(str(result.get("message") or "歌词导出失败。"))
        self.stateChanged.emit()

    def _check_cover_exportable(self) -> bool:
        if not self.hasSession:
            self.set_status_message("当前没有可导出的封面草稿。")
            return False
        if self.anyExporting:
            self.set_status_message("正在导出编辑副本，请等待当前操作完成。")
            return False
        if not self.coverDirty:
            self._cover_last_export_result = {
                "success": False,
                "error_code": "no_cover_changes",
                "message": "封面草稿没有修改，无需导出。",
            }
            self.set_status_message(str(self._cover_last_export_result["message"]))
            self.stateChanged.emit()
            return False
        if self._cover_action == "replace":
            validation = validate_cover_bytes(self._draft_cover_data)
            if not validation.get("ok") or validation.get("mime") != self._draft_cover_mime:
                self._cover_last_export_result = {
                    "success": False,
                    "error_code": str(validation.get("error_code") or "cover_write_failed"),
                    "message": str(validation.get("message") or "封面草稿验证失败。"),
                }
                self._cover_state = "failed"
                self.set_status_message(str(self._cover_last_export_result["message"]))
                self.stateChanged.emit()
                return False
        return True

    def _apply_cover_export_result(self, result: dict) -> None:
        self._cover_export_worker = None
        self._finish_audio_export_transaction()
        self._cover_last_export_result = dict(result or {})
        self._record_unified_export_result(result)
        if result.get("success"):
            self._cover_state = "success"
            self.set_status_message(
                f"已生成新输出：{result.get('output_path')}。当前工作区仍保持原文件，封面草稿未自动清除。"
            )
        else:
            self._cover_state = "failed"
            self.set_status_message(str(result.get("message") or "封面导出失败。"))
        self.stateChanged.emit()

    def _apply_unified_export_result(self, result: dict) -> None:
        self._unified_export_worker = None
        self._finish_audio_export_transaction()
        self._record_unified_export_result(result)
        if result.get("success"):
            self._unified_export_state = "success"
            self._unified_export_validation_message = (
                "修改已导出到副本；当前源文件仍未包含这些修改，草稿保持未保存状态。"
            )
            self.set_status_message(
                f"已生成新输出：{result.get('output_path')}。当前工作区仍保持原文件。"
            )
        else:
            self._unified_export_state = (
                "cancelled"
                if result.get("error_code") == "export_cancelled"
                else "failed"
            )
            self._unified_export_validation_message = str(result.get("message") or "编辑副本导出失败。")
            self.set_status_message(self._unified_export_validation_message)
        self.stateChanged.emit()

    def _record_unified_export_result(self, result: dict) -> None:
        record = dict(result or {})
        record["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._unified_export_result = record

    def _set_unified_failure(self, error_code: str, message: str) -> None:
        self._unified_export_result = {
            "success": False,
            "error_code": str(error_code),
            "message": str(message),
            "output_path": self._unified_export_output_path,
            "applied_operations": [],
            "appliedModules": [],
            "skippedModules": [],
            "failedModules": [],
            "sourceUnchanged": True,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        if self._unified_export_state != "capability_denied":
            self._unified_export_state = "failed"
        self._unified_export_validation_message = str(message)
        self.set_status_message(str(message))
        self.stateChanged.emit()

    def _selected_operations(
        self,
        include_metadata: bool,
        include_lyrics: bool,
        include_cover: bool,
    ) -> list[str]:
        selected: list[str] = []
        if include_metadata and self.dirty:
            selected.append("metadata")
        if include_lyrics and self.lyricsDirty:
            selected.append("lyrics")
        if include_cover and self.coverDirty:
            selected.append("cover")
        return selected

    def _validate_unified_output_path(self, output_path: str) -> tuple[str, str] | None:
        raw_output = str(output_path or "").strip()
        if not raw_output:
            return "output_required", "必须手动选择全新的音频输出路径。"
        if not self._source_path:
            return "source_missing", "当前没有源音频文件。"
        try:
            source = Path(self._source_path).expanduser().resolve()
            output = Path(raw_output).expanduser().resolve()
        except OSError as exc:
            return "output_required", f"无法规范化输出路径：{exc}"
        if str(source).casefold() == str(output).casefold():
            return "output_same_as_source", "输出路径不能与当前源文件相同。"
        if source.suffix.lower() != output.suffix.lower():
            return "output_extension_mismatch", "输出文件扩展名必须与源文件一致。"
        if output.exists():
            return "output_exists", "输出路径已存在，系统不会覆盖已有文件。"
        return None

    def _reset_unified_export_state(self) -> None:
        self._unified_export_dialog_open = False
        self._unified_export_default_module = "metadata"
        self._unified_export_state = "idle"
        self._unified_export_output_path = ""
        self._unified_export_result = {}
        self._unified_export_validation_message = ""
        self._selected_export_modules = []

    def _set_draft_cover_from_validation(self, validation: dict) -> None:
        self._draft_cover_data = bytes(validation.get("data") or b"")
        self._draft_cover_mime = str(validation.get("mime") or "")
        self._draft_cover_size = int(validation.get("byte_size") or 0)
        self._draft_cover_width = int(validation.get("width") or 0)
        self._draft_cover_height = int(validation.get("height") or 0)
        self._draft_cover_preview_url = str(validation.get("preview_data_url") or "")

    def _restore_original_cover_state(self) -> None:
        self._draft_cover_data = bytes(self._original_cover_data)
        self._draft_cover_mime = self._original_cover_mime
        self._draft_cover_size = self._original_cover_size
        self._draft_cover_width = self._original_cover_width
        self._draft_cover_height = self._original_cover_height
        self._draft_cover_preview_url = self._original_cover_preview_url

    def _clear_cover_draft(self) -> None:
        self._original_cover_data = b""
        self._original_cover_mime = ""
        self._original_cover_size = 0
        self._original_cover_width = 0
        self._original_cover_height = 0
        self._original_cover_preview_url = ""
        self._has_original_cover = False
        self._draft_cover_data = b""
        self._draft_cover_mime = ""
        self._draft_cover_size = 0
        self._draft_cover_width = 0
        self._draft_cover_height = 0
        self._draft_cover_preview_url = ""
        self._cover_action = "keep"
        self._cover_validation_state = "empty"
        self._cover_validation_error = ""
        self._cover_last_export_result = {}
        self._cover_state = "empty"

    @staticmethod
    def _dimensions_text(width: int, height: int) -> str:
        return f"{width} × {height}" if width > 0 and height > 0 else "-"

    def _apply_lyrics_source(self, source: str) -> None:
        data = self._lyrics_sources[source]
        self._selected_lyrics_source = source
        self._lyrics_source = source
        self._original_lyrics = str(data.get("text") or "")
        self._draft_lyrics = self._original_lyrics
        self._lyrics_clear_requested = False
        self._lyrics_imported_as_draft = False
        self._lyrics_source_before_import = "none"
        self._lyrics_last_export_result = {}
        self._lyrics_state = "loaded"

    def _clear_lyrics_draft(self) -> None:
        self._original_lyrics = ""
        self._draft_lyrics = ""
        self._lyrics_source = "none"
        self._selected_lyrics_source = "none"
        self._external_lrc_path = ""
        self._lyrics_sources = {}
        self._lyrics_clear_requested = False
        self._lyrics_imported_as_draft = False
        self._lyrics_source_before_import = "none"
        self._lyrics_last_export_result = {}
        self._lyrics_state = "empty"

    @classmethod
    def _lyrics_lines(cls, text: str) -> list[dict[str, object]]:
        lines: list[dict[str, object]] = []
        for index, raw in enumerate(str(text or "").splitlines()):
            match = cls._TIMESTAMP_RE.search(raw)
            lines.append({
                "index": index + 1,
                "time": match.group(0).strip("[]") if match else "",
                "text": raw.split("]", 1)[-1].strip() if match else raw.strip(),
                "translation": "",
                "raw": raw,
                "hasTimestamp": bool(match),
            })
        return lines

    def _clear_draft(self, message: str) -> None:
        self._source_path = ""
        self._original_metadata = {}
        self._draft_metadata = {}
        self._last_export_result = {}
        self._edit_state = "empty"
        self.set_status_message(message)
        self.stateChanged.emit()

    def _prepare_audio_export(self) -> bool:
        self._active_export_generation = self._session_generation
        self._player_released_for_export = False
        if self._audio_player is None:
            return True
        prepare = getattr(self._audio_player, "prepareForFileOperation", None)
        if not callable(prepare):
            return True
        self._player_released_for_export = bool(prepare())
        return self._player_released_for_export

    def _service_for_export(self):
        if self._export_service is None:
            self._export_service = EditExportService(self.capabilityGate)
        return self._export_service

    def _finish_audio_export_transaction(self) -> None:
        should_restore = (
            self._player_released_for_export
            and self._active_export_generation == self._session_generation
            and bool(self._source_path)
        )
        self._player_released_for_export = False
        self._active_export_generation = 0
        if not should_restore or self._audio_player is None:
            return
        restore = getattr(self._audio_player, "restorePlaybackSource", None)
        if callable(restore):
            restore()

    def shutdown(self) -> None:
        self.cancelExport()
        for worker in (
            self._unified_export_worker,
            self._export_worker,
            self._lyrics_export_worker,
            self._cover_export_worker,
        ):
            if worker is not None:
                worker.wait(3_000)

    def _result_matches_session(self, result: dict) -> bool:
        """Reject results that belong to an older or different file session."""
        result_generation = result.get("session_generation")
        if (
            result_generation not in (None, "")
            and self._session_generation
            and int(result_generation) != self._session_generation
        ):
            return False
        result_path = str(result.get("path") or "").strip()
        if (
            result_path
            and self._source_path
            and Path(result_path) != Path(self._source_path)
        ):
            return False
        return True

    @classmethod
    def _result_value(cls, result: dict, field: str) -> str:
        for key in cls._FIELD_ALIASES.get(field, (field,)):
            value = result.get(key)
            if value not in (None, "-"):
                return str(value).strip()
        return ""
