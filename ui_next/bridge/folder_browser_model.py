from __future__ import annotations

from collections import OrderedDict
import os
from pathlib import Path

from PySide6.QtCore import (
    Property,
    QDir,
    QModelIndex,
    QThread,
    QTimer,
    Qt,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QCursor, QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QFileDialog, QFileSystemModel

from config import load_config, save_config
from formats import (
    EDITOR_AUDIO_EXTENSIONS,
    SUPPORTED_INPUT_EXTENSIONS,
    get_source_format,
    is_supported_editor_audio_file,
    is_supported_input_file,
)
from ui_next.bridge.capabilities import (
    AUDIO_PLAYBACK,
    CONFIG_WRITE,
    COVER_READ,
    FOLDER_BROWSER,
    METADATA_READ,
    QUEUE_MUTATION,
    CapabilityGate,
)

try:
    from metadata import read_cover_preview
except ImportError:  # pragma: no cover - optional runtime dependency guard
    read_cover_preview = None


class _FolderCoverWorker(QThread):
    resultReady = Signal(int, str, str, dict)

    def __init__(
        self,
        generation: int,
        path: str,
        cache_key: str,
    ) -> None:
        super().__init__()
        self._generation = generation
        self._path = path
        self._cache_key = cache_key

    def run(self) -> None:
        try:
            result = (
                read_cover_preview(self._path)
                if read_cover_preview is not None
                else {"ok": False, "error": "封面只读接口不可用"}
            )
        except Exception as exc:  # damaged media must not escape the worker
            result = {"ok": False, "error": f"封面读取异常：{exc}"}
        self.resultReady.emit(
            self._generation,
            self._path,
            self._cache_key,
            dict(result),
        )


class FolderBrowserModel(QFileSystemModel):
    """Global, lazy file-system tree shared by both QML workspaces.

    QFileSystemModel performs directory enumeration and change tracking in its
    own worker thread. Only a user-selected/restored root is exposed, and no
    browser action implicitly scans for conversion or mutates the task queue.
    """

    stateChanged = Signal()
    rootModelIndexChanged = Signal()
    countChanged = Signal()
    preferencesChanged = Signal()
    coverChanged = Signal()
    dragStateChanged = Signal()
    internalDragReleased = Signal(str, bool, bool, int, int)
    playbackRequested = Signal(str, str, str, str)
    editorRequested = Signal(str)
    enqueueRequested = Signal(str)

    isDirectoryRole = Qt.UserRole + 100
    isAudioRole = Qt.UserRole + 101
    isPlayableRole = Qt.UserRole + 102
    canEnqueueRole = Qt.UserRole + 103
    fileTypeRole = Qt.UserRole + 104
    sizeTextRole = Qt.UserRole + 105
    modifiedTextRole = Qt.UserRole + 106
    canEditRole = Qt.UserRole + 107
    pathIdentityRole = Qt.UserRole + 108
    fileUrlRole = Qt.UserRole + 109
    treeDepthRole = Qt.UserRole + 110

    _MINIMUM_PANE_WIDTH = 220
    _MAXIMUM_PANE_WIDTH = 360
    _MAXIMUM_RECENT = 12
    _MAXIMUM_FAVORITES = 32
    _MAXIMUM_COVER_CACHE = 48

    def __init__(
        self,
        capability_gate: CapabilityGate | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._capability_gate = capability_gate or CapabilityGate()
        self._available = bool(
            self._capability_gate.allows(FOLDER_BROWSER)
            and not self._capability_gate.previewMode
        )
        self._root_path = ""
        self._root_model_index = QModelIndex()
        self._selected_path = ""
        self._selected_name = ""
        self._selected_summary = "尚未选择文件或文件夹"
        self._selected_is_directory = False
        self._selected_is_audio = False
        self._selected_cover_preview_url = ""
        self._selected_cover_status = "选择音频后显示封面"
        self._selected_has_cover = False
        self._selected_cover_loading = False
        self._cover_generation = 0
        self._cover_worker: _FolderCoverWorker | None = None
        self._pending_cover_request: tuple[int, str, str] | None = None
        self._cover_cache: OrderedDict[str, dict[str, object]] = OrderedDict()
        self._drag_path = ""
        self._drag_global_x = 0
        self._drag_global_y = 0
        self._drag_timer = QTimer(self)
        self._drag_timer.setInterval(16)
        self._drag_timer.timeout.connect(self._poll_internal_drag)
        self._search_text = ""
        self._status_message = (
            "请选择一个根目录开始浏览。"
            if self._available
            else "当前运行模式不会读取真实文件系统。"
        )
        self._favorites: list[str] = []
        self._recent: list[str] = []
        self._pane_visible = True
        self._pane_width = 260

        self.setReadOnly(True)
        self.setResolveSymlinks(False)
        self.setFilter(QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot)
        self.setNameFilterDisables(False)
        self._apply_name_filters()
        self.directoryLoaded.connect(self._handle_directory_loaded)
        self.rowsInserted.connect(lambda *_: self.countChanged.emit())
        self.rowsRemoved.connect(lambda *_: self.countChanged.emit())
        self.modelReset.connect(self.countChanged.emit)

        if self._available:
            self._restore_preferences()

    def roleNames(self) -> dict[int, bytes]:
        roles = dict(super().roleNames())
        roles.update(
            {
                self.isDirectoryRole: b"isDirectory",
                self.isAudioRole: b"isAudio",
                self.isPlayableRole: b"isPlayable",
                self.canEnqueueRole: b"canEnqueue",
                self.fileTypeRole: b"fileType",
                self.sizeTextRole: b"sizeText",
                self.modifiedTextRole: b"modifiedText",
                self.canEditRole: b"canEdit",
                self.pathIdentityRole: b"pathIdentity",
                self.fileUrlRole: b"fileUrl",
                self.treeDepthRole: b"treeDepth",
            }
        )
        return roles

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        # The QML pane renders one compact name column. Metadata is exposed as
        # roles and in the selection summary rather than extra table columns.
        return 1

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        if role < self.isDirectoryRole:
            return super().data(index, role)

        info = self.fileInfo(index)
        is_directory = info.isDir()
        path = info.absoluteFilePath()
        is_audio = bool(
            not is_directory
            and (
                is_supported_input_file(path)
                or is_supported_editor_audio_file(path)
            )
        )
        if role == self.isDirectoryRole:
            return is_directory
        if role == self.isAudioRole:
            return is_audio
        if role == self.isPlayableRole:
            return bool(
                is_audio
                and is_supported_editor_audio_file(path)
                and self._capability_gate.allows(AUDIO_PLAYBACK)
            )
        if role == self.canEnqueueRole:
            return bool(
                is_audio
                and is_supported_input_file(path)
                and self._capability_gate.allows(QUEUE_MUTATION)
            )
        if role == self.fileTypeRole:
            return "文件夹" if is_directory else get_source_format(path)
        if role == self.sizeTextRole:
            return "" if is_directory else self._format_file_size(info.size())
        if role == self.modifiedTextRole:
            return info.lastModified().toString("yyyy-MM-dd HH:mm")
        if role == self.canEditRole:
            return bool(
                is_audio
                and is_supported_editor_audio_file(path)
                and self._capability_gate.allows(METADATA_READ)
            )
        if role == self.pathIdentityRole:
            return self._path_identity(path)
        if role == self.fileUrlRole:
            return QUrl.fromLocalFile(path).toString()
        if role == self.treeDepthRole:
            return self._tree_depth(path)
        return None

    @Property(bool, constant=True)
    def available(self) -> bool:
        return self._available

    @Property(QModelIndex, notify=rootModelIndexChanged)
    def rootModelIndex(self) -> QModelIndex:
        return self._root_model_index

    @Property(str, notify=stateChanged)
    def currentRootPath(self) -> str:
        return self._root_path

    @Property(str, notify=stateChanged)
    def currentRootName(self) -> str:
        if not self._root_path:
            return "未选择根目录"
        return Path(self._root_path).name or self._root_path

    @Property(bool, notify=stateChanged)
    def hasRoot(self) -> bool:
        return bool(self._root_path and self._root_model_index.isValid())

    @Property(int, notify=countChanged)
    def count(self) -> int:
        if not self._root_model_index.isValid():
            return 0
        return int(self.rowCount(self._root_model_index))

    @Property(str, notify=stateChanged)
    def selectedPath(self) -> str:
        return self._selected_path

    @Property(str, notify=stateChanged)
    def selectedPathIdentity(self) -> str:
        return self._path_identity(self._selected_path)

    @Property(str, notify=stateChanged)
    def selectedName(self) -> str:
        return self._selected_name

    @Property(str, notify=stateChanged)
    def selectedSummary(self) -> str:
        return self._selected_summary

    @Property(bool, notify=stateChanged)
    def selectedIsDirectory(self) -> bool:
        return self._selected_is_directory

    @Property(bool, notify=stateChanged)
    def selectedIsAudio(self) -> bool:
        return self._selected_is_audio

    @Property(str, notify=coverChanged)
    def selectedCoverPreviewUrl(self) -> str:
        return self._selected_cover_preview_url

    @Property(str, notify=coverChanged)
    def selectedCoverStatus(self) -> str:
        return self._selected_cover_status

    @Property(bool, notify=coverChanged)
    def selectedHasCover(self) -> bool:
        return self._selected_has_cover

    @Property(bool, notify=coverChanged)
    def selectedCoverLoading(self) -> bool:
        return self._selected_cover_loading

    @Property(bool, notify=dragStateChanged)
    def internalDragActive(self) -> bool:
        return bool(self._drag_path)

    @Property(int, notify=dragStateChanged)
    def internalDragGlobalX(self) -> int:
        return self._drag_global_x

    @Property(int, notify=dragStateChanged)
    def internalDragGlobalY(self) -> int:
        return self._drag_global_y

    @Property(str, notify=dragStateChanged)
    def internalDragFileName(self) -> str:
        return Path(self._drag_path).name if self._drag_path else ""

    @Property(bool, notify=stateChanged)
    def canPlaySelected(self) -> bool:
        return bool(
            self._selected_is_audio
            and is_supported_editor_audio_file(self._selected_path)
            and self._capability_gate.allows(AUDIO_PLAYBACK)
        )

    @Property(bool, notify=stateChanged)
    def canEditSelected(self) -> bool:
        return bool(
            self._selected_is_audio
            and is_supported_editor_audio_file(self._selected_path)
        )

    @Property(bool, notify=stateChanged)
    def canEnqueueSelected(self) -> bool:
        return bool(
            self._selected_is_audio
            and is_supported_input_file(self._selected_path)
            and self._capability_gate.allows(QUEUE_MUTATION)
        )

    @Property(str, notify=stateChanged)
    def searchText(self) -> str:
        return self._search_text

    @Property(str, notify=stateChanged)
    def statusMessage(self) -> str:
        return self._status_message

    @Property("QVariantList", notify=preferencesChanged)
    def favoriteDirectories(self) -> list[dict[str, object]]:
        return self._path_entries(self._favorites)

    @Property("QVariantList", notify=preferencesChanged)
    def recentDirectories(self) -> list[dict[str, object]]:
        return self._path_entries(self._recent)

    @Property(bool, notify=preferencesChanged)
    def currentRootFavorite(self) -> bool:
        identity = self._path_identity(self._root_path)
        return bool(
            identity
            and any(self._path_identity(path) == identity for path in self._favorites)
        )

    @Property(bool, notify=preferencesChanged)
    def paneVisible(self) -> bool:
        return self._pane_visible

    @Property(int, notify=preferencesChanged)
    def paneWidth(self) -> int:
        return self._pane_width

    @Slot(result=bool)
    def chooseRootDirectory(self) -> bool:
        if not self._available:
            self._set_status("当前运行模式不会打开真实目录选择器。")
            return False
        initial_path = self._root_path or str(Path.home())
        selected = QFileDialog.getExistingDirectory(
            None,
            "选择文件浏览根目录",
            initial_path,
        )
        if not selected:
            self._set_status("已取消选择根目录。")
            return False
        return self.openDirectory(selected)

    @Slot(str, result=bool)
    def openDirectory(self, directory_path: str) -> bool:
        if not self._available:
            self._set_status("当前运行模式不会读取真实文件系统。")
            return False
        normalized_path = self._normalize_path(directory_path)
        if not normalized_path or not os.path.isdir(normalized_path):
            self._set_status("所选目录不存在或当前无法访问。")
            return False

        self._root_model_index = super().setRootPath(normalized_path)
        self._root_path = (
            os.path.normpath(self.filePath(self._root_model_index))
            if self._root_model_index.isValid()
            else normalized_path
        )
        self._clear_selection()
        self._add_recent(self._root_path)
        self._set_status(f"正在载入目录：{self._root_path}")
        self.rootModelIndexChanged.emit()
        self.stateChanged.emit()
        self.countChanged.emit()
        self.preferencesChanged.emit()
        self._persist_preferences()
        return self._root_model_index.isValid()

    @Slot(str)
    def setSearchText(self, search_text: str) -> None:
        normalized = str(search_text or "").strip()
        if normalized == self._search_text:
            return
        self._search_text = normalized
        self._apply_name_filters()
        self._set_status(
            f"正在筛选文件名：{normalized}"
            if normalized
            else "已清除文件名筛选。"
        )
        self.stateChanged.emit()

    @Slot(QModelIndex)
    def selectIndex(self, index: QModelIndex) -> None:
        if not index.isValid():
            self._clear_selection()
            return
        self.selectPath(self.filePath(index))

    @Slot(str)
    def selectPath(self, path: str) -> None:
        normalized_path = self._normalize_path(path)
        if not normalized_path or not os.path.exists(normalized_path):
            self._clear_selection("所选项目已不存在。")
            return
        info = self.fileInfo(self.index(normalized_path))
        is_directory = info.isDir()
        is_audio = bool(
            not is_directory
            and (
                is_supported_input_file(normalized_path)
                or is_supported_editor_audio_file(normalized_path)
            )
        )
        self._selected_path = normalized_path
        self._selected_name = info.fileName() or normalized_path
        self._selected_is_directory = is_directory
        self._selected_is_audio = is_audio
        if is_directory:
            self._selected_summary = "文件夹 · 单击箭头展开或折叠"
        elif is_audio:
            self._selected_summary = (
                f"{get_source_format(normalized_path)} · "
                f"{self._format_file_size(info.size())}"
            )
        else:
            self._selected_summary = "不受支持的文件"
        self._prepare_selected_cover()
        self._set_status(f"已选择：{self._selected_name}", emit=False)
        self.stateChanged.emit()

    @Slot(str, result=bool)
    def requestPlayback(self, path: str) -> bool:
        normalized_path = self._validated_audio_path(path, playable=True)
        if not normalized_path:
            return False
        self.playbackRequested.emit(
            normalized_path,
            Path(normalized_path).name,
            "original",
            "folder_tree",
        )
        self._set_status("已载入全局播放器；默认不自动播放。")
        return True

    @Slot(str, result=bool)
    def requestOpenInEditor(self, path: str) -> bool:
        normalized_path = self._validated_audio_path(path, editable=True)
        if not normalized_path:
            return False
        self.editorRequested.emit(normalized_path)
        self._set_status("已请求在音频编辑中打开。")
        return True

    @Slot(str, result=bool)
    def requestAddToQueue(self, path: str) -> bool:
        normalized_path = self._validated_audio_path(path, enqueue=True)
        if not normalized_path:
            return False
        self.enqueueRequested.emit(normalized_path)
        self._set_status("已请求加入现有自动转码任务队列。")
        return True

    @Slot(str, result=bool)
    def openFileLocation(self, path: str) -> bool:
        if not self._available:
            return False
        normalized_path = self._normalize_path(path)
        if not normalized_path or not os.path.exists(normalized_path):
            self._set_status("所选项目已不存在，无法打开文件位置。")
            return False
        target = normalized_path if os.path.isdir(normalized_path) else os.path.dirname(normalized_path)
        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(target))
        self._set_status(
            "已请求打开文件位置。"
            if opened
            else "系统未能打开文件位置。"
        )
        return bool(opened)

    @Slot(str, result=bool)
    def copyPath(self, path: str) -> bool:
        normalized_path = self._normalize_path(path)
        if not normalized_path:
            self._set_status("当前没有可复制的路径。")
            return False
        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            self._set_status("当前无法访问系统剪贴板。")
            return False
        clipboard.setText(normalized_path)
        self._set_status("已复制文件路径。")
        return True

    @Slot(str, result=bool)
    def beginInternalDrag(self, path: str) -> bool:
        normalized_path = self._normalize_path(path)
        if (
            not normalized_path
            or not os.path.isfile(normalized_path)
            or not (
                is_supported_input_file(normalized_path)
                or is_supported_editor_audio_file(normalized_path)
            )
        ):
            return False
        if self._drag_path:
            return (
                self._path_identity(self._drag_path)
                == self._path_identity(normalized_path)
            )
        self._drag_path = normalized_path
        position = QCursor.pos()
        self._drag_global_x = position.x()
        self._drag_global_y = position.y()
        self._drag_timer.start()
        self.dragStateChanged.emit()
        return True

    @Slot()
    def finishInternalDrag(self) -> None:
        self._finish_internal_drag(emit_release=True)

    @Slot()
    def cancelInternalDrag(self) -> None:
        self._finish_internal_drag(emit_release=False)

    @Slot()
    def toggleCurrentRootFavorite(self) -> None:
        if not self._root_path:
            self._set_status("请先选择根目录。")
            return
        root_identity = self._path_identity(self._root_path)
        existing_index = next(
            (
                index
                for index, path in enumerate(self._favorites)
                if self._path_identity(path) == root_identity
            ),
            -1,
        )
        if existing_index >= 0:
            self._favorites.pop(existing_index)
            self._set_status("已取消收藏当前根目录。")
        else:
            self._favorites.insert(0, self._root_path)
            del self._favorites[self._MAXIMUM_FAVORITES :]
            self._set_status("已收藏当前根目录。")
        self.preferencesChanged.emit()
        self._persist_preferences()

    @Slot()
    def clearRecentDirectories(self) -> None:
        if not self._recent:
            return
        self._recent.clear()
        self.preferencesChanged.emit()
        self._persist_preferences()
        self._set_status("已清除最近目录记录。")

    @Slot()
    def clearFavoriteDirectories(self) -> None:
        if not self._favorites:
            return
        self._favorites.clear()
        self.preferencesChanged.emit()
        self._persist_preferences()
        self._set_status("已清除收藏目录记录。")

    @Slot(bool)
    def setPaneVisible(self, visible: bool) -> None:
        normalized = bool(visible)
        if normalized == self._pane_visible:
            return
        self._pane_visible = normalized
        self.preferencesChanged.emit()
        self._persist_preferences()

    @Slot()
    def togglePaneVisible(self) -> None:
        self.setPaneVisible(not self._pane_visible)

    @Slot(int)
    def setPaneWidth(self, width: int) -> None:
        normalized = max(
            self._MINIMUM_PANE_WIDTH,
            min(self._MAXIMUM_PANE_WIDTH, int(width)),
        )
        if normalized == self._pane_width:
            return
        self._pane_width = normalized
        self.preferencesChanged.emit()
        self._persist_preferences()

    @Slot()
    def shutdown(self) -> None:
        self._finish_internal_drag(emit_release=False)
        self._cover_generation += 1
        self._pending_cover_request = None
        worker = self._cover_worker
        if worker is not None and worker.isRunning():
            worker.requestInterruption()
            worker.wait(3_000)

    def _restore_preferences(self) -> None:
        config_data = load_config()
        self._favorites = self._normalize_path_list(
            config_data.get("folder_browser_favorites"),
            self._MAXIMUM_FAVORITES,
        )
        self._recent = self._normalize_path_list(
            config_data.get("folder_browser_recent"),
            self._MAXIMUM_RECENT,
        )
        self._pane_visible = bool(
            config_data.get("folder_browser_visible", True)
        )
        try:
            pane_width = int(config_data.get("folder_browser_width", 260))
        except (TypeError, ValueError):
            pane_width = 260
        self._pane_width = max(
            self._MINIMUM_PANE_WIDTH,
            min(self._MAXIMUM_PANE_WIDTH, pane_width),
        )
        root_path = self._normalize_path(
            str(config_data.get("folder_browser_root") or "")
        )
        if root_path and os.path.isdir(root_path):
            self._root_model_index = super().setRootPath(root_path)
            self._root_path = (
                os.path.normpath(self.filePath(self._root_model_index))
                if self._root_model_index.isValid()
                else root_path
            )
            self._status_message = f"正在恢复目录：{root_path}"

    def _persist_preferences(self) -> None:
        if not self._capability_gate.allows(CONFIG_WRITE):
            return
        try:
            config_data = load_config()
            config_data.update(
                {
                    "folder_browser_root": self._root_path,
                    "folder_browser_favorites": list(self._favorites),
                    "folder_browser_recent": list(self._recent),
                    "folder_browser_visible": self._pane_visible,
                    "folder_browser_width": self._pane_width,
                }
            )
            save_config(config_data)
        except Exception as exc:
            self._set_status(f"文件浏览状态暂未保存：{exc}")

    def _apply_name_filters(self) -> None:
        extensions = sorted(
            set(SUPPORTED_INPUT_EXTENSIONS) | set(EDITOR_AUDIO_EXTENSIONS)
        )
        query = (
            self._search_text.replace("*", "")
            .replace("?", "")
            .replace("[", "")
            .replace("]", "")
        )
        prefix = f"*{query}*" if query else "*"
        self.setNameFilters([f"{prefix}{extension}" for extension in extensions])

    def _validated_audio_path(
        self,
        path: str,
        *,
        playable: bool = False,
        editable: bool = False,
        enqueue: bool = False,
    ) -> str:
        normalized_path = self._normalize_path(path)
        if not normalized_path or not os.path.isfile(normalized_path):
            self._set_status("所选音频文件已不存在。")
            return ""
        if playable and (
            not is_supported_editor_audio_file(normalized_path)
            or not self._capability_gate.allows(AUDIO_PLAYBACK)
        ):
            self._set_status("该文件当前不能直接载入播放器或编辑器。")
            return ""
        if editable and (
            not is_supported_editor_audio_file(normalized_path)
            or not self._capability_gate.allows(METADATA_READ)
        ):
            self._set_status("该文件当前不能在音频编辑中打开。")
            return ""
        if enqueue and (
            not is_supported_input_file(normalized_path)
            or not self._capability_gate.allows(QUEUE_MUTATION)
        ):
            self._set_status("该文件当前不能加入自动转码任务队列。")
            return ""
        return normalized_path

    def _handle_directory_loaded(self, path: str) -> None:
        if self._path_identity(path) == self._path_identity(self._root_path):
            self._set_status(
                f"目录已载入 · {self.count} 个直接项目"
            )
        self.countChanged.emit()

    def _clear_selection(self, message: str = "") -> None:
        self._selected_path = ""
        self._selected_name = ""
        self._selected_summary = "尚未选择文件或文件夹"
        self._selected_is_directory = False
        self._selected_is_audio = False
        self._cover_generation += 1
        self._pending_cover_request = None
        self._selected_cover_preview_url = ""
        self._selected_cover_status = "选择音频后显示封面"
        self._selected_has_cover = False
        self._selected_cover_loading = False
        if message:
            self._status_message = message
        self.coverChanged.emit()
        self.stateChanged.emit()

    def _poll_internal_drag(self) -> None:
        if not self._drag_path:
            self._drag_timer.stop()
            return
        position = QCursor.pos()
        if (
            position.x() != self._drag_global_x
            or position.y() != self._drag_global_y
        ):
            self._drag_global_x = position.x()
            self._drag_global_y = position.y()
            self.dragStateChanged.emit()

    def _finish_internal_drag(self, *, emit_release: bool) -> None:
        if not self._drag_path:
            return
        path = self._drag_path
        position = QCursor.pos()
        self._drag_global_x = position.x()
        self._drag_global_y = position.y()
        editable = bool(
            is_supported_editor_audio_file(path)
            and self._capability_gate.allows(METADATA_READ)
        )
        queueable = bool(
            is_supported_input_file(path)
            and self._capability_gate.allows(QUEUE_MUTATION)
        )
        self._drag_path = ""
        self._drag_timer.stop()
        self.dragStateChanged.emit()
        if emit_release:
            self.internalDragReleased.emit(
                QUrl.fromLocalFile(path).toString(),
                editable,
                queueable,
                self._drag_global_x,
                self._drag_global_y,
            )

    def _prepare_selected_cover(self) -> None:
        self._cover_generation += 1
        generation = self._cover_generation
        self._pending_cover_request = None
        self._selected_cover_preview_url = ""
        self._selected_has_cover = False
        self._selected_cover_loading = False

        if self._selected_is_directory:
            self._selected_cover_status = "文件夹没有封面预览"
            self.coverChanged.emit()
            return
        if not self._selected_is_audio:
            self._selected_cover_status = "当前项目没有封面预览"
            self.coverChanged.emit()
            return
        if not self._capability_gate.allows(COVER_READ):
            self._selected_cover_status = "当前模式未启用封面读取"
            self.coverChanged.emit()
            return
        if read_cover_preview is None:
            self._selected_cover_status = "封面只读接口不可用"
            self.coverChanged.emit()
            return

        cache_key = self._cover_cache_key(self._selected_path)
        cached = self._cover_cache.get(cache_key)
        if cached is not None:
            self._cover_cache.move_to_end(cache_key)
            self._apply_selected_cover_payload(cached)
            return

        self._selected_cover_loading = True
        self._selected_cover_status = "正在读取封面…"
        self.coverChanged.emit()
        request = (generation, self._selected_path, cache_key)
        if self._cover_worker is not None and self._cover_worker.isRunning():
            # Coalesce rapid selection changes: finish the current local read,
            # then start only the most recent pending request.
            self._pending_cover_request = request
            return
        self._start_cover_worker(*request)

    def _start_cover_worker(
        self,
        generation: int,
        path: str,
        cache_key: str,
    ) -> None:
        worker = _FolderCoverWorker(generation, path, cache_key)
        self._cover_worker = worker
        worker.resultReady.connect(self._apply_cover_result)
        worker.finished.connect(lambda: self._finish_cover_worker(worker))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    @Slot(int, str, str, dict)
    def _apply_cover_result(
        self,
        generation: int,
        path: str,
        cache_key: str,
        result: dict,
    ) -> None:
        payload = dict(result)
        self._cover_cache[cache_key] = payload
        self._cover_cache.move_to_end(cache_key)
        while len(self._cover_cache) > self._MAXIMUM_COVER_CACHE:
            self._cover_cache.popitem(last=False)

        if (
            generation != self._cover_generation
            or self._path_identity(path)
            != self._path_identity(self._selected_path)
        ):
            return
        self._apply_selected_cover_payload(payload)

    def _finish_cover_worker(self, worker: _FolderCoverWorker) -> None:
        if self._cover_worker is worker:
            self._cover_worker = None
        pending = self._pending_cover_request
        self._pending_cover_request = None
        if pending is None:
            return
        generation, path, cache_key = pending
        if (
            generation == self._cover_generation
            and self._path_identity(path)
            == self._path_identity(self._selected_path)
        ):
            self._start_cover_worker(generation, path, cache_key)

    def _apply_selected_cover_payload(
        self,
        result: dict[str, object],
    ) -> None:
        ok = bool(result.get("ok", result.get("success", False)))
        self._selected_cover_loading = False
        self._selected_has_cover = bool(ok and result.get("has_cover"))
        self._selected_cover_preview_url = (
            str(result.get("preview_data_url") or "")
            if self._selected_has_cover
            else ""
        )
        if not ok:
            self._selected_cover_status = str(
                result.get("error") or "封面读取失败"
            )
        elif self._selected_has_cover and self._selected_cover_preview_url:
            self._selected_cover_status = "已读取内嵌封面"
        elif self._selected_has_cover:
            self._selected_cover_status = str(
                result.get("error") or "检测到封面，暂无小图"
            )
        else:
            self._selected_cover_status = "未检测到内嵌封面"
        self.coverChanged.emit()

    @classmethod
    def _cover_cache_key(cls, path: str) -> str:
        identity = cls._path_identity(path)
        try:
            stat_result = os.stat(path)
        except OSError:
            return identity
        return (
            f"{identity}|{int(stat_result.st_size)}|"
            f"{int(stat_result.st_mtime_ns)}"
        )

    def _tree_depth(self, path: str) -> int:
        if not self._root_path:
            return -1
        try:
            relative_parent = os.path.relpath(
                os.path.dirname(path),
                self._root_path,
            )
        except (OSError, ValueError):
            return -1
        if relative_parent == ".":
            return 0
        if relative_parent == os.pardir or relative_parent.startswith(
            os.pardir + os.sep
        ):
            return -1
        return len(Path(relative_parent).parts)

    def _add_recent(self, path: str) -> None:
        identity = self._path_identity(path)
        self._recent = [
            existing
            for existing in self._recent
            if self._path_identity(existing) != identity
        ]
        self._recent.insert(0, path)
        del self._recent[self._MAXIMUM_RECENT :]

    def _set_status(self, message: str, *, emit: bool = True) -> None:
        self._status_message = str(message or "")
        if emit:
            self.stateChanged.emit()

    @classmethod
    def _normalize_path(cls, path: str) -> str:
        raw_path = str(path or "").strip()
        if not raw_path:
            return ""
        return os.path.abspath(os.path.normpath(os.path.expanduser(raw_path)))

    @classmethod
    def _normalize_path_list(
        cls,
        value: object,
        limit: int,
    ) -> list[str]:
        try:
            raw_paths = list(value or [])
        except TypeError:
            raw_paths = []
        result: list[str] = []
        seen: set[str] = set()
        for raw_path in raw_paths:
            normalized = cls._normalize_path(str(raw_path or ""))
            identity = cls._path_identity(normalized)
            if not normalized or not identity or identity in seen:
                continue
            seen.add(identity)
            result.append(normalized)
            if len(result) >= limit:
                break
        return result

    @staticmethod
    def _path_identity(path: str) -> str:
        return os.path.normcase(str(path or "")) if path else ""

    @classmethod
    def _path_entries(cls, paths: list[str]) -> list[dict[str, object]]:
        return [
            {
                "path": path,
                "name": Path(path).name or path,
            }
            for path in paths
        ]

    @staticmethod
    def _format_file_size(size: int) -> str:
        value = float(max(0, int(size)))
        units = ("B", "KB", "MB", "GB", "TB")
        unit = units[0]
        for candidate in units:
            unit = candidate
            if value < 1024.0 or candidate == units[-1]:
                break
            value /= 1024.0
        return f"{int(value)} {unit}" if unit == "B" else f"{value:.1f} {unit}"
