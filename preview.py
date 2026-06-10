"""Generate sample cards locally so you can eyeball the visuals without Discord.

    python preview.py [--mock]

Renders the leaderboard, a result card, the ELO curve, and the stats sections
to .webp in the cache dir. Stats use real DB data when available; pass --mock
(or run with an empty DB) to force the sample data below.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
import db
from config import ELO_K
from cards import model, svg_renderer as renderer

CACHE = config.CACHE_DIR


# --- Leaderboard / result sample data --------------------------------------
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

SAMPLE_WINNER = {"name": "Kesanov", "faction": "Dungeon: Warlock",
                 "ultimate": "Frax Essence", "elo": 1420}
SAMPLE_LOSER = {"name": "Valdris", "faction": "Haven: Warrior",
                "ultimate": "Angelic Alliance", "elo": 1338}
SAMPLE_DELTA = 28


# --- Stats sample data (used when the DB is empty or --mock) ----------------
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


MOCK_FF_DATA = {
    "Haven":      {"Sylvan": _fc(12, 8),  "Academy": _fc(7, 13), "Dungeon": _fc(5, 15),
                   "Necropolis": _fc(10, 10), "Inferno": _fc(14, 6), "Fortress": _fc(9, 11), "Stronghold": _fc(11, 9)},
    "Sylvan":     {"Haven": _fc(8, 12),   "Academy": _fc(13, 7), "Dungeon": _fc(6, 14),
                   "Necropolis": _fc(11, 9), "Inferno": _fc(9, 11), "Fortress": _fc(15, 5), "Stronghold": _fc(7, 13)},
    "Academy":    {"Haven": _fc(13, 7),   "Sylvan": _fc(7, 13),  "Dungeon": _fc(10, 10),
                   "Necropolis": _fc(8, 12), "Inferno": _fc(12, 8), "Fortress": _fc(6, 14), "Stronghold": _fc(14, 6)},
    "Dungeon":    {"Haven": _fc(15, 5),   "Sylvan": _fc(14, 6),  "Academy": _fc(10, 10),
                   "Necropolis": _fc(13, 7), "Inferno": _fc(11, 9), "Fortress": _fc(9, 11), "Stronghold": _fc(8, 12)},
    "Necropolis": {"Haven": _fc(10, 10),  "Sylvan": _fc(9, 11),  "Academy": _fc(12, 8),
                   "Dungeon": _fc(7, 13), "Inferno": _fc(14, 6),  "Fortress": _fc(11, 9), "Stronghold": _fc(6, 14)},
    "Inferno":    {"Haven": _fc(6, 14),   "Sylvan": _fc(11, 9),  "Academy": _fc(8, 12),
                   "Dungeon": _fc(9, 11), "Necropolis": _fc(6, 14), "Fortress": _fc(13, 7), "Stronghold": _fc(10, 10)},
    "Fortress":   {"Haven": _fc(11, 9),   "Sylvan": _fc(5, 15),  "Academy": _fc(14, 6),
                   "Dungeon": _fc(11, 9), "Necropolis": _fc(9, 11), "Inferno": _fc(7, 13), "Stronghold": _fc(12, 8)},
    "Stronghold": {"Haven": _fc(9, 11),   "Sylvan": _fc(13, 7),  "Academy": _fc(6, 14),
                   "Dungeon": _fc(12, 8), "Necropolis": _fc(14, 6), "Inferno": _fc(10, 10), "Fortress": _fc(8, 12)},
}

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


def _out(name):
    return os.path.join(CACHE, name)


def render_leaderboard():
    names = {p["user_id"]: p["name"] for p in SAMPLE_PLAYERS}
    entries = model.build_entries(SAMPLE_PLAYERS, name_resolver=names.get)
    print("header   ->", renderer.render_header(_out("lb_header.jpg")))
    for i in range(0, len(entries), 4):
        n = i // 4 + 1
        print(f"chunk{n}   ->", renderer.render_rows(entries[i:i + 4], _out(f"lb_chunk{n}.jpg")))
    print("elo curve->", renderer.render_elo_curve(_out("elo_curve.jpg"), k=ELO_K))


def render_result():
    print("result   ->", renderer.render_result(
        SAMPLE_WINNER, SAMPLE_LOSER, SAMPLE_DELTA, _out("result.jpg"),
        winner_avatar=model.default_avatar(SAMPLE_WINNER["name"]),
        loser_avatar=model.default_avatar(SAMPLE_LOSER["name"]),
    ))


def render_stats(use_mock):
    if not use_mock:
        try:
            db.init_db()
            ult_rows  = db.ultimate_stats()
            fac_rows  = db.faction_stats()
            cls_rows  = db.class_stats()
            frax_rows = db.frax_by_faction()
            fc_rows   = db.faction_class_stats()
            ff_rows   = db.faction_faction_stats() if hasattr(db, "faction_faction_stats") else MOCK_FF_DATA
            if not any(r["games"] for r in ult_rows):
                raise ValueError("empty db")
        except Exception as e:
            print(f"DB empty or unavailable ({e}), using mock data.")
            use_mock = True

    if use_mock:
        ult_rows, fac_rows, cls_rows = MOCK_ULTIMATES, MOCK_FACTIONS, MOCK_CLASSES
        frax_rows, fc_rows, ff_rows = MOCK_FRAX, MOCK_FC_DATA, MOCK_FF_DATA

    renders = [
        ("h1_ult", lambda: renderer.render_stats_header_img("Ultimate winrate", _out("preview_h1_ult.webp"))),
        ("s1_ult", lambda: renderer.render_ult_section_img(ult_rows, frax_rows, _out("preview_s1_ult.webp"))),
        ("h2_fac", lambda: renderer.render_stats_header_img("Faction winrate", _out("preview_h2_fac.webp"))),
        ("s2_fac", lambda: renderer.render_faction_section_img(fac_rows, fc_rows, _out("preview_s2_fac.webp"))),
        ("s3_ff",  lambda: renderer.render_faction_ff_section_img(ff_rows, _out("preview_s3_ff.webp"))),
        ("h4_cls", lambda: renderer.render_stats_header_img("Class winrate", _out("preview_h4_cls.webp"))),
        ("s4_cls", lambda: renderer.render_class_section_img(cls_rows, _out("preview_s4_cls.webp"))),
    ]
    for name, fn in renders:
        print(f"{name}   ->", fn())


def main():
    use_mock = "--mock" in sys.argv
    render_leaderboard()
    render_result()
    render_stats(use_mock)
    print(f"\nOpen the files in {CACHE}")


if __name__ == "__main__":
    main()
