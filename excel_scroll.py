"""Bound scrolling to visible data in the selected Excel window and worksheet."""
import pythoncom
import win32gui
import win32com

from app_storage import cache_session

# Keep any COM support cache in the application's owned session as well.
_com_cache = cache_session().path / "com"
_com_cache.mkdir(exist_ok=True)
win32com.__gen_path__ = str(_com_cache)
win32com.gen_py.__path__ = [str(_com_cache)]

from win32com.client.dynamic import Dispatch

from scroll_capture import ScrollCaptureError


def excel_window_from_handle(handle):
    children = []
    win32gui.EnumChildWindows(handle, lambda child, _: children.append(child)
                             if win32gui.GetClassName(child) == "EXCEL7" and win32gui.IsWindowVisible(child) else None, None)
    for child in children:
        try:
            # Office exposes its native Window object through standard MSAA.
            # Bind the selected HWND, rather than an arbitrary running workbook.
            _, result = win32gui.SendMessageTimeout(child, 0x003D, 0, -16, 2, 2000)
            window = Dispatch(pythoncom.ObjectFromLresult(result, pythoncom.IID_IDispatch, 0))
            if int(window.Hwnd) == handle:
                return window, child
        except (pythoncom.com_error, win32gui.error):
            continue
    raise ScrollCaptureError("Nie można odczytać aktywnego arkusza Excela. Zamknij jego okna dialogowe i zakończ edycję komórki.")


def last_data_cell(sheet):
    # Explicit positional arguments also work with Office's late-bound dispatch.
    # Values exclude formatting-only cells and formulas displaying empty strings.
    cells = sheet.Cells
    after = cells(1, 1)
    row = cells.Find("*", after, -4163, 2, 1, 2, False, False, False)
    column = cells.Find("*", after, -4163, 2, 2, 2, False, False, False)
    if row is None or column is None:
        return 1, 1
    return int(row.Row + row.MergeArea.Rows.Count - 1), int(column.Column + column.MergeArea.Columns.Count - 1)


class ExcelSheetScroll:
    def __init__(self, handle, bbox):
        self.window, self.grid_handle = excel_window_from_handle(handle)
        self.sheet = self.window.ActiveSheet
        if int(self.sheet.Type) != -4167:
            raise ScrollCaptureError("Wybierz arkusz z komórkami; arkusz wykresu nie obsługuje tego przewijania.")
        self.sheet_identity = self.sheet.CodeName
        self.last_row, self.last_column = last_data_cell(self.sheet)
        self.pane = self.window.ActivePane
        self.bbox = bbox
        self.delta = {"x": 0, "y": 0}
        self._calibrate()

    def _cell_at(self, x, y):
        try:
            cell = self.window.RangeFromPoint(int(x), int(y))
            if cell is not None and int(cell.Rows.Count) < 10000 and int(cell.Columns.Count) < 10000:
                return cell
        except (pythoncom.com_error, AttributeError):
            pass
        return None

    def _calibrate(self):
        rect = win32gui.GetWindowRect(self.grid_handle)
        x, y = (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2
        cell = self._cell_at(x, y)
        if cell is None:
            raise ScrollCaptureError("Nie udało się ustalić obszaru komórek Excela. Zamknij jego otwarte menu.")
        # Select the existing pane under the capture point without activating it.
        for index in range(1, int(self.window.Panes.Count) + 1):
            pane = self.window.Panes(index)
            visible = pane.VisibleRange
            if (visible.Row <= cell.Row < visible.Row + visible.Rows.Count
                    and visible.Column <= cell.Column < visible.Column + visible.Columns.Count):
                self.pane = pane
        def boundary(low, high, axis, after):
            target = int(cell.Row if axis == "y" else cell.Column)
            while low < high:
                middle = (low + high) // 2
                point = self._cell_at(x if axis == "y" else middle, middle if axis == "y" else y)
                value = int(point.Row if axis == "y" else point.Column) if point is not None else 0
                if value > target or value == target and not after:
                    high = middle
                else:
                    low = middle + 1
            return low
        cell_top = boundary(rect[1], y, "y", False)
        cell_bottom = boundary(y, rect[3] - 1, "y", True)
        cell_left = boundary(rect[0], x, "x", False)
        cell_right = boundary(x, rect[2] - 1, "x", True)
        self.scale_y = (cell_bottom - cell_top) / float(cell.Height)
        self.scale_x = (cell_right - cell_left) / float(cell.Width)
        if min(self.scale_x, self.scale_y) <= 0:
            raise ScrollCaptureError("Nie można zmierzyć powiększenia arkusza Excela.")
        visible = self.pane.VisibleRange
        top = round(cell_top - (float(cell.Top) - float(visible.Top)) * self.scale_y)
        left = round(cell_left - (float(cell.Left) - float(visible.Left)) * self.scale_x)
        self.region = (max(0, left - self.bbox[0]), max(0, top - self.bbox[1]),
                       min(self.bbox[2], rect[2]) - self.bbox[0], min(self.bbox[3], rect[3]) - self.bbox[1])
        # Frozen rows/columns are part of the fixed frame, captured once.
        self.start_row = int(self.window.SplitRow) + 1 if self.window.FreezePanes else 1
        self.start_column = int(self.window.SplitColumn) + 1 if self.window.FreezePanes else 1
        self.last_row = max(self.start_row, self.last_row)
        self.last_column = max(self.start_column, self.last_column)

    def check(self):
        if self.window.ActiveSheet.CodeName != self.sheet_identity:
            raise ScrollCaptureError("Aktywny arkusz zmienił się podczas przechwytywania.")

    def _position(self, axis):
        index = int(self.pane.ScrollRow if axis == "y" else self.pane.ScrollColumn)
        cell = self.sheet.Cells(index, 1) if axis == "y" else self.sheet.Cells(1, index)
        return float(cell.Top if axis == "y" else cell.Left)

    def _end(self, axis):
        cell = self.sheet.Cells(self.last_row, 1) if axis == "y" else self.sheet.Cells(1, self.last_column)
        return float(cell.Top + cell.Height if axis == "y" else cell.Left + cell.Width)

    def at_edge(self, axis, direction):
        self.check()
        if direction < 0:
            return int(self.pane.ScrollRow if axis == "y" else self.pane.ScrollColumn) <= (self.start_row if axis == "y" else self.start_column)
        extent = self.region[3] - self.region[1] if axis == "y" else self.region[2] - self.region[0]
        scale = self.scale_y if axis == "y" else self.scale_x
        return (self._end(axis) - self._position(axis)) * scale <= extent + 0.5

    def scroll(self, axis, direction, units):
        self.check()
        before = self._position(axis)
        start = self.start_row if axis == "y" else self.start_column
        last = self.last_row if axis == "y" else self.last_column
        current = int(self.pane.ScrollRow if axis == "y" else self.pane.ScrollColumn)
        visible = self.pane.VisibleRange
        count = int(visible.Rows.Count if axis == "y" else visible.Columns.Count)
        step = min(max(1, count // 2), max(1, units * (3 if axis == "y" else 1)))
        # Seeking backwards may use a large step; forward movement keeps overlap.
        if direction < 0:
            step = units * (3 if axis == "y" else 1)
        target = max(start, min(last, current + direction * step))
        if axis == "y":
            self.pane.ScrollRow = target
        else:
            self.pane.ScrollColumn = target
        scale = self.scale_y if axis == "y" else self.scale_x
        self.delta[axis] = abs(round(self._position(axis) * scale) - round(before * scale))

    def capture_bounds(self, axes):
        self.check()
        width, height = self.region[2] - self.region[0], self.region[3] - self.region[1]
        remaining_x = max(1, round((self._end("x") - self._position("x")) * self.scale_x))
        remaining_y = max(1, round((self._end("y") - self._position("y")) * self.scale_y))
        return self.region, (remaining_x if "x" in axes else min(width, remaining_x),
                             remaining_y if "y" in axes else min(height, remaining_y))
