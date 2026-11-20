"""The progress panel stays visible without covering any sampled pixels."""
import ctypes
import unittest
from unittest.mock import call, patch

import win32api
import win32con
import win32gui

from app_advanced import tk
from capture_progress import CaptureProgress, outside, progress_placement


class ProgressPlacementTests(unittest.TestCase):
    def test_regular_card_fits_outside_a_normal_window(self):
        monitor = {"Work": (0, 0, 1920, 1040), "Monitor": (0, 0, 1920, 1080)}
        bbox = (100, 100, 1300, 900)
        rect, compact, safe = progress_placement(bbox, [monitor], 1)
        self.assertTrue(safe)
        self.assertFalse(compact)
        self.assertTrue(outside(rect, bbox))

    def test_maximized_window_uses_a_steady_strip_in_the_taskbar_area(self):
        for scale in (1, 1.5, 2):
            with self.subTest(scale=scale):
                full = (0, 0, round(1920 * scale), round(1080 * scale))
                work = (0, 0, full[2], round(1040 * scale))
                rect, compact, safe = progress_placement(work, [{"Work": work, "Monitor": full}], scale)
                self.assertTrue(safe)
                self.assertTrue(compact)
                self.assertTrue(outside(rect, work))
                self.assertLessEqual(rect[3], full[3])
                self.assertGreaterEqual(rect[1], work[3])

    def test_another_monitor_can_show_progress_for_a_fullscreen_source(self):
        source = (0, 0, 1920, 1080)
        monitors = [{"Work": (0, 0, 1920, 1040), "Monitor": source},
                    {"Work": (-1920, 0, 0, 1040), "Monitor": (-1920, 0, 0, 1080)}]
        rect, compact, safe = progress_placement(source, monitors, 1)
        self.assertTrue(safe)
        self.assertFalse(compact)
        self.assertLessEqual(rect[2], 0)
        self.assertTrue(outside(rect, source))

    def test_true_fullscreen_without_spare_space_uses_the_single_hide_fallback(self):
        rect = (0, 0, 1920, 1080)
        _, _, safe = progress_placement(rect, [{"Work": rect, "Monitor": rect}], 1)
        self.assertFalse(safe)


class ProgressWindowTests(unittest.TestCase):
    def setUp(self):
        ctypes.windll.user32.SetProcessDPIAware()
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)

    def test_maximized_capture_keeps_progress_visible_across_repeated_snapshots(self):
        monitor = win32api.GetMonitorInfo(win32api.MonitorFromWindow(self.root.winfo_id(), 2))
        loader = CaptureProgress(self.root, monitor["Work"])
        self.addCleanup(loader.close)
        self.assertTrue(loader.outside_capture)
        self.assertTrue(outside(win32gui.GetWindowRect(loader.handle), monitor["Work"]))
        style = win32gui.GetWindowLong(loader.handle, win32con.GWL_EXSTYLE)
        self.assertTrue(style & win32con.WS_EX_LAYERED)
        self.assertTrue(style & win32con.WS_EX_TRANSPARENT)
        left, top, right, bottom = win32gui.GetWindowRect(loader.handle)
        hit = win32gui.WindowFromPoint(((left + right) // 2, (top + bottom) // 2))
        self.assertNotEqual(win32gui.GetAncestor(hit, 2), loader.handle)
        with patch("capture_progress.win32gui.ShowWindow", wraps=win32gui.ShowWindow) as show:
            for language in ("pl", "en"):
                loader.ui.set_language(language)
                for _ in range(3):
                    with loader.capture_frame():
                        with loader.capture_frame():
                            loader.set_message("Łączę fragmenty…")
                            self.assertTrue(win32gui.IsWindowVisible(loader.handle))
                loader.window.update_idletasks()
                for label in (loader.capture_hint, loader.elapsed):
                    self.assertLessEqual(label.winfo_rootx() + label.winfo_width(),
                                         loader.window.winfo_rootx() + loader.window.winfo_width())
                    self.assertLessEqual(label.winfo_rooty() + label.winfo_height(),
                                         loader.window.winfo_rooty() + loader.window.winfo_height())
            show.assert_not_called()
        folder = __import__("pathlib").Path("build/progress-review")
        folder.mkdir(parents=True, exist_ok=True)
        from PIL import ImageGrab
        ImageGrab.grab(bbox=win32gui.GetWindowRect(loader.handle), all_screens=True).save(folder / "steady-strip-1.1.16.png")

    def test_fullscreen_fallback_hides_once_and_never_reappears_between_frames(self):
        rect = (100, 100, 450, 250)
        with patch("capture_progress.progress_placement", return_value=(rect, False, False)):
            loader = CaptureProgress(self.root, (0, 0, 1000, 800))
        self.addCleanup(loader.close)
        with patch("capture_progress.win32gui.ShowWindow", wraps=win32gui.ShowWindow) as show:
            for _ in range(4):
                with loader.capture_frame():
                    with loader.capture_frame():
                        self.assertFalse(win32gui.IsWindowVisible(loader.handle))
            self.assertEqual(show.call_args_list, [call(loader.handle, win32con.SW_HIDE)])


if __name__ == "__main__":
    unittest.main()
