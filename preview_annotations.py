"""Pencil and highlighter tools in the existing, zoomable screenshot preview."""
import math
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageColor, ImageTk

from image_annotations import AnnotationHistory, Stroke, stroke_mask
from ui_widgets import BACKGROUND, MUTED, RoundedButton


COLORS = {"Czerwony": "#ef4444", "Żółty": "#facc15", "Zielony": "#22c55e",
          "Niebieski": "#3b82f6", "Biały": "#ffffff", "Czarny": "#111827"}
SIZES = ("Cienka", "Średnia", "Gruba")


class PreviewAnnotations:
    def _build_annotation_controls(self, preview, tools, brush_color, brush_size):
        preview.annotation_tool = None
        preview.annotation_stroke = None
        preview.annotation_job = None
        preview.annotation_history = AnnotationHistory()
        preview.brush_settings = {"pencil": ("Czerwony", "Średnia"), "highlighter": ("Żółty", "Średnia")}
        preview.pen_btn = RoundedButton(tools, "Ołówek", lambda: self._set_annotation_tool(preview, "pencil"), compact=True)
        preview.pen_btn.pack(side="left", padx=(0, 6))
        preview.marker_btn = RoundedButton(tools, "Mazak", lambda: self._set_annotation_tool(preview, "highlighter"), compact=True)
        preview.marker_btn.pack(side="left", padx=(0, 6))
        preview.undo_btn = RoundedButton(tools, "Cofnij", lambda: self._undo_annotation(preview), compact=True)
        preview.undo_btn.pack(side="left")
        preview.undo_btn.configure(state="disabled")
        preview.color_var = tk.StringVar(preview, value="Czerwony")
        preview.brush_size_var = tk.StringVar(preview, value="Średnia")
        for brush, text, variable, values, attribute, width in (
                (brush_color, "Kolor", preview.color_var, tuple(COLORS), "color_picker", 9),
                (brush_size, "Grubość", preview.brush_size_var, SIZES, "brush_size_picker", 8)):
            tk.Label(brush, text=text, bg=BACKGROUND, fg=MUTED, font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
            picker = ttk.Combobox(brush, textvariable=variable, values=values, width=width,
                                  state="disabled", style="Annotation.TCombobox", font=("Segoe UI", 9))
            picker.pack(side="left", padx=(0, 8))
            picker.bind("<<ComboboxSelected>>", lambda event: self._annotation_settings_changed(preview))
            setattr(preview, attribute, picker)

    def _annotation_settings_changed(self, preview):
        if preview.annotation_tool:
            preview.brush_settings[preview.annotation_tool] = (preview.color_var.get(), preview.brush_size_var.get())
        preview.canvas.focus_set()

    def _update_annotation_controls(self, preview):
        active = preview.annotation_tool
        state = "disabled" if preview.crop_active else "normal"
        preview.pen_btn.configure(primary=active == "pencil", state=state)
        preview.marker_btn.configure(primary=active == "highlighter", state=state)
        preview.undo_btn.configure(state="normal" if preview.annotation_history.patches and not preview.crop_active else "disabled")
        for picker in (preview.color_picker, preview.brush_size_picker):
            picker.configure(state="readonly" if active and not preview.crop_active else "disabled")

    def _set_annotation_tool(self, preview, tool):
        if preview.crop_active:
            return "break"
        self._commit_annotation(preview)
        preview.annotation_tool = None if preview.annotation_tool == tool else tool
        if preview.annotation_tool:
            color, size = preview.brush_settings[preview.annotation_tool]
            preview.color_var.set(color)
            preview.brush_size_var.set(size)
        preview.canvas.configure(cursor="crosshair" if preview.annotation_tool else "arrow")
        preview.canvas.focus_set()
        self._update_annotation_controls(preview)
        self._refresh_preview_image(preview)
        return "break"

    def _annotation_press(self, preview, event):
        canvas = preview.canvas
        left, top, right, bottom = self._crop_image_bounds(preview)
        if not (left <= canvas.canvasx(event.x) < right and top <= canvas.canvasy(event.y) < bottom):
            return "break"
        size_index = SIZES.index(preview.brush_size_var.get())
        marker = preview.annotation_tool == "highlighter"
        width = ((12, 24, 40) if marker else (3, 6, 12))[size_index]
        point = self._crop_pointer_position(preview, event)
        preview.annotation_stroke = Stroke([point], COLORS[preview.color_var.get()], width, 85 if marker else 255)
        self._schedule_annotation_render(preview)
        return "break"

    def _annotation_drag(self, preview, event):
        stroke = preview.annotation_stroke
        if stroke is not None:
            point = self._crop_pointer_position(preview, event)
            if point != stroke.points[-1]:
                stroke.points.append(point)
            self._schedule_annotation_render(preview)
        return "break"

    def _annotation_release(self, preview, event):
        self._annotation_drag(preview, event)
        self._commit_annotation(preview)
        return "break"

    def _schedule_annotation_render(self, preview):
        if preview.annotation_job is None:
            preview.annotation_job = preview.after(16, lambda: self._draw_live_annotation(preview))

    def _draw_live_annotation(self, preview):
        if preview.annotation_job is not None:
            preview.after_cancel(preview.annotation_job)
            preview.annotation_job = None
        canvas = preview.canvas
        canvas.delete("annotation_live")
        canvas.annotation_image = None
        stroke = preview.annotation_stroke
        if stroke is None:
            return
        left, top, right, bottom = self._crop_image_bounds(preview)
        sx = (right - left) / preview.display_image.width
        sy = (bottom - top) / preview.display_image.height
        box = stroke.bounds(preview.display_image.size)
        x1 = math.floor(max(canvas.canvasx(0), left + box[0] * sx))
        y1 = math.floor(max(canvas.canvasy(0), top + box[1] * sy))
        x2 = math.ceil(min(canvas.canvasx(0) + canvas.winfo_width(), left + box[2] * sx))
        y2 = math.ceil(min(canvas.canvasy(0) + canvas.winfo_height(), top + box[3] * sy))
        if x2 <= x1 or y2 <= y1:
            return
        points = [(left + x * sx - x1, top + y * sy - y1) for x, y in stroke.points]
        mask = stroke_mask((x2 - x1, y2 - y1), points, stroke.width * (sx + sy) / 2)
        if stroke.opacity != 255:
            mask = mask.point([round(value * stroke.opacity / 255) for value in range(256)])
        overlay = Image.new("RGBA", mask.size, (*ImageColor.getrgb(stroke.color), 0))
        overlay.putalpha(mask)
        canvas.annotation_image = ImageTk.PhotoImage(overlay, master=canvas)
        canvas.create_image(x1, y1, anchor="nw", image=canvas.annotation_image, tags="annotation_live")
        overlay.close()
        mask.close()

    def _clear_annotation_overlay(self, preview):
        if preview.annotation_job is not None:
            preview.after_cancel(preview.annotation_job)
            preview.annotation_job = None
        preview.annotation_stroke = None
        preview.canvas.delete("annotation_live")
        preview.canvas.annotation_image = None

    def _commit_annotation(self, preview):
        stroke = preview.annotation_stroke
        if stroke is None:
            return
        preview.annotation_history.apply(preview.display_image, stroke)
        self._clear_annotation_overlay(preview)
        preview.canvas.render_key = None
        self._update_annotation_controls(preview)
        self._refresh_preview_image(preview)

    def _undo_annotation(self, preview):
        if preview.crop_active:
            return "break"
        if preview.annotation_stroke is not None:
            self._clear_annotation_overlay(preview)
        elif preview.annotation_history.undo(preview.display_image):
            preview.canvas.render_key = None
            self._refresh_preview_image(preview)
        self._update_annotation_controls(preview)
        return "break"

    def _preview_escape(self, preview):
        if preview.crop_active:
            return self._reject_crop(preview)
        self._clear_annotation_overlay(preview)
        if preview.annotation_tool:
            self._set_annotation_tool(preview, None)
        return "break"

    def _clear_annotation_history(self, preview):
        self._clear_annotation_overlay(preview)
        preview.annotation_history.clear()
        self._update_annotation_controls(preview)
