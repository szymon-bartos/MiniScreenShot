"""Capture and register each frame in one scroll pass; spool large images to disk."""

from collections import Counter
from statistics import median
import math
import logging

from PIL import Image, ImageChops, ImageStat

logger = logging.getLogger(__name__)


class ScrollCaptureError(RuntimeError):
    pass


class CaptureCancelled(ScrollCaptureError):
    pass


def frames_equal(first, second, stable_ratio=0.8):
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
    return textured >= 4 and stable / textured >= stable_ratio


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


def _central_scroll_region(first, second, axis):
    """A narrow panel under the wheel can move inside a mostly fixed CRM UI."""
    box = motion_bounds(first, second)
    if box is None:
        return None
    left, top, right, bottom = box
    if not (left <= first.width // 2 < right and top <= first.height // 2 < bottom):
        return None
    extent, across = ((bottom - top, right - left) if axis == "y" else (right - left, bottom - top))
    dimension = first.height if axis == "y" else first.width
    return box if extent >= max(48, dimension * 0.35) and across >= 24 else None


def scroll_frames_equal(first, second, axis, stable_ratio=0.8):
    if not frames_equal(first, second, stable_ratio):
        return False
    box = _central_scroll_region(first, second, axis)
    return box is None or frames_equal(first.crop(box), second.crop(box), stable_ratio)


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
            if y2 - y1 > 48:
                y1 += (y2 - y1 - 48) // 2
                y2 = y1 + 48
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
        box = _central_scroll_region(first, second, axis)
        if box is None:
            return 0
        first, second = first.crop(box), second.crop(box)
        if frames_equal(first, second):
            return 0
    if axis == "x":
        first, second = first.transpose(Image.Transpose.TRANSPOSE), second.transpose(Image.Transpose.TRANSPOSE)
    first, second = first.convert("L"), second.convert("L")
    # Preserve every pixel in the scrolling direction; bound the cost across
    # the perpendicular direction even on a 4K desktop.
    if first.width > 320:
        first = first.resize((320, first.height), Image.Resampling.BILINEAR)
        second = second.resize((320, second.height), Image.Resampling.BILINEAR)
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
    zero_score = _registration_score(first, second, 0)
    if zero_score <= 2.5 and (not ranked or ranked[0][0] > 20):
        return 0
    if not ranked or ranked[0][0] > 20:
        raise ScrollCaptureError("Nie można dopasować przewijanej zawartości. Zatrzymano zrzut, aby nie powielić fragmentów obrazu.")
    best = ranked[0]
    equivalent = [item for item in ranked if item[0] <= best[0] + 0.15 and abs(item[2] - best[2]) > 2]
    if zero_score <= best[0] + 0.15:
        equivalent.append((zero_score, 0, 0))
    if equivalent:
        # Repeated listing cards can agree in several patches at multiple
        # offsets. Use the whole overlap to retain unique text/photo evidence;
        # a predicted wheel distance alone can duplicate the last short step.
        evidence = []
        margin = max(2, height // 20)
        for item in [best, *equivalent]:
            distance = item[2]
            a = first.crop((0, margin + distance, first.width, height - margin))
            b = second.crop((0, margin, first.width, height - margin - distance))
            score = ImageStat.Stat(ImageChops.difference(a, b)).mean[0]
            evidence.append((score, item))
        lowest = min(score for score, _ in evidence)
        plausible = [item for score, item in evidence if score <= lowest + 0.1]
        zero = next((item for item in plausible if item[2] == 0), None)
        best = zero if zero is not None else (min(plausible, key=lambda item: abs(item[2] - expected)) if expected is not None else min(plausible))
    return best[2]


class ScrollingCapture:
    def __init__(self, driver, vertical=True, horizontal=False, progress=None, max_steps=240, max_pixels=24_000_000,
                 max_output_pixels=24_000_000, include_window_frame=False):
        self.driver = driver
        self.axes = (["x"] if horizontal else []) + (["y"] if vertical else [])
        self.progress = progress or (lambda message: None)
        self.max_steps = max_steps
        # This is a RAM threshold, not a limit on the final screenshot size.
        self.max_pixels = max_pixels
        self.max_output_pixels = max_output_pixels
        self.include_window_frame = include_window_frame
        self.moving = self.viewport = None
        self.approximate = False
        self.incomplete_reason = None
        self.frame_count = 0
        self._rates = {}
        self._units = {}
        self._counts = {}

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
            self.approximate = True
            self.progress("Drobne różnice obrazu — łączę z niewielką zakładką…")
            return min(a.height - 12, round(expected) + 2)

    def _union_motion(self, first, second, axis, distance=None):
        box = motion_bounds(first, second)
        if box:
            left, top, right, bottom = box
            if axis == "y" and distance and self.moving is not None and top < self.moving[1]:
                end = min(self.moving[1], first.height - distance)
                if end > top:
                    area = (left, top, right, end)
                    shifted = (left, top + distance, right, end + distance)
                    raw_score = ImageStat.Stat(ImageChops.difference(first.crop(area), second.crop(area)).convert("L")).mean[0]
                    aligned_score = ImageStat.Stat(ImageChops.difference(first.crop(shifted), second.crop(area)).convert("L")).mean[0]
                    # A tab title or address bar can redraw while the document
                    # scrolls. Expand upward only if that area translates too.
                    if raw_score < 3 or aligned_score > min(20, raw_score * 0.65):
                        top = self.moving[1]
                        content_box = (0, top, first.width, bottom)
                        content_motion = motion_bounds(first.crop(content_box), second.crop(content_box))
                        if content_motion:
                            left, right = content_motion[0], content_motion[2]
            margin_y, margin_x = max(2, first.height // 160), max(2, first.width // 80)
            if axis == "y" and (left <= margin_x or right >= first.width - margin_x):
                difference = ImageChops.difference(first, second).convert("L")
                # Recover genuinely moving columns hidden by the scrollbar
                # safety margin on large desktops; stop at fixed window edges.
                if left <= margin_x:
                    while left > 0 and ImageStat.Stat(difference.crop((left - 1, top, left, bottom))).mean[0] > 3:
                        left -= 1
                if right >= first.width - margin_x:
                    while right < first.width and ImageStat.Stat(difference.crop((right, top, right + 1, bottom))).mean[0] > 3:
                        right += 1
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

    def _seek_start(self, axis, initial=None):
        previous = initial if initial is not None else self.driver.snapshot()
        unchanged = 0
        for _ in range(self.max_steps):
            if self.driver.at_edge(axis, -1) is True:
                return previous
            self.driver.scroll(axis, -1, 48)
            current = self.driver.snapshot()
            unchanged = unchanged + 1 if scroll_frames_equal(previous, current, axis, stable_ratio=0.6) else 0
            if unchanged >= 2:
                return current
            previous = current
        raise ScrollCaptureError("Nie znaleziono początku zawartości. Zrzut rozpoczyna się w bieżącym miejscu.")

    def _advance(self, previous, axis):
        if self.driver.at_edge(axis, 1) is True:
            return None, 0
        units = self._units.get(axis, 1)
        expected = self._rates.get(axis, 0) * units or None
        for attempt in range(3):
            self.driver.scroll(axis, 1, units)
            current = self.driver.snapshot()
            displacement = getattr(self.driver, "scroll_displacement", None)
            measured = displacement(axis) if displacement is not None else None
            region = self.moving
            if region is None:
                candidate = _central_scroll_region(previous, current, axis)
                if candidate is not None:
                    across = candidate[2] - candidate[0] if axis == "y" else candidate[3] - candidate[1]
                    full_across = previous.width if axis == "y" else previous.height
                    if across <= full_across * 0.75:
                        region = candidate
            region = region or (0, 0, previous.width, previous.height)
            first, second = previous.crop(region), current.crop(region)
            if measured is None and scroll_frames_equal(first, second, axis):
                edge = self.driver.at_edge(axis, 1)
                if edge is True:
                    return None, 0
                if edge is False:
                    raise ScrollCaptureError("Okno nie pokazuje nowej zawartości mimo przewijania. Zachowano przechwyconą część.")
                if attempt == 2:
                    return None, 0
                continue
            try:
                distance = measured if measured is not None else estimate_shift(first, second, axis, expected)
            except ScrollCaptureError:
                self.progress("Dopasowuję fragment po odświeżeniu strony…")
                current = self.driver.snapshot()
                distance = self._match_after_retry(first, current.crop(region), axis, expected)
            if not distance:
                if self.driver.at_edge(axis, 1) is True or attempt == 2 and self.driver.at_edge(axis, 1) is None:
                    return None, 0
                if attempt == 2:
                    raise ScrollCaptureError("Okno nie pokazuje przesunięcia zawartości. Zachowano wcześniejszą część.")
                continue
            if measured is None:
                self._union_motion(previous, current, axis, distance)
            logger.info("Scroll displacement: axis=%s pixels=%s content=%s", axis, distance, self.moving)
            set_region = getattr(self.driver, "set_content_region", None)
            if set_region is not None:
                set_region(self.moving)
            self._counts[axis] = self._counts.get(axis, 0) + 1
            # Scale the matching hint whenever the wheel step changes. The last
            # partial step must not reduce the normal pixels-per-unit estimate.
            self._rates[axis] = max(self._rates.get(axis, 0), distance / units)
            if self._counts[axis] >= 2:
                extent = self.moving[2] - self.moving[0] if axis == "x" else self.moving[3] - self.moving[1]
                self._units[axis] = max(1, min(24, int(extent * 0.42 / self._rates[axis])))
            return current, distance

    def _record(self, store, frame, x, y, dx, dy):
        store.add(frame, x, y, dx, dy, viewport=self.moving)
        self.frame_count += 1
        scaling = f" · rozdzielczość {store.scale:.0%}" if store.scale < 1 else ""
        self.progress(f"Przechwycono fragment {self.frame_count} · łączę obraz na bieżąco{scaling}…")

    def capture(self):
        from capture_store import CaptureStore, CaptureStorageError
        self.progress("Ustalam początek i od razu przechwytuję zawartość…")
        initial = self.driver.snapshot()
        for axis in self.axes:
            try:
                initial = self._seek_start(axis, initial)
            except CaptureCancelled:
                raise
            except ScrollCaptureError as exc:
                self.incomplete_reason = str(exc)
                break
        bounds = getattr(self.driver, "capture_bounds", None)
        bounds = bounds(self.axes) if bounds is not None else None
        content_size = None
        if bounds is not None:
            self.moving, content_size = bounds
        with CaptureStore(self.max_pixels, self.max_output_pixels) as store:
            x = y = 0
            dx, dy = initial.size
            current = initial
            try:
                for row in range(self.max_steps):
                    x = 0
                    dx = initial.width
                    for column in range(self.max_steps):
                        self._record(store, current, x, y, dx, dy)
                        if "x" not in self.axes:
                            break
                        advanced, dx = self._advance(current, "x")
                        if advanced is None:
                            break
                        x += dx
                        current = advanced
                    else:
                        raise ScrollCaptureError("Osiągnięto limit przewijania w poziomie. Zachowano dotychczasowy zrzut.")
                    if "y" not in self.axes or self.driver.at_edge("y", 1) is True:
                        break
                    if "x" in self.axes and x:
                        current = self._seek_start("x", current)
                    advanced, dy = self._advance(current, "y")
                    if advanced is None:
                        break
                    y += dy
                    current = advanced
                else:
                    raise ScrollCaptureError("Osiągnięto limit przewijania w pionie. Zachowano dotychczasowy zrzut.")
            except CaptureCancelled:
                raise
            except (ScrollCaptureError, CaptureStorageError) as exc:
                if not store.frames:
                    self.incomplete_reason = str(exc)
                    return initial
                self.incomplete_reason = str(exc)
                logger.warning("Returning captured content: %s", exc)
            if self.moving is None:
                return initial
            self.viewport = self.moving
            self.progress(f"Kończę zapis {self.frame_count} przechwyconych fragmentów…")
            # All input is finished. A closed/moved source must not discard
            # already captured frames while they are being assembled.
            pulse = getattr(self.driver, "check_cancelled", getattr(self.driver, "pulse", lambda: None))
            return store.assemble(self.viewport, pulse, include_window_frame=self.include_window_frame, content_size=content_size)
