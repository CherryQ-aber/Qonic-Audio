import logging
import os
import subprocess
import sys
import threading

from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QBrush, QColor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QStyle,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import watcher
from config import (
    APP_NAME,
    APP_VERSION,
    find_watch_folder_candidates,
    get_auto_start_monitor,
    get_output_folder,
    get_scan_existing_on_start,
    get_target_format,
    get_watch_folder,
    is_valid_watch_folder,
    load_config,
    save_config,
)

TARGET_FORMAT_OPTIONS = [
    "mp3",
    "flac",
    "wav",
    "aac",
    "ogg",
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

    def __init__(self, default_target_format, parent=None):
        super().__init__(parent)
        self.default_target_format = default_target_format

    def run(self):
        from converter import convert_audio

        for task in watcher.get_convertible_tasks():
            if self.isInterruptionRequested():
                logging.info("收到停止转换信号，将在当前文件完成后结束")
                break

            file_path = task["path"]
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
                    target_format
                )

                if result:
                    watcher.set_pending_file_status(file_path, watcher.COMPLETED_STATUS)
                    watcher.clear_processed_file(file_path)

                    if is_ncm_task:
                        logging.info(f"NCM 转换完成，状态已更新: {file_name}")
                    else:
                        logging.info(f"转换成功，状态已更新: {file_name}")
                else:
                    watcher.set_pending_file_status(file_path, watcher.FAILED_STATUS)
                    watcher.clear_processed_file(file_path)

                    if is_ncm_task:
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


class MainWindow(QWidget):

    def __init__(self):
        super().__init__()

        self.config_data = load_config()
        self.thread = None
        self.convert_thread = None
        self.scan_thread = None
        self.retry_thread = None
        self.timer = None
        self.is_quitting = False

        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(720, 560)

        layout = QVBoxLayout()

        self.overview_label = QLabel()
        self.overview_label.setWordWrap(True)

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
        # 系统托盘
        # =========================
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

        # =========================
        # 监听目录
        # =========================
        self.watch_label = QLabel(
            f"监听目录:\n{get_watch_folder()}"
        )

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

        self.format_combo = QComboBox()
        self.format_combo.addItems(TARGET_FORMAT_OPTIONS)
        self.format_combo.setCurrentText(
            get_target_format()
        )
        self.format_combo.currentTextChanged.connect(
            self.change_format
        )

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

        self.scan_existing_button = QPushButton("扫描已有文件")
        self.scan_existing_button.clicked.connect(
            self.start_scan_existing_files
        )

        self.scan_status_label = QLabel("扫描状态: 空闲")

        automation_layout = QHBoxLayout()
        automation_layout.addWidget(self.auto_start_checkbox)
        automation_layout.addWidget(self.scan_on_start_checkbox)
        automation_layout.addWidget(self.scan_existing_button)

        settings_layout = QVBoxLayout()
        settings_layout.addWidget(self.watch_label)
        settings_layout.addLayout(watch_button_layout)
        settings_layout.addWidget(self.output_label)
        settings_layout.addLayout(output_button_layout)
        settings_layout.addWidget(self.format_label)
        settings_layout.addWidget(self.format_combo)
        settings_layout.addLayout(automation_layout)
        settings_layout.addWidget(self.scan_status_label)

        self.settings_panel = QGroupBox("设置")
        self.settings_panel.setLayout(settings_layout)
        self.settings_panel.setVisible(False)

        self.settings_toggle_button = QPushButton("显示设置")
        self.settings_toggle_button.clicked.connect(
            self.toggle_settings_panel
        )

        # =========================
        # 文件列表
        # =========================
        self.file_table = QTableWidget()
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
        self.file_table.horizontalHeader().setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch
        )
        self.file_table.horizontalHeader().setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.file_table.horizontalHeader().setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.file_table.horizontalHeader().setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Fixed
        )
        self.file_table.setColumnWidth(3, 110)

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

        self.batch_format_combo = QComboBox()
        self.batch_format_combo.addItem("跟随全局", None)

        for target_format in TARGET_FORMAT_OPTIONS:
            self.batch_format_combo.addItem(target_format.upper(), target_format)

        self.apply_batch_format_button = QPushButton("应用到选中")
        self.apply_batch_format_button.clicked.connect(
            self.apply_batch_target_format
        )

        self.reset_batch_format_button = QPushButton("选中跟随全局")
        self.reset_batch_format_button.clicked.connect(
            self.reset_selected_target_formats
        )

        batch_format_layout = QHBoxLayout()
        batch_format_layout.addWidget(QLabel("选中目标格式"))
        batch_format_layout.addWidget(self.batch_format_combo)
        batch_format_layout.addWidget(self.apply_batch_format_button)
        batch_format_layout.addWidget(self.reset_batch_format_button)

        list_button_layout = QHBoxLayout()
        list_button_layout.addWidget(self.remove_button)
        list_button_layout.addWidget(self.clear_terminal_button)
        list_button_layout.addWidget(self.retry_failed_button)

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

        main_action_layout = QVBoxLayout()
        main_action_layout.addLayout(monitor_button_layout)
        main_action_layout.addWidget(self.convert_button)

        self.main_action_group = QGroupBox("主操作")
        self.main_action_group.setLayout(main_action_layout)

        # =========================
        # 日志窗口
        # =========================
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.append("GUI 已启动")

        # =========================
        # 添加组件
        # =========================
        layout.addWidget(self.overview_label)
        layout.addWidget(self.main_action_group)
        layout.addWidget(self.file_table)
        layout.addLayout(batch_format_layout)
        layout.addLayout(list_button_layout)
        layout.addWidget(self.settings_toggle_button)
        layout.addWidget(self.settings_panel)
        layout.addWidget(self.log_box)

        self.setLayout(layout)
        self.update_overview_label()
        self.start_file_list_timer()
        QTimer.singleShot(0, self.run_startup_flow)

    # =========================
    # 设置面板显示
    # =========================
    def toggle_settings_panel(self):
        is_visible = not self.settings_panel.isVisible()
        self.settings_panel.setVisible(is_visible)

        button_text = "隐藏设置" if is_visible else "显示设置"
        self.settings_toggle_button.setText(button_text)

    def show_settings_panel(self):
        self.settings_panel.setVisible(True)
        self.settings_toggle_button.setText("隐藏设置")

    # =========================
    # 顶部概览
    # =========================
    def update_overview_label(self):
        monitor_status = "监听中" if self._is_watcher_thread_running() else "未监听"
        auto_status = "自动监听开" if self.auto_start_checkbox.isChecked() else "自动监听关"
        scan_status = "启动扫描开" if self.scan_on_start_checkbox.isChecked() else "启动扫描关"

        self.overview_label.setText(
            "当前状态: "
            f"{monitor_status} | "
            f"输出 {self.format_combo.currentText().upper()} | "
            f"{auto_status} | "
            f"{scan_status}\n"
            f"监听: {get_watch_folder()}\n"
            f"输出: {get_output_folder()}"
        )
        self.update_tray_actions()

    # =========================
    # 托盘交互
    # =========================
    def update_tray_actions(self):
        if not hasattr(self, "tray_monitor_action"):
            return

        is_monitoring = self._is_watcher_thread_running()
        monitor_text = "停止监听" if is_monitoring else "开始监听"
        tooltip_status = "监听中" if is_monitoring else "未监听"

        self.tray_monitor_action.setText(monitor_text)
        self.tray_scan_action.setEnabled(not self._is_scan_thread_running())
        self.tray_convert_action.setEnabled(not self._is_convert_thread_running())
        self.tray_icon.setToolTip(
            f"CherryQ Audio Converter - {tooltip_status}"
        )

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
    def start_convert(self):
        if self._is_convert_thread_running():
            self.log_box.append("已有转换任务正在进行")
            return

        if not watcher.get_convertible_tasks():
            self.log_box.append("当前没有等待处理的文件")
            return

        self.log_conversion_summary()
        self.log_box.append("开始后台转换...")

        self.convert_thread = ConvertThread(
            self.format_combo.currentText(),
            self
        )
        self.convert_thread.finished.connect(
            self.on_convert_finished
        )
        self.convert_thread.start()
        self.update_tray_actions()

    def log_conversion_summary(self):
        default_target_format = self.format_combo.currentText()
        summary = {}

        for task in watcher.get_convertible_tasks():
            target_format = task.get("target_format") or default_target_format
            normalized = target_format.upper()
            summary[normalized] = summary.get(normalized, 0) + 1

        summary_text = "，".join(
            f"{target_format} {count} 个"
            for target_format, count in sorted(summary.items())
        )

        self.log_box.append(f"本轮转换摘要: {summary_text}")

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
            "CherryQ Audio Converter",
            "程序仍在后台运行",
            QSystemTrayIcon.Information,
            2000
        )

    def append_log(self, message):
        self.log_box.append(message)

    # =========================
    # 修改输出格式
    # =========================
    def change_format(self, value):
        self.config_data["target_format"] = value
        self.config_data = save_config(self.config_data)

        self.log_box.append(
            f"输出格式已修改: {value}"
        )
        self.refresh_file_table()
        self.update_overview_label()

    # =========================
    # 修改自动监听设置
    # =========================
    def change_auto_start_monitor(self, _state=None):
        enabled = self.auto_start_checkbox.isChecked()
        self.config_data["auto_start_monitor"] = enabled
        self.config_data = save_config(self.config_data)

        status_text = "开启" if enabled else "关闭"
        self.log_box.append(f"启动后自动监听已{status_text}")
        self.update_overview_label()

    # =========================
    # 修改启动扫描设置
    # =========================
    def change_scan_existing_on_start(self, _state=None):
        enabled = self.scan_on_start_checkbox.isChecked()
        self.config_data["scan_existing_on_start"] = enabled
        self.config_data = save_config(self.config_data)

        status_text = "开启" if enabled else "关闭"
        self.log_box.append(f"启动监听时扫描已有文件已{status_text}")
        self.update_overview_label()

    # =========================
    # 选择监听目录
    # =========================
    def select_watch_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择监听目录"
        )

        if folder:
            self.watch_label.setText(
                f"监听目录:\n{folder}"
            )

            self.config_data["watch_folder"] = folder
            self.config_data = save_config(self.config_data)

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
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择输出目录"
        )

        if folder:
            self.output_label.setText(
                f"输出目录:\n{folder}"
            )

            self.config_data["output_folder"] = folder
            self.config_data = save_config(self.config_data)

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
        self.start_file_list_timer()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.log_box.append("监听器已启动")
        self.update_overview_label()

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
        self.thread = WatcherThread(
            watch_folder,
            self
        )
        self.thread.finished.connect(
            self.on_watcher_finished
        )
        self.thread.start()

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

    # =========================
    # 重启 watcher 线程
    # =========================
    def restart_watcher(self, watch_folder):
        self.stop_watcher_thread()
        self.start_watcher_thread(watch_folder)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.log_box.append("监听目录切换完成")
        self.update_overview_label()

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

    # =========================
    # 转换线程结束回调
    # =========================
    def on_convert_finished(self):
        self.convert_thread = None

        if self.is_quitting:
            return

        self.log_box.append("本轮转换任务已结束")
        self.update_tray_actions()

    # =========================
    # 启动流程
    # =========================
    def run_startup_flow(self):
        if self.is_quitting:
            return

        if not is_valid_watch_folder():
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
                self.config_data = save_config(self.config_data)
                self.watch_label.setText(f"监听目录:\n{candidate}")
                self.log_box.append(f"已使用自动发现的监听目录:\n{candidate}")
                self.update_overview_label()

                if self.auto_start_checkbox.isChecked():
                    self.start_monitor()

                return

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
        if self._is_scan_thread_running():
            self.log_box.append("已有文件扫描正在进行")
            return

        watch_folder = get_watch_folder()

        if not is_valid_watch_folder(watch_folder):
            self.log_box.append(f"监听目录不存在，无法扫描已有文件:\n{watch_folder}")
            return

        self.log_box.append("开始扫描已有文件...")
        self.scan_existing_button.setEnabled(False)
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
        self.scan_status_label.setText(
            "扫描状态: "
            f"完成，扫描 {scanned_count}/{total_count} 个，"
            f"新增 {queued_count} 个，跳过 {skipped_count} 个"
        )
        self.log_box.append(
            "已有文件扫描结束: "
            f"扫描 {scanned_count}/{total_count} 个，"
            f"新增入列 {queued_count} 个，"
            f"跳过 {skipped_count} 个"
        )

    def on_scan_thread_stopped(self):
        self.scan_thread = None
        self.scan_existing_button.setEnabled(True)
        self.update_tray_actions()

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

    # =========================
    # 批量设置目标格式
    # =========================
    def apply_batch_target_format(self):
        target_format = self.batch_format_combo.currentData()
        self._set_selected_target_format(target_format)

    def reset_selected_target_formats(self):
        self._set_selected_target_format(None)

    def _set_selected_target_format(self, target_format):
        selected_paths = self._get_selected_file_paths()

        if not selected_paths:
            self.log_box.append("请先选择要设置目标格式的条目")
            return

        updated_count = 0

        for file_path in selected_paths:
            if watcher.set_pending_file_target_format(file_path, target_format):
                updated_count += 1

        if updated_count == 0:
            self.log_box.append("没有条目被更新，可能正在处理或已完成")
            return

        if target_format:
            self.log_box.append(
                f"已将 {updated_count} 个选中条目设置为 {target_format.upper()}"
            )
        else:
            self.log_box.append(
                f"已将 {updated_count} 个选中条目恢复为跟随全局"
            )

        self.refresh_file_table()

    # =========================
    # 重试失败条目
    # =========================
    def retry_failed_items(self):
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
        self.retry_failed_button.setEnabled(False)

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
        self.log_box.append(
            "失败条目重试结束: "
            f"尝试 {summary['attempted_count']} 个，"
            f"重新入列 {summary['requeued_count']} 个，"
            f"跳过 {summary['skipped_count']} 个"
        )

    def on_retry_thread_stopped(self):
        self.retry_thread = None
        self.retry_failed_button.setEnabled(True)

    def stop_retry_thread(self):
        if self.retry_thread is None:
            return

        if self.retry_thread.isRunning():
            self.log_box.append("正在停止失败重试任务...")
            self.retry_thread.stop()
            self.retry_thread.wait(5000)

        self.retry_thread = None
        self.retry_failed_button.setEnabled(True)

    def _get_selected_file_paths(self):
        selected_rows = sorted(
            {
                item.row()
                for item in self.file_table.selectedItems()
            }
        )

        if not selected_rows:
            return []

        tasks = watcher.get_task_snapshots()
        selected_paths = []

        for row in selected_rows:
            if row < len(tasks):
                selected_paths.append(tasks[row]["path"])

        return selected_paths

    # =========================
    # 移除选中条目
    # =========================
    def remove_selected_items(self):
        selected_rows = sorted(
            {
                item.row()
                for item in self.file_table.selectedItems()
            },
            reverse=True
        )

        if not selected_rows:
            self.log_box.append("请先选择要移除的条目")
            return

        pending_files = watcher.get_task_snapshots()
        removed_count = 0

        for row in selected_rows:
            if row >= len(pending_files):
                continue

            file_info = pending_files[row]
            file_path = file_info["path"]
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

    # =========================
    # 清除终态条目
    # =========================
    def clear_terminal_items(self):
        removed_count = watcher.clear_terminal_pending_files()

        if removed_count > 0:
            self.log_box.append(f"已清除 {removed_count} 条已完成/失败记录")
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
        if self._is_target_format_combo_active():
            return

        pending_files = watcher.get_task_snapshots()

        self.file_table.setRowCount(
            len(pending_files)
        )

        for row, file_info in enumerate(pending_files):
            self.file_table.setItem(
                row,
                0,
                self._make_table_item(
                    file_info["filename"]
                )
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
                self._make_table_item("")
            )
            self.file_table.setCellWidget(
                row,
                2,
                self._make_target_format_combo(file_info)
            )

            self.file_table.setItem(
                row,
                3,
                self._make_status_item(
                    file_info["status"]
                )
            )

    def _make_table_item(self, text):
        item = QTableWidgetItem(text)
        item.setToolTip(text)
        return item

    def _make_target_format_combo(self, file_info):
        default_format = self.format_combo.currentText().lower()
        selected_format = file_info.get("target_format")
        file_path = file_info["path"]

        combo = QComboBox()
        combo.setProperty("target_format_combo", True)
        combo.blockSignals(True)
        combo.addItem(f"跟随全局 ({default_format.upper()})", None)

        for target_format in TARGET_FORMAT_OPTIONS:
            combo.addItem(target_format.upper(), target_format)

        if selected_format:
            selected_index = combo.findData(selected_format)
        else:
            selected_index = 0

        combo.setCurrentIndex(max(selected_index, 0))
        combo.setEnabled(file_info.get("can_change_target_format", False))
        combo.setToolTip("为这个文件单独选择输出格式；未设置时跟随顶部全局输出格式")
        combo.blockSignals(False)
        combo.currentIndexChanged.connect(
            lambda _index, path=file_path, widget=combo: self.change_file_target_format(
                path,
                widget.currentData()
            )
        )

        return combo

    def _is_target_format_combo_active(self):
        widget = QApplication.focusWidget()

        while widget is not None:
            if widget.property("target_format_combo"):
                return True

            widget = widget.parent()

        return False

    def change_file_target_format(self, file_path, target_format):
        if watcher.set_pending_file_target_format(file_path, target_format):
            if target_format:
                self.log_box.append(
                    f"单文件输出格式已设置为 {target_format.upper()}"
                )
            else:
                self.log_box.append("单文件输出格式已恢复为跟随全局")

    def _make_status_item(self, status):
        status_display = watcher.get_status_display(status)
        label = status_display["label"]
        detail = status_display["detail"]
        item = QTableWidgetItem(label)

        item.setForeground(
            QBrush(
                QColor(status_display["color"])
            )
        )
        item.setToolTip(f"{label}: {detail}")

        return item


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
