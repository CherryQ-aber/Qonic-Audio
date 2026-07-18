from __future__ import annotations

from PySide6.QtCore import Property, Signal, Slot

from ui_next.bridge.base_viewmodel import BaseViewModel
from ui_next.bridge.capabilities import CapabilityGate

try:
    from app_info import APP_DISPLAY_NAME, APP_STAGE, APP_VERSION
except ImportError:
    APP_DISPLAY_NAME = "CherryQ Audio Converter"
    APP_STAGE = "QML UI Preview"
    APP_VERSION = "Preview"


class AppStateViewModel(BaseViewModel):
    currentModuleKeyChanged = Signal(str)
    currentModuleNameChanged = Signal(str)
    currentModuleDescriptionChanged = Signal(str)
    statusSummaryChanged = Signal(str)

    _MODULES = [
        {
            "key": "autoConvert",
            "title": "自动转码",
            "description": "监听目录、任务队列、输出格式和转码状态的集中工作区。",
        },
        {
            "key": "audioEditor",
            "title": "音频编辑",
            "description": "单曲导入、音频播放、编辑草稿与内容处理的集中工作区。",
        },
        {
            "key": "metadata",
            "title": "文件信息",
            "description": "音频技术信息、基础标签、扩展字段和文件摘要的查看入口。",
        },
        {
            "key": "lyricsCover",
            "title": "歌词",
            "description": "歌词来源、正文预览、外置歌词导入与编辑草稿的工作区。",
        },
        {
            "key": "analysis",
            "title": "音频分析",
            "description": "BPM、Key Detection、波形、频谱和分析报告的预留工作区。",
        },
        {
            "key": "settings",
            "title": "设置",
            "description": "路径、工具、主题、缓存和运行选项的集中配置入口。",
        },
    ]

    def __init__(self, capability_gate: CapabilityGate | None = None) -> None:
        gate = capability_gate or CapabilityGate()
        super().__init__(capability_gate=gate)
        self._current_module_key = self._MODULES[0]["key"]
        self._watch_status = "未监听"
        self._task_status = "无任务"
        self._runtime_mode = gate.userModeLabel
        self.set_status_message(
            f"{gate.userModeLabel} ready · 已启用功能：{gate.enabledFeatureSummary}"
        )

    @Property("QVariantList", constant=True)
    def modules(self) -> list[dict[str, str]]:
        return [dict(module) for module in self._MODULES]

    @Property(str, constant=True)
    def appName(self) -> str:
        return APP_DISPLAY_NAME

    @Property(str, constant=True)
    def versionLabel(self) -> str:
        return f"v{APP_VERSION}"

    @Property(str, constant=True)
    def stageLabel(self) -> str:
        return APP_STAGE

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

    @Slot(str)
    def switchModule(self, module_key: str) -> None:
        if module_key == self._current_module_key:
            return
        if not self._module_exists(module_key):
            message = f"未知模块: {module_key}"
            self.errorOccurred.emit(message)
            self.set_status_message(message)
            return

        self._current_module_key = module_key
        self.currentModuleKeyChanged.emit(module_key)
        self.currentModuleNameChanged.emit(self.currentModuleName)
        self.currentModuleDescriptionChanged.emit(self.currentModuleDescription)
        self.set_status_message(f"已切换到 {self.currentModuleName}")

    @Slot(str)
    def setCurrentModule(self, module_key: str) -> None:
        self.switchModule(module_key)

    def _module_exists(self, module_key: str) -> bool:
        return any(module["key"] == module_key for module in self._MODULES)

    def _current_module(self) -> dict[str, str]:
        for module in self._MODULES:
            if module["key"] == self._current_module_key:
                return module
        return self._MODULES[0]
