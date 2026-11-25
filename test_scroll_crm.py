"""Real Chrome CRM fixtures with independently scrollable menu and content."""
import ctypes
import json
from pathlib import Path
import subprocess
import time
import unittest
from unittest.mock import patch
from uuid import uuid4
from contextlib import contextmanager

from PIL import Image, ImageChops, ImageGrab
import pygetwindow as gw
import win32con
import win32gui

import app_advanced
from app_advanced import ScreenCaptureApp, tk
from test_scroll_chrome import CHROME
from test_scroll_capture import document_image
from windows_coordinates import monitor_rectangles, physical_pixels


@unittest.skipUnless(CHROME, "Chrome is not installed")
class CrmPanelCaptureTests(unittest.TestCase):
    def capture_crm(self, selected_panel, maximized=False, busy_header=False, display=None):
        ctypes.windll.user32.SetProcessDPIAware()
        title = "MiniScreenShot multi-panel CRM " + uuid4().hex[:8]
        folder = Path("build/chrome-review") / title.rsplit(" ", 1)[-1]
        folder.mkdir(parents=True)
        width, height = (240, 180) if selected_panel else (640, 420)
        left = 670 if selected_panel else 320
        if busy_header:
            width, height, left = 350, 500, 620
        document = document_image(width, 2240 if busy_header else 1113)
        document.save(folder / "content.png")
        document_image(600 if selected_panel else 280, 1900).save(folder / "menu.png")
        html = (f'<!doctype html><title>{title}</title><style>'
                'html,body{margin:0;height:100%;overflow:hidden;background:#e7edf5}'
                'header{height:60px;background:#182438;color:white;font:20px Arial}'
                f'#menu{{position:absolute;left:12px;top:80px;width:{600 if selected_panel else 280}px;'
                'height:580px;overflow:auto;overscroll-behavior:contain}'
                f'#content{{position:absolute;left:{left}px;top:120px;width:{width}px;height:{height}px;'
                'border:3px solid rgb(255,0,255);overflow:auto;overscroll-behavior:contain;scrollbar-width:none}'
                '#content::-webkit-scrollbar{display:none}img{display:block}'
                '</style><header>CRM | niezalezne menu i tresc</header>'
                '<aside id="menu"><img src="menu.png"></aside>'
                '<main id="content"><img src="content.png"></main><script>'
                f'const base={json.dumps(title)}, menu=document.getElementById("menu"),'
                'content=document.getElementById("content");let active=false;'
                'function status(){document.title=base+" menu="+menu.scrollTop+" body="+content.scrollTop}'
                'content.addEventListener("scroll",()=>{if(content.scrollTop>250)active=true;status()});'
                'setInterval(()=>{if(active){menu.scrollTop=(menu.scrollTop+17)%1200}status()},120);'
                'addEventListener("load",()=>{document.title=base+" ready menu=0 body=0"});'
                '</script>')
        page = folder / "index.html"
        if busy_header:
            document_image(1400, 1000).save(folder / "background.png")
            html = html.replace('</style>', 'body{background:url(background.png)}#clock{position:absolute;left:20px;top:20px;width:45px;height:45px}#status{position:fixed;bottom:0;left:0;right:0;height:20px}</style>')
            html = html.replace('<main id="content">', '<div id="clock"></div><div id="status"></div><main id="content">')
            html = html.replace('</script>', 'let tick=0;setInterval(()=>{tick++;for(let id of ["clock","status"])document.getElementById(id).style.background=`rgb(${tick*47%255},${tick*73%255},${tick*113%255})`},140);</script>')
        page.write_text(html, encoding="utf-8")
        process = subprocess.Popen([
            str(CHROME), "--user-data-dir=" + str((folder / "profile").resolve()),
            "--no-first-run", "--no-default-browser-check", "--disable-background-networking",
            "--disable-sync", "--force-device-scale-factor=1", "--window-size=" + ("1400,940" if busy_header else "1100,840"),
            "--window-position=60,60", "--new-window", page.resolve().as_uri(),
        ], creationflags=subprocess.CREATE_NO_WINDOW)
        root = None
        handle = 0
        try:
            deadline = time.monotonic() + 40
            while time.monotonic() < deadline:
                windows = [item for item in gw.getAllWindows() if title in item.title]
                if windows:
                    handle = windows[0]._hWnd
                    break
                time.sleep(.15)
            self.assertTrue(handle, "Chrome CRM fixture did not load")
            if display is not None:
                with physical_pixels():
                    width = min(1100, display[2] - display[0] - 32)
                    height = min(840, display[3] - display[1] - 32)
                    win32gui.SetWindowPos(handle, 0, display[0] + 16, display[1] + 16, width, height, 0)
                    time.sleep(.3)
            if maximized:
                win32gui.ShowWindow(handle, win32con.SW_MAXIMIZE)
                time.sleep(.3)
            root = tk.Tk()
            app = ScreenCaptureApp(root, language="pl")
            root.update()
            window = gw.Win32Window(handle)
            with patch.object(app, "get_selectable_windows", return_value=[window]):
                app._select_capture_mode("window")
            app.window_table.selection_set(app.window_table.get_children()[0])
            app.vertical_var.set(True)
            root.update()
            previews = set(root.winfo_children())
            test = self
            original_progress = app_advanced.CaptureProgress
            visibility_samples = []

            class SteadyProgress(original_progress):
                @contextmanager
                def capture_frame(self):
                    with super().capture_frame():
                        visible = bool(win32gui.IsWindowVisible(self.handle))
                        visibility_samples.append(visible)
                        test.assertTrue(visible, "Progress disappeared while Chrome was sampled")
                        yield

            with patch("app_advanced.messagebox.showinfo", side_effect=AssertionError("Unexpected confirmation")), \
                    patch("app_advanced.CaptureProgress", SteadyProgress):
                if selected_panel:
                    # Locate the fixture's magenta frame in client pixels. This
                    # avoids hard-coding Chrome's native toolbar/titlebar size.
                    states = app._hide_capture_windows()
                    app._focus_window_if_possible(window)
                    time.sleep(.3)
                    from scroll_panel_picker import client_bounds
                    bounds = client_bounds(handle)
                    frame = ImageGrab.grab(bbox=bounds, all_screens=True)
                    masks = [channel.point([255 if value == target else 0 for value in range(256)])
                             for channel, target in zip(frame.split(), (255, 0, 255))]
                    mask = ImageChops.multiply(ImageChops.multiply(masks[0], masks[1]), masks[2])
                    pixels = mask.tobytes()
                    edges = [(row.find(b"\xff" * (width + 6)), y)
                             for y in range(mask.height)
                             if (row := pixels[y * mask.width:(y + 1) * mask.width]).find(b"\xff" * (width + 6)) >= 0]
                    self.assertTrue(edges, "CRM panel frame is missing")
                    box = (edges[0][0], edges[0][1], edges[0][0] + width + 6, edges[-1][1] + 1)
                    region = (box[0] + 3, box[1] + 3, box[2] - 3, box[3] - 3)
                    self.assertEqual((region[2] - region[0], region[3] - region[1]), (width, height))
                    app._restore_capture_windows(states)

                    class Selection:
                        def __init__(self, callback, cancel_callback=None, **options):
                            self.callback, self.bounds = callback, options["bounds"]

                        def start_select(self):
                            self.callback((self.bounds[0] + region[0], self.bounds[1] + region[1],
                                           self.bounds[0] + region[2], self.bounds[1] + region[3]))

                    with patch("app_advanced.SelectionOverlay", Selection):
                        app.panel_capture_button.invoke()
                else:
                    app.capture_action.invoke()
            root.update()
            self.assertTrue(visibility_samples, "Browser test did not sample progress visibility")
            results = [item for item in root.winfo_children() if item not in previews and hasattr(item, "display_image")]
            self.assertEqual(len(results), 1, "CRM capture did not open a result preview")
            preview = results[0]
            image = preview.display_image
            content = image if selected_panel else image.crop(image.info["capture_content_box"])
            self.assertEqual(content.size, document.size)
            self.assertIsNone(ImageChops.difference(content, document).getbbox(), "CRM rows were skipped or duplicated")
            with patch.object(app_advanced, "CAPTURE_DIR", folder):
                preview.save_btn.invoke()
            saved_paths = list(folder.glob("selected_window_scroll_*.png"))
            self.assertEqual(len(saved_paths), 1)
            with Image.open(saved_paths[0]) as saved:
                saved_content = saved if selected_panel else saved.crop(image.info["capture_content_box"])
                self.assertEqual(saved_content.size, document.size)
                self.assertIsNone(ImageChops.difference(saved_content, document).getbbox(), "Saved CRM PNG is incomplete")
        finally:
            if root:
                root.destroy()
            if handle and win32gui.IsWindow(handle):
                win32gui.PostMessage(handle, win32con.WM_CLOSE, 0, 0)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, check=False)
                process.wait(timeout=5)

    def test_selected_right_hand_content_is_saved_in_full(self):
        self.capture_crm(selected_panel=True)

    def test_automatic_content_capture_ignores_independently_scrolling_menu(self):
        self.capture_crm(selected_panel=False)

    def test_maximized_browser_keeps_progress_visible_and_saved_content_complete(self):
        self.capture_crm(selected_panel=True, maximized=True)

    def test_automatic_capture_saves_full_right_hand_list_beside_animated_header(self):
        self.capture_crm(selected_panel=False, busy_header=True)

    def test_automatic_scrolling_on_secondary_connected_displays(self):
        import win32api
        with physical_pixels():
            primary = win32api.GetMonitorInfo(win32api.MonitorFromPoint((0, 0), 1))["Monitor"]
            secondary = [rect for rect in monitor_rectangles() if rect != primary]
        if not secondary:
            self.skipTest("A second physical display is not connected; simulated layouts are covered by test_multi_monitor")
        for display in secondary:
            with self.subTest(display=display):
                self.capture_crm(selected_panel=False, display=display)


if __name__ == "__main__":
    unittest.main()
