from __future__ import annotations

from dataclasses import dataclass
import sys
from typing import Callable, Iterable, Mapping

from PySide6.QtCore import QAbstractNativeEventFilter, Qt


IS_WINDOWS = sys.platform == "win32"


# Win32 hit-test values. Keeping these here makes the geometry policy testable
# without importing ctypes on non-Windows platforms.
HTCLIENT = 1
HTCAPTION = 2
HTMINBUTTON = 8
HTLEFT = 10
HTRIGHT = 11
HTTOP = 12
HTTOPLEFT = 13
HTTOPRIGHT = 14
HTBOTTOM = 15
HTBOTTOMLEFT = 16
HTBOTTOMRIGHT = 17
HTMAXBUTTON = 9
HTCLOSE = 20


@dataclass(frozen=True)
class LogicalRect:
    x: float
    y: float
    width: float
    height: float

    def contains_physical(self, x: int, y: int, scale: float) -> bool:
        left = round(self.x * scale)
        top = round(self.y * scale)
        right = round((self.x + self.width) * scale)
        bottom = round((self.y + self.height) * scale)
        return left <= x < right and top <= y < bottom


class NativeHitTestRegions:
    """Stores QML geometry in logical pixels and resolves Win32 hit targets."""

    CONTROL_HITS = {
        "minimize": HTMINBUTTON,
        "maximize": HTMAXBUTTON,
        "close": HTCLOSE,
    }

    def __init__(self, resize_border: float = 7.0) -> None:
        self.resize_border = max(1.0, float(resize_border))
        self.caption_rects: tuple[LogicalRect, ...] = ()
        self.interactive_rects: tuple[LogicalRect, ...] = ()
        self.control_rects: dict[str, LogicalRect] = {}

    def set_caption_rects(self, rects: Iterable[Mapping[str, object]]) -> None:
        parsed: list[LogicalRect] = []
        for rect in rects:
            logical = self._parse_rect(rect)
            if logical is not None:
                parsed.append(logical)
        self.caption_rects = tuple(parsed)

    def set_interactive_rects(
        self,
        rects: Iterable[Mapping[str, object]],
    ) -> None:
        parsed: list[LogicalRect] = []
        for rect in rects:
            logical = self._parse_rect(rect)
            if logical is not None:
                parsed.append(logical)
        self.interactive_rects = tuple(parsed)

    def set_control_rect(
        self,
        name: str,
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        if name not in self.CONTROL_HITS:
            return
        rect = LogicalRect(float(x), float(y), float(width), float(height))
        if rect.width <= 0 or rect.height <= 0:
            self.control_rects.pop(name, None)
            return
        self.control_rects[name] = rect

    def hit_test(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        *,
        scale: float,
        maximized: bool,
    ) -> int:
        scale = max(0.25, float(scale))

        # Caption controls win over resize zones. QML leaves a narrow strip to
        # the right of the close button so the top-right resize corner remains.
        for name, hit in self.CONTROL_HITS.items():
            rect = self.control_rects.get(name)
            if rect is not None and rect.contains_physical(x, y, scale):
                return hit

        if not maximized:
            border = max(1, round(self.resize_border * scale))
            on_left = x < border
            on_right = x >= max(0, width - border)
            on_top = y < border
            on_bottom = y >= max(0, height - border)
            if on_top and on_left:
                return HTTOPLEFT
            if on_top and on_right:
                return HTTOPRIGHT
            if on_bottom and on_left:
                return HTBOTTOMLEFT
            if on_bottom and on_right:
                return HTBOTTOMRIGHT
            if on_left:
                return HTLEFT
            if on_right:
                return HTRIGHT
            if on_top:
                return HTTOP
            if on_bottom:
                return HTBOTTOM

        # The whole visual title bar is a caption except for actual QML
        # controls. Keep their hit target as client content so clicks and
        # keyboard focus still reach the QML item underneath.
        if any(
            rect.contains_physical(x, y, scale)
            for rect in self.interactive_rects
        ):
            return HTCLIENT

        if any(rect.contains_physical(x, y, scale) for rect in self.caption_rects):
            return HTCAPTION
        return HTCLIENT

    @staticmethod
    def _parse_rect(rect: Mapping[str, object]) -> LogicalRect | None:
        try:
            logical = LogicalRect(
                float(rect.get("x", 0.0)),
                float(rect.get("y", 0.0)),
                float(rect.get("width", 0.0)),
                float(rect.get("height", 0.0)),
            )
        except (TypeError, ValueError):
            return None
        if logical.width <= 0 or logical.height <= 0:
            return None
        return logical


if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    WM_GETMINMAXINFO = 0x0024
    WM_NCCALCSIZE = 0x0083
    WM_NCHITTEST = 0x0084
    WM_NCLBUTTONDOWN = 0x00A1
    WM_NCLBUTTONUP = 0x00A2
    WM_NCMOUSEMOVE = 0x00A0
    WM_NCMOUSELEAVE = 0x02A2
    WM_CAPTURECHANGED = 0x0215

    GWL_STYLE = -16
    WS_CAPTION = 0x00C00000
    WS_THICKFRAME = 0x00040000
    WS_MINIMIZEBOX = 0x00020000
    WS_MAXIMIZEBOX = 0x00010000
    WS_SYSMENU = 0x00080000

    MONITOR_DEFAULTTONEAREST = 2
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOZORDER = 0x0004
    SWP_NOACTIVATE = 0x0010
    SWP_FRAMECHANGED = 0x0020

    DWMWA_WINDOW_CORNER_PREFERENCE = 33
    DWMWCP_ROUND = 2
    SM_CXSIZEFRAME = 32
    SM_CYSIZEFRAME = 33
    SM_CXPADDEDBORDER = 92

    class MINMAXINFO(ctypes.Structure):
        _fields_ = [
            ("ptReserved", wintypes.POINT),
            ("ptMaxSize", wintypes.POINT),
            ("ptMaxPosition", wintypes.POINT),
            ("ptMinTrackSize", wintypes.POINT),
            ("ptMaxTrackSize", wintypes.POINT),
        ]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
        ]


class WindowsNativeWindowFilter(QAbstractNativeEventFilter):
    """Win32 non-client integration for the QML-owned top-level window."""

    def __init__(
        self,
        regions: NativeHitTestRegions,
        control_state_callback: Callable[[str, str], None] | None = None,
        control_action_callback: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__()
        self._regions = regions
        self._control_state_callback = control_state_callback
        self._control_action_callback = control_action_callback
        self._window = None
        self._hwnd = 0
        self._user32 = None
        self._dwmapi = None
        if IS_WINDOWS:
            self._load_win32()

    @property
    def available(self) -> bool:
        return bool(IS_WINDOWS and self._user32 is not None)

    def attach_window(self, window) -> bool:
        self._window = window
        if not self.available or window is None:
            return False
        self._hwnd = int(window.winId())
        if not self._hwnd:
            return False
        self.apply_native_frame()
        return True

    def detach_window(self) -> None:
        self._window = None
        self._hwnd = 0
        self._set_control_state("", "")

    def apply_native_frame(self) -> None:
        if not self.available or not self._hwnd:
            return
        style = self._user32.GetWindowLongPtrW(self._hwnd, GWL_STYLE)
        style |= (
            WS_CAPTION
            | WS_THICKFRAME
            | WS_MINIMIZEBOX
            | WS_MAXIMIZEBOX
            | WS_SYSMENU
        )
        self._user32.SetWindowLongPtrW(self._hwnd, GWL_STYLE, style)
        self._user32.SetWindowPos(
            self._hwnd,
            0,
            0,
            0,
            0,
            0,
            SWP_NOMOVE
            | SWP_NOSIZE
            | SWP_NOZORDER
            | SWP_NOACTIVATE
            | SWP_FRAMECHANGED,
        )
        self._apply_dwm_preferences()

    def nativeEventFilter(self, event_type, message):  # noqa: N802 - Qt API
        if not self.available or not self._hwnd:
            return False, 0
        try:
            msg = wintypes.MSG.from_address(int(message))
        except (TypeError, ValueError):
            return False, 0
        if int(msg.hWnd or 0) != self._hwnd:
            return False, 0

        if msg.message == WM_NCCALCSIZE and msg.wParam:
            # The standard resizable styles stay installed, but all visual
            # non-client space is handed to QML.
            self._apply_maximized_client_inset(msg.lParam)
            return True, 0

        if msg.message == WM_GETMINMAXINFO:
            self._apply_monitor_work_area(msg.lParam)
            # Let Qt continue so it can still impose QML minimum dimensions.
            return False, 0

        if msg.message == WM_NCHITTEST:
            hit = self._hit_test_message(msg.lParam)
            hover = self._control_name(hit)
            self._set_control_state(hover, self._pressed_control())
            return True, hit

        if msg.message == WM_NCMOUSEMOVE:
            self._set_control_state(
                self._control_name(int(msg.wParam)),
                self._pressed_control(),
            )
        elif msg.message == WM_NCLBUTTONDOWN:
            control = self._control_name(int(msg.wParam))
            self._set_control_state(control, control)
            if control and self._control_action_callback is not None:
                # Qt's frameless window keeps native hover/Snap behavior, but
                # DefWindowProc does not reliably dispatch the final command
                # for client-rendered caption buttons. Execute it explicitly.
                self._control_action_callback(control)
                return True, 0
        elif msg.message == WM_NCLBUTTONUP:
            control = self._control_name(int(msg.wParam))
            self._set_control_state(control, "")
            if control:
                return True, 0
        elif msg.message in (WM_NCMOUSELEAVE, WM_CAPTURECHANGED):
            self._set_control_state("", "")
        return False, 0

    def _hit_test_message(self, l_param: int) -> int:
        screen_x = ctypes.c_short(int(l_param) & 0xFFFF).value
        screen_y = ctypes.c_short((int(l_param) >> 16) & 0xFFFF).value
        rect = wintypes.RECT()
        if not self._user32.GetWindowRect(self._hwnd, ctypes.byref(rect)):
            return HTCLIENT
        local_x = screen_x - rect.left
        local_y = screen_y - rect.top
        width = max(0, rect.right - rect.left)
        height = max(0, rect.bottom - rect.top)
        return self._regions.hit_test(
            local_x,
            local_y,
            width,
            height,
            scale=self._dpi_scale(),
            maximized=self._qt_window_is_maximized()
            or bool(self._user32.IsZoomed(self._hwnd)),
        )

    def _dpi_scale(self) -> float:
        get_dpi = getattr(self._user32, "GetDpiForWindow", None)
        if get_dpi is not None:
            dpi = int(get_dpi(self._hwnd))
            if dpi > 0:
                return dpi / 96.0
        if self._window is not None:
            return max(0.25, float(self._window.devicePixelRatio()))
        return 1.0

    def _qt_window_is_maximized(self) -> bool:
        if self._window is None:
            return False
        return bool(
            self._window.windowStates() & Qt.WindowState.WindowMaximized
        )

    def _apply_monitor_work_area(self, l_param: int) -> None:
        if not l_param:
            return
        monitor = self._user32.MonitorFromWindow(
            self._hwnd,
            MONITOR_DEFAULTTONEAREST,
        )
        if not monitor:
            return
        monitor_info = MONITORINFO()
        monitor_info.cbSize = ctypes.sizeof(MONITORINFO)
        if not self._user32.GetMonitorInfoW(monitor, ctypes.byref(monitor_info)):
            return
        info = MINMAXINFO.from_address(int(l_param))
        monitor_rect = monitor_info.rcMonitor
        work_rect = monitor_info.rcWork
        info.ptMaxPosition.x = work_rect.left - monitor_rect.left
        info.ptMaxPosition.y = work_rect.top - monitor_rect.top
        info.ptMaxSize.x = work_rect.right - work_rect.left
        info.ptMaxSize.y = work_rect.bottom - work_rect.top
        info.ptMaxTrackSize.x = info.ptMaxSize.x
        info.ptMaxTrackSize.y = info.ptMaxSize.y

    def _apply_maximized_client_inset(self, l_param: int) -> None:
        if (
            not l_param
            or not self._user32.IsZoomed(self._hwnd)
        ):
            return
        rect = wintypes.RECT.from_address(int(l_param))
        dpi = round(self._dpi_scale() * 96)
        metrics_for_dpi = getattr(self._user32, "GetSystemMetricsForDpi", None)
        if metrics_for_dpi is not None:
            frame_x = metrics_for_dpi(SM_CXSIZEFRAME, dpi)
            frame_y = metrics_for_dpi(SM_CYSIZEFRAME, dpi)
            padded = metrics_for_dpi(SM_CXPADDEDBORDER, dpi)
        else:
            frame_x = self._user32.GetSystemMetrics(SM_CXSIZEFRAME)
            frame_y = self._user32.GetSystemMetrics(SM_CYSIZEFRAME)
            padded = self._user32.GetSystemMetrics(SM_CXPADDEDBORDER)
        inset_x = max(0, int(frame_x + padded))
        inset_y = max(0, int(frame_y + padded))
        rect.left += inset_x
        rect.top += inset_y
        rect.right -= inset_x
        rect.bottom -= inset_y

    def _load_win32(self) -> None:
        try:
            self._user32 = ctypes.WinDLL("user32", use_last_error=True)
            self._user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
            self._user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
            self._user32.SetWindowLongPtrW.argtypes = [
                wintypes.HWND,
                ctypes.c_int,
                ctypes.c_ssize_t,
            ]
            self._user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
            self._user32.SetWindowPos.argtypes = [
                wintypes.HWND,
                wintypes.HWND,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                wintypes.UINT,
            ]
            self._user32.SetWindowPos.restype = wintypes.BOOL
            self._user32.GetWindowRect.argtypes = [
                wintypes.HWND,
                ctypes.POINTER(wintypes.RECT),
            ]
            self._user32.GetWindowRect.restype = wintypes.BOOL
            self._user32.IsZoomed.argtypes = [wintypes.HWND]
            self._user32.IsZoomed.restype = wintypes.BOOL
            self._user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
            self._user32.MonitorFromWindow.restype = wintypes.HMONITOR
            self._user32.GetMonitorInfoW.argtypes = [
                wintypes.HMONITOR,
                ctypes.POINTER(MONITORINFO),
            ]
            self._user32.GetMonitorInfoW.restype = wintypes.BOOL
            get_dpi = getattr(self._user32, "GetDpiForWindow", None)
            if get_dpi is not None:
                get_dpi.argtypes = [wintypes.HWND]
                get_dpi.restype = wintypes.UINT
            get_metrics_for_dpi = getattr(
                self._user32,
                "GetSystemMetricsForDpi",
                None,
            )
            if get_metrics_for_dpi is not None:
                get_metrics_for_dpi.argtypes = [ctypes.c_int, wintypes.UINT]
                get_metrics_for_dpi.restype = ctypes.c_int
            try:
                self._dwmapi = ctypes.WinDLL("dwmapi")
            except OSError:
                self._dwmapi = None
        except (AttributeError, OSError):
            self._user32 = None
            self._dwmapi = None

    def _apply_dwm_preferences(self) -> None:
        if self._dwmapi is None:
            return
        preference = ctypes.c_int(DWMWCP_ROUND)
        try:
            self._dwmapi.DwmSetWindowAttribute(
                self._hwnd,
                DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(preference),
                ctypes.sizeof(preference),
            )
        except (AttributeError, OSError):
            pass

    def _set_control_state(self, hovered: str, pressed: str) -> None:
        if self._control_state_callback is not None:
            self._control_state_callback(hovered, pressed)

    def _pressed_control(self) -> str:
        owner = getattr(self._control_state_callback, "__self__", None)
        return str(getattr(owner, "nativePressedControl", ""))

    @staticmethod
    def _control_name(hit: int) -> str:
        return {
            HTMINBUTTON: "minimize",
            HTMAXBUTTON: "maximize",
            HTCLOSE: "close",
        }.get(hit, "")


__all__ = [
    "HTBOTTOM",
    "HTBOTTOMLEFT",
    "HTBOTTOMRIGHT",
    "HTCAPTION",
    "HTCLIENT",
    "HTCLOSE",
    "HTLEFT",
    "HTMAXBUTTON",
    "HTMINBUTTON",
    "HTRIGHT",
    "HTTOP",
    "HTTOPLEFT",
    "HTTOPRIGHT",
    "IS_WINDOWS",
    "LogicalRect",
    "NativeHitTestRegions",
    "WindowsNativeWindowFilter",
]
