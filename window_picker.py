"""Application selection embedded in the main capture dashboard."""

import tkinter as tk
from tkinter import ttk

from ui_widgets import BACKGROUND, SURFACE, TEXT, MUTED, RoundedButton
from window_catalog import describe_window, window_is_available
from localization import msg


class InlineWindowPicker:
    def _build_window_picker(self, parent):
        px = lambda value: round(value * self.ui_scale)
        self.window_entries = []
        self.window_rows = {}
        self.selected_window_key = None
        self.window_filter = tk.StringVar(self.root)
        self.window_picker_card = tk.Frame(parent, bg=SURFACE, padx=px(18), pady=px(16),
                                            highlightthickness=1, highlightbackground="#25324a")
        self.window_picker_card.grid(row=2, column=0, sticky="ew", pady=(px(18), 0))
        self.window_picker_card.columnconfigure(0, weight=1)
        self.window_picker_card.grid_remove()
        self.ui.widget(tk.Label, self.window_picker_card, text="Wybierz okno aplikacji", bg=SURFACE, fg=TEXT,
                 font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        self.refresh_windows_button = self.ui.widget(RoundedButton, self.window_picker_card, "Odśwież", self._refresh_window_picker, background=SURFACE)
        self.refresh_windows_button.grid(row=0, column=1, sticky="e", padx=(px(12), 0))

        search = tk.Frame(self.window_picker_card, bg=BACKGROUND, padx=px(10), pady=px(8))
        search.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(px(12), px(12)))
        search.columnconfigure(1, weight=1)
        self.ui.widget(tk.Label, search, text="Szukaj", bg=BACKGROUND, fg=MUTED, font=("Segoe UI", 9)).grid(row=0, column=0, padx=(0, px(12)))
        self.window_search_entry = tk.Entry(search, textvariable=self.window_filter, bg=BACKGROUND, fg=TEXT,
                                            insertbackground=TEXT, selectbackground="#4f46e5", bd=0,
                                            highlightthickness=0, font=("Segoe UI", 10))
        self.window_search_entry.grid(row=0, column=1, sticky="ew")

        self.style.configure("Windows.Treeview", background=BACKGROUND, fieldbackground=BACKGROUND, foreground=TEXT,
                             rowheight=px(36), borderwidth=0, bordercolor="#25324a", lightcolor="#25324a",
                             darkcolor="#25324a", font=("Segoe UI", 10))
        self.style.configure("Windows.Treeview.Heading", background="#1c2a42", foreground=MUTED,
                             relief="flat", padding=(px(10), px(8)), font=("Segoe UI", 9, "bold"))
        self.style.map("Windows.Treeview", background=[("selected", "#373d78")], foreground=[("selected", "#ffffff")])
        self.style.map("Windows.Treeview.Heading", background=[("active", "#293a56")])
        table = tk.Frame(self.window_picker_card, bg=SURFACE)
        table.grid(row=2, column=0, columnspan=2, sticky="ew")
        table.columnconfigure(0, weight=1)
        self.window_table = ttk.Treeview(table, columns=("program", "document"), show="headings", height=5,
                                         selectmode="browse", style="Windows.Treeview")
        self.ui.heading(self.window_table, "program", "Program", anchor="w")
        self.ui.heading(self.window_table, "document", "Plik, strona lub tytuł okna", anchor="w")
        self.window_table.column("program", width=px(180), minwidth=px(130), stretch=False)
        self.window_table.column("document", width=px(320), minwidth=px(160), stretch=True)
        self.window_table.grid(row=0, column=0, sticky="ew")
        vertical = ttk.Scrollbar(table, orient="vertical", command=self.window_table.yview, style="Preview.Vertical.TScrollbar")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(table, orient="horizontal", command=self.window_table.xview, style="Preview.Horizontal.TScrollbar")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.window_table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.window_picker_message = self.ui.widget(tk.Label, self.window_picker_card, bg=SURFACE, fg=MUTED, justify="left", anchor="w",
                                               font=("Segoe UI", 9), wraplength=px(550))
        self.window_picker_message.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(px(10), 0))
        self.window_table.bind("<<TreeviewSelect>>", self._window_selection_changed)
        self.window_table.bind("<Return>", lambda event: self._capture_selected_window())
        self.window_table.bind("<Double-Button-1>", self._window_double_click)
        self.window_table.bind("<MouseWheel>", self._scroll_window_table)
        self.window_filter.trace_add("write", lambda *args: self._filter_window_list())

    def _show_window_picker(self):
        self.window_picker_card.grid()
        self._refresh_window_picker()
        self.root.update_idletasks()
        # Bring the embedded list into view even when the mode cards are stacked.
        total = max(1, self.dashboard_body.winfo_height())
        self.dashboard_canvas.yview_moveto(max(0, self.window_picker_card.winfo_y() - 8) / total)

    def _refresh_window_picker(self):
        try:
            process_paths = {}
            self.window_entries = sorted((describe_window(window, process_paths) for window in self.get_selectable_windows()),
                                         key=lambda entry: (entry.program.casefold(), entry.document.casefold()))
            self._filter_window_list()
        except Exception as exc:
            self.window_entries = []
            self._filter_window_list()
            self.ui.set(self.window_picker_message, text="Nie udało się odczytać okien. Spróbuj odświeżyć listę.")
            self._add_debug_log(f"Window list failed: {exc}")

    def _filter_window_list(self):
        query = self.window_filter.get().strip().casefold()
        entries = [entry for entry in self.window_entries
                   if query in entry.label.casefold() or query in self.ui.render(entry.program).casefold()]
        self.window_table.delete(*self.window_table.get_children())
        self.window_rows = {}
        for index, entry in enumerate(entries):
            row = f"window_{index}"
            self.window_rows[row] = entry
            self.window_table.insert("", "end", iid=row, values=(self.ui.render(entry.program), entry.document or self.ui.render("Okno aplikacji")))
            if entry.key == self.selected_window_key:
                self.window_table.selection_set(row)
                self.window_table.focus(row)
        if not self.window_table.selection():
            self.selected_window_key = None
        self._window_selection_changed()

    def _window_selection_changed(self, event=None):
        selected = self.window_table.selection()
        entry = self.window_rows.get(selected[0]) if selected else None
        self.selected_window_key = entry.key if entry else None
        if entry:
            message = msg("{program} — {document}", program=msg(entry.program), document=entry.document) if entry.document else msg(entry.program)
        elif not self.window_entries:
            message = "Brak dostępnych okien. Otwórz aplikację i kliknij Odśwież."
        elif not self.window_rows:
            message = "Brak wyników. Zmień wyszukiwaną nazwę programu lub pliku."
        else:
            message = msg("Dostępne okna: {count}. Zaznacz jedno, aby wykonać zrzut.", count=len(self.window_rows))
        self.ui.set(self.window_picker_message, text=message)
        if self.selected_mode == "window":
            self.capture_action.configure(state="normal" if entry else "disabled")

    def _capture_selected_window(self):
        selected = self.window_table.selection()
        entry = self.window_rows.get(selected[0]) if selected else None
        if entry is None:
            self._window_selection_changed()
            return "break"
        if not window_is_available(entry):
            self._refresh_window_picker()
            self.set_status("Wybrane okno zostało zamknięte. Wybierz inne.")
            return "break"
        self._capture_window_obj(entry.window)
        return "break"

    def _window_double_click(self, event):
        row = self.window_table.identify_row(event.y)
        if row and self.window_table.identify_region(event.x, event.y) in ("cell", "tree"):
            self.window_table.selection_set(row)
            return self._capture_selected_window()

    def _scroll_window_table(self, event):
        if event.delta:
            self.window_table.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"
