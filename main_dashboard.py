"""Responsive capture dashboard, independent of the screenshot editor."""

import tkinter as tk
from tkinter import ttk

from ui_widgets import BACKGROUND, SURFACE, TEXT, MUTED, ModeCard, RoundedButton, ToggleSwitch


class MainDashboard:
    def _build_dashboard(self, version, default_directory):
        self.ui_scale = self.root.winfo_fpixels("1i") / 96
        px = lambda value: round(value * self.ui_scale)
        self.root.configure(bg=BACKGROUND)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        self._debug_lines = []
        self.selected_mode = "screen"
        self.dashboard_layout = None
        self.vertical_var = tk.BooleanVar(self.root, value=False)
        self.horizontal_var = tk.BooleanVar(self.root, value=False)
        self.output_dir = tk.StringVar(self.root, value=str(default_directory))

        header = tk.Frame(self.root, bg=BACKGROUND, padx=px(28), pady=px(20))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        tk.Label(header, text="  MiniScreenShot", image=self.brand_icon, compound="left", bg=BACKGROUND, fg="#a5b4fc",
                 font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        tk.Label(header, text=f"v{version}", bg=SURFACE, fg=MUTED,
                 padx=px(10), pady=px(4), font=("Segoe UI", 9)).grid(row=0, column=1, sticky="e")
        tk.Label(header, text="Nowy zrzut ekranu", bg=BACKGROUND, fg=TEXT,
                 font=("Segoe UI", 22, "bold")).grid(row=1, column=0, columnspan=2, sticky="w", pady=(px(12), px(4)))
        self.intro_label = tk.Label(header, text="Wybierz, co chcesz uchwycić. Dopracuj obraz w podglądzie.",
                                    bg=BACKGROUND, fg=MUTED, justify="left", anchor="w", font=("Segoe UI", 10))
        self.intro_label.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.capture_notice = tk.Label(header, bg="#341c2d", fg="#fecdd3", padx=px(14), pady=px(10),
                                       justify="left", anchor="w", font=("Segoe UI", 10))
        self.capture_notice.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(px(12), 0))
        self.capture_notice.grid_remove()

        host = tk.Frame(self.root, bg=BACKGROUND)
        host.grid(row=1, column=0, sticky="nsew", padx=px(24))
        host.columnconfigure(0, weight=1)
        host.rowconfigure(0, weight=1)
        self.dashboard_canvas = tk.Canvas(host, bg=BACKGROUND, highlightthickness=0, bd=0, width=1, height=1)
        self.dashboard_canvas.grid(row=0, column=0, sticky="nsew")
        self.dashboard_scrollbar = ttk.Scrollbar(host, orient="vertical", command=self.dashboard_canvas.yview,
                                                 style="Preview.Vertical.TScrollbar")
        self.dashboard_scrollbar.grid(row=0, column=1, sticky="ns", padx=(px(8), 0))
        self.dashboard_canvas.configure(yscrollcommand=self.dashboard_scrollbar.set)
        self.dashboard_body = tk.Frame(self.dashboard_canvas, bg=BACKGROUND, padx=px(4), pady=px(4))
        self.dashboard_body.columnconfigure(0, weight=1)
        self.dashboard_window = self.dashboard_canvas.create_window(0, 0, window=self.dashboard_body, anchor="nw")

        tk.Label(self.dashboard_body, text="TRYB ZRZUTU", bg=BACKGROUND, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", pady=(0, px(10)))
        self.mode_grid = tk.Frame(self.dashboard_body, bg=BACKGROUND)
        self.mode_grid.grid(row=1, column=0, sticky="ew")
        self.mode_cards = [ModeCard(self.mode_grid, key, title, subtitle, self._select_capture_mode)
                           for key, title, subtitle in (
                               ("screen", "Cały ekran", "Wszystko, co widzisz"),
                               ("window", "Okno aplikacji", "Także z przewijaniem"),
                               ("area", "Wybrany obszar", "Zaznacz fragment myszą"))]

        self._build_window_picker(self.dashboard_body)

        scroll_card = tk.Frame(self.dashboard_body, bg=SURFACE, padx=px(18), pady=px(16),
                               highlightthickness=1, highlightbackground="#25324a")
        scroll_card.grid(row=3, column=0, sticky="ew", pady=(px(18), 0))
        scroll_card.columnconfigure(0, weight=1)
        tk.Label(scroll_card, text="Przewijanie okna", bg=SURFACE, fg=TEXT,
                 font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        self.scroll_hint = tk.Label(scroll_card, bg=SURFACE, fg=MUTED, justify="left", anchor="w", font=("Segoe UI", 9))
        self.scroll_hint.grid(row=1, column=0, sticky="ew", pady=(px(4), px(10)))
        self.scroll_options = tk.Frame(scroll_card, bg=SURFACE)
        self.scroll_options.grid(row=2, column=0, sticky="ew")
        self.option_rows = []
        self.scroll_switches = []
        self.option_labels = []
        for variable, title, detail in ((self.vertical_var, "W pionie", "Góra i dół"),
                                         (self.horizontal_var, "W poziomie", "Lewo i prawo")):
            row = tk.Frame(self.scroll_options, bg=SURFACE)
            row.columnconfigure(0, weight=1)
            label = tk.Label(row, text=title, bg=SURFACE, fg=TEXT, font=("Segoe UI", 10, "bold"), anchor="w")
            label.grid(row=0, column=0, sticky="ew")
            detail_label = tk.Label(row, text=detail, bg=SURFACE, fg=MUTED, font=("Segoe UI", 9), anchor="w")
            detail_label.grid(row=1, column=0, sticky="ew")
            switch = ToggleSwitch(row, variable)
            switch.grid(row=0, column=1, rowspan=2, padx=(px(12), 0))
            for target in (row, label, detail_label):
                target.bind("<Button-1>", switch._toggle)
            self.option_rows.append(row)
            self.scroll_switches.append(switch)
            self.option_labels.append(label)

        output_card = tk.Frame(self.dashboard_body, bg=SURFACE, padx=px(18), pady=px(16),
                               highlightthickness=1, highlightbackground="#25324a")
        output_card.grid(row=4, column=0, sticky="ew", pady=(px(14), px(12)))
        output_card.columnconfigure(0, weight=1)
        tk.Label(output_card, text="Folder zapisu", bg=SURFACE, fg=TEXT,
                 font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        self.output_entry = tk.Entry(output_card, textvariable=self.output_dir, state="readonly",
                                     readonlybackground=SURFACE, fg=MUTED, bd=0, highlightthickness=0,
                                     font=("Segoe UI", 9), selectbackground="#4f46e5")
        self.output_entry.grid(row=1, column=0, sticky="ew", pady=(px(8), 0))
        self.folder_button = RoundedButton(output_card, "Zmień folder", self.choose_folder, background=SURFACE)
        self.folder_button.grid(row=0, column=1, rowspan=2, padx=(px(16), 0))

        footer = tk.Frame(self.root, bg=BACKGROUND, padx=px(28), pady=px(16))
        footer.grid(row=2, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)
        self.status = tk.Label(footer, text="Gotowy do zrzutu", bg=BACKGROUND, fg="#a5b4fc",
                               justify="left", anchor="w", font=("Segoe UI", 9))
        self.status.grid(row=0, column=0, sticky="ew", padx=(0, px(16)))
        self.capture_action = RoundedButton(footer, "Zrób zrzut ekranu", self._capture_selected_mode, primary=True)
        self.capture_action.grid(row=0, column=1, sticky="ew")
        links = tk.Frame(footer, bg=BACKGROUND)
        links.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(px(12), 0))
        self.footer_buttons = []
        for text, command in (("Diagnostyka", self.show_debug_log), ("Informacje", self.show_information)):
            button = tk.Button(links, text=text, command=command, bg=BACKGROUND, fg=MUTED, activebackground=BACKGROUND,
                                activeforeground=TEXT, bd=0, padx=0, cursor="hand2", font=("Segoe UI", 9),
                                highlightbackground=BACKGROUND)
            self.footer_buttons.append(button)
            if text == "Informacje":
                self.information_button = button
        self.footer_links = links
        links.bind("<Configure>", self._layout_footer_links)

        for variable in (self.vertical_var, self.horizontal_var):
            variable.trace_add("write", lambda *args: self._update_capture_options())

        self.dashboard_canvas.bind("<Configure>", self._resize_dashboard)
        self.dashboard_body.bind("<Configure>", self._sync_dashboard_scroll)
        self.root.bind("<Configure>", self._update_responsive_layout)
        self.root.bind("<MouseWheel>", self._scroll_dashboard)
        self._select_capture_mode("screen")
        self._update_responsive_layout()

    def _layout_footer_links(self, event=None):
        available = max(1, self.footer_links.winfo_width())
        gap = round(18 * self.ui_scale)
        row_height = max(button.winfo_reqheight() for button in self.footer_buttons) + round(4 * self.ui_scale)
        x = y = 0
        for button in self.footer_buttons:
            width = button.winfo_reqwidth()
            if x and x + width > available:
                x, y = 0, y + row_height
            button.place(x=x, y=y)
            x += width + gap
        self.footer_links.configure(height=y + row_height)

    def _select_capture_mode(self, mode):
        self.selected_mode = mode
        for card in self.mode_cards:
            card.set_selected(card.key == mode)
        for switch, label in zip(self.scroll_switches, self.option_labels):
            switch.configure(state="normal" if mode == "window" else "disabled")
            label.configure(fg=TEXT if mode == "window" else MUTED)
        self.capture_action.configure(text={"screen": "Zrób zrzut ekranu", "window": "Zrób zrzut okna", "area": "Zaznacz obszar"}[mode], state="normal")
        self._update_capture_options()
        if mode == "window":
            self._show_window_picker()
        else:
            self.window_picker_card.grid_remove()

    def _update_capture_options(self):
        if self.selected_mode != "window":
            self.scroll_hint.configure(text="Dostępne w trybie „Okno aplikacji”.")
            return
        scrolling = self.vertical_var.get() or self.horizontal_var.get()
        self.scroll_hint.configure(text="Przewijanie i łączenie obrazu w jednym przejściu. Esc przerywa."
                                   if scrolling else "Zwykły zrzut widocznego okna. Włącz kierunek, aby uchwycić więcej.")
        self.capture_action.configure(text="Zrób zrzut z przewijaniem" if scrolling else "Zrób zrzut okna")

    def _capture_selected_mode(self):
        actions = {"screen": self.capture_full_screen, "window": self._capture_selected_window,
                   "area": self.capture_selected_area}
        actions[self.selected_mode]()

    def _resize_dashboard(self, event):
        self.dashboard_canvas.itemconfigure(self.dashboard_window, width=event.width)
        self._update_responsive_layout()

    def _sync_dashboard_scroll(self, event=None):
        self.dashboard_canvas.configure(scrollregion=self.dashboard_canvas.bbox("all"))
        if self.dashboard_body.winfo_reqheight() <= self.dashboard_canvas.winfo_height():
            self.dashboard_canvas.yview_moveto(0)

    def _scroll_dashboard(self, event):
        if self.dashboard_body.winfo_reqheight() > self.dashboard_canvas.winfo_height() and event.delta:
            self.dashboard_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def _update_responsive_layout(self, event=None):
        if event is not None and event.widget is not self.root:
            return
        px = lambda value: round(value * self.ui_scale)
        width = max(1, self.dashboard_canvas.winfo_width())
        compact = width < px(720)
        footer_compact = self.root.winfo_width() < px(650)
        if (compact, footer_compact) != self.dashboard_layout:
            for index in range(3):
                self.mode_grid.columnconfigure(index, weight=0, uniform="")
            for index, card in enumerate(self.mode_cards):
                card.set_compact(compact)
                card.grid(row=index if compact else 0, column=0 if compact else index, sticky="ew",
                          padx=(0, 0 if compact or index == 2 else px(12)), pady=(0, px(8) if compact else 0))
                self.mode_grid.columnconfigure(0 if compact else index, weight=1, uniform="modes")
            for index, row in enumerate(self.option_rows):
                row.grid(row=index if compact else 0, column=0 if compact else index, sticky="ew",
                         padx=(0, 0 if compact or index == 1 else px(24)), pady=(px(6), px(6)))
            self.scroll_options.columnconfigure(0, weight=1)
            self.scroll_options.columnconfigure(1, weight=0 if compact else 1)
            if footer_compact:
                self.capture_action.grid(row=0, column=0, columnspan=2, sticky="ew")
                self.status.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(px(8), 0))
                self.footer_links.grid(row=2, column=0, columnspan=2)
            else:
                self.status.grid(row=0, column=0, columnspan=1, pady=0)
                self.capture_action.grid(row=0, column=1, columnspan=1)
                self.footer_links.grid(row=1, column=0, columnspan=2)
            self.dashboard_layout = (compact, footer_compact)
        self.intro_label.configure(wraplength=max(100, self.root.winfo_width() - px(60)))
        self.capture_notice.configure(wraplength=max(100, self.root.winfo_width() - px(90)))
        self.scroll_hint.configure(wraplength=max(100, width - px(50)))
        self.window_picker_message.configure(wraplength=max(100, width - px(50)))
        table_rows = max(1, min(6, (self.dashboard_canvas.winfo_height() - px(170)) // max(1, px(36))))
        if int(self.window_table.cget("height")) != table_rows:
            self.window_table.configure(height=table_rows)
        self.status.configure(wraplength=max(100, self.root.winfo_width() - px(80 if footer_compact else 310)))
        self._sync_dashboard_scroll()
