from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import (
    QAbstractListModel,
    QDateTime,
    QModelIndex,
    Property,
    QTimer,
    Qt,
    Signal,
    Slot,
)

import watcher
from config import (
    get_create_format_subfolder,
    get_output_folder,
    get_target_format,
)
from formats import (
    DEFAULT_TARGET_FORMAT,
    get_target_extension,
    get_target_label,
    is_supported_editor_audio_file,
    normalize_target_format,
)
from ui_next.bridge.capabilities import (
    BATCH_CONVERT,
    QUEUE_MUTATION,
    WATCHER_CONTROL,
    CapabilityGate,
)


class TaskQueueModel(QAbstractListModel):
    filenameRole = Qt.ItemDataRole.UserRole + 1
    formatRole = Qt.ItemDataRole.UserRole + 2
    targetFormatRole = Qt.ItemDataRole.UserRole + 3
    targetFormatLabelRole = Qt.ItemDataRole.UserRole + 4
    statusRole = Qt.ItemDataRole.UserRole + 5
    statusLabelRole = Qt.ItemDataRole.UserRole + 6
    statusDetailRole = Qt.ItemDataRole.UserRole + 7
    statusColorRole = Qt.ItemDataRole.UserRole + 8
    statusToneRole = Qt.ItemDataRole.UserRole + 9
    canConvertRole = Qt.ItemDataRole.UserRole + 10
    canRetryRole = Qt.ItemDataRole.UserRole + 11
    canChangeTargetFormatRole = Qt.ItemDataRole.UserRole + 12
    pathRole = Qt.ItemDataRole.UserRole + 13
    sourceNoteRole = Qt.ItemDataRole.UserRole + 14
    stageRole = Qt.ItemDataRole.UserRole + 15
    outputPathRole = Qt.ItemDataRole.UserRole + 16
    errorSummaryRole = Qt.ItemDataRole.UserRole + 17
    canRemoveRole = Qt.ItemDataRole.UserRole + 18
    canOpenOutputRole = Qt.ItemDataRole.UserRole + 19
    enabledForRunRole = Qt.ItemDataRole.UserRole + 20
    participationLabelRole = Qt.ItemDataRole.UserRole + 21
    outputStrategyLabelRole = Qt.ItemDataRole.UserRole + 22
    outputDirectoryOverrideRole = Qt.ItemDataRole.UserRole + 23
    canChangeRunPolicyRole = Qt.ItemDataRole.UserRole + 24
    canChangeOutputDirectoryRole = Qt.ItemDataRole.UserRole + 25
    effectiveTargetFormatRole = Qt.ItemDataRole.UserRole + 26
    sameFormatWarningRole = Qt.ItemDataRole.UserRole + 27
    plannedOutputPathRole = Qt.ItemDataRole.UserRole + 28
    outputNameConflictRole = Qt.ItemDataRole.UserRole + 29
    queueWarningTextRole = Qt.ItemDataRole.UserRole + 30
    canLoadSourceRole = Qt.ItemDataRole.UserRole + 31
    sourcePlaybackDisabledReasonRole = Qt.ItemDataRole.UserRole + 32
    canLoadOutputRole = Qt.ItemDataRole.UserRole + 33
    outputPlaybackDisabledReasonRole = Qt.ItemDataRole.UserRole + 34

    countChanged = Signal()
    summaryChanged = Signal()
    lastRefreshChanged = Signal()
    errorOccurred = Signal(str)

    _ROLE_NAMES = {
        filenameRole: b"filename",
        formatRole: b"format",
        targetFormatRole: b"targetFormat",
        targetFormatLabelRole: b"targetFormatLabel",
        statusRole: b"status",
        statusLabelRole: b"statusLabel",
        statusDetailRole: b"statusDetail",
        statusColorRole: b"statusColor",
        statusToneRole: b"statusTone",
        canConvertRole: b"canConvert",
        canRetryRole: b"canRetry",
        canChangeTargetFormatRole: b"canChangeTargetFormat",
        pathRole: b"path",
        sourceNoteRole: b"sourceNote",
        stageRole: b"stage",
        outputPathRole: b"outputPath",
        errorSummaryRole: b"errorSummary",
        canRemoveRole: b"canRemove",
        canOpenOutputRole: b"canOpenOutput",
        enabledForRunRole: b"enabledForRun",
        participationLabelRole: b"participationLabel",
        outputStrategyLabelRole: b"outputStrategyLabel",
        outputDirectoryOverrideRole: b"outputDirectoryOverride",
        canChangeRunPolicyRole: b"canChangeRunPolicy",
        canChangeOutputDirectoryRole: b"canChangeOutputDirectory",
        effectiveTargetFormatRole: b"effectiveTargetFormat",
        sameFormatWarningRole: b"sameFormatWarning",
        plannedOutputPathRole: b"plannedOutputPath",
        outputNameConflictRole: b"outputNameConflict",
        queueWarningTextRole: b"queueWarningText",
        canLoadSourceRole: b"canLoadSource",
        sourcePlaybackDisabledReasonRole: b"sourcePlaybackDisabledReason",
        canLoadOutputRole: b"canLoadOutput",
        outputPlaybackDisabledReasonRole: b"outputPlaybackDisabledReason",
    }

    def __init__(
        self,
        parent=None,
        capability_gate: CapabilityGate | None = None,
        live_mode: bool | None = None,
    ) -> None:
        super().__init__(parent)
        self._capability_gate = capability_gate or CapabilityGate()
        self._tasks: list[dict] = []
        self._summary = self._build_summary([])
        self._last_signature: tuple = ()
        self._last_refresh_time = "尚未刷新"

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(
            1000
            if self._capability_gate.allows(WATCHER_CONTROL)
            else 3000
        )
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start()
        self._refresh(force=True)

    def rowCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._tasks)

    def roleNames(self) -> dict[int, bytes]:
        return dict(self._ROLE_NAMES)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() < 0 or index.row() >= len(self._tasks):
            return None

        task = self._tasks[index.row()]

        if role == self.filenameRole:
            return task.get("filename", "")
        if role == self.formatRole:
            return task.get("format", "")
        if role == self.targetFormatRole:
            if "target_format_override" in task:
                return task.get("target_format_override") or ""
            return task.get("target_format") or ""
        if role == self.targetFormatLabelRole:
            return self._format_target_display(task)
        if role == self.statusRole:
            return task.get("status", "")
        if role == self.statusLabelRole:
            return self._status_display(task).get("label", task.get("status", ""))
        if role == self.statusDetailRole:
            return self._status_display(task).get("detail", "")
        if role == self.statusColorRole:
            return self._status_display(task).get("color", "#828282")
        if role == self.statusToneRole:
            return self._status_tone(task.get("status", ""))
        if role == self.canConvertRole:
            return bool(task.get("can_convert", False))
        if role == self.canRetryRole:
            return bool(task.get("can_retry", False))
        if role == self.canChangeTargetFormatRole:
            return bool(task.get("can_change_target_format", False))
        if role == self.pathRole:
            return task.get("path", "")
        if role == self.sourceNoteRole:
            return self._source_note(task)
        if role == self.stageRole:
            return task.get("stage") or self._status_display(task).get("detail", "")
        if role == self.outputPathRole:
            return task.get("output_path", "")
        if role == self.errorSummaryRole:
            return task.get("error_summary", "")
        if role == self.canRemoveRole:
            return task.get("status") not in (
                watcher.READING_STATUS,
                watcher.PROCESSING_STATUS,
            )
        if role == self.canOpenOutputRole:
            return bool(
                task.get("output_path")
                or task.get("output_directory_override")
                or task.get("output_directory")
            )
        if role == self.enabledForRunRole:
            return bool(task.get("enabled_for_run", True))
        if role == self.participationLabelRole:
            return (
                "参与本轮转换"
                if task.get("enabled_for_run", True)
                else "本轮跳过"
            )
        if role == self.outputStrategyLabelRole:
            return (
                "指定目录"
                if task.get("output_directory_override")
                else "默认目录"
            )
        if role == self.outputDirectoryOverrideRole:
            return task.get("output_directory_override") or ""
        if role == self.canChangeRunPolicyRole:
            return bool(task.get("can_change_run_policy", False))
        if role == self.canChangeOutputDirectoryRole:
            return bool(task.get("can_change_output_directory", False))
        if role == self.effectiveTargetFormatRole:
            return task.get("_effective_target_format", "")
        if role == self.sameFormatWarningRole:
            return bool(task.get("_same_format_warning", False))
        if role == self.plannedOutputPathRole:
            return task.get("_planned_output_path", "")
        if role == self.outputNameConflictRole:
            return bool(task.get("_output_name_conflict", False))
        if role == self.queueWarningTextRole:
            return task.get("_queue_warning_text", "")
        if role == self.canLoadSourceRole:
            return not bool(self._source_playback_disabled_reason(task))
        if role == self.sourcePlaybackDisabledReasonRole:
            return self._source_playback_disabled_reason(task)
        if role == self.canLoadOutputRole:
            return not bool(self._output_playback_disabled_reason(task))
        if role == self.outputPlaybackDisabledReasonRole:
            return self._output_playback_disabled_reason(task)

        return None

    @Property(int, notify=countChanged)
    def count(self) -> int:
        return len(self._tasks)

    @Property(int, notify=summaryChanged)
    def totalCount(self) -> int:
        return self._summary["total"]

    @Property(int, notify=summaryChanged)
    def waitingCount(self) -> int:
        return self._summary["waiting"]

    @Property(int, notify=summaryChanged)
    def readingCount(self) -> int:
        return self._summary["reading"]

    @Property(int, notify=summaryChanged)
    def processingCount(self) -> int:
        return self._summary["processing"]

    @Property(int, notify=summaryChanged)
    def completedCount(self) -> int:
        return self._summary["completed"]

    @Property(int, notify=summaryChanged)
    def failedCount(self) -> int:
        return self._summary["failed"]

    @Property(int, notify=summaryChanged)
    def skippedCount(self) -> int:
        return self._summary["skipped"]

    @Property(int, notify=summaryChanged)
    def excludedCount(self) -> int:
        return self._summary["excluded"]

    @Property(int, notify=summaryChanged)
    def retryableCount(self) -> int:
        return self._summary["retryable"]

    @Property(int, notify=summaryChanged)
    def clearableCount(self) -> int:
        return self._summary["clearable"]

    @Property(bool, constant=True)
    def previewMode(self) -> bool:
        return not any(
            self._capability_gate.allows(capability)
            for capability in (WATCHER_CONTROL, QUEUE_MUTATION, BATCH_CONVERT)
        )

    @Property(bool, constant=True)
    def liveMode(self) -> bool:
        return not self.previewMode

    @Property(str, constant=True)
    def capabilitySummary(self) -> str:
        return self._capability_gate.summary

    @Property(int, constant=True)
    def refreshIntervalMs(self) -> int:
        return self._refresh_timer.interval()

    @Property(str, notify=lastRefreshChanged)
    def lastRefreshTime(self) -> str:
        return self._last_refresh_time

    @Slot()
    def refresh(self) -> None:
        self._refresh(force=False)

    @Slot()
    def manualRefresh(self) -> None:
        # Manual refresh reads immediately but still preserves signature de-dup.
        self._refresh(force=False)

    @Slot(int, result=str)
    def pathAt(self, row: int) -> str:
        if row < 0 or row >= len(self._tasks):
            return ""
        return str(self._tasks[row].get("path") or "")

    @Slot(str, result=bool)
    def containsPath(self, file_path: str) -> bool:
        identity = self._normalized_path_identity(file_path)
        return bool(identity) and any(
            self._normalized_path_identity(task.get("path")) == identity
            for task in self._tasks
        )

    @Slot(str, result="QVariantMap")
    def taskDetails(self, file_path: str) -> dict[str, object]:
        identity = self._normalized_path_identity(file_path)
        task = next(
            (
                item
                for item in self._tasks
                if self._normalized_path_identity(item.get("path")) == identity
            ),
            None,
        )
        if task is None:
            return {}

        output_directory = str(
            task.get("output_directory_override")
            or get_output_folder()
            or task.get("output_directory")
            or ""
        )
        output_strategy = (
            "指定目录"
            if task.get("output_directory_override")
            else "默认目录"
        )
        return {
            "path": str(task.get("path") or ""),
            "filename": str(task.get("filename") or ""),
            "inputFormat": str(
                task.get("source_type")
                or task.get("format")
                or ""
            ),
            "targetFormat": self._format_target_display(task),
            "status": self._status_display(task).get("label", ""),
            "stage": str(
                task.get("stage")
                or self._status_display(task).get("detail", "")
            ),
            "participation": (
                "参与本轮转换"
                if task.get("enabled_for_run", True)
                else "本轮跳过"
            ),
            "outputStrategy": output_strategy,
            "outputDirectory": output_directory,
            "errorDetails": str(task.get("error_summary") or ""),
            "outputPath": str(task.get("output_path") or ""),
            "lyricsResult": self._lyrics_result_summary(task),
            "sourceType": str(
                task.get("source_type")
                or task.get("format")
                or ""
            ),
            "sourceOrigin": self._source_note(task),
            "sourceOriginKey": str(task.get("source") or "watcher"),
        }

    def _refresh(self, force: bool = False) -> None:
        try:
            tasks = watcher.get_task_snapshots()
        except Exception as exc:
            self.errorOccurred.emit(f"刷新队列失败: {exc}")
            return

        global_settings = self._queue_derivation_settings()
        tasks = [
            self._with_queue_warnings(task, global_settings)
            for task in tasks
        ]
        tasks = self._with_queue_path_collisions(tasks)
        self._last_refresh_time = QDateTime.currentDateTime().toString("HH:mm:ss")
        self.lastRefreshChanged.emit()
        signature = self._build_signature(tasks, global_settings)
        if not force and signature == self._last_signature:
            return

        same_task_order = (
            len(tasks) == len(self._tasks)
            and all(
                self._normalized_path_identity(previous.get("path"))
                == self._normalized_path_identity(current.get("path"))
                for previous, current in zip(self._tasks, tasks)
            )
        )
        if same_task_order:
            self._tasks = tasks
            if self._tasks:
                self.dataChanged.emit(
                    self.index(0, 0),
                    self.index(len(self._tasks) - 1, 0),
                    list(self._ROLE_NAMES),
                )
        else:
            self.beginResetModel()
            self._tasks = tasks
            self.endResetModel()
        self._last_signature = signature

        self._summary = self._build_summary(self._tasks)
        if not same_task_order:
            self.countChanged.emit()
        self.summaryChanged.emit()

    def _build_signature(
        self,
        tasks: list[dict],
        global_settings: tuple[str, str, bool] | None = None,
    ) -> tuple:
        if global_settings is None:
            global_settings = self._queue_derivation_settings()
            tasks = [
                self._with_queue_warnings(task, global_settings)
                for task in tasks
            ]
            tasks = self._with_queue_path_collisions(tasks)
        return (
            global_settings,
            tuple(
                (
                    task.get("path", ""),
                    task.get("filename", ""),
                    task.get("format", ""),
                    task.get("target_format") or "",
                    task.get("target_format_override") or "",
                    bool(task.get("enabled_for_run", True)),
                    task.get("output_directory_override") or "",
                    task.get("relative_output_path") or "",
                    bool(task.get("preserve_relative_structure", False)),
                    task.get("create_format_subfolder"),
                    task.get("status", ""),
                    bool(task.get("can_convert", False)),
                    bool(task.get("can_retry", False)),
                    bool(task.get("can_change_target_format", False)),
                    bool(task.get("is_ncm_task", False)),
                    task.get("stage", ""),
                    task.get("output_path", ""),
                    task.get("error_summary", ""),
                    task.get("source_type", ""),
                    task.get("source", ""),
                    tuple(
                        sorted(
                            (
                                str(key),
                                str(value),
                            )
                            for key, value in dict(
                                task.get("lyrics_result") or {}
                            ).items()
                        )
                    ),
                    task.get("_effective_target_format", ""),
                    bool(task.get("_same_format_warning", False)),
                    task.get("_planned_output_path", ""),
                    bool(task.get("_output_name_conflict", False)),
                    task.get("_queue_warning_text", ""),
                    self._source_playback_disabled_reason(task),
                    self._output_playback_disabled_reason(task),
                )
                for task in tasks
            ),
        )

    def _queue_derivation_settings(self) -> tuple[str, str, bool]:
        return (
            normalize_target_format(
                get_target_format(),
                DEFAULT_TARGET_FORMAT,
            ),
            str(get_output_folder() or ""),
            bool(get_create_format_subfolder()),
        )

    def _with_queue_warnings(
        self,
        task: dict,
        global_settings: tuple[str, str, bool],
    ) -> dict:
        global_target_format, global_output_folder, global_create_subfolder = (
            global_settings
        )
        decorated = dict(task)
        effective_target = normalize_target_format(
            task.get("target_format_override") or global_target_format,
            global_target_format,
        )
        source_extension = Path(str(task.get("path") or "")).suffix.lower()
        target_extension = get_target_extension(effective_target).lower()
        planned_output_path = self._planned_output_path(
            task,
            effective_target,
            global_output_folder,
            global_create_subfolder,
        )
        warning_actionable = self._queue_warning_actionable(task)
        output_name_conflict = bool(
            warning_actionable
            and planned_output_path
            and Path(planned_output_path).exists()
        )
        same_format_warning = bool(
            warning_actionable
            and source_extension
            and source_extension == target_extension
        )

        warnings: list[str] = []
        if output_name_conflict:
            warnings.append(
                "根目录下已有相同文件：转换时会自动使用新名称，不会覆盖已有文件"
            )
        elif same_format_warning:
            warnings.append("根目录下已有相同文件")

        decorated["_effective_target_format"] = effective_target
        decorated["_same_format_warning"] = same_format_warning
        decorated["_planned_output_path"] = planned_output_path
        decorated["_output_name_conflict"] = output_name_conflict
        decorated["_queue_warning_text"] = "；".join(warnings)
        return decorated

    def _with_queue_path_collisions(self, tasks: list[dict]) -> list[dict]:
        planned_groups: dict[str, list[int]] = {}
        for index, task in enumerate(tasks):
            if task.get("status") not in (
                watcher.QUEUED_STATUS,
                watcher.READING_STATUS,
                watcher.WAITING_STATUS,
                watcher.PROCESSING_STATUS,
                watcher.FAILED_STATUS,
            ):
                continue
            identity = self._normalized_path_identity(
                task.get("_planned_output_path")
            )
            if identity:
                planned_groups.setdefault(identity, []).append(index)

        collision_indexes = {
            index
            for indexes in planned_groups.values()
            if len(indexes) > 1
            for index in indexes
            if self._queue_warning_actionable(tasks[index])
        }
        if not collision_indexes:
            return tasks

        decorated_tasks = list(tasks)
        collision_warning = (
            "队列中多个任务计划输出到同一路径：no-clobber 会自动使用不同名称"
        )
        for index in collision_indexes:
            decorated = dict(tasks[index])
            warnings = [
                warning
                for warning in str(
                    decorated.get("_queue_warning_text") or ""
                ).split("；")
                if warning
            ]
            if collision_warning not in warnings:
                warnings.append(collision_warning)
            decorated["_output_name_conflict"] = True
            decorated["_queue_warning_text"] = "；".join(warnings)
            decorated_tasks[index] = decorated
        return decorated_tasks

    def _queue_warning_actionable(self, task: dict) -> bool:
        return task.get("status") in (
            watcher.QUEUED_STATUS,
            watcher.WAITING_STATUS,
            watcher.FAILED_STATUS,
        )

    def _normalized_path_identity(self, file_path: object) -> str:
        value = str(file_path or "")
        if not value:
            return ""
        return os.path.normcase(
            os.path.abspath(os.path.normpath(value))
        )

    def _planned_output_path(
        self,
        task: dict,
        effective_target: str,
        global_output_folder: str,
        global_create_subfolder: bool,
    ) -> str:
        source_path = str(task.get("path") or "")
        output_root = str(
            task.get("output_directory_override")
            or global_output_folder
            or ""
        )
        if not source_path or not output_root:
            return ""

        output_directory = Path(output_root)
        if bool(task.get("preserve_relative_structure", False)):
            relative_parent = Path(
                str(task.get("relative_output_path") or "")
            ).parent
            if str(relative_parent) not in {"", "."}:
                output_directory = output_directory / relative_parent

        create_format_subfolder = task.get("create_format_subfolder")
        if create_format_subfolder is None:
            create_format_subfolder = global_create_subfolder
        if bool(create_format_subfolder):
            output_directory = output_directory / get_target_label(
                effective_target
            )

        filename = f"{Path(source_path).stem}{get_target_extension(effective_target)}"
        return str(output_directory / filename)

    def _build_summary(self, tasks: list[dict]) -> dict[str, int]:
        return {
            "total": len(tasks),
            "waiting": sum(
                1
                for task in tasks
                if task.get("enabled_for_run", True)
                and task.get("status")
                in (
                    watcher.QUEUED_STATUS,
                    watcher.READING_STATUS,
                    watcher.WAITING_STATUS,
                )
            ),
            "reading": sum(
                1
                for task in tasks
                if task.get("status")
                in (
                    getattr(watcher, "QUEUED_STATUS", "已入队"),
                    watcher.READING_STATUS,
                )
            ),
            "processing": sum(1 for task in tasks if task.get("status") == watcher.PROCESSING_STATUS),
            "completed": sum(1 for task in tasks if task.get("status") == watcher.COMPLETED_STATUS),
            "failed": sum(1 for task in tasks if task.get("status") == watcher.FAILED_STATUS),
            "skipped": sum(1 for task in tasks if task.get("status") == watcher.SKIPPED_STATUS),
            "excluded": sum(
                1 for task in tasks if not task.get("enabled_for_run", True)
            ),
            "retryable": sum(1 for task in tasks if task.get("can_retry")),
            "clearable": sum(
                1
                for task in tasks
                if task.get("status") in watcher.CLEARABLE_TERMINAL_STATUSES
            ),
        }

    def _format_target_display(self, task: dict) -> str:
        selected_format = (
            task.get("target_format_override")
            if "target_format_override" in task
            else task.get("target_format")
        )
        if selected_format:
            return f"单独指定：{get_target_label(selected_format)}"
        effective_target = (
            task.get("_effective_target_format")
            or get_target_format()
        )
        return f"跟随全局：{get_target_label(effective_target)}"

    def _status_display(self, task: dict) -> dict:
        return watcher.get_status_display(task.get("status", ""))

    def _status_tone(self, status: str) -> str:
        if status == watcher.COMPLETED_STATUS:
            return "success"
        if status == watcher.FAILED_STATUS:
            return "danger"
        if status in (watcher.READING_STATUS, watcher.PROCESSING_STATUS):
            return "warning"
        if status == watcher.WAITING_STATUS:
            return "accent"
        return "muted"

    def _source_note(self, task: dict) -> str:
        if task.get("source") == "qml_scan":
            return "目录扫描"
        if task.get("source") == "qml_file":
            return "添加文件"
        if task.get("source") == "qml_drop":
            return "拖入文件"
        if task.get("source") == "folder_browser":
            return "文件夹树"
        if task.get("source") == "watcher":
            return "目录监听"
        if task.get("source") == "retry":
            return "失败重试"
        if task.get("is_ncm_task"):
            return "NCM 解码产物"
        source_path = task.get("path")
        if not source_path:
            return "普通音频"
        suffix = Path(source_path).suffix.lower().lstrip(".")
        return f"{suffix.upper()} 源文件" if suffix else "普通音频"

    def _source_playback_disabled_reason(self, task: dict) -> str:
        source_path = str(task.get("path") or "")
        if not source_path or not os.path.isfile(source_path):
            return "源文件不存在，无法载入播放器"
        if bool(task.get("is_ncm_task")) or Path(source_path).suffix.lower() == ".ncm":
            return "NCM 源文件需先完成转换，再载入正式输出"
        if not is_supported_editor_audio_file(source_path):
            return "当前源格式不能由播放器直接载入"
        return ""

    def _output_playback_disabled_reason(self, task: dict) -> str:
        if task.get("status") != watcher.COMPLETED_STATUS:
            return "转换完成后可用"
        output_path = str(task.get("output_path") or "")
        if not output_path:
            return "任务尚未记录正式输出"
        if not os.path.isfile(output_path):
            return "正式输出文件不存在"
        if not is_supported_editor_audio_file(output_path):
            return "当前输出格式不能由播放器直接载入"
        return ""

    def _lyrics_result_summary(self, task: dict) -> str:
        result = dict(task.get("lyrics_result") or {})
        if not result:
            return "尚无歌词处理结果"
        error = str(result.get("error") or "")
        if error:
            return f"歌词处理失败：{error}"
        embedded = bool(result.get("embedded"))
        copied = bool(result.get("copied"))
        if embedded and copied:
            return "已写入内嵌歌词并复制外置 .lrc"
        if embedded:
            return "已写入内嵌歌词"
        if copied:
            return "已复制外置 .lrc"
        reason_labels = {
            "not_found": "未找到可处理歌词",
            "options_disabled": "歌词处理选项未启用",
            "read_failed": "歌词文件读取失败",
            "same_file_exists": "输出目录已有同名歌词文件",
        }
        skipped_reason = str(result.get("skipped_reason") or "")
        if skipped_reason:
            return reason_labels.get(
                skipped_reason,
                f"歌词处理已跳过：{skipped_reason}",
            )
        if result.get("found"):
            return "已找到歌词，但未写入或复制"
        return "未处理歌词"
