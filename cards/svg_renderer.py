"""Lightweight renderer that builds SVG by hand and rasterizes to JPG.

Uses resvg (a self-contained, cross-platform wheel) + Pillow to produce a JPG.
If resvg is unavailable it falls back to writing the raw .svg (open in a browser).
No Chromium or system Cairo needed.
"""

import os
import sys
import math
import asyncio
import html as _html

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import FACTION_COLORS, faction_base, faction_emoji  # noqa: E402
from cards.model import _latinize

W = 1040

_FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
_FONT_FILES = [
    ("Crimson Pro",      "400", "normal", "CrimsonPro-Regular.ttf"),
    ("Crimson Pro",      "700", "normal", "CrimsonPro-Bold.ttf"),
    ("Crimson Pro",      "400", "italic", "CrimsonPro-Italic.ttf"),
    ("Noto Color Emoji", "400", "normal", "NotoColorEmoji.ttf"),
]
_FONT_FAMILY = "Crimson Pro"
# IMPORTANT: emoji and text must NEVER share a <text> element (not even via <tspan>).
# resvg resolves font-family once per <text> element; if any glyph in the element
# triggers a fallback to _EMOJI_FAMILY, the whole element switches font and regular
# Latin text ends up rendered in Twemoji Mozilla instead of Crimson Pro.
# Fix: put emoji in their own <text font-family="_EMOJI_FAMILY"> elements, text in theirs.
# fonts are loaded via font_files= in svg_to_bytes (resvg ignores @font-face data URIs).
_EMOJI_FAMILY = "Noto Color Emoji"


def _esc(s):
    return _html.escape(str(s))


def _lux_bg():
    return ""


# Warm dark cell, 70% transparent, framed by a bronze edge.
_CELL_FILL = 'fill="#1c1410" fill-opacity="0.3"'
_GOLD_EDGE = '#a9743f'  # bronze
_CELL_STROKE_W = 4
_CELL_STROKE_OPACITY = 0.8

# Very dim, per-rank accent colors for the rank label under each name.
RANK_COLORS = {
    "Champion": "#9c1d1d",
    "Renegade": "#c56d42",
    "Inquisitor": "#8133a0",
    "Paladin": "#44a0ac",
    "Knight": "#5b8ebd",
    "Squire": "#68c7a7",
    "LandLord": "#629c62",
}


_FONT_PATHS = [
    os.path.join(_FONT_DIR, fname)
    for _, _, _, fname in _FONT_FILES
    if os.path.exists(os.path.join(_FONT_DIR, fname))
]


def _save(svg: str, out_path: str, scale: float = 2):
    try:
        import io
        import resvg_py
        from PIL import Image

        png = bytes(resvg_py.svg_to_bytes(
            svg_string=svg, zoom=scale,
            font_files=_FONT_PATHS,
            font_family=_FONT_FAMILY,
        ))
        img = Image.open(io.BytesIO(png)).convert("RGBA")
        webp_path = os.path.splitext(out_path)[0] + ".webp"
        img.save(webp_path, "WEBP", quality=78, method=6)
        return webp_path
    except Exception:
        pass
    # rasterizer unavailable: fall back to writing the raw .svg
    svg_path = os.path.splitext(out_path)[0] + ".svg"
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)
    return svg_path


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
        # Streak: emoji icon in emoji font, number in Crimson Pro
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
            f'fill="#ffffff" fill-opacity="0.05" stroke="{col}" stroke-opacity="0.5"/>'
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
    """Two stacked rows: winner on top, loser below. Faction + ultimate share a
    line; emoji badges replace VICTORY/DEFEAT text."""
    from cards.model import default_avatar

    width = 900
    row_h = 124
    pad = 12
    height = pad * 2 + row_h * 2
    out_w, out_h = 800, height * 800 // width

    WIN_BORDER, LOSE_BORDER = "#ffd54f", "#9045CE"  # gold / dark purple

    def row(y, p, avatar, border_col, emoji, elo_delta):
        avatar = avatar or default_avatar(p["name"])
        faction_col = FACTION_COLORS.get(faction_base(p["faction"]), "#90a4ae")
        cls_emoji = faction_emoji(p["faction"])
        p = {**p, "name": _latinize(p["name"]), "ultimate": _latinize(p["ultimate"])}
        cy = y + row_h // 2
        acx, ar = 88, 46
        lx = 210
        ex = width - 160   # class emoji column
        rx = width - 80    # elo column
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
            f'<text x="140" y="{cy+15}" font-size="44" font-weight="700" font-family="{_EMOJI_FAMILY}" text-anchor="middle">{emoji}</text>'
            f'<text x="{lx}" y="{cy-8}" font-size="34" font-weight="700" '
            f'fill="#f2eefc">{_esc(p["name"][:30])}</text>'
            f'<text x="{lx}" y="{cy+28}" font-size="23" font-weight="700" '
            f'fill="{faction_col}">{info}</text>'
            f'<text x="{ex}" y="{cy+10}" font-size="35" font-weight="700" font-family="{_EMOJI_FAMILY}" '
            f'text-anchor="middle">{_esc(cls_emoji)}</text>'
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
    # gridlines + axis labels
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
    # legend
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


# Async drop-ins. Rasterization is offloaded to a thread so it never blocks the loop.
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


# ---------------------------------------------------------------------------
# Stats card
# ---------------------------------------------------------------------------
_ULTIMATES_DIR = os.path.join(_FONT_DIR, "Ultimates")
_TOWNS_DIR = os.path.join(_FONT_DIR, "Towns")

_ULTIMATE_FILES = {
    "Master of Creation":   "SummoningMagic_MasterOfCreatures.png",
    "Master of Death":      "AvatarOfDeath.png",
    "Master of Destruction":"Demonic_DemonicFlame.png",
    "Master of Life":       "LightMagic_GuardianAngel.png",
    "Angelic Alliance":     "Angel_Wings.png",
    "Blood Thirst":         "BloodThirst.png",
    "Forest Rage":          "Rage_of_the_Forest.png",
    "Forgotten Witchcraft": "Matron_Salvo.png",
    "Frax Essence":         "Artificer_4.png",
    "Mithral Plating":      "Dwarven_Mithral_Cuirass.png",
    "Undying Thirst":       "Vampire_Princess.png",
    "Runic Excelence":      "Researcher.png",
    "Runic Protection":     "Rune_of_Absolute_Protection.png",
    "Nature's Luck":        "Avenger_AbsoluteLuck.png",
    "Absolute Empathy":     "Empathy.png",
    "Might over Magic":     "Training_AbsoluteCharge.png",
    "Arcane Omniscience":   "Artificer_AbsoluteWizardy.png",
    "Howl of Terror":       "Necromancy_AbsoluteFear.png",
    "Blood Frenzy":         "Ultimate_Perk_Absolute_Rage.png",
}

_FACTION_TOWN_FILES = {
    "Haven":      "town_haven.gif",
    "Sylvan":     "town_sylvan.gif",
    "Academy":    "town_academy.gif",
    "Dungeon":    "town_dungeon.gif",
    "Necropolis": "town_necropolis.gif",
    "Inferno":    "town_inferno.gif",
    "Fortress":   "town_fortress.gif",
    "Stronghold": "Stronghold.gif",
}

_CLASS_FILES = {
    "Warrior": "Training_AbsoluteCharge.png",
    "Warmage":  "Rune_of_Absolute_Protection.png",
    "Warlock":  "Artificer_AbsoluteWizardy.png",
}


def _local_data_uri(directory: str, filename: str | None) -> str | None:
    import base64
    if not filename:
        return None
    path = os.path.join(directory, filename)
    if not os.path.exists(path):
        return None
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    mime = {"png": "image/png", "gif": "image/gif"}.get(ext, "image/png")
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    return f"data:{mime};base64,{data}"


# ---------------------------------------------------------------------------
# Shared layout constants (used by all stats-card render functions)
# ---------------------------------------------------------------------------
_S_INSET   = 20
_S_HDR_H   = 112
_S_GAP     = 20
_S_SUB_H   = 34
_S_PAD     = 10
_S_W_INNER = W - 2 * _S_INSET   # 1000

_S_COLS_U  = 9
_S_UCW     = _S_W_INNER // _S_COLS_U   # 111
_S_UISZ    = _S_UCW - 2 * _S_PAD      # 91
_S_UCH     = 148

_S_FC_LBL  = 70
_S_FC_CW   = (_S_W_INNER - _S_FC_LBL) // 8   # 116
_S_FC_HDR  = 90
_S_FC_ISZT = 46
_S_FC_ROW  = 54
_S_FC_H    = _S_FC_HDR + 3 * _S_FC_ROW       # 252
_S_FC_BOT  = 10                               # extra space under faction section

_S_CCW     = _S_W_INNER // 3   # 333
_S_CCH     = 110

# class matchup table (3×3)
_S_CMX_LBL  = 60
_S_CMX_CW   = (_S_W_INNER - _S_CMX_LBL) // 3   # 313
_S_CMX_HDR  = 50   # column header row height
_S_CMX_ROW  = 50   # each data row height
_S_CMX_ISZT = 36   # icon size in matchup headers / row labels
_S_CMX_H    = _S_SUB_H + _S_CMX_HDR + 3 * _S_CMX_ROW   # 234

_S_CCH_TOTAL = _S_CCH + _S_CMX_H   # 344

_S_FRAX_TOWN_ISZ = round(_S_UISZ * 0.7)   # 64  — town icons in frax row (70% of ult icon)

_S_BG      = 'fill="#18120e" fill-opacity="0.55"'


# ---------------------------------------------------------------------------
# Shared drawing primitives — each takes the `parts` list to append to
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
    wr_col    = ("#66bb6a" if winrate >= 50 else "#ef5350") if has else "#606078"
    games_str = f'{games} games' if has else 'no games'
    wr_str    = f'{winrate}%'    if has else '–'
    parts.append(
        f'<text x="{cx}" y="{y_games}" font-size="{fg}" '
        f'fill="#c0b8d8" text-anchor="middle">{_esc(games_str)}</text>'
        f'<text x="{cx}" y="{y_games + fw + 4}" font-size="{fw}" font-weight="700" '
        f'fill="{wr_col}" text-anchor="middle">{_esc(wr_str)}</text>'
    )


def _d_section_header(parts, y, title):
    pad = 8   # equal top and bottom inset within the HDR_H space
    ih  = _S_HDR_H - 2 * pad
    ty  = y + pad + ih // 2 + 22
    parts.append(
        f'<rect x="0" y="{y + pad}" width="{W}" height="{ih}" rx="16" '
        f'{_S_BG} stroke="{_GOLD_EDGE}" stroke-opacity="0.9" stroke-width="5"/>'
        f'<text x="{W//2}" y="{ty}" font-size="60" font-weight="700" '
        f'fill="#ffd54f" text-anchor="middle">{_esc(title)}</text>'
    )


def _d_section_bg(parts, y, h):
    parts.append(
        f'<rect x="{_S_INSET}" y="{y}" width="{_S_W_INNER}" height="{h}" rx="18" '
        f'{_S_BG} stroke="{_GOLD_EDGE}" stroke-opacity="0.2" stroke-width="1.5"/>'
    )


def _d_sub_header(parts, y, title):
    ty = y + _S_SUB_H // 2 + 7
    parts.append(
        f'<text x="{W//2}" y="{ty}" font-size="15" font-weight="700" '
        f'fill="#c9a7ff" text-anchor="middle" font-style="italic">{_esc(title)}</text>'
    )


# ---------------------------------------------------------------------------
# Section-level drawing helpers (depend on shared layout constants)
# ---------------------------------------------------------------------------

def _d_ult_cell(parts, col, row_idx, y, r, ult_imgs):
    x  = _S_INSET + col * _S_UCW
    cx = x + _S_UCW // 2
    ix = cx - _S_UISZ // 2
    _d_sq_img(parts, ult_imgs.get(r["ultimate"]), ix, y + _S_PAD, _S_UISZ, 12,
              _GOLD_EDGE, f"u{row_idx}_{col}")
    yg = y + _S_PAD + _S_UISZ + 12 + 13
    _d_stats(parts, cx, yg, r["games"], r["winrate"], r["games"] > 0, fg=12, fw=15)


def _d_frax_row(parts, y, frax_rows, frax_icon, town_imgs):
    """9-column frax row: col 0 = summary (full icon), cols 1–8 = per-faction towns (70%)."""
    tf_games = sum(r["games"] for r in frax_rows)
    tf_wins  = sum(r.get("wins", 0) for r in frax_rows)
    tf_wr    = round(100 * tf_wins / tf_games) if tf_games else 0

    # Stats y is based on the full _S_UISZ so text aligns horizontally across all cols.
    yg = y + _S_PAD + _S_UISZ + 12 + 13

    def _cell(col, img, isz, border_col, games, winrate):
        x  = _S_INSET + col * _S_UCW
        cx = x + _S_UCW // 2
        # vertical-center the icon within the icon zone (top = _S_PAD, zone height = _S_UISZ)
        iy = y + _S_PAD + (_S_UISZ - isz) // 2
        ix = cx - isz // 2
        _d_sq_img(parts, img, ix, iy, isz, 12, border_col, f"frc{col}", sw=3, so=0.88)
        _d_stats(parts, cx, yg, games, winrate, games > 0, fg=12, fw=15)

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
        _d_sq_img(parts, town_imgs.get(fac), ix, y + 5, _S_FC_ISZT, 8,
                  col_c, f"fch{i}", sw=2, so=0.8)
        yg = y + 5 + _S_FC_ISZT + 3 + 13   # games baseline (fg=13)
        _d_stats(parts, cx, yg, r["games"], r["winrate"], r["games"] > 0, fg=13, fw=17)

    parts.append(
        f'<line x1="{_S_INSET}" y1="{y + _S_FC_HDR}" '
        f'x2="{W - _S_INSET}" y2="{y + _S_FC_HDR}" '
        f'stroke="{_GOLD_EDGE}" stroke-opacity="0.3" stroke-width="1"/>'
    )

    for j, cls in enumerate(CLASSES):
        ry  = y + _S_FC_HDR + j * _S_FC_ROW
        rcy = ry + _S_FC_ROW // 2
        lsz = _S_FC_ROW - 10
        _d_sq_img(parts, cls_imgs.get(cls),
                  _S_INSET + (_S_FC_LBL - lsz) // 2, ry + 5,
                  lsz, 8, _GOLD_EDGE, f"fcl{j}", sw=2, so=0.7)
        parts.append(
            f'<line x1="{_S_INSET}" y1="{ry}" x2="{W - _S_INSET}" y2="{ry}" '
            f'stroke="{_GOLD_EDGE}" stroke-opacity="0.15" stroke-width="1"/>'
        )
        for i, fac in enumerate(FACTIONS):
            cx    = _S_INSET + _S_FC_LBL + i * _S_FC_CW + _S_FC_CW // 2
            cell  = (fc_data.get(fac) or [{}, {}, {}])[j]
            has   = cell.get("games", 0) > 0
            wr    = cell.get("winrate", 0)
            g     = cell.get("games", 0)
            wr_col = ("#66bb6a" if wr >= 50 else "#ef5350") if has else "#606078"
            wr_str = f'{wr}%'      if has else '–'
            g_str  = f'{g} games' if has else '0 games'
            parts.append(
                f'<text x="{cx}" y="{rcy - 5}" font-size="12" '
                f'fill="#c0b8d8" text-anchor="middle">{_esc(g_str)}</text>'
                f'<text x="{cx}" y="{rcy + 16}" font-size="17" font-weight="700" '
                f'fill="{wr_col}" text-anchor="middle">{_esc(wr_str)}</text>'
            )

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
    wr_col    = ("#66bb6a" if r["winrate"] >= 50 else "#ef5350") if has else "#606078"
    games_str = f'{r["games"]} games' if has else 'no games'
    wr_str    = f'{r["winrate"]}%'    if has else '–'
    _d_sq_img(parts, cls_imgs.get(r["class"]), ix, y + _S_PAD, isz, 12,
              _GOLD_EDGE, f"cls{col}", sw=2)
    parts.append(
        f'<text x="{tx}" y="{cy - 18}" font-size="30" font-weight="700" '
        f'fill="#f2eefc">{_esc(r["class"])}</text>'
        f'<text x="{tx}" y="{cy + 8}" font-size="14" fill="#c0b8d8">'
        f'{_esc(games_str)}</text>'
        f'<text x="{tx}" y="{cy + 32}" font-size="22" font-weight="700" '
        f'fill="{wr_col}">{_esc(wr_str)}</text>'
    )


def _d_class_matchup(parts, y, matchup_data, cls_imgs):
    """3×3 class-vs-class matchup table. matchup_data keyed by (i, j) int tuples."""
    from config import CLASSES
    _d_sub_header(parts, y, "— Class Matchups —")
    y += _S_SUB_H

    # column header icons
    for j, cls in enumerate(CLASSES):
        cx  = _S_INSET + _S_CMX_LBL + j * _S_CMX_CW + _S_CMX_CW // 2
        isz = _S_CMX_ISZT
        _d_sq_img(parts, cls_imgs.get(cls),
                  cx - isz // 2, y + (_S_CMX_HDR - isz) // 2,
                  isz, 8, _GOLD_EDGE, f"cmxh{j}", sw=2, so=0.7)

    # separator below column headers
    parts.append(
        f'<line x1="{_S_INSET}" y1="{y + _S_CMX_HDR}" '
        f'x2="{W - _S_INSET}" y2="{y + _S_CMX_HDR}" '
        f'stroke="{_GOLD_EDGE}" stroke-opacity="0.3" stroke-width="1"/>'
    )
    y += _S_CMX_HDR

    for i, row_cls in enumerate(CLASSES):
        ry  = y + i * _S_CMX_ROW
        rcy = ry + _S_CMX_ROW // 2
        if i > 0:
            parts.append(
                f'<line x1="{_S_INSET}" y1="{ry}" x2="{W - _S_INSET}" y2="{ry}" '
                f'stroke="{_GOLD_EDGE}" stroke-opacity="0.15" stroke-width="1"/>'
            )
        isz = _S_CMX_ISZT
        _d_sq_img(parts, cls_imgs.get(row_cls),
                  _S_INSET + (_S_CMX_LBL - isz) // 2, rcy - isz // 2,
                  isz, 8, _GOLD_EDGE, f"cmxr{i}", sw=2, so=0.7)
        for j in range(len(CLASSES)):
            cx = _S_INSET + _S_CMX_LBL + j * _S_CMX_CW + _S_CMX_CW // 2
            if i == j:
                parts.append(
                    f'<text x="{cx}" y="{rcy + 6}" font-size="22" font-weight="700" '
                    f'fill="#606078" text-anchor="middle">–</text>'
                )
                continue
            cell   = matchup_data.get((i, j)) or {}
            has    = cell.get("games", 0) > 0
            wr     = cell.get("winrate", 0)
            g      = cell.get("games", 0)
            wr_col = ("#66bb6a" if wr >= 50 else "#ef5350") if has else "#606078"
            parts.append(
                f'<text x="{cx}" y="{rcy - 5}" font-size="12" '
                f'fill="#c0b8d8" text-anchor="middle">'
                f'{_esc(f"{g} games" if has else "no games")}</text>'
                f'<text x="{cx}" y="{rcy + 16}" font-size="17" font-weight="700" '
                f'fill="{wr_col}" text-anchor="middle">'
                f'{_esc(f"{wr}%" if has else "–")}</text>'
            )

    # vertical separators
    y_top = y - _S_CMX_HDR
    y_bot = y + 3 * _S_CMX_ROW
    for j in range(1, 3):
        lx = _S_INSET + _S_CMX_LBL + j * _S_CMX_CW
        parts.append(
            f'<line x1="{lx}" y1="{y_top}" x2="{lx}" y2="{y_bot}" '
            f'stroke="{_GOLD_EDGE}" stroke-opacity="0.12" stroke-width="1"/>'
        )
    parts.append(
        f'<line x1="{_S_INSET + _S_CMX_LBL}" y1="{y_top}" '
        f'x2="{_S_INSET + _S_CMX_LBL}" y2="{y_bot}" '
        f'stroke="{_GOLD_EDGE}" stroke-opacity="0.2" stroke-width="1"/>'
    )


# ---------------------------------------------------------------------------
# Public standalone section renderers (one per output file)
# ---------------------------------------------------------------------------

def render_stats_header_img(title, out_path, scale=1):
    """Render just one section header bar with equal top/bottom padding."""
    outer = 10   # external padding above and below the bar in the standalone file
    ih    = _S_HDR_H - 16   # inner rect height (matches composite: HDR_H - 2*pad=8)
    h     = ih + 2 * outer  # total SVG height: equal outer margin top and bottom
    ow    = 800
    oh    = h * ow // W
    ty    = outer + ih // 2 + 22
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{ow}" height="{oh}" '
        f'viewBox="0 0 {W} {h}" font-family="{_FONT_FAMILY}">',
        f'<rect x="0" y="{outer}" width="{W}" height="{ih}" rx="16" '
        f'{_S_BG} stroke="{_GOLD_EDGE}" stroke-opacity="0.9" stroke-width="5"/>'
        f'<text x="{W//2}" y="{ty}" font-size="60" font-weight="700" '
        f'fill="#ffd54f" text-anchor="middle">{_esc(title)}</text>',
    ]
    parts.append("</svg>")
    return _save("".join(parts), out_path, scale)


def render_ult_section_img(ult_rows, frax_rows, out_path, scale=1):
    """Render the Ultimate Winrate section body (no header bar)."""
    from config import CLASSES

    main_ult = [r for r in ult_rows if r["ultimate"] != "Frax Essence"]
    main_ult.sort(key=lambda r: r["games"], reverse=True)

    ult_imgs  = {r["ultimate"]: _local_data_uri(_ULTIMATES_DIR, _ULTIMATE_FILES.get(r["ultimate"]))
                 for r in main_ult}
    frax_icon = _local_data_uri(_ULTIMATES_DIR, _ULTIMATE_FILES.get("Frax Essence"))
    town_imgs = {f: _local_data_uri(_TOWNS_DIR, _FACTION_TOWN_FILES.get(f))
                 for f in {r["faction"] for r in frax_rows}}

    sec_h = _S_UCH * 3 + _S_SUB_H + 5   # +5 bottom breathing room under frax WR
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
    _d_sub_header(parts, y, "— Frax Essence by Faction —")
    y += _S_SUB_H
    _d_frax_row(parts, y, frax_rows, frax_icon, town_imgs)

    parts.append("</svg>")
    return _save("".join(parts), out_path, scale)


def render_faction_section_img(faction_rows, fc_data, out_path, scale=1):
    """Render the Faction Stats section body (no header bar)."""
    from config import FACTIONS, CLASSES

    town_imgs = {f: _local_data_uri(_TOWNS_DIR, _FACTION_TOWN_FILES.get(f)) for f in FACTIONS}
    cls_imgs  = {c: _local_data_uri(_ULTIMATES_DIR, _CLASS_FILES.get(c)) for c in CLASSES}

    total_h = _S_GAP + _S_FC_H + _S_FC_BOT + _S_GAP
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


def render_class_section_img(class_rows, out_path, matchup_data=None, scale=1):
    """Render the Class Winrate section body (no header bar)."""
    from config import CLASSES

    cls_imgs = {c: _local_data_uri(_ULTIMATES_DIR, _CLASS_FILES.get(c)) for c in CLASSES}

    total_h = _S_GAP + _S_CCH_TOTAL + _S_GAP
    ow = 800
    oh = total_h * ow // W

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{ow}" height="{oh}" '
        f'viewBox="0 0 {W} {total_h}" font-family="{_FONT_FAMILY}">',
    ]
    y = _S_GAP
    _d_section_bg(parts, y, _S_CCH_TOTAL)
    for i, r in enumerate(class_rows):
        _d_class_cell(parts, i, y, r, cls_imgs)
    _d_class_matchup(parts, y + _S_CCH, matchup_data or {}, cls_imgs)

    parts.append("</svg>")
    return _save("".join(parts), out_path, scale)


# ---------------------------------------------------------------------------
# Composite card (all sections in one image)
# ---------------------------------------------------------------------------

def render_stats_card(ult_rows, faction_rows, class_rows, frax_rows, fc_data,
                      out_path, matchup_data=None, scale=1):
    """Stats card: ultimates / faction stats / class — all in one image."""
    from config import FACTIONS, CLASSES

    main_ult = [r for r in ult_rows if r["ultimate"] != "Frax Essence"]
    main_ult.sort(key=lambda r: r["games"], reverse=True)

    ult_imgs  = {r["ultimate"]: _local_data_uri(_ULTIMATES_DIR, _ULTIMATE_FILES.get(r["ultimate"]))
                 for r in main_ult}
    frax_icon = _local_data_uri(_ULTIMATES_DIR, _ULTIMATE_FILES.get("Frax Essence"))
    town_imgs = {f: _local_data_uri(_TOWNS_DIR, _FACTION_TOWN_FILES.get(f)) for f in FACTIONS}
    cls_imgs  = {c: _local_data_uri(_ULTIMATES_DIR, _CLASS_FILES.get(c)) for c in CLASSES}

    ult_sec_h = _S_UCH * 3 + _S_SUB_H + 5
    fc_sec_h  = _S_FC_H
    cls_sec_h = _S_CCH_TOTAL

    total_h = (_S_GAP
               + _S_HDR_H + ult_sec_h
               + _S_GAP
               + _S_HDR_H + fc_sec_h + _S_FC_BOT
               + _S_GAP
               + _S_HDR_H + cls_sec_h
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
    _d_sub_header(parts, y, "— Frax Essence by Faction —")
    y += _S_SUB_H
    _d_frax_row(parts, y, frax_rows, frax_icon, town_imgs)
    y += _S_UCH + _S_GAP

    _d_section_header(parts, y, "Faction Stats")
    y += _S_HDR_H
    _d_section_bg(parts, y, fc_sec_h)
    _d_faction_fc_grid(parts, y, faction_rows, fc_data, town_imgs, cls_imgs)
    y += _S_FC_H + _S_FC_BOT + _S_GAP

    _d_section_header(parts, y, "Class Winrate")
    y += _S_HDR_H
    _d_section_bg(parts, y, cls_sec_h)
    for i, r in enumerate(class_rows):
        _d_class_cell(parts, i, y, r, cls_imgs)
    _d_class_matchup(parts, y + _S_CCH, matchup_data or {}, cls_imgs)

    parts.append("</svg>")
    return _save("".join(parts), out_path, scale)


async def render_stats_card_async(ult_rows, faction_rows, class_rows, frax_rows,
                                   fc_data, out_path, matchup_data=None):
    return await asyncio.to_thread(
        render_stats_card, ult_rows, faction_rows, class_rows,
        frax_rows, fc_data, out_path, matchup_data)
