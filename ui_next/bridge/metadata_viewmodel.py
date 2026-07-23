from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Property, Signal, Slot
from PySide6.QtWidgets import QFileDialog

from ui_next.bridge.base_viewmodel import BaseViewModel
from ui_next.bridge.capabilities import (
    COVER_READ,
    COVER_WRITE,
    LYRICS_READ,
    LYRICS_WRITE,
    METADATA_READ,
    METADATA_WRITE,
    CapabilityGate,
)

try:
    from metadata import (
        SUPPORTED_METADATA_READ_EXTENSIONS,
        read_audio_metadata,
    )
except ImportError:  # pragma: no cover - optional runtime dependency guard
    SUPPORTED_METADATA_READ_EXTENSIONS = frozenset()
    read_audio_metadata = None


class MetadataViewModel(BaseViewModel):
    """Capability-gated, read-only metadata state for QML Phase 4.2."""

    stateChanged = Signal()
    metadataReadApplied = Signal(dict)

    _EMPTY_TAG = "未读取"
    _PREVIEW_MESSAGE = (
        "当前未启用 metadata_read，只显示 Preview / Mock 信息。"
    )
    _PREVIEW_SAFETY_MESSAGE = (
        "预览模式：文件信息页不会读取真实音频信息。"
    )
    _LIVE_SAFETY_MESSAGE = (
        "文件信息已读取。标签、封面和歌词修改会先保存在草稿中，"
        "不会立即写入音频。"
    )
    _EMPTY_STATE_MESSAGE = (
        "当前没有音频编辑文件。可以手动选择一个音频文件进行只读 metadata 读取。"
    )
    _WRITE_DISABLED_MESSAGE = (
        "当前操作暂不可用；未修改任何音频文件。"
    )
    _AUDIO_FILTER = (
        "音频文件 (*.mp3 *.flac *.m4a *.aac *.ogg *.opus *.wav "
        "*.aiff *.aif *.ape *.wma);;所有文件 (*)"
    )

    def __init__(
        self,
        capability_gate: CapabilityGate | None = None,
        live_mode: bool | None = None,
    ) -> None:
        super().__init__(capability_gate=capability_gate)
        self._logger = logging.getLogger("AudioConverter.QML.Metadata")
        self._last_loaded_path = ""
        self._reset_state()
        self.set_status_message(self._EMPTY_STATE_MESSAGE)

    @Property(bool, constant=True)
    def previewMode(self) -> bool:
        return not self.metadataReadEnabled

    @Property(bool, constant=True)
    def metadataReadEnabled(self) -> bool:
        return self.allows_capability(METADATA_READ)

    @Property(bool, constant=True)
    def coverReadEnabled(self) -> bool:
        return self.allows_capability(COVER_READ)

    @Property(bool, constant=True)
    def lyricsReadEnabled(self) -> bool:
        return self.allows_capability(LYRICS_READ)

    @Property(str, constant=True)
    def previewSafetyMessage(self) -> str:
        return (
            self._LIVE_SAFETY_MESSAGE
            if self.metadataReadEnabled
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

    @Property(str, notify=stateChanged)
    def fileFormat(self) -> str:
        return self._file_format

    @Property(str, notify=stateChanged)
    def fileSizeText(self) -> str:
        return self._file_size_text

    @Property(str, notify=stateChanged)
    def fileSize(self) -> str:
        return self._file_size_text

    @Property(str, notify=stateChanged)
    def durationText(self) -> str:
        return self._duration_text

    @Property(str, notify=stateChanged)
    def durationLabel(self) -> str:
        return self._duration_text

    @Property(str, notify=stateChanged)
    def sampleRateText(self) -> str:
        return self._sample_rate_text

    @Property(str, notify=stateChanged)
    def sampleRateLabel(self) -> str:
        return self._sample_rate_text

    @Property(str, notify=stateChanged)
    def bitRateText(self) -> str:
        return self._bit_rate_text

    @Property(str, notify=stateChanged)
    def bitrateLabel(self) -> str:
        return self._bit_rate_text

    @Property(str, notify=stateChanged)
    def channelsText(self) -> str:
        return self._channels_text

    @Property(str, notify=stateChanged)
    def title(self) -> str:
        return self._title

    @Property(str, notify=stateChanged)
    def artist(self) -> str:
        return self._artist

    @Property(str, notify=stateChanged)
    def album(self) -> str:
        return self._album

    @Property(str, notify=stateChanged)
    def albumArtist(self) -> str:
        return self._album_artist

    @Property(str, notify=stateChanged)
    def year(self) -> str:
        return self._year

    @Property(str, notify=stateChanged)
    def genre(self) -> str:
        return self._genre

    @Property(str, notify=stateChanged)
    def track(self) -> str:
        return self._track

    @Property(str, notify=stateChanged)
    def disc(self) -> str:
        return self._disc

    @Property(str, notify=stateChanged)
    def comment(self) -> str:
        return self._comment

    @Property(bool, notify=stateChanged)
    def hasBasicTags(self) -> bool:
        return self._has_basic_tags

    @Property(bool, notify=stateChanged)
    def hasCover(self) -> bool:
        return self._has_cover

    @Property(bool, notify=stateChanged)
    def hasLyrics(self) -> bool:
        return self._has_lyrics

    @Property(str, notify=stateChanged)
    def readBackend(self) -> str:
        return self._read_backend

    @Property(str, notify=stateChanged)
    def readStatus(self) -> str:
        return self._read_status

    @Property(str, notify=stateChanged)
    def lastReadError(self) -> str:
        return self._last_read_error

    # Compatibility properties used by the existing read-only QML components.
    @Property(str, notify=stateChanged)
    def tagReadStatus(self) -> str:
        return self._tag_read_status

    @Property(str, notify=stateChanged)
    def coverStatus(self) -> str:
        return self._cover_status

    @Property(str, notify=stateChanged)
    def coverImageUrl(self) -> str:
        return ""

    @Property(str, notify=stateChanged)
    def coverDimensions(self) -> str:
        return "详细封面读取留到 Phase 4.3"

    @Property(str, notify=stateChanged)
    def lyricsSource(self) -> str:
        return "内嵌歌词标记" if self._has_lyrics else "未检测到"

    @Property(str, notify=stateChanged)
    def lyricsStatus(self) -> str:
        return (
            "检测到歌词标记；正文未读取"
            if self._has_lyrics
            else "未检测到歌词标记"
        )

    @Property(bool, notify=stateChanged)
    def hasExternalLrc(self) -> bool:
        return False

    @Property(bool, notify=stateChanged)
    def hasEmbeddedLyrics(self) -> bool:
        return self._has_lyrics

    @Property(str, notify=stateChanged)
    def embeddedLyricsStatus(self) -> str:
        return self.lyricsStatus

    @Property(bool, notify=stateChanged)
    def metadataDirty(self) -> bool:
        return False

    @Property(bool, notify=stateChanged)
    def coverDirty(self) -> bool:
        return False

    @Property(str, notify=stateChanged)
    def syncSummary(self) -> str:
        return "真实 metadata 只读" if self.metadataReadEnabled else "Preview / Mock"

    @Slot()
    def chooseFileForMetadataRead(self) -> None:
        selected_path, _selected_filter = QFileDialog.getOpenFileName(
            None,
            "选择音频文件进行只读 metadata 读取",
            "",
            self._AUDIO_FILTER,
        )
        if not selected_path:
            self.set_status_message("已取消选择音频文件。")
            return
        self.loadMetadataReadOnly(selected_path)

    @Slot(str)
    def loadMetadataReadOnly(self, path: str) -> None:
        normalized_path = str(path or "").strip()
        self._last_loaded_path = normalized_path
        if not normalized_path:
            self._reset_state()
            self.set_status_message(self._EMPTY_STATE_MESSAGE)
            self.stateChanged.emit()
            return

        self._load_preview_path(normalized_path)
        if not self.metadataReadEnabled:
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

        if read_audio_metadata is None:
            self._set_read_failure(
                "mutagen 未安装，无法读取真实 metadata"
            )
            return

        try:
            result = read_audio_metadata(
                normalized_path,
                include_cover=False,
            )
        except Exception as exc:  # defensive boundary for damaged media
            self._set_read_failure(f"metadata 读取异常：{exc}")
            return

        if not result.get("ok", result.get("success", False)):
            self._set_read_failure(
                str(result.get("error") or "未读取到 metadata")
            )
            return

        self._apply_real_result(result)
        self.set_status_message(self._LIVE_SAFETY_MESSAGE)
        self.metadataReadApplied.emit(dict(result))
        self.stateChanged.emit()

    @Slot()
    def reloadMetadataReadOnly(self) -> None:
        self.loadMetadataReadOnly(self._last_loaded_path)

    @Slot()
    def clearMetadata(self) -> None:
        self._last_loaded_path = ""
        self._reset_state()
        self.set_status_message(
            "已清除 metadata 只读摘要；没有修改或删除任何文件。"
        )
        self.stateChanged.emit()

    # Existing cross-page and QML method names remain compatible.
    @Slot(str)
    def loadCurrentFileReadOnly(self, path: str) -> None:
        self.loadMetadataReadOnly(path)

    @Slot(str)
    def load_from_current_file(self, path: str) -> None:
        self.loadMetadataReadOnly(path)

    @Slot()
    def reloadReadOnly(self) -> None:
        self.reloadMetadataReadOnly()

    @Slot()
    def clearReadOnly(self) -> None:
        self.clearMetadata()

    @Slot()
    def openFileLocationPreview(self) -> None:
        self.set_status_message(
            "打开文件位置当前为安全占位，不执行系统操作。"
        )

    @Slot()
    def edit_metadata(self) -> None:
        self.disabledEditMetadata()

    @Slot()
    def reset_metadata(self) -> None:
        self.reloadMetadataReadOnly()

    @Slot()
    def write_metadata(self) -> None:
        self.disabledWriteMetadata()

    @Slot()
    def import_cover(self) -> None:
        self.disabledImportCover()

    @Slot()
    def remove_cover(self) -> None:
        self.disabledRemoveCover()

    @Slot()
    def reset_cover(self) -> None:
        self.reloadMetadataReadOnly()

    @Slot()
    def write_cover(self) -> None:
        self.disabledWriteCover()

    @Slot()
    def write_lyrics(self) -> None:
        self.disabledWriteLyrics()

    @Slot()
    def save_lyrics(self) -> None:
        self.disabledSaveLyrics()

    @Slot()
    def disabledEditMetadata(self) -> None:
        self._block_write_capability(METADATA_WRITE)

    @Slot()
    def disabledWriteMetadata(self) -> None:
        self._block_write_capability(METADATA_WRITE)

    @Slot()
    def disabledImportCover(self) -> None:
        self._block_write_capability(COVER_WRITE)

    @Slot()
    def disabledRemoveCover(self) -> None:
        self._block_write_capability(COVER_WRITE)

    @Slot()
    def disabledWriteCover(self) -> None:
        self._block_write_capability(COVER_WRITE)

    @Slot()
    def disabledWriteLyrics(self) -> None:
        self._block_write_capability(LYRICS_WRITE)

    @Slot()
    def disabledSaveLyrics(self) -> None:
        self._block_write_capability(LYRICS_WRITE)

    # FileSessionViewModel owns cross-page selection and schedules reads on
    # background threads. These methods only apply already-read data on QML's
    # thread and deliberately never call a writer.
    def beginSessionRead(self, path: str, state: str) -> None:
        self._last_loaded_path = path
        self._load_preview_path(path)
        if state == "loading":
            self._read_status = "正在读取（只读）"
            self._tag_read_status = "正在读取"
            self.set_status_message("正在读取当前工作区文件的信息。")
        else:
            self._read_status = "能力未启用"
            self._tag_read_status = "当前未启用文件信息读取"
            self.set_status_message(self._PREVIEW_MESSAGE)
        self.stateChanged.emit()

    def applySessionReadResult(self, result: dict) -> None:
        if result.get("ok", result.get("success", False)):
            self._apply_real_result(result)
            self.set_status_message(self._LIVE_SAFETY_MESSAGE)
            self.metadataReadApplied.emit(dict(result))
            self.stateChanged.emit()
            return
        self._set_read_failure(str(result.get("error") or "metadata 读取失败"))

    def clearSessionState(self) -> None:
        self._last_loaded_path = ""
        self._reset_state()
        self.set_status_message(self._EMPTY_STATE_MESSAGE)
        self.stateChanged.emit()

    def _load_preview_path(self, path: str) -> None:
        file_path = Path(path)
        self._current_file_path = path
        self._current_file_name = file_path.name or path
        self._file_format = file_path.suffix.lstrip(".").upper() or "未知"
        self._file_size_text = "Preview / 未读取"
        self._duration_text = "Preview / Mock"
        self._sample_rate_text = "Preview / Mock"
        self._bit_rate_text = "Preview / Mock"
        self._channels_text = "Preview / Mock"
        self._title = self._EMPTY_TAG
        self._artist = self._EMPTY_TAG
        self._album = self._EMPTY_TAG
        self._album_artist = self._EMPTY_TAG
        self._year = self._EMPTY_TAG
        self._genre = self._EMPTY_TAG
        self._track = self._EMPTY_TAG
        self._disc = self._EMPTY_TAG
        self._comment = self._EMPTY_TAG
        self._has_basic_tags = False
        self._has_cover = False
        self._has_lyrics = False
        self._read_backend = "未调用"
        self._read_status = "Preview / Mock；未读取真实 metadata"
        self._tag_read_status = "未读取真实标签"
        self._cover_status = "未读取；Phase 4.3 处理详细封面"
        self._last_read_error = ""

    def _apply_real_result(self, result: dict) -> None:
        self._current_file_path = str(
            result.get("path") or self._current_file_path
        )
        self._current_file_name = str(
            result.get("filename") or self._current_file_name
        )
        self._file_format = str(
            result.get("format")
            or result.get("extension")
            or self._file_format
        ).upper()
        self._file_size_text = self._display_value(
            result.get("file_size_text")
        )
        self._duration_text = self._display_value(
            result.get("duration_text")
        )
        self._sample_rate_text = self._display_value(
            result.get("sample_rate_text")
        )
        self._bit_rate_text = self._display_value(
            result.get("bitrate_text")
        )
        self._channels_text = self._display_value(
            result.get("channels_text")
        )
        self._title = self._display_value(result.get("title"))
        self._artist = self._display_value(result.get("artist"))
        self._album = self._display_value(result.get("album"))
        self._album_artist = self._display_value(
            result.get("album_artist") or result.get("albumartist")
        )
        self._year = self._display_value(
            result.get("year") or result.get("date")
        )
        self._genre = self._display_value(result.get("genre"))
        self._track = self._display_value(
            result.get("track") or result.get("tracknumber")
        )
        self._disc = self._display_value(
            result.get("disc") or result.get("discnumber")
        )
        self._comment = self._display_value(result.get("comment"))
        self._has_basic_tags = bool(result.get("has_basic_tags"))
        self._has_cover = bool(result.get("has_cover"))
        self._has_lyrics = bool(result.get("has_lyrics"))
        self._read_backend = str(result.get("read_backend") or "mutagen")
        self._read_status = (
            "读取成功（只读）"
            if self._has_basic_tags
            else "读取成功；未读取到基础标签"
        )
        self._tag_read_status = self._read_status
        self._cover_status = (
            "检测到封面；详细读取留到 Phase 4.3"
            if self._has_cover
            else "未检测到封面"
        )
        self._last_read_error = ""

    def _set_read_failure(self, error: str) -> None:
        self._last_read_error = str(error or "未知错误")
        self._read_backend = "mutagen"
        self._read_status = f"读取失败：{self._last_read_error}"
        self._tag_read_status = "真实标签读取失败"
        self.set_status_message(self._read_status)
        self._logger.warning("QML metadata 只读读取失败：%s", self._last_read_error)
        self.stateChanged.emit()

    def _reset_state(self) -> None:
        self._current_file_path = ""
        self._current_file_name = ""
        self._file_format = "-"
        self._file_size_text = "-"
        self._duration_text = "-"
        self._sample_rate_text = "-"
        self._bit_rate_text = "-"
        self._channels_text = "-"
        self._title = self._EMPTY_TAG
        self._artist = self._EMPTY_TAG
        self._album = self._EMPTY_TAG
        self._album_artist = self._EMPTY_TAG
        self._year = self._EMPTY_TAG
        self._genre = self._EMPTY_TAG
        self._track = self._EMPTY_TAG
        self._disc = self._EMPTY_TAG
        self._comment = self._EMPTY_TAG
        self._has_basic_tags = False
        self._has_cover = False
        self._has_lyrics = False
        self._read_backend = "未调用"
        self._read_status = "无当前文件"
        self._tag_read_status = "未读取"
        self._cover_status = "未读取"
        self._last_read_error = ""

    def _block_write_capability(self, capability: str) -> None:
        self.block_capability(capability)
        self.set_status_message(self._WRITE_DISABLED_MESSAGE)

    @classmethod
    def _display_value(cls, value) -> str:
        if value is None:
            return cls._EMPTY_TAG
        text = str(value).strip()
        return text if text and text != "-" else cls._EMPTY_TAG
