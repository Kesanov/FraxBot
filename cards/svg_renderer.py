"""Lightweight renderer that builds SVG by hand and rasterizes to JPG.

Uses resvg (a self-contained, cross-platform wheel) + Pillow to produce a JPG.
If resvg is unavailable it falls back to writing the raw .svg (open in a browser).
No Chromium or system Cairo needed.
"""

import os
import sys
import asyncio
import html as _html

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import FACTION_COLORS  # noqa: E402

W = 900


def _esc(s):
    return _html.escape(str(s))


# Background the JPEG is flattened onto (matches the card background #14101f).
_BG = (20, 16, 31)


def _rasterize_jpg(svg: str, jpg_path: str) -> bool:
    """Rasterize SVG -> JPG. resvg (self-contained wheel, cross-platform) renders
    to PNG bytes, then Pillow flattens alpha and saves JPEG. True on success."""
    try:
        import io
        import resvg_py
        from PIL import Image

        png = bytes(resvg_py.svg_to_bytes(svg_string=svg, zoom=2))
        img = Image.open(io.BytesIO(png)).convert("RGBA")
        bg = Image.new("RGB", img.size, _BG)
        bg.paste(img, mask=img.split()[3])
        bg.save(jpg_path, "JPEG", quality=92)
        return True
    except Exception:
        return False


def _save(svg: str, out_path: str):
    base, _ = os.path.splitext(out_path)
    jpg_path = base + ".jpg"
    if _rasterize_jpg(svg, jpg_path):
        return jpg_path
    # rasterizer unavailable: fall back to writing the raw .svg
    svg_path = base + ".svg"
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)
    return svg_path


def render_leaderboard(entries, out_path, heading="H55 ELO Ladder",
                       subheading="Top players"):
    row_h = 78
    top = 130
    height = top + row_h * len(entries) + 20
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" '
        f'font-family="Segoe UI, Arial, sans-serif">',
        f'<rect width="{W}" height="{height}" fill="#14101f"/>',
        f'<text x="40" y="56" font-size="40" font-weight="800" fill="#ffd54f">{_esc(heading)}</text>',
        f'<text x="40" y="86" font-size="16" fill="#9a90c0">{_esc(subheading)}</text>',
    ]
    medals = {1: "#ffd54f", 2: "#cfd8dc", 3: "#cd7f32"}
    for e in entries:
        y = top + (e["position"] - 1) * row_h
        parts.append(
            f'<rect x="30" y="{y}" width="{W-60}" height="{row_h-12}" rx="14" '
            f'fill="#ffffff" fill-opacity="0.05" stroke="#ffffff" stroke-opacity="0.08"/>'
        )
        pc = medals.get(e["position"], "#8a80b0")
        parts.append(
            f'<text x="70" y="{y+44}" font-size="26" font-weight="800" '
            f'fill="{pc}" text-anchor="middle">#{e["position"]}</text>'
        )
        # avatar (clipped circle)
        cid = f"clip{e['position']}"
        parts.append(
            f'<clipPath id="{cid}"><circle cx="135" cy="{y+33}" r="26"/></clipPath>'
            f'<image x="109" y="{y+7}" width="52" height="52" '
            f'href="{_esc(e["avatar"])}" clip-path="url(#{cid})"/>'
        )
        parts.append(
            f'<text x="180" y="{y+30}" font-size="22" font-weight="700" fill="#f2eefc">{_esc(e["name"])}</text>'
            f'<text x="180" y="{y+52}" font-size="14" fill="#c9a7ff">{_esc(e["rank"])}</text>'
        )
        cols = [
            (str(e["elo"]), "ELO", "#80d8ff"),
            (f'{e["winrate"]}%', "WINRATE", "#f2eefc"),
            (str(e["games"]), "GAMES", "#f2eefc"),
            (f'{e["wins"]}-{e["losses"]}', "W-L", "#f2eefc"),
        ]
        x = W - 360
        for val, lab, col in cols:
            parts.append(
                f'<text x="{x+40}" y="{y+30}" font-size="20" font-weight="700" '
                f'fill="{col}" text-anchor="middle">{_esc(val)}</text>'
                f'<text x="{x+40}" y="{y+50}" font-size="11" fill="#9a90c0" '
                f'text-anchor="middle">{lab}</text>'
            )
            x += 85
    parts.append("</svg>")
    return _save("".join(parts), out_path)


def render_result(winner, loser, delta, out_path, heading="Match Reported"):
    w_col = FACTION_COLORS.get(winner["faction"], "#d9b44a")
    l_col = FACTION_COLORS.get(loser["faction"], "#90a4ae")
    width, height = 820, 170
    py, ph = 42, 112  # panel top / height

    def side(x, p, col, badge, elo_delta):
        lx = x + 20          # left text column
        rx = x + 268         # right (elo) column, centered
        return (
            f'<rect x="{x}" y="{py}" width="340" height="{ph}" rx="16" '
            f'fill="#ffffff" fill-opacity="0.05" stroke="{col}" stroke-width="2"/>'
            f'<text x="{lx}" y="{py+30}" font-size="20" font-weight="800" '
            f'fill="#f2eefc">{_esc(p["name"])}</text>'
            f'<text x="{lx}" y="{py+56}" font-size="15" font-weight="700" '
            f'fill="{col}">{_esc(p["faction"])}</text>'
            f'<text x="{lx}" y="{py+78}" font-size="12" fill="#b9aee0">'
            f'Ult: {_esc(p["ultimate"])}</text>'
            f'<text x="{rx}" y="{py+26}" font-size="11" letter-spacing="2" '
            f'fill="{col}" text-anchor="middle">{badge}</text>'
            f'<text x="{rx}" y="{py+64}" font-size="26" font-weight="800" '
            f'fill="#f2eefc" text-anchor="middle">{p["elo"]}</text>'
            f'<text x="{rx}" y="{py+88}" font-size="14" '
            f'fill="{"#66bb6a" if elo_delta>=0 else "#ef5350"}" '
            f'text-anchor="middle">{"+" if elo_delta>=0 else ""}{elo_delta}</text>'
        )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'font-family="Segoe UI, Arial, sans-serif">'
        f'<rect width="{width}" height="{height}" fill="#14101f"/>'
        f'<text x="{width//2}" y="30" font-size="22" font-weight="800" '
        f'fill="#ffd54f" text-anchor="middle">{_esc(heading)}</text>'
        + side(30, winner, w_col, "VICTORY", delta)
        + f'<text x="{width//2}" y="{py+ph//2+8}" font-size="24" font-weight="900" '
          f'fill="#6a5f95" text-anchor="middle">VS</text>'
        + side(450, loser, l_col, "DEFEAT", -delta)
        + "</svg>"
    )
    return _save(svg, out_path)


# Async drop-ins so this module is interchangeable with html_renderer in the bot.
# Rasterization is offloaded to a thread so it never blocks the event loop.
async def render_leaderboard_async(entries, out_path, heading="H55 ELO Ladder",
                                   subheading="Top players"):
    return await asyncio.to_thread(
        render_leaderboard, entries, out_path, heading, subheading)


async def render_result_async(winner, loser, delta, out_path, heading="Match Reported"):
    return await asyncio.to_thread(
        render_result, winner, loser, delta, out_path, heading)
