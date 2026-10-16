"""Reusable GDI capture of just the selected client rectangle."""
import ctypes
from ctypes import wintypes
from PIL import Image


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


class DesktopFrameGrabber:
    def __init__(self, bbox):
        self.bbox = bbox
        self.size = (bbox[2] - bbox[0], bbox[3] - bbox[1])
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
        self.user32.GetDC.argtypes = [wintypes.HWND]
        self.user32.GetDC.restype = wintypes.HDC
        self.user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
        self.gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
        self.gdi32.CreateCompatibleDC.restype = wintypes.HDC
        self.gdi32.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.POINTER(BITMAPINFOHEADER), wintypes.UINT,
                                               ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD]
        self.gdi32.CreateDIBSection.restype = wintypes.HBITMAP
        self.gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
        self.gdi32.SelectObject.restype = wintypes.HANDLE
        self.gdi32.BitBlt.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                     wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD]
        self.gdi32.BitBlt.restype = wintypes.BOOL
        self.gdi32.DeleteDC.argtypes = [wintypes.HDC]
        self.gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
        self.screen_dc = self.memory_dc = self.bitmap = self.previous_bitmap = None
        self.pixels = ctypes.c_void_p()
        try:
            self.screen_dc = self.user32.GetDC(None)
            self.memory_dc = self.gdi32.CreateCompatibleDC(self.screen_dc)
            header = BITMAPINFOHEADER()
            header.biSize = ctypes.sizeof(header)
            header.biWidth, header.biHeight = self.size[0], -self.size[1]
            header.biPlanes, header.biBitCount = 1, 32
            self.bitmap = self.gdi32.CreateDIBSection(self.screen_dc, ctypes.byref(header), 0,
                                                     ctypes.byref(self.pixels), None, 0)
            if not all((self.screen_dc, self.memory_dc, self.bitmap, self.pixels.value)):
                raise ctypes.WinError(ctypes.get_last_error())
            self.previous_bitmap = self.gdi32.SelectObject(self.memory_dc, self.bitmap)
            if self.previous_bitmap in (None, ctypes.c_void_p(-1).value):
                raise ctypes.WinError(ctypes.get_last_error())
        except Exception:
            self.close()
            raise

    def grab(self):
        if not self.gdi32.BitBlt(self.memory_dc, 0, 0, *self.size, self.screen_dc, *self.bbox[:2], 0x00CC0020):
            raise ctypes.WinError(ctypes.get_last_error())
        self.gdi32.GdiFlush()
        data = ctypes.string_at(self.pixels, self.size[0] * self.size[1] * 4)
        return Image.frombytes("RGB", self.size, data, "raw", "BGRX", 0, 1)

    def close(self):
        try:
            if self.memory_dc is not None:
                if self.previous_bitmap is not None:
                    self.gdi32.SelectObject(self.memory_dc, self.previous_bitmap)
                self.gdi32.DeleteDC(self.memory_dc)
                self.memory_dc = None
            if self.bitmap is not None:
                self.gdi32.DeleteObject(self.bitmap)
                self.bitmap = None
        finally:
            if self.screen_dc:
                self.user32.ReleaseDC(None, self.screen_dc)
                self.screen_dc = None
