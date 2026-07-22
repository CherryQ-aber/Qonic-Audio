from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtCore import QEvent, QObject, Property, QTimer, Signal, Slot, Qt
from PySide6.QtGui import QCloseEvent, QIcon, QWindow
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from ui_next.bridge.windows_native_window import (
    NativeHitTestRegions,
    WindowsNativeWindowFilter,
)


class WindowController(QObject):
    """Owns QML window chrome, tray behavior, and the unified close path."""

    stateChanged = Signal()
    nativeControlStateChanged = Signal()
    trayAvailabilityChanged = Signal()
    initialShowReadyChanged = Signal()
    settingsRequested = Signal()

    def __init__(
        self,
        application: QApplication,
        *,
        icon_path: str | Path | None = None,
        smoke_test: bool = False,
        tray_enabled: bool = True,
    ) -> None:
        super().__init__()
        self._application = application
        self._icon_path = Path(icon_path).resolve() if icon_path else None
        self._smoke_test = bool(smoke_test)
        self._tray_enabled = bool(tray_enabled and not smoke_test)
        self._window: QWindow | None = None
        self._quitting = False
        self._tray_available = False
        self._tray_notice_shown = False
        self._tray_icon: QSystemTrayIcon | None = None
        self._tray_menu: QMenu | None = None
        self._maximized = False
        self._active = False
        self._native_hover_control = ""
        self._native_pressed_control = ""
        platform_name = application.platformName().lower()
        self._frameless_enabled = sys.platform == "win32" and platform_name == "windows"
        self._initial_show_ready = not self._frameless_enabled
        self._regions = NativeHitTestRegions(resize_border=7.0)
        self._native_filter = WindowsNativeWindowFilter(
            self._regions,
            self._set_native_control_state,
            self._handle_native_control_action,
        )

    @Property(bool, constant=True)
    def framelessEnabled(self) -> bool:
        return self._frameless_enabled

    @Property(bool, notify=initialShowReadyChanged)
    def deferInitialShow(self) -> bool:
        return self._frameless_enabled and not self._initial_show_ready

    @Property(bool, notify=stateChanged)
    def maximized(self) -> bool:
        return self._maximized

    @Property(bool, notify=stateChanged)
    def active(self) -> bool:
        return self._active

    @Property(bool, notify=trayAvailabilityChanged)
    def trayAvailable(self) -> bool:
        return self._tray_available

    @Property(str, notify=nativeControlStateChanged)
    def nativeHoverControl(self) -> str:
        return self._native_hover_control

    @Property(str, notify=nativeControlStateChanged)
    def nativePressedControl(self) -> str:
        return self._native_pressed_control

    def attach_window(self, window: QWindow) -> None:
        if self._window is window:
            return
        if self._window is not None:
            self._window.removeEventFilter(self)
        self._window = window
        window.installEventFilter(self)
        window.windowStateChanged.connect(self._sync_window_state)
        window.activeChanged.connect(self._sync_window_state)
        if self._frameless_enabled:
            self._application.installNativeEventFilter(self._native_filter)
            self._native_filter.attach_window(window)
        if not self._initial_show_ready:
            self._initial_show_ready = True
            self.initialShowReadyChanged.emit()
        self._create_tray()
        self._sync_window_state()

    @Slot()
    def showInitialWindow(self) -> None:
        if self._window is not None:
            self._window.show()
            self._window.requestActivate()

    @Slot()
    def minimize(self) -> None:
        if self._window is not None:
            self._window.showMinimized()

    @Slot()
    def toggleMaximized(self) -> None:
        if self._window is None:
            return
        if self._window.windowStates() & Qt.WindowState.WindowMaximized:
            self._window.showNormal()
        else:
            self._window.showMaximized()

    @Slot()
    def closeWindow(self) -> None:
        if self._window is not None:
            self._window.close()

    @Slot(result=bool)
    def startSystemMove(self) -> bool:
        if self._window is None:
            return False
        return bool(self._window.startSystemMove())

    @Slot(int, result=bool)
    def startSystemResize(self, edges: int) -> bool:
        if self._window is None or self._maximized:
            return False
        return bool(self._window.startSystemResize(Qt.Edge(edges)))

    @Slot("QVariantList")
    def setCaptionRects(self, rects) -> None:
        self._regions.set_caption_rects(rects or ())

    @Slot("QVariantList")
    def setInteractiveRects(self, rects) -> None:
        self._regions.set_interactive_rects(rects or ())

    @Slot(str, float, float, float, float)
    def setControlRect(
        self,
        name: str,
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        self._regions.set_control_rect(name, x, y, width, height)

    @Slot()
    def showWindow(self) -> None:
        if self._window is None:
            return
        if self._maximized:
            self._window.showMaximized()
        else:
            self._window.showNormal()
        self._window.raise_()
        self._window.requestActivate()

    @Slot()
    def quitApplication(self) -> None:
        self._quitting = True
        if self._tray_icon is not None:
            self._tray_icon.hide()
        self._application.quit()

    @Slot()
    def shutdown(self) -> None:
        self._quitting = True
        if self._tray_icon is not None:
            self._tray_icon.hide()
        if self._window is not None:
            self._window.removeEventFilter(self)
        if self._frameless_enabled:
            self._application.removeNativeEventFilter(self._native_filter)
            self._native_filter.detach_window()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is not self._window:
            return False
        if event.type() == QEvent.Type.Close:
            if self._quitting or self._smoke_test or not self._tray_available:
                return False
            close_event = event if isinstance(event, QCloseEvent) else None
            if close_event is not None:
                close_event.ignore()
            self._window.hide()
            self._show_background_notice()
            return True
        if event.type() in (
            QEvent.Type.WindowStateChange,
            QEvent.Type.ActivationChange,
            QEvent.Type.Show,
            QEvent.Type.Hide,
        ):
            self._sync_window_state()
        if event.type() in (
            QEvent.Type.WinIdChange,
            QEvent.Type.DevicePixelRatioChange,
        ) and self._frameless_enabled:
            self._native_filter.attach_window(self._window)
        return False

    def _create_tray(self) -> None:
        if (
            not self._tray_enabled
            or self._tray_icon is not None
            or not QSystemTrayIcon.isSystemTrayAvailable()
        ):
            self._set_tray_available(False)
            return

        icon = self._window.icon() if self._window is not None else QIcon()
        if (icon is None or icon.isNull()) and self._icon_path is not None:
            icon = QIcon(str(self._icon_path))

        tray = QSystemTrayIcon(icon, self)
        tray.setToolTip(self._application.applicationName())
        menu = QMenu()
        show_action = menu.addAction("显示窗口")
        settings_action = menu.addAction("打开设置")
        menu.addSeparator()
        quit_action = menu.addAction("退出程序")
        show_action.triggered.connect(self.showWindow)
        settings_action.triggered.connect(self._open_settings_from_tray)
        quit_action.triggered.connect(self.quitApplication)
        tray.setContextMenu(menu)
        tray.activated.connect(self._on_tray_activated)
        tray.show()

        self._tray_icon = tray
        self._tray_menu = menu
        self._application.setQuitOnLastWindowClosed(False)
        self._set_tray_available(True)

    def _open_settings_from_tray(self) -> None:
        self.showWindow()
        self.settingsRequested.emit()

    def _on_tray_activated(self, reason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.DoubleClick,
            QSystemTrayIcon.ActivationReason.Trigger,
        ):
            self.showWindow()

    def _show_background_notice(self) -> None:
        if self._tray_icon is None or self._tray_notice_shown:
            return
        self._tray_notice_shown = True
        self._tray_icon.showMessage(
            self._application.applicationName(),
            "程序仍在后台运行；请使用托盘菜单中的“退出程序”彻底退出。",
            QSystemTrayIcon.MessageIcon.Information,
            2400,
        )

    def _sync_window_state(self, *_args) -> None:
        if self._window is None:
            return
        maximized = bool(
            self._window.windowStates() & Qt.WindowState.WindowMaximized
        )
        active = bool(self._window.isActive())
        if maximized == self._maximized and active == self._active:
            return
        self._maximized = maximized
        self._active = active
        self.stateChanged.emit()

    def _set_native_control_state(self, hovered: str, pressed: str) -> None:
        if (
            hovered == self._native_hover_control
            and pressed == self._native_pressed_control
        ):
            return
        self._native_hover_control = hovered
        self._native_pressed_control = pressed
        self.nativeControlStateChanged.emit()

    def _handle_native_control_action(self, control: str) -> None:
        action = {
            "minimize": self.minimize,
            "maximize": self.toggleMaximized,
            "close": self.closeWindow,
        }.get(control)
        if action is not None:
            def perform_action() -> None:
                action()
                self._set_native_control_state(control, "")

            QTimer.singleShot(0, perform_action)

    def _set_tray_available(self, available: bool) -> None:
        available = bool(available)
        if available == self._tray_available:
            return
        self._tray_available = available
        self.trayAvailabilityChanged.emit()


__all__ = ["WindowController"]
