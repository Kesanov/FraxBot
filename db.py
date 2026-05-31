"""SQLite storage for players and matches."""

import sqlite3
from contextlib import contextmanager

from config import DB_PATH, ELO_START, FACTIONS, CLASSES
import elo


@contextmanager
def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()



def _class_id(name: str | None) -> int | None:
    if name is None:
        return None
    try:
        return CLASSES.index(name)
    except ValueError:
        return None



def init_db():
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS players (
                user_id   TEXT PRIMARY KEY,
                elo       INTEGER NOT NULL,
                wins      INTEGER NOT NULL DEFAULT 0,
                losses    INTEGER NOT NULL DEFAULT 0,
                streak    INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS matches (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                winner_id       TEXT NOT NULL REFERENCES players(user_id),
                loser_id        TEXT NOT NULL REFERENCES players(user_id),
                winner_faction  TEXT,
                winner_class    INTEGER,
                winner_ultimate TEXT,
                loser_faction   TEXT,
                loser_class     INTEGER,
                loser_ultimate  TEXT,
                delta           INTEGER NOT NULL DEFAULT 0,
                played_at       TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_matches_winner ON matches(winner_id);
            CREATE INDEX IF NOT EXISTS idx_matches_loser  ON matches(loser_id);
        """)


def _ensure_player(con, user_id: str):
    row = con.execute("SELECT elo, streak FROM players WHERE user_id=?", (user_id,)).fetchone()
    if row is None:
        con.execute("INSERT INTO players (user_id, elo) VALUES (?,?)", (user_id, ELO_START))
        return ELO_START, 0
    return row["elo"], row["streak"]


def record_match(winner_id, loser_id, w_faction, w_class, w_ult, l_faction, l_class, l_ult):
    """Record a confirmed match. Returns dict with new ratings and delta."""
    w_id, l_id = str(winner_id), str(loser_id)
    with _conn() as con:
        w_elo, w_streak = _ensure_player(con, w_id)
        l_elo, l_streak = _ensure_player(con, l_id)
        new_w, new_l, delta = elo.update_ratings(w_elo, l_elo)
        con.execute(
            "UPDATE players SET elo=?, wins=wins+1, streak=? WHERE user_id=?",
            (new_w, w_streak + 1 if w_streak > 0 else 1, w_id),
        )
        con.execute(
            "UPDATE players SET elo=?, losses=losses+1, streak=? WHERE user_id=?",
            (new_l, l_streak - 1 if l_streak < 0 else -1, l_id),
        )
        con.execute(
            """INSERT INTO matches
               (winner_id, loser_id,
                winner_faction, winner_class, winner_ultimate,
                loser_faction,  loser_class,  loser_ultimate,
                delta)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (w_id, l_id, w_faction, _class_id(w_class), w_ult, l_faction, _class_id(l_class), l_ult, delta),
        )
    return {"winner_elo": new_w, "loser_elo": new_l, "delta": delta}


def get_player(user_id):
    with _conn() as con:
        row = con.execute("SELECT * FROM players WHERE user_id=?", (str(user_id),)).fetchone()
    return dict(row) if row else None


def preview_match(winner_id, loser_id):
    """Compute the projected ELO outcome without writing anything."""
    wp = get_player(winner_id)
    lp = get_player(loser_id)
    w_elo = wp["elo"] if wp else ELO_START
    l_elo = lp["elo"] if lp else ELO_START
    new_w, new_l, delta = elo.update_ratings(w_elo, l_elo)
    return {"winner_elo": new_w, "loser_elo": new_l, "delta": delta}


def top_players(limit: int = 10):
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM players ORDER BY elo DESC, wins DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def faction_stats():
    """Global per-faction record, sorted by winrate then games (desc)."""
    with _conn() as con:
        wins = dict(con.execute(
            "SELECT winner_faction, COUNT(*) FROM matches GROUP BY winner_faction"
        ).fetchall())
        losses = dict(con.execute(
            "SELECT loser_faction, COUNT(*) FROM matches GROUP BY loser_faction"
        ).fetchall())
    out = []
    for f in FACTIONS:
        w, l = wins.get(f, 0), losses.get(f, 0)
        g = w + l
        out.append({"faction": f, "wins": w, "losses": l, "games": g,
                    "winrate": round(100 * w / g) if g else 0})
    out.sort(key=lambda r: (r["winrate"], r["games"]), reverse=True)
    return out


def ultimate_stats():
    """Global per-ultimate record, sorted by popularity (games desc)."""
    from config import ULTIMATES
    with _conn() as con:
        wins = dict(con.execute(
            "SELECT winner_ultimate, COUNT(*) FROM matches GROUP BY winner_ultimate"
        ).fetchall())
        losses = dict(con.execute(
            "SELECT loser_ultimate, COUNT(*) FROM matches GROUP BY loser_ultimate"
        ).fetchall())
    out = []
    for u in ULTIMATES:
        w, l = wins.get(u, 0), losses.get(u, 0)
        g = w + l
        out.append({"ultimate": u, "wins": w, "losses": l, "games": g,
                    "winrate": round(100 * w / g) if g else 0})
    out.sort(key=lambda r: r["games"], reverse=True)
    return out


def frax_by_faction():
    """Frax Essence winrate broken down by faction, in FACTIONS order."""
    with _conn() as con:
        wins = dict(con.execute(
            "SELECT winner_faction, COUNT(*) FROM matches "
            "WHERE winner_ultimate='Frax Essence' GROUP BY winner_faction"
        ).fetchall())
        losses = dict(con.execute(
            "SELECT loser_faction, COUNT(*) FROM matches "
            "WHERE loser_ultimate='Frax Essence' GROUP BY loser_faction"
        ).fetchall())
    out = []
    for f in FACTIONS:
        w, l = wins.get(f, 0), losses.get(f, 0)
        g = w + l
        out.append({"faction": f, "wins": w, "losses": l, "games": g,
                    "winrate": round(100 * w / g) if g else 0})
    return out


def faction_class_stats():
    """WR for each (faction, class) pair. Returns {faction: [cls0, cls1, cls2]}."""
    with _conn() as con:
        wins = {}
        for f, ci, cnt in con.execute(
            "SELECT winner_faction, winner_class, COUNT(*) FROM matches "
            "WHERE winner_faction IS NOT NULL AND winner_class IS NOT NULL "
            "GROUP BY winner_faction, winner_class"
        ):
            wins[(f, ci)] = cnt
        losses = {}
        for f, ci, cnt in con.execute(
            "SELECT loser_faction, loser_class, COUNT(*) FROM matches "
            "WHERE loser_faction IS NOT NULL AND loser_class IS NOT NULL "
            "GROUP BY loser_faction, loser_class"
        ):
            losses[(f, ci)] = cnt
    out = {}
    for f in FACTIONS:
        row = []
        for i, _ in enumerate(CLASSES):
            w = wins.get((f, i), 0)
            l = losses.get((f, i), 0)
            g = w + l
            row.append({"wins": w, "losses": l, "games": g,
                        "winrate": round(100 * w / g) if g else 0})
        out[f] = row
    return out


def class_stats():
    """Global per-class record (Warrior/Warmage/Warlock), original order."""
    with _conn() as con:
        wins = dict(con.execute(
            "SELECT winner_class, COUNT(*) FROM matches GROUP BY winner_class"
        ).fetchall())
        losses = dict(con.execute(
            "SELECT loser_class, COUNT(*) FROM matches GROUP BY loser_class"
        ).fetchall())
    out = []
    for i, c in enumerate(CLASSES):
        w, l = wins.get(i, 0), losses.get(i, 0)
        g = w + l
        out.append({"class": c, "wins": w, "losses": l, "games": g,
                    "winrate": round(100 * w / g) if g else 0})
    return out
