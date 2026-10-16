"""Regression for a desktop-sized page exceeding the former 60 MP limit."""
import json
from pathlib import Path
import time
import unittest

from PIL import Image, ImageChops, ImageDraw, ImageStat

from scroll_capture import ScrollingCapture
from test_scroll_capture import FakeScrollDriver


class LargeScrollTests(unittest.TestCase):
    def test_71_megapixel_page_is_complete_scaled_and_saved_as_one_png(self):
        document = Image.new("RGB", (2736, 26000))
        draw = ImageDraw.Draw(document)
        for y in range(document.height):
            draw.line((0, y, document.width - 1, y), fill=(y % 251, y // 251, 70))
        for index in range(260):
            draw.text((40, index * 100 + 10), f"Ogloszenie {index:04d} - pelny zrzut", fill="white")
        driver = FakeScrollDriver(document, viewport=(2736, 1664), position=(0, 4500))
        engine = ScrollingCapture(driver)
        started = time.perf_counter()
        result = engine.capture()
        try:
            self.assertIsNone(engine.incomplete_reason)
            self.assertEqual(result.info["capture_original_size"], document.size)
            self.assertEqual(result.size, (1539, 14625))
            self.assertLessEqual(result.width * result.height, 24_000_000)
            self.assertFalse(hasattr(result, "_capture_backing"))
            sx, sy = result.width / document.width, result.height / document.height
            for y in (0, 37, 700, 1660, 5000, 13970, 24000, 25900):
                top = max(3, round(y * sy))
                bottom = min(result.height - 3, top + 56)
                box = (result.width // 3, top, result.width * 2 // 3, bottom)
                tile = result.crop(box)
                extent = (box[0] / sx, top / sy, box[2] / sx, bottom / sy)
                expected = document.transform(tile.size, Image.Transform.EXTENT, extent, Image.Resampling.BILINEAR)
                error = ImageStat.Stat(ImageChops.difference(tile, expected)).mean
                self.assertLess(max(error), 5, "Scaled content was skipped or duplicated")
            first_forward = next(i for i, event in enumerate(driver.events) if event[1] > 0)
            self.assertTrue(all(event[1] > 0 for event in driver.events[first_forward:]))
            self.assertLess(engine.frame_count, 60)
            folder = Path("build/scroll-performance")
            folder.mkdir(parents=True, exist_ok=True)
            result.save(folder / "large-scaled.png")
            with Image.open(folder / "large-scaled.png") as saved:
                self.assertEqual(saved.size, result.size)
            report = {"source_size": document.size, "size": result.size,
                      "source_megapixels": document.width * document.height / 1_000_000,
                      "megapixels": result.width * result.height / 1_000_000,
                      "scale": result.info["capture_scale"],
                      "pixel_reduction_percent": 100 * (1 - result.width * result.height / (document.width * document.height)),
                      "frames": engine.frame_count, "capture_and_save_seconds": time.perf_counter() - started,
                      "complete": engine.incomplete_reason is None}
            (folder / "large-scaled.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        finally:
            result.close()
            document.close()


if __name__ == "__main__":
    unittest.main()
