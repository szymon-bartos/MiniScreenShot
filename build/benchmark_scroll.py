"""Time the existing correctness tests with real desktop capture."""
import argparse
import functools
import json
from pathlib import Path
import sys
import time
import unittest

workspace = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(workspace))
parser = argparse.ArgumentParser()
parser.add_argument("--label", required=True)
parser.add_argument("--browser", action="store_true")
arguments = parser.parse_args()
destination = workspace / "build" / "scroll-performance"

import scroll_capture
import windows_scroll

measurements = {}
def measure(owner, name, label):
    original = getattr(owner, name)
    @functools.wraps(original)
    def wrapper(*args, **kwargs):
        started = time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            entry = measurements.setdefault(label, {"calls": 0, "seconds": 0})
            entry["calls"] += 1
            entry["seconds"] += time.perf_counter() - started
    setattr(owner, name, wrapper)

for method in ("_grab", "snapshot", "scroll"):
    measure(windows_scroll.WindowsScrollDriver, method, method)
measure(scroll_capture, "estimate_shift", "registration")
measure(scroll_capture.ScrollingCapture, "_seek_start", "seek_start")
measure(scroll_capture.ScrollingCapture, "capture", "capture")
test_name = ("test_scroll_browser.FirefoxCaptureTests.test_full_page_with_smooth_scrolling_and_loader" if arguments.browser
             else "test_scroll_live.LiveScrollTests.test_main_button_captures_two_axis_document_without_repeated_pixels")
started = time.perf_counter()
result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName(test_name))
report = {"label": arguments.label, "test": test_name, "success": result.wasSuccessful(),
          "total_seconds": time.perf_counter() - started, "measurements": measurements}
destination.mkdir(parents=True, exist_ok=True)
(destination / f"{arguments.label}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2), flush=True)
sys.exit(0 if result.wasSuccessful() else 1)
