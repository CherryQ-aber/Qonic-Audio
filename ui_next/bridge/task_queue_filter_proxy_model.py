from __future__ import annotations

import os

from PySide6.QtCore import (
    QModelIndex,
    Property,
    QSortFilterProxyModel,
    Signal,
    Slot,
)

import watcher
from ui_next.bridge.task_queue_model import TaskQueueModel


class TaskQueueFilterProxyModel(QSortFilterProxyModel):
    """Read-only task queue projection used by the workspace filters."""

    countChanged = Signal()
    filterChanged = Signal()

    _FILTER_KEYS = {
        "all",
        "waiting",
        "processing",
        "excluded",
        "completed",
        "failed",
    }
    _WAITING_STATUSES = {
        watcher.QUEUED_STATUS,
        watcher.READING_STATUS,
        watcher.WAITING_STATUS,
    }

    def __init__(
        self,
        source_model: TaskQueueModel,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._filter_key = "all"
        self.setDynamicSortFilter(True)
        self.setSourceModel(source_model)
        self.rowsInserted.connect(self._notify_count_changed)
        self.rowsRemoved.connect(self._notify_count_changed)
        self.modelReset.connect(self._notify_count_changed)
        self.layoutChanged.connect(self._notify_count_changed)

    @Property(str, notify=filterChanged)
    def filterKey(self) -> str:
        return self._filter_key

    @Property(int, notify=countChanged)
    def count(self) -> int:
        return self.rowCount()

    @Slot(str)
    def setFilterKey(self, filter_key: str) -> None:
        normalized = str(filter_key or "").strip().lower()
        if normalized not in self._FILTER_KEYS:
            normalized = "all"
        if normalized == self._filter_key:
            return
        self.beginFilterChange()
        self._filter_key = normalized
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)
        self.filterChanged.emit()
        self.countChanged.emit()

    @Slot(int, result=str)
    def pathAt(self, row: int) -> str:
        if row < 0 or row >= self.rowCount():
            return ""
        source_index = self.mapToSource(self.index(row, 0))
        source_model = self.sourceModel()
        if not source_index.isValid() or source_model is None:
            return ""
        return source_model.pathAt(source_index.row())

    @Slot(str, result=bool)
    def containsPath(self, file_path: str) -> bool:
        identity = self._normalized_path_identity(file_path)
        if not identity:
            return False
        return any(
            self._normalized_path_identity(self.pathAt(row)) == identity
            for row in range(self.rowCount())
        )

    def filterAcceptsRow(
        self,
        source_row: int,
        source_parent: QModelIndex,
    ) -> bool:
        source_model = self.sourceModel()
        if source_model is None:
            return False
        if self._filter_key == "all":
            return True

        source_index = source_model.index(source_row, 0, source_parent)
        status = source_model.data(source_index, TaskQueueModel.statusRole)
        enabled_for_run = bool(
            source_model.data(
                source_index,
                TaskQueueModel.enabledForRunRole,
            )
        )
        if self._filter_key == "waiting":
            return enabled_for_run and status in self._WAITING_STATUSES
        if self._filter_key == "processing":
            return status == watcher.PROCESSING_STATUS
        if self._filter_key == "excluded":
            return not enabled_for_run
        if self._filter_key == "completed":
            return status == watcher.COMPLETED_STATUS
        if self._filter_key == "failed":
            return status == watcher.FAILED_STATUS
        return True

    def _notify_count_changed(self, *_args) -> None:
        self.countChanged.emit()

    @staticmethod
    def _normalized_path_identity(file_path: object) -> str:
        value = str(file_path or "")
        if not value:
            return ""
        return os.path.normcase(
            os.path.abspath(os.path.normpath(value))
        )
