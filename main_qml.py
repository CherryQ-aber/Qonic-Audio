import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from ui_next.bridge.app_state_viewmodel import AppStateViewModel
from ui_next.bridge.audio_player_viewmodel import AudioPlayerViewModel
from ui_next.bridge.audio_processing_session import ProcessingSessionViewModel
from ui_next.bridge.auto_convert_viewmodel import AutoConvertViewModel
from ui_next.bridge.runtime_mode import RuntimeModeParseError, resolve_runtime_mode
from ui_next.bridge.cover_viewmodel import CoverViewModel
from ui_next.bridge.edit_session import EditSessionViewModel
from ui_next.bridge.editor_file_browser_viewmodel import EditorFileBrowserViewModel
from ui_next.bridge.file_session_viewmodel import FileSessionViewModel
from ui_next.bridge.folder_browser_model import FolderBrowserModel
from ui_next.bridge.lyrics_viewmodel import LyricsViewModel
from ui_next.bridge.lyrics_sync_viewmodel import LyricsSyncViewModel
from ui_next.bridge.log_model import LogModel, install_log_model_handler
from ui_next.bridge.metadata_viewmodel import MetadataViewModel
from ui_next.bridge.settings_viewmodel import SettingsViewModel
from ui_next.bridge.task_queue_filter_proxy_model import (
    TaskQueueFilterProxyModel,
)
from ui_next.bridge.task_queue_model import TaskQueueModel
from ui_next.bridge.window_controller import WindowController

try:
    from app_info import APP_DISPLAY_NAME, APP_VERSION
except ImportError:
    APP_DISPLAY_NAME = "CherryQ Audio Converter"
    APP_VERSION = "QML Preview"


def _print_startup_error(message: str) -> None:
    print(f"[CherryQ QML UI] {message}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    raw_args = list(sys.argv if argv is None else argv)
    try:
        runtime_config = resolve_runtime_mode(raw_args)
    except RuntimeModeParseError as exc:
        _print_startup_error(str(exc))
        return 2

    requested_theme = os.environ.get("CHERRYQ_QML_THEME", "dark").strip().lower()
    qml_theme_mode = requested_theme if requested_theme in {"dark", "light"} else "dark"
    capability_gate = runtime_config.create_capability_gate()

    QQuickStyle.setStyle("Basic")
    app = QApplication(list(runtime_config.app_arguments))
    app.setApplicationName(APP_DISPLAY_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("CherryQ Studio")

    print(f"[CherryQ QML UI] 当前模式：{capability_gate.modeLabel}")
    print(f"[CherryQ QML UI] 可用功能：{capability_gate.enabledFeatureSummary}")
    if runtime_config.legacy_user_trial_requested:
        print("[CherryQ QML UI] 已兼容 CHERRYQ_QML_USER_TEST=1，并使用默认用户模式。")
    if runtime_config.legacy_capabilities_requested:
        print("[CherryQ QML UI] 已兼容 CHERRYQ_QML_CAPS 的受限启动配置。")
    if requested_theme not in {"dark", "light"}:
        print(
            "[CherryQ QML UI] CHERRYQ_QML_THEME 仅支持 dark/light；"
            "已回退深色主题。"
        )
    print(f"[CherryQ QML UI] 会话主题：{qml_theme_mode}")
    if runtime_config.legacy_live_requested:
        print(
            "[CherryQ QML UI] CHERRYQ_QML_LIVE=1 不再自动开放真实能力；"
            "普通启动已使用默认用户模式。"
        )

    project_root = Path(__file__).resolve().parent
    qml_root = project_root / "ui_next" / "qml"
    qml_entry = qml_root / "AppShell.qml"
    application_icon = project_root / "Assets" / "icon.ico"

    if application_icon.exists():
        app.setWindowIcon(QIcon(str(application_icon)))

    if not qml_entry.exists():
        _print_startup_error(f"QML entry not found: {qml_entry}")
        return 1

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(qml_root))

    def handle_qml_warnings(warnings) -> None:
        for warning in warnings:
            _print_startup_error(warning.toString())

    engine.warnings.connect(handle_qml_warnings)

    log_model = LogModel()
    install_log_model_handler(log_model)
    window_controller = WindowController(
        app,
        icon_path=application_icon if application_icon.exists() else None,
        smoke_test=runtime_config.smoke_test,
    )

    app_state = AppStateViewModel(capability_gate=capability_gate)
    if runtime_config.requested_module:
        if not app_state.setCurrentModule(runtime_config.requested_module):
            _print_startup_error(f"未知模块: {runtime_config.requested_module}")
            return 2
    if runtime_config.open_settings:
        app_state.openSettings()

    folder_browser_model = FolderBrowserModel(capability_gate=capability_gate)
    task_queue_model = TaskQueueModel(capability_gate=capability_gate)
    task_queue_filter_model = TaskQueueFilterProxyModel(task_queue_model)
    auto_convert_view_model = AutoConvertViewModel(
        task_queue_model,
        capability_gate=capability_gate,
    )
    metadata_view_model = MetadataViewModel(capability_gate=capability_gate)
    lyrics_view_model = LyricsViewModel(capability_gate=capability_gate)
    cover_view_model = CoverViewModel(capability_gate=capability_gate)
    file_session_view_model = FileSessionViewModel(capability_gate=capability_gate)
    file_session_view_model.attach_readers(
        metadata_view_model,
        lyrics_view_model,
        cover_view_model,
    )
    edit_session_view_model = EditSessionViewModel(capability_gate=capability_gate)
    file_session_view_model.attach_edit_session(edit_session_view_model)
    file_session_view_model.currentFileChanged.connect(
        edit_session_view_model.beginCurrentFile
    )
    file_session_view_model.currentFileReloaded.connect(
        edit_session_view_model.beginCurrentFile
    )
    file_session_view_model.currentFileCleared.connect(edit_session_view_model.clear)
    metadata_view_model.metadataReadApplied.connect(
        edit_session_view_model.loadMetadataResult
    )
    lyrics_view_model.lyricsReadApplied.connect(
        edit_session_view_model.loadLyricsResult
    )
    cover_view_model.coverReadApplied.connect(
        edit_session_view_model.loadCoverResult
    )
    file_session_view_model.setUnsavedChangesGuard(
        lambda: edit_session_view_model.hasUnsavedDrafts
    )
    edit_session_view_model.stateChanged.connect(
        file_session_view_model.notifyDraftStateChanged
    )
    editor_file_browser_view_model = EditorFileBrowserViewModel(
        capability_gate=capability_gate,
    )
    editor_file_browser_view_model.requestLoadSelected.connect(
        lambda path: file_session_view_model.setCurrentFile(path, "file_browser")
    )
    audio_player_view_model = AudioPlayerViewModel(
        file_session_view_model,
        capability_gate=capability_gate,
    )
    lyrics_sync_view_model = LyricsSyncViewModel(
        edit_session_view_model,
        audio_player_view_model,
    )
    edit_session_view_model.attach_runtime(
        file_session_view_model,
        audio_player_view_model,
    )
    processing_session_view_model = ProcessingSessionViewModel(
        file_session_view_model, audio_player_view_model, edit_session_view_model,
        capability_gate=capability_gate,
    )
    edit_session_view_model.attach_processing_session(
        processing_session_view_model
    )
    file_session_view_model.setFileChangeBlocker(
        lambda: (
            edit_session_view_model.anyExporting
            or processing_session_view_model.isBusy
            or audio_player_view_model.mediaOperationBusy
        )
    )
    settings_view_model = SettingsViewModel(
        log_model=log_model,
        capability_gate=capability_gate,
    )
    settings_view_model.configPersisted.connect(
        auto_convert_view_model.notify_settings_saved
    )
    settings_view_model.settingsChanged.connect(
        lambda: audio_player_view_model.setTimestampPrecision(
            settings_view_model.lyricsTimestampPrecision
        )
    )
    audio_player_view_model.setTimestampPrecision(
        settings_view_model.lyricsTimestampPrecision
    )

    def load_task_source_in_player(
        path: str,
        label: str,
        source_type: str,
        origin: str,
    ) -> None:
        audio_player_view_model.setPlaybackSourceWithOrigin(
            path,
            label,
            source_type,
            origin,
            False,
            0,
        )

    auto_convert_view_model.playbackSourceRequested.connect(
        load_task_source_in_player
    )

    def open_source_in_editor(path: str, source: str) -> None:
        result = file_session_view_model.setCurrentFile(path, source)
        if result not in {"blocked", "rejected"}:
            app_state.switchEditorPage("fileInfo")

    def open_task_source_in_editor(path: str) -> None:
        open_source_in_editor(path, "audio_editor")

    def open_folder_source_in_editor(path: str) -> None:
        open_source_in_editor(path, "folder_tree")

    auto_convert_view_model.editorFileRequested.connect(
        open_task_source_in_editor
    )

    folder_browser_model.playbackRequested.connect(
        load_task_source_in_player
    )
    folder_browser_model.editorRequested.connect(
        open_folder_source_in_editor
    )
    folder_browser_model.enqueueRequested.connect(
        auto_convert_view_model.enqueue_folder_browser_file
    )

    app.aboutToQuit.connect(auto_convert_view_model.shutdown)
    app.aboutToQuit.connect(folder_browser_model.shutdown)
    app.aboutToQuit.connect(editor_file_browser_view_model.shutdown)
    app.aboutToQuit.connect(processing_session_view_model.shutdown)
    app.aboutToQuit.connect(edit_session_view_model.shutdown)
    app.aboutToQuit.connect(audio_player_view_model.shutdown)
    app.aboutToQuit.connect(file_session_view_model.shutdown)
    app.aboutToQuit.connect(window_controller.shutdown)
    window_controller.settingsRequested.connect(app_state.openSettings)

    engine.rootContext().setContextProperty("appState", app_state)
    engine.rootContext().setContextProperty(
        "folderBrowserModel",
        folder_browser_model,
    )
    engine.rootContext().setContextProperty("taskQueueModel", task_queue_model)
    engine.rootContext().setContextProperty(
        "taskQueueFilterModel",
        task_queue_filter_model,
    )
    engine.rootContext().setContextProperty("autoConvertViewModel", auto_convert_view_model)
    engine.rootContext().setContextProperty("fileSessionViewModel", file_session_view_model)
    engine.rootContext().setContextProperty(
        "editorFileBrowserViewModel",
        editor_file_browser_view_model,
    )
    engine.rootContext().setContextProperty("audioPlayerViewModel", audio_player_view_model)
    engine.rootContext().setContextProperty("processingSessionViewModel", processing_session_view_model)
    engine.rootContext().setContextProperty("metadataViewModel", metadata_view_model)
    engine.rootContext().setContextProperty("editSessionViewModel", edit_session_view_model)
    engine.rootContext().setContextProperty("lyricsViewModel", lyrics_view_model)
    engine.rootContext().setContextProperty(
        "lyricsSyncViewModel",
        lyrics_sync_view_model,
    )
    engine.rootContext().setContextProperty("coverViewModel", cover_view_model)
    engine.rootContext().setContextProperty("settingsViewModel", settings_view_model)
    engine.rootContext().setContextProperty("logModel", log_model)
    engine.rootContext().setContextProperty("windowController", window_controller)
    engine.rootContext().setContextProperty(
        "qmlApplicationIconUrl",
        QUrl.fromLocalFile(str(application_icon)) if application_icon.exists() else QUrl(),
    )
    engine.rootContext().setContextProperty("capabilityGate", capability_gate)
    engine.rootContext().setContextProperty("qmlThemeMode", qml_theme_mode)
    engine.rootContext().setContextProperty(
        "qmlPreviewMode",
        capability_gate.previewMode,
    )
    engine.rootContext().setContextProperty(
        "qmlLiveMode",
        capability_gate.liveMode,
    )
    engine.rootContext().setContextProperty(
        "qmlTestMode",
        capability_gate.testMode,
    )
    engine.load(QUrl.fromLocalFile(str(qml_entry)))

    if not engine.rootObjects():
        _print_startup_error(f"Failed to load QML entry: {qml_entry}")
        return 1

    window_controller.attach_window(engine.rootObjects()[0])
    window_controller.showInitialWindow()

    if runtime_config.smoke_test:
        QTimer.singleShot(250, app.quit)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
