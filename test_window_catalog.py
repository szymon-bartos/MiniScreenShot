import unittest
from types import SimpleNamespace
from unittest.mock import patch

from window_catalog import describe_window, executable_program_name, split_window_title


class WindowCatalogTests(unittest.TestCase):
    def test_known_applications_keep_document_names_and_punctuation(self):
        for executable, title, program, document in (
            ("chrome.exe", "Projekt — API - Google Chrome", "Google Chrome", "Projekt — API"),
            ("msedge.exe", "Dokumentacja – Microsoft Edge", "Microsoft Edge", "Dokumentacja"),
            ("firefox.exe", "Projekt — Mozilla Firefox", "Mozilla Firefox", "Projekt"),
            ("notepad.exe", "Plan - wersja 2.txt — Notatnik", "Notatnik", "Plan - wersja 2.txt"),
            ("winword.exe", "Oferta.docx - Word", "Microsoft Word", "Oferta.docx"),
            ("code.exe", "main.py - Projekt - Visual Studio Code", "Visual Studio Code", "main.py - Projekt"),
        ):
            with self.subTest(title=title), patch("window_catalog.window_process_id", return_value=123), patch("window_catalog.process_executable", return_value=f"C:/Programs/{executable}"):
                entry = describe_window(SimpleNamespace(title=title))
                self.assertEqual((entry.program, entry.document), (program, document))
                self.assertEqual(entry.label, f"{program} — {document}")

    def test_program_is_resolved_from_process_even_when_title_names_other_app(self):
        with patch("window_catalog.window_process_id", return_value=123), patch("window_catalog.process_executable", return_value="C:/Programs/notepad.exe"):
            entry = describe_window(SimpleNamespace(title="Instrukcja do Chrome.txt"))
        self.assertEqual(entry.program, "Notatnik")
        self.assertEqual(entry.document, "Instrukcja do Chrome.txt")

    def test_unreadable_process_uses_matching_title_suffix(self):
        with patch("window_catalog.window_process_id", return_value=123), patch("window_catalog.process_executable", return_value=None):
            entry = describe_window(SimpleNamespace(title="Zażółć gęślą.docx - Word"))
        self.assertEqual(entry.label, "Microsoft Word — Zażółć gęślą.docx")

    def test_unknown_app_preserves_entire_title_when_process_is_unreadable(self):
        entry = describe_window(SimpleNamespace(title="Raport - nieznany format"))
        self.assertEqual(entry.label, "Aplikacja — Raport - nieznany format")

    def test_prefix_and_program_only_titles_do_not_duplicate_application_name(self):
        self.assertEqual(split_window_title("Notatnik — Plan.txt", "Notatnik"), "Plan.txt")
        self.assertEqual(split_window_title("Google Chrome", "Google Chrome"), "")
        self.assertEqual(split_window_title("Praca - wersja - końcowa.txt", "Notatnik"), "Praca - wersja - końcowa.txt")

    def test_multiple_windows_of_one_process_share_path_lookup(self):
        process_paths = {}
        with patch("window_catalog.window_process_id", return_value=123), patch("window_catalog.process_executable", return_value="C:/Programs/chrome.exe") as lookup:
            first = describe_window(SimpleNamespace(title="Strona A - Google Chrome"), process_paths)
            second = describe_window(SimpleNamespace(title="Strona B - Google Chrome"), process_paths)
        lookup.assert_called_once_with(123)
        self.assertNotEqual(first.document, second.document)
        self.assertNotEqual(first.key, second.key)

    def test_unknown_executable_uses_windows_file_description(self):
        executable_program_name.cache_clear()
        with patch("window_catalog.win32api.GetFileVersionInfo", side_effect=[[(1033, 1200)], "Edytor projektów"]):
            name, aliases = executable_program_name("C:/Programs/custom-editor.exe")
        self.assertEqual(name, "Edytor projektów")
        self.assertIn("custom-editor", aliases)
        executable_program_name.cache_clear()

    def test_missing_version_info_uses_executable_name(self):
        executable_program_name.cache_clear()
        with patch("window_catalog.win32api.GetFileVersionInfo", side_effect=OSError("No version info")):
            name, _aliases = executable_program_name("C:/Programs/CustomApp.exe")
        self.assertEqual(name, "CustomApp")
        executable_program_name.cache_clear()


if __name__ == "__main__":
    unittest.main()
