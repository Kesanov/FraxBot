"""Layout constants and low-level SVG drawing helpers for stats cards."""

import itertools

from cards.svg_base import (
    W, _esc, _GOLD_EDGE, render_text, render_text_outlined, render_winrate_outlined, render_engraved,
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
_S_SUB_H   = 34
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
_S_ALL_SEP_PAD = 10                                                        # extra gap around "All" separator
_S_FC_H     = _S_CELL_PAD + _S_FC_COL_H + 4 * _S_FC_ROW_H + 2 * _S_ALL_SEP_PAD + _S_CELL_PAD  # total

_S_FF_LBL   = _S_FC_LBL                                 # left label column width (same as fc grid)
_S_FF_CW    = (_S_W_CONTENT - _S_FF_LBL) // 8          # faction column width (~107)
_S_FF_ROW_H = 80                                        # row height
_S_FF_H     = _S_CELL_PAD + _S_FC_COL_H + 4 * _S_FF_ROW_H + _S_CELL_PAD

_S_CCW     = _S_W_CONTENT // 3   # 320
_S_CCH     = 186   # base 146 + 2 * _S_CELL_PAD

_S_FRAX_TOWN_ISZ = round(_S_UISZ * 0.7)   # 60

_S_CELL_BG = 'fill="#ffffff" fill-opacity="0.05"'
_S_MIN_GAMES = 1   # minimum games required to display a winrate


def _wr_colors(wr):
    """Return (fill, shadow) for a winrate value: red < 40% < green < 60% < gold."""
    if wr >= 61:
        return "#e1c807", "#a07800"
    if wr >= 40:
        return "#93d7b7", "#249b61" # 00e676
    return "#ff8a80", "#a22919"


# ---------------------------------------------------------------------------
# Layout DSL
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
        parts: list[str] = []
        _d_sq_img(parts, self.src, cx - self.sz / 2, top_y, self.sz, self.rx,
                  self.stroke, f"dsl{next(_clip_seq)}", sw=self.sw, so=self.so)
        return "".join(parts)


def vstack(items: list, cx: float, cy: float, gap: float = 6) -> str:
    """Render items in a vertical stack centered at (cx, cy). Returns SVG string."""
    total_h = sum(i.layout_h() for i in items) + gap * (len(items) - 1)
    y = cy - total_h / 2
    out = []
    for item in items:
        out.append(item.render_at(cx, y))
        y += item.layout_h() + gap
    return "".join(out)


# ---------------------------------------------------------------------------
# Low-level drawing primitives
# ---------------------------------------------------------------------------

def _d_sq_img(parts, img, x, y, sz, rx, stroke_col, clip_id, sw=2, so=0.75):
    parts.append(
        f'<clipPath id="{clip_id}"><rect x="{x}" y="{y}" width="{sz}" '
        f'height="{sz}" rx="{rx}"/></clipPath>'
    )
    if img:
        parts.append(
            f'<image x="{x}" y="{y}" width="{sz}" height="{sz}" href="{_esc(img)}" '
            f'clip-path="url(#{clip_id})" preserveAspectRatio="xMidYMid meet"/>'
        )
    parts.append(
        f'<rect x="{x}" y="{y}" width="{sz}" height="{sz}" rx="{rx}" fill="none" '
        f'stroke="{stroke_col}" stroke-opacity="{so}" stroke-width="{sw}"/>'
    )


def _d_overlay_sq_img(parts, overlay_parts, img_main, img_overlay, x, y, sz, rx,
                      col_main, col_overlay, clip_id, sw=2, so=0.8):
    """Full-size main icon with a 50%-size overlay icon in the bottom-left corner.
    overlay_parts receives the small icon so callers can flush it last (on top of everything)."""
    _d_sq_img(parts, img_main, x, y, sz, rx, col_main, f"{clip_id}_m", sw=sw, so=so)
    osz = max(sz // 2, 8)
    ox  = x - osz // 2 + 15
    oy  = y + sz - osz // 2
    _d_sq_img(overlay_parts, img_overlay, ox, oy, osz, max(rx // 2, 2), col_overlay, f"{clip_id}_o", sw=1, so=0.9)


def _d_stats(parts, cx, cy, games, winrate, has, fg=14, fw=32):
    if not has:
        return
    wr_col, wr_luma = _wr_colors(winrate)
    parts.append(vstack([
        Winrate(f"{winrate}%", fw, wr_col, stroke=wr_luma),
        Text(f"{games}x", fg, "#c0b8d8"),
    ], cx, cy))


def _d_section_header(parts, y, title):
    pad = 8
    ih  = _S_HDR_H - 2 * pad
    cy  = y + pad + ih // 2
    parts.append(
        _cell(_S_INSET, y + pad, W - 2*_S_INSET, ih, 16, width=_CELL_STROKE_W * 2)
        + render_engraved(W//2, cy, title, 60, "#ffd54f", small_caps=True)
    )


def _d_section_bg(parts, y, h):
    parts.append(
        _cell(_S_INSET, y, _S_W_INNER, h, 18)
    )


def _d_sub_header(parts, y, title):
    parts.append(vstack([Text(title, 15, "#c9a7ff", weight="400", italic=True)], W // 2, y + _S_SUB_H // 2))


def _d_ult_cell(parts, col, row_idx, y, r, ult_imgs):
    x  = _S_CONTENT_X + col * _S_UCW
    cx = x + _S_UCW // 2
    ix = cx - _S_UISZ // 2
    _d_sq_img(parts, ult_imgs.get(r["ultimate"]), ix, y + _S_PAD, _S_UISZ, 12,
              _GOLD_EDGE, f"u{row_idx}_{col}", sw=0)
    cy = y + _S_PAD + _S_UISZ + (_S_UCH - _S_PAD - _S_UISZ) // 2
    _d_stats(parts, cx, cy, r["games"], r["winrate"], r["games"] > 0, fg=18, fw=36)


def _d_frax_row(parts, y, frax_rows, frax_icon, town_imgs):
    """9-column frax row: col 0 = summary (full icon), cols 1–8 = per-faction towns (70%)."""
    tf_games = sum(r["games"] for r in frax_rows)
    tf_wins  = sum(r.get("wins", 0) for r in frax_rows)
    tf_wr    = round(100 * tf_wins / tf_games) if tf_games else 0

    cy = y + _S_PAD + _S_UISZ + (_S_UCH - _S_PAD - _S_UISZ) // 2

    def _cell(col, img, isz, border_col, games, winrate):
        x  = _S_CONTENT_X + col * _S_UCW
        cx = x + _S_UCW // 2
        iy = y + _S_PAD + (_S_UISZ - isz) // 2
        ix = cx - isz // 2
        _d_sq_img(parts, img, ix, iy, isz, 12, border_col, f"frc{col}", sw=3, so=0.88)
        _d_stats(parts, cx, cy, games, winrate, games >= _S_MIN_GAMES, fg=18, fw=36)

    _cell(0, frax_icon, _S_UISZ, _GOLD_EDGE, tf_games, tf_wr)
    for i, r in enumerate(frax_rows):
        col_c = FACTION_COLORS.get(r["faction"], "#90a4ae")
        _cell(i + 1, town_imgs.get(r["faction"]), _S_FRAX_TOWN_ISZ, col_c,
              r["games"], r["winrate"])


def _d_faction_fc_grid(parts, y, faction_rows, fc_data, town_imgs, cls_imgs):
    """Table: rows = [Warrior, Warmage, Warlock, All], columns = 8 factions."""
    from config import FACTIONS, CLASSES
    fac_lookup = {r["faction"]: r for r in faction_rows}

    content_y = y + _S_CELL_PAD
    data_x    = _S_CONTENT_X + _S_FC_LBL
    right_x   = W - _S_CONTENT_X
    hdr_cy    = content_y + _S_FC_COL_H // 2

    # --- column headers: faction town images ---
    for i, fac in enumerate(FACTIONS):
        cx    = data_x + i * _S_FC_CW + _S_FC_CW // 2
        col_c = FACTION_COLORS.get(fac, "#90a4ae")
        parts.append(vstack([Img(town_imgs.get(fac), _S_FC_ISZT, rx=8, stroke=col_c, sw=2, so=0.8)], cx, hdr_cy))

    # separator below header
    sep_y = content_y + _S_FC_COL_H
    parts.append(
        f'<line x1="{_S_CONTENT_X}" y1="{sep_y}" x2="{right_x}" y2="{sep_y}" '
        f'stroke="{_GOLD_EDGE}" stroke-opacity="0.4" stroke-width="1"/>'
    )

    # --- data rows: 3 classes then "All" ---
    rows = [(cls, False) for cls in CLASSES] + [("All", True)]
    for j, (label, is_all) in enumerate(rows):
        base_ry = sep_y + j * _S_FC_ROW_H + (2 * _S_ALL_SEP_PAD if is_all else 0)
        ry  = base_ry
        rcy = ry + _S_FC_ROW_H // 2

        # row separator (skip first, already have header sep)
        if j > 0:
            sep_line_y = ry - (_S_ALL_SEP_PAD if is_all else 0)
            sep_op = "0.55" if is_all else "0.15"
            sep_sw = "2"   if is_all else "1"
            parts.append(
                f'<line x1="{_S_CONTENT_X}" y1="{sep_line_y}" x2="{right_x}" y2="{sep_line_y}" '
                f'stroke="{_GOLD_EDGE}" stroke-opacity="{sep_op}" stroke-width="{sep_sw}"/>'
            )

        # row label: class image or "All" text, centered in the label column
        lbl_cx = _S_CONTENT_X + _S_FC_LBL // 2
        if is_all:
            parts.append(vstack([Text("All", 22, "#c9a7ff")], lbl_cx, rcy))
        else:
            parts.append(vstack([Img(cls_imgs.get(label), _S_FC_LSZT, rx=8, stroke=_GOLD_EDGE, sw=0)], lbl_cx, rcy))

        # data cells
        for i, fac in enumerate(FACTIONS):
            cx = data_x + i * _S_FC_CW + _S_FC_CW // 2
            if is_all:
                r   = fac_lookup.get(fac, {"games": 0, "winrate": 0})
                g   = r["games"]
                wr  = r["winrate"]
            else:
                cell = (fc_data.get(fac) or [{}, {}, {}])[j]
                g    = cell.get("games", 0)
                wr   = cell.get("winrate", 0)
            if g >= _S_MIN_GAMES:
                wr_col, wr_luma = _wr_colors(wr)
                parts.append(vstack([
                    Winrate(f"{wr}%", 36, wr_col, stroke=wr_luma),
                    Text(f"{g}x", 18, "#c0b8d8"),
                ], cx, rcy))

    # vertical column separators
    parts.append(
        f'<line x1="{data_x}" y1="{content_y}" x2="{data_x}" y2="{y + _S_FC_H - _S_CELL_PAD}" '
        f'stroke="{_GOLD_EDGE}" stroke-opacity="0.25" stroke-width="1"/>'
    )
    for i in range(1, 8):
        lx = data_x + i * _S_FC_CW
        parts.append(
            f'<line x1="{lx}" y1="{content_y}" x2="{lx}" y2="{y + _S_FC_H - _S_CELL_PAD}" '
            f'stroke="{_GOLD_EDGE}" stroke-opacity="0.12" stroke-width="1"/>'
        )


def _d_faction_ff_grid(parts, y, ff_data, town_imgs):
    """4 rows × 8 columns — all 28 unique faction matchups, no redundancy.

    Reversed column layout: diagonal at visual col 7-r for row r.
    Row r: diagonal cell (visual col 7-r) shows FACTIONS[r] + FACTIONS[7-r] icons.
    visual col vc < 7-r: FACTIONS[r] vs FACTIONS[7-vc]
    visual col vc > 7-r: FACTIONS[7-r] vs FACTIONS[vc]
    """
    from config import FACTIONS

    data_x    = _S_CONTENT_X + _S_FF_LBL
    right_x   = W - _S_CONTENT_X
    content_y = y + _S_CELL_PAD
    data_y    = content_y + _S_FC_COL_H
    bottom_y  = y + _S_FF_H - _S_CELL_PAD
    hdr_cy    = content_y + _S_FC_COL_H // 2

    def _col_cx(c):
        return data_x + c * _S_FF_CW + _S_FF_CW // 2

    def _cell_svg(cx, cy, fac_a, fac_b):
        cell = (ff_data.get(fac_a) or {}).get(fac_b, {})
        g  = cell.get("games", 0)
        wr = cell.get("winrate", 0)
        if g < _S_MIN_GAMES:
            return ""
        wr_col, wr_luma = _wr_colors(wr)
        return vstack([
            Winrate(f"{wr}%", 36, wr_col, stroke=wr_luma),
            Text(f"{g}x", 18, "#c0b8d8"),
        ], cx, cy)

    overlays = []  # rendered last so nothing covers them

    # top column headers — reversed order; col 7 is left empty (diagonal shown in data rows)
    for i in range(7):
        fac   = FACTIONS[7 - i]
        cx    = _col_cx(i)
        col_c = FACTION_COLORS.get(fac, "#90a4ae")
        parts.append(vstack([Img(town_imgs.get(fac), _S_FC_ISZT, rx=8, stroke=col_c, sw=2, so=0.8)], cx, hdr_cy))

    parts.append(
        f'<line x1="{_S_CONTENT_X}" y1="{data_y}" x2="{right_x}" y2="{data_y}" '
        f'stroke="{_GOLD_EDGE}" stroke-opacity="0.4" stroke-width="1"/>'
    )

    row_isz = round(_S_FC_ISZT * 0.7)

    for r in range(4):
        row_y  = data_y + r * _S_FF_ROW_H
        row_cy = row_y + _S_FF_ROW_H // 2

        if r > 0:
            parts.append(
                f'<line x1="{_S_CONTENT_X}" y1="{row_y}" x2="{right_x}" y2="{row_y}" '
                f'stroke="{_GOLD_EDGE}" stroke-opacity="0.2" stroke-width="1"/>'
            )

        fac_a = FACTIONS[r]
        fac_b = FACTIONS[7 - r]

        # left row label
        lbl_cx = _S_CONTENT_X + _S_FF_LBL // 2
        col_c  = FACTION_COLORS.get(fac_a, "#90a4ae")
        parts.append(vstack([Img(town_imgs.get(fac_a), row_isz, rx=8, stroke=col_c, sw=2, so=0.8)], lbl_cx, row_cy))

        for vc in range(8):
            cx = _col_cx(vc)
            if vc == 7 - r:
                # diagonal cell: faction icon for the paired faction
                col_b = FACTION_COLORS.get(fac_b, "#90a4ae")
                parts.append(vstack([Img(town_imgs.get(fac_b), row_isz, rx=8, stroke=col_b, sw=2, so=0.8)], cx, row_cy))
            elif vc < 7 - r:
                parts.append(_cell_svg(cx, row_cy, fac_a, FACTIONS[7 - vc]))
            else:
                parts.append(_cell_svg(cx, row_cy, fac_b, FACTIONS[vc]))

    # vertical separator between label and data
    parts.append(
        f'<line x1="{data_x}" y1="{content_y}" x2="{data_x}" y2="{bottom_y}" '
        f'stroke="{_GOLD_EDGE}" stroke-opacity="0.25" stroke-width="1"/>'
    )
    for i in range(1, 8):
        lx = data_x + i * _S_FF_CW
        parts.append(
            f'<line x1="{lx}" y1="{content_y}" x2="{lx}" y2="{bottom_y}" '
            f'stroke="{_GOLD_EDGE}" stroke-opacity="0.12" stroke-width="1"/>'
        )

    # flush overlays on top of everything
    parts.extend(overlays)


def _d_class_cell(parts, col, y, r, cls_imgs):
    x   = _S_CONTENT_X + col * _S_CCW
    isz = _S_CCH - 2 * _S_CELL_PAD - 2 * _S_PAD
    cy  = y + _S_CELL_PAD + (_S_CCH - 2 * _S_CELL_PAD) // 2
    ix  = x + _S_PAD
    tx  = ix + isz + 16
    has = r["games"] >= _S_MIN_GAMES

    # image centered vertically on the left
    parts.append(vstack([Img(cls_imgs.get(r["class"]), isz, rx=12, stroke=_GOLD_EDGE, sw=0)], ix + isz // 2, cy))

    # class name + stats stacked on the right
    if has:
        wr_col, wr_luma = _wr_colors(r["winrate"])
        parts.append(vstack([
            Text(r["class"], 30, "#f2eefc", anchor="start"),
            Winrate(f'{r["winrate"]}%', 48, wr_col, stroke=wr_luma, anchor="start", x_offset=-5),
            Pad(2),
            Text(f'{r["games"]}x', 21, "#c0b8d8", anchor="start"),
        ], tx, cy))
    else:
        parts.append(vstack([Text(r["class"], 30, "#f2eefc", anchor="start")], tx, cy))
