"""Author credit and the application's bundled license."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from app_identity import apply_window_icon
from ui_widgets import BACKGROUND, SURFACE, TEXT, MUTED, RoundedButton


AUTHOR_NOTE = "Stworzone przez Szymona Bartosa"
LICENSE_TEXT = (Path(__file__).resolve().parent / "LICENSE.txt").read_text(encoding="utf-8").strip()


class InformationDialog(tk.Toplevel):
    def __init__(self, parent, version, brand_icon):
        super().__init__(parent)
        self.withdraw()
        self.title("Informacje — MiniScreenShot")
        apply_window_icon(self)
        self.configure(bg=BACKGROUND)
        self.transient(parent)
        self.resizable(True, True)
        scale = parent.winfo_fpixels("1i") / 96
        px = lambda value: round(value * scale)
        width = min(px(640), self.winfo_screenwidth() - px(48))
        height = min(px(480), self.winfo_screenheight() - px(80))
        self.geometry(f"{width}x{height}")
        self.minsize(min(px(400), width), min(px(320), height))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        header = tk.Frame(self, bg=BACKGROUND, padx=px(22), pady=px(18))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        tk.Label(header, text="  MiniScreenShot", image=brand_icon, compound="left",
                 bg=BACKGROUND, fg=TEXT, font=("Segoe UI", 18, "bold"), anchor="w").grid(row=0, column=0, sticky="ew")
        tk.Label(header, text=f"Wersja {version}", bg=BACKGROUND, fg=MUTED,
                 font=("Segoe UI", 9), anchor="w").grid(row=1, column=0, sticky="ew", pady=(px(4), px(12)))
        self.author_label = tk.Label(header, text=AUTHOR_NOTE, bg=BACKGROUND, fg="#a5b4fc",
                                     font=("Segoe UI", 11), anchor="w", justify="left")
        self.author_label.grid(row=2, column=0, sticky="ew")
        tk.Label(self, text="Warunki licencji", bg=BACKGROUND, fg=TEXT,
                 font=("Segoe UI", 11, "bold"), anchor="w").grid(row=1, column=0, sticky="ew", padx=px(22), pady=(0, px(8)))

        content = tk.Frame(self, bg=SURFACE)
        content.grid(row=2, column=0, sticky="nsew", padx=px(22))
        content.rowconfigure(0, weight=1)
        content.columnconfigure(0, weight=1)
        self.license_text = tk.Text(content, wrap="word", font=("Segoe UI", 10), bg=SURFACE, fg=TEXT,
                                    selectbackground="#4f46e5", selectforeground="white", relief="flat",
                                    highlightthickness=1, highlightbackground="#25324a", padx=px(14), pady=px(12),
                                    width=1, height=1)
        self.license_text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(content, orient="vertical", command=self.license_text.yview,
                                style="Preview.Vertical.TScrollbar")
        scroll.grid(row=0, column=1, sticky="ns")
        self.license_text.configure(yscrollcommand=scroll.set)
        self.license_text.insert("1.0", LICENSE_TEXT)
        self.license_text.configure(state="disabled")

        footer = tk.Frame(self, bg=BACKGROUND, padx=px(22), pady=px(16))
        footer.grid(row=3, column=0, sticky="ew")
        self.close_button = RoundedButton(footer, "Zamknij", self.destroy, primary=True, compact=True)
        self.close_button.pack(side="right")
        self.bind("<Escape>", lambda event: self.destroy())
        self.bind("<Configure>", lambda event: self.author_label.configure(wraplength=max(100, event.width - px(44)))
                  if event.widget is self else None)

        self.update_idletasks()
        x = max(0, min(parent.winfo_rootx() + (parent.winfo_width() - width) // 2, self.winfo_screenwidth() - width))
        y = max(0, min(parent.winfo_rooty() + (parent.winfo_height() - height) // 2, self.winfo_screenheight() - height))
        self.geometry(f"+{x}+{y}")
        self.deiconify()
        self.lift()
        self.close_button.focus_set()
