"""Regression checks for saving captures and clipboard failure recovery."""
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

from PIL import Image

import app_advanced as app


class CaptureIOTests(TestCase):
    def test_same_timestamp_preserves_both_captures(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(app, "CAPTURE_DIR", Path(directory)), \
                patch.object(app, "timestamp_name", return_value="capture.png"):
            with Image.new("RGB", (2, 2), "red") as first, \
                    Image.new("RGB", (2, 2), "blue") as second:
                first_path = app.save_image(first, "capture")
                second_path = app.save_image(second, "capture")
            self.assertNotEqual(first_path, second_path)
            with Image.open(first_path) as saved:
                self.assertEqual(saved.getpixel((0, 0)), (255, 0, 0))
            with Image.open(second_path) as saved:
                self.assertEqual(saved.getpixel((0, 0)), (0, 0, 255))

    def test_failed_save_removes_only_its_incomplete_file(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(app, "CAPTURE_DIR", Path(directory)), \
                patch.object(app, "timestamp_name", return_value="capture.png"):
            existing = Path(directory) / "capture.png"
            existing.write_bytes(b"keep")
            image = Mock()
            image.save.side_effect = OSError("Disk full")
            with self.assertRaises(OSError):
                app.save_image(image, "capture")
            self.assertEqual(existing.read_bytes(), b"keep")
            self.assertEqual(list(Path(directory).iterdir()), [existing])

    def test_clipboard_write_failure_closes_clipboard_before_fallback(self):
        owner, preview = Mock(), Mock()
        with Image.new("RGB", (2, 2), "red") as image, \
                patch("win32clipboard.OpenClipboard") as opened, \
                patch("win32clipboard.EmptyClipboard"), \
                patch("win32clipboard.SetClipboardData", side_effect=OSError("Clipboard error")), \
                patch("win32clipboard.CloseClipboard") as closed, \
                patch.object(app, "save_image") as save:
            def fallback(*args):
                closed.assert_called_once_with()
                return "capture.png"
            save.side_effect = fallback
            app.ScreenCaptureApp._copy_image_to_clipboard(owner, preview, image)
        opened.assert_called_once_with()
        preview.destroy.assert_called_once_with()

    def test_failed_clipboard_fallback_keeps_preview_open(self):
        owner, preview = Mock(), Mock()
        with Image.new("RGB", (2, 2), "red") as image, \
                patch("win32clipboard.OpenClipboard", side_effect=OSError("Busy")), \
                patch("win32clipboard.CloseClipboard") as closed, \
                patch.object(app, "save_image", side_effect=OSError("Disk full")):
            app.ScreenCaptureApp._copy_image_to_clipboard(owner, preview, image)
        closed.assert_not_called()
        preview.destroy.assert_not_called()
        owner.ui.dialog.assert_called_once()
