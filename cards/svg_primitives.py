"""Layout constants and low-level SVG drawing helpers for stats cards."""

from cards.svg_base import (
    W, _esc, _GOLD_EDGE, render_text, render_engraved,
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
_S_W_INNER = W - 2 * _S_INSET   # 1000

_S_COLS_U  = 9
_S_UCW     = _S_W_INNER // _S_COLS_U   # 111
_S_UISZ    = _S_UCW - 2 * _S_PAD      # 91
_S_UCH     = 170

_S_FC_LBL   = 70
_S_FC_CW    = (_S_W_INNER - _S_FC_LBL) // 8   # 116
_S_FC_HDR   = 148
_S_FC_ISZT  = 66
_S_FC_ROW   = 72
_S_FC_RGAP  = 10
_S_FC_H     = _S_FC_HDR + _S_FC_RGAP + 3 * _S_FC_ROW   # 338

_S_CCW     = _S_W_INNER // 3   # 333
_S_CCH     = 146

_S_FRAX_TOWN_ISZ = round(_S_UISZ * 0.7)   # 64

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


def _d_stats(parts, cx, y_games, games, winrate, has, fg=13, fw=17):
    if not has:
        return
    wr_col = "#66bb6a" if winrate >= 50 else "#ef5350"
    parts.append(
        render_text(cx, y_games, f"{winrate}%", fw, wr_col, anchor="middle")
        + render_text(cx, y_games + fw + 4, f"{games}x", fg, "#c0b8d8",
                      anchor="middle")
    )


def _d_section_header(parts, y, title):
    pad = 8
    ih  = _S_HDR_H - 2 * pad
    ty  = y + pad + ih // 2 + 22
    parts.append(
        _cell(_S_INSET, y + pad, W - 2*_S_INSET, ih, 16, width=_CELL_STROKE_W * 2)
        + render_engraved(W//2, ty, title, 60, "#ffd54f")
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
    x  = _S_INSET + col * _S_UCW
    cx = x + _S_UCW // 2
    ix = cx - _S_UISZ // 2
    _d_sq_img(parts, ult_imgs.get(r["ultimate"]), ix, y + _S_PAD, _S_UISZ, 12,
              _GOLD_EDGE, f"u{row_idx}_{col}", sw=0)
    yg = y + _S_PAD + _S_UISZ + 12 + 17
    _d_stats(parts, cx, yg, r["games"], r["winrate"], r["games"] > 0, fg=17, fw=21)


def _d_frax_row(parts, y, frax_rows, frax_icon, town_imgs):
    """9-column frax row: col 0 = summary (full icon), cols 1–8 = per-faction towns (70%)."""
    tf_games = sum(r["games"] for r in frax_rows)
    tf_wins  = sum(r.get("wins", 0) for r in frax_rows)
    tf_wr    = round(100 * tf_wins / tf_games) if tf_games else 0

    yg = y + _S_PAD + _S_UISZ + 12 + 17

    def _cell(col, img, isz, border_col, games, winrate):
        x  = _S_INSET + col * _S_UCW
        cx = x + _S_UCW // 2
        iy = y + _S_PAD + (_S_UISZ - isz) // 2
        ix = cx - isz // 2
        _d_sq_img(parts, img, ix, iy, isz, 12, border_col, f"frc{col}", sw=3, so=0.88)
        _d_stats(parts, cx, yg, games, winrate, games > 0, fg=17, fw=21)

    _cell(0, frax_icon, _S_UISZ, _GOLD_EDGE, tf_games, tf_wr)
    for i, r in enumerate(frax_rows):
        col_c = FACTION_COLORS.get(r["faction"], "#90a4ae")
        _cell(i + 1, town_imgs.get(r["faction"]), _S_FRAX_TOWN_ISZ, col_c,
              r["games"], r["winrate"])


def _d_faction_fc_grid(parts, y, faction_rows, fc_data, town_imgs, cls_imgs):
    """Faction header (town + overall WR) fused with class × faction grid."""
    from config import FACTIONS, CLASSES
    fac_lookup = {r["faction"]: r for r in faction_rows}

    for i, fac in enumerate(FACTIONS):
        r     = fac_lookup.get(fac, {"games": 0, "winrate": 0})
        x     = _S_INSET + _S_FC_LBL + i * _S_FC_CW
        cx    = x + _S_FC_CW // 2
        col_c = FACTION_COLORS.get(fac, "#90a4ae")
        ix    = cx - _S_FC_ISZT // 2
        _d_sq_img(parts, town_imgs.get(fac), ix, y + 15, _S_FC_ISZT, 8,
                  col_c, f"fch{i}", sw=2, so=0.8)
        yg = y + 15 + _S_FC_ISZT + 3 + 18
        _d_stats(parts, cx, yg, r["games"], r["winrate"], r["games"] > 0, fg=18, fw=24)

    parts.append(
        f'<line x1="{_S_INSET}" y1="{y + _S_FC_HDR + _S_FC_RGAP}" '
        f'x2="{W - _S_INSET}" y2="{y + _S_FC_HDR + _S_FC_RGAP}" '
        f'stroke="{_GOLD_EDGE}" stroke-opacity="0.3" stroke-width="1"/>'
    )

    for j, cls in enumerate(CLASSES):
        ry  = y + _S_FC_HDR + _S_FC_RGAP + j * _S_FC_ROW
        rcy = ry + _S_FC_ROW // 2
        lsz = _S_FC_ROW - 10
        _d_sq_img(parts, cls_imgs.get(cls),
                  _S_INSET + (_S_FC_LBL - lsz) // 2, ry + 5,
                  lsz, 8, _GOLD_EDGE, f"fcl{j}", sw=0)
        parts.append(
            f'<line x1="{_S_INSET}" y1="{ry}" x2="{W - _S_INSET}" y2="{ry}" '
            f'stroke="{_GOLD_EDGE}" stroke-opacity="0.15" stroke-width="1"/>'
        )
        for i, fac in enumerate(FACTIONS):
            cx   = _S_INSET + _S_FC_LBL + i * _S_FC_CW + _S_FC_CW // 2
            cell = (fc_data.get(fac) or [{}, {}, {}])[j]
            has  = cell.get("games", 0) > 0
            wr   = cell.get("winrate", 0)
            g    = cell.get("games", 0)
            if has:
                wr_col = "#66bb6a" if wr >= 50 else "#ef5350"
                parts.append(
                    render_text(cx, rcy - 7, f"{wr}%", 24, wr_col, anchor="middle")
                    + render_text(cx, rcy + 23, f"{g}x", 17, "#c0b8d8",
                                  anchor="middle")
                )
            else:
                pass

    for i in range(1, 8):
        lx = _S_INSET + _S_FC_LBL + i * _S_FC_CW
        parts.append(
            f'<line x1="{lx}" y1="{y}" x2="{lx}" y2="{y + _S_FC_H}" '
            f'stroke="{_GOLD_EDGE}" stroke-opacity="0.12" stroke-width="1"/>'
        )
    lx = _S_INSET + _S_FC_LBL
    parts.append(
        f'<line x1="{lx}" y1="{y}" x2="{lx}" y2="{y + _S_FC_H}" '
        f'stroke="{_GOLD_EDGE}" stroke-opacity="0.2" stroke-width="1"/>'
    )


def _d_class_cell(parts, col, y, r, cls_imgs):
    x   = _S_INSET + col * _S_CCW
    cy  = y + _S_CCH // 2
    isz = _S_CCH - 2 * _S_PAD
    ix  = x + _S_PAD
    tx  = ix + isz + 16
    has = r["games"] > 0
    _d_sq_img(parts, cls_imgs.get(r["class"]), ix, y + _S_PAD, isz, 12,
              _GOLD_EDGE, f"cls{col}", sw=0)
    parts.append(render_text(tx, cy - 18, r["class"], 30, "#f2eefc"))
    if has:
        wr_col = "#66bb6a" if r["winrate"] >= 50 else "#ef5350"
        parts.append(
            render_text(tx, cy + 8, f'{r["winrate"]}%', 31, wr_col)
            + render_text(tx, cy + 40, f'{r["games"]}x', 20, "#c0b8d8")
        )
    else:
        pass
