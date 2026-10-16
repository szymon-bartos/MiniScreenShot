import time
import unittest
import os
from unittest.mock import patch
from unittest.mock import Mock

from PIL import Image
import pyautogui
import pygetwindow as gw

from app_advanced import ScreenCaptureApp, SelectionOverlay, ImageGrab


class DummyRoot:
    def winfo_rootx(self):
        return 100

    def winfo_rooty(self):
        return 100

    def winfo_width(self):
        return 400

    def winfo_height(self):
        return 300


class DummyWindow:
    def __init__(self, title, left, top, right, bottom, visible=True, minimized=False):
        self.title = title
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom
        self.visible = visible
        self.minimized = minimized


class DummyWindowWithoutMinimized:
    def __init__(self, title, left, top, right, bottom, visible=True):
        self.title = title
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom
        self.visible = visible


class DummyZeroSizeWindow:
    def __init__(self, title, left, top, right, bottom, visible=True, minimized=False):
        self.title = title
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom
        self.visible = visible
        self.minimized = minimized


class CaptureTargetingTests(unittest.TestCase):
    def setUp(self):
        self.app = ScreenCaptureApp.__new__(ScreenCaptureApp)
        self.app.root = DummyRoot()
        self.app.set_status = lambda message: None

    def test_get_selectable_windows_excludes_app_window(self):
        original = gw.getAllWindows
        gw.getAllWindows = lambda: [
            DummyWindow("Windows Capture Studio", 100, 100, 500, 450, visible=True, minimized=False),
            DummyWindow("Chrome", 600, 150, 1200, 700, visible=True, minimized=False),
            DummyWindow("Notepad", 50, 50, 300, 250, visible=True, minimized=False),
        ]
        try:
            result = self.app.get_selectable_windows()
        finally:
            gw.getAllWindows = original

        titles = [w.title for w in result]
        self.assertEqual(titles, ["Chrome", "Notepad"])

    def test_get_selectable_windows_handles_objects_without_minimized_attr(self):
        original = gw.getAllWindows
        gw.getAllWindows = lambda: [
            DummyWindowWithoutMinimized("Windows Capture Studio", 100, 100, 500, 450, visible=True),
            DummyWindowWithoutMinimized("Chrome", 600, 150, 1200, 700, visible=True),
        ]
        try:
            result = self.app.get_selectable_windows()
        finally:
            gw.getAllWindows = original

        titles = [w.title for w in result]
        self.assertEqual(titles, ["Chrome"])

    def test_get_selectable_windows_skips_zero_size_windows(self):
        original = gw.getAllWindows
        gw.getAllWindows = lambda: [
            DummyZeroSizeWindow("Windows Capture Studio", 100, 100, 500, 450, visible=True, minimized=False),
            DummyZeroSizeWindow("Chrome", 600, 150, 1200, 700, visible=True, minimized=False),
            DummyZeroSizeWindow("Broken", 300, 300, 300, 300, visible=True, minimized=False),
        ]
        try:
            result = self.app.get_selectable_windows()
        finally:
            gw.getAllWindows = original

        titles = [w.title for w in result]
        self.assertEqual(titles, ["Chrome"])

    def test_get_selectable_windows_keeps_valid_secondary_monitor_window(self):
        original = gw.getAllWindows
        gw.getAllWindows = lambda: [
            DummyWindow("Windows Capture Studio", 100, 100, 500, 450, visible=True, minimized=False),
            DummyWindow("Firefox", -1400, 120, -200, 840, visible=True, minimized=False),
        ]
        try:
            result = self.app.get_selectable_windows()
        finally:
            gw.getAllWindows = original

        titles = [w.title for w in result]
        self.assertIn("Firefox", titles)

    def test_get_selectable_windows_keeps_offscreen_visible_window(self):
        original = gw.getAllWindows
        gw.getAllWindows = lambda: [
            DummyWindow("Windows Capture Studio", 100, 100, 500, 450, visible=True, minimized=False),
            DummyWindow("OTOMOTO", -16000, -16000, -15843, -15975, visible=True, minimized=False),
        ]
        try:
            result = self.app.get_selectable_windows()
        finally:
            gw.getAllWindows = original

        titles = [w.title for w in result]
        self.assertIn("OTOMOTO", titles)

    def test_get_selectable_windows_keeps_minimized_browser_window(self):
        original = gw.getAllWindows
        gw.getAllWindows = lambda: [
            DummyWindow("Windows Capture Studio", 100, 100, 500, 450, visible=True, minimized=False),
            DummyWindow("Firefox", -16000, -16000, -15843, -15975, visible=True, minimized=True),
        ]
        try:
            result = self.app.get_selectable_windows()
        finally:
            gw.getAllWindows = original

        titles = [w.title for w in result]
        self.assertIn("Firefox", titles)

    def test_get_selectable_windows_excludes_own_preview_and_hidden_windows(self):
        own = DummyWindow("Podgląd zrzutu", 20, 20, 600, 400)
        hidden = DummyWindow("Ukryte okno", 20, 20, 600, 400, visible=False)
        browser = DummyWindow("Strona - Google Chrome", 20, 20, 600, 400)
        with patch.object(gw, "getAllWindows", return_value=[own, hidden, browser]), patch(
            "app_advanced.window_process_id", side_effect=lambda window: os.getpid() if window is own else None
        ):
            self.assertEqual(self.app.get_selectable_windows(), [browser])

    def test_window_capture_reads_geometry_after_restoring_minimized_window(self):
        window = DummyWindow("Raport - Excel", -16000, -16000, -15843, -15975, minimized=True)
        def restore():
            window.left, window.top, window.right, window.bottom = (50, 80, 650, 480)
        window.restore = restore
        self.app.vertical_var = type("Option", (), {"get": lambda self: False})()
        self.app.horizontal_var = self.app.vertical_var
        self.app._show_capture_warning = lambda: None
        with patch("app_advanced.time.sleep"), patch("app_advanced.ImageGrab.grab", return_value=Image.new("RGB", (600, 400))) as grab, patch.object(self.app, "_capture_to_preview"):
            self.app._capture_window_obj(window)
        grab.assert_called_once_with(bbox=(50, 80, 650, 480))

    def test_focus_keeps_maximized_window_size(self):
        window = DummyWindow("Strona - Chrome", 0, 0, 1920, 1080, minimized=False)
        window.restore = Mock()
        window.activate = Mock()
        self.app._focus_window_if_possible(window)
        window.restore.assert_not_called()
        window.activate.assert_called_once_with()

    def test_default_capture_dir_is_on_c_drive(self):
        from app_advanced import DEFAULT_CAPTURE_DIR
        self.assertTrue(str(DEFAULT_CAPTURE_DIR).lower().startswith("c:"))

    def test_has_new_content_ignores_minor_redraws(self):
        prev = Image.new("RGB", (100, 100), "white")
        current = Image.new("RGB", (100, 100), "white")
        current.putpixel((10, 10), (255, 255, 254))

        self.assertFalse(self.app.has_meaningful_change(prev, current))

        big_change = Image.new("RGB", (100, 100), "white")
        for x in range(5, 95):
            for y in range(5, 95):
                big_change.putpixel((x, y), (0, 0, 0))
        self.assertTrue(self.app.has_meaningful_change(prev, big_change))

    def test_capture_scrolled_window_handles_horizontal_only_mode(self):
        self.app.vertical_var = type("VerticalVar", (), {"get": lambda self: False})()
        self.app.horizontal_var = type("HorizontalVar", (), {"get": lambda self: True})()
        self.app._focus_window_if_possible = lambda window: None
        window = DummyWindow("Browser", 10, 20, 200, 300, visible=True, minimized=False)
        image = Image.new("RGB", (420, 280), "white")
        driver = Mock()
        engine = Mock()
        engine.capture.return_value = image
        with patch("app_advanced.WindowsScrollDriver", return_value=driver), patch("app_advanced.ScrollingCapture", return_value=engine) as constructor, patch("app_advanced.time.sleep"), patch.object(self.app, "_capture_to_preview") as preview:
            self.app._capture_scrolled_window(window)
        constructor.assert_called_once_with(driver, vertical=False, horizontal=True, progress=self.app._scroll_progress)
        engine.capture.assert_called_once_with()
        driver.close.assert_called_once_with()
        self.assertIs(preview.call_args.args[0], image)

    def test_cancelled_scroll_capture_restores_driver_without_showing_partial_preview(self):
        from scroll_capture import CaptureCancelled
        self.app.vertical_var = type("Option", (), {"get": lambda self: True})()
        self.app.horizontal_var = self.app.vertical_var
        self.app._focus_window_if_possible = lambda window: None
        driver, engine = Mock(), Mock()
        engine.capture.side_effect = CaptureCancelled("Anulowano")
        with patch("app_advanced.WindowsScrollDriver", return_value=driver), patch("app_advanced.ScrollingCapture", return_value=engine), patch("app_advanced.time.sleep"), patch.object(self.app, "_capture_to_preview") as preview:
            self.app._capture_scrolled_window(DummyWindow("Browser", 10, 20, 200, 300))
        driver.close.assert_called_once_with()
        preview.assert_not_called()

    def test_partial_scroll_is_shown_with_clear_notice_and_can_be_saved(self):
        self.app.vertical_var = type("Option", (), {"get": lambda self: True})()
        self.app.horizontal_var = type("Option", (), {"get": lambda self: False})()
        self.app._focus_window_if_possible = lambda window: None
        driver, engine, preview = Mock(), Mock(), Mock()
        engine.capture.return_value = Image.new("RGB", (240, 800), "white")
        engine.incomplete_reason = "Strona przestała się przewijać."
        with patch("app_advanced.WindowsScrollDriver", return_value=driver), patch("app_advanced.ScrollingCapture", return_value=engine), patch("app_advanced.time.sleep"), patch.object(self.app, "_capture_to_preview", return_value=preview):
            self.app._capture_scrolled_window(DummyWindow("Browser", 10, 20, 200, 300))
        preview.heading.configure.assert_called_once_with(text="Zrzut częściowy", fg="#fbbf24")
        preview.source_label.configure.assert_called_once_with(text=engine.incomplete_reason)
        driver.close.assert_called_once_with()

    def test_deduplicate_screenshots_removes_duplicate_bottom_frames(self):
        frame = Image.new("RGB", (200, 200), "white")
        result = self.app._deduplicate_screenshots([frame, frame, frame], min_changed_ratio=0.02)
        self.assertEqual(len(result), 1)

    def test_normalize_crop_box_clamps_out_of_bounds_values(self):
        result = self.app._normalize_crop_box((-20, -10, 300, 220), 200, 180)
        self.assertEqual(result, (0, 0, 200, 180))

    def test_area_selection_keeps_horizontal_and_vertical_coordinates_separate(self):
        overlay = SelectionOverlay.__new__(SelectionOverlay)
        overlay.start_x, overlay.start_y = 900, 100
        result = []
        overlay.callback = result.append
        overlay.destroy = lambda: None
        event = type("Release", (), {"x_root": 400, "y_root": 350})()
        overlay.on_release(event)
        self.assertEqual(result, [(400, 100, 900, 350)])


if __name__ == "__main__":
    unittest.main()
