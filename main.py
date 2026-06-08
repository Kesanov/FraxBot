"""H5 Frax Discord ELO bot (FraxBot).

Run:
    $env:DISCORD_TOKEN = "..."
    $env:REPORTS_CHANNEL_ID = "..."        # where result cards are posted
    $env:LEADERBOARD_CHANNEL_ID = "..."   # where the ladder is auto-posted
    $env:WINRATE_CHANNEL_ID = "..."       # where daily stats cards are posted
    python main.py

Flow:
    /defeated @enemy -> the reporter gets a private (ephemeral) picker and selects
                        faction + ultimate for BOTH players, then submits. A public
                        message pings the enemy, who confirms with a 👍 reaction.
                        On confirmation the match is recorded, a result card is
                        posted, and the leaderboard refreshes.
"""

import asyncio
import base64
import hashlib
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field

import aiohttp
import discord
from discord import app_commands

import config
import db
from cards import model
from cards import svg_renderer as renderer

# Log to log.txt (and still echo to the console) so a crash leaves a trace.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler("log.txt", encoding="utf-8"),
              logging.StreamHandler()],
)
log = logging.getLogger("fraxbot")

CONFIRM_EMOJI = "👍"
DENY_EMOJI = "👎"


def _split_faction_class(combined: str | None) -> tuple[str | None, str | None]:
    if combined and ": " in combined:
        f, c = combined.split(": ", 1)
        return f, c
    return combined, None

# Default (non-privileged) intents are enough: slash commands resolve Member
# objects directly, reactions are in the default set, and avatars come via REST.
intents = discord.Intents.default()

client: discord.Client = None
tree: app_commands.CommandTree = None


def _make_client():
    global client, tree
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)
    client.event(on_raw_reaction_add)
    client.event(on_ready)
    tree.command(name="defeated", description="Report that you defeated another player.")(
        app_commands.describe(enemy="The player you defeated")(defeated)
    )
    tree.command(name="elo", description="Show a player's ELO, winrate and games.")(
        app_commands.describe(player="The player to look up")(elo_cmd)
    )


@dataclass
class PendingGame:
    winner: discord.Member          # the reporter
    loser: discord.Member           # the enemy who must confirm
    factions: dict = field(default_factory=lambda: {"winner": None, "loser": None})
    ultimates: dict = field(default_factory=lambda: {"winner": None, "loser": None})
    message: discord.Message = None  # the public confirmation message
    done: bool = False
    created: float = field(default_factory=time.monotonic)
    timeout_task: object = None      # asyncio task that expires the game


# Games awaiting the enemy's 👍, keyed by the public confirmation message id.
PENDING: dict[int, PendingGame] = {}

# Serializes leaderboard updates so the timer and post-game refresh can't race.
_leaderboard_lock = asyncio.Lock()

# Path to the pre-rendered header image (set once at startup, reused every refresh).
_cached_header_path: str | None = None

# Chunk render cache: chunk_index -> last_hash. Files are named lb_chunk_{i}.webp
# so there is always exactly one file per leaderboard position.
_chunk_cache: dict[int, str] = {}

# Stats header cache: title -> rendered file path. Headers never change so they
# are rendered once and reused on every daily refresh.
_stats_header_cache: dict[str, str] = {}

# on_ready fires on every gateway reconnect/resume, not just first launch. This
# guards the whole one-time init block (command sync, initial leaderboard +
# stats posts, daily loop) so a reconnect never re-posts or spawns a duplicate
# loop. Without it, every reconnect would repost the boards and stack another
# midnight stats loop, producing duplicates.
_initialized = False

# Serializes stats updates so the daily loop and any future trigger can't race
# through the delete-then-repost sequence at the same time (mirrors the
# leaderboard lock).
_stats_lock = asyncio.Lock()

# Drop pending games the enemy never confirmed after this many seconds.
PENDING_TTL = 24 * 3600

# How long the enemy has to confirm with 👍 before the game is discarded.
CONFIRM_TIMEOUT = 300  # 5 minutes

# Cache of rendered avatar data URIs: user_id -> (data_uri | None, fetched_at).
# Cache of display names: user_id -> (name | None, fetched_at).
# Both refreshed once a day since users can change them.
AVATAR_TTL = 24 * 3600
_avatar_cache: dict[str, tuple[str | None, float]] = {}
_name_cache: dict[str, tuple[str | None, float]] = {}


def _prune_pending():
    cutoff = time.monotonic() - PENDING_TTL
    for mid in [m for m, g in PENDING.items() if g.created < cutoff]:
        PENDING.pop(mid, None)


# --------------------------------------------------------------------------
# avatar helper
# --------------------------------------------------------------------------
async def _fetch_avatar(session, user) -> str | None:
    try:
        url = user.display_avatar.replace(size=128, format="png").url
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            data = await resp.read()
        b64 = base64.b64encode(data).decode()
        return f"data:image/png;base64,{b64}"
    except Exception:
        return None


async def get_avatar(session, user_id: str) -> str | None:
    """Return a cached avatar data URI, refreshing entries older than a day."""
    now = time.monotonic()
    cached = _avatar_cache.get(user_id)
    if cached and now - cached[1] < AVATAR_TTL:
        return cached[0]
    try:
        user = await client.fetch_user(int(user_id))
        data_uri = await _fetch_avatar(session, user)
    except Exception:
        data_uri = cached[0] if cached else None  # keep stale value on failure
    _avatar_cache[user_id] = (data_uri, now)
    return data_uri


async def get_display_name(user_id: str) -> str | None:
    """Return a cached server display name, refreshing entries older than a day."""
    now = time.monotonic()
    cached = _name_cache.get(user_id)
    if cached and now - cached[1] < AVATAR_TTL:
        return cached[0]
    try:
        uid = int(user_id)
        name = None
        for guild in client.guilds:
            try:
                member = await guild.fetch_member(uid)
                name = member.display_name
                break
            except discord.NotFound:
                continue
        if name is None:
            user = await client.fetch_user(uid)
            name = user.display_name
    except Exception:
        name = cached[0] if cached else None  # keep stale value on failure
    _name_cache[user_id] = (name, now)
    return name


# --------------------------------------------------------------------------
# Ephemeral picker — the reporter sets faction + ultimate for both players
# --------------------------------------------------------------------------
class FactionSelect(discord.ui.Select):
    def __init__(self, view, side, row):
        self._pview = view
        self.side = side  # "winner" or "loser"
        player = view.game.winner if side == "winner" else view.game.loser
        options = [
            discord.SelectOption(
                label=f"{f}: {c}",
                value=f"{f}: {c}",
                emoji=config.FACTION_EMOJI.get(f))
            for f in config.FACTIONS
            for c in config.CLASSES
        ]
        super().__init__(placeholder=f"{player.display_name}: Town & Class",
                         options=options, row=row)

    async def callback(self, interaction):
        self._pview.game.factions[self.side] = self.values[0]
        await interaction.response.defer()


class UltimateSelect(discord.ui.Select):
    def __init__(self, view, side, row):
        self._pview = view
        self.side = side
        player = view.game.winner if side == "winner" else view.game.loser
        options = [discord.SelectOption(label=u, value=u) for u in config.ULTIMATES]
        super().__init__(placeholder=f"{player.display_name}: Ultimate",
                         options=options, row=row)

    async def callback(self, interaction):
        self._pview.game.ultimates[self.side] = self.values[0]
        await interaction.response.defer()


class SubmitButton(discord.ui.Button):
    def __init__(self, view):
        self._pview = view
        super().__init__(label="Submit for confirmation", style=discord.ButtonStyle.success,
                         row=4)

    async def callback(self, interaction):
        await self._pview.submit(interaction)


class PickerView(discord.ui.View):
    """Shown only to the reporter (ephemeral)."""

    def __init__(self, game: PendingGame):
        super().__init__(timeout=300)
        self.game = game
        self.add_item(FactionSelect(self, "winner", row=0))
        self.add_item(UltimateSelect(self, "winner", row=1))
        self.add_item(FactionSelect(self, "loser", row=2))
        self.add_item(UltimateSelect(self, "loser", row=3))
        self.add_item(SubmitButton(self))

    async def submit(self, interaction):
        g = self.game
        if not (all(g.factions.values()) and all(g.ultimates.values())):
            await interaction.response.send_message(
                "Please select a faction and ultimate for both players first.", ephemeral=True)
            return
        # close the ephemeral picker
        await interaction.response.edit_message(content="Submitted.", view=None)

        # In test mode the match is recorded immediately (no confirmation).
        if config.TEST_MODE:
            before = _top16_ids()
            wf, wc = _split_faction_class(g.factions["winner"])
            lf, lc = _split_faction_class(g.factions["loser"])
            res = db.record_match(
                g.winner.id, g.loser.id,
                wf, wc, g.ultimates["winner"],
                lf, lc, g.ultimates["loser"])
            after = _top16_ids()
        else:
            res = db.preview_match(g.winner.id, g.loser.id)

        # render the result card immediately, with avatars
        async with aiohttp.ClientSession() as session:
            w_av = await get_avatar(session, str(g.winner.id))
            l_av = await get_avatar(session, str(g.loser.id))
        out = os.path.join(config.PREVIEW_DIR, f"result_{interaction.id}.jpg")
        winner = {"name": g.winner.display_name, "faction": g.factions["winner"],
                  "ultimate": g.ultimates["winner"], "elo": res["winner_elo"]}
        loser = {"name": g.loser.display_name, "faction": g.factions["loser"],
                 "ultimate": g.ultimates["loser"], "elo": res["loser_elo"]}
        path = await renderer.render_result_async(
            winner, loser, res["delta"], out, winner_avatar=w_av, loser_avatar=l_av)

        if config.TEST_MODE:
            content = (f"🧪 [TEST] **{g.winner.display_name}** defeated "
                       f"**{g.loser.display_name}** — recorded immediately.")
        else:
            content = (
                f"{g.loser.mention} use {CONFIRM_EMOJI} to confirm within 5 minutes")

        channel = await _resolve_channel(config.REPORTS_CHANNEL_ID)
        if channel is None:
            await interaction.followup.send(
                "⚠️ Reports channel not found — check REPORTS_CHANNEL_ID.", ephemeral=True)
            return
        try:
            msg = await channel.send(content, file=discord.File(path))
        except discord.Forbidden:
            await interaction.followup.send(
                "⚠️ I'm missing **Send Messages** permission in the reports channel.",
                ephemeral=True)
            return
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

        self.stop()

        if config.TEST_MODE:
            players = {str(g.winner.id), str(g.loser.id)}
            if not players.isdisjoint(before | after):
                try:
                    await publish_leaderboard()
                except Exception:
                    log.exception("leaderboard refresh failed")
            return

        g.message = msg
        _prune_pending()
        PENDING[msg.id] = g
        g.timeout_task = asyncio.create_task(_expire_game(g))
        try:
            await msg.add_reaction(CONFIRM_EMOJI)
            await msg.add_reaction(DENY_EMOJI)
        except discord.Forbidden:
            await interaction.followup.send(
                f"Posted the result, but I'm missing the **Add Reactions** permission, so "
                f"I couldn't add the {CONFIRM_EMOJI}/{DENY_EMOJI}. {g.loser.display_name} can still add "
                f"it manually to confirm.", ephemeral=True)
        except discord.HTTPException:
            pass


async def _expire_game(game: PendingGame):
    """Discard a game the enemy never confirmed in time, with a red notice."""
    try:
        await asyncio.sleep(CONFIRM_TIMEOUT)
    except asyncio.CancelledError:
        return
    if game.done:
        return
    game.done = True
    PENDING.pop(game.message.id, None)
    try:
        await game.message.clear_reactions()
    except discord.HTTPException:
        pass
    try:
        await game.message.edit(
            content=f"❌ Failed to confirm in time — match not recorded.")
    except discord.HTTPException:
        pass


async def deny_game(game: PendingGame):
    if game.done:
        return
    game.done = True
    if game.timeout_task:
        game.timeout_task.cancel()
    PENDING.pop(game.message.id, None)
    try:
        await game.message.delete()
    except discord.HTTPException:
        pass


def _top16_ids() -> set:
    return {p["user_id"] for p in db.top_players(16)}


async def confirm_game(game: PendingGame):
    if game.done:
        return
    game.done = True
    if game.timeout_task:
        game.timeout_task.cancel()
    w, l = game.winner, game.loser
    before = _top16_ids()
    wf, wc = _split_faction_class(game.factions["winner"])
    lf, lc = _split_faction_class(game.factions["loser"])
    db.record_match(
        w.id, l.id,
        wf, wc, game.ultimates["winner"],
        lf, lc, game.ultimates["loser"],
    )
    after = _top16_ids()
    PENDING.pop(game.message.id, None)
    try:
        await game.message.edit(
            content=f"✅ The match has been confirmed.")
    except discord.HTTPException:
        pass
    players = {str(w.id), str(l.id)}
    if not players.isdisjoint(before | after):
        try:
            await publish_leaderboard()
        except Exception:
            log.exception("leaderboard refresh failed")


async def defeated(interaction, enemy: discord.Member):
    if enemy.id == interaction.user.id:
        await interaction.response.send_message(
            "You can't report a game against yourself.", ephemeral=True)
        return
    if enemy.bot:
        await interaction.response.send_message("Pick a human opponent.", ephemeral=True)
        return

    game = PendingGame(winner=interaction.user, loser=enemy)
    view = PickerView(game)
    await interaction.response.send_message(
        content=f"You vs **{enemy.display_name}** — pick faction & ultimate for both, "
                f"then submit. {enemy.display_name} will confirm with {CONFIRM_EMOJI}.",
        view=view, ephemeral=True)


async def on_raw_reaction_add(payload):
    if payload.user_id == client.user.id:
        return
    game = PENDING.get(payload.message_id)
    if game is None:
        return
    emoji = str(payload.emoji)
    if emoji == CONFIRM_EMOJI:
        if payload.user_id != game.loser.id:
            return
        await confirm_game(game)
    elif emoji == DENY_EMOJI:
        if payload.user_id not in (game.winner.id, game.loser.id):
            return
        await deny_game(game)


# --------------------------------------------------------------------------
# leaderboard rendering
# --------------------------------------------------------------------------
async def _prerender_header():
    global _cached_header_path
    path = os.path.join(config.PREVIEW_DIR, "lb_header_cached.webp")
    _cached_header_path = await renderer.render_header_async(path)


async def build_leaderboard_images(tag):
    """Render the ladder as an ordered list of image paths:
    [header, rows 1-4, rows 5-8, rows 9-12, rows 13-16, faction table].
    Discord caps image height, so the rows are split into chunks of 4 and each
    chunk is its own image (posted as separate stacked messages)."""
    d = config.PREVIEW_DIR
    if _cached_header_path and os.path.exists(_cached_header_path):
        header_path = _cached_header_path
    else:
        header_path = await renderer.render_header_async(os.path.join(d, f"lb_{tag}_header.jpg"))
    paths = [header_path]

    players = db.top_players(20)
    if players:
        async with aiohttp.ClientSession() as session:
            avatars = {p["user_id"]: await get_avatar(session, p["user_id"])
                       for p in players}
        names = {p["user_id"]: await get_display_name(p["user_id"]) for p in players}
        # exclude deleted accounts (name fetch returned None), cap at 16
        players = [p for p in players if names.get(p["user_id"]) is not None][:16]
        entries = model.build_entries(
            players,
            avatar_resolver=lambda uid: avatars.get(uid),
            name_resolver=lambda uid: names.get(uid))
        for i in range(0, len(entries), 4):
            chunk = players[i:i + 4]
            n = i // 4
            key = hashlib.md5(
                str([(p["user_id"], p["elo"], p["wins"], p["losses"], p.get("streak", 0))
                     for p in chunk]).encode()
            ).hexdigest()
            out = os.path.join(d, f"lb_chunk_{n}.webp")
            if _chunk_cache.get(n) == key and os.path.exists(out):
                paths.append(out)
                continue
            path = await renderer.render_rows_async(entries[i:i + 4], out)
            _chunk_cache[n] = key
            paths.append(path)
            await asyncio.sleep(0.3)
    return paths


def _cleanup(paths):
    for p in paths:
        if p == _cached_header_path or p.startswith(
                os.path.join(config.PREVIEW_DIR, "lb_chunk_")):
            continue
        try:
            os.remove(p)
        except OSError:
            pass


async def _resolve_channel(channel_id):
    """Look up a channel by id (cache first, REST fallback), or None if unset."""
    if not channel_id:
        return None
    return client.get_channel(channel_id) or await client.fetch_channel(channel_id)


async def _purge_bot_messages(channel, limit):
    """Delete the bot's own recent messages so a repost replaces the old set."""
    async for msg in channel.history(limit=limit):
        if msg.author.id == client.user.id:
            try:
                await msg.delete()
            except discord.HTTPException:
                pass


async def _post_files(channel, paths):
    """Post each image path as its own stacked message."""
    for p in paths:
        await channel.send(file=discord.File(p))


async def publish_leaderboard():
    """Repost the ladder (header + row chunks + faction table) as stacked
    messages in the leaderboard channel, replacing the bot's previous set."""
    channel = await _resolve_channel(config.LEADERBOARD_CHANNEL_ID)
    if channel is None:
        return
    async with _leaderboard_lock:
        paths = await build_leaderboard_images("auto")
        # remove the bot's previous leaderboard messages so order stays correct
        await _purge_bot_messages(channel, limit=30)
        await _post_files(channel, paths)
        _cleanup(paths)


async def _render_stats_header(title: str) -> str:
    """Return a cached path for a stats header bar, rendering it once if needed."""
    cached = _stats_header_cache.get(title)
    if cached and os.path.exists(cached):
        return cached
    safe = title.replace(" ", "_").lower()
    path = os.path.join(config.CACHE_DIR, f"stats_hdr_{safe}.webp")
    out = await asyncio.get_event_loop().run_in_executor(
        None, renderer.render_stats_header_img, title, path)
    _stats_header_cache[title] = out
    return out


async def publish_winrate_stats():
    """Post (or repost) the 6 stats card images into the winrate channel."""
    channel = await _resolve_channel(config.WINRATE_CHANNEL_ID)
    if channel is None:
        return

    async with _stats_lock:
        ult_rows  = db.ultimate_stats()
        fac_rows  = db.faction_stats()
        cls_rows  = db.class_stats()
        frax_rows = db.frax_by_faction()
        fc_rows   = db.faction_class_stats()

        d    = config.CACHE_DIR
        loop = asyncio.get_event_loop()

        h1 = await _render_stats_header("Ultimate Winrate")
        s1 = await loop.run_in_executor(None, renderer.render_ult_section_img,
                                        ult_rows, frax_rows, os.path.join(d, "stats_s1.webp"))
        await asyncio.sleep(2)
        h2 = await _render_stats_header("Faction Winrate")
        s2 = await loop.run_in_executor(None, renderer.render_faction_section_img,
                                        fac_rows, fc_rows, os.path.join(d, "stats_s2.webp"))
        await asyncio.sleep(2)
        h3 = await _render_stats_header("Class Winrate")
        s3 = await loop.run_in_executor(None, renderer.render_class_section_img,
                                        cls_rows, os.path.join(d, "stats_s3.webp"))

        # delete the bot's previous stats messages before reposting
        await _purge_bot_messages(channel, limit=20)
        await _post_files(channel, [h1, s1, h2, s2, h3, s3])


async def _winrate_daily_loop():
    """Repost stats cards once per day at UTC midnight."""
    while True:
        now = datetime.now(timezone.utc)
        next_midnight = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0)
        await asyncio.sleep((next_midnight - now).total_seconds())
        try:
            await publish_winrate_stats()
        except Exception:
            log.exception("daily stats refresh failed")


async def elo_cmd(interaction, player: discord.Member):
    p = db.get_player(player.id)
    if p is None:
        await interaction.response.send_message(
            f"🆕 **{player.display_name}** hasn't played any ranked games yet.",
            ephemeral=True)
        return
    games = p["wins"] + p["losses"]
    winrate = round(100 * p["wins"] / games) if games else 0
    embed = discord.Embed(color=discord.Color.gold())
    # paired fields share a row (3 inline fields per row in Discord)
    embed.add_field(name="🏰 Player", value=player.display_name, inline=True)
    embed.add_field(name="📊 ELO", value=f"**{p['elo']}**", inline=True)
    embed.add_field(name="🎖️ Rank", value=config.rank_title(p["elo"]), inline=True)
    embed.add_field(name="⚔️ Games", value=str(games), inline=True)
    embed.add_field(name="📈 Winrate", value=f"{winrate}%", inline=True)
    embed.add_field(name="🔥 Streak", value=model.streak_label(p.get("streak", 0)),
                    inline=True)
    embed.add_field(name="✅ Wins", value=str(p["wins"]), inline=True)
    embed.add_field(name="❌ Losses", value=str(p["losses"]), inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def on_ready():
    db.init_db()
    mode = " [TEST MODE — no confirmation, test DB]" if config.TEST_MODE else ""
    log.info("Logged in as %s (%s)%s", client.user, client.user.id, mode)

    # on_ready re-fires on every reconnect/resume. Everything below posts to
    # channels or registers commands and must run exactly once per process, or
    # reconnects would repost the boards/stats and stack duplicate daily loops.
    global _initialized
    if _initialized:
        return
    _initialized = True

    # Register commands per-guild (instant) and clear the global scope so commands
    # don't show up twice (once global + once per guild).
    for guild in client.guilds:
        tree.copy_global_to(guild=guild)
        await tree.sync(guild=guild)
    tree.clear_commands(guild=None)
    await tree.sync()
    try:
        await _prerender_header()
    except Exception:
        log.exception("header prerender failed")
    try:
        await publish_leaderboard()
    except Exception:
        log.exception("initial leaderboard failed")
    try:
        await publish_winrate_stats()
    except Exception:
        log.exception("initial stats failed")
    asyncio.create_task(_winrate_daily_loop())


if __name__ == "__main__":
    if not config.DISCORD_TOKEN:
        raise SystemExit("Set DISCORD_TOKEN in your environment first.")
    db.init_db()
    delays = [60, 120, 180, 240, 600, 1800, 10800, 86400]
    for attempt in range(1, len(delays) + 2):
        _make_client()
        try:
            # log_handler=None: route discord.py's logs through our root config
            # (basicConfig) so they land in log.txt too, instead of its own handler.
            client.run(config.DISCORD_TOKEN, log_handler=None)
            break
        except discord.errors.HTTPException as e:
            if e.status == 429 and attempt <= len(delays):
                delay = delays[attempt - 1]
                log.warning("Rate limited (attempt %s/%s), retrying in %ss...",
                            attempt, len(delays) + 1, delay)
                time.sleep(delay)
            else:
                log.exception("fatal HTTP error, giving up")
                raise
        except Exception:
            log.exception("bot crashed")
            raise
