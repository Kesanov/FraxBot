"""Highlight cards: Reckoning (vanquished streak) and Undefeated (ongoing streak)."""

import asyncio

from config import FACTION_COLORS, faction_base
from cards.model import _latinize, default_avatar
from cards.svg_base import (
    W, _esc, _lux_bg, _save, _FONT_FAMILY, render_text, render_small_caps,
    _cell, _CELL_STROKE_W,
    _OUTER_PAD, _CELL_OUTER_PAD, _run_width,
    _local_data_uri, _TOWNS_DIR,
)

_CELL_TOP = 26
_CELL_H = 162
_CARD_HEIGHT = _CELL_TOP + _CELL_H + _OUTER_PAD
_DX = int(W * 0.72)
_LEAN = 34
_GOLD = "#ffd54f"

_THEME_RECKONING = dict(
    cell_border=None,           # default cell border (gold gradient)
    zone_fill="#4a0e1c",
    zone_opacity="0.6",
    slash_stroke="url(#goldEdge)",
    slash_opacity=None,
    streak_col="#ffab40",
    streak_emoji="🔥",
    label="VANQUISHED",
    label_x_offset=0,
    label_col="#e53935",
    lose_border="#9045CE",
    lose_sublabel="DEFEATED",
    lose_sublabel_col="#ff5b7a",
    zone_id="rkzone",
)

_THEME_UNDEFEATED = dict(
    cell_border=None,
    zone_fill="#4a0e1c",
    zone_opacity="0.75",
    slash_stroke="url(#goldEdge)",
    slash_opacity="0.9",
    streak_col="#ffab40",
    streak_emoji="🔥",
    label="INVINCIBLE",
    label_x_offset=-5,
    label_col="#ffab40",
    lose_border="#546e7a",
    lose_sublabel="OPPONENT",
    lose_sublabel_col="#ff5b7a",
    zone_id="udzone",
)


def _side(p):
    base = faction_base(p["faction"])
    return {
        "name": _latinize(p["name"]),
        "avatar": p.get("avatar") or default_avatar(p["name"]),
        "col": FACTION_COLORS.get(base, "#90a4ae"),
        "town": _local_data_uri(_TOWNS_DIR, base + ".gif"),
    }


def _avatar(acx, acy, ar, href, border, dim=False):
    cid = f"rk_{acx}"
    op = ' opacity="0.78"' if dim else ""
    return (
        f'<clipPath id="{cid}"><circle cx="{acx}" cy="{acy}" r="{ar}"/></clipPath>'
        f'<circle cx="{acx}" cy="{acy}" r="{ar+4}" fill="none" '
        f'stroke="{border}" stroke-width="3"/>'
        f'<image x="{acx-ar}" y="{acy-ar}" width="{ar*2}" height="{ar*2}" '
        f'href="{_esc(href)}" clip-path="url(#{cid})"{op}/>'
    )


def _town_badge(href, ccx, ccy, border, bsz=38):
    if not href:
        return ""
    frame = (f'<rect x="{ccx - bsz//2}" y="{ccy - bsz//2}" width="{bsz}" height="{bsz}" '
             f'rx="8" fill="none" stroke="{border}" stroke-width="2" stroke-opacity="0.8"/>'
             if border else "")
    return (f'<image x="{ccx - bsz//2}" y="{ccy - bsz//2}" width="{bsz}" height="{bsz}" '
            f'rx="8" href="{_esc(href)}"/>' + frame)


def _render_highlight(data, out_path, theme, scale=1):
    streak = data["streak"]
    delta = data["delta"]
    w, l = _side(data["winner"]), _side(data["loser"])

    yt = _CELL_TOP + 4
    yb = _CELL_TOP + _CELL_H - 4
    cx0, cx1 = _CELL_OUTER_PAD, W - _CELL_OUTER_PAD
    cw, ch = W - 2 * cx0, _CELL_H - 8
    cy = (yt + yb) // 2
    height = _CARD_HEIGHT
    out_w = 800
    out_h = height * out_w // W

    t = theme
    cell_kw = dict(color=t["cell_border"]) if t["cell_border"] else {}
    slash_extra = f' stroke-opacity="{t["slash_opacity"]}"' if t["slash_opacity"] else ""

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{out_w}" height="{out_h}" '
        f'viewBox="0 0 {W} {height}" font-family="{_FONT_FAMILY}">',
        _lux_bg(),
        _cell(cx0, yt, cw, ch, 18, **cell_kw),
        f'<clipPath id="{t["zone_id"]}"><rect x="{cx0+3}" y="{yt+3}" width="{cw-6}" '
        f'height="{ch-6}" rx="15"/></clipPath>',
        f'<polygon points="{_DX+_LEAN},{yt} {cx1},{yt} {cx1},{yb} {_DX-_LEAN},{yb}" '
        f'fill="{t["zone_fill"]}" fill-opacity="{t["zone_opacity"]}" '
        f'clip-path="url(#{t["zone_id"]})"/>',
        f'<line x1="{_DX-_LEAN}" y1="{yb-6}" x2="{_DX+_LEAN}" y2="{yt+6}" '
        f'stroke="{t["slash_stroke"]}" stroke-width="{_CELL_STROKE_W}" '
        f'stroke-linecap="round"{slash_extra}/>',
    ]

    # Winner — wide left zone
    ar_w = 56
    acx_w = cx0 + 18 + ar_w
    parts.append(_avatar(acx_w, cy, ar_w, w["avatar"], "#ffd54f"))
    parts.append(_town_badge(w["town"], acx_w + round(ar_w * 0.7),
                             cy + round(ar_w * 0.7), w["col"]))
    tx = acx_w + ar_w + 26
    parts.append(render_text(tx, cy - 6, w["name"][:12], 50, _GOLD))
    parts.append(render_text(tx, cy + 30, f'+{delta} ELO', 26, "#3ba040"))

    # Centre — streak number + emoji + label
    cxm = int(W * 0.56)
    nstr, emj = str(streak), t["streak_emoji"]
    nw = _run_width(False, nstr, 80, "700", False)
    ew = _run_width(True, emj, 64, "700", False)
    gx = cxm - (nw - 10 + ew) / 2
    parts.append(render_text(gx, cy + 6, nstr, 80, t["streak_col"]))
    parts.append(render_text(gx + nw - 10, cy + 4, emj, 64, t["streak_col"]))
    parts.append(render_small_caps(cxm + t["label_x_offset"], cy + 40, t["label"], 30, t["label_col"]))

    # Loser — narrow dark zone on the right
    ar_l = 46
    acx_l = cx1 - 16 - ar_l
    parts.append(_avatar(acx_l, cy, ar_l, l["avatar"], t["lose_border"], dim=True))
    parts.append(_town_badge(l["town"], acx_l - round(ar_l * 0.7),
                             cy + round(ar_l * 0.7), l["col"]))
    lnx = acx_l - ar_l - 22
    parts.append(render_small_caps(lnx, cy - 18, t["lose_sublabel"], 20,
                                   t["lose_sublabel_col"], anchor="end"))
    parts.append(render_text(lnx, cy + 28, l["name"][:8], 30, _GOLD, anchor="end"))

    parts.append("</svg>")
    return _save("".join(parts), out_path, scale)


def render_reckoning(data, out_path, title="Reckoning", scale=1):
    return _render_highlight(data, out_path, _THEME_RECKONING, scale)


def render_undefeated(data, out_path, scale=1):
    return _render_highlight(data, out_path, _THEME_UNDEFEATED, scale)


async def render_reckoning_async(data, out_path, title="Reckoning"):
    return await asyncio.to_thread(render_reckoning, data, out_path, title)


async def render_undefeated_async(data, out_path):
    return await asyncio.to_thread(render_undefeated, data, out_path)
