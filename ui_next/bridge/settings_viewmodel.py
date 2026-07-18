from __future__ import annotations

import logging
import os

from PySide6.QtCore import Property, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QMessageBox

from config import (
    CONFIG_FILE,
    get_cache_folder,
    load_config,
    save_config,
)
from formats import DEFAULT_TARGET_FORMAT, SUPPORTED_TARGET_FORMATS, normalize_target_format
from logger import LOG_DIR, LOG_FILE
from ui_next.bridge.base_viewmodel import BaseViewModel
from ui_next.bridge.capabilities import CONFIG_WRITE, CapabilityGate
from ui_next.bridge.log_model import LogModel


class SettingsViewModel(BaseViewModel):
    settingsChanged = Signal()
    saveStatusChanged = Signal(str)
    hasPendingChangesChanged = Signal(bool)
    configPersisted = Signal()

    _PATH_KEYS = {
        "watch_folder": "监听目录",
        "output_folder": "自动转码输出目录",
        "editor_output_folder": "音频编辑输出目录",
    }
    _KNOWN_KEYS = {
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
    }
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
        self._save_status = self._PREVIEW_SAFETY_MESSAGE
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
            return "当前无草稿修改"
        if self.previewMode:
            return "有未应用草稿 · 草稿未写入磁盘 · 预览模式不会保存"
        return "有未应用草稿 · 确认后才会写入 config.json"

    @Property("QVariantMap", notify=settingsChanged)
    def currentConfig(self) -> dict:
        return dict(self._current_config)

    @Property("QVariantMap", notify=settingsChanged)
    def pendingConfig(self) -> dict:
        return dict(self._pending_config)

    @Slot()
    def reload(self) -> None:
        self.reloadConfig()

    @Slot()
    def reloadConfig(self) -> None:
        self._current_config = load_config()
        self._pending_config = dict(self._current_config)
        self._set_pending_changes(False)
        self.settingsChanged.emit()
        self._set_save_status(
            "已重新读取真实配置并恢复页面显示；未影响旧 Widgets UI 或后台任务。"
        )

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

    @Slot(str)
    def setThemeMode(self, value: str) -> None:
        normalized = str(value or "system").strip().lower()
        if normalized not in {"system", "dark", "light"}:
            normalized = "system"
        self.updatePendingValue("theme_mode", normalized)

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
            self._set_save_status(
                "已模拟保存页面草稿；草稿未写入 config.json，"
                "不会影响旧 Widgets UI 或后台任务。",
                level="warning" if self.previewMode else "info",
            )
        else:
            self._set_save_status("当前无草稿修改；没有需要模拟保存的内容。")

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
            self._set_save_status(
                f"{blocked_message} 未调用 save_config；"
                "config.json、旧 Widgets UI 和后台任务均未改变。",
                level="warning",
            )
            return

        if not self._has_pending_changes:
            self._set_save_status("当前无草稿修改；config.json 未改变。")
            return

        if not self._confirm_live_save():
            self._set_save_status("已取消写入 config.json；页面草稿仍保留。")
            return

        # Merge only QML-supported keys onto the newest on-disk config.  This
        # keeps Legacy-only/unknown fields intact while preventing a stale UI
        # draft from writing arbitrary fields back to disk.
        config_to_save = load_config()
        for key in self._KNOWN_KEYS:
            if key in self._pending_config:
                config_to_save[key] = self._pending_config[key]
        self._current_config = save_config(config_to_save)
        self._pending_config = dict(self._current_config)
        self._set_pending_changes(False)
        self.settingsChanged.emit()
        self._apply_log_level(self.logLevel)
        self.configPersisted.emit()
        self._set_save_status(f"设置草稿已确认写入 {CONFIG_FILE}")

    @Slot()
    def discardPendingChanges(self) -> None:
        self._pending_config = dict(self._current_config)
        self._set_pending_changes(False)
        self.settingsChanged.emit()
        self._set_save_status(
            "已放弃页面草稿并恢复真实配置显示；config.json 未改变。"
        )

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
        if normalized_key == "lyrics_timestamp_precision":
            self._set_save_status(
                "时间点精度已在本次会话中预览；"
                + (
                    "未写入 config.json。"
                    if self.previewMode
                    else "保存并确认后才会作为下次启动默认值。"
                ),
                level="warning" if self.previewMode else "info",
            )
        elif self.previewMode:
            self._set_save_status(
                "草稿不生效：修改仅保存在当前页面内存，未写入 config.json，"
                "不会影响旧 Widgets UI 或后台任务。",
                level="warning",
            )
        else:
            self._set_save_status(
                "修改已进入页面草稿；仍需点击保存并二次确认。"
            )

    def _set_pending_changes(self, value: bool) -> None:
        if self._has_pending_changes == value:
            return
        self._has_pending_changes = value
        self.hasPendingChangesChanged.emit(value)

    def _set_save_status(self, message: str, level: str = "info") -> None:
        self._save_status = message
        self.saveStatusChanged.emit(message)
        self.set_status_message(message)

        if level == "warning":
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
            return normalized if normalized in {"system", "dark", "light"} else "system"
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

    def _confirm_live_save(self) -> bool:
        result = QMessageBox.question(
            None,
            "保存设置",
            f"确定要将设置草稿写入 config.json 吗？\n\n{CONFIG_FILE}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

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
