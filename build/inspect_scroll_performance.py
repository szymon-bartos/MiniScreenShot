"""Trace real wheel delivery and rendered changes on the isolated browser fixture."""
from pathlib import Path
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import win32gui
from PIL import ImageChops
from windows_scroll import WindowsScrollDriver
import scroll_capture

original_scroll = WindowsScrollDriver.scroll
original_snapshot = WindowsScrollDriver.snapshot
last = None
original_estimate = scroll_capture.estimate_shift

def estimate(*args, **kwargs):
    result = original_estimate(*args, **kwargs)
    print("MATCH", result, "expected", kwargs.get("expected", args[3] if len(args) > 3 else None), flush=True)
    return result

scroll_capture.estimate_shift = estimate
original_record = scroll_capture.ScrollingCapture._record
original_capture = scroll_capture.ScrollingCapture.capture

def capture(self):
    result = original_capture(self)
    print("RESULT", result.size, self.moving, "partial", self.incomplete_reason, flush=True)
    if self.frame_count == 1:
        import pyautogui
        print("CURSOR", pyautogui.position(), flush=True)
        pyautogui.click(*win32gui.ClientToScreen(self.driver.handle, (100, 150)))
        time.sleep(0.3)
        print("AFTER CLICK", win32gui.GetWindowText(self.driver.handle), flush=True)
        pyautogui.scroll(-3)
        time.sleep(0.5)
        print("AFTER REAL WHEEL", win32gui.GetWindowText(self.driver.handle), flush=True)
    return result

scroll_capture.ScrollingCapture.capture = capture

def record(self, store, frame, x, y, dx, dy):
    print("RECORD", x, y, "viewport", self.moving, "actual", win32gui.GetWindowText(self.driver.handle), flush=True)
    return original_record(self, store, frame, x, y, dx, dy)

scroll_capture.ScrollingCapture._record = record

def scroll(self, axis, direction, units):
    hit = win32gui.WindowFromPoint(self.pointer)
    print("WHEEL", axis, direction, units, "target", self.input_handle,
          "under pointer", hit, win32gui.GetClassName(hit), flush=True)
    return original_scroll(self, axis, direction, units)

def snapshot(self):
    global last
    started = time.monotonic()
    frame = original_snapshot(self)
    print("FRAME", round(time.monotonic() - started, 3),
          ImageChops.difference(last, frame).getbbox() if last is not None else "first",
          win32gui.GetWindowText(self.handle), flush=True)
    last = frame
    return frame

WindowsScrollDriver.scroll = scroll
WindowsScrollDriver.snapshot = snapshot
unittest.main(module="test_scroll_browser", verbosity=2)
