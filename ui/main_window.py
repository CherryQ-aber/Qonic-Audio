import logging
import os
import subprocess
import threading

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStyle,
    QStackedWidget,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import cache_manager
import watcher
from app_info import APP_DISPLAY_NAME, APP_WINDOW_TITLE
from config import (
    APP_NAME,
    find_watch_folder_candidates,
    get_auto_start_monitor,
    get_copy_lrc_to_output,
    get_create_format_subfolder,
    get_embed_lyrics_after_convert,
    get_output_folder,
    get_overwrite_existing_lyrics,
    get_scan_existing_on_start,
    get_target_format,
    get_theme_mode,
    get_watch_folder,
    is_first_launch_completed,
    is_valid_watch_folder,
    load_config,
    save_config,
)
from formats import get_target_format_options, get_target_label
from ui.audio_editor import AudioEditorWorkspace
from ui.status_widgets import StatusCard
from ui.theme import apply_theme
from ui.widgets import make_hard_edge_combo_box

THEME_MODE_OPTIONS = [
    ("跟随系统", "system"),
    ("浅色", "light"),
    ("深色", "dark"),
]

class QTextEditLogger(logging.Handler):

    def __init__(self, emitter):
        super().__init__()
        self.emitter = emitter

    def emit(self, record):
        msg = self.format(record)
        self.emitter.log_signal.emit(msg)


class LogEmitter(QObject):
    log_signal = Signal(str)


class DropEnabledTableWidget(QTableWidget):
    files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return

        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return

        super().dragMoveEvent(event)

    def dropEvent(self, event):
        if not event.mimeData().hasUrls():
            super().dropEvent(event)
            return

        file_paths = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.toLocalFile()
        ]

        if file_paths:
            self.files_dropped.emit(file_paths)

        event.acceptProposedAction()


class WatcherThread(QThread):

    def __init__(self, watch_folder, parent=None):
        super().__init__(parent)
        self.watch_folder = watch_folder
        self.stop_event = threading.Event()

    def run(self):
        watcher.start_watch(
            stop_event=self.stop_event,
            watch_folder=self.watch_folder
        )

    def stop(self):
        self.stop_event.set()


class ConvertThread(QThread):

    def __init__(
        self,
        default_target_format,
        output_root_override=None,
        create_format_subfolder=None,
        file_paths=None,
        parent=None,
    ):
        super().__init__(parent)
        self.default_target_format = default_target_format
        self.output_root_override = output_root_override
        self.create_format_subfolder = create_format_subfolder
        self.file_paths = set(file_paths) if file_paths is not None else None

    def run(self):
        from converter import convert_audio

        for task in watcher.get_convertible_tasks():
            if self.isInterruptionRequested():
                logging.info("收到停止转换信号，将在当前文件完成后结束")
                break

            file_path = task["path"]
            if self.file_paths is not None and file_path not in self.file_paths:
                continue

            file_name = task["filename"]
            input_path = task["input_path"]
            is_ncm_task = task["is_ncm_task"]
            target_format = task.get("target_format") or self.default_target_format

            try:
                if not watcher.has_pending_file(file_path):
                    continue

                if watcher.get_pending_file_status(file_path) != watcher.WAITING_STATUS:
                    continue

                if not watcher.set_pending_file_status(file_path, watcher.PROCESSING_STATUS):
                    logging.warning(f"无法更新文件状态，已跳过: {file_name}")
                    continue

                if is_ncm_task:
                    logging.info(f"NCM 解码任务开始转换: {file_name}")

                result = convert_audio(
                    input_path,
                    target_format,
                    output_root_override=self.output_root_override,
                    create_format_subfolder=self.create_format_subfolder,
                    preserve_source=True,
                    original_source_path=file_path,
                    lyrics_source_paths=[file_path, input_path],
                )
                success = (
                    result.get("success", False)
                    if isinstance(result, dict)
                    else bool(result)
                )

                if success:
                    watcher.set_pending_file_status(file_path, watcher.COMPLETED_STATUS)
                    watcher.clear_processed_file(file_path)

                    if is_ncm_task:
                        watcher.cleanup_task_runtime_files(file_path)
                        logging.info(f"NCM 转换完成，状态已更新: {file_name}")
                    else:
                        logging.info(f"转换成功，状态已更新: {file_name}")
                else:
                    watcher.set_pending_file_status(file_path, watcher.FAILED_STATUS)
                    watcher.clear_processed_file(file_path)

                    if is_ncm_task:
                        watcher.cleanup_task_runtime_files(file_path)
                        logging.warning(
                            f"NCM 转换失败，任务已保留在列表中，可修复后重试: {file_name}"
                        )
                    else:
                        logging.warning(
                            f"转换失败，文件已保留在列表中，可修复后重试: {file_name}"
                        )

            except Exception as e:
                watcher.set_pending_file_status(file_path, watcher.FAILED_STATUS)
                watcher.clear_processed_file(file_path)
                if is_ncm_task:
                    watcher.cleanup_task_runtime_files(file_path)
                logging.exception(f"转换线程处理失败: {file_name} - {e}")

    def stop(self):
        self.requestInterruption()


class ScanThread(QThread):
    scan_progress = Signal(dict)
    scan_finished = Signal(dict)

    def __init__(self, watch_folder, parent=None):
        super().__init__(parent)
        self.watch_folder = watch_folder
        self.stop_event = threading.Event()

    def run(self):
        summary = watcher.scan_existing_files(
            self.watch_folder,
            stop_event=self.stop_event,
            progress_callback=self.scan_progress.emit,
            return_summary=True
        )
        self.scan_finished.emit(summary)

    def stop(self):
        self.stop_event.set()


class RetryThread(QThread):
    retry_finished = Signal(dict)

    def __init__(self, file_paths, parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.stop_event = threading.Event()

    def run(self):
        summary = watcher.retry_failed_files(
            self.file_paths,
            stop_event=self.stop_event
        )
        self.retry_finished.emit(summary)

    def stop(self):
        self.stop_event.set()


class QueuePrepareThread(QThread):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.stop_event = threading.Event()

    def run(self):
        watcher.prepare_pending_files(
            stop_event=self.stop_event,
            keep_running=True,
        )

    def stop(self):
        self.stop_event.set()


class CacheScanThread(QThread):
    scan_finished = Signal(dict)

    def run(self):
        self.scan_finished.emit(cache_manager.scan_cache())


class CacheClearThread(QThread):
    clear_finished = Signal(dict)

    def __init__(self, categories=None, parent=None):
        super().__init__(parent)
        self.categories = categories

    def run(self):
        self.clear_finished.emit(
            cache_manager.clear_cache(categories=self.categories)
        )


class MainWindow(QMainWindow):

    def __init__(self, safe_start=False):
        super().__init__()

        self.safe_start = bool(safe_start)
        self.config_data = load_config()
        self.thread = None
        self.convert_thread = None
        self.scan_thread = None
        self.retry_thread = None
        self.prepare_thread = None
        self.cache_scan_thread = None
        self.cache_clear_thread = None
        self.last_cache_scan = None
        self.cache_scan_summary = None
        self.pending_cache_clear_after_scan = False
        self.rescan_cache_after_clear = False
        self.timer = None
        self.is_quitting = False
        cache_manager.ensure_cache_dirs()

        self.setWindowTitle(APP_WINDOW_TITLE)
        self.resize(1440, 900)
        self.setMinimumSize(960, 620)

        self.overview_label = QLabel()
        self.overview_label.setWordWrap(True)
        self.overview_label.setVisible(False)

        # =========================
        # 日志系统
        # =========================
        self.log_emitter = LogEmitter()
        self.log_emitter.log_signal.connect(self.append_log)

        self.gui_handler = QTextEditLogger(self.log_emitter)
        self.gui_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s"
            )
        )
        logging.getLogger().addHandler(self.gui_handler)

        # =========================
        # 监听目录
        # =========================
        self.watch_label = QLabel(
            f"监听目录:\n{get_watch_folder()}"
        )
        self.watch_label.setObjectName("PathLabel")
        self.watch_label.setWordWrap(True)

        self.watch_button = QPushButton("选择监听目录")
        self.watch_button.clicked.connect(
            self.select_watch_folder
        )

        self.open_watch_button = QPushButton("打开监听目录")
        self.open_watch_button.clicked.connect(
            self.open_watch_folder
        )

        watch_button_layout = QHBoxLayout()
        watch_button_layout.addWidget(self.watch_button)
        watch_button_layout.addWidget(self.open_watch_button)

        # =========================
        # 输出目录
        # =========================
        self.output_label = QLabel(
            f"输出目录:\n{get_output_folder()}"
        )
        self.output_label.setObjectName("PathLabel")
        self.output_label.setWordWrap(True)

        self.output_button = QPushButton("选择输出目录")
        self.output_button.clicked.connect(
            self.select_output_folder
        )

        self.open_output_button = QPushButton("打开输出目录")
        self.open_output_button.clicked.connect(
            self.open_output_folder
        )

        output_button_layout = QHBoxLayout()
        output_button_layout.addWidget(self.output_button)
        output_button_layout.addWidget(self.open_output_button)

        # =========================
        # 输出格式
        # =========================
        self.format_label = QLabel("输出格式")

        self.format_combo = make_hard_edge_combo_box()
        for target_format in get_target_format_options():
            self.format_combo.addItem(
                get_target_label(target_format),
                target_format,
            )

        format_index = self.format_combo.findData(get_target_format())
        self.format_combo.setCurrentIndex(max(format_index, 0))
        self.format_combo.currentIndexChanged.connect(
            self.change_format
        )

        self.theme_label = QLabel("界面主题")
        self.theme_combo = make_hard_edge_combo_box()

        for label, mode in THEME_MODE_OPTIONS:
            self.theme_combo.addItem(label, mode)

        theme_index = self.theme_combo.findData(get_theme_mode())
        self.theme_combo.setCurrentIndex(max(theme_index, 0))
        self.theme_combo.currentIndexChanged.connect(self.change_theme_mode)

        # =========================
        # 自动化选项
        # =========================
        self.auto_start_checkbox = QCheckBox("启动后自动监听")
        self.auto_start_checkbox.setChecked(
            get_auto_start_monitor()
        )
        self.auto_start_checkbox.stateChanged.connect(
            self.change_auto_start_monitor
        )

        self.scan_on_start_checkbox = QCheckBox("启动监听时扫描已有文件")
        self.scan_on_start_checkbox.setChecked(
            get_scan_existing_on_start()
        )
        self.scan_on_start_checkbox.stateChanged.connect(
            self.change_scan_existing_on_start
        )

        self.format_subfolder_checkbox = QCheckBox("按目标格式创建子文件夹")
        self.format_subfolder_checkbox.setChecked(
            get_create_format_subfolder()
        )
        self.format_subfolder_checkbox.stateChanged.connect(
            self.change_create_format_subfolder
        )

        self.embed_lyrics_checkbox = QCheckBox("转换后写入内嵌歌词")
        self.embed_lyrics_checkbox.setChecked(
            get_embed_lyrics_after_convert()
        )
        self.embed_lyrics_checkbox.stateChanged.connect(
            self.change_embed_lyrics_after_convert
        )

        self.copy_lrc_checkbox = QCheckBox("输出时保留外置 .lrc 文件")
        self.copy_lrc_checkbox.setChecked(
            get_copy_lrc_to_output()
        )
        self.copy_lrc_checkbox.stateChanged.connect(
            self.change_copy_lrc_to_output
        )

        self.overwrite_lyrics_checkbox = QCheckBox("覆盖已有歌词")
        self.overwrite_lyrics_checkbox.setToolTip(
            "默认关闭，避免覆盖音频中已有的歌词标签"
        )
        self.overwrite_lyrics_checkbox.setChecked(
            get_overwrite_existing_lyrics()
        )
        self.overwrite_lyrics_checkbox.stateChanged.connect(
            self.change_overwrite_existing_lyrics
        )

        self.scan_existing_button = QPushButton("扫描已有文件")
        self.scan_existing_button.clicked.connect(
            self.start_scan_existing_files
        )

        self.scan_status_label = QLabel("扫描状态: 空闲")
        self.scan_status_label.setObjectName("MutedLabel")

        self.cache_status_label = QLabel("当前缓存: 未扫描")
        self.cache_status_label.setObjectName("MutedLabel")
        self.cache_status_label.setWordWrap(True)

        self.cache_detail_label = QLabel("仅清理 Temp/Cache，不影响源文件。")
        self.cache_detail_label.setObjectName("MutedLabel")
        self.cache_detail_label.setWordWrap(True)

        self.scan_cache_button = QPushButton("扫描缓存大小")
        self.scan_cache_button.setToolTip("统计程序 Temp/Cache 缓存大小，不会清理文件")
        self.scan_cache_button.setStatusTip("统计程序 Temp/Cache 缓存大小，不会清理文件")
        self.scan_cache_button.clicked.connect(self.start_cache_scan)

        self.clear_cache_button = QPushButton("清理缓存...")
        self.clear_cache_button.setToolTip("需先扫描到可清理缓存；仅清理 Temp/Cache，不影响源文件")
        self.clear_cache_button.setStatusTip("需先扫描到可清理缓存；仅清理 Temp/Cache，不影响源文件")
        self.clear_cache_button.clicked.connect(self.start_cache_clear)

        # =========================
        # 文件列表
        # =========================
        self.file_table = DropEnabledTableWidget()
        self.file_table.setColumnCount(4)
        self.file_table.setHorizontalHeaderLabels([
            "文件名",
            "原格式",
            "目标格式",
            "状态"
        ])
        self.file_table.setSelectionBehavior(
            QTableWidget.SelectRows
        )
        self.file_table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.file_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table_header = self.file_table.horizontalHeader()
        table_header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch
        )
        table_header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Fixed
        )
        table_header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.Fixed
        )
        table_header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Fixed
        )
        table_header.setFixedHeight(30)
        table_header.setSectionsMovable(False)
        table_header.setStretchLastSection(False)
        table_header.setHighlightSections(False)
        vertical_header = self.file_table.verticalHeader()
        vertical_header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        vertical_header.setDefaultSectionSize(32)
        vertical_header.setMinimumSectionSize(32)
        vertical_header.setSectionsMovable(False)
        vertical_header.setHighlightSections(False)
        self.file_table.setColumnWidth(1, 76)
        self.file_table.setColumnWidth(2, 190)
        self.file_table.setColumnWidth(3, 112)
        self.file_table.setAlternatingRowColors(True)
        self.file_table.setMinimumHeight(320)
        self.file_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.file_table.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.file_table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.file_table.itemSelectionChanged.connect(
            self.on_table_selection_changed
        )
        self.file_table.files_dropped.connect(
            self.handle_dropped_files
        )
        self.file_table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.file_table.customContextMenuRequested.connect(
            self.show_file_table_context_menu
        )

        self.remove_button = QPushButton("移除选中条目")
        self.remove_button.clicked.connect(
            self.remove_selected_items
        )

        self.clear_terminal_button = QPushButton("清除已完成/失败记录")
        self.clear_terminal_button.clicked.connect(
            self.clear_terminal_items
        )

        self.retry_failed_button = QPushButton("重试失败条目")
        self.retry_failed_button.clicked.connect(
            self.retry_failed_items
        )

        self.batch_format_combo = make_hard_edge_combo_box()
        self.batch_format_combo.addItem("跟随全局", None)

        for target_format in get_target_format_options():
            self.batch_format_combo.addItem(
                get_target_label(target_format),
                target_format,
            )

        self.selection_target_combo = make_hard_edge_combo_box()
        self.selection_target_combo.addItem("跟随全局", None)

        for target_format in get_target_format_options():
            self.selection_target_combo.addItem(
                get_target_label(target_format),
                target_format,
            )

        self.selection_apply_target_button = QPushButton("应用")
        self.selection_apply_target_button.clicked.connect(
            self.apply_selection_target_format
        )

        self.selection_remove_button = QPushButton("移除条目")
        self.selection_remove_button.clicked.connect(
            self.remove_selected_items
        )

        self.selection_retry_button = QPushButton("重试失败条目")
        self.selection_retry_button.clicked.connect(
            self.retry_failed_items
        )

        self.open_file_location_button = QPushButton("打开位置")
        self.open_file_location_button.clicked.connect(
            self.open_selected_file_location
        )

        self.copy_file_path_button = QPushButton("复制路径")
        self.copy_file_path_button.clicked.connect(
            self.copy_selected_file_path
        )

        self.open_decoded_location_button = QPushButton("打开产物位置")
        self.open_decoded_location_button.clicked.connect(
            self.open_selected_decoded_location
        )

        self.copy_decoded_path_button = QPushButton("复制产物路径")
        self.copy_decoded_path_button.clicked.connect(
            self.copy_selected_decoded_path
        )

        for button in (
            self.open_file_location_button,
            self.copy_file_path_button,
            self.open_decoded_location_button,
            self.copy_decoded_path_button,
            self.selection_apply_target_button,
            self.selection_remove_button,
            self.selection_retry_button,
        ):
            button.setProperty("compact", True)
            button.setMinimumWidth(0)

        self.apply_batch_format_button = QPushButton("应用到选中")
        self.apply_batch_format_button.clicked.connect(
            self.apply_batch_target_format
        )

        self.reset_batch_format_button = QPushButton("选中跟随全局")
        self.reset_batch_format_button.clicked.connect(
            self.reset_selected_target_formats
        )

        for button in (
            self.apply_batch_format_button,
            self.reset_batch_format_button,
            self.remove_button,
            self.clear_terminal_button,
            self.retry_failed_button,
        ):
            button.setProperty("compact", True)
            button.setMinimumWidth(0)

        # =========================
        # 开始监听按钮
        # =========================
        self.start_button = QPushButton("开始监听")
        self.start_button.clicked.connect(
            self.start_monitor
        )

        self.stop_button = QPushButton("停止监听")
        self.stop_button.clicked.connect(
            self.stop_monitor
        )
        self.stop_button.setEnabled(False)

        monitor_button_layout = QHBoxLayout()
        monitor_button_layout.addWidget(self.start_button)
        monitor_button_layout.addWidget(self.stop_button)

        # =========================
        # 开始转换按钮
        # =========================
        self.convert_button = QPushButton("开始转换")
        self.convert_button.clicked.connect(
            self.start_convert
        )

        self.convert_to_button = QPushButton("转换到...")
        self.convert_to_button.clicked.connect(
            self.start_convert_to
        )
        self.convert_button.setMinimumWidth(0)
        self.convert_to_button.setMinimumWidth(0)

        # =========================
        # 日志窗口
        # =========================
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.append("GUI 已启动")
        if self.safe_start:
            self.log_box.append(
                "Legacy Safe Start：自动监听、扫描与配置写入已禁用。"
            )

        # =========================
        # 主窗口框架
        # =========================
        self._build_tray()
        self._build_main_shell(
            monitor_button_layout,
            watch_button_layout,
            output_button_layout,
        )
        if self.safe_start:
            self._apply_safe_start_ui_state()
        self.update_overview_label()
        self.start_file_list_timer()
        QTimer.singleShot(0, self.run_startup_flow)

    def _build_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(
            self.style().standardIcon(
                QStyle.StandardPixmap.SP_ComputerIcon
            )
        )

        tray_menu = QMenu()

        self.tray_show_action = QAction("显示窗口", self)
        self.tray_settings_action = QAction("打开设置", self)
        self.tray_monitor_action = QAction("开始监听", self)
        self.tray_scan_action = QAction("扫描已有文件", self)
        self.tray_convert_action = QAction("开始转换", self)
        self.tray_quit_action = QAction("退出程序", self)

        self.tray_show_action.triggered.connect(self.show_window)
        self.tray_settings_action.triggered.connect(self.show_settings_window)
        self.tray_monitor_action.triggered.connect(self.toggle_monitor_from_tray)
        self.tray_scan_action.triggered.connect(self.start_scan_existing_files)
        self.tray_convert_action.triggered.connect(self.start_convert)
        self.tray_quit_action.triggered.connect(self.quit_app)

        tray_menu.addAction(self.tray_show_action)
        tray_menu.addAction(self.tray_settings_action)
        tray_menu.addSeparator()
        tray_menu.addAction(self.tray_monitor_action)
        tray_menu.addAction(self.tray_scan_action)
        tray_menu.addAction(self.tray_convert_action)
        tray_menu.addSeparator()
        tray_menu.addAction(self.tray_quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()
        self.update_tray_actions()

    def _build_main_shell(
        self,
        monitor_button_layout,
        watch_button_layout,
        output_button_layout,
    ):
        shell = QWidget()
        shell.setObjectName("AppShell")
        root_layout = QVBoxLayout(shell)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(12)

        self.workspace_tabs = QTabWidget()
        self.workspace_tabs.setObjectName("WorkspaceTabs")
        self.workspace_tabs.addTab(
            self.build_converter_workspace(
                monitor_button_layout,
                watch_button_layout,
                output_button_layout,
            ),
            "自动转码",
        )
        self.workspace_tabs.addTab(
            self.build_audio_editor_workspace(),
            "音频编辑",
        )

        root_layout.addWidget(self.workspace_tabs, 1)

        self.setCentralWidget(shell)
        self._set_active_nav(0)

    def build_converter_workspace(
        self,
        monitor_button_layout,
        watch_button_layout,
        output_button_layout,
    ):
        workspace = QWidget()
        root_layout = QVBoxLayout(workspace)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(12)

        root_layout.addWidget(self._build_top_status_bar())

        content_layout = QHBoxLayout()
        content_layout.setSpacing(12)
        content_layout.addWidget(self._build_nav_bar())

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_dashboard_page(monitor_button_layout))
        self.pages.addWidget(self._build_queue_page())
        self.pages.addWidget(self._build_settings_page(watch_button_layout, output_button_layout))
        content_layout.addWidget(self.pages, 1)

        root_layout.addLayout(content_layout, 1)
        root_layout.addWidget(self._build_log_panel())

        return workspace

    def build_audio_editor_workspace(self):
        self.audio_editor_workspace = AudioEditorWorkspace(
            self,
            log_callback=self.append_log,
            config_saver=self._save_config_if_allowed,
        )
        return self.audio_editor_workspace

    def _build_top_status_bar(self):
        bar = QFrame()
        bar.setObjectName("TopStatusBar")
        layout = QGridLayout(bar)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.monitor_card = StatusCard("监听状态", "未监听")
        self.format_card = StatusCard("默认输出格式", get_target_format().upper())
        self.waiting_card = StatusCard("等待处理", "0")
        self.processing_card = StatusCard("处理中", "0")
        self.completed_card = StatusCard("已完成", "0")
        self.failed_card = StatusCard("失败", "0")

        cards = [
            self.monitor_card,
            self.format_card,
            self.waiting_card,
            self.processing_card,
            self.completed_card,
            self.failed_card,
        ]

        for column, card in enumerate(cards):
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            layout.addWidget(card, 0, column)

        return bar

    def _build_nav_bar(self):
        nav = QFrame()
        nav.setObjectName("NavBar")
        nav.setFixedWidth(160)
        layout = QVBoxLayout(nav)
        layout.setContentsMargins(12, 14, 12, 14)
        layout.setSpacing(8)

        title = QLabel(APP_DISPLAY_NAME)
        title.setObjectName("NavTitle")
        layout.addWidget(title)
        layout.addSpacing(8)

        self.nav_buttons = []
        for index, text in enumerate(["总览", "任务队列", "设置"]):
            button = QPushButton(text)
            button.setProperty("nav", True)
            button.clicked.connect(lambda _checked=False, page=index: self.show_page(page))
            self.nav_buttons.append(button)
            layout.addWidget(button)

        layout.addStretch(1)
        return nav

    def _build_dashboard_page(self, monitor_button_layout):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel("总览")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        action_pane = QFrame()
        action_pane.setObjectName("DashboardActionPane")
        action_layout = QVBoxLayout(action_pane)
        action_layout.setContentsMargins(14, 14, 14, 14)
        action_layout.setSpacing(10)

        section_title = QLabel("快捷操作")
        section_title.setObjectName("SectionTitle")
        action_layout.addWidget(section_title)
        action_layout.addLayout(monitor_button_layout)
        action_layout.addWidget(self.scan_existing_button)
        action_layout.addWidget(self.scan_status_label)

        self.dashboard_watch_label = QLabel()
        self.dashboard_watch_label.setObjectName("PathLabel")
        self.dashboard_watch_label.setWordWrap(True)
        self.dashboard_output_label = QLabel()
        self.dashboard_output_label.setObjectName("PathLabel")
        self.dashboard_output_label.setWordWrap(True)
        action_layout.addWidget(self.dashboard_watch_label)
        action_layout.addWidget(self.dashboard_output_label)

        layout.addWidget(action_pane)
        layout.addStretch(1)
        return page

    def _build_queue_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        title = QLabel("任务队列")
        title.setObjectName("PageTitle")
        drop_hint = QLabel("可将音频文件拖入此处加入任务队列")
        drop_hint.setObjectName("MutedLabel")

        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(8)
        title_layout.addWidget(title)
        title_layout.addStretch(1)
        title_layout.addWidget(drop_hint)
        layout.addLayout(title_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("QueueSplitter")
        splitter.setChildrenCollapsible(False)

        table_area = QWidget()
        table_layout = QVBoxLayout(table_area)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(6)
        table_layout.addWidget(self.file_table, 1)

        context_hint = QLabel("提示：右键任务条目可进行格式设置、重试、移除等操作。")
        context_hint.setObjectName("MutedLabel")
        table_layout.addWidget(context_hint)

        task_action_layout = QHBoxLayout()
        task_action_layout.setSpacing(6)
        task_action_layout.addWidget(self.remove_button)
        task_action_layout.addWidget(self.clear_terminal_button)
        task_action_layout.addWidget(self.retry_failed_button)
        task_action_layout.addStretch(1)
        task_action_layout.addWidget(self.convert_button)
        task_action_layout.addWidget(self.convert_to_button)
        table_layout.addLayout(task_action_layout)

        selection_panel = self._build_selection_panel()
        selection_panel.setMinimumWidth(320)
        selection_panel.setMaximumWidth(420)
        selection_panel.setFixedWidth(350)

        splitter.addWidget(table_area)
        splitter.addWidget(selection_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([760, 350])

        layout.addWidget(splitter, 1)

        return page

    def _build_selection_panel(self):
        panel = QFrame()
        panel.setObjectName("SelectionPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("选中条目")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("SelectionScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(10)

        self.selection_empty_label = QLabel(
            "未选择条目。点击任务队列中的文件以查看详情，也可拖入音频文件加入队列。"
        )
        self.selection_empty_label.setObjectName("MutedLabel")
        self.selection_empty_label.setWordWrap(True)
        scroll_layout.addWidget(self.selection_empty_label)

        self.single_selection_panel = QFrame()
        self.single_selection_panel.setObjectName("SelectionDetailPane")
        single_layout = QGridLayout(self.single_selection_panel)
        single_layout.setContentsMargins(0, 0, 0, 0)
        single_layout.setHorizontalSpacing(8)
        single_layout.setVerticalSpacing(6)
        single_layout.setColumnStretch(0, 0)
        single_layout.setColumnStretch(1, 1)

        self.selection_file_name_value = QLabel()
        self.selection_format_value = QLabel()
        self.selection_target_value = QLabel()
        self.selection_status_value = QLabel()
        self.selection_directory_value = self._make_detail_path_field()
        self.selection_path_value = self._make_detail_path_field()
        self.selection_decoded_directory_value = self._make_detail_path_field()
        self.selection_decoded_path_value = self._make_detail_path_field()

        simple_fields = [
            ("文件名", self.selection_file_name_value),
            ("原格式", self.selection_format_value),
            ("目标格式", self.selection_target_value),
            ("状态", self.selection_status_value),
        ]

        for row, (label_text, value_label) in enumerate(simple_fields):
            label = QLabel(label_text)
            label.setObjectName("DetailLabel")
            value_label.setObjectName("DetailValue")
            value_label.setWordWrap(True)
            single_layout.addWidget(label, row, 0)
            single_layout.addWidget(value_label, row, 1)

        detail_row = len(simple_fields)
        single_layout.addWidget(self._make_detail_label("所在目录"), detail_row, 0)
        single_layout.addWidget(self.selection_directory_value, detail_row, 1)

        detail_row += 1
        single_layout.addWidget(self._make_detail_label("完整路径"), detail_row, 0)
        single_layout.addWidget(self.selection_path_value, detail_row, 1)

        detail_row += 1
        path_button_layout = QHBoxLayout()
        path_button_layout.setSpacing(6)
        path_button_layout.addWidget(self.copy_file_path_button)
        path_button_layout.addStretch(1)
        single_layout.addLayout(path_button_layout, detail_row, 1)

        detail_row += 1
        path_open_layout = QHBoxLayout()
        path_open_layout.setSpacing(6)
        path_open_layout.addWidget(self.open_file_location_button)
        path_open_layout.addStretch(1)
        single_layout.addLayout(path_open_layout, detail_row, 1)

        detail_row += 1
        single_layout.addWidget(self._make_detail_label("解码产物目录"), detail_row, 0)
        single_layout.addWidget(self.selection_decoded_directory_value, detail_row, 1)

        detail_row += 1
        single_layout.addWidget(self._make_detail_label("解码产物路径"), detail_row, 0)
        single_layout.addWidget(self.selection_decoded_path_value, detail_row, 1)

        detail_row += 1
        decoded_button_layout = QHBoxLayout()
        decoded_button_layout.setSpacing(6)
        decoded_button_layout.addWidget(self.copy_decoded_path_button)
        decoded_button_layout.addStretch(1)
        single_layout.addLayout(decoded_button_layout, detail_row, 1)

        detail_row += 1
        decoded_open_layout = QHBoxLayout()
        decoded_open_layout.setSpacing(6)
        decoded_open_layout.addWidget(self.open_decoded_location_button)
        decoded_open_layout.addStretch(1)
        single_layout.addLayout(decoded_open_layout, detail_row, 1)

        detail_row += 1
        single_layout.addWidget(QLabel("编辑目标格式"), detail_row, 0)
        single_edit_layout = QHBoxLayout()
        single_edit_layout.addWidget(self.selection_target_combo, 1)
        single_edit_layout.addWidget(self.selection_apply_target_button)
        single_layout.addLayout(single_edit_layout, detail_row, 1)

        detail_row += 1
        single_button_layout = QHBoxLayout()
        single_button_layout.addWidget(self.selection_remove_button)
        single_button_layout.addWidget(self.selection_retry_button)
        single_button_layout.addStretch(1)
        single_layout.addLayout(single_button_layout, detail_row, 0, 1, 2)
        scroll_layout.addWidget(self.single_selection_panel)

        self.multi_selection_panel = QFrame()
        self.multi_selection_panel.setObjectName("SelectionDetailPane")
        multi_layout = QVBoxLayout(self.multi_selection_panel)
        multi_layout.setContentsMargins(0, 0, 0, 0)
        multi_layout.setSpacing(8)

        self.selection_summary_values = {}
        summary_grid = QGridLayout()
        summary_grid.setContentsMargins(0, 0, 0, 0)
        summary_grid.setHorizontalSpacing(12)
        summary_grid.setVerticalSpacing(5)
        summary_rows = [
            ("selected", "已选择"),
            ("queued", "已入队"),
            ("waiting", "等待处理"),
            ("processing", "处理中"),
            ("completed", "已完成"),
            ("failed", "失败"),
            ("reading", "读取中"),
            ("skipped", "已跳过"),
        ]

        for row, (key, label_text) in enumerate(summary_rows):
            label = self._make_detail_label(label_text)
            value = QLabel("0 个")
            value.setObjectName("DetailValue")
            self.selection_summary_values[key] = value
            summary_grid.addWidget(label, row, 0)
            summary_grid.addWidget(value, row, 1)

        multi_layout.addLayout(summary_grid)

        batch_label = QLabel("批量目标格式")
        batch_label.setObjectName("DetailLabel")
        multi_layout.addWidget(batch_label)

        batch_format_layout = QHBoxLayout()
        batch_format_layout.addWidget(self.batch_format_combo, 1)
        batch_format_layout.addWidget(self.apply_batch_format_button)
        multi_layout.addLayout(batch_format_layout)

        batch_button_layout = QVBoxLayout()
        batch_button_layout.setSpacing(6)
        batch_button_layout.addWidget(self.reset_batch_format_button)
        multi_layout.addLayout(batch_button_layout)
        scroll_layout.addWidget(self.multi_selection_panel)
        scroll_layout.addStretch(1)

        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area, 1)

        self.single_selection_panel.setVisible(False)
        self.multi_selection_panel.setVisible(False)
        return panel

    def _make_detail_path_field(self):
        field = QLineEdit()
        field.setObjectName("DetailPathField")
        field.setReadOnly(True)
        field.setMinimumWidth(0)
        return field

    def _make_detail_label(self, text):
        label = QLabel(text)
        label.setObjectName("DetailLabel")
        return label

    def _build_settings_page(self, watch_button_layout, output_button_layout):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel("设置")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        self.settings_panel = QFrame()
        self.settings_panel.setObjectName("SettingsPane")
        settings_layout = QVBoxLayout(self.settings_panel)
        settings_layout.setContentsMargins(14, 14, 14, 14)
        settings_layout.setSpacing(12)

        path_group = QGroupBox("路径设置")
        path_group_layout = QVBoxLayout(path_group)
        path_group_layout.setSpacing(8)
        path_group_layout.addWidget(self.watch_label)
        path_group_layout.addLayout(watch_button_layout)
        path_group_layout.addWidget(self.output_label)
        path_group_layout.addLayout(output_button_layout)

        output_group = QGroupBox("输出设置")
        output_group_layout = QVBoxLayout(output_group)
        output_group_layout.setSpacing(8)
        output_group_layout.addWidget(self.format_label)
        output_group_layout.addWidget(self.format_combo)
        output_group_layout.addWidget(self.format_subfolder_checkbox)

        lyrics_group = QGroupBox("歌词 / 元数据选项")
        lyrics_group_layout = QVBoxLayout(lyrics_group)
        lyrics_group_layout.setSpacing(8)
        lyrics_group_layout.addWidget(self.embed_lyrics_checkbox)
        lyrics_group_layout.addWidget(self.copy_lrc_checkbox)
        lyrics_group_layout.addWidget(self.overwrite_lyrics_checkbox)

        theme_group = QGroupBox("主题设置")
        theme_group_layout = QVBoxLayout(theme_group)
        theme_group_layout.setSpacing(8)
        theme_group_layout.addWidget(self.theme_label)
        theme_group_layout.addWidget(self.theme_combo)

        monitor_group = QGroupBox("自动监听")
        monitor_group_layout = QVBoxLayout(monitor_group)
        monitor_group_layout.setSpacing(8)
        monitor_group_layout.addWidget(self.auto_start_checkbox)
        monitor_group_layout.addWidget(self.scan_on_start_checkbox)

        settings_layout.addWidget(path_group)
        settings_layout.addWidget(output_group)
        settings_layout.addWidget(lyrics_group)
        settings_layout.addWidget(theme_group)
        settings_layout.addWidget(monitor_group)
        settings_layout.addWidget(self._build_cache_management_panel())

        self.settings_toggle_button = QPushButton("打开设置页")
        self.settings_toggle_button.clicked.connect(self.toggle_settings_panel)
        self.settings_toggle_button.setVisible(False)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("SettingsScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(0)
        scroll_layout.addWidget(self.settings_panel)
        scroll_layout.addStretch(1)
        scroll_area.setWidget(scroll_content)

        layout.addWidget(scroll_area, 1)
        return page

    def _build_cache_management_panel(self):
        panel = QGroupBox("缓存管理")
        layout = QVBoxLayout(panel)
        layout.setSpacing(8)

        safety_hint = QLabel("仅清理 Temp/Cache，不影响源文件。")
        safety_hint.setObjectName("MutedLabel")
        safety_hint.setWordWrap(True)
        layout.addWidget(safety_hint)
        layout.addWidget(self.cache_status_label)
        layout.addWidget(self.cache_detail_label)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(6)
        button_layout.addWidget(self.scan_cache_button)
        button_layout.addWidget(self.clear_cache_button)
        button_layout.addStretch(1)
        layout.addLayout(button_layout)

        return panel

    def _build_log_panel(self):
        panel = QFrame()
        panel.setObjectName("LogPanel")
        self.log_panel = panel
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("日志")
        title.setObjectName("SectionTitle")
        self.log_toggle_button = QPushButton("展开日志")
        self.log_toggle_button.clicked.connect(self.toggle_log_panel)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.log_toggle_button)

        self.log_box.setVisible(False)
        self.log_box.setMinimumHeight(100)
        self.log_box.setMaximumHeight(160)
        self.log_panel.setMaximumHeight(52)
        layout.addLayout(header)
        layout.addWidget(self.log_box)

        return panel

    def show_page(self, index):
        if hasattr(self, "workspace_tabs"):
            self.workspace_tabs.setCurrentIndex(0)

        self.pages.setCurrentIndex(index)
        self._set_active_nav(index)

    def _set_active_nav(self, active_index):
        for index, button in enumerate(self.nav_buttons):
            button.setProperty("active", index == active_index)
            button.style().unpolish(button)
            button.style().polish(button)

    def toggle_log_panel(self):
        is_visible = not self.log_box.isVisible()
        self.log_box.setVisible(is_visible)
        self.log_panel.setMaximumHeight(220 if is_visible else 52)
        self.log_toggle_button.setText("收起日志" if is_visible else "展开日志")

    def on_table_selection_changed(self):
        self.update_selection_panel()

    def show_file_table_context_menu(self, position):
        self._select_context_menu_row(position)
        menu = self._build_file_table_context_menu()
        menu.exec(self.file_table.viewport().mapToGlobal(position))

    def _availability_tip(self, reason):
        return f"当前不可用：{reason}" if reason else ""

    def _set_widget_availability_hint(self, widget, enabled, disabled_reason="", enabled_tip=""):
        tip = enabled_tip if enabled else MainWindow._availability_tip(self, disabled_reason)
        if hasattr(widget, "setToolTip"):
            widget.setToolTip(tip)
        if hasattr(widget, "setStatusTip"):
            widget.setStatusTip(tip)

    def _set_action_availability(self, action, enabled, disabled_reason="", enabled_tip=""):
        action.setEnabled(enabled)
        tip = enabled_tip if enabled else MainWindow._availability_tip(self, disabled_reason)
        action.setToolTip(tip)
        action.setStatusTip(tip)

    def _select_context_menu_row(self, position):
        index = self.file_table.indexAt(position)

        if not index.isValid():
            self.file_table.clearSelection()
            return

        row = index.row()
        selected_rows = {
            selected_index.row()
            for selected_index in self.file_table.selectionModel().selectedRows()
        }

        if row in selected_rows:
            return

        self.file_table.clearSelection()
        self.file_table.selectRow(row)

    def _build_file_table_context_menu(self):
        state = self.get_file_table_context_menu_state()

        menu = QMenu(self)

        start_selected_action = menu.addAction("开始转换选中条目")
        MainWindow._set_action_availability(
            self,
            start_selected_action,
            state["can_start_selected"],
            state["start_selected_reason"],
            "仅转换当前选中的等待条目",
        )
        start_selected_action.triggered.connect(
            lambda _checked=False: self.start_convert_selected()
        )

        start_all_action = menu.addAction("开始转换全部等待条目")
        MainWindow._set_action_availability(
            self,
            start_all_action,
            state["can_start_all"],
            state["start_all_reason"],
            "转换队列中全部等待条目",
        )
        start_all_action.triggered.connect(
            lambda _checked=False: self.start_convert()
        )

        menu.addSeparator()

        format_menu = menu.addMenu("设置目标格式")
        MainWindow._set_action_availability(
            self,
            format_menu.menuAction(),
            state["can_set_format"],
            state["set_format_reason"],
            "修改选中等待条目的目标格式",
        )

        follow_action = format_menu.addAction("跟随全局")
        MainWindow._set_action_availability(
            self,
            follow_action,
            state["can_set_format"],
            state["set_format_reason"],
            "让选中条目跟随全局目标格式",
        )
        follow_action.triggered.connect(
            lambda _checked=False: self._set_selected_target_format_from_menu(None)
        )

        for target_format in ("mp3", "flac", "wav", "aac", "ogg"):
            action = format_menu.addAction(get_target_label(target_format))
            MainWindow._set_action_availability(
                self,
                action,
                state["can_set_format"],
                state["set_format_reason"],
                f"将选中等待条目的目标格式设置为 {get_target_label(target_format)}",
            )
            action.triggered.connect(
                lambda _checked=False, value=target_format: self._set_selected_target_format_from_menu(value)
            )

        menu.addSeparator()

        retry_action = menu.addAction("重试失败条目")
        MainWindow._set_action_availability(
            self,
            retry_action,
            state["can_retry_failed"],
            state["retry_failed_reason"],
            "重新入列选中的失败条目",
        )
        retry_action.triggered.connect(
            lambda _checked=False: self.retry_failed_items()
        )

        remove_action = menu.addAction("移除选中条目")
        MainWindow._set_action_availability(
            self,
            remove_action,
            state["can_remove_selected"],
            state["remove_selected_reason"],
            "从队列中移除选中条目，不删除源文件",
        )
        remove_action.triggered.connect(
            lambda _checked=False: self.remove_selected_items()
        )

        clear_action = menu.addAction("清除已完成/失败记录")
        MainWindow._set_action_availability(
            self,
            clear_action,
            state["can_clear_terminal"],
            state["clear_terminal_reason"],
            "清除已完成、失败或跳过的队列记录",
        )
        clear_action.triggered.connect(
            lambda _checked=False: self.clear_terminal_items()
        )

        menu.addSeparator()

        open_action = menu.addAction("打开源文件位置")
        MainWindow._set_action_availability(
            self,
            open_action,
            state["can_open_source"],
            state["open_source_reason"],
            "在资源管理器中定位第一个选中源文件",
        )
        open_action.triggered.connect(
            lambda _checked=False: self.open_selected_source_location()
        )

        copy_action = menu.addAction("复制源文件路径")
        MainWindow._set_action_availability(
            self,
            copy_action,
            state["can_copy_paths"],
            "未选择任务条目",
            "复制选中条目的源文件路径",
        )
        copy_action.triggered.connect(
            lambda _checked=False: self.copy_selected_source_paths()
        )

        status_action = menu.addAction("查看任务状态")
        MainWindow._set_action_availability(
            self,
            status_action,
            state["can_show_status"],
            "未选择任务条目",
            "查看选中条目的详细状态",
        )
        status_action.triggered.connect(
            lambda _checked=False: self.show_selected_task_status()
        )

        return menu

    def get_file_table_context_menu_state(self):
        selected_tasks = self._get_selected_tasks()
        all_tasks = watcher.get_task_snapshots()
        has_selection = bool(selected_tasks)
        selected_statuses = [task.get("status") for task in selected_tasks]
        has_processing_selected = watcher.PROCESSING_STATUS in selected_statuses
        has_waiting_selected = watcher.WAITING_STATUS in selected_statuses
        has_failed_selected = watcher.FAILED_STATUS in selected_statuses
        has_any_waiting = any(
            task.get("status") == watcher.WAITING_STATUS
            for task in all_tasks
        )
        has_clearable_terminal = any(
            task.get("status") in watcher.CLEARABLE_TERMINAL_STATUSES
            for task in all_tasks
        )
        first_selected_path = selected_tasks[0].get("path") if selected_tasks else ""
        first_source_exists = bool(first_selected_path and os.path.exists(first_selected_path))
        convert_running = self._is_convert_thread_running()
        retry_running = self._is_retry_thread_running()
        start_selected_reason = (
            "转换任务正在运行"
            if convert_running else
            "请选择等待转换的条目"
        )
        start_all_reason = (
            "转换任务正在运行"
            if convert_running else
            "队列中没有等待转换的条目"
        )
        set_format_reason = (
            "请选择等待转换的条目"
            if not has_selection else
            "只有等待转换的条目可以修改目标格式"
        )
        retry_failed_reason = (
            "失败重试任务正在运行"
            if retry_running else
            "请选择失败条目"
        )
        remove_selected_reason = (
            "未选择任务条目"
            if not has_selection else
            "正在处理的条目不能移除"
        )
        clear_terminal_reason = "没有已完成、失败或跳过的记录"
        open_source_reason = (
            "未选择任务条目"
            if not has_selection else
            "源文件不存在或路径不可访问"
        )

        return {
            "has_selection": has_selection,
            "has_waiting_selected": has_waiting_selected,
            "has_failed_selected": has_failed_selected,
            "has_processing_selected": has_processing_selected,
            "has_any_waiting": has_any_waiting,
            "has_clearable_terminal": has_clearable_terminal,
            "can_start_selected": has_selection and has_waiting_selected and not convert_running,
            "can_start_all": has_any_waiting and not convert_running,
            "can_set_format": has_selection and has_waiting_selected and not has_processing_selected,
            "can_retry_failed": has_selection and has_failed_selected and not retry_running,
            "can_remove_selected": has_selection and not has_processing_selected,
            "can_clear_terminal": has_clearable_terminal,
            "can_open_source": has_selection and first_source_exists,
            "can_copy_paths": has_selection,
            "can_show_status": has_selection,
            "start_selected_reason": start_selected_reason,
            "start_all_reason": start_all_reason,
            "set_format_reason": set_format_reason,
            "retry_failed_reason": retry_failed_reason,
            "remove_selected_reason": remove_selected_reason,
            "clear_terminal_reason": clear_terminal_reason,
            "open_source_reason": open_source_reason,
        }

    def update_selection_panel(self):
        if self._is_selection_target_combo_active():
            return

        selected_paths = self._get_selected_file_paths()
        selected_tasks = [
            task
            for path in selected_paths
            if (task := self._get_task_by_path(path)) is not None
        ]

        if not selected_tasks:
            self.selection_empty_label.setVisible(True)
            self.single_selection_panel.setVisible(False)
            self.multi_selection_panel.setVisible(False)
            return

        self.selection_empty_label.setVisible(False)

        if len(selected_tasks) == 1:
            self._show_single_selection(selected_tasks[0])
            return

        self._show_multi_selection(selected_tasks)

    def _show_single_selection(self, task):
        self.single_selection_panel.setVisible(True)
        self.multi_selection_panel.setVisible(False)

        status_display = watcher.get_status_display(task["status"])
        selected_format = task.get("target_format")
        target_index = 0

        if selected_format:
            target_index = self.selection_target_combo.findData(selected_format)

        self.selection_file_name_value.setText(task["filename"])
        self.selection_format_value.setText(task["format"])
        self.selection_target_value.setText(
            self._format_target_format_display(task)
        )
        self.selection_status_value.setText(
            f"{status_display['label']} - {status_display['detail']}"
        )
        file_path = task["path"]
        decoded_path = task.get("decoded_path")
        file_dir = os.path.dirname(file_path) or "无"
        decoded_dir = os.path.dirname(decoded_path) if decoded_path else "无"

        self._set_path_field(self.selection_directory_value, file_dir)
        self._set_path_field(self.selection_path_value, file_path)
        self._set_path_field(self.selection_decoded_directory_value, decoded_dir)
        self._set_path_field(
            self.selection_decoded_path_value,
            decoded_path or "无",
        )

        self.selection_target_combo.blockSignals(True)
        self.selection_target_combo.setCurrentIndex(max(target_index, 0))
        self.selection_target_combo.blockSignals(False)

        can_change = task.get("can_change_target_format", False)
        can_retry = task.get("can_retry", False)
        can_remove = task["status"] != watcher.PROCESSING_STATUS

        self.selection_target_combo.setEnabled(can_change)
        self.selection_apply_target_button.setEnabled(can_change)
        self.selection_retry_button.setEnabled(
            can_retry and not self._is_retry_thread_running()
        )
        self.selection_retry_button.setVisible(can_retry)
        self.selection_remove_button.setEnabled(can_remove)
        self.open_file_location_button.setEnabled(
            self._can_open_path_location(file_path)
        )
        self.copy_file_path_button.setEnabled(bool(file_path))
        self.open_decoded_location_button.setEnabled(
            bool(decoded_path) and self._can_open_path_location(decoded_path)
        )
        self.copy_decoded_path_button.setEnabled(bool(decoded_path))
        self.open_decoded_location_button.setVisible(bool(decoded_path))
        self.copy_decoded_path_button.setVisible(bool(decoded_path))
        self._set_widget_availability_hint(
            self.selection_target_combo,
            can_change,
            "只有等待转换的条目可以修改目标格式",
            "修改当前条目的目标格式",
        )
        self._set_widget_availability_hint(
            self.selection_apply_target_button,
            can_change,
            "只有等待转换的条目可以应用目标格式",
            "应用当前选择的目标格式",
        )
        self._set_widget_availability_hint(
            self.selection_retry_button,
            can_retry and not self._is_retry_thread_running(),
            "请选择失败条目，或等待当前重试任务结束",
            "重新入列当前失败条目",
        )
        self._set_widget_availability_hint(
            self.selection_remove_button,
            can_remove,
            "正在处理的条目不能移除",
            "从队列中移除当前条目，不删除源文件",
        )
        self._set_widget_availability_hint(
            self.open_file_location_button,
            self._can_open_path_location(file_path),
            "源文件不存在或路径不可访问",
            "在资源管理器中定位源文件",
        )
        self._set_widget_availability_hint(
            self.copy_file_path_button,
            bool(file_path),
            "当前条目没有源文件路径",
            "复制源文件路径",
        )
        self._set_widget_availability_hint(
            self.open_decoded_location_button,
            bool(decoded_path) and self._can_open_path_location(decoded_path),
            "当前条目没有可打开的解码产物",
            "在资源管理器中定位解码产物",
        )
        self._set_widget_availability_hint(
            self.copy_decoded_path_button,
            bool(decoded_path),
            "当前条目没有解码产物路径",
            "复制解码产物路径",
        )

    def _show_multi_selection(self, tasks):
        self.single_selection_panel.setVisible(False)
        self.multi_selection_panel.setVisible(True)

        counts = {}
        for task in tasks:
            status = task["status"]
            counts[status] = counts.get(status, 0) + 1

        summary_values = {
            "selected": len(tasks),
            "queued": counts.get(watcher.QUEUED_STATUS, 0),
            "waiting": counts.get(watcher.WAITING_STATUS, 0),
            "processing": counts.get(watcher.PROCESSING_STATUS, 0),
            "completed": counts.get(watcher.COMPLETED_STATUS, 0),
            "failed": counts.get(watcher.FAILED_STATUS, 0),
            "reading": counts.get(watcher.READING_STATUS, 0),
            "skipped": counts.get(watcher.SKIPPED_STATUS, 0),
        }

        for key, count in summary_values.items():
            self.selection_summary_values[key].setText(f"{count} 个")

        has_changeable = any(
            task.get("can_change_target_format", False)
            for task in tasks
        )
        has_retryable = any(task.get("can_retry", False) for task in tasks)
        has_removable = any(
            task["status"] != watcher.PROCESSING_STATUS
            for task in tasks
        )

        self.batch_format_combo.setEnabled(has_changeable)
        self.apply_batch_format_button.setEnabled(has_changeable)
        self.reset_batch_format_button.setEnabled(has_changeable)
        self.retry_failed_button.setEnabled(
            has_retryable and not self._is_retry_thread_running()
        )
        self.retry_failed_button.setVisible(True)
        self.remove_button.setEnabled(has_removable)
        retry_enabled = has_retryable and not self._is_retry_thread_running()
        self._set_widget_availability_hint(
            self.batch_format_combo,
            has_changeable,
            "选中项中没有可修改格式的等待条目",
            "批量选择选中等待条目的目标格式",
        )
        self._set_widget_availability_hint(
            self.apply_batch_format_button,
            has_changeable,
            "选中项中没有可应用格式的等待条目",
            "应用批量目标格式",
        )
        self._set_widget_availability_hint(
            self.reset_batch_format_button,
            has_changeable,
            "选中项中没有可重置格式的等待条目",
            "让选中等待条目跟随全局目标格式",
        )
        self._set_widget_availability_hint(
            self.retry_failed_button,
            retry_enabled,
            "没有失败条目，或失败重试任务正在运行",
            "重新入列选中的失败条目",
        )
        self._set_widget_availability_hint(
            self.remove_button,
            has_removable,
            "选中项都在处理中，暂不能移除",
            "从队列中移除选中条目，不删除源文件",
        )

    def _set_path_field(self, field, text):
        value = text or "无"
        field.setText(value)
        field.setToolTip(value)
        field.setCursorPosition(0)

    def _can_open_path_location(self, file_path):
        if not file_path or file_path == "无":
            return False

        parent_dir = os.path.dirname(file_path)
        return os.path.exists(file_path) or os.path.isdir(parent_dir)

    def _get_single_selected_task(self):
        selected_paths = self._get_selected_file_paths()

        if len(selected_paths) != 1:
            return None

        return self._get_task_by_path(selected_paths[0])

    def _open_path_location(self, file_path, label):
        if not file_path:
            self.log_box.append(f"{label}路径为空，无法打开")
            return

        parent_dir = os.path.dirname(file_path)

        try:
            if os.path.exists(file_path):
                if os.name == "nt":
                    subprocess.Popen(["explorer", "/select,", os.path.normpath(file_path)])
                else:
                    self.open_folder(parent_dir, label)
                self.log_box.append(f"已打开{label}位置")
                return

            if os.path.isdir(parent_dir):
                self.open_folder(parent_dir, f"{label}所在目录")
                return

            self.log_box.append(f"{label}所在目录不存在，无法打开: {parent_dir}")
        except Exception as e:
            self.log_box.append(f"打开{label}位置失败: {e}")

    def _copy_path_to_clipboard(self, file_path, label):
        if not file_path:
            self.log_box.append(f"{label}路径为空，无法复制")
            return

        QApplication.clipboard().setText(file_path)
        self.log_box.append(f"已复制{label}路径")

    def open_selected_file_location(self):
        task = self._get_single_selected_task()
        if task is None:
            self.log_box.append("请先选择一个条目")
            return

        self._open_path_location(task.get("path"), "文件")

    def copy_selected_file_path(self):
        task = self._get_single_selected_task()
        if task is None:
            self.log_box.append("请先选择一个条目")
            return

        self._copy_path_to_clipboard(task.get("path"), "文件")

    def open_selected_decoded_location(self):
        task = self._get_single_selected_task()
        if task is None:
            self.log_box.append("请先选择一个条目")
            return

        self._open_path_location(task.get("decoded_path"), "解码产物")

    def copy_selected_decoded_path(self):
        task = self._get_single_selected_task()
        if task is None:
            self.log_box.append("请先选择一个条目")
            return

        self._copy_path_to_clipboard(task.get("decoded_path"), "解码产物")

    def handle_dropped_files(self, file_paths):
        if getattr(self, "safe_start", False) and self._safe_start_blocks("拖入文件入队"):
            return

        if not file_paths:
            return

        queued_count = 0
        skipped_count = 0

        for raw_path in file_paths:
            if not raw_path:
                skipped_count += 1
                continue

            file_path = os.path.normpath(os.path.abspath(raw_path))

            if os.path.isdir(file_path):
                skipped_count += 1
                self.log_box.append(f"暂不支持拖入文件夹: {file_path}")
                continue

            if not os.path.isfile(file_path):
                skipped_count += 1
                self.log_box.append(f"拖入路径不存在，已跳过: {file_path}")
                continue

            if watcher.handle_detected_file(file_path, source="manual_drop"):
                queued_count += 1
            else:
                skipped_count += 1

        if queued_count > 0:
            self.start_prepare_thread()
            self.refresh_file_table()
            self.update_selection_panel()

        self.log_box.append(
            "拖入文件处理完成: "
            f"入队 {queued_count} 个，跳过 {skipped_count} 个"
        )

    # =========================
    # 设置面板显示
    # =========================
    def toggle_settings_panel(self):
        self.show_settings_panel()

    def show_settings_panel(self):
        self.show_page(2)

    # =========================
    # 顶部概览
    # =========================
    def update_overview_label(self):
        monitor_status = "监听中" if self._is_watcher_thread_running() else "未监听"
        auto_status = "自动监听开" if self.auto_start_checkbox.isChecked() else "自动监听关"
        scan_status = "启动扫描开" if self.scan_on_start_checkbox.isChecked() else "启动扫描关"
        archive_status = (
            "按格式归档开"
            if self.format_subfolder_checkbox.isChecked()
            else "按格式归档关"
        )
        watch_folder = get_watch_folder()
        output_folder = get_output_folder()
        status_counts = self._count_task_statuses()

        self.overview_label.setText(
            "当前状态: "
            f"{monitor_status} | "
            f"输出 {get_target_label(self._get_global_target_format())} | "
            f"{auto_status} | "
            f"{scan_status} | "
            f"{archive_status}\n"
            f"监听: {watch_folder}\n"
            f"输出: {output_folder}"
        )
        self.monitor_card.set_value(monitor_status, auto_status)
        self.format_card.set_value(
            get_target_label(self._get_global_target_format()),
            archive_status,
        )
        self.waiting_card.set_value(status_counts.get(watcher.WAITING_STATUS, 0))
        self.processing_card.set_value(status_counts.get(watcher.PROCESSING_STATUS, 0))
        self.completed_card.set_value(status_counts.get(watcher.COMPLETED_STATUS, 0))
        self.failed_card.set_value(status_counts.get(watcher.FAILED_STATUS, 0))
        self.dashboard_watch_label.setText(f"监听目录:\n{watch_folder}")
        self.dashboard_output_label.setText(f"输出目录:\n{output_folder}")
        self.update_tray_actions()
        self.update_runtime_action_hints()

    def update_runtime_action_hints(self):
        if not hasattr(self, "start_button"):
            return

        watcher_running = self._is_watcher_thread_running()
        convert_running = self._is_convert_thread_running()
        scan_running = self._is_scan_thread_running()
        retry_running = self._is_retry_thread_running()
        has_convertible = bool(watcher.get_convertible_tasks())
        has_terminal_records = any(
            task.get("status") in watcher.CLEARABLE_TERMINAL_STATUSES
            for task in watcher.get_task_snapshots()
        )

        self._set_widget_availability_hint(
            self.start_button,
            self.start_button.isEnabled(),
            "监听器已在运行" if watcher_running else "请先确认监听目录有效",
            "开始监听目录变化",
        )
        self._set_widget_availability_hint(
            self.stop_button,
            self.stop_button.isEnabled(),
            "监听器未在运行",
            "停止当前监听",
        )
        self._set_widget_availability_hint(
            self.convert_button,
            (not convert_running and has_convertible),
            "转换任务正在运行" if convert_running else "当前没有等待转换的文件",
            "开始转换所有等待条目",
        )
        self._set_widget_availability_hint(
            self.convert_to_button,
            (not convert_running and has_convertible),
            "转换任务正在运行" if convert_running else "当前没有等待转换的文件",
            "选择本轮临时输出目录后转换",
        )
        self._set_widget_availability_hint(
            self.scan_existing_button,
            self.scan_existing_button.isEnabled(),
            "已有文件扫描正在进行" if scan_running else "请先确认监听目录有效",
            "扫描监听目录中已有文件并加入队列",
        )
        self._set_widget_availability_hint(
            self.clear_terminal_button,
            has_terminal_records,
            "没有已完成、失败或跳过的记录",
            "清除已完成、失败或跳过的队列记录",
        )
        self._set_widget_availability_hint(
            self.retry_failed_button,
            self.retry_failed_button.isEnabled(),
            "失败重试任务正在运行" if retry_running else "没有可重试的失败条目",
            "重新入列失败条目",
        )

    def _count_task_statuses(self):
        counts = {}
        for task in watcher.get_task_snapshots():
            status = task.get("status")
            counts[status] = counts.get(status, 0) + 1
        return counts

    # =========================
    # 托盘交互
    # =========================
    def update_tray_actions(self):
        if not hasattr(self, "tray_monitor_action"):
            return

        if self.safe_start:
            self.tray_monitor_action.setEnabled(False)
            self.tray_scan_action.setEnabled(False)
            self.tray_convert_action.setEnabled(False)
            self.tray_icon.setToolTip(f"{APP_NAME} - Legacy Safe Start")
            return

        is_monitoring = self._is_watcher_thread_running()
        monitor_text = "停止监听" if is_monitoring else "开始监听"
        tooltip_status = "监听中" if is_monitoring else "未监听"

        self.tray_monitor_action.setText(monitor_text)
        self.tray_scan_action.setEnabled(not self._is_scan_thread_running())
        self.tray_convert_action.setEnabled(not self._is_convert_thread_running())
        self.tray_icon.setToolTip(
            f"{APP_NAME} - {tooltip_status}"
        )
        self._update_cache_buttons()

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_window()

    def show_settings_window(self):
        self.show_window()
        self.show_settings_panel()

    def toggle_monitor_from_tray(self):
        if self._is_watcher_thread_running():
            self.stop_monitor()
            return

        self.start_monitor()

    # =========================
    # 开始转换
    # =========================
    def start_convert(self, output_root_override=None):
        if getattr(self, "safe_start", False) and self._safe_start_blocks("转换"):
            return

        if isinstance(output_root_override, bool):
            output_root_override = None

        if self._is_convert_thread_running():
            self.log_box.append("已有转换任务正在进行")
            return

        if not watcher.get_convertible_tasks():
            if watcher.has_preparing_tasks():
                self.log_box.append("当前没有等待处理的文件，部分文件可能仍在读取验证中。")
            else:
                self.log_box.append("当前没有等待处理的文件")
            return

        self.log_conversion_summary(output_root_override=output_root_override)
        if output_root_override:
            self.log_box.append(f"本轮临时输出目录: {output_root_override}")
        self.log_box.append("开始后台转换...")

        self.convert_thread = ConvertThread(
            self._get_global_target_format(),
            output_root_override=output_root_override,
            create_format_subfolder=None,
            parent=self,
        )
        self.convert_thread.finished.connect(
            self.on_convert_finished
        )
        self.convert_thread.start()
        self.update_tray_actions()
        self.update_runtime_action_hints()

    def start_convert_selected(self):
        if getattr(self, "safe_start", False) and self._safe_start_blocks("选中条目转换"):
            return

        if self._is_convert_thread_running():
            self.log_box.append("已有转换任务正在进行")
            return

        selected_paths = self._get_selected_file_paths()
        if not selected_paths:
            self.log_box.append("选中条目中没有等待处理的文件")
            return

        selected_path_set = set(selected_paths)
        convertible_tasks = [
            task
            for task in watcher.get_convertible_tasks()
            if task.get("path") in selected_path_set
        ]

        if not convertible_tasks:
            self.log_box.append("选中条目中没有等待处理的文件")
            return

        convertible_paths = [task["path"] for task in convertible_tasks]
        self.log_conversion_summary(file_paths=convertible_paths)
        self.log_box.append(
            f"开始后台转换 {len(convertible_paths)} 个选中条目..."
        )

        self.convert_thread = ConvertThread(
            self._get_global_target_format(),
            output_root_override=None,
            create_format_subfolder=None,
            file_paths=convertible_paths,
            parent=self,
        )
        self.convert_thread.finished.connect(
            self.on_convert_finished
        )
        self.convert_thread.start()
        self.update_tray_actions()
        self.update_runtime_action_hints()

    def start_convert_to(self):
        if getattr(self, "safe_start", False) and self._safe_start_blocks("指定目录转换"):
            return

        if self._is_convert_thread_running():
            self.log_box.append("已有转换任务正在进行")
            return

        folder = QFileDialog.getExistingDirectory(
            self,
            "选择本轮转换输出目录"
        )

        if not folder:
            return

        self.log_box.append(f"本轮将转换到临时目录: {folder}")
        self.start_convert(output_root_override=folder)

    def log_conversion_summary(self, output_root_override=None, file_paths=None):
        default_target_format = self._get_global_target_format()
        summary = {}
        allowed_paths = set(file_paths) if file_paths is not None else None

        for task in watcher.get_convertible_tasks():
            if allowed_paths is not None and task.get("path") not in allowed_paths:
                continue

            target_format = task.get("target_format") or default_target_format
            normalized = get_target_label(target_format)
            summary[normalized] = summary.get(normalized, 0) + 1

        summary_text = "，".join(
            f"{target_format} {count} 个"
            for target_format, count in sorted(summary.items())
        )

        self.log_box.append(f"本轮转换摘要: {summary_text}")
        if output_root_override:
            self.log_box.append(f"本轮输出根目录: {output_root_override}")

    # =========================
    # 显示窗口
    # =========================
    def show_window(self):
        self.showNormal()
        self.activateWindow()

    # =========================
    # 退出程序
    # =========================
    def quit_app(self):
        audio_editor = getattr(self, "audio_editor_workspace", None)
        if audio_editor is not None and not audio_editor.confirm_discard_unsaved_changes():
            return

        self.is_quitting = True

        self.log_box.append("正在退出程序...")

        if not self.stop_convert_thread():
            self.is_quitting = False
            QMessageBox.warning(
                self,
                "转换仍在进行",
                "当前文件尚未转换完成，程序暂未退出。请稍后再次退出。"
            )
            return

        self.stop_watcher_thread()
        self.stop_scan_thread()
        self.stop_retry_thread()
        self.stop_prepare_thread()
        self.stop_cache_threads()

        if self.timer is not None:
            self.timer.stop()

        self.tray_icon.hide()
        QApplication.quit()

    # =========================
    # 关闭事件重写，最小化到托盘
    # =========================
    def closeEvent(self, event):
        if self.is_quitting:
            event.accept()
            return

        event.ignore()
        self.hide()

        self.tray_icon.showMessage(
            APP_NAME,
            "程序仍在后台运行",
            QSystemTrayIcon.Information,
            2000
        )

    def append_log(self, message):
        self.log_box.append(message)

    def _save_config_if_allowed(self, config_data):
        if self.safe_start:
            self._log_safe_start_block("配置保存")
            return config_data

        return save_config(config_data)

    def _log_safe_start_block(self, operation):
        self.log_box.append(
            f"Legacy Safe Start：{operation}已禁用，未执行真实后台操作。"
        )

    def _safe_start_blocks(self, operation):
        if not self.safe_start:
            return False

        self._log_safe_start_block(operation)
        return True

    def _apply_safe_start_ui_state(self):
        for widget in (
            self.start_button,
            self.scan_existing_button,
            self.convert_button,
            self.convert_to_button,
            self.retry_failed_button,
            self.clear_terminal_button,
            self.remove_button,
            self.apply_batch_format_button,
            self.reset_batch_format_button,
            self.selection_apply_target_button,
            self.selection_remove_button,
            self.selection_retry_button,
        ):
            widget.setEnabled(False)

        self.update_tray_actions()

    def _get_global_target_format(self):
        return (
            self.format_combo.currentData()
            or self.format_combo.currentText().lower()
        )

    # =========================
    # 修改输出格式
    # =========================
    def change_format(self, _value=None):
        value = self._get_global_target_format()
        self.config_data["target_format"] = value
        self.config_data = self._save_config_if_allowed(self.config_data)

        self.log_box.append(
            f"输出格式已修改: {get_target_label(value)}"
        )
        self.refresh_file_table()
        self.update_overview_label()

    def change_theme_mode(self, _index=None):
        selected_mode = self.theme_combo.currentData()
        if selected_mode is None:
            return

        self.config_data["theme_mode"] = selected_mode
        self.config_data = self._save_config_if_allowed(self.config_data)
        resolved_mode = apply_theme(QApplication.instance(), selected_mode)

        label = self.theme_combo.currentText()
        resolved_label = "深色" if resolved_mode == "dark" else "浅色"
        self.log_box.append(f"界面主题已切换: {label}，当前应用 {resolved_label}")

    # =========================
    # 修改自动监听设置
    # =========================
    def change_auto_start_monitor(self, _state=None):
        enabled = self.auto_start_checkbox.isChecked()
        self.config_data["auto_start_monitor"] = enabled
        self.config_data = self._save_config_if_allowed(self.config_data)

        status_text = "开启" if enabled else "关闭"
        self.log_box.append(f"启动后自动监听已{status_text}")
        self.update_overview_label()

    # =========================
    # 修改启动扫描设置
    # =========================
    def change_scan_existing_on_start(self, _state=None):
        enabled = self.scan_on_start_checkbox.isChecked()
        self.config_data["scan_existing_on_start"] = enabled
        self.config_data = self._save_config_if_allowed(self.config_data)

        status_text = "开启" if enabled else "关闭"
        self.log_box.append(f"启动监听时扫描已有文件已{status_text}")
        self.update_overview_label()

    def change_create_format_subfolder(self, _state=None):
        enabled = self.format_subfolder_checkbox.isChecked()
        self.config_data["create_format_subfolder"] = enabled
        self.config_data = self._save_config_if_allowed(self.config_data)

        status_text = "开启" if enabled else "关闭"
        self.log_box.append(f"按目标格式创建子文件夹已{status_text}")
        self.update_overview_label()

    def change_embed_lyrics_after_convert(self, _state=None):
        enabled = self.embed_lyrics_checkbox.isChecked()
        self.config_data["embed_lyrics_after_convert"] = enabled
        self.config_data = self._save_config_if_allowed(self.config_data)

        status_text = "开启" if enabled else "关闭"
        self.log_box.append(f"转换后写入内嵌歌词已{status_text}")

    def change_copy_lrc_to_output(self, _state=None):
        enabled = self.copy_lrc_checkbox.isChecked()
        self.config_data["copy_lrc_to_output"] = enabled
        self.config_data = self._save_config_if_allowed(self.config_data)

        status_text = "开启" if enabled else "关闭"
        self.log_box.append(f"输出时保留外置 .lrc 文件已{status_text}")

    def change_overwrite_existing_lyrics(self, _state=None):
        enabled = self.overwrite_lyrics_checkbox.isChecked()
        self.config_data["overwrite_existing_lyrics"] = enabled
        self.config_data = self._save_config_if_allowed(self.config_data)

        status_text = "开启" if enabled else "关闭"
        self.log_box.append(f"覆盖已有歌词已{status_text}")

    def start_cache_scan(self, for_clear=False):
        if self._is_cache_scan_thread_running() or self._is_cache_clear_thread_running():
            self.log_box.append("已有缓存扫描或清理任务正在进行")
            return

        self.pending_cache_clear_after_scan = bool(for_clear)
        self.cache_status_label.setText("当前缓存: 正在扫描...")
        self.cache_detail_label.setText("正在统计程序缓存目录，请稍候。")
        self.log_box.append("开始扫描缓存...")

        self.cache_scan_thread = CacheScanThread(self)
        self.cache_scan_thread.scan_finished.connect(self.on_cache_scan_finished)
        self.cache_scan_thread.finished.connect(self.on_cache_scan_thread_stopped)
        self.cache_scan_thread.start()
        self._update_cache_buttons()

    def start_cache_clear(self):
        summary = self.cache_scan_summary

        if summary is None:
            self.start_cache_scan(for_clear=True)
            return

        cleanable_files, cleanable_size = self._get_cache_cleanable_counts(summary)

        if cleanable_files <= 0 or cleanable_size <= 0:
            QMessageBox.information(self, "无需清理", "当前没有可清理缓存。")
            self._update_cache_buttons()
            return

        blocking_reasons = self._get_cache_blocking_reasons()

        if blocking_reasons:
            message = "当前有任务正在运行，请停止播放或等待任务结束后再清理缓存。"
            self.log_box.append(f"{message} 原因: {'，'.join(blocking_reasons)}")
            QMessageBox.information(self, "暂不能清理缓存", message)
            self._update_cache_buttons()
            return

        self.confirm_and_start_cache_clear(summary)

    def on_cache_scan_finished(self, summary):
        self.last_cache_scan = summary
        self.cache_scan_summary = summary
        total_size = cache_manager.format_size(summary.get("total_size", 0))
        total_files = summary.get("total_files", 0)
        cleanable_files, cleanable_size = self._get_cache_cleanable_counts(summary)
        cleanable_size_text = cache_manager.format_size(cleanable_size)
        self.cache_status_label.setText(
            f"当前缓存: {total_size} / {total_files} 个文件\n"
            f"可清理: {cleanable_size_text} / {cleanable_files} 个文件"
        )
        self.cache_detail_label.setText(self._format_cache_category_summary(summary))
        self.log_box.append(
            f"缓存扫描完成: 共 {total_files} 个文件，{total_size}；"
            f"可清理 {cleanable_files} 个文件，{cleanable_size_text}"
        )

        if self.pending_cache_clear_after_scan:
            self.pending_cache_clear_after_scan = False
            self.confirm_and_start_cache_clear(summary)

    def on_cache_scan_thread_stopped(self):
        self.cache_scan_thread = None
        self._update_cache_buttons()

    def confirm_and_start_cache_clear(self, summary):
        cleanable_files, cleanable_size = self._get_cache_cleanable_counts(summary)

        if cleanable_files <= 0 or cleanable_size <= 0:
            QMessageBox.information(self, "无需清理", "当前没有可清理的程序缓存。")
            self._update_cache_buttons()
            return

        blocking_reasons = self._get_cache_blocking_reasons()
        if blocking_reasons:
            message = "当前有任务正在运行，请停止播放或等待任务结束后再清理缓存。"
            self.log_box.append(f"{message} 原因: {'，'.join(blocking_reasons)}")
            QMessageBox.information(self, "暂不能清理缓存", message)
            self._update_cache_buttons()
            return

        category_lines = []
        for category in summary.get("categories", {}).values():
            category_files = category.get("cleanable_files", category.get("files", 0))
            category_size = category.get("cleanable_size", category.get("size", 0))

            if category_files <= 0 and category_size <= 0:
                continue

            category_lines.append(
                f"- {category['label']}: "
                f"{cache_manager.format_size(category_size)} / "
                f"{category_files} 个文件"
            )

        message = (
            "将清理程序生成的缓存：\n"
            f"可清理: {cache_manager.format_size(cleanable_size)} / "
            f"{cleanable_files} 个文件\n\n"
            + "\n".join(category_lines)
            + "\n\n此操作不会删除监听目录、输出目录、源音频、歌词文件、"
            "配置文件和工具文件。\n\n是否继续？"
        )
        confirm = QMessageBox.question(
            self,
            "确认清理缓存",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if confirm != QMessageBox.StandardButton.Yes:
            self.log_box.append("用户取消清理缓存")
            self._update_cache_buttons()
            return

        self.cache_status_label.setText("当前缓存: 正在清理...")
        self.cache_detail_label.setText("正在清理程序缓存目录，请稍候。")
        self.log_box.append("开始清理缓存...")

        self.cache_clear_thread = CacheClearThread(parent=self)
        self.cache_clear_thread.clear_finished.connect(self.on_cache_clear_finished)
        self.cache_clear_thread.finished.connect(self.on_cache_clear_thread_stopped)
        self.cache_clear_thread.start()
        self._update_cache_buttons()

    def on_cache_clear_finished(self, result):
        freed_size = cache_manager.format_size(result.get("freed_size", 0))
        deleted_files = result.get("deleted_files", 0)
        failed_count = result.get("failed_count", 0)
        skipped_count = result.get("skipped_count", 0)
        self.cache_status_label.setText(
            f"当前缓存: 已清理，释放 {freed_size}"
        )
        self.cache_detail_label.setText(
            f"删除 {deleted_files} 个文件；"
            f"跳过 {skipped_count} 项；失败 {failed_count} 项。"
        )
        self.log_box.append(
            f"缓存清理完成: 释放 {freed_size}，删除 {deleted_files} 个文件"
        )

        for failure in result.get("failures", [])[:5]:
            self.log_box.append(f"缓存清理提示: {failure}")

        self.last_cache_scan = None
        self.cache_scan_summary = None
        self.rescan_cache_after_clear = True

    def on_cache_clear_thread_stopped(self):
        self.cache_clear_thread = None
        if self.rescan_cache_after_clear:
            self.rescan_cache_after_clear = False
            self.start_cache_scan()
            return

        self._update_cache_buttons()

    def _format_cache_category_summary(self, summary):
        lines = ["分类明细:"]

        for category in summary.get("categories", {}).values():
            category_files = category.get("cleanable_files", category.get("files", 0))
            category_size = category.get("cleanable_size", category.get("size", 0))
            lines.append(
                f"{category['label']}: "
                f"{cache_manager.format_size(category_size)}"
                f" / {category_files} 个文件"
            )

        skipped_files = summary.get("skipped_files", summary.get("skipped_count", 0))
        skipped_size = summary.get("skipped_size", 0)

        if skipped_files > 0 or skipped_size > 0:
            lines.append(
                "不可清理: "
                f"{cache_manager.format_size(skipped_size)} / {skipped_files} 项"
            )

        return "\n".join(lines) if len(lines) > 1 else "未发现缓存文件。"

    # =========================
    # 选择监听目录
    # =========================
    def select_watch_folder(self):
        if getattr(self, "safe_start", False) and self._safe_start_blocks("修改监听目录"):
            return

        folder = QFileDialog.getExistingDirectory(
            self,
            "选择监听目录"
        )

        if folder:
            self.watch_label.setText(
                f"监听目录:\n{folder}"
            )

            self.config_data["watch_folder"] = folder
            self.config_data["first_launch_completed"] = True
            self.config_data = self._save_config_if_allowed(self.config_data)

            self.log_box.append(
                f"监听目录已修改:\n{folder}"
            )
            self.update_overview_label()

            if self._is_watcher_thread_running():
                self.log_box.append("正在切换监听目录...")
                self.restart_watcher(folder)

            self._offer_scan_after_folder_change()

    # =========================
    # 打开监听目录
    # =========================
    def open_watch_folder(self):
        self.open_folder(get_watch_folder(), "监听目录")

    # =========================
    # 选择输出目录
    # =========================
    def select_output_folder(self):
        if getattr(self, "safe_start", False) and self._safe_start_blocks("修改输出目录"):
            return

        folder = QFileDialog.getExistingDirectory(
            self,
            "选择输出目录"
        )

        if folder:
            self.output_label.setText(
                f"输出目录:\n{folder}"
            )

            self.config_data["output_folder"] = folder
            self.config_data = self._save_config_if_allowed(self.config_data)

            self.log_box.append(
                f"输出目录已修改:\n{folder}"
            )
            self.update_overview_label()

    # =========================
    # 打开输出目录
    # =========================
    def open_output_folder(self):
        self.open_folder(get_output_folder(), "输出目录")

    # =========================
    # 打开目录
    # =========================
    def open_folder(self, folder_path, folder_name):
        if not folder_path or not os.path.isdir(folder_path):
            self.log_box.append(f"{folder_name}不存在，无法打开")
            return

        try:
            os.startfile(folder_path)
            self.log_box.append(f"已打开{folder_name}")
        except AttributeError:
            try:
                subprocess.Popen(["open", folder_path])
                self.log_box.append(f"已打开{folder_name}")
            except Exception as e:
                self.log_box.append(f"打开{folder_name}失败: {e}")
        except Exception as e:
            self.log_box.append(f"打开{folder_name}失败: {e}")

    # =========================
    # 开始监听
    # =========================
    def start_monitor(self):
        if getattr(self, "safe_start", False) and self._safe_start_blocks("自动监听"):
            return False

        if self._is_watcher_thread_running():
            self.log_box.append("监听器已在运行")
            return True

        watch_folder = get_watch_folder()

        if not is_valid_watch_folder(watch_folder):
            self.log_box.append(f"监听目录不存在，无法启动监听:\n{watch_folder}")
            QMessageBox.information(
                self,
                "需要设置监听目录",
                "当前监听目录不存在。请先选择网易云音乐下载目录，或其他需要监听的音频目录。"
            )
            return False

        self.log_box.append("开始后台监听...")
        self.start_watcher_thread(watch_folder)
        self.start_prepare_thread()
        self.start_file_list_timer()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.log_box.append("监听器已启动")
        self.update_overview_label()
        self.update_runtime_action_hints()

        if self.scan_on_start_checkbox.isChecked():
            self.start_scan_existing_files()

        return True

    # =========================
    # 停止监听
    # =========================
    def stop_monitor(self):
        if not self._is_watcher_thread_running():
            self.log_box.append("监听器未在运行")
            return

        self.log_box.append("正在停止监听...")
        self.stop_watcher_thread()
        self.log_box.append("监听器已停止")
        self.update_overview_label()

    # =========================
    # watcher 线程状态
    # =========================
    def _is_watcher_thread_running(self):
        return self.thread is not None and self.thread.isRunning()

    def _is_convert_thread_running(self):
        return (
            self.convert_thread is not None
            and self.convert_thread.isRunning()
        )

    def _is_scan_thread_running(self):
        return (
            self.scan_thread is not None
            and self.scan_thread.isRunning()
        )

    def _is_retry_thread_running(self):
        return (
            self.retry_thread is not None
            and self.retry_thread.isRunning()
        )

    def _is_prepare_thread_running(self):
        return (
            self.prepare_thread is not None
            and self.prepare_thread.isRunning()
        )

    def _is_cache_scan_thread_running(self):
        return (
            self.cache_scan_thread is not None
            and self.cache_scan_thread.isRunning()
        )

    def _is_cache_clear_thread_running(self):
        return (
            self.cache_clear_thread is not None
            and self.cache_clear_thread.isRunning()
        )

    def _get_cache_blocking_reasons(self):
        reasons = []

        if self._is_convert_thread_running():
            reasons.append("正在转换")

        if self._is_scan_thread_running():
            reasons.append("正在扫描已有文件")

        if self._is_retry_thread_running():
            reasons.append("正在重试失败条目")

        try:
            active_statuses = {
                watcher.QUEUED_STATUS,
                watcher.READING_STATUS,
                watcher.WAITING_STATUS,
                watcher.PROCESSING_STATUS,
            }
            for task in watcher.get_task_snapshots():
                if task.get("status") not in active_statuses:
                    continue

                if (
                    task.get("temp_work_dir")
                    or task.get("decoded_path")
                    or task.get("temp_ncm_path")
                ):
                    reasons.append("队列中存在待处理的 NCM 临时文件")
                    break
        except Exception as e:
            self.log_box.append(f"缓存清理状态检查失败: {e}")
            reasons.append("任务状态检查未完成")

        audio_editor = getattr(self, "audio_editor_workspace", None)
        if audio_editor is not None:
            if (
                hasattr(audio_editor, "_is_pitch_processing")
                and audio_editor._is_pitch_processing()
            ):
                reasons.append("正在生成试听或导出")

            if (
                getattr(audio_editor, "playback_source_type", None) == "pitch_preview"
                and getattr(audio_editor, "playback_status", "") == "播放中"
            ):
                reasons.append("正在播放试听缓存")

        return reasons

    def _get_cache_cleanable_counts(self, summary=None):
        summary = summary if summary is not None else self.cache_scan_summary

        if not summary:
            return 0, 0

        cleanable_files = summary.get(
            "cleanable_files",
            summary.get("total_files", 0),
        )
        cleanable_size = summary.get(
            "cleanable_size",
            summary.get("total_size", 0),
        )
        return int(cleanable_files or 0), int(cleanable_size or 0)

    def update_cache_buttons_state(self):
        cache_busy = (
            self._is_cache_scan_thread_running()
            or self._is_cache_clear_thread_running()
        )
        cleanable_files, cleanable_size = self._get_cache_cleanable_counts()
        has_cleanable_cache = cleanable_files > 0 and cleanable_size > 0
        blocking_reasons = self._get_cache_blocking_reasons()
        has_conflict = bool(blocking_reasons)

        if hasattr(self, "scan_cache_button"):
            scan_enabled = not cache_busy
            self.scan_cache_button.setEnabled(scan_enabled)
            MainWindow._set_widget_availability_hint(
                self,
                self.scan_cache_button,
                scan_enabled,
                "缓存扫描或清理正在进行",
                "统计程序 Temp/Cache 缓存大小，不会清理文件",
            )

        if hasattr(self, "clear_cache_button"):
            clear_enabled = has_cleanable_cache and not cache_busy and not has_conflict
            if cache_busy:
                clear_reason = "缓存扫描或清理正在进行"
            elif self.cache_scan_summary is None:
                clear_reason = "请先扫描缓存"
            elif not has_cleanable_cache:
                clear_reason = "当前没有可清理缓存"
            elif has_conflict:
                clear_reason = "，".join(blocking_reasons)
            else:
                clear_reason = ""

            self.clear_cache_button.setEnabled(clear_enabled)
            MainWindow._set_widget_availability_hint(
                self,
                self.clear_cache_button,
                clear_enabled,
                clear_reason,
                "清理程序 Temp/Cache 缓存，不影响源文件",
            )

    def _update_cache_buttons(self):
        self.update_cache_buttons_state()

    def stop_cache_threads(self):
        for thread_attr, label in (
            ("cache_scan_thread", "缓存扫描线程"),
            ("cache_clear_thread", "缓存清理线程"),
        ):
            thread = getattr(self, thread_attr, None)

            if thread is not None and thread.isRunning():
                self.log_box.append(f"正在等待{label}结束...")
                thread.wait(5000)

            setattr(self, thread_attr, None)

    def stop_convert_thread(self):
        if self.convert_thread is None:
            return True

        if self.convert_thread.isRunning():
            self.log_box.append("正在等待当前转换安全结束...")
            self.convert_thread.stop()

            if not self.convert_thread.wait(30000):
                self.log_box.append("当前转换未能在 30 秒内结束，已取消退出")
                return False

        self.convert_thread = None
        return True

    # =========================
    # 启动 watcher 线程
    # =========================
    def start_watcher_thread(self, watch_folder):
        if getattr(self, "safe_start", False) and self._safe_start_blocks("watcher 线程"):
            return

        self.thread = WatcherThread(
            watch_folder,
            self
        )
        self.thread.finished.connect(
            self.on_watcher_finished
        )
        self.thread.start()

    def start_prepare_thread(self):
        if getattr(self, "safe_start", False) and self._safe_start_blocks("后台读取/验证"):
            return

        if self._is_prepare_thread_running():
            return

        self.prepare_thread = QueuePrepareThread(self)
        self.prepare_thread.finished.connect(
            self.on_prepare_thread_stopped
        )
        self.prepare_thread.start()
        self.log_box.append("后台读取/验证线程已启动")

    def stop_prepare_thread(self):
        if self.prepare_thread is None:
            return

        if self.prepare_thread.isRunning():
            self.log_box.append("正在停止后台读取/验证线程...")
            self.prepare_thread.stop()
            if not self.prepare_thread.wait(5000):
                self.log_box.append("后台读取/验证线程未能在 5 秒内结束")

        self.prepare_thread = None

    def on_prepare_thread_stopped(self):
        self.prepare_thread = None

        if self.is_quitting:
            return

        self.log_box.append("后台读取/验证线程已停止")

    # =========================
    # 停止 watcher 线程
    # =========================
    def stop_watcher_thread(self):
        if self.thread is None:
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            return

        if self.thread.isRunning():
            self.log_box.append("正在停止监听线程...")
            self.thread.stop()
            self.thread.wait(5000)

        self.thread = None
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.update_overview_label()
        self.update_runtime_action_hints()

    # =========================
    # 重启 watcher 线程
    # =========================
    def restart_watcher(self, watch_folder):
        if getattr(self, "safe_start", False) and self._safe_start_blocks("重启 watcher"):
            return

        self.stop_watcher_thread()
        self.start_watcher_thread(watch_folder)
        self.start_prepare_thread()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.log_box.append("监听目录切换完成")
        self.update_overview_label()
        self.update_runtime_action_hints()

    # =========================
    # watcher 线程结束回调
    # =========================
    def on_watcher_finished(self):
        self.thread = None

        if self.is_quitting:
            return

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.update_overview_label()
        self.update_runtime_action_hints()

    # =========================
    # 转换线程结束回调
    # =========================
    def on_convert_finished(self):
        self.convert_thread = None

        if self.is_quitting:
            return

        self.log_box.append("本轮转换任务已结束")
        self.update_tray_actions()
        self.update_runtime_action_hints()

    # =========================
    # 启动流程
    # =========================
    def run_startup_flow(self):
        if self.is_quitting:
            return

        if self.safe_start:
            self.log_box.append(
                "Legacy Safe Start：已跳过自动监听、扫描和首次使用引导。"
            )
            return

        # 首次启动始终弹出引导，让用户了解监听目录的概念
        if not is_first_launch_completed() or not is_valid_watch_folder():
            self.show_first_use_guidance()
            return

        if self.auto_start_checkbox.isChecked():
            self.log_box.append("已启用自动监听，正在启动...")
            self.start_monitor()

    # =========================
    # 首次使用提示
    # =========================
    def show_first_use_guidance(self):
        candidates = find_watch_folder_candidates()

        if candidates:
            candidate = candidates[0]
            result = QMessageBox.question(
                self,
                "找到可能的下载目录",
                (
                    "当前监听目录不可用，但找到了一个可能的网易云下载目录：\n\n"
                    f"{candidate}\n\n"
                    "是否使用这个目录作为监听目录？"
                )
            )

            if result == QMessageBox.StandardButton.Yes:
                self.config_data["watch_folder"] = candidate
                self.config_data["first_launch_completed"] = True
                self.config_data = self._save_config_if_allowed(self.config_data)
                self.watch_label.setText(f"监听目录:\n{candidate}")
                self.log_box.append(f"已使用自动发现的监听目录:\n{candidate}")
                self.update_overview_label()

                if self.auto_start_checkbox.isChecked():
                    self.start_monitor()

                return

        # 无论用户是否接受了候选目录，只要看到了引导就算完成首次引导
        self.config_data["first_launch_completed"] = True
        self.config_data = self._save_config_if_allowed(self.config_data)

        QMessageBox.information(
            self,
            "首次使用提示",
            "请先选择监听目录。通常可以选择网易云音乐的下载目录，设置后即可开始监听。"
        )

    # =========================
    # 切换目录后扫描提示
    # =========================
    def _offer_scan_after_folder_change(self):
        result = QMessageBox.question(
            self,
            "扫描已有文件",
            "是否立即扫描新监听目录中已经存在的音频文件？"
        )

        if result == QMessageBox.StandardButton.Yes:
            self.start_scan_existing_files()

    # =========================
    # 扫描已有文件
    # =========================
    def start_scan_existing_files(self):
        if getattr(self, "safe_start", False) and self._safe_start_blocks("扫描已有文件"):
            return

        if self._is_scan_thread_running():
            self.log_box.append("已有文件扫描正在进行")
            return

        watch_folder = get_watch_folder()

        if not is_valid_watch_folder(watch_folder):
            self.log_box.append(f"监听目录不存在，无法扫描已有文件:\n{watch_folder}")
            return

        self.log_box.append("开始扫描已有文件并快速入队...")
        self.start_prepare_thread()
        self.scan_existing_button.setEnabled(False)
        self.update_runtime_action_hints()
        self.update_tray_actions()

        self.scan_thread = ScanThread(
            watch_folder,
            self
        )
        self.scan_thread.scan_progress.connect(
            self.on_scan_progress
        )
        self.scan_thread.scan_finished.connect(
            self.on_scan_finished
        )
        self.scan_thread.finished.connect(
            self.on_scan_thread_stopped
        )
        self.scan_thread.start()

    def on_scan_progress(self, summary):
        if self.is_quitting:
            return

        self.scan_status_label.setText(
            "扫描状态: "
            f"{summary['scanned_count']}/{summary['total_count']} - "
            f"{summary['current_file']}"
        )

    def on_scan_finished(self, summary):
        if self.is_quitting:
            return

        total_count = summary["total_count"]
        scanned_count = summary["scanned_count"]
        queued_count = summary["queued_count"]
        skipped_count = summary["skipped_count"]

        self.refresh_file_table()
        self.start_prepare_thread()
        self.scan_status_label.setText(
            "扫描状态: "
            f"入队完成，扫描 {scanned_count}/{total_count} 个，"
            f"新增 {queued_count} 个，跳过 {skipped_count} 个；"
            "后台读取/验证继续"
        )
        self.log_box.append(
            "已有文件扫描结束: "
            f"扫描 {scanned_count}/{total_count} 个，"
            f"新增入列 {queued_count} 个，"
            f"跳过 {skipped_count} 个；后台读取/验证仍在继续"
        )

    def on_scan_thread_stopped(self):
        self.scan_thread = None
        self.scan_existing_button.setEnabled(True)
        self.update_tray_actions()
        self.update_runtime_action_hints()

    def stop_scan_thread(self):
        if self.scan_thread is None:
            return

        if self.scan_thread.isRunning():
            self.log_box.append("正在停止已有文件扫描...")
            self.scan_thread.stop()
            self.scan_thread.wait(5000)

        self.scan_thread = None
        self.scan_existing_button.setEnabled(True)
        self.update_tray_actions()
        self.update_runtime_action_hints()

    # =========================
    # 批量设置目标格式
    # =========================
    def apply_selection_target_format(self):
        selected_paths = self._get_selected_file_paths()
        if len(selected_paths) != 1:
            self.log_box.append("请先选择一个条目")
            return

        target_format = self.selection_target_combo.currentData()
        self._apply_target_format_to_paths(selected_paths, target_format)

    def apply_batch_target_format(self):
        target_format = self.batch_format_combo.currentData()
        selected_paths = self._get_selected_file_paths()
        self._apply_target_format_to_paths(selected_paths, target_format)

    def reset_selected_target_formats(self):
        selected_paths = self._get_selected_file_paths()
        self._apply_target_format_to_paths(selected_paths, None)

    def _apply_target_format_to_paths(self, file_paths, target_format):
        if getattr(self, "safe_start", False) and self._safe_start_blocks("修改任务目标格式"):
            return

        if not file_paths:
            self.log_box.append("请先选择要设置目标格式的条目")
            return

        updated_count = 0

        for file_path in file_paths:
            if watcher.set_pending_file_target_format(file_path, target_format):
                updated_count += 1

        if updated_count == 0:
            self.log_box.append("没有条目被更新，可能正在处理或已完成")
            return

        if target_format:
            self.log_box.append(
                f"已将 {updated_count} 个选中条目设置为 {get_target_label(target_format)}"
            )
        else:
            self.log_box.append(
                f"已将 {updated_count} 个选中条目恢复为跟随全局"
            )

        self.refresh_file_table()
        self.update_selection_panel()

    # =========================
    # 重试失败条目
    # =========================
    def retry_failed_items(self):
        if getattr(self, "safe_start", False) and self._safe_start_blocks("重试失败条目"):
            return

        if self._is_retry_thread_running():
            self.log_box.append("已有失败重试任务正在进行")
            return

        selected_paths = self._get_selected_file_paths()
        retryable_tasks = watcher.get_retryable_tasks(selected_paths)

        if selected_paths and not retryable_tasks:
            self.log_box.append("选中的条目中没有可重试的失败记录")
            return

        if not selected_paths:
            retryable_tasks = watcher.get_retryable_tasks()

        if not retryable_tasks:
            self.log_box.append("当前没有可重试的失败条目")
            return

        retry_paths = [
            task["path"]
            for task in retryable_tasks
        ]

        self.log_box.append(f"开始重试 {len(retry_paths)} 个失败条目...")
        self.start_prepare_thread()
        self.retry_failed_button.setEnabled(False)
        self.selection_retry_button.setEnabled(False)
        self.update_runtime_action_hints()

        self.retry_thread = RetryThread(
            retry_paths,
            self
        )
        self.retry_thread.retry_finished.connect(
            self.on_retry_finished
        )
        self.retry_thread.finished.connect(
            self.on_retry_thread_stopped
        )
        self.retry_thread.start()

    def on_retry_finished(self, summary):
        if self.is_quitting:
            return

        self.refresh_file_table()
        self.update_selection_panel()
        self.start_prepare_thread()
        self.log_box.append(
            "失败条目重试结束: "
            f"尝试 {summary['attempted_count']} 个，"
            f"重新入列 {summary['requeued_count']} 个，"
            f"跳过 {summary['skipped_count']} 个"
        )

    def on_retry_thread_stopped(self):
        self.retry_thread = None
        self.retry_failed_button.setEnabled(True)
        self.selection_retry_button.setEnabled(True)
        self.update_selection_panel()
        self.update_runtime_action_hints()

    def stop_retry_thread(self):
        if self.retry_thread is None:
            return

        if self.retry_thread.isRunning():
            self.log_box.append("正在停止失败重试任务...")
            self.retry_thread.stop()
            self.retry_thread.wait(5000)

        self.retry_thread = None
        self.retry_failed_button.setEnabled(True)
        self.selection_retry_button.setEnabled(True)
        self.update_runtime_action_hints()

    def _get_selected_file_paths(self):
        return self._get_selected_file_paths_from_table()

    def _get_selected_file_paths_from_table(self):
        selected_rows = self.file_table.selectionModel().selectedRows()

        if not selected_rows:
            return []

        selected_paths = []

        for index in selected_rows:
            item = self.file_table.item(index.row(), 0)

            if item is None:
                continue

            file_path = item.data(Qt.ItemDataRole.UserRole)

            if file_path:
                selected_paths.append(file_path)

        return selected_paths

    def _get_task_by_path(self, file_path):
        for task in watcher.get_task_snapshots():
            if task.get("path") == file_path:
                return task

        return None

    def _get_selected_tasks(self):
        selected_tasks = []

        for file_path in self._get_selected_file_paths():
            task = self._get_task_by_path(file_path)
            if task is not None:
                selected_tasks.append(task)

        return selected_tasks

    def _set_selected_target_format_from_menu(self, target_format):
        self._apply_target_format_to_paths(
            self._get_selected_file_paths(),
            target_format,
        )

    def open_selected_source_location(self):
        selected_tasks = self._get_selected_tasks()

        if not selected_tasks:
            self.log_box.append("请先选择要打开位置的条目")
            return

        file_path = selected_tasks[0].get("path")
        if not file_path or not os.path.exists(file_path):
            self.log_box.append(f"源文件不存在，无法打开位置: {file_path or '无'}")
            return

        folder = os.path.dirname(file_path)
        self.open_folder(folder, "源文件所在目录")

    def copy_selected_source_paths(self):
        selected_paths = self._get_selected_file_paths()

        if not selected_paths:
            self.log_box.append("请先选择要复制路径的条目")
            return

        QApplication.clipboard().setText("\n".join(selected_paths))
        self.log_box.append(f"已复制 {len(selected_paths)} 个源文件路径")

    def show_selected_task_status(self):
        selected_tasks = self._get_selected_tasks()

        if not selected_tasks:
            self.log_box.append("请先选择要查看状态的条目")
            return

        if len(selected_tasks) == 1:
            task = selected_tasks[0]
            status_display = watcher.get_status_display(task.get("status"))
            decoded_path = task.get("decoded_path") or "无"
            message = (
                f"文件名: {task.get('filename', '-')}\n"
                f"原格式: {task.get('format', '-')}\n"
                f"目标格式: {self._format_target_format_display(task)}\n"
                f"当前状态: {status_display['label']} - {status_display['detail']}\n"
                f"源文件路径: {task.get('path', '-')}\n"
                f"解码产物路径: {decoded_path}"
            )
            QMessageBox.information(self, "任务状态", message)
            return

        status_counts = {}
        for task in selected_tasks:
            status = task.get("status")
            status_counts[status] = status_counts.get(status, 0) + 1

        lines = [f"已选择 {len(selected_tasks)} 个条目", "", "状态统计:"]
        for status, count in sorted(status_counts.items(), key=lambda item: str(item[0])):
            status_display = watcher.get_status_display(status)
            lines.append(f"{status_display['label']}: {count} 个")

        QMessageBox.information(self, "任务状态", "\n".join(lines))

    # =========================
    # 移除选中条目
    # =========================
    def remove_selected_items(self):
        if getattr(self, "safe_start", False) and self._safe_start_blocks("移除任务条目"):
            return

        selected_paths = self._get_selected_file_paths()

        if not selected_paths:
            self.log_box.append("请先选择要移除的条目")
            return

        removed_count = 0

        for file_path in selected_paths:
            file_info = self._get_task_by_path(file_path)

            if file_info is None:
                continue

            status = file_info["status"]

            if status == watcher.PROCESSING_STATUS:
                self.log_box.append(
                    f"条目正在处理中，无法移除: {file_info['filename']}"
                )
                continue

            if watcher.remove_pending_file_by_path(file_path):
                removed_count += 1

        if removed_count > 0:
            self.log_box.append(f"已移除 {removed_count} 个条目")
            self.refresh_file_table()
            self.update_selection_panel()

    # =========================
    # 清除终态条目
    # =========================
    def clear_terminal_items(self):
        if getattr(self, "safe_start", False) and self._safe_start_blocks("清除终态任务"):
            return

        removed_count = watcher.clear_terminal_pending_files()

        if removed_count > 0:
            self.log_box.append(f"已清除 {removed_count} 条已完成/失败记录")
            self.refresh_file_table()
            self.update_selection_panel()
        else:
            self.log_box.append("当前没有可清除的已完成/失败记录")

    # =========================
    # 定时刷新文件列表
    # =========================
    def start_file_list_timer(self):
        if self.timer is not None and self.timer.isActive():
            return

        self.timer = QTimer(self)
        self.timer.timeout.connect(
            self.refresh_file_table
        )
        self.timer.start(1000)

    # =========================
    # 刷新文件列表
    # =========================
    def refresh_file_table(self):
        selected_paths = set(self._get_selected_file_paths())
        pending_files = watcher.get_task_snapshots()

        self.file_table.blockSignals(True)
        self.file_table.clearContents()
        self.file_table.setRowCount(
            len(pending_files)
        )

        for row, file_info in enumerate(pending_files):
            self.file_table.setItem(
                row,
                0,
                self._make_file_name_item(file_info)
            )

            self.file_table.setItem(
                row,
                1,
                self._make_table_item(
                    file_info["format"]
                )
            )

            self.file_table.setItem(
                row,
                2,
                self._make_table_item(
                    self._format_target_format_display(file_info)
                )
            )

            self.file_table.setItem(
                row,
                3,
                self._make_status_item(
                    file_info["status"]
                )
            )

            if file_info["path"] in selected_paths:
                for column in range(self.file_table.columnCount()):
                    item = self.file_table.item(row, column)
                    if item is not None:
                        item.setSelected(True)

        self.file_table.blockSignals(False)
        self.update_overview_label()
        self.update_selection_panel()

    def _make_table_item(self, text):
        item = QTableWidgetItem(text)
        item.setToolTip(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    def _make_file_name_item(self, file_info):
        item = self._make_table_item(file_info["filename"])
        item.setData(Qt.ItemDataRole.UserRole, file_info["path"])
        return item

    def _format_target_format_display(self, file_info):
        default_format = self._get_global_target_format()
        selected_format = file_info.get("target_format")

        if selected_format:
            return f"单独指定（{get_target_label(selected_format)}）"

        return f"跟随全局（{get_target_label(default_format)}）"

    def _is_selection_target_combo_active(self):
        widget = QApplication.focusWidget()

        while widget is not None:
            if widget in (self.selection_target_combo, self.batch_format_combo):
                return True

            widget = widget.parent()

        return False

    def change_file_target_format(self, file_path, target_format):
        if getattr(self, "safe_start", False) and self._safe_start_blocks("修改任务目标格式"):
            return False

        if watcher.set_pending_file_target_format(file_path, target_format):
            if target_format:
                self.log_box.append(
                    f"单文件输出格式已设置为 {get_target_label(target_format)}"
                )
            else:
                self.log_box.append("单文件输出格式已恢复为跟随全局")
            self.refresh_file_table()
            self.update_selection_panel()

    def _make_status_item(self, status):
        status_display = watcher.get_status_display(status)
        label = status_display["label"]
        detail = status_display["detail"]
        item = QTableWidgetItem(f"■ {label}")

        item.setForeground(
            QBrush(
                QColor(status_display["color"])
            )
        )
        item.setToolTip(f"{label}: {detail}")
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

        return item
