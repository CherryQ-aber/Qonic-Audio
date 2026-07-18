from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Property, Signal, Slot
from PySide6.QtWidgets import QFileDialog

from ui_next.bridge.base_viewmodel import BaseViewModel
from ui_next.bridge.capabilities import COVER_READ, COVER_WRITE, CapabilityGate

try:
    from metadata import SUPPORTED_METADATA_READ_EXTENSIONS, read_cover_preview
except ImportError:  # pragma: no cover - optional runtime dependency guard
    SUPPORTED_METADATA_READ_EXTENSIONS = frozenset()
    read_cover_preview = None


class CoverViewModel(BaseViewModel):
    """Capability-gated, read-only cover preview state for QML Phase 4.3B."""

    stateChanged = Signal()
    coverReadApplied = Signal(dict)

    _PREVIEW_MESSAGE = (
        "当前未启用 cover_read，只显示 Preview / Mock 封面占位。"
    )
    _PREVIEW_SAFETY_MESSAGE = (
        "预览模式：封面区域仅显示占位内容，不读取真实封面。"
    )
    _LIVE_SAFETY_MESSAGE = (
        "封面已读取；替换或移除会先保存在草稿中，不会立即写入音频。"
    )
    _WRITE_DISABLED_MESSAGE = (
        "当前操作暂不可用；未修改任何封面或音频文件。"
    )
    _AUDIO_FILTER = (
        "音频文件 (*.mp3 *.flac *.m4a *.aac *.ogg *.opus *.wav "
        "*.aiff *.aif *.ape *.wma);;所有文件 (*)"
    )

    def __init__(self, capability_gate: CapabilityGate | None = None) -> None:
        super().__init__(capability_gate=capability_gate)
        self._logger = logging.getLogger("AudioConverter.QML.Cover")
        self._last_loaded_path = ""
        self._reset_state()
        self.set_status_message("等待选择音频文件读取封面预览。")

    @Property(bool, constant=True)
    def previewMode(self) -> bool:
        return not self.coverReadEnabled

    @Property(bool, constant=True)
    def coverReadEnabled(self) -> bool:
        return self.allows_capability(COVER_READ)

    @Property(str, constant=True)
    def previewSafetyMessage(self) -> str:
        return (
            self._LIVE_SAFETY_MESSAGE
            if self.coverReadEnabled
            else self._PREVIEW_SAFETY_MESSAGE
        )

    @Property(str, notify=stateChanged)
    def currentFilePath(self) -> str:
        return self._current_file_path

    @Property(str, notify=stateChanged)
    def currentFileName(self) -> str:
        return self._current_file_name

    @Property(str, notify=stateChanged)
    def fileName(self) -> str:
        return self._current_file_name

    @Property(bool, notify=stateChanged)
    def hasCover(self) -> bool:
        return self._has_cover

    @Property(str, notify=stateChanged)
    def coverStatus(self) -> str:
        return self._cover_status

    @Property(str, notify=stateChanged)
    def coverMime(self) -> str:
        return self._cover_mime

    @Property(str, notify=stateChanged)
    def coverSizeText(self) -> str:
        return self._cover_size_text

    @Property(str, notify=stateChanged)
    def coverDimensionsText(self) -> str:
        return self._cover_dimensions_text

    @Property(str, notify=stateChanged)
    def coverDimensions(self) -> str:
        return self._cover_dimensions_text

    @Property(str, notify=stateChanged)
    def coverPreviewUrl(self) -> str:
        return self._cover_preview_url

    @Property(str, notify=stateChanged)
    def coverImageUrl(self) -> str:
        return self._cover_preview_url

    @Property(str, notify=stateChanged)
    def readBackend(self) -> str:
        return self._read_backend

    @Property(str, notify=stateChanged)
    def lastReadError(self) -> str:
        return self._last_read_error

    @Slot()
    def chooseAudioForCoverRead(self) -> None:
        selected_path, _selected_filter = QFileDialog.getOpenFileName(
            None,
            "选择音频文件只读读取封面",
            "",
            self._AUDIO_FILTER,
        )
        if not selected_path:
            self.set_status_message("已取消选择音频文件。")
            return
        self.loadCoverReadOnly(selected_path)

    @Slot(str)
    def loadCoverReadOnly(self, path: str) -> None:
        normalized_path = str(path or "").strip()
        self._last_loaded_path = normalized_path
        if not normalized_path:
            self._reset_state()
            self.set_status_message("当前没有可读取封面的音频文件。")
            self.stateChanged.emit()
            return

        self._load_preview_path(normalized_path)
        if not self.coverReadEnabled:
            self.set_status_message(self._PREVIEW_MESSAGE)
            self.stateChanged.emit()
            return

        file_path = Path(normalized_path)
        extension = file_path.suffix.lower()
        if extension not in SUPPORTED_METADATA_READ_EXTENSIONS:
            self._set_read_failure(
                f"不支持的格式：{extension or '无扩展名'}"
            )
            return

        try:
            if not file_path.is_file():
                self._set_read_failure("文件不存在")
                return
        except OSError as exc:
            self._set_read_failure(f"无法访问文件：{exc}")
            return

        if read_cover_preview is None:
            self._set_read_failure("mutagen 未安装，无法读取真实封面")
            return

        try:
            result = read_cover_preview(normalized_path)
        except Exception as exc:
            self._set_read_failure(f"封面读取异常：{exc}")
            return

        if not result.get("ok", False):
            self._set_read_failure(
                str(result.get("error") or "封面读取失败")
            )
            return

        self._apply_cover_result(result)
        self.set_status_message(
            self._LIVE_SAFETY_MESSAGE
            if self._has_cover
            else "只读读取完成：未检测到内嵌封面。"
        )
        self.stateChanged.emit()

    @Slot()
    def reloadCoverReadOnly(self) -> None:
        self.loadCoverReadOnly(self._last_loaded_path)

    @Slot()
    def clearCoverPreview(self) -> None:
        self._last_loaded_path = ""
        self._reset_state()
        self.set_status_message(
            "已清除封面内存预览；没有修改或删除任何文件。"
        )
        self.stateChanged.emit()

    @Slot()
    def disabledImportCover(self) -> None:
        self._block_write()

    @Slot()
    def disabledWriteCover(self) -> None:
        self._block_write()

    @Slot()
    def disabledRemoveCover(self) -> None:
        self._block_write()

    @Slot()
    def disabledRestoreCover(self) -> None:
        self._block_write()

    @Slot()
    def disabledOverwriteCover(self) -> None:
        self._block_write()

    # Compatibility names used by older QML drafts.
    @Slot()
    def import_cover(self) -> None:
        self.disabledImportCover()

    @Slot()
    def write_cover(self) -> None:
        self.disabledWriteCover()

    @Slot()
    def remove_cover(self) -> None:
        self.disabledRemoveCover()

    @Slot()
    def reset_cover(self) -> None:
        self.disabledRestoreCover()

    def beginSessionRead(self, path: str, state: str) -> None:
        self._last_loaded_path = path
        self._load_preview_path(path)
        if state == "loading":
            self._cover_status = "正在读取封面（只读）"
            self.set_status_message("正在读取当前工作区文件的封面预览。")
        else:
            self._cover_status = "当前未启用封面读取"
            self.set_status_message(self._PREVIEW_MESSAGE)
        self.stateChanged.emit()

    def applySessionReadResult(self, result: dict) -> None:
        if result.get("ok", False):
            self._apply_cover_result(result)
            self.set_status_message(self._LIVE_SAFETY_MESSAGE if self._has_cover else "只读读取完成：未检测到内嵌封面。")
            self.coverReadApplied.emit(dict(result))
            self.stateChanged.emit()
            return
        self._set_read_failure(str(result.get("error") or "封面读取失败"))
        self.coverReadApplied.emit(dict(result))

    def clearSessionState(self) -> None:
        self._last_loaded_path = ""
        self._reset_state()
        self.set_status_message("等待选择工作区音频文件读取封面预览。")
        self.stateChanged.emit()

    def _load_preview_path(self, path: str) -> None:
        file_path = Path(path)
        self._current_file_path = path
        self._current_file_name = file_path.name or path
        self._has_cover = False
        self._cover_status = "Preview / Mock；未读取真实封面"
        self._cover_mime = "-"
        self._cover_size_text = "-"
        self._cover_dimensions_text = "-"
        self._cover_preview_url = ""
        self._read_backend = "未调用"
        self._last_read_error = ""

    def _apply_cover_result(self, result: dict) -> None:
        self._current_file_path = str(
            result.get("path") or self._current_file_path
        )
        self._current_file_name = str(
            result.get("filename") or self._current_file_name
        )
        self._has_cover = bool(result.get("has_cover"))
        self._cover_mime = str(result.get("mime") or "-")
        self._cover_size_text = str(result.get("byte_size_text") or "-")
        self._cover_dimensions_text = str(
            result.get("dimensions_text") or "-"
        )
        self._cover_preview_url = str(result.get("preview_data_url") or "")
        self._read_backend = str(result.get("read_backend") or "mutagen")
        self._last_read_error = str(result.get("error") or "")
        if self._has_cover and self._cover_preview_url:
            self._cover_status = "已读取封面预览（只读）"
        elif self._has_cover:
            self._cover_status = (
                self._last_read_error
                or "检测到封面，但未生成预览。"
            )
        else:
            self._cover_status = "未检测到内嵌封面"

    def _set_read_failure(self, error: str) -> None:
        self._last_read_error = str(error or "未知错误")
        self._read_backend = "mutagen"
        self._cover_status = f"读取失败：{self._last_read_error}"
        self.set_status_message(self._cover_status)
        self._logger.warning("QML 封面只读读取失败：%s", self._last_read_error)
        self.stateChanged.emit()

    def _reset_state(self) -> None:
        self._current_file_path = ""
        self._current_file_name = ""
        self._has_cover = False
        self._cover_status = "未读取"
        self._cover_mime = "-"
        self._cover_size_text = "-"
        self._cover_dimensions_text = "-"
        self._cover_preview_url = ""
        self._read_backend = "未调用"
        self._last_read_error = ""

    def _block_write(self) -> None:
        self.block_capability(COVER_WRITE)
        self.set_status_message(self._WRITE_DISABLED_MESSAGE)
