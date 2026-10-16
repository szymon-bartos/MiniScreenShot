"""Spool captured frames once, then assemble without a second scroll pass."""
from dataclasses import dataclass
from contextlib import contextmanager
import atexit
import math
import mmap
from pathlib import Path
import shutil
import weakref

from PIL import Image
from app_storage import cache_session


class CaptureStorageError(RuntimeError):
    pass


class MappedCaptureImage(Image.Image):
    def close(self):
        super().close()
        backing = self.__dict__.pop("_capture_backing", None)
        if backing is not None:
            backing.close()

    def __del__(self):
        self.close()


def _close_live_image(reference):
    image = reference()
    if image is not None:
        image.close()


class _ImageBacking:
    def __init__(self, size):
        session = cache_session()
        try:
            session.check_space(size[0] * size[1] * 4)
        except OSError as exc:
            raise CaptureStorageError(str(exc)) from exc
        self.directory = session.temporary_directory(prefix="result-")
        self.file = self.buffer = None
        try:
            self.file = open(Path(self.directory.name) / "image.rgba", "w+b")
            self.file.truncate(size[0] * size[1] * 4)
            self.buffer = mmap.mmap(self.file.fileno(), 0, access=mmap.ACCESS_WRITE)
        except Exception:
            self.close()
            raise

    def close(self):
        if self.buffer is not None:
            self.buffer.close()
            self.buffer = None
        if self.file is not None:
            self.file.close()
            self.file = None
        self.directory.cleanup()


@dataclass
class StoredFrame:
    path: Path | None
    size: tuple
    x: int
    y: int
    dx: int
    dy: int
    image: Image.Image | None = None
    source_size: tuple | None = None


class CaptureStore:
    def __init__(self, memory_pixels=24_000_000, max_output_pixels=24_000_000):
        if max_output_pixels is not None and max_output_pixels < 1:
            raise ValueError("max_output_pixels must be positive or None")
        self.directory = cache_session().temporary_directory(prefix="frames-")
        self.frames = []
        self.memory_pixels = memory_pixels
        self.max_output_pixels = max_output_pixels
        self.scale = 1.0
        self.max_x = self.max_y = 0
        self.memory_bytes = 0
        self.cache_budget = min(64 * 1024**2, memory_pixels * 4)
        self.bytes_written = 0
        # Reserve room for the assembled image as well as the captured frames.
        self.storage_budget = min(384 * 1024**2, max(0, (shutil.disk_usage(self.directory.name).free - 256 * 1024**2) // 2))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        for record in self.frames:
            if record.image is not None:
                record.image.close()
                record.image = None
        self.directory.cleanup()

    def _fit_scale(self, size):
        if self.max_output_pixels is not None:
            # Change scale in steps to avoid repeatedly resizing the output as
            # each new strip arrives. Ordinary screenshots remain unchanged.
            while max(1, round(size[0] * self.scale)) * max(1, round(size[1] * self.scale)) > self.max_output_pixels:
                self.scale *= 0.75

    def add(self, frame, x, y, dx, dy, viewport=None):
        source_size = frame.size
        self.max_x, self.max_y = max(self.max_x, x), max(self.max_y, y)
        width, height = frame.size if viewport is None else (viewport[2] - viewport[0], viewport[3] - viewport[1])
        self._fit_scale((width + self.max_x, height + self.max_y))
        stored_size = tuple(max(1, round(value * self.scale)) for value in source_size)
        stored = frame if stored_size == source_size else frame.resize(stored_size, Image.Resampling.BILINEAR)
        try:
            self._store(stored, source_size, x, y, dx, dy)
        finally:
            if stored is not frame:
                stored.close()

    def _store(self, frame, source_size, x, y, dx, dy):
        size = frame.width * frame.height * 4
        if self.memory_bytes + size <= self.cache_budget:
            self.frames.append(StoredFrame(None, frame.size, x, y, dx, dy, frame.copy(), source_size))
            self.memory_bytes += size
            return
        if self.bytes_written + size > self.storage_budget:
            raise CaptureStorageError("Brakuje miejsca na dalszą część zrzutu. Zachowano przechwycony fragment.")
        path = Path(self.directory.name) / f"{len(self.frames):05d}.rgba"
        try:
            cache_session().check_space(size)
            with path.open("wb") as target:
                target.write(frame.convert("RGBA").tobytes())
        except OSError as exc:
            raise CaptureStorageError("Nie udało się zapisać kolejnego fragmentu. Zachowano wcześniejszą część zrzutu.") from exc
        self.frames.append(StoredFrame(path, frame.size, x, y, dx, dy, source_size=source_size))
        self.bytes_written += size

    @contextmanager
    def _open_frame(self, record):
        if record.image is not None:
            yield record.image
        else:
            with record.path.open("rb") as source:
                with mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ) as buffer:
                    image = Image.frombuffer("RGBA", record.size, buffer, "raw", "RGBA", 0, 1)
                    try:
                        yield image
                    finally:
                        image.close()

    def assemble(self, viewport, pulse=lambda: None, include_window_frame=False, content_size=None):
        left, top, right, bottom = viewport
        width, height = right - left, bottom - top
        captured_size = (width + max(frame.x for frame in self.frames), height + max(frame.y for frame in self.frames))
        content_size = tuple(min(requested, captured) for requested, captured in zip(content_size, captured_size)) if content_size else captured_size
        source_size = self.frames[0].source_size or self.frames[0].size
        offset_x, offset_y = (left, top) if include_window_frame else (0, 0)
        original_size = ((max(source_size[0], content_size[0] + source_size[0] - width), content_size[1] + source_size[1] - height)
                         if include_window_frame else content_size)
        self._fit_scale(original_size)
        size = tuple(max(1, round(value * self.scale)) for value in original_size)
        scale_x, scale_y = size[0] / original_size[0], size[1] / original_size[1]
        backing = None
        if size[0] * size[1] > self.memory_pixels:
            backing = _ImageBacking(size)
            result = Image.frombuffer("RGBA", size, backing.buffer, "raw", "RGBA", 0, 1)
            result.__class__ = MappedCaptureImage
            result._capture_backing = backing
            # Close the Pillow core before its exported mmap buffer, including
            # at interpreter shutdown when a preview still owns the image.
            atexit.register(_close_live_image, weakref.ref(result))
        else:
            result = Image.new("RGB", size, "white")
        def paste(tile, destination):
            if backing is None:
                result.paste(tile, destination)
            else:
                raw = tile.convert("RGBA").tobytes()
                stride = tile.width * 4
                for row in range(tile.height):
                    offset = ((destination[1] + row) * size[0] + destination[0]) * 4
                    backing.buffer[offset:offset + stride] = raw[row * stride:(row + 1) * stride]
                    if row % 128 == 0:
                        pulse()
        try:
            if include_window_frame:
                if backing is not None:
                    block = b"\xff" * min(len(backing.buffer), 1024**2)
                    for start in range(0, len(backing.buffer), len(block)):
                        length = min(len(block), len(backing.buffer) - start)
                        backing.buffer[start:start + length] = block[:length]
                # Keep fixed application chrome once, outside the stitched body.
                # Never stretch or repeat a toolbar down the captured document.
                max_x, max_y = content_size[0] - width, content_size[1] - height
                pieces = (((0, 0, source_size[0], top), (0, 0)),
                          ((0, top, left, min(bottom, top + content_size[1])), (0, top)),
                          ((right, top, source_size[0], min(bottom, top + content_size[1])), (right + max(0, max_x), top)),
                          ((0, bottom, source_size[0], source_size[1]), (0, bottom + max_y)))
                with self._open_frame(self.frames[0]) as source:
                    sx, sy = source.width / source_size[0], source.height / source_size[1]
                    for box, origin in pieces:
                        if box[2] <= box[0] or box[3] <= box[1]:
                            continue
                        end = (min(size[0], round((origin[0] + box[2] - box[0]) * scale_x)),
                               min(size[1], round((origin[1] + box[3] - box[1]) * scale_y)))
                        destination = (round(origin[0] * scale_x), round(origin[1] * scale_y))
                        tile_size = (end[0] - destination[0], end[1] - destination[1])
                        if min(tile_size) < 1:
                            continue
                        tile = source.transform(tile_size, Image.Transform.EXTENT,
                                                (box[0] * sx, box[1] * sy, box[2] * sx, box[3] * sy), Image.Resampling.BILINEAR)
                        paste(tile, destination)
                        tile.close()
            for record in self.frames:
                pulse()
                # Replace a small part of the overlap when reducing resolution
                # so filtered window/footer edges cannot leave dark seams.
                guard = math.ceil(2 / min(scale_x, scale_y)) if size != original_size else 0
                cut_left = max(0, width - record.dx - guard) if record.x else 0
                cut_top = max(0, height - record.dy - guard) if record.y else 0
                box = (left + cut_left, top + cut_top, right, bottom)
                # Round shared boundaries in global coordinates. Independently
                # rounding each tile's width would leave seams or repeat rows.
                destination = (round((offset_x + record.x + cut_left) * scale_x), round((offset_y + record.y + cut_top) * scale_y))
                end = (round((offset_x + min(record.x + width, content_size[0])) * scale_x), round((offset_y + min(record.y + height, content_size[1])) * scale_y))
                target_size = (end[0] - destination[0], end[1] - destination[1])
                source_size = record.source_size or record.size
                def render(source):
                    if size == original_size and record.size == source_size:
                        return source.crop((box[0], box[1], box[0] + target_size[0], box[1] + target_size[1]))
                    sx, sy = record.size[0] / source_size[0], record.size[1] / source_size[1]
                    extent = ((destination[0] / scale_x - offset_x - record.x + left) * sx,
                              (destination[1] / scale_y - offset_y - record.y + top) * sy,
                              (end[0] / scale_x - offset_x - record.x + left) * sx,
                              (end[1] / scale_y - offset_y - record.y + top) * sy)
                    return source.transform(target_size, Image.Transform.EXTENT, extent, Image.Resampling.BILINEAR)
                if min(target_size) < 1:
                    if record.image is not None:
                        record.image.close()
                        record.image = None
                    if record.path is not None:
                        record.path.unlink()
                    continue
                with self._open_frame(record) as source:
                    tile = render(source)
                if record.image is not None:
                    record.image.close()
                    record.image = None
                paste(tile, destination)
                tile.close()
                if record.path is not None:
                    record.path.unlink()
            if size != original_size:
                result.info["capture_original_size"] = original_size
                result.info["capture_scale"] = self.scale
            if include_window_frame:
                result.info["capture_content_box"] = (round(offset_x * scale_x), round(offset_y * scale_y),
                                                      round((offset_x + content_size[0]) * scale_x),
                                                      round((offset_y + content_size[1]) * scale_y))
            return result
        except Exception:
            result.close()
            if backing is not None:
                backing.close()
            raise
