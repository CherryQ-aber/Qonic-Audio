from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import Property, QObject, Slot


METADATA_READ = "metadata_read"
LYRICS_READ = "lyrics_read"
COVER_READ = "cover_read"
SCAN_PREVIEW = "scan_preview"
SINGLE_FILE_CONVERT = "single_file_convert"
FOLDER_BROWSER = "folder_browser"

CONFIG_WRITE = "config_write"
WATCHER_CONTROL = "watcher_control"
QUEUE_MUTATION = "queue_mutation"
BATCH_CONVERT = "batch_convert"
LYRICS_WRITE = "lyrics_write"
METADATA_WRITE = "metadata_write"
COVER_WRITE = "cover_write"
OVERWRITE_FILE = "overwrite_file"
CACHE_CLEANUP = "cache_cleanup"
AUDIO_PLAYBACK = "audio_playback"
AUDIO_PROCESSING = "audio_processing"
AUDIO_EXPORT = "audio_export"

DEFAULT_USER_MODE = "default_user"
PREVIEW_MODE = "preview"
TEST_MODE = "test"

ALL_CAPABILITIES = (
    METADATA_READ,
    LYRICS_READ,
    COVER_READ,
    SCAN_PREVIEW,
    SINGLE_FILE_CONVERT,
    FOLDER_BROWSER,
    CONFIG_WRITE,
    WATCHER_CONTROL,
    QUEUE_MUTATION,
    BATCH_CONVERT,
    LYRICS_WRITE,
    METADATA_WRITE,
    COVER_WRITE,
    OVERWRITE_FILE,
    CACHE_CLEANUP,
    AUDIO_PLAYBACK,
    AUDIO_PROCESSING,
    AUDIO_EXPORT,
)

# These are retained as the Phase 4 / 5.6 compatibility subset.  Phase 5.7
# deliberately widens only the auto-convert workflow actions listed below;
# destructive overwrite and unrelated system actions remain denied.
PHASE4_PILOT_CAPABILITIES = frozenset(
    {
        METADATA_READ,
        LYRICS_READ,
        COVER_READ,
        SCAN_PREVIEW,
        SINGLE_FILE_CONVERT,
        FOLDER_BROWSER,
    }
)

PHASE57_ENABLED_CAPABILITIES = frozenset(
    {
        METADATA_READ,
        LYRICS_READ,
        COVER_READ,
        SCAN_PREVIEW,
        SINGLE_FILE_CONVERT,
        FOLDER_BROWSER,
        AUDIO_PLAYBACK,
        AUDIO_PROCESSING,
        AUDIO_EXPORT,
        METADATA_WRITE,
        LYRICS_WRITE,
        COVER_WRITE,
        CONFIG_WRITE,
        CACHE_CLEANUP,
        WATCHER_CONTROL,
        QUEUE_MUTATION,
        BATCH_CONVERT,
    }
)

# The normal QML launch profile contains every currently implemented action
# that is protected by an explicit confirmation boundary.  File outputs remain
# new files; cache/log cleanup is limited to inspected application-owned paths.
DEFAULT_USER_CAPABILITIES = PHASE57_ENABLED_CAPABILITIES

# Human acceptance uses this fixed profile instead of treating a broad Live
# switch as permission.  Settings writes and application-owned cache/log
# cleanup remain behind separate confirmation paths.
USER_TRIAL_CAPABILITIES = frozenset(
    {
        METADATA_READ,
        LYRICS_READ,
        COVER_READ,
        SCAN_PREVIEW,
        SINGLE_FILE_CONVERT,
        CONFIG_WRITE,
        CACHE_CLEANUP,
        WATCHER_CONTROL,
        QUEUE_MUTATION,
        BATCH_CONVERT,
        AUDIO_PLAYBACK,
        AUDIO_PROCESSING,
        AUDIO_EXPORT,
    }
)

_USER_FEATURE_GROUPS = (
    ((SCAN_PREVIEW,), "扫描"),
    ((FOLDER_BROWSER,), "文件浏览"),
    ((SINGLE_FILE_CONVERT, BATCH_CONVERT), "转换"),
    ((QUEUE_MUTATION,), "队列"),
    ((WATCHER_CONTROL,), "监听"),
    ((CONFIG_WRITE,), "配置保存"),
    ((CACHE_CLEANUP,), "日志与缓存清理"),
    ((METADATA_READ, LYRICS_READ, COVER_READ), "文件信息读取"),
    ((METADATA_WRITE, LYRICS_WRITE, COVER_WRITE), "文件信息编辑导出"),
    ((AUDIO_PLAYBACK,), "音频播放"),
    ((AUDIO_PROCESSING, AUDIO_EXPORT), "音频处理"),
)

# Compatibility export used by earlier QML safety tests and review tools.
PHASE4_ENABLED_CAPABILITIES = PHASE57_ENABLED_CAPABILITIES

ALWAYS_DISABLED_CAPABILITIES = (
    frozenset(ALL_CAPABILITIES) - PHASE57_ENABLED_CAPABILITIES
)


class CapabilityGate(QObject):
    """Immutable capability allowlist shared by all QML-facing ViewModels."""

    def __init__(
        self,
        requested_capabilities: object = (),
        *,
        runtime_mode: str = "auto",
        legacy_live_requested: bool = False,
        legacy_user_trial_requested: bool = False,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        requested = self._normalize_requested(requested_capabilities)
        known = tuple(name for name in requested if name in ALL_CAPABILITIES)
        unknown = tuple(name for name in requested if name not in ALL_CAPABILITIES)

        self._requested_capabilities = known
        self._unknown_capabilities = unknown
        self._enabled_capabilities = tuple(
            name
            for name in ALL_CAPABILITIES
            if name in known and name in PHASE57_ENABLED_CAPABILITIES
        )
        self._denied_capabilities = tuple(
            name
            for name in requested
            if name in unknown or name in ALWAYS_DISABLED_CAPABILITIES
        )
        if runtime_mode not in {DEFAULT_USER_MODE, PREVIEW_MODE, TEST_MODE}:
            runtime_mode = (
                PREVIEW_MODE if not self._enabled_capabilities else DEFAULT_USER_MODE
            )
        self._runtime_mode = runtime_mode
        self._legacy_live_requested = bool(legacy_live_requested)
        self._legacy_user_trial_requested = bool(legacy_user_trial_requested)

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> "CapabilityGate":
        """Compatibility facade for callers that previously parsed env here.

        Importing lazily avoids a module cycle while ensuring every startup-like
        caller uses the same centralized resolver as ``main_qml.py``.
        """
        from ui_next.bridge.runtime_mode import resolve_runtime_mode

        return resolve_runtime_mode(["main_qml.py"], environment).create_capability_gate()

    @Property(bool, constant=True)
    def previewMode(self) -> bool:
        return self._runtime_mode in {PREVIEW_MODE, TEST_MODE}

    @Property(bool, constant=True)
    def liveMode(self) -> bool:
        return self._runtime_mode == DEFAULT_USER_MODE

    @Property(bool, constant=True)
    def testMode(self) -> bool:
        return self._runtime_mode == TEST_MODE

    @Property(bool, constant=True)
    def defaultUserMode(self) -> bool:
        return self._runtime_mode == DEFAULT_USER_MODE

    @Property(str, constant=True)
    def modeLabel(self) -> str:
        if self.testMode:
            return "QML Test Mode"
        return "QML Preview Mode" if self.previewMode else "Default User Mode"

    @Property(str, constant=True)
    def userModeLabel(self) -> str:
        return "预览模式" if self.previewMode else "正常运行"

    @Property(bool, constant=True)
    def userTrialMode(self) -> bool:
        """Compatibility-only marker; it is no longer shown in product UI."""
        return self._legacy_user_trial_requested

    @Property("QStringList", constant=True)
    def enabledCapabilities(self) -> list[str]:
        return list(self._enabled_capabilities)

    @Property("QStringList", constant=True)
    def disabledCapabilities(self) -> list[str]:
        return [
            name for name in ALL_CAPABILITIES if name not in self._enabled_capabilities
        ]

    @Property("QStringList", constant=True)
    def deniedCapabilities(self) -> list[str]:
        return list(self._denied_capabilities)

    @Property("QStringList", constant=True)
    def unknownCapabilities(self) -> list[str]:
        return list(self._unknown_capabilities)

    @Property(str, constant=True)
    def enabledCapabilitiesText(self) -> str:
        return ", ".join(self._enabled_capabilities) or "无"

    @Property(str, constant=True)
    def disabledCapabilitiesText(self) -> str:
        return ", ".join(self.disabledCapabilities)

    @Property(str, constant=True)
    def deniedCapabilitiesText(self) -> str:
        return ", ".join(self._denied_capabilities) or "无"

    @Property(str, constant=True)
    def enabledFeatureSummary(self) -> str:
        labels = [
            label
            for capabilities, label in _USER_FEATURE_GROUPS
            if any(capability in self._enabled_capabilities for capability in capabilities)
        ]
        return "、".join(labels) or "无"

    @Property(str, constant=True)
    def deniedRequestSummary(self) -> str:
        if not self._denied_capabilities:
            return "无"
        return "已拒绝不受支持或未授权的额外请求"

    @Property(bool, constant=True)
    def sourceFileProtectionEnabled(self) -> bool:
        """The QML trial profile never grants source deletion or overwrite."""
        return True

    @Property(str, constant=True)
    def safetySummary(self) -> str:
        return (
            "禁止覆盖已有文件；源文件保护已启用；"
            "启动时不会自动扫描、监听或转换"
        )

    @Property(str, constant=True)
    def summary(self) -> str:
        return f"可用功能：{self.enabledFeatureSummary}"

    @Property(bool, constant=True)
    def legacyLiveRequested(self) -> bool:
        return self._legacy_live_requested

    @Slot(str, result=bool)
    def allows(self, capability: str) -> bool:
        return str(capability or "").strip().lower() in self._enabled_capabilities

    @Slot(str, result=str)
    def blockedMessage(self, capability: str) -> str:
        return "此操作当前不可用，未执行任何更改。"

    @staticmethod
    def _normalize_requested(value: object) -> tuple[str, ...]:
        if isinstance(value, str):
            raw_values = value.replace(";", ",").split(",")
        else:
            try:
                raw_values = list(value or ())
            except TypeError:
                raw_values = [value]

        normalized: list[str] = []
        for item in raw_values:
            name = str(item or "").strip().lower()
            if name and name not in normalized:
                normalized.append(name)
        return tuple(normalized)
