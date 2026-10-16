"""Native, two-axis test window; contains only deterministic synthetic pixels."""
import ctypes
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import win32api
import win32con
import win32gui
from PIL import Image, ImageDraw, ImageWin
from test_scroll_capture import document_image

ctypes.windll.user32.SetProcessDPIAware()
document = document_image(421, 363)
offset_x = offset_y = 0


def procedure(handle, message, wparam, lparam):
    global offset_x, offset_y
    if message in (0x020A, 0x020E):
        ticks = ctypes.c_short((wparam >> 16) & 0xffff).value // 120
        client = win32gui.GetClientRect(handle)
        width, height = client[2] - 32, client[3] - 64
        if message == 0x020A:
            offset_y = max(0, min(document.height - height, offset_y - ticks * 27))
        else:
            offset_x = max(0, min(document.width - width, offset_x + ticks * 27))
        win32gui.InvalidateRect(handle, None, False)
        win32gui.UpdateWindow(handle)
        return 0
    if message == win32con.WM_PAINT:
        hdc, paint = win32gui.BeginPaint(handle)
        try:
            client = win32gui.GetClientRect(handle)
            width, height = client[2], client[3]
            frame = Image.new("RGB", (width, height), "#17243b")
            draw = ImageDraw.Draw(frame)
            draw.text((18, 10), "FIXED HEADER", fill="white")
            draw.text((18, height - 18), "FIXED FOOTER", fill="white")
            frame.paste(document.crop((offset_x, offset_y, offset_x + width - 32, offset_y + height - 64)), (16, 40))
            ImageWin.Dib(frame).draw(hdc, (0, 0, width, height))
        finally:
            win32gui.EndPaint(handle, paint)
        return 0
    if message == win32con.WM_DESTROY:
        win32gui.PostQuitMessage(0)
        return 0
    return win32gui.DefWindowProc(handle, message, wparam, lparam)


window_class = win32gui.WNDCLASS()
window_class.hInstance = win32api.GetModuleHandle(None)
window_class.lpszClassName = "MiniScreenShotScrollFixture"
window_class.lpfnWndProc = procedure
window_class.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
win32gui.RegisterClass(window_class)
handle = win32gui.CreateWindowEx(0, window_class.lpszClassName, sys.argv[1], win32con.WS_OVERLAPPEDWINDOW,
                                120, 120, 328, 303, 0, 0, window_class.hInstance, None)
win32gui.ShowWindow(handle, win32con.SW_SHOW)
win32gui.UpdateWindow(handle)
try:
    win32gui.SetForegroundWindow(handle)
except win32gui.error:
    pass
win32gui.PumpMessages()
