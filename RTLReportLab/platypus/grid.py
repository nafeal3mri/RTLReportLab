"""
grid.py — Tailwind-inspired Grid flowable for RTLReportLab.

Key features
============
* Page overflow  — splits cleanly at row boundaries; rounded corners adjust
  so the top piece gets rounded top corners and the bottom piece gets rounded
  bottom corners.
* Border radius  — per-corner control via a single ``border_radius`` value
  (or a ``[TL, TR, BL, BR]`` list for mixed radii).
* Border colour / width — container *and* per-cell.
* Background colour — container *and* per-cell.
* Tailwind-style columns — ``cols=N`` for N equal columns, or explicit
  ``col_widths=[…]`` for fixed sizes.
* Gap — ``gap`` (row *and* column), ``row_gap``, ``col_gap``.
* Column span  — ``GridCell(content, col_span=2)``
* Header rows  — ``header_rows=1`` repeats the first row after every split.

Basic usage
-----------
::

    from RTLReportLab.platypus.grid import Grid, GridCell
    from RTLReportLab.lib import colors

    story.append(
        Grid(
            data=[
                ["Name", "Score"],
                ["Alice", "98"],
                ["Bob",   "82"],
            ],
            cols=2,
            gap=4,
            cell_padding=8,
            border_radius=8,
            border_color=colors.lightgrey,
            border_width=1,
            bg_color=colors.white,
            header_rows=1,
        )
    )

Card-style usage (single content box with rounded corners)
----------------------------------------------------------
::

    story.append(
        Grid(
            data=[[my_paragraph]],
            cols=1,
            cell_padding=16,
            bg_color=colors.white,
            border_radius=12,
            border_color=colors.HexColor('#E1E8ED'),
            border_width=1,
        )
    )
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Union

from RTLReportLab.platypus.flowables import Flowable
from RTLReportLab.lib import colors
from RTLReportLab.lib.utils import isStr

__all__ = ['Grid', 'GridCell']

# ── helpers ───────────────────────────────────────────────────────────────────

def _pad4(p) -> tuple:
    """Normalise *padding* to a ``(top, right, bottom, left)`` tuple."""
    if isinstance(p, (int, float)):
        return (p, p, p, p)
    p = tuple(p)
    if len(p) == 2:
        return (p[0], p[1], p[0], p[1])
    if len(p) == 4:
        return p
    raise ValueError("padding must be a number, 2-tuple or 4-tuple")


def _r4(r) -> list:
    """Normalise *border_radius* to a ``[TL, TR, BL, BR]`` list."""
    if isinstance(r, (int, float)):
        return [r, r, r, r]
    r = list(r)
    if len(r) == 4:
        return r
    raise ValueError("border_radius must be a number or 4-element list [TL,TR,BL,BR]")


def _rounded_rect_path(path, x, y, w, h, radii):
    """
    Add a rounded-rectangle sub-path to *path* (a PDFPathObject).

    *radii* is ``[TL, TR, BL, BR]`` — set individual radii to 0 for a
    square corner.  Uses cubic Bézier arcs (m≈0.4472).
    """
    m = 0.4472          # Bézier magic number for a quarter-circle approximation
    tl, tr, bl, br = [max(0.0, v) for v in radii]

    # clamp to half the shortest side
    max_r = min(w, h) / 2
    tl = min(tl, max_r)
    tr = min(tr, max_r)
    bl = min(bl, max_r)
    br = min(br, max_r)

    # Start at bottom-left, after the BL corner
    path.moveTo(x + bl, y)

    # Bottom edge → bottom-right corner
    path.lineTo(x + w - br, y)
    if br:
        path.curveTo(x + w - m * br, y,
                     x + w,           y + m * br,
                     x + w,           y + br)

    # Right edge → top-right corner
    path.lineTo(x + w, y + h - tr)
    if tr:
        path.curveTo(x + w,           y + h - m * tr,
                     x + w - m * tr,  y + h,
                     x + w - tr,      y + h)

    # Top edge → top-left corner
    path.lineTo(x + tl, y + h)
    if tl:
        path.curveTo(x + m * tl, y + h,
                     x,          y + h - m * tl,
                     x,          y + h - tl)

    # Left edge → bottom-left corner
    path.lineTo(x, y + bl)
    if bl:
        path.curveTo(x,          y + m * bl,
                     x + m * bl, y,
                     x + bl,     y)

    path.close()


def _draw_rounded_rect(canv, x, y, w, h, radii, fill=1, stroke=0):
    """Draw a rounded rectangle on *canv* using the given radii list."""
    if not any(radii):
        canv.rect(x, y, w, h, fill=fill, stroke=stroke)
        return
    p = canv.beginPath()
    _rounded_rect_path(p, x, y, w, h, radii)
    canv.drawPath(p, fill=fill, stroke=stroke)


# ── GridCell ──────────────────────────────────────────────────────────────────

class GridCell:
    """
    A single cell inside a :class:`Grid`, with optional per-cell style
    overrides.

    Parameters
    ----------
    content     : str | Flowable | list[Flowable] | None
                  The cell content.  A plain string is auto-wrapped in a
                  Paragraph using the default style.  A list of Flowables
                  is stacked top-to-bottom inside the cell.
    col_span    : int
                  How many columns this cell occupies (default 1).
    bg_color    : Color | None   Overrides ``Grid.cell_bg``.
    border_color: Color | None   Overrides ``Grid.cell_border_color``.
    border_width: float | None   Overrides ``Grid.cell_border_width``.
    border_radius: float | None  Overrides ``Grid.cell_border_radius``.
    padding     : number | tuple Overrides ``Grid.cell_padding``.
    valign      : 'top' | 'middle' | 'bottom'
    """

    def __init__(
        self,
        content=None,
        *,
        col_span: int = 1,
        bg_color=None,
        border_color=None,
        border_width: Optional[float] = None,
        border_radius: Optional[float] = None,
        padding=None,
        valign: str = 'top',
    ):
        self.content = content
        self.col_span = max(1, int(col_span))
        self.bg_color = bg_color
        self.border_color = border_color
        self.border_width = border_width
        self.border_radius = border_radius
        self.padding = padding
        self.valign = valign


# ── Grid ─────────────────────────────────────────────────────────────────────

class Grid(Flowable):
    """
    Tailwind-inspired grid layout with automatic page-overflow handling.

    See the module docstring for full parameter descriptions and examples.
    """

    def __init__(
        self,
        data: list,
        *,
        cols: Optional[int] = None,
        col_widths: Optional[Sequence[float]] = None,
        gap: float = 0,
        row_gap: Optional[float] = None,
        col_gap: Optional[float] = None,
        padding: Union[float, tuple] = 0,
        cell_padding: Union[float, tuple] = 8,
        # container styling
        bg_color=None,
        border_color=None,
        border_width: float = 0,
        border_radius: Union[float, list] = 0,
        # cell defaults
        cell_bg=None,
        cell_border_color=None,
        cell_border_width: float = 0,
        cell_border_radius: float = 0,
        # pagination
        header_rows: int = 0,
        # ── internal (used by split()) ────────────────────────────────────────
        _radii: Optional[list] = None,   # overrides border_radius post-split
    ):
        super().__init__()
        self._raw_data = data
        self._cols_arg = cols
        self._col_widths_arg = list(col_widths) if col_widths is not None else None
        self._row_gap = row_gap if row_gap is not None else gap
        self._col_gap = col_gap if col_gap is not None else gap
        self._padding = _pad4(padding)
        self._cell_padding = _pad4(cell_padding)

        self.bg_color = bg_color
        self.border_color = border_color
        self.border_width = float(border_width)
        self._radii = _radii if _radii is not None else _r4(border_radius)

        self.cell_bg = cell_bg
        self.cell_border_color = cell_border_color
        self.cell_border_width = float(cell_border_width)
        self.cell_border_radius = float(cell_border_radius)

        self.header_rows = int(header_rows)

        # computed during wrap()
        self._cells: List[List[GridCell]] = []
        self._n_cols: int = 0
        self._col_w: List[float] = []
        self._row_h: List[float] = []
        self._width: float = 0
        self._height: float = 0

    # ── normalisation ─────────────────────────────────────────────────────────

    @staticmethod
    def _as_cell(raw) -> GridCell:
        return raw if isinstance(raw, GridCell) else GridCell(raw)

    def _normalise_data(self, data) -> List[List[GridCell]]:
        return [[self._as_cell(c) for c in row] for row in data]

    # ── geometry ──────────────────────────────────────────────────────────────

    def _resolve_col_widths(self, avail_w: float) -> List[float]:
        n = self._n_cols
        bw2 = self.border_width * 2
        outer = self._padding[1] + self._padding[3]
        inner_w = avail_w - bw2 - outer - self._col_gap * max(n - 1, 0)

        if not self._col_widths_arg:
            # all equal
            cw = max(inner_w / n, 1.0) if n else avail_w
            return [cw] * n

        # Explicit col_widths — None means "share the remaining space equally"
        base = list(self._col_widths_arg)[:n]
        # pad to n if shorter
        while len(base) < n:
            base.append(None)

        fixed = sum(v for v in base if v is not None)
        n_auto = sum(1 for v in base if v is None)
        remaining = max(inner_w - fixed, 0.0)
        auto_w = (remaining / n_auto) if n_auto else 0.0

        return [v if v is not None else auto_w for v in base]

    def _span_width(self, col_idx: int, span: int) -> float:
        """Width for a cell that spans *span* columns from *col_idx*."""
        cols = self._col_w[col_idx: col_idx + span]
        return sum(cols) + self._col_gap * max(span - 1, 0)

    def _get_cell_pad(self, cell: GridCell) -> tuple:
        if cell.padding is not None:
            return _pad4(cell.padding)
        return self._cell_padding

    def _measure_content(self, content, width: float) -> float:
        """Return the required height for *content* inside *width*."""
        if content is None:
            return 0.0
        if isStr(content):
            from RTLReportLab.platypus import Paragraph
            from RTLReportLab.lib.styles import ParagraphStyle
            p = Paragraph(content, ParagraphStyle('_grid_tmp'))
            _, h = p.wrap(max(width, 1), 72000)
            return h
        if isinstance(content, Flowable):
            content.canv = getattr(self, 'canv', None)
            _, h = content.wrap(max(width, 1), 72000)
            return h
        if isinstance(content, (list, tuple)):
            total = 0.0
            for item in content:
                total += self._measure_content(item, width)
            return total
        return 0.0

    def _measure_row(self, row: List[GridCell]) -> float:
        col_idx = 0
        max_h = 0.0
        for cell in row:
            if col_idx >= self._n_cols:
                break
            span = cell.col_span
            cw = self._span_width(col_idx, span)
            cp = self._get_cell_pad(cell)
            content_w = max(cw - cp[1] - cp[3], 1.0)
            content_h = self._measure_content(cell.content, content_w)
            row_h = content_h + cp[0] + cp[2]
            max_h = max(max_h, row_h)
            col_idx += span
        return max_h

    # ── wrap ──────────────────────────────────────────────────────────────────

    def wrap(self, availWidth, availHeight):
        self._cells = self._normalise_data(self._raw_data)

        # resolve number of columns
        if self._col_widths_arg:
            self._n_cols = len(self._col_widths_arg)
        elif self._cols_arg:
            self._n_cols = self._cols_arg
        else:
            self._n_cols = max(
                (sum(c.col_span for c in row) for row in self._cells),
                default=1,
            )

        self._col_w = self._resolve_col_widths(availWidth)

        # measure rows
        self._row_h = [self._measure_row(row) for row in self._cells]

        n = len(self._row_h)
        bw2 = self.border_width * 2
        total_h = (
            sum(self._row_h)
            + self._row_gap * max(n - 1, 0)
            + self._padding[0] + self._padding[2]
            + bw2
        )
        total_w = (
            sum(self._col_w)
            + self._col_gap * max(self._n_cols - 1, 0)
            + self._padding[1] + self._padding[3]
            + bw2
        )
        self._width = min(total_w, availWidth)
        self._height = total_h
        # Last-resort: a grid marked for force-fit (taller than a whole page and
        # unsplittable) reports a clamped height so the frame accepts it instead
        # of looping forever; its content overflows the frame but the export
        # completes rather than raising a LayoutError.
        clamp = getattr(self, '_clamp_h', None)
        if clamp is not None and self._height > clamp:
            self._height = clamp
        return (self._width, self._height)

    # ── split ─────────────────────────────────────────────────────────────────

    def split(self, availWidth, availHeight):
        """Split the Grid at the first row boundary that fits in *availHeight*.

        Returns ``[self]`` if the whole grid fits, or ``[]`` if nothing fits
        (single row taller than the page).  Otherwise returns two Grid pieces
        where:
        * The first piece keeps the top rounded corners.
        * The second piece keeps the bottom rounded corners.
        """
        self.wrap(availWidth, availHeight)

        if self._height <= availHeight:
            return [self]

        bw = self.border_width
        used = self._padding[0] + self._padding[2] + bw * 2

        fit_rows = 0
        for i, rh in enumerate(self._row_h):
            gap = self._row_gap if i > 0 else 0.0
            if used + gap + rh <= availHeight:
                used += gap + rh
                fit_rows = i + 1
            else:
                break

        if fit_rows == 0:
            # No whole row fits.  Try splitting the first row's cell content
            # vertically (the single-tall-cell card case).
            pieces = self._split_first_row(availWidth, availHeight)
            if pieces:
                return pieces
            # Nothing splits and the grid is taller than the frame.  Defer once
            # so the doctemplate can retry on a fresh, full-height frame where
            # it may fit or split.  If we are asked to split *again* and still
            # cannot, the grid is larger than a whole page (e.g. a single image
            # taller than the frame): force it to draw — overflowing — rather
            # than raising a LayoutError and aborting the whole export.
            if getattr(self, '_force_fit', False):
                self._clamp_h = availHeight
                return [self]
            self._force_fit = True
            return []

        if fit_rows >= len(self._raw_data):
            return [self]

        header = self._raw_data[: self.header_rows]
        data1 = self._raw_data[:fit_rows]
        data2 = header + self._raw_data[fit_rows:]

        base = dict(
            cols=self._cols_arg,
            col_widths=self._col_widths_arg,
            row_gap=self._row_gap,
            col_gap=self._col_gap,
            padding=self._padding,
            cell_padding=self._cell_padding,
            bg_color=self.bg_color,
            border_color=self.border_color,
            border_width=self.border_width,
            cell_bg=self.cell_bg,
            cell_border_color=self.cell_border_color,
            cell_border_width=self.cell_border_width,
            cell_border_radius=self.cell_border_radius,
            header_rows=self.header_rows,
        )
        tl, tr, bl, br = self._radii

        # First piece: top corners keep their radius; bottom corners → 0
        g1 = Grid(data1, **base, _radii=[tl, tr, 0,  0 ])
        # Second piece: top corners → 0; bottom corners keep their radius
        g2 = Grid(data2, **base, _radii=[0,  0,  bl, br])
        return [g1, g2]

    def _split_first_row(self, availWidth, availHeight):
        """Attempt to split a single oversized row by splitting each cell's
        flowable list at the available height.

        This handles the *card* pattern — a single-row Grid whose only cell
        contains a tall list of Flowables.  Returns ``[g1, g2]`` on success,
        or ``[]`` if splitting was not possible.
        """
        if not self._cells:
            return []

        row = self._cells[0]   # operate on the first row only
        bw = self.border_width
        vert_used = self._padding[0] + self._padding[2] + bw * 2

        # Build per-cell (first_part, rest) splits
        first_parts: list = []
        rest_parts:  list = []
        any_split = False

        for col_idx, cell in enumerate(row):
            if col_idx >= self._n_cols:
                break
            span = cell.col_span
            cw = self._span_width(col_idx, span)
            cp = self._get_cell_pad(cell)
            content_w = max(cw - cp[1] - cp[3], 1.0)
            avail_content_h = max(availHeight - vert_used - cp[0] - cp[2], 0.0)

            part1, part2 = self._split_content(cell.content, content_w, avail_content_h)

            if part1 and part2:
                any_split = True

            # Preserve original cell's styling; only replace content
            def _make_cell(c, content):
                return GridCell(
                    content,
                    col_span=c.col_span,
                    bg_color=c.bg_color,
                    border_color=c.border_color,
                    border_width=c.border_width,
                    border_radius=c.border_radius,
                    padding=c.padding,
                    valign=c.valign,
                )

            first_parts.append(_make_cell(cell, part1 if part1 else cell.content))
            rest_parts.append(_make_cell(cell, part2 if part2 else []))

        if not any_split:
            return []

        tl, tr, bl, br = self._radii
        base = dict(
            cols=self._cols_arg,
            col_widths=self._col_widths_arg,
            row_gap=self._row_gap,
            col_gap=self._col_gap,
            padding=self._padding,
            cell_padding=self._cell_padding,
            bg_color=self.bg_color,
            border_color=self.border_color,
            border_width=self.border_width,
            cell_bg=self.cell_bg,
            cell_border_color=self.cell_border_color,
            cell_border_width=self.cell_border_width,
            cell_border_radius=self.cell_border_radius,
            header_rows=0,
        )
        data2_tail = self._raw_data[1:]  # rows after the first

        g1 = Grid([first_parts],                    **base, _radii=[tl, tr, 0,  0 ])
        g2 = Grid([rest_parts] + data2_tail,        **base, _radii=[0,  0,  bl, br])
        return [g1, g2]

    def _split_content(self, content, width: float, avail_height: float):
        """Split *content* (Flowable, list of Flowables, or string) into
        ``(first_part, rest_part)`` lists that each fit within *avail_height*.

        Algorithm
        ---------
        Items are processed in order.  For each item:

        1. Measure its **full** natural height via ``wrap(width, 72000)``
           (ignoring the height limit so we get the true size).
        2. If it fits exactly (``ih ≤ remaining``, no fuzz), add to *first*.
        3. Otherwise call ``item.split(width, remaining)`` and inspect the
           result:

           * ``[]``      — unsplittable (image, drawing, fixed-size flowable).
             The whole item goes to *rest* (next page).
           * ``[piece]`` — fits as one piece (floating-point edge case where
             ``ih`` is a hair over ``remaining``).  The piece is added to
             *first* with height capped at ``remaining`` to prevent an
             epsilon overage.
           * ``[p1, p2, …]`` — genuine split.  A sanity check (``p1.height
             ≤ remaining + _FUZZ``) guards against corrupt RTL/emoji splits.
             If sane, ``p1`` → *first*, rest → *rest*; otherwise the whole
             item goes to *rest*.

        4. Everything after the first non-fitting item goes into *rest* to
           preserve content order.

        **Key invariant:** ``sum(heights in first) ≤ avail_height``, so the
        Grid piece wrapping *first* will always fit inside the available frame
        height, preventing ``LayoutError: Splitting error(n==2)``.

        An empty *first* signals "nothing fits here"; the caller returns
        ``[]`` and the doctemplate defers the whole flowable to the next page.
        Both parts are lists of Flowables (possibly empty).
        """
        if content is None:
            return ([], [])

        # Normalise to a list of Flowables
        items = []
        raw = content if isinstance(content, (list, tuple)) else [content]
        for item in raw:
            if isStr(item):
                from RTLReportLab.platypus import Paragraph
                from RTLReportLab.lib.styles import ParagraphStyle
                item = Paragraph(item, ParagraphStyle('_grid_tmp'))
            if isinstance(item, Flowable):
                items.append(item)

        if not items:
            return ([], [])

        first: list = []
        rest:  list = []
        used = 0.0
        _FUZZ = 1.0   # tolerance for split sanity-check only (not for fit test)

        for item in items:
            if rest:
                # Preserve order: once anything has gone to rest, everything
                # following it must too.
                rest.append(item)
                continue

            item.canv = getattr(self, 'canv', None)
            # Measure at full height so we know the item's TRUE size.
            _, ih = item.wrap(width, 72000)

            remaining = avail_height - used

            if ih <= remaining:
                # Item fits exactly — add to first without calling split().
                first.append(item)
                used += ih
            elif remaining > _FUZZ:
                # Item doesn't fit exactly.  Ask it to split.
                splits = item.split(width, remaining)
                n = len(splits)

                if n == 0:
                    # Truly unsplittable (e.g. image, drawing).
                    # Move the whole item to the next page.
                    rest.append(item)

                elif n == 1:
                    # split() decided the item fits whole — this happens when
                    # the item's measured height is only a hair over remaining
                    # due to floating-point rounding in wrap().
                    # Cap accumulated height at remaining so g1 never exceeds
                    # availHeight by a floating-point epsilon.
                    first.append(splits[0])
                    used += min(ih, remaining)

                else:
                    # Got 2+ pieces.  Sanity-check: first piece must fit.
                    _, sh = splits[0].wrap(width, 72000)
                    if sh <= remaining + _FUZZ:
                        first.append(splits[0])
                        # Clamp to remaining to prevent a floating-point overage
                        # from making g1 taller than availHeight.
                        used += min(sh, remaining)
                        rest.extend(splits[1:])
                    else:
                        # Corrupt/oversized first piece (can happen with certain
                        # RTL + emoji paragraph layouts).  Push whole item to rest.
                        rest.append(item)
            else:
                # No meaningful space left at all.
                rest.append(item)

        return (first, rest)

    # ── draw ──────────────────────────────────────────────────────────────────

    def draw(self):
        c = self.canv
        bw = self.border_width
        w = self._width
        h = self._height

        # ── container background ──────────────────────────────────────────────
        if self.bg_color:
            c.saveState()
            c.setFillColor(self.bg_color)
            _draw_rounded_rect(c, 0, 0, w, h, self._radii, fill=1, stroke=0)
            c.restoreState()

        # ── container border ─────────────────────────────────────────────────
        if self.border_color and bw > 0:
            c.saveState()
            c.setStrokeColor(self.border_color)
            c.setLineWidth(bw)
            half = bw / 2
            _draw_rounded_rect(
                c, half, half, w - bw, h - bw,
                self._radii, fill=0, stroke=1,
            )
            c.restoreState()

        # ── rows ─────────────────────────────────────────────────────────────
        # y starts at the inner top (just inside container padding + border)
        inner_top = h - self._padding[0] - bw
        pad_l = self._padding[3] + bw

        for row_idx, (row, rh) in enumerate(zip(self._cells, self._row_h)):
            inner_top -= rh
            row_bottom = inner_top  # bottom y of this row
            x = pad_l

            col_idx = 0
            for cell in row:
                if col_idx >= self._n_cols:
                    break
                span = cell.col_span
                cw = self._span_width(col_idx, span)

                self._draw_cell(c, cell, x, row_bottom, cw, rh)

                x += cw + self._col_gap
                col_idx += span

            inner_top -= self._row_gap

    # ── cell drawing ─────────────────────────────────────────────────────────

    def _draw_cell(self, c, cell: GridCell, x, y, w, h):
        """Draw one cell at canvas position *(x, y)* (bottom-left)."""
        bg = cell.bg_color if cell.bg_color is not None else self.cell_bg
        bc = cell.border_color if cell.border_color is not None else self.cell_border_color
        bw = cell.border_width if cell.border_width is not None else self.cell_border_width
        br = cell.border_radius if cell.border_radius is not None else self.cell_border_radius
        radii = _r4(br)

        if bg:
            c.saveState()
            c.setFillColor(bg)
            _draw_rounded_rect(c, x, y, w, h, radii, fill=1, stroke=0)
            c.restoreState()

        if bc and bw > 0:
            c.saveState()
            c.setStrokeColor(bc)
            c.setLineWidth(bw)
            half = bw / 2
            _draw_rounded_rect(c, x + half, y + half,
                                w - bw, h - bw, radii, fill=0, stroke=1)
            c.restoreState()

        cp = self._get_cell_pad(cell)
        content_x = x + cp[3]
        content_w = max(w - cp[1] - cp[3], 1.0)
        content_h = max(h - cp[0] - cp[2], 0.0)
        content_y_bottom = y + cp[2]

        self._draw_cell_content(c, cell, content_x, content_y_bottom, content_w, content_h)

    def _draw_cell_content(self, c, cell: GridCell, x, y_bot, w, h):
        """Draw a cell's content.  *(x, y_bot)* is the bottom-left of the
        content area; *(w, h)* are the available dimensions."""
        content = cell.content
        if content is None:
            return

        # Normalise to a flat list of Flowables
        items = []
        raw = content if isinstance(content, (list, tuple)) else [content]
        for item in raw:
            if isStr(item):
                from RTLReportLab.platypus import Paragraph
                from RTLReportLab.lib.styles import ParagraphStyle
                item = Paragraph(item, ParagraphStyle('_grid_tmp'))
            if isinstance(item, Flowable):
                items.append(item)

        if not items:
            return

        # Measure — set canv so RTL/shaping paragraphs can access it
        measured = []   # (flowable, height)
        total_content_h = 0.0
        for item in items:
            item.canv = c
            _, ih = item.wrap(w, max(h - total_content_h, 1.0))
            measured.append((item, ih))
            total_content_h += ih

        # Vertical alignment
        valign = (cell.valign or 'top').lower()
        if valign == 'middle':
            y_start = y_bot + (h + total_content_h) / 2
        elif valign == 'bottom':
            y_start = y_bot + total_content_h
        else:                            # top (default)
            y_start = y_bot + h

        # Draw top → bottom (y decreases)
        cy = y_start
        for item, ih in measured:
            cy -= ih
            item.drawOn(c, x, cy)
