"""Use physical desktop pixels across monitors, even in legacy DPI hosts."""
import ctypes
from contextlib import contextmanager
from functools import lru_cache, wraps
import sys


@lru_cache(maxsize=1)
def _dpi_api():
    if sys.platform != "win32":
        return None
    api = ctypes.WinDLL("user32", use_last_error=True)
    for name in ("SetThreadDpiAwarenessContext", "SetProcessDpiAwarenessContext"):
        method = getattr(api, name, None)
        if method is not None:
            method.argtypes = [ctypes.c_void_p]
            method.restype = ctypes.c_void_p if name.startswith("SetThread") else ctypes.c_int
    return api


def configure_process_dpi():
    """Run before Tk/Pillow/PyAutoGUI; frozen builds also declare PMv2."""
    api = _dpi_api()
    if api is None:
        return
    setter = getattr(api, "SetProcessDpiAwarenessContext", None)
    if setter is not None:
        if setter(ctypes.c_void_p(-4)) or ctypes.get_last_error() == 5:
            # A manifest or an embedding host may have set the policy already.
            return
    try:
        setter = ctypes.WinDLL("shcore").SetProcessDpiAwareness
        setter.argtypes = [ctypes.c_int]
        setter.restype = ctypes.c_long
        if setter(2) in (0, -2147024891):
            return
    except (AttributeError, OSError):
        pass
    api.SetProcessDPIAware()


@contextmanager
def physical_pixels():
    api = _dpi_api()
    setter = getattr(api, "SetThreadDpiAwarenessContext", None)
    if setter is None:
        yield
        return
    previous = setter(ctypes.c_void_p(-4)) or setter(ctypes.c_void_p(-3))
    if not previous:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        yield
    finally:
        setter(previous)


def physical_coordinates(function):
    @wraps(function)
    def run(*args, **kwargs):
        with physical_pixels():
            return function(*args, **kwargs)
    return run


@physical_coordinates
def client_bounds(handle):
    import win32gui
    left, top, right, bottom = win32gui.GetClientRect(handle)
    return (*win32gui.ClientToScreen(handle, (left, top)),
            *win32gui.ClientToScreen(handle, (right, bottom)))


@physical_coordinates
def monitor_rectangles():
    import win32api
    return tuple(sorted(win32api.GetMonitorInfo(item[0])["Monitor"] for item in win32api.EnumDisplayMonitors()))


def rectangle_visible(bbox, monitors):
    """A virtual desktop's bounding box can contain gaps with no monitor."""
    if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
        return False
    remaining = [bbox]
    for screen in monitors:
        pieces = []
        for left, top, right, bottom in remaining:
            x0, y0 = max(left, screen[0]), max(top, screen[1])
            x1, y1 = min(right, screen[2]), min(bottom, screen[3])
            if x1 <= x0 or y1 <= y0:
                pieces.append((left, top, right, bottom))
                continue
            for rect in ((left, top, x0, bottom), (x1, top, right, bottom),
                         (x0, top, x1, y0), (x0, y1, x1, bottom)):
                if rect[2] > rect[0] and rect[3] > rect[1]:
                    pieces.append(rect)
        remaining = pieces
        if not remaining:
            return True
    return False
