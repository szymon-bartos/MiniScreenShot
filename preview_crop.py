"""Non-destructive crop selection inside the existing screenshot canvas."""


class InlineCropEditor:
    def _toggle_crop_mode(self, preview, image=None):
        if preview.crop_active:
            return self._reject_crop(preview)
        self._set_annotation_tool(preview, None)
        preview.crop_active = True
        preview.pending_crop = None
        preview.crop_drag_mode = None
        preview.crop_btn.grid_remove()
        preview.accept_btn.grid()
        preview.accept_btn.configure(state="disabled")
        preview.reject_btn.grid()
        preview.save_btn.configure(state="disabled")
        preview.copy_btn.configure(state="disabled")
        preview.canvas.configure(cursor="crosshair")
        preview.canvas.focus_set()
        self._update_annotation_controls(preview)
        self._schedule_preview_layout(preview)
        self._refresh_preview_image(preview)

    def _crop_image_bounds(self, preview):
        canvas = preview.canvas
        if hasattr(canvas, "logical_image_bounds"):
            return canvas.logical_image_bounds
        left, top = canvas.coords("image")
        return left, top, left + canvas.image.width(), top + canvas.image.height()

    def _crop_pointer_position(self, preview, event):
        canvas = preview.canvas
        left, top, right, bottom = self._crop_image_bounds(preview)
        x = (canvas.canvasx(event.x) - left) * preview.display_image.width / (right - left)
        y = (canvas.canvasy(event.y) - top) * preview.display_image.height / (bottom - top)
        return (max(0, min(preview.display_image.width, x)),
                max(0, min(preview.display_image.height, y)))

    def _crop_canvas_box(self, preview):
        left, top, right, bottom = self._crop_image_bounds(preview)
        sx = (right - left) / preview.display_image.width
        sy = (bottom - top) / preview.display_image.height
        x1, y1, x2, y2 = preview.pending_crop
        return left + x1 * sx, top + y1 * sy, left + x2 * sx, top + y2 * sy

    def _crop_handles(self, preview):
        x1, y1, x2, y2 = self._crop_canvas_box(preview)
        return {"nw": (x1, y1), "ne": (x2, y1), "sw": (x1, y2), "se": (x2, y2),
                "n": ((x1 + x2) / 2, y1), "s": ((x1 + x2) / 2, y2),
                "w": (x1, (y1 + y2) / 2), "e": (x2, (y1 + y2) / 2)}

    def _crop_hit_test(self, preview, event):
        if not preview.pending_crop:
            return None
        canvas = preview.canvas
        x, y = canvas.canvasx(event.x), canvas.canvasy(event.y)
        for handle, (hx, hy) in self._crop_handles(preview).items():
            if abs(x - hx) <= 10 and abs(y - hy) <= 10:
                return handle
        x1, y1, x2, y2 = self._crop_canvas_box(preview)
        return "move" if x1 < x < x2 and y1 < y < y2 else None

    def _preview_crop_press(self, preview, event):
        if not preview.crop_active:
            return
        hit = self._crop_hit_test(preview, event)
        canvas = preview.canvas
        left, top, right, bottom = self._crop_image_bounds(preview)
        x, y = canvas.canvasx(event.x), canvas.canvasy(event.y)
        if hit is None and not (left <= x <= right and top <= y <= bottom):
            return
        canvas.focus_set()
        preview.crop_drag_start = self._crop_pointer_position(preview, event)
        preview.crop_drag_anchor = preview.pending_crop
        preview.crop_drag_mode = hit or "new"
        if hit is None:
            preview.pending_crop = None
            preview.accept_btn.configure(state="disabled")
            self._draw_crop_selection(preview)
        return "break"

    def _preview_crop_drag(self, preview, event):
        mode = getattr(preview, "crop_drag_mode", None)
        if not preview.crop_active or mode is None:
            return
        x, y = self._crop_pointer_position(preview, event)
        start_x, start_y = preview.crop_drag_start
        dx, dy = x - start_x, y - start_y
        width, height = preview.display_image.size
        if mode == "new":
            box = (min(start_x, x), min(start_y, y), max(start_x, x), max(start_y, y))
            preview.pending_crop = box if box[2] - box[0] >= 1 and box[3] - box[1] >= 1 else None
        else:
            left, top, right, bottom = preview.crop_drag_anchor
            if mode == "move":
                moved_x = max(0, min(width - (right - left), left + dx))
                moved_y = max(0, min(height - (bottom - top), top + dy))
                preview.pending_crop = (moved_x, moved_y, moved_x + right - left, moved_y + bottom - top)
            else:
                if "w" in mode:
                    left = max(0, min(left + dx, right - 1))
                if "e" in mode:
                    right = min(width, max(right + dx, left + 1))
                if "n" in mode:
                    top = max(0, min(top + dy, bottom - 1))
                if "s" in mode:
                    bottom = min(height, max(bottom + dy, top + 1))
                preview.pending_crop = (left, top, right, bottom)
        preview.accept_btn.configure(state="normal" if preview.pending_crop else "disabled")
        self._draw_crop_selection(preview)
        self._update_crop_hint(preview)
        return "break"

    def _preview_crop_release(self, preview, event):
        if not preview.crop_active or getattr(preview, "crop_drag_mode", None) is None:
            return
        self._preview_crop_drag(preview, event)
        preview.crop_drag_mode = None
        self._update_crop_hint(preview)
        return "break"

    def _preview_crop_hover(self, preview, event):
        if preview.crop_active and getattr(preview, "crop_drag_mode", None) is None:
            preview.canvas.configure(cursor="fleur" if self._crop_hit_test(preview, event) == "move" else "crosshair")

    def _update_crop_hint(self, preview):
        if preview.pending_crop:
            left, top, right, bottom = self._normalize_crop_box(preview.pending_crop, *preview.display_image.size)
            hint = f"{right - left} × {bottom - top} px\nEnter: przytnij  ·  Esc: anuluj"
        else:
            hint = "Zaznacz obszar na obrazie.\nEsc: anuluj"
        preview.info_label.configure(text=hint)

    def _draw_crop_selection(self, preview):
        canvas = preview.canvas
        canvas.delete("crop_overlay")
        if not preview.crop_active or not preview.pending_crop:
            return
        left, top, right, bottom = self._crop_image_bounds(preview)
        x1, y1, x2, y2 = self._crop_canvas_box(preview)
        for bounds in ((left, top, right, y1), (left, y2, right, bottom),
                       (left, y1, x1, y2), (x2, y1, right, y2)):
            canvas.create_rectangle(*bounds, fill="#020617", stipple="gray50", outline="", tags="crop_overlay")
        canvas.create_rectangle(x1, y1, x2, y2, outline="#a5b4fc", width=2, tags="crop_overlay")
        for x, y in self._crop_handles(preview).values():
            canvas.create_rectangle(x - 5, y - 5, x + 5, y + 5, fill="#eef2ff", outline="#6366f1", width=2, tags="crop_overlay")
        canvas.tag_raise("crop_overlay")

    def _finish_preview_crop(self, preview):
        preview.crop_active = False
        preview.pending_crop = None
        preview.crop_drag_mode = None
        preview.canvas.delete("crop_overlay")
        preview.canvas.configure(cursor="arrow")
        preview.accept_btn.grid_remove()
        preview.reject_btn.grid_remove()
        preview.crop_btn.grid()
        preview.save_btn.configure(state="normal")
        preview.copy_btn.configure(state="normal")
        self._update_annotation_controls(preview)
        self._schedule_preview_layout(preview)

    def _accept_crop(self, preview):
        if not preview.pending_crop:
            return "break"
        image = preview.display_image
        box = self._normalize_crop_box(preview.pending_crop, *image.size)
        preview.display_image = image.crop(box)
        if getattr(self, "_latest_preview_image", None) is image:
            self._latest_preview_image = preview.display_image
        self._clear_annotation_history(preview)
        self._finish_preview_crop(preview)
        self._refresh_preview_image(preview)
        self.set_status("Przycięcie zapisane w podglądzie.")
        return "break"

    def _reject_crop(self, preview):
        self._finish_preview_crop(preview)
        self._refresh_preview_image(preview)
        self.set_status("Przycinanie anulowane.")
        return "break"
