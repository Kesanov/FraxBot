"""Render 10 leaderboard-cell palette variations for picking the best look.

    python variations.py

Outputs preview_output/variant_01.webp .. variant_10.webp (one chunk each).
Each varies the cell fill + border color/opacity only.
"""

import os

from config import PREVIEW_DIR
from cards import model, svg_renderer as r

PLAYERS = [
    {"user_id": "1", "name": "Markal", "elo": 1672, "wins": 41, "losses": 9,  "streak": 7},
    {"user_id": "2", "name": "Zehir",  "elo": 1540, "wins": 33, "losses": 14, "streak": 3},
    {"user_id": "3", "name": "Findan", "elo": 1488, "wins": 28, "losses": 16, "streak": 1},
    {"user_id": "4", "name": "Isabel", "elo": 1330, "wins": 22, "losses": 18, "streak": 0},
]

# (label, cell_fill, border_color, border_opacity)
VARIANTS = [
    ("rough-gold",      'fill="#14101f" fill-opacity="0.85"', "#8a6d3b", 0.7),
    ("bright-gold",     'fill="#1a1322" fill-opacity="0.85"', "#d4af37", 0.55),
    ("amber-glow",      'fill="#211608" fill-opacity="0.80"', "#c8902a", 0.85),
    ("bronze-warm",     'fill="#1c1410" fill-opacity="0.85"', "#a9743f", 0.8),
    ("royal-purple",    'fill="#171026" fill-opacity="0.85"', "#7c5cc4", 0.6),
    ("steel-slate",     'fill="#12141c" fill-opacity="0.85"', "#5a6b82", 0.7),
    ("emerald-edge",    'fill="#0f1a16" fill-opacity="0.85"', "#3f9c78", 0.6),
    ("crimson-edge",    'fill="#1c0f12" fill-opacity="0.85"', "#b24a4a", 0.6),
    ("pale-champagne",  'fill="#1a161f" fill-opacity="0.80"', "#e6cf9c", 0.45),
    ("no-fill-gold",    'fill="#000000" fill-opacity="0"',    "#c8902a", 0.9),
]


if __name__ == "__main__":
    entries = model.build_entries(PLAYERS)
    for i, (label, fill, edge, op) in enumerate(VARIANTS, start=1):
        r._CELL_FILL = fill
        r._GOLD_EDGE = edge
        r._CELL_STROKE_OPACITY = op
        out = os.path.join(PREVIEW_DIR, f"variant_{i:02d}.webp")
        print(f"{i:02d} {label:14s} ->", r.render_rows(entries, out))
    print(f"\nOpen variant_01..10 in {PREVIEW_DIR}")
