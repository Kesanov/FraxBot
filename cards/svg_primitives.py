"""Layout constants and low-level SVG drawing helpers for stats cards."""

from cards.svg_base import (
    W, _esc, _GOLD_EDGE, render_text, render_text_outlined, render_winrate_outlined, render_engraved,
    _ULTIMATES_DIR, _TOWNS_DIR, _local_data_uri,
    _cell, _CELL_STROKE_W,
    _OUTER_PAD, _CELL_OUTER_PAD,
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
_S_FF_ROW_H = 90                                        # row height
_S_FF_H     = _S_CELL_PAD + _S_FC_COL_H + 4 * _S_FF_ROW_H + _S_CELL_PAD

_S_CCW     = _S_W_CONTENT // 3   # 320
_S_CCH     = 186   # base 146 + 2 * _S_CELL_PAD

_S_FRAX_TOWN_ISZ = round(_S_UISZ * 0.7)   # 60

_S_CELL_BG = 'fill="#ffffff" fill-opacity="0.05"'


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


def _d_stats(parts, cx, y_games, games, winrate, has, fg=14, fw=32):
    if not has:
        return
    wr_col = "#00e676" if winrate >= 50 else "#ff8a80"
    wr_luma = "#249b61" if winrate >= 50 else "#a22919"
    parts.append(
        render_winrate_outlined(cx, y_games, f"{winrate}%", fw, wr_col, stroke=wr_luma, sw=0.0, anchor="middle")
        + render_text(cx, y_games + fw - 11, f"{games}x", fg, "#c0b8d8", anchor="middle")
    )


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
    ty = y + _S_SUB_H // 2 + 7
    parts.append(
        render_text(W//2, ty, title, 15, "#c9a7ff", anchor="middle", italic=True)
    )


def _d_ult_cell(parts, col, row_idx, y, r, ult_imgs):
    x  = _S_CONTENT_X + col * _S_UCW
    cx = x + _S_UCW // 2
    ix = cx - _S_UISZ // 2
    _d_sq_img(parts, ult_imgs.get(r["ultimate"]), ix, y + _S_PAD, _S_UISZ, 12,
              _GOLD_EDGE, f"u{row_idx}_{col}", sw=0)
    yg = y + _S_PAD + _S_UISZ + 12 + 17
    _d_stats(parts, cx, yg, r["games"], r["winrate"], r["games"] > 0, fg=18, fw=36)


def _d_frax_row(parts, y, frax_rows, frax_icon, town_imgs):
    """9-column frax row: col 0 = summary (full icon), cols 1–8 = per-faction towns (70%)."""
    tf_games = sum(r["games"] for r in frax_rows)
    tf_wins  = sum(r.get("wins", 0) for r in frax_rows)
    tf_wr    = round(100 * tf_wins / tf_games) if tf_games else 0

    yg = y + _S_PAD + _S_UISZ + 12 + 17

    def _cell(col, img, isz, border_col, games, winrate):
        x  = _S_CONTENT_X + col * _S_UCW
        cx = x + _S_UCW // 2
        iy = y + _S_PAD + (_S_UISZ - isz) // 2
        ix = cx - isz // 2
        _d_sq_img(parts, img, ix, iy, isz, 12, border_col, f"frc{col}", sw=3, so=0.88)
        _d_stats(parts, cx, yg, games, winrate, games > 0, fg=18, fw=36)

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

    # --- column headers: faction town images ---
    for i, fac in enumerate(FACTIONS):
        cx  = data_x + i * _S_FC_CW + _S_FC_CW // 2
        ix  = cx - _S_FC_ISZT // 2
        iy  = content_y + (_S_FC_COL_H - _S_FC_ISZT) // 2
        col_c = FACTION_COLORS.get(fac, "#90a4ae")
        _d_sq_img(parts, town_imgs.get(fac), ix, iy, _S_FC_ISZT, 8,
                  col_c, f"fch{i}", sw=2, so=0.8)

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

        # row label: class image + name (or "All" text)
        lx = _S_CONTENT_X + (_S_FC_LBL - _S_FC_LSZT) // 2
        if is_all:
            parts.append(render_text(
                _S_CONTENT_X + _S_FC_LBL // 2, rcy + 8,
                "All", 22, "#c9a7ff", anchor="middle"))
        else:
            _d_sq_img(parts, cls_imgs.get(label), lx, rcy - _S_FC_LSZT // 2,
                      _S_FC_LSZT, 8, _GOLD_EDGE, f"fcl{j}", sw=0)

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
            if g > 0:
                wr_col = "#00e676" if wr >= 50 else "#ff8a80"
                wr_luma = "#b9f5d8" if wr >= 50 else "#ffc4bc"
                parts.append(
                    render_winrate_outlined(cx, rcy - 6, f"{wr}%", 36, wr_col, stroke=wr_luma, sw=0.0, anchor="middle")
                    + render_text(cx, rcy + 18, f"{g}x", 18, "#c0b8d8", anchor="middle")
                )

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

    Row r: diagonal cell (col r) shows FACTIONS[r] + FACTIONS[7-r] icons.
    col c > r: FACTIONS[r] vs FACTIONS[c]
    col c < r: FACTIONS[7-r] vs FACTIONS[7-c]
    """
    from config import FACTIONS

    data_x    = _S_CONTENT_X + _S_FF_LBL
    right_x   = W - _S_CONTENT_X
    content_y = y + _S_CELL_PAD
    data_y    = content_y + _S_FC_COL_H
    bottom_y  = y + _S_FF_H - _S_CELL_PAD

    def _col_cx(c):
        return data_x + c * _S_FF_CW + _S_FF_CW // 2

    def _cell_svg(cx, cy, fac_a, fac_b):
        cell = (ff_data.get(fac_a) or {}).get(fac_b, {})
        g  = cell.get("games", 0)
        wr = cell.get("winrate", 0)
        if g <= 0:
            return ""
        wr_col  = "#00e676" if wr >= 50 else "#ff8a80"
        wr_luma = "#249b61" if wr >= 50 else "#a22919"
        return (render_winrate_outlined(cx, cy + 4, f"{wr}%", 36, wr_col, stroke=wr_luma, sw=0.0, anchor="middle")
                + render_text(cx, cy + 25, f"{g}x", 18, "#c0b8d8", anchor="middle"))

    overlays = []  # rendered last so nothing covers them

    # top column headers — cols 0-2 get their paired faction as a 50% overlay
    for i, fac in enumerate(FACTIONS):
        cx    = _col_cx(i)
        isz   = _S_FC_ISZT
        ix    = cx - isz // 2
        iy    = content_y + (_S_FC_COL_H - isz) // 2
        col_c = FACTION_COLORS.get(fac, "#90a4ae")
        if i == 0:
            # col 0: show full-size paired faction (Stronghold) only
            paired = FACTIONS[7]
            col_p  = FACTION_COLORS.get(paired, "#90a4ae")
            _d_sq_img(parts, town_imgs.get(paired), ix, iy, isz, 8, col_p, f"ffch{i}", sw=2, so=0.8)
        elif i < 3:
            paired = FACTIONS[7 - i]
            col_p  = FACTION_COLORS.get(paired, "#90a4ae")
            _d_overlay_sq_img(parts, overlays, town_imgs.get(fac), town_imgs.get(paired),
                              ix, iy, isz, 8, col_c, col_p, f"ffch{i}")
        else:
            _d_sq_img(parts, town_imgs.get(fac), ix, iy, isz, 8, col_c, f"ffch{i}", sw=2, so=0.8)

    parts.append(
        f'<line x1="{_S_CONTENT_X}" y1="{data_y}" x2="{right_x}" y2="{data_y}" '
        f'stroke="{_GOLD_EDGE}" stroke-opacity="0.4" stroke-width="1"/>'
    )

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

        row_isz = round(_S_FC_ISZT * 0.7)

        # left row label — row 0 identifies fac_a (Haven), rows 1-3 identify fac_b
        lbl_fac = fac_a if r == 0 else fac_b
        lx      = _S_CONTENT_X + (_S_FF_LBL - row_isz) // 2
        col_c   = FACTION_COLORS.get(lbl_fac, "#90a4ae")
        _d_sq_img(parts, town_imgs.get(lbl_fac), lx, row_cy - row_isz // 2,
                  row_isz, 8, col_c, f"fflbl{r}", sw=2, so=0.8)

        for c in range(8):
            cx = _col_cx(c)
            if c == r and r > 0:
                sz    = row_isz
                ix    = cx - sz // 2
                iy    = row_cy - sz // 2
                col_a = FACTION_COLORS.get(fac_a, "#90a4ae")
                _d_sq_img(parts, town_imgs.get(fac_a), ix, iy, sz, 8, col_a, f"ffd{r}", sw=2, so=0.8)
            elif c > r:
                parts.append(_cell_svg(cx, row_cy, fac_a, FACTIONS[c]))
            else:
                parts.append(_cell_svg(cx, row_cy, fac_b, FACTIONS[7 - c]))

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
    has = r["games"] > 0
    _d_sq_img(parts, cls_imgs.get(r["class"]), ix, y + _S_PAD + _S_CELL_PAD, isz, 12,
              _GOLD_EDGE, f"cls{col}", sw=0)
    parts.append(render_text(tx, cy - 18, r["class"], 30, "#f2eefc"))
    if has:
        wr_col = "#00e676" if r["winrate"] >= 50 else "#ff8a80"
        wr_luma = "#b9f5d8" if r["winrate"] >= 50 else "#ffc4bc"
        parts.append(
            render_winrate_outlined(tx - 4, cy + 18, f'{r["winrate"]}%', 48, wr_col, stroke=wr_luma, sw=0.0, anchor="start")
            + render_text(tx, cy + 48, f'{r["games"]}x', 21, "#c0b8d8")
        )
    else:
        pass
