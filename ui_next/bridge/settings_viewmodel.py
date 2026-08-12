from __future__ import annotations

import logging
import os
from collections.abc import Callable

from PySide6.QtCore import Property, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QMessageBox

from config import (
    CONFIG_FILE,
    get_cache_folder,
    load_config,
    update_config,
)
from formats import DEFAULT_TARGET_FORMAT, SUPPORTED_TARGET_FORMATS, normalize_target_format
from logger import LOG_DIR, LOG_FILE
from ui_next.bridge.base_viewmodel import BaseViewModel
from cache_manager import format_size
from ui_next.bridge.capabilities import CACHE_CLEANUP, CONFIG_WRITE, CapabilityGate
from ui_next.bridge.log_model import LogModel
from ui.theme import resolve_theme_mode
from ui_next.bridge.settings_storage import (
    clear_log_storage,
    clear_selected_cache,
    scan_settings_storage,
)


class _StorageWorker(QThread):
    resultReady = Signal(object)
    errorReady = Signal(str)

    def __init__(self, action: Callable[[], dict], parent=None) -> None:
        super().__init__(parent)
        self._action = action

    def run(self) -> None:
        try:
            self.resultReady.emit(self._action())
        except Exception as exc:  # pragma: no cover - surfaced in the UI
            self.errorReady.emit(str(exc))


class SettingsViewModel(BaseViewModel):
    settingsChanged = Signal()
    saveStatusChanged = Signal(str)
    hasPendingChangesChanged = Signal(bool)
    configPersisted = Signal()
    runtimeStateChanged = Signal()
    storageChanged = Signal()
    storageBusyChanged = Signal(bool)
    cleanupPlanChanged = Signal()
    cleanupDialogRequested = Signal()

    _PATH_KEYS = {
        "watch_folder": "监听目录",
        "output_folder": "自动转码输出目录",
        "editor_output_folder": "音频编辑输出目录",
    }
    _SETTING_ORDER = (
        "watch_folder",
        "output_folder",
        "editor_output_folder",
        "target_format",
        "auto_start_monitor",
        "scan_existing_on_start",
        "create_format_subfolder",
        "preserve_relative_structure",
        "embed_lyrics_after_convert",
        "copy_lrc_to_output",
        "overwrite_existing_lyrics",
        "theme_mode",
        "log_level",
        "ui_density",
        "editor_file_bar_mode",
        "lyrics_timestamp_precision",
    )
    _KNOWN_KEYS = frozenset(_SETTING_ORDER)
    _SETTING_LABELS = {
        "watch_folder": "监听目录",
        "output_folder": "转码输出目录",
        "editor_output_folder": "编辑输出目录",
        "target_format": "目标格式",
        "auto_start_monitor": "启动时自动监听",
        "scan_existing_on_start": "启动时扫描已有文件",
        "create_format_subfolder": "按格式创建子目录",
        "preserve_relative_structure": "保留相对目录结构",
        "embed_lyrics_after_convert": "转码后嵌入歌词",
        "copy_lrc_to_output": "复制同名 LRC",
        "overwrite_existing_lyrics": "覆盖已有歌词",
        "theme_mode": "界面主题",
        "log_level": "日志级别",
        "ui_density": "界面密度",
        "editor_file_bar_mode": "公共文件栏",
        "lyrics_timestamp_precision": "歌词时间精度",
    }
    _AUTO_CONVERT_KEYS = frozenset(
        {
            "watch_folder",
            "output_folder",
            "target_format",
            "auto_start_monitor",
            "scan_existing_on_start",
            "create_format_subfolder",
            "preserve_relative_structure",
            "embed_lyrics_after_convert",
            "copy_lrc_to_output",
            "overwrite_existing_lyrics",
        }
    )
    _PREVIEW_SAFETY_MESSAGE = (
        "预览模式：设置修改只保存为页面草稿，不会写入 config.json，"
        "也不会影响旧 Widgets UI 或后台任务。"
    )

    def __init__(
        self,
        log_model: LogModel | None = None,
        capability_gate: CapabilityGate | None = None,
        live_mode: bool | None = None,
    ) -> None:
        gate = capability_gate or CapabilityGate()
        super().__init__(capability_gate=gate)
        self._logger = logging.getLogger("AudioConverter.QML")
        self._log_model = log_model
        self._current_config = load_config()
        self._pending_config = dict(self._current_config)
        self._has_pending_changes = False
        self._save_status = ""
        self._auto_convert_view_model = None
        self._processing_session_view_model = None
        self._edit_session_view_model = None
        self._storage_worker: _StorageWorker | None = None
        self._storage_operation = ""
        self._storage_result: dict | None = None
        self._storage_error = ""
        self._storage_busy = False
        self._log_storage = self._empty_log_storage()
        self._cache_storage = self._empty_cache_storage()
        self._cleanup_target = ""
        self._cleanup_title = ""
        self._cleanup_summary = ""
        self._cleanup_items: list[dict] = []
        if gate.allows(CONFIG_WRITE):
            self._apply_log_level(self.logLevel)

    @Property(str, notify=settingsChanged)
    def watchFolder(self) -> str:
        return str(self._pending_config.get("watch_folder") or "")

    @Property(str, notify=settingsChanged)
    def outputFolder(self) -> str:
        return str(self._pending_config.get("output_folder") or "")

    @Property(str, notify=settingsChanged)
    def editorOutputFolder(self) -> str:
        return str(self._pending_config.get("editor_output_folder") or "")

    @Property(str, constant=True)
    def cacheFolder(self) -> str:
        return get_cache_folder()

    @Property(str, constant=True)
    def configFilePath(self) -> str:
        return CONFIG_FILE

    @Property(str, constant=True)
    def lastSavedConfigPath(self) -> str:
        return CONFIG_FILE

    @Property(str, constant=True)
    def logFilePath(self) -> str:
        return LOG_FILE

    @Property(str, notify=settingsChanged)
    def targetFormat(self) -> str:
        return str(self._pending_config.get("target_format") or DEFAULT_TARGET_FORMAT)

    @Property("QVariantList", constant=True)
    def targetFormatOptions(self) -> list[dict[str, str]]:
        return [
            {
                "value": value,
                "label": f'{metadata["label"]} - {metadata["description"]}',
            }
            for value, metadata in SUPPORTED_TARGET_FORMATS.items()
        ]

    @Property(bool, notify=settingsChanged)
    def autoStartMonitor(self) -> bool:
        return self._as_bool(self._pending_config.get("auto_start_monitor"), True)

    @Property(bool, notify=settingsChanged)
    def scanExistingOnStart(self) -> bool:
        return self._as_bool(self._pending_config.get("scan_existing_on_start"), False)

    @Property(bool, notify=settingsChanged)
    def createFormatSubfolder(self) -> bool:
        return self._as_bool(self._pending_config.get("create_format_subfolder"), True)

    @Property(bool, notify=settingsChanged)
    def preserveRelativeStructure(self) -> bool:
        return self._as_bool(self._pending_config.get("preserve_relative_structure"), False)

    @Property(bool, notify=settingsChanged)
    def embedLyricsAfterConvert(self) -> bool:
        return self._as_bool(self._pending_config.get("embed_lyrics_after_convert"), True)

    @Property(bool, notify=settingsChanged)
    def copyLrcToOutput(self) -> bool:
        return self._as_bool(self._pending_config.get("copy_lrc_to_output"), False)

    @Property(bool, notify=settingsChanged)
    def overwriteExistingLyrics(self) -> bool:
        return self._as_bool(self._pending_config.get("overwrite_existing_lyrics"), False)

    @Property(str, notify=settingsChanged)
    def audioOutputDeviceName(self) -> str:
        return str(self._pending_config.get("audio_output_device_name") or "系统默认输出")

    @Property(str, notify=settingsChanged)
    def themeMode(self) -> str:
        return str(self._pending_config.get("theme_mode") or "system")

    @Property(str, notify=settingsChanged)
    def resolvedThemeMode(self) -> str:
        return self._resolve_theme_mode(self.themeMode)

    @Property(str, notify=settingsChanged)
    def logLevel(self) -> str:
        return str(self._pending_config.get("log_level") or "INFO").upper()

    @Property(str, notify=settingsChanged)
    def uiDensity(self) -> str:
        return str(self._pending_config.get("ui_density") or "standard")

    @Property(str, notify=settingsChanged)
    def editorFileBarMode(self) -> str:
        value = str(
            self._pending_config.get("editor_file_bar_mode") or "fixed"
        ).strip().lower()
        return value if value in {"fixed", "floating"} else "fixed"

    @Property(str, notify=settingsChanged)
    def lyricsTimestampPrecision(self) -> str:
        value = str(
            self._pending_config.get("lyrics_timestamp_precision")
            or "millisecond"
        ).strip().lower()
        return (
            value
            if value in {"centisecond", "millisecond"}
            else "millisecond"
        )

    @Property(str, notify=saveStatusChanged)
    def saveStatus(self) -> str:
        return self._save_status

    @Property(bool, constant=True)
    def previewMode(self) -> bool:
        return not self.allows_capability(CONFIG_WRITE)

    @Property(bool, constant=True)
    def liveMode(self) -> bool:
        return self.allows_capability(CONFIG_WRITE)

    @Property(bool, constant=True)
    def isDraftOnly(self) -> bool:
        return True

    @Property(bool, constant=True)
    def isLiveOnly(self) -> bool:
        return True

    @Property(bool, constant=True)
    def isDisabledInPreview(self) -> bool:
        return self.previewMode

    @Property(bool, constant=True)
    def canPersistConfig(self) -> bool:
        return self.liveMode

    @Property(str, constant=True)
    def previewSafetyMessage(self) -> str:
        return self._PREVIEW_SAFETY_MESSAGE

    @Property(bool, notify=hasPendingChangesChanged)
    def hasPendingChanges(self) -> bool:
        return self._has_pending_changes

    @Property(str, notify=hasPendingChangesChanged)
    def draftStateText(self) -> str:
        if not self._has_pending_changes:
            return ""
        return f"{self.pendingChangeCount} 项修改未应用"

    @Property(int, notify=hasPendingChangesChanged)
    def pendingChangeCount(self) -> int:
        return len(self._changed_keys())

    @Property("QVariantList", notify=hasPendingChangesChanged)
    def pendingChangeItems(self) -> list[dict]:
        return [self._change_item(key) for key in self._changed_keys()]

    @Property(str, notify=hasPendingChangesChanged)
    def pendingChangeSummary(self) -> str:
        return "\n".join(
            f'{item["label"]}：{item["before"]} → {item["after"]}'
            for item in self.pendingChangeItems
        )

    @Property(bool, notify=hasPendingChangesChanged)
    def hasAutoConvertChanges(self) -> bool:
        return any(key in self._AUTO_CONVERT_KEYS for key in self._changed_keys())

    @Property(bool, notify=runtimeStateChanged)
    def autoConvertBusy(self) -> bool:
        view_model = self._auto_convert_view_model
        return bool(view_model is not None and getattr(view_model, "isConverting", False))

    @Property(bool, notify=runtimeStateChanged)
    def cacheCleanupBlocked(self) -> bool:
        auto_busy = bool(
            self._auto_convert_view_model is not None
            and getattr(self._auto_convert_view_model, "hasBackgroundTask", False)
        )
        processing_busy = bool(
            self._processing_session_view_model is not None
            and getattr(self._processing_session_view_model, "isBusy", False)
        )
        exporting = bool(
            self._edit_session_view_model is not None
            and getattr(self._edit_session_view_model, "anyExporting", False)
        )
        return auto_busy or processing_busy or exporting

    @Property(str, notify=runtimeStateChanged)
    def cacheCleanupBlockedReason(self) -> str:
        if not self.cacheCleanupBlocked:
            return ""
        return "当前有转换、扫描、音频处理或导出任务，暂不能清理缓存。"

    @Property(bool, notify=runtimeStateChanged)
    def canApplyPendingChanges(self) -> bool:
        return bool(
            self.canPersistConfig
            and self.hasPendingChanges
            and not (self.hasAutoConvertChanges and self.autoConvertBusy)
        )

    @Property(str, notify=runtimeStateChanged)
    def applyBlockedReason(self) -> str:
        if not self.canPersistConfig:
            return "当前运行模式不允许保存设置。"
        if not self.hasPendingChanges:
            return "当前没有需要应用的修改。"
        if self.hasAutoConvertChanges and self.autoConvertBusy:
            return "自动转码正在运行，结束后才能应用相关设置。"
        return ""

    @Property(bool, notify=storageBusyChanged)
    def storageBusy(self) -> bool:
        return self._storage_busy

    @Property(str, notify=storageChanged)
    def logUsageText(self) -> str:
        return str(self._log_storage.get("total_size_text") or "0 B")

    @Property(int, notify=storageChanged)
    def logFileCount(self) -> int:
        return int(self._log_storage.get("total_files") or 0)

    @Property(str, notify=storageChanged)
    def cacheUsageText(self) -> str:
        return format_size(self._cache_storage.get("total_size") or 0)

    @Property(int, notify=storageChanged)
    def cacheFileCount(self) -> int:
        return int(self._cache_storage.get("total_files") or 0)

    @Property(str, notify=storageChanged)
    def storageSummary(self) -> str:
        if self.storageBusy:
            return "正在读取占用空间…"
        return f"日志 {self.logUsageText} · 缓存 {self.cacheUsageText}"

    @Property(bool, notify=storageChanged)
    def canPrepareLogCleanup(self) -> bool:
        return bool(
            self.allows_capability(CACHE_CLEANUP)
            and not self.storageBusy
            and self.logFileCount > 0
        )

    @Property(bool, notify=storageChanged)
    def canPrepareCacheCleanup(self) -> bool:
        return bool(
            self.allows_capability(CACHE_CLEANUP)
            and not self.storageBusy
            and not self.cacheCleanupBlocked
            and int(self._cache_storage.get("cleanable_files") or 0) > 0
        )

    @Property(str, notify=cleanupPlanChanged)
    def cleanupTarget(self) -> str:
        return self._cleanup_target

    @Property(str, notify=cleanupPlanChanged)
    def cleanupTitle(self) -> str:
        return self._cleanup_title

    @Property(str, notify=cleanupPlanChanged)
    def cleanupSummary(self) -> str:
        return self._cleanup_summary

    @Property("QVariantList", notify=cleanupPlanChanged)
    def cleanupItems(self) -> list[dict]:
        return list(self._cleanup_items)

    @Property("QVariantMap", notify=settingsChanged)
    def currentConfig(self) -> dict:
        return dict(self._current_config)

    @Property("QVariantMap", notify=settingsChanged)
    def pendingConfig(self) -> dict:
        return dict(self._pending_config)

    def attach_runtime(
        self,
        auto_convert_view_model=None,
        processing_session_view_model=None,
        edit_session_view_model=None,
    ) -> None:
        self._auto_convert_view_model = auto_convert_view_model
        self._processing_session_view_model = processing_session_view_model
        self._edit_session_view_model = edit_session_view_model

        if auto_convert_view_model is not None:
            auto_convert_view_model.busyChanged.connect(self._emit_runtime_state)
        if processing_session_view_model is not None:
            processing_session_view_model.stateChanged.connect(self._emit_runtime_state)
        if edit_session_view_model is not None:
            edit_session_view_model.stateChanged.connect(self._emit_runtime_state)
        self._emit_runtime_state()

    @Slot()
    def refreshStorageUsage(self) -> None:
        self._start_storage_operation("scan", scan_settings_storage)

    @Slot()
    def prepareLogCleanup(self) -> None:
        self._start_storage_operation("prepare_logs", scan_settings_storage)

    @Slot()
    def prepareCacheCleanup(self) -> None:
        if self.cacheCleanupBlocked:
            self._set_save_status(self.cacheCleanupBlockedReason, level="warning")
            return
        self._start_storage_operation("prepare_cache", scan_settings_storage)

    @Slot()
    def cancelPreparedCleanup(self) -> None:
        self._clear_cleanup_plan()

    @Slot()
    def confirmPreparedCleanup(self) -> None:
        if not self._cleanup_target or not self._cleanup_items:
            self._set_save_status("没有可清理的项目。")
            return
        if not self.allows_capability(CACHE_CLEANUP):
            self._set_save_status(
                self.block_capability(CACHE_CLEANUP), level="warning"
            )
            return
        if self._cleanup_target == "cache" and self.cacheCleanupBlocked:
            self._set_save_status(self.cacheCleanupBlockedReason, level="warning")
            return

        target = self._cleanup_target
        if target == "logs":
            action = clear_log_storage
        else:
            category_ids = [item["id"] for item in self._cleanup_items]
            action = lambda: clear_selected_cache(category_ids)
        self._clear_cleanup_plan()
        self._start_storage_operation(f"clear_{target}", action)

    @Slot()
    def shutdown(self) -> None:
        worker = self._storage_worker
        if worker is not None and worker.isRunning():
            worker.wait()

    @Slot()
    def reload(self) -> None:
        self.reloadConfig()

    @Slot()
    def reloadConfig(self) -> None:
        self._current_config = load_config()
        self._pending_config = dict(self._current_config)
        self._set_pending_changes(False)
        self.settingsChanged.emit()
        self._set_save_status("已重新载入设置。")

    @Slot(str)
    def chooseDirectory(self, key: str) -> None:
        if key not in self._PATH_KEYS:
            self._set_save_status(f"未知路径设置: {key}", level="warning")
            return

        current_path = str(self._pending_config.get(key) or "")
        if not current_path or not os.path.isdir(current_path):
            current_path = os.path.expanduser("~")

        folder = QFileDialog.getExistingDirectory(
            None,
            f"选择{self._PATH_KEYS[key]}",
            current_path,
            QFileDialog.Option.ShowDirsOnly,
        )

        if not folder:
            return

        self.updatePendingValue(
            key,
            os.path.normpath(folder),
        )

    @Slot()
    def choosePendingWatchFolder(self) -> None:
        self.chooseDirectory("watch_folder")

    @Slot()
    def choosePendingOutputFolder(self) -> None:
        self.chooseDirectory("output_folder")

    @Slot()
    def choosePendingEditorOutputFolder(self) -> None:
        self.chooseDirectory("editor_output_folder")

    @Slot(str, str)
    def setPathValue(self, key: str, value: str) -> None:
        if key not in self._PATH_KEYS:
            self._set_save_status(f"未知路径设置: {key}", level="warning")
            return
        normalized = os.path.normpath(str(value or "").strip())
        self.updatePendingValue(key, normalized)

    @Slot(str)
    def set_watch_folder(self, value: str) -> None:
        self.setPathValue("watch_folder", value)

    @Slot(str)
    def set_output_folder(self, value: str) -> None:
        self.setPathValue("output_folder", value)

    @Slot(str)
    def setTargetFormat(self, value: str) -> None:
        normalized = normalize_target_format(value, DEFAULT_TARGET_FORMAT)
        self.updatePendingValue("target_format", normalized)

    @Slot(str)
    def set_target_format(self, value: str) -> None:
        self.setTargetFormat(value)

    @Slot(bool)
    def setAutoStartMonitor(self, enabled: bool) -> None:
        self.updatePendingValue("auto_start_monitor", bool(enabled))

    @Slot(bool)
    def set_auto_start_monitor(self, enabled: bool) -> None:
        self.setAutoStartMonitor(enabled)

    @Slot(bool)
    def setScanExistingOnStart(self, enabled: bool) -> None:
        self.updatePendingValue("scan_existing_on_start", bool(enabled))

    @Slot(bool)
    def set_scan_existing_on_start(self, enabled: bool) -> None:
        self.setScanExistingOnStart(enabled)

    @Slot(bool)
    def setCreateFormatSubfolder(self, enabled: bool) -> None:
        self.updatePendingValue("create_format_subfolder", bool(enabled))

    @Slot(bool)
    def setPreserveRelativeStructure(self, enabled: bool) -> None:
        self.updatePendingValue("preserve_relative_structure", bool(enabled))

    @Slot(bool)
    def setEmbedLyricsAfterConvert(self, enabled: bool) -> None:
        self.updatePendingValue("embed_lyrics_after_convert", bool(enabled))

    @Slot(bool)
    def setCopyLrcToOutput(self, enabled: bool) -> None:
        self.updatePendingValue("copy_lrc_to_output", bool(enabled))

    @Slot(bool)
    def setOverwriteExistingLyrics(self, enabled: bool) -> None:
        self.updatePendingValue("overwrite_existing_lyrics", bool(enabled))

    @Slot(str, result=bool)
    def setThemeMode(self, value: str) -> bool:
        return self.applyThemeMode(value)

    @Slot(str, result=bool)
    def applyThemeMode(self, value: str) -> bool:
        normalized = str(value or "system").strip().lower()
        if normalized not in {"system", "dark", "light", "black", "purple"}:
            normalized = "system"
        if not self.allows_capability(CONFIG_WRITE):
            self.updatePendingValue("theme_mode", normalized)
            self._set_save_status(
                "主题已在本次运行中预览，但当前模式不允许持久化。",
                level="warning",
            )
            return True

        try:
            saved = update_config({"theme_mode": normalized})
        except Exception as exc:
            self._set_save_status(f"主题保存失败：{exc}", level="error")
            return False

        self._current_config = dict(saved)
        self._pending_config["theme_mode"] = normalized
        self._set_pending_changes(bool(self._changed_keys()))
        self.settingsChanged.emit()
        self._set_save_status("主题已保存。")
        return True

    @Slot(str, result=str)
    def resolveThemeMode(self, value: str) -> str:
        return self._resolve_theme_mode(value)

    @Slot(str)
    def setLogLevel(self, value: str) -> None:
        normalized = str(value or "INFO").strip().upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
            normalized = "INFO"
        self.updatePendingValue("log_level", normalized)

    @Slot(str)
    def setUiDensity(self, value: str) -> None:
        normalized = str(value or "standard").strip().lower()
        if normalized not in {"compact", "standard"}:
            normalized = "standard"
        self.updatePendingValue("ui_density", normalized)

    @Slot(str)
    def setEditorFileBarMode(self, value: str) -> None:
        self.updatePendingValue("editor_file_bar_mode", value)

    @Slot(str)
    def setLyricsTimestampPrecision(self, value: str) -> None:
        self.updatePendingValue("lyrics_timestamp_precision", value)

    @Slot()
    def openLogFolder(self) -> None:
        os.makedirs(LOG_DIR, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(LOG_DIR))
        self._set_save_status("已请求打开日志文件位置")

    @Slot()
    def copyRecentLogs(self) -> None:
        if self._log_model is None:
            self._set_save_status("日志模型尚未接入", level="warning")
            return
        self._log_model.copy_all_text()
        self._set_save_status("最近日志已复制")

    @Slot()
    def clearLogPreview(self) -> None:
        if self._log_model is None:
            self._set_save_status("日志模型尚未接入", level="warning")
            return
        self._log_model.clear()
        self._set_save_status("日志抽屉已清空")

    @Slot()
    def applyPendingDraft(self) -> None:
        self.simulateSaveDraft()

    @Slot()
    def simulateSaveDraft(self) -> None:
        if self._has_pending_changes:
            self._set_save_status(self.pendingChangeSummary)
        else:
            self._set_save_status("")

    @Slot()
    def saveConfig(self) -> None:
        self.savePendingChanges()

    @Slot()
    def save_config(self) -> None:
        self.savePendingChanges()

    @Slot()
    def savePendingChanges(self) -> None:
        if not self.allows_capability(CONFIG_WRITE):
            blocked_message = self.block_capability(CONFIG_WRITE)
            self._set_save_status(blocked_message, level="warning")
            return

        if not self._has_pending_changes:
            self._set_save_status("")
            return

        if self.hasAutoConvertChanges and self.autoConvertBusy:
            self._set_save_status(self.applyBlockedReason, level="warning")
            return

        if not self._confirm_live_save():
            self._set_save_status("已取消应用，修改仍保留。")
            return

        # Apply only confirmed changes. update_config merges them onto the
        # newest on-disk state while holding the shared config lock.
        updates = {
            key: self._pending_config[key]
            for key in self._changed_keys()
            if key in self._pending_config
        }
        try:
            self._current_config = update_config(updates)
        except Exception as exc:
            self._set_save_status(f"设置保存失败：{exc}", level="error")
            return
        self._pending_config = dict(self._current_config)
        self._set_pending_changes(False)
        self.settingsChanged.emit()
        self._apply_log_level(self.logLevel)
        self.configPersisted.emit()
        self._set_save_status("设置已应用。")

    @Slot()
    def discardPendingChanges(self) -> None:
        self._pending_config = dict(self._current_config)
        self._set_pending_changes(False)
        self.settingsChanged.emit()
        self._set_save_status("已放弃修改。")

    @Slot(str, "QVariant")
    def updatePendingValue(self, key: str, value) -> None:
        normalized_key = str(key or "").strip()
        if normalized_key not in self._KNOWN_KEYS:
            self._set_save_status(f"未知设置项: {normalized_key}", level="warning")
            return

        normalized_value = self._normalize_value(normalized_key, value)
        if self._pending_config.get(normalized_key) == normalized_value:
            return

        self._pending_config[normalized_key] = normalized_value
        self._set_pending_changes(self._pending_config != self._current_config)
        self.settingsChanged.emit()
        self._set_save_status(
            f"已修改：{self._SETTING_LABELS.get(normalized_key, normalized_key)}"
            if self._has_pending_changes
            else ""
        )

    def _set_pending_changes(self, value: bool) -> None:
        if self._has_pending_changes == value:
            return
        self._has_pending_changes = value
        self.hasPendingChangesChanged.emit(value)
        self.runtimeStateChanged.emit()

    def _set_save_status(self, message: str, level: str = "info") -> None:
        self._save_status = message
        self.saveStatusChanged.emit(message)
        self.set_status_message(message)

        if level == "error":
            self._logger.error(message)
        elif level == "warning":
            self._logger.warning(message)
        else:
            self._logger.info(message)

    def _normalize_value(self, key: str, value):
        if key in self._PATH_KEYS:
            return os.path.normpath(str(value or "").strip())
        if key == "target_format":
            return normalize_target_format(value, DEFAULT_TARGET_FORMAT)
        if key in {
            "auto_start_monitor",
            "scan_existing_on_start",
            "create_format_subfolder",
            "preserve_relative_structure",
            "embed_lyrics_after_convert",
            "copy_lrc_to_output",
            "overwrite_existing_lyrics",
        }:
            return self._as_bool(value, False)
        if key == "theme_mode":
            normalized = str(value or "system").strip().lower()
            return normalized if normalized in {"system", "dark", "light", "black", "purple"} else "system"
        if key == "log_level":
            normalized = str(value or "INFO").strip().upper()
            return normalized if normalized in {"DEBUG", "INFO", "WARNING", "ERROR"} else "INFO"
        if key == "ui_density":
            normalized = str(value or "standard").strip().lower()
            return normalized if normalized in {"compact", "standard"} else "standard"
        if key == "editor_file_bar_mode":
            normalized = str(value or "fixed").strip().lower()
            return normalized if normalized in {"fixed", "floating"} else "fixed"
        if key == "lyrics_timestamp_precision":
            normalized = str(value or "millisecond").strip().lower()
            return (
                normalized
                if normalized in {"centisecond", "millisecond"}
                else "millisecond"
            )
        return value

    def _changed_keys(self) -> list[str]:
        return [
            key
            for key in self._SETTING_ORDER
            if self._pending_config.get(key) != self._current_config.get(key)
        ]

    def _change_item(self, key: str) -> dict:
        return {
            "key": key,
            "label": self._SETTING_LABELS.get(key, key),
            "before": self._format_setting_value(key, self._current_config.get(key)),
            "after": self._format_setting_value(key, self._pending_config.get(key)),
            "automaticConversion": key in self._AUTO_CONVERT_KEYS,
        }

    @staticmethod
    def _format_setting_value(key: str, value) -> str:
        if isinstance(value, bool):
            return "开启" if value else "关闭"
        if value in (None, ""):
            return "未设置"
        normalized = str(value)
        labels = {
            "dark": "深色主题",
            "light": "浅色主题",
            "system": "跟随系统",
            "standard": "标准",
            "compact": "紧凑",
            "fixed": "固定",
            "floating": "悬浮",
            "millisecond": "千分之一秒",
            "centisecond": "百分之一秒",
        }
        if key == "target_format":
            return normalized.upper()
        return labels.get(normalized.lower(), normalized)

    def _emit_runtime_state(self) -> None:
        self.runtimeStateChanged.emit()
        self.storageChanged.emit()

    def _start_storage_operation(
        self, operation: str, action: Callable[[], dict]
    ) -> None:
        if self._storage_worker is not None:
            self._set_save_status("正在处理日志与缓存，请稍候。")
            return
        self._storage_operation = operation
        self._storage_result = None
        self._storage_error = ""
        self._set_storage_busy(True)
        worker = _StorageWorker(action, self)
        self._storage_worker = worker
        worker.resultReady.connect(self._store_storage_result)
        worker.errorReady.connect(self._store_storage_error)
        worker.finished.connect(self._finish_storage_operation)
        worker.start()

    @Slot(object)
    def _store_storage_result(self, result: object) -> None:
        self._storage_result = dict(result or {})

    @Slot(str)
    def _store_storage_error(self, message: str) -> None:
        self._storage_error = str(message or "未知错误")

    @Slot()
    def _finish_storage_operation(self) -> None:
        operation = self._storage_operation
        result = self._storage_result or {}
        error = self._storage_error
        worker = self._storage_worker
        self._storage_worker = None
        self._storage_operation = ""
        self._storage_result = None
        self._storage_error = ""
        self._set_storage_busy(False)
        if worker is not None:
            worker.deleteLater()

        if error:
            self._set_save_status(f"日志与缓存操作失败：{error}", level="warning")
            return
        if operation in {"scan", "prepare_logs", "prepare_cache"}:
            self._apply_storage_scan(result)
            if operation == "prepare_logs":
                self._prepare_cleanup_plan("logs")
            elif operation == "prepare_cache":
                self._prepare_cleanup_plan("cache")
            return

        freed = format_size(result.get("freed_size") or 0)
        failed_count = int(result.get("failed_count") or 0)
        label = "日志" if operation == "clear_logs" else "缓存"
        message = f"{label}清理完成，释放 {freed}。"
        if failed_count:
            message += f" {failed_count} 项未能清理。"
        if operation == "clear_logs" and self._log_model is not None:
            self._log_model.clear()
        self._set_save_status(message, level="warning" if failed_count else "info")
        self.refreshStorageUsage()

    def _apply_storage_scan(self, result: dict) -> None:
        self._log_storage = dict(result.get("logs") or self._empty_log_storage())
        self._cache_storage = dict(result.get("cache") or self._empty_cache_storage())
        self.storageChanged.emit()

    def _prepare_cleanup_plan(self, target: str) -> None:
        if not self.allows_capability(CACHE_CLEANUP):
            self._set_save_status(self.block_capability(CACHE_CLEANUP), level="warning")
            return
        if target == "cache" and self.cacheCleanupBlocked:
            self._set_save_status(self.cacheCleanupBlockedReason, level="warning")
            return

        if target == "logs":
            items = [
                {
                    "id": item["id"],
                    "label": item["label"],
                    "sizeText": item["size_text"],
                    "detail": item["path"],
                }
                for item in self._log_storage.get("items", [])
            ]
            title = "确认清理日志"
            summary = f"将清理 {len(items)} 个日志文件，共 {self.logUsageText}。"
        else:
            items = []
            for category in (self._cache_storage.get("categories") or {}).values():
                cleanable_files = int(category.get("cleanable_files") or 0)
                if cleanable_files <= 0:
                    continue
                paths = list(category.get("paths") or [])
                items.append(
                    {
                        "id": category["id"],
                        "label": category["label"],
                        "sizeText": format_size(category.get("cleanable_size") or 0),
                        "detail": f"{cleanable_files} 个文件"
                        + (f" · {paths[0]}" if paths else ""),
                    }
                )
            title = "确认清理缓存"
            cleanable_size = format_size(
                self._cache_storage.get("cleanable_size") or 0
            )
            summary = f"将清理 {len(items)} 类缓存，共 {cleanable_size}。"

        if not items:
            self._set_save_status("当前没有可清理的项目。")
            return
        self._cleanup_target = target
        self._cleanup_title = title
        self._cleanup_summary = summary
        self._cleanup_items = items
        self.cleanupPlanChanged.emit()
        self.cleanupDialogRequested.emit()

    def _clear_cleanup_plan(self) -> None:
        self._cleanup_target = ""
        self._cleanup_title = ""
        self._cleanup_summary = ""
        self._cleanup_items = []
        self.cleanupPlanChanged.emit()

    def _set_storage_busy(self, busy: bool) -> None:
        if self._storage_busy == busy:
            return
        self._storage_busy = busy
        self.storageBusyChanged.emit(busy)
        self.storageChanged.emit()

    @staticmethod
    def _empty_log_storage() -> dict:
        return {
            "total_size": 0,
            "total_size_text": "0 B",
            "total_files": 0,
            "items": [],
        }

    @staticmethod
    def _empty_cache_storage() -> dict:
        return {
            "total_size": 0,
            "total_files": 0,
            "cleanable_size": 0,
            "cleanable_files": 0,
            "categories": {},
        }

    def _confirm_live_save(self) -> bool:
        change_summary = self.pendingChangeSummary
        warning = ""
        if self.hasAutoConvertChanges:
            warning = "\n\n自动转码相关设置将在确认后生效。"
        result = QMessageBox.question(
            None,
            "应用设置",
            f"确认应用以下 {self.pendingChangeCount} 项修改？\n\n"
            f"{change_summary}{warning}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    @staticmethod
    def _resolve_theme_mode(value: str) -> str:
        normalized = str(value or "system").strip().lower()
        if normalized in {"black", "purple"}:
            return normalized
        return resolve_theme_mode(normalized)

    @staticmethod
    def _as_bool(value, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "y", "on"}:
                return True
            if normalized in {"false", "0", "no", "n", "off", ""}:
                return False
        return default

    @staticmethod
    def _apply_log_level(level: str) -> None:
        normalized = str(level or "INFO").strip().upper()
        numeric_level = getattr(logging, normalized, logging.INFO)
        logging.getLogger().setLevel(numeric_level)
