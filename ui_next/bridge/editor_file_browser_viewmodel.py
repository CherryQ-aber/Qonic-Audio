from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Property, QThread, Signal, Slot
from PySide6.QtWidgets import QFileDialog

from formats import is_supported_editor_audio_file, normalize_extension
from ui_next.bridge.base_viewmodel import BaseViewModel
from ui_next.bridge.capabilities import METADATA_READ, CapabilityGate


def enumerate_editor_audio_files(
    folder_path: str,
    *,
    should_stop: Callable[[], bool] | None = None,
) -> list[dict[str, object]]:
    """Return a shallow, extension-only snapshot for the editor browser."""

    folder = Path(folder_path)
    items: list[dict[str, object]] = []
    for entry in folder.iterdir():
        if should_stop is not None and should_stop():
            break
        try:
            if not entry.is_file() or not is_supported_editor_audio_file(entry.name):
                continue
            extension = normalize_extension(entry.name).lstrip(".")
            items.append(
                {
                    "name": entry.name,
                    "path": str(entry.resolve()),
                    "format": extension.upper(),
                    "extension": extension,
                    "size": entry.stat().st_size,
                }
            )
        except OSError:
            # One unreadable entry must not hide the rest of the folder.
            continue
    items.sort(key=lambda item: str(item["name"]).casefold())
    return items


class _EditorFolderScanThread(QThread):
    resultReady = Signal(int, str, object, str)

    def __init__(self, folder_path: str, request_generation: int) -> None:
        super().__init__()
        self._folder_path = folder_path
        self._request_generation = request_generation

    def run(self) -> None:
        try:
            folder = Path(self._folder_path)
            if not folder.exists():
                raise FileNotFoundError("所选文件夹不存在。")
            if not folder.is_dir():
                raise NotADirectoryError("所选路径不是文件夹。")
            items = enumerate_editor_audio_files(
                self._folder_path,
                should_stop=self.isInterruptionRequested,
            )
            error = ""
        except (OSError, ValueError) as exc:
            items = []
            error = str(exc) or "无法读取所选文件夹。"
        self.resultReady.emit(
            self._request_generation,
            self._folder_path,
            items,
            error,
        )


class EditorFileBrowserViewModel(BaseViewModel):
    """A capability-gated, shallow file browser for the current edit session."""

    stateChanged = Signal()
    requestLoadSelected = Signal(str)

    def __init__(self, capability_gate: CapabilityGate | None = None) -> None:
        super().__init__(capability_gate=capability_gate)
        self._folder_path = ""
        self._items: list[dict[str, object]] = []
        self._selected_file_path = ""
        self._state = "empty"
        self._error = ""
        self._request_generation = 0
        self._active_request_generation = 0
        self._threads: set[_EditorFolderScanThread] = set()
        self.set_status_message("请选择一个文件夹浏览支持的音频文件。")

    @Property(bool, constant=True)
    def browserEnabled(self) -> bool:
        return (
            self.allows_capability(METADATA_READ)
            and not self.capabilityGate.previewMode
        )

    @Property(str, notify=stateChanged)
    def folderPath(self) -> str:
        return self._folder_path

    @Property("QVariantList", notify=stateChanged)
    def items(self) -> list[dict[str, object]]:
        return [dict(item) for item in self._items]

    @Property(int, notify=stateChanged)
    def itemCount(self) -> int:
        return len(self._items)

    @Property(str, notify=stateChanged)
    def selectedFilePath(self) -> str:
        return self._selected_file_path

    @Property(bool, notify=stateChanged)
    def hasSelection(self) -> bool:
        return bool(self._selected_file_path)

    @Property(bool, notify=stateChanged)
    def canLoadSelected(self) -> bool:
        return self.browserEnabled and self.hasSelection

    @Property(str, notify=stateChanged)
    def state(self) -> str:
        return self._state

    @Property(bool, notify=stateChanged)
    def isLoading(self) -> bool:
        return self._state == "loading"

    @Property(str, notify=stateChanged)
    def error(self) -> str:
        return self._error

    @Property(str, notify=BaseViewModel.statusMessageChanged)
    def status(self) -> str:
        return self.statusMessage

    @Slot()
    def chooseFolder(self) -> None:
        if not self.browserEnabled:
            self._set_disabled_state()
            return
        folder = QFileDialog.getExistingDirectory(
            None,
            "选择音频文件夹",
            self._folder_path,
        )
        if not folder:
            self.set_status_message("已取消选择文件夹。")
            return
        self.scanFolder(str(folder))

    @Slot(str)
    def scanFolder(self, folder_path: str) -> None:
        normalized_path = self._normalize_folder_path(folder_path)
        self._request_generation += 1
        self._active_request_generation = self._request_generation
        self._interrupt_threads()
        self._folder_path = normalized_path
        self._items = []
        self._selected_file_path = ""
        self._error = ""

        if not self.browserEnabled:
            self._set_disabled_state()
            return
        if not normalized_path:
            self._state = "error"
            self._error = "文件夹路径为空。"
            self.set_status_message(self._error)
            self.stateChanged.emit()
            return

        self._state = "loading"
        self.set_status_message("正在读取文件夹中的音频文件。")
        self.stateChanged.emit()

        thread = _EditorFolderScanThread(
            normalized_path,
            self._active_request_generation,
        )
        self._threads.add(thread)
        thread.resultReady.connect(self._apply_scan_result)
        thread.finished.connect(lambda: self._finish_thread(thread))
        thread.finished.connect(thread.deleteLater)
        thread.start()

    @Slot(str)
    def selectFile(self, path: str) -> None:
        selected_path = str(path or "")
        if not any(str(item.get("path") or "") == selected_path for item in self._items):
            self._selected_file_path = ""
            self.set_status_message("请选择列表中的音频文件。")
            self.stateChanged.emit()
            return
        self._selected_file_path = selected_path
        self.set_status_message(
            f"已选中 {Path(selected_path).name}；点击加载后才会切换当前编辑文件。"
        )
        self.stateChanged.emit()

    @Slot()
    def loadSelected(self) -> None:
        if not self.canLoadSelected:
            self.set_status_message("请先选择一个可加载的音频文件。")
            self.stateChanged.emit()
            return
        self.requestLoadSelected.emit(self._selected_file_path)
        self.set_status_message(
            f"已请求加载 {Path(self._selected_file_path).name}；不会自动播放。"
        )

    @Slot()
    def clear(self) -> None:
        self._request_generation += 1
        self._active_request_generation = self._request_generation
        self._interrupt_threads()
        self._folder_path = ""
        self._items = []
        self._selected_file_path = ""
        self._state = "empty"
        self._error = ""
        self.set_status_message("已清除文件浏览列表；未修改任何磁盘文件。")
        self.stateChanged.emit()

    @Slot()
    def shutdown(self) -> None:
        self._request_generation += 1
        self._active_request_generation = self._request_generation
        self._interrupt_threads()
        deadline = time.monotonic() + 3.0
        for thread in tuple(self._threads):
            remaining_ms = max(0, int((deadline - time.monotonic()) * 1000))
            if remaining_ms:
                thread.wait(remaining_ms)
            if not thread.isRunning():
                self._threads.discard(thread)

    def _apply_scan_result(
        self,
        request_generation: int,
        folder_path: str,
        items: object,
        error: str,
    ) -> None:
        if (
            request_generation != self._active_request_generation
            or folder_path != self._folder_path
        ):
            return
        self._items = list(items or [])
        self._selected_file_path = ""
        self._error = str(error or "")
        if self._error:
            self._state = "error"
            self.set_status_message(f"读取文件夹失败：{self._error}")
        else:
            self._state = "ready"
            self.set_status_message(
                f"已找到 {len(self._items)} 个支持的音频文件。"
            )
        self.stateChanged.emit()

    def _finish_thread(self, thread: _EditorFolderScanThread) -> None:
        self._threads.discard(thread)

    def _interrupt_threads(self) -> None:
        for thread in tuple(self._threads):
            if thread.isRunning():
                thread.requestInterruption()

    def _set_disabled_state(self) -> None:
        self._items = []
        self._selected_file_path = ""
        self._state = "disabled"
        self._error = ""
        self.set_status_message("预览模式下不会读取真实文件夹。")
        self.stateChanged.emit()

    @staticmethod
    def _normalize_folder_path(folder_path: str) -> str:
        raw_path = str(folder_path or "").strip()
        if not raw_path:
            return ""
        return os.path.normpath(os.path.abspath(os.path.expanduser(raw_path)))
