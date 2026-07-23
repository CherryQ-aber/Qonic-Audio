from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import QAbstractListModel, QModelIndex, QObject, Property, Qt, Signal, Slot
from PySide6.QtGui import QGuiApplication


class LogModel(QAbstractListModel):
    TimeRole = Qt.ItemDataRole.UserRole + 1
    LevelRole = Qt.ItemDataRole.UserRole + 2
    MessageRole = Qt.ItemDataRole.UserRole + 3

    countChanged = Signal()
    filterLevelChanged = Signal(str)
    summaryChanged = Signal()

    _ROLE_NAMES = {
        TimeRole: b"time",
        LevelRole: b"level",
        MessageRole: b"message",
    }

    def __init__(self, parent: QObject | None = None, max_entries: int = 500) -> None:
        super().__init__(parent)
        self._entries: list[dict[str, str]] = []
        self._filtered_entries: list[dict[str, str]] = []
        self._filter_level = "all"
        self._max_entries = max_entries

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._filtered_entries)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        if row < 0 or row >= len(self._filtered_entries):
            return None

        entry = self._filtered_entries[row]
        if role == self.TimeRole:
            return entry["time"]
        if role == self.LevelRole:
            return entry["level"]
        if role == self.MessageRole:
            return entry["message"]
        if role == Qt.ItemDataRole.DisplayRole:
            return f'{entry["time"]} [{entry["level"].upper()}] {entry["message"]}'
        return None

    def roleNames(self) -> dict[int, bytes]:
        return self._ROLE_NAMES

    @Property(int, notify=countChanged)
    def count(self) -> int:
        return len(self._entries)

    @Property(str, notify=filterLevelChanged)
    def filterLevel(self) -> str:
        return self._filter_level

    @Property(str, notify=summaryChanged)
    def summary(self) -> str:
        if not self._entries:
            return "暂无日志"

        latest = self._entries[-1]
        return f'{len(self._entries)} 条 | {latest["level"].upper()} {latest["message"]}'

    @Slot(str, str)
    def appendLog(self, level: str, message: str) -> None:
        self.append_log(level, message)

    def append_log(self, level: str, message: str) -> None:
        normalized_level = self._normalize_level(level)
        entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "level": normalized_level,
            "message": str(message or "").strip(),
        }

        if not entry["message"]:
            return

        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries :]

        self._rebuild_filtered()
        self.countChanged.emit()
        self.summaryChanged.emit()

    @Slot()
    def clear(self) -> None:
        if not self._entries:
            return
        self._entries.clear()
        self._rebuild_filtered()
        self.countChanged.emit()
        self.summaryChanged.emit()

    @Slot(result=str)
    def copyAllText(self) -> str:
        return self.copy_all_text()

    def copy_all_text(self) -> str:
        text = "\n".join(
            f'{entry["time"]} [{entry["level"].upper()}] {entry["message"]}'
            for entry in self._entries
        )
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
        return text

    @Slot(str)
    def setFilterLevel(self, level: str) -> None:
        normalized = self._normalize_filter(level)
        if self._filter_level == normalized:
            return

        self._filter_level = normalized
        self._rebuild_filtered()
        self.filterLevelChanged.emit(normalized)

    def _rebuild_filtered(self) -> None:
        self.beginResetModel()
        if self._filter_level == "all":
            self._filtered_entries = list(self._entries)
        else:
            self._filtered_entries = [
                entry
                for entry in self._entries
                if entry["level"] == self._filter_level
            ]
        self.endResetModel()

    @staticmethod
    def _normalize_level(level: str) -> str:
        normalized = str(level or "info").strip().lower()
        if normalized in {"warn"}:
            return "warning"
        if normalized in {"debug", "info", "warning", "error", "critical"}:
            return "error" if normalized == "critical" else normalized
        return "info"

    @staticmethod
    def _normalize_filter(level: str) -> str:
        normalized = str(level or "all").strip().lower()
        if normalized in {"all", "info", "warning", "error"}:
            return normalized
        return "all"


class QtLogHandler(QObject, logging.Handler):
    logEmitted = Signal(str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        QObject.__init__(self, parent)
        logging.Handler.__init__(self)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.logEmitted.emit(record.levelname.lower(), record.getMessage())
        except Exception:
            self.handleError(record)


def install_log_model_handler(log_model: LogModel) -> QtLogHandler:
    root_logger = logging.getLogger()

    for handler in root_logger.handlers:
        if getattr(handler, "_qonic_qml_log_handler", False):
            if isinstance(handler, QtLogHandler):
                try:
                    handler.logEmitted.disconnect()
                except (RuntimeError, TypeError):
                    pass
                handler.logEmitted.connect(log_model.appendLog)
                return handler

    handler = QtLogHandler()
    handler.setLevel(logging.DEBUG)
    handler._qonic_qml_log_handler = True
    handler.logEmitted.connect(log_model.appendLog)
    root_logger.addHandler(handler)
    return handler
