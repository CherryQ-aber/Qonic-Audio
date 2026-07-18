from __future__ import annotations

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
from config import get_target_format
from formats import get_target_label
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
        identity = str(file_path or "")
        return any(str(task.get("path") or "") == identity for task in self._tasks)

    def _refresh(self, force: bool = False) -> None:
        try:
            tasks = watcher.get_task_snapshots()
        except Exception as exc:
            self.errorOccurred.emit(f"刷新队列失败: {exc}")
            return

        tasks = list(tasks)
        self._last_refresh_time = QDateTime.currentDateTime().toString("HH:mm:ss")
        self.lastRefreshChanged.emit()
        signature = self._build_signature(tasks)
        if not force and signature == self._last_signature:
            return

        self.beginResetModel()
        self._tasks = tasks
        self.endResetModel()
        self._last_signature = signature

        self._summary = self._build_summary(self._tasks)
        self.countChanged.emit()
        self.summaryChanged.emit()

    def _build_signature(self, tasks: list[dict]) -> tuple:
        global_target_format = get_target_format()
        return (
            global_target_format,
            tuple(
                (
                    task.get("path", ""),
                    task.get("filename", ""),
                    task.get("format", ""),
                    task.get("target_format") or "",
                    task.get("target_format_override") or "",
                    bool(task.get("enabled_for_run", True)),
                    task.get("output_directory_override") or "",
                    task.get("status", ""),
                    bool(task.get("can_convert", False)),
                    bool(task.get("can_retry", False)),
                    bool(task.get("can_change_target_format", False)),
                    bool(task.get("is_ncm_task", False)),
                    task.get("stage", ""),
                    task.get("output_path", ""),
                    task.get("error_summary", ""),
                )
                for task in tasks
            ),
        )

    def _build_summary(self, tasks: list[dict]) -> dict[str, int]:
        return {
            "total": len(tasks),
            "waiting": sum(1 for task in tasks if task.get("status") == watcher.WAITING_STATUS),
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
        return f"跟随全局：{get_target_label(get_target_format())}"

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
