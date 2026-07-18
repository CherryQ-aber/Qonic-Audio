from __future__ import annotations

import logging
import re

from PySide6.QtCore import Property, Signal, Slot
from PySide6.QtWidgets import QFileDialog

from ui_next.bridge.base_viewmodel import BaseViewModel
from ui_next.bridge.capabilities import (
    COVER_READ,
    LYRICS_READ,
    LYRICS_WRITE,
    CapabilityGate,
)

try:
    from lyrics import read_embedded_lyrics, read_lrc_file_preview
except ImportError:  # pragma: no cover - optional runtime dependency guard
    read_embedded_lyrics = None
    read_lrc_file_preview = None


class LyricsViewModel(BaseViewModel):
    """Capability-gated, read-only lyrics state for QML Phase 4.3A."""

    stateChanged = Signal()
    lyricsReadApplied = Signal(dict)

    _TIMESTAMP_RE = re.compile(
        r"^\s*(\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\])+\s*(.*)$"
    )
    _PREVIEW_MESSAGE = (
        "当前未启用 lyrics_read，只显示 Preview / Mock 信息。"
    )
    _PREVIEW_SAFETY_MESSAGE = (
        "预览模式：歌词页不会读取真实歌词。"
    )
    _LIVE_SAFETY_MESSAGE = (
        "歌词已读取；修改会先保存在草稿中，不会立即保存或写入音频。"
    )
    _WRITE_DISABLED_MESSAGE = (
        "当前操作暂不可用；未修改歌词或音频文件。"
    )
    _AUDIO_FILTER = (
        "音频文件 (*.mp3 *.flac *.m4a *.mp4 *.aac *.ogg *.opus);;"
        "所有文件 (*)"
    )

    def __init__(self, capability_gate: CapabilityGate | None = None) -> None:
        super().__init__(capability_gate=capability_gate)
        self._logger = logging.getLogger("AudioConverter.QML.Lyrics")
        self._current_file_path = ""
        self._last_read_kind = ""
        self._reset_lyrics_state(clear_audio_path=False)
        self.set_status_message("等待选择音频文件或 .lrc 文件。")

    @Property(bool, constant=True)
    def previewMode(self) -> bool:
        return not self.lyricsReadEnabled

    @Property(bool, constant=True)
    def lyricsReadEnabled(self) -> bool:
        return self.allows_capability(LYRICS_READ)

    @Property(bool, constant=True)
    def coverReadEnabled(self) -> bool:
        return self.allows_capability(COVER_READ)

    @Property(str, constant=True)
    def previewSafetyMessage(self) -> str:
        return (
            self._LIVE_SAFETY_MESSAGE
            if self.lyricsReadEnabled
            else self._PREVIEW_SAFETY_MESSAGE
        )

    @Property(str, notify=stateChanged)
    def currentFilePath(self) -> str:
        return self._current_file_path

    @Property(str, notify=stateChanged)
    def currentLyricsPath(self) -> str:
        return self._current_lyrics_path

    @Property(str, notify=stateChanged)
    def lyricsSource(self) -> str:
        return self._lyrics_source

    @Property(str, notify=stateChanged)
    def lyricsStatus(self) -> str:
        return self._lyrics_status

    @Property(str, notify=stateChanged)
    def syncStatus(self) -> str:
        return self._sync_status

    @Property(str, notify=stateChanged)
    def lyricsText(self) -> str:
        return self._lyrics_text

    @Property("QVariantList", notify=stateChanged)
    def lyricsLines(self) -> list[dict[str, object]]:
        return self._parse_lyrics_lines(self._lyrics_text)

    @Property(int, notify=stateChanged)
    def lineCount(self) -> int:
        return len(self._lyrics_text.splitlines()) if self._lyrics_text else 0

    @Property(bool, notify=stateChanged)
    def hasLyrics(self) -> bool:
        return self._has_lyrics

    @Property(bool, notify=stateChanged)
    def hasTimestamps(self) -> bool:
        return self._has_timestamps

    @Property(bool, notify=stateChanged)
    def isMemoryPreview(self) -> bool:
        return self._is_memory_preview

    @Property(bool, notify=stateChanged)
    def isMockPreview(self) -> bool:
        return self._is_mock_preview

    @Property("QStringList", notify=stateChanged)
    def detectedFields(self) -> list[str]:
        return list(self._detected_fields)

    @Property(str, notify=stateChanged)
    def detectedFieldsText(self) -> str:
        return ", ".join(self._detected_fields) or "无"

    @Property(str, notify=stateChanged)
    def readBackend(self) -> str:
        return self._read_backend

    @Property(str, notify=stateChanged)
    def encoding(self) -> str:
        return self._encoding

    @Property(str, notify=stateChanged)
    def lastReadError(self) -> str:
        return self._last_read_error

    @Property(bool, notify=stateChanged)
    def lyricsDirty(self) -> bool:
        return False

    @Property(str, notify=stateChanged)
    def originalLrcPath(self) -> str:
        # Never retain a writable target in the QML read-only workflow.
        return ""

    @Slot()
    def chooseAudioForLyricsRead(self) -> None:
        selected_path, _selected_filter = QFileDialog.getOpenFileName(
            None,
            "选择音频文件只读读取内嵌歌词",
            "",
            self._AUDIO_FILTER,
        )
        if not selected_path:
            self.set_status_message("已取消选择音频文件。")
            return
        self.loadEmbeddedLyricsReadOnly(selected_path)

    @Slot(str)
    def loadEmbeddedLyricsReadOnly(self, path: str) -> None:
        normalized_path = str(path or "").strip()
        self._current_file_path = normalized_path
        self._last_read_kind = "embedded"
        self._reset_lyrics_state(clear_audio_path=False)

        if not normalized_path:
            self.set_status_message("当前没有可读取的音频文件。")
            self.stateChanged.emit()
            return

        if not self.lyricsReadEnabled:
            self._lyrics_source = "Preview"
            self._lyrics_status = "未读取真实歌词"
            self._is_mock_preview = True
            self.set_status_message(self._PREVIEW_MESSAGE)
            self.stateChanged.emit()
            return

        if read_embedded_lyrics is None:
            self._set_read_failure("mutagen 未安装，无法读取真实内嵌歌词")
            return

        try:
            result = read_embedded_lyrics(normalized_path)
        except Exception as exc:
            self._set_read_failure(f"内嵌歌词读取异常：{exc}")
            return

        if not result.get("ok", False):
            self._set_read_failure(
                str(result.get("error") or "内嵌歌词读取失败")
            )
            return

        self._detected_fields = list(result.get("detected_fields") or [])
        self._read_backend = str(result.get("read_backend") or "mutagen")
        lyrics_text = str(result.get("lyrics_text") or "")
        if result.get("has_lyrics") and lyrics_text.strip():
            self._set_lyrics(
                lyrics_text,
                source="Embedded",
                status="已读取（只读）",
                is_memory_preview=True,
                is_mock_preview=False,
                has_timestamps=bool(result.get("has_timestamps")),
            )
            self.set_status_message(self._LIVE_SAFETY_MESSAGE)
        elif result.get("has_lyrics"):
            self._has_lyrics = True
            self._lyrics_source = "Embedded"
            self._lyrics_status = "已检测歌词字段（正文解析暂缓）"
            self._sync_status = "检测到同步歌词字段 · 未接播放器"
            self._is_memory_preview = True
            self.set_status_message(
                "已检测到内嵌歌词字段；当前格式的正文解析暂缓，"
                "未修改音频文件。"
            )
        else:
            self._lyrics_source = "None"
            self._lyrics_status = "未检测到内嵌歌词"
            self._sync_status = "无时间轴"
            self.set_status_message("当前音频未检测到可显示的内嵌歌词。")
        self.lyricsReadApplied.emit(dict(result))
        self.stateChanged.emit()

    @Slot()
    def chooseLrcForPreview(self) -> None:
        selected_path, _selected_filter = QFileDialog.getOpenFileName(
            None,
            "选择 .lrc 进行内存预览",
            "",
            "LRC 歌词 (*.lrc *.LRC)",
        )
        if not selected_path:
            self.set_status_message("已取消选择 .lrc 预览。")
            return
        self.loadLrcPreviewReadOnly(selected_path)

    @Slot(str)
    def loadLrcPreviewReadOnly(self, path: str) -> None:
        normalized_path = str(path or "").strip()
        self._last_read_kind = "external_lrc"
        self._reset_lyrics_state(clear_audio_path=False)
        self._current_lyrics_path = normalized_path

        if not normalized_path:
            self.set_status_message("当前没有可读取的 .lrc 文件。")
            self.stateChanged.emit()
            return

        if not self.lyricsReadEnabled:
            self._lyrics_source = "Preview"
            self._lyrics_status = "未读取真实 .lrc"
            self._is_mock_preview = True
            self.set_status_message(self._PREVIEW_MESSAGE)
            self.stateChanged.emit()
            return

        if read_lrc_file_preview is None:
            self._set_read_failure("LRC 只读接口不可用")
            return

        try:
            result = read_lrc_file_preview(normalized_path)
        except Exception as exc:
            self._set_read_failure(f"LRC 读取异常：{exc}")
            return

        if not result.get("ok", False):
            self._set_read_failure(
                str(result.get("error") or "LRC 读取失败")
            )
            return

        self._encoding = str(result.get("encoding") or "未知")
        self._read_backend = "text"
        lyrics_text = str(result.get("lyrics_text") or "")
        self._set_lyrics(
            lyrics_text,
            source="External LRC Preview",
            status="内存预览",
            is_memory_preview=True,
            is_mock_preview=False,
            has_timestamps=bool(result.get("has_timestamps")),
        )
        self.set_status_message(
            "已载入 .lrc 内存预览；不会保存、另存或修改所选文件。"
        )
        self.stateChanged.emit()

    @Slot()
    def clearLyricsPreview(self) -> None:
        self._last_read_kind = ""
        self._reset_lyrics_state(clear_audio_path=False)
        self._lyrics_source = "None"
        self._lyrics_status = "预览已清除"
        self.set_status_message(
            "已清除内存歌词预览；磁盘文件和音频均未修改。"
        )
        self.stateChanged.emit()

    @Slot()
    def reloadLyricsReadOnly(self) -> None:
        if self._last_read_kind == "external_lrc" and self._current_lyrics_path:
            self.loadLrcPreviewReadOnly(self._current_lyrics_path)
            return
        self.loadEmbeddedLyricsReadOnly(self._current_file_path)

    # Existing cross-page and QML method names remain compatible.
    @Slot()
    @Slot(str)
    def loadReadOnlyLyrics(self, path: str = "") -> None:
        self.loadEmbeddedLyricsReadOnly(path or self._current_file_path)

    @Slot(str)
    def load_from_current_file(self, path: str) -> None:
        self.loadEmbeddedLyricsReadOnly(path)

    @Slot()
    def clearLrcPreview(self) -> None:
        self.clearLyricsPreview()

    @Slot()
    def reloadReadOnly(self) -> None:
        self.reloadLyricsReadOnly()

    @Slot()
    def disabledSaveAsLrc(self) -> None:
        self._block_write()

    @Slot()
    def disabledSaveToOriginalLrc(self) -> None:
        self._block_write()

    @Slot()
    def disabledWriteLyricsToAudio(self) -> None:
        self._block_write()

    @Slot()
    def disabledEditLyrics(self) -> None:
        self._block_write()

    @Slot()
    def import_lrc(self) -> None:
        self.chooseLrcForPreview()

    @Slot()
    def select_lrc(self) -> None:
        self.chooseLrcForPreview()

    @Slot(str)
    def edit_lyrics(self, _text: str) -> None:
        self.disabledEditLyrics()

    @Slot()
    def reset_lyrics(self) -> None:
        self.reloadLyricsReadOnly()

    @Slot()
    def save_as_lrc(self) -> None:
        self.disabledSaveAsLrc()

    @Slot()
    def save_to_original_lrc(self) -> None:
        self.disabledSaveToOriginalLrc()

    @Slot()
    def write_lyrics_to_audio(self) -> None:
        self.disabledWriteLyricsToAudio()

    @Slot()
    def show_drop_lrc_hint(self) -> None:
        self.set_status_message(
            "拖入 .lrc 暂未开放；请使用“选择 .lrc 内存预览”。"
        )

    # Shared session APIs receive data after FileSessionViewModel's background
    # reader has finished. They keep manual .lrc preview as memory-only state.
    def beginSessionRead(self, path: str, state: str) -> None:
        self._current_file_path = path
        self._last_read_kind = "embedded"
        self._reset_lyrics_state(clear_audio_path=False)
        if state == "loading":
            self._lyrics_source = "Loading"
            self._lyrics_status = "正在读取（只读）"
            self._sync_status = "等待读取完成"
            self.set_status_message("正在读取当前工作区文件的内嵌歌词。")
        else:
            self._lyrics_source = "None"
            self._lyrics_status = "当前未启用歌词读取"
            self._sync_status = "能力未启用"
            self.set_status_message(self._PREVIEW_MESSAGE)
        self.stateChanged.emit()

    def applySessionReadResult(self, result: dict) -> None:
        if not result.get("ok", False):
            self._set_read_failure(str(result.get("error") or "内嵌歌词读取失败"))
            return
        external = result.get("external_lrc_result") or {}
        if external.get("ok"):
            self._current_lyrics_path = str(result.get("external_lrc_path") or "")
            self._encoding = str(external.get("encoding") or "未知")
        self._detected_fields = list(result.get("detected_fields") or [])
        self._read_backend = str(result.get("read_backend") or "mutagen")
        lyrics_text = str(result.get("lyrics_text") or "")
        if result.get("has_lyrics") and lyrics_text.strip():
            self._set_lyrics(lyrics_text, source="Embedded", status="已读取（只读）", is_memory_preview=True, is_mock_preview=False, has_timestamps=bool(result.get("has_timestamps")))
            self.set_status_message(
                "已读取内嵌歌词；同时检测到同名 .lrc，可在编辑草稿中明确选择来源。"
                if external.get("ok") else self._LIVE_SAFETY_MESSAGE
            )
        elif external.get("ok"):
            self._read_backend = "text"
            self._set_lyrics(
                str(external.get("lyrics_text") or ""),
                source="External LRC",
                status="已读取同名 LRC（只读）",
                is_memory_preview=True,
                is_mock_preview=False,
                has_timestamps=bool(external.get("has_timestamps")),
            )
            self.set_status_message("已读取当前文件同名 .lrc；仅在内存中预览。")
        elif result.get("has_lyrics"):
            self._has_lyrics = True
            self._lyrics_source = "Embedded"
            self._lyrics_status = "已检测歌词字段（正文解析暂缓）"
            self._sync_status = "检测到同步歌词字段 · 未接播放器"
            self._is_memory_preview = True
            self.set_status_message("已检测到内嵌歌词字段；未修改音频文件。")
        else:
            self._lyrics_source = "None"
            self._lyrics_status = "未检测到内嵌歌词"
            self._sync_status = "无时间轴"
            self.set_status_message("当前音频未检测到可显示的内嵌歌词。")
        self.lyricsReadApplied.emit(dict(result))
        self.stateChanged.emit()

    def clearSessionState(self) -> None:
        self._last_read_kind = ""
        self._reset_lyrics_state(clear_audio_path=True)
        self.set_status_message("等待选择工作区音频文件或 .lrc 文件。")
        self.stateChanged.emit()

    def _reset_lyrics_state(self, *, clear_audio_path: bool) -> None:
        if clear_audio_path:
            self._current_file_path = ""
        self._current_lyrics_path = ""
        self._lyrics_source = "Preview" if self.previewMode else "None"
        self._lyrics_status = "未读取"
        self._sync_status = "未读取"
        self._lyrics_text = ""
        self._has_lyrics = False
        self._has_timestamps = False
        self._is_memory_preview = False
        self._is_mock_preview = False
        self._detected_fields: list[str] = []
        self._read_backend = "未调用"
        self._encoding = "-"
        self._last_read_error = ""

    def _set_lyrics(
        self,
        text: str,
        *,
        source: str,
        status: str,
        is_memory_preview: bool,
        is_mock_preview: bool,
        has_timestamps: bool,
    ) -> None:
        self._lyrics_text = text
        self._has_lyrics = bool(text.strip())
        self._lyrics_source = source
        self._lyrics_status = status
        self._has_timestamps = bool(has_timestamps)
        self._sync_status = (
            "检测到时间戳（未接播放器）"
            if self._has_timestamps
            else "无时间轴 · 不做同步滚动"
        )
        self._is_memory_preview = is_memory_preview
        self._is_mock_preview = is_mock_preview
        self._last_read_error = ""

    def _set_read_failure(self, error: str) -> None:
        self._has_lyrics = False
        self._last_read_error = str(error or "未知错误")
        self._lyrics_source = "None"
        self._lyrics_status = f"读取失败：{self._last_read_error}"
        self._sync_status = "无时间轴"
        self.set_status_message(self._lyrics_status)
        self._logger.warning("QML 歌词只读读取失败：%s", self._last_read_error)
        self.stateChanged.emit()

    def _block_write(self) -> None:
        self.block_capability(LYRICS_WRITE)
        self.set_status_message(self._WRITE_DISABLED_MESSAGE)

    def _parse_lyrics_lines(self, text: str) -> list[dict[str, object]]:
        if not text:
            return []

        lines = []
        for index, raw_line in enumerate(text.splitlines()):
            match = self._TIMESTAMP_RE.match(raw_line)
            if match:
                time_label = raw_line.split("]", 1)[0].lstrip("[")
                lyric_text = match.group(5).strip()
                lines.append(
                    {
                        "index": index + 1,
                        "time": time_label,
                        "text": lyric_text,
                        "translation": "",
                        "raw": raw_line,
                        "hasTimestamp": True,
                    }
                )
            else:
                lines.append(
                    {
                        "index": index + 1,
                        "time": "",
                        "text": raw_line.strip(),
                        "translation": "",
                        "raw": raw_line,
                        "hasTimestamp": False,
                    }
                )
        return lines
