"""Independent CRM panes must not contribute motion to the selected content."""
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageChops

from scroll_capture import ScrollingCapture
from test_scroll_capture import document_image


class IndependentPanelsDriver:
    capture_region = (520, 120, 760, 300)

    def __init__(self):
        self.document = document_image(240, 913)
        self.menu = document_image(440, 1000)
        self.y = 185
        self.x = 0
        self.snapshots = 0

    def at_edge(self, axis, direction):
        return None

    def scroll(self, axis, direction, units):
        if axis == "x":
            self.x = max(0, min(self.document.width - 240, self.x + direction * units * 37))
        else:
            self.y = max(0, min(self.document.height - 180, self.y + direction * units * 37))

    def snapshot(self):
        self.snapshots += 1
        frame = Image.new("RGB", (820, 440), "#182438")
        menu_y = self.snapshots * 37 % 560
        frame.paste(self.menu.crop((0, menu_y, 440, menu_y + 400)), (12, 30))
        frame.paste(self.document.crop((self.x, self.y, self.x + 240, self.y + 180)), (520, 120))
        return frame

    def capture_bounds(self, axes):
        return self.capture_region, None

    def set_content_region(self, region):
        pass


class IndependentPanelTests(unittest.TestCase):
    def test_selected_panel_preserves_horizontal_and_two_axis_content(self):
        for vertical in (False, True):
            with self.subTest(vertical=vertical):
                driver = IndependentPanelsDriver()
                driver.document = document_image(607, 613 if vertical else 180)
                driver.x, driver.y = 93, 185 if vertical else 0
                engine = ScrollingCapture(driver, vertical=vertical, horizontal=True, max_steps=40)
                result = engine.capture()
                try:
                    self.assertIsNone(engine.incomplete_reason)
                    self.assertEqual(result.size, driver.document.size)
                    self.assertIsNone(ImageChops.difference(result, driver.document).getbbox())
                finally:
                    result.close()

    def test_region_validation_rejects_coordinates_outside_the_window(self):
        from windows_scroll import validate_capture_region
        from scroll_capture import ScrollCaptureError
        self.assertEqual(validate_capture_region((2, 3, 90, 95), (100, 100)), (2, 3, 90, 95))
        self.assertIsNone(validate_capture_region(None, (100, 100)))
        for region in ((-1, 0, 90, 90), (0, 0, 101, 90), (0, 0, 31, 90), (0, 0, 90, 31),
                       (0, 0, 1), (0, 0, float("inf"), 90)):
            with self.subTest(region=region), self.assertRaises(ScrollCaptureError):
                validate_capture_region(region, (100, 100))

    def test_automatic_capture_does_not_expand_into_a_menu_that_starts_moving(self):
        class AutomaticDriver(IndependentPanelsDriver):
            capture_region = None

            def __init__(self):
                super().__init__()
                self.y = 0
                self.menu_active = False

            def snapshot(self):
                self.snapshots += 1
                self.menu_active = self.menu_active or self.y >= 74
                menu_y = self.snapshots * 37 % 560 if self.menu_active else 0
                frame = Image.new("RGB", (820, 440), "#182438")
                frame.paste(self.menu.crop((0, menu_y, 440, menu_y + 400)), (12, 30))
                frame.paste(self.document.crop((0, self.y, 240, self.y + 180)), (520, 120))
                return frame

            def capture_bounds(self, axes):
                return None

        driver = AutomaticDriver()
        engine = ScrollingCapture(driver, max_steps=40)
        result = engine.capture()
        self.addCleanup(result.close)
        self.assertIsNone(engine.incomplete_reason)
        self.assertEqual(result.size, driver.document.size)
        self.assertIsNone(ImageChops.difference(result, driver.document).getbbox())

    def test_selected_content_is_complete_and_saved_despite_independent_menu_motion(self):
        driver = IndependentPanelsDriver()
        engine = ScrollingCapture(driver, max_steps=40)
        result = engine.capture()
        self.addCleanup(result.close)
        self.assertIsNone(engine.incomplete_reason)
        self.assertEqual(result.size, driver.document.size)
        self.assertIsNone(ImageChops.difference(result, driver.document).getbbox())
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "crm.png"
            result.save(path)
            with Image.open(path) as saved:
                self.assertEqual(saved.size, driver.document.size)
                self.assertIsNone(ImageChops.difference(saved, driver.document).getbbox())


if __name__ == "__main__":
    unittest.main()
