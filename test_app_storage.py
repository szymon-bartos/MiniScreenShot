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
        self.assertEqual(len(attempted), 2)


if __name__ == "__main__":
    unittest.main()
