"""Native wheel input and stable client-area frames for scrolling capture."""

import ctypes
import logging
import os
import time
from ctypes import wintypes
from contextlib import nullcontext

import win32api
import win32gui
import win32process
from PIL import ImageGrab

from scroll_capture import CaptureCancelled, ScrollCaptureError, frames_equal

logger = logging.getLogger(__name__)


def foreground_matches(handle):
    foreground = win32gui.GetForegroundWindow()
    return bool(foreground and win32gui.GetAncestor(foreground, 2) == win32gui.GetAncestor(handle, 2))


def ensure_window_foreground(handle, timeout=1.0):
    """Wait for native activation instead of assuming that activate() succeeded."""
    if foreground_matches(handle):
        return
    try:
        win32gui.SetForegroundWindow(handle)
    except win32gui.error:
        # Windows can report failure even though activation is still in flight.
        pass
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if foreground_matches(handle):
            return
        time.sleep(0.02)
    raise ScrollCaptureError("Nie udało się uaktywnić wybranego okna. Zamknij jego otwarte menu lub komunikat i spróbuj ponownie.")


class SCROLLINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("fMask", wintypes.UINT),
                ("nMin", ctypes.c_int), ("nMax", ctypes.c_int), ("nPage", wintypes.UINT),
                ("nPos", ctypes.c_int), ("nTrackPos", ctypes.c_int)]


class WindowsScrollDriver:
    def __init__(self, window):
        self.handle = window._hWnd
        self.original_cursor = win32api.GetCursorPos()
        self.bbox = self._client_bbox()
        self.pointer = ((self.bbox[0] + self.bbox[2]) // 2, (self.bbox[1] + self.bbox[3]) // 2)
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.user32.GetScrollInfo.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.POINTER(SCROLLINFO)]
        self.user32.GetScrollInfo.restype = wintypes.BOOL
        self.scroll_handles = {}
        self.pulse = lambda: None
        self.frame_guard = nullcontext
        ensure_window_foreground(self.handle)
        # Resolve a child within the selected window, even under a progress
        # overlay. Global wheel injection can otherwise go to an address bar.
        self.input_handle = self.handle
        for _ in range(16):
            child = win32gui.ChildWindowFromPointEx(self.input_handle,
                                                    win32gui.ScreenToClient(self.input_handle, self.pointer), 7)
            if not child or child == self.input_handle:
                break
            self.input_handle = child
        logger.info("Scroll input target=%s, class=%s, client=%s", self.input_handle,
                    win32gui.GetClassName(self.input_handle), self.bbox)
        candidate = self.input_handle
        while candidate:
            for axis in ("x", "y"):
                if axis not in self.scroll_handles and self._scroll_info(candidate, axis) is not None:
                    self.scroll_handles[axis] = candidate
            if candidate == self.handle:
                break
            candidate = win32gui.GetParent(candidate)
        win32api.SetCursorPos(self.pointer)

    def _client_bbox(self):
        if not win32gui.IsWindow(self.handle):
            raise ScrollCaptureError("Wybrane okno zostało zamknięte.")
        left, top, right, bottom = win32gui.GetClientRect(self.handle)
        start = win32gui.ClientToScreen(self.handle, (left, top))
        end = win32gui.ClientToScreen(self.handle, (right, bottom))
        return (*start, *end)

    def _check(self):
        getattr(self, "pulse", lambda: None)()
        if win32api.GetAsyncKeyState(0x1B) & 0x8000:
            raise CaptureCancelled("Anulowano przechwytywanie klawiszem Esc.")
        if self._client_bbox() != self.bbox:
            raise ScrollCaptureError("Położenie lub rozmiar okna zmieniły się podczas zrzutu.")
        if foreground_matches(self.handle):
            return
        # Withdrawing Tk windows can briefly return focus to the capture process.
        # Recover only our own activation; never send wheel input to another app.
        deadline = time.monotonic() + 0.3
        recovered = False
        while True:
            foreground = win32gui.GetForegroundWindow()
            if foreground and not recovered and win32process.GetWindowThreadProcessId(foreground)[1] == os.getpid():
                logger.info("Restoring capture focus from own window: target=%s, foreground=%s", self.handle, foreground)
                ensure_window_foreground(self.handle)
                recovered = True
            if foreground_matches(self.handle):
                return
            if win32api.GetAsyncKeyState(0x1B) & 0x8000:
                raise CaptureCancelled("Anulowano przechwytywanie klawiszem Esc.")
            if time.monotonic() >= deadline:
                break
            time.sleep(0.02)
        logger.warning("Capture focus changed: target=%s, foreground=%s, class=%s", self.handle, foreground,
                       win32gui.GetClassName(foreground) if foreground else "none")
        raise CaptureCancelled("Przerwano zrzut po przełączeniu do innej aplikacji. Pozostaw wybrane okno aktywne do zakończenia zrzutu; Esc anuluje.")

    def _scroll_info(self, handle, axis):
        info = SCROLLINFO()
        info.cbSize, info.fMask = ctypes.sizeof(info), 0x17
        if self.user32.GetScrollInfo(handle, 0 if axis == "x" else 1, ctypes.byref(info)):
            if info.nMax - info.nMin + 1 > info.nPage and info.nPage > 0:
                return info
        return None

    def at_edge(self, axis, direction):
        self._check()
        handle = self.scroll_handles.get(axis)
        info = self._scroll_info(handle, axis) if handle else None
        if info is None:
            return None
        end = max(info.nMin, info.nMax - info.nPage + 1)
        return info.nPos <= info.nMin if direction < 0 else info.nPos >= end

    def scroll(self, axis, direction, units):
        self._check()
        win32api.SetCursorPos(self.pointer)
        # Send to the content under the pointer, not the last focused control.
        # WM_MOUSEWHEEL propagates through parents when a child does not handle it.
        delta = direction * units * 120 * (-1 if axis == "y" else 1)
        coordinates = (self.pointer[0] & 0xffff) | ((self.pointer[1] & 0xffff) << 16)
        win32gui.PostMessage(self.input_handle, 0x020A if axis == "y" else 0x020E,
                             (delta & 0xffff) << 16, coordinates)
        time.sleep(0.12)

    def snapshot(self):
        self._check()
        previous = self._grab()
        stable = 0
        for _ in range(8):
            time.sleep(0.06)
            self._check()
            current = self._grab()
            stable = stable + 1 if frames_equal(previous, current) else 0
            if stable >= 2:
                return current
            previous = current
        return previous

    def _grab(self):
        with self.frame_guard():
            return ImageGrab.grab(bbox=self.bbox, all_screens=True)

    def close(self):
        win32api.SetCursorPos(self.original_cursor)
