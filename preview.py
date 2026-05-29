"""Generate sample cards locally so you can eyeball the visuals without Discord.

    python preview.py

Renders the leaderboard and a result card to JPG in discord/preview_output/.
"""

import os

from config import PREVIEW_DIR
from cards import model, svg_renderer as renderer

SAMPLE_PLAYERS = [
    {"user_id": "1", "name": "Markal",     "elo": 1672, "wins": 41, "losses": 9},
    {"user_id": "2", "name": "Zehir",      "elo": 1540, "wins": 33, "losses": 14},
    {"user_id": "3", "name": "Findan",     "elo": 1488, "wins": 28, "losses": 16},
    {"user_id": "4", "name": "Isabel",     "elo": 1330, "wins": 22, "losses": 18},
    {"user_id": "5", "name": "Raelag",     "elo": 1275, "wins": 19, "losses": 17},
    {"user_id": "6", "name": "Kujin",      "elo": 1180, "wins": 15, "losses": 15},
    {"user_id": "7", "name": "Wulfstan",   "elo": 1095, "wins": 11, "losses": 14},
    {"user_id": "8", "name": "Nadia",      "elo": 1010, "wins": 8,  "losses": 12},
    {"user_id": "9", "name": "Gotai",      "elo": 970,  "wins": 6,  "losses": 13},
    {"user_id": "10", "name": "Sandro",    "elo": 905,  "wins": 4,  "losses": 16},
]

SAMPLE_WINNER = {"name": "Markal", "faction": "Necropolis",
                 "ultimate": "Eternal Servitude", "elo": 1704}
SAMPLE_LOSER = {"name": "Zehir", "faction": "Academy",
                "ultimate": "Arcane Omniscience", "elo": 1508}
SAMPLE_DELTA = 32


if __name__ == "__main__":
    entries = model.build_entries(SAMPLE_PLAYERS)
    lb = renderer.render_leaderboard(
        entries, os.path.join(PREVIEW_DIR, "leaderboard.jpg"),
        subheading="Top 10 players  ·  preview",
    )
    res = renderer.render_result(
        SAMPLE_WINNER, SAMPLE_LOSER, SAMPLE_DELTA,
        os.path.join(PREVIEW_DIR, "result.jpg"),
    )
    print(f"leaderboard -> {lb}")
    print(f"result      -> {res}")
    print(f"\nOpen the files in {PREVIEW_DIR}")
