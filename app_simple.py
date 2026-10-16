import os
import sys
import time
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from PIL import ImageGrab

ROOT_DIR = Path(__file__).resolve().parent
CAPTURE_DIR = ROOT_DIR / "captures"
CAPTURE_DIR.mkdir(exist_ok=True)


def save_capture(kind: str, source: str = "screen"):
    folder = Path(CAPTURE_DIR)
    folder.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = folder / f"{kind}_{stamp}.png"

    try:
        if source == "screen":
            img = ImageGrab.grab()
            img.save(path)
        else:
            raise ValueError("Nieobsługiwany typ zrzutu")

        return str(path)
    except Exception as exc:
        raise RuntimeError(str(exc)) from exc


class SimpleCaptureApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Screen Capture")
        self.root.geometry("420x220")
        self.root.resizable(False, False)
        self.root.configure(bg="#111827")

        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TButton", padding=(18, 10), font=("Segoe UI", 10, "bold"))
        style.configure("TLabel", background="#111827", foreground="#e5e7eb", font=("Segoe UI", 10))

        main = ttk.Frame(root, padding=20)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="Portable Screen Capture", font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 12))
        ttk.Label(main, text="Zrób prosty zrzut ekranu do pliku PNG.", foreground="#93c5fd").pack(anchor="w", pady=(0, 8))

        btns = ttk.Frame(main)
        btns.pack(fill="x", pady=(10, 8))

        ttk.Button(btns, text="Zrzut całego ekranu", command=self.capture_screen).pack(side="left", padx=(0, 10))
        ttk.Button(btns, text="Wybierz folder", command=self.choose_folder).pack(side="left")

        self.status = ttk.Label(main, text="Gotowy.", foreground="#a7f3d0")
        self.status.pack(anchor="w", pady=(18, 0))

    def choose_folder(self):
        folder = filedialog.askdirectory(title="Wybierz katalog zapisów")
        if folder:
            global CAPTURE_DIR
            CAPTURE_DIR = Path(folder)
            CAPTURE_DIR.mkdir(exist_ok=True)
            self.status.config(text=f"Folder zapisów: {folder}")

    def capture_screen(self):
        self.status.config(text="Robię zrzut ekranu...")
        self.root.update_idletasks()
        try:
            path = save_capture("screen")
            self.status.config(text=f"Zapisano: {path}")
            messagebox.showinfo("Gotowe", f"Zrzut zapisano w:\n{path}")
        except Exception as exc:
            self.status.config(text="Błąd: " + str(exc))
            messagebox.showerror("Błąd", str(exc))


def main():
    root = tk.Tk()
    SimpleCaptureApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
