"""Choose one scrolling viewport when a window contains independent panes."""
from localization import msg
from window_catalog import window_is_available
from windows_coordinates import client_bounds


class ScrollPanelPicker:
    def _capture_scroll_panel(self):
        selected = self.window_table.selection()
        entry = self.window_rows.get(selected[0]) if selected else None
        if entry is None:
            self._window_selection_changed()
            return
        if not window_is_available(entry):
            self._refresh_window_picker()
            self.set_status("Wybrane okno zostało zamknięte. Wybierz inne.")
            return
        window = entry.window
        states = self._hide_capture_windows()

        def cancel():
            self._restore_capture_windows(states)
            self.set_status("Wybór panelu anulowany.")

        try:
            self._focus_window_if_possible(window)
            bounds = client_bounds(window._hWnd)

            def chosen(selection):
                self._restore_capture_windows(states)
                try:
                    if client_bounds(window._hWnd) != bounds:
                        self._report_capture_failure("Położenie lub rozmiar okna zmieniły się podczas zrzutu.")
                        return
                    region = (max(0, selection[0] - bounds[0]), max(0, selection[1] - bounds[1]),
                              min(bounds[2] - bounds[0], selection[2] - bounds[0]),
                              min(bounds[3] - bounds[1], selection[3] - bounds[1]))
                    if region[2] - region[0] < 32 or region[3] - region[1] < 32:
                        self.set_status("Zaznacz panel o rozmiarze co najmniej 32 × 32 piksele.")
                        return
                    self._capture_scrolled_window(window, capture_region=region)
                except Exception as exc:
                    self._report_capture_failure(msg("Nie udało się wybrać panelu: {error}", error=str(exc)))

            from app_advanced import SelectionOverlay
            overlay = SelectionOverlay(chosen, cancel, bounds=bounds,
                                       instruction=self.ui.render("Zaznacz samą przewijaną treść. Esc anuluje."))
            overlay.start_select()
        except Exception as exc:
            self._restore_capture_windows(states)
            self._report_capture_failure(msg("Nie udało się wybrać panelu: {error}", error=str(exc)))
