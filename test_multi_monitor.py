"""Coordinate and pixel regressions for negative origins and legacy DPI hosts."""
from contextlib import contextmanager
import ctypes
from pathlib import Path
import time
import unittest
import subprocess
import sys
from unittest.mock import Mock, patch

from PIL import ImageChops, ImageGrab, ImageTk
import win32gui

from app_advanced import tk
from desktop_capture import DesktopFrameGrabber
from windows_scroll import WindowsScrollDriver
from test_scroll_capture import FakeScrollDriver, document_image
from scroll_capture import ScrollCaptureError, ScrollingCapture
from windows_coordinates import client_bounds, monitor_rectangles, physical_pixels, rectangle_visible


@contextmanager
def thread_dpi(context):
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    setter = user32.SetThreadDpiAwarenessContext
    setter.argtypes = [ctypes.c_void_p]
    setter.restype = ctypes.c_void_p
    previous = setter(ctypes.c_void_p(context))
    if not previous:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        yield
    finally:
        setter(previous)


class NativeCoordinateTests(unittest.TestCase):
    def setUp(self):
        with thread_dpi(-4):
            self.root = tk.Tk()
            self.root.geometry("420x280+100+100")
            self.canvas = tk.Canvas(self.root, highlightthickness=0, bd=0)
            self.canvas.pack(fill="both", expand=True)
            self.image = ImageTk.PhotoImage(document_image(420, 280), master=self.root)
            self.canvas.create_image(0, 0, anchor="nw", image=self.image)
            self.root.update()
            self.handle = win32gui.GetAncestor(self.root.winfo_id(), 2)
            self.root.lift()
            self.root.update()
            ctypes.windll.dwmapi.DwmFlush()
            time.sleep(.1)
            rect = win32gui.GetClientRect(self.handle)
            self.physical_bounds = (*win32gui.ClientToScreen(self.handle, rect[:2]),
                                    *win32gui.ClientToScreen(self.handle, rect[2:]))
            self.baseline = ImageGrab.grab(bbox=self.physical_bounds, all_screens=True)
        self.addCleanup(self.root.destroy)

    def test_client_bounds_are_physical_even_in_an_unaware_host_thread(self):
        driver = WindowsScrollDriver.__new__(WindowsScrollDriver)
        driver.handle = self.handle
        with thread_dpi(-1):
            self.assertEqual(driver._client_bbox(), self.physical_bounds)
            self.assertEqual(client_bounds(self.handle), self.physical_bounds)

    def test_native_window_pixels_on_every_connected_display(self):
        for monitor in monitor_rectangles():
            with self.subTest(monitor=monitor), physical_pixels():
                win32gui.SetWindowPos(self.handle, -1, monitor[0] + 40, monitor[1] + 40, 460, 340, 0x10)
                self.root.update()
                ctypes.windll.dwmapi.DwmFlush()
                time.sleep(.15)
                bbox = client_bounds(self.handle)
                self.assertTrue(rectangle_visible(bbox, (monitor,)))
                expected = ImageGrab.grab(bbox=bbox, all_screens=True)
                with thread_dpi(-1):
                    grabber = DesktopFrameGrabber(bbox)
                    try:
                        actual = grabber.grab()
                        self.assertEqual(actual.size, expected.size)
                        self.assertIsNone(ImageChops.difference(actual, expected).getbbox())
                    finally:
                        grabber.close()

    def test_dpi_context_is_restored_after_nested_calls_and_exceptions(self):
        api = ctypes.WinDLL("user32")
        api.GetThreadDpiAwarenessContext.restype = ctypes.c_void_p
        api.GetAwarenessFromDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        awareness = lambda: api.GetAwarenessFromDpiAwarenessContext(api.GetThreadDpiAwarenessContext())
        with thread_dpi(-1):
            self.assertEqual(awareness(), 0)
            with self.assertRaises(ValueError):
                with physical_pixels():
                    self.assertEqual(awareness(), 2)
                    client_bounds(self.handle)
                    raise ValueError("Synthetic capture failure")
            self.assertEqual(awareness(), 0)

    def test_gdi_samples_the_same_pixels_when_the_host_thread_is_unaware(self):
        with thread_dpi(-1):
            grabber = DesktopFrameGrabber(self.physical_bounds)
            try:
                result = grabber.grab()
                self.assertEqual(result.size, self.baseline.size)
                if ImageChops.difference(result, self.baseline).getbbox():
                    folder = Path("build/monitor-review")
                    folder.mkdir(parents=True, exist_ok=True)
                    result.save(folder / "gdi.png")
                    self.baseline.save(folder / "pillow.png")
                self.assertIsNone(ImageChops.difference(result, self.baseline).getbbox())
            finally:
                grabber.close()

    def test_a_display_disconnect_stops_before_another_frame_is_sampled(self):
        driver = WindowsScrollDriver.__new__(WindowsScrollDriver)
        driver.handle = self.handle
        driver.bbox = self.physical_bounds
        driver._display_layout = monitor_rectangles()
        driver.pulse = lambda: None
        driver._grab = Mock()
        with patch("windows_scroll.monitor_rectangles", return_value=()):
            with self.assertRaisesRegex(ScrollCaptureError, "monitorów"):
                driver._check()
        driver._grab.assert_not_called()


class VirtualDesktopTests(unittest.TestCase):
    def test_same_scale_displays_left_right_above_and_below_keep_signed_coordinates(self):
        layouts = [
            (((-1920, 0, 0, 1080), (0, 0, 1920, 1080)), (-1800, 80, -900, 900)),
            (((0, 0, 1920, 1080), (1920, 0, 3840, 1080)), (2050, 80, 3000, 900)),
            (((0, -1080, 1920, 0), (0, 0, 1920, 1080)), (100, -1000, 1700, -120)),
            (((0, 0, 1920, 1080), (0, 1080, 1920, 2160)), (100, 1160, 1700, 2000)),
        ]
        for monitors, bbox in layouts:
            with self.subTest(bbox=bbox):
                self.assertTrue(rectangle_visible(bbox, monitors))
                # Native client offsets are already physical screen pixels;
                # neither the virtual desktop origin nor DPI is added again.
                with patch("win32gui.GetClientRect", return_value=(0, 0, bbox[2]-bbox[0], bbox[3]-bbox[1])), \
                        patch("win32gui.ClientToScreen", side_effect=[bbox[:2], bbox[2:]]):
                    self.assertEqual(client_bounds(123), bbox)

    def test_spanning_two_adjacent_displays_is_allowed_without_clipping(self):
        monitors = ((-1920, 0, 0, 1080), (0, 0, 2560, 1440))
        self.assertTrue(rectangle_visible((-600, 100, 900, 1000), monitors))

    def test_gaps_between_displays_and_offscreen_edges_are_rejected(self):
        monitors = ((-1920, -300, 0, 780), (0, 0, 2560, 1440))
        for bbox in ((-500, 600, 500, 1100), (-2100, 0, -1500, 700), (2300, 200, 2800, 900),
                     (-500, -200, 500, 200)):
            with self.subTest(bbox=bbox):
                self.assertFalse(rectangle_visible(bbox, monitors))

    def test_mirrored_displays_are_not_double_counted_as_visible_area(self):
        monitors = ((0, 0, 1920, 1080), (0, 0, 1920, 1080))
        self.assertTrue(rectangle_visible((100, 100, 1800, 1000), monitors))
        self.assertFalse(rectangle_visible((1500, 100, 2200, 800), monitors))

    def test_offscreen_window_is_rejected_before_gdi_or_wheel_input(self):
        with patch("windows_scroll.WindowsScrollDriver._client_bbox", return_value=(-200, -200, 600, 500)), \
                patch("windows_scroll.monitor_rectangles", return_value=((0, 0, 1920, 1080),)), \
                patch("windows_scroll.DesktopFrameGrabber") as grabber, \
                patch("windows_scroll.win32api.SetCursorPos") as cursor:
            with self.assertRaisesRegex(ScrollCaptureError, "nie mieści"):
                WindowsScrollDriver(type("Window", (), {"_hWnd":123})())
        grabber.assert_not_called()
        cursor.assert_not_called()


class VirtualDesktopPixelsTests(unittest.TestCase):
    def test_full_saved_content_with_simulated_second_monitor_positions_and_same_scale(self):
        import tempfile
        from PIL import Image
        for scale in (1, 1.5):
            for origin in ((-1600, 120), (2100, 120), (120, -900), (120, 1400), (-100, 120)):
                with self.subTest(scale=scale, origin=origin):
                    document = document_image(round(240 * scale), round(1100 * scale))
                    driver = FakeScrollDriver(document, viewport=(round(240 * scale), round(180 * scale)))
                    size = (driver.viewport[0] + 32, driver.viewport[1] + 64)
                    bbox = (origin[0], origin[1], origin[0] + size[0], origin[1] + size[1])
                    grabber = DesktopFrameGrabber(bbox)
                    original_snapshot = driver.snapshot
                    current = None
                    test = self

                    def copy_virtual_window(destination, x, y, width, height, source, sx, sy, operation):
                        test.assertEqual((sx, sy), origin)
                        test.assertEqual((width, height), size)
                        data = current.tobytes("raw", "BGRX")
                        ctypes.memmove(grabber.pixels, data, len(data))
                        return True

                    def snapshot():
                        nonlocal current
                        current = original_snapshot()
                        # Pixels are supplied from our synthetic window to our
                        # own DIB; no desktop content outside a test is read.
                        with thread_dpi(-1):
                            return grabber.grab()

                    driver.snapshot = snapshot
                    try:
                        with patch.object(grabber.gdi32, "BitBlt", side_effect=copy_virtual_window):
                            engine = ScrollingCapture(driver, include_window_frame=True)
                            result = engine.capture()
                        try:
                            self.assertIsNone(engine.incomplete_reason)
                            self.assertEqual(result.size, (document.width + 32, document.height + 64))
                            content = result.crop(result.info["capture_content_box"])
                            self.assertEqual(content.size, document.size)
                            self.assertIsNone(ImageChops.difference(content, document).getbbox())
                            with tempfile.TemporaryDirectory() as folder:
                                path = Path(folder) / "window-scroll.png"
                                result.save(path)
                                with Image.open(path) as saved:
                                    self.assertIsNone(ImageChops.difference(saved.crop(result.info["capture_content_box"]), document).getbbox())
                        finally:
                            result.close()
                    finally:
                        grabber.close()


class SourceStartupTests(unittest.TestCase):
    def test_source_bootstrap_keeps_per_monitor_dpi_after_pyautogui_import(self):
        code = """
import ctypes
from windows_coordinates import configure_process_dpi
configure_process_dpi()
import pyautogui
api=ctypes.WinDLL('user32')
api.GetThreadDpiAwarenessContext.restype=ctypes.c_void_p
api.GetAwarenessFromDpiAwarenessContext.argtypes=[ctypes.c_void_p]
assert api.GetAwarenessFromDpiAwarenessContext(api.GetThreadDpiAwarenessContext())==2
print('Per-monitor DPI startup: OK')
"""
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
