"""Panel selection keeps native screen and client coordinates consistent."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from app_advanced import SelectionOverlay, tk
from scroll_panel_picker import ScrollPanelPicker


class PanelPickerTests(unittest.TestCase):
    def choose(self, selection=None, moved=False):
        window = SimpleNamespace(_hWnd=123)
        app = Mock()
        app.window_table.selection.return_value = ("crm",)
        app.window_rows = {"crm": SimpleNamespace(window=window)}
        app._hide_capture_windows.return_value = [("original", "state")]
        bounds = (-500, 100, 500, 800)

        class Overlay:
            def __init__(self, callback, cancel_callback, **options):
                self.callback, self.cancel_callback = callback, cancel_callback
                self.bounds = options["bounds"]

            def start_select(self):
                if selection is None:
                    self.cancel_callback()
                else:
                    self.callback(selection)

        positions = [bounds, (-490, 100, 510, 800) if moved else bounds]
        with patch("scroll_panel_picker.window_is_available", return_value=True), \
                patch("scroll_panel_picker.client_bounds", side_effect=positions), \
                patch("app_advanced.SelectionOverlay", Overlay):
            ScrollPanelPicker._capture_scroll_panel(app)
        app._restore_capture_windows.assert_called_once_with([("original", "state")])
        return app, window

    def test_selection_on_left_monitor_is_converted_and_clamped_to_client(self):
        app, window = self.choose((-550, 170, 600, 760))
        app._capture_scrolled_window.assert_called_once_with(window, capture_region=(0, 70, 1000, 660))

    def test_cancel_restores_windows_without_capture(self):
        app, _ = self.choose()
        app._capture_scrolled_window.assert_not_called()

    def test_window_move_during_selection_stops_capture(self):
        app, _ = self.choose((-400, 170, 450, 760), moved=True)
        app._capture_scrolled_window.assert_not_called()
        app._report_capture_failure.assert_called_once()

    def test_too_small_selection_stops_capture(self):
        app, _ = self.choose((-400, 170, -390, 190))
        app._capture_scrolled_window.assert_not_called()


class PanelOverlayTests(unittest.TestCase):
    def test_overlay_uses_absolute_screen_position_and_local_rectangle_coordinates(self):
        import win32con
        import win32gui
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        selected = Mock()
        bounds = (-420, 80, 220, 480)
        overlay = SelectionOverlay(selected, bounds=bounds, instruction="Select content")
        overlay.start_select()
        handle = win32gui.GetAncestor(overlay.winfo_id(), win32con.GA_ROOT)
        self.assertEqual(win32gui.GetWindowRect(handle), bounds)
        overlay.on_press(SimpleNamespace(x=30, y=40, x_root=-390, y_root=120))
        overlay.on_drag(SimpleNamespace(x=200, y=180, x_root=-220, y_root=260))
        self.assertEqual(overlay.canvas.coords(overlay.rect), [30, 40, 200, 180])
        overlay.on_release(SimpleNamespace(x_root=-220, y_root=260))
        selected.assert_called_once_with((-390, 120, -220, 260))


if __name__ == "__main__":
    unittest.main()
