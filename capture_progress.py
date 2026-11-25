"""Non-activating progress placed outside captured pixels without flashing."""
import ctypes
import math
import time
import tkinter as tk
from contextlib import contextmanager

import win32con
import win32gui
import win32api

from ui_widgets import SURFACE, TEXT, MUTED
from localization import LocalizedUI, msg
from windows_coordinates import physical_coordinates


def outside(rect, bbox):
    return rect[2] <= bbox[0] or rect[0] >= bbox[2] or rect[3] <= bbox[1] or rect[1] >= bbox[3]


def progress_placement(bbox, monitors, scale):
    """Prefer a card beside the source; a compact strip can fit the taskbar."""
    width, height = round(350 * scale), round(150 * scale)
    compact_width, compact_height = round(760 * scale), round(36 * scale)

    def candidates(area, size, gap):
        left, top, right, bottom = area
        bands = ((left, top, min(right, bbox[0]), bottom),
                 (max(left, bbox[2]), top, right, bottom),
                 (left, top, right, min(bottom, bbox[1])),
                 (left, max(top, bbox[3]), right, bottom))
        for x0, y0, x1, y1 in bands:
            w, h = size
            if x1 - x0 < w + 2 * gap or y1 - y0 < h + 2 * gap:
                continue
            x = min(x1 - w - gap, max(x0 + gap, bbox[2] - w - gap))
            y = min(y1 - h - gap, max(y0 + gap, bbox[3] - h - gap))
            yield (x, y, x + w, y + h)

    for compact, key, size, gap in ((False, "Work", (width, height), round(8 * scale)),
                                    (True, "Monitor", (compact_width, compact_height), max(1, round(2 * scale)))):
        for monitor in monitors:
            places = list(candidates(monitor[key], size, gap))
            if places:
                rect = min(places, key=lambda r: (r[2] - bbox[2]) ** 2 + (r[3] - bbox[3]) ** 2)
                return rect, compact, True
    # True full-screen with no spare monitor has no safe place for an overlay.
    # Hide it once for the capture rather than toggling it for every frame.
    work = monitors[0]["Work"]
    x, y = max(work[0], work[2] - width - 8), max(work[1], work[3] - height - 8)
    return (x, y, x + width, y + height), False, False


class CaptureProgress:
    @physical_coordinates
    def __init__(self, root, bbox, ui=None):
        self.root = root
        self.ui = ui if ui is not None else LocalizedUI()
        self.started = time.monotonic()
        self.last_paint = 0
        self.closed = False
        self.window = tk.Toplevel(root)
        self.window.withdraw()
        self.window.overrideredirect(True)
        # Layered + transparent makes mouse/wheel input pass to other processes.
        self.window.attributes("-alpha", 1.0)
        self.window.configure(bg="#334155")
        scale = root.winfo_fpixels("1i") / 96
        px = lambda value: round(value * scale)
        primary = win32api.MonitorFromRect(bbox, 2)
        monitors = [primary] + [handle for handle, _, _ in win32api.EnumDisplayMonitors() if handle != primary]
        rect, compact, self.outside_capture = progress_placement(bbox, [win32api.GetMonitorInfo(h) for h in monitors], scale)
        x, y, right, bottom = rect
        width, height = right - x, bottom - y
        self.window.geometry(f"{width}x{height}")
        card = tk.Frame(self.window, bg=SURFACE, padx=px(8 if compact else 14), pady=px(4 if compact else 12))
        card.pack(fill="both", expand=True, padx=1, pady=1)
        card.columnconfigure(1, weight=1)
        spinner_size = px(20 if compact else 28)
        self.spinner = tk.Canvas(card, width=spinner_size, height=spinner_size, bg=SURFACE, bd=0, highlightthickness=0)
        self.spinner.grid(row=0, column=0, rowspan=1 if compact else 2, padx=(0, px(12)))
        self.spinner.create_oval(px(3), px(3), spinner_size - px(3), spinner_size - px(3), outline="#293854", width=px(3))
        self.arc = self.spinner.create_arc(px(3), px(3), spinner_size - px(3), spinner_size - px(3), start=0, extent=100,
                                           outline="#a5b4fc", width=px(3), style="arc")
        if not compact:
            self.ui.widget(tk.Label, card, text="Tworzę pełny zrzut", font=("Segoe UI", 10, "bold"),
                           fg=TEXT, bg=SURFACE, anchor="w").grid(row=0, column=1, sticky="ew")
        self.phase = self.ui.widget(tk.Label, card, text="Ustalam granice zawartości…", font=("Segoe UI", 9),
                              fg=MUTED, bg=SURFACE, anchor="w", justify="left", wraplength=0 if compact else px(270))
        self.phase.grid(row=0 if compact else 1, column=1, sticky="ew", pady=0 if compact else (px(3), 0))
        self.capture_hint = self.ui.widget(tk.Label, card,
                                         text="Nie poruszaj myszką i nie przełączaj okna.",
                                         font=("Segoe UI", 9), fg="#fbbf24", bg=SURFACE,
                                         anchor="w", justify="left", wraplength=0 if compact else px(320))
        self.capture_hint.grid(row=0 if compact else 2, column=2 if compact else 0,
                               columnspan=1 if compact else 2, sticky="ew", padx=(px(12), px(12)) if compact else 0,
                               pady=0 if compact else (px(8), 0))
        self.elapsed = self.ui.widget(tk.Label, card, font=("Segoe UI", 8), fg="#a5b4fc", bg=SURFACE, anchor="w")
        self.elapsed.grid(row=0 if compact else 3, column=3 if compact else 1, sticky="ew",
                          pady=0 if compact else (px(6), 0))
        if compact:
            self.phase.configure(width=1)
        self.window.update_idletasks()
        self.handle = win32gui.GetAncestor(self.window.winfo_id(), 2)
        style = win32gui.GetWindowLong(self.handle, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(self.handle, win32con.GWL_EXSTYLE,
                              style | 0x08000000 | win32con.WS_EX_TOOLWINDOW | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_LAYERED)
        win32gui.SetLayeredWindowAttributes(self.handle, 0, 255, win32con.LWA_ALPHA)
        win32gui.SetWindowPos(self.handle, win32con.HWND_TOPMOST, x, y, width, height, win32con.SWP_NOACTIVATE)
        self.window.deiconify()
        self._show()
        self.pump()

    @physical_coordinates
    def _show(self):
        win32gui.SetWindowPos(self.handle, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                              win32con.SWP_NOACTIVATE | win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)

    def set_message(self, message):
        self.ui.set(self.phase, text=message)
        self.pump(force=True)

    def pump(self, force=False):
        if self.closed:
            return
        now = time.monotonic()
        if not force and now - self.last_paint < 0.045:
            return
        self.last_paint = now
        self.spinner.itemconfigure(self.arc, start=-(now - self.started) * 240 % 360)
        self.ui.set(self.elapsed, text=msg("{seconds} s  ·  Esc: anuluj", seconds=math.floor(now - self.started)))
        self.window.update_idletasks()

    @contextmanager
    def capture_frame(self):
        if not self.closed and not self.outside_capture and win32gui.IsWindowVisible(self.handle):
            win32gui.ShowWindow(self.handle, win32con.SW_HIDE)
            ctypes.windll.dwmapi.DwmFlush()
        yield

    def close(self):
        if not self.closed:
            self.closed = True
            self.window.destroy()
