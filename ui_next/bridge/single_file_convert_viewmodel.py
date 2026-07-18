from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog

from single_file_convert import (
    SUPPORTED_OUTPUT_FORMATS,
    SUPPORTED_INPUT_EXTENSIONS,
    UNSUPPORTED_INPUT_MESSAGES,
    convert_single_file_to_new_path,
    format_file_size,
    get_input_format_label,
    get_output_format_options,
    validate_single_file_convert_request,
)
from ui_next.bridge.base_viewmodel import BaseViewModel
from ui_next.bridge.capabilities import (
    BATCH_CONVERT,
    METADATA_WRITE,
    OVERWRITE_FILE,
    QUEUE_MUTATION,
    SINGLE_FILE_CONVERT,
    WATCHER_CONTROL,
    CapabilityGate,
)


class _SingleFileConvertThread(QThread):
    resultReady = Signal(dict)

    def __init__(self, input_path: str, output_path: str, target_format: str) -> None:
        super().__init__()
        self._input_path = input_path
        self._output_path = output_path
        self._target_format = target_format

    def run(self) -> None:
        result = convert_single_file_to_new_path(
            self._input_path,
            self._output_path,
            self._target_format,
        )
        self.resultReady.emit(result)


class SingleFileConvertViewModel(BaseViewModel):
    """Capability-gated single file conversion pilot for QML Phase 4.5."""

    stateChanged = Signal()

    _PREVIEW_MESSAGE = "当前模式下单文件转换不可用，不会生成文件。"
    _PREVIEW_SAFETY_MESSAGE = (
        "预览模式：单文件转换不会生成文件。"
    )
    _LIVE_SAFETY_MESSAGE = (
        "单文件转换可用。请手动选择新的输出路径；不会覆盖、不会加入队列，"
        "也不会批量转换。"
    )
    _DISABLED_ACTION_MESSAGE = (
        "当前操作仅支持选择全新输出路径；请使用任务队列进行批量转换。"
        "覆盖已有文件和直接写回均不可用。"
    )

    def __init__(self, capability_gate: CapabilityGate | None = None) -> None:
        super().__init__(capability_gate=capability_gate)
        self._input_path = ""
        self._input_source = ""
        self._output_path = ""
        self._target_format = "flac"
        self._is_converting = False
        self._convert_status = "未开始"
        self._progress_text = "等待选择输入文件和全新输出路径。"
        self._last_error = ""
        self._last_error_code = ""
        self._last_warning = ""
        self._finalization_strategy = ""
        self._temp_cleanup_ok = True
        self._last_result_path = ""
        self._source_size_bytes = 0
        self._output_size_bytes = 0
        self._duration_ms = 0
        self._ffmpeg_returncode = None
        self._ffmpeg_stderr_tail = ""
        self._worker: _SingleFileConvertThread | None = None
        self.set_status_message("等待单文件转换试点操作。")

    @Property(bool, constant=True)
    def previewMode(self) -> bool:
        return not self.singleFileConvertEnabled

    @Property(bool, constant=True)
    def singleFileConvertEnabled(self) -> bool:
        return self.allows_capability(SINGLE_FILE_CONVERT)

    @Property(str, constant=True)
    def previewSafetyMessage(self) -> str:
        return (
            self._LIVE_SAFETY_MESSAGE
            if self.singleFileConvertEnabled
            else self._PREVIEW_SAFETY_MESSAGE
        )

    @Property("QStringList", constant=True)
    def outputFormatOptions(self) -> list[str]:
        return get_output_format_options()

    @Property(str, notify=stateChanged)
    def inputPath(self) -> str:
        return self._input_path

    @Property(str, notify=stateChanged)
    def inputFileName(self) -> str:
        return Path(self._input_path).name if self._input_path else "未选择"

    @Property(str, notify=stateChanged)
    def inputFormat(self) -> str:
        return get_input_format_label(self._input_path) if self._input_path else "未选择"

    @Property(str, notify=stateChanged)
    def inputSourceLabel(self) -> str:
        return self._input_source or "未选择"

    @Property(str, notify=stateChanged)
    def outputPath(self) -> str:
        return self._output_path

    @Property(str, notify=stateChanged)
    def targetFormat(self) -> str:
        return self._target_format

    @Property(bool, notify=stateChanged)
    def isConverting(self) -> bool:
        return self._is_converting

    @Property(str, notify=stateChanged)
    def convertStatus(self) -> str:
        return self._convert_status

    @Property(str, notify=stateChanged)
    def progressText(self) -> str:
        return self._progress_text

    @Property(str, notify=stateChanged)
    def lastError(self) -> str:
        return self._last_error

    @Property(str, notify=stateChanged)
    def lastErrorCode(self) -> str:
        return self._last_error_code

    @Property(str, notify=stateChanged)
    def lastWarning(self) -> str:
        return self._last_warning

    @Property(str, notify=stateChanged)
    def finalizationStrategy(self) -> str:
        return self._finalization_strategy

    @Property(bool, notify=stateChanged)
    def tempCleanupOk(self) -> bool:
        return self._temp_cleanup_ok

    @Property(str, notify=stateChanged)
    def lastResultPath(self) -> str:
        return self._last_result_path

    @Property(str, notify=stateChanged)
    def sourceSizeText(self) -> str:
        return format_file_size(self._source_size_bytes)

    @Property(str, notify=stateChanged)
    def outputSizeText(self) -> str:
        return format_file_size(self._output_size_bytes)

    @Property(int, notify=stateChanged)
    def durationMs(self) -> int:
        return int(self._duration_ms)

    @Property(str, notify=stateChanged)
    def ffmpegStderrTail(self) -> str:
        return self._ffmpeg_stderr_tail

    @Slot()
    def chooseInputFile(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            None,
            "选择单文件转换输入音频",
            self._input_path or "",
            (
                "音频文件 (*.mp3 *.flac *.wav *.m4a *.aac *.ogg *.opus "
                "*.ape *.aiff *.aif *.wma *.alac *.ncm);;所有文件 (*.*)"
            ),
        )
        if not file_path:
            self.set_status_message("已取消选择输入文件。")
            return
        self.setInputPath(file_path)

    @Slot()
    def chooseOutputFile(self) -> None:
        extension = SUPPORTED_OUTPUT_FORMATS.get(
            self._target_format,
            SUPPORTED_OUTPUT_FORMATS["flac"],
        )["extension"]
        start_dir = str(Path(self._input_path).parent) if self._input_path else ""
        file_path, _ = QFileDialog.getSaveFileName(
            None,
            "选择全新输出路径",
            start_dir,
            "音频输出 (*.mp3 *.flac *.wav *.aac *.ogg *.opus *.m4a);;所有文件 (*.*)",
        )
        if not file_path:
            self.set_status_message("已取消选择输出路径。")
            return
        if not Path(file_path).suffix:
            file_path = f"{file_path}{extension}"
        self.setOutputPath(file_path)

    @Slot(str)
    def setInputPath(self, path: str) -> None:
        self._input_path = str(path or "").strip()
        self._input_source = "手动选择"
        self._source_size_bytes = _safe_size(self._input_path)
        self._convert_status = "等待输出路径"
        self._progress_text = (
            "已选择输入文件；请选择一个不存在的全新输出路径。"
        )
        if self._input_path.lower().endswith(".ncm"):
            self._last_error = (
                "当前单文件转换暂不支持 NCM，请继续使用旧 Widgets 自动转码流程。"
            )
            self._last_error_code = "NCM_NOT_SUPPORTED"
            self._convert_status = "校验失败"
            self.set_status_message(self._last_error)
        else:
            self._last_error = ""
            self._last_error_code = ""
            self.set_status_message("已选择输入文件。")
        self.stateChanged.emit()

    @Slot(str)
    def setInputFileFromPreview(self, path: str) -> None:
        if not self.singleFileConvertEnabled:
            self.block_capability(SINGLE_FILE_CONVERT)
            self.stateChanged.emit()
            return

        input_path = str(path or "").strip()
        input_file = Path(input_path)
        if not input_path or not input_file.exists() or not input_file.is_file():
            self._last_error = "目录扫描预览中的文件不存在，未载入转换输入。"
            self._last_error_code = "INPUT_NOT_FOUND"
            self._convert_status = "校验失败"
            self._progress_text = f"校验失败：{self._last_error}"
            self.set_status_message(self._progress_text)
            self.stateChanged.emit()
            return

        suffix = input_file.suffix.lower()
        if suffix in UNSUPPORTED_INPUT_MESSAGES:
            self._last_error = UNSUPPORTED_INPUT_MESSAGES[suffix]
            self._last_error_code = "NCM_NOT_SUPPORTED"
            self._convert_status = "校验失败"
            self._progress_text = f"校验失败：{self._last_error}"
            self.set_status_message(self._progress_text)
            self.stateChanged.emit()
            return
        if suffix not in SUPPORTED_INPUT_EXTENSIONS:
            self._last_error = "目录扫描预览中的文件格式暂不支持单文件转换。"
            self._last_error_code = "INVALID_INPUT"
            self._convert_status = "校验失败"
            self._progress_text = f"校验失败：{self._last_error}"
            self.set_status_message(self._progress_text)
            self.stateChanged.emit()
            return

        self._input_path = input_path
        self._input_source = "目录扫描预览"
        self._output_path = ""
        self._source_size_bytes = _safe_size(input_path)
        self._output_size_bytes = 0
        self._duration_ms = 0
        self._last_error = ""
        self._last_error_code = ""
        self._last_result_path = ""
        self._ffmpeg_returncode = None
        self._ffmpeg_stderr_tail = ""
        self._convert_status = "等待输出路径"
        self._progress_text = "文件已载入，请选择新的输出路径后开始转换。"
        self.set_status_message(self._progress_text)
        self.stateChanged.emit()

    @Slot(str)
    def setInputFileFromCurrentSession(self, path: str) -> None:
        self.setInputFileFromPreview(path)
        if self._input_path == str(path or "").strip() and not self._last_error:
            self._input_source = "当前工作区文件"
            self.set_status_message("已使用当前工作区文件；请手动选择全新输出路径。")
            self.stateChanged.emit()

    @Slot(str)
    def setOutputPath(self, path: str) -> None:
        self._output_path = str(path or "").strip()
        detected = _target_format_from_path(self._output_path)
        if detected:
            self._target_format = detected
        self._convert_status = "等待转换"
        self._progress_text = "输出路径已记录；开始前会再次校验是否可安全写入。"
        self._last_error = ""
        self._last_error_code = ""
        self._last_warning = ""
        self._finalization_strategy = ""
        self._temp_cleanup_ok = True
        self.set_status_message("已选择全新输出路径候选。")
        self.stateChanged.emit()

    @Slot(str)
    def setTargetFormat(self, target_format: str) -> None:
        normalized = str(target_format or "").strip().lower()
        if normalized not in SUPPORTED_OUTPUT_FORMATS:
            self.set_status_message("目标格式暂不支持。")
            return
        self._target_format = normalized
        self.set_status_message(
            f"目标格式已设置为 {normalized}；输出路径必须使用对应后缀。"
        )
        self.stateChanged.emit()

    @Slot(result=bool)
    def validateSingleConvertRequest(self) -> bool:
        validation = validate_single_file_convert_request(
            self._input_path,
            self._output_path,
            self._target_format,
        )
        self._last_error = str(validation.get("error") or "")
        self._last_error_code = str(validation.get("error_code") or "")
        self._source_size_bytes = int(validation.get("source_size_bytes") or self._source_size_bytes)
        if validation.get("ok"):
            self._convert_status = "等待转换"
            self._progress_text = "校验通过：输出路径不存在，可执行单文件转换。"
            self.set_status_message(self._progress_text)
        else:
            self._convert_status = "校验失败"
            self._progress_text = f"校验失败：{self._last_error}"
            self.set_status_message(self._progress_text)
        self.stateChanged.emit()
        return bool(validation.get("ok"))

    @Slot()
    def startSingleFileConvert(self) -> None:
        if not self.singleFileConvertEnabled:
            self._convert_status = "Preview 占位"
            self._progress_text = self._PREVIEW_MESSAGE
            self.set_status_message(self._PREVIEW_MESSAGE)
            self.stateChanged.emit()
            return

        if self._is_converting:
            self.set_status_message("单文件转换正在进行，请稍候。")
            return

        if not self.validateSingleConvertRequest():
            return

        self._is_converting = True
        self._convert_status = "转换中"
        self._progress_text = "正在调用 FFmpeg 生成全新输出文件。"
        self._last_error = ""
        self._last_error_code = ""
        self._last_warning = ""
        self._finalization_strategy = ""
        self._temp_cleanup_ok = True
        self._output_size_bytes = 0
        self._duration_ms = 0
        self._ffmpeg_returncode = None
        self._ffmpeg_stderr_tail = ""
        self.set_status_message("单文件转换中；不会加入 watcher 队列。")
        self.stateChanged.emit()

        worker = _SingleFileConvertThread(
            self._input_path,
            self._output_path,
            self._target_format,
        )
        self._worker = worker
        worker.resultReady.connect(self._apply_convert_result)
        worker.finished.connect(lambda: self._finish_worker(worker))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    @Slot()
    def clearSingleConvertState(self) -> None:
        if self._is_converting:
            self.set_status_message("转换进行中，暂不能清除状态。")
            return
        self._input_path = ""
        self._input_source = ""
        self._output_path = ""
        self._target_format = "flac"
        self._convert_status = "未开始"
        self._progress_text = "等待选择输入文件和全新输出路径。"
        self._last_error = ""
        self._last_error_code = ""
        self._last_warning = ""
        self._finalization_strategy = ""
        self._temp_cleanup_ok = True
        self._last_result_path = ""
        self._source_size_bytes = 0
        self._output_size_bytes = 0
        self._duration_ms = 0
        self._ffmpeg_returncode = None
        self._ffmpeg_stderr_tail = ""
        self.set_status_message("已清除单文件转换试点状态。")
        self.stateChanged.emit()

    @Slot()
    def openOutputLocation(self) -> None:
        path = self._last_result_path or self._output_path
        if not path:
            self.set_status_message("当前没有可打开的输出位置。")
            return
        folder = Path(path).parent
        if not folder.exists():
            self.set_status_message("输出目录不存在。")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
        self.set_status_message("已请求打开输出目录。")

    @Slot()
    def disabledAddToQueue(self) -> None:
        self.block_capability(QUEUE_MUTATION)
        self.set_status_message(self._DISABLED_ACTION_MESSAGE)

    @Slot()
    def disabledBatchConvert(self) -> None:
        self.block_capability(BATCH_CONVERT)
        self.set_status_message(self._DISABLED_ACTION_MESSAGE)

    @Slot()
    def disabledOverwriteConvert(self) -> None:
        self.block_capability(OVERWRITE_FILE)
        self.set_status_message(self._DISABLED_ACTION_MESSAGE)

    @Slot()
    def disabledApplyToWatcher(self) -> None:
        self.block_capability(WATCHER_CONTROL)
        self.set_status_message(self._DISABLED_ACTION_MESSAGE)

    @Slot()
    def disabledWriteMetadata(self) -> None:
        self.block_capability(METADATA_WRITE)
        self.set_status_message(self._DISABLED_ACTION_MESSAGE)

    def _apply_convert_result(self, result: dict) -> None:
        self._is_converting = False
        self._last_error = str(result.get("error") or "")
        self._last_error_code = str(result.get("error_code") or "")
        self._last_warning = str(result.get("warning") or "")
        self._finalization_strategy = str(result.get("finalization_strategy") or "")
        self._temp_cleanup_ok = bool(result.get("temp_cleanup_ok", True))
        self._last_result_path = str(result.get("output_path") or "") if result.get("ok") else ""
        self._source_size_bytes = int(result.get("source_size_bytes") or self._source_size_bytes)
        self._output_size_bytes = int(result.get("output_size_bytes") or 0)
        self._duration_ms = int(result.get("duration_ms") or 0)
        self._ffmpeg_returncode = result.get("ffmpeg_returncode")
        self._ffmpeg_stderr_tail = str(result.get("ffmpeg_stderr_tail") or "")

        if result.get("ok"):
            self._convert_status = "转换成功"
            self._progress_text = (
                "转换成功：已生成全新输出文件，"
                f"最终落位策略 {self._finalization_strategy or 'unknown'}，"
                f"用时 {self._duration_ms} ms。"
            )
            if self._last_warning:
                self._progress_text += f" 警告：{self._last_warning}"
            self.set_status_message(self._progress_text)
        else:
            self._convert_status = {
                "OUTPUT_EXISTS": "输出路径已存在",
                "OUTPUT_CONFLICT": "并发输出冲突",
                "TEMP_CLEANUP_FAILED": "清理失败",
            }.get(self._last_error_code, "转换失败")
            self._progress_text = f"转换失败：{self._last_error}"
            if self._last_warning:
                self._progress_text += f" 警告：{self._last_warning}"
            self.set_status_message(self._progress_text)
        self.stateChanged.emit()

    def _finish_worker(self, worker: _SingleFileConvertThread) -> None:
        if self._worker is worker:
            self._worker = None
        if self._is_converting:
            self._is_converting = False
            self.stateChanged.emit()


def _safe_size(path: str) -> int:
    try:
        return int(Path(path).stat().st_size)
    except OSError:
        return 0


def _target_format_from_path(path: str) -> str:
    suffix = Path(str(path or "")).suffix.lower()
    for name, info in SUPPORTED_OUTPUT_FORMATS.items():
        if suffix == info["extension"]:
            return name
    return ""
