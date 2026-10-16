"""Integration checks for the real Tk preview; requires a Windows desktop."""

import ctypes
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageGrab

from app_advanced import ScreenCaptureApp, tk


class PreviewLayoutTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.callback_errors = []
        self.root.report_callback_exception = lambda *args: self.callback_errors.append(args)
        self.app = ScreenCaptureApp(self.root)
        self.image = Image.new("RGB", (1600, 900), "#6b91b3")
        drawing = ImageDraw.Draw(self.image)
        drawing.rounded_rectangle((120, 120, 1480, 780), radius=24, fill="#f8fafc")
        drawing.rectangle((120, 120, 1480, 220), fill="#cbd5e1")
        for row in range(4):
            drawing.rounded_rectangle((200, 290 + row * 100, 1400, 335 + row * 100), radius=12, fill="#dbe4ee")
        self.preview = self.app._show_preview(self.image, "test", "Pełny ekran — podgląd")
        self.settle()

    def tearDown(self):
        self.root.destroy()
        self.assertEqual(self.callback_errors, [])

    def settle(self):
        deadline = time.monotonic() + 3
        stable_since = time.monotonic()
        while time.monotonic() < deadline:
            self.root.update()
            if self.preview.render_job is not None or self.preview.layout_job is not None:
                stable_since = time.monotonic()
            elif time.monotonic() - stable_since >= 0.25:
                return
            time.sleep(0.01)
        self.fail("Preview layout did not settle within three seconds")

    def resize(self, width, height):
        self.preview.geometry(f"{width}x{height}+40+40")
        self.settle()

    def assert_controls_visible(self):
        preview = self.preview
        controls = [preview.save_btn, preview.copy_btn,
                    preview.zoom_out, preview.zoom_in, preview.zoom_slider,
                    preview.fit_btn, preview.actual_size_btn]
        if preview.pending_crop:
            controls += [preview.accept_btn, preview.reject_btn]
        else:
            controls += [preview.crop_btn]
        for control in controls:
            with self.subTest(control=str(control)):
                self.assertTrue(control.winfo_ismapped())
                self.assertGreaterEqual(control.winfo_rootx(), preview.winfo_rootx())
                self.assertLessEqual(control.winfo_rootx() + control.winfo_width(),
                                     preview.winfo_rootx() + preview.winfo_width())
                self.assertLessEqual(control.winfo_rooty() + control.winfo_height(),
                                     preview.canvas.winfo_rooty())
                self.assertGreaterEqual(control.winfo_width(), control.winfo_reqwidth())
        self.assertGreater(preview.canvas.winfo_width(), 100)
        self.assertGreater(preview.canvas.winfo_height(), 40)
        self.assertLessEqual(preview.canvas.winfo_rooty() + preview.canvas.winfo_height(),
                             preview.info_label.winfo_rooty())
        middle_x = preview.canvas.winfo_rootx() + preview.canvas.winfo_width() // 2
        middle_y = preview.canvas.winfo_rooty() + preview.canvas.winfo_height() // 2
        self.assertEqual(self.root.winfo_containing(middle_x, middle_y), preview.canvas)

    def test_toolbar_wraps_without_clipping(self):
        for width, height in ((480, 360), (640, 480), (900, 600), (1280, 800)):
            with self.subTest(size=(width, height)):
                self.resize(width, height)
                self.assert_controls_visible()
                if width in (480, 1280):
                    self.save_review_image(f"preview-{width}x{height}.png")

    def save_review_image(self, name):
        preview = self.preview
        destination = Path("build/preview-review")
        destination.mkdir(parents=True, exist_ok=True)
        data = {}
        for key, widget in (("window", preview), ("toolbar", preview.toolbar), ("canvas", preview.canvas), ("footer", preview.info_label)):
            data[key] = [widget.winfo_rootx(), widget.winfo_rooty(), widget.winfo_width(), widget.winfo_height()]
        data["image"] = [preview.canvas.image.width(), preview.canvas.image.height(), *preview.canvas.coords("image")]
        data["scaling"] = preview.tk.call("tk", "scaling")
        (destination / f"{name}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
        # Capture this test window only; its image is synthetic test data.
        ImageGrab.grab(bbox=(preview.winfo_rootx(), preview.winfo_rooty(),
                            preview.winfo_rootx() + preview.winfo_width(),
                            preview.winfo_rooty() + preview.winfo_height())).save(destination / name)

    def test_crop_confirmation_fits_in_narrow_window(self):
        self.preview.crop_btn.invoke()
        self.settle()
        self.drag_crop((100, 100), (700, 500))
        for width in (480, 640, 900):
            with self.subTest(width=width):
                self.resize(width, 480)
                self.assert_controls_visible()
                if width == 480:
                    self.save_review_image("preview-crop-480x480.png")

    def crop_event(self, name, source_x, source_y):
        canvas = self.preview.canvas
        left, top, right, bottom = self.app._crop_image_bounds(self.preview)
        x = left + source_x * (right - left) / self.preview.display_image.width - canvas.canvasx(0)
        y = top + source_y * (bottom - top) / self.preview.display_image.height - canvas.canvasy(0)
        canvas.event_generate(name, x=round(x), y=round(y))

    def drag_crop(self, start, end):
        self.crop_event("<ButtonPress-1>", *start)
        self.crop_event("<B1-Motion>", *end)
        self.crop_event("<ButtonRelease-1>", *end)

    def test_crop_draws_in_existing_window_then_enter_accepts(self):
        windows = [widget for widget in self.root.winfo_children() if isinstance(widget, tk.Toplevel)]
        self.preview.crop_btn.invoke()
        self.settle()
        self.assertEqual(windows, [widget for widget in self.root.winfo_children() if isinstance(widget, tk.Toplevel)])
        self.assertTrue(self.preview.crop_active)
        self.assertTrue(self.preview.accept_btn.instate(["disabled"]))
        self.drag_crop((200, 150), (1000, 650))
        self.assertEqual(self.preview.display_image.size, (1600, 900))
        self.assertTrue(self.preview.canvas.find_withtag("crop_overlay"))
        self.assertTrue(self.preview.accept_btn.instate(["!disabled"]))
        self.preview.canvas.focus_force()
        self.preview.canvas.event_generate("<Return>")
        self.settle()
        self.assertAlmostEqual(self.preview.display_image.width, 800, delta=4)
        self.assertAlmostEqual(self.preview.display_image.height, 500, delta=4)
        self.assertFalse(self.preview.crop_active)
        self.assertFalse(self.preview.canvas.find_withtag("crop_overlay"))

    def test_crop_can_move_resize_and_cancel_with_escape(self):
        original = self.preview.display_image
        self.preview.crop_btn.invoke()
        self.settle()
        self.drag_crop((200, 150), (1000, 650))
        initial = self.preview.pending_crop
        self.drag_crop((600, 400), (700, 450))
        moved = self.preview.pending_crop
        for actual, expected in zip(moved, (300, 200, 1100, 700)):
            self.assertAlmostEqual(actual, expected, delta=5)
        self.drag_crop((1100, 700), (1300, 800))
        self.assertGreater(self.preview.pending_crop[2], moved[2])
        self.assertGreater(self.preview.pending_crop[3], moved[3])
        self.assertNotEqual(initial, self.preview.pending_crop)
        self.preview.canvas.focus_force()
        self.preview.canvas.event_generate("<Escape>")
        self.settle()
        self.assertIs(self.preview.display_image, original)
        self.assertIsNone(self.preview.pending_crop)
        self.assertFalse(self.preview.crop_active)
        self.assertTrue(self.preview.save_btn.instate(["!disabled"]))

    def test_crop_coordinates_account_for_zoom_scroll_and_resize(self):
        self.preview.actual_size_btn.invoke()
        self.resize(900, 700)
        self.preview.crop_btn.invoke()
        self.settle()
        self.preview.canvas.xview_moveto(0.25)
        self.preview.canvas.yview_moveto(0.1)
        self.drag_crop((500, 250), (800, 500))
        for actual, expected in zip(self.preview.pending_crop, (500, 250, 800, 500)):
            self.assertAlmostEqual(actual, expected, delta=1)
        selected = self.preview.pending_crop
        self.preview.fit_btn.invoke()
        self.resize(1100, 720)
        self.assertEqual(self.preview.pending_crop, selected)
        self.assertTrue(self.preview.canvas.find_withtag("crop_overlay"))
        self.preview.accept_btn.invoke()
        self.settle()
        self.assertEqual(self.preview.display_image.size, (300, 250))

    def test_large_zoom_renders_visible_pixels_and_preserves_crop_coordinates(self):
        self.preview.display_image = Image.new("RGB", (2000, 9000), "#345678")
        self.preview.actual_size_btn.invoke()
        self.settle()
        canvas = self.preview.canvas
        self.assertTrue(canvas.virtual_image)
        self.assertLessEqual(canvas.image.width(), canvas.winfo_width() + 3)
        self.assertLessEqual(canvas.image.height(), canvas.winfo_height() + 3)
        self.preview.crop_btn.invoke()
        self.settle()
        canvas.yview_moveto(0.65)
        self.settle()
        self.assertGreater(canvas.coords("image")[1], 5000)
        self.assertEqual(self.app._crop_image_bounds(self.preview), (0, 0, 2000, 9000))
        y = round(canvas.canvasy(0) + 50)
        self.drag_crop((100, y), (400, y + 150))
        self.assertEqual(tuple(round(value) for value in self.preview.pending_crop), (100, y, 400, y + 150))

    def test_disk_backed_preview_keeps_original_and_releases_file_when_closed(self):
        from capture_store import CaptureStore
        with CaptureStore(memory_pixels=1000) as store:
            store.add(self.image, 0, 0, *self.image.size)
            image = store.assemble((0, 0, *self.image.size))
        backing = Path(image._capture_backing.directory.name)
        self.preview.destroy()
        self.preview = self.app._show_preview(image, "test", "Duży zrzut")
        self.settle()
        self.assertIs(self.preview.display_image, image)
        self.preview.destroy()
        self.assertFalse(backing.exists())

    def test_reduced_preview_shows_resolution_and_avoids_another_full_copy(self):
        self.preview.destroy()
        self.image.info["capture_original_size"] = (3200, 1800)
        self.image.info["capture_scale"] = 0.5
        self.preview = self.app._show_preview(self.image, "test", "Zmniejszony zrzut")
        self.settle()
        self.assertIs(self.preview.display_image, self.image)
        self.assertIn("zmniejszono do 50%", self.preview.info_label.cget("text"))
        self.preview.destroy()
        self.assertIsNone(self.app._latest_preview_image)

    def test_crop_clamps_reverse_drag_to_image_edges(self):
        self.preview.crop_btn.invoke()
        self.settle()
        self.drag_crop((1000, 700), (-100, -100))
        box = self.app._normalize_crop_box(self.preview.pending_crop, 1600, 900)
        self.assertEqual(box[:2], (0, 0))
        self.assertAlmostEqual(box[2], 1000, delta=4)
        self.assertAlmostEqual(box[3], 700, delta=4)

    def test_long_images_fit_and_remain_centered_after_resize(self):
        for size in ((900, 12000), (12000, 900)):
            self.preview.display_image = Image.new("RGB", size, "white")
            self.app._fit_preview_image(self.preview)
            for width, height in ((480, 360), (1100, 720)):
                with self.subTest(image=size, window=(width, height)):
                    self.resize(width, height)
                    canvas = self.preview.canvas
                    self.assertLess(self.preview.zoom_percent, 25)
                    self.assertLessEqual(canvas.image.width(), canvas.winfo_width() - 30)
                    self.assertLessEqual(canvas.image.height(), canvas.winfo_height() - 30)
                    left, top = canvas.coords("image")
                    self.assertAlmostEqual(left * 2 + canvas.image.width(), canvas.winfo_width(), delta=1)
                    self.assertAlmostEqual(top * 2 + canvas.image.height(), canvas.winfo_height(), delta=1)

    def test_manual_zoom_survives_resize_and_scrolls(self):
        self.preview.actual_size_btn.invoke()
        self.resize(640, 480)
        self.assertEqual(self.preview.canvas.image.width(), 1600)
        self.assertEqual(self.preview.canvas.image.height(), 900)
        self.preview.canvas.xview_moveto(0.5)
        self.preview.canvas.yview_moveto(0.5)
        self.assertGreater(self.preview.canvas.xview()[0], 0)
        self.assertGreater(self.preview.canvas.yview()[0], 0)
        self.resize(900, 600)
        self.assertEqual(self.preview.canvas.zoom_factor, 1)
        self.preview.fit_btn.invoke()
        self.settle()
        self.assertTrue(self.preview.fit_to_window)
        self.assertEqual(self.preview.canvas.xview(), (0, 1))
        self.assertEqual(self.preview.canvas.yview(), (0, 1))

    def test_crop_updates_image_and_saved_file(self):
        self.preview.pending_crop = (100, 50, 700, 450)
        self.app._accept_crop(self.preview)
        self.settle()
        self.assertEqual(self.preview.display_image.size, (600, 400))
        self.assertIn("600 × 400", self.preview.info_label.cget("text"))
        self.assertTrue(self.preview.fit_to_window)
        with tempfile.TemporaryDirectory() as directory:
            with patch("app_advanced.CAPTURE_DIR", Path(directory)):
                self.preview.save_btn.invoke()
            files = list(Path(directory).glob("*.png"))
            self.assertEqual(len(files), 1)
            with Image.open(files[0]) as saved:
                self.assertEqual(saved.size, (600, 400))

    def prepare_scrollable_preview(self):
        self.preview.actual_size_btn.invoke()
        self.resize(640, 480)
        canvas = self.preview.canvas
        canvas.xview_moveto(0.25)
        canvas.yview_moveto(0.25)
        canvas.event_generate("<ButtonPress-1>", x=40, y=40)
        canvas.event_generate("<ButtonRelease-1>", x=40, y=40)
        self.root.update()
        return canvas

    def test_arrows_and_page_keys_pan_without_changing_zoom(self):
        canvas = self.prepare_scrollable_preview()
        before = canvas.canvasx(0), canvas.canvasy(0)
        canvas.event_generate("<Right>")
        canvas.event_generate("<Down>")
        self.settle()
        self.assertEqual((canvas.canvasx(0), canvas.canvasy(0)), (before[0] + 48, before[1] + 48))
        canvas.event_generate("<Left>")
        canvas.event_generate("<Up>")
        self.settle()
        self.assertEqual((canvas.canvasx(0), canvas.canvasy(0)), before)
        canvas.event_generate("<Next>")
        self.settle()
        self.assertGreater(canvas.canvasy(0), before[1])
        canvas.event_generate("<Prior>")
        self.settle()
        self.assertAlmostEqual(canvas.canvasy(0), before[1], delta=1)
        self.assertEqual(canvas.zoom_factor, 1)

    def test_wheel_scrolls_both_axes_and_control_wheel_zooms(self):
        canvas = self.prepare_scrollable_preview()
        x, y = canvas.canvasx(0), canvas.canvasy(0)
        for _ in range(10):
            canvas.event_generate("<MouseWheel>", delta=-1)
        self.settle()
        self.assertAlmostEqual(canvas.canvasy(0), y + 8, delta=1)
        canvas.event_generate("<Shift-MouseWheel>", delta=-120)
        self.settle()
        self.assertEqual(canvas.canvasx(0), x + 96)
        self.assertEqual(canvas.zoom_factor, 1)
        canvas.event_generate("<Control-MouseWheel>", delta=120)
        self.settle()
        self.assertAlmostEqual(canvas.zoom_factor, 1.1)

    def test_precise_touchpad_event_pans_diagonally_and_preserves_crop(self):
        canvas = self.prepare_scrollable_preview()
        if not canvas.bind("<TouchpadScroll>"):
            self.skipTest("Precise touchpad events require Tk 9")
        self.app._toggle_crop_mode(self.preview)
        self.preview.pending_crop = (500, 250, 800, 500)
        self.app._draw_crop_selection(self.preview)
        self.settle()
        x, y = canvas.canvasx(0), canvas.canvasy(0)
        packed_delta = ((-13 & 0xffff) << 16) | (-21 & 0xffff)
        # Tk takes a signed 32-bit delta even though its words encode two axes.
        canvas.event_generate("<TouchpadScroll>", delta=packed_delta - 0x100000000)
        self.settle()
        self.assertEqual((canvas.canvasx(0), canvas.canvasy(0)), (x + 13, y + 21))
        self.assertEqual(canvas.zoom_factor, 1)
        self.assertEqual(self.preview.pending_crop, (500, 250, 800, 500))
        self.assertTrue(canvas.find_withtag("crop_overlay"))
        for _ in range(12):
            canvas.event_generate("<Control-TouchpadScroll>", delta=10)
        self.settle()
        self.assertAlmostEqual(canvas.zoom_factor, 1.1)

    @unittest.skipUnless(os.name == "nt", "Native touchpad messages require Windows")
    def test_windows_high_resolution_touchpad_messages_scroll_both_axes(self):
        import win32gui

        canvas = self.prepare_scrollable_preview()
        x, y = canvas.canvasx(0), canvas.canvasy(0)
        point = ((canvas.winfo_rootx() + 30) & 0xffff) | (((canvas.winfo_rooty() + 30) & 0xffff) << 16)
        # Windows precision devices send small signed deltas, not wheel notches.
        win32gui.SendMessage(canvas.winfo_id(), 0x020A, (-17 & 0xffff) << 16, point)
        win32gui.SendMessage(canvas.winfo_id(), 0x020E, 11 << 16, point)
        self.settle()
        self.assertEqual((canvas.canvasx(0), canvas.canvasy(0)), (x + 11, y + 17))
        self.assertEqual(canvas.zoom_factor, 1)
        # Fast gestures can cross Tk's heuristic from precise to notch events.
        # Both representations must keep the same horizontal direction.
        win32gui.SendMessage(canvas.winfo_id(), 0x020E, 120 << 16, point)
        win32gui.SendMessage(canvas.winfo_id(), 0x020E, 120 << 16, point)
        self.settle()
        self.assertEqual(canvas.canvasx(0), x + 11 + 120 + 96)

    @unittest.skipUnless(os.name == "nt", "Native window controls require Windows")
    def test_native_window_controls_minimize_maximize_restore(self):
        preview = self.preview
        self.assertFalse(preview.transient())
        self.assertFalse(preview.overrideredirect())
        user32 = ctypes.windll.user32
        user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        user32.GetAncestor.restype = ctypes.c_void_p
        user32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
        wrapper = user32.GetAncestor(preview.winfo_id(), 2)
        import win32gui
        # Tk applies the native icon when a withdrawn window is first mapped.
        self.root.deiconify()
        self.settle()
        for widget in (self.root, preview):
            handle = win32gui.GetAncestor(widget.winfo_id(), 2)
            self.assertTrue(win32gui.SendMessage(handle, 0x007F, 0, 0), f"Missing small app icon: {widget}")
            self.assertTrue(win32gui.SendMessage(handle, 0x007F, 1, 0), f"Missing large app icon: {widget}")
        style = user32.GetWindowLongW(wrapper, -16)
        for flag in (0x00020000, 0x00010000, 0x00080000):
            self.assertTrue(style & flag, hex(flag))
        preview.iconify()
        self.settle()
        self.assertEqual(preview.state(), "iconic")
        preview.deiconify()
        preview.state("zoomed")
        self.settle()
        self.assertEqual(preview.state(), "zoomed")
        self.assert_controls_visible()
        preview.state("normal")
        self.settle()
        self.assertEqual(preview.state(), "normal")

    def test_preview_is_topmost_and_can_be_unpinned(self):
        import win32gui
        preview = self.preview
        self.assertTrue(preview.attributes("-topmost"))
        self.assertEqual(win32gui.GetForegroundWindow(), win32gui.GetAncestor(preview.winfo_id(), 2))
        preview.pin_switch._toggle()
        self.root.update()
        self.assertFalse(preview.attributes("-topmost"))
        preview.pin_switch._toggle()
        self.root.update()
        self.assertTrue(preview.attributes("-topmost"))

    def test_capture_hides_own_windows_and_restores_them_before_preview(self):
        preview = self.preview
        with self.app._hidden_capture_windows():
            self.assertEqual(preview.state(), "withdrawn")
            self.assertEqual(self.root.state(), "withdrawn")
        self.assertEqual(preview.state(), "normal")
        self.assertTrue(preview.attributes("-topmost"))

    def test_capture_restores_own_windows_even_when_capture_fails(self):
        with self.assertRaises(RuntimeError):
            with self.app._hidden_capture_windows():
                raise RuntimeError("capture failed")
        self.assertEqual(self.preview.state(), "normal")

    def test_close_cancels_scheduled_work_and_keeps_main_window(self):
        errors = []
        self.root.report_callback_exception = lambda *args: errors.append(args)
        self.app._schedule_preview_render(self.preview)
        self.app._schedule_preview_layout(self.preview)
        self.preview.tk.eval(self.preview.protocol("WM_DELETE_WINDOW"))
        self.settle()
        self.assertFalse(self.preview.winfo_exists())
        self.assertTrue(self.root.winfo_exists())
        self.assertIsNone(self.preview.render_job)
        self.assertIsNone(self.preview.layout_job)
        self.assertEqual(errors, [])


class MainWindowLayoutTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.callback_errors = []
        self.root.report_callback_exception = lambda *args: self.callback_errors.append(args)
        self.app = ScreenCaptureApp(self.root)
        self.windows = [SimpleNamespace(title=title) for title in (
            "Projekt – Google Chrome", "Raport - Q1.xlsx - Excel", "Plan.txt — Notatnik")]
        self.window_source = patch.object(self.app, "get_selectable_windows", return_value=self.windows)
        self.window_source.start()
        self.settle()

    def tearDown(self):
        self.window_source.stop()
        self.root.destroy()
        self.assertEqual(self.callback_errors, [])

    def settle(self):
        deadline = time.monotonic() + 0.35
        while time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)

    def test_mode_cards_and_capture_action_choose_correct_handler(self):
        app = self.app
        for key, method in (("screen", "capture_full_screen"), ("window", "_capture_selected_window"), ("area", "capture_selected_area")):
            card = next(card for card in app.mode_cards if card.key == key)
            card.event_generate("<Button-1>", x=20, y=20)
            self.assertEqual(app.selected_mode, key)
            self.assertEqual(sum(item.selected for item in app.mode_cards), 1)
            if key == "window":
                app.window_table.selection_set(app.window_table.get_children()[0])
                app._window_selection_changed()
            with patch.object(app, method) as handler:
                app.capture_action.invoke()
                handler.assert_called_once_with()

    def test_window_picker_is_embedded_and_names_start_with_program(self):
        app = self.app
        windows_before = [item for item in self.root.winfo_children() if isinstance(item, tk.Toplevel)]
        app._select_capture_mode("window")
        self.settle()
        self.assertTrue(app.window_picker_card.winfo_ismapped())
        self.assertEqual(windows_before, [item for item in self.root.winfo_children() if isinstance(item, tk.Toplevel)])
        values = [app.window_table.item(row, "values") for row in app.window_table.get_children()]
        self.assertEqual([tuple(value) for value in values], [
            ("Google Chrome", "Projekt"), ("Microsoft Excel", "Raport - Q1.xlsx"), ("Notatnik", "Plan.txt")])
        self.assertTrue(app.capture_action.disabled)
        rows = app.window_table.get_children()
        app.window_table.selection_set(rows[1])
        self.settle()
        self.assertFalse(app.capture_action.disabled)
        with patch.object(app, "_capture_window_obj") as capture:
            app.capture_action.invoke()
            capture.assert_called_once_with(self.windows[1])
        app._select_capture_mode("screen")
        self.settle()
        self.assertFalse(app.window_picker_card.winfo_ismapped())
        self.assertFalse(app.capture_action.disabled)

    def test_window_search_matches_program_and_document_without_hidden_selection(self):
        app = self.app
        app._select_capture_mode("window")
        app.window_filter.set("CHROME")
        self.assertEqual(len(app.window_rows), 1)
        row = next(iter(app.window_rows))
        app.window_table.selection_set(row)
        self.settle()
        self.assertFalse(app.capture_action.disabled)
        app.window_filter.set("q1")
        self.settle()
        self.assertEqual([entry.program for entry in app.window_rows.values()], ["Microsoft Excel"])
        self.assertTrue(app.capture_action.disabled)
        app.window_filter.set("nieistniejący plik")
        self.assertFalse(app.window_rows)
        self.assertIn("Brak wyników", app.window_picker_message.cget("text"))

    def test_window_refresh_preserves_selection_and_clears_closed_window(self):
        app = self.app
        app._select_capture_mode("window")
        app.window_table.selection_set(app.window_table.get_children()[1])
        self.settle()
        selected_key = app.selected_window_key
        app.refresh_windows_button.invoke()
        self.settle()
        self.assertEqual(app.selected_window_key, selected_key)
        self.assertFalse(app.capture_action.disabled)
        self.window_source.stop()
        self.window_source = patch.object(app, "get_selectable_windows", return_value=[])
        self.window_source.start()
        app.refresh_windows_button.invoke()
        self.settle()
        self.assertFalse(app.window_rows)
        self.assertIsNone(app.selected_window_key)
        self.assertTrue(app.capture_action.disabled)
        self.assertIn("Brak dostępnych okien", app.window_picker_message.cget("text"))

    def test_closed_window_is_not_captured(self):
        app = self.app
        app._select_capture_mode("window")
        app.window_table.selection_set(app.window_table.get_children()[0])
        self.settle()
        with patch("window_picker.window_is_available", return_value=False), patch.object(app, "_capture_window_obj") as capture:
            app.capture_action.invoke()
            capture.assert_not_called()
        self.assertIn("zostało zamknięte", app.status.cget("text"))

    def test_window_table_scroll_does_not_scroll_main_page(self):
        app = self.app
        self.windows.extend(SimpleNamespace(title=f"Strona {index} - Google Chrome") for index in range(15))
        app._select_capture_mode("window")
        self.settle()
        before = app.dashboard_canvas.yview()
        app.window_table.event_generate("<MouseWheel>", delta=-120)
        self.root.update()
        self.assertGreater(app.window_table.yview()[0], 0)
        self.assertEqual(app.dashboard_canvas.yview(), before)

    def test_window_picker_layout_in_narrow_main_window(self):
        app = self.app
        self.root.geometry("1000x1100+30+30")
        app._select_capture_mode("window")
        self.settle()
        table = app.window_table
        self.assertGreater(table.winfo_width(), 200)
        self.assertLessEqual(table.winfo_rootx() + table.winfo_width(), self.root.winfo_rootx() + self.root.winfo_width())
        self.assertLessEqual(app.capture_action.winfo_rooty() + app.capture_action.winfo_height(), self.root.winfo_rooty() + self.root.winfo_height())
        destination = Path("build/preview-review")
        destination.mkdir(parents=True, exist_ok=True)
        ImageGrab.grab(bbox=(self.root.winfo_rootx(), self.root.winfo_rooty(),
                            self.root.winfo_rootx() + self.root.winfo_width(),
                            self.root.winfo_rooty() + self.root.winfo_height())).save(destination / "window-picker.png")

    def test_switches_support_keyboard_and_preserve_options_between_modes(self):
        app = self.app
        self.assertTrue(all(switch.disabled for switch in app.scroll_switches))
        app.mode_cards[1].focus_force()
        app.mode_cards[1].event_generate("<space>")
        self.assertEqual(app.selected_mode, "window")
        self.assertTrue(all(not switch.disabled for switch in app.scroll_switches))
        switch = app.scroll_switches[0]
        switch.focus_force()
        switch.event_generate("<space>")
        self.assertTrue(app.vertical_var.get())
        app._select_capture_mode("area")
        switch._toggle()
        self.assertTrue(app.vertical_var.get())
        app._select_capture_mode("window")
        self.assertTrue(app.vertical_var.get())
        self.assertFalse(app.horizontal_var.get())

    def test_window_capture_is_immediate_unless_scrolling_is_explicitly_enabled(self):
        app = self.app
        app._select_capture_mode("window")
        self.assertFalse(app.vertical_var.get())
        self.assertFalse(app.horizontal_var.get())
        self.assertEqual(app.capture_action.cget("text"), "Zrób zrzut okna")
        app.horizontal_var.set(True)
        self.assertEqual(app.capture_action.cget("text"), "Zrób zrzut z przewijaniem")
        self.assertIn("jednym przejściu", app.scroll_hint.cget("text"))
        app.horizontal_var.set(False)
        self.assertEqual(app.capture_action.cget("text"), "Zrób zrzut okna")

    def test_capture_failure_has_visible_feedback_and_clears_for_next_capture(self):
        app = self.app
        app._report_capture_failure("Przerwano zrzut po przełączeniu do innej aplikacji.")
        self.root.update()
        self.assertTrue(app.capture_notice.winfo_ismapped())
        self.assertIn("Przerwano", app.capture_notice.cget("text"))
        app._select_capture_mode("screen")
        with patch("app_advanced.messagebox.showinfo") as info:
            app._show_capture_warning()
        self.root.update()
        self.assertFalse(app.capture_notice.winfo_ismapped())
        info.assert_not_called()

    def test_main_layout_scrolls_and_keeps_capture_button_accessible(self):
        app = self.app
        for width, height in ((1000, 700), (1800, 1100)):
            self.root.geometry(f"{width}x{height}+30+30")
            self.settle()
            button = app.capture_action
            self.assertTrue(button.winfo_ismapped())
            self.assertLessEqual(button.winfo_rootx() + button.winfo_width(), self.root.winfo_rootx() + self.root.winfo_width())
            self.assertLessEqual(button.winfo_rooty() + button.winfo_height(), self.root.winfo_rooty() + self.root.winfo_height())
            for card in app.mode_cards:
                self.assertLessEqual(card.winfo_x() + card.winfo_width(), app.mode_grid.winfo_width())
            app.dashboard_canvas.yview_moveto(1)
            self.root.update()
            entry = app.output_entry
            self.assertLessEqual(entry.winfo_rooty() + entry.winfo_height(), app.dashboard_canvas.winfo_rooty() + app.dashboard_canvas.winfo_height())
            app.dashboard_canvas.yview_moveto(0)
            self.root.update()
            destination = Path("build/preview-review")
            destination.mkdir(parents=True, exist_ok=True)
            ImageGrab.grab(bbox=(self.root.winfo_rootx(), self.root.winfo_rooty(),
                                self.root.winfo_rootx() + self.root.winfo_width(),
                                self.root.winfo_rooty() + self.root.winfo_height())).save(destination / f"main-{width}.png")


if __name__ == "__main__":
    unittest.main()
