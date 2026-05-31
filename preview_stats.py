"""Render a stats card preview and open it.

Uses real DB data when available, otherwise falls back to mock data.

    python preview_stats.py [--mock]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
import db
from cards import svg_renderer as renderer

CACHE = config.CACHE_DIR

MOCK_ULTIMATES = [
    {"ultimate": u, "wins": w, "losses": l, "games": w + l,
     "winrate": round(100 * w / (w + l)) if w + l else 0}
    for u, w, l in [
        ("Master of Creation", 14, 6), ("Angelic Alliance", 11, 9),
        ("Blood Frenzy", 9, 11),       ("Forest Rage", 13, 7),
        ("Howl of Terror", 8, 12),     ("Mithral Plating", 10, 5),
        ("Arcane Omniscience", 7, 8),  ("Undying Thirst", 12, 8),
        ("Nature's Luck", 5, 10),      ("Absolute Empathy", 9, 6),
        ("Master of Death", 6, 9),     ("Runic Protection", 11, 4),
        ("Runic Excelence", 7, 7),     ("Might over Magic", 10, 10),
        ("Forgotten Witchcraft", 8, 7),("Frax Essence", 4, 11),
        ("Master of Destruction", 6, 8),("Master of Life", 9, 5),
        ("Blood Thirst", 3, 12),
    ]
]
MOCK_ULTIMATES.sort(key=lambda r: r["games"], reverse=True)

MOCK_FACTIONS = [
    {"faction": f, "wins": w, "losses": l, "games": w + l,
     "winrate": round(100 * w / (w + l))}
    for f, w, l in [
        ("Haven", 22, 18), ("Sylvan", 19, 21), ("Academy", 17, 23),
        ("Dungeon", 25, 15), ("Necropolis", 20, 20), ("Inferno", 14, 26),
        ("Fortress", 18, 22), ("Stronghold", 21, 19),
    ]
]

MOCK_CLASSES = [
    {"class": c, "wins": w, "losses": l, "games": w + l,
     "winrate": round(100 * w / (w + l))}
    for c, w, l in [("Warrior", 45, 35), ("Warmage", 38, 42), ("Warlock", 50, 30)]
]


MOCK_FRAX = [
    {"faction": f, "wins": w, "losses": l, "games": w + l,
     "winrate": round(100 * w / (w + l)) if w + l else 0}
    for f, w, l in [
        ("Haven", 3, 1), ("Sylvan", 1, 3), ("Academy", 2, 2),
        ("Dungeon", 4, 0), ("Necropolis", 0, 4), ("Inferno", 1, 2),
        ("Fortress", 2, 1), ("Stronghold", 0, 3),
    ]
]

def _fc(w, l):
    g = w + l
    return {"wins": w, "losses": l, "games": g, "winrate": round(100 * w / g) if g else 0}

MOCK_FC_DATA = {
    "Haven":      [_fc(12, 8),  _fc(7, 13),  _fc(0, 0)],
    "Sylvan":     [_fc(9, 11),  _fc(0, 0),   _fc(10, 10)],
    "Academy":    [_fc(6, 14),  _fc(11, 9),  _fc(8, 12)],
    "Dungeon":    [_fc(15, 5),  _fc(0, 0),   _fc(13, 7)],
    "Necropolis": [_fc(10, 10), _fc(9, 11),  _fc(0, 0)],
    "Inferno":    [_fc(7, 13),  _fc(5, 15),  _fc(6, 14)],
    "Fortress":   [_fc(0, 0),   _fc(14, 6),  _fc(9, 11)],
    "Stronghold": [_fc(11, 9),  _fc(8, 12),  _fc(0, 0)],
}


def main():
    use_mock = "--mock" in sys.argv
    if not use_mock:
        try:
            db.init_db()
            ult_rows  = db.ultimate_stats()
            fac_rows  = db.faction_stats()
            cls_rows  = db.class_stats()
            frax_rows = db.frax_by_faction()
            fc_rows   = db.faction_class_stats()
            if not any(r["games"] for r in ult_rows):
                raise ValueError("empty db")
        except Exception as e:
            print(f"DB empty or unavailable ({e}), using mock data.")
            use_mock = True

    if use_mock:
        ult_rows  = MOCK_ULTIMATES
        fac_rows  = MOCK_FACTIONS
        cls_rows  = MOCK_CLASSES
        frax_rows = MOCK_FRAX
        fc_rows   = MOCK_FC_DATA

    def _out(name):
        return os.path.join(CACHE, f"preview_{name}.webp")

    renders = [
        ("h1_ult",   lambda: renderer.render_stats_header_img("Ultimate Winrate",  _out("h1_ult"))),
        ("s1_ult",   lambda: renderer.render_ult_section_img(ult_rows, frax_rows,  _out("s1_ult"))),
        ("h2_fac",   lambda: renderer.render_stats_header_img("Faction Winrate",      _out("h2_fac"))),
        ("s2_fac",   lambda: renderer.render_faction_section_img(fac_rows, fc_rows, _out("s2_fac"))),
        ("h3_cls",   lambda: renderer.render_stats_header_img("Class Winrate",      _out("h3_cls"))),
        ("s3_cls",   lambda: renderer.render_class_section_img(cls_rows, _out("s3_cls"))),
    ]

    for name, fn in renders:
        path = fn()
        print(f"Rendered {name}: {path}")


if __name__ == "__main__":
    main()
