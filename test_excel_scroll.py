"""Excel captures must stop at active-sheet values, not formatted empty cells."""
import ctypes
import threading
import time
import unittest
from pathlib import Path

import pygetwindow as gw
import win32con
import win32gui
import win32process
import win32com.client

from app_advanced import ScreenCaptureApp, tk
from excel_scroll import ExcelSheetScroll, last_data_cell
from scroll_capture import ScrollingCapture
from windows_scroll import WindowsScrollDriver


@unittest.skipUnless(Path('C:/Program Files/Microsoft Office/root/Office16/EXCEL.EXE').exists(), 'Excel is not installed')
class ExcelScrollTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ctypes.windll.user32.SetProcessDPIAware()
        cls.excel = win32com.client.DispatchEx('Excel.Application')
        cls.book = cls.excel.Workbooks.Add()
        cls.sheet = cls.book.Worksheets(1)
        cls.sheet.Name = 'MiniScreenShot test'
        cls.sheet.Range('A1:F85').Value = tuple(tuple(f'Row {row:03d} Col {col}' for col in range(1, 7)) for row in range(1, 86))
        cls.sheet.Range('A20:F25').ClearContents()
        cls.sheet.Rows.RowHeight = 18
        cls.sheet.Range('A40000:Z40000').Interior.Color = 0x00FFFF
        cls.sheet.Range('A85:F85').Interior.Color = 0x7911EF
        cls.sheet.Range('A86:F90').Interior.Color = 0x00FFFF
        cls.other = cls.book.Worksheets.Add()
        cls.other.Range('A5000').Value = 'Data from a different worksheet'
        cls.wide = cls.book.Worksheets.Add()
        cls.wide.Name = 'Wide test'
        cls.wide.Range('A1:AD12').Value = tuple(tuple(f'{row}:{col}' for col in range(1, 31)) for row in range(1, 13))
        cls.wide.Rows.RowHeight = 18
        cls.excel.Visible = True
        cls.handle = int(cls.excel.Hwnd)
        cls.pid = win32process.GetWindowThreadProcessId(cls.handle)[1]
        cls.stop = threading.Event()
        def dismiss_test_activation():
            # Only the activation wizard of our separately created test process.
            # Dismissing it neither activates Office nor changes license settings.
            while not cls.stop.wait(0.1):
                windows = []
                win32gui.EnumWindows(lambda h, _: windows.append(h) if win32process.GetWindowThreadProcessId(h)[1] == cls.pid
                                     and win32gui.GetClassName(h) == 'NUIDialog' and 'aktywacji' in win32gui.GetWindowText(h) else None, None)
                for handle in windows:
                    win32gui.PostMessage(handle, win32con.WM_CLOSE, 0, 0)
        cls.thread = threading.Thread(target=dismiss_test_activation, daemon=True)
        cls.thread.start()
        win32gui.ShowWindow(cls.handle, win32con.SW_RESTORE)
        win32gui.MoveWindow(cls.handle, 30, 30, 1300, 1000, True)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.book.Close(False)
            cls.excel.Quit()
        finally:
            cls.stop.set()
            cls.thread.join(timeout=2)

    def capture(self, sheet, vertical, horizontal):
        sheet.Activate()
        root = tk.Tk()
        driver = None
        try:
            app = ScreenCaptureApp(root)
            root.update()
            with app._hidden_capture_windows():
                window = gw.Win32Window(self.handle)
                app._focus_window_if_possible(window)
                time.sleep(0.2)
                driver = WindowsScrollDriver(window)
                engine = ScrollingCapture(driver, vertical=vertical, horizontal=horizontal, include_window_frame=True)
                result = engine.capture()
                self.assertIsNone(engine.incomplete_reason)
                self.assertLess(engine.frame_count, 70)
                self.assertIsNotNone(driver._excel)
                return result, driver._excel, engine
        finally:
            if driver:
                driver.close()
            root.destroy()

    def test_vertical_stops_at_row_85_and_keeps_ribbon(self):
        result, bounds, engine = self.capture(self.sheet, True, False)
        try:
            self.assertEqual((bounds.last_row, bounds.last_column), (85, 6))
            box = result.info['capture_content_box']
            self.assertGreater(box[1], 100, 'Excel ribbon was cropped')
            self.assertEqual(box[3] - box[1], round(float(self.sheet.Range('A1:A85').Height) * bounds.scale_y))
            self.assertGreater(engine.frame_count, 1)
            # The final row is magenta. Formatted-only yellow rows below it
            # must not be included, including across a gap of empty data rows.
            strip = result.crop((box[0] + 10, box[3] - 8, box[2] - 10, box[3] - 3)).convert('RGB')
            colors = list(strip.get_flattened_data())
            magenta = sum(r > 180 and g < 60 and b > 80 for r, g, b in colors)
            # One raster row may contain the dark Excel grid line.
            self.assertGreaterEqual(magenta / len(colors), 0.8)
        finally:
            result.close()

    def test_horizontal_stops_at_column_ad(self):
        result, bounds, engine = self.capture(self.wide, False, True)
        try:
            self.assertEqual((bounds.last_row, bounds.last_column), (12, 30))
            box = result.info['capture_content_box']
            expected = round(float(self.wide.Range('A1:AD1').Width) * bounds.scale_x)
            self.assertEqual(box[2] - box[0], expected)
            self.assertGreater(engine.frame_count, 1)
        finally:
            result.close()


if __name__ == '__main__':
    unittest.main()
