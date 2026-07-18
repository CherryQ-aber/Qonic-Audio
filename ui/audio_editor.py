import math
import os
import re
import shutil
from pathlib import Path
import subprocess
import time

from PySide6.QtCore import QEvent, QSize, QThread, QUrl, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QTextCharFormat, QTextCursor, QTextFormat
from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QMenu,
    QMessageBox,
    QProxyStyle,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QScrollArea,
    QSlider,
    QSplitter,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTabWidget,
    QTextEdit,
    QToolTip,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from audio_editor_backend import process_pitch_shift
from config import FFMPEG_PATH, get_editor_output_folder, get_editor_temp_folder, load_config, save_config
from editor_workspace import AudioEditWorkspace
from formats import (
    EDITOR_AUDIO_EXTENSIONS,
    get_editor_audio_filter,
    get_source_format,
    is_supported_editor_audio_file,
    normalize_extension,
)
from lyrics import (
    audio_has_lyrics,
    embed_lrc_to_audio,
    find_matching_lrc,
    read_embedded_lyrics,
    read_lrc_file,
    write_lrc_file,
)
from metadata import (
    format_bit_depth,
    format_bitrate,
    format_duration as format_seconds_duration,
    format_file_size,
    format_modified_time,
    format_sample_rate,
    read_audio_cover_preview,
    read_audio_metadata,
    remove_audio_cover,
    write_audio_cover,
    write_audio_metadata,
)
from ui.status_widgets import StatusPill
from ui.waveform_widget import WaveformGenerateThread, WaveformWidget


def format_duration(ms):
    total_seconds = max(0, int(ms or 0) // 1000)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    return f"{minutes:02d}:{seconds:02d}"


LRC_TIMESTAMP_PATTERN = re.compile(r"\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]")
COVER_IMAGE_SIZE_WARNING_BYTES = 10 * 1024 * 1024
SUPPORTED_COVER_EXTENSIONS = {".jpg", ".jpeg", ".png"}
SUPPORTED_PITCH_AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".m4a", ".aac", ".ogg", ".opus"}
AUDIO_BROWSER_EXTENSIONS = EDITOR_AUDIO_EXTENSIONS | {".alac"}


def scan_audio_folder(folder_path):
    normalized_folder = os.path.normpath(os.path.abspath(folder_path))

    if not os.path.isdir(normalized_folder):
        return {
            "success": False,
            "folder": normalized_folder,
            "files": [],
            "error": "目录不存在，请重新选择",
        }

    files = []

    try:
        with os.scandir(normalized_folder) as entries:
            for entry in entries:
                if not entry.is_file():
                    continue

                extension = normalize_extension(entry.name)

                if extension not in AUDIO_BROWSER_EXTENSIONS:
                    continue

                try:
                    stat_result = entry.stat()
                except OSError:
                    continue

                files.append({
                    "path": os.path.normpath(os.path.abspath(entry.path)),
                    "filename": entry.name,
                    "ext": extension.lstrip(".").upper(),
                    "size": stat_result.st_size,
                    "modified_time": stat_result.st_mtime,
                })

    except OSError as e:
        return {
            "success": False,
            "folder": normalized_folder,
            "files": [],
            "error": str(e),
        }

    files.sort(key=lambda item: item["filename"].lower())
    return {
        "success": True,
        "folder": normalized_folder,
        "files": files,
        "error": None,
    }


def scan_audio_project_folders(folder_paths):
    normalized_roots = [
        os.path.normpath(os.path.abspath(folder))
        for folder in folder_paths
        if isinstance(folder, str) and folder.strip()
    ]
    files = []
    skipped = []

    for root_folder in normalized_roots:
        if not os.path.isdir(root_folder):
            skipped.append({"path": root_folder, "error": "目录不存在，请重新选择"})
            continue

        try:
            for current_dir, dir_names, file_names in os.walk(root_folder):
                dir_names.sort(key=str.lower)
                file_names.sort(key=str.lower)

                for filename in file_names:
                    extension = normalize_extension(filename)

                    if extension not in AUDIO_BROWSER_EXTENSIONS:
                        continue

                    path = os.path.normpath(os.path.abspath(os.path.join(current_dir, filename)))

                    try:
                        stat_result = os.stat(path)
                    except OSError:
                        continue

                    relative_dir = os.path.relpath(current_dir, root_folder)
                    rel_parts = [] if relative_dir == "." else relative_dir.split(os.sep)
                    files.append({
                        "path": path,
                        "filename": filename,
                        "ext": extension.lstrip(".").upper(),
                        "size": stat_result.st_size,
                        "modified_time": stat_result.st_mtime,
                        "root_path": root_folder,
                        "relative_dir_parts": rel_parts,
                    })
        except OSError as e:
            skipped.append({"path": root_folder, "error": str(e)})

    files.sort(key=lambda item: (
        os.path.normcase(item.get("root_path") or ""),
        [part.lower() for part in item.get("relative_dir_parts") or []],
        item.get("filename", "").lower(),
    ))
    return {
        "success": True,
        "folders": normalized_roots,
        "files": files,
        "skipped": skipped,
        "error": None,
    }



def parse_lrc_timestamps(text):
    entries = []

    for line_index, line in enumerate((text or "").splitlines()):
        matches = list(LRC_TIMESTAMP_PATTERN.finditer(line))

        if not matches:
            continue

        lyric_text = LRC_TIMESTAMP_PATTERN.sub("", line).strip()

        for match in matches:
            minutes = int(match.group(1))
            seconds = int(match.group(2))
            fraction = match.group(3) or "0"

            if len(fraction) == 1:
                milliseconds = int(fraction) * 100
            elif len(fraction) == 2:
                milliseconds = int(fraction) * 10
            else:
                milliseconds = int(fraction[:3])

            entries.append({
                "time_ms": (minutes * 60 + seconds) * 1000 + milliseconds,
                "line_index": line_index,
                "text": lyric_text,
            })

    return sorted(entries, key=lambda item: (item["time_ms"], item["line_index"]))


class PitchShiftThread(QThread):
    finished_signal = Signal(dict)

    def __init__(self, input_path, output_path, semitones, mode="export", parent=None):
        super().__init__(parent)
        self.input_path = input_path
        self.output_path = output_path
        self.semitones = semitones
        self.mode = mode

    def run(self):
        result = process_pitch_shift(
            self.input_path,
            self.output_path,
            self.semitones,
            preserve_metadata=True,
        )
        result["mode"] = self.mode
        self.finished_signal.emit(result)


class AudioBrowserScanThread(QThread):
    finished_signal = Signal(dict)

    def __init__(self, folder_paths, request_id, parent=None):
        super().__init__(parent)
        self.folder_paths = list(folder_paths or [])
        self.request_id = request_id

    def run(self):
        result = scan_audio_project_folders(self.folder_paths)
        result["request_id"] = self.request_id
        self.finished_signal.emit(result)


class AudioDeviceComboBox(QComboBox):
    about_to_show_popup = Signal()

    def showPopup(self):
        self.about_to_show_popup.emit()
        super().showPopup()


class AudioEditExportDialog(QDialog):
    def __init__(self, file_name, dirty_labels, default_output_path="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("导出当前编辑结果")
        self.setModal(True)
        self.setObjectName("AudioEditExportDialog")
        self.setMinimumWidth(440)
        self.default_output_path = default_output_path or ""
        self.setStyleSheet("""
            QDialog#AudioEditExportDialog QLabel#ExportDialogHeading {
                color: #E5EEF8;
                font-size: 13px;
                font-weight: 700;
            }
            QDialog#AudioEditExportDialog QLabel#ExportDialogFileName {
                color: #FFFFFF;
                font-size: 14px;
                font-weight: 700;
            }
            QDialog#AudioEditExportDialog QLabel#ExportDialogBody {
                color: #CBD5E1;
                line-height: 130%;
            }
            QDialog#AudioEditExportDialog QFrame#ExportDialogSection {
                border: 1px solid #26364D;
                border-radius: 6px;
                background: #0B1220;
            }
            QDialog#AudioEditExportDialog QRadioButton {
                spacing: 8px;
                color: #F8FAFC;
                min-height: 24px;
            }
            QDialog#AudioEditExportDialog QRadioButton::indicator {
                width: 15px;
                height: 15px;
                border-radius: 8px;
                border: 1px solid #8FA3BF;
                background: transparent;
            }
            QDialog#AudioEditExportDialog QRadioButton::indicator:hover {
                border: 1px solid #58A6FF;
            }
            QDialog#AudioEditExportDialog QRadioButton::indicator:checked {
                border: 1px solid #58A6FF;
                background: #58A6FF;
            }
            QDialog#AudioEditExportDialog QRadioButton::indicator:checked:hover {
                background: #6CB2FF;
            }
            QDialog#AudioEditExportDialog QComboBox#ExportFormatCombo {
                min-height: 28px;
                padding: 4px 34px 4px 10px;
                border: 1px solid #334155;
                border-radius: 4px;
                background: #101827;
                color: #CBD5E1;
            }
            QDialog#AudioEditExportDialog QComboBox#ExportFormatCombo:disabled {
                color: #94A3B8;
                background: #0F1726;
                border-color: #26364D;
            }
            QDialog#AudioEditExportDialog QComboBox#ExportFormatCombo::drop-down {
                width: 28px;
                border-left: 1px solid #334155;
            }
            QDialog#AudioEditExportDialog QComboBox#ExportFormatCombo::down-arrow {
                image: none;
                width: 0px;
                height: 0px;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #8FA3BF;
                margin-right: 8px;
            }
            QDialog#AudioEditExportDialog QLabel#ExportDialogHint {
                color: #94A3B8;
            }
            QDialog#AudioEditExportDialog QLineEdit#ExportPathEdit {
                min-height: 28px;
                padding: 4px 8px;
                border: 1px solid #334155;
                border-radius: 4px;
                background: #101827;
                color: #CBD5E1;
            }
            QDialog#AudioEditExportDialog QLineEdit#ExportPathEdit:disabled {
                color: #64748B;
                background: #0F1726;
                border-color: #26364D;
            }
            QDialog#AudioEditExportDialog QPushButton#ExportBrowseButton:disabled {
                color: #64748B;
            }
            QDialog#AudioEditExportDialog QLabel#ExportDialogWarning[danger="false"] {
                color: #94A3B8;
            }
            QDialog#AudioEditExportDialog QLabel#ExportDialogWarning[danger="true"] {
                color: #FBBF24;
                font-weight: 700;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(10)

        file_section, file_layout = self._make_section("当前文件")
        file_name_label = QLabel(file_name or "-")
        file_name_label.setObjectName("ExportDialogFileName")
        file_name_label.setWordWrap(True)
        file_layout.addWidget(file_name_label)
        layout.addWidget(file_section)

        changes_section, changes_layout = self._make_section("未导出修改")
        dirty_text = "\n".join(f"• {label}" for label in dirty_labels) if dirty_labels else "• 当前没有需要导出的修改"
        dirty_label = QLabel(dirty_text)
        dirty_label.setObjectName("ExportDialogBody")
        dirty_label.setWordWrap(True)
        changes_layout.addWidget(dirty_label)
        layout.addWidget(changes_section)

        mode_section, mode_layout = self._make_section("导出方式")
        self.save_as_radio = QRadioButton("另存为新文件（推荐）")
        self.save_as_radio.setChecked(True)
        self.overwrite_radio = QRadioButton("覆盖原文件")
        self.overwrite_radio.setToolTip("覆盖原文件前会二次确认，并先导出到临时文件再替换。")
        self.overwrite_radio.toggled.connect(self._update_warning_state)
        mode_layout.addWidget(self.save_as_radio)
        mode_layout.addWidget(self.overwrite_radio)
        layout.addWidget(mode_section)

        format_section, format_section_layout = self._make_section("导出格式")
        format_layout = QGridLayout()
        format_layout.setContentsMargins(0, 0, 0, 0)
        self.export_format_combo = QComboBox()
        self.export_format_combo.setObjectName("ExportFormatCombo")
        self.export_format_combo.addItem("保持原格式", None)
        self.export_format_combo.setEnabled(False)
        self.export_format_combo.setToolTip("当前版本仅支持保持原格式；后续预留 MP3 / FLAC / WAV / M4A / OGG / OPUS。")
        format_layout.addWidget(self.export_format_combo, 0, 0)
        format_layout.setColumnStretch(0, 1)
        format_section_layout.addLayout(format_layout)
        format_hint = QLabel("格式转换将在后续版本支持。")
        format_hint.setObjectName("ExportDialogHint")
        format_hint.setWordWrap(True)
        format_section_layout.addWidget(format_hint)
        layout.addWidget(format_section)

        location_section, location_section_layout = self._make_section("导出位置")
        location_layout = QGridLayout()
        location_layout.setContentsMargins(0, 0, 0, 0)
        self.output_path_edit = QLineEdit(self.default_output_path)
        self.output_path_edit.setObjectName("ExportPathEdit")
        self.output_path_edit.setReadOnly(True)
        self.browse_output_button = QPushButton("浏览...")
        self.browse_output_button.setObjectName("ExportBrowseButton")
        self.browse_output_button.clicked.connect(self._browse_output_path)
        location_layout.addWidget(self.output_path_edit, 0, 0)
        location_layout.addWidget(self.browse_output_button, 0, 1)
        location_layout.setColumnStretch(0, 1)
        location_section_layout.addLayout(location_layout)
        self.output_path_hint = QLabel()
        self.output_path_hint.setObjectName("ExportDialogHint")
        self.output_path_hint.setWordWrap(True)
        location_section_layout.addWidget(self.output_path_hint)
        layout.addWidget(location_section)

        self.warning_label = QLabel()
        self.warning_label.setObjectName("ExportDialogWarning")
        self.warning_label.setWordWrap(True)
        layout.addWidget(self.warning_label)
        self._update_warning_state(False)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("导出")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _make_section(self, title):
        frame = QFrame()
        frame.setObjectName("ExportDialogSection")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)
        title_label = QLabel(title)
        title_label.setObjectName("ExportDialogHeading")
        layout.addWidget(title_label)
        return frame, layout

    def _update_warning_state(self, overwrite_checked):
        is_danger = bool(overwrite_checked)
        self.output_path_edit.setEnabled(not is_danger)
        self.browse_output_button.setEnabled(not is_danger)
        if is_danger:
            self.output_path_hint.setText("覆盖原文件时不使用另存路径。")
        else:
            self.output_path_hint.setText("点击“导出”将直接使用此路径。")
        self.warning_label.setProperty("danger", is_danger)
        if is_danger:
            self.warning_label.setText("风险提示：覆盖原文件会直接替换当前音频。建议优先另存为新文件。")
        else:
            self.warning_label.setText("提示：覆盖原文件会直接替换当前音频。建议优先另存为新文件。")
        self.warning_label.style().unpolish(self.warning_label)
        self.warning_label.style().polish(self.warning_label)

    def _browse_output_path(self):
        current_path = self.output_path_edit.text().strip() or self.default_output_path
        current_ext = os.path.splitext(current_path)[1]
        file_filter = f"音频文件 (*{current_ext});;所有文件 (*.*)" if current_ext else "所有文件 (*.*)"
        selected_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "选择导出位置",
            current_path,
            file_filter,
        )

        if selected_path:
            self.output_path_edit.setText(os.path.normpath(selected_path))

    def export_mode(self):
        return "overwrite" if self.overwrite_radio.isChecked() else "save_as"

    def target_format(self):
        return self.export_format_combo.currentData()

    def output_path(self):
        return self.output_path_edit.text().strip()


class ElidedLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__("", parent)
        self._full_text = ""
        self.setWordWrap(False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.set_full_text(text)

    def set_full_text(self, text):
        self._full_text = str(text or "")
        self._refresh_elide()

    def full_text(self):
        return self._full_text

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_elide()

    def _refresh_elide(self):
        available_width = max(20, self.width() or 160)
        elided_text = self.fontMetrics().elidedText(
            self._full_text,
            Qt.TextElideMode.ElideMiddle,
            available_width,
        )
        super().setText(elided_text)


class MetadataCommentBox(QTextEdit):
    def text(self):
        return self.toPlainText()


class NoFocusTreeItemDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        option_without_focus = QStyleOptionViewItem(option)
        option_without_focus.state &= ~QStyle.StateFlag.State_HasFocus
        super().paint(painter, option_without_focus, index)


class BrowserTreeChevronStyle(QProxyStyle):
    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PrimitiveElement.PE_IndicatorBranch:
            has_children = bool(option.state & QStyle.StateFlag.State_Children)

            if not has_children:
                return

            is_open = bool(option.state & QStyle.StateFlag.State_Open)
            rect = option.rect
            center = rect.center()
            size = 4

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            pen = QPen(QColor("#8FA3BF"))
            pen.setWidthF(1.4)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)

            if is_open:
                painter.drawLine(center.x() - size, center.y() - 1, center.x(), center.y() + size)
                painter.drawLine(center.x(), center.y() + size, center.x() + size, center.y() - 1)
            else:
                painter.drawLine(center.x() - 1, center.y() - size, center.x() + size, center.y())
                painter.drawLine(center.x() + size, center.y(), center.x() - 1, center.y() + size)

            painter.restore()
            return

        super().drawPrimitive(element, option, painter, widget)


class AudioEditorWorkspace(QWidget):

    def __init__(self, parent=None, log_callback=None, config_saver=None):
        super().__init__(parent)
        self.log_callback = log_callback
        self._config_saver = config_saver
        self.config_data = load_config()
        self.current_audio_path = None
        self.current_audio_display_name = ""
        self.edit_workspace = None
        self.is_workspace_exporting = False
        self.playback_source_path = None
        self.playback_source_type = "none"
        self.playback_source_label = "未加载"
        self.current_play_source_path = None
        self.current_play_source_type = "none"
        self.player_status = "stopped"
        self.position_ms = 0
        self.volume = 80
        self.waveform_status = "未加载"
        self.waveform_thread = None
        self._stale_waveform_threads = []
        self.current_waveform_source_path = None
        self.editor_output_folder = os.path.normpath(os.path.abspath(get_editor_output_folder()))
        self.editor_temp_folder = os.path.normpath(os.path.abspath(get_editor_temp_folder()))
        self.editor_browser_folder = str(self.config_data.get("editor_browser_folder") or "")
        self.editor_project_folders = self._normalize_project_folders(
            self.config_data.get("editor_project_folders") or [],
            self.editor_browser_folder,
        )
        self.editor_browser_collapsed = self.config_data.get("editor_browser_collapsed") is True
        self.browser_all_files = []
        self.browser_selected_file_path = None
        self.browser_selected_file_info = None
        self.browser_scan_thread = None
        self.browser_scan_request_id = 0
        self._ensure_editor_directories()
        self.saved_audio_output_device_id = str(self.config_data.get("audio_output_device_id") or "")
        self.saved_audio_output_device_name = str(self.config_data.get("audio_output_device_name") or "")
        self.current_audio_output_device_id = ""
        self.current_audio_output_device_name = "系统默认输出"
        self.audio_output_device_applied = False
        self._refreshing_audio_output_devices = False
        self.duration_ms = 0
        self.is_slider_pressed = False
        self.file_load_status = "等待导入"
        self.playback_status = "未播放"
        self.lyrics_status = "未加载歌词"
        self.error_text = ""
        self.current_lrc_path = None
        self.current_lrc_source = ""
        self.pending_lrc_path = None
        self.original_lrc_text = ""
        self.current_lrc_text = ""
        self.current_lyrics_text = ""
        self.current_lyrics_source_path = None
        self.current_lyrics_source_type = None
        self.lyrics_dirty = False
        self.is_manual_lyrics = False
        self.is_lyrics_editing = False
        self.has_netease_metadata_warning = False
        self.current_audio_metadata = None
        self.metadata_dirty = False
        self.metadata_form_dirty = False
        self.is_metadata_editing = False
        self.original_metadata = None
        self.current_metadata_form = {}
        self.custom_metadata_tags = {}
        self.original_custom_metadata_tags = {}
        self.custom_metadata_dirty = False
        self._updating_metadata_form = False
        self.original_cover_data = None
        self.original_cover_mime = None
        self.original_cover_source = ""
        self.current_cover_data = None
        self.current_cover_mime = None
        self.current_cover_source = ""
        self.cover_dirty = False
        self.cover_marked_for_removal = False
        self.cover_status = "未读取封面"
        self.pitch_shift_thread = None
        self.pitch_shift_player_state = None
        self.pitch_shift_original_path = None
        self.pitch_shift_output_path = None
        self.pitch_shift_mode = None
        self.pitch_shift_semitones = None
        self.pitch_preview_path = None
        self.current_pitch_preview_path = None
        self.current_pitch_preview_semitones = None
        self.last_exported_audio_path = None
        self.is_pitch_preview_loaded = False
        self.current_lrc_entries = []
        self.current_sync_entry_index = None
        self.current_sync_line_index = None
        self.sync_lyrics_enabled = True
        self.lyrics_sync_status = "未解析歌词时间轴"
        self.last_lyrics_sync_position = None

        self.setAcceptDrops(True)
        self._setup_player()
        self._build_ui()
        self._refresh_file_info()
        self._refresh_output_folder()
        self._clear_audio_metadata_display()
        self._clear_lyrics_preview()
        self._restore_editor_browser_folder()
        self.update_editor_status_panel()

    def _setup_player(self):
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(0.8)
        self.player.setAudioOutput(self.audio_output)
        self.media_devices = QMediaDevices(self)

        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_playback_state_changed)
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.player.errorOccurred.connect(self._on_player_error)

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        title = QLabel("音频编辑")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        layout.addWidget(self._build_info_group())
        layout.addWidget(self._build_player_group())

        self.workspace_tabs = QTabWidget()
        self.workspace_tabs.setObjectName("AudioEditorWorkspaceTabs")
        self.workspace_tabs.addTab(self._build_metadata_tab(), "元数据")
        self.workspace_tabs.addTab(self._build_lyrics_tab(), "歌词编辑")
        self.workspace_tabs.addTab(self._build_pitch_tab(), "升降调")
        layout.addWidget(self.workspace_tabs, 1)

        layout.addWidget(self._build_status_group())
        scroll_area.setWidget(content)
        self.browser_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.browser_splitter.setChildrenCollapsible(False)
        self.browser_splitter.addWidget(self._build_browser_sidebar())
        self.browser_splitter.addWidget(scroll_area)
        self.browser_splitter.setStretchFactor(0, 0)
        self.browser_splitter.setStretchFactor(1, 1)
        self.browser_splitter.setSizes([260, 980])
        root_layout.addWidget(self.browser_splitter, 1)
        self.set_browser_sidebar_collapsed(self.editor_browser_collapsed, persist=False)

    def _build_browser_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("AudioBrowserSidebar")
        sidebar.setFrameShape(QFrame.Shape.StyledPanel)
        sidebar.setMinimumWidth(220)
        sidebar.setMaximumWidth(340)
        self.browser_sidebar = sidebar

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(4)
        self.browser_title_label = QLabel("文件目录")
        self.browser_title_label.setObjectName("DetailLabel")
        self.browser_toggle_button = QPushButton("◀")
        self.browser_toggle_button.setFixedWidth(34)
        self.browser_toggle_button.setToolTip("收起文件目录")
        self.browser_toggle_button.clicked.connect(self.toggle_browser_sidebar)
        header_layout.addWidget(self.browser_title_label, 1)
        header_layout.addWidget(self.browser_toggle_button)
        layout.addLayout(header_layout)

        self.browser_content_widget = QWidget()
        content_layout = QVBoxLayout(self.browser_content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(6)

        self.browser_folder_value = self._make_value_label()
        self.browser_folder_value.setText("未添加项目文件夹")
        content_layout.addWidget(self.browser_folder_value)

        choose_button = QPushButton("添加文件夹")
        choose_button.clicked.connect(self.select_editor_browser_folder)
        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self.refresh_editor_browser_folder)
        open_button = QPushButton("打开")
        open_button.clicked.connect(self.open_editor_browser_folder)

        top_buttons = QHBoxLayout()
        top_buttons.addWidget(choose_button)
        top_buttons.addWidget(refresh_button)
        top_buttons.addWidget(open_button)
        content_layout.addLayout(top_buttons)

        self.browser_filter_edit = QLineEdit()
        self.browser_filter_edit.setPlaceholderText("搜索文件名")
        self.browser_filter_edit.textChanged.connect(self.apply_browser_filter)
        content_layout.addWidget(self.browser_filter_edit)

        self.browser_tree = QTreeWidget()
        self.browser_tree.setHeaderHidden(True)
        self.browser_tree.setColumnCount(1)
        self.browser_tree.setIndentation(12)
        self.browser_tree.setRootIsDecorated(True)
        self.browser_tree.setItemsExpandable(True)
        self.browser_tree.setAllColumnsShowFocus(False)
        self.browser_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.browser_tree.setUniformRowHeights(True)
        self.browser_tree.setAnimated(False)
        self.browser_tree.setExpandsOnDoubleClick(False)
        self.browser_tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.browser_tree.setMouseTracking(True)
        self.browser_tree.viewport().setMouseTracking(True)
        self.browser_tree.setAcceptDrops(False)
        self.browser_tree.setStyleSheet(
            """
            QTreeWidget {
                outline: 0;
                border: none;
                show-decoration-selected: 0;
            }
            QTreeWidget::item {
                padding: 2px 4px;
                min-height: 22px;
                border: none;
                margin: 0;
                outline: none;
            }
            QTreeWidget::item:focus {
                outline: none;
                border: none;
            }
            QTreeWidget::item:hover {
                background: rgba(80, 140, 220, 0.18);
                border: none;
                outline: none;
            }
            QTreeWidget::item:selected {
                background: rgba(80, 140, 220, 0.42);
                border: none;
                outline: none;
            }
            QTreeWidget::item:selected:hover {
                background: rgba(80, 140, 220, 0.50);
                border: none;
                outline: none;
            }
            """
        )
        self.browser_tree_chevron_style = BrowserTreeChevronStyle(self.browser_tree.style())
        self.browser_tree.setStyle(self.browser_tree_chevron_style)
        self.browser_tree.setItemDelegate(NoFocusTreeItemDelegate(self.browser_tree))
        self.browser_tree.itemSelectionChanged.connect(self.on_browser_selection_changed)
        self.browser_tree.itemDoubleClicked.connect(self.on_browser_item_double_clicked)
        self.browser_tree.itemExpanded.connect(self.on_browser_folder_expanded)
        self.browser_tree.itemCollapsed.connect(self.on_browser_folder_collapsed)
        self.browser_tree.installEventFilter(self)
        self.browser_tree.viewport().installEventFilter(self)
        self.browser_list = self.browser_tree
        content_layout.addWidget(self.browser_tree, 1)

        self.browser_preview_frame = QFrame()
        self.browser_preview_frame.setObjectName("AudioBrowserPreview")
        self.browser_preview_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.browser_preview_frame.setMinimumHeight(76)
        self.browser_preview_frame.setMaximumHeight(96)
        preview_layout = QHBoxLayout(self.browser_preview_frame)
        preview_layout.setContentsMargins(6, 6, 6, 6)
        preview_layout.setSpacing(6)

        self.browser_preview_cover = QLabel("无封面")
        self.browser_preview_cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.browser_preview_cover.setFixedSize(56, 56)
        self.browser_preview_cover.setFrameShape(QFrame.Shape.StyledPanel)
        self.browser_preview_cover.setWordWrap(True)

        preview_text_layout = QVBoxLayout()
        preview_text_layout.setContentsMargins(0, 0, 0, 0)
        preview_text_layout.setSpacing(2)
        self.browser_preview_name = ElidedLabel("未选择文件")
        self.browser_preview_name.setObjectName("DetailValue")
        self.browser_preview_name.setMaximumHeight(22)
        self.browser_preview_name.setMinimumWidth(0)
        self.browser_preview_detail = QLabel("-")
        self.browser_preview_detail.setObjectName("MutedLabel")
        self.browser_preview_detail.setWordWrap(False)
        preview_text_layout.addWidget(self.browser_preview_name)
        preview_text_layout.addWidget(self.browser_preview_detail)
        preview_text_layout.addStretch(1)

        preview_layout.addWidget(self.browser_preview_cover)
        preview_layout.addLayout(preview_text_layout, 1)
        content_layout.addWidget(self.browser_preview_frame)
        self._reset_browser_preview(clear_selection=True)

        self.browser_status_text = "空闲"
        layout.addWidget(self.browser_content_widget, 1)
        return sidebar

    def _build_info_group(self):
        group = QGroupBox("文件信息")
        layout = QGridLayout(group)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(6)

        self.file_name_value = self._make_value_label()
        self.file_path_value = self._make_value_label()
        self.file_format_value = self._make_value_label()
        self.playback_source_value = self._make_value_label()
        self.original_file_state_value = self._make_value_label()
        self.unsaved_state_value = self._make_value_label()
        self.editor_output_path_value = self._make_value_label()
        self.editor_temp_path_value = self._make_value_label()
        self.audio_output_device_combo = self._build_audio_output_device_combo()

        rows = [
            ("编辑文件", self.file_name_value, "输出设备", self.audio_output_device_combo),
            ("路径", self.file_path_value, "播放器正在预览", self.playback_source_value),
            ("格式", self.file_format_value, "原文件状态", self.original_file_state_value),
            ("编辑区输出目录", self.editor_output_path_value, "修改内容", self.unsaved_state_value),
            ("编辑区临时缓存", self.editor_temp_path_value, None, None),
        ]

        for row, (left_label, left_value, right_label, right_value) in enumerate(rows):
            layout.addWidget(self._make_detail_label(left_label), row, 0)
            layout.addWidget(left_value, row, 1)

            if right_value is not None:
                layout.addWidget(self._make_detail_label(right_label), row, 2)
                layout.addWidget(right_value, row, 3)

        import_button = QPushButton("导入音频")
        import_button.clicked.connect(self.select_audio_file)

        clear_button = QPushButton("清除当前音频")
        clear_button.clicked.connect(self.clear_current_audio)

        open_source_button = QPushButton("打开文件位置")
        open_source_button.clicked.connect(self.open_current_audio_folder)

        self.return_current_playback_button = QPushButton("返回原音频预览")
        self.return_current_playback_button.clicked.connect(self.return_to_current_audio_playback)
        self.return_current_playback_button.setEnabled(False)

        self.export_workspace_button = QPushButton("导出")
        self.export_workspace_button.clicked.connect(self.show_export_workspace_dialog)
        self.export_workspace_button.setEnabled(False)

        button_layout = QHBoxLayout()
        button_layout.addWidget(import_button)
        button_layout.addWidget(clear_button)
        button_layout.addWidget(open_source_button)
        button_layout.addWidget(self.return_current_playback_button)
        button_layout.addWidget(self.export_workspace_button)
        button_layout.addStretch(1)

        layout.addLayout(button_layout, len(rows), 0, 1, 4)
        layout.setColumnStretch(1, 3)
        layout.setColumnStretch(3, 2)

        return group

    def _build_audio_output_device_combo(self):
        combo = AudioDeviceComboBox()
        combo.setMinimumWidth(260)
        combo.setMaximumWidth(360)
        combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        audio_device_view = QListView(combo)
        audio_device_view.setObjectName("HardEdgeComboPopup")
        audio_device_view.setMouseTracking(True)
        audio_device_view.viewport().setMouseTracking(True)
        combo.setView(audio_device_view)
        combo.about_to_show_popup.connect(self.refresh_audio_output_devices_before_popup)
        combo.currentIndexChanged.connect(self.on_audio_output_device_changed)
        self.audio_output_device_combo = combo
        self.refresh_audio_output_devices()
        self.apply_audio_output_device(self.get_selected_audio_output_device(), persist=False)
        return combo

    def _build_metadata_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        layout.addWidget(self._build_metadata_group(), 1)
        return page

    def _build_lyrics_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        layout.addWidget(self._build_lyrics_group(), 1)
        return page

    def _build_pitch_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        note = QLabel("内容处理会改变音频声音结果。默认不修改原文件，请先试听，再加入工作区后通过顶部“导出”统一输出。")
        note.setObjectName("MutedLabel")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addWidget(self._build_pitch_shift_group())
        layout.addStretch(1)
        return page

    def _build_metadata_group(self):
        group = QGroupBox("元数据")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self.cover_label = QLabel("未加载")
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setFixedSize(140, 140)
        self.cover_label.setFrameShape(QFrame.Shape.StyledPanel)
        self.cover_label.setObjectName("CoverPreview")
        self.cover_label.setWordWrap(True)
        self.cover_label.setToolTip("右键封面可导入、移除、恢复、写入。")

        cover_panel = QFrame()
        cover_panel.setObjectName("MetadataCoverPanel")
        cover_layout = QVBoxLayout(cover_panel)
        cover_layout.setContentsMargins(0, 0, 0, 0)
        cover_layout.setSpacing(6)
        cover_layout.addWidget(self.cover_label, 0, Qt.AlignmentFlag.AlignHCenter)

        self.setup_cover_context_menu()

        cover_context_hint = QLabel("右键封面可导入、移除、恢复；最终通过顶部“导出”统一写入。")
        cover_context_hint.setObjectName("MutedLabel")
        cover_context_hint.setWordWrap(True)
        cover_layout.addWidget(cover_context_hint)
        cover_layout.addStretch(1)

        common_group = QGroupBox("常用标签")
        common_layout = QGridLayout(common_group)
        common_layout.setHorizontalSpacing(10)
        common_layout.setVerticalSpacing(6)
        self.metadata_title_value = self._make_metadata_edit()
        self.metadata_artist_value = self._make_metadata_edit()
        self.metadata_album_value = self._make_metadata_edit()
        self.metadata_album_artist_value = self._make_metadata_edit()
        self.metadata_date_value = self._make_metadata_edit()
        self.metadata_genre_value = self._make_metadata_edit()
        self.metadata_track_value = self._make_metadata_edit()
        self.metadata_disc_value = self._make_metadata_edit()
        self.metadata_bpm_value = self._make_metadata_edit()
        self.metadata_key_value = self._make_metadata_edit()
        self.metadata_comment_value = self._make_metadata_comment_box()

        common_layout.addWidget(self._make_detail_label("标题"), 0, 0)
        common_layout.addWidget(self.metadata_title_value, 0, 1, 1, 3)
        common_layout.addWidget(self._make_detail_label("艺术家"), 1, 0)
        common_layout.addWidget(self.metadata_artist_value, 1, 1, 1, 3)
        common_layout.addWidget(self._make_detail_label("专辑"), 2, 0)
        common_layout.addWidget(self.metadata_album_value, 2, 1, 1, 3)
        common_layout.addWidget(self._make_detail_label("专辑艺术家"), 3, 0)
        common_layout.addWidget(self.metadata_album_artist_value, 3, 1, 1, 3)
        common_layout.addWidget(self._make_detail_label("年份 / 日期"), 4, 0)
        common_layout.addWidget(self.metadata_date_value, 4, 1)
        common_layout.addWidget(self._make_detail_label("风格"), 4, 2)
        common_layout.addWidget(self.metadata_genre_value, 4, 3)
        common_layout.addWidget(self._make_detail_label("轨道号"), 5, 0)
        common_layout.addWidget(self.metadata_track_value, 5, 1)
        common_layout.addWidget(self._make_detail_label("碟号"), 5, 2)
        common_layout.addWidget(self.metadata_disc_value, 5, 3)
        common_layout.addWidget(self._make_detail_label("BPM"), 6, 0)
        common_layout.addWidget(self.metadata_bpm_value, 6, 1)
        common_layout.addWidget(self._make_detail_label("Key / Initial Key"), 6, 2)
        common_layout.addWidget(self.metadata_key_value, 6, 3)
        common_layout.addWidget(self._make_detail_label("备注"), 7, 0)
        common_layout.addWidget(self.metadata_comment_value, 7, 1, 1, 3)
        common_layout.setColumnStretch(1, 1)
        common_layout.setColumnStretch(3, 1)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(12)
        top_layout.addWidget(cover_panel, 0)
        top_layout.addWidget(common_group, 1)
        layout.addLayout(top_layout)

        technical_group = QGroupBox("文件 / 技术信息")
        technical_layout = QGridLayout(technical_group)
        technical_layout.setHorizontalSpacing(10)
        technical_layout.setVerticalSpacing(5)
        self.metadata_filename_value = self._make_value_label()
        self.metadata_path_value = self._make_value_label()
        self.metadata_modified_value = self._make_value_label()
        self.metadata_format_value = self._make_value_label()
        self.metadata_container_value = self._make_value_label()
        self.metadata_codec_value = self._make_value_label()
        self.metadata_file_size_value = self._make_value_label()
        self.metadata_duration_value = self._make_value_label()
        self.metadata_sample_rate_value = self._make_value_label()
        self.metadata_bitrate_value = self._make_value_label()
        self.metadata_channels_value = self._make_value_label()
        self.metadata_bit_depth_value = self._make_value_label()
        self.metadata_status_value = self._make_value_label()
        self.cover_status_value = self._make_value_label()
        self.cover_source_value = self._make_value_label()

        tech_rows = [
            ("文件名", self.metadata_filename_value, "格式 / 编码", self.metadata_format_value),
            ("大小", self.metadata_file_size_value, "时长", self.metadata_duration_value),
            ("采样率", self.metadata_sample_rate_value, "码率", self.metadata_bitrate_value),
            ("声道", self.metadata_channels_value, "位深", self.metadata_bit_depth_value),
            ("最后修改", self.metadata_modified_value, "读取状态", self.metadata_status_value),
            ("封面状态", self.cover_status_value, "封面来源", self.cover_source_value),
        ]

        for row, (left_label, left_value, right_label, right_value) in enumerate(tech_rows):
            technical_layout.addWidget(self._make_detail_label(left_label), row, 0)
            technical_layout.addWidget(left_value, row, 1)
            technical_layout.addWidget(self._make_detail_label(right_label), row, 2)
            technical_layout.addWidget(right_value, row, 3)

        path_row = len(tech_rows)
        technical_layout.addWidget(self._make_detail_label("完整路径"), path_row, 0)
        technical_layout.addWidget(self.metadata_path_value, path_row, 1, 1, 3)
        technical_layout.setColumnStretch(1, 1)
        technical_layout.setColumnStretch(3, 1)
        layout.addWidget(technical_group)

        custom_group = QGroupBox("扩展标签")
        custom_layout = QVBoxLayout(custom_group)
        custom_layout.setSpacing(6)
        custom_hint = QLabel("非常用标签仅保存在当前编辑区状态；当前版本不会自动写入音频文件。")
        custom_hint.setObjectName("MutedLabel")
        custom_hint.setWordWrap(True)
        custom_layout.addWidget(custom_hint)

        custom_input_layout = QHBoxLayout()
        custom_input_layout.setSpacing(6)
        self.custom_metadata_name_edit = QLineEdit()
        self.custom_metadata_name_edit.setPlaceholderText("标签名，例如 composer")
        self.custom_metadata_value_edit = QLineEdit()
        self.custom_metadata_value_edit.setPlaceholderText("标签值")
        self.add_custom_metadata_button = QPushButton("添加标签")
        self.add_custom_metadata_button.clicked.connect(self.add_custom_metadata_tag)
        self.remove_custom_metadata_button = QPushButton("移除选中")
        self.remove_custom_metadata_button.clicked.connect(self.remove_selected_custom_metadata_tag)
        custom_input_layout.addWidget(self.custom_metadata_name_edit, 1)
        custom_input_layout.addWidget(self.custom_metadata_value_edit, 2)
        custom_input_layout.addWidget(self.add_custom_metadata_button)
        custom_input_layout.addWidget(self.remove_custom_metadata_button)
        custom_layout.addLayout(custom_input_layout)

        self.custom_metadata_tree = QTreeWidget()
        self.custom_metadata_tree.setHeaderLabels(["标签名", "标签值"])
        self.custom_metadata_tree.setRootIsDecorated(False)
        self.custom_metadata_tree.setAlternatingRowColors(False)
        self.custom_metadata_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.custom_metadata_tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.custom_metadata_tree.setMinimumHeight(88)
        self.custom_metadata_tree.setMaximumHeight(128)
        self.custom_metadata_tree.setColumnWidth(0, 140)
        custom_layout.addWidget(self.custom_metadata_tree)
        layout.addWidget(custom_group)

        metadata_button_layout = QGridLayout()
        metadata_button_layout.setHorizontalSpacing(8)
        metadata_button_layout.setVerticalSpacing(6)

        self.metadata_edit_button = QPushButton("编辑信息")
        self.metadata_edit_button.setMinimumWidth(104)
        self.metadata_edit_button.clicked.connect(self.toggle_metadata_edit_mode)

        self.metadata_restore_button = QPushButton("恢复原信息")
        self.metadata_restore_button.setMinimumWidth(104)
        self.metadata_restore_button.clicked.connect(self.restore_audio_metadata)

        self.metadata_write_button = QPushButton("加入导出修改")
        self.metadata_write_button.setMinimumWidth(116)
        self.metadata_write_button.clicked.connect(self.write_current_audio_metadata)

        metadata_button_layout.addWidget(self.metadata_edit_button, 0, 0)
        metadata_button_layout.addWidget(self.metadata_restore_button, 0, 1)
        metadata_button_layout.addWidget(self.metadata_write_button, 1, 0, 1, 2)
        layout.addLayout(metadata_button_layout)
        layout.addStretch(1)
        self._refresh_custom_metadata_table()
        return group

    def _build_import_group(self):
        group = QGroupBox("导入区域")
        group.setAcceptDrops(True)
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self.drop_hint_label = QLabel(
            "可拖入单个普通音频文件到此工作区。"
        )
        self.drop_hint_label.setObjectName("MutedLabel")
        self.drop_hint_label.setWordWrap(True)

        import_button = QPushButton("导入音频")
        import_button.clicked.connect(self.select_audio_file)

        clear_button = QPushButton("清除当前音频")
        clear_button.clicked.connect(self.clear_current_audio)

        open_source_button = QPushButton("打开原文件位置")
        open_source_button.clicked.connect(self.open_current_audio_folder)

        button_layout = QHBoxLayout()
        button_layout.addWidget(import_button)
        button_layout.addWidget(clear_button)
        button_layout.addWidget(open_source_button)
        button_layout.addStretch(1)

        layout.addWidget(self.drop_hint_label)
        layout.addLayout(button_layout)
        return group

    def _build_player_group(self):
        group = QFrame()
        group.setObjectName("PlayerControlBar")
        group.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        control_layout = QHBoxLayout()
        control_layout.setSpacing(8)

        self.play_pause_button = QPushButton("播放")
        self.play_pause_button.clicked.connect(self.toggle_playback)
        self.play_pause_button.setEnabled(False)

        self.stop_button = QPushButton("停止")
        self.stop_button.clicked.connect(self.stop_playback)
        self.stop_button.setEnabled(False)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setObjectName("DetailValue")
        self.player_source_hint_label = self._make_value_label()
        self.player_source_hint_label.setText("播放器正在预览：未加载")
        self.player_status_hint_label = self._make_value_label()
        self.player_status_hint_label.setText("播放状态：未播放")
        self.waveform_status_label = self._make_value_label()
        self.waveform_status_label.setText("波形预览：未加载")
        self.waveform_widget = WaveformWidget()
        self.waveform_widget.seek_requested.connect(self.seek_waveform_position)

        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderPressed.connect(self._on_slider_pressed)
        self.position_slider.sliderReleased.connect(self._on_slider_released)
        self.position_slider.sliderMoved.connect(self._on_slider_moved)
        self.position_slider.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.position_slider.customContextMenuRequested.connect(
            self.show_progress_slider_context_menu
        )

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setFixedWidth(130)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        self.setup_player_hover_tips()

        control_layout.addWidget(self.play_pause_button)
        control_layout.addWidget(self.stop_button)
        control_layout.addWidget(self.time_label)
        control_layout.addWidget(self.player_source_hint_label)
        control_layout.addWidget(self._make_detail_label("进度"))
        control_layout.addWidget(self.position_slider, 1)
        control_layout.addWidget(self._make_detail_label("音量"))
        control_layout.addWidget(self.volume_slider)

        status_layout = QHBoxLayout()
        status_layout.setSpacing(12)
        status_layout.addWidget(self.player_status_hint_label)
        status_layout.addWidget(self.waveform_status_label)
        status_layout.addStretch(1)

        layout.addLayout(control_layout)
        layout.addLayout(status_layout)
        layout.addWidget(self.waveform_widget)
        return group

    def _audio_device_id(self, device):
        if device is None:
            return ""

        try:
            raw_id = device.id()
        except Exception:
            return ""

        if raw_id is None:
            return ""

        try:
            return bytes(raw_id).decode("utf-8", errors="ignore")
        except Exception:
            return str(raw_id)

    def _audio_device_name(self, device):
        if device is None:
            return "系统默认输出"

        try:
            name = device.description()
        except Exception:
            name = ""

        return str(name or "").strip() or "未知输出设备"

    def _available_audio_output_devices(self):
        try:
            return list(self.media_devices.audioOutputs())
        except Exception:
            try:
                return list(QMediaDevices.audioOutputs())
            except Exception as e:
                self._log(f"播放输出设备枚举失败: {e}")
                return []

    def _default_audio_output_device(self):
        try:
            return self.media_devices.defaultAudioOutput()
        except Exception:
            try:
                return QMediaDevices.defaultAudioOutput()
            except Exception:
                return None

    def _add_audio_output_combo_item(self, text, item_type, device=None, enabled=True, tooltip=None):
        data = {
            "type": item_type,
            "device": device,
            "enabled": bool(enabled),
        }
        self.audio_output_device_combo.addItem(text, data)
        index = self.audio_output_device_combo.count() - 1
        self.audio_output_device_combo.setItemData(
            index,
            tooltip or text.strip(),
            Qt.ItemDataRole.ToolTipRole,
        )

        item = self.audio_output_device_combo.model().item(index)

        if item is not None:
            item.setEnabled(bool(enabled))

        return index

    def refresh_audio_output_devices(self):
        if not hasattr(self, "audio_output_device_combo"):
            return

        previous_id = self.current_audio_output_device_id or self.saved_audio_output_device_id
        previous_name = self.current_audio_output_device_name or self.saved_audio_output_device_name
        devices = self._available_audio_output_devices()
        selected_index = 0
        self._refreshing_audio_output_devices = True
        self.audio_output_device_combo.blockSignals(True)
        self.audio_output_device_combo.clear()
        self._add_audio_output_combo_item(
            "无输出",
            "none",
            enabled=False,
            tooltip="暂不支持切换到无输出",
        )
        self._add_audio_output_combo_item(
            "系统输出",
            "header",
            enabled=False,
            tooltip="当前 Qt 可用的系统播放输出设备",
        )
        selected_index = self._add_audio_output_combo_item(
            "  系统默认输出",
            "qt_output",
            device=None,
            enabled=True,
            tooltip="系统默认输出",
        )

        for device in devices:
            device_id = self._audio_device_id(device)
            device_name = self._audio_device_name(device)
            item_index = self._add_audio_output_combo_item(
                f"  {device_name}",
                "qt_output",
                device=device,
                enabled=True,
                tooltip=device_name,
            )

            if previous_id and device_id == previous_id:
                selected_index = item_index
            elif not previous_id and previous_name and device_name == previous_name:
                selected_index = item_index

        self._add_audio_output_combo_item(
            "实验 / ASIO",
            "header",
            enabled=False,
            tooltip="ASIO 输出为后续预留，本版本尚未接入",
        )
        self._add_audio_output_combo_item(
            "  ASIO 输出后端尚未接入",
            "asio_placeholder",
            enabled=False,
            tooltip="ASIO 输出后端尚未接入，本项不可选择",
        )
        self.audio_output_device_combo.setCurrentIndex(selected_index)
        self._update_audio_output_device_combo_tooltip()
        self.audio_output_device_combo.setEnabled(bool(self.audio_output and devices))
        self.audio_output_device_combo.blockSignals(False)
        self._refreshing_audio_output_devices = False
        self._log("播放设备已刷新")

    def refresh_audio_output_devices_before_popup(self):
        self.refresh_audio_output_devices()

    def get_selected_audio_output_entry(self):
        if not hasattr(self, "audio_output_device_combo"):
            return None

        index = self.audio_output_device_combo.currentIndex()

        if index < 0:
            return None

        data = self.audio_output_device_combo.itemData(index)

        if isinstance(data, dict):
            return data

        return None

    def get_selected_audio_output_device(self):
        entry = self.get_selected_audio_output_entry()

        if not entry or entry.get("type") != "qt_output" or not entry.get("enabled"):
            return None

        return entry.get("device")

    def _update_audio_output_device_combo_tooltip(self):
        if not hasattr(self, "audio_output_device_combo"):
            return

        text = (self.audio_output_device_combo.currentText() or "系统默认输出").strip()
        self.audio_output_device_combo.setToolTip(text)

    def on_audio_output_device_changed(self, _index):
        if self._refreshing_audio_output_devices:
            return

        entry = self.get_selected_audio_output_entry()

        if not entry or entry.get("type") != "qt_output" or not entry.get("enabled"):
            return

        self._update_audio_output_device_combo_tooltip()
        self.apply_audio_output_device(entry.get("device"), persist=True)

    def apply_audio_output_device(self, device, persist=False):
        if not self.player:
            return False

        if self.audio_output is None:
            self.audio_output = QAudioOutput(self)
            self.player.setAudioOutput(self.audio_output)

        target_device = device or self._default_audio_output_device()
        selected_id = self._audio_device_id(device)
        selected_name = self._audio_device_name(device)

        if self.audio_output_device_applied:
            same_device = False

            if selected_id:
                same_device = selected_id == self.current_audio_output_device_id
            else:
                same_device = (
                    selected_name == self.current_audio_output_device_name
                    and not self.current_audio_output_device_id
                )

            if same_device:
                return True

        volume = self.audio_output.volume()
        position = self.player.position()
        was_playing = self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

        try:
            if target_device is not None:
                self.audio_output.setDevice(target_device)

            self.audio_output.setVolume(volume)

            if position > 0:
                self.player.setPosition(position)

            if was_playing:
                self.player.play()

            self.current_audio_output_device_id = selected_id
            self.current_audio_output_device_name = selected_name
            self.audio_output_device_applied = True

            if persist:
                self.config_data["audio_output_device_id"] = self.current_audio_output_device_id
                self.config_data["audio_output_device_name"] = self.current_audio_output_device_name
                self.config_data = self._save_config(self.config_data)

            self._log(f"播放输出设备已切换: {self.current_audio_output_device_name}")
            return True

        except Exception as e:
            self.error_text = f"播放输出设备切换失败：{e}"
            self.update_editor_status_panel()
            self._log(f"播放输出设备切换失败: {e}")
            return False

    def _build_pitch_shift_group(self):
        group = QGroupBox("升降调")
        layout = QGridLayout(group)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(6)

        self.pitch_current_value = self._make_value_label()
        self.pitch_current_value.setText("当前设置：原调")

        self.pitch_shift_slider = QSlider(Qt.Orientation.Horizontal)
        self.pitch_shift_slider.setMinimum(-12)
        self.pitch_shift_slider.setMaximum(12)
        self.pitch_shift_slider.setSingleStep(1)
        self.pitch_shift_slider.setPageStep(1)
        self.pitch_shift_slider.setTickInterval(1)
        self.pitch_shift_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.pitch_shift_slider.setValue(0)
        self.pitch_shift_slider.valueChanged.connect(self.on_pitch_shift_slider_changed)
        self.pitch_shift_slider.setEnabled(False)

        self.pitch_reset_button = QPushButton("重置为原调")
        self.pitch_reset_button.setMinimumWidth(96)
        self.pitch_reset_button.clicked.connect(self.reset_pitch_shift_to_zero)

        self.pitch_auto_load_checkbox = QCheckBox("导出完成后加载为当前音频")
        self.pitch_auto_load_checkbox.setChecked(True)
        self.pitch_auto_load_checkbox.setMinimumWidth(210)

        self.preview_pitch_button = QPushButton("试听当前设置")
        self.preview_pitch_button.setMinimumWidth(128)
        self.preview_pitch_button.clicked.connect(self.preview_pitch_shift_audio)
        self.preview_pitch_button.setEnabled(False)

        self.return_original_pitch_button = QPushButton("返回原音频预览")
        self.return_original_pitch_button.setMinimumWidth(140)
        self.return_original_pitch_button.clicked.connect(self.return_to_original_pitch_audio)
        self.return_original_pitch_button.setEnabled(False)

        self.export_pitch_button = QPushButton("加入导出修改")
        self.export_pitch_button.setMinimumWidth(148)
        self.export_pitch_button.clicked.connect(self.export_pitch_shift_audio)
        self.export_pitch_button.setEnabled(False)

        self.pitch_status_value = self._make_value_label()
        self.pitch_status_value.setText("当前设置：原调")
        self.pitch_preview_path_value = self._make_value_label()
        self.pitch_preview_path_value.setText("未生成")
        self.pitch_export_path_value = self._make_value_label()
        self.pitch_export_path_value.setText("-")

        scale_layout = QHBoxLayout()
        scale_layout.setContentsMargins(0, 0, 0, 0)
        scale_layout.addWidget(self._make_detail_label("-12 key"))
        scale_layout.addStretch(1)
        scale_layout.addWidget(self._make_detail_label("0"))
        scale_layout.addStretch(1)
        scale_layout.addWidget(self._make_detail_label("+12 key"))

        action_layout = QHBoxLayout()
        action_layout.setSpacing(6)
        action_layout.addWidget(self.pitch_reset_button)
        action_layout.addWidget(self.preview_pitch_button)
        action_layout.addWidget(self.return_original_pitch_button)
        action_layout.addWidget(self.export_pitch_button)
        action_layout.addStretch(1)

        layout.addWidget(self._make_detail_label("当前设置"), 0, 0)
        layout.addWidget(self.pitch_current_value, 0, 1, 1, 3)
        layout.addWidget(self._make_detail_label("范围"), 1, 0)
        layout.addLayout(scale_layout, 1, 1, 1, 3)
        layout.addWidget(self._make_detail_label("升降调"), 2, 0)
        layout.addWidget(self.pitch_shift_slider, 2, 1, 1, 3)
        layout.addLayout(action_layout, 3, 1, 1, 3)
        layout.addWidget(self.pitch_auto_load_checkbox, 4, 1, 1, 3)
        layout.addWidget(self._make_detail_label("状态"), 5, 0)
        layout.addWidget(self.pitch_status_value, 5, 1, 1, 3)
        layout.addWidget(self._make_detail_label("当前试听版本"), 6, 0)
        layout.addWidget(self.pitch_preview_path_value, 6, 1, 1, 3)
        layout.addWidget(self._make_detail_label("最近导出路径"), 7, 0)
        layout.addWidget(self.pitch_export_path_value, 7, 1, 1, 3)
        layout.setColumnStretch(1, 1)
        return group

    def _build_output_group(self):
        group = QGroupBox("输出目录设置")
        layout = QGridLayout(group)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(8)

        self.output_folder_value = self._make_value_label()

        choose_button = QPushButton("选择编辑输出目录")
        choose_button.clicked.connect(self.select_editor_output_folder)

        open_button = QPushButton("打开编辑输出目录")
        open_button.clicked.connect(self.open_editor_output_folder)

        button_layout = QHBoxLayout()
        button_layout.addWidget(choose_button)
        button_layout.addWidget(open_button)
        button_layout.addStretch(1)

        layout.addWidget(self._make_detail_label("当前音频编辑输出目录"), 0, 0)
        layout.addWidget(self.output_folder_value, 0, 1)
        layout.addLayout(button_layout, 1, 1)
        layout.setColumnStretch(1, 1)
        return group

    def _build_status_group(self):
        group = QGroupBox("基础状态摘要")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        status_grid = QGridLayout()
        status_grid.setHorizontalSpacing(12)
        status_grid.setVerticalSpacing(5)
        self.file_load_status_value = self._make_value_label()
        self.playback_status_value = self._make_value_label()
        self.lyrics_status_value = self._make_value_label()
        self.error_status_value = self._make_value_label()
        status_grid.addWidget(self._make_detail_label("文件加载状态"), 0, 0)
        status_grid.addWidget(self.file_load_status_value, 0, 1)
        status_grid.addWidget(self._make_detail_label("播放状态"), 0, 2)
        status_grid.addWidget(self.playback_status_value, 0, 3)
        status_grid.addWidget(self._make_detail_label("歌词状态"), 1, 0)
        status_grid.addWidget(self.lyrics_status_value, 1, 1)
        status_grid.addWidget(self._make_detail_label("错误信息"), 1, 2)
        status_grid.addWidget(self.error_status_value, 1, 3)
        status_grid.setColumnStretch(1, 1)
        status_grid.setColumnStretch(3, 1)

        self.stage_note = QLabel(
            "当前阶段支持导入、拖入、基础播放预览和歌词审核。\n"
            "波形预览为整首概览显示；调式识别将在后续版本规划。"
        )
        self.stage_note.setObjectName("MutedLabel")
        self.stage_note.setWordWrap(True)
        self.stage_note.setMaximumHeight(48)
        self.stage_note.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        layout.addLayout(status_grid)
        layout.addWidget(self.stage_note)
        return group

    def _build_lyrics_group(self):
        group = QGroupBox("歌词预览 / 歌词审核")
        group.setMinimumWidth(560)
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self.lyrics_title_hint = QLabel("右键或双击可编辑歌词。")
        self.lyrics_title_hint.setObjectName("MutedLabel")
        self.lyrics_title_hint.setWordWrap(True)

        source_layout = QGridLayout()
        self.lyrics_source_value = self._make_value_label()
        self.lyrics_source_value.setText("未加载歌词")
        self.lyrics_status_detail_value = self._make_value_label()
        self.lyrics_status_detail_value.setText("未加载歌词")
        self.lyrics_source_field_value = self._make_value_label()
        self.lyrics_source_field_value.setText("-")
        self.lyrics_sync_status_value = self._make_value_label()
        self.lyrics_sync_status_value.setText("未解析歌词时间轴")
        self.lyrics_edit_state_pill = StatusPill("只读", tone="neutral")
        source_layout.addWidget(self._make_detail_label("歌词来源"), 0, 0)
        source_layout.addWidget(self.lyrics_source_value, 0, 1)
        source_layout.addWidget(self._make_detail_label("歌词状态"), 1, 0)
        source_layout.addWidget(self.lyrics_status_detail_value, 1, 1)
        source_layout.addWidget(self._make_detail_label("来源字段"), 2, 0)
        source_layout.addWidget(self.lyrics_source_field_value, 2, 1)
        source_layout.addWidget(self._make_detail_label("同步状态"), 3, 0)
        source_layout.addWidget(self.lyrics_sync_status_value, 3, 1)
        source_layout.addWidget(self._make_detail_label("编辑状态"), 4, 0)
        source_layout.addWidget(self.lyrics_edit_state_pill, 4, 1)
        source_layout.setColumnStretch(1, 1)

        self.import_lrc_button = QPushButton("导入 .lrc")
        self.import_lrc_button.clicked.connect(self.select_lrc_file)
        self.sync_lrc_button = QPushButton("同步导入")
        self.sync_lrc_button.clicked.connect(self.sync_pending_lrc)
        self.skip_lrc_button = QPushButton("暂不导入")
        self.skip_lrc_button.clicked.connect(self.skip_pending_lrc)
        self.choose_other_lrc_button = QPushButton("选择其他 .lrc")
        self.choose_other_lrc_button.clicked.connect(self.select_lrc_file)
        self.manual_lyrics_button = QPushButton("手动编入歌词")
        self.manual_lyrics_button.clicked.connect(self.start_manual_lyrics_entry)
        self.edit_lyrics_button = QPushButton("编辑歌词")
        self.edit_lyrics_button.clicked.connect(self.toggle_lyrics_edit_mode)
        self.restore_lyrics_button = QPushButton("恢复原文")
        self.restore_lyrics_button.clicked.connect(self.restore_original_lyrics)
        self.jump_to_body_button = QPushButton("跳到歌词正文")
        self.jump_to_body_button.clicked.connect(self.jump_to_lyrics_body)
        self.save_lrc_as_button = QPushButton("另存为 .lrc")
        self.save_lrc_as_button.clicked.connect(self.save_lrc_as)
        self.save_lrc_original_button = QPushButton("保存到原 .lrc")
        self.save_lrc_original_button.clicked.connect(self.save_lrc_to_original)
        self.write_audio_lyrics_button = QPushButton("加入导出修改")
        self.write_audio_lyrics_button.clicked.connect(self.write_lyrics_to_current_audio)
        self.sync_lyrics_checkbox = QCheckBox("同步滚动歌词")
        self.sync_lyrics_checkbox.setChecked(True)
        self.sync_lyrics_checkbox.stateChanged.connect(self.toggle_lyrics_sync)

        for button in (
            self.import_lrc_button,
            self.sync_lrc_button,
            self.skip_lrc_button,
            self.choose_other_lrc_button,
            self.manual_lyrics_button,
            self.edit_lyrics_button,
            self.restore_lyrics_button,
            self.jump_to_body_button,
            self.save_lrc_as_button,
            self.save_lrc_original_button,
            self.write_audio_lyrics_button,
        ):
            button.setMinimumWidth(116)

        self.write_audio_lyrics_button.setMinimumWidth(128)
        self.sync_lyrics_checkbox.setMinimumWidth(132)

        import_buttons_layout = QHBoxLayout()
        import_buttons_layout.setSpacing(8)
        import_buttons_layout.addWidget(self.import_lrc_button)
        import_buttons_layout.addWidget(self.write_audio_lyrics_button)
        import_buttons_layout.addStretch(1)

        for hidden_widget in (
            self.sync_lrc_button,
            self.skip_lrc_button,
            self.choose_other_lrc_button,
            self.manual_lyrics_button,
            self.edit_lyrics_button,
            self.restore_lyrics_button,
            self.jump_to_body_button,
            self.save_lrc_as_button,
            self.save_lrc_original_button,
            self.sync_lyrics_checkbox,
        ):
            hidden_widget.setParent(group)
            hidden_widget.setVisible(False)

        self.netease_metadata_hint = QLabel(
            "检测到歌词开头可能包含网易歌词元数据。\n"
            "这些内容通常用于记录作词、作曲、翻译等信息，不一定适合直接作为歌词展示。\n"
            "是否需要保留请自行判断，可点击“编辑歌词”后手动删除。"
        )
        self.netease_metadata_hint.setObjectName("MutedLabel")
        self.netease_metadata_hint.setWordWrap(True)
        self.netease_metadata_hint.setVisible(False)

        self.lyrics_preview = QTextEdit()
        self.lyrics_preview.setReadOnly(True)
        self.lyrics_preview.setMinimumHeight(260)
        self.lyrics_preview.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.lyrics_preview.installEventFilter(self)
        self.lyrics_preview.viewport().installEventFilter(self)

        self.lyrics_context_hint = QLabel(
            "右键歌词区域可恢复、另存或加入统一导出；双击正文可直接编辑。"
        )
        self.lyrics_context_hint.setObjectName("MutedLabel")
        self.lyrics_context_hint.setWordWrap(True)

        self.setup_lyrics_context_menu()

        layout.addWidget(self.lyrics_title_hint)
        layout.addLayout(source_layout)
        layout.addLayout(import_buttons_layout)
        layout.addWidget(self.netease_metadata_hint)
        layout.addWidget(self.lyrics_preview, 1)
        layout.addWidget(self.lyrics_context_hint)
        self._set_pending_lrc_controls_visible(False)
        return group

    def setup_cover_context_menu(self):
        self.cover_context_menu = QMenu(self)
        self.import_cover_action = self.cover_context_menu.addAction("导入封面...")
        self.remove_cover_action = self.cover_context_menu.addAction("移除封面")
        self.restore_cover_action = self.cover_context_menu.addAction("恢复原封面")
        self.cover_context_menu.addSeparator()
        self.write_cover_action = self.cover_context_menu.addAction("加入封面到统一导出")

        self.import_cover_action.triggered.connect(self.select_cover_image)
        self.remove_cover_action.triggered.connect(self.remove_current_cover)
        self.restore_cover_action.triggered.connect(self.restore_original_cover)
        self.write_cover_action.triggered.connect(self.write_current_audio_cover)

        self.cover_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.cover_label.customContextMenuRequested.connect(self.show_cover_context_menu)
        self.update_cover_menu_actions()

    def _unavailable_tip(self, reason):
        return f"当前不可用：{reason}" if reason else ""

    def set_button_available(self, button, enabled, reason="", enabled_tip=""):
        button.setEnabled(enabled)
        tip = enabled_tip if enabled else self._unavailable_tip(reason)
        button.setToolTip(tip)
        button.setStatusTip(tip)

    def set_action_available(self, action, enabled, reason="", enabled_tip=""):
        base_text = action.property("base_text")
        if not base_text:
            base_text = action.text()
            action.setProperty("base_text", base_text)

        action.setEnabled(enabled)
        action.setText(base_text)
        tip = enabled_tip if enabled else self._unavailable_tip(reason)
        action.setToolTip(tip)
        action.setStatusTip(tip)

    def show_cover_context_menu(self, position):
        self.update_cover_menu_actions()
        self.cover_context_menu.exec(self.cover_label.mapToGlobal(position))

    def update_cover_menu_actions(self):
        if not hasattr(self, "import_cover_action"):
            return

        has_audio = bool(self.current_audio_path)
        has_current_cover = bool(self.current_cover_data and not self.cover_marked_for_removal)
        has_original_cover = bool(self.original_cover_data)

        self.set_action_available(
            self.import_cover_action,
            has_audio,
            "请先导入音频",
            "选择 JPG/PNG 作为当前封面预览，不会自动写入音频",
        )
        self.set_action_available(
            self.remove_cover_action,
            has_audio and has_current_cover,
            "请先导入音频" if not has_audio else "没有可移除的封面",
            "标记移除当前封面，需写入后才会修改音频文件",
        )
        self.set_action_available(
            self.restore_cover_action,
            has_audio and has_original_cover,
            "请先导入音频" if not has_audio else "没有可恢复的原封面",
            "恢复到音频导入时读取到的原封面预览",
        )
        self.set_action_available(
            self.write_cover_action,
            has_audio and self.cover_dirty,
            "请先导入音频" if not has_audio else "没有需要导出的封面修改",
            "将当前封面修改加入统一导出",
        )

    def setup_lyrics_context_menu(self):
        self.lyrics_context_menu = QMenu(self)

        self.lyrics_preview.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.lyrics_preview.customContextMenuRequested.connect(self.show_lyrics_context_menu)
        self.update_lyrics_menu_actions()

    def show_lyrics_context_menu(self, position):
        self.rebuild_lyrics_context_menu()
        self.lyrics_context_menu.exec(self.lyrics_preview.mapToGlobal(position))

    def update_lyrics_menu_actions(self):
        if not hasattr(self, "lyrics_context_menu"):
            return

        self.rebuild_lyrics_context_menu()
        state = self.get_lyrics_menu_state()
        write_reason = "请先导入音频" if not state["has_audio"] else "没有可导出的歌词"
        self.set_button_available(
            self.write_audio_lyrics_button,
            state["has_audio"] and state["has_exportable_lyrics"],
            write_reason,
            "将当前歌词加入统一导出修改",
        )

    def rebuild_lyrics_context_menu(self):
        state = self.get_lyrics_menu_state()
        self.lyrics_context_menu.clear()
        for attr_name in (
            "sync_lyrics_action",
            "sync_pending_lrc_action",
            "skip_pending_lrc_action",
            "choose_other_lrc_action",
            "manual_lyrics_action",
            "import_lrc_action",
            "edit_lyrics_action",
            "restore_lyrics_action",
            "focus_lyrics_body_action",
            "save_lrc_as_action",
            "save_lrc_original_action",
            "write_audio_lyrics_action",
        ):
            setattr(self, attr_name, None)

        action_specs = {
            "sync": (
                "sync_lyrics_action",
                "同步歌词",
                self.sync_available_lrc,
                state["has_sync_source"],
                "没有可同步的外部 .lrc",
                "从已发现或已绑定的 .lrc 重新同步歌词",
            ),
            "manual": (
                "manual_lyrics_action",
                "手动编辑歌词",
                self.start_manual_lyrics_entry,
                True,
                "",
                "从空白歌词正文开始手动编辑歌词",
            ),
            "import": (
                "import_lrc_action",
                "导入 .lrc...",
                self.select_lrc_file,
                True,
                "",
                "导入外置 .lrc 歌词，仅加载到音频编辑区，不会自动写入音频",
            ),
            "edit": (
                "edit_lyrics_action",
                "编辑歌词",
                self.enter_lyrics_edit_mode,
                state["has_exportable_lyrics"],
                "没有可编辑的歌词内容",
                "进入歌词正文编辑模式",
            ),
            "restore": (
                "restore_lyrics_action",
                "恢复原文",
                self.restore_original_lyrics,
                state["can_restore"],
                "没有可恢复的原文",
                "从原 .lrc 或音频内嵌歌词恢复正文",
            ),
            "focus": (
                "focus_lyrics_body_action",
                "跳到歌词正文",
                self.jump_to_lyrics_body,
                True,
                "",
                "聚焦歌词正文区域，不会进入编辑模式",
            ),
            "save_as": (
                "save_lrc_as_action",
                "另存为 .lrc...",
                self.save_lrc_as,
                state["has_exportable_lyrics"],
                "没有可导出的歌词内容",
                "将当前歌词另存为新的 .lrc 文件",
            ),
            "save_original": (
                "save_lrc_original_action",
                "保存到原 .lrc",
                self.save_lrc_to_original,
                state["has_exportable_lyrics"] and state["has_original_lrc"],
                state["original_lrc_reason"],
                "覆盖保存到当前绑定的原 .lrc 文件",
            ),
            "write": (
                "write_audio_lyrics_action",
                "加入歌词到统一导出",
                self.write_lyrics_to_current_audio,
                state["has_audio"] and state["has_exportable_lyrics"],
                state["write_reason"],
                "将当前歌词加入统一导出修改",
            ),
        }

        for index, group in enumerate(self.get_lyrics_menu_groups(state)):
            if index > 0:
                self.lyrics_context_menu.addSeparator()

            for key in group:
                self.add_lyrics_menu_action(action_specs[key])

        self.sync_pending_lrc_action = self.sync_lyrics_action
        self.skip_pending_lrc_action = None
        self.choose_other_lrc_action = None

    def add_lyrics_menu_action(self, spec):
        attr_name, text, handler, enabled, reason, enabled_tip = spec
        action = self.lyrics_context_menu.addAction(text)
        action.setProperty("base_text", text)
        action.triggered.connect(handler)
        self.set_action_available(action, enabled, reason, enabled_tip)
        setattr(self, attr_name, action)
        return action

    def get_lyrics_menu_groups(self, state):
        if state["has_pending_lrc"] and not state["has_exportable_lyrics"]:
            return (
                ("sync", "manual"),
                ("import", "focus"),
                ("save_as", "save_original", "write"),
            )

        if state["has_exportable_lyrics"]:
            return (
                ("edit", "restore"),
                ("focus",),
                ("sync", "import", "manual"),
                ("save_as", "save_original", "write"),
            )

        return (
            ("import", "manual", "edit"),
            ("focus",),
            ("save_as", "save_original", "write"),
        )

    def get_lyrics_menu_state(self):
        lyrics_text = self.lyrics_preview.toPlainText() if hasattr(self, "lyrics_preview") else ""
        has_audio = bool(self.current_audio_path)
        has_exportable_lyrics = self._has_exportable_lyrics(lyrics_text)
        has_pending_lrc = bool(self.pending_lrc_path)
        can_restore = bool(
            (self.current_lyrics_source_type == "embedded" and self.current_audio_path)
            or self.current_lrc_path
        )
        has_original_lrc = bool(self.current_lyrics_source_path)
        has_sync_source = bool(has_pending_lrc or self._available_lrc_sync_path())
        original_lrc_reason = (
            "没有可保存的歌词内容"
            if not has_exportable_lyrics
            else "未绑定原始 .lrc 文件"
        )
        write_reason = "请先导入音频" if not has_audio else "没有可导出的歌词"

        return {
            "has_audio": has_audio,
            "has_exportable_lyrics": has_exportable_lyrics,
            "has_pending_lrc": has_pending_lrc,
            "has_sync_source": has_sync_source,
            "can_restore": can_restore,
            "has_original_lrc": has_original_lrc,
            "original_lrc_reason": original_lrc_reason,
            "write_reason": write_reason,
        }

    def setup_player_hover_tips(self):
        for slider in (self.position_slider, self.volume_slider):
            slider.setMouseTracking(True)
            slider.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
            slider.installEventFilter(self)

        self.update_player_action_states()

    def _public_play_source_type(self, source_type):
        return {
            "none": "none",
            "current_file": "original",
            "original": "original",
            "pitch_preview": "preview",
            "preview": "preview",
            "exported_result": "export",
            "export": "export",
        }.get(source_type or "none", source_type or "none")

    def _public_player_status_text(self):
        return {
            "stopped": "未播放",
            "loading": "加载中",
            "playing": "播放中",
            "paused": "已暂停",
            "error": "播放错误",
        }.get(self.player_status, self.playback_status or "未播放")

    def _sync_public_player_state(self):
        self.current_play_source_path = self.playback_source_path
        self.current_play_source_type = self._public_play_source_type(self.playback_source_type)
        self.position_ms = max(0, int(self.player.position() or self.position_slider.value() or 0))
        self.duration_ms = max(0, int(self.duration_ms or self.player.duration() or 0))
        self.volume = max(0, min(100, int(round(self.audio_output.volume() * 100))))

    def update_waveform_state(self, file_path=None, status=None):
        if status is None:
            status = "待生成" if (file_path or self.current_audio_path) else "未加载"

        self.waveform_status = status

        if hasattr(self, "waveform_status_label"):
            self.waveform_status_label.setText(f"波形预览：{status}")
            self.waveform_status_label.setToolTip(
                "波形为 FFmpeg 生成的整首概览峰值，不会修改音频文件。"
            )

        if hasattr(self, "waveform_widget"):
            self.waveform_widget.set_status_text(f"波形预览：{status}")

    def _waveform_cache_dir(self):
        cache_dir = os.path.join(self.editor_temp_folder, "WaveformCache")
        os.makedirs(cache_dir, exist_ok=True)
        return cache_dir

    def stop_waveform_generation(self):
        if self.waveform_thread and self.waveform_thread.isRunning():
            self.waveform_thread.request_stop()
            self._stale_waveform_threads.append(self.waveform_thread)

        self.waveform_thread = None

    def start_waveform_generation(self, audio_path=None, source_type=None):
        self.stop_waveform_generation()

        audio_path = os.path.normpath(os.path.abspath(audio_path)) if audio_path else None
        self.current_waveform_source_path = audio_path

        if not audio_path:
            self.update_waveform_state(None, "未加载")
            if hasattr(self, "waveform_widget"):
                self.waveform_widget.clear_waveform()
            return

        if not os.path.isfile(audio_path):
            self.update_waveform_state(audio_path, "生成失败，不影响播放")
            if hasattr(self, "waveform_widget"):
                self.waveform_widget.clear_waveform()
                self.waveform_widget.set_status_text("波形预览：生成失败")
            self._log(f"波形生成失败，文件不存在: {audio_path}")
            return

        self.update_waveform_state(audio_path, "生成中...")
        if hasattr(self, "waveform_widget"):
            self.waveform_widget.clear_waveform()
            self.waveform_widget.set_status_text("波形预览：生成中...")

        self.waveform_thread = WaveformGenerateThread(
            audio_path,
            self._waveform_cache_dir(),
            FFMPEG_PATH,
            parent=self,
        )
        self.waveform_thread.finished_signal.connect(self._on_waveform_generated)
        self.waveform_thread.finished.connect(self._cleanup_waveform_threads)
        self.waveform_thread.start()
        self._log(f"波形生成开始: {audio_path}")

    def _cleanup_waveform_threads(self):
        sender = self.sender()
        if sender is self.waveform_thread:
            self.waveform_thread = None

        self._stale_waveform_threads = [
            thread for thread in self._stale_waveform_threads if thread is not sender
        ]

        if sender is not None:
            sender.deleteLater()

    def _on_waveform_generated(self, result):
        source_path = result.get("source_path")

        if (
            not source_path
            or not self.current_waveform_source_path
            or os.path.normcase(os.path.abspath(source_path))
            != os.path.normcase(os.path.abspath(self.current_waveform_source_path))
        ):
            self._log(f"已忽略过期波形结果: {source_path}")
            return

        if result.get("stopped"):
            return

        if not result.get("success"):
            message = result.get("error") or "波形生成失败。"
            self.update_waveform_state(source_path, "生成失败，不影响播放")
            if hasattr(self, "waveform_widget"):
                self.waveform_widget.clear_waveform()
                self.waveform_widget.set_status_text("波形预览：生成失败，不影响播放")
            self._log(f"波形生成失败: {source_path} - {message}")
            return

        peaks = result.get("peaks") or []
        if hasattr(self, "waveform_widget"):
            self.waveform_widget.set_peaks(peaks)
            self._update_waveform_position()

        if result.get("from_cache"):
            self.update_waveform_state(source_path, "已从缓存加载")
            self._log(f"波形已从缓存加载: {source_path}")
        else:
            self.update_waveform_state(source_path, "已生成")
            self._log(f"波形生成完成: {source_path}")

    def _update_waveform_position(self):
        if not hasattr(self, "waveform_widget"):
            return

        duration = max(0, int(self.duration_ms or self.player.duration() or 0))
        position = max(0, int(self.player.position() or self.position_slider.value() or 0))
        ratio = position / duration if duration > 0 else 0.0
        self.waveform_widget.set_position_ratio(ratio)

    def seek_waveform_position(self, ratio):
        duration = max(0, int(self.duration_ms or self.player.duration() or 0))
        if duration <= 0:
            return False

        position = max(0, min(duration, int(duration * ratio)))
        self.player.setPosition(position)
        self.position_slider.setValue(position)
        self._update_time_label(position)
        self._update_waveform_position()
        self._log(f"波形点击跳转播放位置: {format_duration(position)}")
        return True

    def update_player_action_states(self):
        if not hasattr(self, "position_slider"):
            return

        has_audio = bool(self.current_audio_path or self.playback_source_path)
        has_duration = self.duration_ms > 0
        player_reason = "请先导入音频"

        if hasattr(self, "play_pause_button"):
            self.set_button_available(
                self.play_pause_button,
                has_audio,
                player_reason,
                "播放或暂停当前预览音频",
            )

        if hasattr(self, "stop_button"):
            self.set_button_available(
                self.stop_button,
                has_audio,
                player_reason,
                "停止播放并回到起点",
            )

        preview_unavailable = not (has_audio and has_duration)
        if self.position_slider.property("previewUnavailable") != preview_unavailable:
            self.position_slider.setProperty("previewUnavailable", preview_unavailable)
            self.position_slider.style().unpolish(self.position_slider)
            self.position_slider.style().polish(self.position_slider)

        self.position_slider.setEnabled(True)
        if preview_unavailable:
            reason = "请先导入可预览音频" if not has_audio else "音频时长尚未读取"
            self.position_slider.setToolTip(f"进度条暂不可拖动：{reason}；右键菜单会在加载音频后可复制时间戳")
            self.position_slider.setStatusTip(f"进度条暂不可拖动：{reason}")
        else:
            self.position_slider.setToolTip("")
            self.position_slider.setStatusTip("悬停可预览对应播放时间，右键可复制时间戳")

        self.volume_slider.setToolTip("")
        self.volume_slider.setStatusTip("悬停可预览对应音量，不会改变当前音量")

    def get_slider_hover_ratio(self, slider, event):
        width = max(1, slider.width() - 1)

        if hasattr(event, "position"):
            position = event.position()
            x = position.x()
        else:
            position = event.pos()
            x = position.x()

        return max(0.0, min(1.0, float(x) / float(width)))

    def _tooltip_global_pos(self, event):
        if hasattr(event, "globalPosition"):
            return event.globalPosition().toPoint()

        return event.globalPos()

    def format_time_ms(self, milliseconds):
        return format_duration(milliseconds)

    def format_time_for_copy(self, milliseconds):
        total_centiseconds = max(0, int(round(int(milliseconds) / 10.0)))
        centiseconds = total_centiseconds % 100
        total_seconds = total_centiseconds // 100
        seconds = total_seconds % 60
        total_minutes = total_seconds // 60
        minutes = total_minutes % 60
        hours = total_minutes // 60

        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"

        return f"{total_minutes:02d}:{seconds:02d}.{centiseconds:02d}"

    def format_lrc_timestamp(self, milliseconds):
        total_centiseconds = max(0, int(round(int(milliseconds) / 10.0)))
        centiseconds = total_centiseconds % 100
        total_seconds = total_centiseconds // 100
        seconds = total_seconds % 60
        total_minutes = total_seconds // 60
        return f"[{total_minutes:02d}:{seconds:02d}.{centiseconds:02d}]"

    def get_current_playback_duration_ms(self):
        return max(0, int(self.duration_ms or self.player.duration() or 0))

    def can_copy_progress_time(self):
        return bool(self.current_audio_path or self.playback_source_path) and (
            self.get_current_playback_duration_ms() > 0
        )

    def get_progress_time_from_slider_position(self, slider, position):
        duration = self.get_current_playback_duration_ms()
        if duration <= 0 or position is None:
            return max(0, int(self.player.position() or self.position_slider.value() or 0))

        width = max(1, slider.width() - 1)
        ratio = max(0.0, min(1.0, float(position.x()) / float(width)))
        return max(0, min(duration, int(round(duration * ratio))))

    def build_progress_slider_context_menu(self, position):
        menu = QMenu(self)
        can_copy = self.can_copy_progress_time()

        copy_time_action = menu.addAction("复制当前时间")
        self.set_action_available(
            copy_time_action,
            can_copy,
            "请先导入可预览音频",
            "复制鼠标所在位置对应的普通时间",
        )
        copy_time_action.triggered.connect(
            lambda _checked=False: self.copy_progress_time_at_position(position, as_lrc=False)
        )

        copy_lrc_action = menu.addAction("复制 LRC 时间戳")
        self.set_action_available(
            copy_lrc_action,
            can_copy,
            "请先导入可预览音频",
            "复制鼠标所在位置对应的 LRC 时间戳",
        )
        copy_lrc_action.triggered.connect(
            lambda _checked=False: self.copy_progress_time_at_position(position, as_lrc=True)
        )

        copy_playback_action = menu.addAction("复制当前播放时间")
        self.set_action_available(
            copy_playback_action,
            can_copy,
            "请先导入可预览音频",
            "复制播放器当前播放位置",
        )
        copy_playback_action.triggered.connect(
            lambda _checked=False: self.copy_progress_time_at_position(
                position,
                as_lrc=True,
                use_current_position=True,
            )
        )

        self.copy_progress_time_action = copy_time_action
        self.copy_lrc_timestamp_action = copy_lrc_action
        self.copy_current_playback_time_action = copy_playback_action
        return menu

    def show_progress_slider_context_menu(self, position):
        menu = self.build_progress_slider_context_menu(position)
        menu.exec(self.position_slider.mapToGlobal(position))

    def copy_progress_time_at_position(self, position, as_lrc=False, use_current_position=False):
        if not self.can_copy_progress_time():
            return ""

        if use_current_position:
            milliseconds = max(0, int(self.player.position() or self.position_slider.value() or 0))
        else:
            milliseconds = self.get_progress_time_from_slider_position(
                self.position_slider,
                position,
            )

        copied_text = (
            self.format_lrc_timestamp(milliseconds)
            if as_lrc
            else self.format_time_for_copy(milliseconds)
        )
        QApplication.clipboard().setText(copied_text)
        self._log(f"已复制时间戳: {copied_text}")
        return copied_text

    def show_progress_hover_tip(self, event):
        duration = max(0, int(self.duration_ms or self.player.duration() or 0))

        if not self.current_audio_path and not self.playback_source_path:
            tip = "未加载音频"
        elif duration <= 0:
            tip = "00:00 / 00:00"
        else:
            ratio = self.get_slider_hover_ratio(self.position_slider, event)
            hover_position = int(duration * ratio)
            tip = f"{self.format_time_ms(hover_position)} / {self.format_time_ms(duration)}"

        QToolTip.showText(self._tooltip_global_pos(event), tip, self.position_slider)
        return tip

    def percent_to_db(self, volume_percent):
        if volume_percent <= 0:
            return "-∞ dB"

        return f"{20 * math.log10(volume_percent / 100):.1f} dB"

    def format_volume_tip(self, volume_percent):
        volume_percent = max(0, min(100, int(round(volume_percent))))
        return f"音量：{volume_percent}%（{self.percent_to_db(volume_percent)}）"

    def show_volume_hover_tip(self, event):
        ratio = self.get_slider_hover_ratio(self.volume_slider, event)
        value_range = self.volume_slider.maximum() - self.volume_slider.minimum()
        hover_volume = self.volume_slider.minimum() + int(round(value_range * ratio))
        tip = self.format_volume_tip(hover_volume)
        QToolTip.showText(self._tooltip_global_pos(event), tip, self.volume_slider)
        return tip

    def eventFilter(self, watched, event):
        if watched is getattr(self, "position_slider", None):
            if event.type() in (
                QEvent.Type.MouseMove,
                QEvent.Type.HoverMove,
                QEvent.Type.ToolTip,
            ):
                self.show_progress_hover_tip(event)
                if event.type() == QEvent.Type.ToolTip:
                    return True
                return False

            if event.type() == QEvent.Type.Leave:
                QToolTip.hideText()
                return False

        if watched is getattr(self, "volume_slider", None):
            if event.type() in (
                QEvent.Type.MouseMove,
                QEvent.Type.HoverMove,
                QEvent.Type.ToolTip,
            ):
                self.show_volume_hover_tip(event)
                if event.type() == QEvent.Type.ToolTip:
                    return True
                return False

            if event.type() == QEvent.Type.Leave:
                QToolTip.hideText()
                return False

        browser_tree = getattr(self, "browser_tree", None)
        if watched is browser_tree or (browser_tree is not None and watched is browser_tree.viewport()):
            if (
                event.type() == QEvent.Type.MouseButtonPress
                and self._is_left_mouse_button_event(event)
                and self.handle_browser_folder_mouse_press(event)
            ):
                return True

            if event.type() == QEvent.Type.MouseButtonDblClick and self._is_left_mouse_button_event(event):
                item = self.browser_item_from_mouse_event(event)

                if item is not None and item.data(0, Qt.ItemDataRole.UserRole + 1) == "folder":
                    return True

            if (
                event.type() == QEvent.Type.KeyPress
                and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            ):
                selected_item = self.selected_browser_item()

                if selected_item is not None and selected_item.data(0, Qt.ItemDataRole.UserRole + 1) == "folder":
                    self.update_browser_folder_preview(selected_item)
                    return True

                if selected_item is not None and selected_item.data(0, Qt.ItemDataRole.UserRole + 1) == "audio":
                    self.load_selected_browser_file()
                    return True

                return False

        if self._is_lyrics_preview_event_target(watched):
            if (
                event.type() == QEvent.Type.MouseButtonDblClick
                and self._is_left_mouse_button_event(event)
            ):
                self.enter_lyrics_edit_mode()
                return True

        return super().eventFilter(watched, event)

    def browser_item_from_mouse_event(self, event):
        browser_tree = getattr(self, "browser_tree", None)

        if browser_tree is None:
            return None

        return browser_tree.itemAt(event.position().toPoint() if hasattr(event, "position") else event.pos())

    def handle_browser_folder_mouse_press(self, event):
        item = self.browser_item_from_mouse_event(event)

        if item is None or item.data(0, Qt.ItemDataRole.UserRole + 1) != "folder":
            return False

        position = event.position().toPoint() if hasattr(event, "position") else event.pos()

        if not self.is_browser_folder_arrow_click(item, position):
            return False

        return self.toggle_browser_folder_item(item)

    def is_browser_folder_arrow_click(self, item, position):
        if item is None:
            return False

        arrow_width = 22
        indent = max(1, self.browser_tree.indentation())
        control_left = self.browser_item_depth(item) * indent
        control_right = control_left + arrow_width
        return control_left <= position.x() <= control_right

    def browser_item_depth(self, item):
        depth = 0
        parent = item.parent() if item is not None else None

        while parent is not None:
            depth += 1
            parent = parent.parent()

        return depth

    def toggle_browser_folder_item(self, item):
        self.browser_tree.setCurrentItem(item)
        item.setExpanded(not item.isExpanded())
        self.update_browser_folder_arrow(item)
        self.update_browser_folder_preview(item)
        return True

    def on_browser_folder_expanded(self, item):
        self.update_browser_folder_arrow(item)

    def on_browser_folder_collapsed(self, item):
        self.update_browser_folder_arrow(item)

    def update_browser_folder_arrow(self, item):
        if item is None or item.data(0, Qt.ItemDataRole.UserRole + 1) != "folder":
            return

        display_name = item.data(0, Qt.ItemDataRole.UserRole + 3)
        folder_path = item.data(0, Qt.ItemDataRole.UserRole) or ""

        if not display_name:
            display_name = os.path.basename(folder_path) or folder_path or "文件夹"

        item.setText(0, display_name)

    def _is_lyrics_preview_event_target(self, watched):
        preview = getattr(self, "lyrics_preview", None)
        if preview is None:
            return False

        return watched is preview or watched is preview.viewport()

    def _is_left_mouse_button_event(self, event):
        button = getattr(event, "button", None)
        if not callable(button):
            return False

        return button() == Qt.MouseButton.LeftButton

    def enter_lyrics_edit_mode(self):
        if self.is_lyrics_editing:
            self.focus_lyrics_body()
            return True

        if not self._has_exportable_lyrics(self.lyrics_preview.toPlainText()):
            return self.start_manual_lyrics_entry()

        self.is_lyrics_editing = True
        self.lyrics_preview.setReadOnly(False)
        self.edit_lyrics_button.setText("完成编辑")
        self._clear_lyrics_highlight()
        self._set_lyrics_sync_status("编辑模式下已暂停同步滚动")
        self.focus_lyrics_body()
        self.update_editor_status_panel()
        self.update_lyrics_menu_actions()
        self._log("已进入歌词编辑模式")
        return True

    def focus_lyrics_body(self):
        self.lyrics_preview.setFocus(Qt.FocusReason.MouseFocusReason)
        self.lyrics_preview.viewport().setFocus(Qt.FocusReason.MouseFocusReason)
        self.lyrics_preview.ensureCursorVisible()
        return True

    def select_audio_file(self):
        file_path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "导入音频",
            "",
            get_editor_audio_filter(),
        )

        if file_path:
            self.load_audio_file(file_path, source="dialog")

    def _restore_editor_browser_folder(self):
        if not hasattr(self, "browser_folder_value"):
            return

        configured_folders = self.config_data.get("editor_project_folders")
        configured_legacy_folder = self.config_data.get("editor_browser_folder")
        restored_folders = self._normalize_project_folders(
            configured_folders,
            configured_legacy_folder,
        )
        restored_legacy_folder = restored_folders[0] if restored_folders else ""

        self.editor_project_folders = restored_folders
        self.editor_browser_folder = restored_legacy_folder

        if not self._project_folder_lists_equal(
            configured_folders,
            restored_folders,
        ) or not self._folders_semantically_equal(
            configured_legacy_folder,
            restored_legacy_folder,
        ):
            self._save_project_folders()

        self._refresh_browser_folder_label()

        if self.editor_project_folders:
            self.start_editor_browser_scan()

    def _normalize_project_folders(self, folders, legacy_folder=None):
        normalized = []
        seen = set()
        candidates = list(folders or [])

        if legacy_folder:
            candidates.append(legacy_folder)

        for folder in candidates:
            if not isinstance(folder, str) or not folder.strip():
                continue

            normalized_folder = os.path.normpath(os.path.abspath(folder))
            key = os.path.normcase(normalized_folder)

            if key in seen:
                continue

            seen.add(key)
            normalized.append(normalized_folder)

        return normalized

    @staticmethod
    def _normalize_folder_for_compare(folder):
        if not isinstance(folder, str) or not folder.strip():
            return ""

        return os.path.normcase(
            os.path.normpath(os.path.abspath(folder.strip()))
        )

    def _project_folder_lists_equal(self, left, right):
        if not isinstance(left, list) or not isinstance(right, list):
            return False

        return [
            self._normalize_folder_for_compare(folder)
            for folder in left
        ] == [
            self._normalize_folder_for_compare(folder)
            for folder in right
        ]

    def _folders_semantically_equal(self, left, right):
        return (
            self._normalize_folder_for_compare(left)
            == self._normalize_folder_for_compare(right)
        )

    def _folder_contains_path(self, parent_folder, child_path):
        parent_key = os.path.normcase(os.path.normpath(parent_folder or ""))
        child_key = os.path.normcase(os.path.normpath(child_path or ""))

        if not parent_key or not child_key:
            return False

        if parent_key == child_key:
            return True

        try:
            return os.path.commonpath([parent_key, child_key]) == parent_key
        except ValueError:
            return False

    def _save_project_folders(self):
        self.config_data["editor_project_folders"] = list(self.editor_project_folders)
        self.config_data["editor_browser_folder"] = self.editor_project_folders[0] if self.editor_project_folders else ""
        self.editor_browser_folder = self.config_data["editor_browser_folder"]
        self.config_data = self._save_config(self.config_data)

    def _save_config(self, config_data):
        if self._config_saver is not None:
            return self._config_saver(config_data)

        return save_config(config_data)

    def select_editor_browser_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "添加项目文件夹",
            self.editor_project_folders[0] if self.editor_project_folders else os.path.expanduser("~"),
        )

        if not folder:
            return False

        return self.add_editor_project_folder(folder, scan=True)

    def set_editor_browser_folder(self, folder_path, scan=True):
        return self.add_editor_project_folder(folder_path, scan=scan)

    def add_editor_project_folder(self, folder_path, scan=True):
        normalized_folder = os.path.normpath(os.path.abspath(folder_path))

        if not os.path.isdir(normalized_folder):
            self._set_browser_status("目录不存在，请重新选择", log=True)
            self._log(f"音频项目文件夹不存在: {normalized_folder}")
            return False

        existing_folders = list(self.editor_project_folders)

        for existing_folder in existing_folders:
            if os.path.normcase(existing_folder) == os.path.normcase(normalized_folder):
                self._set_browser_status("项目文件夹已存在", log=True)
                self._log(f"项目文件夹已存在: {normalized_folder}")
                return True

            if self._folder_contains_path(existing_folder, normalized_folder):
                self._set_browser_status("该文件夹已包含在现有项目文件夹中", log=True)
                self._log(f"该文件夹已包含在现有项目文件夹中: {normalized_folder}")

                if scan:
                    self.start_editor_browser_scan()

                return True

        child_folders = [
            existing_folder
            for existing_folder in existing_folders
            if self._folder_contains_path(normalized_folder, existing_folder)
        ]

        if child_folders:
            child_keys = {os.path.normcase(folder) for folder in child_folders}
            self.editor_project_folders = [
                folder
                for folder in existing_folders
                if os.path.normcase(folder) not in child_keys
            ]
            self.editor_project_folders.append(normalized_folder)
            self._set_browser_status("已合并子项目文件夹到上级目录", log=True)
            self._log(f"已合并子项目文件夹到上级目录: {normalized_folder}")
        else:
            self.editor_project_folders.append(normalized_folder)
            self._set_browser_status("已添加项目文件夹", log=True)
            self._log(f"已添加音频项目文件夹: {normalized_folder}")

        self.editor_project_folders = self._normalize_project_folders(self.editor_project_folders)
        self._save_project_folders()
        self._refresh_browser_folder_label()

        if scan:
            self.start_editor_browser_scan()

        return True

    def add_editor_project_folders(self, folder_paths, scan=True):
        changed = False

        for folder_path in folder_paths:
            changed = self.add_editor_project_folder(folder_path, scan=False) or changed

        if scan and changed:
            self.start_editor_browser_scan()

        return changed

    def add_dropped_project_folders(self, paths):
        folders = []

        for raw_path in paths:
            path = os.path.normpath(os.path.abspath(raw_path))

            if os.path.isdir(path):
                folders.append(path)
            else:
                self._log(f"音频目录侧栏仅支持拖入文件夹，已忽略: {path}")

        if not folders:
            self._set_browser_status("请拖入文件夹", log=True)
            return False

        return self.add_editor_project_folders(folders, scan=True)

    def refresh_editor_browser_folder(self):
        if not self.editor_project_folders:
            QMessageBox.information(self, "未添加项目文件夹", "当前未添加项目文件夹。")
            self._set_browser_status("未添加项目文件夹", log=True)
            return False

        self.start_editor_browser_scan()
        return True

    def open_editor_browser_folder(self):
        target_path = None
        selected_item = self.selected_browser_item()

        if selected_item is not None:
            selected_path = selected_item.data(0, Qt.ItemDataRole.UserRole) or ""
            selected_type = selected_item.data(0, Qt.ItemDataRole.UserRole + 1)

            if selected_type == "folder":
                target_path = selected_path
            elif selected_type == "audio":
                target_path = os.path.dirname(selected_path)

        if target_path is None and self.editor_project_folders:
            target_path = self.editor_project_folders[0]

        if not target_path:
            QMessageBox.information(self, "未添加项目文件夹", "当前未添加项目文件夹。")
            self._set_browser_status("当前未添加项目文件夹", log=True)
            return False

        if not os.path.isdir(target_path):
            QMessageBox.warning(self, "目录不存在", "当前目录不存在，请重新选择。")
            self._set_browser_status("目录不存在，请重新选择", log=True)
            return False

        try:
            os.startfile(target_path)
            return True
        except OSError as e:
            QMessageBox.warning(self, "打开目录失败", f"打开目录失败：{e}")
            self._log(f"打开音频编辑区文件目录失败: {target_path} - {e}")
            return False

    def clear_editor_browser_folder(self):
        self.browser_scan_request_id += 1
        self.editor_browser_folder = ""
        self.editor_project_folders = []
        self.browser_all_files = []
        self.config_data["editor_project_folders"] = []
        self.config_data["editor_browser_folder"] = ""
        self.config_data = self._save_config(self.config_data)
        self.browser_filter_edit.clear()
        self.browser_tree.clear()
        self._reset_browser_preview()
        self._refresh_browser_folder_label()
        self._set_browser_status("空闲")
        self._log("音频编辑区已清除文件目录")
        return True

    def start_editor_browser_scan(self, folder_paths=None):
        folders = self._normalize_project_folders(folder_paths or self.editor_project_folders)

        if not folders:
            self.browser_all_files = []
            self.apply_browser_filter()
            self._set_browser_status("未添加项目文件夹", log=True)
            return False

        self.browser_scan_request_id += 1
        request_id = self.browser_scan_request_id
        self._set_browser_status("正在读取目录...", log=True)

        thread = AudioBrowserScanThread(folders, request_id, self)
        thread.finished_signal.connect(self.on_editor_browser_scan_finished)
        thread.finished.connect(thread.deleteLater)
        self.browser_scan_thread = thread
        thread.start()
        return True

    def on_editor_browser_scan_finished(self, result):
        request_id = result.get("request_id")

        if request_id != self.browser_scan_request_id:
            return

        self.browser_scan_thread = None
        self.browser_all_files = list(result.get("files") or [])

        if self.browser_selected_file_path and not self._browser_path_exists_in_files(
            self.browser_selected_file_path,
            self.browser_all_files,
        ):
            self._reset_browser_preview(clear_selection=True)

        self.apply_browser_filter()

        for skipped in result.get("skipped") or []:
            self._log(f"音频项目文件夹跳过: {skipped.get('path')} - {skipped.get('error')}")

        if self.browser_all_files:
            self._set_browser_status("读取完成", log=True)
        else:
            self._set_browser_status("未发现支持的音频文件", log=True)

        self._log(f"音频项目文件夹读取完成: {len(self.editor_project_folders)} 个项目文件夹，{len(self.browser_all_files)} 个音频文件")

    def apply_browser_filter(self):
        if not hasattr(self, "browser_tree"):
            return

        keyword = self.browser_filter_edit.text().strip().lower() if hasattr(self, "browser_filter_edit") else ""
        visible_files = [
            item for item in self.browser_all_files
            if not keyword or keyword in item.get("filename", "").lower()
        ]

        self.populate_browser_tree(visible_files, filtered=bool(keyword))
        self._restore_browser_selection()
        self._update_browser_title(len(visible_files) if keyword else None)

    def populate_browser_tree(self, files, filtered=False):
        expanded_paths = self._expanded_browser_folder_paths()
        self.browser_tree.clear()
        current_path = os.path.normcase(os.path.normpath(self.current_audio_path or ""))
        root_items = {}
        folder_items = {}

        if not filtered:
            for root_path in self.editor_project_folders:
                self._ensure_browser_folder_item(root_path, root_path, None, root_items, folder_items)

        for item in files:
            path = item.get("path") or ""
            filename = item.get("filename") or "-"
            modified_time = format_modified_time(item.get("modified_time"))
            root_path = item.get("root_path") or self._matching_project_root_for_path(path)
            is_current_edit_file = current_path and os.path.normcase(os.path.normpath(path)) == current_path

            parent_item = self._ensure_browser_folder_item(root_path, root_path, None, root_items, folder_items)
            current_folder_path = root_path

            for folder_name in item.get("relative_dir_parts") or []:
                current_folder_path = os.path.join(current_folder_path, folder_name)
                parent_item = self._ensure_browser_folder_item(
                    current_folder_path,
                    folder_name,
                    parent_item,
                    root_items,
                    folder_items,
                )

            display_name = f"▶ {filename}" if is_current_edit_file else filename
            file_item = QTreeWidgetItem(parent_item, [display_name])
            file_item.setData(0, Qt.ItemDataRole.UserRole, path)
            file_item.setData(0, Qt.ItemDataRole.UserRole + 1, "audio")
            file_item.setData(0, Qt.ItemDataRole.UserRole + 2, item)
            file_item.setData(0, Qt.ItemDataRole.UserRole + 3, filename)
            file_item.setFlags(file_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            file_item.setSizeHint(0, QSize(0, 24))
            tooltip = f"{filename}\n{path}\n格式：{item.get('ext') or '-'}\n大小：{format_file_size(item.get('size'))}\n修改时间：{modified_time}"

            if is_current_edit_file:
                font = file_item.font(0)
                font.setBold(True)
                file_item.setFont(0, font)
                tooltip = f"{tooltip}\n当前编辑文件"

            file_item.setToolTip(
                0,
                tooltip
            )

        self.update_browser_folder_stats()
        self._restore_browser_expanded_paths(expanded_paths, expand_all=filtered)

    def _ensure_browser_folder_item(self, folder_path, display_name, parent_item, root_items, folder_items):
        normalized_path = os.path.normpath(os.path.abspath(folder_path))
        key = os.path.normcase(normalized_path)

        if key in folder_items:
            return folder_items[key]

        label = os.path.basename(normalized_path) or normalized_path
        display_label = label if parent_item is None else (display_name or label)

        if parent_item is None:
            item = QTreeWidgetItem()
            self.browser_tree.addTopLevelItem(item)
            root_items[key] = item
        else:
            item = QTreeWidgetItem(parent_item)

        if not os.path.isdir(normalized_path):
            display_label = f"{display_label}（不可用）"

        item.setData(0, Qt.ItemDataRole.UserRole, normalized_path)
        item.setData(0, Qt.ItemDataRole.UserRole + 1, "folder")
        item.setData(0, Qt.ItemDataRole.UserRole + 3, display_label)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        item.setSizeHint(0, QSize(0, 24))
        item.setToolTip(0, normalized_path)
        self.update_browser_folder_arrow(item)

        folder_items[key] = item
        return item

    def update_browser_folder_stats(self):
        items = list(self._iter_browser_tree_items())

        for item in reversed(items):
            if item.data(0, Qt.ItemDataRole.UserRole + 1) != "folder":
                continue

            direct_folder_count = 0
            direct_audio_count = 0
            total_audio_count = 0

            for index in range(item.childCount()):
                child = item.child(index)
                child_type = child.data(0, Qt.ItemDataRole.UserRole + 1)

                if child_type == "folder":
                    direct_folder_count += 1
                    child_stats = child.data(0, Qt.ItemDataRole.UserRole + 2) or {}
                    total_audio_count += int(child_stats.get("total_audio_count") or 0)
                elif child_type == "audio":
                    direct_audio_count += 1
                    total_audio_count += 1

            item.setData(0, Qt.ItemDataRole.UserRole + 2, {
                "direct_folder_count": direct_folder_count,
                "direct_audio_count": direct_audio_count,
                "total_audio_count": total_audio_count,
            })

    def _expanded_browser_folder_paths(self):
        expanded = set()

        if not hasattr(self, "browser_tree"):
            return expanded

        for item in self._iter_browser_tree_items():
            if item.data(0, Qt.ItemDataRole.UserRole + 1) != "folder":
                continue

            if item.isExpanded():
                expanded.add(os.path.normcase(os.path.normpath(item.data(0, Qt.ItemDataRole.UserRole) or "")))

        return expanded

    def _restore_browser_expanded_paths(self, expanded_paths, expand_all=False):
        for item in self._iter_browser_tree_items():
            if item.data(0, Qt.ItemDataRole.UserRole + 1) != "folder":
                continue

            path_key = os.path.normcase(os.path.normpath(item.data(0, Qt.ItemDataRole.UserRole) or ""))
            item.setExpanded(expand_all or path_key in expanded_paths)
            self.update_browser_folder_arrow(item)

    def _iter_browser_tree_items(self):
        if not hasattr(self, "browser_tree"):
            return

        stack = [
            self.browser_tree.topLevelItem(index)
            for index in range(self.browser_tree.topLevelItemCount() - 1, -1, -1)
        ]

        while stack:
            item = stack.pop()
            yield item

            for index in range(item.childCount() - 1, -1, -1):
                stack.append(item.child(index))

    def _matching_project_root_for_path(self, path):
        for root_path in self.editor_project_folders:
            if self._folder_contains_path(root_path, path):
                return root_path

        return os.path.dirname(path or "")

    def _restore_browser_selection(self):
        if not hasattr(self, "browser_tree") or not self.browser_selected_file_path:
            return False

        selected_path = os.path.normcase(os.path.normpath(self.browser_selected_file_path))

        for item in self._iter_browser_tree_items():
            if item.data(0, Qt.ItemDataRole.UserRole + 1) != "audio":
                continue

            item_path = item.data(0, Qt.ItemDataRole.UserRole) or ""

            if os.path.normcase(os.path.normpath(item_path)) != selected_path:
                continue

            was_blocked = self.browser_tree.blockSignals(True)
            self.browser_tree.setCurrentItem(item)
            self.browser_tree.blockSignals(was_blocked)
            return True

        return False

    def _browser_path_exists_in_files(self, path, files):
        expected_path = os.path.normcase(os.path.normpath(path or ""))

        if not expected_path:
            return False

        for item in files:
            item_path = item.get("path") or ""
            if os.path.normcase(os.path.normpath(item_path)) == expected_path:
                return True

        return False

    def on_browser_selection_changed(self):
        selected_item = self.selected_browser_item()
        path = selected_item.data(0, Qt.ItemDataRole.UserRole) if selected_item else None
        item_type = selected_item.data(0, Qt.ItemDataRole.UserRole + 1) if selected_item else None

        if path and item_type == "audio":
            self._set_browser_status(f"已选择 {os.path.basename(path)}")
            self.update_browser_preview(selected_item)
        elif path and item_type == "folder":
            self._set_browser_status(f"已选择文件夹 {os.path.basename(path)}")
            self.update_browser_folder_preview(selected_item)

    def selected_browser_item(self):
        if not hasattr(self, "browser_tree"):
            return None

        selected_items = self.browser_tree.selectedItems()

        if not selected_items:
            return None

        return selected_items[0]

    def selected_browser_audio_path(self):
        selected_item = self.selected_browser_item()

        if selected_item is None:
            return None

        if selected_item.data(0, Qt.ItemDataRole.UserRole + 1) != "audio":
            return None

        return selected_item.data(0, Qt.ItemDataRole.UserRole)

    def on_browser_item_double_clicked(self, item):
        if item.data(0, Qt.ItemDataRole.UserRole + 1) == "folder":
            return True

        return self.load_selected_browser_file()

    def load_selected_browser_file(self):
        path = self.selected_browser_audio_path()

        if not path:
            QMessageBox.information(self, "未选择文件", "请先选择一个音频文件。")
            return False

        loaded = self.load_audio_file(path, source="browser")

        if loaded:
            self._set_browser_status(f"已加载 {os.path.basename(path)}", log=True)
            self._log(f"已从目录加载音频: {path}")

        return loaded

    def _refresh_browser_folder_label(self):
        if not hasattr(self, "browser_folder_value"):
            return

        if self.editor_project_folders:
            first_folder = self.editor_project_folders[0]
            text = self._compact_path(first_folder)

            if len(self.editor_project_folders) > 1:
                text = f"{text} 等 {len(self.editor_project_folders)} 项"

            self.browser_folder_value.setText(text)
            self.browser_folder_value.setToolTip("\n".join(self.editor_project_folders))
        else:
            self.browser_folder_value.setText("未添加项目文件夹")
            self.browser_folder_value.setToolTip("")

        self._update_browser_title()

    def _update_browser_title(self, visible_count=None):
        if not hasattr(self, "browser_title_label"):
            return

        total_count = len(self.browser_all_files)

        if visible_count is not None and visible_count != total_count:
            title = f"文件目录（{visible_count}/{total_count}）"
        elif total_count:
            title = f"文件目录（{total_count}）"
        else:
            title = "文件目录"

        self.browser_title_label.setText(title)

    def _set_browser_status(self, status, log=False):
        self.browser_status_text = status

        if log:
            self._log(f"音频目录：{status}")

    def _reset_browser_preview(self, clear_selection=True):
        if not hasattr(self, "browser_preview_cover"):
            return

        if clear_selection:
            self.browser_selected_file_path = None
            self.browser_selected_file_info = None

        self.browser_preview_cover.setPixmap(QPixmap())
        self.browser_preview_cover.setText("无封面")
        self.browser_preview_cover.setToolTip("")
        self.browser_preview_name.set_full_text("未选择文件")
        self.browser_preview_name.setToolTip("")
        self.browser_preview_detail.setText("-")
        self.browser_preview_detail.setToolTip("")

    def update_browser_preview(self, list_item):
        file_info = list_item.data(0, Qt.ItemDataRole.UserRole + 2) or {}
        path = file_info.get("path") or list_item.data(0, Qt.ItemDataRole.UserRole) or ""
        filename = file_info.get("filename") or os.path.basename(path) or "未选择文件"
        detail = f"{file_info.get('ext') or '-'} · {format_file_size(file_info.get('size'))}"

        self.browser_selected_file_path = os.path.normpath(os.path.abspath(path)) if path else None
        self.browser_selected_file_info = dict(file_info) if file_info else None
        self.browser_preview_name.set_full_text(filename)
        self.browser_preview_name.setToolTip(f"{filename}\n{path}")
        self.browser_preview_detail.setText(detail)
        self.browser_preview_detail.setToolTip(path)
        self._show_browser_preview_cover(None, None, "无封面")

        if not path:
            return

        result = read_audio_cover_preview(path)

        if not result.get("success"):
            self._show_browser_preview_cover(None, None, "读取失败")
            self._log(f"文件目录预览封面读取失败: {path} - {result.get('error')}")
            return

        cover_data = result.get("cover_data")

        if not cover_data:
            self._show_browser_preview_cover(None, None, "无封面")
            return

        if not self._show_browser_preview_cover(cover_data, result.get("cover_mime"), "无封面"):
            self._show_browser_preview_cover(None, None, "读取失败")
            self._log(f"文件目录预览封面数据损坏: {path}")

    def update_browser_folder_preview(self, folder_item):
        folder_path = folder_item.data(0, Qt.ItemDataRole.UserRole) or ""
        folder_name = os.path.basename(folder_path) or folder_path or "文件夹"
        stats = folder_item.data(0, Qt.ItemDataRole.UserRole + 2) or {}
        folder_count = int(stats.get("direct_folder_count") or 0)
        audio_count = int(stats.get("total_audio_count") or 0)
        self.browser_selected_file_path = None
        self.browser_selected_file_info = {
            "type": "folder",
            "path": folder_path,
            "filename": folder_name,
            "direct_folder_count": folder_count,
            "total_audio_count": audio_count,
        }
        self.browser_preview_name.set_full_text(folder_name)
        self.browser_preview_name.setToolTip(folder_path)
        self.browser_preview_detail.setText(f"{folder_count} 个文件夹 · {audio_count} 个音频")
        self.browser_preview_detail.setToolTip(folder_path)
        self._show_browser_preview_cover(None, None, "文件夹")

    def _show_browser_preview_cover(self, cover_data, cover_mime=None, placeholder="无封面"):
        if not hasattr(self, "browser_preview_cover"):
            return False

        if not cover_data:
            self.browser_preview_cover.setPixmap(QPixmap())
            self.browser_preview_cover.setText(placeholder)
            self.browser_preview_cover.setToolTip(placeholder)
            return True

        pixmap = QPixmap()

        if not pixmap.loadFromData(cover_data):
            return False

        scaled = pixmap.scaled(
            self.browser_preview_cover.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.browser_preview_cover.setText("")
        self.browser_preview_cover.setPixmap(scaled)
        self.browser_preview_cover.setToolTip(f"封面已读取：{cover_mime or '未知类型'}")
        return True

    def toggle_browser_sidebar(self):
        return self.set_browser_sidebar_collapsed(not self.editor_browser_collapsed)

    def set_browser_sidebar_collapsed(self, collapsed, persist=True):
        self.editor_browser_collapsed = bool(collapsed)

        if hasattr(self, "browser_content_widget"):
            self.browser_content_widget.setVisible(not self.editor_browser_collapsed)

        if hasattr(self, "browser_preview_frame"):
            self.browser_preview_frame.setVisible(not self.editor_browser_collapsed)

        if hasattr(self, "browser_title_label"):
            self.browser_title_label.setVisible(not self.editor_browser_collapsed)

        if hasattr(self, "browser_toggle_button"):
            self.browser_toggle_button.setText("目录" if self.editor_browser_collapsed else "收起")
            self.browser_toggle_button.setFixedWidth(38 if self.editor_browser_collapsed else 34)
            self.browser_toggle_button.setToolTip("展开文件目录" if self.editor_browser_collapsed else "收起文件目录")

        if hasattr(self, "browser_sidebar"):
            if self.editor_browser_collapsed:
                self.browser_sidebar.setMinimumWidth(34)
                self.browser_sidebar.setMaximumWidth(42)
            else:
                self.browser_sidebar.setMinimumWidth(220)
                self.browser_sidebar.setMaximumWidth(340)

        if hasattr(self, "browser_splitter"):
            if self.editor_browser_collapsed:
                self.browser_splitter.setSizes([36, 1200])
            else:
                self.browser_splitter.setSizes([260, 980])

        if persist:
            self.config_data["editor_browser_collapsed"] = self.editor_browser_collapsed
            self.config_data = self._save_config(self.config_data)

        return True

    def load_audio_file(self, file_path, source="manual", confirm_unsaved=True):
        if confirm_unsaved and not self.confirm_discard_unsaved_changes():
            return False

        self._cleanup_current_workspace_if_clean()
        normalized_path = os.path.normpath(os.path.abspath(file_path))
        validation_error = self._validate_import_path(normalized_path)

        if validation_error:
            self._show_import_message(validation_error)
            self._log(f"不支持导入的文件格式: {normalized_path}")
            self.file_load_status = "导入失败" if not self.current_audio_path else self.file_load_status
            self.error_text = validation_error
            self.update_editor_status_panel()
            return False

        self.set_playback_source(None, source_type="none", label="未加载")
        self._clear_pitch_preview_state(remove_file=True)
        self._clear_audio_metadata_display()
        self.current_audio_path = normalized_path
        self._begin_edit_workspace(normalized_path)
        self.set_playback_source(normalized_path, source_type="current_file", label="原音频")
        self._refresh_file_info()
        self.file_load_status = "已加载"
        self.playback_status = "已停止"
        self.error_text = ""
        self.update_editor_status_panel()
        self._load_audio_metadata(normalized_path)
        self._load_initial_lyrics_for_audio(normalized_path)
        self._set_pitch_buttons_enabled(True)
        self.apply_browser_filter()
        self._log(f"音频编辑区已导入文件: {normalized_path}")
        return True

    def clear_current_audio(self):
        if not self.confirm_discard_unsaved_changes():
            return False

        self._cleanup_current_workspace_if_clean()
        self.set_playback_source(None, source_type="none", label="未加载")
        self._clear_pitch_preview_state(remove_file=True)
        self.current_audio_path = None
        self.edit_workspace = None
        self.duration_ms = 0
        self.position_slider.setRange(0, 0)
        self.time_label.setText("00:00 / 00:00")
        self.play_pause_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.play_pause_button.setText("播放")
        self.update_player_action_states()
        self._refresh_file_info()
        self.file_load_status = "等待导入"
        self.playback_status = "未播放"
        self.error_text = ""
        self._clear_audio_metadata_display()
        self._clear_lyrics_preview()
        self._set_pitch_buttons_enabled(False)
        self.apply_browser_filter()
        self.update_editor_status_panel()
        self._log("音频编辑区已清除当前文件")
        return True

    def _begin_edit_workspace(self, audio_path):
        self.edit_workspace = AudioEditWorkspace.create(audio_path, self.editor_temp_folder)
        self._log(f"已创建音频编辑工作区: {self.edit_workspace.workspace_dir}")
        self.refresh_editor_dirty_state()

    def _cleanup_current_workspace_if_clean(self):
        if self.edit_workspace is None:
            return

        if self.edit_workspace.has_unsaved_changes:
            self.edit_workspace.save_pending_changes()
            return

        self.edit_workspace.remove_pending_changes()

    def _has_workspace_unsaved_changes(self):
        return bool(self.edit_workspace and self.edit_workspace.has_unsaved_changes)

    def _workspace_dirty_labels(self):
        if self.edit_workspace is None:
            return []

        unknown_flags = self.edit_workspace.unknown_dirty_flags()
        for flag in unknown_flags:
            self._log(f"发现未知导出修改类型: {flag}")

        return self.edit_workspace.dirty_labels()

    def _workspace_export_blocking_labels(self):
        if self.edit_workspace is None:
            return []

        workspace = self.edit_workspace
        blocking_labels = []
        dirty_flags = set(workspace.dirty_flags)

        if "format" in dirty_flags:
            blocking_labels.append("导出格式")

        if "metadata" in dirty_flags and (workspace.pending_metadata or {}).get("custom_dirty"):
            blocking_labels.append("自定义标签")

        for flag in workspace.unknown_dirty_flags():
            self._log(f"当前导出暂不支持未知修改类型: {flag}")
            blocking_labels.append("其他修改")

        seen = set()
        return [
            label
            for label in blocking_labels
            if not (label in seen or seen.add(label))
        ]

    def _set_workspace_exporting(self, exporting):
        self.is_workspace_exporting = bool(exporting)
        self.refresh_editor_dirty_state()

    def _mark_workspace_dirty(self, flag, pending=None):
        if not self.current_audio_path or self.edit_workspace is None:
            return False

        self.edit_workspace.mark_dirty(flag, pending or {})
        self.refresh_editor_dirty_state()
        return True

    def _clear_workspace_dirty_flag(self, flag):
        if self.edit_workspace is None:
            return

        self.edit_workspace.clear_dirty_flag(flag)
        self.refresh_editor_dirty_state()

    def _mark_workspace_metadata_dirty(self):
        if not (
            bool(getattr(self, "metadata_form_dirty", False))
            or bool(getattr(self, "custom_metadata_dirty", False))
        ):
            self._clear_workspace_dirty_flag("metadata")
            return False

        pending = {
            "fields": self._get_metadata_form_data() if hasattr(self, "metadata_title_value") else {},
            "custom_tags": dict(getattr(self, "custom_metadata_tags", {}) or {}),
            "custom_dirty": bool(getattr(self, "custom_metadata_dirty", False)),
            "form_dirty": bool(getattr(self, "metadata_form_dirty", False)),
        }
        return self._mark_workspace_dirty("metadata", pending)

    def _mark_workspace_lyrics_dirty(self):
        text = self.lyrics_preview.toPlainText() if hasattr(self, "lyrics_preview") else self.current_lrc_text
        pending = {
            "text": text or "",
            "source_path": self.current_lyrics_source_path,
            "source_type": self.current_lyrics_source_type,
        }
        return self._mark_workspace_dirty("lyrics", pending)

    def _mark_workspace_cover_dirty(self):
        if self.cover_marked_for_removal:
            action = "remove"
        elif self.current_cover_data:
            action = "replace"
        else:
            action = "none"

        pending = {
            "action": action,
            "mime": self.current_cover_mime,
            "size": len(self.current_cover_data or b""),
            "source": self.current_cover_source,
        }
        return self._mark_workspace_dirty("cover", pending)

    def _mark_workspace_pitch_dirty(self, output_path, semitones):
        pending = {
            "type": "pitch_shift",
            "output_path": output_path,
            "semitones": int(semitones or 0),
        }
        self._mark_workspace_dirty("pitch", pending)
        return self._mark_workspace_dirty("audio_content", pending)

    def _sync_pending_workspace_state_from_ui(self):
        if not self.current_audio_path:
            return

        if self.metadata_dirty:
            self._mark_workspace_metadata_dirty()

        if self.lyrics_dirty:
            self._mark_workspace_lyrics_dirty()

        if self.cover_dirty:
            self._mark_workspace_cover_dirty()

    def _default_workspace_export_path(self):
        if not self.current_audio_path:
            return os.path.join(self.editor_output_folder, "edited_audio")

        source_stem, source_ext = os.path.splitext(os.path.basename(self.current_audio_path))
        suffix = "_edited"

        labels = self.edit_workspace.dirty_labels() if self.edit_workspace else []
        if labels == ["元数据"]:
            suffix = "_metadata"
        elif labels == ["歌词"]:
            suffix = "_lyrics"
        elif labels == ["封面"]:
            suffix = "_cover"
        elif labels == ["升降调"]:
            suffix = "_pitch"

        candidate = os.path.join(self.editor_output_folder, f"{source_stem}{suffix}{source_ext}")
        if not os.path.exists(candidate):
            return candidate

        counter = 1
        while True:
            next_candidate = os.path.join(self.editor_output_folder, f"{source_stem}{suffix} ({counter}){source_ext}")
            if not os.path.exists(next_candidate):
                return next_candidate
            counter += 1

    def _normalize_workspace_export_path(self, output_path, target_format=None):
        normalized = os.path.normpath(os.path.abspath(output_path))
        _stem, ext = os.path.splitext(normalized)

        if ext:
            return normalized

        if target_format:
            return f"{normalized}.{str(target_format).lstrip('.')}"

        source_ext = os.path.splitext(self.current_audio_path or "")[1]
        return f"{normalized}{source_ext}"

    def show_export_workspace_dialog(self):
        if not self.current_audio_path:
            QMessageBox.information(self, "没有当前音频", "请先导入音频文件。")
            return False

        self._sync_pending_workspace_state_from_ui()

        if not self._has_workspace_unsaved_changes():
            QMessageBox.information(self, "没有需要导出的修改", "当前没有需要导出的修改。")
            return False

        dialog = AudioEditExportDialog(
            os.path.basename(self.current_audio_path),
            self._workspace_dirty_labels(),
            default_output_path=self._default_workspace_export_path(),
            parent=self,
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False

        mode = dialog.export_mode()
        target_format = dialog.target_format()
        output_path = None
        allow_overwrite_output = False

        if mode == "save_as":
            selected_path = dialog.output_path()

            if not selected_path:
                QMessageBox.warning(self, "缺少导出位置", "请先指定导出位置。")
                return False

            output_path = self._normalize_workspace_export_path(selected_path, target_format)

            if os.path.normcase(os.path.abspath(output_path)) == os.path.normcase(os.path.abspath(self.current_audio_path)):
                QMessageBox.warning(self, "路径冲突", "另存为新文件不能直接选择当前原文件路径，请改用覆盖原文件。")
                return False

            if os.path.exists(output_path):
                overwrite_confirm = QMessageBox.question(
                    self,
                    "确认覆盖输出文件",
                    f"目标文件已存在：\n{output_path}\n\n是否覆盖？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )

                if overwrite_confirm != QMessageBox.StandardButton.Yes:
                    return False
                allow_overwrite_output = True

        else:
            confirm = QMessageBox.question(
                self,
                "确认覆盖原文件",
                "覆盖原文件会直接修改当前音频文件。建议优先另存为新文件。\n\n是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if confirm != QMessageBox.StandardButton.Yes:
                return False

        return self.export_current_workspace(
            mode=mode,
            output_path=output_path,
            target_format=target_format,
            allow_overwrite_output=allow_overwrite_output,
        )

    def export_current_workspace(self, mode, output_path=None, target_format=None, allow_overwrite_output=False):
        if not self.current_audio_path:
            return {"success": False, "error": "当前没有导入音频文件。"}

        self._sync_pending_workspace_state_from_ui()

        if not self._has_workspace_unsaved_changes():
            return {"success": False, "error": "当前没有需要导出的修改。"}

        if target_format not in (None, "", "original"):
            message = "导出格式转换暂未接入，当前仅支持保持原格式。"
            self.error_text = message
            self.update_editor_status_panel()
            QMessageBox.warning(self, "暂不支持", message)
            return {"success": False, "error": message}

        if mode == "save_as":
            if not output_path:
                message = "请先指定导出位置。"
                self.error_text = message
                self.update_editor_status_panel()
                QMessageBox.warning(self, "缺少导出位置", message)
                return {"success": False, "error": message}

            normalized_output_path = self._normalize_workspace_export_path(output_path, target_format)
            if os.path.normcase(os.path.abspath(normalized_output_path)) == os.path.normcase(os.path.abspath(self.current_audio_path)):
                message = "另存为新文件不能直接选择当前原文件路径，请改用覆盖原文件。"
                self.error_text = message
                self.update_editor_status_panel()
                QMessageBox.warning(self, "路径冲突", message)
                return {"success": False, "error": message}

            if os.path.exists(normalized_output_path) and not allow_overwrite_output:
                message = "目标文件已存在，请先确认是否覆盖。"
                self.error_text = message
                self.update_editor_status_panel()
                QMessageBox.warning(self, "确认覆盖输出文件", message)
                return {"success": False, "error": message}

        workspace = self.edit_workspace
        blocking_labels = self._workspace_export_blocking_labels()
        if blocking_labels:
            labels_text = "、".join(blocking_labels)
            message = f"以下修改类型当前暂未接入实际导出：{labels_text}。请取消导出或先移除对应修改。"
            self.error_text = message
            self.update_editor_status_panel()
            QMessageBox.warning(self, "暂不支持导出", message)
            self._log(message)
            return {"success": False, "error": message}

        base_source = self.current_audio_path

        if "pitch" in workspace.dirty_flags or "audio_content" in workspace.dirty_flags:
            pending_audio = workspace.pending_audio_process or {}
            pending_output = pending_audio.get("output_path")

            if not pending_output or not os.path.isfile(pending_output):
                message = "当前升降调处理暂未生成可导出的结果。"
                QMessageBox.warning(self, "无法导出", message)
                self.error_text = message
                self.update_editor_status_panel()
                return {"success": False, "error": message}

            base_source = pending_output

        player_state = None
        final_path = None
        temp_path = None
        export_error_message = None

        try:
            self._set_workspace_exporting(True)
            player_state = self.release_editor_player_source()
            workspace.ensure_directories()

            if mode == "overwrite":
                final_path = self.current_audio_path
                temp_path = self._workspace_temp_export_path(final_path)
                backup_path = self._backup_current_audio_file(final_path)
                self._log(f"覆盖导出前已备份原文件: {backup_path}")
            else:
                final_path = normalized_output_path
                temp_path = self._workspace_temp_export_path(final_path)

            try:
                os.makedirs(os.path.dirname(temp_path), exist_ok=True)
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                shutil.copy2(base_source, temp_path)
            except OSError as e:
                if mode == "overwrite":
                    raise RuntimeError(f"无法在原文件目录创建临时导出文件，请检查目录权限：{e}") from e
                raise

            apply_result = self._apply_workspace_pending_changes(temp_path)

            if not apply_result.get("success"):
                raise RuntimeError(apply_result.get("error") or "导出修改应用失败。")

            self._ensure_export_output_created(temp_path)

            os.replace(temp_path, final_path)
            self._ensure_export_output_created(final_path)

            workspace.mark_exported(final_path)
            self._clear_export_dirty_state_after_success()
            self.last_exported_audio_path = final_path

            if hasattr(self, "pitch_export_path_value"):
                self.pitch_export_path_value.setText(self._compact_path(final_path))
                self.pitch_export_path_value.setToolTip(final_path)

            if mode == "overwrite":
                self._load_audio_metadata(final_path)
                self._load_initial_lyrics_for_audio(final_path)
                self.reload_editor_player_source(
                    final_path,
                    position=0,
                    volume=player_state.get("volume") if player_state else None,
                    source_type="current_file",
                    source_label="原音频",
                )
            else:
                self.reload_editor_player_source(
                    self.current_audio_path,
                    position=player_state.get("position") if player_state else None,
                    volume=player_state.get("volume") if player_state else None,
                    source_type="current_file",
                    source_label="原音频",
                )

            self.error_text = ""
            self.file_load_status = "已加载"
            self.update_editor_status_panel()
            self._log(f"统一导出完成: {final_path}")
            return {"success": True, "output_path": final_path, "error": None}

        except Exception as e:
            message = f"统一导出失败：{e}"
            export_error_message = message
            self.error_text = message
            self.update_editor_status_panel()
            QMessageBox.warning(self, "导出失败", message)
            self._log(message)
            return {"success": False, "output_path": final_path, "error": str(e)}

        finally:
            self._set_workspace_exporting(False)

            if player_state is not None and self.current_audio_path and self.player.source().isEmpty():
                self.reload_editor_player_source(
                    self.current_audio_path,
                    position=player_state.get("position"),
                    volume=player_state.get("volume"),
                    source_type="current_file",
                    source_label="原音频",
                )

            if export_error_message:
                if temp_path and final_path and os.path.normcase(os.path.abspath(temp_path)) != os.path.normcase(os.path.abspath(final_path)) and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError as cleanup_error:
                        self._log(f"清理导出临时文件失败: {cleanup_error}")
                self.error_text = export_error_message
                self.update_editor_status_panel()

    def _workspace_temp_export_path(self, final_path):
        stem, ext = os.path.splitext(os.path.basename(final_path))
        return os.path.join(os.path.dirname(os.path.abspath(final_path)), f".{stem}.exporting.tmp{ext}")

    def _backup_current_audio_file(self, source_path):
        stem, ext = os.path.splitext(os.path.basename(source_path))
        backup_path = os.path.join(self.edit_workspace.backup_dir, f"{stem}.backup{ext}")
        counter = 1

        while os.path.exists(backup_path):
            backup_path = os.path.join(self.edit_workspace.backup_dir, f"{stem}.backup ({counter}){ext}")
            counter += 1

        shutil.copy2(source_path, backup_path)
        return backup_path

    def _ensure_export_output_created(self, output_path):
        if not os.path.isfile(output_path):
            raise RuntimeError("导出文件未生成。")

        if os.path.getsize(output_path) <= 0:
            raise RuntimeError("导出文件大小为 0。")

    def _apply_workspace_pending_changes(self, target_path):
        workspace = self.edit_workspace

        if "metadata" in workspace.dirty_flags:
            pending_metadata = workspace.pending_metadata or {}

            if pending_metadata.get("custom_dirty"):
                return {"success": False, "error": "自定义标签暂未接入统一导出，请先移除自定义标签修改。"}

            fields = pending_metadata.get("fields") or {}
            result = write_audio_metadata(target_path, fields, overwrite=True)

            if not result.get("success"):
                return result

        if "cover" in workspace.dirty_flags:
            pending_cover = workspace.pending_cover or {}
            action = pending_cover.get("action")

            if action == "remove":
                result = remove_audio_cover(target_path)
            elif action == "replace":
                result = write_audio_cover(target_path, self.current_cover_data, self.current_cover_mime)
            else:
                result = {"success": True, "error": None}

            if not result.get("success"):
                return result

        if "lyrics" in workspace.dirty_flags:
            pending_lyrics = workspace.pending_lyrics or {}
            lyrics_text = pending_lyrics.get("text") or self.current_lrc_text or self.current_lyrics_text

            if not self._has_exportable_lyrics(lyrics_text):
                return {"success": False, "error": "当前没有可写入的歌词内容。"}

            result = embed_lrc_to_audio(target_path, lyrics_text, overwrite=True)

            if not result.get("embedded"):
                return {"success": False, "error": result.get("error") or "歌词写入导出文件失败。"}

        return {"success": True, "error": None}

    def _clear_export_dirty_state_after_success(self):
        self.metadata_dirty = False
        self.metadata_form_dirty = False
        self.custom_metadata_dirty = False
        self.lyrics_dirty = False
        self.cover_dirty = False
        self.cover_marked_for_removal = False
        self.is_metadata_editing = False
        self.is_lyrics_editing = False
        self._set_metadata_fields_read_only(True)
        self.metadata_edit_button.setText("编辑信息")
        self.edit_lyrics_button.setText("编辑歌词")
        self.lyrics_preview.setReadOnly(True)
        self.metadata_status_value.setText("已导出")
        self.lyrics_status = "已导出"
        self.lyrics_status_detail_value.setText(self.lyrics_status)
        self._set_cover_status("已导出")
        self._set_pitch_status("已导出")
        self.update_cover_menu_actions()
        self.update_lyrics_menu_actions()

    def select_lrc_file(self):
        file_path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "导入 .lrc",
            "",
            "LRC 歌词文件 (*.lrc *.LRC);;所有文件 (*.*)",
        )

        if not file_path:
            return

        if not self.current_audio_path:
            QMessageBox.information(
                self,
                "仅预览歌词",
                "当前未导入音频，仅预览歌词文件。",
            )

        self.load_lrc_file(file_path, source="manual")

    def sync_pending_lrc(self):
        if not self.pending_lrc_path:
            QMessageBox.information(self, "没有待导入歌词", "当前没有等待同步导入的同名 .lrc。")
            return

        if self.load_lrc_file(self.pending_lrc_path, source="sync"):
            self._log(f"已同步导入同名 .lrc: {self.current_lrc_path}")

    def sync_available_lrc(self):
        if self.pending_lrc_path:
            return self.sync_pending_lrc()

        source_path = self._available_lrc_sync_path()
        if not source_path:
            QMessageBox.information(self, "没有可同步歌词", "当前没有可同步的外部 .lrc。")
            return False

        if self.load_lrc_file(source_path, source="sync"):
            self._log(f"已同步歌词: {self.current_lrc_path}")
            return True

        return False

    def _available_lrc_sync_path(self):
        for candidate in (self.current_lrc_path, self.current_lyrics_source_path):
            if candidate and normalize_extension(candidate) == ".lrc" and os.path.isfile(candidate):
                return candidate

        return None

    def skip_pending_lrc(self):
        if not self.pending_lrc_path:
            return

        if self.current_lyrics_source_type == "embedded":
            skipped_path = self.pending_lrc_path
            self.pending_lrc_path = None
            self.lyrics_status = "已读取音频内嵌歌词；已暂不导入同名 .lrc"
            self.lyrics_status_detail_value.setText(self.lyrics_status)
            self._set_pending_lrc_controls_visible(False)
            self.update_editor_status_panel()
            self._log(f"已跳过同名 .lrc 自动导入，因为当前音频已有内嵌歌词: {skipped_path}")
            return

        self.lyrics_status = "已找到同名 .lrc，但用户暂未导入"
        self.lyrics_status_detail_value.setText(self.lyrics_status)
        self.lyrics_preview.setPlainText("已找到同名歌词，暂未导入。")
        self._clear_lrc_sync_state("未解析歌词时间轴")
        self._set_pending_lrc_controls_visible(False)
        self.update_editor_status_panel()
        self._log(f"用户选择暂不导入同名 .lrc: {self.pending_lrc_path}")

    def start_manual_lyrics_entry(self):
        if self.lyrics_dirty and not self.confirm_discard_unsaved_lyrics():
            return False

        if self.pending_lrc_path:
            self._log(f"用户放弃自动找到的同名 .lrc，改为手动编入: {self.pending_lrc_path}")

        self.current_lrc_path = None
        self.current_lyrics_source_path = None
        self.current_lyrics_source_type = "manual_text"
        self.current_lrc_source = "手动编入"
        self.pending_lrc_path = None
        self.original_lrc_text = ""
        self.current_lrc_text = ""
        self.current_lyrics_text = ""
        self.lyrics_dirty = True
        self.is_manual_lyrics = True
        self.is_lyrics_editing = True
        self.has_netease_metadata_warning = False
        self.lyrics_status = "手动编入歌词中"
        self.error_text = ""

        self.lyrics_source_value.setText("手动编入")
        self.lyrics_source_value.setToolTip("")
        if hasattr(self, "lyrics_source_field_value"):
            self.lyrics_source_field_value.setText("手动文本")
            self.lyrics_source_field_value.setToolTip("")
        self.lyrics_status_detail_value.setText(self.lyrics_status)
        self.lyrics_preview.setPlainText("")
        self.lyrics_preview.setReadOnly(False)
        self.edit_lyrics_button.setText("完成编辑")
        self.netease_metadata_hint.setVisible(False)
        self._clear_lrc_sync_state("编辑模式下已暂停同步滚动")
        self._set_pending_lrc_controls_visible(False)
        self.update_editor_status_panel()
        self.update_lyrics_menu_actions()
        self._mark_workspace_lyrics_dirty()
        self._log("用户选择手动编入歌词")
        self._log("手动歌词编辑开始")
        return True

    def load_lrc_file(self, file_path, source="manual"):
        if self.lyrics_dirty and not self.confirm_discard_unsaved_lyrics():
            return False

        normalized_path = os.path.normpath(os.path.abspath(file_path))

        if normalize_extension(normalized_path) != ".lrc":
            message = "不支持导入的歌词文件格式，请选择 .lrc 文件。"
            self._show_import_message(message)
            self._log(f"不支持导入的歌词文件格式: {normalized_path}")
            self.lyrics_status = "歌词读取失败"
            self.error_text = message
            self.update_editor_status_panel()
            return False

        if not os.path.isfile(normalized_path):
            message = "歌词文件不存在，无法导入。"
            self._show_import_message(message)
            self._log(f"歌词读取失败: {normalized_path}")
            self.lyrics_status = "歌词读取失败"
            self.error_text = message
            self.update_editor_status_panel()
            return False

        lrc_text = read_lrc_file(normalized_path)

        if lrc_text is None:
            message = "歌词读取失败。"
            self._log(f"歌词读取失败: {normalized_path}")
            self._set_lyrics_preview(
                None,
                message,
                status="歌词读取失败",
                error_text=message,
            )
            return False

        if source == "sync":
            status = "已同步导入同名 .lrc"
            source_type = "external_lrc"
        else:
            status = "已手动导入 .lrc"
            source_type = "manual_lrc"

        self._set_lyrics_preview(
            normalized_path,
            lrc_text,
            status=status,
            source_type=source_type,
        )

        if self.current_audio_path:
            self.lyrics_dirty = True
            self.lyrics_status = f"{status}，待统一导出"
            self.lyrics_status_detail_value.setText(self.lyrics_status)
            self._mark_workspace_lyrics_dirty()
            self.update_lyrics_menu_actions()

        if source == "sync":
            pass
        elif source == "drop":
            self._log(f"拖入 .lrc 到音频编辑区: {normalized_path}")
            self._log(f"音频编辑区手动导入歌词成功: {normalized_path}")
        else:
            self._log(f"音频编辑区手动导入歌词成功: {normalized_path}")

        return True

    def select_editor_output_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择音频编辑输出目录",
            self.editor_output_folder,
        )

        if not folder:
            return

        self.editor_output_folder = os.path.normpath(os.path.abspath(folder))
        self._ensure_editor_directories()
        self.config_data = load_config()
        self.config_data["editor_output_folder"] = self.editor_output_folder
        self.config_data = self._save_config(self.config_data)
        self._refresh_output_folder()
        self._log(f"音频编辑区输出目录已修改: {self.editor_output_folder}")

    def open_editor_output_folder(self):
        folder = self.editor_output_folder

        try:
            os.makedirs(folder, exist_ok=True)
            if os.name == "nt":
                os.startfile(folder)
            else:
                subprocess.Popen(["open", folder])
            self._log(f"已打开音频编辑输出目录: {folder}")
        except Exception as e:
            message = f"打开音频编辑输出目录失败: {e}"
            self.error_text = message
            self.update_editor_status_panel()
            QMessageBox.warning(self, "无法打开输出目录", message)

    def open_current_audio_folder(self):
        if not self.current_audio_path:
            QMessageBox.information(self, "尚未导入音频", "请先导入音频文件。")
            return

        folder = os.path.dirname(self.current_audio_path)

        try:
            if os.name == "nt":
                os.startfile(folder)
            else:
                subprocess.Popen(["open", folder])
            self._log(f"已打开当前音频所在位置: {folder}")
        except Exception as e:
            message = f"打开当前音频所在位置失败: {e}"
            self.error_text = message
            self.update_editor_status_panel()
            QMessageBox.warning(self, "无法打开原文件位置", message)

    def toggle_playback(self):
        if not self.playback_source_path:
            message = "当前未加载音频。"
            self.error_text = message
            self.update_editor_status_panel()
            QMessageBox.information(self, "无法播放", message)
            return False

        if not os.path.isfile(self.playback_source_path):
            message = "当前音频文件不存在，请重新导入。"
            self.file_load_status = "加载失败"
            self.player_status = "error"
            self.playback_status = "播放错误"
            self.error_text = message
            self.update_editor_status_panel()
            QMessageBox.warning(self, "无法播放", message)
            return False

        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self._log("播放暂停")
            return True

        self.player_status = "loading"
        self.playback_status = "加载中"
        self.update_editor_status_panel()
        self.player.play()
        self._log("播放开始")
        return True

    def stop_playback(self):
        self.player.stop()
        self.player.setPosition(0)
        self.position_ms = 0
        self.player_status = "stopped"
        self.playback_status = "已停止" if self.playback_source_path else "未播放"
        self._update_time_label(0)
        self._update_waveform_position()
        self._clear_lyrics_highlight()
        self.current_sync_entry_index = None
        self.current_sync_line_index = None
        if self.current_lrc_entries and self.sync_lyrics_enabled:
            self._set_lyrics_sync_status(
                f"已解析 {len(self.current_lrc_entries)} 条时间轴歌词"
            )
        self._log("播放停止")
        self.update_editor_status_panel()
        return True

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            if self._is_browser_drop_position(event) and self._drag_urls_are_directories(event):
                event.acceptProposedAction()
                return

            event.acceptProposedAction()
            return

        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            if self._is_browser_drop_position(event) and self._drag_urls_are_directories(event):
                event.acceptProposedAction()
                return

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

        if self._is_browser_drop_position(event):
            self.add_dropped_project_folders(file_paths)
            event.acceptProposedAction()
            return

        self.handle_dropped_files(file_paths)
        event.acceptProposedAction()

    def _is_browser_drop_position(self, event):
        if not hasattr(self, "browser_sidebar"):
            return False

        position = event.position().toPoint() if hasattr(event, "position") else event.pos()
        global_position = self.mapToGlobal(position)
        sidebar_position = self.browser_sidebar.mapFromGlobal(global_position)
        return self.browser_sidebar.rect().contains(sidebar_position)

    def _drag_urls_are_directories(self, event):
        if not event.mimeData().hasUrls():
            return False

        return any(
            os.path.isdir(url.toLocalFile())
            for url in event.mimeData().urls()
            if url.toLocalFile()
        )

    def handle_dropped_files(self, file_paths):
        if not file_paths:
            return False

        selected_audio_path = None
        selected_lrc_path = None
        lrc_count = 0
        skipped_messages = []

        for raw_path in file_paths:
            file_path = os.path.normpath(os.path.abspath(raw_path))

            if os.path.isdir(file_path):
                skipped_messages.append(f"暂不支持拖入文件夹: {file_path}")
                continue

            extension = normalize_extension(file_path)

            if extension == ".lrc":
                lrc_count += 1

                if selected_lrc_path is None:
                    selected_lrc_path = file_path

                continue

            if selected_audio_path is None:
                validation_error = self._validate_import_path(file_path)
                if validation_error:
                    skipped_messages.append(validation_error)
                    continue

                selected_audio_path = file_path
                continue

            if is_supported_editor_audio_file(file_path):
                continue

            validation_error = self._validate_import_path(file_path)
            if validation_error:
                skipped_messages.append(validation_error)

        for message in skipped_messages:
            self._log(message)

        if selected_audio_path is None and selected_lrc_path is None:
            message = skipped_messages[0] if skipped_messages else "未找到可导入的音频文件。"
            self._show_import_message(message)
            self.file_load_status = "导入失败" if not self.current_audio_path else self.file_load_status
            self.error_text = message
            self.update_editor_status_panel()
            return False

        changed = False

        if selected_audio_path is not None:
            changed = self.load_audio_file(selected_audio_path, source="drop")

        if selected_lrc_path is not None:
            changed = self.load_lrc_file(selected_lrc_path, source="drop") or changed

            if lrc_count > 1:
                self._log("拖入多个 .lrc 时只导入第一个可用歌词文件")

        if len(file_paths) > 1 and selected_audio_path is not None:
            self._log("拖入多个文件时只导入第一个支持的音频文件")

        return changed

    def _validate_import_path(self, file_path):
        if os.path.isdir(file_path):
            return "音频编辑区暂不支持拖入文件夹。"

        if not os.path.isfile(file_path):
            return "文件不存在，无法导入。"

        extension = normalize_extension(file_path)

        if extension == ".ncm":
            return "音频编辑区暂不支持直接编辑 .ncm，请先在自动转码区转换为普通音频格式。"

        if extension == ".lrc":
            return "歌词文件请通过歌词预览区导入。"

        if not is_supported_editor_audio_file(file_path):
            supported = ", ".join(sorted(EDITOR_AUDIO_EXTENSIONS))
            return f"不支持导入的文件格式。当前支持: {supported}"

        return ""

    def _load_initial_lyrics_for_audio(self, audio_path):
        self._clear_lyrics_preview()
        self._log(f"开始读取音频内嵌歌词: {audio_path}")
        embedded_result = read_embedded_lyrics(audio_path)

        if embedded_result.get("error"):
            self._log(
                f"内嵌歌词读取失败: {audio_path} - {embedded_result.get('error')}"
            )

        if embedded_result.get("found"):
            self._log(f"已读取音频内嵌歌词: {audio_path}")
            lrc_path = find_matching_lrc(audio_path)

            if lrc_path:
                self._log("同时发现同名 .lrc，等待用户选择")
                self._log("已跳过同名 .lrc 自动导入，因为当前音频已有内嵌歌词")

            self._set_embedded_lyrics_preview(
                embedded_result.get("lyrics") or "",
                pending_lrc_path=lrc_path,
                field=embedded_result.get("field"),
            )
            return

        self._log(f"当前音频未检测到内嵌歌词: {audio_path}")
        self._log("未检测到音频内嵌歌词，正在查找同名 .lrc")
        self._auto_load_matching_lrc(audio_path)

    def _set_embedded_lyrics_preview(self, lyrics_text, pending_lrc_path=None, status=None, field=None):
        self.current_lrc_path = None
        self.current_lyrics_source_path = None
        self.current_lyrics_source_type = "embedded"
        self.current_lrc_source = "音频内嵌歌词"
        self.pending_lrc_path = (
            os.path.normpath(os.path.abspath(pending_lrc_path))
            if pending_lrc_path else None
        )
        self.original_lrc_text = lyrics_text or ""
        self.current_lrc_text = lyrics_text or ""
        self.current_lyrics_text = lyrics_text or ""
        self.lyrics_dirty = False
        self.is_manual_lyrics = False
        self.is_lyrics_editing = False
        self.error_text = ""
        self.lyrics_status = status or "已读取音频内嵌歌词"

        if self.pending_lrc_path and status is None:
            self.lyrics_status = "已读取音频内嵌歌词；同时发现同名 .lrc，可选择导入外置歌词"

        self.lyrics_source_value.setText("音频内嵌歌词")
        self.lyrics_source_value.setToolTip("")
        if hasattr(self, "lyrics_source_field_value"):
            self.lyrics_source_field_value.setText(field or "内嵌歌词")
            self.lyrics_source_field_value.setToolTip(field or "")
        self.lyrics_status_detail_value.setText(self.lyrics_status)
        self.lyrics_preview.setReadOnly(True)
        self.edit_lyrics_button.setText("编辑歌词")
        self.lyrics_preview.setPlainText(lyrics_text or "未加载歌词。")
        self.has_netease_metadata_warning = self._looks_like_netease_metadata(lyrics_text or "")
        self.netease_metadata_hint.setVisible(self.has_netease_metadata_warning)
        self._set_pending_lrc_controls_visible(bool(self.pending_lrc_path))
        self._reparse_current_lrc_timestamps()

        if self.has_netease_metadata_warning:
            self._log("检测到疑似网易歌词元数据")

        self.update_editor_status_panel()

    def _auto_load_matching_lrc(self, audio_path):
        lrc_path = find_matching_lrc(audio_path)

        if not lrc_path:
            self._set_lyrics_preview(
                None,
                "未找到任何歌词。\n\n你可以：\n* 手动导入 .lrc；\n* 或手动编入歌词。",
                status="未找到任何歌词，可手动导入或手动编入",
                error_text=self.error_text,
            )
            self._log(f"音频编辑区未找到任何歌词: {audio_path}")
            return

        self.pending_lrc_path = os.path.normpath(os.path.abspath(lrc_path))
        self.current_lrc_path = None
        self.current_lrc_source = self.pending_lrc_path
        self.current_lyrics_source_path = None
        self.current_lyrics_source_type = None
        self.original_lrc_text = ""
        self.current_lrc_text = ""
        self.current_lyrics_text = ""
        self.lyrics_dirty = False
        self.is_manual_lyrics = False
        self.has_netease_metadata_warning = False
        self.netease_metadata_hint.setVisible(False)
        self.lyrics_source_value.setText(self.pending_lrc_path)
        self.lyrics_source_value.setToolTip(self.pending_lrc_path)
        if hasattr(self, "lyrics_source_field_value"):
            self.lyrics_source_field_value.setText("同名 .lrc 待确认")
            self.lyrics_source_field_value.setToolTip(self.pending_lrc_path)
        self.lyrics_status = "已找到同名 .lrc，等待用户确认"
        self.lyrics_status_detail_value.setText(self.lyrics_status)
        self.lyrics_preview.setPlainText(
            "已自动找到同名 .lrc 文件：\n"
            f"{self.pending_lrc_path}\n\n"
            "是否同步导入？"
        )
        self._clear_lrc_sync_state("未解析歌词时间轴")
        self._set_pending_lrc_controls_visible(True)
        self.update_editor_status_panel()
        self._log(f"已自动找到同名 .lrc，等待用户确认: {self.pending_lrc_path}")

    def _set_lyrics_preview(self, lrc_path, lrc_text, status, error_text="", source_type=None):
        self.current_lrc_path = lrc_path
        self.current_lyrics_source_path = lrc_path
        self.current_lyrics_source_type = source_type or ("external_lrc" if lrc_path else None)
        self.pending_lrc_path = None
        self.original_lrc_text = lrc_text or ""
        self.current_lrc_text = lrc_text or ""
        self.current_lyrics_text = lrc_text or ""
        self.lyrics_dirty = False
        self.is_manual_lyrics = False
        self.is_lyrics_editing = False
        self.lyrics_status = status
        self.error_text = error_text
        self.lyrics_preview.setReadOnly(True)
        self.edit_lyrics_button.setText("编辑歌词")
        self._set_pending_lrc_controls_visible(False)

        if lrc_path:
            self.current_lrc_source = lrc_path
            self.lyrics_source_value.setText(lrc_path)
            self.lyrics_source_value.setToolTip(lrc_path)
            if hasattr(self, "lyrics_source_field_value"):
                self.lyrics_source_field_value.setText("外置 .lrc")
                self.lyrics_source_field_value.setToolTip(lrc_path)
        else:
            self.current_lrc_source = ""
            self.lyrics_source_value.setText("未加载歌词")
            self.lyrics_source_value.setToolTip("")
            if hasattr(self, "lyrics_source_field_value"):
                self.lyrics_source_field_value.setText("-")
                self.lyrics_source_field_value.setToolTip("")

        self.lyrics_status_detail_value.setText(status)
        self.lyrics_preview.setPlainText(lrc_text or "未加载歌词。")
        self.has_netease_metadata_warning = self._looks_like_netease_metadata(lrc_text or "")
        self.netease_metadata_hint.setVisible(self.has_netease_metadata_warning)
        self._reparse_current_lrc_timestamps()

        if self.has_netease_metadata_warning:
            self._log("检测到疑似网易歌词元数据")

        self.update_editor_status_panel()

    def _clear_lyrics_preview(self):
        self.current_lrc_path = None
        self.current_lrc_source = ""
        self.current_lyrics_source_path = None
        self.current_lyrics_source_type = None
        self.pending_lrc_path = None
        self.original_lrc_text = ""
        self.current_lrc_text = ""
        self.current_lyrics_text = ""
        self.lyrics_dirty = False
        self.is_manual_lyrics = False
        self.is_lyrics_editing = False
        self.has_netease_metadata_warning = False
        self.lyrics_status = "未加载歌词"

        if hasattr(self, "lyrics_source_value"):
            self.lyrics_source_value.setText("未加载歌词")
            self.lyrics_source_value.setToolTip("")
            if hasattr(self, "lyrics_source_field_value"):
                self.lyrics_source_field_value.setText("-")
                self.lyrics_source_field_value.setToolTip("")
            self.lyrics_status_detail_value.setText("未加载歌词")
            self.lyrics_preview.setPlainText("未加载歌词。")
            self.lyrics_preview.setReadOnly(True)
            self.edit_lyrics_button.setText("编辑歌词")
            self.netease_metadata_hint.setVisible(False)
            self._clear_lrc_sync_state("未解析歌词时间轴")
            self._set_pending_lrc_controls_visible(False)

    def toggle_lyrics_edit_mode(self):
        if self.is_lyrics_editing:
            self.is_lyrics_editing = False
            self.lyrics_preview.setReadOnly(True)
            self.edit_lyrics_button.setText("编辑歌词")
            edited_text = self.lyrics_preview.toPlainText()
            if self.is_manual_lyrics and not edited_text.strip():
                self.lyrics_dirty = True
                self.lyrics_status = "当前手动歌词为空"
                self.lyrics_status_detail_value.setText(self.lyrics_status)
                self._log("手动歌词为空")
            elif self.is_manual_lyrics:
                self.lyrics_dirty = True
                self.lyrics_status = "手动歌词已编辑，尚未保存"
                self.lyrics_status_detail_value.setText(self.lyrics_status)
                self._log("手动歌词编辑完成")
            elif edited_text != self.current_lrc_text:
                self.lyrics_dirty = True
                self.lyrics_status = "歌词已修改，尚未保存"
                self.lyrics_status_detail_value.setText(self.lyrics_status)
            self.current_lrc_text = edited_text
            self.current_lyrics_text = edited_text
            if self.lyrics_dirty:
                self._mark_workspace_lyrics_dirty()
            self._reparse_current_lrc_timestamps()
            self._log("歌词编辑已完成，当前仅保存在编辑区")
            self.update_editor_status_panel()
            self.update_lyrics_menu_actions()
            return

        if not self.lyrics_preview.toPlainText().strip() or self.lyrics_status in (
            "未加载歌词",
            "未找到同名 .lrc",
            "未找到同名 .lrc，可手动导入或手动编入",
            "未找到任何歌词，可手动导入或手动编入",
            "已找到同名 .lrc，等待用户确认",
            "已找到同名 .lrc，但用户暂未导入",
        ):
            QMessageBox.information(self, "没有可编辑歌词", "当前没有已导入的歌词内容。")
            return

        self.is_lyrics_editing = True
        self.lyrics_preview.setReadOnly(False)
        self.edit_lyrics_button.setText("完成编辑")
        self._clear_lyrics_highlight()
        self._set_lyrics_sync_status("编辑模式下已暂停同步滚动")
        self.focus_lyrics_body()
        self.update_editor_status_panel()
        self.update_lyrics_menu_actions()
        self._log("用户进入歌词编辑模式")

    def restore_original_lyrics(self):
        if self.current_lyrics_source_type == "embedded":
            if not self.current_audio_path:
                message = "当前歌词没有原文来源，无法恢复。"
                QMessageBox.information(self, "无可恢复内容", message)
                self.lyrics_status = message
                self.lyrics_status_detail_value.setText(self.lyrics_status)
                self.update_editor_status_panel()
                return

            embedded_result = read_embedded_lyrics(self.current_audio_path)

            if not embedded_result.get("found"):
                message = "音频内嵌歌词读取失败，无法恢复原文。"
                if embedded_result.get("error"):
                    message = f"{message} {embedded_result.get('error')}"
                QMessageBox.information(self, "无可恢复内容", message)
                self.lyrics_status = "歌词读取失败"
                self.error_text = message
                self.lyrics_status_detail_value.setText(self.lyrics_status)
                self.update_editor_status_panel()
                self._log(f"内嵌歌词恢复失败: {self.current_audio_path}")
                return

            self._set_embedded_lyrics_preview(
                embedded_result.get("lyrics") or "",
                status="已从音频内嵌歌词恢复原文",
            )
            self._clear_workspace_dirty_flag("lyrics")
            self._log("已从音频内嵌歌词恢复原文")
            return

        if not self.current_lrc_path:
            message = "当前歌词没有原文来源，无法恢复。"
            QMessageBox.information(self, "无可恢复内容", message)
            self.lyrics_status = message
            self.lyrics_status_detail_value.setText(self.lyrics_status)
            self.update_editor_status_panel()
            self._log("当前歌词没有原文来源，无法恢复")
            return

        lrc_text = read_lrc_file(self.current_lrc_path)

        if lrc_text is None:
            message = "歌词读取失败。"
            self._set_lyrics_preview(
                self.current_lrc_path,
                self.current_lrc_text,
                status="歌词读取失败",
                error_text=message,
            )
            self._log(f"歌词读取失败: {self.current_lrc_path}")
            return

        status = self.lyrics_status
        if status == "歌词读取失败":
            status = "已手动导入 .lrc"

        self._set_lyrics_preview(self.current_lrc_path, lrc_text, status=status)
        self._clear_workspace_dirty_flag("lyrics")
        self._log("用户恢复歌词原文")

    def save_lrc_as(self):
        lyrics_text = self._get_current_lyrics_text()

        if not self._has_exportable_lyrics(lyrics_text):
            QMessageBox.information(self, "没有歌词内容", "当前没有可导出的歌词内容。")
            return False

        default_path = self._default_lrc_save_path()
        target_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "另存为 .lrc",
            default_path,
            "LRC 歌词文件 (*.lrc);;所有文件 (*.*)",
        )

        if not target_path:
            return False

        target_path = os.path.normpath(os.path.abspath(target_path))
        if normalize_extension(target_path) != ".lrc":
            target_path = f"{target_path}.lrc"

        if os.path.exists(target_path) and not self._confirm_overwrite_lrc(target_path):
            self._log(f"用户取消覆盖 .lrc: {target_path}")
            return False

        try:
            write_lrc_file(target_path, lyrics_text)
        except Exception as e:
            message = f"歌词另存失败: {e}"
            self.lyrics_status = "保存失败"
            self.error_text = message
            self.lyrics_status_detail_value.setText(self.lyrics_status)
            self.update_editor_status_panel()
            QMessageBox.warning(self, "保存失败", message)
            self._log(message)
            return False

        self.current_lrc_path = target_path
        self.current_lyrics_source_path = target_path
        self.current_lyrics_source_type = "manual_lrc" if self.is_manual_lyrics or self.current_lyrics_source_type == "embedded" else "external_lrc"
        self.current_lrc_source = target_path
        if hasattr(self, "lyrics_source_field_value"):
            self.lyrics_source_field_value.setText("外置 .lrc")
            self.lyrics_source_field_value.setToolTip(target_path)
        self.original_lrc_text = lyrics_text
        self.current_lrc_text = lyrics_text
        self.current_lyrics_text = lyrics_text
        self.lyrics_dirty = False
        if self.is_manual_lyrics:
            self.lyrics_status = "手动歌词已另存为 .lrc"
        else:
            self.lyrics_status = "歌词已另存为 .lrc"
        self.error_text = ""
        self.lyrics_source_value.setText(target_path)
        self.lyrics_source_value.setToolTip(target_path)
        self.lyrics_status_detail_value.setText(self.lyrics_status)
        self._reparse_current_lrc_timestamps()
        self.update_editor_status_panel()
        self.update_lyrics_menu_actions()
        if self.is_manual_lyrics:
            self._log(f"手动歌词已另存为 .lrc: {target_path}")
        else:
            self._log(f"用户另存为 .lrc: {target_path}")
        return True

    def save_lrc_to_original(self):
        lyrics_text = self._get_current_lyrics_text()

        if not self._has_exportable_lyrics(lyrics_text):
            QMessageBox.information(self, "没有歌词内容", "当前没有可保存的歌词内容。")
            return False

        if not self.current_lyrics_source_path:
            if self.current_lyrics_source_type == "embedded":
                message = "当前歌词来源为音频内嵌歌词，没有原 .lrc 文件。请使用“另存为 .lrc”或“写入当前音频”。"
                QMessageBox.information(self, "没有原 .lrc 来源", message)
                self.lyrics_status = "当前歌词来源为音频内嵌歌词，没有原 .lrc 文件"
                self.lyrics_status_detail_value.setText(self.lyrics_status)
                self.update_editor_status_panel()
                self._log("当前歌词来源为音频内嵌歌词，没有原 .lrc 文件")
                return False

            QMessageBox.information(
                self,
                "没有原 .lrc 来源",
                "当前歌词没有原 .lrc 来源，请使用“另存为 .lrc”。",
            )
            return False

        source_path = os.path.normpath(os.path.abspath(self.current_lyrics_source_path))

        if not os.path.isfile(source_path):
            QMessageBox.information(
                self,
                "原 .lrc 不存在",
                "原 .lrc 文件不存在，请使用“另存为 .lrc”。",
            )
            return False

        confirm = QMessageBox.question(
            self,
            "确认覆盖原 .lrc",
            f"即将覆盖原 .lrc 文件：\n{source_path}\n\n此操作会修改原歌词文件，是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if confirm != QMessageBox.StandardButton.Yes:
            self._log(f"用户取消覆盖原 .lrc: {source_path}")
            return False

        try:
            write_lrc_file(source_path, lyrics_text)
        except Exception as e:
            message = f"保存到原 .lrc 失败: {e}"
            self.lyrics_status = "保存失败"
            self.error_text = message
            self.lyrics_status_detail_value.setText(self.lyrics_status)
            self.update_editor_status_panel()
            QMessageBox.warning(self, "保存失败", message)
            self._log(message)
            return False

        self.original_lrc_text = lyrics_text
        self.current_lrc_text = lyrics_text
        self.current_lyrics_text = lyrics_text
        self.lyrics_dirty = False
        self.lyrics_status = "已保存到原 .lrc"
        self.error_text = ""
        self.lyrics_status_detail_value.setText(self.lyrics_status)
        self._reparse_current_lrc_timestamps()
        self.update_editor_status_panel()
        self.update_lyrics_menu_actions()
        self._log(f"用户保存到原 .lrc: {source_path}")
        return True

    def write_lyrics_to_current_audio(self):
        if not self.current_audio_path:
            QMessageBox.information(self, "没有当前音频", "当前没有导入音频文件，无法写入。")
            return False

        lyrics_text = self._get_current_lyrics_text()

        if not self._has_exportable_lyrics(lyrics_text):
            QMessageBox.information(self, "没有歌词内容", "当前没有可写入的歌词内容。")
            return False

        self.lyrics_dirty = True
        self.current_lrc_text = lyrics_text
        self.current_lyrics_text = lyrics_text
        self.lyrics_status = "歌词已加入统一导出修改"
        self.lyrics_status_detail_value.setText(self.lyrics_status)
        self._mark_workspace_lyrics_dirty()
        self.error_text = ""
        self.update_editor_status_panel()
        self.update_lyrics_menu_actions()
        self._log("歌词已加入统一导出修改")
        return True

    def release_editor_player_source(self):
        source_url = self.player.source()
        state = {
            "audio_path": self.current_audio_path,
            "position": self.player.position(),
            "volume": self.audio_output.volume(),
            "was_playing": self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState,
            "had_source": source_url.isValid() and not source_url.isEmpty(),
        }

        self._log("写入前停止播放器")
        self.player.stop()
        self._log("写入前释放播放器媒体源")
        self.player.setSource(QUrl())
        QApplication.processEvents()
        time.sleep(0.15)
        QApplication.processEvents()
        self.playback_status = "已停止"
        self.error_text = "写入音频前已临时停止播放器并释放媒体源。"
        self.update_editor_status_panel()
        self._log("播放器媒体源已释放")
        return state

    def set_playback_source(self, audio_path, source_type="unknown", label=None, position=None, volume=None):
        self.playback_source_path = audio_path
        self.playback_source_type = source_type
        self.playback_source_label = label or self._playback_label_for_source(audio_path, source_type)
        previous_source_path = self.player.source().toLocalFile()
        next_source_path = audio_path or ""
        source_changed = os.path.normcase(os.path.abspath(previous_source_path)) != os.path.normcase(os.path.abspath(next_source_path)) if previous_source_path or next_source_path else False

        if source_changed or not audio_path:
            self.player.stop()

        if source_changed:
            self.duration_ms = 0
            self.position_ms = 0
            self.position_slider.setRange(0, 0)
            self.position_slider.setValue(0)
            self._update_time_label(0)

        if audio_path:
            if source_changed and previous_source_path:
                self.player.setSource(QUrl())
                QApplication.processEvents()
            self.player.setSource(QUrl.fromLocalFile(audio_path))
            self.play_pause_button.setEnabled(True)
            self.stop_button.setEnabled(True)
            self.player_status = "loading"
        else:
            self.player.setSource(QUrl())
            self.play_pause_button.setEnabled(False)
            self.stop_button.setEnabled(False)
            self.play_pause_button.setText("播放")
            self.player_status = "stopped"
            self.duration_ms = 0
            self.position_ms = 0
            self.position_slider.setRange(0, 0)
            self.position_slider.setValue(0)
            self._update_time_label(0)

        if volume is not None:
            self.audio_output.setVolume(volume)
            self.volume = max(0, min(100, int(round(volume * 100))))

        QApplication.processEvents()

        if position is not None and position > 0:
            self.player.setPosition(position)
            self.position_ms = max(0, int(position))

        if audio_path:
            self.playback_status = "已停止"
            self.player_status = "stopped"

        if audio_path and source_changed:
            self.start_waveform_generation(audio_path, source_type=source_type)
        elif not audio_path:
            self.stop_waveform_generation()
            self.current_waveform_source_path = None
            if hasattr(self, "waveform_widget"):
                self.waveform_widget.clear_waveform()
            self.update_waveform_state(None, "未加载")

        self.refresh_player_bar_state()
        self.refresh_editor_header()
        self.update_player_action_states()

    def _playback_label_for_source(self, audio_path, source_type):
        if not audio_path or source_type == "none":
            return "未加载"

        if source_type == "current_file":
            return "原音频"

        if source_type == "pitch_preview":
            value = (
                self.current_pitch_preview_semitones
                if self.current_pitch_preview_semitones is not None
                else self.get_current_pitch_shift_value()
            )
            return f"升降调试听缓存（{self.format_pitch_shift_label(value)}）"

        if source_type == "exported_result":
            return "导出结果"

        return "未知来源"

    def reload_editor_player_source(self, audio_path, position=None, volume=None, source_type=None, source_label=None):
        if not audio_path or not os.path.isfile(audio_path):
            return

        if source_type is None:
            if self.current_audio_path and os.path.normcase(os.path.abspath(audio_path)) == os.path.normcase(os.path.abspath(self.current_audio_path)):
                source_type = "current_file"
            elif self.pitch_preview_path and os.path.normcase(os.path.abspath(audio_path)) == os.path.normcase(os.path.abspath(self.pitch_preview_path)):
                source_type = "pitch_preview"
            elif self.last_exported_audio_path and os.path.normcase(os.path.abspath(audio_path)) == os.path.normcase(os.path.abspath(self.last_exported_audio_path)):
                source_type = "exported_result"
            else:
                source_type = "unknown"

        self.set_playback_source(
            audio_path,
            source_type=source_type,
            label=source_label,
            position=position,
            volume=volume,
        )

        self.play_pause_button.setEnabled(True)
        self.stop_button.setEnabled(True)
        self.play_pause_button.setText("播放")
        self.file_load_status = "已加载"
        self.playback_status = "已停止"

        if self.lyrics_status == "歌词已写入当前音频，当前来源为音频内嵌歌词":
            self.lyrics_status = "歌词已写入当前音频，当前来源为音频内嵌歌词，播放器已重新加载"
            self.lyrics_status_detail_value.setText(self.lyrics_status)
        elif self.lyrics_status == "写入失败":
            self.error_text = f"{self.error_text}\n播放器已重新加载当前音频。".strip()
        elif hasattr(self, "metadata_status_value") and self.metadata_status_value.text() in (
            "音频信息写入失败",
            "当前格式暂不支持写入",
        ):
            self.error_text = f"{self.error_text}\n播放器已重新加载当前音频。".strip()
        elif hasattr(self, "cover_status_value") and self.cover_status_value.text() in (
            "封面写入失败",
            "当前格式暂不支持写入封面",
        ):
            self.error_text = f"{self.error_text}\n播放器已重新加载当前音频。".strip()
        else:
            self.error_text = ""

        self.update_editor_status_panel()
        self._log(f"播放器已重新加载当前音频: {audio_path}")

    def _embed_lrc_with_permission_retry(self, audio_path, lyrics_text, overwrite=False):
        max_attempts = 2
        result = None

        for attempt in range(1, max_attempts + 1):
            result = embed_lrc_to_audio(audio_path, lyrics_text, overwrite=overwrite)

            if result.get("embedded"):
                return result

            if not self._is_permission_denied_error(result.get("error")):
                return result

            if attempt >= max_attempts:
                return result

            self._log(f"Permission denied，准备重试写入: {audio_path}")
            self.player.stop()
            self.player.setSource(QUrl())
            QApplication.processEvents()
            time.sleep(0.2)
            QApplication.processEvents()

        return result or {"embedded": False, "skipped_reason": None, "error": "歌词写入失败。"}

    def toggle_metadata_edit_mode(self):
        if not self.current_audio_path:
            QMessageBox.information(self, "没有当前音频", "当前没有导入音频文件。")
            return False

        if self.is_metadata_editing:
            self.is_metadata_editing = False
            self._set_metadata_fields_read_only(True)
            self.metadata_edit_button.setText("编辑信息")
            self.metadata_status_value.setText("有未导出修改" if self.metadata_dirty else "已读取")
            self.update_editor_status_panel()
            self._log("用户完成音频信息编辑")
            return True

        self.is_metadata_editing = True
        self._set_metadata_fields_read_only(False)
        self.metadata_edit_button.setText("完成编辑")
        self.metadata_status_value.setText("编辑中")
        self.update_editor_status_panel()
        self._log("用户进入音频信息编辑模式")
        return True

    def restore_audio_metadata(self):
        if not self.current_audio_path:
            QMessageBox.information(self, "没有当前音频", "当前没有导入音频文件。")
            return False

        if self.metadata_dirty:
            confirm = QMessageBox.question(
                self,
                "恢复原信息",
                "恢复原信息会丢弃当前未导出修改，是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if confirm != QMessageBox.StandardButton.Yes:
                return False

        self._log(f"用户恢复原信息: {self.current_audio_path}")
        restored = self._load_audio_metadata(self.current_audio_path)

        if restored:
            self.metadata_dirty = False
            self.is_metadata_editing = False
            self._set_metadata_fields_read_only(True)
            self.metadata_edit_button.setText("编辑信息")
            self.metadata_status_value.setText("已读取")
            self.error_text = ""
            self._clear_workspace_dirty_flag("metadata")
            self.update_editor_status_panel()

        return restored

    def format_pitch_shift_label(self, value):
        value = int(value or 0)

        if value < 0:
            return f"降 {abs(value)} key"

        if value > 0:
            return f"升 {value} key"

        return "原调"

    def get_current_pitch_shift_value(self):
        if not hasattr(self, "pitch_shift_slider"):
            return 0

        return int(self.pitch_shift_slider.value())

    def set_pitch_shift_value(self, value):
        normalized = max(-12, min(12, int(value or 0)))
        self.pitch_shift_slider.setValue(normalized)

    def reset_pitch_shift_to_zero(self):
        self.set_pitch_shift_value(0)

    def on_pitch_shift_slider_changed(self, value):
        label = self.format_pitch_shift_label(value)

        if hasattr(self, "pitch_current_value"):
            text = f"当前设置：{label}"
            self.pitch_current_value.setText(text)
            self.pitch_current_value.setToolTip(text)

        self._set_pitch_status(f"当前设置：{label}")
        self._refresh_pitch_preview_version_label()

    def _refresh_pitch_preview_version_label(self):
        if not hasattr(self, "pitch_preview_path_value"):
            return

        if self.current_pitch_preview_semitones is None:
            text = "未生成"
        elif self.current_pitch_preview_semitones != self.get_current_pitch_shift_value():
            text = "设置已变更，等待试听"
        else:
            text = self.format_pitch_shift_label(self.current_pitch_preview_semitones)

        self.pitch_preview_path_value.setText(text)
        self.pitch_preview_path_value.setToolTip(self.current_pitch_preview_path or "")

    def _set_pitch_status(self, status):
        if hasattr(self, "pitch_status_value"):
            self.pitch_status_value.setText(status)
            self.pitch_status_value.setToolTip(status)
        self.refresh_editor_status_summary()

    def _is_pitch_processing(self):
        return self.pitch_shift_thread is not None and self.pitch_shift_thread.isRunning()

    def _set_pitch_buttons_enabled(self, enabled):
        has_audio = bool(self.current_audio_path)
        active = bool(enabled and has_audio)
        disabled_reason = "请先导入音频" if not has_audio else "音频处理正在进行，请稍候"

        if hasattr(self, "preview_pitch_button"):
            self.set_button_available(
                self.preview_pitch_button,
                active,
                disabled_reason,
                "按当前升降调设置生成试听缓存",
            )

        if hasattr(self, "export_pitch_button"):
            self.set_button_available(
                self.export_pitch_button,
                active,
                disabled_reason,
                "按当前升降调设置生成待统一导出的音频结果",
            )

        if hasattr(self, "return_original_pitch_button"):
            return_enabled = bool(has_audio and self.is_pitch_preview_loaded and enabled)
            return_reason = (
                "请先导入音频"
                if not has_audio else
                "当前没有正在预览的试听缓存"
            )
            self.set_button_available(
                self.return_original_pitch_button,
                return_enabled,
                return_reason,
                "让播放器重新预览原音频",
            )

        if hasattr(self, "pitch_shift_slider"):
            self.pitch_shift_slider.setEnabled(active)
            tip = (
                "拖动设置升降调半音数，不会自动处理音频"
                if active else
                self._unavailable_tip(disabled_reason)
            )
            self.pitch_shift_slider.setToolTip(tip)
            self.pitch_shift_slider.setStatusTip(tip)

        if hasattr(self, "pitch_reset_button"):
            self.set_button_available(
                self.pitch_reset_button,
                active,
                disabled_reason,
                "将当前升降调设置重置为原调",
            )

    def _confirm_pitch_uses_saved_file(self, action_name):
        if not (self.lyrics_dirty or self.metadata_dirty or self.cover_dirty):
            return True

        message = (
            "当前存在未导出的歌词、封面或音频信息修改。\n"
            f"{action_name}将基于当前已保存的音频文件生成，不会自动导出这些修改。\n\n"
            "是否继续？"
        )
        confirm = QMessageBox.question(
            self,
            "存在未导出修改",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return confirm == QMessageBox.StandardButton.Yes

    def _get_pitch_preview_dir(self):
        preview_dir = os.path.join(self.editor_temp_folder, "PitchPreview")
        os.makedirs(preview_dir, exist_ok=True)
        return preview_dir

    def _is_pitch_preview_path(self, file_path):
        if not file_path:
            return False

        try:
            preview_root = os.path.normcase(os.path.abspath(self._get_pitch_preview_dir()))
            candidate = os.path.normcase(os.path.abspath(file_path))
            return os.path.commonpath([preview_root, candidate]) == preview_root
        except (OSError, ValueError):
            return False

    def _remove_pitch_preview_file(self, file_path):
        if not self._is_pitch_preview_path(file_path) or not os.path.exists(file_path):
            return

        try:
            os.remove(file_path)
            self._log(f"已清理升降调试听临时文件: {file_path}")
        except OSError as e:
            self._log(f"升降调试听临时文件清理失败: {file_path} - {e}")

    def _clear_pitch_preview_state(self, remove_file=True):
        if remove_file:
            self._remove_pitch_preview_file(self.pitch_preview_path)

        self.pitch_preview_path = None
        self.current_pitch_preview_path = None
        self.current_pitch_preview_semitones = None
        self.is_pitch_preview_loaded = False
        self._refresh_pitch_preview_version_label()
        self._set_pitch_buttons_enabled(True)

    def _default_pitch_preview_output_path(self, semitones):
        source_stem, source_ext = os.path.splitext(os.path.basename(self.current_audio_path))
        suffix = f"_preview_pitch{semitones:+d}"
        return os.path.join(self._get_pitch_preview_dir(), f"{source_stem}{suffix}{source_ext}")

    def _start_pitch_shift_task(self, output_path, semitones, mode):
        self._set_pitch_buttons_enabled(False)
        self.pitch_shift_mode = mode
        self.pitch_shift_semitones = semitones
        self.pitch_shift_original_path = self.current_audio_path
        self.pitch_shift_output_path = output_path
        self.pitch_shift_player_state = self.release_editor_player_source()
        self._log("后端处理开始")
        self.pitch_shift_thread = PitchShiftThread(
            self.pitch_shift_original_path,
            output_path,
            semitones,
            mode=mode,
            parent=self,
        )
        self.pitch_shift_thread.finished_signal.connect(self._on_pitch_shift_finished)
        self.pitch_shift_thread.start()

    def preview_pitch_shift_audio(self):
        if self._is_pitch_processing():
            QMessageBox.information(self, "正在处理", "升降调处理正在进行，请稍候。")
            return False

        if not self.current_audio_path:
            QMessageBox.information(self, "没有当前音频", "请先导入音频文件。")
            return False

        source_ext = normalize_extension(self.current_audio_path)

        if source_ext == ".ncm":
            message = "音频编辑区不支持直接处理 .ncm，请先转换为普通音频格式。"
            QMessageBox.warning(self, "当前格式不支持", message)
            self._set_pitch_status("当前格式暂不支持")
            self._log(message)
            return False

        if source_ext not in SUPPORTED_PITCH_AUDIO_EXTENSIONS:
            message = "当前格式暂不支持升降调处理。"
            QMessageBox.warning(self, "当前格式不支持", message)
            self._set_pitch_status("当前格式暂不支持")
            self._log(f"当前格式不支持升降调试听: {self.current_audio_path}")
            return False

        semitones = self.get_current_pitch_shift_value()

        if semitones == 0:
            confirm_zero = QMessageBox.question(
                self,
                "确认试听",
                "当前升降调为 0，是否仍然生成试听？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if confirm_zero != QMessageBox.StandardButton.Yes:
                return False

        if not self._confirm_pitch_uses_saved_file("试听"):
            return False

        output_path = self._default_pitch_preview_output_path(semitones)
        self._remove_pitch_preview_file(self.pitch_preview_path)
        self._remove_pitch_preview_file(output_path)
        self._log("准备生成升降调试听")
        self._log(f"输入音频路径: {self.current_audio_path}")
        self._log(f"试听临时路径: {output_path}")
        self._log(f"升降调半音数: {semitones:+d}")
        self._set_pitch_status("正在生成试听...")
        self._start_pitch_shift_task(output_path, semitones, mode="preview")
        return True

    def return_to_original_pitch_audio(self):
        return self.return_to_current_audio_playback()

    def return_to_current_audio_playback(self):
        if not self.current_audio_path:
            return False

        self.reload_editor_player_source(
            self.current_audio_path,
            source_type="current_file",
            source_label="原音频",
        )
        self._clear_pitch_preview_state(remove_file=False)
        self._set_pitch_status("已返回原音频预览")
        self._log("已返回原音频预览")
        return True

    def export_pitch_shift_audio(self):
        if self._is_pitch_processing():
            QMessageBox.information(self, "正在处理", "升降调处理正在进行，请稍候。")
            return False

        if not self.current_audio_path:
            QMessageBox.information(self, "没有当前音频", "请先导入音频文件。")
            return False

        source_ext = normalize_extension(self.current_audio_path)

        if source_ext == ".ncm":
            message = "音频编辑区不支持直接处理 .ncm，请先转换为普通音频格式。"
            QMessageBox.warning(self, "当前格式不支持", message)
            self._set_pitch_status("当前格式暂不支持")
            self._log(message)
            return False

        if source_ext not in SUPPORTED_PITCH_AUDIO_EXTENSIONS:
            message = "当前格式暂不支持升降调处理。"
            QMessageBox.warning(self, "当前格式不支持", message)
            self._set_pitch_status("当前格式暂不支持")
            self._log(f"当前格式不支持升降调: {self.current_audio_path}")
            return False

        semitones = self.get_current_pitch_shift_value()

        if semitones == 0:
            confirm_zero = QMessageBox.question(
                self,
                "确认导出",
                "当前升降调为 0，是否仍然导出？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if confirm_zero != QMessageBox.StandardButton.Yes:
                return False

        if self.edit_workspace is None:
            self._begin_edit_workspace(self.current_audio_path)

        output_path = self._default_workspace_pitch_output_path(semitones)
        if os.path.exists(output_path):
            os.remove(output_path)
        self._log("准备执行升降调")
        self._log(f"输入音频路径: {self.current_audio_path}")
        self._log(f"工作区升降调输出路径: {output_path}")
        self._log(f"升降调半音数: {semitones:+d}")
        self._set_pitch_status("正在生成待导出升降调结果...")
        self._start_pitch_shift_task(output_path, semitones, mode="workspace_pitch")
        return True

    def _default_workspace_pitch_output_path(self, semitones):
        workspace_dir = self.edit_workspace.export_dir if self.edit_workspace else self.editor_temp_folder
        source_stem, source_ext = os.path.splitext(os.path.basename(self.current_audio_path))
        suffix = f"_workspace_pitch{semitones:+d}"
        os.makedirs(workspace_dir, exist_ok=True)
        return os.path.join(workspace_dir, f"{source_stem}{suffix}{source_ext}")

    def _default_pitch_shift_output_path(self, semitones):
        source_dir = os.path.dirname(self.current_audio_path)
        source_stem, source_ext = os.path.splitext(os.path.basename(self.current_audio_path))
        suffix = f"_pitch{semitones:+d}"
        return os.path.join(source_dir, f"{source_stem}{suffix}{source_ext}")

    def _normalize_pitch_output_path(self, output_path, source_ext):
        normalized = os.path.normpath(os.path.abspath(output_path))
        _stem, ext = os.path.splitext(normalized)

        if not ext:
            normalized = f"{normalized}{source_ext}"

        return normalized

    def _on_pitch_shift_finished(self, result):
        thread = self.pitch_shift_thread
        self.pitch_shift_thread = None

        if thread is not None:
            thread.deleteLater()

        success = bool(result.get("success"))
        mode = result.get("mode") or self.pitch_shift_mode or "export"
        output_path = result.get("output_path") or self.pitch_shift_output_path
        original_path = self.pitch_shift_original_path
        player_state = self.pitch_shift_player_state
        warnings = result.get("warnings") or []
        self.pitch_shift_player_state = None
        self.pitch_shift_original_path = None
        self.pitch_shift_output_path = None
        self.pitch_shift_mode = None
        finished_semitones = (
            self.pitch_shift_semitones
            if self.pitch_shift_semitones is not None
            else self.get_current_pitch_shift_value()
        )
        self.pitch_shift_semitones = None
        self._set_pitch_buttons_enabled(True)

        warning_text = "；".join(str(item) for item in warnings if item)

        if success:
            self._log(f"后端处理完成: {output_path}")
            self.error_text = ""
            self.update_editor_status_panel()

            if warning_text:
                self._log(warning_text)

            if mode == "preview":
                self.pitch_preview_path = output_path
                self.current_pitch_preview_path = output_path

                if output_path:
                    self.current_pitch_preview_semitones = finished_semitones
                    self.reload_editor_player_source(
                        output_path,
                        position=0,
                        volume=player_state.get("volume") if player_state else None,
                        source_type="pitch_preview",
                        source_label=f"升降调试听缓存（{self.format_pitch_shift_label(finished_semitones)}）",
                    )
                    self.is_pitch_preview_loaded = True
                    self._refresh_pitch_preview_version_label()
                    self._set_pitch_buttons_enabled(True)
                    status = f"正在试听升降调结果：{self.format_pitch_shift_label(finished_semitones)}"

                    if warning_text:
                        status = f"{status}；{warning_text}"
                    elif result.get("cover_copied"):
                        status = f"{status}；已复制原封面"
                    else:
                        status = f"{status}；原音频无封面"

                    self._set_pitch_status(status)
                    self._log(f"升降调试听已加载: {output_path}")
                    return

                if original_path:
                    self.reload_editor_player_source(
                        original_path,
                        position=player_state.get("position") if player_state else None,
                        volume=player_state.get("volume") if player_state else None,
                    )
                self._set_pitch_status("试听生成失败")
                return

            if mode == "workspace_pitch":
                if output_path:
                    self._mark_workspace_pitch_dirty(output_path, finished_semitones)
                    self.last_exported_audio_path = output_path
                    if hasattr(self, "pitch_export_path_value"):
                        self.pitch_export_path_value.setText("待统一导出")
                        self.pitch_export_path_value.setToolTip(output_path)

                if original_path:
                    self.reload_editor_player_source(
                        original_path,
                        position=player_state.get("position") if player_state else None,
                        volume=player_state.get("volume") if player_state else None,
                        source_type="current_file",
                        source_label="原音频",
                    )

                status = f"升降调结果已加入统一导出：{self.format_pitch_shift_label(finished_semitones)}"

                if warning_text:
                    status = f"{status}；{warning_text}"

                self._set_pitch_status(status)
                self._log(f"升降调结果已加入统一导出: {output_path}")
                return

            status = f"升降调导出完成：{output_path}"

            if warning_text:
                status = f"升降调导出完成，但封面复制失败：{warning_text}"
            elif result.get("cover_copied"):
                status = "升降调导出完成，已保留原封面。"
            else:
                status = "升降调导出完成，原音频无封面。"

            self._set_pitch_status(status)
            self.last_exported_audio_path = output_path
            if hasattr(self, "pitch_export_path_value") and output_path:
                self.pitch_export_path_value.setText(self._compact_path(output_path))
                self.pitch_export_path_value.setToolTip(output_path)

            if self.pitch_auto_load_checkbox.isChecked() and output_path:
                self._log(f"处理完成后加载结果: {output_path}")
                self._clear_pitch_preview_state(remove_file=True)
                loaded = self.load_audio_file(
                    output_path,
                    source="pitch_shift_result",
                    confirm_unsaved=False,
                )

                if loaded:
                    loaded_status = f"已加载处理结果：{output_path}"

                    if warning_text:
                        loaded_status = f"{loaded_status}；音频处理完成，但封面复制失败"
                    elif result.get("cover_copied"):
                        loaded_status = f"{loaded_status}；已保留原封面"
                    else:
                        loaded_status = f"{loaded_status}；原音频无封面"

                    self._set_pitch_status(loaded_status)
                elif original_path:
                    self.reload_editor_player_source(
                        original_path,
                        position=player_state.get("position") if player_state else None,
                        volume=player_state.get("volume") if player_state else None,
                    )
                return

            if original_path:
                self.reload_editor_player_source(
                    original_path,
                    position=player_state.get("position") if player_state else None,
                    volume=player_state.get("volume") if player_state else None,
                )
                self._set_pitch_status(status)
                self._log("处理完成后恢复原音频")
            return

        error = result.get("error") or result.get("message") or "后端处理失败。"

        if self._is_permission_denied_error(error):
            message = "处理失败：文件可能被播放器或其他程序占用，请关闭外部播放器后重试。"
        else:
            message = error

        self._set_pitch_status(f"处理失败：{message}")
        self.error_text = message
        self.update_editor_status_panel()
        QMessageBox.warning(self, "升降调处理失败", message)
        self._log(f"后端处理失败: {message}")

        if original_path:
            self.reload_editor_player_source(
                original_path,
                position=player_state.get("position") if player_state else None,
                volume=player_state.get("volume") if player_state else None,
            )
            self._log("处理失败后恢复原音频")

        if mode == "preview":
            self.is_pitch_preview_loaded = False
            self.pitch_preview_path = None
            self._set_pitch_buttons_enabled(True)

    def select_cover_image(self):
        if not self.current_audio_path:
            QMessageBox.information(self, "没有当前音频", "请先导入音频文件。")
            return False

        file_path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "导入封面",
            "",
            "封面图片 (*.jpg *.jpeg *.png);;所有文件 (*.*)",
        )

        if not file_path:
            return False

        normalized_path = os.path.normpath(os.path.abspath(file_path))
        ext = os.path.splitext(normalized_path)[1].lower()

        if ext not in SUPPORTED_COVER_EXTENSIONS:
            QMessageBox.warning(self, "不支持的封面图片格式", "不支持的封面图片格式，请选择 JPG 或 PNG 图片。")
            self._log(f"不支持的封面图片格式: {normalized_path}")
            return False

        try:
            file_size = os.path.getsize(normalized_path)
        except OSError as e:
            QMessageBox.warning(self, "封面图片读取失败", f"封面图片读取失败：{e}")
            self._log(f"封面图片读取失败: {normalized_path} - {e}")
            return False

        if file_size > COVER_IMAGE_SIZE_WARNING_BYTES:
            self._log(f"图片过大，等待用户确认: {normalized_path}")
            confirm = QMessageBox.question(
                self,
                "封面图片较大",
                "封面图片较大，可能显著增加音频文件体积，是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if confirm != QMessageBox.StandardButton.Yes:
                return False

        try:
            cover_data = Path(normalized_path).read_bytes()
        except OSError as e:
            QMessageBox.warning(self, "封面图片读取失败", f"封面图片读取失败：{e}")
            self._log(f"封面图片读取失败: {normalized_path} - {e}")
            return False

        cover_mime = self._cover_mime_from_path(normalized_path)

        if not self._show_cover_preview(cover_data, cover_mime):
            QMessageBox.warning(self, "封面图片读取失败", "封面图片读取失败，请确认图片文件未损坏。")
            self._log(f"封面图片读取失败: {normalized_path}")
            return False

        self.current_cover_data = cover_data
        self.current_cover_mime = cover_mime
        self.current_cover_source = "用户导入封面"
        self.cover_marked_for_removal = False
        self.cover_dirty = not (
            cover_data == self.original_cover_data
            and cover_mime == self.original_cover_mime
        )
        self._set_cover_status(
            "已导入新封面，待统一导出"
            if self.cover_dirty else
            "封面与原始封面一致"
        )
        self._set_cover_source(self.current_cover_source)
        self.error_text = ""
        if self.cover_dirty:
            self._mark_workspace_cover_dirty()
        else:
            self._clear_workspace_dirty_flag("cover")
        self.update_editor_status_panel()
        self.update_cover_menu_actions()
        self._log(f"用户导入封面: {normalized_path}")
        self._log(f"封面图片读取成功: {normalized_path}")
        return True

    def remove_current_cover(self):
        if not self.current_audio_path:
            QMessageBox.information(self, "没有当前音频", "请先导入音频文件。")
            return False

        if not self.current_cover_data and not self.original_cover_data:
            QMessageBox.information(self, "没有封面", "当前没有封面可移除。")
            return False

        self.current_cover_data = None
        self.current_cover_mime = None
        self.current_cover_source = ""
        self.cover_marked_for_removal = True
        self.cover_dirty = True
        self._show_cover_preview(None, None)
        self._set_cover_status("封面已标记移除，待统一导出")
        self._set_cover_source("-")
        self.error_text = ""
        self._mark_workspace_cover_dirty()
        self.update_editor_status_panel()
        self.update_cover_menu_actions()
        self._log("用户标记移除封面")
        return True

    def restore_original_cover(self):
        if not self.current_audio_path:
            QMessageBox.information(self, "没有当前音频", "当前没有导入音频文件。")
            return False

        self.current_cover_data = self.original_cover_data
        self.current_cover_mime = self.original_cover_mime
        self.current_cover_source = self.original_cover_source
        self.cover_marked_for_removal = False
        self.cover_dirty = False

        if self.original_cover_data:
            if self._show_cover_preview(self.original_cover_data, self.original_cover_mime):
                self._set_cover_status("已恢复原封面预览")
                self._set_cover_source(self.original_cover_source or "-")
            else:
                self._show_cover_preview(None, None)
                self._set_cover_status("封面读取失败")
                self._set_cover_source(self.original_cover_source or "-")
        else:
            self._show_cover_preview(None, None)
            self._set_cover_status("未读取到封面")
            self._set_cover_source("-")

        self.error_text = ""
        self._clear_workspace_dirty_flag("cover")
        self.update_editor_status_panel()
        self.update_cover_menu_actions()
        self._log("用户恢复原封面")
        return True

    def write_current_audio_cover(self):
        if not self.current_audio_path:
            QMessageBox.information(self, "没有当前音频", "当前没有导入音频文件。")
            return False

        if not self.cover_dirty:
            QMessageBox.information(self, "没有需要写入的封面", "当前没有需要写入的封面修改。")
            return False

        self._mark_workspace_cover_dirty()
        self._set_cover_status("封面修改已加入统一导出")
        self.error_text = ""
        self.update_editor_status_panel()
        self.update_cover_menu_actions()
        self._log("封面修改已加入统一导出")
        return True

    def write_current_audio_metadata(self):
        if not self.current_audio_path:
            QMessageBox.information(self, "没有当前音频", "当前没有导入音频文件。")
            return False

        self._refresh_metadata_dirty_state()

        if not self.metadata_dirty:
            QMessageBox.information(self, "没有需要写入的修改", "当前没有需要写入的音频信息修改。")
            return False

        self._mark_workspace_metadata_dirty()
        self.is_metadata_editing = False
        self._set_metadata_fields_read_only(True)
        self.metadata_edit_button.setText("编辑信息")
        self.metadata_status_value.setText("音频信息修改已加入统一导出")
        self.error_text = ""
        self.update_editor_status_panel()
        self._log("音频信息修改已加入统一导出")
        return True

    def _is_permission_denied_error(self, error_text):
        if not error_text:
            return False

        lowered = str(error_text).lower()
        return any(
            marker in lowered
            for marker in (
                "permission denied",
                "errno 13",
                "winerror 32",
                "being used by another process",
                "另一个程序正在使用",
                "文件正由另一进程使用",
            )
        )

    def confirm_discard_unsaved_lyrics(self):
        if not self.lyrics_dirty:
            return True

        self._log("当前歌词有未保存修改")
        confirm = QMessageBox.question(
            self,
            "未保存的歌词修改",
            "当前歌词有未保存的修改，是否继续？未保存内容可能会丢失。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return confirm == QMessageBox.StandardButton.Yes

    def confirm_discard_unsaved_changes(self):
        self._sync_pending_workspace_state_from_ui()

        if (
            not self.lyrics_dirty
            and not self.metadata_dirty
            and not self.cover_dirty
            and not self._has_workspace_unsaved_changes()
        ):
            return True

        dirty_labels = self._workspace_dirty_labels()
        dirty_count = len(dirty_labels) or sum(1 for dirty in (self.lyrics_dirty, self.metadata_dirty, self.cover_dirty) if dirty)

        if self._has_workspace_unsaved_changes():
            action = self._ask_workspace_switch_action(dirty_labels)

            if action == "keep":
                if self.edit_workspace is not None:
                    self.edit_workspace.save_pending_changes()
                return True

            if action == "discard":
                if self.edit_workspace is not None:
                    self.edit_workspace.discard(remove_workspace=False)
                self.metadata_dirty = False
                self.metadata_form_dirty = False
                self.custom_metadata_dirty = False
                self.lyrics_dirty = False
                self.cover_dirty = False
                self.cover_marked_for_removal = False
                self.refresh_editor_dirty_state()
                return True

            return False
        elif dirty_count > 1:
            title = "未导出的修改"
            message = "当前歌词、音频信息或封面存在未导出修改，是否继续？未导出内容可能会丢失。"
        elif self.cover_dirty:
            title = "未导出的封面修改"
            message = "当前封面有未导出的修改，是否继续？未导出内容可能会丢失。"
        elif self.metadata_dirty:
            title = "未导出的音频信息修改"
            message = "当前音频信息有未导出的修改，是否继续？未导出内容可能会丢失。"
        else:
            title = "未保存的歌词修改"
            message = "当前歌词有未保存的修改，是否继续？未保存内容可能会丢失。"

        self._log("当前歌词、音频信息或封面存在未保存修改")
        confirm = QMessageBox.question(
            self,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if confirm == QMessageBox.StandardButton.Yes:
            if self.edit_workspace is not None and self.edit_workspace.has_unsaved_changes:
                self.edit_workspace.save_pending_changes()
            return True

        return False

    def _ask_workspace_switch_action(self, dirty_labels):
        details = "、".join(dirty_labels) if dirty_labels else "当前编辑内容"
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("未导出的编辑修改")
        box.setText(f"当前文件有未导出修改：{details}。")
        box.setInformativeText("请选择如何处理当前工作区修改。")
        keep_button = box.addButton("保留并切换", QMessageBox.ButtonRole.AcceptRole)
        discard_button = box.addButton("放弃修改", QMessageBox.ButtonRole.DestructiveRole)
        cancel_button = box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel_button)
        box.exec()
        clicked = box.clickedButton()

        if clicked is keep_button:
            return "keep"

        if clicked is discard_button:
            return "discard"

        return "cancel"

    def _get_current_lyrics_text(self):
        text = self.lyrics_preview.toPlainText()
        if self.is_lyrics_editing and text != self.current_lrc_text:
            self.lyrics_dirty = True
            if self.is_manual_lyrics:
                self.lyrics_status = "手动歌词已编辑，尚未保存"
            else:
                self.lyrics_status = "歌词已修改，尚未保存"
            self.lyrics_status_detail_value.setText(self.lyrics_status)
            self._mark_workspace_lyrics_dirty()
            self.update_editor_status_panel()
            self.update_lyrics_menu_actions()
        self.current_lrc_text = text
        self.current_lyrics_text = text
        return text

    def _has_exportable_lyrics(self, text):
        if not text.strip() or text.strip() == "未加载歌词。":
            return False

        return self.lyrics_status not in (
            "未加载歌词",
            "未找到同名 .lrc",
            "未找到同名 .lrc，可手动导入或手动编入",
            "未找到任何歌词，可手动导入或手动编入",
            "已找到同名 .lrc，等待用户确认",
            "已找到同名 .lrc，但用户暂未导入",
            "歌词读取失败",
            "当前手动歌词为空",
        )

    def _default_lrc_save_path(self):
        if self.current_audio_path:
            base_name = f"{os.path.splitext(os.path.basename(self.current_audio_path))[0]}.lrc"
            base_dir = os.path.dirname(self.current_audio_path)
        elif self.current_lyrics_source_path:
            base_name = os.path.basename(self.current_lyrics_source_path)
            base_dir = os.path.dirname(self.current_lyrics_source_path)
        else:
            base_name = "lyrics.lrc"
            base_dir = self.editor_output_folder

        return os.path.join(base_dir, base_name)

    def _confirm_overwrite_lrc(self, target_path):
        confirm = QMessageBox.question(
            self,
            "确认覆盖 .lrc",
            f"目标 .lrc 文件已存在：\n{target_path}\n\n是否覆盖？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return confirm == QMessageBox.StandardButton.Yes

    def jump_to_lyrics_body(self):
        self.focus_lyrics_body()
        text = self.lyrics_preview.toPlainText()
        index = self._find_first_lrc_timestamp_index(text)

        if index < 0:
            return

        cursor = self.lyrics_preview.textCursor()
        cursor.setPosition(index)
        self.lyrics_preview.setTextCursor(cursor)
        self.lyrics_preview.ensureCursorVisible()

    def _set_pending_lrc_controls_visible(self, visible):
        for button in (
            self.sync_lrc_button,
            self.skip_lrc_button,
            self.choose_other_lrc_button,
        ):
            button.setVisible(False)

        if hasattr(self, "sync_pending_lrc_action"):
            for action in (
                getattr(self, "sync_pending_lrc_action", None),
                getattr(self, "skip_pending_lrc_action", None),
                getattr(self, "choose_other_lrc_action", None),
            ):
                if action is None:
                    continue
                action.setVisible(visible)
                action.setEnabled(visible)

        self.update_lyrics_menu_actions()

    def _looks_like_netease_metadata(self, text):
        head_lines = text.splitlines()[:12]
        head_text = "\n".join(head_lines).strip()

        if not head_text:
            return False

        first_timestamp_index = self._find_first_lrc_timestamp_index(head_text)
        prefix = head_text if first_timestamp_index < 0 else head_text[:first_timestamp_index]
        lowered_prefix = prefix.lower()

        if any(marker in lowered_prefix for marker in ('{"t":', '"tx":', '"c":[', '"c": [')):
            return True

        if "{" in prefix and any(marker in prefix for marker in ('"t"', '"tx"', '"c"')):
            return True

        return first_timestamp_index > 40 and "{" in prefix and "}" in prefix

    def _find_first_lrc_timestamp_index(self, text):
        for marker in ("[00:", "[01:", "[02:", "[03:", "[04:", "[05:", "[06:", "[07:", "[08:", "[09:"):
            index = text.find(marker)

            if index >= 0:
                return index

        return -1

    def toggle_lyrics_sync(self, _state=None):
        self.sync_lyrics_enabled = self.sync_lyrics_checkbox.isChecked()

        if not self.sync_lyrics_enabled:
            self._clear_lyrics_highlight()
            self.current_sync_entry_index = None
            self.current_sync_line_index = None
            self._set_lyrics_sync_status("同步滚动已关闭")
            self.update_editor_status_panel()
            return

        if self.is_lyrics_editing:
            self._set_lyrics_sync_status("编辑模式下已暂停同步滚动")
        elif self.current_lrc_entries:
            self._set_lyrics_sync_status("同步滚动已开启")
            self._update_lyrics_sync_for_position(self.player.position(), force=True)
        else:
            self._set_lyrics_sync_status("当前歌词没有可同步时间轴")

        self.update_editor_status_panel()

    def _reparse_current_lrc_timestamps(self):
        text = self.lyrics_preview.toPlainText()
        self.current_lrc_entries = parse_lrc_timestamps(text)
        self.current_sync_entry_index = None
        self.current_sync_line_index = None
        self.last_lyrics_sync_position = None
        self._clear_lyrics_highlight()

        if self.is_lyrics_editing:
            self._set_lyrics_sync_status("编辑模式下已暂停同步滚动")
        elif self.current_lrc_entries:
            self._set_lyrics_sync_status(
                f"已解析 {len(self.current_lrc_entries)} 条时间轴歌词"
            )

            if (
                self.sync_lyrics_enabled and
                self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
            ):
                self._update_lyrics_sync_for_position(self.player.position(), force=True)
        else:
            self._set_lyrics_sync_status("当前歌词没有可同步时间轴")

    def _clear_lrc_sync_state(self, status="未解析歌词时间轴"):
        self.current_lrc_entries = []
        self.current_sync_entry_index = None
        self.current_sync_line_index = None
        self.last_lyrics_sync_position = None
        self._clear_lyrics_highlight()
        self._set_lyrics_sync_status(status)

    def _set_lyrics_sync_status(self, status):
        self.lyrics_sync_status = status

        if hasattr(self, "lyrics_sync_status_value"):
            self.lyrics_sync_status_value.setText(status)

    def _update_lyrics_sync_for_position(self, position, force=False):
        if not self.sync_lyrics_enabled:
            return

        if self.is_lyrics_editing:
            self._set_lyrics_sync_status("编辑模式下已暂停同步滚动")
            return

        if not self.current_lrc_entries:
            self._set_lyrics_sync_status("当前歌词没有可同步时间轴")
            return

        position = max(0, int(position or 0))

        if (
            not force and
            self.last_lyrics_sync_position is not None and
            abs(position - self.last_lyrics_sync_position) < 150
        ):
            return

        entry_index = 0

        for index, entry in enumerate(self.current_lrc_entries):
            if entry["time_ms"] <= position:
                entry_index = index
                continue

            break

        if not force and entry_index == self.current_sync_entry_index:
            self.last_lyrics_sync_position = position
            return

        self.current_sync_entry_index = entry_index
        self.last_lyrics_sync_position = position
        entry = self.current_lrc_entries[entry_index]
        self.current_sync_line_index = entry["line_index"]
        self._highlight_lyrics_line(entry["line_index"])
        self._set_lyrics_sync_status(
            f"当前同步行：第 {entry['line_index'] + 1} 行"
        )
        self.update_editor_status_panel()

    def _highlight_lyrics_line(self, line_index):
        document = self.lyrics_preview.document()
        block = document.findBlockByLineNumber(line_index)

        if not block.isValid():
            self._clear_lyrics_highlight()
            return

        selection = QTextEdit.ExtraSelection()
        line_format = QTextCharFormat()
        line_format.setBackground(QColor(76, 107, 145, 120))
        line_format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        cursor = QTextCursor(block)
        selection.cursor = cursor
        selection.format = line_format
        self.lyrics_preview.setExtraSelections([selection])

        if not self.is_lyrics_editing:
            self.lyrics_preview.setTextCursor(cursor)
            self.lyrics_preview.ensureCursorVisible()

    def _clear_lyrics_highlight(self):
        if hasattr(self, "lyrics_preview"):
            self.lyrics_preview.setExtraSelections([])

    def _on_position_changed(self, position):
        self.position_ms = max(0, int(position or 0))
        if not self.is_slider_pressed:
            self.position_slider.setValue(position)
        self._update_time_label(position)
        self._update_waveform_position()
        self._update_lyrics_sync_for_position(position)

    def _on_duration_changed(self, duration):
        self.duration_ms = max(0, duration)
        self.position_slider.setRange(0, self.duration_ms)
        self._update_time_label(self.player.position())
        self.update_player_action_states()
        self.refresh_player_bar_state()

    def _on_playback_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_pause_button.setText("暂停")
            self.player_status = "playing"
            self.playback_status = "播放中"
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self.play_pause_button.setText("播放")
            self.player_status = "paused"
            self.playback_status = "已暂停"
        else:
            self.play_pause_button.setText("播放")
            self.player_status = "stopped"
            self.playback_status = "已停止" if self.current_audio_path else "未播放"

        self.update_editor_status_panel()

    def _on_media_status_changed(self, status):
        if status in (
            QMediaPlayer.MediaStatus.LoadingMedia,
            QMediaPlayer.MediaStatus.BufferingMedia,
        ):
            self.file_load_status = "加载中"
            self.player_status = "loading"
            self.playback_status = "加载中"
            self.update_editor_status_panel()
        elif status == QMediaPlayer.MediaStatus.LoadedMedia:
            self.file_load_status = "已加载"
            if self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                self.player_status = "stopped"
                self.playback_status = "已停止" if self.playback_source_path else "未播放"
            self.error_text = ""
            self.update_editor_status_panel()
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.player.setPosition(0)
            self.position_ms = 0
            self.player_status = "stopped"
            self.playback_status = "播放结束"
            self.error_text = ""
            self._update_waveform_position()
            self._clear_lyrics_highlight()
            self.current_sync_entry_index = None
            self.current_sync_line_index = None
            self.update_editor_status_panel()
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            message = "当前系统可能不支持该格式预览。"
            self.file_load_status = "加载失败"
            self.player_status = "error"
            self.playback_status = "播放失败"
            self.error_text = message
            self.update_editor_status_panel()
            self._log(f"播放器加载失败: {message}")

    def _on_player_error(self, _error, error_string=""):
        message = error_string or "当前系统可能不支持该格式预览。"
        message = f"当前系统可能不支持该格式预览。{message}"
        self.file_load_status = "加载失败"
        self.player_status = "error"
        self.playback_status = "播放失败"
        self.error_text = message
        self.update_editor_status_panel()
        self._log(f"播放器加载失败: {message}")

    def _on_slider_pressed(self):
        if self.get_current_playback_duration_ms() <= 0 and self.position_slider.maximum() <= 0:
            return

        self.is_slider_pressed = True

    def _on_slider_released(self):
        if self.get_current_playback_duration_ms() <= 0 and self.position_slider.maximum() <= 0:
            self.is_slider_pressed = False
            return

        self.is_slider_pressed = False
        self.player.setPosition(self.position_slider.value())
        self._update_waveform_position()
        self._update_lyrics_sync_for_position(self.position_slider.value(), force=True)

    def _on_slider_moved(self, position):
        self._update_time_label(position)
        duration = max(0, int(self.duration_ms or self.player.duration() or 0))
        if duration > 0 and hasattr(self, "waveform_widget"):
            self.waveform_widget.set_position_ratio(max(0.0, min(1.0, position / duration)))

    def _on_volume_changed(self, value):
        self.volume = max(0, min(100, int(value)))
        self.audio_output.setVolume(value / 100)
        self.refresh_player_bar_state()

    def _ensure_editor_directories(self):
        for folder in (self.editor_output_folder, self.editor_temp_folder):
            if not folder:
                continue

            try:
                os.makedirs(folder, exist_ok=True)
            except OSError as e:
                self._log(f"音频编辑区目录创建失败: {folder} - {e}")

    def _refresh_file_info(self):
        if not self.current_audio_path:
            self.current_audio_display_name = ""
            self.file_name_value.setText("尚未导入音频文件")
            self.file_path_value.setText("-")
            self.file_format_value.setText("-")
            self.file_path_value.setToolTip("")
            self.refresh_editor_header()
            return

        file_name = os.path.basename(self.current_audio_path)
        self.current_audio_display_name = file_name
        self.file_name_value.setText(file_name)
        self.file_path_value.setText(self.current_audio_path)
        self.file_path_value.setToolTip(self.current_audio_path)
        self.file_format_value.setText(get_source_format(self.current_audio_path))
        self.refresh_editor_header()

    def refresh_editor_header(self):
        if not hasattr(self, "playback_source_value"):
            return

        if self.current_audio_path:
            self.file_name_value.setText(os.path.basename(self.current_audio_path))
            self.file_path_value.setText(self._compact_path(self.current_audio_path))
            self.file_path_value.setToolTip(self.current_audio_path)
            self.file_format_value.setText(get_source_format(self.current_audio_path))
        else:
            self.file_name_value.setText("尚未导入音频文件")
            self.file_path_value.setText("-")
            self.file_path_value.setToolTip("")
            self.file_format_value.setText("-")

        self.playback_source_value.setText(self.playback_source_label or "未加载")
        self.playback_source_value.setToolTip(self.playback_source_path or "")
        if self._has_workspace_unsaved_changes():
            file_state = "有未导出修改"
            file_tip = self.edit_workspace.pending_changes_path
        elif self.edit_workspace and self.edit_workspace.last_export_path:
            file_state = "已导出"
            file_tip = self.edit_workspace.last_export_path
        else:
            file_state = "未修改"
            file_tip = "编辑动作先进入工作区，不会自动修改原音频文件"
        self.original_file_state_value.setText(file_state)
        self.original_file_state_value.setToolTip(file_tip)
        self.unsaved_state_value.setText(self._dirty_state_text())
        self.unsaved_state_value.setToolTip(
            self.edit_workspace.pending_changes_path
            if self._has_workspace_unsaved_changes() else ""
        )

        can_return = bool(
            self.current_audio_path and
            self.playback_source_type not in ("none", "current_file")
        )
        self.set_button_available(
            self.return_current_playback_button,
            can_return,
            "当前已经在预览原音频" if self.current_audio_path else "请先导入音频",
            "让播放器重新预览原音频",
        )

        if hasattr(self, "export_workspace_button"):
            if self.is_workspace_exporting:
                self.export_workspace_button.setText("导出中...")
                self.set_button_available(
                    self.export_workspace_button,
                    False,
                    "当前正在导出",
                    "当前正在导出",
                )
            else:
                self.export_workspace_button.setText("导出")
                self.set_button_available(
                    self.export_workspace_button,
                    bool(self.current_audio_path and self._has_workspace_unsaved_changes()),
                    "当前没有需要导出的修改" if self.current_audio_path else "请先导入音频",
                    "导出当前编辑工作区结果",
                )

    def refresh_player_bar_state(self):
        if not hasattr(self, "player_source_hint_label"):
            return

        self._sync_public_player_state()
        label = self.playback_source_label or "未加载"
        self.player_source_hint_label.setText(f"播放器正在预览：{label}")
        self.player_source_hint_label.setToolTip(self.playback_source_path or "")

        if hasattr(self, "player_status_hint_label"):
            self.player_status_hint_label.setText(
                f"播放状态：{self._public_player_status_text()}"
            )

    def refresh_editor_dirty_state(self):
        self.refresh_editor_header()

    def refresh_editor_status_summary(self):
        if not hasattr(self, "stage_note"):
            return

        file_state = "已加载" if self.current_audio_path else "未加载"
        file_prefix = (
            f"编辑文件：{os.path.basename(self.current_audio_path)}"
            if self.current_audio_path else
            "尚未导入音频文件。"
        )
        info_state = "待导出" if self.metadata_dirty else "已同步"
        cover_state = "待导出" if self.cover_dirty else "已同步"
        lyrics_state = "待导出" if self.lyrics_dirty else (self.lyrics_status or "无歌词")
        process_state = self.pitch_status_value.text() if hasattr(self, "pitch_status_value") else "未处理"
        error_state = self.error_text or "-"
        self.stage_note.setText(
            f"{file_prefix} | 文件：{file_state} | 播放器正在预览：{self.playback_source_label or '未加载'} | "
            f"信息：{info_state} | 封面：{cover_state} | 歌词：{lyrics_state} | "
            f"处理：{process_state} | 播放状态：{self.playback_status} | "
            f"歌词状态：{self.lyrics_status} | 错误：{error_state}"
        )

    def _dirty_state_text(self):
        if self.edit_workspace is not None and self.edit_workspace.has_unsaved_changes:
            labels = self.edit_workspace.dirty_labels()
            return "、".join(labels) if labels else "有未导出修改"

        dirty_items = []

        if self.metadata_dirty:
            dirty_items.append("音频信息")

        if self.cover_dirty:
            dirty_items.append("封面")

        if self.lyrics_dirty:
            dirty_items.append("歌词")

        return "、".join(dirty_items) if dirty_items else "暂无未导出修改"

    def _compact_path(self, file_path, max_length=80):
        if not file_path:
            return "-"

        normalized = os.path.normpath(file_path)

        if len(normalized) <= max_length:
            return normalized

        drive, tail = os.path.splitdrive(normalized)
        filename = os.path.basename(normalized)
        parent = os.path.basename(os.path.dirname(normalized))
        prefix = f"{drive}{os.sep}..." if drive else "..."
        return os.path.join(prefix, parent, filename)

    def _refresh_output_folder(self):
        if hasattr(self, "editor_output_path_value"):
            self.editor_output_path_value.setText(self._compact_path(self.editor_output_folder))
            self.editor_output_path_value.setToolTip(self.editor_output_folder)

        if hasattr(self, "editor_temp_path_value"):
            self.editor_temp_path_value.setText(self._compact_path(self.editor_temp_folder))
            self.editor_temp_path_value.setToolTip(
                f"{self.editor_temp_folder}\n用于未来试听缓存、波形缓存和临时处理文件。"
            )

        if hasattr(self, "info_output_folder_value"):
            self.info_output_folder_value.setText(self.editor_output_folder)
            self.info_output_folder_value.setToolTip(self.editor_output_folder)

        if hasattr(self, "output_folder_value"):
            self.output_folder_value.setText(self.editor_output_folder)
            self.output_folder_value.setToolTip(self.editor_output_folder)

    def _load_audio_metadata(self, audio_path):
        self._log(f"准备读取音频信息: {audio_path}")
        metadata = read_audio_metadata(audio_path)
        self.current_audio_metadata = metadata

        if not metadata.get("success"):
            message = metadata.get("error") or "音频信息读取失败。"
            self._show_metadata_failure(message)
            self._log(f"音频信息读取失败: {audio_path} - {message}")
            return False

        self._update_audio_metadata_display(metadata)
        if metadata.get("format") == "FLAC":
            self._log("FLAC 标签读取成功")
        self._log(f"音频信息读取成功: {audio_path}")
        return True

    def _update_audio_metadata_display(self, metadata):
        self.error_text = ""
        form_data = self._metadata_form_from_read_result(metadata)
        self.original_metadata = dict(form_data)
        self.current_metadata_form = dict(form_data)
        self.metadata_dirty = False
        self.metadata_form_dirty = False
        self.is_metadata_editing = False
        self._set_metadata_fields_read_only(True)
        self.metadata_edit_button.setText("编辑信息")
        self._set_metadata_form_data(form_data)
        self.metadata_filename_value.setText(self._metadata_text(metadata.get("filename")))
        self.metadata_filename_value.setToolTip(self._metadata_text(metadata.get("filename")))
        path_text = self._metadata_text(metadata.get("path"))
        self.metadata_path_value.setText(self._compact_path(path_text))
        self.metadata_path_value.setToolTip(path_text)
        self.metadata_modified_value.setText(format_modified_time(metadata.get("modified_time")))
        format_summary = self._format_metadata_codec_summary(metadata)
        self.metadata_format_value.setText(format_summary)
        self.metadata_format_value.setToolTip(format_summary)
        self.metadata_container_value.setText(self._metadata_text(metadata.get("container_format")))
        self.metadata_codec_value.setText(self._metadata_text(metadata.get("codec")))
        self.metadata_file_size_value.setText(format_file_size(metadata.get("file_size")))
        self.metadata_duration_value.setText(format_seconds_duration(metadata.get("duration")))
        self.metadata_sample_rate_value.setText(format_sample_rate(metadata.get("sample_rate")))
        self.metadata_bitrate_value.setText(format_bitrate(metadata.get("bitrate")))
        self.metadata_channels_value.setText(self._metadata_text(metadata.get("channels")))
        self.metadata_bit_depth_value.setText(format_bit_depth(metadata.get("bits_per_sample")))
        self.metadata_status_value.setText("已读取")
        self._set_custom_metadata_tags(self._extract_extended_metadata_tags(metadata), dirty=False)
        self._set_cover_from_metadata(metadata)
        self.update_editor_status_panel()
        self._log("已刷新音频信息区域")

    def _set_cover_from_metadata(self, metadata):
        cover_data = metadata.get("cover_data")
        cover_mime = metadata.get("cover_mime")
        cover_source = metadata.get("cover_source") or "-"
        self.original_cover_data = cover_data
        self.original_cover_mime = cover_mime
        self.original_cover_source = cover_source if cover_data else ""
        self.current_cover_data = cover_data
        self.current_cover_mime = cover_mime
        self.current_cover_source = cover_source if cover_data else ""
        self.cover_dirty = False
        self.cover_marked_for_removal = False

        if not cover_data:
            self._show_cover_preview(None, None)
            self._set_cover_status("未读取到封面")
            self._set_cover_source("-")
            self.update_cover_menu_actions()
            self._log("未找到封面")
            return

        if not self._show_cover_preview(cover_data, cover_mime):
            self.current_cover_data = None
            self.current_cover_mime = None
            self.current_cover_source = ""
            self._show_cover_preview(None, None)
            self._set_cover_status("封面读取失败")
            self._set_cover_source(cover_source)
            self.update_cover_menu_actions()
            self._log("封面读取失败")
            return

        self._set_cover_status("已读取封面")
        self._set_cover_source(cover_source)
        self.update_cover_menu_actions()
        self._log(f"封面读取成功: {cover_mime or '未知类型'} / {cover_source}")

    def _show_cover_preview(self, cover_data, cover_mime=None):
        if not cover_data:
            self.cover_label.setPixmap(QPixmap())
            self.cover_label.setText("未读取到封面")
            self.cover_label.setToolTip("右键封面可导入、移除、恢复、写入。")
            return True

        pixmap = QPixmap()

        if not pixmap.loadFromData(cover_data):
            self.cover_label.setPixmap(QPixmap())
            self.cover_label.setText("封面读取失败")
            self.cover_label.setToolTip("封面读取失败。右键封面可导入、移除、恢复、写入。")
            return False

        scaled = pixmap.scaled(
            self.cover_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.cover_label.setText("")
        self.cover_label.setPixmap(scaled)
        self.cover_label.setToolTip(
            f"封面已读取：{cover_mime or '未知类型'}。右键封面可导入、移除、恢复、写入。"
        )
        return True

    def _set_cover_status(self, status):
        self.cover_status = status

        if hasattr(self, "cover_status_value"):
            self.cover_status_value.setText(status)

    def _set_cover_source(self, source):
        if hasattr(self, "cover_source_value"):
            self.cover_source_value.setText(source or "-")
            self.cover_source_value.setToolTip(source or "")

    def _cover_mime_from_path(self, file_path):
        ext = os.path.splitext(file_path)[1].lower()

        if ext in (".jpg", ".jpeg"):
            return "image/jpeg"

        if ext == ".png":
            return "image/png"

        return ""

    def _refresh_cover_from_current_audio(self, status):
        metadata = read_audio_metadata(self.current_audio_path)

        if not metadata.get("success"):
            message = metadata.get("error") or "音频信息读取失败。"
            self._set_cover_status("封面写入失败")
            self.error_text = f"封面写入后刷新失败：{message}"
            self._log(f"封面写入后刷新失败: {self.current_audio_path} - {message}")
            return False

        self.current_audio_metadata = metadata
        self._set_cover_from_metadata(metadata)
        self._set_cover_status(status)

        if not self.metadata_dirty:
            format_summary = self._format_metadata_codec_summary(metadata)
            self.metadata_format_value.setText(format_summary)
            self.metadata_format_value.setToolTip(format_summary)
            self.metadata_file_size_value.setText(format_file_size(metadata.get("file_size")))
            self.metadata_duration_value.setText(format_seconds_duration(metadata.get("duration")))
            self.metadata_sample_rate_value.setText(format_sample_rate(metadata.get("sample_rate")))
            self.metadata_bitrate_value.setText(format_bitrate(metadata.get("bitrate")))
            self.metadata_channels_value.setText(self._metadata_text(metadata.get("channels")))
            self.metadata_bit_depth_value.setText(format_bit_depth(metadata.get("bits_per_sample")))
            self.metadata_status_value.setText("已读取")

        return True

    def _show_metadata_failure(self, message):
        self.current_audio_metadata = None
        self.original_metadata = None
        self.current_metadata_form = {}
        self.metadata_dirty = False
        self.metadata_form_dirty = False
        self._set_custom_metadata_tags({}, dirty=False)
        self.is_metadata_editing = False
        self._reset_cover_state("未读取封面")
        self._set_metadata_fields_read_only(True)
        self.metadata_edit_button.setText("编辑信息")
        self.metadata_status_value.setText("读取失败")
        self._set_metadata_form_data({
            "title": "",
            "artist": "",
            "album": "",
            "albumartist": "",
            "date": "",
            "genre": "",
            "tracknumber": "",
            "discnumber": "",
            "bpm": "",
            "initialkey": "",
            "comment": "",
        })
        self._clear_readonly_metadata_values()
        self.error_text = f"音频信息读取失败：{message}"
        self.update_editor_status_panel()
        self._log("已刷新音频信息区域")

    def _clear_audio_metadata_display(self):
        self.current_audio_metadata = None
        self.original_metadata = None
        self.current_metadata_form = {}
        self.metadata_dirty = False
        self.metadata_form_dirty = False
        self._set_custom_metadata_tags({}, dirty=False)
        self.is_metadata_editing = False
        self._reset_cover_state("未读取封面")
        if not hasattr(self, "metadata_title_value"):
            return

        self._set_metadata_fields_read_only(True)
        self.metadata_edit_button.setText("编辑信息")
        self._set_metadata_form_data({
            "title": "",
            "artist": "",
            "album": "",
            "albumartist": "",
            "date": "",
            "genre": "",
            "tracknumber": "",
            "discnumber": "",
            "bpm": "",
            "initialkey": "",
            "comment": "",
        })

        self._clear_readonly_metadata_values()
        self.metadata_status_value.setText("未读取")
        self._log("已清空旧音频信息显示")

    def _clear_readonly_metadata_values(self):
        for label in (
            self.metadata_filename_value,
            self.metadata_path_value,
            self.metadata_modified_value,
            self.metadata_format_value,
            self.metadata_container_value,
            self.metadata_codec_value,
            self.metadata_file_size_value,
            self.metadata_duration_value,
            self.metadata_sample_rate_value,
            self.metadata_bitrate_value,
            self.metadata_channels_value,
            self.metadata_bit_depth_value,
        ):
            label.setText("-")
            label.setToolTip("")

    def _reset_cover_state(self, status="未读取封面"):
        self.original_cover_data = None
        self.original_cover_mime = None
        self.original_cover_source = ""
        self.current_cover_data = None
        self.current_cover_mime = None
        self.current_cover_source = ""
        self.cover_dirty = False
        self.cover_marked_for_removal = False

        if hasattr(self, "cover_label"):
            self._show_cover_preview(None, None)

        self._set_cover_status(status)
        self._set_cover_source("-")
        self.update_cover_menu_actions()

    def _metadata_text(self, value):
        if value is None or value == "":
            return "-"

        return str(value)

    def _metadata_form_from_read_result(self, metadata):
        return {
            "title": self._metadata_form_text(metadata.get("title")),
            "artist": self._metadata_form_text(metadata.get("artist")),
            "album": self._metadata_form_text(metadata.get("album")),
            "albumartist": self._metadata_form_text(metadata.get("albumartist")),
            "date": self._metadata_form_text(metadata.get("date")),
            "genre": self._metadata_form_text(metadata.get("genre")),
            "tracknumber": self._metadata_form_text(metadata.get("tracknumber")),
            "discnumber": self._metadata_form_text(metadata.get("discnumber")),
            "bpm": self._metadata_form_text(metadata.get("bpm")),
            "initialkey": self._metadata_form_text(metadata.get("initialkey")),
            "comment": self._metadata_form_text(metadata.get("comment")),
        }

    def _metadata_form_text(self, value):
        if value is None or value == "-":
            return ""

        return str(value)

    def _set_metadata_form_data(self, form_data):
        self._updating_metadata_form = True

        try:
            for field, widget in self._metadata_edit_widgets().items():
                text = form_data.get(field) or ""
                widget.setText(text)
                widget.setToolTip(text)
        finally:
            self._updating_metadata_form = False

    def _get_metadata_form_data(self):
        data = {}

        for field, widget in self._metadata_edit_widgets().items():
            text = widget.text().strip()
            data[field] = text

        self.current_metadata_form = dict(data)
        return data

    def _metadata_edit_widgets(self):
        return {
            "title": self.metadata_title_value,
            "artist": self.metadata_artist_value,
            "album": self.metadata_album_value,
            "albumartist": self.metadata_album_artist_value,
            "date": self.metadata_date_value,
            "genre": self.metadata_genre_value,
            "tracknumber": self.metadata_track_value,
            "discnumber": self.metadata_disc_value,
            "bpm": self.metadata_bpm_value,
            "initialkey": self.metadata_key_value,
            "comment": self.metadata_comment_value,
        }

    def _set_metadata_fields_read_only(self, read_only):
        if not hasattr(self, "metadata_title_value"):
            return

        for widget in self._metadata_edit_widgets().values():
            widget.setReadOnly(read_only)

    def _on_metadata_field_changed(self, _text=None):
        if self._updating_metadata_form or not self.current_audio_path:
            return

        self._refresh_metadata_dirty_state(log_on_dirty=True)

    def _set_custom_metadata_tags(self, tags, dirty=False):
        self.custom_metadata_tags = dict(tags or {})
        self.custom_metadata_dirty = dirty

        if not dirty:
            self.original_custom_metadata_tags = dict(tags or {})

        self._refresh_custom_metadata_table()

    def _metadata_form_has_changes(self, form_data):
        original = self.original_metadata or {}

        for field in self._metadata_edit_widgets():
            if (form_data.get(field) or "") != (original.get(field) or ""):
                return True

        return False

    def _custom_metadata_has_changes(self):
        return dict(getattr(self, "custom_metadata_tags", {}) or {}) != dict(
            getattr(self, "original_custom_metadata_tags", {}) or {}
        )

    def _refresh_metadata_dirty_state(self, log_on_dirty=False):
        if not self.current_audio_path or not hasattr(self, "metadata_title_value"):
            return False

        form_data = self._get_metadata_form_data()
        self.metadata_form_dirty = self._metadata_form_has_changes(form_data)
        self.custom_metadata_dirty = self._custom_metadata_has_changes()
        dirty = bool(self.metadata_form_dirty or self.custom_metadata_dirty)
        was_dirty = bool(self.metadata_dirty)
        self.metadata_dirty = dirty

        if dirty:
            if log_on_dirty and not was_dirty:
                self._log("检测到音频信息修改")

            self.metadata_status_value.setText("有未导出修改")
            self._mark_workspace_metadata_dirty()
        else:
            status = "编辑中" if self.is_metadata_editing else ("已读取" if self.current_audio_metadata else "未读取")
            self.metadata_status_value.setText(status)
            self._clear_workspace_dirty_flag("metadata")

        self.update_editor_status_panel()
        return dirty

    def _refresh_custom_metadata_table(self):
        if not hasattr(self, "custom_metadata_tree"):
            return

        self.custom_metadata_tree.clear()

        for key in sorted(self.custom_metadata_tags, key=str.lower):
            value = self.custom_metadata_tags.get(key, "")
            display_value = self._compact_metadata_value(value)
            item = QTreeWidgetItem([key, display_value])
            item.setData(0, Qt.ItemDataRole.UserRole, key)
            item.setToolTip(0, key)
            item.setToolTip(1, str(value))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.custom_metadata_tree.addTopLevelItem(item)

    def add_custom_metadata_tag(self):
        name = self.custom_metadata_name_edit.text().strip() if hasattr(self, "custom_metadata_name_edit") else ""
        value = self.custom_metadata_value_edit.text() if hasattr(self, "custom_metadata_value_edit") else ""

        if not name:
            QMessageBox.information(self, "标签名为空", "请输入自定义标签名。")
            return False

        normalized_name = name.lower()

        if self._is_reserved_metadata_tag(normalized_name):
            QMessageBox.information(self, "标签已存在", "该标签已存在，请直接修改对应字段。")
            return False

        if not value.strip():
            confirm = QMessageBox.question(
                self,
                "标签值为空",
                "当前标签值为空，是否仍然添加？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if confirm != QMessageBox.StandardButton.Yes:
                return False

        self.custom_metadata_tags[name] = value
        self._refresh_metadata_dirty_state(log_on_dirty=True)
        self._refresh_custom_metadata_table()
        self._log(f"用户添加自定义标签: {name}")
        self.custom_metadata_name_edit.clear()
        self.custom_metadata_value_edit.clear()
        return True

    def remove_selected_custom_metadata_tag(self):
        if not hasattr(self, "custom_metadata_tree"):
            return False

        selected_items = self.custom_metadata_tree.selectedItems()

        if not selected_items:
            QMessageBox.information(self, "未选择标签", "请先选择一个自定义标签。")
            return False

        tag_name = selected_items[0].data(0, Qt.ItemDataRole.UserRole)

        if not tag_name or tag_name not in self.custom_metadata_tags:
            return False

        del self.custom_metadata_tags[tag_name]
        self._refresh_metadata_dirty_state(log_on_dirty=True)
        self._refresh_custom_metadata_table()
        self._log(f"用户移除自定义标签: {tag_name}")
        return True

    def _is_reserved_metadata_tag(self, tag_name):
        reserved = {
            "title",
            "artist",
            "album",
            "albumartist",
            "album_artist",
            "date",
            "year",
            "genre",
            "track",
            "tracknumber",
            "disc",
            "discnumber",
            "bpm",
            "key",
            "initialkey",
            "comment",
            "description",
            "cover",
            "picture",
            "artwork",
            "apic",
            "covr",
            "metadata_block_picture",
            "lyrics",
            "unsyncedlyrics",
            "syncedlyrics",
        }
        return str(tag_name or "").strip().lower() in reserved

    def _extract_extended_metadata_tags(self, metadata):
        reserved = {
            "success",
            "path",
            "filename",
            "format",
            "extension",
            "container_format",
            "title",
            "artist",
            "album",
            "albumartist",
            "date",
            "genre",
            "tracknumber",
            "discnumber",
            "bpm",
            "initialkey",
            "comment",
            "duration",
            "sample_rate",
            "bitrate",
            "channels",
            "bits_per_sample",
            "codec",
            "file_size",
            "modified_time",
            "cover_data",
            "cover_mime",
            "cover_source",
            "error",
        }
        tags = {}

        for key, value in (metadata or {}).items():
            if key in reserved or value in (None, "", "-", [], {}):
                continue

            if isinstance(value, (bytes, bytearray)):
                continue

            tags[str(key)] = self._metadata_form_text(value)

        return tags

    def _compact_metadata_value(self, value, limit=180):
        text = self._metadata_form_text(value)

        if len(text) <= limit:
            return text

        return f"{text[:limit - 1]}..."

    def _format_metadata_codec_summary(self, metadata):
        container = self._metadata_form_text(
            metadata.get("container_format") or metadata.get("format")
        )
        codec = self._metadata_form_text(metadata.get("codec"))

        if not container and not codec:
            return "-"

        if not codec or codec.lower() == container.lower():
            return container or codec

        if not container:
            return codec

        return f"{container} / {codec}"

    def refresh_lyrics_edit_state_hint(self):
        if not hasattr(self, "lyrics_edit_state_pill"):
            return

        if self.is_lyrics_editing:
            text = "编辑中"
            tone = "processing"
            tip = "歌词正文当前可编辑，完成编辑不会自动保存或写入音频"
        elif self.lyrics_dirty:
            text = "有未保存修改"
            tone = "unsaved"
            tip = "当前歌词已修改，需另存、保存到原 .lrc 或写入音频"
        else:
            text = "只读"
            tone = "neutral"
            tip = "双击歌词正文或右键菜单可进入编辑"

        self.lyrics_edit_state_pill.setText(text)
        self.lyrics_edit_state_pill.set_tone(tone)
        self.lyrics_edit_state_pill.setToolTip(tip)
        self.lyrics_edit_state_pill.setStatusTip(tip)

    def update_editor_status_panel(self):
        self._sync_public_player_state()
        self.file_load_status_value.setText(self.file_load_status or "-")
        self.playback_status_value.setText(self.playback_status or "-")
        self.lyrics_status_value.setText(self.lyrics_status or "-")
        self.error_status_value.setText(self.error_text or "-")
        self.error_status_value.setToolTip(self.error_text or "")
        self.refresh_lyrics_edit_state_hint()
        self.refresh_editor_header()
        self.refresh_player_bar_state()
        self.refresh_editor_status_summary()

    def _update_time_label(self, position):
        self.time_label.setText(
            f"{format_duration(position)} / {format_duration(self.duration_ms)}"
        )

    def _playback_status_text(self):
        state = self.player.playbackState()

        if state == QMediaPlayer.PlaybackState.PlayingState:
            return "播放中"

        if state == QMediaPlayer.PlaybackState.PausedState:
            return "已暂停"

        return "已停止"

    def _show_import_message(self, message):
        QMessageBox.information(self, "无法导入", message)

    def _log(self, message):
        if self.log_callback is not None:
            self.log_callback(message)

    def _make_value_label(self):
        label = QLabel("-")
        label.setObjectName("DetailValue")
        label.setWordWrap(True)
        label.setMinimumWidth(0)
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        return label
    def _make_metadata_edit(self):
        edit = QLineEdit("")
        edit.setObjectName("MetadataEdit")
        edit.setReadOnly(True)
        edit.setMinimumWidth(0)
        edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        edit.textChanged.connect(self._on_metadata_field_changed)
        return edit

    def _make_readonly_metadata_edit(self):
        edit = QLineEdit("")
        edit.setObjectName("MetadataEdit")
        edit.setReadOnly(True)
        edit.setMinimumWidth(0)
        edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return edit

    def _make_metadata_comment_box(self):
        edit = MetadataCommentBox()
        edit.setObjectName("MetadataEdit")
        edit.setReadOnly(True)
        edit.setMinimumWidth(0)
        edit.setMaximumHeight(78)
        edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        edit.textChanged.connect(self._on_metadata_field_changed)
        return edit

    def _make_detail_label(self, text):
        label = QLabel(text)
        label.setObjectName("DetailLabel")
        return label
