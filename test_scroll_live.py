"""Desktop integration check for real vertical AND horizontal Windows input."""
import os
import ctypes
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import win32con
import win32gui
from PIL import ImageChops, ImageGrab, ImageDraw

from app_advanced import ScreenCaptureApp, tk
from capture_progress import CaptureProgress
from desktop_capture import DesktopFrameGrabber
from test_scroll_capture import document_image
from windows_scroll import WindowsScrollDriver
from scroll_capture import ScrollingCapture

ctypes.windll.user32.SetProcessDPIAware()


@unittest.skipUnless(os.name == "nt", "Requires the Windows desktop")
class LiveScrollTests(unittest.TestCase):
    def setUp(self):
        title = f"MiniScreenShot scroll test {os.getpid()}"
        self.process = subprocess.Popen([sys.executable, "build/scroll_fixture.py", title], creationflags=subprocess.CREATE_NO_WINDOW)
        self.handle = 0
        self.addCleanup(self.close_fixture)
        deadline = time.monotonic() + 10
        while not self.handle and time.monotonic() < deadline:
            self.handle = win32gui.FindWindow(None, title)
            time.sleep(0.1)
        self.assertTrue(self.handle, "Synthetic test window did not start")
        self.root = tk.Tk()
        self.addCleanup(self.root.destroy)
        self.app = ScreenCaptureApp(self.root, language="pl")
        self.root.update()
        # Leave a pinned preview open: it must not steal focus during the next capture.
        self.old_preview = self.app._show_preview(document_image(421, 363), "old", "Poprzedni zrzut")
        self.root.update()
        import pygetwindow as gw
        self.window = gw.Win32Window(self.handle)
        with patch.object(self.app, "get_selectable_windows", return_value=[self.window]):
            self.app._select_capture_mode("window")
        self.app.window_table.selection_set(self.app.window_table.get_children()[0])
        self.root.update()

    def close_fixture(self):
        if self.handle and win32gui.IsWindow(self.handle):
            win32gui.PostMessage(self.handle, win32con.WM_CLOSE, 0, 0)
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            self.process.wait(timeout=5)

    def capture_from_main_button(self):
        existing = set(self.root.winfo_children())
        self.app.capture_action.invoke()
        self.root.update()
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)
            new = [item for item in self.root.winfo_children() if item not in existing and isinstance(item, tk.Toplevel)]
            if new and new[0].render_job is None and new[0].layout_job is None:
                break
        self.assertEqual(len(new), 1, self.app.status.cget("text") + ": " + self.app.capture_notice.cget("text"))
        preview = new[0]
        self.assertTrue(preview.attributes("-topmost"))
        self.assertEqual(self.root.state(), "normal")
        self.assertEqual(self.old_preview.state(), "normal")
        self.assertFalse(self.app.capture_notice.winfo_ismapped())
        return preview.display_image

    def test_ordinary_window_capture_opens_preview_without_boundary_scan(self):
        with patch("app_advanced.ScrollingCapture", side_effect=AssertionError("Unexpected boundary scan")):
            result = self.capture_from_main_button()
        self.assertEqual(result.size, (self.window.width, self.window.height))
        origin = win32gui.ClientToScreen(self.handle, (0, 0))
        client = win32gui.GetClientRect(self.handle)
        left = origin[0] - self.window.left + 16
        top = origin[1] - self.window.top + 40
        width, height = client[2] - 32, client[3] - 64
        content = result.crop((left, top, left + width, top + height))
        expected = document_image(421, 363).crop((0, 0, width, height))
        self.assertIsNone(ImageChops.difference(content, expected).getbbox())

    def test_rectangle_capture_matches_pillow_and_releases_native_buffers(self):
        with self.app._hidden_capture_windows():
            self.app._focus_window_if_possible(self.window)
            origin = win32gui.ClientToScreen(self.handle, (0, 0))
            client = win32gui.GetClientRect(self.handle)
            bbox = (*origin, origin[0] + client[2], origin[1] + client[3])
            baseline = ImageGrab.grab(bbox=bbox, all_screens=True)
            user32 = ctypes.windll.user32
            user32.GetGuiResources.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            kernel32 = ctypes.windll.kernel32
            kernel32.GetCurrentProcess.restype = ctypes.c_void_p
            current_process = kernel32.GetCurrentProcess()
            before = user32.GetGuiResources(current_process, 0)
            for _ in range(8):
                grabber = DesktopFrameGrabber(bbox)
                try:
                    frame = grabber.grab()
                    self.assertIsNone(ImageChops.difference(frame, baseline).getbbox())
                finally:
                    grabber.close()
                    grabber.close()
            self.assertLessEqual(user32.GetGuiResources(current_process, 0), before + 1)

    def test_loader_does_not_capture_pixels_or_intercept_wheel_input(self):
        with self.app._hidden_capture_windows():
            self.app._focus_window_if_possible(self.window)
            driver = WindowsScrollDriver(self.window)
            loader = None
            try:
                baseline = driver.snapshot()
                loader = CaptureProgress(self.root, driver.bbox)
                hint = loader.capture_hint.cget("text")
                self.assertEqual(hint, "Nie poruszaj myszką i nie przełączaj okna.")
                loader.set_message("Łączę fragmenty…")
                self.assertEqual(loader.capture_hint.cget("text"), hint)
                loader.ui.set_language("en")
                self.assertEqual(loader.capture_hint.cget("text"),
                                 "Do not move the mouse or switch windows during capture.")
                loader.window.update_idletasks()
                self.assertLessEqual(loader.elapsed.winfo_rooty() + loader.elapsed.winfo_height(),
                                     loader.window.winfo_rooty() + loader.window.winfo_height())
                hit = win32gui.WindowFromPoint(driver.pointer)
                self.assertEqual(win32gui.GetAncestor(hit, 2), self.handle,
                                 "Progress panel covered the native wheel-input target")
                driver.pulse, driver.frame_guard = loader.pump, loader.capture_frame
                frame = driver.snapshot()
                self.assertIsNone(ImageChops.difference(baseline, frame).getbbox(), "Loader appeared in captured pixels")
                driver.scroll("y", 1, 1)
                frame = driver.snapshot()
                self.assertEqual(win32gui.GetForegroundWindow(), self.handle)
                width, height = frame.width - 32, frame.height - 64
                content = frame.crop((16, 40, 16 + width, 40 + height))
                expected = document_image(421, 363).crop((0, 27, width, 27 + height))
                self.assertIsNone(ImageChops.difference(content, expected).getbbox(), "Loader intercepted scrolling")
                repeated = driver.snapshot()
                self.assertIsNone(ImageChops.difference(frame, repeated).getbbox(), "Loader leaked into a repeated frame")
                self.assertTrue(win32gui.IsWindowVisible(loader.handle))
            finally:
                if loader:
                    loader.close()
                driver.close()

    def test_redacted_progress_window_never_leaves_a_black_rectangle(self):
        with self.app._hidden_capture_windows():
            self.app._focus_window_if_possible(self.window)
            driver = WindowsScrollDriver(self.window)
            loader = CaptureProgress(self.root, driver.bbox)
            # Some desktop capture paths report exclusion support but redact
            # visible protected windows instead of recovering the pixels below.
            loader.excluded = True
            original = driver._grabber.grab
            def redacting_grab():
                frame = original()
                if win32gui.IsWindowVisible(loader.handle):
                    left, top, right, bottom = win32gui.GetWindowRect(loader.handle)
                    ImageDraw.Draw(frame).rectangle((left - driver.bbox[0], top - driver.bbox[1],
                                                      right - driver.bbox[0], bottom - driver.bbox[1]), fill="black")
                return frame
            driver._grabber.grab = redacting_grab
            driver.frame_guard, driver.pulse = loader.capture_frame, loader.pump
            try:
                engine = ScrollingCapture(driver, include_window_frame=True)
                result = engine.capture()
                self.assertIsNone(engine.incomplete_reason)
                content = result.crop(result.info["capture_content_box"])
                expected = document_image(421, 363).crop((0, 0, content.width, 363))
                self.assertEqual(content.size, expected.size)
                self.assertIsNone(ImageChops.difference(content, expected).getbbox(),
                                  "Progress-window redaction damaged the stitched image")
                result.close()
            finally:
                loader.close()
                driver.close()

    def test_main_button_captures_two_axis_document_without_repeated_pixels(self):
        self.app.vertical_var.set(True)
        self.app.horizontal_var.set(True)
        with patch("app_advanced.messagebox.showinfo",
                   side_effect=AssertionError("Scrolling capture must not require confirmation")):
            result = self.capture_from_main_button()
        expected = document_image(421, 363)
        content = result.crop(result.info["capture_content_box"])
        self.assertEqual(content.size, expected.size)
        self.assertIsNone(ImageChops.difference(content, expected).getbbox())
        self.assertGreater(result.info["capture_content_box"][1], 0, "Fixed header was cropped")
        destination = Path("build/preview-review")
        destination.mkdir(parents=True, exist_ok=True)
        result.save(destination / "scroll-grid-live.png")


if __name__ == "__main__":
    unittest.main()
