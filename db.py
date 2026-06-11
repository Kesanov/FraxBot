"""SQLite storage for players and matches."""

import sqlite3
from contextlib import contextmanager

from config import DB_PATH, ELO_START, FACTIONS, CLASSES, VERSION, STAT_PRIOR
import elo

VERSION_STR = ".".join(str(p) for p in VERSION)


def _vtuple(s):
    """Parse a 'a.b.c' version string into a tuple for ordering. Unknown -> (0,)."""
    try:
        return tuple(int(x) for x in str(s).split("."))
    except (ValueError, AttributeError):
        return (0,)


def _bucketed(rows):
    """rows of (key, version, count) -> {key: {version_tuple: count}}."""
    out = {}
    for key, ver, cnt in rows:
        out.setdefault(key, {})[_vtuple(ver)] = cnt
    return out


def _weighted(key, wins, losses):
    """Fold a bucket's per-version record into one (winrate%, total_wins, total_losses).

    Recurrence over patches in ascending order, skipping patches with no games:
        EffWr(p) = (G(p)*RawWr(p) + STAT_PRIOR*EffWr(p-1)) / (G(p) + STAT_PRIOR)
    The earliest patch with games seeds EffWr with its raw winrate (no prior).
    Reported games are the real total across all patches.
    """
    w_by, l_by = wins.get(key, {}), losses.get(key, {})
    eff = None
    for v in sorted(set(w_by) | set(l_by)):
        w, l = w_by.get(v, 0), l_by.get(v, 0)
        g = w + l
        if g == 0:
            continue
        raw = w / g
        eff = raw if eff is None else (g * raw + STAT_PRIOR * eff) / (g + STAT_PRIOR)
    tw, tl = sum(w_by.values()), sum(l_by.values())
    winrate = round(100 * eff) if eff is not None else 0
    return winrate, tw, tl


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
                played_at       TEXT NOT NULL DEFAULT (datetime('now')),
                version         TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_matches_winner ON matches(winner_id);
            CREATE INDEX IF NOT EXISTS idx_matches_loser  ON matches(loser_id);
        """)
        # Migrate older DBs that predate the `version` column.
        cols = {r["name"] for r in con.execute("PRAGMA table_info(matches)")}
        if "version" not in cols:
            con.execute("ALTER TABLE matches ADD COLUMN version TEXT")
        # Backfill any unstamped matches as the current patch (chosen baseline:
        # all existing history counts as the current version).
        con.execute(
            "UPDATE matches SET version=? WHERE version IS NULL", (VERSION_STR,)
        )


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
                delta, version)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (w_id, l_id, w_faction, _class_id(w_class), w_ult, l_faction, _class_id(l_class), l_ult, delta, VERSION_STR),
        )
    return {"winner_elo": new_w, "loser_elo": new_l, "delta": delta}


def match_count() -> int:
    with _conn() as con:
        return con.execute("SELECT COUNT(*) FROM matches").fetchone()[0]


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
    """Global per-faction record, mirrors excluded, sorted by winrate then games (desc)."""
    with _conn() as con:
        wins = _bucketed(con.execute(
            "SELECT winner_faction, version, COUNT(*) FROM matches "
            "WHERE winner_faction != loser_faction GROUP BY winner_faction, version"
        ))
        losses = _bucketed(con.execute(
            "SELECT loser_faction, version, COUNT(*) FROM matches "
            "WHERE winner_faction != loser_faction GROUP BY loser_faction, version"
        ))
    out = []
    for f in FACTIONS:
        wr, w, l = _weighted(f, wins, losses)
        out.append({"faction": f, "wins": w, "losses": l, "games": w + l,
                    "winrate": wr})
    out.sort(key=lambda r: (r["winrate"], r["games"]), reverse=True)
    return out


def ultimate_stats():
    """Global per-ultimate record, mirrors excluded, sorted by popularity (games desc)."""
    from config import ULTIMATES
    with _conn() as con:
        wins = _bucketed(con.execute(
            "SELECT winner_ultimate, version, COUNT(*) FROM matches "
            "WHERE winner_ultimate != loser_ultimate GROUP BY winner_ultimate, version"
        ))
        losses = _bucketed(con.execute(
            "SELECT loser_ultimate, version, COUNT(*) FROM matches "
            "WHERE winner_ultimate != loser_ultimate GROUP BY loser_ultimate, version"
        ))
    out = []
    for u in ULTIMATES:
        wr, w, l = _weighted(u, wins, losses)
        out.append({"ultimate": u, "wins": w, "losses": l, "games": w + l,
                    "winrate": wr})
    out.sort(key=lambda r: r["games"], reverse=True)
    return out


def frax_by_faction():
    """Frax Essence winrate broken down by faction, mirrors excluded, in FACTIONS order."""
    with _conn() as con:
        wins = _bucketed(con.execute(
            "SELECT winner_faction, version, COUNT(*) FROM matches "
            "WHERE winner_ultimate='Frax Essence' AND loser_ultimate != 'Frax Essence' "
            "GROUP BY winner_faction, version"
        ))
        losses = _bucketed(con.execute(
            "SELECT loser_faction, version, COUNT(*) FROM matches "
            "WHERE loser_ultimate='Frax Essence' AND winner_ultimate != 'Frax Essence' "
            "GROUP BY loser_faction, version"
        ))
    out = []
    for f in FACTIONS:
        wr, w, l = _weighted(f, wins, losses)
        out.append({"faction": f, "wins": w, "losses": l, "games": w + l,
                    "winrate": wr})
    return out


def faction_class_stats():
    """WR for each (faction, class) pair, mirrors excluded. Returns {faction: [cls0, cls1, cls2]}."""
    with _conn() as con:
        wins = _bucketed(
            ((f, ci), ver, cnt) for f, ci, ver, cnt in con.execute(
                "SELECT winner_faction, winner_class, version, COUNT(*) FROM matches "
                "WHERE winner_faction IS NOT NULL AND winner_class IS NOT NULL "
                "AND NOT (winner_faction = loser_faction AND winner_class = loser_class) "
                "GROUP BY winner_faction, winner_class, version"
            )
        )
        losses = _bucketed(
            ((f, ci), ver, cnt) for f, ci, ver, cnt in con.execute(
                "SELECT loser_faction, loser_class, version, COUNT(*) FROM matches "
                "WHERE loser_faction IS NOT NULL AND loser_class IS NOT NULL "
                "AND NOT (winner_faction = loser_faction AND winner_class = loser_class) "
                "GROUP BY loser_faction, loser_class, version"
            )
        )
    out = {}
    for f in FACTIONS:
        row = []
        for i, _ in enumerate(CLASSES):
            wr, w, l = _weighted((f, i), wins, losses)
            row.append({"wins": w, "losses": l, "games": w + l, "winrate": wr})
        out[f] = row
    return out


def faction_faction_stats():
    """WR for each ordered faction pair, mirrors excluded. Returns {fac_a: {fac_b: {games, winrate}}}."""
    with _conn() as con:
        wins = _bucketed(
            ((wf, lf), ver, cnt) for wf, lf, ver, cnt in con.execute(
                "SELECT winner_faction, loser_faction, version, COUNT(*) FROM matches "
                "WHERE winner_faction != loser_faction "
                "GROUP BY winner_faction, loser_faction, version"
            )
        )
        losses = _bucketed(
            ((wf, lf), ver, cnt) for wf, lf, ver, cnt in con.execute(
                "SELECT loser_faction, winner_faction, version, COUNT(*) FROM matches "
                "WHERE winner_faction != loser_faction "
                "GROUP BY loser_faction, winner_faction, version"
            )
        )
    out = {}
    for fa in FACTIONS:
        out[fa] = {}
        for fb in FACTIONS:
            if fa == fb:
                continue
            wr, w, l = _weighted((fa, fb), wins, losses)
            out[fa][fb] = {"wins": w, "losses": l, "games": w + l, "winrate": wr}
    return out


def class_stats():
    """Global per-class record, mirrors excluded (Warrior/Warmage/Warlock), original order."""
    with _conn() as con:
        wins = _bucketed(con.execute(
            "SELECT winner_class, version, COUNT(*) FROM matches "
            "WHERE winner_class != loser_class GROUP BY winner_class, version"
        ))
        losses = _bucketed(con.execute(
            "SELECT loser_class, version, COUNT(*) FROM matches "
            "WHERE winner_class != loser_class GROUP BY loser_class, version"
        ))
    out = []
    for i, c in enumerate(CLASSES):
        wr, w, l = _weighted(i, wins, losses)
        out.append({"class": c, "wins": w, "losses": l, "games": w + l,
                    "winrate": wr})
    return out
