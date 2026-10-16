"""Language selection, live editor state and safe persisted preferences."""
import ast
import json
import re
from pathlib import Path
from string import Formatter
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops

from app_advanced import ScreenCaptureApp, tk
from app_information import AUTHOR_NOTE, LICENSE_TEXT, ENGLISH_LICENSE_TEXT
from localization import LANGUAGES, LocalizedUI, load_language, save_language, msg
from translations import ENGLISH


class TranslationTests(unittest.TestCase):
    def test_catalogue_preserves_all_format_fields(self):
        fields = lambda value: sorted((name, spec, conversion) for _, name, spec, conversion in Formatter().parse(value) if name is not None)
        for source, translation in ENGLISH.items():
            with self.subTest(source=source):
                self.assertTrue(translation.strip())
                self.assertEqual(fields(source), fields(translation))

    def test_nested_messages_translate_but_user_data_is_literal(self):
        ui = LocalizedUI("en")
        title = "Zapisz {lead_id} — Żółty"
        text = msg("Okno: {title} — {description}", title=title, description=msg("z przewijaniem"))
        self.assertEqual(ui.render(text), f"Window: {title} — scrolling capture")
        self.assertEqual(str(text), f"Okno: {title} — z przewijaniem")
        self.assertEqual(ui.render(msg("{message}  Esc: anuluj", message=msg("Kończę zapis {count} przechwyconych fragmentów…", count=12))),
                         "Finishing 12 captured sections…  Esc: cancel")

    def test_backend_errors_have_english_translations(self):
        for name in ("windows_scroll.py", "excel_scroll.py", "capture_store.py", "app_storage.py", "scroll_capture.py"):
            tree = ast.parse(Path(name).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call) and node.exc.args:
                    argument = node.exc.args[0]
                    if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                        source = argument.value
                        if source.startswith(("Nie ", "Wybrane ", "Anulowano ", "Położenie ", "Przerwano ", "Zwolnij ", "Windows nie ", "Wybierz ", "Aktywny ", "Brakuje ", "Osiągnięto ", "Okno ", "Rozmiar ")):
                            self.assertIn(source, ENGLISH, (name, node.lineno))

    def test_preferences_are_small_atomic_and_invalid_settings_fall_back_to_polish(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            self.assertEqual(load_language(path), "pl")
            for language in LANGUAGES:
                save_language(language, path)
                self.assertEqual(load_language(path), language)
                self.assertLess(path.stat().st_size, 100)
                self.assertEqual(list(Path(folder).glob("*.tmp")), [])
            for invalid in ('{"language":"xx"}', '[]', 'broken', 'x' * 5000):
                path.write_text(invalid, encoding="utf-8")
                self.assertEqual(load_language(path), "pl")
            with self.assertRaises(ValueError):
                save_language("xx", path)


class LanguageInterfaceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings = Path(self.directory.name) / "settings.json"
        patcher = patch("localization.settings_path", return_value=self.settings)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.root = tk.Tk()
        self.app = ScreenCaptureApp(self.root)
        self.addCleanup(self.close_root)
        self.pump()

    def close_root(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def pump(self):
        deadline = time.monotonic() + .15
        while time.monotonic() < deadline:
            self.root.update()
            time.sleep(.01)

    def assert_bound_text_is_english(self):
        for widget, bindings in list(self.app.ui._bindings.items()):
            if widget.winfo_exists() and "text" in bindings:
                self.assertEqual(widget.cget("text"), self.app.ui.render(bindings["text"]))
                source = getattr(bindings["text"], "source", bindings["text"])
                natural_text = re.sub(r"\{[^}]+\}", "", source).replace("MiniScreenShot", "").strip()
                if any(character.isalpha() for character in natural_text) and not natural_text.startswith("v1."):
                    self.assertIn(source, ENGLISH, f"Untranslated UI source: {source}")

    def test_selector_persists_and_next_app_start_restores_english(self):
        self.app.language_var.set("English")
        self.app.language_picker.event_generate("<<ComboboxSelected>>")
        self.pump()
        self.assertEqual(self.app.ui.language, "en")
        self.assertEqual(json.loads(self.settings.read_text())["language"], "en")
        self.assertEqual(self.app.capture_action.cget("text"), "Capture screen")
        self.assertEqual(self.app.mode_cards[1].title, "Application window")
        self.assert_bound_text_is_english()
        self.root.destroy()
        self.root = tk.Tk()
        self.app = ScreenCaptureApp(self.root)
        self.pump()
        self.assertEqual(self.app.language_var.get(), "English")
        self.assertEqual(self.app.information_button.cget("text"), "About")

    def test_language_switch_preserves_editor_crop_zoom_and_undo(self):
        preview = self.app._show_preview(Image.new("RGB", (800, 900), "white"), "language-test",
                                         msg("Okno: {title} - podgląd", title="Żółty {lead_id}.txt"))
        self.pump()
        self.app._apply_zoom_from_slider(preview, preview.display_image, 75)
        self.app._set_annotation_tool(preview, "pencil")
        self.app.set_language("en", persist=False)
        self.pump()
        preview.color_var.set("Green")
        preview.brush_size_var.set("Thick")
        self.app._annotation_settings_changed(preview)
        canvas = preview.canvas
        left, top, right, bottom = self.app._crop_image_bounds(preview)
        event = SimpleNamespace(x=round(left + 120 - canvas.canvasx(0)), y=round(top + 120 - canvas.canvasy(0)))
        self.app._annotation_press(preview, event)
        self.app._annotation_release(preview, event)
        annotated = preview.display_image.copy()
        self.assertTrue(preview.annotation_history.patches)
        self.assertIn("Żółty {lead_id}.txt", preview.title())
        self.assertTrue(preview.title().startswith("Window:"))
        self.app._toggle_crop_mode(preview)
        preview.pending_crop = (10, 15, 150, 170)
        self.app._update_crop_hint(preview)
        zoom = preview.zoom_percent
        self.app.set_language("pl", persist=False)
        self.pump()
        self.assertEqual(preview.pending_crop, (10, 15, 150, 170))
        self.assertEqual(preview.zoom_percent, zoom)
        self.assertEqual(preview.color_var.get(), "Zielony")
        self.assertIsNone(ImageChops.difference(annotated, preview.display_image).getbbox())
        self.app.set_language("en", persist=False)
        self.assertIn("Enter: crop", preview.info_label.cget("text"))
        self.app._reject_crop(preview)
        self.app._undo_annotation(preview)
        self.assertEqual(preview.display_image.getextrema(), ((255, 255),) * 3)

    def test_about_dialog_translates_and_preserves_original_polish_licence(self):
        dialog = self.app.show_information()
        self.assertEqual(dialog.author_label.cget("text"), AUTHOR_NOTE)
        self.app.set_language("en", persist=False)
        self.pump()
        self.assertEqual(dialog.title(), "About MiniScreenShot")
        self.assertEqual(dialog.author_label.cget("text"), "Created by Szymon Bartos")
        self.assertIn(ENGLISH_LICENSE_TEXT, dialog.license_text.get("1.0", "end"))
        self.assertIn(LICENSE_TEXT, dialog.license_text.get("1.0", "end"))
        self.app.set_language("pl", persist=False)
        self.assertEqual(dialog.license_text.get("1.0", "end").strip(), LICENSE_TEXT)

    def test_english_window_picker_and_scroll_options_keep_selection(self):
        window = SimpleNamespace(title="Umowa {2026} - Notepad", _hWnd=None)
        with patch.object(self.app, "get_selectable_windows", return_value=[window]):
            self.app._select_capture_mode("window")
        row = self.app.window_table.get_children()[0]
        self.app.window_table.selection_set(row)
        self.app._window_selection_changed()
        self.app.vertical_var.set(True)
        self.app.set_language("en", persist=False)
        self.pump()
        self.assertEqual(self.app.capture_action.cget("text"), "Capture with scrolling")
        self.assertEqual(self.app.window_table.selection(), (row,))
        self.assertIn("Umowa {2026}", self.app.window_table.item(row, "values")[1])
        self.assertEqual(self.app.window_table.heading("document", "text"), "File, page or window title")
        self.app.root.geometry("520x680")
        self.pump()
        self.assertLessEqual(self.app.language_picker.winfo_rootx() + self.app.language_picker.winfo_width(),
                             self.root.winfo_rootx() + self.root.winfo_width())


if __name__ == "__main__":
    unittest.main()
