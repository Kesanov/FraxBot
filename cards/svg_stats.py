"""Stats card renderers (ultimates, faction, class sections and composite)."""

import asyncio

from cards.svg_base import (
    W, _save, _FONT_FAMILY, render_text, render_engraved, _local_data_uri,
    _ULTIMATES_DIR, _TOWNS_DIR,
    _cell, _CELL_STROKE_W,
    _OUTER_PAD, _HDR_VPAD,
)
from cards.svg_primitives import (
    SVGCanvas,
    _S_GAP, _S_HDR_H, _S_UCH, _S_COLS_U, _S_FC_H, _S_FF_H, _S_CCH, _S_CELL_PAD,
)


def render_stats_header_img(title, out_path, scale=1):
    """Render just one section header bar with equal top/bottom padding."""
    outer = _HDR_VPAD
    ih    = _S_HDR_H - 2 * _HDR_VPAD
    h     = ih + 2 * outer
    ow    = 800
    oh    = h * ow // W
    cy    = outer + ih // 2
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{ow}" height="{oh}" '
        f'viewBox="0 0 {W} {h}" font-family="{_FONT_FAMILY}">'
        + _cell(_OUTER_PAD, outer, W - 2*_OUTER_PAD, ih, 16, width=_CELL_STROKE_W * 2)
        + render_engraved(W//2, cy, title, 60, "#ffd54f", small_caps=True)
        + "</svg>"
    )
    return _save(svg, out_path, scale)


def render_ult_section_img(ult_rows, frax_rows, out_path, scale=1):
    """Render the Ultimate Winrate section body (no header bar)."""
    main_ult = [r for r in ult_rows if r["ultimate"] != "Frax Essence"]
    main_ult.sort(key=lambda r: r["games"], reverse=True)

    sec_h   = _S_UCH * 3 + 5 + 2 * _S_CELL_PAD
    total_h = _S_GAP + sec_h + _S_GAP
    ow = 800
    oh = total_h * ow // W

    canvas = SVGCanvas()
    canvas.ult_imgs  = {r["ultimate"]: _local_data_uri(_ULTIMATES_DIR, r["ultimate"] + ".png") for r in main_ult}
    canvas.frax_icon = _local_data_uri(_ULTIMATES_DIR, "Frax Essence.png")
    canvas.town_imgs = {f: _local_data_uri(_TOWNS_DIR, f + ".gif") for f in {r["faction"] for r in frax_rows}}
    canvas.y = _S_GAP

    canvas.write(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{ow}" height="{oh}" '
        f'viewBox="0 0 {W} {total_h}" font-family="{_FONT_FAMILY}">'
    )
    canvas.section_bg(sec_h)
    for i, r in enumerate(main_ult[:_S_COLS_U]):
        canvas.ult_cell(i, 0, r)
    for i, r in enumerate(main_ult[_S_COLS_U: _S_COLS_U * 2]):
        canvas.ult_cell(i, 1, r)
    canvas.frax_row(frax_rows)
    canvas.write("</svg>")
    return _save(canvas.render(), out_path, scale)


def render_faction_section_img(faction_rows, fc_data, out_path, scale=1):
    """Render the Faction Winrate section body (no header bar)."""
    from config import FACTIONS, CLASSES

    total_h = _S_GAP + _S_FC_H + _S_GAP
    ow = 800
    oh = total_h * ow // W

    canvas = SVGCanvas()
    canvas.town_imgs = {f: _local_data_uri(_TOWNS_DIR, f + ".gif") for f in FACTIONS}
    canvas.cls_imgs  = {c: _local_data_uri(_ULTIMATES_DIR, c + ".png") for c in CLASSES}
    canvas.y = _S_GAP

    canvas.write(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{ow}" height="{oh}" '
        f'viewBox="0 0 {W} {total_h}" font-family="{_FONT_FAMILY}">'
    )
    canvas.section_bg(_S_FC_H)
    canvas.faction_fc_grid(faction_rows, fc_data)
    canvas.write("</svg>")
    return _save(canvas.render(), out_path, scale)


def render_faction_ff_section_img(ff_data, out_path, scale=1):
    """Render the Faction × Faction winrate section body (no header bar)."""
    from config import FACTIONS

    total_h = _S_GAP + _S_FF_H + _S_GAP
    ow = 800
    oh = total_h * ow // W

    canvas = SVGCanvas()
    canvas.town_imgs = {f: _local_data_uri(_TOWNS_DIR, f + ".gif") for f in FACTIONS}
    canvas.y = _S_GAP

    canvas.write(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{ow}" height="{oh}" '
        f'viewBox="0 0 {W} {total_h}" font-family="{_FONT_FAMILY}">'
    )
    canvas.section_bg(_S_FF_H)
    canvas.faction_ff_grid(ff_data)
    canvas.write("</svg>")
    return _save(canvas.render(), out_path, scale)


def render_class_section_img(class_rows, out_path, scale=1):
    """Render the Class Winrate section body (no header bar)."""
    from config import CLASSES

    total_h = _S_GAP + _S_CCH + _S_GAP
    ow = 800
    oh = total_h * ow // W

    canvas = SVGCanvas()
    canvas.cls_imgs = {c: _local_data_uri(_ULTIMATES_DIR, c + ".png") for c in CLASSES}
    canvas.y = _S_GAP

    canvas.write(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{ow}" height="{oh}" '
        f'viewBox="0 0 {W} {total_h}" font-family="{_FONT_FAMILY}">'
    )
    canvas.section_bg(_S_CCH)
    for i, r in enumerate(class_rows):
        canvas.class_cell(i, r)
    canvas.write("</svg>")
    return _save(canvas.render(), out_path, scale)


def render_stats_card(ult_rows, faction_rows, class_rows, frax_rows, fc_data,
                      out_path, scale=1):
    """Stats card: ultimates / faction winrate / class — all in one image."""
    from config import FACTIONS, CLASSES

    main_ult = [r for r in ult_rows if r["ultimate"] != "Frax Essence"]
    main_ult.sort(key=lambda r: r["games"], reverse=True)

    ult_sec_h = _S_UCH * 3 + 5 + 2 * _S_CELL_PAD
    total_h   = _S_GAP + _S_HDR_H + ult_sec_h + _S_GAP + _S_HDR_H + _S_FC_H + _S_GAP + _S_HDR_H + _S_CCH + _S_GAP
    out_w = 800
    out_h = total_h * out_w // W

    canvas = SVGCanvas()
    canvas.ult_imgs  = {r["ultimate"]: _local_data_uri(_ULTIMATES_DIR, r["ultimate"] + ".png") for r in main_ult}
    canvas.frax_icon = _local_data_uri(_ULTIMATES_DIR, "Frax Essence.png")
    canvas.town_imgs = {f: _local_data_uri(_TOWNS_DIR, f + ".gif") for f in FACTIONS}
    canvas.cls_imgs  = {c: _local_data_uri(_ULTIMATES_DIR, c + ".png") for c in CLASSES}
    canvas.y = _S_GAP

    canvas.write(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{out_w}" height="{out_h}" '
        f'viewBox="0 0 {W} {total_h}" font-family="{_FONT_FAMILY}">'
    )

    canvas.section_header("Ultimate winrate")
    canvas.section_bg(ult_sec_h)
    for i, r in enumerate(main_ult[:_S_COLS_U]):
        canvas.ult_cell(i, 0, r)
    for i, r in enumerate(main_ult[_S_COLS_U: _S_COLS_U * 2]):
        canvas.ult_cell(i, 1, r)
    canvas.frax_row(frax_rows)

    canvas.section_header("Faction winrate")
    canvas.section_bg(_S_FC_H)
    canvas.faction_fc_grid(faction_rows, fc_data)

    canvas.section_header("Class winrate")
    canvas.section_bg(_S_CCH)
    for i, r in enumerate(class_rows):
        canvas.class_cell(i, r)

    canvas.write("</svg>")
    return _save(canvas.render(), out_path, scale)


async def render_stats_card_async(ult_rows, faction_rows, class_rows, frax_rows,
                                   fc_data, out_path):
    return await asyncio.to_thread(
        render_stats_card, ult_rows, faction_rows, class_rows,
        frax_rows, fc_data, out_path)
