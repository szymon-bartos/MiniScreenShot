"""Focus regression checks without injecting mouse or keyboard input."""
import os
import unittest
from unittest.mock import Mock, patch

from scroll_capture import CaptureCancelled, ScrollCaptureError
from windows_scroll import WindowsScrollDriver, ensure_window_foreground


class CaptureFocusTests(unittest.TestCase):
    def setUp(self):
        self.foreground = 100
        self.driver = WindowsScrollDriver.__new__(WindowsScrollDriver)
        self.driver.handle = 100
        self.driver.bbox = (0, 0, 500, 300)
        self.driver._client_bbox = Mock(return_value=self.driver.bbox)
        self.driver.user32 = Mock()
        self.driver.pointer = (250, 150)
        for target, replacement in (
            ("windows_scroll.win32gui.GetForegroundWindow", lambda: self.foreground),
            ("windows_scroll.win32gui.GetAncestor", lambda handle, flag: 100 if handle == 101 else handle),
            ("windows_scroll.win32api.GetAsyncKeyState", lambda key: 0),
            ("windows_scroll.win32gui.GetClassName", lambda handle: "TestWindow"),
            ("windows_scroll.win32gui.WindowFromPoint", lambda point: 101),
            ("windows_scroll.win32api.GetCurrentThreadId", lambda: 1),
            ("windows_scroll.win32gui.BringWindowToTop", Mock()),
            ("windows_scroll.win32process.GetWindowThreadProcessId", lambda handle: (1, os.getpid() if handle == 200 else os.getpid() + 1)),
        ):
            patcher = patch(target, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_target_child_does_not_cancel_capture(self):
        self.foreground = 101
        self.driver._check()

    def test_transient_missing_foreground_does_not_cancel_capture(self):
        with patch("windows_scroll.win32gui.GetForegroundWindow", side_effect=[0, 0, 100]):
            self.driver._check()

    def test_focus_returning_to_capture_process_is_recovered(self):
        self.foreground = 200
        def activate(handle):
            self.foreground = handle
        with patch("windows_scroll.win32gui.SetForegroundWindow", side_effect=activate) as activate_mock:
            self.driver._check()
        activate_mock.assert_called_once_with(100)

    def test_switch_to_other_application_cancels_before_sending_wheel_input(self):
        self.foreground = 300
        with patch("windows_scroll.win32gui.SetForegroundWindow") as activate, patch("windows_scroll.time.monotonic", side_effect=[0, 1]), patch("windows_scroll.win32gui.PostMessage") as wheel:
            with self.assertRaises(CaptureCancelled):
                self.driver.scroll("y", 1, 3)
        activate.assert_not_called()
        self.driver.user32.mouse_event.assert_not_called()
        wheel.assert_not_called()
        self.driver.user32.SendInput.assert_not_called()

    def test_wheel_targets_selected_content_and_preserves_signed_screen_coordinates(self):
        self.driver.input_handle = 101
        self.driver.pointer = (-200, 150)
        with patch("windows_scroll.win32api.SetCursorPos"), patch("windows_scroll.time.sleep"), patch("windows_scroll.win32gui.PostMessage") as wheel:
            self.driver.scroll("x", 1, 2)
            self.driver.scroll("y", 1, 1)
        coordinates = ((-200) & 0xffff) | (150 << 16)
        self.assertEqual(wheel.call_args_list[0].args, (101, 0x020E, 240 << 16, coordinates))
        self.assertEqual(wheel.call_args_list[1].args, (101, 0x020A, ((-120) & 0xffff) << 16, coordinates))
        self.driver.user32.mouse_event.assert_not_called()

    def test_overlay_outside_target_does_not_receive_wheel_input(self):
        self.driver.input_handle = 101
        with patch("windows_scroll.win32gui.WindowFromPoint", return_value=300), patch("windows_scroll.win32api.SetCursorPos"), patch("windows_scroll.win32gui.PostMessage") as wheel:
            self.driver.scroll("y", 1, 1)
        self.assertEqual(wheel.call_args.args[0], 101)

    def test_browser_native_input_is_allowed_only_over_selected_window(self):
        self.driver._browser = True
        self.driver.user32.SendInput.return_value = 1
        self.driver.input_handle = 101
        with patch("windows_scroll.win32api.SetCursorPos"), patch("windows_scroll.win32gui.PostMessage") as posted:
            self.driver.scroll("y", 1, 1)
        self.driver.user32.SendInput.assert_called_once()
        posted.assert_not_called()
        self.driver.user32.SendInput.reset_mock()
        with patch("windows_scroll.win32gui.WindowFromPoint", return_value=300), patch("windows_scroll.win32api.SetCursorPos"), patch("windows_scroll.win32gui.PostMessage"):
            self.driver.scroll("y", 1, 1)
        self.driver.user32.SendInput.assert_not_called()

    def test_escape_still_cancels_before_focus_recovery(self):
        self.foreground = 200
        with patch("windows_scroll.win32api.GetAsyncKeyState", return_value=0x8000), patch("windows_scroll.win32gui.SetForegroundWindow") as activate:
            with self.assertRaises(CaptureCancelled):
                self.driver._check()
        activate.assert_not_called()

    def test_failed_initial_activation_is_reported(self):
        self.foreground = 300
        with patch("windows_scroll.win32gui.SetForegroundWindow"), patch("windows_scroll.time.monotonic", side_effect=[0, 1]):
            with self.assertRaisesRegex(ScrollCaptureError, "uaktywnić"):
                ensure_window_foreground(100)

    def test_delayed_initial_activation_is_awaited(self):
        with patch("windows_scroll.win32gui.GetForegroundWindow", side_effect=[300, 300, 100]), patch("windows_scroll.win32gui.SetForegroundWindow") as activate:
            ensure_window_foreground(100)
        activate.assert_called_once_with(100)

    def test_foreground_lock_recovery_detaches_input_queues(self):
        self.foreground = 300
        attached = False
        def attach(first, second, enabled):
            nonlocal attached
            attached = enabled
        def activate(handle):
            if attached:
                self.foreground = handle
        with patch("windows_scroll.win32api.GetCurrentThreadId", return_value=2), patch("windows_scroll.win32process.AttachThreadInput", side_effect=attach) as link, patch("windows_scroll.win32gui.SetForegroundWindow", side_effect=activate):
            ensure_window_foreground(100, timeout=0)
        self.assertFalse(attached)
        self.assertEqual([call.args for call in link.call_args_list], [(2, 1, True), (2, 1, False)])


if __name__ == "__main__":
    unittest.main()
