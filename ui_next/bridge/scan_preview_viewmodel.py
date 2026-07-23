from __future__ import annotations

from datetime import datetime
import threading

from PySide6.QtCore import Property, QThread, Signal, Slot
from PySide6.QtWidgets import QFileDialog

from scan_preview import DEFAULT_MAX_FILES, scan_directory_preview
from ui_next.bridge.base_viewmodel import BaseViewModel
from ui_next.bridge.capabilities import (
    BATCH_CONVERT,
    QUEUE_MUTATION,
    SCAN_PREVIEW,
    SINGLE_FILE_CONVERT,
    CapabilityGate,
)


class _ScanPreviewThread(QThread):
    resultReady = Signal(dict, int, int)
    progressReady = Signal(dict, int, int)

    def __init__(
        self,
        folder_path: str,
        recursive: bool,
        max_files: int,
        request_id: int,
        folder_generation: int,
        stop_event: threading.Event,
    ) -> None:
        super().__init__()
        self._folder_path = folder_path
        self._recursive = recursive
        self._max_files = max_files
        self._request_id = request_id
        self._folder_generation = folder_generation
        self._stop_event = stop_event

    def run(self) -> None:
        result = scan_directory_preview(
            self._folder_path,
            recursive=self._recursive,
            max_files=self._max_files,
            stop_event=self._stop_event,
            progress_callback=lambda summary: self.progressReady.emit(
                summary,
                self._request_id,
                self._folder_generation,
            ),
        )
        self.resultReady.emit(result, self._request_id, self._folder_generation)


class ScanPreviewViewModel(BaseViewModel):
    """Capability-gated scan results with explicit queue handoff requests."""

    stateChanged = Signal()
    requestSingleFileConvert = Signal(str)
    requestCurrentFileSession = Signal(str)
    requestQueueAdd = Signal(object, str, int)

    _PREVIEW_MESSAGE = "当前模式下目录扫描不可用，只显示安全预览内容。"
    _PREVIEW_SAFETY_MESSAGE = (
        "预览模式：目录扫描区域仅显示占位内容，不读取真实目录。"
    )
    _LIVE_SAFETY_MESSAGE = "目录扫描已启用；扫描只读取目录，转换仍需显式加入队列并启动。"
    _SINGLE_FILE_HANDOFF_MESSAGE = (
        "已选择：{filename}。请前往单文件转换区域选择输出路径。"
    )

    def __init__(self, capability_gate: CapabilityGate | None = None) -> None:
        super().__init__(capability_gate=capability_gate)
        self._folder_path = ""
        self._recursive = False
        self._is_scanning = False
        self._last_error = ""
        self._total_entries = 0
        self._scanned_files = 0
        self._supported_count = 0
        self._unsupported_count = 0
        self._lrc_count = 0
        self._too_many_files = False
        self._last_scan_time = "尚未扫描"
        self._items: list[dict[str, object]] = []
        self._selected_file_paths: set[str] = set()
        self._scan_thread: _ScanPreviewThread | None = None
        self._scan_stop_event: threading.Event | None = None
        self._request_id = 0
        self._folder_generation = 0
        self._active_request_id = 0
        self.set_status_message("等待选择目录进行扫描预览。")

    @Property(bool, constant=True)
    def previewMode(self) -> bool:
        return not self.scanPreviewEnabled

    @Property(bool, constant=True)
    def scanPreviewEnabled(self) -> bool:
        return self.allows_capability(SCAN_PREVIEW)

    @Property(str, constant=True)
    def previewSafetyMessage(self) -> str:
        return (
            self._LIVE_SAFETY_MESSAGE
            if self.scanPreviewEnabled
            else self._PREVIEW_SAFETY_MESSAGE
        )

    @Property(str, notify=stateChanged)
    def folderPath(self) -> str:
        return self._folder_path

    @Property(bool, notify=stateChanged)
    def recursive(self) -> bool:
        return self._recursive

    @Property(bool, notify=stateChanged)
    def isScanning(self) -> bool:
        return self._is_scanning

    @Property(str, notify=stateChanged)
    def lastError(self) -> str:
        return self._last_error

    @Property(int, notify=stateChanged)
    def totalEntries(self) -> int:
        return self._total_entries

    @Property(int, notify=stateChanged)
    def scannedFiles(self) -> int:
        return self._scanned_files

    @Property(int, notify=stateChanged)
    def supportedCount(self) -> int:
        return self._supported_count

    @Property(int, notify=stateChanged)
    def unsupportedCount(self) -> int:
        return self._unsupported_count

    @Property(int, notify=stateChanged)
    def lrcCount(self) -> int:
        return self._lrc_count

    @Property(bool, notify=stateChanged)
    def tooManyFiles(self) -> bool:
        return self._too_many_files

    @Property(str, notify=stateChanged)
    def lastScanTime(self) -> str:
        return self._last_scan_time

    @Property(int, constant=True)
    def maxFiles(self) -> int:
        return DEFAULT_MAX_FILES

    @Property("QVariantList", notify=stateChanged)
    def items(self) -> list[dict[str, object]]:
        return list(self._items)

    @Property(int, notify=stateChanged)
    def itemCount(self) -> int:
        return len(self._items)

    @Property(str, notify=stateChanged)
    def selectedFilePath(self) -> str:
        return next(iter(self._selected_file_paths), "")

    @Property("QStringList", notify=stateChanged)
    def selectedFilePaths(self) -> list[str]:
        return sorted(self._selected_file_paths)

    @Property(str, notify=stateChanged)
    def selectedFileName(self) -> str:
        for item in self._items:
            if str(item.get("path") or "") == self.selectedFilePath:
                return str(item.get("filename") or "")
        return ""

    @Property(bool, notify=stateChanged)
    def hasSelectedAudio(self) -> bool:
        return bool(self._selected_file_paths)

    @Property(int, notify=stateChanged)
    def selectedCount(self) -> int:
        return len(self._selected_file_paths)

    @Property(bool, notify=stateChanged)
    def queueMutationEnabled(self) -> bool:
        return self.allows_capability(QUEUE_MUTATION)

    @Property(bool, notify=stateChanged)
    def canAddSelectedToQueue(self) -> bool:
        return self.queueMutationEnabled and bool(self._queue_eligible_selected_paths())

    @Property(bool, notify=stateChanged)
    def canAddAllToQueue(self) -> bool:
        return self.queueMutationEnabled and bool(self._queue_eligible_paths())

    @Property(bool, notify=stateChanged)
    def singleFileConvertEnabled(self) -> bool:
        return self.allows_capability(SINGLE_FILE_CONVERT)

    @Property(bool, notify=stateChanged)
    def canUseSelectedFileForConvert(self) -> bool:
        return self.hasSelectedAudio and self.singleFileConvertEnabled

    @Slot()
    def chooseFolderForPreview(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            None,
            "选择目录进行只读扫描预览",
            self._folder_path or "",
        )
        if not folder:
            self.set_status_message("已取消选择目录。")
            return
        normalized_folder = str(folder)
        if normalized_folder != self._folder_path:
            self._folder_generation += 1
            self.cancelScan()
            self._items = []
            self._selected_file_paths.clear()
            self._clear_result_counts()
        self._folder_path = normalized_folder
        self.set_status_message(
            "已选择目录；点击“扫描”生成候选列表。"
        )
        self.stateChanged.emit()

    @Slot()
    def scanSelectedFolderPreview(self) -> None:
        self.scanFolderPreview(self._folder_path)

    @Slot(str)
    def scanFolderPreview(self, path: str) -> None:
        normalized_path = str(path or "").strip()
        if normalized_path != self._folder_path:
            self._folder_generation += 1
            self._selected_file_paths.clear()
        self._folder_path = normalized_path
        if not normalized_path:
            self.set_status_message("当前没有可扫描的目录。")
            self.stateChanged.emit()
            return

        if not self.scanPreviewEnabled:
            self._clear_result_counts()
            self.set_status_message(self._PREVIEW_MESSAGE)
            self.stateChanged.emit()
            return

        if self._is_scanning:
            self.cancelScan()

        self._is_scanning = True
        self._last_error = ""
        self._request_id += 1
        self._active_request_id = self._request_id
        stop_event = threading.Event()
        self._scan_stop_event = stop_event
        self.set_status_message("正在扫描目录；不会自动加入任务队列或转换。")
        self.stateChanged.emit()

        thread = _ScanPreviewThread(
            normalized_path,
            recursive=self._recursive,
            max_files=DEFAULT_MAX_FILES,
            request_id=self._active_request_id,
            folder_generation=self._folder_generation,
            stop_event=stop_event,
        )
        self._scan_thread = thread
        thread.resultReady.connect(self._apply_scan_result)
        thread.progressReady.connect(self._apply_scan_progress)
        thread.finished.connect(lambda: self._finish_scan_thread(thread))
        thread.finished.connect(thread.deleteLater)
        thread.start()

    @Slot()
    def clearPreview(self) -> None:
        self.cancelScan()
        self._request_id += 1
        self._active_request_id = self._request_id
        self._is_scanning = False
        self._scan_stop_event = None
        self._items = []
        self._selected_file_paths.clear()
        self._clear_result_counts()
        self._last_scan_time = "尚未扫描"
        self.set_status_message(
            "已清除扫描预览；未修改任何文件或任务队列。"
        )
        self.stateChanged.emit()

    @Slot(bool)
    def setRecursivePreview(self, enabled: bool) -> None:
        self._recursive = bool(enabled)
        self.set_status_message(
            "递归扫描预览已开启；仍只读取文件列表。"
            if self._recursive
            else "递归扫描预览已关闭；默认只扫描当前目录。"
        )
        self.stateChanged.emit()

    @Slot()
    def disabledAddToQueue(self) -> None:
        self.block_capability(QUEUE_MUTATION)

    @Slot()
    def disabledStartConvert(self) -> None:
        self.block_capability(BATCH_CONVERT)

    @Slot()
    def disabledScanAndQueue(self) -> None:
        self.disabledAddToQueue()

    @Slot()
    def disabledApplyTargetFormat(self) -> None:
        self.disabledAddToQueue()

    @Slot(str)
    def selectAudioCandidate(self, path: str) -> None:
        if not self.scanPreviewEnabled:
            self.block_capability(SCAN_PREVIEW)
            self.stateChanged.emit()
            return

        selected_path = str(path or "").strip()
        selected_item = next(
            (
                item
                for item in self._items
                if str(item.get("path") or "") == selected_path
                and bool(item.get("is_supported_audio"))
            ),
            None,
        )
        if selected_item is None:
            self._selected_file_paths.clear()
            self.set_status_message("请选择一个支持的音频候选文件。")
            self.stateChanged.emit()
            return

        if not bool(selected_item.get("can_add_to_queue", True)) and selected_path not in self._selected_file_paths:
            self.set_status_message("该文件已在任务队列中或不能加入队列。")
            self.stateChanged.emit()
            return
        if selected_path in self._selected_file_paths:
            self._selected_file_paths.remove(selected_path)
        else:
            self._selected_file_paths.add(selected_path)
        filename = str(selected_item.get("filename") or selected_path)
        self.set_status_message(
            self._SINGLE_FILE_HANDOFF_MESSAGE.format(filename=filename)
        )
        self.stateChanged.emit()

    @Slot()
    def sendSelectedFileToSingleConvert(self) -> None:
        if not self.selectedFilePath:
            self.set_status_message("请选择一个音频文件。")
            self.stateChanged.emit()
            return
        if not self.singleFileConvertEnabled:
            self.block_capability(SINGLE_FILE_CONVERT)
            self.stateChanged.emit()
            return

        self.requestSingleFileConvert.emit(self.selectedFilePath)

    @Slot()
    def loadSelectedFileIntoWorkspace(self) -> None:
        if not self.selectedFilePath:
            self.set_status_message("请选择一个支持的音频候选文件。")
            self.stateChanged.emit()
            return
        self.requestCurrentFileSession.emit(self.selectedFilePath)
        self.set_status_message(
            f"已将 {self.selectedFileName} 载入当前工作区；未加入 watcher 队列。"
        )
        self.stateChanged.emit()

    @Slot()
    def cancelScan(self) -> None:
        if self._scan_stop_event is None or not self._is_scanning:
            return
        self._scan_stop_event.set()
        self.set_status_message("正在取消扫描；当前结果不会覆盖新的目录请求。")

    @Slot()
    def addSelectedToQueue(self) -> None:
        if not self.queueMutationEnabled:
            self.disabledAddToQueue()
            return
        paths = self._queue_eligible_selected_paths()
        self._request_queue_add(paths)

    @Slot()
    def addAllToQueue(self) -> None:
        if not self.queueMutationEnabled:
            self.disabledAddToQueue()
            return
        self._request_queue_add(self._queue_eligible_paths())

    def markQueuedPaths(self, paths: list[str]) -> None:
        normalized_paths = {str(path) for path in paths}
        changed = False
        for item in self._items:
            if str(item.get("path") or "") not in normalized_paths:
                continue
            item["queue_status"] = "已在任务队列"
            item["scan_status"] = "已入队"
            item["can_add_to_queue"] = False
            item["skip_reason"] = "已存在于任务队列"
            changed = True
        self._selected_file_paths.difference_update(normalized_paths)
        if changed:
            self.stateChanged.emit()

    def _request_queue_add(self, paths: list[str]) -> None:
        if not paths:
            self.set_status_message("没有可加入任务队列的扫描结果。")
            self.stateChanged.emit()
            return
        self.requestQueueAdd.emit(paths, self._folder_path, self._folder_generation)
        self.set_status_message(f"已请求将 {len(paths)} 个扫描结果加入任务队列；不会自动开始转换。")
        self.stateChanged.emit()

    def _apply_scan_progress(
        self,
        summary: dict,
        request_id: int,
        folder_generation: int,
    ) -> None:
        if not self._is_current_request(request_id, folder_generation):
            return
        self._total_entries = int(summary.get("total_entries") or 0)
        self._scanned_files = int(summary.get("scanned_files") or 0)
        self._supported_count = int(summary.get("supported_count") or 0)
        self._unsupported_count = int(summary.get("unsupported_count") or 0)
        self._lrc_count = int(summary.get("lrc_count") or 0)
        self.stateChanged.emit()

    def _apply_scan_result(
        self,
        result: dict,
        request_id: int,
        folder_generation: int,
    ) -> None:
        if not self._is_current_request(request_id, folder_generation):
            return
        self._folder_path = str(result.get("folder_path") or self._folder_path)
        self._items = list(result.get("items") or [])
        if not any(
            str(item.get("path") or "") in self._selected_file_paths
            and bool(item.get("is_supported_audio"))
            for item in self._items
        ):
            self._selected_file_paths.clear()
        self._total_entries = int(result.get("total_entries") or 0)
        self._scanned_files = int(result.get("scanned_files") or 0)
        self._supported_count = int(result.get("supported_count") or 0)
        self._unsupported_count = int(result.get("unsupported_count") or 0)
        self._lrc_count = int(result.get("lrc_count") or 0)
        self._too_many_files = bool(result.get("too_many_files"))
        self._last_error = str(result.get("error") or "")
        self._last_scan_time = datetime.now().strftime("%H:%M:%S")
        if result.get("cancelled"):
            self.set_status_message("扫描已取消；未修改任务队列或产生输出。")
        elif result.get("ok"):
            message = (
                f"扫描预览完成：{self._supported_count} 个支持的音频候选，"
                f"{self._lrc_count} 个 .lrc。"
            )
            if self._too_many_files:
                message += " 结果已按上限截断。"
            self.set_status_message(message)
        else:
            self.set_status_message(f"扫描预览失败：{self._last_error}")
        self._is_scanning = False
        self._scan_stop_event = None
        self.stateChanged.emit()

    def _finish_scan_thread(self, thread: _ScanPreviewThread) -> None:
        if self._scan_thread is thread:
            self._scan_thread = None
            if self._is_scanning:
                self._is_scanning = False
                self.stateChanged.emit()

    def _is_current_request(self, request_id: int, folder_generation: int) -> bool:
        return (
            request_id == self._active_request_id
            and folder_generation == self._folder_generation
        )

    def _queue_eligible_paths(self) -> list[str]:
        return [
            str(item.get("path") or "")
            for item in self._items
            if bool(item.get("is_supported_audio"))
            and bool(item.get("can_add_to_queue", True))
        ]

    def _queue_eligible_selected_paths(self) -> list[str]:
        eligible = set(self._queue_eligible_paths())
        return [path for path in self.selectedFilePaths if path in eligible]

    def _clear_result_counts(self) -> None:
        self._last_error = ""
        self._total_entries = 0
        self._scanned_files = 0
        self._supported_count = 0
        self._unsupported_count = 0
        self._lrc_count = 0
        self._too_many_files = False
