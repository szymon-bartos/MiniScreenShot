import io
import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

from PIL import Image, ImageGrab
from playwright.sync_api import sync_playwright

ROOT_DIR = Path(__file__).resolve().parent
CAPTURE_DIR = ROOT_DIR / "captures"
CAPTURE_DIR.mkdir(exist_ok=True)


class ScreenCaptureApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Portable Screen Capture")
        self.root.geometry("560x420")
        self.root.minsize(500, 360)

        self.root.configure(bg="#0f172a")
        self.style = ttk.Style(root)
        self.style.theme_use("clam")
        self.style.configure("TFrame", background="#0f172a")
        self.style.configure("TLabel", background="#0f172a", foreground="#e2e8f0", font=("Segoe UI", 10))
        self.style.configure("TButton", padding=(10, 8), font=("Segoe UI", 10, "bold"))
        self.style.configure("TCheckbutton", background="#0f172a", foreground="#e2e8f0", font=("Segoe UI", 10))
        self.style.configure("TLabelframe", background="#0f172a")
        self.style.configure("TLabelframe.Label", background="#0f172a", foreground="#7dd3fc")
        self.style.configure("TEntry", fieldbackground="#111827", foreground="#f8fafc")

        main = ttk.Frame(root, padding=18)
        main.pack(fill="both", expand=True)

        title = ttk.Label(main, text="Portable Screen Capture", font=("Segoe UI", 18, "bold"))
        title.pack(anchor="w", pady=(0, 12))

        info = ttk.Label(main, text="Prosty, przenośny zrzut ekranu na Windows bez uprawnień administratora.")
        info.pack(anchor="w", pady=(0, 16))

        settings = ttk.LabelFrame(main, text="Opcje zrzutu")
        settings.pack(fill="x", pady=(0, 12))

        self.vertical_var = tk.BooleanVar(value=True)
        self.horizontal_var = tk.BooleanVar(value=True)
        self.url_var = tk.StringVar(value="https://example.com")
        self.output_dir = tk.StringVar(value=str(CAPTURE_DIR))

        ttk.Checkbutton(settings, text="Inteligentny scroll w dół / góra", variable=self.vertical_var).pack(anchor="w", padx=12, pady=(12, 6))
        ttk.Checkbutton(settings, text="Inteligentny scroll w lewo / prawo", variable=self.horizontal_var).pack(anchor="w", padx=12, pady=(0, 12))

        url_box = ttk.Frame(main)
        url_box.pack(fill="x", pady=(0, 10))
        ttk.Label(url_box, text="URL strony:").pack(anchor="w")
        url_entry = ttk.Entry(url_box, textvariable=self.url_var)
        url_entry.pack(fill="x", pady=(4, 0))

        output_box = ttk.Frame(main)
        output_box.pack(fill="x", pady=(0, 12))
        ttk.Label(output_box, text="Folder zapisu:").pack(anchor="w")
        output_row = ttk.Frame(output_box)
        output_row.pack(fill="x", pady=(4, 0))
        ttk.Entry(output_row, textvariable=self.output_dir).pack(side="left", fill="x", expand=True)
        ttk.Button(output_row, text="Wybierz", command=self.choose_folder).pack(side="left", padx=(8, 0))

        buttons = ttk.Frame(main)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Zrzut całego ekranu", command=self.capture_full_screen).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Zrzut inteligentny", command=self.capture_smart_page).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Zamknij", command=self.root.destroy).pack(side="left")

        self.status = ttk.Label(main, text="Gotowy do pracy.", foreground="#93c5fd")
        self.status.pack(anchor="w", pady=(18, 0))

    def choose_folder(self):
        folder = filedialog.askdirectory(title="Wybierz folder zapisu")
        if folder:
            self.output_dir.set(folder)

    def capture_full_screen(self):
        save_path = self._make_save_path("screen")
        thread = threading.Thread(target=self._run_full_capture, args=(save_path,), daemon=True)
        thread.start()

    def capture_smart_page(self):
        url = self.url_var.get().strip()
        if not url:
            self._set_status("Najpierw wpisz adres URL.")
            return
        save_path = self._make_save_path("smart_page")
        thread = threading.Thread(
            target=self._run_smart_page_capture,
            args=(url, save_path, self.vertical_var.get(), self.horizontal_var.get()),
            daemon=True,
        )
        thread.start()

    def _run_full_capture(self, save_path):
        try:
            image = ImageGrab.grab()
            image.save(save_path)
            self.root.after(0, self._set_status, f"Zapisano pełny zrzut: {save_path}")
        except Exception as exc:
            self.root.after(0, self._set_status, f"Błąd: {exc}")

    def _run_smart_page_capture(self, url, save_path, vertical, horizontal):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1600, "height": 900})
                page.goto(url, wait_until="networkidle", timeout=60000)

                if not vertical and not horizontal:
                    page.screenshot(path=save_path, full_page=True)
                    browser.close()
                    self.root.after(0, self._set_status, f"Zapisano zrzut strony: {save_path}")
                    return

                document = page.evaluate(
                    """
                    () => {
                        const doc = document.documentElement;
                        return {
                            width: Math.max(doc.scrollWidth, doc.clientWidth, doc.offsetWidth || 0),
                            height: Math.max(doc.scrollHeight, doc.clientHeight, doc.offsetHeight || 0)
                        };
                    }
                    """
                )

                viewport = page.viewport_size or {"width": 1600, "height": 900}
                vw = viewport["width"]
                vh = viewport["height"]

                y_positions = [0]
                x_positions = [0]

                if vertical:
                    max_y = max(int(document["height"]) - vh, 0)
                    step_y = max(400, vh // 2)
                    y_positions = list(range(0, max_y + 1, step_y))
                if horizontal:
                    max_x = max(int(document["width"]) - vw, 0)
                    step_x = max(400, vw // 2)
                    x_positions = list(range(0, max_x + 1, step_x))

                pieces = []
                for x in x_positions:
                    for y in y_positions:
                        page.evaluate(f"window.scrollTo({x}, {y})")
                        page.wait_for_timeout(350)
                        screenshot_png = page.screenshot()
                        pieces.append((x, y, Image.open(io.BytesIO(screenshot_png))))

                width = max((x + vw for x, _, _ in pieces), default=vw) + 20
                height = max((y + vh for _, y, _ in pieces), default=vh) + 20
                canvas = Image.new("RGB", (width, height), "white")

                for x, y, img in pieces:
                    canvas.paste(img, (x, y))

                canvas.save(save_path)
                browser.close()
                self.root.after(0, self._set_status, f"Zapisano inteligentny zrzut: {save_path}")

        except Exception as exc:
            self.root.after(0, self._set_status, f"Błąd podczas tworzenia zrzutu: {exc}")

    def _make_save_path(self, prefix):
        folder = Path(self.output_dir.get())
        folder.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return folder / f"{prefix}_{timestamp}.png"

    def _set_status(self, message):
        self.status.config(text=message)


def main():
    root = tk.Tk()
    app = ScreenCaptureApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
