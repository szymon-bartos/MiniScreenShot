"""Resolve window owners and keep application names before document titles."""

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import win32api
import win32gui
import win32process


PROGRAMS = {
    "chrome": ("Google Chrome", ("Chrome",)),
    "msedge": ("Microsoft Edge", ("Edge",)),
    "firefox": ("Mozilla Firefox", ("Firefox",)),
    "brave": ("Brave", ("Brave Browser",)),
    "opera": ("Opera", ()),
    "code": ("Visual Studio Code", ("Code",)),
    "devenv": ("Microsoft Visual Studio", ("Visual Studio",)),
    "notepad": ("Notatnik", ("Notepad", "Windows Notepad")),
    "notepad++": ("Notepad++", ()),
    "winword": ("Microsoft Word", ("Word",)),
    "excel": ("Microsoft Excel", ("Excel",)),
    "powerpnt": ("Microsoft PowerPoint", ("PowerPoint",)),
    "outlook": ("Microsoft Outlook", ("Outlook",)),
    "onenote": ("Microsoft OneNote", ("OneNote",)),
    "acrord32": ("Adobe Acrobat Reader", ("Adobe Acrobat Reader DC",)),
    "acrobat": ("Adobe Acrobat", ("Adobe Acrobat Pro",)),
    "sumatrapdf": ("SumatraPDF", ()),
    "explorer": ("Eksplorator plików", ("File Explorer", "Windows Explorer")),
    "mspaint": ("Paint", ()),
}
SEPARATORS = (" — ", " – ", " - ", " | ", " · ")
HOST_PROCESSES = {"applicationframehost", "wwahost"}


def window_process_id(window):
    handle = getattr(window, "_hWnd", None)
    if not handle:
        return None
    try:
        return win32process.GetWindowThreadProcessId(handle)[1] or None
    except (OSError, win32api.error):
        return None


def process_executable(process_id):
    # Limited query access also works for elevated apps without reading memory.
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(0x1000, False, process_id)
    if not handle:
        return None
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return buffer.value
    finally:
        kernel32.CloseHandle(handle)
    return None


@lru_cache(maxsize=256)
def executable_program_name(executable):
    stem = Path(executable).stem
    known = PROGRAMS.get(stem.casefold())
    if known:
        return known
    try:
        translations = win32api.GetFileVersionInfo(executable, r"\VarFileInfo\Translation") or []
        for language, codepage in translations:
            description = win32api.GetFileVersionInfo(executable, rf"\StringFileInfo\{language:04x}{codepage:04x}\FileDescription")
            if isinstance(description, str) and description.strip():
                return description.strip(), (stem,)
    except (OSError, win32api.error, TypeError, ValueError):
        pass
    return stem, ()


def split_window_title(title, program, aliases=()):
    """Remove only a matching application prefix/suffix; retain filename dashes."""
    title = title.strip()
    for name in sorted({program, *aliases}, key=len, reverse=True):
        if not name:
            continue
        if title.casefold() == name.casefold():
            return ""
        for separator in SEPARATORS:
            suffix, prefix = separator + name, name + separator
            if title.casefold().endswith(suffix.casefold()):
                return title[:-len(suffix)].strip()
            if title.casefold().startswith(prefix.casefold()):
                return title[len(prefix):].strip()
    return title


def infer_program_from_title(title):
    for program, aliases in PROGRAMS.values():
        document = split_window_title(title, program, aliases)
        if document != title.strip():
            return program, document
    return "Aplikacja", title.strip()


@dataclass(frozen=True)
class WindowEntry:
    window: object
    program: str
    document: str
    process_id: int | None = None

    @property
    def key(self):
        handle = getattr(self.window, "_hWnd", None)
        return f"{handle}:{self.process_id}" if handle else f"object:{id(self.window)}"

    @property
    def label(self):
        return f"{self.program} — {self.document}" if self.document else self.program


def describe_window(window, process_paths=None):
    title = (getattr(window, "title", "") or "").strip()
    process_id = window_process_id(window)
    executable = None
    if process_id:
        if process_paths is None:
            process_paths = {}
        if process_id not in process_paths:
            process_paths[process_id] = process_executable(process_id)
        executable = process_paths[process_id]
    if executable and Path(executable).stem.casefold() not in HOST_PROCESSES:
        program, aliases = executable_program_name(executable)
        document = split_window_title(title, program, aliases)
    else:
        program, document = infer_program_from_title(title)
    return WindowEntry(window, program, document, process_id)


def window_is_available(entry):
    handle = getattr(entry.window, "_hWnd", None)
    if not handle:
        return True  # Non-native window adapters (also used by the UI tests).
    return bool(win32gui.IsWindow(handle)) and window_process_id(entry.window) == entry.process_id
