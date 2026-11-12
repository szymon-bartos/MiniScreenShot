"""Cache ownership, bounded disk use and capture cleanup regressions."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

import app_storage
from app_storage import CacheSession
from capture_store import CaptureStore, CaptureStorageError


class StorageTests(unittest.TestCase):
    def test_unwritable_log_does_not_prevent_startup(self):
        with patch("app_storage.data_directory", side_effect=PermissionError("Read-only")), \
                patch("app_storage.logging.basicConfig") as configure:
            self.assertIsNone(app_storage.configure_logging())
        self.assertIsInstance(configure.call_args.kwargs["handlers"][0], app_storage.logging.NullHandler)

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name) / "cache"

    def session(self, limit=512 * 1024**2):
        session = CacheSession(self.root, limit=limit)
        self.addCleanup(session.close)
        return session

    def test_abandoned_sessions_removed_but_live_and_unowned_data_preserved(self):
        live = self.session()
        active_data = live.path / "active.rgba"
        active_data.write_bytes(b"active")
        orphan = self.root / "session-orphan"
        orphan.mkdir()
        (orphan / ".owner").write_bytes(app_storage._MARKER)
        (orphan / "frame.rgba").write_bytes(b"old")
        unrelated = self.root / "session-unrelated"
        unrelated.mkdir()
        (unrelated / "keep.png").write_bytes(b"user data")
        second = self.session()
        self.assertFalse(orphan.exists())
        self.assertEqual(active_data.read_bytes(), b"active")
        self.assertEqual((unrelated / "keep.png").read_bytes(), b"user data")
        second.close()
        self.assertTrue(live.path.exists())

    def test_capture_files_stay_in_session_and_close_removes_them(self):
        session = self.session()
        image = Image.new("RGB", (40, 30), "blue")
        self.addCleanup(image.close)
        with patch("capture_store.cache_session", return_value=session):
            with CaptureStore(memory_pixels=1) as store:
                frame_folder = Path(store.directory.name)
                self.assertEqual(frame_folder.parent, session.path)
                store.add(image, 0, 0, *image.size)
                self.assertTrue(store.frames[0].path.is_file())
                result = store.assemble((0, 0, *image.size))
            self.assertFalse(frame_folder.exists())
            result_folder = Path(result._capture_backing.directory.name)
            self.assertEqual(result_folder.parent, session.path)
            self.assertEqual(result.convert("RGB").getpixel((20, 20)), (0, 0, 255))
            result.close()
            self.assertFalse(result_folder.exists())
        session.close()
        self.assertFalse(session.path.exists())

    def test_limit_is_checked_before_writing_capture(self):
        session = self.session(limit=4096)
        image = Image.new("RGB", (40, 40), "white")
        self.addCleanup(image.close)
        with patch("capture_store.cache_session", return_value=session):
            with CaptureStore(memory_pixels=1) as store:
                with self.assertRaises(CaptureStorageError):
                    store.add(image, 0, 0, *image.size)
                self.assertEqual(store.frames, [])
                self.assertEqual(list(Path(store.directory.name).iterdir()), [])

    def test_logical_limit_counts_files_already_in_use(self):
        session = self.session(limit=4096)
        (session.path / "existing.rgba").write_bytes(b"x" * 3000)
        with self.assertRaises(OSError):
            session.check_space(2000)
        self.assertEqual((session.path / "existing.rgba").stat().st_size, 3000)

    def test_low_disk_space_stops_writes_without_deleting_existing_data(self):
        session = self.session()
        with patch("app_storage.shutil.disk_usage", return_value=type("Disk", (), {"free": 1000})()):
            with self.assertRaises(OSError):
                session.check_space(100)

    def test_unwritable_c_drive_uses_local_appdata_without_admin(self):
        local = Path(self.folder.name) / "LocalAppData"
        attempted = []

        def writable(path):
            attempted.append(path)
            if str(path).replace("\\", "/") == "C:/MiniScreenShot":
                raise PermissionError("Root is read-only")
            path.mkdir(parents=True)
            return path

        app_storage.data_directory.cache_clear()
        self.addCleanup(app_storage.data_directory.cache_clear)
        with patch.dict(os.environ, {"LOCALAPPDATA": str(local)}), patch("app_storage._writable_directory", side_effect=writable):
            self.assertEqual(app_storage.data_directory(), local / "MiniScreenShot")
        self.assertEqual(len(attempted), 3)

    def test_denied_cache_uses_fallback_even_when_parent_is_writable(self):
        local = Path(self.folder.name) / "LocalAppData"
        attempts = []

        def writable(path):
            attempts.append(path)
            normalized = str(path).replace("\\", "/")
            if normalized == "C:/MiniScreenShot/cache":
                raise PermissionError("Cache is read-only")
            if not normalized.startswith("C:/"):
                path.mkdir(parents=True, exist_ok=True)
            return path

        app_storage.data_directory.cache_clear()
        self.addCleanup(app_storage.data_directory.cache_clear)
        with patch.dict(os.environ, {"LOCALAPPDATA": str(local)}), \
                patch("app_storage._writable_directory", side_effect=writable):
            self.assertEqual(app_storage.data_directory(), local / "MiniScreenShot")
        self.assertIn(Path("C:/MiniScreenShot/cache"), attempts)

    def test_linked_parent_is_rejected_before_creating_child(self):
        parent = Path(self.folder.name) / "redirected"
        parent.mkdir()
        child = parent / "cache"
        original = app_storage._linked
        with patch("app_storage._linked", side_effect=lambda path: path == parent or original(path)):
            with self.assertRaises(OSError):
                app_storage._writable_directory(child)
        self.assertFalse(child.exists())

    def test_linked_log_is_not_opened_or_rotated(self):
        root = Path(self.folder.name)
        logs = root / "logs"
        logs.mkdir()
        path = logs / "capture_debug.log"
        path.write_bytes(b"preserve this file")
        original = app_storage._linked
        with patch("app_storage.data_directory", return_value=root), \
                patch("app_storage._linked", side_effect=lambda item: item == path or original(item)), \
                patch("app_storage.RotatingFileHandler") as handler, \
                patch("app_storage.logging.basicConfig"):
            self.assertIsNone(app_storage.configure_logging())
        handler.assert_not_called()
        self.assertEqual(path.read_bytes(), b"preserve this file")

    def test_hardlinked_log_does_not_modify_the_other_file(self):
        root = Path(self.folder.name)
        logs = root / "logs"
        logs.mkdir()
        original = root / "keep.txt"
        original.write_bytes(b"user file")
        try:
            os.link(original, logs / "capture_debug.log")
        except OSError as exc:
            self.skipTest(f"Filesystem does not support hard links: {exc}")
        with patch("app_storage.data_directory", return_value=root), \
                patch("app_storage.RotatingFileHandler") as handler, \
                patch("app_storage.logging.basicConfig"):
            self.assertIsNone(app_storage.configure_logging())
        handler.assert_not_called()
        self.assertEqual(original.read_bytes(), b"user file")


if __name__ == "__main__":
    unittest.main()
