import sys

from config import get_theme_mode as get_config_theme_mode

LIGHT_QSS = """
QWidget {
    background: #F3F6FA;
    color: #0F172A;
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
    font-size: 13px;
}

QFrame {
    border-radius: 0px;
}

QMainWindow,
#AppShell,
QStackedWidget {
    background: #F3F6FA;
}

#TopStatusBar,
#LogPanel,
#SettingsPane,
#QueueActionsPane,
#DashboardActionPane,
#SelectionPanel {
    background: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
}

#SelectionDetailPane,
#PlayerControlBar {
    background: #F8FAFC;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
}

#NavBar {
    background: #111827;
    border: 1px solid #0B1120;
    border-radius: 0px;
}

#NavTitle {
    background: transparent;
    color: #FFFFFF;
    font-size: 15px;
    font-weight: 700;
    padding: 2px 0 10px 0;
    border-bottom: 1px solid #334155;
}

QLabel {
    background: transparent;
}

QGroupBox {
    background: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    margin-top: 14px;
    padding: 14px 10px 10px 10px;
    font-weight: 700;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 6px;
    color: #0F172A;
    background: #F3F6FA;
}

QPushButton {
    background: #F8FAFC;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 7px 12px;
}

QPushButton:hover {
    background: #E8EEF7;
    border-color: #94A3B8;
}

QPushButton:pressed {
    background: #DBEAFE;
    border-color: #2563EB;
}

QPushButton:disabled {
    color: #94A3B8;
    background: #EEF2F7;
    border-color: #CBD5E1;
}

QPushButton[compact="true"] {
    padding: 4px 8px;
    min-height: 22px;
}

QPushButton[nav="true"] {
    color: #CBD5E1;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 0px;
    padding: 9px 10px;
    text-align: left;
}

QPushButton[nav="true"]:hover {
    color: #FFFFFF;
    background: #1E293B;
    border-color: #334155;
}

QPushButton[nav="true"][active="true"] {
    color: #FFFFFF;
    background: #2563EB;
    border-color: #3B82F6;
}

QComboBox,
QLineEdit {
    background: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 5px 8px;
    min-height: 24px;
}

QComboBox {
    padding-right: 28px;
}

QComboBox:hover,
QComboBox:focus,
QComboBox:on,
QLineEdit:hover,
QLineEdit:focus {
    border-color: #2563EB;
    background: #FFFFFF;
}

QComboBox:disabled,
QLineEdit:disabled {
    background: #EEF2F7;
    color: #94A3B8;
    border-color: #CBD5E1;
}

QLineEdit[readOnly="true"] {
    background: #F8FAFC;
    color: #334155;
    border-color: #CBD5E1;
}

QComboBox::drop-down {
    border: 0;
    border-radius: 0px;
    width: 24px;
}

QComboBox::down-arrow {
    width: 0px;
    height: 0px;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #475569;
    margin-right: 8px;
}

QComboBox QAbstractItemView {
    background: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 0px;
    selection-background-color: #DBEAFE;
    selection-color: #0F172A;
}

QComboBox QAbstractItemView::item {
    background: transparent;
    border-radius: 0px;
    min-height: 28px;
    padding: 6px 12px;
}

QComboBox QAbstractItemView::item:hover {
    background: #EAF2FF;
    color: #0F172A;
    border-radius: 0px;
}

QComboBox QAbstractItemView::item:selected {
    background: #DBEAFE;
    color: #0F172A;
    border-radius: 0px;
}

QComboBox QAbstractItemView::item:disabled {
    color: #6B7280;
    background: transparent;
}

QComboBox#HardEdgeComboBox {
    border-radius: 0px;
}

QComboBox#HardEdgeComboBox::drop-down {
    border: 0;
    border-radius: 0px;
}

QAbstractItemView {
    border-radius: 0px;
    outline: 0;
}

QListView {
    border-radius: 0px;
    outline: 0;
}

QListView::item {
    border-radius: 0px;
    padding: 5px 8px;
}

QListView#HardEdgeComboPopup {
    background: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 0px;
    outline: 0;
}

QListView#HardEdgeComboPopup::item {
    border-radius: 0px;
    padding: 5px 8px;
}

QListView#HardEdgeComboPopup::item:hover {
    background: #EFF6FF;
    color: #0F172A;
    border-radius: 0px;
}

QListView#HardEdgeComboPopup::item:selected {
    background: #DBEAFE;
    color: #0F172A;
    border-radius: 0px;
}

QMenu {
    background: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 0px;
}

QMenu::item {
    background: transparent;
    border-radius: 0px;
    min-height: 28px;
    padding: 6px 18px;
}

QMenu::item:selected {
    background: #EAF2FF;
    color: #0F172A;
}

QMenu::separator {
    height: 1px;
    background: #CBD5E1;
    margin: 4px 8px;
}

QMenu::item:disabled {
    color: #6B7280;
    background-color: transparent;
}

QMenu::item:disabled:selected {
    color: #6B7280;
    background-color: transparent;
}

QToolTip {
    background: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 0px;
    padding: 4px 6px;
}

QCheckBox {
    spacing: 8px;
    background: transparent;
}

QSplitter::handle {
    background: #CBD5E1;
}

QTabWidget::pane {
    background: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    top: -1px;
}

QTabBar::tab {
    background: #EEF2F7;
    color: #334155;
    border: 1px solid #CBD5E1;
    border-bottom-color: #CBD5E1;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 7px 14px;
    margin-right: 4px;
    font-weight: 600;
}

QTabBar::tab:hover {
    background: #E8EEF7;
    color: #0F172A;
}

QTabBar::tab:selected {
    background: #FFFFFF;
    color: #0F172A;
    border-top: 2px solid #2563EB;
    border-bottom-color: #FFFFFF;
}

QTabBar::tab:disabled {
    background: #EEF2F7;
    color: #94A3B8;
    border-color: #CBD5E1;
}

QScrollArea,
QScrollArea > QWidget,
QScrollArea > QWidget > QWidget {
    background: transparent;
    border: 0;
}

QScrollBar:vertical {
    background: #EEF2F7;
    width: 10px;
    margin: 0;
    border: 0;
}

QScrollBar::handle:vertical {
    background: #CBD5E1;
    min-height: 28px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #94A3B8;
}

QScrollBar:horizontal {
    background: #EEF2F7;
    height: 10px;
    margin: 0;
    border: 0;
}

QScrollBar::handle:horizontal {
    background: #CBD5E1;
    min-width: 28px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal:hover {
    background: #94A3B8;
}

QScrollBar::add-line,
QScrollBar::sub-line,
QScrollBar::add-page,
QScrollBar::sub-page {
    background: transparent;
    border: 0;
}

QSlider::groove:horizontal {
    background: #CBD5E1;
    height: 6px;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: #2563EB;
    border-radius: 3px;
}

QSlider::add-page:horizontal {
    background: #E2E8F0;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #FFFFFF;
    border: 2px solid #2563EB;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}

QSlider::handle:horizontal:hover {
    background: #DBEAFE;
    border-color: #1D4ED8;
}

QSlider::groove:horizontal:disabled,
QSlider::add-page:horizontal:disabled,
QSlider::sub-page:horizontal:disabled,
QSlider[previewUnavailable="true"]::groove:horizontal,
QSlider[previewUnavailable="true"]::add-page:horizontal,
QSlider[previewUnavailable="true"]::sub-page:horizontal {
    background: #E2E8F0;
}

QSlider::handle:horizontal:disabled,
QSlider[previewUnavailable="true"]::handle:horizontal {
    background: #F8FAFC;
    border-color: #94A3B8;
}

QTableWidget {
    background: #FFFFFF;
    alternate-background-color: #F8FAFC;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 0px;
    gridline-color: #E2E8F0;
    selection-background-color: #EAF2FF;
}

QTableWidget::item {
    padding: 3px 4px;
}

QTableWidget::item:selected {
    background: #EAF2FF;
    border-left: 3px solid #2563EB;
}

QTableWidget::item:focus {
    border: 0;
    outline: none;
}

QHeaderView::section {
    background: #FFFFFF;
    color: #475569;
    border: 0;
    border-right: 1px solid #CBD5E1;
    border-bottom: 1px solid #CBD5E1;
    padding: 3px 6px;
    min-height: 26px;
    max-height: 30px;
    font-weight: 700;
}

QTextEdit,
QPlainTextEdit {
    background: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 8px;
    font-family: "Consolas", "Microsoft YaHei UI", monospace;
    selection-background-color: #DBEAFE;
    selection-color: #0F172A;
}

QTextEdit:focus,
QPlainTextEdit:focus {
    border-color: #2563EB;
    background: #FFFFFF;
}

QTextEdit:read-only,
QPlainTextEdit:read-only {
    background: #F8FAFC;
    color: #0F172A;
}

#PageTitle {
    font-size: 20px;
    font-weight: 700;
    color: #0F172A;
}

#SectionTitle {
    font-size: 15px;
    font-weight: 700;
    color: #0F172A;
}

#PathLabel,
#MutedLabel,
#StatusCardSubtitle {
    color: #475569;
}

#StatusCard {
    background: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
}

#StatusCardTitle {
    color: #64748B;
    font-size: 12px;
    font-weight: 600;
}

#StatusCardValue {
    color: #0F172A;
    font-size: 20px;
    font-weight: 700;
}

#SelectionDetailPane {
    background: #F8FAFC;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
}

#DetailLabel {
    color: #334155;
    font-weight: 700;
}

#DetailValue {
    color: #0F172A;
}

#DetailPathField {
    background: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 4px 6px;
}

#StatusPill {
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 2px 6px;
}

#StatusPill[tone="neutral"] {
    background: #F8FAFC;
    color: #334155;
    border-color: #CBD5E1;
}

#StatusPill[tone="success"] {
    background: #DCFCE7;
    color: #166534;
    border-color: #86EFAC;
}

#StatusPill[tone="warning"],
#StatusPill[tone="unsaved"] {
    background: #FEF3C7;
    color: #92400E;
    border-color: #FCD34D;
}

#StatusPill[tone="processing"] {
    background: #DBEAFE;
    color: #1D4ED8;
    border-color: #93C5FD;
}

#StatusPill[tone="error"] {
    background: #FEE2E2;
    color: #B91C1C;
    border-color: #FCA5A5;
}

#CoverPreview {
    background: #F8FAFC;
    color: #64748B;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    font-weight: 600;
}

#MetadataEdit {
    background: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 5px 8px;
}

#MetadataEdit:focus {
    border-color: #2563EB;
}

#MetadataEdit[readOnly="true"] {
    background: #F8FAFC;
    color: #334155;
}

#AudioEditorWorkspaceTabs::pane,
#WorkspaceTabs::pane {
    background: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
}

#AudioEditorWorkspaceTabs QTabBar::tab:selected,
#WorkspaceTabs QTabBar::tab:selected {
    background: #FFFFFF;
    color: #0F172A;
    border-top: 2px solid #2563EB;
}
"""

DARK_QSS = """
QWidget {
    background: #0F172A;
    color: #E5E7EB;
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
    font-size: 13px;
}

QFrame {
    border-radius: 0px;
}

QMainWindow,
#AppShell,
QStackedWidget {
    background: #0F172A;
}

#TopStatusBar,
#LogPanel,
#SettingsPane,
#QueueActionsPane,
#DashboardActionPane,
#SelectionPanel {
    background: #111827;
    border: 1px solid #334155;
    border-radius: 0px;
}

#NavBar {
    background: #020617;
    border: 1px solid #1E293B;
    border-radius: 0px;
}

#NavTitle {
    background: transparent;
    color: #F8FAFC;
    font-size: 15px;
    font-weight: 700;
    padding: 2px 0 10px 0;
    border-bottom: 1px solid #334155;
}

QLabel {
    background: transparent;
}

QGroupBox {
    background: #111827;
    color: #E5E7EB;
    border: 1px solid #334155;
    border-radius: 6px;
    margin-top: 14px;
    padding: 14px 10px 10px 10px;
    font-weight: 700;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 6px;
    color: #F8FAFC;
    background: #0F172A;
}

QPushButton {
    background: #1E293B;
    color: #E5E7EB;
    border: 1px solid #334155;
    border-radius: 0px;
    padding: 7px 12px;
}

QPushButton:hover {
    background: #25344A;
    border-color: #3B82F6;
}

QPushButton:pressed {
    background: #1D4ED8;
    border-color: #60A5FA;
}

QPushButton:disabled {
    color: #64748B;
    background: #111827;
    border-color: #1E293B;
}

QPushButton[compact="true"] {
    padding: 4px 8px;
    min-height: 22px;
}

QPushButton[nav="true"] {
    color: #94A3B8;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 0px;
    padding: 9px 10px;
    text-align: left;
}

QPushButton[nav="true"]:hover {
    color: #E5E7EB;
    background: #111827;
    border-color: #334155;
}

QPushButton[nav="true"][active="true"] {
    color: #FFFFFF;
    background: #2563EB;
    border-color: #60A5FA;
}

QComboBox,
QLineEdit {
    background: #111827;
    color: #E5E7EB;
    border: 1px solid #334155;
    border-radius: 0px;
    padding: 5px 8px;
    min-height: 24px;
}

QComboBox {
    padding-right: 28px;
}

QComboBox:hover,
QComboBox:focus,
QComboBox:on,
QLineEdit:hover {
    border-color: #3B82F6;
}

QComboBox::drop-down {
    border: 0;
    border-radius: 0px;
    width: 24px;
}

QComboBox::down-arrow {
    width: 0px;
    height: 0px;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #CBD5E1;
    margin-right: 8px;
}

QComboBox QAbstractItemView {
    background: #111827;
    color: #E5E7EB;
    border: 1px solid #334155;
    border-radius: 0px;
    selection-background-color: #1D4ED8;
    selection-color: #FFFFFF;
}

QComboBox QAbstractItemView::item {
    background: transparent;
    border-radius: 0px;
    min-height: 28px;
    padding: 6px 12px;
}

QComboBox QAbstractItemView::item:hover {
    background: #1E293B;
    color: #FFFFFF;
    border-radius: 0px;
}

QComboBox QAbstractItemView::item:selected {
    background: #26364D;
    color: #FFFFFF;
    border-radius: 0px;
}

QComboBox QAbstractItemView::item:disabled {
    color: #6B7280;
    background: transparent;
}

QComboBox#HardEdgeComboBox {
    border-radius: 0px;
}

QComboBox#HardEdgeComboBox::drop-down {
    border: 0;
    border-radius: 0px;
}

QAbstractItemView {
    border-radius: 0px;
    outline: 0;
}

QListView {
    border-radius: 0px;
    outline: 0;
}

QListView::item {
    border-radius: 0px;
    padding: 5px 8px;
}

QListView#HardEdgeComboPopup {
    background: #111827;
    color: #E5E7EB;
    border: 1px solid #334155;
    border-radius: 0px;
    outline: 0;
}

QListView#HardEdgeComboPopup::item {
    border-radius: 0px;
    padding: 5px 8px;
}

QListView#HardEdgeComboPopup::item:hover {
    background: #25344A;
    color: #E5E7EB;
    border-radius: 0px;
}

QListView#HardEdgeComboPopup::item:selected {
    background: #1D4ED8;
    color: #FFFFFF;
    border-radius: 0px;
}

QMenu {
    background: #111827;
    color: #E5E7EB;
    border: 1px solid #334155;
    border-radius: 0px;
}

QMenu::item {
    background: transparent;
    border-radius: 0px;
    min-height: 28px;
    padding: 6px 18px;
}

QMenu::item:selected {
    background: #1E293B;
    color: #FFFFFF;
}

QMenu::separator {
    height: 1px;
    background: #334155;
    margin: 4px 8px;
}

QMenu::item:disabled {
    color: #6B7280;
    background-color: transparent;
}

QMenu::item:disabled:selected {
    color: #6B7280;
    background-color: transparent;
}

QToolTip {
    background: #111827;
    color: #E5E7EB;
    border: 1px solid #334155;
    border-radius: 0px;
    padding: 4px 6px;
}

QCheckBox {
    spacing: 8px;
    background: transparent;
}

QSplitter::handle {
    background: #334155;
}

QScrollArea,
QScrollArea > QWidget,
QScrollArea > QWidget > QWidget {
    background: transparent;
    border: 0;
}

QSlider::groove:horizontal {
    background: #334155;
    height: 6px;
    border-radius: 0px;
}

QSlider::sub-page:horizontal {
    background: #3B82F6;
    border-radius: 0px;
}

QSlider::add-page:horizontal {
    background: #1E293B;
    border-radius: 0px;
}

QSlider::handle:horizontal {
    background: #E5E7EB;
    border: 2px solid #60A5FA;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 0px;
}

QSlider::handle:horizontal:hover {
    background: #FFFFFF;
    border-color: #93C5FD;
}

QSlider::groove:horizontal:disabled,
QSlider::add-page:horizontal:disabled,
QSlider::sub-page:horizontal:disabled,
QSlider[previewUnavailable="true"]::groove:horizontal,
QSlider[previewUnavailable="true"]::add-page:horizontal,
QSlider[previewUnavailable="true"]::sub-page:horizontal {
    background: #1E293B;
}

QSlider::handle:horizontal:disabled,
QSlider[previewUnavailable="true"]::handle:horizontal {
    background: #111827;
    border-color: #475569;
}

QTableWidget {
    background: #111827;
    alternate-background-color: #172033;
    color: #E5E7EB;
    border: 1px solid #334155;
    border-radius: 0px;
    gridline-color: #334155;
    selection-background-color: #1E293B;
}

QTableWidget::item {
    padding: 3px 4px;
}

QTableWidget::item:selected {
    background: #1E293B;
    border-left: 3px solid #3B82F6;
}

QTableWidget::item:focus {
    border: 0;
    outline: none;
}

QHeaderView::section {
    background: #1E293B;
    color: #CBD5E1;
    border: 0;
    border-right: 1px solid #334155;
    border-bottom: 1px solid #334155;
    padding: 3px 6px;
    min-height: 26px;
    max-height: 30px;
    font-weight: 700;
}

QTextEdit {
    background: #020617;
    color: #E5E7EB;
    border: 1px solid #334155;
    border-radius: 0px;
    padding: 8px;
    font-family: "Consolas", "Microsoft YaHei UI", monospace;
}

#PageTitle {
    font-size: 20px;
    font-weight: 700;
    color: #F8FAFC;
}

#SectionTitle {
    font-size: 15px;
    font-weight: 700;
    color: #E5E7EB;
}

#PathLabel,
#MutedLabel,
#StatusCardSubtitle {
    color: #94A3B8;
}

#StatusCard {
    background: #111827;
    border: 1px solid #334155;
    border-radius: 0px;
}

#StatusCardTitle {
    color: #94A3B8;
    font-size: 12px;
}

#StatusCardValue {
    color: #F8FAFC;
    font-size: 19px;
    font-weight: 700;
}

#SelectionDetailPane {
    background: transparent;
    border: 0;
}

#DetailLabel {
    color: #94A3B8;
    font-weight: 700;
}

#DetailValue {
    color: #E5E7EB;
}

#DetailPathField {
    background: #0F172A;
    color: #E5E7EB;
    border: 1px solid #334155;
    border-radius: 0px;
    padding: 4px 6px;
}

#StatusPill {
    border: 1px solid #334155;
    border-radius: 0px;
    padding: 2px 6px;
}

#StatusPill[tone="neutral"] {
    background: #111827;
    color: #CBD5E1;
    border-color: #334155;
}

#StatusPill[tone="success"] {
    background: #052E16;
    color: #BBF7D0;
    border-color: #166534;
}

#StatusPill[tone="warning"],
#StatusPill[tone="unsaved"] {
    background: #451A03;
    color: #FDE68A;
    border-color: #92400E;
}

#StatusPill[tone="processing"] {
    background: #0B2447;
    color: #BFDBFE;
    border-color: #2563EB;
}

#StatusPill[tone="error"] {
    background: #450A0A;
    color: #FCA5A5;
    border-color: #991B1B;
}
"""


def get_theme_mode():
    return get_config_theme_mode()


def _read_windows_theme_mode():
    if sys.platform != "win32":
        return "light"

    try:
        import winreg

        key_path = (
            "Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize"
        )
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            apps_use_light_theme, _value_type = winreg.QueryValueEx(
                key,
                "AppsUseLightTheme",
            )
        return "light" if apps_use_light_theme else "dark"
    except Exception:
        return "light"


def resolve_theme_mode(mode=None):
    selected_mode = mode or get_theme_mode()

    if selected_mode not in ("light", "dark", "system"):
        selected_mode = "system"

    if selected_mode == "system":
        return _read_windows_theme_mode()

    return selected_mode


def apply_theme(app_or_widget, mode=None):
    resolved_mode = resolve_theme_mode(mode)
    stylesheet = DARK_QSS if resolved_mode == "dark" else LIGHT_QSS
    app_or_widget.setStyleSheet(stylesheet)
    app_or_widget.setProperty("theme_mode", mode or get_theme_mode())
    app_or_widget.setProperty("resolved_theme_mode", resolved_mode)
    return resolved_mode


def apply_app_theme(app_or_widget):
    return apply_theme(app_or_widget)
