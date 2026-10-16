import io
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

APP_VERSION = "1.1.8"

from tk_runtime import prepare_tk_runtime

prepare_tk_runtime()

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from PIL import Image, ImageChops, ImageGrab, ImageTk
import pyautogui
import pygetwindow as gw
from main_dashboard import MainDashboard
from preview_crop import InlineCropEditor
from preview_annotations import PreviewAnnotations
from window_catalog import window_process_id
from window_picker import InlineWindowPicker
from ui_widgets import BACKGROUND, SURFACE, TEXT, MUTED, RoundedButton, ToggleSwitch, RangeSlider
from scroll_capture import ScrollingCapture, ScrollCaptureError, CaptureCancelled
from windows_scroll import WindowsScrollDriver, ensure_window_foreground
from capture_progress import CaptureProgress
from app_identity import apply_app_icon, apply_window_icon, set_process_app_id
from app_information import InformationDialog
from app_storage import cache_session, configure_logging
from localization import LocalizedUI, LANGUAGES, load_language, remember_language, msg, error_message

DEFAULT_CAPTURE_DIR = Path("C:/Screenshots")
CAPTURE_DIR = DEFAULT_CAPTURE_DIR
LOG_PATH = configure_logging()
logger = logging.getLogger("WindowsCaptureStudio")


def timestamp_name(prefix: str) -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"


def save_image(img: Image.Image, prefix: str) -> str:
    folder = Path(CAPTURE_DIR)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / timestamp_name(prefix)
    img.save(path)
    return str(path)


class SelectionOverlay(tk.Toplevel):
    def __init__(self, callback, cancel_callback=None):
        super().__init__()
        apply_window_icon(self)
        self.callback = callback
        self.cancel_callback = cancel_callback
        self.withdraw()
        self.attributes("-fullscreen", True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.20)
        self.configure(bg="black")
        self.canvas = tk.Canvas(self, cursor="crosshair", bg="#000000", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.start_x = self.start_y = self.current_x = self.current_y = 0
        self.rect = None
        self.bind("<Escape>", self.cancel)
        self.protocol("WM_DELETE_WINDOW", self.cancel)

    def cancel(self, event=None):
        self.destroy()
        if self.cancel_callback:
            self.cancel_callback()

    def start_select(self):
        self.deiconify()
        self.focus_set()
        self.canvas.focus_set()
        self.canvas.update()

    def on_press(self, event):
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.current_x = event.x_root
        self.current_y = event.y_root
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.current_x, self.current_y, outline="#7dd3fc", width=2)

    def on_drag(self, event):
        self.current_x = event.x_root
        self.current_y = event.y_root
        if self.rect:
            self.canvas.coords(self.rect, self.start_x, self.start_y, self.current_x, self.current_y)

    def on_release(self, event):
        x1, x2 = sorted((self.start_x, event.x_root))
        y1, y2 = sorted((self.start_y, event.y_root))
        self.destroy()
        if x2 > x1 and y2 > y1:
            self.callback((x1, y1, x2, y2))
        elif getattr(self, "cancel_callback", None):
            self.cancel_callback()


class ScreenCaptureApp(MainDashboard, InlineCropEditor, PreviewAnnotations, InlineWindowPicker):
    @property
    def ui(self):
        if not hasattr(self, "_ui"):
            self._ui = LocalizedUI()
        return self._ui

    def __init__(self, root, language=None):
        self.root = root
        self._ui = LocalizedUI(load_language() if language is None else language)
        set_process_app_id()
        self.brand_icon = apply_app_icon(root)
        self.ui.title(self.root, f"MiniScreenShot v{APP_VERSION}")
        self.root.configure(bg="#0f172a")
        screen_w = self.root.winfo_screenwidth() if hasattr(self.root, "winfo_screenwidth") else 1280
        screen_h = self.root.winfo_screenheight() if hasattr(self.root, "winfo_screenheight") else 720
        scale = self.root.winfo_fpixels("1i") / 96
        target_w = min(round(1080 * scale), int(screen_w * 0.90))
        target_h = min(round(780 * scale), int(screen_h * 0.86))
        self.root.minsize(min(round(480 * scale), target_w), min(round(480 * scale), target_h))
        self.root.geometry(f"{target_w}x{target_h}+{(screen_w - target_w) // 2}+{max(0, (screen_h - target_h) // 2 - 20)}")
        self.root.resizable(True, True)

        self.style = ttk.Style(root)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        self.style.configure("TFrame", background="#0b1020")
        self.style.configure("TLabel", background="#0b1020", foreground="#e2e8f0", font=("Segoe UI", 10))
        self.style.configure("Header.TLabel", background="#111827", foreground="#f8fafc", font=("Segoe UI", 22, "bold"))
        self.style.configure("Muted.TLabel", background="#111827", foreground="#94a3b8", font=("Segoe UI", 10))
        self.style.configure("Status.TLabel", background="#0b1020", foreground="#93c5fd", font=("Segoe UI", 10))

        self.style.configure("Action.TButton", padding=(12, 8), relief="flat", background="#1d4ed8", foreground="#ffffff", font=("Segoe UI", 10, "bold"))
        self.style.map("Action.TButton", background=[("active", "#2563eb"), ("pressed", "#1e40af")], foreground=[("active", "#ffffff")])

        self.style.configure("Secondary.TButton", padding=(10, 7), relief="flat", background="#111827", foreground="#e2e8f0", font=("Segoe UI", 10, "bold"))
        self.style.map("Secondary.TButton", background=[("active", "#1f2937"), ("pressed", "#0f172a")], foreground=[("active", "#ffffff")])

        self.style.configure("TCheckbutton", background="#0b1020", foreground="#e2e8f0", font=("Segoe UI", 10))
        self.style.configure("TLabelframe", background="#0b1020", borderwidth=1)
        self.style.configure("TLabelframe.Label", background="#0b1020", foreground="#7dd3fc", font=("Segoe UI", 10, "bold"))
        self.style.configure("TEntry", fieldbackground="#111827", foreground="#f8fafc", insertcolor="#f8fafc")
        self.style.configure("Annotation.TCombobox", fieldbackground=SURFACE, background=SURFACE,
                             foreground=TEXT, arrowcolor=MUTED, padding=5)
        self.style.map("Annotation.TCombobox", fieldbackground=[("readonly", SURFACE), ("disabled", BACKGROUND)],
                       foreground=[("disabled", MUTED), ("readonly", TEXT)])

        self.style.configure("Preview.TFrame", background="#0f172a")
        self.style.configure("Preview.TLabel", background="#0f172a", foreground="#cbd5e1", font=("Segoe UI", 10))
        self.style.configure("PreviewTitle.TLabel", background="#0f172a", foreground="#f8fafc", font=("Segoe UI", 14, "bold"))
        self.style.configure("PreviewStatus.TLabel", background="#0f172a", foreground="#94a3b8", font=("Segoe UI", 9))
        self.style.configure("Preview.Horizontal.TScale", background="#64748b", troughcolor="#1e293b", bordercolor="#1e293b", lightcolor="#64748b", darkcolor="#64748b")
        for orientation in ("Horizontal", "Vertical"):
            scrollbar_style = f"Preview.{orientation}.TScrollbar"
            self.style.configure(scrollbar_style, background="#334155", troughcolor="#080e1a", bordercolor="#080e1a", arrowcolor="#94a3b8", lightcolor="#334155", darkcolor="#334155")
            self.style.map(scrollbar_style, background=[("active", "#475569"), ("pressed", "#64748b")])

        self._build_dashboard(APP_VERSION, DEFAULT_CAPTURE_DIR)

    def set_language(self, language, persist=True):
        self.ui.set_language(language)
        self.language_var.set(LANGUAGES[language])
        if persist and not remember_language(language):
            self.set_status("Język zmieniono. Nie udało się zapamiętać wyboru.")
        self._filter_window_list()
        self._layout_footer_links()
        self.dashboard_layout = None
        self._update_responsive_layout()
        for window in self.root.winfo_children():
            if hasattr(window, "display_image"):
                self._localize_annotation_choices(window)
                self._schedule_preview_layout(window)
            if isinstance(window, InformationDialog):
                window.update_license()

    def _language_selected(self, event=None):
        language = next(code for code, label in LANGUAGES.items() if label == self.language_var.get())
        self.set_language(language)

    def choose_folder(self):
        folder = filedialog.askdirectory(title=self.ui.render("Wybierz katalog zapisu"))
        if folder:
            self.output_dir.set(folder)
            global CAPTURE_DIR
            CAPTURE_DIR = Path(folder)
            CAPTURE_DIR.mkdir(exist_ok=True)

    def set_status(self, message: str):
        self.ui.set(self.status, text=message)

    def _add_debug_log(self, message: str):
        if not hasattr(self, "_debug_lines"):
            self._debug_lines = []
        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"[{ts}] {message}"
        self._debug_lines.append(entry)
        if len(self._debug_lines) > 200:
            self._debug_lines = self._debug_lines[-200:]
        logger.info(message)

    def show_debug_log(self):
        dialog = tk.Toplevel(self.root)
        apply_window_icon(dialog)
        self.ui.title(dialog, "Diagnostyka i logi")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.geometry("700x420")

        text = tk.Text(dialog, wrap="word", font=("Consolas", 10), padx=10, pady=10)
        text.pack(fill="both", expand=True, padx=12, pady=(12, 8))

        try:
            with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except FileNotFoundError:
            content = ""

        if not content:
            content = "\n".join(self._debug_lines)

        if content:
            text.insert("1.0", content)
        else:
            self.ui.body(text, "Brak logów.")
        text.config(state="disabled")

        buttons = ttk.Frame(dialog)
        buttons.pack(fill="x", padx=12, pady=(0, 12))
        self.ui.widget(ttk.Button, buttons, text="Kopiuj", command=lambda: self._copy_debug_text(dialog, text)).pack(side="right")
        self.ui.widget(ttk.Button, buttons, text="Zamknij", command=dialog.destroy).pack(side="right", padx=(0, 8))

    def show_information(self):
        dialog = getattr(self, "information_window", None)
        if dialog is not None and dialog.winfo_exists():
            dialog.deiconify()
            dialog.lift()
            dialog.focus_set()
        else:
            self.information_window = InformationDialog(self.root, APP_VERSION, self.brand_icon, ui=self.ui)
        return self.information_window

    def _copy_debug_text(self, dialog, text_widget):
        try:
            text_widget.configure(state="normal")
            content = text_widget.get("1.0", "end")
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self.root.update()
            self.set_status("Log skopiowany do schowka.")
        except Exception as exc:
            self.set_status(msg("Błąd kopiowania logu: {error}", error=error_message(exc)))
        finally:
            text_widget.configure(state="disabled")
            dialog.destroy()

    def _show_capture_warning(self):
        if hasattr(self, "capture_notice"):
            self.capture_notice.grid_remove()
        scrolling = getattr(self, "selected_mode", "") == "window" and (self.vertical_var.get() or self.horizontal_var.get())
        if scrolling:
            message = ("Program przewinie zawartość i od razu połączy ją w pełny zrzut.\n"
                       "Pozostaw wybrane okno aktywne i nie używaj myszy podczas przewijania.\n"
                       "Esc lub przełączenie do innej aplikacji przerywa zrzut.")
        elif getattr(self, "selected_mode", "") == "area":
            message = "Zaznacz fragment ekranu myszą. Esc anuluje zaznaczanie."
        else:
            return
        self.ui.dialog(messagebox.showinfo,
            "Zrzut ekranu",
            message,
            parent=self.root,
        )

    def _show_preview(self, image: Image.Image, prefix: str, title: str = msg("Podgląd zrzutu")):
        preview = tk.Toplevel(self.root)
        preview.withdraw()
        apply_window_icon(preview)
        # A regular window keeps the native minimize, maximize and close buttons.
        self.ui.title(preview, msg("{title} — MiniScreenShot", title=title))
        preview.configure(bg=BACKGROUND)
        preview.protocol("WM_DELETE_WINDOW", lambda: self._discard_preview(preview, getattr(preview, "display_image", image)))

        screen_w = preview.winfo_screenwidth()
        screen_h = preview.winfo_screenheight()
        width = min(int(screen_w * 0.88), 1280)
        height = min(int(screen_h * 0.84), 860)
        preview.geometry(f"{width}x{height}+{(screen_w - width) // 2}+{max(0, (screen_h - height) // 2 - 20)}")
        preview.minsize(min(480, width), min(360, height))
        preview.resizable(True, True)
        preview.columnconfigure(0, weight=1)
        preview.rowconfigure(3, weight=1)

        owns_image = hasattr(image, "_capture_backing") or "capture_original_size" in image.info
        preview.display_image = image if owns_image else image.copy()
        preview.source_image = image if owns_image else None
        preview.zoom_percent = 100
        preview.fit_to_window = True
        preview.crop_active = False
        preview.crop_drag_mode = None
        preview.pending_crop = None
        preview.prefix = prefix
        preview.render_job = None
        preview.layout_job = None
        preview.toolbar_layout = None
        preview.focus_job = None
        preview.pin_var = tk.BooleanVar(preview, value=True)
        preview.pin_trace = preview.pin_var.trace_add("write", lambda *args: preview.attributes("-topmost", preview.pin_var.get()))

        header = tk.Frame(preview, bg=BACKGROUND, padx=18, pady=12)
        preview.header = header
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        preview.brand = self.ui.widget(tk.Label, header, text="  MiniScreenShot", image=self.brand_icon, compound="left",
                                 bg=BACKGROUND, fg="#a5b4fc", font=("Segoe UI", 9, "bold"), anchor="w")
        preview.brand.grid(row=0, column=0, sticky="w")
        preview.pin_group = tk.Frame(header, bg=SURFACE, padx=8)
        preview.pin_group.grid(row=0, column=1, sticky="e")
        self.ui.widget(tk.Label, preview.pin_group, text="Na wierzchu", bg=SURFACE, fg=MUTED, font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        preview.pin_switch = ToggleSwitch(preview.pin_group, preview.pin_var)
        preview.pin_switch.pack(side="left")
        preview.heading = self.ui.widget(tk.Label, header, text="Zrzut gotowy", bg=BACKGROUND, fg=TEXT, font=("Segoe UI", 18, "bold"), anchor="w")
        preview.heading.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        preview.source_label = self.ui.widget(tk.Label, header, text=msg("{title}", title=title).clipped(120), bg=BACKGROUND, fg=MUTED,
                                        font=("Segoe UI", 9), anchor="w", justify="left", wraplength=width - 40)
        preview.source_label.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(2, 0))

        preview.toolbar = tk.Frame(preview, bg=BACKGROUND, padx=12, pady=8)
        preview.toolbar.grid(row=1, column=0, sticky="ew")
        actions = tk.Frame(preview.toolbar, bg=BACKGROUND)
        edits = tk.Frame(preview.toolbar, bg=BACKGROUND)
        zoom = tk.Frame(preview.toolbar, bg=BACKGROUND)
        views = tk.Frame(preview.toolbar, bg=BACKGROUND)
        drawing = tk.Frame(preview.toolbar, bg=BACKGROUND)
        brush_color = tk.Frame(preview.toolbar, bg=BACKGROUND)
        brush_size = tk.Frame(preview.toolbar, bg=BACKGROUND)
        preview.toolbar_groups = (actions, edits, zoom, views, drawing, brush_color, brush_size)
        preview.toolbar_rows = [tk.Frame(preview.toolbar, bg=BACKGROUND) for _ in preview.toolbar_groups]
        preview.toolbar.columnconfigure(0, weight=1)
        self._build_annotation_controls(preview, drawing, brush_color, brush_size)

        preview.save_btn = self.ui.widget(RoundedButton, actions, text="Zapisz", command=lambda: self._confirm_save(preview, preview.display_image, prefix), primary=True, compact=True)
        preview.save_btn.pack(side="left", padx=(0, 6))
        preview.copy_btn = self.ui.widget(RoundedButton, actions, text="Kopiuj", command=lambda: self._copy_image_to_clipboard(preview, preview.display_image), compact=True)
        preview.copy_btn.pack(side="left")

        preview.crop_btn = self.ui.widget(RoundedButton, edits, text="Przytnij", command=lambda: self._toggle_crop_mode(preview, preview.display_image), compact=True)
        preview.crop_btn.grid(row=0, column=0)
        preview.accept_btn = self.ui.widget(RoundedButton, edits, text="Zatwierdź", command=lambda: self._accept_crop(preview), primary=True, compact=True)
        preview.accept_btn.grid(row=0, column=1, padx=(6, 0))
        preview.accept_btn.grid_remove()
        preview.reject_btn = self.ui.widget(RoundedButton, edits, text="Anuluj", command=lambda: self._reject_crop(preview), compact=True)
        preview.reject_btn.grid(row=0, column=2, padx=(6, 0))
        preview.reject_btn.grid_remove()

        preview.zoom_out = self.ui.widget(RoundedButton, zoom, text="−", command=lambda: self._set_preview_zoom(preview, -1), compact=True)
        preview.zoom_out.grid(row=0, column=0)
        preview.zoom_var = tk.DoubleVar(preview, value=100)
        preview.zoom_slider = RangeSlider(zoom, variable=preview.zoom_var,
                                          command=lambda value: self._apply_zoom_from_slider(preview, preview.display_image, float(value)))
        preview.zoom_slider.grid(row=0, column=1, sticky="ew", padx=8)
        zoom.columnconfigure(1, weight=1)
        preview.zoom_in = self.ui.widget(RoundedButton, zoom, text="+", command=lambda: self._set_preview_zoom(preview, 1), compact=True)
        preview.zoom_in.grid(row=0, column=2)
        preview.zoom_label = self.ui.widget(tk.Label, zoom, text="100%", width=5, anchor="e", bg=BACKGROUND, fg=MUTED, font=("Segoe UI", 9))
        preview.zoom_label.grid(row=0, column=3, padx=(6, 0))
        preview.fit_btn = self.ui.widget(RoundedButton, views, text="Dopasuj", command=lambda: self._fit_preview_image(preview), primary=True, compact=True)
        preview.fit_btn.pack(side="left", padx=(0, 6))
        preview.actual_size_btn = self.ui.widget(RoundedButton, views, text="100%", command=lambda: self._apply_zoom_from_slider(preview, preview.display_image, 100), compact=True)
        preview.actual_size_btn.pack(side="left")

        ttk.Separator(preview).grid(row=2, column=0, sticky="ew")
        content = tk.Frame(preview, bg="#080e1a")
        content.grid(row=3, column=0, sticky="nsew", padx=12, pady=(12, 0))
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)

        preview_canvas = tk.Canvas(content, bg="#080e1a", highlightthickness=0, cursor="arrow", width=1, height=1, takefocus=True)
        preview_canvas.grid(row=0, column=0, sticky="nsew")
        preview.pan_remainder = [0.0, 0.0]
        preview.wheel_zoom_delta = 0
        preview_canvas.bind("<MouseWheel>", lambda event: self._preview_mousewheel(preview, event))
        preview_canvas.bind("<Shift-MouseWheel>", lambda event: self._preview_mousewheel(preview, event))
        preview_canvas.bind("<Button-4>", lambda event: self._preview_mousewheel(preview, event, 120))
        preview_canvas.bind("<Button-5>", lambda event: self._preview_mousewheel(preview, event, -120))
        try:
            # Tk 9 exposes both precise touchpad axes in a single event.
            preview_canvas.bind("<TouchpadScroll>", lambda event: self._preview_touchpad_scroll(preview, event))
        except tk.TclError:
            pass  # Tk 8 delivers touchpad input as MouseWheel events instead.
        for key, dx, dy in (("Left", -48, 0), ("Right", 48, 0), ("Up", 0, -48), ("Down", 0, 48)):
            preview_canvas.bind(f"<{key}>", lambda event, dx=dx, dy=dy: self._pan_preview(preview, dx, dy))
        preview_canvas.bind("<Prior>", lambda event: self._pan_preview(preview, 0, -preview_canvas.winfo_height() * 0.85))
        preview_canvas.bind("<Next>", lambda event: self._pan_preview(preview, 0, preview_canvas.winfo_height() * 0.85))
        preview_canvas.zoom_factor = 1.0
        preview_canvas.bind("<Configure>", lambda event: self._schedule_preview_render(preview))
        preview_canvas.bind("<ButtonPress-1>", lambda event: self._preview_canvas_press(preview, event))
        preview_canvas.bind("<B1-Motion>", lambda event: self._preview_canvas_drag(preview, event))
        preview_canvas.bind("<ButtonRelease-1>", lambda event: self._preview_canvas_release(preview, event))
        preview_canvas.bind("<Motion>", lambda event: self._preview_crop_hover(preview, event))

        x_scroll = ttk.Scrollbar(content, orient="horizontal", command=preview_canvas.xview, style="Preview.Horizontal.TScrollbar")
        x_scroll.grid(row=1, column=0, sticky="ew")
        y_scroll = ttk.Scrollbar(content, orient="vertical", command=preview_canvas.yview, style="Preview.Vertical.TScrollbar")
        y_scroll.grid(row=0, column=1, sticky="ns")
        preview_canvas.configure(xscrollcommand=lambda first, last: self._preview_scroll_changed(preview, x_scroll, first, last),
                                 yscrollcommand=lambda first, last: self._preview_scroll_changed(preview, y_scroll, first, last))

        preview.canvas = preview_canvas
        preview.x_scroll = x_scroll
        preview.y_scroll = y_scroll

        footer = tk.Frame(preview, bg=BACKGROUND, padx=16, pady=8)
        preview.footer = footer
        footer.grid(row=4, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)
        preview.info_label = self.ui.widget(tk.Label, footer, bg=BACKGROUND, fg=MUTED, font=("Segoe UI", 9), anchor="w", justify="left", wraplength=width - 40)
        preview.info_label.grid(row=0, column=0, sticky="ew")

        preview.toolbar.bind("<Configure>", lambda event: self._schedule_preview_layout(preview))
        preview.bind("<Destroy>", lambda event: self._cancel_preview_callbacks(preview) if event.widget is preview else None)
        preview.bind("<Control-s>", lambda event: preview.save_btn.invoke())
        preview.bind("<Control-c>", lambda event: preview.copy_btn.invoke())
        preview.bind("<Control-0>", lambda event: self._fit_preview_image(preview))
        preview.bind("<Control-1>", lambda event: self._apply_zoom_from_slider(preview, preview.display_image, 100))
        preview.bind("<Control-z>", lambda event: self._undo_annotation(preview))
        preview.bind("<Return>", lambda event: self._accept_crop(preview) if preview.crop_active else None)
        preview.bind("<Escape>", lambda event: self._preview_escape(preview))
        self._latest_preview_image = preview.display_image
        self._schedule_preview_layout(preview)
        self._schedule_preview_render(preview)
        preview.deiconify()
        preview.attributes("-topmost", True)
        preview.lift()
        preview.focus_job = preview.after_idle(lambda: self._activate_preview(preview))
        self._localize_annotation_choices(preview)
        return preview

    def _activate_preview(self, preview):
        preview.focus_job = None
        if preview.state() != "withdrawn":
            preview.lift()
            preview.focus_force()
            preview.canvas.focus_set()

    def _schedule_preview_layout(self, preview):
        if preview.layout_job is not None:
            preview.after_cancel(preview.layout_job)
        preview.layout_job = preview.after_idle(lambda: self._layout_preview_toolbar(preview))

    def _layout_preview_toolbar(self, preview):
        preview.layout_job = None
        available = max(1, preview.toolbar.winfo_width() - 24)
        row, column, used = 0, 0, 0
        layout = []
        for group in preview.toolbar_groups:
            requested = group.winfo_reqwidth() + 12
            if column and used + requested > available:
                row, column, used = row + 1, 0, 0
            layout.append((row, column))
            used += requested
            column += 1

        if tuple(layout) != preview.toolbar_layout:
            # Each wrapped row has its own columns so a wide group in another
            # row cannot push these controls beyond the edge of the window.
            for group in preview.toolbar_groups:
                group.grid_forget()
            for frame in preview.toolbar_rows:
                frame.grid_remove()
                for index in range(len(preview.toolbar_groups)):
                    frame.columnconfigure(index, weight=0)
                frame.columnconfigure(len(preview.toolbar_groups), weight=1)
            for group, (row, column) in zip(preview.toolbar_groups, layout):
                frame = preview.toolbar_rows[row]
                frame.grid(row=row, column=0, sticky="ew")
                group.grid(in_=frame, row=0, column=column, sticky="ew", padx=(0, 12), pady=4)
                group.lift()
            zoom_row, zoom_column = layout[2]
            preview.toolbar_rows[zoom_row].columnconfigure(len(preview.toolbar_groups), weight=0)
            preview.toolbar_rows[zoom_row].columnconfigure(zoom_column, weight=1)
            preview.toolbar_layout = tuple(layout)

        wrap = max(100, preview.winfo_width() - 40)
        preview.heading.configure(wraplength=wrap)
        preview.source_label.configure(wraplength=wrap)
        preview.info_label.configure(wraplength=wrap)
        if preview.winfo_width() < 640:
            preview.brand.grid_remove()
            preview.pin_group.grid(row=0, column=0, columnspan=2, sticky="w")
        else:
            preview.brand.grid()
            preview.pin_group.grid(row=0, column=1, columnspan=1, sticky="e")
        # Wrapping adds rows. Keep room for the image even with large Windows
        # text scaling rather than letting the toolbar cover the canvas.
        minimum_height = (preview.header.winfo_reqheight() + preview.toolbar.winfo_reqheight()
                          + preview.footer.winfo_reqheight() + preview.x_scroll.winfo_reqheight() + 154)
        preview.minsize(preview.minsize()[0], min(minimum_height, preview.winfo_screenheight() - 100))

    def _cancel_preview_callbacks(self, preview):
        for attribute in ("render_job", "layout_job", "focus_job", "annotation_job"):
            job = getattr(preview, attribute, None)
            if job is not None:
                preview.after_cancel(job)
                setattr(preview, attribute, None)
        if getattr(preview, "pin_trace", None):
            preview.pin_var.trace_remove("write", preview.pin_trace)
            preview.pin_trace = None
        preview.annotation_history.clear()
        preview.annotation_stroke = None
        preview.canvas.annotation_image = None
        for image in (getattr(preview, "display_image", None), getattr(preview, "source_image", None)):
            if image is not None and getattr(self, "_latest_preview_image", None) is image:
                self._latest_preview_image = None
            if image is not None and hasattr(image, "_capture_backing"):
                image.close()

    def _schedule_preview_render(self, preview):
        if preview.render_job is not None:
            preview.after_cancel(preview.render_job)
        preview.render_job = preview.after(60, lambda: self._refresh_preview_image(preview))

    def _fit_preview_image(self, preview):
        preview.fit_to_window = True
        self._refresh_preview_image(preview)

    def _refresh_preview_image(self, preview):
        if preview.render_job is not None:
            preview.after_cancel(preview.render_job)
            preview.render_job = None
        canvas = preview.canvas
        image = preview.display_image
        if preview.fit_to_window:
            # Fit even very long scrolling captures, without a 25% lower limit.
            canvas.zoom_factor = min(
                max(1, canvas.winfo_width() - 32) / image.width,
                max(1, canvas.winfo_height() - 32) / image.height,
                1.0,
            )
        preview.zoom_percent = canvas.zoom_factor * 100
        preview.zoom_var.set(max(1, preview.zoom_percent))
        self.ui.set(preview.zoom_label, text=f"{preview.zoom_percent:.0f}%" if preview.zoom_percent >= 1 else "<1%")
        preview.fit_btn.configure(primary=preview.fit_to_window)
        mode = "Dopasowanie do okna · Ctrl + kółko: powiększenie" if preview.fit_to_window else "Strzałki / dwa palce: przewijanie · Ctrl + kółko: powiększenie"
        if preview.pending_crop:
            mode = "Zatwierdź przycięcie lub kliknij Anuluj"
        elif preview.annotation_tool:
            tool = "Mazak" if preview.annotation_tool == "highlighter" else "Ołówek"
            mode = msg("{tool}: rysuj na obrazie · Esc: zakończ · Ctrl+Z: cofnij", tool=msg(tool))
        scaled = image.info.get("capture_scale")
        resolution = msg("  ·  Automatycznie zmniejszono do {scale:.0%}", scale=scaled) if scaled else ""
        self.ui.set(preview.info_label, text=msg("{width} × {height} px{resolution}  ·  {mode}", width=image.width, height=image.height,
                                               resolution=resolution, mode=msg(mode)))
        if preview.crop_active:
            self._update_crop_hint(preview)
        self._render_image_on_canvas(canvas, image, canvas.zoom_factor)

    def _normalize_crop_box(self, box, width, height):
        left, top, right, bottom = [int(round(v)) for v in box]
        left = max(0, min(left, width - 1))
        top = max(0, min(top, height - 1))
        right = max(left + 1, min(right, width))
        bottom = max(top + 1, min(bottom, height))
        return (left, top, right, bottom)

    def _apply_zoom_from_slider(self, preview, image, percent):
        percent = max(1, min(300, float(percent)))
        preview.zoom_percent = percent
        preview.fit_to_window = False
        preview.canvas.zoom_factor = percent / 100.0
        # Coalesce slider/mouse-wheel updates instead of resizing a large
        # screenshot on every input event.
        self._schedule_preview_render(preview)

    def _set_preview_zoom(self, preview, direction):
        if not hasattr(preview, "display_image"):
            return
        new_percent = preview.canvas.zoom_factor * 100 + (direction * 10)
        self._apply_zoom_from_slider(preview, preview.display_image, new_percent)

    def _preview_canvas_press(self, preview, event):
        preview.canvas.focus_set()
        if preview.annotation_tool:
            return self._annotation_press(preview, event)
        return self._preview_crop_press(preview, event)

    def _preview_canvas_drag(self, preview, event):
        if preview.annotation_tool:
            return self._annotation_drag(preview, event)
        return self._preview_crop_drag(preview, event)

    def _preview_canvas_release(self, preview, event):
        if preview.annotation_tool:
            return self._annotation_release(preview, event)
        return self._preview_crop_release(preview, event)

    def _pan_preview(self, preview, dx, dy):
        canvas = preview.canvas
        region = tuple(float(value) for value in canvas.tk.splitlist(canvas.cget("scrollregion")))
        if len(region) != 4:
            return "break"
        for index, (pixels, extent, view) in enumerate(((dx, region[2] - region[0], canvas.xview),
                                                       (dy, region[3] - region[1], canvas.yview))):
            preview.pan_remainder[index] += pixels
            whole_pixels = int(preview.pan_remainder[index])
            preview.pan_remainder[index] -= whole_pixels
            if whole_pixels and extent > 0:
                view("moveto", view()[0] + whole_pixels / extent)
        return "break"

    def _preview_mousewheel(self, preview, event, delta=None):
        delta = event.delta if delta is None else delta
        if event.state & 0x4:  # Control: keep zoom separate from touchpad panning.
            preview.wheel_zoom_delta += delta
            steps = int(preview.wheel_zoom_delta / 120)
            preview.wheel_zoom_delta -= steps * 120
            if steps:
                self._set_preview_zoom(preview, steps)
            return "break"
        pixels = -delta * 96 / 120
        horizontal = bool(event.state & 0x1)
        if horizontal and sys.platform == "win32" and getattr(event, "send_event", False):
            import ctypes
            # Tk represents native WM_MOUSEHWHEEL as Shift-MouseWheel, but its
            # delta has the opposite sign to a wheel used with physical Shift.
            if not ctypes.windll.user32.GetKeyState(0x10) & 0x8000:
                pixels = -pixels
        return self._pan_preview(preview, pixels if horizontal else 0, 0 if horizontal else pixels)

    def _preview_touchpad_scroll(self, preview, event):
        # The installed Tk runtime packs signed X/Y deltas into the two words.
        dx, dy = (event.delta >> 16) & 0xffff, event.delta & 0xffff
        dx = dx - 0x10000 if dx >= 0x8000 else dx
        dy = dy - 0x10000 if dy >= 0x8000 else dy
        if event.state & 0x4:
            return self._preview_mousewheel(preview, event, dy)
        if event.state & 0x1 and not dx:
            dx, dy = dy, 0
        return self._pan_preview(preview, -dx, -dy)

    def _preview_scroll_changed(self, preview, scrollbar, first, last):
        scrollbar.set(first, last)
        canvas = preview.canvas
        view = (round(canvas.canvasx(0)), round(canvas.canvasy(0)), canvas.winfo_width(), canvas.winfo_height())
        if getattr(canvas, "virtual_image", False) and view != getattr(canvas, "render_view", None):
            self._schedule_preview_render(preview)
        if preview.annotation_stroke is not None:
            self._schedule_annotation_render(preview)

    def _render_image_on_canvas(self, canvas, image, zoom_factor):
        width = max(1, int(image.width * zoom_factor))
        height = max(1, int(image.height * zoom_factor))
        viewport_w, viewport_h = canvas.winfo_width(), canvas.winfo_height()
        left, top = max(0, (viewport_w - width) // 2), max(0, (viewport_h - height) // 2)
        canvas.logical_image_bounds = (left, top, left + width, top + height)
        canvas.virtual_image = width * height > 12_000_000
        canvas.configure(scrollregion=(0, 0, max(width, viewport_w), max(height, viewport_h)))
        if width <= viewport_w:
            canvas.xview_moveto(0)
        if height <= viewport_h:
            canvas.yview_moveto(0)
        canvas.render_view = (round(canvas.canvasx(0)), round(canvas.canvasy(0)), viewport_w, viewport_h)
        box = (0, 0, image.width, image.height)
        origin = (left, top)
        target_size = (width, height)
        if canvas.virtual_image:
            # Only allocate pixels visible in the viewport at high zoom.
            x, y = canvas.canvasx(0) - left, canvas.canvasy(0) - top
            x1, y1 = max(0, int(x / zoom_factor)), max(0, int(y / zoom_factor))
            x2 = min(image.width, int((x + viewport_w) / zoom_factor) + 2)
            y2 = min(image.height, int((y + viewport_h) / zoom_factor) + 2)
            box = (x1, y1, max(x1 + 1, x2), max(y1 + 1, y2))
            origin = (left + round(x1 * zoom_factor), top + round(y1 * zoom_factor))
            target_size = (max(1, round((box[2] - x1) * zoom_factor)), max(1, round((box[3] - y1) * zoom_factor)))
        render_key = (id(image), width, height, box)
        if getattr(canvas, "render_key", None) != render_key:
            source = image.crop(box) if canvas.virtual_image else image
            resized = source.resize(target_size, Image.Resampling.LANCZOS)
            canvas.image = ImageTk.PhotoImage(resized, master=canvas)
            canvas.delete("image")
            canvas.create_image(*origin, anchor="nw", image=canvas.image, tags="image")
            canvas.render_key = render_key
        canvas.coords("image", *origin)
        self._draw_crop_selection(canvas.winfo_toplevel())
        self._draw_live_annotation(canvas.winfo_toplevel())

    def _copy_image_to_clipboard(self, preview, image):
        self._commit_annotation(preview)
        try:
            import win32clipboard
            output = io.BytesIO()
            image.convert("RGB").save(output, format="BMP")
            data = output.getvalue()[14:]
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            win32clipboard.CloseClipboard()
            self.set_status("Zrzut skopiowany do schowka.")
            preview.destroy()
            return
        except Exception:
            path = save_image(image, "clipboard_copy")
            self.root.clipboard_clear()
            self.root.clipboard_append(path)
            self.set_status(msg("Zrzut zapisany do pliku i ścieżka skopiowana: {path}", path=path))
            preview.destroy()

    def _confirm_save(self, preview, image, prefix):
        self._commit_annotation(preview)
        try:
            path = save_image(image, prefix)
            preview.destroy()
            self.set_status(msg("Zapisano: {path}", path=path))
        except Exception as exc:
            self.ui.dialog(messagebox.showerror, "Błąd", error_message(exc))
            self.set_status("Nie udało się zapisać zrzutu.")

    def _discard_preview(self, preview, image):
        preview.destroy()
        self.set_status("Zrzut odrzucony.")

    def _capture_to_preview(self, image, prefix, title):
        return self._show_preview(image, prefix, title)

    def capture_full_screen(self):
        self._show_capture_warning()
        try:
            with self._hidden_capture_windows():
                time.sleep(0.15)
                img = ImageGrab.grab()
            self._capture_to_preview(img, "full_screen", msg("Pełny ekran - podgląd"))
        except Exception as exc:
            self.ui.dialog(messagebox.showerror, "Błąd", error_message(exc))
            self.set_status("Błąd zrzutu całego ekranu.")

    def _window_bbox(self, window):
        try:
            left = int(window.left)
            top = int(window.top)
            right = int(window.right)
            bottom = int(window.bottom)
        except Exception:
            return None

        if left <= -20000 or top <= -20000 or right <= -20000 or bottom <= -20000:
            return None

        if right <= left or bottom <= top:
            return None
        return (left, top, right, bottom)

    def _focus_window_if_possible(self, window):
        minimized = getattr(window, "isMinimized", getattr(window, "minimized", False))
        if minimized and hasattr(window, "restore"):
            window.restore()
        if hasattr(window, "activate"):
            try:
                window.activate()
            except Exception as exc:
                logger.info("Window activation needs verification: %s", exc)
        handle = getattr(window, "_hWnd", None)
        if handle:
            ensure_window_foreground(handle)

    def has_meaningful_change(self, prev: Image.Image, current: Image.Image, min_changed_ratio: float = 0.003) -> bool:
        if prev.size != current.size:
            return True
        diff = ImageChops.difference(prev.convert("L"), current.convert("L"))
        bbox = diff.getbbox()
        if bbox is None:
            return False

        hist = diff.histogram()
        changed = sum(hist[1:])
        total_pixels = prev.width * prev.height
        ratio = changed / total_pixels if total_pixels else 0
        return ratio >= min_changed_ratio

    def _deduplicate_screenshots(self, screenshots, min_changed_ratio: float = 0.01):
        if not screenshots:
            return []

        deduped = [screenshots[0]]
        for frame in screenshots[1:]:
            previous = deduped[-1]
            if self.has_meaningful_change(previous, frame, min_changed_ratio=min_changed_ratio):
                deduped.append(frame)
        return deduped

    def get_selectable_windows(self):
        app_title = "Windows Capture Studio"
        windows = []
        exclude_titles = {app_title}

        for w in gw.getAllWindows():
            title = (getattr(w, "title", "") or "").strip()
            if not title:
                continue

            if title == app_title or any(item in title for item in exclude_titles):
                continue
            if title == f"MiniScreenShot v{APP_VERSION}" or window_process_id(w) == os.getpid():
                continue
            if getattr(w, "visible", True) is False:
                continue

            bbox = self._window_bbox(w)
            if bbox is None:
                continue

            width = abs(bbox[2] - bbox[0])
            height = abs(bbox[3] - bbox[1])
            if width <= 0 or height <= 0:
                continue
            if width < 10 or height < 10:
                continue

            windows.append(w)

        self._add_debug_log(f"Detected windows: {[getattr(w, 'title', '<unknown>') for w in windows]}")
        return sorted(windows, key=lambda item: (getattr(item, "title", "") or "").lower())

    def refresh_window_list_debug(self):
        if getattr(self, "selected_mode", None) == "window":
            self._refresh_window_picker()
            return
        try:
            windows = self.get_selectable_windows()
            titles = [getattr(w, "title", "<unknown>") for w in windows]
            self._add_debug_log(f"Refresh window list: {titles}")
            self.set_status(msg("Wczytano okien: {count}", count=len(windows)))
        except Exception as exc:
            self._add_debug_log(f"Refresh window list failed: {exc}")
            self.set_status(msg("Błąd odświeżania listy okien: {error}", error=error_message(exc)))

    def _capture_window_obj(self, window):
        self._show_capture_warning()
        try:
            if self.vertical_var.get() or self.horizontal_var.get():
                self._capture_scrolled_window(window)
                return
            with self._hidden_capture_windows():
                self._focus_window_if_possible(window)
                time.sleep(0.25)
                bbox = self._window_bbox(window)
                if bbox is None:
                    raise ValueError("Wybrane okno nie ma prawidłowych wymiarów.")
                img = ImageGrab.grab(bbox=bbox)
            self._capture_to_preview(img, "selected_window", msg("Okno: {title} - podgląd", title=window.title))
        except Exception as exc:
            self.ui.dialog(messagebox.showerror, "Błąd", error_message(exc))
            self._report_capture_failure(msg("Nie udało się wykonać zrzutu okna: {error}", error=msg(error_message(exc))))

    def _hide_capture_windows(self):
        states = []
        if not hasattr(self.root, "winfo_children"):
            return states
        windows = [self.root] + [item for item in self.root.winfo_children() if isinstance(item, tk.Toplevel)]
        for window in windows:
            state = window.state()
            if state not in ("withdrawn", "iconic"):
                states.append((window, state))
                window.withdraw()
        self.root.update_idletasks()
        return states

    def _restore_capture_windows(self, states):
        for window, state in states:
            if window.winfo_exists():
                window.state(state)

    @contextmanager
    def _hidden_capture_windows(self):
        states = self._hide_capture_windows()
        try:
            yield
        finally:
            self._restore_capture_windows(states)

    def _scroll_progress(self, message):
        self.set_status(msg("{message}  Esc: anuluj", message=msg(message)))
        if getattr(self, "capture_progress", None):
            self.capture_progress.set_message(message)
        self._add_debug_log(message)
        if hasattr(self.root, "update_idletasks"):
            self.root.update_idletasks()

    def _report_capture_failure(self, message):
        self.set_status("Nie wykonano zrzutu.")
        if hasattr(self, "capture_notice"):
            self.ui.set(self.capture_notice, text=message)
            self.capture_notice.grid()
            self.root.lift()

    def _capture_scrolled_window(self, window):
        driver = None
        try:
            with self._hidden_capture_windows():
                self._focus_window_if_possible(window)
                time.sleep(0.25)
                driver = WindowsScrollDriver(window)
                try:
                    if hasattr(self.root, "winfo_children"):
                        self.capture_progress = CaptureProgress(self.root, driver.bbox, ui=self.ui)
                        driver.pulse = self.capture_progress.pump
                        driver.frame_guard = self.capture_progress.capture_frame
                    engine = ScrollingCapture(driver, vertical=self.vertical_var.get(), horizontal=self.horizontal_var.get(),
                                              progress=self._scroll_progress, include_window_frame=True)
                    image = engine.capture()
                finally:
                    if getattr(self, "capture_progress", None):
                        self.capture_progress.close()
                        self.capture_progress = None
                    driver.close()
            reason = getattr(engine, "incomplete_reason", None)
            reason = reason if isinstance(reason, str) else None
            no_movement = not reason and getattr(engine, "frame_count", None) == 1
            description = "zrzut częściowy" if reason else ("widoczny obszar" if no_movement else "z przewijaniem")
            preview = self._capture_to_preview(image, "selected_window_scroll", msg("Okno: {title} — {description}", title=window.title, description=msg(description)))
            if reason:
                self.ui.set(preview.heading, text="Zrzut częściowy", fg="#fbbf24")
                self.ui.set(preview.source_label, text=reason)
                self.set_status(msg("Zachowano zrzut częściowy. {reason}", reason=msg(reason)))
            elif no_movement:
                self.ui.set(preview.heading, text="Widoczny obszar", fg="#fbbf24")
                self.ui.set(preview.source_label, text="Nie wykryto przesunięcia zawartości. Przechwycono tylko widoczny obszar.")
                self.set_status("Przechwycono widoczny obszar — nie wykryto przewijania.")
            else:
                self.set_status("Zrzut gotowy. Możliwe niewielkie zakładki." if engine.approximate is True else "Zrzut gotowy. Otworzono podgląd.")
        except (CaptureCancelled, ScrollCaptureError) as exc:
            self._add_debug_log(str(exc))
            self._report_capture_failure(str(exc))
        except Exception as exc:
            logger.exception("Scrolling capture failed")
            self._report_capture_failure(msg("Nie udało się wykonać zrzutu z przewijaniem: {error}", error=msg(error_message(exc))))

    def capture_selected_area(self):
        self._show_capture_warning()
        self._area_window_states = self._hide_capture_windows()
        overlay = SelectionOverlay(self._area_selected, self._cancel_area_selection)
        overlay.start_select()

    def _cancel_area_selection(self):
        self._restore_capture_windows(getattr(self, "_area_window_states", []))
        self._area_window_states = []
        self.set_status("Zaznaczanie obszaru anulowane.")

    def _area_selected(self, selection):
        x1, y1, x2, y2 = selection
        try:
            time.sleep(0.12)
            img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
            self._restore_capture_windows(getattr(self, "_area_window_states", []))
            self._area_window_states = []
            self._capture_to_preview(img, "selected_area", msg("Zaznaczony wycinek - podgląd"))
        except Exception as exc:
            self._cancel_area_selection()
            self.ui.dialog(messagebox.showerror, "Błąd", error_message(exc))
            self.set_status("Błąd zrzutu obszaru.")

def main():
    cache_session()
    set_process_app_id()
    root = tk.Tk()
    app = ScreenCaptureApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
