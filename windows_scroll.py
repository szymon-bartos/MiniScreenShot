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
from PIL import Image, ImageChops, ImageGrab

from scroll_capture import CaptureCancelled, ScrollCaptureError, frames_equal, scroll_frames_equal, scroll_motion_region
from desktop_capture import DesktopFrameGrabber

logger = logging.getLogger(__name__)


def render_stable(first, second, axis="y"):
    # Small smooth-scroll movements must not count as stable just because the
    # screenshot matcher tolerates antialiasing differences below 18 levels.
    region = scroll_motion_region(first, second, axis)
    if region is not None:
        first, second = first.crop(region), second.crop(region)
    scale = min(1, 320 / max(first.size))
    if scale < 1:
        size = tuple(max(1, round(value * scale)) for value in first.size)
        first = first.resize(size, Image.Resampling.BILINEAR)
        second = second.resize(size, Image.Resampling.BILINEAR)
    histogram = ImageChops.difference(first, second).convert("L").histogram()
    pixels = first.width * first.height
    if sum(level * count for level, count in enumerate(histogram)) / pixels < 0.35:
        return True
    # Preserve tolerance for a small animated advertisement or blinking caret.
    return region is None and sum(histogram[18:]) / pixels >= 0.0015 and frames_equal(first, second)


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
    # A selected capture target can be rejected by Windows' foreground lock
    # after our Tk window is withdrawn. Share the foreground input queue only
    # for activation, and always detach before capturing or sending any input.
    attached = None
    try:
        foreground = win32gui.GetForegroundWindow()
        thread = win32api.GetCurrentThreadId()
        foreground_thread = win32process.GetWindowThreadProcessId(foreground)[0] if foreground else thread
        if foreground_thread != thread:
            win32process.AttachThreadInput(thread, foreground_thread, True)
            attached = (thread, foreground_thread)
        win32gui.BringWindowToTop(handle)
        win32gui.SetForegroundWindow(handle)
    except win32gui.error:
        pass
    finally:
        if attached is not None:
            win32process.AttachThreadInput(*attached, False)
    if foreground_matches(handle):
        return
    logger.warning("Capture target activation failed: target=%s, foreground=%s", handle, win32gui.GetForegroundWindow())
    raise ScrollCaptureError("Nie udało się uaktywnić wybranego okna. Zamknij jego otwarte menu lub komunikat i spróbuj ponownie.")


class SCROLLINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("fMask", wintypes.UINT),
                ("nMin", ctypes.c_int), ("nMax", ctypes.c_int), ("nPage", wintypes.UINT),
                ("nPos", ctypes.c_int), ("nTrackPos", ctypes.c_int)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", wintypes.WPARAM)]


class INPUTPAYLOAD(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("payload", INPUTPAYLOAD)]


class WindowsScrollDriver:
    def __init__(self, window):
        self.handle = window._hWnd
        self.original_cursor = win32api.GetCursorPos()
        self.bbox = self._client_bbox()
        self.pointer = ((self.bbox[0] + self.bbox[2]) // 2, (self.bbox[1] + self.bbox[3]) // 2)
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.user32.GetScrollInfo.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.POINTER(SCROLLINFO)]
        self.user32.GetScrollInfo.restype = wintypes.BOOL
        self.user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
        self.user32.SendInput.restype = wintypes.UINT
        self.scroll_handles = {}
        self.pulse = lambda: None
        self.frame_guard = nullcontext
        self._last_frame = None
        self._scroll_time = None
        self._content_region = None
        self._browser = win32gui.GetClassName(self.handle).startswith(("Mozilla", "Chrome_"))
        self._corner_style = None
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
        # Windows 11 rounds browser client corners, hiding real page pixels.
        # Keep the rectangle visible during capture and restore its preference.
        try:
            dwmapi = ctypes.WinDLL("dwmapi")
            signature = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
            dwmapi.DwmGetWindowAttribute.argtypes = signature
            dwmapi.DwmSetWindowAttribute.argtypes = signature
            original = ctypes.c_int()
            square = ctypes.c_int(1)
            if dwmapi.DwmGetWindowAttribute(self.handle, 33, ctypes.byref(original), ctypes.sizeof(original)) == 0:
                if dwmapi.DwmSetWindowAttribute(self.handle, 33, ctypes.byref(square), ctypes.sizeof(square)) == 0:
                    self._corner_style = (dwmapi, original)
                    dwmapi.DwmFlush()
        except OSError:
            pass
        self._grabber = None
        try:
            self._grabber = DesktopFrameGrabber(self.bbox)
        except OSError as exc:
            logger.warning("Direct rectangle capture unavailable; using Pillow: %s", exc)
        self._excel = None
        if win32gui.GetClassName(self.handle) == "XLMAIN":
            try:
                from excel_scroll import ExcelSheetScroll
                self._excel = ExcelSheetScroll(self.handle, self.bbox)
                self._content_region = self._excel.region
                logger.info("Excel data bounds: row=%s column=%s content=%s", self._excel.last_row, self._excel.last_column, self._excel.region)
            except Exception as exc:
                self.close()
                if isinstance(exc, ScrollCaptureError):
                    raise
                raise ScrollCaptureError("Nie udało się odczytać granic danych Excela. Zakończ edycję komórki i zamknij okna dialogowe.") from exc

    def _client_bbox(self):
        if not win32gui.IsWindow(self.handle):
            raise ScrollCaptureError("Wybrane okno zostało zamknięte.")
        left, top, right, bottom = win32gui.GetClientRect(self.handle)
        start = win32gui.ClientToScreen(self.handle, (left, top))
        end = win32gui.ClientToScreen(self.handle, (right, bottom))
        return (*start, *end)

    def check_cancelled(self):
        getattr(self, "pulse", lambda: None)()
        if win32api.GetAsyncKeyState(0x1B) & 0x8000:
            raise CaptureCancelled("Anulowano przechwytywanie klawiszem Esc.")

    def _check(self):
        self.check_cancelled()
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
        if getattr(self, "_excel", None) is not None:
            return self._excel.at_edge(axis, direction)
        handle = self.scroll_handles.get(axis)
        info = self._scroll_info(handle, axis) if handle else None
        if info is None:
            return None
        end = max(info.nMin, info.nMax - info.nPage + 1)
        return info.nPos <= info.nMin if direction < 0 else info.nPos >= end

    def scroll(self, axis, direction, units):
        self._check()
        self._scroll_axis = axis
        if getattr(self, "_excel", None) is not None:
            self._excel.scroll(axis, direction, units)
            self._scroll_time = time.monotonic()
            return
        win32api.SetCursorPos(self.pointer)
        # Refresh the native hit test before posting wheel input. Browser
        # content can change its input child after startup or navigation.
        target = win32gui.WindowFromPoint(self.pointer)
        hovered = bool(target and win32gui.GetAncestor(target, 2) == win32gui.GetAncestor(self.handle, 2))
        if not hovered:
            target = self.input_handle
        # Send to the content under the pointer, not the last focused control.
        # WM_MOUSEWHEEL propagates through parents when a child does not handle it.
        delta = direction * units * 120 * (-1 if axis == "y" else 1)
        coordinates = (self.pointer[0] & 0xffff) | ((self.pointer[1] & 0xffff) << 16)
        if getattr(self, "_browser", False) and hovered:
            # Firefox uses GetMessagePos in addition to WM_MOUSEWHEEL.lParam.
            # A posted message can retain a stale point over its toolbar. Real
            # input supplies the native event position; guard both focus and
            # the window under the cursor before injecting it.
            if any(win32api.GetAsyncKeyState(key) & 0x8000 for key in (0x10, 0x11, 0x12)):
                raise ScrollCaptureError("Zwolnij klawisze Ctrl, Alt i Shift podczas przewijania. Zachowano wcześniejszą część zrzutu.")
            event = INPUT()
            event.payload.mi.mouseData = delta & 0xffffffff
            event.payload.mi.dwFlags = 0x0800 if axis == "y" else 0x1000
            if self.user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT)) != 1:
                raise ScrollCaptureError("Windows nie przekazał przewijania do przeglądarki. Zachowano wcześniejszą część zrzutu.")
        else:
            win32gui.PostMessage(target, 0x020A if axis == "y" else 0x020E,
                                 (delta & 0xffff) << 16, coordinates)
        self._scroll_time = time.monotonic()

    def set_content_region(self, region):
        self._content_region = region

    def capture_bounds(self, axes):
        return self._excel.capture_bounds(axes) if getattr(self, "_excel", None) is not None else None

    def scroll_displacement(self, axis):
        return self._excel.delta[axis] if getattr(self, "_excel", None) is not None else None

    def snapshot(self):
        self._check()
        previous = self._grab()
        started = time.monotonic()
        pending = self._scroll_time is not None
        axis = getattr(self, "_scroll_axis", "y")
        region = getattr(self, "_content_region", None)
        content = lambda frame: frame.crop(region) if region is not None else frame
        last_content = content(self._last_frame) if self._last_frame is not None else None
        previous_content = content(previous)
        moved = pending and last_content is not None and not scroll_frames_equal(last_content, previous_content, axis)
        minimum = 0.10 if self._browser else 0.04
        # Busy browser pages can dispatch/render wheel input well after 250 ms.
        # Apply the extra grace only while no movement has appeared.
        unchanged_wait = 0.65 if self._browser else 0.16
        stable_samples = 4 if self._browser else 2
        stable = 0
        while time.monotonic() - started < 1.0:
            time.sleep(0.025)
            self._check()
            current = self._grab()
            current_content = content(current)
            if pending and not moved and last_content is not None:
                moved = not scroll_frames_equal(last_content, current_content, axis)
            stable = stable + 1 if render_stable(previous_content, current_content, axis) else 0
            age = time.monotonic() - (self._scroll_time if pending else started)
            waited = time.monotonic() - started
            if stable >= stable_samples and age >= minimum and (not pending or moved or waited >= unchanged_wait):
                previous = current
                break
            previous = current
            previous_content = current_content
        self._scroll_time = None
        self._last_frame = previous
        return previous

    def _grab(self):
        with self.frame_guard():
            if self._grabber is not None:
                try:
                    return self._grabber.grab()
                except OSError as exc:
                    logger.warning("Direct rectangle capture failed; using Pillow: %s", exc)
                    self._grabber.close()
                    self._grabber = None
            return ImageGrab.grab(bbox=self.bbox, all_screens=True)

    def close(self):
        try:
            if self._grabber is not None:
                self._grabber.close()
                self._grabber = None
            self._last_frame = None
        finally:
            if self._corner_style is not None:
                dwmapi, original = self._corner_style
                dwmapi.DwmSetWindowAttribute(self.handle, 33, ctypes.byref(original), ctypes.sizeof(original))
                self._corner_style = None
            win32api.SetCursorPos(self.original_cursor)
