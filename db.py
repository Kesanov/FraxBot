"""SQLite storage for players and matches."""

import sqlite3
from contextlib import contextmanager

from config import DB_PATH, ELO_START, FACTIONS
import elo


@contextmanager
def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db():
    with _conn() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS players (
                user_id   TEXT PRIMARY KEY,
                name      TEXT NOT NULL,
                elo       INTEGER NOT NULL,
                wins      INTEGER NOT NULL DEFAULT 0,
                losses    INTEGER NOT NULL DEFAULT 0,
                streak    INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS matches (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                winner_id       TEXT NOT NULL,
                loser_id        TEXT NOT NULL,
                winner_faction  TEXT,
                winner_ultimate TEXT,
                loser_faction   TEXT,
                loser_ultimate  TEXT,
                delta           INTEGER NOT NULL,
                played_at       TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )
        # migrate older DBs that predate the streak column
        cols = [r[1] for r in con.execute("PRAGMA table_info(players)").fetchall()]
        if "streak" not in cols:
            con.execute("ALTER TABLE players ADD COLUMN streak INTEGER NOT NULL DEFAULT 0")


def _ensure_player(con, user_id: str, name: str):
    """Return (elo, streak), creating the player if needed."""
    row = con.execute("SELECT * FROM players WHERE user_id=?", (user_id,)).fetchone()
    if row is None:
        con.execute(
            "INSERT INTO players (user_id, name, elo) VALUES (?,?,?)",
            (user_id, name, ELO_START),
        )
        return ELO_START, 0
    # keep name fresh
    con.execute("UPDATE players SET name=? WHERE user_id=?", (name, user_id))
    return row["elo"], row["streak"]


def record_match(winner, loser, w_faction, w_ult, l_faction, l_ult):
    """winner/loser are (user_id, name) tuples. Returns dict with new ratings."""
    w_id, w_name = str(winner[0]), winner[1]
    l_id, l_name = str(loser[0]), loser[1]
    with _conn() as con:
        w_elo, w_streak = _ensure_player(con, w_id, w_name)
        l_elo, l_streak = _ensure_player(con, l_id, l_name)
        new_w, new_l, delta = elo.update_ratings(w_elo, l_elo)
        new_w_streak = w_streak + 1 if w_streak > 0 else 1
        new_l_streak = l_streak - 1 if l_streak < 0 else -1
        con.execute(
            "UPDATE players SET elo=?, wins=wins+1, streak=? WHERE user_id=?",
            (new_w, new_w_streak, w_id),
        )
        con.execute(
            "UPDATE players SET elo=?, losses=losses+1, streak=? WHERE user_id=?",
            (new_l, new_l_streak, l_id),
        )
        con.execute(
            """INSERT INTO matches
               (winner_id, loser_id, winner_faction, winner_ultimate,
                loser_faction, loser_ultimate, delta)
               VALUES (?,?,?,?,?,?,?)""",
            (w_id, l_id, w_faction, w_ult, l_faction, l_ult, delta),
        )
    return {"winner_elo": new_w, "loser_elo": new_l, "delta": delta}


def get_player(user_id):
    """Return a player's row as a dict, or None if they've never played."""
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM players WHERE user_id=?", (str(user_id),)).fetchone()
    return dict(row) if row else None


def preview_match(winner_id, loser_id):
    """Compute the projected ELO outcome WITHOUT writing anything."""
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
