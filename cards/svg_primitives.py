"""Layout constants and low-level SVG drawing helpers for stats cards."""

import itertools

from cards.svg_base import (
    W, _esc, _GOLD_EDGE, render_text, render_winrate_outlined, render_engraved,
    _ULTIMATES_DIR, _TOWNS_DIR, _local_data_uri,
    _cell, _CELL_STROKE_W,
    _OUTER_PAD, _CELL_OUTER_PAD,
    text_cap_height,
)
from config import FACTION_COLORS

# ---------------------------------------------------------------------------
# Stats-card layout constants
# ---------------------------------------------------------------------------
_S_INSET   = _CELL_OUTER_PAD
_S_HDR_H   = 112
_S_GAP     = _OUTER_PAD
_S_PAD     = 10
_S_CELL_PAD = 20   # uniform padding inside section background cells (all sides)
_S_W_INNER   = W - 2 * _S_INSET          # 1000 — width of section background
_S_W_CONTENT = _S_W_INNER - 2 * _S_CELL_PAD  # 960 — content area inside padding
_S_CONTENT_X = _S_INSET + _S_CELL_PAD    # 50  — left edge of content area

_S_COLS_U  = 9
_S_UCW     = _S_W_CONTENT // _S_COLS_U   # 106
_S_UISZ    = _S_UCW - 2 * _S_PAD        # 86
_S_UCH     = 155

_S_FC_LBL   = 80                                  # row-label column width
_S_FC_CW    = (_S_W_CONTENT - _S_FC_LBL) // 8   # faction column width (~110)
_S_FC_COL_H = 100                                 # column-header row height (town images)
_S_FC_ROW_H = 68                                  # data row height (3 classes + all)
_S_FC_ISZT  = 88                                  # town image size in header
_S_FC_LSZT  = 60                                  # class image size in row label
_S_ALL_SEP_PAD = 10                               # extra gap around "All" separator
_S_FC_H     = _S_CELL_PAD + _S_FC_COL_H + 4 * _S_FC_ROW_H + 2 * _S_ALL_SEP_PAD + _S_CELL_PAD  # total

_S_FF_LBL   = _S_FC_LBL                                 # left label column width (same as fc grid)
_S_FF_CW    = (_S_W_CONTENT - _S_FF_LBL) // 8          # faction column width (~107)
_S_FF_ROW_H = 80                                        # row height
_S_FF_H     = _S_CELL_PAD + _S_FC_COL_H + 4 * _S_FF_ROW_H + _S_CELL_PAD

_S_CCW     = _S_W_CONTENT // 3   # 320
_S_CCH     = 186   # base 146 + 2 * _S_CELL_PAD

_S_FRAX_TOWN_ISZ = round(_S_UISZ * 0.7)   # 60

_S_MIN_GAMES = 1   # minimum games required to display a winrate


def _wr_colors(wr):
    """Return (fill, shadow) for a winrate value: red < 40% < green < 60% < gold."""
    if wr >= 61:
        return "#e1c807", "#a07800"
    if wr >= 40:
        return "#93d7b7", "#249b61"
    return "#ff8a80", "#a22919"


# ---------------------------------------------------------------------------
# Layout DSL — inline shapes: render_at(cx, top_y) where cx is center x
# ---------------------------------------------------------------------------

_clip_seq = itertools.count()


class Pad:
    """Fixed empty space."""
    def __init__(self, px: float):
        self.px = px
    def layout_h(self) -> float: return self.px
    def layout_w(self) -> float: return self.px
    def render_at(self, cx: float, top_y: float) -> str: return ""


class Text:
    """Single line of text; top_y is the cap-top, baseline is computed internally."""
    def __init__(self, content, size, fill, weight="700", anchor="middle", italic=False):
        self.content = str(content)
        self.size, self.fill = size, fill
        self.weight, self.anchor, self.italic = weight, anchor, italic
    def layout_h(self) -> float: return text_cap_height(self.size)
    def render_at(self, cx: float, top_y: float) -> str:
        return render_text(cx, top_y + self.layout_h(), self.content, self.size, self.fill,
                           weight=self.weight, anchor=self.anchor, italic=self.italic)


class Winrate:
    """Winrate text (large first digit); top_y is the cap-top."""
    def __init__(self, content, size, fill, stroke=None, sw=0.0, anchor="middle", x_offset=0):
        self.content = str(content)
        self.size, self.fill = size, fill
        self.stroke, self.sw, self.anchor = stroke, sw, anchor
        self.x_offset = x_offset
    def layout_h(self) -> float: return text_cap_height(self.size)
    def render_at(self, cx: float, top_y: float) -> str:
        return render_winrate_outlined(cx + self.x_offset, top_y + self.layout_h(), self.content, self.size, self.fill,
                                       stroke=self.stroke, sw=self.sw, anchor=self.anchor)


class Img:
    """Square image with optional border; top_y is the top edge."""
    def __init__(self, src, sz, rx=8, stroke=_GOLD_EDGE, sw=2, so=0.75):
        self.src, self.sz, self.rx = src, sz, rx
        self.stroke, self.sw, self.so = stroke, sw, so
    def layout_h(self) -> float: return self.sz
    def render_at(self, cx: float, top_y: float) -> str:
        canvas = SVGCanvas()
        canvas.sq_img(self.src, cx - self.sz / 2, top_y, self.sz, self.rx,
                      self.stroke, f"dsl{next(_clip_seq)}", sw=self.sw, so=self.so)
        return canvas.render()


class Stack:
    """Vertical stack of inline shapes, centered at render_at's cx.

    render_at(cx, top_y) renders top-aligned; render_centered(cx, cy) centers on cy.
    """
    def __init__(self, items: list, gap: float = 6):
        self.items, self.gap = items, gap

    def layout_h(self) -> float:
        return sum(i.layout_h() for i in self.items) + self.gap * (len(self.items) - 1)

    def render_at(self, cx: float, top_y: float) -> str:
        heights = [i.layout_h() for i in self.items]
        offsets = itertools.accumulate([0] + [h + self.gap for h in heights[:-1]])
        return "".join(item.render_at(cx, top_y + off) for item, off in zip(self.items, offsets))

    def render_centered(self, cx: float, cy: float) -> str:
        return self.render_at(cx, cy - self.layout_h() / 2)


def vstack(items: list, cx: float, cy: float, gap: float = 6) -> str:
    """Convenience wrapper: render a Stack centered at (cx, cy)."""
    return Stack(items, gap).render_centered(cx, cy)


def _hline(x1, y, x2, opacity=0.2, sw=1) -> str:
    return (f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" '
            f'stroke="{_GOLD_EDGE}" stroke-opacity="{opacity}" stroke-width="{sw}"/>')


def _vline(x, y1, y2, opacity=0.12, sw=1) -> str:
    return (f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" '
            f'stroke="{_GOLD_EDGE}" stroke-opacity="{opacity}" stroke-width="{sw}"/>')


def _wr_cell(g, wr):
    """Returns a list of DSL items for a winrate+games cell, or None if below min games."""
    if g < _S_MIN_GAMES:
        return None
    wr_col, wr_luma = _wr_colors(wr)
    return [Winrate(f"{wr}%", 36, wr_col, stroke=wr_luma), Text(f"{g}x", 18, "#c0b8d8")]


class Table:
    """Block-level labeled grid: one header row + N data rows with a label column.

    Unlike inline shapes, render_at(left_x, top_y) uses the left edge, not center x,
    since tables are always left-anchored to a content area.

    rows — list[list]: each row is [label, cells, strong_sep=False, top_pad=0]
           label: DSL item or None; cells: list of (DSL item | list | None)
    """
    def __init__(self, headers, rows, col_w, row_h, lbl_w, hdr_h):
        self.headers = headers
        self.rows    = rows
        self.col_w, self.row_h = col_w, row_h
        self.lbl_w,  self.hdr_h = lbl_w, hdr_h

    def layout_h(self) -> float:
        return self.hdr_h + sum(
            self.row_h + (row[3] if len(row) > 3 else 0)
            for row in self.rows
        )

    def layout_w(self) -> float:
        return self.lbl_w + self.col_w * len(self.headers)

    def render_at(self, left_x: float, top_y: float) -> str:
        x       = left_x
        y       = top_y
        data_x  = x + self.lbl_w
        right_x = x + self.layout_w()
        hdr_cy  = y + self.hdr_h // 2

        parts = [
            vstack([hdr] if not isinstance(hdr, list) else hdr,
                   data_x + i * self.col_w + self.col_w // 2, hdr_cy)
            for i, hdr in enumerate(self.headers) if hdr is not None
        ]

        data_y = y + self.hdr_h
        parts.append(_hline(x, data_y, right_x, opacity=0.4))

        cur_y = data_y
        for j, row in enumerate(self.rows):
            label      = row[0]
            cells      = row[1]
            strong_sep = row[2] if len(row) > 2 else False
            top_pad    = row[3] if len(row) > 3 else 0

            if j > 0:
                sep_y = cur_y + (top_pad // 2 if top_pad else 0)
                parts.append(_hline(x, sep_y, right_x,
                                    opacity=0.55 if strong_sep else 0.15,
                                    sw=2 if strong_sep else 1))

            row_y  = cur_y + top_pad
            row_cy = row_y + self.row_h // 2

            if label is not None:
                lbl_items = label if isinstance(label, list) else [label]
                parts.append(vstack(lbl_items, x + self.lbl_w // 2, row_cy))

            parts += [
                vstack(cell if isinstance(cell, list) else [cell],
                       data_x + i * self.col_w + self.col_w // 2, row_cy)
                for i, cell in enumerate(cells) if cell is not None
            ]

            cur_y = row_y + self.row_h

        bottom_y = cur_y
        parts.append(_vline(data_x, y, bottom_y, opacity=0.25))
        parts += [_vline(data_x + i * self.col_w, y, bottom_y, opacity=0.12)
                  for i in range(1, len(self.headers))]

        return "".join(parts)


# ---------------------------------------------------------------------------
# SVGCanvas — accumulates SVG fragments; card-level scene assembly
# ---------------------------------------------------------------------------

class SVGCanvas:
    def __init__(self):
        self.parts: list[str] = []
        self.y: float = 0           # outer cursor; advanced by section_header / section_bg
        self._section_y: float = 0  # top of current section body; set by section_bg
        # image dicts — populate before calling the methods that need them
        self.ult_imgs:  dict = {}
        self.town_imgs: dict = {}
        self.cls_imgs:  dict = {}
        self.frax_icon: str  = ""

    def render(self) -> str:
        return "".join(self.parts)

    def write(self, s: str) -> None:
        """Append a raw SVG string."""
        self.parts.append(s)

    def sq_img(self, img, x, y, sz, rx, stroke_col, clip_id, sw=2, so=0.75):
        self.parts.append(
            f'<clipPath id="{clip_id}"><rect x="{x}" y="{y}" width="{sz}" '
            f'height="{sz}" rx="{rx}"/></clipPath>'
        )
        if img:
            self.parts.append(
                f'<image x="{x}" y="{y}" width="{sz}" height="{sz}" href="{_esc(img)}" '
                f'clip-path="url(#{clip_id})" preserveAspectRatio="xMidYMid meet"/>'
            )
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{sz}" height="{sz}" rx="{rx}" fill="none" '
            f'stroke="{stroke_col}" stroke-opacity="{so}" stroke-width="{sw}"/>'
        )

    def section_header(self, title):
        pad = 8
        ih  = _S_HDR_H - 2 * pad
        cy  = self.y + pad + ih // 2
        self.parts.append(
            _cell(_S_INSET, self.y + pad, W - 2*_S_INSET, ih, 16, width=_CELL_STROKE_W * 2)
            + render_engraved(W//2, cy, title, 60, "#ffd54f", small_caps=True)
        )
        self.y += _S_HDR_H

    def section_bg(self, h):
        self._section_y = self.y
        self.parts.append(_cell(_S_INSET, self.y, _S_W_INNER, h, 18))
        self.y += h + _S_GAP

    def ult_cell(self, col, row_idx, r):
        y  = self._section_y + _S_CELL_PAD + row_idx * _S_UCH
        x  = _S_CONTENT_X + col * _S_UCW
        cx = x + _S_UCW // 2
        ix = cx - _S_UISZ // 2
        self.sq_img(self.ult_imgs.get(r["ultimate"]), ix, y + _S_PAD, _S_UISZ, 12,
                    _GOLD_EDGE, f"u{row_idx}_{col}", sw=0)
        cy = y + _S_PAD + _S_UISZ + (_S_UCH - _S_PAD - _S_UISZ) // 2
        if items := _wr_cell(r["games"], r["winrate"]):
            self.parts.append(Stack(items).render_centered(cx, cy))

    def frax_row(self, frax_rows):
        """9-column frax row: col 0 = summary (full icon), cols 1–8 = per-faction towns (70%)."""
        y        = self._section_y + _S_CELL_PAD + 2 * _S_UCH
        tf_games = sum(r["games"] for r in frax_rows)
        tf_wins  = sum(r.get("wins", 0) for r in frax_rows)
        tf_wr    = round(100 * tf_wins / tf_games) if tf_games else 0

        cy = y + _S_PAD + _S_UISZ + (_S_UCH - _S_PAD - _S_UISZ) // 2

        def _draw_cell(col, img, isz, border_col, games, winrate):
            x  = _S_CONTENT_X + col * _S_UCW
            cx = x + _S_UCW // 2
            iy = y + _S_PAD + (_S_UISZ - isz) // 2
            ix = cx - isz // 2
            self.sq_img(img, ix, iy, isz, 12, border_col, f"frc{col}", sw=3, so=0.88)
            if items := _wr_cell(games, winrate):
                self.parts.append(Stack(items).render_centered(cx, cy))

        _draw_cell(0, self.frax_icon, _S_UISZ, _GOLD_EDGE, tf_games, tf_wr)
        for i, r in enumerate(frax_rows):
            col_c = FACTION_COLORS.get(r["faction"], "#90a4ae")
            _draw_cell(i + 1, self.town_imgs.get(r["faction"]), _S_FRAX_TOWN_ISZ, col_c,
                       r["games"], r["winrate"])

    def faction_fc_grid(self, faction_rows, fc_data):
        """Table: rows = [Warrior, Warmage, Warlock, All], columns = 8 factions."""
        from config import FACTIONS, CLASSES
        fac_lookup = {r["faction"]: r for r in faction_rows}

        headers = [
            Img(self.town_imgs.get(fac), _S_FC_ISZT, rx=8, stroke=FACTION_COLORS.get(fac, "#90a4ae"), sw=2, so=0.8)
            for fac in FACTIONS
        ]
        rows = [
            [
                Text("All", 22, "#c9a7ff") if is_all else Img(self.cls_imgs.get(label), _S_FC_LSZT, rx=8, stroke=_GOLD_EDGE, sw=0),
                [
                    _wr_cell((r := fac_lookup.get(fac, {"games": 0, "winrate": 0}))["games"], r["winrate"])
                    if is_all else
                    _wr_cell((d := (fc_data.get(fac) or [{}, {}, {}])[j]).get("games", 0), d.get("winrate", 0))
                    for fac in FACTIONS
                ],
                is_all,
                2 * _S_ALL_SEP_PAD if is_all else 0,
            ]
            for j, (label, is_all) in enumerate([(cls, False) for cls in CLASSES] + [("All", True)])
        ]
        self.parts.append(
            Table(headers, rows, _S_FC_CW, _S_FC_ROW_H, _S_FC_LBL, _S_FC_COL_H)
            .render_at(_S_CONTENT_X, self._section_y + _S_CELL_PAD)
        )

    def faction_ff_grid(self, ff_data):
        """4 rows × 8 columns — all 28 unique faction matchups, no redundancy.

        Reversed column layout: diagonal at visual col 7-r for row r.
        Row r: diagonal cell (visual col 7-r) shows FACTIONS[r] + FACTIONS[7-r] icons.
        visual col vc < 7-r: FACTIONS[r] vs FACTIONS[7-vc]
        visual col vc > 7-r: FACTIONS[7-r] vs FACTIONS[vc]
        """
        from config import FACTIONS

        row_isz = round(_S_FC_ISZT * 0.7)

        def _faction_img(fac, sz=_S_FC_ISZT):
            return Img(self.town_imgs.get(fac), sz, rx=8, stroke=FACTION_COLORS.get(fac, "#90a4ae"), sw=2, so=0.8)

        def _ff_cell(fac_a, fac_b):
            d = (ff_data.get(fac_a) or {}).get(fac_b, {})
            return _wr_cell(d.get("games", 0), d.get("winrate", 0))

        headers = [_faction_img(FACTIONS[7 - i]) if i < 7 else None for i in range(8)]
        rows = [
            [
                _faction_img(FACTIONS[r], row_isz),
                [
                    _faction_img(FACTIONS[7 - r], row_isz) if vc == 7 - r else
                    _ff_cell(FACTIONS[r], FACTIONS[7 - vc]) if vc < 7 - r else
                    _ff_cell(FACTIONS[7 - r], FACTIONS[vc])
                    for vc in range(8)
                ],
            ]
            for r in range(4)
        ]
        self.parts.append(
            Table(headers, rows, _S_FF_CW, _S_FF_ROW_H, _S_FF_LBL, _S_FC_COL_H)
            .render_at(_S_CONTENT_X, self._section_y + _S_CELL_PAD)
        )

    def class_cell(self, col, r):
        x   = _S_CONTENT_X + col * _S_CCW
        isz = _S_CCH - 2 * _S_CELL_PAD - 2 * _S_PAD
        cy  = self._section_y + _S_CELL_PAD + (_S_CCH - 2 * _S_CELL_PAD) // 2
        ix  = x + _S_PAD
        tx  = ix + isz + 16

        self.parts.append(vstack([Img(self.cls_imgs.get(r["class"]), isz, rx=12, stroke=_GOLD_EDGE, sw=0)], ix + isz // 2, cy))

        if r["games"] >= _S_MIN_GAMES:
            wr_col, wr_luma = _wr_colors(r["winrate"])
            self.parts.append(vstack([
                Text(r["class"], 30, "#f2eefc", anchor="start"),
                Winrate(f'{r["winrate"]}%', 48, wr_col, stroke=wr_luma, anchor="start", x_offset=-5),
                Pad(2),
                Text(f'{r["games"]}x', 21, "#c0b8d8", anchor="start"),
            ], tx, cy))
        else:
            self.parts.append(vstack([Text(r["class"], 30, "#f2eefc", anchor="start")], tx, cy))
