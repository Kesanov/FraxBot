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

    Blend patches in order: EffWr(p) = (W(p) + wt*EffWr(p-1)) / (G(p) + wt)
    where wt = min(∑G(prev), STAT_PRIOR).
    """
    w_by, l_by = wins.get(key, {}), losses.get(key, {})
    eff = total_prev = 0

    for v in sorted(set(w_by) | set(l_by)):
        w, l = w_by.get(v, 0), l_by.get(v, 0)
        g = w + l
        wt = min(total_prev, STAT_PRIOR)
        eff = (w + wt * eff) / (g + wt)
        total_prev += g

    return round(100 * eff), sum(w_by.values()), sum(l_by.values())


@contextmanager
def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    # WAL lets readers and a writer coexist; busy_timeout makes a connection wait
    # for a lock instead of raising 'database is locked' immediately, which matters
    # once stats queries and match writes can overlap across threads.
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA busy_timeout = 5000")
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
                streak    INTEGER NOT NULL DEFAULT 0,
                peak_elo  INTEGER NOT NULL DEFAULT 0
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
        # Migrate older DBs that predate peak_elo, then backfill peaks by replaying
        # match history (winner +delta, loser -delta from ELO_START).
        if "peak_elo" not in {r["name"] for r in con.execute("PRAGMA table_info(players)")}:
            con.execute("ALTER TABLE players ADD COLUMN peak_elo INTEGER NOT NULL DEFAULT 0")
        if con.execute("SELECT COUNT(*) FROM players WHERE peak_elo=0").fetchone()[0]:
            _backfill_peaks(con)


def _backfill_peaks(con):
    """Replay all matches in order to set each player's all-time ELO peak."""
    cur = {}   # user_id -> running elo
    peak = {}  # user_id -> max elo seen
    for w, l, d in con.execute(
        "SELECT winner_id, loser_id, delta FROM matches ORDER BY id"
    ):
        for uid in (w, l):
            if uid not in cur:
                cur[uid] = peak[uid] = ELO_START
        cur[w] += d
        cur[l] -= d
        peak[w] = max(peak[w], cur[w])
        peak[l] = max(peak[l], cur[l])
    for uid, elo_val in con.execute("SELECT user_id, elo FROM players").fetchall():
        con.execute("UPDATE players SET peak_elo=? WHERE user_id=?",
                    (max(peak.get(uid, elo_val), elo_val), uid))


def _ensure_player(con, user_id: str):
    row = con.execute("SELECT elo, streak FROM players WHERE user_id=?", (user_id,)).fetchone()
    if row is None:
        con.execute("INSERT INTO players (user_id, elo, peak_elo) VALUES (?,?,?)",
                    (user_id, ELO_START, ELO_START))
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
            "UPDATE players SET elo=?, wins=wins+1, streak=?, peak_elo=MAX(peak_elo,?) "
            "WHERE user_id=?",
            (new_w, w_streak + 1 if w_streak > 0 else 1, new_w, w_id),
        )
        con.execute(
            "UPDATE players SET elo=?, losses=losses+1, streak=?, peak_elo=MAX(peak_elo,?) "
            "WHERE user_id=?",
            (new_l, l_streak - 1 if l_streak < 0 else -1, new_l, l_id),
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


def player_breakdown(user_id):
    """Per-player record split by faction, ultimate and class.

    Raw counts (no version weighting / mirror exclusion): every game the player
    played counts for whatever they picked. Returns:
        {"factions": [...FACTIONS order...],
         "ultimates": [...sorted by games desc...],
         "classes":  [...CLASSES order...]}
    each entry a dict with wins/losses/games/winrate (+ name key).
    """
    uid = str(user_id)

    def _tally(col):
        """{value: [wins, losses]} for the player's matches grouped by `col`."""
        out = {}
        with _conn() as con:
            for val, w in con.execute(
                f"SELECT winner_{col}, 1 FROM matches WHERE winner_id=? "
                f"UNION ALL SELECT loser_{col}, 0 FROM matches WHERE loser_id=?",
                (uid, uid),
            ):
                if val is None:
                    continue
                rec = out.setdefault(val, [0, 0])
                rec[0 if w else 1] += 1
        return out

    def _entry(key, name, wins, losses):
        g = wins + losses
        return {key: name, "wins": wins, "losses": losses, "games": g,
                "winrate": round(100 * wins / g) if g else 0}

    fac = _tally("faction")
    factions = [_entry("faction", f, *fac.get(f, (0, 0))) for f in FACTIONS]

    ult = _tally("ultimate")
    ultimates = [_entry("ultimate", u, w, l) for u, (w, l) in ult.items()]
    ultimates.sort(key=lambda r: r["games"], reverse=True)

    cls = _tally("class")
    classes = [_entry("class", c, *cls.get(i, (0, 0)))
               for i, c in enumerate(CLASSES)]

    return {"factions": factions, "ultimates": ultimates, "classes": classes}


def head_to_head(user_id):
    """Per-opponent record for a player: [{opponent_id, wins, losses, games}], games desc.

    `wins` = times this player beat that opponent; `losses` = times they lost to them.
    """
    uid = str(user_id)
    rec = {}  # opponent_id -> [wins, losses]
    with _conn() as con:
        for opp, w in con.execute(
            "SELECT loser_id, 1 FROM matches WHERE winner_id=? "
            "UNION ALL SELECT winner_id, 0 FROM matches WHERE loser_id=?",
            (uid, uid),
        ):
            r = rec.setdefault(opp, [0, 0])
            r[0 if w else 1] += 1
    out = [{"opponent_id": opp, "wins": w, "losses": l, "games": w + l}
           for opp, (w, l) in rec.items()]
    out.sort(key=lambda r: r["games"], reverse=True)
    return out


def preview_match(winner_id, loser_id):
    """Compute the projected ELO outcome without writing anything."""
    wp = get_player(winner_id)
    lp = get_player(loser_id)
    w_elo = wp["elo"] if wp else ELO_START
    l_elo = lp["elo"] if lp else ELO_START
    new_w, new_l, delta = elo.update_ratings(w_elo, l_elo)
    return {"winner_elo": new_w, "loser_elo": new_l, "delta": delta}


def leaderboard_rank(user_id):
    """Return (rank, total) by ELO standing (1-based), or (None, total) if absent."""
    uid = str(user_id)
    with _conn() as con:
        total = con.execute("SELECT COUNT(*) FROM players").fetchone()[0]
        row = con.execute("SELECT elo FROM players WHERE user_id=?", (uid,)).fetchone()
        if row is None:
            return None, total
        ahead = con.execute(
            "SELECT COUNT(*) FROM players WHERE elo > ?", (row["elo"],)
        ).fetchone()[0]
    return ahead + 1, total


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
