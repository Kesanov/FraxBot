"""Leaderboard and match-result card renderers."""

import asyncio

from config import FACTION_COLORS, faction_base, faction_emoji
from cards.model import _latinize, default_avatar
from cards.svg_base import (
    W, _esc, _lux_bg, _save, _FONT_FAMILY, _EMOJI_FAMILY,
    _CELL_FILL, _GOLD_EDGE, _CELL_STROKE_W, _CELL_STROKE_OPACITY, RANK_COLORS,
)


def render_header(out_path, title="Frax Arena Top12", scale=1):
    h = 152
    out_w, out_h = 800, h * 800 // W
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{out_w}" height="{out_h}" '
        f'viewBox="0 0 {W} {h}" font-family="{_FONT_FAMILY}">'
        + _lux_bg()
        + f'<rect x="20" y="16" width="{W-40}" height="{h-32}" rx="22" '
          f'{_CELL_FILL} stroke="{_GOLD_EDGE}" stroke-opacity="{_CELL_STROKE_OPACITY}" stroke-width="{_CELL_STROKE_W*2}"/>'
        + f'<text x="{int(W*0.2)}" y="{h//2+18}" font-size="54" font-weight="700" font-family="{_EMOJI_FAMILY}" '
          f'fill="#ffd54f" text-anchor="middle">🏆</text>'
        + f'<text x="{W//2}" y="{h//2+13}" font-size="54" font-weight="700" '
          f'fill="#ffd54f" text-anchor="middle">{_esc(title)}</text>'
        + f'<text x="{int(W*0.8)}" y="{h//2+18}" font-size="54" font-weight="700" font-family="{_EMOJI_FAMILY}" '
          f'fill="#ffd54f" text-anchor="middle">🏆</text>'
        + '</svg>'
    )
    return _save(svg, out_path, scale)


def render_rows(entries, out_path, scale=1):
    """Render a chunk of leaderboard rows (no header). `entries` keep their
    global `position`. Small labels are enlarged and bold for readability."""
    row_h = 95
    pad = 5
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
            f'<rect x="20" y="{y+6}" width="{W-40}" height="{row_h-12}" rx="16" '
            f'{_CELL_FILL} stroke="{_GOLD_EDGE}" '
            f'stroke-opacity="{_CELL_STROKE_OPACITY}" stroke-width="{_CELL_STROKE_W}"/>'
        )
        parts.append(
            f'<text x="72" y="{cy+12}" font-size="36" font-weight="700" '
            f'fill="{pc}" text-anchor="middle">#{pos}</text>'
        )
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
            f'<text x="{name_x}" y="{cy-2}" font-size="30" font-weight="700" '
            f'fill="{name_col}">{_esc(e["name"][:21])}</text>'
            f'<text x="{name_x}" y="{cy+26}" font-size="19" font-weight="700" '
            f'fill="{RANK_COLORS.get(e["rank"], "#9a90c0")}">{_esc(e["rank"])}</text>'
        )
        if pos in (1, 2, 3):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}[pos]
            parts.append(
                f'<text x="186" y="{cy+38}" font-size="39" font-weight="700" '
                f'font-family="{_EMOJI_FAMILY}" text-anchor="middle">{medal}</text>'
            )
        cols = [
            (str(e["elo"]), "ELO", "#80d8ff"),
            (f'{e["winrate"]}%', "WINRATE", "#f2eefc"),
            (str(e["games"]), "GAMES", "#f2eefc"),
            (f'{e["wins"]}/{e["losses"]}', "W/L", "#f2eefc"),
        ]
        cx = W - 510
        for val, lab, col in cols:
            parts.append(
                f'<text x="{cx}" y="{cy-2}" font-size="27" font-weight="700" '
                f'fill="{col}" text-anchor="middle">{_esc(val)}</text>'
                f'<text x="{cx}" y="{cy+24}" font-size="18" font-weight="700" '
                f'fill="#9a90c0" text-anchor="middle">{lab}</text>'
            )
            cx += 100
        streak = e.get("streak", "–")
        if len(streak) > 1:
            parts.append(
                f'<text x="{cx-14}" y="{cy-2}" font-size="27" font-weight="700" '
                f'font-family="{_EMOJI_FAMILY}" fill="#ffab40" text-anchor="middle">{_esc(streak[0])}</text>'
                f'<text x="{cx+14}" y="{cy-2}" font-size="27" font-weight="700" '
                f'fill="#ffab40" text-anchor="middle">{_esc(streak[1:])}</text>'
            )
        else:
            parts.append(
                f'<text x="{cx}" y="{cy-2}" font-size="27" font-weight="700" '
                f'fill="#ffab40" text-anchor="middle">{_esc(streak)}</text>'
            )
        parts.append(
            f'<text x="{cx}" y="{cy+24}" font-size="18" font-weight="700" '
            f'fill="#9a90c0" text-anchor="middle">STREAK</text>'
        )
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
        f'<text x="40" y="46" font-size="34" font-weight="700" fill="#ffd54f">'
        f'{_esc(title)}</text>',
    ]
    for idx, r in enumerate(rows):
        y = title_h + idx * row_h
        cy = y + row_h // 2
        col = FACTION_COLORS.get(r["faction"], "#90a4ae")
        parts.append(
            f'<rect x="20" y="{y+5}" width="{W-40}" height="{row_h-10}" rx="14" '
            f'{_CELL_FILL} stroke="{col}" stroke-opacity="1" stroke-width="4"/>'
            f'<text x="45" y="{cy+9}" font-size="26" font-weight="700" '
            f'fill="{col}">{_esc(r["faction"])}</text>'
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
                f'<text x="{cx}" y="{cy-2}" font-size="24" font-weight="700" '
                f'fill="#f2eefc" text-anchor="middle">{_esc(val)}</text>'
                f'<text x="{cx}" y="{cy+20}" font-size="16" font-weight="700" '
                f'fill="#9a90c0" text-anchor="middle">{lab}</text>'
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
        info = f'{_esc(faction_base(p["faction"]))}  ·  {_esc(p["ultimate"])}'
        return (
            f'<rect x="20" y="{y}" width="{width-40}" height="{row_h-12}" rx="18" '
            f'{_CELL_FILL} stroke="{border_col}" '
            f'stroke-opacity="{_CELL_STROKE_OPACITY}" stroke-width="{_CELL_STROKE_W}"/>'
            f'<clipPath id="{cid}"><circle cx="{acx}" cy="{cy}" r="{ar}"/></clipPath>'
            f'<circle cx="{acx}" cy="{cy}" r="{ar+3}" fill="none" stroke="{border_col}" stroke-width="3"/>'
            f'<image x="{acx-ar}" y="{cy-ar}" width="{ar*2}" height="{ar*2}" '
            f'href="{_esc(avatar)}" clip-path="url(#{cid})"/>'
            f'<text x="140" y="{cy+15}" font-size="44" font-weight="700" '
            f'font-family="{_EMOJI_FAMILY}" text-anchor="middle">{result_emoji}</text>'
            f'<text x="{lx}" y="{cy-8}" font-size="34" font-weight="700" '
            f'fill="#f2eefc">{_esc(p["name"][:30])}</text>'
            f'<text x="{lx}" y="{cy+28}" font-size="23" font-weight="700" '
            f'fill="{faction_col}">{info}</text>'
            f'<text x="{ex}" y="{cy+10}" font-size="35" font-weight="700" '
            f'font-family="{_EMOJI_FAMILY}" text-anchor="middle">{_esc(cls_emoji)}</text>'
            f'<text x="{rx}" y="{cy-2}" font-size="42" font-weight="700" '
            f'fill="#f2eefc" text-anchor="middle">{p["elo"]}</text>'
            f'<text x="{rx}" y="{cy+30}" font-size="24" font-weight="700" '
            f'fill="{"#66bb6a" if elo_delta>=0 else "#ef5350"}" '
            f'text-anchor="middle">{"+" if elo_delta>=0 else ""}{elo_delta}</text>'
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
        f'<text x="{width//2}" y="44" font-size="30" font-weight="700" '
        f'fill="#ffd54f" text-anchor="middle">ELO change per game (K={k})</text>',
    ]
    for v in (0, 25, 50, 75, 100):
        gy = Y(v)
        parts.append(
            f'<line x1="{left}" y1="{gy:.1f}" x2="{left+pw}" y2="{gy:.1f}" '
            f'stroke="#ffffff" stroke-opacity="0.08"/>'
            f'<text x="{left-12}" y="{gy+6:.1f}" font-size="18" font-weight="700" '
            f'fill="#9a90c0" text-anchor="end">{v}</text>'
        )
    for d in (-500, -250, 0, 250, 500):
        gx = X(d)
        parts.append(
            f'<line x1="{gx:.1f}" y1="{top}" x2="{gx:.1f}" y2="{top+ph}" '
            f'stroke="#ffffff" stroke-opacity="0.08"/>'
            f'<text x="{gx:.1f}" y="{top+ph+30}" font-size="18" font-weight="700" '
            f'fill="#9a90c0" text-anchor="middle">{"+" if d>0 else ""}{d}</text>'
        )
    parts.append(
        f'<text x="{left+pw//2}" y="{height-22}" font-size="20" font-weight="700" '
        f'fill="#c9a7ff" text-anchor="middle">Your ELO − Opponent ELO</text>'
    )
    parts.append(f'<polyline points="{win}" fill="none" stroke="#66bb6a" stroke-width="4"/>')
    parts.append(f'<polyline points="{loss}" fill="none" stroke="#ef5350" stroke-width="4"/>')
    parts.append(
        f'<rect x="{left+20}" y="{top+10}" width="20" height="20" fill="#66bb6a"/>'
        f'<text x="{left+48}" y="{top+27}" font-size="20" font-weight="700" '
        f'fill="#f2eefc">If you win</text>'
        f'<rect x="{left+20}" y="{top+40}" width="20" height="20" fill="#ef5350"/>'
        f'<text x="{left+48}" y="{top+57}" font-size="20" font-weight="700" '
        f'fill="#f2eefc">If you lose</text>'
    )
    parts.append("</svg>")
    return _save("".join(parts), out_path, scale)


async def render_header_async(out_path, title="Frax Arena Leaderboard"):
    return await asyncio.to_thread(render_header, out_path, title)


async def render_rows_async(entries, out_path):
    return await asyncio.to_thread(render_rows, entries, out_path)


async def render_faction_table_async(rows, out_path):
    return await asyncio.to_thread(render_faction_table, rows, out_path)


async def render_result_async(winner, loser, delta, out_path,
                              winner_avatar=None, loser_avatar=None):
    return await asyncio.to_thread(
        render_result, winner, loser, delta, out_path, winner_avatar, loser_avatar)
