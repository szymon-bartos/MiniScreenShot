"""Realistic fixed CRM chrome must not conceal motion in the content pane."""
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageChops, ImageDraw

from scroll_capture import ScrollingCapture
from test_scroll_capture import FakeScrollDriver, document_image


class BusyChromeDriver:
    capture_region = None

    def __init__(self):
        self.document = document_image(350, 2240)
        self.region = (820, 170, 1170, 670)
        self.background = document_image(1200, 800)
        self.y = 0
        self.snapshots = 0
        self.counter_box = (20, 20, 65, 65)
        self.status_bar = False

    def capture_bounds(self, axes):
        return None

    def at_edge(self, axis, direction):
        return None

    def scroll(self, axis, direction, units):
        self.y = max(0, min(self.document.height - 500, self.y + direction * units * 37))

    def snapshot(self):
        self.snapshots += 1
        frame = self.background.copy()
        frame.paste(self.document.crop((0, self.y, 350, self.y + 500)), self.region[:2])
        ImageDraw.Draw(frame).rectangle(self.counter_box, fill=tuple(self.snapshots * n % 255 for n in (47, 73, 113)))
        if self.status_bar:
            ImageDraw.Draw(frame).rectangle((10, 750, 1170, 780), fill=tuple(self.snapshots * n % 255 for n in (73, 47, 113)))
        return frame

    def set_content_region(self, region):
        pass


class AutomaticMotionTests(unittest.TestCase):
    def test_preserved_dark_sidebar_has_no_white_gap_below_it(self):
        for memory_pixels in (24_000_000, 1000):
            with self.subTest(memory_pixels=memory_pixels):
                driver = FakeScrollDriver(document_image(240, 900))
                engine = ScrollingCapture(driver, include_window_frame=True, max_pixels=memory_pixels)
                result = engine.capture()
                try:
                    self.assertEqual(result.getpixel((0, 400))[:3], (23, 36, 59))
                    content = result.crop(result.info["capture_content_box"]).convert("RGB")
                    self.assertEqual(content.size, driver.document.size)
                    self.assertIsNone(ImageChops.difference(content, driver.document).getbbox())
                finally:
                    result.close()

    def test_wide_changing_status_bar_does_not_join_unrelated_motion(self):
        driver = BusyChromeDriver()
        driver.status_bar = True
        engine = ScrollingCapture(driver, max_steps=70)
        result = engine.capture()
        self.addCleanup(result.close)
        self.assertIsNone(engine.incomplete_reason)
        self.assertEqual(result.size, driver.document.size)
        self.assertIsNone(ImageChops.difference(result, driver.document).getbbox())

    def test_counter_above_the_content_does_not_extend_the_saved_document(self):
        driver = BusyChromeDriver()
        driver.counter_box = (840, 20, 885, 65)
        engine = ScrollingCapture(driver, max_steps=70)
        result = engine.capture()
        self.addCleanup(result.close)
        self.assertIsNone(engine.incomplete_reason)
        self.assertEqual(result.size, driver.document.size)
        self.assertIsNone(ImageChops.difference(result, driver.document).getbbox())

    def test_capture_from_the_middle_finds_the_actual_first_row(self):
        driver = BusyChromeDriver()
        driver.y = 700
        engine = ScrollingCapture(driver, max_steps=70)
        result = engine.capture()
        self.addCleanup(result.close)
        self.assertIsNone(engine.incomplete_reason)
        self.assertEqual(result.size, driver.document.size)
        self.assertIsNone(ImageChops.difference(result, driver.document).getbbox())

    def test_the_same_disconnected_motion_is_handled_horizontally(self):
        class HorizontalDriver(BusyChromeDriver):
            def snapshot(self):
                return super().snapshot().transpose(Image.Transpose.TRANSPOSE)

        driver = HorizontalDriver()
        engine = ScrollingCapture(driver, vertical=False, horizontal=True, max_steps=70)
        result = engine.capture()
        self.addCleanup(result.close)
        self.assertIsNone(engine.incomplete_reason)
        expected = driver.document.transpose(Image.Transpose.TRANSPOSE)
        self.assertEqual(result.size, expected.size)
        self.assertIsNone(ImageChops.difference(result, expected).getbbox())

    def test_animated_header_and_fixed_sidebar_do_not_hide_a_scrolling_list(self):
        driver = BusyChromeDriver()
        engine = ScrollingCapture(driver, max_steps=70)
        result = engine.capture()
        self.addCleanup(result.close)
        self.assertIsNone(engine.incomplete_reason)
        self.assertGreater(engine.frame_count, 1, "The list scrolled but only its top was retained")
        self.assertEqual(result.size, driver.document.size)
        self.assertIsNone(ImageChops.difference(result, driver.document).getbbox())
        with tempfile.TemporaryDirectory() as folder:
            saved = Path(folder) / "all-records.png"
            result.save(saved)
            with Image.open(saved) as image:
                self.assertEqual(image.size, driver.document.size)
                self.assertIsNone(ImageChops.difference(image, driver.document).getbbox())


if __name__ == "__main__":
    unittest.main()
