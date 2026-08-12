from __future__ import annotations

import logging
import os

from PySide6.QtCore import Property, Signal, Slot
from PySide6.QtWidgets import QFileDialog

from config import (
    find_watch_folder_candidates,
    is_first_launch_completed,
    update_config,
)
from ui_next.bridge.base_viewmodel import BaseViewModel
from ui_next.bridge.capabilities import CONFIG_WRITE, CapabilityGate


class FirstRunViewModel(BaseViewModel):
    stateChanged = Signal()
    completed = Signal()

    def __init__(
        self,
        *,
        capability_gate: CapabilityGate | None = None,
        enabled: bool = True,
    ) -> None:
        super().__init__(capability_gate=capability_gate or CapabilityGate())
        self._logger = logging.getLogger("AudioConverter.FirstRun")
        self._required = bool(enabled and not is_first_launch_completed())
        self._candidates = (
            find_watch_folder_candidates() if self._required else []
        )
        self._selected_path = self._candidates[0] if len(self._candidates) == 1 else ""
        self._status_message = ""
        self._logger.info("First run required: %s", self._required)
        if self._required:
            self._logger.info(
                "Watch folder candidates found: %d", len(self._candidates)
            )

    @Property(bool, notify=stateChanged)
    def required(self) -> bool:
        return self._required

    @Property(int, notify=stateChanged)
    def candidateCount(self) -> int:
        return len(self._candidates)

    @Property("QVariantList", notify=stateChanged)
    def candidateOptions(self) -> list[dict[str, str]]:
        return [
            {"value": path, "label": path}
            for path in self._candidates
        ]

    @Property(str, notify=stateChanged)
    def selectedPath(self) -> str:
        return self._selected_path

    @Property(str, notify=stateChanged)
    def statusMessage(self) -> str:
        return self._status_message

    @Slot(str)
    def selectCandidate(self, path: str) -> None:
        normalized = os.path.normpath(str(path or "").strip())
        if normalized and normalized in self._candidates:
            self._selected_path = normalized
            self._status_message = ""
            self.stateChanged.emit()

    @Slot()
    def chooseOtherDirectory(self) -> None:
        start_path = (
            self._selected_path
            if self._selected_path and os.path.isdir(self._selected_path)
            else os.path.expanduser("~")
        )
        folder = QFileDialog.getExistingDirectory(
            None,
            "选择音乐下载目录",
            start_path,
            QFileDialog.Option.ShowDirsOnly,
        )
        if not folder:
            return
        normalized = os.path.normpath(folder)
        if normalized not in self._candidates:
            self._candidates.append(normalized)
        self._selected_path = normalized
        self._status_message = "已选择目录，请确认使用。"
        self.stateChanged.emit()

    @Slot(result=bool)
    def useSelectedDirectory(self) -> bool:
        if not self._selected_path or not os.path.isdir(self._selected_path):
            self._set_error("所选目录当前不可用，请重新选择。")
            return False
        return self._complete({"watch_folder": self._selected_path})

    @Slot(result=bool)
    def skip(self) -> bool:
        return self._complete({})

    def _complete(self, updates: dict) -> bool:
        if not self.allows_capability(CONFIG_WRITE):
            self._set_error("当前运行模式不允许保存首次启动设置。")
            return False
        try:
            persisted = dict(updates)
            persisted["first_launch_completed"] = True
            update_config(persisted)
        except Exception as exc:
            self._logger.exception("First run state save failed")
            self._set_error(f"首次启动设置保存失败：{exc}")
            return False

        self._required = False
        self._status_message = "首次启动设置已保存。"
        self.stateChanged.emit()
        self.completed.emit()
        return True

    def _set_error(self, message: str) -> None:
        self._status_message = message
        self.set_status_message(message)
        self.stateChanged.emit()


__all__ = ["FirstRunViewModel"]
