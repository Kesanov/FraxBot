"""Leaderboard and match-result card renderers."""

import asyncio

from config import FACTION_COLORS, faction_base, faction_emoji
from cards.model import _latinize, default_avatar
from cards.svg_base import (
    W, _esc, _lux_bg, _save, _FONT_FAMILY, render_text, render_engraved, render_small_caps,
    _cell, _GOLD_EDGE, _CELL_STROKE_W, RANK_COLORS,
    _OUTER_PAD, _HDR_VPAD, _CELL_OUTER_PAD,
)


def render_header(out_path, title="Frax arena Leaderboard", scale=1):
    h = 152
    out_w, out_h = 800, h * 800 // W
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{out_w}" height="{out_h}" '
        f'viewBox="0 0 {W} {h}" font-family="{_FONT_FAMILY}">'
        + _lux_bg()
        + _cell(_OUTER_PAD, _HDR_VPAD, W-2*_OUTER_PAD, h-2*_HDR_VPAD, 22, width=_CELL_STROKE_W*2)
        + render_text(int(W*0.2), h//2 + round(54 * 0.70 / 2), "🏆", 54, "#ffd54f", anchor="middle")
        + render_engraved(W//2, h//2, title, 54, "#ffd54f", small_caps=True)
        + render_text(int(W*0.8), h//2 + round(54 * 0.70 / 2), "🏆", 54, "#ffd54f", anchor="middle")
        + '</svg>'
    )
    return _save(svg, out_path, scale)


def render_rows(entries, out_path, scale=1):
    """Render a chunk of leaderboard rows (no header). `entries` keep their
    global `position`. Small labels are enlarged and bold for readability."""
    row_h = 95
    pad = _OUTER_PAD
    height = pad * 2 + row_h * len(entries)
    out_w = 800
    out_h = height * out_w // W
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{out_w}" height="{out_h}" '
        f'viewBox="0 0 {W} {height}" font-family="{_FONT_FAMILY}">',
        _lux_bg(),
    ]
    pos_color = {1: "#ffd54f", 2: "#7fd6e8", 3: "#cd7f32"}
    for idx, e in enumerate(entries):
        y = pad + idx * row_h
        cy = y + row_h // 2
        pos = e["position"]
        pc = pos_color.get(pos, "#8a80b0")
        parts.append(
            _cell(_CELL_OUTER_PAD, y+6, W-2*_CELL_OUTER_PAD, row_h-12, 16)
        )
        parts.append(render_text(72, cy+12, f"#{pos}", 36, pc, anchor="middle"))
        cid = f"clip_{pos}"
        parts.append(
            f'<clipPath id="{cid}"><circle cx="160" cy="{cy}" r="34"/></clipPath>'
            f'<circle cx="160" cy="{cy}" r="36" fill="none" '
            f'stroke="{pc if pos in pos_color else _GOLD_EDGE}" '
            f'stroke-opacity="{0.9 if pos in pos_color else 0.5}" stroke-width="2"/>'
            f'<image x="126" y="{cy-34}" width="68" height="68" '
            f'href="{_esc(e["avatar"])}" clip-path="url(#{cid})"/>'
        )
        name_x = 215
        name_col = pc if pos in pos_color else "#f2eefc"
        parts.append(
            render_text(name_x, cy-2, e["name"][:21], 30, name_col)
            + render_text(name_x, cy+26, e["rank"], 19,
                          RANK_COLORS.get(e["rank"], "#9a90c0"))
        )
        if pos in (1, 2, 3):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}[pos]
            parts.append(render_text(186, cy+38, medal, 39, "#ffd54f",
                                     anchor="middle"))
        cols = [
            (str(e["elo"]), "ELO", "#80d8ff"),
            (f'{e["winrate"]}%', "WINRATE", "#f2eefc"),
            (str(e["games"]), "GAMES", "#f2eefc"),
            (f'{e["wins"]}/{e["losses"]}', "W/L", "#f2eefc"),
        ]
        cx = W - 510
        for val, lab, col in cols:
            parts.append(
                render_text(cx, cy-2, val, 27, col, anchor="middle")
                + render_text(cx, cy+24, lab, 18, "#9a90c0", anchor="middle")
            )
            cx += 100
        streak = e.get("streak", "–")
        parts.append(render_text(cx, cy-2, streak, 27, "#ffab40", anchor="middle"))
        parts.append(render_text(cx, cy+24, "STREAK", 18, "#9a90c0", anchor="middle"))
    parts.append("</svg>")
    return _save("".join(parts), out_path, scale)


def render_faction_table(rows, out_path, title="Faction Winrate", scale=1):
    title_h = 64
    row_h = 64
    pad = 10
    height = title_h + row_h * len(rows) + pad
    out_w = 800
    out_h = height * out_w // W
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{out_w}" height="{out_h}" '
        f'viewBox="0 0 {W} {height}" font-family="{_FONT_FAMILY}">',
        f'<rect width="{W}" height="{height}" fill="#14101f"/>',
        render_small_caps(W//2, title_h // 2, title, 34, "#ffd54f"),
    ]
    for idx, r in enumerate(rows):
        y = title_h + idx * row_h
        cy = y + row_h // 2
        col = FACTION_COLORS.get(r["faction"], "#90a4ae")
        parts.append(
            _cell(_CELL_OUTER_PAD, y+5, W-2*_CELL_OUTER_PAD, row_h-10, 14, color=col)
            + render_text(45, cy+9, r["faction"], 26, col)
        )
        has = r["games"] > 0
        cols = [
            (f'{r["winrate"]}%' if has else "N/A", "WINRATE"),
            (str(r["games"]), "GAMES"),
            (f'{r["wins"]}/{r["losses"]}' if has else "N/A", "W/L"),
        ]
        cx = W - 300
        for val, lab in cols:
            parts.append(
                render_text(cx, cy-2, val, 24, "#f2eefc", anchor="middle")
                + render_text(cx, cy+20, lab, 16, "#9a90c0", anchor="middle")
            )
            cx += 100
    parts.append("</svg>")
    return _save("".join(parts), out_path, scale)


def render_result(winner, loser, delta, out_path,
                  winner_avatar=None, loser_avatar=None, scale=1):
    """Two stacked rows: winner on top, loser below. Icons show town/ultimate/class."""
    width = 900
    row_h = 124
    pad = 12
    height = pad * 2 + row_h * 2
    out_w, out_h = 800, height * 800 // width

    WIN_BORDER, LOSE_BORDER = "#ffd54f", "#9045CE"

    def row(y, p, avatar, border_col, result_emoji, elo_delta):
        avatar      = avatar or default_avatar(p["name"])
        faction_col = FACTION_COLORS.get(faction_base(p["faction"]), "#90a4ae")
        cls_emoji   = faction_emoji(p["faction"])
        p = {**p, "name": _latinize(p["name"]), "ultimate": _latinize(p["ultimate"])}
        cy  = y + row_h // 2
        acx, ar = 88, 46
        lx  = 210
        ex  = width - 160
        rx  = width - 80
        cid = f"clip_{y}"
        info = f'{faction_base(p["faction"])}  ·  {p["ultimate"]}'
        delta_txt = f'{"+" if elo_delta>=0 else ""}{elo_delta}'
        return (
            _cell(20, y, width-40, row_h-12, 18, color=border_col)
            + f'<clipPath id="{cid}"><circle cx="{acx}" cy="{cy}" r="{ar}"/></clipPath>'
            f'<circle cx="{acx}" cy="{cy}" r="{ar+3}" fill="none" stroke="{border_col}" stroke-width="3"/>'
            f'<image x="{acx-ar}" y="{cy-ar}" width="{ar*2}" height="{ar*2}" '
            f'href="{_esc(avatar)}" clip-path="url(#{cid})"/>'
            + render_text(140, cy+15, result_emoji, 44, "#f2eefc", anchor="middle")
            + render_text(lx, cy-8, p["name"][:30], 34, "#f2eefc")
            + render_text(lx, cy+28, info, 23, faction_col)
            + render_text(ex, cy+10, cls_emoji, 35, "#f2eefc", anchor="middle")
            + render_text(rx, cy-2, p["elo"], 42, "#f2eefc", anchor="middle")
            + render_text(rx, cy+30, delta_txt, 24,
                          "#66bb6a" if elo_delta >= 0 else "#ef5350",
                          anchor="middle")
        )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{out_w}" height="{out_h}" '
        f'viewBox="0 0 {width} {height}" font-family="{_FONT_FAMILY}">'
        + _lux_bg()
        + row(pad, winner, winner_avatar, WIN_BORDER, "🏆", delta)
        + row(pad + row_h, loser, loser_avatar, LOSE_BORDER, "💀", -delta)
        + "</svg>"
    )
    return _save(svg, out_path, scale)


def render_elo_curve(out_path, k=96, scale=2):
    """Line chart: ELO gained on a win / lost on a loss vs the rating gap
    (your ELO − opponent ELO), from -500 to +500."""
    width, height = 980, 560
    left, right, top, bot = 90, 40, 80, 80
    pw, ph = width - left - right, height - top - bot

    def X(d):
        return left + (d + 500) / 1000 * pw

    def Y(v):
        return top + ph - (v / 100) * ph

    def expected(d):
        return 1 / (1 + 10 ** (-d / 400))

    def poly(fn):
        pts = " ".join(f"{X(d):.1f},{Y(fn(d)):.1f}" for d in range(-500, 501, 20))
        return pts

    win = poly(lambda d: k * (1 - expected(d)))
    loss = poly(lambda d: k * expected(d))

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'font-family="{_FONT_FAMILY}">',
        f'<rect width="{width}" height="{height}" fill="#14101f"/>',
        render_text(width//2, 44, f"ELO change per game (K={k})", 30,
                    "#ffd54f", anchor="middle"),
    ]
    for v in (0, 25, 50, 75, 100):
        gy = Y(v)
        parts.append(
            f'<line x1="{left}" y1="{gy:.1f}" x2="{left+pw}" y2="{gy:.1f}" '
            f'stroke="#ffffff" stroke-opacity="0.08"/>'
            + render_text(left-12, f"{gy+6:.1f}", v, 18, "#9a90c0", anchor="end")
        )
    for d in (-500, -250, 0, 250, 500):
        gx = X(d)
        parts.append(
            f'<line x1="{gx:.1f}" y1="{top}" x2="{gx:.1f}" y2="{top+ph}" '
            f'stroke="#ffffff" stroke-opacity="0.08"/>'
            + render_text(f"{gx:.1f}", top+ph+30, f'{"+" if d>0 else ""}{d}', 18,
                          "#9a90c0", anchor="middle")
        )
    parts.append(
        render_text(left+pw//2, height-22, "Your ELO − Opponent ELO", 20,
                    "#c9a7ff", anchor="middle")
    )
    parts.append(f'<polyline points="{win}" fill="none" stroke="#66bb6a" stroke-width="4"/>')
    parts.append(f'<polyline points="{loss}" fill="none" stroke="#ef5350" stroke-width="4"/>')
    parts.append(
        f'<rect x="{left+20}" y="{top+10}" width="20" height="20" fill="#66bb6a"/>'
        + render_text(left+48, top+27, "If you win", 20, "#f2eefc")
        + f'<rect x="{left+20}" y="{top+40}" width="20" height="20" fill="#ef5350"/>'
        + render_text(left+48, top+57, "If you lose", 20, "#f2eefc")
    )
    parts.append("</svg>")
    return _save("".join(parts), out_path, scale)


async def render_header_async(out_path, title="Frax arena Leaderboard"):
    return await asyncio.to_thread(render_header, out_path, title)


async def render_rows_async(entries, out_path):
    return await asyncio.to_thread(render_rows, entries, out_path)


async def render_faction_table_async(rows, out_path):
    return await asyncio.to_thread(render_faction_table, rows, out_path)


async def render_result_async(winner, loser, delta, out_path, winner_avatar=None, loser_avatar=None):
    return await asyncio.to_thread(
        render_result, winner, loser, delta, out_path, winner_avatar, loser_avatar)
