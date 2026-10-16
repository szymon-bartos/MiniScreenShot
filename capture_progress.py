"""Small non-activating progress panel, excluded from desktop screenshots."""
import ctypes
import math
import sys
import time
import tkinter as tk
from contextlib import contextmanager
from ctypes import wintypes

import win32con
import win32gui
import win32api

from ui_widgets import SURFACE, TEXT, MUTED
from localization import LocalizedUI, msg


class CaptureProgress:
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
        self.window.attributes("-alpha", 0.97)
        self.window.configure(bg="#334155")
        scale = root.winfo_fpixels("1i") / 96
        px = lambda value: round(value * scale)
        width, height = px(350), px(110)
        work = win32api.GetMonitorInfo(win32api.MonitorFromRect(bbox, 2))["Work"]
        x = min(work[2] - width - px(16), max(work[0] + px(8), bbox[2] - width - px(16)))
        y = min(work[3] - height - px(16), max(work[1] + px(8), bbox[3] - height - px(16)))
        self.window.geometry(f"{width}x{height}{x:+d}{y:+d}")
        card = tk.Frame(self.window, bg=SURFACE, padx=px(14), pady=px(12))
        card.pack(fill="both", expand=True, padx=1, pady=1)
        card.columnconfigure(1, weight=1)
        self.spinner = tk.Canvas(card, width=px(28), height=px(28), bg=SURFACE, bd=0, highlightthickness=0)
        self.spinner.grid(row=0, column=0, rowspan=2, padx=(0, px(12)))
        self.spinner.create_oval(px(3), px(3), px(25), px(25), outline="#293854", width=px(3))
        self.arc = self.spinner.create_arc(px(3), px(3), px(25), px(25), start=0, extent=100,
                                           outline="#a5b4fc", width=px(3), style="arc")
        self.ui.widget(tk.Label, card, text="Tworzę pełny zrzut", font=("Segoe UI", 10, "bold"),
                 fg=TEXT, bg=SURFACE, anchor="w").grid(row=0, column=1, sticky="ew")
        self.phase = self.ui.widget(tk.Label, card, text="Ustalam granice zawartości…", font=("Segoe UI", 9),
                              fg=MUTED, bg=SURFACE, anchor="w", justify="left", wraplength=px(270))
        self.phase.grid(row=1, column=1, sticky="ew", pady=(px(3), 0))
        self.elapsed = self.ui.widget(tk.Label, card, font=("Segoe UI", 8), fg="#a5b4fc", bg=SURFACE, anchor="w")
        self.elapsed.grid(row=2, column=1, sticky="ew", pady=(px(6), 0))
        self.window.update_idletasks()
        self.handle = win32gui.GetAncestor(self.window.winfo_id(), 2)
        style = win32gui.GetWindowLong(self.handle, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(self.handle, win32con.GWL_EXSTYLE,
                              style | 0x08000000 | win32con.WS_EX_TOOLWINDOW | win32con.WS_EX_TRANSPARENT)
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
        self.excluded = sys.getwindowsversion().build >= 19041 and bool(user32.SetWindowDisplayAffinity(self.handle, 0x11))
        self.window.deiconify()
        self._show()
        self.pump()

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
        hide = not self.excluded and not self.closed
        if hide:
            win32gui.ShowWindow(self.handle, win32con.SW_HIDE)
            ctypes.windll.dwmapi.DwmFlush()
        try:
            yield
        finally:
            if hide and not self.closed:
                self._show()

    def close(self):
        if not self.closed:
            self.closed = True
            self.window.destroy()
