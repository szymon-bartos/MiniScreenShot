"""Downscaling must preserve the complete capture and its tile boundaries."""
import tempfile
from pathlib import Path
import unittest

from PIL import Image, ImageChops, ImageStat

from capture_store import CaptureStore
from scroll_capture import ScrollingCapture
from test_scroll_capture import FakeScrollDriver


def patterned_image(width, height):
    red = Image.frombytes("L", (width, 1), bytes((x * 31) % 180 for x in range(width))).resize((width, height), Image.Resampling.NEAREST)
    green = Image.frombytes("L", (1, height), bytes((y * 31) % 180 for y in range(height))).resize((width, height), Image.Resampling.NEAREST)
    return Image.merge("RGB", (red, green, Image.new("L", (width, height), 70)))


class CaptureScalingTests(unittest.TestCase):
    def test_normal_image_keeps_its_resolution_and_pixels(self):
        image = patterned_image(240, 180)
        with CaptureStore() as store:
            store.add(image, 0, 0, *image.size)
            result = store.assemble((0, 0, *image.size))
        self.assertEqual(result.size, image.size)
        self.assertIsNone(ImageChops.difference(result, image).getbbox())
        self.assertNotIn("capture_scale", result.info)

    def test_existing_and_new_frames_can_have_different_scales_without_gaps(self):
        document = patterned_image(240, 1100)
        with CaptureStore(max_output_pixels=80_000) as store:
            previous = 0
            for y in (0, 140, 280, 420, 560, 700, 840, 920):
                frame = document.crop((0, y, 240, y + 180))
                store.add(frame, 0, y, 240, y - previous if y else 180)
                previous = y
            self.assertEqual(store.frames[0].size, (240, 180))
            self.assertLess(store.frames[-1].size[0], 240)
            result = store.assemble((0, 0, 240, 180))
        self.assert_complete_scaled_image(result, document.size, 80_000)
        self.assertEqual(result.getchannel("B").getextrema(), (70, 70))

    def assert_complete_scaled_image(self, result, source_size, budget):
        self.assertEqual(result.info["capture_original_size"], source_size)
        self.assertLessEqual(result.width * result.height, budget)
        self.assertLess(result.info["capture_scale"], 1)
        self.assertAlmostEqual(result.width / source_size[0], result.height / source_size[1], delta=0.01)

    def test_scrolling_scales_vertical_horizontal_and_grid_captures(self):
        for size, vertical, horizontal in (((240, 1100), True, False), ((1100, 180), False, True), ((610, 520), True, True)):
            with self.subTest(size=size):
                document = patterned_image(*size)
                engine = ScrollingCapture(FakeScrollDriver(document), vertical=vertical, horizontal=horizontal,
                                          max_output_pixels=80_000)
                result = engine.capture()
                self.assertIsNone(engine.incomplete_reason)
                self.assert_complete_scaled_image(result, size, 80_000)
                # White/black unwritten bands or blended fixed window borders
                # must not appear between scaled tiles.
                blue = result.crop((4, 4, result.width - 4, result.height - 4)).getchannel("B")
                low, high = blue.getextrema()
                self.assertGreaterEqual(low, 68)
                self.assertLessEqual(high, 72)

    def test_scaled_disk_backed_image_saves_reduced_png(self):
        image = patterned_image(400, 300)
        with CaptureStore(memory_pixels=1000, max_output_pixels=50_000) as store:
            store.add(image, 0, 0, *image.size)
            result = store.assemble((0, 0, *image.size))
        try:
            self.assertTrue(hasattr(result, "_capture_backing"))
            self.assert_complete_scaled_image(result, image.size, 50_000)
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "scaled.png"
                result.save(path)
                with Image.open(path) as saved:
                    self.assertEqual(saved.size, result.size)
        finally:
            result.close()

    def test_explicit_full_resolution_remains_available_to_engine(self):
        image = patterned_image(400, 300)
        with CaptureStore(memory_pixels=1000, max_output_pixels=None) as store:
            store.add(image, 0, 0, *image.size)
            result = store.assemble((0, 0, *image.size))
        try:
            self.assertEqual(result.size, image.size)
            self.assertIsNone(ImageChops.difference(result.convert("RGB"), image).getbbox())
        finally:
            result.close()
