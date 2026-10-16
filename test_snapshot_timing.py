"""The fast path must still wait for delayed or smoothly animated wheel input."""
import unittest
from unittest.mock import Mock, patch

from PIL import Image
from scroll_capture import CaptureCancelled
from windows_scroll import WindowsScrollDriver, render_stable
from test_scroll_capture import lead_table_image


class SnapshotTimingTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.white = Image.new("RGB", (120, 100), "white")
        self.black = Image.new("RGB", (120, 100), "black")
        self.driver = WindowsScrollDriver.__new__(WindowsScrollDriver)
        self.driver._browser = False
        self.driver._scroll_time = 0.0
        self.driver._last_frame = self.white
        self.driver._check = Mock()
        self.driver._grab = lambda: self.black
        for target, replacement in (("windows_scroll.time.monotonic", lambda: self.now),
                                     ("windows_scroll.time.sleep", self.advance)):
            patcher = patch(target, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)

    def advance(self, delay):
        self.now += delay

    def test_instant_render_does_not_wait_for_fixed_quarter_second_delay(self):
        self.assertIs(self.driver.snapshot(), self.black)
        self.assertLess(self.now, 0.12)

    def test_delayed_wheel_input_is_not_mistaken_for_end_of_document(self):
        self.driver._grab = lambda: self.white if self.now < 0.12 else self.black
        self.assertIs(self.driver.snapshot(), self.black)
        self.assertGreaterEqual(self.now, 0.16)

    def test_browser_smooth_scroll_is_allowed_to_finish(self):
        self.driver._browser = True
        self.driver._grab = lambda: Image.new("RGB", (120, 100), int(min(0.3, self.now) * 700)) if self.now < 0.3 else self.black
        self.assertIs(self.driver.snapshot(), self.black)
        self.assertGreaterEqual(self.now, 0.34)

    def test_browser_waits_for_wheel_render_delayed_by_busy_page(self):
        self.driver._browser = True
        self.driver._grab = lambda: self.white if self.now < 0.45 else self.black
        self.assertIs(self.driver.snapshot(), self.black)
        self.assertGreaterEqual(self.now, 0.5)

    def test_busy_browser_does_not_finish_during_short_render_pause(self):
        self.driver._browser = True
        intermediate = Image.new("RGB", (120, 100), "gray")
        self.driver._grab = lambda: self.white if self.now < 0.10 else (intermediate if self.now < 0.18 else self.black)
        self.assertIs(self.driver.snapshot(), self.black)
        self.assertGreaterEqual(self.now, 0.25)

    def test_escape_remains_responsive_while_waiting_for_render(self):
        self.driver._check.side_effect = [None, CaptureCancelled("Esc")]
        with self.assertRaises(CaptureCancelled):
            self.driver.snapshot()
        self.assertLess(self.now, 0.06)

    def test_sparse_lead_rows_are_not_treated_as_finished_smooth_scroll(self):
        table = lead_table_image()
        first = table.crop((0, 56, 720, 392))
        second = table.crop((0, 61, 720, 397))
        self.assertFalse(render_stable(first, second))

    def test_instant_sparse_table_render_skips_the_unchanged_browser_timeout(self):
        self.driver._browser = True
        table = lead_table_image()
        self.driver._last_frame = table.crop((0, 56, 720, 392))
        final = table.crop((0, 140, 720, 476))
        self.driver._grab = lambda: final
        self.assertIs(self.driver.snapshot(), final)
        self.assertLess(self.now, 0.2)


if __name__ == "__main__":
    unittest.main()
