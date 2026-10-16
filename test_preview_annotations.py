"""Drawing, crop, export and layout checks in the real screenshot preview."""
import io
import tempfile
from pathlib import Path
import unittest
from unittest.mock import DEFAULT, patch

from PIL import Image, ImageChops

import test_preview_layout as preview_tests


class PreviewAnnotationTests(unittest.TestCase):
    setUp = preview_tests.PreviewLayoutTests.setUp
    tearDown = preview_tests.PreviewLayoutTests.tearDown
    settle = preview_tests.PreviewLayoutTests.settle
    resize = preview_tests.PreviewLayoutTests.resize
    crop_event = preview_tests.PreviewLayoutTests.crop_event
    assert_controls_visible = preview_tests.PreviewLayoutTests.assert_controls_visible
    save_review_image = preview_tests.PreviewLayoutTests.save_review_image

    def draw_stroke(self, start, end):
        self.crop_event("<ButtonPress-1>", *start)
        self.crop_event("<B1-Motion>", *end)
        self.crop_event("<ButtonRelease-1>", *end)
        self.settle()

    def assert_red_near(self, image, point):
        x, y = point
        self.assertIn((239, 68, 68), [image.getpixel((x + dx, y + dy))
                                    for dx in range(-3, 4) for dy in range(-3, 4)])

    def test_pencil_draws_live_in_same_window_then_changes_image_pixels(self):
        windows = self.root.winfo_children()
        self.preview.pen_btn.invoke()
        self.settle()
        self.crop_event("<ButtonPress-1>", 300, 250)
        self.crop_event("<B1-Motion>", 1000, 250)
        self.settle()
        self.assertTrue(self.preview.canvas.find_withtag("annotation_live"))
        self.assertEqual(self.preview.display_image.getpixel((600, 250)), self.image.getpixel((600, 250)))
        self.crop_event("<ButtonRelease-1>", 1000, 250)
        self.settle()
        self.assert_red_near(self.preview.display_image, (600, 250))
        self.assertFalse(self.preview.canvas.find_withtag("annotation_live"))
        self.assertEqual(windows, self.root.winfo_children())
        self.assertTrue(self.preview.undo_btn.instate(["!disabled"]))
        self.assertEqual(self.preview.display_image.size, self.image.size)

    def test_marker_is_transparent_and_undo_restores_original_pixels(self):
        self.preview.marker_btn.invoke()
        self.settle()
        self.assertEqual(self.preview.color_var.get(), "Żółty")
        original = self.preview.display_image.copy()
        self.draw_stroke((300, 250), (1000, 250))
        red, green, blue = self.preview.display_image.getpixel((600, 250))
        self.assertGreater(red, 240)
        self.assertGreater(green, 220)
        self.assertLess(blue, 200)
        self.assertGreater(blue, 100)
        self.preview.canvas.focus_force()
        self.root.update()
        self.preview.canvas.event_generate("<Control-z>")
        self.settle()
        self.assertIsNone(ImageChops.difference(self.preview.display_image, original).getbbox())
        self.assertTrue(self.preview.undo_btn.instate(["disabled"]))

    def test_color_width_and_tool_settings_are_independent(self):
        self.preview.pen_btn.invoke()
        self.preview.color_var.set("Niebieski")
        self.preview.brush_size_var.set("Gruba")
        self.preview.color_picker.event_generate("<<ComboboxSelected>>")
        self.draw_stroke((300, 250), (1000, 250))
        self.assertEqual(self.preview.display_image.getpixel((600, 250)), (59, 130, 246))
        self.preview.marker_btn.invoke()
        self.assertEqual(self.preview.color_var.get(), "Żółty")
        self.preview.pen_btn.invoke()
        self.assertEqual(self.preview.color_var.get(), "Niebieski")
        self.assertEqual(self.preview.brush_size_var.get(), "Gruba")

    def test_drawing_coordinates_survive_zoom_scroll_resize_and_crop(self):
        self.preview.actual_size_btn.invoke()
        self.resize(900, 760)
        self.preview.canvas.xview_moveto(0.25)
        self.preview.canvas.yview_moveto(0.1)
        self.preview.pen_btn.invoke()
        self.draw_stroke((500, 200), (750, 260))
        self.assert_red_near(self.preview.display_image, (625, 230))
        self.preview.fit_btn.invoke()
        self.resize(1100, 760)
        self.assert_red_near(self.preview.display_image, (625, 230))
        self.preview.crop_btn.invoke()
        self.settle()
        self.assertIsNone(self.preview.annotation_tool)
        self.assertTrue(self.preview.pen_btn.instate(["disabled"]))
        self.crop_event("<ButtonPress-1>", 450, 170)
        self.crop_event("<B1-Motion>", 800, 300)
        self.crop_event("<ButtonRelease-1>", 800, 300)
        self.preview.accept_btn.invoke()
        self.settle()
        self.assert_red_near(self.preview.display_image, (175, 60))
        self.assertFalse(self.preview.annotation_history.patches)
        self.assertTrue(self.preview.pen_btn.instate(["!disabled"]))

    def test_save_and_clipboard_include_annotations(self):
        self.preview.pen_btn.invoke()
        self.draw_stroke((300, 250), (1000, 250))
        annotated = self.preview.display_image.copy()
        with tempfile.TemporaryDirectory() as directory:
            with patch("app_advanced.CAPTURE_DIR", Path(directory)):
                self.preview.save_btn.invoke()
            files = list(Path(directory).glob("*.png"))
            self.assertEqual(len(files), 1)
            with Image.open(files[0]) as saved:
                self.assert_red_near(saved, (600, 250))
                self.assertIsNone(ImageChops.difference(saved, annotated).getbbox())
        self.preview = self.app._show_preview(annotated, "test", "Zrzut z oznaczeniami")
        self.settle()
        with patch.multiple("win32clipboard", OpenClipboard=DEFAULT, EmptyClipboard=DEFAULT,
                            SetClipboardData=DEFAULT, CloseClipboard=DEFAULT) as clipboard:
            self.preview.copy_btn.invoke()
        payload = clipboard["SetClipboardData"].call_args.args[1]
        with Image.open(io.BytesIO(payload)) as copied:
            self.assert_red_near(copied, (600, 250))

    def test_escape_cancels_current_stroke_and_narrow_toolbar_remains_usable(self):
        self.preview.marker_btn.invoke()
        self.resize(480, 600)
        self.assert_controls_visible()
        for control in (self.preview.pen_btn, self.preview.marker_btn, self.preview.undo_btn,
                        self.preview.color_picker, self.preview.brush_size_picker):
            self.assertTrue(control.winfo_ismapped())
            self.assertLessEqual(control.winfo_rootx() + control.winfo_width(),
                                 self.preview.winfo_rootx() + self.preview.winfo_width())
            self.assertLessEqual(control.winfo_rooty() + control.winfo_height(), self.preview.canvas.winfo_rooty())
        original = self.preview.display_image.copy()
        self.crop_event("<ButtonPress-1>", 300, 250)
        self.crop_event("<B1-Motion>", 1000, 250)
        self.preview.canvas.event_generate("<Escape>")
        self.settle()
        self.assertIsNone(self.preview.annotation_tool)
        self.assertIsNone(self.preview.annotation_stroke)
        self.assertFalse(self.preview.canvas.find_withtag("annotation_live"))
        self.assertIsNone(ImageChops.difference(self.preview.display_image, original).getbbox())
        self.save_review_image("preview-annotations-480.png")

    def test_large_scrolling_image_draws_only_visible_preview_and_small_undo_patch(self):
        self.preview.display_image = Image.new("RGB", (2000, 9000), "#345678")
        self.preview.actual_size_btn.invoke()
        self.resize(900, 760)
        canvas = self.preview.canvas
        canvas.yview_moveto(0.65)
        self.preview.pen_btn.invoke()
        self.settle()
        y = round(canvas.canvasy(0) + 50)
        self.draw_stroke((100, y), (400, y + 60))
        self.assert_red_near(self.preview.display_image, (250, y + 30))
        self.assertTrue(canvas.virtual_image)
        self.assertLessEqual(canvas.image.width(), canvas.winfo_width() + 3)
        self.assertLess(self.preview.annotation_history.bytes, 200_000)
        self.preview.undo_btn.invoke()
        self.settle()
        self.assertEqual(self.preview.display_image.getpixel((250, y + 30)), (52, 86, 120))


if __name__ == "__main__":
    unittest.main()
