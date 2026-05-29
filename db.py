"""SQLite storage for players and matches."""

import sqlite3
from contextlib import contextmanager

from config import DB_PATH, ELO_START
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
                losses    INTEGER NOT NULL DEFAULT 0
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


def _ensure_player(con, user_id: str, name: str):
    row = con.execute("SELECT * FROM players WHERE user_id=?", (user_id,)).fetchone()
    if row is None:
        con.execute(
            "INSERT INTO players (user_id, name, elo) VALUES (?,?,?)",
            (user_id, name, ELO_START),
        )
        return ELO_START
    # keep name fresh
    con.execute("UPDATE players SET name=? WHERE user_id=?", (name, user_id))
    return row["elo"]


def record_match(winner, loser, w_faction, w_ult, l_faction, l_ult):
    """winner/loser are (user_id, name) tuples. Returns dict with new ratings."""
    w_id, w_name = str(winner[0]), winner[1]
    l_id, l_name = str(loser[0]), loser[1]
    with _conn() as con:
        w_elo = _ensure_player(con, w_id, w_name)
        l_elo = _ensure_player(con, l_id, l_name)
        new_w, new_l, delta = elo.update_ratings(w_elo, l_elo)
        con.execute(
            "UPDATE players SET elo=?, wins=wins+1 WHERE user_id=?", (new_w, w_id)
        )
        con.execute(
            "UPDATE players SET elo=?, losses=losses+1 WHERE user_id=?", (new_l, l_id)
        )
        con.execute(
            """INSERT INTO matches
               (winner_id, loser_id, winner_faction, winner_ultimate,
                loser_faction, loser_ultimate, delta)
               VALUES (?,?,?,?,?,?,?)""",
            (w_id, l_id, w_faction, w_ult, l_faction, l_ult, delta),
        )
    return {"winner_elo": new_w, "loser_elo": new_l, "delta": delta}


def top_players(limit: int = 10):
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM players ORDER BY elo DESC, wins DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
