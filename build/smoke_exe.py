"""Launch the packaged build, verify its window, and close only that window."""

import subprocess
import struct
import sys
import time
from pathlib import Path

import pygetwindow as gw
import win32api
import win32con
import win32gui


executable = Path(sys.argv[1] if len(sys.argv) > 1 else "dist/MiniScreenShot_v1.1.2.exe").resolve()
title = "MiniScreenShot v1.1.2"

# Check that every ICO resolution is actually embedded in the packaged EXE.
icon_data = Path("assets/capture-frame.ico").read_bytes()
_, icon_type, count = struct.unpack_from("<HHH", icon_data)
assert icon_type == 1 and count == 10
expected_frames = set()
for index in range(count):
    entry = struct.unpack_from("<BBBBHHII", icon_data, 6 + index * 16)
    length, offset = entry[-2:]
    expected_frames.add(icon_data[offset:offset + length])
module = win32api.LoadLibraryEx(str(executable), 0, win32con.LOAD_LIBRARY_AS_DATAFILE)
try:
    frames = {win32api.LoadResource(module, win32con.RT_ICON, resource)
              for resource in win32api.EnumResourceNames(module, win32con.RT_ICON)}
    assert expected_frames.issubset(frames), "EXE does not contain the intended icon frames"
finally:
    win32api.FreeLibrary(module)
print("EXE icon resources: 10 intended resolutions, OK")
existing = {window._hWnd for window in gw.getAllWindows()}
process = subprocess.Popen([str(executable)], creationflags=subprocess.CREATE_NO_WINDOW)
window = None
try:
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        candidates = [item for item in gw.getAllWindows()
                      if item.title == title and item._hWnd not in existing]
        for candidate in candidates:
            # Tk can briefly expose a tiny startup wrapper before mapping the
            # final main window and applying its native icons.
            handle = candidate._hWnd
            if (win32gui.IsWindow(handle) and win32gui.IsWindowVisible(handle)
                    and candidate.width >= 450 and candidate.height >= 350
                    and win32gui.SendMessage(handle, win32con.WM_GETICON, win32con.ICON_BIG, 0)
                    and win32gui.SendMessage(handle, win32con.WM_GETICON, win32con.ICON_SMALL, 0)):
                window = candidate
                break
        if window is not None:
            break
        if process.poll() is not None:
            raise RuntimeError(f"Packaged app exited before opening its window: {process.returncode}")
        time.sleep(0.2)
    if window is None:
        raise RuntimeError("Packaged app did not open its main window within 25 seconds")
    print(f"EXE started: {window.title}; window {window.width}x{window.height}")
    assert win32gui.SendMessage(window._hWnd, win32con.WM_GETICON, win32con.ICON_BIG, 0), "Missing large window icon"
    assert win32gui.SendMessage(window._hWnd, win32con.WM_GETICON, win32con.ICON_SMALL, 0), "Missing small window icon"
    print("Main window title/taskbar icons: OK")
finally:
    if window is not None and win32gui.IsWindow(window._hWnd):
        window.close()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.terminate()
        raise RuntimeError("Packaged app did not exit after closing the window")

if process.returncode != 0:
    raise RuntimeError(f"Packaged app exited with code {process.returncode}")
print("Packaged app startup and shutdown: OK")
