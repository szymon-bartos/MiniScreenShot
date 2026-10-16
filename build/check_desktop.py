"""Read desktop/session availability without sending any input."""
import ctypes
from ctypes import wintypes
import json

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
user32.OpenInputDesktop.restype = wintypes.HANDLE
user32.GetThreadDesktop.argtypes = [wintypes.DWORD]
user32.GetThreadDesktop.restype = wintypes.HANDLE
user32.GetUserObjectInformationW.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
user32.CloseDesktop.argtypes = [wintypes.HANDLE]
handle = user32.OpenInputDesktop(0, False, 1)
error = ctypes.get_last_error()
name = ctypes.create_unicode_buffer(256)
if handle:
    user32.GetUserObjectInformationW(handle, 2, name, ctypes.sizeof(name), None)
    user32.CloseDesktop(handle)
print(json.dumps({"input_desktop": name.value, "open_error": error, "available": bool(handle)}))
