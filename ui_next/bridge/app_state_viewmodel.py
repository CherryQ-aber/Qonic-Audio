from __future__ import annotations

from PySide6.QtCore import Property, Signal, Slot

from ui_next.bridge.base_viewmodel import BaseViewModel
from ui_next.bridge.capabilities import CapabilityGate

try:
    from app_info import (
        APP_DISPLAY_NAME,
        APP_PROJECT_CLASSIFICATION,
        APP_RELEASE_CHANNEL,
        APP_STAGE,
        APP_VERSION,
    )
except ImportError:
    APP_DISPLAY_NAME = "Qonic Audio"
    APP_PROJECT_CLASSIFICATION = "Personal Software Project"
    APP_RELEASE_CHANNEL = "Internal Beta"
    APP_STAGE = "QML UI Preview"
    APP_VERSION = "Preview"


class AppStateViewModel(BaseViewModel):
    currentModuleKeyChanged = Signal(str)
    currentModuleNameChanged = Signal(str)
    currentModuleDescriptionChanged = Signal(str)
    currentWorkspaceKeyChanged = Signal(str)
    currentEditorPageKeyChanged = Signal(str)
    settingsOverlayOpenChanged = Signal(bool)
    legacyAnalysisOpenChanged = Signal(bool)
    statusSummaryChanged = Signal(str)

    _WORKSPACES = [
        {
            "key": "autoConvert",
            "title": "自动转码",
            "description": "监听目录、任务队列、输出格式和转码状态的集中工作区。",
        },
        {
            "key": "audioEditor",
            "title": "音频编辑",
            "description": "单曲导入、编辑草稿与内容处理的集中工作区。",
        },
    ]
    _EDITOR_PAGES = [
        {
            "key": "fileInfo",
            "title": "文件信息",
            "description": "音频技术信息、基础标签、扩展字段和文件摘要。",
        },
        {
            "key": "lyrics",
            "title": "歌词",
            "description": "歌词来源、正文预览、外置歌词导入与编辑草稿。",
        },
        {
            "key": "audioProcessing",
            "title": "音频处理",
            "description": "Pitch Shift、试听缓存与正式处理结果。",
        },
    ]
    _MODULES = [
        *_WORKSPACES,
        {
            "key": "metadata",
            "title": "文件信息",
            "description": _EDITOR_PAGES[0]["description"],
        },
        {
            "key": "lyricsCover",
            "title": "歌词",
            "description": _EDITOR_PAGES[1]["description"],
        },
        {
            "key": "audioProcessing",
            "title": "音频处理",
            "description": _EDITOR_PAGES[2]["description"],
        },
        {
            "key": "analysis",
            "title": "音频分析",
            "description": "BPM、Key Detection、波形、频谱和分析报告的兼容入口。",
        },
        {
            "key": "settings",
            "title": "设置",
            "description": "路径、工具、主题、缓存和运行选项的集中配置入口。",
        },
    ]
    _COMPATIBILITY_ROUTES = frozenset(
        (
            "autoConvert",
            "audioEditor",
            "metadata",
            "lyricsCover",
            "audioProcessing",
            "settings",
            "analysis",
        )
    )

    def __init__(self, capability_gate: CapabilityGate | None = None) -> None:
        gate = capability_gate or CapabilityGate()
        super().__init__(capability_gate=gate)
        self._current_workspace_key = "autoConvert"
        self._current_editor_page_key = "fileInfo"
        self._current_module_key = "autoConvert"
        self._settings_overlay_open = False
        self._legacy_analysis_open = False
        self._watch_status = "未监听"
        self._task_status = "无任务"
        self._runtime_mode = gate.userModeLabel
        self.set_status_message(
            f"{gate.userModeLabel} ready · 已启用功能：{gate.enabledFeatureSummary}"
        )

    @Property("QVariantList", constant=True)
    def workspaces(self) -> list[dict[str, str]]:
        return [dict(workspace) for workspace in self._WORKSPACES]

    @Property("QVariantList", constant=True)
    def editorPages(self) -> list[dict[str, str]]:
        return [dict(page) for page in self._EDITOR_PAGES]

    @Property("QVariantList", constant=True)
    def modules(self) -> list[dict[str, str]]:
        """Compatibility list for QML components that still consume module metadata."""
        return [dict(module) for module in self._MODULES]

    @Property(str, constant=True)
    def appName(self) -> str:
        return APP_DISPLAY_NAME

    @Property(str, constant=True)
    def versionLabel(self) -> str:
        return f"v{APP_VERSION} · {APP_RELEASE_CHANNEL}"

    @Property(str, constant=True)
    def stageLabel(self) -> str:
        return APP_STAGE

    @Property(str, constant=True)
    def releaseChannelLabel(self) -> str:
        return APP_RELEASE_CHANNEL

    @Property(str, constant=True)
    def projectClassification(self) -> str:
        return APP_PROJECT_CLASSIFICATION

    @Property(str, constant=True)
    def previewMode(self) -> str:
        return self._runtime_mode

    @Property(bool, constant=True)
    def isPreviewMode(self) -> bool:
        return self._capability_gate.previewMode

    @Property(bool, constant=True)
    def isLiveMode(self) -> bool:
        return self._capability_gate.liveMode

    @Property(str, constant=True)
    def enabledCapabilitiesText(self) -> str:
        return self._capability_gate.enabledFeatureSummary

    @Property(str, constant=True)
    def disabledCapabilitiesText(self) -> str:
        return self._capability_gate.safetySummary

    @Property(str, notify=currentWorkspaceKeyChanged)
    def currentWorkspaceKey(self) -> str:
        return self._current_workspace_key

    @Property(str, notify=currentEditorPageKeyChanged)
    def currentEditorPageKey(self) -> str:
        return self._current_editor_page_key

    @Property(str, constant=True)
    def currentAutoConvertFilterKey(self) -> str:
        return "all"

    @Property(bool, notify=settingsOverlayOpenChanged)
    def settingsOverlayOpen(self) -> bool:
        return self._settings_overlay_open

    @Property(bool, notify=legacyAnalysisOpenChanged)
    def legacyAnalysisOpen(self) -> bool:
        return self._legacy_analysis_open

    @Property(str, notify=currentModuleKeyChanged)
    def currentModuleKey(self) -> str:
        return self._current_module_key

    @Property(str, notify=currentModuleNameChanged)
    def currentModuleName(self) -> str:
        return self._current_module()["title"]

    @Property(str, notify=currentModuleDescriptionChanged)
    def currentModuleDescription(self) -> str:
        return self._current_module()["description"]

    @Property(str, notify=statusSummaryChanged)
    def statusSummary(self) -> str:
        return (
            f"{self._watch_status} / {self._task_status} / {self._runtime_mode}"
            f" / 已启用功能：{self._capability_gate.enabledFeatureSummary}"
        )

    @Property(str, notify=statusSummaryChanged)
    def currentStatus(self) -> str:
        return self.statusSummary

    @Slot(str, result=bool)
    def switchWorkspace(self, workspace_key: str) -> bool:
        if workspace_key not in {"autoConvert", "audioEditor"}:
            return self._reject_unknown("工作区", workspace_key)

        module_key = (
            "autoConvert"
            if workspace_key == "autoConvert"
            else self._module_key_for_editor_page(self._current_editor_page_key)
        )
        self._apply_navigation(
            workspace_key=workspace_key,
            module_key=module_key,
            legacy_analysis_open=False,
        )
        self.set_status_message(f"已切换到 {self._workspace_title(workspace_key)}")
        return True

    @Slot(str, result=bool)
    def switchEditorPage(self, page_key: str) -> bool:
        if page_key not in {"fileInfo", "lyrics", "audioProcessing"}:
            return self._reject_unknown("编辑页面", page_key)

        self._apply_navigation(
            workspace_key="audioEditor",
            editor_page_key=page_key,
            module_key=self._module_key_for_editor_page(page_key),
            legacy_analysis_open=False,
        )
        self.set_status_message(f"已切换到 {self._editor_page_title(page_key)}")
        return True

    @Slot(str, result=bool)
    def switchModule(self, module_key: str) -> bool:
        return self.setCurrentModule(module_key)

    @Slot(str, result=bool)
    def setCurrentModule(self, module_key: str) -> bool:
        if module_key not in self._COMPATIBILITY_ROUTES:
            return self._reject_unknown("模块", module_key)

        if module_key == "settings":
            self.openSettings()
            return True
        if module_key == "analysis":
            self._apply_navigation(
                module_key="analysis",
                legacy_analysis_open=True,
            )
            self.set_status_message("已打开音频分析兼容入口")
            return True
        if module_key == "autoConvert":
            self._apply_navigation(
                workspace_key="autoConvert",
                module_key="autoConvert",
                legacy_analysis_open=False,
            )
        else:
            page_key = {
                "audioEditor": "fileInfo",
                "metadata": "fileInfo",
                "lyricsCover": "lyrics",
                "audioProcessing": "audioProcessing",
            }[module_key]
            self._apply_navigation(
                workspace_key="audioEditor",
                editor_page_key=page_key,
                module_key=self._module_key_for_editor_page(page_key),
                legacy_analysis_open=False,
            )
        self.set_status_message(f"已切换到 {self.currentModuleName}")
        return True

    @Slot()
    def openSettings(self) -> None:
        if self._settings_overlay_open:
            return
        self._settings_overlay_open = True
        self.settingsOverlayOpenChanged.emit(True)
        self.set_status_message("已打开设置")

    @Slot()
    def closeSettings(self) -> None:
        if not self._settings_overlay_open:
            return
        self._settings_overlay_open = False
        self.settingsOverlayOpenChanged.emit(False)
        self.set_status_message("已关闭设置")

    @Slot()
    def closeLegacyAnalysis(self) -> None:
        if not self._legacy_analysis_open:
            return
        self._apply_navigation(
            module_key=self._module_key_for_current_workspace(),
            legacy_analysis_open=False,
        )
        self.set_status_message(
            f"已返回{self._workspace_title(self._current_workspace_key)}"
        )

    def _apply_navigation(
        self,
        *,
        workspace_key: str | None = None,
        editor_page_key: str | None = None,
        module_key: str | None = None,
        legacy_analysis_open: bool | None = None,
    ) -> bool:
        old_name = self.currentModuleName
        old_description = self.currentModuleDescription
        changed = False

        if (
            workspace_key is not None
            and workspace_key != self._current_workspace_key
        ):
            self._current_workspace_key = workspace_key
            self.currentWorkspaceKeyChanged.emit(workspace_key)
            changed = True
        if (
            editor_page_key is not None
            and editor_page_key != self._current_editor_page_key
        ):
            self._current_editor_page_key = editor_page_key
            self.currentEditorPageKeyChanged.emit(editor_page_key)
            changed = True
        if module_key is not None and module_key != self._current_module_key:
            self._current_module_key = module_key
            self.currentModuleKeyChanged.emit(module_key)
            changed = True
        if (
            legacy_analysis_open is not None
            and legacy_analysis_open != self._legacy_analysis_open
        ):
            self._legacy_analysis_open = legacy_analysis_open
            self.legacyAnalysisOpenChanged.emit(legacy_analysis_open)
            changed = True

        if self.currentModuleName != old_name:
            self.currentModuleNameChanged.emit(self.currentModuleName)
        if self.currentModuleDescription != old_description:
            self.currentModuleDescriptionChanged.emit(self.currentModuleDescription)
        return changed

    def _reject_unknown(self, route_type: str, route_key: str) -> bool:
        message = f"未知{route_type}: {route_key}"
        self.errorOccurred.emit(message)
        self.set_status_message(message)
        return False

    def _current_module(self) -> dict[str, str]:
        for module in self._MODULES:
            if module["key"] == self._current_module_key:
                return module
        return self._MODULES[0]

    def _workspace_title(self, workspace_key: str) -> str:
        for workspace in self._WORKSPACES:
            if workspace["key"] == workspace_key:
                return workspace["title"]
        return self._WORKSPACES[0]["title"]

    def _editor_page_title(self, page_key: str) -> str:
        for page in self._EDITOR_PAGES:
            if page["key"] == page_key:
                return page["title"]
        return self._EDITOR_PAGES[0]["title"]

    def _module_key_for_editor_page(self, page_key: str) -> str:
        return {
            "fileInfo": "metadata",
            "lyrics": "lyricsCover",
            "audioProcessing": "audioProcessing",
        }[page_key]

    def _module_key_for_current_workspace(self) -> str:
        if self._current_workspace_key == "autoConvert":
            return "autoConvert"
        return self._module_key_for_editor_page(self._current_editor_page_key)
