"""Capture a sparse ERP-style list in an isolated Chrome profile."""
import ctypes
import json
import os
from pathlib import Path
import subprocess
import time
import unittest
from uuid import uuid4

import pyautogui
import pygetwindow as gw
import win32con
import win32gui
from PIL import ImageChops

from app_advanced import ScreenCaptureApp, tk
from capture_progress import CaptureProgress
from scroll_capture import ScrollingCapture
from test_scroll_capture import lead_table_image
from windows_scroll import WindowsScrollDriver


CHROME = next((path for path in (
    Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
    Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
    Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
) if path.is_file()), None)


@unittest.skipUnless(CHROME, "Chrome is not installed")
class ChromeErpCaptureTests(unittest.TestCase):
    def test_sparse_lead_grid_with_fixed_chrome_and_delayed_virtualized_rows(self):
        ctypes.windll.user32.SetProcessDPIAware()
        title = "MiniScreenShot ERP fixture " + uuid4().hex[:8]
        folder = Path("build/chrome-review") / title.rsplit(" ", 1)[-1]
        folder.mkdir(parents=True)
        document = lead_table_image()
        document.save(folder / "leads.png")
        # Canvas represents a virtualized grid: only the visible rows are drawn.
        # Its wheel listener can render after input, like a busy ERP application.
        html = (f'<!doctype html><title>{title}</title><style>'
                'html,body{margin:0;height:100%;overflow:hidden;background:#eef2f7;font:14px Arial}'
                'header{height:90px;background:#17243b;color:white;padding:20px;box-sizing:border-box}'
                'aside{position:fixed;top:90px;bottom:0;left:0;width:125px;background:#e0e5ec}'
                'aside p{margin:20px}#grid{position:absolute;left:50%;top:50%;transform:translate(-50%,-25%)}'
                '</style><header>ERP test | Lista leadow | Filtry | Raporty</header>'
                '<aside><p>Pulpit</p><p>Kontakty</p><p>Zadania</p></aside>'
                '<canvas id="grid" width="720" height="280"></canvas><script>'
                f'const title={json.dumps(title)}, image=new Image(), grid=document.getElementById("grid"),'
                'ctx=grid.getContext("2d");let offset=308,delay=0,timer;'
                'function render(){ctx.drawImage(image,0,offset,720,280,0,0,720,280);'
                'document.title=title+" y="+offset+" delay="+delay}'
                'image.onload=render;image.src="leads.png";'
                'grid.addEventListener("wheel",e=>{e.preventDefault();'
                'const next=Math.max(0,Math.min(image.height-280,offset+Math.sign(e.deltaY)*84));'
                'clearTimeout(timer);timer=setTimeout(()=>{offset=next;render()},delay)},{passive:false});'
                'document.addEventListener("keydown",e=>{if(e.key==="d"){delay=450;offset=308;render()}});'
                '</script>')
        (folder / "index.html").write_text(html, encoding="utf-8")
        process = subprocess.Popen([
            str(CHROME), "--user-data-dir=" + str((folder / "profile").resolve()),
            "--no-first-run", "--no-default-browser-check", "--disable-background-networking",
            "--disable-sync", "--force-device-scale-factor=1", "--window-size=1000,800",
            "--window-position=80,80", "--new-window", (folder / "index.html").resolve().as_uri(),
        ], creationflags=subprocess.CREATE_NO_WINDOW)
        handle = 0
        root = loader = driver = None
        try:
            deadline = time.monotonic() + 40
            while time.monotonic() < deadline:
                windows = [window for window in gw.getAllWindows() if title + " y=" in window.title]
                if windows:
                    handle = windows[0]._hWnd
                    break
                time.sleep(0.15)
            self.assertTrue(handle, "Isolated Chrome fixture did not load")
            window = gw.Win32Window(handle)
            root = tk.Tk()
            app = ScreenCaptureApp(root)
            root.update()
            with app._hidden_capture_windows():
                pyautogui.click(*win32gui.ClientToScreen(handle, (700, 12)))
                app._focus_window_if_possible(window)
                time.sleep(0.2)
                for delayed in (False, True):
                    if delayed:
                        self.assertEqual(win32gui.GetForegroundWindow(), handle)
                        pyautogui.press("d")
                        deadline = time.monotonic() + 3
                        while "delay=450" not in window.title and time.monotonic() < deadline:
                            time.sleep(0.05)
                        self.assertIn("delay=450", window.title)
                    driver = WindowsScrollDriver(window)
                    loader = CaptureProgress(root, driver.bbox)
                    driver.pulse, driver.frame_guard = loader.pump, loader.capture_frame
                    engine = ScrollingCapture(driver, progress=loader.set_message, include_window_frame=True)
                    result = engine.capture()
                    result.save(folder / ("delayed.png" if delayed else "instant.png"))
                    self.assertIsNone(engine.incomplete_reason)
                    self.assertGreater(engine.frame_count, 1, "Moving lead rows were classified as stationary")
                    content = result.crop(result.info["capture_content_box"])
                    self.assertEqual(content.size, document.size)
                    self.assertIsNone(ImageChops.difference(content, document).getbbox(),
                                      "Lead rows were missing, repeated or misaligned")
                    self.assertIn("y=1064", window.title, "The ERP list did not reach its actual bottom")
                    self.assertGreater(result.info["capture_content_box"][1], 90, "Chrome toolbar was cropped")
                    result.close()
                    loader.close()
                    loader = None
                    driver.close()
                    driver = None
        finally:
            if loader:
                loader.close()
            if driver:
                driver.close()
            if root:
                root.destroy()
            if handle and win32gui.IsWindow(handle):
                win32gui.PostMessage(handle, win32con.WM_CLOSE, 0, 0)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
