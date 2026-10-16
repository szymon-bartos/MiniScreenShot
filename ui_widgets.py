"""Small, keyboard-accessible canvas controls for the capture dashboard."""

import tkinter as tk
from tkinter import font as tkfont

BACKGROUND = "#0b1120"
SURFACE = "#111c30"
TEXT = "#edf2ff"
MUTED = "#94a3b8"
ACCENT = "#818cf8"


def rounded_rectangle(canvas, x1, y1, x2, y2, radius=12, **options):
    radius = min(radius, (x2 - x1) / 2, (y2 - y1) / 2)
    points = [x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
              x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
              x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1]
    return canvas.create_polygon(points, smooth=True, splinesteps=24, **options)


class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command, primary=False, background=BACKGROUND, compact=False):
        self.text = text
        self.command = command
        self.primary = primary
        self.compact = compact
        self.scale = parent.winfo_fpixels("1i") / 96
        self.label_font = tkfont.Font(family="Segoe UI", size=10, weight="bold")
        self.hovered = False
        self.focused = False
        self.disabled = False
        super().__init__(parent, bg=background, highlightthickness=0, bd=0,
                         height=round((36 if compact else 44) * self.scale), takefocus=True, cursor="hand2")
        self._measure()
        self.bind("<Configure>", lambda event: self._draw())
        self.bind("<Enter>", lambda event: self._hover(True))
        self.bind("<Leave>", lambda event: self._hover(False))
        self.bind("<FocusIn>", lambda event: self._focus(True))
        self.bind("<FocusOut>", lambda event: self._focus(False))
        self.bind("<Button-1>", lambda event: self.focus_set())
        self.bind("<ButtonRelease-1>", self._click_release)
        self.bind("<space>", self._keyboard_invoke)
        self.bind("<Return>", self._keyboard_invoke)

    def _measure(self):
        super().configure(width=self.label_font.measure(self.text) + round((24 if self.compact else 36) * self.scale))

    def configure(self, cnf=None, **options):
        if "primary" in options:
            self.primary = options.pop("primary")
        if "text" in options:
            self.text = options.pop("text")
            self._measure()
        if "state" in options:
            self.disabled = options.pop("state") == "disabled"
            super().configure(takefocus=not self.disabled, cursor="arrow" if self.disabled else "hand2")
        result = super().configure(cnf, **options)
        self._draw()
        return result

    config = configure

    def cget(self, key):
        if key == "state":
            return "disabled" if self.disabled else "normal"
        if key == "text":
            return self.text
        return super().cget(key)

    def instate(self, statespec):
        states = {"disabled": self.disabled, "focus": self.focused, "active": self.hovered}
        return all(states.get(state.lstrip("!"), False) == (not state.startswith("!")) for state in statespec)

    def _hover(self, active):
        self.hovered = active
        self._draw()

    def _focus(self, active):
        self.focused = active
        self._draw()

    def _draw(self):
        self.delete("all")
        fill = "#6366f1" if self.primary else "#1c2a42"
        if self.hovered:
            fill = "#7477f5" if self.primary else "#293a56"
        if self.disabled:
            fill = "#1c263a"
        rounded_rectangle(self, 2, 2, max(3, self.winfo_width() - 2), max(3, self.winfo_height() - 2),
                          radius=10 * self.scale, fill=fill,
                          outline=ACCENT if self.focused else fill, width=2)
        self.create_text(self.winfo_width() / 2, self.winfo_height() / 2, text=self.text,
                         font=self.label_font, fill=MUTED if self.disabled else TEXT)

    def invoke(self):
        if not self.disabled:
            return self.command()

    def _click_release(self, event):
        if 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height():
            self.invoke()

    def _keyboard_invoke(self, event):
        self.invoke()
        return "break"


class RangeSlider(tk.Canvas):
    def __init__(self, parent, variable, command, minimum=1, maximum=300):
        self.variable, self.command = variable, command
        self.minimum, self.maximum = minimum, maximum
        self.scale = parent.winfo_fpixels("1i") / 96
        super().__init__(parent, bg=BACKGROUND, bd=0, highlightthickness=0,
                         width=round(90 * self.scale), height=round(30 * self.scale), takefocus=True, cursor="hand2")
        self.trace = variable.trace_add("write", lambda *args: self._draw())
        self.bind("<Configure>", lambda event: self._draw())
        self.bind("<Button-1>", self._choose)
        self.bind("<B1-Motion>", self._choose)
        self.bind("<Left>", lambda event: self._step(-10))
        self.bind("<Right>", lambda event: self._step(10))
        self.bind("<FocusIn>", lambda event: self._draw())
        self.bind("<FocusOut>", lambda event: self._draw())
        self.bind("<Destroy>", self._cleanup)

    def _cleanup(self, event):
        if event.widget is self:
            self.variable.trace_remove("write", self.trace)

    def _step(self, amount):
        value = max(self.minimum, min(self.maximum, self.variable.get() + amount))
        self.variable.set(value)
        self.command(value)
        return "break"

    def _choose(self, event):
        self.focus_set()
        padding = 9 * self.scale
        fraction = max(0, min(1, (event.x - padding) / max(1, self.winfo_width() - 2 * padding)))
        value = self.minimum + fraction * (self.maximum - self.minimum)
        self.variable.set(value)
        self.command(value)
        return "break"

    def _draw(self):
        self.delete("all")
        padding, middle = 9 * self.scale, self.winfo_height() / 2
        end = max(padding + 1, self.winfo_width() - padding)
        fraction = max(0, min(1, (self.variable.get() - self.minimum) / (self.maximum - self.minimum)))
        x = padding + fraction * (end - padding)
        self.create_line(padding, middle, end, middle, fill="#293a56", width=max(2, round(4 * self.scale)), capstyle="round")
        if x > padding:
            self.create_line(padding, middle, x, middle, fill="#6366f1", width=max(2, round(4 * self.scale)), capstyle="round")
        radius = 6 * self.scale
        self.create_oval(x - radius, middle - radius, x + radius, middle + radius, fill="#a5b4fc", outline="#818cf8", width=2)


class ToggleSwitch(tk.Canvas):
    def __init__(self, parent, variable):
        self.variable = variable
        self.scale = parent.winfo_fpixels("1i") / 96
        self.disabled = False
        self.focused = False
        super().__init__(parent, bg=SURFACE, highlightthickness=0, bd=0,
                         width=round(52 * self.scale), height=round(32 * self.scale),
                         takefocus=True, cursor="hand2")
        self.trace = variable.trace_add("write", lambda *args: self._draw())
        self.bind("<Configure>", lambda event: self._draw())
        self.bind("<Button-1>", self._toggle)
        self.bind("<space>", self._toggle)
        self.bind("<Return>", self._toggle)
        self.bind("<FocusIn>", lambda event: self._focus(True))
        self.bind("<FocusOut>", lambda event: self._focus(False))
        self.bind("<Destroy>", self._remove_trace)

    def _remove_trace(self, event):
        if event.widget is self:
            self.variable.trace_remove("write", self.trace)

    def configure(self, cnf=None, **options):
        if "state" in options:
            self.disabled = options.pop("state") == "disabled"
            super().configure(takefocus=not self.disabled, cursor="arrow" if self.disabled else "hand2")
        result = super().configure(cnf, **options)
        self._draw()
        return result

    config = configure

    def _focus(self, active):
        self.focused = active
        self._draw()

    def _toggle(self, event=None):
        if not self.disabled:
            self.focus_set()
            self.variable.set(not self.variable.get())
        return "break"

    def _draw(self):
        self.delete("all")
        unit = self.scale
        fill = "#6366f1" if self.variable.get() else "#36435b"
        if self.disabled:
            fill = "#263248"
        rounded_rectangle(self, 3 * unit, 4 * unit, 49 * unit, 28 * unit,
                          radius=12 * unit, fill=fill, outline=ACCENT if self.focused else fill, width=2)
        left = (28 if self.variable.get() else 6) * unit
        self.create_oval(left, 7 * unit, left + 18 * unit, 25 * unit,
                         fill="#64748b" if self.disabled else "#ffffff", outline="")


class ModeCard(tk.Canvas):
    def __init__(self, parent, key, title, subtitle, command):
        self.key, self.title, self.subtitle, self.command = key, title, subtitle, command
        self.scale = parent.winfo_fpixels("1i") / 96
        self.selected = False
        self.compact = False
        self.hovered = False
        self.focused = False
        super().__init__(parent, bg=BACKGROUND, bd=0, highlightthickness=0,
                         width=round(220 * self.scale), height=round(142 * self.scale),
                         takefocus=True, cursor="hand2")
        self.bind("<Configure>", lambda event: self._draw())
        self.bind("<Button-1>", self._select)
        self.bind("<space>", self._select)
        self.bind("<Return>", self._select)
        self.bind("<Enter>", lambda event: self._hover(True))
        self.bind("<Leave>", lambda event: self._hover(False))
        self.bind("<FocusIn>", lambda event: self._focus(True))
        self.bind("<FocusOut>", lambda event: self._focus(False))

    def set_compact(self, compact):
        if self.compact != compact:
            self.compact = compact
            self.configure(height=round((88 if compact else 142) * self.scale))
            self._draw()

    def set_selected(self, selected):
        self.selected = selected
        self._draw()

    def _select(self, event=None):
        self.focus_set()
        self.command(self.key)
        return "break"

    def _hover(self, active):
        self.hovered = active
        self._draw()

    def _focus(self, active):
        self.focused = active
        self._draw()

    def _draw(self):
        self.delete("all")
        unit = self.scale
        width, height = self.winfo_width(), self.winfo_height()
        fill = "#1b2547" if self.selected else ("#172640" if self.hovered else SURFACE)
        edge = ACCENT if self.selected or self.focused else "#25324a"
        rounded_rectangle(self, 2, 2, max(3, width - 2), max(3, height - 2),
                          radius=14 * unit, fill=fill, outline=edge, width=2)
        icon_x, icon_y = 22 * unit, (29 if self.compact else 23) * unit
        color = "#a5b4fc" if self.selected else MUTED
        if self.key == "screen":
            self.create_rectangle(icon_x, icon_y, icon_x + 28 * unit, icon_y + 19 * unit, outline=color, width=2)
            self.create_line(icon_x + 14 * unit, icon_y + 19 * unit, icon_x + 14 * unit, icon_y + 25 * unit, fill=color, width=2)
            self.create_line(icon_x + 7 * unit, icon_y + 25 * unit, icon_x + 21 * unit, icon_y + 25 * unit, fill=color, width=2)
        elif self.key == "window":
            self.create_rectangle(icon_x, icon_y, icon_x + 28 * unit, icon_y + 24 * unit, outline=color, width=2)
            self.create_line(icon_x, icon_y + 7 * unit, icon_x + 28 * unit, icon_y + 7 * unit, fill=color, width=2)
        else:
            for dx, dy, sign_x, sign_y in ((0, 0, 1, 1), (28, 0, -1, 1), (0, 24, 1, -1), (28, 24, -1, -1)):
                x, y = icon_x + dx * unit, icon_y + dy * unit
                self.create_line(x, y + sign_y * 8 * unit, x, y, x + sign_x * 8 * unit, y, fill=color, width=2)
        text_x, text_y = (70 * unit, 31 * unit) if self.compact else (22 * unit, 78 * unit)
        self.create_text(text_x, text_y, text=self.title, anchor="w", fill=TEXT, font=("Segoe UI", 11, "bold"))
        self.create_text(text_x, text_y + 25 * unit, text=self.subtitle, anchor="w", fill=MUTED, font=("Segoe UI", 9))
        radio_x = width - 29 * unit
        self.create_oval(radio_x - 7 * unit, 22 * unit, radio_x + 7 * unit, 36 * unit, outline=edge, width=2)
        if self.selected:
            self.create_oval(radio_x - 3 * unit, 26 * unit, radio_x + 3 * unit, 32 * unit, fill=ACCENT, outline="")
