# RTLReportLab

A fork of **ReportLab** with first-class **RTL / BiDi (Arabic)** support for PDF
generation — Arabic letter shaping (via `arabic-reshaper`), bidirectional
reordering (via `python-bidi`), color emoji rendering, and a few extra
flowables such as `Grid`.

> **Note:** This project is built on top of [ReportLab](https://www.reportlab.com).
> RTLReportLab re-packages the ReportLab toolkit and layers RTL/BiDi handling and
> additional helpers on top of it. All of ReportLab's own APIs
> (`canvas`, `platypus`, `pdfgen`, `pdfbase`, …) remain available under the
> `RTLReportLab` namespace.

---

## Installation

Install directly from GitHub with pip:

```bash
pip install git+https://github.com/nafeal3mri/RTLReportLab.git
```

To reinstall after an update (bypassing pip's cache):

```bash
pip install --force-reinstall --no-cache-dir git+https://github.com/nafeal3mri/RTLReportLab.git
```

Or from a local clone:

```bash
git clone https://github.com/nafeal3mri/RTLReportLab.git
cd RTLReportLab
pip install .          # or:  pip install -e .   (editable/dev install)
```

### Dependencies

Installed automatically by pip:

- `pillow >= 10.0.0`
- `python-bidi >= 0.4.2`
- `arabic-reshaper >= 3.0.0`
- `uharfbuzz >= 0.30.0`

### Arabic font

An Arabic-capable TrueType font (`NotoNaskhArabic.ttf`) ships **inside** the
package, so you can locate and register it without bundling your own:

```python
import os
import RTLReportLab
from RTLReportLab.pdfbase import pdfmetrics
from RTLReportLab.pdfbase.ttfonts import TTFont

font_path = os.path.join(os.path.dirname(RTLReportLab.__file__), 'NotoNaskhArabic.ttf')
pdfmetrics.registerFont(TTFont('ArabicFont', font_path))
```

---

## Usage

### `text_to_rl_markup`
 
Converts a plain text string containing **emojis** into ReportLab `Paragraph`
markup, replacing each emoji with an inline `<img>` tag rendered as a color PNG.
If the text has no emoji it is returned unchanged.

```python
from RTLReportLab.lib.emoji_utils import text_to_rl_markup

markup = text_to_rl_markup(text, font_size=12, valign='middle', rtl=False)
```

| Parameter   | Type   | Default    | Description                                                                 |
|-------------|--------|------------|-----------------------------------------------------------------------------|
| `text`      | str    | —          | Input text, may contain emoji.                                              |
| `font_size` | int    | `12`       | Emoji images are sized proportionally to this.                              |
| `valign`    | str    | `'middle'` | Vertical alignment of the emoji image relative to the text baseline.        |
| `rtl`       | bool   | `False`    | Set `True` for Arabic / RTL text so word order stays visually correct.      |

The returned string is fed to a `Paragraph`. For RTL text, pair it with a style
whose `wordWrap='RTL'` (which enables the bidi algorithm and automatic Arabic
reshaping).

### `Grid`

A grid/table flowable with rounded corners, per-cell styling,
and automatic page-overflow handling (it splits cleanly at row boundaries).

```python
from RTLReportLab.platypus.grid import Grid, GridCell
```

Key options:

| Option            | Description                                                                 |
|-------------------|-----------------------------------------------------------------------------|
| `data`            | 2D list of rows. Cells may be strings, `Flowable`s, or `GridCell` objects.  |
| `cols`            | Number of equal-width columns (or use `col_widths=[…]` for fixed widths).   |
| `gap`             | Spacing between cells (`row_gap` / `col_gap` for per-axis control).         |
| `cell_padding`    | Inner padding per cell (number, 2-tuple, or 4-tuple).                       |
| `bg_color`        | Container background color.                                                 |
| `border_color` / `border_width` | Container border.                                            |
| `border_radius`   | Corner radius — a single number, or `[TL, TR, BL, BR]` for mixed corners.   |
| `cell_bg`, `cell_border_color`, `cell_border_width`, `cell_border_radius` | Per-cell defaults. |
| `header_rows`     | Number of leading rows repeated after each page break.                      |

Use `GridCell(content, col_span=2, bg_color=..., valign='middle', …)` to
override styling for an individual cell or span multiple columns.

---

## Examples

### `text_to_rl_markup` — emoji + Arabic paragraph

```python
import os
import RTLReportLab
from RTLReportLab.platypus import SimpleDocTemplate, Paragraph
from RTLReportLab.lib.styles import ParagraphStyle
from RTLReportLab.lib.enums import TA_RIGHT
from RTLReportLab.lib.pagesizes import A4
from RTLReportLab.pdfbase import pdfmetrics
from RTLReportLab.pdfbase.ttfonts import TTFont
from RTLReportLab.lib.emoji_utils import text_to_rl_markup

# Register the bundled Arabic font
font_path = os.path.join(os.path.dirname(RTLReportLab.__file__), 'NotoNaskhArabic.ttf')
pdfmetrics.registerFont(TTFont('ArabicFont', font_path))

rtl_style = ParagraphStyle(
    'RTL',
    fontName='ArabicFont',
    fontSize=14,
    leading=24,
    alignment=TA_RIGHT,
    wordWrap='RTL',      # enables BiDi + automatic Arabic reshaping
)

text = "مرحبا بالعالم 👋 هذا مثال على النص العربي مع رموز تعبيرية 🚀"
markup = text_to_rl_markup(text, font_size=14, rtl=True)

doc = SimpleDocTemplate("emoji_rtl.pdf", pagesize=A4)
doc.build([Paragraph(markup, rtl_style)])
```

### `Grid` — styled table with rounded corners

```python
from RTLReportLab.platypus import SimpleDocTemplate
from RTLReportLab.platypus.grid import Grid, GridCell
from RTLReportLab.lib.pagesizes import A4
from RTLReportLab.lib import colors

grid = Grid(
    data=[
        ["Name", "Score"],
        ["Alice", "98"],
        ["Bob",   "82"],
        [GridCell("Total", col_span=1, bg_color=colors.whitesmoke), "180"],
    ],
    cols=2,
    gap=4,
    cell_padding=8,
    bg_color=colors.white,
    border_color=colors.lightgrey,
    border_width=1,
    border_radius=8,          # rounded container; use [TL,TR,BL,BR] for mixed
    header_rows=1,            # repeat the header row after each page break
)

doc = SimpleDocTemplate("grid.pdf", pagesize=A4)
doc.build([grid])
```

**Card-style** (a single rounded content box):

```python
from RTLReportLab.platypus import Paragraph
from RTLReportLab.lib.styles import getSampleStyleSheet

styles = getSampleStyleSheet()
card = Grid(
    data=[[Paragraph("Any flowable can go inside a Grid cell.", styles['Normal'])]],
    cols=1,
    cell_padding=16,
    bg_color=colors.white,
    border_color=colors.HexColor('#E1E8ED'),
    border_width=1,
    border_radius=12,
)
```

---

## Built on ReportLab

RTLReportLab is a fork of and is built using **[ReportLab](https://www.reportlab.com)**.
ReportLab is the underlying open-source PDF generation toolkit; this project
extends it with RTL/BiDi text handling and the additional flowables documented
above. Please refer to the official ReportLab documentation at
[reportlab.com](https://www.reportlab.com) for the full PDF/Platypus API.
