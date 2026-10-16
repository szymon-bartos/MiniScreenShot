"""Two-pass scrolling capture with pixel registration and overlap removal.

The first pass finds both ends and the moving viewport. The second pass lays
tiles onto measured pixel coordinates, including a true two-dimensional grid.
No keyboard shortcuts or application-specific page navigation are involved.
"""

from collections import Counter
from dataclasses import dataclass
from statistics import median
import math
import logging

from PIL import Image, ImageChops, ImageStat

logger = logging.getLogger(__name__)


class ScrollCaptureError(RuntimeError):
    pass


class CaptureCancelled(ScrollCaptureError):
    pass


def frames_equal(first, second):
    if first.size != second.size:
        return False
    diff = ImageChops.difference(first.convert("RGB"), second.convert("RGB")).convert("L")
    histogram = diff.histogram()
    # Ignore caret blinking, antialiasing noise and tiny redraws.
    if sum(histogram[18:]) / (first.width * first.height) < 0.0015:
        return True
    # Ads and clocks can keep changing after the page has reached its edge.
    # Compare several textured areas rather than waiting for an identical frame.
    a, b = first.convert("L"), second.convert("L")
    stable = textured = 0
    for row in range(4):
        for column in range(5):
            box = (round(a.width * (0.06 + column * 0.176)), round(a.height * (0.20 + row * 0.17)),
                   round(a.width * (0.06 + (column + 1) * 0.176)), round(a.height * (0.20 + (row + 1) * 0.17)))
            left, right = a.crop(box), b.crop(box)
            if max(ImageStat.Stat(left).stddev[0], ImageStat.Stat(right).stddev[0]) < 5:
                continue
            textured += 1
            stable += ImageStat.Stat(ImageChops.difference(left, right)).mean[0] < 2.0
    return textured >= 4 and stable / textured >= 0.8


def motion_bounds(first, second):
    # Ignore the outside scrollbar tracks and window edge pixels.
    margin_x = max(2, first.width // 80)
    margin_y = max(2, first.height // 160)
    box = (margin_x, margin_y, first.width - margin_x, first.height - margin_y)
    diff = ImageChops.difference(first.convert("RGB"), second.convert("RGB")).convert("L")
    mask = diff.point([0] * 18 + [255] * 238)
    mask = mask.crop(box)
    row_threshold = max(1, math.ceil(255 * max(4, mask.width * 0.004) / mask.width))
    column_threshold = max(1, math.ceil(255 * max(4, mask.height * 0.004) / mask.height))
    rows = [index for index, value in enumerate(mask.resize((1, mask.height), Image.Resampling.BOX).tobytes()) if value >= row_threshold]
    columns = [index for index, value in enumerate(mask.resize((mask.width, 1), Image.Resampling.BOX).tobytes()) if value >= column_threshold]
    return (columns[0] + box[0], rows[0] + box[1], columns[-1] + box[0] + 1, rows[-1] + box[1] + 1) if rows and columns else None


def _registration_score(first, second, distance):
    height = first.height
    margin = max(2, height // 20)
    overlap = height - distance - 2 * margin
    if overlap < 12:
        return float("inf")
    scores = []
    for column in range(3):
        x1 = round(first.width * (0.12 + column * 0.26))
        x2 = min(first.width, x1 + max(8, round(first.width * 0.18)))
        for band in range(3):
            y1 = margin + round(overlap * band / 3)
            y2 = margin + round(overlap * (band + 1) / 3)
            a = first.crop((x1, y1 + distance, x2, y2 + distance))
            b = second.crop((x1, y1, x2, y2))
            if ImageStat.Stat(a).stddev[0] > 3:
                scores.append(ImageStat.Stat(ImageChops.difference(a, b)).mean[0])
    # Fixed toolbars may intersect the first and last bands. Require agreement
    # in multiple textured patches, rather than penalizing the whole viewport.
    return median(sorted(scores)[:max(2, len(scores) // 2)]) if len(scores) >= 2 else float("inf")


def _approximate_candidates(first, second):
    """Numerical matching also works after text antialiasing or image redraws."""
    scale = max(1, math.ceil(first.height / 240))
    size = (min(96, first.width), max(1, round(first.height / scale)))
    a = first.resize(size, Image.Resampling.BOX)
    b = second.resize(size, Image.Resampling.BOX)
    ranked = sorted((_registration_score(a, b, distance), distance)
                    for distance in range(1, max(2, size[1] - max(16, size[1] // 6))))
    selected = []
    for score, distance in ranked:
        if not math.isfinite(score):
            continue
        if all(abs(distance - previous) > 2 for previous in selected):
            selected.append(distance)
        if len(selected) >= 8:
            break
    return {candidate for distance in selected
            for candidate in range(max(1, round(distance * scale) - scale * 2),
                                   min(first.height - 12, round(distance * scale) + scale * 2 + 1))}


def estimate_shift(first, second, axis, expected=None):
    """Find the positive content displacement, with pixel-level precision."""
    if first.size != second.size:
        raise ScrollCaptureError("Rozmiar przechwytywanego okna zmienił się podczas przewijania.")
    if frames_equal(first, second):
        return 0
    if axis == "x":
        first, second = first.transpose(Image.Transpose.TRANSPOSE), second.transpose(Image.Transpose.TRANSPOSE)
    first, second = first.convert("L"), second.convert("L")
    height = first.height
    patch_height = min(12, max(4, height // 30))
    candidates = Counter()
    quantize = [value // 12 * 12 for value in range(256)]
    for center in (0.25, 0.5, 0.75):
        left, right = round(first.width * (center - 0.09)), round(first.width * (center + 0.09))
        a = first.crop((left, 0, max(left + 1, right), height)).resize((48, height)).point(quantize).tobytes()
        b = second.crop((left, 0, max(left + 1, right), height)).resize((48, height)).point(quantize).tobytes()
        for fraction in (0.12, 0.22, 0.32, 0.42, 0.52, 0.62, 0.72):
            row = round(height * fraction)
            patch = b[row * 48:(row + patch_height) * 48]
            if not patch or max(patch) - min(patch) < 24:
                continue
            index = a.find(patch, (row + 1) * 48)
            matches = 0
            while index >= 0 and matches < 64:
                if index % 48 == 0:
                    distance = index // 48 - row
                    if 0 < distance < height - max(16, height // 8):
                        candidates[distance] += 1
                index = a.find(patch, index + 1)
                matches += 1
    if expected is not None:
        for distance in range(max(1, round(expected) - 2), min(height - 12, round(expected) + 3)):
            candidates[distance] += 1
    ranked = []
    for distance, votes in candidates.most_common(16):
        score = _registration_score(first, second, distance)
        ranked.append((score, -votes, distance))
    ranked.sort()
    if not ranked or ranked[0][0] > 2.5:
        tried = {item[2] for item in ranked}
        for distance in _approximate_candidates(first, second) - tried:
            ranked.append((_registration_score(first, second, distance), 0, distance))
        ranked.sort()
    if not ranked or ranked[0][0] > 20:
        raise ScrollCaptureError("Nie można dopasować przewijanej zawartości. Zatrzymano zrzut, aby nie powielić fragmentów obrazu.")
    best = ranked[0]
    equivalent = [item for item in ranked if item[0] <= best[0] + 0.15 and abs(item[2] - best[2]) > 2]
    if equivalent and expected is not None:
        best = min([best, *equivalent], key=lambda item: abs(item[2] - expected))
    return best[2]


@dataclass
class AxisBounds:
    offsets: list
    units: int


class ScrollingCapture:
    def __init__(self, driver, vertical=True, horizontal=False, progress=None, max_steps=240, max_pixels=60_000_000):
        self.driver = driver
        self.axes = (["x"] if horizontal else []) + (["y"] if vertical else [])
        self.progress = progress or (lambda message: None)
        self.max_steps = max_steps
        self.max_pixels = max_pixels
        self.moving = None
        self.viewport = None
        self.approximate = False

    def _match_after_retry(self, previous, current, axis, expected):
        try:
            return estimate_shift(previous, current, axis, expected)
        except ScrollCaptureError:
            if expected is None:
                raise
            a, b = previous.convert("L"), current.convert("L")
            if axis == "x":
                a, b = a.transpose(Image.Transpose.TRANSPOSE), b.transpose(Image.Transpose.TRANSPOSE)
            if _registration_score(a, b, round(expected)) > 40:
                raise
            # A redraw obscured the alignment, but the last wheel displacement
            # still agrees reasonably. Add two pixels of overlap, not a gap.
            self.approximate = True
            logger.warning("Approximate scroll alignment: axis=%s, displacement=%s", axis, expected)
            self.progress("Drobne różnice obrazu — łączę z niewielką zakładką…")
            return min(a.height - 12, round(expected) + 2)

    def _union_motion(self, first, second, axis):
        box = motion_bounds(first, second)
        if box:
            left, top, right, bottom = box
            # Browser documents often reach the last client pixel. Extend a
            # moving edge through the safety margin, but not across a fixed
            # perpendicular scrollbar or toolbar.
            margin_y, margin_x = max(2, first.height // 160), max(2, first.width // 80)
            if axis == "y" and bottom >= first.height - margin_y:
                strip = (left, bottom, right, first.height)
                if ImageStat.Stat(ImageChops.difference(first.crop(strip), second.crop(strip))).mean[0] > 3:
                    bottom = first.height
            if axis == "x" and right >= first.width - margin_x:
                strip = (right, top, first.width, bottom)
                if ImageStat.Stat(ImageChops.difference(first.crop(strip), second.crop(strip))).mean[0] > 3:
                    right = first.width
            box = (left, top, right, bottom)
            self.moving = box if self.moving is None else (
                min(self.moving[0], box[0]), min(self.moving[1], box[1]),
                max(self.moving[2], box[2]), max(self.moving[3], box[3]))

    def _seek_start(self, axis):
        previous = self.driver.snapshot()
        unchanged = 0
        for _ in range(self.max_steps):
            if self.driver.at_edge(axis, -1) is True:
                return
            self.driver.scroll(axis, -1, 12)
            current = self.driver.snapshot()
            unchanged = unchanged + 1 if frames_equal(previous, current) else 0
            if unchanged >= 2:
                return
            previous = current
        raise ScrollCaptureError("Nie znaleziono początku przewijanej zawartości. Zrzut został zatrzymany.")

    def _measure_axis(self, axis, initial):
        dimension = initial.width if axis == "x" else initial.height
        units = max(1, min(3, dimension // 240))
        offsets = [0]
        previous = initial
        expected = None
        unchanged = 0
        for index in range(self.max_steps):
            if self.driver.at_edge(axis, 1) is True:
                break
            self.driver.scroll(axis, 1, units)
            current = self.driver.snapshot()
            if frames_equal(previous, current):
                if self.driver.at_edge(axis, 1) is not None:
                    raise ScrollCaptureError("Przewijanie nie daje rozpoznawalnego przesunięcia obrazu. Zatrzymano zrzut, aby nie pominąć ani nie powielić treści.")
                unchanged += 1
                if unchanged >= 2:
                    break
                continue
            try:
                distance = estimate_shift(previous, current, axis, expected)
            except ScrollCaptureError:
                # A lazy-loaded image or the last smooth-scroll animation can
                # change a single frame. Let the driver settle and try again.
                self.progress("Czekam na wyrenderowanie zawartości…")
                current = self.driver.snapshot()
                distance = self._match_after_retry(previous, current, axis, expected)
            if not distance:
                raise ScrollCaptureError("Nie można ustalić przesunięcia zawartości.")
            self._union_motion(previous, current, axis)
            offsets.append(offsets[-1] + distance)
            expected = distance if expected is None else max(expected, distance)
            previous = current
            unchanged = 0
            self.progress(f"Pomiar granic: {'pion' if axis == 'y' else 'poziom'}, fragment {index + 1}…")
        else:
            raise ScrollCaptureError("Nie znaleziono końca zawartości. Strona może przewijać się bez końca.")
        self._seek_start(axis)
        return AxisBounds(offsets, units)

    def _tile(self):
        return self.driver.snapshot().crop(self.viewport)

    def _next_tile(self, previous, axis, units, expected):
        if self.driver.at_edge(axis, 1) is True:
            return None, 0
        self.driver.scroll(axis, 1, units)
        current = self._tile()
        if frames_equal(previous, current):
            if self.driver.at_edge(axis, 1) is False:
                raise ScrollCaptureError("Okno nie pokazuje nowej zawartości mimo przewijania. Sprawdź, czy nad stroną nie ma komunikatu.")
            # Confirm an unknown end once more; wheel events can be coalesced.
            if self.driver.at_edge(axis, 1) is None:
                self.driver.scroll(axis, 1, units)
                current = self._tile()
                if not frames_equal(previous, current):
                    return current, estimate_shift(previous, current, axis, expected)
            return None, 0
        try:
            distance = estimate_shift(previous, current, axis, expected)
        except ScrollCaptureError:
            self.progress("Dopasowuję fragment po odświeżeniu strony…")
            current = self._tile()
            distance = self._match_after_retry(previous, current, axis, expected)
        return current, distance

    def capture(self):
        self.progress("Ustalam początek przewijanej zawartości…")
        for axis in self.axes:
            self._seek_start(axis)
        initial = self.driver.snapshot()
        bounds = {}
        for axis in self.axes:
            self.progress("Szukam lewej i prawej granicy…" if axis == "x" else "Szukam górnej i dolnej granicy…")
            bounds[axis] = self._measure_axis(axis, initial)
            initial = self.driver.snapshot()
        if self.moving is None:
            return initial
        self.viewport = self.moving
        width, height = self.viewport[2] - self.viewport[0], self.viewport[3] - self.viewport[1]
        xs = bounds.get("x", AxisBounds([0], 1))
        ys = bounds.get("y", AxisBounds([0], 1))
        result_size = (width + xs.offsets[-1], height + ys.offsets[-1])
        if result_size[0] * result_size[1] > self.max_pixels:
            raise ScrollCaptureError("Zawartość jest zbyt duża na jeden obraz. Zmniejsz jej powiększenie i spróbuj ponownie.")
        result = Image.new("RGB", result_size, "white")
        self.progress("Granice ustalone. Przechwytuję i łączę zawartość…")
        first_tile = self._tile()
        y = actual_width = actual_height = 0
        dy = height
        expected_y = ys.offsets[1] if len(ys.offsets) > 1 else None
        expected_x = xs.offsets[1] if len(xs.offsets) > 1 else None
        fragments = 0
        for row in range(self.max_steps):
            previous_tile = first_tile
            crop_top = max(0, height - dy)
            x = 0
            dx = width
            tile = first_tile
            for column in range(self.max_steps):
                needed = (max(result.width, x + width), max(result.height, y + height))
                if needed[0] * needed[1] > self.max_pixels:
                    raise ScrollCaptureError("Zawartość jest zbyt duża na jeden obraz.")
                if needed != result.size:
                    expanded = Image.new("RGB", needed, "white")
                    expanded.paste(result, (0, 0))
                    result = expanded
                crop_left = max(0, width - dx)
                result.paste(tile.crop((crop_left, crop_top, width, height)), (x + crop_left, y + crop_top))
                actual_width, actual_height = max(actual_width, x + width), y + height
                fragments += 1
                self.progress(f"Łączę fragment {fragments} · wiersz {row + 1}…")
                previous_tile = tile
                if "x" not in self.axes:
                    break
                hint_x = min(expected_x, xs.offsets[-1] - x) if expected_x and x < xs.offsets[-1] else expected_x
                tile, dx = self._next_tile(previous_tile, "x", xs.units, hint_x)
                if tile is None:
                    break
                x += dx
                expected_x = max(expected_x or 0, dx)
            else:
                raise ScrollCaptureError("Nie znaleziono prawej granicy zawartości.")
            if "x" in self.axes and x:
                self._seek_start("x")
            if "y" not in self.axes:
                break
            hint_y = min(expected_y, ys.offsets[-1] - y) if expected_y and y < ys.offsets[-1] else expected_y
            first_tile, dy = self._next_tile(first_tile, "y", ys.units, hint_y)
            if first_tile is None:
                break
            y += dy
            expected_y = max(expected_y or 0, dy)
        else:
            raise ScrollCaptureError("Nie znaleziono dolnej granicy zawartości.")
        # Leave the document at its start; the preview is shown only afterwards.
        for axis in self.axes:
            self._seek_start(axis)
        return result.crop((0, 0, actual_width, actual_height))
