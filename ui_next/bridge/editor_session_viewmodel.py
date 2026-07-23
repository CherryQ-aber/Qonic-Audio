from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QTimer, Signal, Slot
from PySide6.QtWidgets import QFileDialog

from ui_next.bridge.base_viewmodel import BaseViewModel
from ui_next.bridge.capabilities import (
    AUDIO_PLAYBACK,
    AUDIO_PROCESSING,
    SINGLE_FILE_CONVERT,
    CapabilityGate,
)


class EditorSessionViewModel(BaseViewModel):
    """QML-facing audio editor session state.

    This first QML pass keeps playback, pitch preview, and export as mock state
    flows. Future real media processing can attach behind the same slots.
    """

    stateChanged = Signal()

    _AUDIO_FILTER = (
        "音频文件 (*.mp3 *.flac *.wav *.m4a *.aac *.ogg *.opus *.ape *.aiff *.aif *.wma);;"
        "所有文件 (*)"
    )
    _MOCK_DURATION_MS = 260000
    _MOCK_OPERATION_DELAY_MS = 320
    _PREVIEW_SAFETY_MESSAGE = (
        "预览模式：音频编辑页当前为模拟状态，"
        "不会播放、处理、缓存或导出真实音频。"
    )

    def __init__(
        self,
        capability_gate: CapabilityGate | None = None,
        live_mode: bool | None = None,
        file_session=None,
    ) -> None:
        super().__init__(capability_gate=capability_gate)
        self._file_session = file_session
        self._current_file_path = ""
        self._original_file_path = ""
        self._current_file_is_mock_export = False
        self._current_play_source = ""
        self._current_play_source_label = "未加载"
        self._player_state = "stopped"
        self._position = 0
        self._duration = 0
        self._volume = 70
        self._pitch_semitone = 0
        self._preview_state = "未生成模拟试听"
        self._preview_version_semitone: int | None = None
        self._pending_preview_semitone = 0
        self._export_state = "未模拟导出"
        self._export_version_semitone: int | None = None
        self._pending_export_semitone = 0
        self._last_export_path = ""
        self._load_export_result_after_export = False

        self._play_timer = QTimer(self)
        self._play_timer.setInterval(500)
        self._play_timer.timeout.connect(self._advance_mock_playback)

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(self._MOCK_OPERATION_DELAY_MS)
        self._preview_timer.timeout.connect(self._finish_mock_preview)

        self._export_timer = QTimer(self)
        self._export_timer.setSingleShot(True)
        self._export_timer.setInterval(self._MOCK_OPERATION_DELAY_MS)
        self._export_timer.timeout.connect(self._finish_mock_export)
        if self._file_session is not None:
            self._file_session.currentFileChanged.connect(self._apply_shared_file)
            self._file_session.currentFileCleared.connect(self._clear_shared_file)
        self.set_status_message(self._PREVIEW_SAFETY_MESSAGE)

    @Property(bool, constant=True)
    def previewMode(self) -> bool:
        # Phase 4.1 only declares capabilities; this session remains mock until
        # a later phase explicitly wires a real backend behind a capability.
        return True

    @Property(bool, constant=True)
    def audioPlaybackEnabled(self) -> bool:
        return self.allows_capability(AUDIO_PLAYBACK)

    @Property(bool, constant=True)
    def audioProcessingEnabled(self) -> bool:
        return self.allows_capability(AUDIO_PROCESSING)

    @Property(bool, constant=True)
    def singleFileConvertDeclared(self) -> bool:
        return self.allows_capability(SINGLE_FILE_CONVERT)

    @Property(bool, constant=True)
    def isMockSession(self) -> bool:
        return True

    @Property(str, constant=True)
    def previewSafetyMessage(self) -> str:
        return self._PREVIEW_SAFETY_MESSAGE

    @Property(str, notify=stateChanged)
    def currentFilePath(self) -> str:
        return self._current_file_path

    @Property(str, notify=stateChanged)
    def currentFileName(self) -> str:
        if not self._current_file_path:
            return "未导入音频"
        file_name = Path(self._current_file_path).name
        if self._current_file_is_mock_export:
            return f"{file_name} (mock)"
        return file_name

    @Property(str, notify=stateChanged)
    def currentPlaySource(self) -> str:
        return self._current_play_source

    @Property(str, notify=stateChanged)
    def currentPlaySourceLabel(self) -> str:
        return self._current_play_source_label

    @Property(bool, notify=stateChanged)
    def currentFileIsMockExport(self) -> bool:
        return self._current_file_is_mock_export

    @Property(bool, notify=stateChanged)
    def hasCurrentFile(self) -> bool:
        return bool(self._current_file_path)

    @Property(str, notify=stateChanged)
    def unsavedSummary(self) -> str:
        if not self.hasCurrentFile:
            return "未加载音频"
        return "无真实未保存内容；路径、播放、升降调和导出均为内存 mock 状态"

    @Property(str, notify=stateChanged)
    def playerState(self) -> str:
        return self._player_state

    @Property(int, notify=stateChanged)
    def position(self) -> int:
        return self._position

    @Property(int, notify=stateChanged)
    def duration(self) -> int:
        return self._duration

    @Property(int, notify=stateChanged)
    def volume(self) -> int:
        return self._volume

    @Property(int, notify=stateChanged)
    def pitchSemitone(self) -> int:
        return self._pitch_semitone

    @Property(str, notify=stateChanged)
    def previewState(self) -> str:
        return self._preview_state

    @Property(bool, notify=stateChanged)
    def isPreviewGenerating(self) -> bool:
        return self._preview_timer.isActive()

    @Property(str, notify=stateChanged)
    def previewVersionLabel(self) -> str:
        if self._preview_timer.isActive():
            return self._format_pitch_label(
                "正在生成的模拟版本",
                self._pending_preview_semitone,
            )
        if self._preview_version_semitone is None:
            return "当前试听版本：未生成"
        return self._format_pitch_label(
            "当前试听版本",
            self._preview_version_semitone,
        )

    @Property(str, notify=stateChanged)
    def exportState(self) -> str:
        return self._export_state

    @Property(bool, notify=stateChanged)
    def isExporting(self) -> bool:
        return self._export_timer.isActive()

    @Property(str, notify=stateChanged)
    def lastExportPath(self) -> str:
        return self._last_export_path

    @Property(bool, notify=stateChanged)
    def hasLastExport(self) -> bool:
        return bool(self._last_export_path)

    @Property(bool, notify=stateChanged)
    def loadExportResultAfterExport(self) -> bool:
        return self._load_export_result_after_export

    @Slot()
    def importAudioMock(self) -> None:
        if self._file_session is not None:
            self._file_session.chooseAudioFile("audio_editor")
            return
        selected_path, _ = QFileDialog.getOpenFileName(
            None,
            "导入音频",
            "",
            self._AUDIO_FILTER,
        )
        if not selected_path:
            self.set_status_message("已取消导入音频")
            return
        self._load_current_file(
            selected_path,
            play_source_label="原音频路径（mock，不播放）",
            is_mock_export=False,
        )
        self._pitch_semitone = 0
        self._reset_mock_results()
        self.set_status_message(
            f"已记录音频路径（mock）: {self.currentFileName}；未读取音频内容。"
        )
        self.stateChanged.emit()

    @Slot()
    def clearCurrentAudio(self) -> None:
        if self._file_session is not None:
            self._file_session.clearCurrentFile()
            return
        self._clear_local_current_file()

    @Slot(str, int)
    def _apply_shared_file(self, file_path: str, _generation: int) -> None:
        if not file_path:
            return
        self._load_current_file(
            file_path,
            play_source_label="工作区当前文件（mock，不播放）",
            is_mock_export=False,
        )
        self._pitch_semitone = 0
        self._reset_mock_results()
        self.set_status_message("已载入共享工作区文件；播放器仍为 mock，不播放真实音频。")
        self.stateChanged.emit()

    @Slot()
    def _clear_shared_file(self) -> None:
        self._clear_local_current_file()

    def _clear_local_current_file(self) -> None:
        self._play_timer.stop()
        self._preview_timer.stop()
        self._export_timer.stop()
        self._current_file_path = ""
        self._original_file_path = ""
        self._current_file_is_mock_export = False
        self._current_play_source = ""
        self._current_play_source_label = "未加载"
        self._player_state = "stopped"
        self._position = 0
        self._duration = 0
        self._pitch_semitone = 0
        self._reset_mock_results()
        self.set_status_message("已清除当前 mock 会话；未删除任何磁盘文件。")
        self.stateChanged.emit()

    @Slot()
    def openCurrentFileLocationMock(self) -> None:
        self.set_status_message("预览模式：打开文件位置暂为占位，不执行系统打开操作。")

    @Slot()
    def returnToOriginalMock(self) -> None:
        if not self.hasCurrentFile:
            self.set_status_message("请先导入音频")
            return
        if not self._original_file_path:
            self.set_status_message("当前 mock 会话没有原始音频路径。")
            return
        self._current_play_source = self._original_file_path
        self._current_play_source_label = "原音频路径（mock，不播放）"
        self._position = 0
        self._player_state = "stopped"
        self._play_timer.stop()
        self.set_status_message("播放源已返回原始路径（mock）；没有播放真实音频。")
        self.stateChanged.emit()

    @Slot()
    def playMock(self) -> None:
        if not self.hasCurrentFile:
            self.set_status_message("请先导入音频")
            return
        self._player_state = "playing"
        if self._duration <= 0:
            self._duration = self._MOCK_DURATION_MS
        self._play_timer.start()
        self.set_status_message("Mock 播放器：状态切换为 playing，不播放真实音频。")
        self.stateChanged.emit()

    @Slot()
    def pauseMock(self) -> None:
        if self._player_state != "playing":
            return
        self._player_state = "paused"
        self._play_timer.stop()
        self.set_status_message("Mock 播放器：状态切换为 paused。")
        self.stateChanged.emit()

    @Slot()
    def stopMock(self) -> None:
        self._player_state = "stopped"
        self._position = 0
        self._play_timer.stop()
        self.set_status_message("Mock 播放器：状态切换为 stopped。")
        self.stateChanged.emit()

    @Slot(float)
    def seekMock(self, position: float) -> None:
        if self._duration <= 0:
            return
        self._position = max(0, min(int(position), self._duration))
        self.stateChanged.emit()

    @Slot(float)
    def setVolume(self, value: float) -> None:
        self._volume = max(0, min(int(round(value)), 100))
        self.stateChanged.emit()

    @Slot(float)
    def setPitchSemitone(self, value: float) -> None:
        next_value = max(-12, min(int(round(value)), 12))
        if next_value == self._pitch_semitone:
            return
        self._pitch_semitone = next_value
        if self.hasCurrentFile:
            if self._preview_timer.isActive():
                self._preview_state = "正在生成模拟试听"
            elif self._preview_version_semitone is None:
                self._preview_state = "未生成模拟试听"
            elif self._preview_version_semitone == next_value:
                self._preview_state = "已生成模拟试听"
            else:
                self._preview_state = "当前设置已变更，需重新试听"
            if self._export_timer.isActive():
                self._export_state = "正在模拟导出"
            elif self._export_version_semitone is None:
                self._export_state = "未模拟导出"
            elif self._export_version_semitone == next_value and self._last_export_path:
                self._export_state = "模拟导出完成"
            else:
                self._export_state = "当前设置已变更，需重新模拟导出"
        self.set_status_message(
            f"升降调参数已更新为 {self._format_pitch_value(next_value)}；"
            "仅改变内存设置。"
        )
        self.stateChanged.emit()

    @Slot()
    def previewPitchMock(self) -> None:
        if not self.hasCurrentFile:
            self.set_status_message("请先导入音频")
            return
        if self._preview_timer.isActive():
            self.set_status_message("正在生成模拟试听状态，请稍候。")
            return
        self._pending_preview_semitone = self._pitch_semitone
        self._preview_state = "正在生成模拟试听"
        self.set_status_message("正在生成模拟试听状态；不会创建试听缓存文件。")
        self._preview_timer.start()
        self.stateChanged.emit()

    def _finish_mock_preview(self) -> None:
        self._preview_version_semitone = self._pending_preview_semitone
        self._preview_state = (
            "已生成模拟试听"
            if self._pitch_semitone == self._preview_version_semitone
            else "当前设置已变更，需重新试听"
        )
        self._current_play_source_label = self._format_pitch_label("模拟升降调试听")
        self._current_play_source = self._format_preview_source(
            self._preview_version_semitone
        )
        self._position = 0
        self.set_status_message("已生成模拟试听：未生成真实缓存文件。")
        self.stateChanged.emit()

    @Slot()
    def exportPitchMock(self) -> None:
        if not self.hasCurrentFile:
            self.set_status_message("请先导入音频")
            return
        if self._export_timer.isActive():
            self.set_status_message("正在模拟导出，请稍候。")
            return
        self._pending_export_semitone = self._pitch_semitone
        self._export_state = "正在模拟导出"
        self._last_export_path = ""
        self.set_status_message("正在模拟导出状态；不会生成真实音频文件。")
        self._export_timer.start()
        self.stateChanged.emit()

    def _finish_mock_export(self) -> None:
        self._export_version_semitone = self._pending_export_semitone
        self._last_export_path = self._build_mock_export_path(
            self._export_version_semitone
        )
        self._export_state = (
            "模拟导出完成"
            if self._pitch_semitone == self._export_version_semitone
            else "模拟导出完成（当前设置已变更）"
        )
        self.set_status_message(
            f"模拟导出完成：{self._last_export_path}；未生成真实文件。"
        )
        if self._load_export_result_after_export:
            self.loadExportResultAsCurrentMock()
        else:
            self.stateChanged.emit()

    @Slot()
    def loadExportResultAsCurrentMock(self) -> None:
        if not self._last_export_path:
            self.set_status_message("暂无可加载的导出结果")
            return
        self._load_current_file(
            self._last_export_path,
            play_source_label="模拟导出结果",
            is_mock_export=True,
        )
        self._export_state = "已加载模拟导出结果为当前音频"
        self.set_status_message("已加载模拟导出结果为当前编辑对象；未写入真实文件。")
        self.stateChanged.emit()

    @Slot()
    def openLastExportLocationMock(self) -> None:
        self.set_status_message("预览模式：模拟导出结果没有真实文件位置。")

    @Slot(bool)
    def setLoadExportResultAfterExport(self, value: bool) -> None:
        self._load_export_result_after_export = bool(value)
        self.stateChanged.emit()

    @Slot()
    def import_audio(self) -> None:
        self.importAudioMock()

    @Slot()
    def clear_current_audio(self) -> None:
        self.clearCurrentAudio()

    @Slot()
    def open_current_file_location(self) -> None:
        self.openCurrentFileLocationMock()

    @Slot()
    def return_to_original_audio(self) -> None:
        self.returnToOriginalMock()

    @Slot()
    def play(self) -> None:
        self.playMock()

    @Slot()
    def pause(self) -> None:
        self.pauseMock()

    @Slot()
    def stop(self) -> None:
        self.stopMock()

    @Slot(float)
    def seek(self, position: float) -> None:
        self.seekMock(position)

    @Slot(float)
    def set_volume(self, value: float) -> None:
        self.setVolume(value)

    @Slot(float)
    def set_pitch_semitone(self, value: float) -> None:
        self.setPitchSemitone(value)

    @Slot()
    def preview_pitch(self) -> None:
        self.previewPitchMock()

    @Slot()
    def export_pitch_to_new_file(self) -> None:
        self.exportPitchMock()

    @Slot()
    def load_export_result_as_current(self) -> None:
        self.loadExportResultAsCurrentMock()

    @Slot()
    def open_last_export_location(self) -> None:
        self.openLastExportLocationMock()

    @Slot(bool)
    def set_load_export_result_after_export(self, value: bool) -> None:
        self.setLoadExportResultAfterExport(value)

    def _load_current_file(
        self,
        file_path: str,
        play_source_label: str,
        is_mock_export: bool = False,
    ) -> None:
        self._play_timer.stop()
        self._current_file_path = file_path
        if not is_mock_export:
            self._original_file_path = file_path
        self._current_file_is_mock_export = is_mock_export
        self._current_play_source = file_path
        self._current_play_source_label = play_source_label
        self._player_state = "stopped"
        self._position = 0
        self._duration = self._MOCK_DURATION_MS

    def _advance_mock_playback(self) -> None:
        if self._player_state != "playing":
            return
        self._position = min(self._position + self._play_timer.interval(), self._duration)
        if self._position >= self._duration:
            self._player_state = "stopped"
            self._position = 0
            self._play_timer.stop()
        self.stateChanged.emit()

    def _reset_mock_results(self) -> None:
        self._preview_timer.stop()
        self._export_timer.stop()
        self._preview_state = "未生成模拟试听"
        self._preview_version_semitone = None
        self._pending_preview_semitone = 0
        self._export_state = "未模拟导出"
        self._export_version_semitone = None
        self._pending_export_semitone = 0
        self._last_export_path = ""

    def _format_pitch_value(self, semitone: int) -> str:
        if semitone == 0:
            return "原调 0 半音"
        return f"{semitone:+d} 半音"

    def _format_pitch_label(self, prefix: str, semitone: int | None = None) -> str:
        value = self._pitch_semitone if semitone is None else semitone
        if value == 0:
            return f"{prefix}（原调）"
        return f"{prefix}（{value:+d} 半音）"

    def _format_preview_source(self, semitone: int) -> str:
        suffix = "0" if semitone == 0 else f"{semitone:+d}"
        return f"preview://pitch/{suffix}/{self.currentFileName}"

    def _build_mock_export_path(self, semitone: int) -> str:
        source_path = self._original_file_path or self._current_file_path
        source = Path(source_path)
        stem = source.stem or "audio"
        sign = "0" if semitone == 0 else f"{semitone:+d}"
        return f"<mock>/{stem}_pitch{sign}.flac"
