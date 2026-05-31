"""Render a result card preview into cache and print the path.

    python preview_report.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from cards import svg_renderer as renderer

MOCK_WINNER = {
    "name":     "Kesanov",
    "faction":  "Dungeon: Warlock",
    "ultimate": "Frax Essence",
    "elo":      1420,
}
MOCK_LOSER = {
    "name":     "Valdris",
    "faction":  "Haven: Warrior",
    "ultimate": "Angelic Alliance",
    "elo":      1338,
}
MOCK_DELTA = 28


def main():
    out = os.path.join(config.CACHE_DIR, "preview_report.webp")
    path = renderer.render_result(MOCK_WINNER, MOCK_LOSER, MOCK_DELTA, out)
    print(f"Rendered report: {path}")


if __name__ == "__main__":
    main()
