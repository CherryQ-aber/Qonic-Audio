from __future__ import annotations

import os
import threading
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Property, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import QFileDialog, QMessageBox

import watcher
from config import (
    get_create_format_subfolder,
    get_output_folder,
    get_target_format,
    get_watch_folder,
    is_valid_watch_folder,
    load_config,
    save_config,
)
from formats import (
    get_target_format_options,
    get_target_label,
    is_supported_input_file,
    normalize_target_format,
)
from scan_preview import DEFAULT_MAX_FILES, scan_directory_preview
from ui_next.bridge.base_viewmodel import BaseViewModel
from ui_next.bridge.capabilities import (
    BATCH_CONVERT,
    CONFIG_WRITE,
    QUEUE_MUTATION,
    SCAN_PREVIEW,
    WATCHER_CONTROL,
    CapabilityGate,
)
from ui_next.bridge.drop_path_utils import extract_local_drop_paths
from ui_next.bridge.task_queue_model import TaskQueueModel


def _task_snapshot(
    file_path: str,
    *,
    config_data: dict,
    source: str,
    source_root: str,
    request_generation: int,
) -> dict:
    normalized_path = os.path.abspath(os.path.normpath(file_path))
    normalized_root = (
        os.path.abspath(os.path.normpath(source_root))
        if source_root
        else os.path.dirname(normalized_path)
    )
    try:
        relative_path = os.path.relpath(normalized_path, normalized_root)
    except ValueError:
        relative_path = os.path.basename(normalized_path)
    return {
        "target_format": normalize_target_format(config_data.get("target_format")),
        "target_format_override": None,
        "output_directory": str(config_data.get("output_folder") or ""),
        "output_directory_override": None,
        "enabled_for_run": True,
        "relative_output_path": relative_path,
        "preserve_relative_structure": bool(
            config_data.get("preserve_relative_structure", False)
        ),
        "source_action": "保留源文件",
        "request_generation": int(request_generation),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_root": normalized_root,
        "source": source,
        "create_format_subfolder": bool(
            config_data.get("create_format_subfolder", True)
        ),
    }


def _enqueue_paths_to_watcher(
    file_paths: list[str],
    *,
    config_data: dict,
    source: str,
    source_root: str = "",
    request_generation: int = 0,
) -> dict[str, object]:
    summary: dict[str, object] = {
        "added_paths": [],
        "added_count": 0,
        "duplicate_count": 0,
        "unsupported_count": 0,
    }
    seen: set[str] = set()
    for file_path in file_paths:
        normalized_path = os.path.abspath(os.path.normpath(str(file_path or "")))
        identity = os.path.normcase(normalized_path)
        if not normalized_path or identity in seen:
            summary["duplicate_count"] = int(summary["duplicate_count"]) + 1
            continue
        seen.add(identity)

        if not os.path.isfile(normalized_path) or not is_supported_input_file(
            normalized_path
        ):
            summary["unsupported_count"] = int(summary["unsupported_count"]) + 1
            continue

        snapshot = _task_snapshot(
            normalized_path,
            config_data=config_data,
            source=source,
            source_root=source_root,
            request_generation=request_generation,
        )
        if watcher.handle_detected_file(
            normalized_path,
            source=source,
            task_snapshot=snapshot,
        ):
            added_paths = summary["added_paths"]
            if isinstance(added_paths, list):
                added_paths.append(normalized_path)
            summary["added_count"] = int(summary["added_count"]) + 1
        else:
            summary["duplicate_count"] = int(summary["duplicate_count"]) + 1
    return summary


class WatcherThread(QThread):
    def __init__(self, watch_folder: str, parent=None) -> None:
        super().__init__(parent)
        self.watch_folder = watch_folder
        self.stop_event = threading.Event()

    def run(self) -> None:
        watcher.start_watch(
            stop_event=self.stop_event,
            watch_folder=self.watch_folder,
        )

    def stop(self) -> None:
        self.stop_event.set()


class ConvertThread(QThread):
    taskUpdated = Signal(str, str)

    def __init__(
        self,
        default_target_format: str,
        output_root_override: str | None = None,
        create_format_subfolder: bool | None = None,
        selected_paths: set[str] | None = None,
        include_disabled: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.default_target_format = default_target_format
        self.output_root_override = output_root_override
        self.create_format_subfolder = create_format_subfolder
        self.selected_paths = {
            os.path.normcase(os.path.abspath(os.path.normpath(path)))
            for path in (selected_paths or set())
        }
        self.include_disabled = bool(include_disabled)
        self._cancel_event = threading.Event()
        self._stop_after_current_event = threading.Event()

    def run(self) -> None:
        from converter import convert_audio

        tasks = watcher.get_convertible_tasks(
            include_disabled=self.include_disabled
        )
        if self.selected_paths:
            tasks = [
                task
                for task in tasks
                if os.path.normcase(
                    os.path.abspath(os.path.normpath(str(task.get("path") or "")))
                )
                in self.selected_paths
            ]

        for task in tasks:
            if (
                self.isInterruptionRequested()
                or self._cancel_event.is_set()
                or self._stop_after_current_event.is_set()
            ):
                break

            file_path = task["path"]
            file_name = task["filename"]
            input_path = task["input_path"]
            is_ncm_task = task["is_ncm_task"]
            target_format = (
                task.get("target_format_override")
                or self.default_target_format
            )
            output_root = str(
                task.get("output_directory_override")
                or self.output_root_override
                or get_output_folder()
                or ""
            )
            if bool(task.get("preserve_relative_structure")) and output_root:
                relative_parent = Path(str(task.get("relative_output_path") or "")).parent
                if str(relative_parent) not in {"", "."}:
                    output_root = os.path.join(output_root, str(relative_parent))
            create_format_subfolder = task.get("create_format_subfolder")
            if create_format_subfolder is None:
                create_format_subfolder = self.create_format_subfolder

            try:
                if not watcher.has_pending_file(file_path):
                    continue

                if not watcher.claim_pending_file_for_conversion(
                    file_path,
                    include_disabled=self.include_disabled,
                ):
                    continue

                watcher.set_pending_file_runtime_data(
                    file_path,
                    stage="正在转换" if not is_ncm_task else "NCM 已解码，正在转换",
                    error_summary="",
                )
                self.taskUpdated.emit(file_path, "正在转换")

                result = convert_audio(
                    input_path,
                    target_format,
                    output_root_override=output_root,
                    create_format_subfolder=create_format_subfolder,
                    preserve_source=True,
                    original_source_path=file_path,
                    lyrics_source_paths=[file_path, input_path],
                    cancel_event=self._cancel_event,
                    safe_publish=True,
                )
                success = result.get("success", False) if isinstance(result, dict) else bool(result)

                if success:
                    watcher.set_pending_file_status(file_path, watcher.COMPLETED_STATUS)
                    watcher.set_pending_file_runtime_data(
                        file_path,
                        stage="已发布输出",
                        output_path=str(result.get("output_path") or ""),
                        error_summary="",
                    )
                    self.taskUpdated.emit(file_path, "已完成")
                elif isinstance(result, dict) and result.get("cancelled"):
                    watcher.set_pending_file_status(file_path, watcher.CANCELLED_STATUS)
                    watcher.set_pending_file_runtime_data(
                        file_path,
                        stage="已取消",
                        error_summary=str(result.get("error") or "用户取消"),
                    )
                    self.taskUpdated.emit(file_path, "已取消")
                else:
                    watcher.set_pending_file_status(file_path, watcher.FAILED_STATUS)
                    watcher.set_pending_file_runtime_data(
                        file_path,
                        stage="转换失败",
                        error_summary=str(result.get("error") or "转换失败"),
                    )
                    self.taskUpdated.emit(file_path, "转换失败")

                watcher.clear_processed_file(file_path)
                if is_ncm_task:
                    watcher.cleanup_task_runtime_files(file_path)
                if self._stop_after_current_event.is_set():
                    break
            except Exception as exc:
                watcher.set_pending_file_status(file_path, watcher.FAILED_STATUS)
                watcher.set_pending_file_runtime_data(
                    file_path,
                    stage="转换失败",
                    error_summary=str(exc),
                )
                watcher.clear_processed_file(file_path)
                if is_ncm_task:
                    watcher.cleanup_task_runtime_files(file_path)
                watcher.logger.exception(f"QML 转换线程处理失败: {file_name}")

    def stop(self) -> None:
        self._cancel_event.set()
        self.requestInterruption()

    def stop_after_current(self) -> None:
        self._stop_after_current_event.set()


class ScanThread(QThread):
    scanProgress = Signal(dict)
    scanFinished = Signal(dict)

    def __init__(self, watch_folder: str, parent=None) -> None:
        super().__init__(parent)
        self.watch_folder = watch_folder
        self.stop_event = threading.Event()

    def run(self) -> None:
        summary = watcher.scan_existing_files(
            self.watch_folder,
            stop_event=self.stop_event,
            progress_callback=self.scanProgress.emit,
            return_summary=True,
        )
        self.scanFinished.emit(summary)

    def stop(self) -> None:
        self.stop_event.set()


class RetryThread(QThread):
    retryFinished = Signal(dict)

    def __init__(self, file_paths: list[str], parent=None) -> None:
        super().__init__(parent)
        self.file_paths = file_paths
        self.stop_event = threading.Event()

    def run(self) -> None:
        summary = watcher.retry_failed_files(
            self.file_paths,
            stop_event=self.stop_event,
        )
        self.retryFinished.emit(summary)

    def stop(self) -> None:
        self.stop_event.set()


class QueuePrepareThread(QThread):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.stop_event = threading.Event()

    def run(self) -> None:
        watcher.prepare_pending_files(
            stop_event=self.stop_event,
            keep_running=True,
        )

    def stop(self) -> None:
        self.stop_event.set()


class DirectoryScanThread(QThread):
    scanProgress = Signal(dict)
    scanFinished = Signal(dict)

    def __init__(
        self,
        folder_paths: list[str],
        config_data: dict,
        request_generation: int,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.folder_paths = list(folder_paths)
        self.config_data = dict(config_data)
        self.request_generation = int(request_generation)
        self.stop_event = threading.Event()

    def run(self) -> None:
        summary = {
            "total_count": 0,
            "added_count": 0,
            "duplicate_count": 0,
            "unsupported_count": 0,
            "cancelled": False,
            "completed": False,
            "current_file": "",
            "error": "",
        }
        for folder_path in self.folder_paths:
            if self.stop_event.is_set():
                summary["cancelled"] = True
                break

            base_total = int(summary["total_count"])
            result = scan_directory_preview(
                folder_path,
                recursive=False,
                max_files=DEFAULT_MAX_FILES,
                stop_event=self.stop_event,
                progress_callback=lambda progress, offset=base_total: self.scanProgress.emit(
                    {
                        **summary,
                        "total_count": offset
                        + int(progress.get("scanned_files") or 0),
                        "current_file": str(
                            (progress.get("items") or [{}])[-1].get("filename")
                            if progress.get("items")
                            else ""
                        ),
                    }
                ),
            )

            supported_paths = [
                str(item.get("path") or "")
                for item in list(result.get("items") or [])
                if bool(item.get("is_supported_audio"))
            ]
            enqueue_summary = _enqueue_paths_to_watcher(
                supported_paths,
                config_data=self.config_data,
                source="qml_scan",
                source_root=folder_path,
                request_generation=self.request_generation,
            )
            summary["total_count"] = int(summary["total_count"]) + int(
                result.get("scanned_files") or 0
            )
            summary["added_count"] = int(summary["added_count"]) + int(
                enqueue_summary["added_count"]
            )
            summary["duplicate_count"] = int(summary["duplicate_count"]) + int(
                enqueue_summary["duplicate_count"]
            )
            summary["unsupported_count"] = int(summary["unsupported_count"]) + int(
                result.get("unsupported_count") or 0
            ) + int(result.get("lrc_count") or 0)
            summary["cancelled"] = bool(result.get("cancelled")) or self.stop_event.is_set()
            summary["error"] = str(result.get("error") or "")
            self.scanProgress.emit(dict(summary))

            if summary["cancelled"]:
                break
            if not result.get("ok") and summary["error"]:
                break

        summary["completed"] = not bool(summary["cancelled"]) and not bool(
            summary["error"]
        )
        self.scanFinished.emit(summary)

    def stop(self) -> None:
        self.stop_event.set()


class AutoConvertViewModel(BaseViewModel):
    watchFolderChanged = Signal()
    outputFolderChanged = Signal()
    globalTargetFormatChanged = Signal()
    monitoringChanged = Signal()
    busyChanged = Signal()
    lastOperationChanged = Signal()
    errorSummaryChanged = Signal()
    backgroundTaskLabelChanged = Signal()
    scanSummaryChanged = Signal()
    scanQueueAccepted = Signal(object)
    _PREVIEW_SAFETY_MESSAGE = (
        "预览模式：自动转码页当前只用于查看任务队列和状态，"
        "不会执行真实监听或转换。"
    )

    def __init__(
        self,
        task_queue_model: TaskQueueModel,
        parent=None,
        capability_gate: CapabilityGate | None = None,
        live_mode: bool | None = None,
    ) -> None:
        gate = capability_gate or CapabilityGate()
        super().__init__(parent, capability_gate=gate)
        self._task_queue_model = task_queue_model
        self._watcher_thread: WatcherThread | None = None
        self._convert_thread: ConvertThread | None = None
        self._scan_thread: ScanThread | None = None
        self._retry_thread: RetryThread | None = None
        self._prepare_thread: QueuePrepareThread | None = None
        self._directory_scan_thread: DirectoryScanThread | None = None
        self._scan_total_count = 0
        self._scan_added_count = 0
        self._scan_duplicate_count = 0
        self._scan_unsupported_count = 0
        self._scan_status_label = "尚未扫描"
        self._scan_was_cancelled = False
        self._scan_request_generation = 0
        self._last_operation = (
            self._PREVIEW_SAFETY_MESSAGE
            if self.previewMode
            else "等待手动扫描、入队或开始转换。"
        )
        self._error_summary = ""
        self._background_task_label = "空闲"

        self._state_timer = QTimer(self)
        self._state_timer.setInterval(
            500 if gate.allows(WATCHER_CONTROL) else 3000
        )
        self._state_timer.timeout.connect(self._emit_runtime_state)
        self._state_timer.start()

    @Property(str, notify=watchFolderChanged)
    def watchFolder(self) -> str:
        return get_watch_folder()

    @Property(str, notify=outputFolderChanged)
    def outputFolder(self) -> str:
        return get_output_folder()

    @Property(str, notify=globalTargetFormatChanged)
    def globalTargetFormat(self) -> str:
        return get_target_format()

    @Property(str, notify=globalTargetFormatChanged)
    def globalTargetFormatLabel(self) -> str:
        return get_target_label(get_target_format())

    @Property(str, notify=globalTargetFormatChanged)
    def formatSubfolderStatus(self) -> str:
        return "已启用" if get_create_format_subfolder() else "未启用"

    @Property("QVariantList", constant=True)
    def targetFormats(self) -> list[dict[str, str]]:
        return [
            {"value": target_format, "label": get_target_label(target_format)}
            for target_format in get_target_format_options()
        ]

    @Property("QVariantList", notify=globalTargetFormatChanged)
    def targetFormatsWithFollow(self) -> list[dict[str, str]]:
        return [
            {"value": "", "label": f"跟随全局（{self.globalTargetFormatLabel}）"},
            *self.targetFormats,
        ]

    @Property(bool, constant=True)
    def previewMode(self) -> bool:
        return not any(
            self.allows_capability(capability)
            for capability in (
                WATCHER_CONTROL,
                QUEUE_MUTATION,
                BATCH_CONVERT,
                CONFIG_WRITE,
            )
        )

    @Property(bool, constant=True)
    def liveMode(self) -> bool:
        return not self.previewMode

    @Property(str, constant=True)
    def modeLabel(self) -> str:
        return "自动转码能力未启用" if self.previewMode else "自动转码能力已启用"

    @Property(str, constant=True)
    def previewSafetyMessage(self) -> str:
        return self._PREVIEW_SAFETY_MESSAGE

    @Property(bool, constant=True)
    def canControlWatcher(self) -> bool:
        return self.allows_capability(WATCHER_CONTROL) and self.allows_capability(QUEUE_MUTATION)

    @Property(bool, constant=True)
    def canMutateQueue(self) -> bool:
        return self.allows_capability(QUEUE_MUTATION)

    @Property(bool, constant=True)
    def canAddFiles(self) -> bool:
        return self.allows_capability(QUEUE_MUTATION)

    @Property(bool, constant=True)
    def canScanDirectories(self) -> bool:
        return self.allows_capability(SCAN_PREVIEW) and self.allows_capability(
            QUEUE_MUTATION
        )

    @Property(bool, constant=True)
    def canBatchConvert(self) -> bool:
        return self.allows_capability(BATCH_CONVERT)

    @Property(bool, constant=True)
    def canWriteConfig(self) -> bool:
        return self.allows_capability(CONFIG_WRITE)

    @Property(bool, notify=busyChanged)
    def canCancelCurrentTask(self) -> bool:
        return self._is_thread_running(self._convert_thread)

    @Property(bool, notify=busyChanged)
    def canStopAfterCurrentTask(self) -> bool:
        return self._is_thread_running(self._convert_thread)

    @Property(bool, notify=monitoringChanged)
    def isMonitoring(self) -> bool:
        return self._is_thread_running(self._watcher_thread)

    @Property(bool, notify=scanSummaryChanged)
    def isDirectoryScanning(self) -> bool:
        return self._directory_scan_thread is not None

    @Property(int, notify=scanSummaryChanged)
    def scanTotalCount(self) -> int:
        return self._scan_total_count

    @Property(int, notify=scanSummaryChanged)
    def scanAddedCount(self) -> int:
        return self._scan_added_count

    @Property(int, notify=scanSummaryChanged)
    def scanDuplicateCount(self) -> int:
        return self._scan_duplicate_count

    @Property(int, notify=scanSummaryChanged)
    def scanUnsupportedCount(self) -> int:
        return self._scan_unsupported_count

    @Property(str, notify=scanSummaryChanged)
    def scanStatusLabel(self) -> str:
        return self._scan_status_label

    @Property(bool, notify=scanSummaryChanged)
    def scanWasCancelled(self) -> bool:
        return self._scan_was_cancelled

    @Property(str, notify=monitoringChanged)
    def monitoringStatus(self) -> str:
        return "监听中" if self.isMonitoring else "未监听"

    @Property(bool, notify=busyChanged)
    def isQueuePreparing(self) -> bool:
        """Whether any queued file is still being read or validated.

        ``QueuePrepareThread`` deliberately stays alive between batches so it
        can prepare newly queued files.  Its idle lifetime must not be treated
        as active work, otherwise a completed preparation phase permanently
        disables batch conversion.
        """
        return watcher.has_preparing_tasks()

    @Property(bool, notify=busyChanged)
    def hasBackgroundTask(self) -> bool:
        return self.isQueuePreparing or any(
            self._is_thread_running(thread)
            for thread in (
                self._convert_thread,
                self._scan_thread,
                self._retry_thread,
                self._directory_scan_thread,
            )
        )

    @Property(str, notify=backgroundTaskLabelChanged)
    def backgroundTaskLabel(self) -> str:
        if self._is_thread_running(self._convert_thread):
            return "转换中"
        if self._is_thread_running(self._scan_thread):
            return "扫描中"
        if self._is_thread_running(self._directory_scan_thread):
            return "扫描目录中"
        if self._is_thread_running(self._retry_thread):
            return "重试中"
        if self.isQueuePreparing:
            return "读取验证中"
        return self._background_task_label

    @Property(str, notify=lastOperationChanged)
    def lastOperation(self) -> str:
        return self._last_operation

    @Property(str, notify=errorSummaryChanged)
    def errorSummary(self) -> str:
        return self._error_summary

    @Slot()
    def refresh_queue(self) -> None:
        self._task_queue_model.manualRefresh()
        self._set_last_operation(
            f"已手动刷新只读队列快照 · {self._task_queue_model.lastRefreshTime}"
        )

    @Slot()
    def choose_input_files(self) -> None:
        if not self.allows_capability(QUEUE_MUTATION):
            self._capability_blocked(QUEUE_MUTATION)
            return
        file_paths, _ = QFileDialog.getOpenFileNames(
            None,
            "添加音频文件到任务队列",
            "",
            "音频文件 (*.*)",
        )
        if not file_paths:
            self._set_last_operation("已取消添加文件")
            return
        self.enqueue_files(file_paths)

    @Slot("QVariantList")
    def enqueue_files(self, file_paths: object) -> None:
        if not self.allows_capability(QUEUE_MUTATION):
            self._capability_blocked(QUEUE_MUTATION)
            return
        try:
            paths = [str(path) for path in list(file_paths or []) if str(path)]
        except TypeError:
            paths = []
        if not paths:
            self._set_last_operation("没有可加入任务队列的文件")
            return

        summary = _enqueue_paths_to_watcher(
            paths,
            config_data=load_config(),
            source="qml_file",
            request_generation=self._next_scan_generation(),
        )
        self._finish_enqueue_summary(summary, label="文件导入")

    @Slot()
    def choose_scan_folder(self) -> None:
        if not self.canScanDirectories:
            self._capability_blocked(
                SCAN_PREVIEW
                if not self.allows_capability(SCAN_PREVIEW)
                else QUEUE_MUTATION
            )
            return
        folder = QFileDialog.getExistingDirectory(
            None,
            "选择要扫描并加入任务队列的目录",
            "",
        )
        if not folder:
            self._set_last_operation("已取消扫描目录")
            return
        self.scan_folders([str(folder)])

    @Slot(str)
    def scan_folder(self, folder_path: str) -> None:
        self.scan_folders([folder_path])

    @Slot("QVariantList")
    def scan_folders(self, folder_paths: object) -> None:
        if not self.allows_capability(SCAN_PREVIEW):
            self._capability_blocked(SCAN_PREVIEW)
            return
        if not self.allows_capability(QUEUE_MUTATION):
            self._capability_blocked(QUEUE_MUTATION)
            return
        if self.isDirectoryScanning:
            self._set_last_operation("目录扫描正在进行；请先等待完成或取消")
            return

        try:
            paths = [
                os.path.abspath(os.path.normpath(str(path)))
                for path in list(folder_paths or [])
                if str(path) and os.path.isdir(str(path))
            ]
        except TypeError:
            paths = []
        paths = list(dict.fromkeys(paths))
        if not paths:
            self._set_error("没有可扫描的本地目录")
            return

        self._scan_total_count = 0
        self._scan_added_count = 0
        self._scan_duplicate_count = 0
        self._scan_unsupported_count = 0
        self._scan_status_label = "扫描中"
        self._scan_was_cancelled = False
        generation = self._next_scan_generation()
        self._directory_scan_thread = DirectoryScanThread(
            paths,
            load_config(),
            generation,
            self,
        )
        self._directory_scan_thread.scanProgress.connect(
            self._on_directory_scan_progress
        )
        self._directory_scan_thread.scanFinished.connect(
            self._on_directory_scan_finished
        )
        self._directory_scan_thread.finished.connect(
            self._on_directory_scan_thread_stopped
        )
        self._directory_scan_thread.start()
        self._set_last_operation(
            f"开始后台扫描 {len(paths)} 个目录；支持文件将直接加入统一任务队列。"
        )
        self.scanSummaryChanged.emit()
        self._emit_runtime_state()

    @Slot()
    def cancel_directory_scan(self) -> None:
        if not self.isDirectoryScanning or self._directory_scan_thread is None:
            self._set_last_operation("当前没有正在运行的目录扫描")
            return
        self._directory_scan_thread.stop()
        self._scan_status_label = "正在取消"
        self._scan_was_cancelled = True
        self.scanSummaryChanged.emit()
        self._set_last_operation("已请求取消扫描；已成功加入队列的任务会保留。")

    @Slot("QVariantList")
    def enqueue_dropped_items(self, values: object) -> None:
        if not self.allows_capability(QUEUE_MUTATION):
            self._capability_blocked(QUEUE_MUTATION)
            return
        paths, skipped_reasons = extract_local_drop_paths(values)
        file_paths = [path for path in paths if os.path.isfile(path)]
        folder_paths = [path for path in paths if os.path.isdir(path)]
        missing_count = len(paths) - len(file_paths) - len(folder_paths)

        added_count = 0
        duplicate_count = 0
        unsupported_count = missing_count + len(skipped_reasons)
        if file_paths:
            summary = _enqueue_paths_to_watcher(
                file_paths,
                config_data=load_config(),
                source="qml_drop",
                request_generation=self._next_scan_generation(),
            )
            added_count = int(summary["added_count"])
            duplicate_count = int(summary["duplicate_count"])
            unsupported_count += int(summary["unsupported_count"])
            if added_count:
                self._start_prepare_thread()
                self._task_queue_model.manualRefresh()

        if folder_paths:
            if self.canScanDirectories and not self.isDirectoryScanning:
                self.scan_folders(folder_paths)
            elif self.isDirectoryScanning:
                self._set_last_operation(
                    "已有目录扫描正在进行；拖入的文件已处理，新增目录暂未扫描。"
                )
            else:
                unsupported_count += len(folder_paths)

        if not folder_paths:
            self._set_last_operation(
                f"拖入处理完成：新增 {added_count} 项，重复跳过 {duplicate_count} 项，"
                f"不支持或无效 {unsupported_count} 项；不会自动开始转换。"
            )
        self._emit_runtime_state()

    @Slot()
    def start_monitor(self) -> None:
        if not self.allows_capability(WATCHER_CONTROL):
            self._capability_blocked(WATCHER_CONTROL)
            return
        if not self.allows_capability(QUEUE_MUTATION):
            self._capability_blocked(QUEUE_MUTATION)
            return
        if not self._confirm_live_operation("开始监听", "确定要启动监听吗？监听到的文件只会加入任务队列，不会自动转换。"):
            return

        if self.isMonitoring:
            self._set_last_operation("监听器已在运行")
            return

        watch_folder = get_watch_folder()
        if not is_valid_watch_folder(watch_folder):
            self._set_error(f"监听目录不存在，无法启动监听: {watch_folder}")
            return

        self._watcher_thread = WatcherThread(watch_folder, self)
        self._watcher_thread.finished.connect(self._on_watcher_finished)
        self._watcher_thread.start()
        self._start_prepare_thread()
        self._set_last_operation("监听器已启动")
        self._emit_runtime_state()

    @Slot()
    def stop_monitor(self) -> None:
        if not self.allows_capability(WATCHER_CONTROL):
            self._capability_blocked(WATCHER_CONTROL)
            return
        if not self._confirm_live_operation("停止监听", "确定要停止监听吗？"):
            return

        if not self.isMonitoring:
            self._set_last_operation("监听器未在运行")
            return

        self._set_last_operation("正在停止监听...")
        self._stop_thread(self._watcher_thread)
        self._watcher_thread = None
        self._set_last_operation("监听器已停止")
        self._emit_runtime_state()

    @Slot()
    def scan_existing_files(self) -> None:
        if not self.allows_capability(QUEUE_MUTATION):
            self._capability_blocked(QUEUE_MUTATION)
            return
        if not self._confirm_live_operation("扫描已有文件", "确定要扫描已有文件并修改 watcher 队列吗？"):
            return

        if self._is_thread_running(self._scan_thread):
            self._set_last_operation("已有文件扫描正在进行")
            return

        watch_folder = get_watch_folder()
        if not is_valid_watch_folder(watch_folder):
            self._set_error(f"监听目录不存在，无法扫描已有文件: {watch_folder}")
            return

        self._start_prepare_thread()
        self._scan_thread = ScanThread(watch_folder, self)
        self._scan_thread.scanProgress.connect(self._on_scan_progress)
        self._scan_thread.scanFinished.connect(self._on_scan_finished)
        self._scan_thread.finished.connect(self._on_scan_thread_stopped)
        self._scan_thread.start()
        self._set_last_operation("开始扫描已有文件并快速入队...")
        self._emit_runtime_state()

    @Slot()
    def start_convert(self) -> None:
        if not self.allows_capability(BATCH_CONVERT):
            self._capability_blocked(BATCH_CONVERT)
            return

        if self._is_thread_running(self._convert_thread):
            self._set_last_operation("已有转换任务正在进行")
            return

        tasks = watcher.get_convertible_tasks()
        if not tasks:
            if watcher.has_preparing_tasks():
                self._set_last_operation(
                    "当前没有参与本轮转换的可用任务，部分文件仍在读取验证中"
                )
            else:
                self._set_last_operation("当前没有参与本轮转换的可用任务")
            return
        invalid_task = self._first_task_with_invalid_output(tasks)
        if invalid_task:
            self._set_error(
                f"任务没有有效输出目录：{invalid_task.get('filename') or invalid_task.get('path')}"
            )
            return
        if not self._confirm_live_operation(
            "开始转换",
            f"确定要转换 {len(tasks)} 个已启用的等待任务吗？",
        ):
            return

        self._start_convert_thread(None, "开始转换全部已启用任务...")

    @Slot(str)
    def start_convert_item(self, file_path: str) -> None:
        if not self.allows_capability(BATCH_CONVERT):
            self._capability_blocked(BATCH_CONVERT)
            return
        selected_path = os.path.abspath(os.path.normpath(str(file_path or "")))
        task = self._find_task(selected_path)
        if task is None:
            self._set_error("任务不存在，无法转换此文件。")
            return
        if task.get("status") != watcher.WAITING_STATUS:
            self._set_last_operation("该任务当前不能转换；请等待读取验证完成或检查任务状态。")
            return
        if self._is_thread_running(self._convert_thread):
            self._set_last_operation("已有转换任务正在进行，不能重复启动。")
            return

        output_directory = self._effective_output_directory(task)
        if not output_directory or not os.path.isdir(output_directory):
            self._set_error("没有有效输出目录；请先在设置页保存可用的输出目录。")
            return
        if not self._confirm_live_operation(
            "转换此文件",
            f"确定只转换当前任务吗？\n{task.get('filename') or selected_path}",
        ):
            return

        self._start_convert_thread(
            {selected_path},
            f"开始转换此文件：{task.get('filename') or os.path.basename(selected_path)}",
            include_disabled=True,
        )

    @Slot("QVariantList")
    def start_convert_selected(self, file_paths: object) -> None:
        if not self.allows_capability(BATCH_CONVERT):
            self._capability_blocked(BATCH_CONVERT)
            return
        if self._is_thread_running(self._convert_thread):
            self._set_last_operation("已有转换任务正在进行，不能重复启动。")
            return

        selected_paths = self._normalize_task_paths(file_paths)
        if not selected_paths:
            self._set_last_operation("请先在任务队列中选择要转换的任务。")
            return
        tasks = [
            task
            for task in watcher.get_convertible_tasks()
            if os.path.normcase(task["path"]) in selected_paths
        ]
        if not tasks:
            self._set_last_operation("选中任务中没有已启用且允许转换的任务。")
            return
        invalid_task = self._first_task_with_invalid_output(tasks)
        if invalid_task:
            self._set_error(
                f"任务没有有效输出目录：{invalid_task.get('filename') or invalid_task.get('path')}"
            )
            return
        if not self._confirm_live_operation(
            "转换选中文件",
            f"确定只转换当前选中的 {len(tasks)} 个可用任务吗？",
        ):
            return

        self._start_convert_thread(
            {task["path"] for task in tasks},
            f"开始转换 {len(tasks)} 个选中任务...",
        )

    @Slot()
    def cancel_current_task(self) -> None:
        if not self.allows_capability(BATCH_CONVERT):
            self._capability_blocked(BATCH_CONVERT)
            return
        if not self._is_thread_running(self._convert_thread):
            self._set_last_operation("当前没有正在运行的转换任务")
            return
        self._set_last_operation("正在取消当前转换任务并回收 FFmpeg 子进程...")
        self._stop_thread(self._convert_thread)
        self._task_queue_model.manualRefresh()
        self._set_last_operation("已请求取消当前转换；后续等待任务保持在队列中")
        self._emit_runtime_state()

    @Slot()
    def stop_after_current_task(self) -> None:
        if not self.allows_capability(BATCH_CONVERT):
            self._capability_blocked(BATCH_CONVERT)
            return
        if not self._is_thread_running(self._convert_thread):
            self._set_last_operation("当前没有运行中的转换任务")
            return
        self._convert_thread.stop_after_current()
        self._set_last_operation("将在当前任务结束后停止本轮队列；后续等待任务会保留。")

    @Slot()
    def convert_to_placeholder(self) -> None:
        self._set_last_operation("请先在任务队列中选择文件，再使用“转换到…”")

    @Slot()
    def apply_target_format_placeholder(self) -> None:
        self._capability_blocked(QUEUE_MUTATION)

    @Slot()
    def clear_terminal_items(self) -> None:
        if not self.allows_capability(QUEUE_MUTATION):
            self._capability_blocked(QUEUE_MUTATION)
            return
        if not self._confirm_live_operation("清除队列记录", "确定要清除已完成/失败的 watcher 队列记录吗？"):
            return

        removed_count = watcher.clear_terminal_pending_files()
        self._task_queue_model.refresh()
        if removed_count > 0:
            self._set_last_operation(f"已清除 {removed_count} 条已完成/失败记录")
        else:
            self._set_last_operation("当前没有可清除的已完成/失败记录")

    @Slot()
    def retry_failed_items(self) -> None:
        if not self.allows_capability(QUEUE_MUTATION):
            self._capability_blocked(QUEUE_MUTATION)
            return
        if not self._confirm_live_operation("重试失败条目", "确定要重新入队失败条目并修改 watcher 队列吗？"):
            return

        if self._is_thread_running(self._retry_thread):
            self._set_last_operation("已有失败重试任务正在进行")
            return

        retryable_tasks = watcher.get_retryable_tasks()
        if not retryable_tasks:
            self._set_last_operation("当前没有可重试的失败条目")
            return

        retry_paths = [task["path"] for task in retryable_tasks]
        self._start_prepare_thread()
        self._retry_thread = RetryThread(retry_paths, self)
        self._retry_thread.retryFinished.connect(self._on_retry_finished)
        self._retry_thread.finished.connect(self._on_retry_thread_stopped)
        self._retry_thread.start()
        self._set_last_operation(f"开始重试 {len(retry_paths)} 个失败条目...")
        self._emit_runtime_state()

    @Slot(str)
    def retry_failed_item(self, file_path: str) -> None:
        self.retry_failed_tasks([file_path])

    @Slot("QVariantList")
    def retry_failed_tasks(self, file_paths: object) -> None:
        if not self.allows_capability(QUEUE_MUTATION):
            self._capability_blocked(QUEUE_MUTATION)
            return
        selected_paths = self._normalize_task_paths(file_paths)
        retryable = watcher.get_retryable_tasks(selected_paths)
        if not retryable:
            self._set_last_operation("选中任务中没有可重试的失败任务")
            return
        if self._is_thread_running(self._retry_thread):
            self._set_last_operation("已有失败重试任务正在进行")
            return
        retry_paths = [task["path"] for task in retryable]
        self._retry_thread = RetryThread(retry_paths, self)
        self._retry_thread.retryFinished.connect(self._on_retry_finished)
        self._retry_thread.finished.connect(self._on_retry_thread_stopped)
        self._retry_thread.start()
        self._set_last_operation(f"已开始重新验证 {len(retry_paths)} 个失败条目")
        self._emit_runtime_state()

    @Slot(str)
    def remove_pending_item(self, file_path: str) -> None:
        self.remove_pending_items([file_path])

    @Slot("QVariantList")
    def remove_pending_items(self, file_paths: object) -> None:
        if not self.allows_capability(QUEUE_MUTATION):
            self._capability_blocked(QUEUE_MUTATION)
            return
        selected_paths = self._normalize_task_paths(file_paths)
        if not selected_paths:
            self._set_last_operation("请先选择要移除的任务")
            return
        tasks = [
            task
            for task in watcher.get_task_snapshots()
            if os.path.normcase(task["path"]) in selected_paths
        ]
        removable = [
            task
            for task in tasks
            if task.get("status") not in (
                watcher.READING_STATUS,
                watcher.PROCESSING_STATUS,
            )
        ]
        if not removable:
            self._set_error(
                "选中任务均在运行中；请先取消当前转换或等待读取验证结束。"
            )
            return
        removed_count = sum(
            1
            for task in removable
            if watcher.remove_pending_file_by_path(task["path"])
        )
        if removed_count:
            self._task_queue_model.manualRefresh()
            self._set_last_operation(
                f"已从任务队列移除 {removed_count} 个任务；未删除源文件或输出文件"
            )
        else:
            self._set_error("移除任务失败，条目可能已被其他操作更新。")

    @Slot(str)
    def open_task_output(self, file_path: str) -> None:
        task = self._find_task(file_path)
        if task is None:
            self._set_error("任务不存在，无法定位输出。")
            return
        output_path = str(task.get("output_path") or "")
        if output_path:
            self._open_folder(os.path.dirname(output_path), "任务输出目录")
            return
        output_root = self._effective_output_directory(task)
        self._open_folder(output_root, "输出目录")

    @Slot(str)
    def open_task_source(self, file_path: str) -> None:
        task = self._find_task(file_path)
        if task is None:
            self._set_error("任务不存在，无法定位源文件。")
            return
        self._open_folder(os.path.dirname(task["path"]), "源文件位置")

    @Slot()
    def choose_watch_folder(self) -> None:
        self._set_last_operation("请在“设置”页面修改监听目录草稿，并点击“保存设置”确认写入。")

    @Slot()
    def choose_output_folder(self) -> None:
        self._set_last_operation("请在“设置”页面修改输出目录草稿，并点击“保存设置”确认写入。")

    @Slot()
    def open_watch_folder(self) -> None:
        self._open_folder(get_watch_folder(), "监听目录")

    @Slot()
    def open_output_folder(self) -> None:
        self._open_folder(get_output_folder(), "输出目录")

    @Slot(str)
    def set_global_target_format(self, target_format: str) -> None:
        self._set_last_operation("默认输出格式需在“设置”页面作为草稿修改并显式保存。")

    @Slot(str, str)
    def set_file_target_format(self, file_path: str, target_format: str) -> None:
        self.set_tasks_target_format([file_path], target_format)

    @Slot("QVariantList", str)
    def set_tasks_target_format(
        self,
        file_paths: object,
        target_format: str,
    ) -> None:
        if not self.allows_capability(QUEUE_MUTATION):
            self._capability_blocked(QUEUE_MUTATION)
            return

        normalized = normalize_target_format(target_format) if target_format else None
        if target_format and normalized is None:
            self._set_error(f"不支持的任务目标格式: {target_format}")
            return

        selected_paths = self._normalize_task_paths(file_paths)
        updated_count = sum(
            1
            for file_path in selected_paths
            if watcher.set_pending_file_target_format(file_path, normalized)
        )
        if updated_count:
            self._task_queue_model.refresh()
            if normalized:
                self._set_last_operation(
                    f"已将 {updated_count} 个任务单独设置为 "
                    f"{get_target_label(normalized)}"
                )
            else:
                self._set_last_operation(
                    f"已将 {updated_count} 个任务恢复为跟随全局格式"
                )
        else:
            self._set_last_operation("没有更新目标格式；任务可能正在处理或已完成")

    @Slot(str, bool)
    def set_task_enabled_for_run(self, file_path: str, enabled: bool) -> None:
        self.set_tasks_enabled_for_run([file_path], enabled)

    @Slot("QVariantList", bool)
    def set_tasks_enabled_for_run(
        self,
        file_paths: object,
        enabled: bool,
    ) -> None:
        if not self.allows_capability(QUEUE_MUTATION):
            self._capability_blocked(QUEUE_MUTATION)
            return
        selected_paths = self._normalize_task_paths(file_paths)
        updated_count = sum(
            1
            for file_path in selected_paths
            if watcher.set_pending_file_enabled_for_run(file_path, enabled)
        )
        if updated_count:
            self._task_queue_model.manualRefresh()
            self._set_last_operation(
                f"已将 {updated_count} 个任务设为"
                f"{'参与本轮转换' if enabled else '本轮跳过'}"
            )
        else:
            self._set_last_operation("没有更新参与策略；运行中或已完成任务不可修改")

    @Slot("QVariantList")
    def reset_tasks_output_directory(self, file_paths: object) -> None:
        self._set_tasks_output_directory(file_paths, "")

    @Slot("QVariantList")
    def choose_tasks_output_directory(self, file_paths: object) -> None:
        self._choose_tasks_output_directory(file_paths, start_after=False)

    @Slot("QVariantList")
    def convert_selected_to_directory(self, file_paths: object) -> None:
        self._choose_tasks_output_directory(file_paths, start_after=True)

    @Slot(int)
    def report_drop_placeholder(self, dropped_count: int) -> None:
        self._set_last_operation(
            f"已检测到 {dropped_count} 个拖入项目；QML 手动入队将在后续阶段接入"
        )

    # Legacy Python Signal(object, str, int) handoff; this is not a QML
    # JavaScript-array entry point and must retain PyObject compatibility.
    @Slot(object, str, int)
    def add_scan_candidates(
        self,
        file_paths: object,
        source_root: str,
        request_generation: int,
    ) -> None:
        if not self.allows_capability(QUEUE_MUTATION):
            self._capability_blocked(QUEUE_MUTATION)
            return

        try:
            candidates = [str(path) for path in list(file_paths or []) if str(path)]
        except TypeError:
            candidates = []
        if not candidates:
            self._set_last_operation("没有可交接的扫描结果")
            return

        config_data = load_config()
        output_directory = str(config_data.get("output_folder") or "")
        target_format = normalize_target_format(config_data.get("target_format"))
        create_subfolder = bool(config_data.get("create_format_subfolder", True))
        added_paths: list[str] = []
        duplicate_count = 0
        normalized_root = os.path.abspath(os.path.normpath(source_root)) if source_root else ""
        for candidate in candidates:
            normalized_path = os.path.abspath(os.path.normpath(candidate))
            try:
                relative_path = os.path.relpath(normalized_path, normalized_root)
            except ValueError:
                relative_path = os.path.basename(normalized_path)
            snapshot = {
                "target_format": target_format,
                "output_directory": output_directory,
                "relative_output_path": relative_path,
                "preserve_relative_structure": bool(config_data.get("preserve_relative_structure", False)),
                "source_action": "保留源文件",
                "request_generation": int(request_generation),
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source_root": normalized_root,
                "source": "qml_scan",
                "create_format_subfolder": create_subfolder,
            }
            if watcher.handle_detected_file(
                normalized_path,
                source="qml_scan",
                task_snapshot=snapshot,
            ):
                added_paths.append(normalized_path)
            else:
                duplicate_count += 1

        if added_paths:
            self._start_prepare_thread()
            self._task_queue_model.manualRefresh()
            self.scanQueueAccepted.emit(added_paths)
        self._set_last_operation(
            f"扫描结果交接完成：新增 {len(added_paths)} 项，重复或不可加入 {duplicate_count} 项；不会自动开始转换。"
        )
        self._emit_runtime_state()

    @Slot()
    def notify_settings_saved(self) -> None:
        self.watchFolderChanged.emit()
        self.outputFolderChanged.emit()
        self.globalTargetFormatChanged.emit()
        self._task_queue_model.manualRefresh()
        self._set_last_operation("已读取已保存的 QML 转码设置；仅后续新任务会使用新的参数快照。")

    @Slot()
    def shutdown(self) -> None:
        self._state_timer.stop()
        self._stop_thread(self._directory_scan_thread)
        self._stop_thread(self._scan_thread)
        self._stop_thread(self._retry_thread)
        self._stop_thread(self._convert_thread)
        self._stop_thread(self._watcher_thread)
        self._stop_thread(self._prepare_thread)
        self._scan_thread = None
        self._retry_thread = None
        self._convert_thread = None
        self._watcher_thread = None
        self._prepare_thread = None
        self._directory_scan_thread = None

    def _start_convert_thread(
        self,
        selected_paths: set[str] | None,
        message: str,
        *,
        include_disabled: bool = False,
    ) -> None:
        self._convert_thread = ConvertThread(
            get_target_format(),
            output_root_override=get_output_folder(),
            create_format_subfolder=get_create_format_subfolder(),
            selected_paths=selected_paths,
            include_disabled=include_disabled,
            parent=self,
        )
        self._convert_thread.finished.connect(self._on_convert_finished)
        self._convert_thread.taskUpdated.connect(self._on_convert_task_updated)
        self._convert_thread.start()
        self._set_last_operation(message)
        self._emit_runtime_state()

    def _normalize_task_paths(self, values: object) -> set[str]:
        try:
            raw_values = list(values or [])
        except TypeError:
            raw_values = []
        normalized: set[str] = set()
        for value in raw_values:
            text = str(value or "").strip()
            if not text:
                continue
            normalized.add(
                os.path.normcase(os.path.abspath(os.path.normpath(text)))
            )
        return normalized

    def _find_task(self, file_path: str) -> dict | None:
        normalized = os.path.normcase(
            os.path.abspath(os.path.normpath(str(file_path or "")))
        )
        return next(
            (
                task
                for task in watcher.get_task_snapshots()
                if os.path.normcase(task["path"]) == normalized
            ),
            None,
        )

    def _effective_output_directory(self, task: dict) -> str:
        return str(
            task.get("output_directory_override")
            or get_output_folder()
            or ""
        )

    def _first_task_with_invalid_output(self, tasks: list[dict]) -> dict | None:
        return next(
            (
                task
                for task in tasks
                if not os.path.isdir(self._effective_output_directory(task))
            ),
            None,
        )

    def _set_tasks_output_directory(
        self,
        file_paths: object,
        output_directory: str,
    ) -> list[str]:
        if not self.allows_capability(QUEUE_MUTATION):
            self._capability_blocked(QUEUE_MUTATION)
            return []
        selected_paths = self._normalize_task_paths(file_paths)
        updated_paths = [
            file_path
            for file_path in selected_paths
            if watcher.set_pending_file_output_directory_override(
                file_path,
                output_directory,
            )
        ]
        if updated_paths:
            self._task_queue_model.manualRefresh()
            if output_directory:
                self._set_last_operation(
                    f"已为 {len(updated_paths)} 个任务设置本轮输出目录："
                    f"{os.path.normpath(os.path.abspath(output_directory))}"
                )
            else:
                self._set_last_operation(
                    f"已将 {len(updated_paths)} 个任务恢复为使用默认输出目录"
                )
        else:
            self._set_last_operation(
                "没有更新输出目录；任务可能正在读取、处理或已完成"
            )
        return updated_paths

    def _choose_tasks_output_directory(
        self,
        file_paths: object,
        *,
        start_after: bool,
    ) -> None:
        if not self.allows_capability(QUEUE_MUTATION):
            self._capability_blocked(QUEUE_MUTATION)
            return
        if start_after and not self.allows_capability(BATCH_CONVERT):
            self._capability_blocked(BATCH_CONVERT)
            return
        selected_paths = self._normalize_task_paths(file_paths)
        if not selected_paths:
            self._set_last_operation("请先在任务队列中选择任务")
            return
        folder = QFileDialog.getExistingDirectory(
            None,
            "选择本轮任务输出目录",
            get_output_folder(),
        )
        if not folder:
            self._set_last_operation("已取消选择本轮输出目录")
            return
        updated_paths = self._set_tasks_output_directory(
            selected_paths,
            folder,
        )
        if start_after and updated_paths:
            self.start_convert_selected(updated_paths)

    def _finish_enqueue_summary(self, summary: dict[str, object], *, label: str) -> None:
        added_count = int(summary.get("added_count") or 0)
        duplicate_count = int(summary.get("duplicate_count") or 0)
        unsupported_count = int(summary.get("unsupported_count") or 0)
        if added_count:
            self._start_prepare_thread()
            self._task_queue_model.manualRefresh()
        self._set_last_operation(
            f"{label}完成：新增 {added_count} 项，重复跳过 {duplicate_count} 项，"
            f"不支持或无效 {unsupported_count} 项；不会自动开始转换。"
        )
        self._emit_runtime_state()

    def _next_scan_generation(self) -> int:
        self._scan_request_generation += 1
        return self._scan_request_generation

    def _start_prepare_thread(self) -> None:
        if self._is_thread_running(self._prepare_thread):
            return

        self._prepare_thread = QueuePrepareThread(self)
        self._prepare_thread.finished.connect(self._on_prepare_thread_stopped)
        self._prepare_thread.start()
        self._emit_runtime_state()

    def _on_watcher_finished(self) -> None:
        self._watcher_thread = None
        self._emit_runtime_state()

    def _on_convert_task_updated(self, file_path: str, stage: str) -> None:
        self._task_queue_model.manualRefresh()
        filename = os.path.basename(str(file_path or "")) or "当前任务"
        self._set_last_operation(f"{filename}：{stage}")
        self._emit_runtime_state()

    def _on_convert_finished(self) -> None:
        self._convert_thread = None
        self._task_queue_model.refresh()
        self._set_last_operation("本轮转换任务已结束")
        self._emit_runtime_state()

    def _on_directory_scan_progress(self, summary: dict) -> None:
        self._scan_total_count = int(summary.get("total_count") or 0)
        self._scan_added_count = int(summary.get("added_count") or 0)
        self._scan_duplicate_count = int(summary.get("duplicate_count") or 0)
        self._scan_unsupported_count = int(summary.get("unsupported_count") or 0)
        self._scan_status_label = "正在取消" if self._scan_was_cancelled else "扫描中"
        self.scanSummaryChanged.emit()
        self._task_queue_model.manualRefresh()

    def _on_directory_scan_finished(self, summary: dict) -> None:
        self._scan_total_count = int(summary.get("total_count") or 0)
        self._scan_added_count = int(summary.get("added_count") or 0)
        self._scan_duplicate_count = int(summary.get("duplicate_count") or 0)
        self._scan_unsupported_count = int(summary.get("unsupported_count") or 0)
        self._scan_was_cancelled = bool(summary.get("cancelled"))
        error = str(summary.get("error") or "")
        if self._scan_was_cancelled:
            self._scan_status_label = "已取消"
        elif error:
            self._scan_status_label = "扫描失败"
        else:
            self._scan_status_label = "已完成"

        if self._scan_added_count:
            self._start_prepare_thread()
        self._task_queue_model.manualRefresh()
        self._set_last_operation(
            f"目录扫描{self._scan_status_label}：扫描 {self._scan_total_count} 个文件，"
            f"新增 {self._scan_added_count} 项，重复跳过 {self._scan_duplicate_count} 项，"
            f"不支持格式 {self._scan_unsupported_count} 项；不会自动开始转换。"
        )
        if error and not self._scan_was_cancelled:
            self._error_summary = error
            self.errorSummaryChanged.emit()
        self.scanSummaryChanged.emit()
        self._emit_runtime_state()

    def _on_directory_scan_thread_stopped(self) -> None:
        self._directory_scan_thread = None
        self.scanSummaryChanged.emit()
        self._emit_runtime_state()

    def _on_scan_progress(self, summary: dict) -> None:
        self._set_last_operation(
            "扫描中: "
            f"{summary.get('scanned_count', 0)}/{summary.get('total_count', 0)} - "
            f"{summary.get('current_file', '')}"
        )

    def _on_scan_finished(self, summary: dict) -> None:
        self._task_queue_model.refresh()
        self._start_prepare_thread()
        self._set_last_operation(
            "已有文件扫描结束: "
            f"扫描 {summary.get('scanned_count', 0)}/{summary.get('total_count', 0)} 个，"
            f"新增 {summary.get('queued_count', 0)} 个，"
            f"跳过 {summary.get('skipped_count', 0)} 个；后台读取/验证继续"
        )

    def _on_scan_thread_stopped(self) -> None:
        self._scan_thread = None
        self._emit_runtime_state()

    def _on_retry_finished(self, summary: dict) -> None:
        self._task_queue_model.refresh()
        self._start_prepare_thread()
        self._set_last_operation(
            "失败条目重试结束: "
            f"尝试 {summary.get('attempted_count', 0)} 个，"
            f"重新入列 {summary.get('requeued_count', 0)} 个，"
            f"跳过 {summary.get('skipped_count', 0)} 个"
        )

    def _on_retry_thread_stopped(self) -> None:
        self._retry_thread = None
        self._emit_runtime_state()

    def _on_prepare_thread_stopped(self) -> None:
        self._prepare_thread = None
        self._emit_runtime_state()

    def _set_last_operation(self, message: str) -> None:
        self._last_operation = message
        self._error_summary = ""
        self.lastOperationChanged.emit()
        self.errorSummaryChanged.emit()
        self.set_status_message(message)

    def _set_error(self, message: str) -> None:
        self._error_summary = message
        self._last_operation = message
        self.errorSummaryChanged.emit()
        self.lastOperationChanged.emit()
        self.errorOccurred.emit(message)
        self.set_status_message(message)

    def _preview_blocked(self, message: str) -> None:
        self._set_last_operation(message)

    def _capability_blocked(self, capability: str) -> None:
        self._set_last_operation(self.block_capability(capability))

    def _confirm_live_operation(self, title: str, message: str) -> bool:
        result = QMessageBox.question(
            None,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result != QMessageBox.StandardButton.Yes:
            self._set_last_operation(f"已取消操作：{title}")
            return False
        return True

    def _open_folder(self, folder_path: str, label: str) -> None:
        if not folder_path or not os.path.isdir(folder_path):
            self._set_error(f"{label}不存在，无法打开: {folder_path or '未设置'}")
            return

        try:
            os.startfile(folder_path)
            self._set_last_operation(f"已打开{label}")
        except Exception as exc:
            self._set_error(f"打开{label}失败: {exc}")

    def _emit_runtime_state(self) -> None:
        self.monitoringChanged.emit()
        self.busyChanged.emit()
        self.backgroundTaskLabelChanged.emit()

    def _is_thread_running(self, thread: QThread | None) -> bool:
        return thread is not None and thread.isRunning()

    def _stop_thread(self, thread: QThread | None) -> None:
        if thread is None:
            return

        if hasattr(thread, "stop"):
            thread.stop()
        elif hasattr(thread, "requestInterruption"):
            thread.requestInterruption()

        thread.wait(5000)
