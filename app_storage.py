"""Bounded, per-process scratch storage and persistent application logs."""
import atexit
from functools import lru_cache
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile


CACHE_LIMIT = 512 * 1024**2
FREE_SPACE_RESERVE = 256 * 1024**2
_MARKER = b"MiniScreenShot cache v1\n"


def _linked(path):
    return bool(path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT) if sys.platform == "win32" else path.is_symlink()


def _lock(file):
    file.seek(0)
    if sys.platform == "win32":
        import msvcrt
        msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _writable_directory(path):
    # Check before mkdir as well: an existing junction in a parent must not
    # redirect creation outside the intended application directory.
    def check_parents():
        for parent in (path, *path.parents):
            try:
                if _linked(parent):
                    raise OSError("Application storage must be an ordinary directory")
            except FileNotFoundError:
                continue

    check_parents()
    path.mkdir(parents=True, exist_ok=True)
    check_parents()
    with tempfile.TemporaryFile(dir=path):
        pass
    return path


@lru_cache(maxsize=1)
def data_directory():
    candidates = [Path("C:/MiniScreenShot")] if sys.platform == "win32" else []
    candidates.append(Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share")) / "MiniScreenShot")
    for candidate in candidates:
        try:
            folder = _writable_directory(candidate)
            # A writable parent does not imply that an existing cache is
            # accessible. Validate the directory actually needed at startup.
            _writable_directory(folder / "cache")
            return folder
        except OSError:
            continue
    raise OSError("Nie można utworzyć katalogu MiniScreenShot do zapisu plików roboczych.")


class CacheSession:
    def __init__(self, root, limit=CACHE_LIMIT):
        self.root = _writable_directory(Path(root))
        self.limit = limit
        self._remove_abandoned()
        self.directory = tempfile.TemporaryDirectory(prefix="session-", dir=self.root)
        self.path = Path(self.directory.name)
        self.marker = (self.path / ".owner").open("x+b")
        self.marker.write(_MARKER)
        self.marker.flush()
        _lock(self.marker)

    def _remove_abandoned(self):
        # Only our marked sessions; a held OS lock protects another running copy.
        for candidate in self.root.glob("session-*"):
            try:
                if _linked(candidate) or not candidate.is_dir():
                    continue
                marker = candidate / ".owner"
                if _linked(marker):
                    continue
                with marker.open("r+b") as owner:
                    if owner.read() != _MARKER:
                        continue
                    _lock(owner)
                shutil.rmtree(candidate)
            except OSError:
                continue

    def used_bytes(self):
        return sum(path.stat().st_size for path in self.path.rglob("*")
                   if path.is_file() and not _linked(path))

    def check_space(self, size):
        if (size + self.used_bytes() > self.limit
                or shutil.disk_usage(self.path).free - size < FREE_SPACE_RESERVE):
            raise OSError("Osiągnięto limit cache lub brakuje wolnego miejsca na dysku.")

    def temporary_directory(self, prefix):
        return tempfile.TemporaryDirectory(prefix=prefix, dir=self.path)

    def close(self):
        if self.marker is not None:
            self.marker.close()
            self.marker = None
        try:
            self.directory.cleanup()
        except OSError:
            # A later startup will retry after remaining file handles close.
            pass


@lru_cache(maxsize=1)
def cache_session():
    session = CacheSession(data_directory() / "cache")
    atexit.register(session.close)
    return session


def configure_logging():
    try:
        folder = _writable_directory(data_directory() / "logs")
        path = folder / "capture_debug.log"
        for target in (path, Path(str(path) + ".1"), Path(str(path) + ".2")):
            try:
                if _linked(target) or target.stat().st_nlink != 1:
                    raise OSError("Application log must be an ordinary, unlinked file")
            except FileNotFoundError:
                continue
        handler = RotatingFileHandler(path, maxBytes=512 * 1024, backupCount=2, encoding="utf-8")
    except OSError:
        path = None
        handler = logging.NullHandler()
    logging.basicConfig(handlers=[handler], level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", force=True)
    return path
