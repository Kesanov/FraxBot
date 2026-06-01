"""Stats card renderers (ultimates, faction, class sections and composite)."""

import asyncio

from cards.svg_base import (
    W, _esc, _save, _FONT_FAMILY, _local_data_uri,
    _ULTIMATES_DIR, _TOWNS_DIR, _GOLD_EDGE,
    _CELL_FILL, _CELL_STROKE_W, _CELL_STROKE_OPACITY,
    _OUTER_PAD, _HDR_VPAD,
)
from cards.svg_primitives import (
    _S_GAP, _S_HDR_H, _S_UCH, _S_COLS_U, _S_FC_H, _S_CCH,
    _d_section_header, _d_section_bg,
    _d_ult_cell, _d_frax_row, _d_faction_fc_grid, _d_class_cell,
)


def render_stats_header_img(title, out_path, scale=1):
    """Render just one section header bar with equal top/bottom padding."""
    outer = _HDR_VPAD
    ih    = _S_HDR_H - 2 * _HDR_VPAD
    h     = ih + 2 * outer
    ow    = 800
    oh    = h * ow // W
    ty    = outer + ih // 2 + 22
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{ow}" height="{oh}" '
        f'viewBox="0 0 {W} {h}" font-family="{_FONT_FAMILY}">',
        f'<rect x="{_OUTER_PAD}" y="{outer}" width="{W - 2*_OUTER_PAD}" height="{ih}" rx="16" '
        f'{_CELL_FILL} stroke="{_GOLD_EDGE}" stroke-opacity="{_CELL_STROKE_OPACITY}" stroke-width="{_CELL_STROKE_W * 2}"/>'
        f'<text x="{W//2}" y="{ty}" font-size="60" font-weight="700" '
        f'fill="#ffd54f" text-anchor="middle">{_esc(title)}</text>',
    ]
    parts.append("</svg>")
    return _save("".join(parts), out_path, scale)


def render_ult_section_img(ult_rows, frax_rows, out_path, scale=1):
    """Render the Ultimate Winrate section body (no header bar)."""
    main_ult = [r for r in ult_rows if r["ultimate"] != "Frax Essence"]
    main_ult.sort(key=lambda r: r["games"], reverse=True)

    ult_imgs  = {r["ultimate"]: _local_data_uri(_ULTIMATES_DIR, r["ultimate"] + ".png")
                 for r in main_ult}
    frax_icon = _local_data_uri(_ULTIMATES_DIR, "Frax Essence.png")
    town_imgs = {f: _local_data_uri(_TOWNS_DIR, f + ".gif")
                 for f in {r["faction"] for r in frax_rows}}

    sec_h = _S_UCH * 3 + 5
    total_h = _S_GAP + sec_h + _S_GAP
    ow = 800
    oh = total_h * ow // W

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{ow}" height="{oh}" '
        f'viewBox="0 0 {W} {total_h}" font-family="{_FONT_FAMILY}">',

    ]
    y = _S_GAP
    _d_section_bg(parts, y, sec_h)

    ult_r1 = main_ult[:_S_COLS_U]
    ult_r2 = main_ult[_S_COLS_U: _S_COLS_U * 2]
    for i, r in enumerate(ult_r1):
        _d_ult_cell(parts, i, 0, y, r, ult_imgs)
    y += _S_UCH
    for i, r in enumerate(ult_r2):
        _d_ult_cell(parts, i, 1, y, r, ult_imgs)
    y += _S_UCH
    _d_frax_row(parts, y, frax_rows, frax_icon, town_imgs)

    parts.append("</svg>")
    return _save("".join(parts), out_path, scale)


def render_faction_section_img(faction_rows, fc_data, out_path, scale=1):
    """Render the Faction Winrate section body (no header bar)."""
    from config import FACTIONS, CLASSES

    town_imgs = {f: _local_data_uri(_TOWNS_DIR, f + ".gif") for f in FACTIONS}
    cls_imgs  = {c: _local_data_uri(_ULTIMATES_DIR, c + ".png") for c in CLASSES}

    total_h = _S_GAP + _S_FC_H + _S_GAP
    ow = 800
    oh = total_h * ow // W

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{ow}" height="{oh}" '
        f'viewBox="0 0 {W} {total_h}" font-family="{_FONT_FAMILY}">',

    ]
    y = _S_GAP
    _d_section_bg(parts, y, _S_FC_H)
    _d_faction_fc_grid(parts, y, faction_rows, fc_data, town_imgs, cls_imgs)

    parts.append("</svg>")
    return _save("".join(parts), out_path, scale)


def render_class_section_img(class_rows, out_path, scale=1):
    """Render the Class Winrate section body (no header bar)."""
    from config import CLASSES

    cls_imgs = {c: _local_data_uri(_ULTIMATES_DIR, c + ".png") for c in CLASSES}

    total_h = _S_GAP + _S_CCH + _S_GAP
    ow = 800
    oh = total_h * ow // W

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{ow}" height="{oh}" '
        f'viewBox="0 0 {W} {total_h}" font-family="{_FONT_FAMILY}">',

    ]
    y = _S_GAP
    _d_section_bg(parts, y, _S_CCH)
    for i, r in enumerate(class_rows):
        _d_class_cell(parts, i, y, r, cls_imgs)

    parts.append("</svg>")
    return _save("".join(parts), out_path, scale)


def render_stats_card(ult_rows, faction_rows, class_rows, frax_rows, fc_data,
                      out_path, scale=1):
    """Stats card: ultimates / faction winrate / class — all in one image."""
    from config import FACTIONS, CLASSES

    main_ult = [r for r in ult_rows if r["ultimate"] != "Frax Essence"]
    main_ult.sort(key=lambda r: r["games"], reverse=True)

    ult_imgs  = {r["ultimate"]: _local_data_uri(_ULTIMATES_DIR, r["ultimate"] + ".png")
                 for r in main_ult}
    frax_icon = _local_data_uri(_ULTIMATES_DIR, "Frax Essence.png")
    town_imgs = {f: _local_data_uri(_TOWNS_DIR, f + ".gif") for f in FACTIONS}
    cls_imgs  = {c: _local_data_uri(_ULTIMATES_DIR, c + ".png") for c in CLASSES}

    ult_sec_h = _S_UCH * 3 + 5

    total_h = (_S_GAP
               + _S_HDR_H + ult_sec_h
               + _S_GAP
               + _S_HDR_H + _S_FC_H
               + _S_GAP
               + _S_HDR_H + _S_CCH
               + _S_GAP)

    out_w = 800
    out_h = total_h * out_w // W

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{out_w}" height="{out_h}" '
        f'viewBox="0 0 {W} {total_h}" font-family="{_FONT_FAMILY}">',

    ]

    y = _S_GAP

    _d_section_header(parts, y, "Ultimate Winrate")
    y += _S_HDR_H
    _d_section_bg(parts, y, ult_sec_h)
    ult_r1 = main_ult[:_S_COLS_U]
    ult_r2 = main_ult[_S_COLS_U: _S_COLS_U * 2]
    for i, r in enumerate(ult_r1):
        _d_ult_cell(parts, i, 0, y, r, ult_imgs)
    y += _S_UCH
    for i, r in enumerate(ult_r2):
        _d_ult_cell(parts, i, 1, y, r, ult_imgs)
    y += _S_UCH
    _d_frax_row(parts, y, frax_rows, frax_icon, town_imgs)
    y += _S_UCH + _S_GAP

    _d_section_header(parts, y, "Faction Winrate")
    y += _S_HDR_H
    _d_section_bg(parts, y, _S_FC_H)
    _d_faction_fc_grid(parts, y, faction_rows, fc_data, town_imgs, cls_imgs)
    y += _S_FC_H + _S_GAP

    _d_section_header(parts, y, "Class Winrate")
    y += _S_HDR_H
    _d_section_bg(parts, y, _S_CCH)
    for i, r in enumerate(class_rows):
        _d_class_cell(parts, i, y, r, cls_imgs)

    parts.append("</svg>")
    return _save("".join(parts), out_path, scale)


async def render_stats_card_async(ult_rows, faction_rows, class_rows, frax_rows,
                                   fc_data, out_path):
    return await asyncio.to_thread(
        render_stats_card, ult_rows, faction_rows, class_rows,
        frax_rows, fc_data, out_path)
