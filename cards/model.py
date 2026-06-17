"""Turn raw player rows into display-ready leaderboard entries."""

import sys
import os
import html as _html

from unidecode import unidecode as _unidecode


def _latinize(name: str) -> str:
    """Transliterate non-Latin characters to ASCII so Crimson Pro can render them."""
    return _unidecode(name)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import rank_title  # noqa: E402

# A small set of medal accent colors for the top 3.
MEDALS = {1: "#ffd54f", 2: "#cfd8dc", 3: "#cd7f32"}


def build_entries(players, avatar_resolver=None, name_resolver=None):
    """players: list of dicts (from db.top_players).

    avatar_resolver(user_id) -> str (data URI / URL / file path) or None.
    name_resolver(user_id) -> str or None (falls back to DB name).
    Returns list of dicts ready for templates.
    """
    entries = []
    for i, p in enumerate(players, start=1):
        games = p["wins"] + p["losses"]
        winrate = round(100 * p["wins"] / games) if games else 0
        avatar = avatar_resolver(p["user_id"]) if avatar_resolver else None
        name = name_resolver(p["user_id"]) if name_resolver else None
        if name is None:
            continue  # skip deleted accounts
        entries.append(
            {
                "position": i,
                "name": _latinize(name),
                "elo": p["elo"],
                "rank": rank_title(p["elo"]),
                "wins": p["wins"],
                "losses": p["losses"],
                "games": games,
                "winrate": winrate,
                "streak": streak_label(p.get("streak", 0)),
                "avatar": avatar or default_avatar(name),
                "medal": MEDALS.get(i),
            }
        )
    return entries


def streak_label(streak: int) -> str:
    """🔥 for a win streak, – otherwise"""
    if streak >= 1:
        return f"🔥{streak}"
    # if streak <= -2:
    #     return f"🧊{abs(streak)}"
    return "–"


def default_avatar(name: str) -> str:
    """An inline SVG data URI used when no real avatar is available."""
    import base64

    initial = _html.escape((name.strip()[:1] or "?").upper())
    # deterministic hue from name
    hue = sum(ord(c) for c in name) % 360
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128">'
        f'<rect width="128" height="128" rx="64" fill="hsl({hue},45%,40%)"/>'
        f'<text x="64" y="84" font-size="64" font-family="Arial" '
        f'fill="white" text-anchor="middle">{initial}</text></svg>'
    )
    b64 = base64.b64encode(svg.encode()).decode()
    return f"data:image/svg+xml;base64,{b64}"
