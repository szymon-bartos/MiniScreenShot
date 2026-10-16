"""Shared artwork and Windows identity for every application window."""
import ctypes
import sys
from pathlib import Path

from PIL import Image, ImageTk

APP_USER_MODEL_ID = "MiniScreenShot.Desktop"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
ICON_PATH = ASSETS_DIR / "capture-frame.ico"
ARTWORK_PATH = ASSETS_DIR / "capture-frame.png"


def set_process_app_id():
    if sys.platform == "win32":
        setter = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        setter.argtypes = [ctypes.c_wchar_p]
        setter.restype = ctypes.c_long
        setter(APP_USER_MODEL_ID)


def apply_app_icon(root):
    # The default also covers future previews, diagnostics and other Toplevels.
    root.iconbitmap(default=str(ICON_PATH))
    apply_window_icon(root)
    size = max(16, round(24 * root.winfo_fpixels("1i") / 96))
    with Image.open(ARTWORK_PATH) as artwork:
        root.app_brand_icon = ImageTk.PhotoImage(artwork.resize((size, size), Image.Resampling.LANCZOS), master=root)
    return root.app_brand_icon


def apply_window_icon(window):
    window.iconbitmap(str(ICON_PATH))
