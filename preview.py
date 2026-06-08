"""Generate sample cards locally so you can eyeball the visuals without Discord.

    python preview.py

Renders the leaderboard and a result card to JPG in discord/preview_output/.
"""

import os

from config import PREVIEW_DIR, ELO_K
from cards import model, svg_renderer as renderer

SAMPLE_PLAYERS = [
    {"user_id": "1", "name": "𝕲𝖗𝖞𝖜",       "elo": 2072, "wins": 41, "losses": 9,  "streak": 7},
    {"user_id": "2", "name": "中文",        "elo": 1840, "wins": 33, "losses": 14, "streak": 3},
    {"user_id": "3", "name": "Maрkal",     "elo": 1688, "wins": 28, "losses": 16, "streak": 1},
    {"user_id": "4", "name": "Isabel",     "elo": 1430, "wins": 22, "losses": 18, "streak": 0},
    {"user_id": "5", "name": "Raelag",     "elo": 1275, "wins": 19, "losses": 17, "streak": -2},
    {"user_id": "6", "name": "Kujin",      "elo": 1180, "wins": 15, "losses": 15, "streak": 2},
    {"user_id": "7", "name": "Wulfstan",   "elo": 1095, "wins": 11, "losses": 14, "streak": -1},
    {"user_id": "8", "name": "Nadia",      "elo": 1010, "wins": 8,  "losses": 12, "streak": -4},
    {"user_id": "9", "name": "Gotai",      "elo": 970,  "wins": 6,  "losses": 13, "streak": 1},
    {"user_id": "10", "name": "Sandro",    "elo": 905,  "wins": 4,  "losses": 16, "streak": -3},
    {"user_id": "11", "name": "Agrael",    "elo": 880,  "wins": 5,  "losses": 18, "streak": -6},
    {"user_id": "12", "name": "Freyda",    "elo": 855,  "wins": 3,  "losses": 17, "streak": 1},
]

SAMPLE_FACTIONS = [
    {"faction": "Necropolis", "wins": 34, "losses": 18, "games": 52, "winrate": 65},
    {"faction": "Dungeon",    "wins": 28, "losses": 20, "games": 48, "winrate": 58},
    {"faction": "Sylvan",     "wins": 22, "losses": 21, "games": 43, "winrate": 51},
    {"faction": "Haven",      "wins": 19, "losses": 21, "games": 40, "winrate": 48},
    {"faction": "Academy",    "wins": 17, "losses": 22, "games": 39, "winrate": 44},
    {"faction": "Inferno",    "wins": 14, "losses": 20, "games": 34, "winrate": 41},
    {"faction": "Stronghold", "wins": 11, "losses": 19, "games": 30, "winrate": 37},
    {"faction": "Fortress",   "wins": 9,  "losses": 21, "games": 30, "winrate": 30},
]

SAMPLE_WINNER = {"name": "Markal", "faction": "Necropolis",
                 "ultimate": "Eternal Servitude", "elo": 1704}
SAMPLE_LOSER = {"name": "Zehir", "faction": "Academy",
                "ultimate": "Arcane Omniscience", "elo": 1508}
SAMPLE_DELTA = 32


if __name__ == "__main__":
    entries = model.build_entries(SAMPLE_PLAYERS)
    print("header ->", renderer.render_header(os.path.join(PREVIEW_DIR, "lb_header.jpg")))
    for i in range(0, len(entries), 4):
        n = i // 4 + 1
        out = os.path.join(PREVIEW_DIR, f"lb_chunk{n}.jpg")
        print(f"chunk{n} ->", renderer.render_rows(entries[i:i + 4], out))
    print("elo curve ->", renderer.render_elo_curve(
        os.path.join(PREVIEW_DIR, "elo_curve.jpg"), k=ELO_K))
    print(f"\nOpen the files in {PREVIEW_DIR}")
