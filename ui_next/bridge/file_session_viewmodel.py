from __future__ import annotations

from pathlib import Path
from typing import Callable
import uuid

from PySide6.QtCore import Property, QThread, Signal, Slot
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog

from formats import (
    get_editor_audio_filter,
    get_source_format,
    is_supported_editor_audio_file,
)
from ui_next.bridge.base_viewmodel import BaseViewModel
from ui_next.bridge.capabilities import (
    AUDIO_PLAYBACK,
    COVER_READ,
    LYRICS_READ,
    METADATA_READ,
    CapabilityGate,
)
from ui_next.bridge.drop_path_utils import extract_local_drop_paths

try:
    from metadata import read_audio_metadata, read_cover_preview
except ImportError:  # pragma: no cover - optional runtime dependency guard
    read_audio_metadata = None
    read_cover_preview = None

try:
    from lyrics import read_embedded_lyrics, read_lrc_file_preview
except ImportError:  # pragma: no cover - optional runtime dependency guard
    read_embedded_lyrics = None
    read_lrc_file_preview = None


class _ReadOnlySessionWorker(QThread):
    resultReady = Signal(str, int, str, dict)

    def __init__(self, kind: str, path: str, generation: int) -> None:
        super().__init__()
        self._kind = kind
        self._path = path
        self._generation = generation

    def run(self) -> None:
        try:
            if self._kind == "metadata":
                result = read_audio_metadata(self._path, include_cover=False) if read_audio_metadata else {
                    "ok": False, "error": "metadata 只读接口不可用"
                }
            elif self._kind == "lyrics":
                result = read_embedded_lyrics(self._path) if read_embedded_lyrics else {
                    "ok": False, "error": "歌词只读接口不可用"
                }
                if result.get("ok") and read_lrc_file_preview:
                    base = Path(self._path)
                    lrc_candidates = [base.with_suffix(".lrc"), base.with_suffix(".LRC")]
                    lrc_path = next((candidate for candidate in lrc_candidates if candidate.is_file()), None)
                    if lrc_path is not None:
                        external = read_lrc_file_preview(str(lrc_path))
                        if external.get("ok"):
                            result["external_lrc_path"] = str(lrc_path)
                            result["external_lrc_result"] = external
            else:
                result = read_cover_preview(self._path) if read_cover_preview else {
                    "ok": False, "error": "封面只读接口不可用"
                }
                if result.get("ok") and result.get("has_cover") and read_audio_metadata:
                    # Keep the original cover snapshot in memory only.  This
                    # worker already runs off the QML thread and never writes.
                    source_metadata = read_audio_metadata(self._path, include_cover=True)
                    if source_metadata.get("ok", source_metadata.get("success", False)):
                        result["cover_data"] = bytes(source_metadata.get("cover_data") or b"")
                        result["cover_mime"] = str(
                            source_metadata.get("cover_mime") or result.get("mime") or ""
                        )
        except Exception as exc:  # defensive boundary for damaged media
            result = {"ok": False, "error": f"只读读取异常：{exc}"}
        self.resultReady.emit(self._kind, self._generation, self._path, result)


class _LrcSessionWorker(QThread):
    resultReady = Signal(int, str, str, dict)

    def __init__(
        self,
        generation: int,
        audio_path: str,
        lyrics_path: str,
    ) -> None:
        super().__init__()
        self._generation = generation
        self._audio_path = audio_path
        self._lyrics_path = lyrics_path

    def run(self) -> None:
        try:
            result = (
                read_lrc_file_preview(self._lyrics_path)
                if read_lrc_file_preview
                else {"ok": False, "error": "LRC 只读接口不可用"}
            )
        except Exception as exc:
            result = {"ok": False, "error": f"LRC 读取异常：{exc}"}
        self.resultReady.emit(
            self._generation,
            self._audio_path,
            self._lyrics_path,
            dict(result),
        )


class FileSessionViewModel(BaseViewModel):
    """Authoritative current-file coordinator for the QML editor workspace."""

    stateChanged = Signal()
    currentFileChanged = Signal(str, int)
    currentFileReloaded = Signal(str, int)
    editorFilePlaybackRequested = Signal(str, int, str)
    currentFileCleared = Signal()
    currentFileMissing = Signal(str, int)
    fileChangeConfirmationRequested = Signal()
    externalLyricsImportFinished = Signal(str, bool)

    _SOURCE_LABELS = {
        "file_dialog": "手动选择",
        "scan_preview": "目录预览",
        "file_browser": "文件浏览",
        "folder_tree": "文件夹树",
        "drag_drop": "拖入文件",
        "audio_editor": "音频编辑",
        "metadata_page": "文件信息",
        "lyrics_cover_page": "歌词",
        "single_convert": "单文件转换",
        "conversion_result": "转换结果",
        "edit_export_result": "编辑导出结果",
        "pitch_export_result": "Pitch 导出结果",
    }

    def __init__(self, capability_gate: CapabilityGate | None = None) -> None:
        super().__init__(capability_gate=capability_gate)
        self._current_file_path = ""
        self._current_file_source = ""
        self._current_file_id = ""
        self._generation = 0
        self._session_state = "empty"
        self._metadata_state = "idle"
        self._lyrics_state = "idle"
        self._cover_state = "idle"
        self._error_summary = ""
        self._workers: list[_ReadOnlySessionWorker] = []
        self._metadata_view_model = None
        self._lyrics_view_model = None
        self._cover_view_model = None
        self._edit_session = None
        self._unsaved_changes_guard: Callable[[], bool] | None = None
        self._file_change_blocker: Callable[[], bool] | None = None
        self._pending_file_path = ""
        self._pending_file_source = ""
        self._pending_clear = False
        self._pending_lrc_after_switch = ""
        self._deferred_lrc_path = ""
        self._deferred_lrc_generation = 0
        self._lrc_workers: list[_LrcSessionWorker] = []
        self.set_status_message("当前没有工作区文件。")

    def attach_readers(self, metadata_view_model, lyrics_view_model, cover_view_model) -> None:
        self._metadata_view_model = metadata_view_model
        self._lyrics_view_model = lyrics_view_model
        self._cover_view_model = cover_view_model

    def attach_edit_session(self, edit_session) -> None:
        self._edit_session = edit_session

    @Property(str, notify=stateChanged)
    def currentFileId(self) -> str:
        return self._current_file_id

    @Property(str, notify=stateChanged)
    def currentFilePath(self) -> str:
        return self._current_file_path

    @Property(str, notify=stateChanged)
    def currentFileName(self) -> str:
        return Path(self._current_file_path).name if self._current_file_path else "未选择"

    @Property(str, notify=stateChanged)
    def currentFileExtension(self) -> str:
        return Path(self._current_file_path).suffix.lower().lstrip(".") if self._current_file_path else ""

    @Property(str, notify=stateChanged)
    def currentFileFormat(self) -> str:
        return get_source_format(self._current_file_path) if self._current_file_path else ""

    @Property(str, notify=stateChanged)
    def currentFileDirectory(self) -> str:
        return str(Path(self._current_file_path).parent) if self._current_file_path else ""

    @Property(str, notify=stateChanged)
    def currentFileSource(self) -> str:
        return self._current_file_source

    @Property(str, notify=stateChanged)
    def currentFileSourceLabel(self) -> str:
        return self._SOURCE_LABELS.get(self._current_file_source, "未选择")

    @Property(bool, notify=stateChanged)
    def hasCurrentFile(self) -> bool:
        return bool(self._current_file_path)

    @Property(bool, notify=stateChanged)
    def currentFileExists(self) -> bool:
        return bool(self._current_file_path) and Path(self._current_file_path).is_file()

    @Property(bool, notify=stateChanged)
    def currentFileSupported(self) -> bool:
        return bool(
            self._current_file_path
            and is_supported_editor_audio_file(self._current_file_path)
        )

    @Property(bool, notify=stateChanged)
    def realFileAccessEnabled(self) -> bool:
        return (
            not self.capabilityGate.previewMode
            and any(
                self.allows_capability(capability)
                for capability in (
                    METADATA_READ,
                    LYRICS_READ,
                    COVER_READ,
                    AUDIO_PLAYBACK,
                )
            )
        )

    @Property(int, notify=stateChanged)
    def sessionGeneration(self) -> int:
        return self._generation

    @Property(str, notify=stateChanged)
    def sessionState(self) -> str:
        return self._session_state

    @Property(bool, notify=stateChanged)
    def isLoading(self) -> bool:
        return any(state == "loading" for state in self._read_states().values())

    @Property(str, notify=stateChanged)
    def metadataState(self) -> str:
        return self._metadata_state

    @Property(str, notify=stateChanged)
    def lyricsState(self) -> str:
        return self._lyrics_state

    @Property(str, notify=stateChanged)
    def coverState(self) -> str:
        return self._cover_state

    @Property(str, notify=stateChanged)
    def errorSummary(self) -> str:
        return self._error_summary

    @Property(bool, notify=stateChanged)
    def hasUnsavedChanges(self) -> bool:
        return self._has_unsaved_changes()

    @Property(str, notify=stateChanged)
    def importedLyricsPath(self) -> str:
        if self._edit_session is None:
            return ""
        return str(getattr(self._edit_session, "externalLrcPath", "") or "")

    @Property(bool, notify=stateChanged)
    def hasPendingFileChange(self) -> bool:
        return bool(self._pending_file_path) or self._pending_clear

    @Property(str, notify=stateChanged)
    def pendingFileName(self) -> str:
        return Path(self._pending_file_path).name if self._pending_file_path else ""

    def setUnsavedChangesGuard(self, guard: Callable[[], bool] | None) -> None:
        self._unsaved_changes_guard = guard

    def setFileChangeBlocker(self, blocker: Callable[[], bool] | None) -> None:
        self._file_change_blocker = blocker

    @Slot()
    def notifyDraftStateChanged(self) -> None:
        self.stateChanged.emit()

    @Slot(str)
    def chooseAudioFile(self, source: str = "file_dialog") -> None:
        if not self.realFileAccessEnabled:
            self.set_status_message("预览模式不会选择或读取真实音频文件。")
            self.stateChanged.emit()
            return
        path, _selected_filter = QFileDialog.getOpenFileName(
            None,
            "选择工作区音频文件",
            self.currentFileDirectory,
            get_editor_audio_filter(),
        )
        if not path:
            self.set_status_message("已取消选择工作区音频文件。")
            return
        self.setCurrentFile(path, source or "file_dialog")

    @Slot(str, str, result=str)
    def setCurrentFile(self, path: str, source: str = "file_dialog") -> str:
        normalized_path, error = self._validate_path(path)
        normalized_source = (
            source if source in self._SOURCE_LABELS else "file_dialog"
        )
        same_path = bool(
            not error and normalized_path == self._current_file_path
        )
        result_load = normalized_source in {
            "edit_export_result",
            "pitch_export_result",
        }
        if not error and self._is_file_change_blocked():
            self.set_status_message("正在导出编辑副本；请等待导出完成后再切换当前文件。")
            self.stateChanged.emit()
            return "blocked"
        if error:
            if self._current_file_path:
                self.set_status_message(
                    f"未切换文件：{error} 当前文件和编辑草稿保持不变。"
                )
                self.stateChanged.emit()
                return "rejected"
            self._session_state = "error"
            self._error_summary = error
            self.set_status_message(error)
            self.stateChanged.emit()
            return "rejected"
        if self._has_unsaved_changes() and (not same_path or result_load):
            self._pending_file_path = normalized_path
            self._pending_file_source = normalized_source
            self._pending_clear = False
            self.set_status_message("当前存在未导出的编辑草稿；请确认放弃草稿后再切换文件。")
            self.fileChangeConfirmationRequested.emit()
            self.stateChanged.emit()
            return "confirmation_required"
        if same_path:
            if result_load:
                self._current_file_source = normalized_source
            self.set_status_message(
                "当前音频已经载入；已请求播放器从开头重新载入。"
            )
            self.editorFilePlaybackRequested.emit(
                self._current_file_path,
                self._generation,
                self._playback_origin_for_source(normalized_source),
            )
            self.stateChanged.emit()
            return "unchanged"
        self._apply_current_file(normalized_path, normalized_source)
        return "loaded"

    @Slot()
    def discardPendingFileChange(self) -> None:
        if not self.hasPendingFileChange:
            return
        if self._is_file_change_blocked():
            self.set_status_message(
                "当前有媒体处理或导出操作；请等待完成后再确认切换文件。"
            )
            self.stateChanged.emit()
            return
        pending_path = self._pending_file_path
        pending_source = self._pending_file_source
        pending_clear = self._pending_clear
        pending_lrc = self._pending_lrc_after_switch
        self._clear_pending_file_change()
        if pending_clear:
            self._clear_local_state("")
        elif pending_path == self._current_file_path:
            self._current_file_source = (
                pending_source
                if pending_source in self._SOURCE_LABELS
                else "file_dialog"
            )
            self._generation += 1
            self._error_summary = ""
            self.currentFileReloaded.emit(
                self._current_file_path,
                self._generation,
            )
            self._begin_read_cycle()
            self.editorFilePlaybackRequested.emit(
                self._current_file_path,
                self._generation,
                self._playback_origin_for_source(self._current_file_source),
            )
        else:
            self._apply_current_file(pending_path, pending_source)
            if pending_lrc:
                self.importLyricsFile(pending_lrc)

    @Slot()
    def cancelPendingFileChange(self) -> None:
        if not self.hasPendingFileChange:
            return
        self._clear_pending_file_change()
        self._pending_lrc_after_switch = ""
        self.set_status_message("已取消切换；当前文件与编辑草稿保持不变。")
        self.stateChanged.emit()

    def _apply_current_file(self, normalized_path: str, source: str) -> None:
        self._clear_pending_file_change()
        self._current_file_path = normalized_path
        self._current_file_source = source if source in self._SOURCE_LABELS else "file_dialog"
        self._generation += 1
        self._current_file_id = uuid.uuid4().hex
        self._error_summary = ""
        self.currentFileChanged.emit(self._current_file_path, self._generation)
        self._begin_read_cycle()
        self.editorFilePlaybackRequested.emit(
            self._current_file_path,
            self._generation,
            self._playback_origin_for_source(self._current_file_source),
        )

    @Slot()
    def clearCurrentFile(self) -> None:
        if self._current_file_path and self._is_file_change_blocked():
            self.set_status_message("正在导出编辑副本；请等待导出完成后再清除当前文件。")
            self.stateChanged.emit()
            return
        if self._current_file_path and self._has_unsaved_changes():
            self._pending_file_path = ""
            self._pending_file_source = ""
            self._pending_clear = True
            self.set_status_message("当前存在未导出的编辑草稿；请确认放弃草稿后再清除文件。")
            self.fileChangeConfirmationRequested.emit()
            self.stateChanged.emit()
            return
        self._clear_local_state("")

    @Slot()
    def reloadCurrentFile(self) -> None:
        if not self._current_file_path:
            self.set_status_message("当前没有可重新读取的工作区文件。")
            return
        if self._is_file_change_blocked():
            self.set_status_message("正在导出编辑副本；请等待导出完成后再重新读取文件。")
            self.stateChanged.emit()
            return
        if self._has_unsaved_changes():
            self.set_status_message("当前存在未导出的编辑草稿；已阻止重新读取以避免丢弃草稿。")
            self.stateChanged.emit()
            return
        if not Path(self._current_file_path).is_file():
            self.markCurrentFileMissing("当前音频文件已被移动、重命名或删除。")
            return
        self._generation += 1
        self._error_summary = ""
        self.currentFileReloaded.emit(
            self._current_file_path,
            self._generation,
        )
        self._begin_read_cycle()

    @Slot(str)
    def useScanPreviewFile(self, path: str) -> None:
        self.setCurrentFile(path, "scan_preview")

    @Slot()
    def chooseLyricsFile(self) -> None:
        if not self.hasCurrentFile:
            self.set_status_message("请先导入音频，再选择外置 .lrc 歌词。")
            self.stateChanged.emit()
            return
        if (
            self.capabilityGate.previewMode
            or not self.allows_capability(LYRICS_READ)
        ):
            self.set_status_message("预览模式不会读取真实 .lrc 文件。")
            self.stateChanged.emit()
            return
        path, _selected_filter = QFileDialog.getOpenFileName(
            None,
            "选择 .lrc 作为当前音频的歌词草稿",
            self.currentFileDirectory,
            "LRC 歌词 (*.lrc *.LRC)",
        )
        if not path:
            self.set_status_message("已取消选择 .lrc 歌词草稿。")
            return
        self.importLyricsFile(path)

    @Slot(str, result=str)
    def importLyricsFile(self, path: str) -> str:
        if not self.hasCurrentFile:
            self.set_status_message("请先导入音频，再导入外置 .lrc 歌词。")
            self.stateChanged.emit()
            return "audio_session_missing"
        if (
            self.capabilityGate.previewMode
            or not self.allows_capability(LYRICS_READ)
        ):
            self.set_status_message("当前模式不会读取真实 .lrc 文件。")
            self.stateChanged.emit()
            return "capability_denied"
        if self._edit_session is not None and bool(
            getattr(self._edit_session, "lyricsDirty", False)
        ):
            self.set_status_message(
                "当前已有未导出的歌词草稿；请先恢复或导出，再更换外置歌词。"
            )
            self.stateChanged.emit()
            return "unsaved_changes"
        lyrics_path, error = self._validate_lrc_path(path)
        if error:
            self.set_status_message(error)
            self.stateChanged.emit()
            return "lrc_rejected"
        if self._lyrics_state == "loading":
            self._deferred_lrc_path = lyrics_path
            self._deferred_lrc_generation = self._generation
            self.set_status_message(
                "音频歌词信息正在读取；外置 .lrc 将在当前会话就绪后载入草稿。"
            )
            self.stateChanged.emit()
            return "deferred"
        self._start_lrc_import(lyrics_path, self._generation)
        return "loading"

    @Slot("QVariantList", result=str)
    def handleDroppedUrls(self, values) -> str:
        paths, skipped = extract_local_drop_paths(values)
        if skipped:
            self.set_status_message("拖入内容包含非本地项目，未执行任何加载。")
            self.stateChanged.emit()
            return "non_local_rejected"
        if not paths:
            self.set_status_message("没有识别到可用的本地文件。")
            self.stateChanged.emit()
            return "empty_drop"
        if any(Path(path).is_dir() for path in paths):
            self.set_status_message("音频编辑区不接受文件夹拖入；请使用文件浏览入口。")
            self.stateChanged.emit()
            return "directory_rejected"

        audio_paths = [path for path in paths if is_supported_editor_audio_file(path)]
        lrc_paths = [path for path in paths if Path(path).suffix.lower() == ".lrc"]
        unsupported = [
            path for path in paths if path not in audio_paths and path not in lrc_paths
        ]
        if unsupported:
            self.set_status_message("拖入内容包含不支持的文件，未切换当前音频。")
            self.stateChanged.emit()
            return "unsupported_rejected"
        if len(audio_paths) > 1 or len(lrc_paths) > 1 or len(paths) > 2:
            self.set_status_message(
                "一次只能拖入一个音频，或一个音频与其同名 .lrc；未随机选择文件。"
            )
            self.stateChanged.emit()
            return "multiple_files_rejected"
        if len(lrc_paths) == 1 and not audio_paths:
            return self.importLyricsFile(lrc_paths[0])
        if len(audio_paths) != 1:
            self.set_status_message("没有识别到可加载的音频文件。")
            self.stateChanged.emit()
            return "audio_missing"

        audio_path = audio_paths[0]
        if lrc_paths:
            if Path(audio_path).stem.casefold() != Path(lrc_paths[0]).stem.casefold():
                result = self.setCurrentFile(audio_path, "drag_drop")
                if result in {"loaded", "unchanged"}:
                    self.set_status_message(
                        "音频已载入；外置 .lrc 与音频不同名，未自动绑定。"
                    )
                    self.stateChanged.emit()
                    return "audio_loaded_lrc_name_mismatch"
                return result
            result = self.setCurrentFile(audio_path, "drag_drop")
            if result == "confirmation_required":
                self._pending_lrc_after_switch = lrc_paths[0]
                return result
            if result in {"loaded", "unchanged"}:
                return self.importLyricsFile(lrc_paths[0])
            return result
        return self.setCurrentFile(audio_path, "drag_drop")

    @Slot(str)
    def markCurrentFileMissing(self, message: str = "") -> None:
        if not self._current_file_path:
            return
        # Invalidate every in-flight reader without discarding in-memory
        # drafts. The player listens to this signal and releases its handle.
        self._generation += 1
        self._session_state = "missing"
        self._error_summary = str(
            message or "当前音频文件已被移动、重命名或删除。"
        )
        self.set_status_message(self._error_summary)
        self.currentFileMissing.emit(self._current_file_path, self._generation)
        self.stateChanged.emit()

    @Slot()
    def openCurrentFileLocation(self) -> None:
        if not self.hasCurrentFile:
            self.set_status_message("当前没有可定位的音频文件。")
            return
        target = Path(self._current_file_path).parent
        if not target.is_dir():
            self.markCurrentFileMissing()
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    @Slot()
    def shutdown(self) -> None:
        workers = [*self._workers, *self._lrc_workers]
        for worker in workers:
            if worker.isRunning():
                worker.requestInterruption()
        for worker in workers:
            if worker.isRunning():
                worker.wait(3_000)

    def _validate_path(self, path: str) -> tuple[str, str]:
        raw_path = str(path or "").strip()
        if not raw_path:
            return "", "文件路径为空。"
        try:
            file_path = Path(raw_path).expanduser().resolve()
        except OSError as exc:
            return "", f"无法规范化文件路径：{exc}"
        if not file_path.exists():
            return "", "文件不存在。"
        if not file_path.is_file():
            return "", "所选路径不是文件。"
        if not is_supported_editor_audio_file(file_path):
            return "", f"文件格式不受支持：{file_path.suffix or '无扩展名'}"
        return str(file_path), ""

    def _validate_lrc_path(self, path: str) -> tuple[str, str]:
        raw_path = str(path or "").strip()
        if not raw_path:
            return "", "歌词文件路径为空。"
        try:
            file_path = Path(raw_path).expanduser().resolve()
        except OSError as exc:
            return "", f"无法规范化歌词文件路径：{exc}"
        if not file_path.is_file():
            return "", "所选歌词文件不存在或不是普通文件。"
        if file_path.suffix.lower() != ".lrc":
            return "", "仅支持导入 .lrc 歌词文件。"
        return str(file_path), ""

    def _begin_read_cycle(self) -> None:
        path = self._current_file_path
        generation = self._generation
        capability_map = {
            "metadata": (
                not self.capabilityGate.previewMode
                and self.allows_capability(METADATA_READ)
            ),
            "lyrics": (
                not self.capabilityGate.previewMode
                and self.allows_capability(LYRICS_READ)
            ),
            "cover": (
                not self.capabilityGate.previewMode
                and self.allows_capability(COVER_READ)
            ),
        }
        for kind, enabled in capability_map.items():
            self._set_read_state(kind, "loading" if enabled else "capability_disabled")
            self._prepare_reader(kind, path, "loading" if enabled else "capability_disabled")
            if enabled:
                self._start_reader(kind, path, generation)
        self._refresh_session_state()
        self.set_status_message("正在读取工作区文件的已授权只读信息。" if self.isLoading else "当前文件已载入；读取能力尚未启用。")
        self.stateChanged.emit()
        if (
            self._deferred_lrc_path
            and self._deferred_lrc_generation == generation
            and not capability_map["lyrics"]
        ):
            self._deferred_lrc_path = ""
            self._deferred_lrc_generation = 0
            self.set_status_message("当前模式不会读取真实 .lrc 文件。")
            self.stateChanged.emit()

    def _start_reader(self, kind: str, path: str, generation: int) -> None:
        worker = _ReadOnlySessionWorker(kind, path, generation)
        self._workers.append(worker)
        worker.resultReady.connect(self._apply_reader_result)
        worker.finished.connect(lambda: self._finish_worker(worker))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _finish_worker(self, worker: _ReadOnlySessionWorker) -> None:
        if worker in self._workers:
            self._workers.remove(worker)

    def _apply_reader_result(self, kind: str, generation: int, path: str, result: dict) -> None:
        if generation != self._generation or path != self._current_file_path:
            return
        # Reader helpers may return a Windows 8.3 alias or another equivalent
        # spelling. The session keeps the one normalized path authoritative.
        result = dict(result)
        result["path"] = self._current_file_path
        result["session_generation"] = self._generation
        result.setdefault("filename", Path(self._current_file_path).name)
        ok = bool(result.get("ok", result.get("success", False)))
        if ok:
            if kind == "lyrics" and not bool(result.get("has_lyrics")) and not bool(result.get("external_lrc_result")):
                state = "not_available"
            elif kind == "cover" and not bool(result.get("has_cover")):
                state = "not_available"
            else:
                state = "ready"
        else:
            state = "error"
            error = str(result.get("error") or f"{kind} 读取失败")
            self._error_summary = self._error_summary or error
        self._set_read_state(kind, state)
        self._apply_to_reader(kind, result)
        self._refresh_session_state()
        self.set_status_message(self._session_message())
        self.stateChanged.emit()
        if (
            kind == "lyrics"
            and self._deferred_lrc_path
            and self._deferred_lrc_generation == self._generation
        ):
            lyrics_path = self._deferred_lrc_path
            self._deferred_lrc_path = ""
            self._deferred_lrc_generation = 0
            self._start_lrc_import(lyrics_path, self._generation)

    def _start_lrc_import(self, lyrics_path: str, generation: int) -> None:
        worker = _LrcSessionWorker(
            generation,
            self._current_file_path,
            lyrics_path,
        )
        self._lrc_workers.append(worker)
        worker.resultReady.connect(self._apply_lrc_result)
        worker.finished.connect(lambda: self._finish_lrc_worker(worker))
        worker.finished.connect(worker.deleteLater)
        worker.start()
        self.set_status_message("正在读取外置 .lrc 到当前会话草稿。")
        self.stateChanged.emit()

    def _finish_lrc_worker(self, worker: _LrcSessionWorker) -> None:
        if worker in self._lrc_workers:
            self._lrc_workers.remove(worker)

    def _apply_lrc_result(
        self,
        generation: int,
        audio_path: str,
        lyrics_path: str,
        result: dict,
    ) -> None:
        if generation != self._generation or audio_path != self._current_file_path:
            return
        payload = dict(result)
        payload["path"] = lyrics_path
        payload["audio_path"] = audio_path
        payload["session_generation"] = generation
        ok = bool(payload.get("ok", payload.get("success", False)))
        if ok and self._edit_session is not None and hasattr(
            self._edit_session, "applyImportedLyricsDraft"
        ):
            ok = bool(self._edit_session.applyImportedLyricsDraft(payload))
        if ok:
            self.set_status_message(
                "外置 .lrc 已载入当前歌词草稿；原歌词文件和音频文件均未修改。"
            )
        else:
            self.set_status_message(
                str(payload.get("error") or "外置 .lrc 读取失败。")
            )
        self.externalLyricsImportFinished.emit(lyrics_path, ok)
        self.stateChanged.emit()

    def _prepare_reader(self, kind: str, path: str, state: str) -> None:
        reader = {"metadata": self._metadata_view_model, "lyrics": self._lyrics_view_model, "cover": self._cover_view_model}[kind]
        if reader is not None and hasattr(reader, "beginSessionRead"):
            reader.beginSessionRead(path, state)

    def _apply_to_reader(self, kind: str, result: dict) -> None:
        reader = {"metadata": self._metadata_view_model, "lyrics": self._lyrics_view_model, "cover": self._cover_view_model}[kind]
        if reader is not None and hasattr(reader, "applySessionReadResult"):
            reader.applySessionReadResult(result)

    def _clear_local_state(self, error: str) -> None:
        self._clear_pending_file_change()
        self._pending_lrc_after_switch = ""
        self._deferred_lrc_path = ""
        self._deferred_lrc_generation = 0
        self._generation += 1
        self._current_file_path = ""
        self._current_file_source = ""
        self._current_file_id = ""
        self._metadata_state = self._lyrics_state = self._cover_state = "idle"
        self._session_state = "error" if error else "empty"
        self._error_summary = error
        for reader in (self._metadata_view_model, self._lyrics_view_model, self._cover_view_model):
            if reader is not None and hasattr(reader, "clearSessionState"):
                reader.clearSessionState()
        self.set_status_message(error or "已清除当前工作区文件；未删除任何磁盘文件。")
        self.currentFileCleared.emit()
        self.stateChanged.emit()

    def _has_unsaved_changes(self) -> bool:
        try:
            return bool(self._unsaved_changes_guard and self._unsaved_changes_guard())
        except Exception:
            return False

    def _is_file_change_blocked(self) -> bool:
        try:
            return bool(self._file_change_blocker and self._file_change_blocker())
        except Exception:
            return False

    @staticmethod
    def _playback_origin_for_source(source: str) -> str:
        if source in {"edit_export_result", "pitch_export_result"}:
            return "editor_export"
        return "editor_file"

    def _clear_pending_file_change(self) -> None:
        self._pending_file_path = ""
        self._pending_file_source = ""
        self._pending_clear = False
        self._pending_lrc_after_switch = ""

    def _set_read_state(self, kind: str, state: str) -> None:
        setattr(self, f"_{kind}_state", state)

    def _read_states(self) -> dict[str, str]:
        return {"metadata": self._metadata_state, "lyrics": self._lyrics_state, "cover": self._cover_state}

    def _refresh_session_state(self) -> None:
        states = tuple(self._read_states().values())
        if any(state == "loading" for state in states):
            self._session_state = "loading"
        elif any(state == "error" for state in states):
            self._session_state = "partial" if any(state in {"ready", "not_available"} for state in states) else "error"
        elif all(state == "capability_disabled" for state in states):
            self._session_state = "ready"
        elif any(state == "not_available" for state in states):
            self._session_state = "partial"
        else:
            self._session_state = "ready"

    def _session_message(self) -> str:
        if self._session_state == "error":
            return self._error_summary or "工作区文件读取失败。"
        if self._session_state == "partial":
            return "工作区文件已载入；部分只读信息不可用。"
        if self._session_state == "ready":
            return "工作区文件已载入；仅执行已授权的只读读取。"
        return "正在读取工作区文件的已授权只读信息。"
