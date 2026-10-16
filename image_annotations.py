"""Raster annotations with transparent strokes and bounded patch undo history."""
from dataclasses import dataclass
import math

from PIL import Image, ImageColor, ImageDraw


def stroke_mask(size, points, width):
    mask = Image.new("L", size)
    drawing = ImageDraw.Draw(mask)
    width = max(1, round(width))
    if len(points) > 1:
        drawing.line(points, fill=255, width=width, joint="curve")
    radius = (width - 1) / 2
    for x, y in (points[0], points[-1]):
        drawing.ellipse((x - radius, y - radius, x + radius, y + radius), fill=255)
    return mask


def paste_patch(image, patch, box):
    backing = getattr(image, "_capture_backing", None)
    if backing is not None and image.readonly:
        # Pillow would copy the entire mapped screenshot on its first paste.
        # Write only the changed rows through its existing RGBA backing instead.
        raw = patch.convert("RGBA").tobytes()
        stride = patch.width * 4
        for row in range(patch.height):
            offset = ((box[1] + row) * image.width + box[0]) * 4
            backing.buffer[offset:offset + stride] = raw[row * stride:(row + 1) * stride]
    else:
        image.paste(patch, box)


@dataclass
class Stroke:
    points: list
    color: str
    width: int
    opacity: int = 255

    def bounds(self, size):
        radius = self.width / 2 + 2
        return (max(0, math.floor(min(x for x, y in self.points) - radius)),
                max(0, math.floor(min(y for x, y in self.points) - radius)),
                min(size[0], math.ceil(max(x for x, y in self.points) + radius + 1)),
                min(size[1], math.ceil(max(y for x, y in self.points) + radius + 1)))


class AnnotationHistory:
    def __init__(self, max_bytes=32 * 1024**2, max_steps=30):
        self.max_bytes, self.max_steps = max_bytes, max_steps
        self.patches = []
        self.bytes = 0

    def apply(self, image, stroke):
        box = stroke.bounds(image.size)
        if box[2] <= box[0] or box[3] <= box[1]:
            return False
        before = image.crop(box)
        points = [(x - box[0], y - box[1]) for x, y in stroke.points]
        mask = stroke_mask(before.size, points, stroke.width)
        if stroke.opacity != 255:
            # One uniform mask per gesture: retracing a highlighter stroke
            # cannot darken its intersections repeatedly.
            mask = mask.point([round(value * stroke.opacity / 255) for value in range(256)])
        after = before.copy()
        color = ImageColor.getrgb(stroke.color)
        after.paste((*color, 255) if image.mode == "RGBA" else color, (0, 0), mask)
        try:
            paste_patch(image, after, box)
        except Exception:
            before.close()
            raise
        finally:
            after.close()
            mask.close()
        cost = before.width * before.height * len(before.getbands())
        self.patches.append((box, before, cost))
        self.bytes += cost
        # Keep the last action undoable even when its patch alone exceeds the
        # budget, without retaining other large screenshot copies alongside it.
        while len(self.patches) > 1 and (self.bytes > self.max_bytes or len(self.patches) > self.max_steps):
            _, previous, previous_cost = self.patches.pop(0)
            previous.close()
            self.bytes -= previous_cost
        return True

    def undo(self, image):
        if not self.patches:
            return False
        box, patch, cost = self.patches.pop()
        try:
            paste_patch(image, patch, box)
        finally:
            self.bytes -= cost
            patch.close()
        return True

    def clear(self):
        for _, patch, _ in self.patches:
            patch.close()
        self.patches.clear()
        self.bytes = 0
