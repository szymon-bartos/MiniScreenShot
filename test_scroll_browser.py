"""Real Firefox scroll regression on an isolated local page and profile."""
import subprocess
import sys
import time
import unittest
from pathlib import Path
from uuid import uuid4

import pygetwindow as gw
import win32con
import win32gui
from PIL import ImageChops, ImageDraw, ImageFilter, ImageStat
import pyautogui

from app_advanced import ScreenCaptureApp, tk
from capture_progress import CaptureProgress
from scroll_capture import ScrollingCapture
from windows_scroll import WindowsScrollDriver
from test_scroll_capture import document_image

FIREFOX = Path("C:/Program Files/Mozilla Firefox/firefox.exe")


@unittest.skipUnless(FIREFOX.exists(), "Firefox is not installed")
class FirefoxCaptureTests(unittest.TestCase):
    def test_full_page_with_smooth_scrolling_and_loader(self):
        title = f"MiniScreenShot browser fixture {uuid4().hex[:8]}"
        folder = Path("build/browser-review") / title.rsplit(" ", 1)[-1]
        folder.mkdir(parents=True, exist_ok=True)
        profile = folder / "profile"
        profile.mkdir()
        preferences = {
            "browser.shell.checkDefaultBrowser": False, "browser.aboutwelcome.enabled": False,
            "browser.startup.homepage_override.mstone": "ignore", "browser.startup.page": 0,
            "browser.tabs.warnOnClose": False, "browser.newtabpage.enabled": False,
            "datareporting.policy.dataSubmissionPolicyBypassNotification": True,
            "toolkit.telemetry.reportingpolicy.firstRun": False, "layout.css.devPixelsPerPx": "1.0",
        }
        import json
        (profile / "user.js").write_text("\n".join(f"user_pref({json.dumps(k)}, {json.dumps(v)});" for k, v in preferences.items()), encoding="utf-8")
        document = document_image(800, 1373).filter(ImageFilter.GaussianBlur(0.7))
        drawing = ImageDraw.Draw(document)
        for row in range(15):
            drawing.rectangle((80, row * 90 + 16, 720, row * 90 + 56), fill="#fafafa")
            drawing.text((100, row * 90 + 24), f"Listing {row:02d} - browser scroll regression", fill="#182035")
        document.save(folder / "document.png")
        (folder / "index.html").write_text(f'<!doctype html><title>{title}</title><style>html{{scroll-behavior:smooth}}body{{margin:0;background:white}}img{{display:block}}</style><img src="document.png" width="800" height="1373"><script>let wheels=0,clicks=0;function state(){{document.title={json.dumps(title)}+" y="+scrollY+" focus="+document.hasFocus()+" wheels="+wheels+" clicks="+clicks}}onload=onscroll=onfocus=onblur=state;onwheel=()=>{{wheels++;state()}};onclick=()=>{{clicks++;state()}}</script>', encoding="utf-8")
        rows = "".join(f'<article><img src="document.png" style="object-position:0 -{index * 50}px"><div><h2>Samochód testowy {index:02d}</h2><p>Opis ogłoszenia · różne zdjęcia i wygładzany tekst</p><strong>{10000 + index * 371} PLN</strong></div></article>' for index in range(12))
        natural_html = (f'<!doctype html><meta charset="utf-8"><title>{title} HTML</title>'
                        '<style>html{scroll-behavior:smooth}body{margin:0;width:800px;zoom:1.1;font:16px "Segoe UI";background:white}'
                        'header,footer{height:24px;background:rgb(242,1,121)}footer{background:rgb(1,222,244)}'
                        'article{height:124px;box-sizing:border-box;border-bottom:1px solid #bdc5d0;display:flex;gap:25px;background:#fafafa}'
                        'article img{width:280px;height:123px;object-fit:none}h2{font-size:20px;margin:15px 0 7px}p{font-size:14px}'
                        'article:hover{background:#f1f5f9}</style><header></header>' + rows + '<footer></footer>'
                        f'<script>onload=onscroll=()=>{{document.title={json.dumps(title)}+" HTML height="+Math.ceil(document.body.getBoundingClientRect().height*devicePixelRatio)+" y="+scrollY}};'
                        'let frame=0;setInterval(()=>document.body.style.filter="brightness("+(++frame%2?1.035:0.975)+")",350)</script>')
        (folder / "natural.html").write_text(natural_html, encoding="utf-8")
        crm_document = document_image(160, 1600)
        crm_document.save(folder / "crm-document.png")
        (folder / "crm.html").write_text(
            f'<!doctype html><title>{title} CRM</title><style>'
            'html,body{margin:0;overflow:hidden;width:100%;height:100%}'
            'body{background:url(document.png) center/cover}'
            '#panel{position:fixed;top:30px;left:50%;transform:translateX(-50%);'
            'width:160px;height:520px;overflow:auto;scrollbar-width:none;scroll-behavior:smooth}'
            'img{display:block}</style><div id="panel"><img src="crm-document.png" width="160" height="1600"></div>'
            f'<script>let panel=document.getElementById("panel");onload=panel.onscroll=()=>'
            f'{{document.title={json.dumps(title)}+" CRM y="+panel.scrollTop}};</script>', encoding="utf-8")
        process = subprocess.Popen([str(FIREFOX), "-no-remote", "-profile", str(profile.resolve()),
                                    "-width", "980", "-height", "760", (folder / "index.html").resolve().as_uri()],
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        handle = 0
        root = loader = driver = None
        try:
            deadline = time.monotonic() + 75
            while not handle and time.monotonic() < deadline:
                windows = [window for window in gw.getAllWindows() if title in window.title]
                handle = windows[0]._hWnd if windows else 0
                time.sleep(0.15)
            self.assertTrue(handle, "Isolated Firefox window did not open")
            window = gw.Win32Window(handle)
            deadline = time.monotonic() + 10
            while "focus=" not in window.title and time.monotonic() < deadline:
                time.sleep(0.1)
            self.assertIn("focus=", window.title, "Local image page did not finish loading")
            root = tk.Tk()
            app = ScreenCaptureApp(root, language="pl")
            root.update()
            with app._hidden_capture_windows():
                # Supply a real activation gesture on this fixture's empty
                # title-bar area; Windows can reject background test startup.
                pyautogui.click(*win32gui.ClientToScreen(handle, (700, 12)))
                app._focus_window_if_possible(window)
                time.sleep(1)
                # Focus a blank, link-free margin of this local fixture so both
                # timings start with document focus, not browser startup UI.
                self.assertEqual(win32gui.GetForegroundWindow(), handle)
                point = win32gui.ClientToScreen(handle, (900, 150))
                pyautogui.click(*point)
                time.sleep(0.15)
                driver = WindowsScrollDriver(window)
                baseline = driver.snapshot()
                loader = CaptureProgress(root, driver.bbox)
                driver.pulse, driver.frame_guard = loader.pump, loader.capture_frame
                loader.set_message("Test ładowania pełnej strony…")
                covered = driver.snapshot()
                # Firefox's native scrollbar can fade outside the panel while
                # it is opening. Compare all pixels actually covered by it.
                left, top, right, bottom = win32gui.GetWindowRect(loader.handle)
                panel = (left - driver.bbox[0], top - driver.bbox[1],
                         right - driver.bbox[0], bottom - driver.bbox[1])
                self.assertIsNone(ImageChops.difference(baseline, covered).crop(panel).getbbox(), "Loader leaked into the screenshot")
                self.assertEqual(win32gui.GetForegroundWindow(), handle, "Loader stole keyboard focus")
                engine = ScrollingCapture(driver, vertical=True, progress=loader.set_message)
                result = engine.capture()
                result.save(folder / "full-page.png")
                self.assertEqual(result.height, document.height,
                                 f"{window.title}; captured={engine.frame_count}; reason={engine.incomplete_reason}")
                # The engine can trim static white margins. Compare the moving image.
                self.assertLessEqual(result.width, document.width)
                # Rounded native window corners can affect the outer two
                # columns of subsequent tiles. Check all rows of the interior.
                interior = result.crop((3, 0, result.width - 3, result.height))
                candidates = [ImageChops.difference(interior, document.crop((x + 3, 0, x + result.width - 3, document.height))).getbbox()
                              for x in range(document.width - result.width + 1)]
                self.assertIn(None, candidates, "Browser content was skipped or duplicated")
                # Exercise real antialiased HTML, fractional layout and redraws.
                self.assertEqual(win32gui.GetForegroundWindow(), handle)
                pyautogui.hotkey("ctrl", "l")
                pyautogui.write((folder / "natural.html").resolve().as_uri(), interval=0.001)
                pyautogui.press("enter")
                deadline = time.monotonic() + 10
                while "HTML height=" not in window.title and time.monotonic() < deadline:
                    time.sleep(0.1)
                self.assertIn("HTML height=", window.title, "Local HTML page did not finish loading")
                time.sleep(0.25)
                natural_height = int(window.title.split("height=")[-1].split()[0])
                natural = ScrollingCapture(driver, vertical=True, progress=loader.set_message).capture()
                natural.save(folder / "full-page-html.png")
                self.assertLessEqual(abs(natural.height - natural_height), 8, "HTML content was skipped or excessively repeated")
                for box, color in (((natural.width // 4, 2, natural.width * 3 // 4, 18), (242, 1, 121)),
                                    ((natural.width // 4, natural.height - 18, natural.width * 3 // 4, natural.height - 2), (1, 222, 244))):
                    mean = ImageStat.Stat(natural.crop(box)).mean
                    self.assertLess(max(abs(a - b) for a, b in zip(mean, color)), 15, "Top or bottom marker is missing")
                # A real CRM-like inner panel: most of the surrounding image
                # remains textured and fixed while the small central panel moves.
                pyautogui.hotkey("ctrl", "l")
                pyautogui.write((folder / "crm.html").resolve().as_uri(), interval=0.001)
                pyautogui.press("enter")
                deadline = time.monotonic() + 10
                while "CRM y=" not in window.title and time.monotonic() < deadline:
                    time.sleep(0.1)
                self.assertIn("CRM y=", window.title, "Local CRM fixture did not load")
                time.sleep(0.25)
                driver.close()
                driver = WindowsScrollDriver(window)
                driver.pulse, driver.frame_guard = loader.pump, loader.capture_frame
                crm_engine = ScrollingCapture(driver, progress=loader.set_message, include_window_frame=True)
                crm_result = crm_engine.capture()
                crm_result.save(folder / "crm-full-panel.png")
                self.assertIsNone(crm_engine.incomplete_reason)
                self.assertGreater(crm_engine.frame_count, 1)
                content = crm_result.crop(crm_result.info["capture_content_box"])
                self.assertEqual(content.size, crm_document.size)
                self.assertIsNone(ImageChops.difference(content, crm_document).getbbox(), "CRM rows were missed or duplicated")
                self.assertGreater(crm_result.info["capture_content_box"][1], 60, "Browser toolbar was cropped")
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
