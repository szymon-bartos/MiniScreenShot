"""Pixel and memory checks for the screenshot drawing tools."""
import tempfile
from pathlib import Path
import unittest

from PIL import Image, ImageChops

from capture_store import CaptureStore
from image_annotations import AnnotationHistory, Stroke


class ImageAnnotationTests(unittest.TestCase):
    def test_highlighter_is_transparent_and_does_not_darken_itself(self):
        image = Image.new("RGB", (200, 100), "white")
        image.putpixel((80, 50), (0, 0, 0))
        history = AnnotationHistory()
        history.apply(image, Stroke([(20, 50), (180, 50), (20, 50)], "#facc15", 24, 85))
        self.assertEqual(image.getpixel((100, 50)), (253, 238, 177))
        self.assertEqual(image.getpixel((80, 50)), (83, 68, 7))
        self.assertEqual(image.getpixel((100, 10)), (255, 255, 255))
        history.clear()

    def test_pencil_and_single_dot_are_opaque_and_clipped_to_image(self):
        image = Image.new("RGB", (100, 80), "white")
        history = AnnotationHistory()
        history.apply(image, Stroke([(0, 0), (99, 79)], "#ef4444", 6))
        self.assertEqual(image.getpixel((0, 0)), (239, 68, 68))
        self.assertEqual(image.getpixel((50, 40)), (239, 68, 68))
        history.apply(image, Stroke([(80, 10)], "#3b82f6", 12))
        self.assertEqual(image.getpixel((80, 10)), (59, 130, 246))
        self.assertEqual(image.getpixel((60, 10)), (255, 255, 255))
        history.clear()

    def test_undo_restores_exact_pixels_without_storing_full_screenshot(self):
        image = Image.new("RGB", (1000, 2600), "#18324a")
        original = image.copy()
        image.info["capture_scale"] = 0.75
        history = AnnotationHistory()
        history.apply(image, Stroke([(300, 2000), (500, 2020)], "#ef4444", 6))
        history.apply(image, Stroke([(400, 2000), (450, 2010)], "#facc15", 24, 85))
        self.assertLess(history.bytes, 100_000)
        self.assertTrue(history.undo(image))
        self.assertTrue(history.undo(image))
        self.assertFalse(history.undo(image))
        self.assertIsNone(ImageChops.difference(image, original).getbbox())
        self.assertEqual(image.info["capture_scale"], 0.75)

    def test_history_is_bounded_and_keeps_the_latest_action(self):
        image = Image.new("RGB", (200, 100), "white")
        history = AnnotationHistory(max_bytes=1000, max_steps=2)
        for y in (10, 30, 50, 70):
            history.apply(image, Stroke([(10, y), (180, y)], "#ef4444", 6))
        self.assertEqual(len(history.patches), 1)
        self.assertTrue(history.undo(image))
        self.assertEqual(image.getpixel((100, 70)), (255, 255, 255))
        self.assertEqual(image.getpixel((100, 50)), (239, 68, 68))
        self.assertEqual(history.bytes, 0)

    def test_mapped_capture_can_be_drawn_saved_and_undone_without_copying_it(self):
        source = Image.new("RGB", (400, 300), "white")
        with CaptureStore(memory_pixels=1000) as store:
            store.add(source, 0, 0, *source.size)
            image = store.assemble((0, 0, *source.size))
        backing = image._capture_backing
        history = AnnotationHistory()
        try:
            self.assertTrue(image.readonly)
            history.apply(image, Stroke([(30, 50), (200, 50)], "#ef4444", 6))
            self.assertTrue(image.readonly)
            self.assertIs(image._capture_backing, backing)
            self.assertEqual(image.getpixel((100, 50)), (239, 68, 68, 255))
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "annotated.png"
                image.save(path)
                with Image.open(path) as saved:
                    self.assertEqual(saved.getpixel((100, 50)), (239, 68, 68, 255))
            history.undo(image)
            self.assertEqual(image.getpixel((100, 50)), (255, 255, 255, 255))
            self.assertTrue(image.readonly)
        finally:
            history.clear()
            image.close()


if __name__ == "__main__":
    unittest.main()
