import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

from scroll_capture import ScrollingCapture, ScrollCaptureError, estimate_shift


def document_image(width, height):
    randomizer = random.Random(23)
    return Image.frombytes("RGB", (width, height), randomizer.randbytes(width * height * 3))


def lead_table_image(width=720, rows=48, row_height=28):
    """Mostly identical grid cells; only lead identifiers change between rows."""
    document = Image.new("RGB", (width, rows * row_height), "white")
    draw = ImageDraw.Draw(document)
    for row in range(rows):
        y = row * row_height
        draw.line((0, y + row_height - 1, width, y + row_height - 1), fill="#d1d5db")
        draw.text((12, y + 7), f"LEAD {row:04d}", fill="#17243b")
        draw.text((190, y + 7), "Nowy kontakt", fill="#17243b")
        draw.text((400, y + 7), "Oczekuje", fill="#17243b")
        draw.text((610, y + 7), f"ID {row * 173 + 41:05d}", fill="#17243b")
    for x in (175, 385, 595):
        draw.line((x, 0, x, document.height), fill="#d1d5db")
    draw.rectangle((0, 0, width - 1, 1), fill="#f20179")
    draw.rectangle((0, document.height - 2, width - 1, document.height - 1), fill="#01def4")
    return document


class FakeScrollDriver:
    def __init__(self, document, viewport=(240, 180), position=(0, 0), native=True, blink=False):
        self.document, self.viewport = document, viewport
        self.x, self.y = position
        self.native, self.blink = native, blink
        self.events = []
        self.snapshots = 0

    def at_edge(self, axis, direction):
        if not self.native:
            return None
        position = self.x if axis == "x" else self.y
        maximum = max(0, (self.document.width - self.viewport[0]) if axis == "x" else (self.document.height - self.viewport[1]))
        return position == 0 if direction < 0 else position == maximum

    def scroll(self, axis, direction, units):
        self.events.append((axis, direction, units))
        if axis == "x":
            self.x = max(0, min(self.document.width - self.viewport[0], self.x + direction * units * 37))
        else:
            self.y = max(0, min(self.document.height - self.viewport[1], self.y + direction * units * 37))

    def snapshot(self):
        self.snapshots += 1
        frame = Image.new("RGB", (self.viewport[0] + 32, self.viewport[1] + 64), "#17243b")
        drawing = ImageDraw.Draw(frame)
        drawing.text((18, 10), "FIXED HEADER", fill="white")
        drawing.text((18, frame.height - 18), "FIXED FOOTER", fill="white")
        frame.paste(self.document.crop((self.x, self.y, self.x + self.viewport[0], self.y + self.viewport[1])), (16, 40))
        if self.blink:
            frame.putpixel((7, 7), (255, 255, 255) if self.snapshots % 2 else (0, 0, 0))
        return frame


class ScrollCaptureTests(unittest.TestCase):
    def assert_same_image(self, first, second):
        self.assertEqual(first.size, second.size)
        self.assertIsNone(ImageChops.difference(first, second).getbbox())

    def test_vertical_capture_finds_both_ends_and_removes_all_overlaps(self):
        document = document_image(240, 509)
        driver = FakeScrollDriver(document, position=(0, 143))
        stages = []
        result = ScrollingCapture(driver, progress=stages.append).capture()
        self.assert_same_image(result, document)
        self.assertTrue(driver.at_edge("y", 1))
        self.assertTrue(any(stage.startswith("Przechwycono fragment") for stage in stages))
        first_forward = next(index for index, event in enumerate(driver.events) if event[1] > 0)
        self.assertTrue(all(direction > 0 for _, direction, _ in driver.events[first_forward:]))

    def test_narrow_crm_panel_scrolls_inside_mostly_fixed_interface(self):
        document = document_image(50, 900)
        driver = FakeScrollDriver(document, viewport=(50, 400), native=False)
        fixed = document_image(900, 600)
        def snapshot():
            driver.snapshots += 1
            frame = fixed.copy()
            frame.paste(document.crop((0, driver.y, 50, driver.y + 400)), (425, 100))
            return frame
        driver.snapshot = snapshot
        engine = ScrollingCapture(driver)
        result = engine.capture()
        self.assertIsNone(engine.incomplete_reason)
        self.assertGreater(engine.frame_count, 1)
        self.assert_same_image(result, document)

    def test_shallow_horizontal_panel_scrolls_inside_fixed_interface(self):
        document = document_image(1200, 36)
        driver = FakeScrollDriver(document, viewport=(600, 36), native=False)
        fixed = document_image(900, 600)
        def snapshot():
            driver.snapshots += 1
            frame = fixed.copy()
            frame.paste(document.crop((driver.x, 0, driver.x + 600, 36)), (150, 280))
            return frame
        driver.snapshot = snapshot
        engine = ScrollingCapture(driver, vertical=False, horizontal=True)
        result = engine.capture()
        self.assertIsNone(engine.incomplete_reason)
        self.assertGreater(engine.frame_count, 1)
        self.assert_same_image(result, document)

    def test_sparse_erp_lead_table_is_captured_when_panel_is_below_window_center(self):
        document = lead_table_image()
        driver = FakeScrollDriver(document, viewport=(720, 224), native=False)
        fixed = document_image(1100, 760)
        def snapshot():
            driver.snapshots += 1
            frame = fixed.copy()
            frame.paste(document.crop((0, driver.y, 720, driver.y + 224)), (300, 440))
            return frame
        driver.snapshot = snapshot
        engine = ScrollingCapture(driver)
        result = engine.capture()
        self.assertIsNone(engine.incomplete_reason)
        self.assertGreater(engine.frame_count, 1)
        self.assert_same_image(result, document)

    def test_sparse_erp_rows_are_not_confused_with_unchanged_grid(self):
        document = lead_table_image()
        first = document.crop((0, 56, 720, 392))
        second = document.crop((0, 140, 720, 476))
        self.assertEqual(estimate_shift(first, second, "y"), 84)
        self.assertEqual(estimate_shift(first, first, "y"), 0)

    def test_seek_start_does_not_stop_on_nonoverlapping_inner_panel_pages(self):
        document = document_image(50, 12000)
        driver = FakeScrollDriver(document, viewport=(50, 400), position=(0, 9000), native=False)
        fixed = document_image(900, 600)
        def snapshot():
            frame = fixed.copy()
            frame.paste(document.crop((0, driver.y, 50, driver.y + 400)), (425, 100))
            return frame
        driver.snapshot = snapshot
        ScrollingCapture(driver)._seek_start("y")
        self.assertEqual(driver.y, 0)

    def test_window_toolbar_is_kept_once_above_complete_content(self):
        document = document_image(240, 509)
        driver = FakeScrollDriver(document)
        first = driver.snapshot()
        engine = ScrollingCapture(driver, include_window_frame=True)
        result = engine.capture()
        self.assertEqual(result.size, (272, 573))
        self.assertEqual(result.info["capture_content_box"], (16, 40, 256, 549))
        self.assert_same_image(result.crop((16, 40, 256, 549)), document)
        self.assert_same_image(result.crop((0, 0, 272, 40)), first.crop((0, 0, 272, 40)))

    def test_window_frame_survives_horizontal_and_vertical_stitching(self):
        document = document_image(419, 509)
        driver = FakeScrollDriver(document)
        first = driver.snapshot()
        engine = ScrollingCapture(driver, vertical=True, horizontal=True, include_window_frame=True)
        result = engine.capture()
        self.assertEqual(result.size, (451, 573))
        self.assert_same_image(result.crop(result.info["capture_content_box"]), document)
        self.assert_same_image(result.crop((0, 0, 272, 40)), first.crop((0, 0, 272, 40)))

    def test_horizontal_capture_grows_width_instead_of_stacking_vertically(self):
        document = document_image(607, 180)
        driver = FakeScrollDriver(document, position=(150, 0))
        result = ScrollingCapture(driver, vertical=False, horizontal=True).capture()
        self.assert_same_image(result, document)
        self.assertEqual({axis for axis, _direction, _units in driver.events}, {"x"})

    def test_two_axis_capture_covers_corners_as_a_grid(self):
        document = document_image(419, 333)
        driver = FakeScrollDriver(document, position=(80, 50))
        result = ScrollingCapture(driver, vertical=True, horizontal=True).capture()
        self.assert_same_image(result, document)

    def test_long_document_uses_fewer_frames_without_losing_pixels(self):
        document = document_image(240, 1800)
        driver = FakeScrollDriver(document)
        result = ScrollingCapture(driver).capture()
        self.assert_same_image(result, document)
        self.assertLess(driver.snapshots, 35)

    def test_fast_wheel_calibration_scales_hints_to_the_smaller_final_step(self):
        document = document_image(240, 1800)
        driver = FakeScrollDriver(document, viewport=(240, 675))
        original_scroll = driver.scroll
        driver.scroll = lambda axis, direction, units: original_scroll(axis, direction, units * 3)
        hints = []
        def match(first, second, axis, expected=None):
            hints.append(expected)
            return estimate_shift(first, second, axis, expected)
        with patch("scroll_capture.estimate_shift", side_effect=match):
            result = ScrollingCapture(driver).capture()
        self.assert_same_image(result, document)
        self.assertEqual(hints[2], 222)

    def test_vertical_capture_keeps_original_horizontal_position(self):
        document = document_image(510, 420)
        driver = FakeScrollDriver(document, position=(93, 70))
        result = ScrollingCapture(driver, vertical=True, horizontal=False).capture()
        self.assert_same_image(result, document.crop((93, 0, 333, 420)))

    def test_unknown_scrollbar_bounds_stop_after_unchanged_frames(self):
        document = document_image(240, 407)
        driver = FakeScrollDriver(document, position=(0, 100), native=False)
        result = ScrollingCapture(driver).capture()
        self.assert_same_image(result, document)

    def test_non_scrollable_window_returns_one_unchanged_frame(self):
        driver = FakeScrollDriver(document_image(240, 180))
        expected = driver.snapshot()
        result = ScrollingCapture(driver, horizontal=True).capture()
        self.assert_same_image(result, expected)

    def test_fixed_header_and_blinking_caret_are_not_repeated(self):
        document = document_image(240, 375)
        driver = FakeScrollDriver(document, blink=True)
        result = ScrollingCapture(driver).capture()
        self.assert_same_image(result, document)

    def test_step_limit_returns_captured_content_and_explicit_partial_reason(self):
        driver = FakeScrollDriver(document_image(240, 1500))
        engine = ScrollingCapture(driver, max_steps=3)
        result = engine.capture()
        self.assertIn("limit", engine.incomplete_reason)
        self.assertGreater(result.height, 180)
        self.assert_same_image(result, driver.document.crop((0, 0, result.width, result.height)))

    def test_large_result_uses_disk_backing_and_preserves_full_resolution(self):
        driver = FakeScrollDriver(document_image(240, 500))
        result = ScrollingCapture(driver, max_pixels=1000).capture()
        self.assert_same_image(result.convert("RGB"), driver.document)
        backing = Path(result._capture_backing.directory.name)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "large.png"
            result.save(path)
            with Image.open(path) as saved:
                self.assert_same_image(saved.convert("RGB"), driver.document)
        result.close()
        self.assertFalse(backing.exists())

    def test_changed_content_does_not_produce_an_invented_match(self):
        first, second = document_image(300, 200), Image.new("RGB", (300, 200), "white")
        with self.assertRaises(ScrollCaptureError):
            estimate_shift(first, second, "y")

    def test_registration_measures_partial_last_step_exactly(self):
        document = document_image(240, 400)
        first = document.crop((0, 0, 240, 180))
        second = document.crop((0, 17, 240, 197))
        self.assertEqual(estimate_shift(first, second, "y", expected=37), 17)

    def test_blocked_scroll_keeps_visible_image_and_marks_it_incomplete(self):
        driver = FakeScrollDriver(Image.new("RGB", (240, 500), "white"))
        expected = driver.snapshot()
        engine = ScrollingCapture(driver)
        result = engine.capture()
        self.assertTrue(engine.incomplete_reason)
        self.assert_same_image(result, expected)

    def test_content_growing_after_boundary_scan_does_not_return_a_truncated_image(self):
        driver = FakeScrollDriver(document_image(240, 375))
        def progress(message):
            if message.startswith("Przechwycono fragment 3 "):
                expanded = document_image(240, 440)
                expanded.paste(driver.document, (0, 0))
                driver.document = expanded
        result = ScrollingCapture(driver, progress=progress).capture()
        self.assert_same_image(result, driver.document)

    def test_fuzzy_registration_tolerates_redrawn_pixels_in_both_axes(self):
        document = document_image(460, 500).filter(ImageFilter.GaussianBlur(0.7))
        for axis in ("x", "y"):
            first = document.crop((0, 0, 300, 260))
            second = document.crop((53, 0, 353, 260) if axis == "x" else (0, 53, 300, 313))
            second = ImageEnhance.Brightness(second).enhance(1.06).filter(ImageFilter.GaussianBlur(0.25))
            self.assertLessEqual(abs(estimate_shift(first, second, axis) - 53), 1)

    def test_capture_measures_each_step_when_wheel_speed_changes_after_scan(self):
        driver = FakeScrollDriver(document_image(240, 603))
        original = driver.scroll
        def progress(message):
            if message.startswith("Przechwycono fragment 3 "):
                driver.scroll = lambda axis, direction, units: original(axis, direction, units * 2 if direction > 0 else units)
        result = ScrollingCapture(driver, progress=progress).capture()
        self.assert_same_image(result, driver.document)

    def test_local_animation_does_not_hide_the_end_of_the_page(self):
        driver = FakeScrollDriver(document_image(240, 407), native=False)
        original = driver.snapshot
        def animated_snapshot():
            frame = original()
            ImageDraw.Draw(frame).rectangle((20, 46, 55, 72), fill="red" if driver.snapshots % 2 else "blue")
            return frame
        driver.snapshot = animated_snapshot
        result = ScrollingCapture(driver).capture()
        self.assertEqual(result.size, driver.document.size)

    def test_weak_alignment_keeps_content_with_small_overlap_instead_of_aborting(self):
        driver = FakeScrollDriver(document_image(240, 407))
        assembling = False
        failed = 0
        def progress(message):
            nonlocal assembling
            if message.startswith("Przechwycono fragment 3 "):
                assembling = True
        def redraw(first, second, axis, expected=None):
            nonlocal failed
            if assembling and failed < 2:
                failed += 1
                raise ScrollCaptureError("Simulated transient redraw")
            return estimate_shift(first, second, axis, expected)
        engine = ScrollingCapture(driver, progress=progress)
        with patch("scroll_capture.estimate_shift", side_effect=redraw):
            result = engine.capture()
        self.assertTrue(engine.approximate)
        self.assertEqual(result.height, driver.document.height + 2)
        self.assert_same_image(result.crop((0, result.height - 100, result.width, result.height)),
                               driver.document.crop((0, driver.document.height - 100, driver.document.width, driver.document.height)))

    def test_large_animated_ad_does_not_invent_more_rows_at_the_bottom(self):
        document = document_image(240, 700)
        driver = FakeScrollDriver(document, native=False)
        original_snapshot = driver.snapshot
        def animated_snapshot():
            frame = original_snapshot()
            draw = ImageDraw.Draw(frame)
            for row in range(18):
                color = (240, 20, 40) if (row + driver.snapshots) % 2 else (10, 70, 245)
                draw.rectangle((16, 40 + row * 10, 105, 49 + row * 10), fill=color)
            return frame
        driver.snapshot = animated_snapshot
        engine = ScrollingCapture(driver)
        result = engine.capture()
        self.assertIsNone(engine.incomplete_reason)
        self.assertEqual(result.height, document.height)
        self.assert_same_image(result.crop((150, 0, 240, result.height)), document.crop((150, 0, 240, document.height)))

    def test_unmatchable_redraw_preserves_all_previously_captured_rows(self):
        document = document_image(240, 700)
        driver = FakeScrollDriver(document)
        original_snapshot = driver.snapshot
        driver.snapshot = lambda: Image.new("RGB", (272, 244), "white") if driver.y > 100 else original_snapshot()
        engine = ScrollingCapture(driver)
        result = engine.capture()
        self.assertTrue(engine.incomplete_reason)
        self.assertGreater(result.height, 180)
        self.assert_same_image(result, document.crop((0, 0, 240, result.height)))

    def test_browser_toolbar_redraw_is_not_added_to_scrolling_document(self):
        document = document_image(240, 700)
        driver = FakeScrollDriver(document)
        original = driver.snapshot
        def snapshot():
            frame = original()
            if driver.y >= 74:
                ImageDraw.Draw(frame).rectangle((8, 12, 264, 30), fill="white" if driver.snapshots % 2 else "#718bad")
            return frame
        driver.snapshot = snapshot
        result = ScrollingCapture(driver).capture()
        self.assert_same_image(result, document)

    def test_source_closing_does_not_discard_captured_rows_during_assembly(self):
        document = document_image(240, 700)
        driver = FakeScrollDriver(document)
        original_snapshot = driver.snapshot
        def snapshot():
            if driver.y > 100:
                raise ScrollCaptureError("Okno zostało zamknięte.")
            return original_snapshot()
        driver.snapshot = snapshot
        driver._check = Mock(side_effect=ScrollCaptureError("Okno zostało zamknięte."))
        driver.check_cancelled = Mock()
        engine = ScrollingCapture(driver)
        result = engine.capture()
        self.assertIn("zamknięte", engine.incomplete_reason)
        self.assert_same_image(result, document.crop((0, 0, 240, result.height)))
        driver.check_cancelled.assert_called()

    def test_realistic_text_document_matches_without_repeating_lines(self):
        document = Image.new("RGB", (240, 900), "#f8fafc")
        draw = ImageDraw.Draw(document)
        for row in range(36):
            draw.text((16, row * 24 + 8), f"{row:03d}  Report row with text", fill="#111827")
            draw.rectangle((190, row * 24 + 8, 220, row * 24 + 17), fill=(row * 7, 90, 130))
        driver = FakeScrollDriver(document)
        engine = ScrollingCapture(driver)
        result = engine.capture()
        left, top, _, _ = engine.viewport
        self.assertEqual(result.height, document.height)
        self.assert_same_image(result, document.crop((left - 16, top - 40, left - 16 + result.width, top - 40 + result.height)))


if __name__ == "__main__":
    unittest.main()
