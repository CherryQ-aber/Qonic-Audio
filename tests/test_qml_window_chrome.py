from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, QPointF, Qt, QUrl
from PySide6.QtGui import QCloseEvent, QWindow
from PySide6.QtQml import QQmlComponent
from PySide6.QtQuick import QQuickItem, QQuickView
from PySide6.QtWidgets import QApplication

from ui_next.bridge.window_controller import WindowController
from ui_next.bridge.windows_native_window import (
    HTBOTTOMLEFT,
    HTCAPTION,
    HTCLIENT,
    HTCLOSE,
    HTMAXBUTTON,
    HTMINBUTTON,
    HTRIGHT,
    HTTOPRIGHT,
    NativeHitTestRegions,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class NativeHitTestRegionTests(unittest.TestCase):
    def setUp(self):
        self.regions = NativeHitTestRegions(resize_border=7)
        self.regions.set_caption_rects(
            [
                {"x": 0, "y": 0, "width": 1080, "height": 58},
            ]
        )
        self.regions.set_interactive_rects(
            [{"x": 230, "y": 0, "width": 240, "height": 58}]
        )
        self.regions.set_control_rect("minimize", 930, 0, 46, 58)
        self.regions.set_control_rect("maximize", 976, 0, 46, 58)
        self.regions.set_control_rect("close", 1022, 0, 46, 58)

    def test_caption_and_controls_scale_from_logical_to_physical_pixels(self):
        scale = 1.25
        width = round(1080 * scale)
        height = round(720 * scale)
        self.assertEqual(
            HTCAPTION,
            self.regions.hit_test(100, 30, width, height, scale=scale, maximized=False),
        )
        self.assertEqual(
            HTMINBUTTON,
            self.regions.hit_test(1180, 30, width, height, scale=scale, maximized=False),
        )
        self.assertEqual(
            HTMAXBUTTON,
            self.regions.hit_test(1240, 30, width, height, scale=scale, maximized=False),
        )
        self.assertEqual(
            HTCLOSE,
            self.regions.hit_test(1300, 30, width, height, scale=scale, maximized=False),
        )

    def test_all_resize_edges_use_invisible_dpi_scaled_hot_zones(self):
        scale = 1.5
        width = round(1080 * scale)
        height = round(720 * scale)
        self.assertEqual(
            HTRIGHT,
            self.regions.hit_test(width - 2, 400, width, height, scale=scale, maximized=False),
        )
        self.assertEqual(
            HTTOPRIGHT,
            self.regions.hit_test(width - 2, 2, width, height, scale=scale, maximized=False),
        )
        self.assertEqual(
            HTBOTTOMLEFT,
            self.regions.hit_test(2, height - 2, width, height, scale=scale, maximized=False),
        )

    def test_maximized_window_disables_resize_but_keeps_caption_and_controls(self):
        self.assertEqual(
            HTMAXBUTTON,
            self.regions.hit_test(990, 20, 1080, 720, scale=1.0, maximized=True),
        )
        self.assertEqual(
            HTCAPTION,
            self.regions.hit_test(500, 20, 1080, 720, scale=1.0, maximized=True),
        )

    def test_interactive_title_bar_content_stays_client_but_all_gaps_drag(self):
        self.assertEqual(
            HTCLIENT,
            self.regions.hit_test(300, 30, 1080, 720, scale=1.0, maximized=False),
        )
        self.assertEqual(
            HTCAPTION,
            self.regions.hit_test(700, 30, 1080, 720, scale=1.0, maximized=False),
        )

    def test_unknown_or_empty_rectangles_do_not_create_native_controls(self):
        self.regions.set_control_rect("not-a-window-control", 0, 0, 100, 100)
        self.regions.set_control_rect("close", 0, 0, 0, 0)
        self.assertNotIn("not-a-window-control", self.regions.control_rects)
        self.assertNotIn("close", self.regions.control_rects)


class WindowControllerCloseFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_offscreen_platform_uses_safe_native_titlebar_fallback(self):
        controller = WindowController(
            self.app,
            smoke_test=True,
            tray_enabled=False,
        )
        self.assertFalse(controller.framelessEnabled)
        self.assertFalse(controller.deferInitialShow)
        self.assertFalse(controller.trayAvailable)

    def test_close_hides_only_when_a_real_tray_exit_path_exists(self):
        controller = WindowController(
            self.app,
            smoke_test=False,
            tray_enabled=False,
        )
        window = QWindow()
        controller.attach_window(window)
        controller._tray_available = True
        window.show()
        self.app.processEvents()
        event = QCloseEvent()
        self.assertTrue(controller.eventFilter(window, event))
        self.assertFalse(event.isAccepted())
        self.assertFalse(window.isVisible())
        controller.shutdown()
        window.destroy()

    def test_without_tray_the_close_event_is_allowed_to_exit(self):
        controller = WindowController(
            self.app,
            smoke_test=False,
            tray_enabled=False,
        )
        window = QWindow()
        controller.attach_window(window)
        event = QCloseEvent()
        self.assertFalse(controller.eventFilter(window, event))
        controller.shutdown()
        window.destroy()

    def test_native_control_action_dispatches_to_the_same_controller_slots(self):
        class FakeWindow:
            def __init__(self):
                self.calls = []
                self.states = Qt.WindowState.WindowNoState

            def showMinimized(self):
                self.calls.append("minimize")

            def showMaximized(self):
                self.calls.append("maximize")
                self.states = Qt.WindowState.WindowMaximized

            def showNormal(self):
                self.calls.append("restore")
                self.states = Qt.WindowState.WindowNoState

            def close(self):
                self.calls.append("close")

            def windowStates(self):
                return self.states

        controller = WindowController(
            self.app,
            smoke_test=True,
            tray_enabled=False,
        )
        fake = FakeWindow()
        controller._window = fake
        for control in ("minimize", "maximize", "maximize", "close"):
            controller._handle_native_control_action(control)
            self.app.processEvents()
        self.assertEqual(
            ["minimize", "maximize", "restore", "close"],
            fake.calls,
        )


class QmlWindowChromeLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _create_title_bar(self, width: int, theme_mode: str):
        view = QQuickView()
        controller = WindowController(
            self.app,
            smoke_test=True,
            tray_enabled=False,
        )
        view.engine().rootContext().setContextProperty("chrome", controller)
        view.engine().rootContext().setContextProperty(
            "chromeIcon",
            QUrl.fromLocalFile(str(PROJECT_ROOT / "Assets" / "icon.ico")),
        )
        component = QQmlComponent(view.engine())
        source = f'''import QtQuick
import "ui_next/qml/components"
import "ui_next/qml/theme"

Item {{
    width: {width}
    height: 58
    Theme {{ id: probeTheme; requestedMode: "{theme_mode}" }}
    TopStatusBar {{
        objectName: "titleBarUnderTest"
        anchors.fill: parent
        theme: probeTheme
        nativeWindowChrome: true
        windowController: chrome
        applicationIconSource: chromeIcon
        versionLabel: "v5.0 Internal Test"
        workspaces: [
            {{ "key": "autoConvert", "title": "自动转码", "description": "任务" }},
            {{ "key": "audioEditor", "title": "音频编辑", "description": "编辑" }}
        ]
        currentWorkspaceKey: "autoConvert"
        folderBrowserAvailable: true
    }}
}}
'''.encode("utf-8")
        component.setData(
            source,
            QUrl.fromLocalFile(str(PROJECT_ROOT / "window_chrome_probe.qml")),
        )
        container = component.create()
        self.assertIsNotNone(container, component.errors())
        self.assertIsInstance(container, QQuickItem)
        container.setParentItem(view.contentItem())
        view.setWidth(width)
        view.setHeight(58)
        view.show()
        self.app.processEvents()
        self.app.processEvents()
        return view, component, container, controller

    def _dispose_title_bar(self, view, container, controller):
        controller.shutdown()
        view.close()
        container.deleteLater()
        view.deleteLater()
        self.app.processEvents()

    def test_1080px_title_bar_keeps_every_core_action_inside_the_window(self):
        view, _component, container, controller = self._create_title_bar(1080, "dark")
        try:
            expected = (
                "applicationTitleIcon",
                "workspaceSwitcher",
                "toggleGlobalFolderBrowserButton",
                "openSettingsButton",
                "openGlobalLogButton",
                "minimizeWindowButton",
                "maximizeRestoreWindowButton",
                "closeWindowButton",
            )
            for object_name in expected:
                item = container.findChild(QQuickItem, object_name)
                self.assertIsNotNone(item, object_name)
                point = item.mapToItem(container, QPointF(0, 0))
                self.assertGreaterEqual(point.x(), -0.5, object_name)
                self.assertLessEqual(
                    point.x() + item.width(),
                    container.width() + 0.5,
                    object_name,
                )

            drag_region = container.findChild(QQuickItem, "windowTitleDragRegion")
            self.assertIsNotNone(drag_region)
            self.assertGreater(drag_region.width(), 20)
            caption_rects = controller._regions.caption_rects
            self.assertEqual(1, len(caption_rects))
            self.assertEqual(round(container.width()), round(caption_rects[0].width))
            self.assertGreaterEqual(len(controller._regions.interactive_rects), 4)
            drag_point = drag_region.mapToItem(
                container,
                QPointF(drag_region.width() / 2, drag_region.height() / 2),
            )
            self.assertEqual(
                HTCAPTION,
                controller._regions.hit_test(
                    round(drag_point.x()),
                    round(drag_point.y()),
                    round(container.width()),
                    round(container.height()),
                    scale=1.0,
                    maximized=True,
                ),
            )
            workspace = container.findChild(QQuickItem, "workspaceSwitcher")
            workspace_point = workspace.mapToItem(
                container,
                QPointF(workspace.width() / 2, workspace.height() / 2),
            )
            self.assertEqual(
                HTCLIENT,
                controller._regions.hit_test(
                    round(workspace_point.x()),
                    round(workspace_point.y()),
                    round(container.width()),
                    round(container.height()),
                    scale=1.0,
                    maximized=True,
                ),
            )
            close_button = container.findChild(QQuickItem, "closeWindowButton")
            close_point = close_button.mapToItem(container, QPointF(0, 0))
            self.assertLessEqual(container.width() - close_point.x() - close_button.width(), 8)
        finally:
            self._dispose_title_bar(view, container, controller)

    def test_window_controls_and_icon_remain_visible_in_both_themes(self):
        for theme_mode in ("dark", "light", "black", "purple"):
            with self.subTest(theme=theme_mode):
                view, _component, container, controller = self._create_title_bar(
                    1280,
                    theme_mode,
                )
                try:
                    icon = container.findChild(QQuickItem, "applicationTitleIcon")
                    controls = container.findChild(QQuickItem, "windowControls")
                    self.assertTrue(icon.isVisible())
                    self.assertGreater(icon.width(), 0)
                    self.assertTrue(controls.isVisible())
                    self.assertEqual(138, round(controls.width()))
                    glyph_canvases = container.findChildren(
                        QQuickItem,
                        "windowControlGlyphCanvas",
                    )
                    self.assertEqual(3, len(glyph_canvases))
                    for canvas in glyph_canvases:
                        parent = canvas.parentItem()
                        self.assertAlmostEqual(
                            parent.width() / 2,
                            canvas.x() + canvas.width() / 2,
                            delta=0.5,
                        )
                        self.assertAlmostEqual(
                            parent.height() / 2,
                            canvas.y() + canvas.height() / 2,
                            delta=0.5,
                        )
                finally:
                    self._dispose_title_bar(view, container, controller)

    def test_shell_and_startup_wire_one_window_controller_without_qml_quit(self):
        shell = (PROJECT_ROOT / "ui_next/qml/AppShell.qml").read_text(encoding="utf-8")
        startup = (PROJECT_ROOT / "main_qml.py").read_text(encoding="utf-8")
        controls = (
            PROJECT_ROOT / "ui_next/qml/components/WindowControls.qml"
        ).read_text(encoding="utf-8")
        title_bar = (
            PROJECT_ROOT / "ui_next/qml/components/TopStatusBar.qml"
        ).read_text(encoding="utf-8")
        self.assertIn("Qt.FramelessWindowHint", shell)
        self.assertIn("windowController", shell)
        self.assertNotIn("Qt.quit", shell)
        self.assertEqual(1, startup.count("WindowController("))
        self.assertIn('setContextProperty("windowController", window_controller)', startup)
        self.assertIn("window_controller.attach_window(engine.rootObjects()[0])", startup)
        self.assertNotIn("Qt.quit", controls)
        self.assertIn("setInteractiveRects", title_bar)
        self.assertNotIn("startSystemMove()", title_bar)

    @unittest.skipUnless(sys.platform == "win32", "Windows native frame check")
    def test_windows_platform_installs_resizable_system_styles(self):
        script = textwrap.dedent(
            """
            import ctypes
            from PySide6.QtCore import Qt
            from PySide6.QtGui import QWindow
            from PySide6.QtWidgets import QApplication
            from ui_next.bridge.window_controller import WindowController

            app = QApplication([])
            window = QWindow()
            window.setFlags(
                Qt.WindowType.Window
                | Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowSystemMenuHint
                | Qt.WindowType.WindowMinimizeButtonHint
                | Qt.WindowType.WindowMaximizeButtonHint
                | Qt.WindowType.WindowCloseButtonHint
            )
            controller = WindowController(app, smoke_test=True, tray_enabled=False)
            window.setGeometry(100, 100, 1080, 720)
            assert controller.framelessEnabled
            controller.attach_window(window)
            controller.setCaptionRects([
                {"x": 0, "y": 0, "width": 1080, "height": 58},
            ])
            controller.setInteractiveRects([
                {"x": 250, "y": 0, "width": 200, "height": 58},
            ])
            controller.setControlRect("minimize", 930, 0, 46, 58)
            controller.setControlRect("maximize", 976, 0, 46, 58)
            controller.setControlRect("close", 1022, 0, 46, 58)
            controller.showInitialWindow()
            app.processEvents()
            hwnd = int(window.winId())
            style = ctypes.windll.user32.GetWindowLongPtrW(hwnd, -16)
            required = 0x00040000 | 0x00020000 | 0x00010000 | 0x00080000
            assert style & required == required, hex(style)
            assert window.isVisible()

            class Rect(ctypes.Structure):
                _fields_ = [
                    ("left", ctypes.c_long),
                    ("top", ctypes.c_long),
                    ("right", ctypes.c_long),
                    ("bottom", ctypes.c_long),
                ]

            def native_hit(logical_x, logical_y):
                rect = Rect()
                assert ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                dpi = ctypes.windll.user32.GetDpiForWindow(hwnd)
                scale = dpi / 96.0
                screen_x = rect.left + round(logical_x * scale)
                screen_y = rect.top + round(logical_y * scale)
                l_param = (screen_x & 0xFFFF) | ((screen_y & 0xFFFF) << 16)
                return ctypes.windll.user32.SendMessageW(hwnd, 0x0084, 0, l_param)

            assert native_hit(100, 30) == 2
            assert native_hit(300, 30) == 1
            assert native_hit(990, 30) == 9
            window.showMaximized()
            app.processEvents()
            assert window.windowStates() & Qt.WindowState.WindowMaximized
            assert native_hit(700, 30) == 2
            controller.shutdown()
            window.close()
            """
        )
        env = os.environ.copy()
        env.pop("QT_QPA_PLATFORM", None)
        completed = subprocess.run(
            [sys.executable, "-B", "-c", script],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
