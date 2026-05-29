"""H5 Frax Discord ELO bot (FraxBot).

Run:
    $env:DISCORD_TOKEN = "..."
    $env:REPORT_CHANNEL_ID = "..."        # where players run /defeated
    $env:LEADERBOARD_CHANNEL_ID = "..."   # where the ladder is auto-posted
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
import os
import time
import traceback
from dataclasses import dataclass, field

import aiohttp
import discord
from discord import app_commands

import config
import db
from cards import model
from cards import svg_renderer as renderer

CONFIRM_EMOJI = "👍"

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

# Drop pending games the enemy never confirmed after this many seconds.
PENDING_TTL = 24 * 3600

# How long the enemy has to confirm with 👍 before the game is discarded.
CONFIRM_TIMEOUT = 300  # 5 minutes

# Cache of rendered avatar data URIs: user_id -> (data_uri | None, fetched_at).
# Refreshed once a day since users can change their avatar.
AVATAR_TTL = 24 * 3600
_avatar_cache: dict[str, tuple[str | None, float]] = {}


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


# --------------------------------------------------------------------------
# Ephemeral picker — the reporter sets faction + ultimate for both players
# --------------------------------------------------------------------------
class FactionSelect(discord.ui.Select):
    def __init__(self, view, side, row):
        self._pview = view
        self.side = side  # "winner" or "loser"
        player = view.game.winner if side == "winner" else view.game.loser
        options = [discord.SelectOption(label=f, value=f) for f in config.FACTIONS]
        super().__init__(placeholder=f"{player.display_name} — faction",
                         options=options, row=row)

    async def callback(self, interaction):
        self._pview.game.factions[self.side] = self.values[0]
        self._pview.game.ultimates[self.side] = None
        self._pview.rebuild()
        await interaction.response.edit_message(view=self._pview)


class UltimateSelect(discord.ui.Select):
    def __init__(self, view, side, faction, row):
        self._pview = view
        self.side = side
        player = view.game.winner if side == "winner" else view.game.loser
        opts = config.ULTIMATES.get(faction, ["None"])
        options = [discord.SelectOption(label=u, value=u) for u in opts]
        super().__init__(placeholder=f"{player.display_name} — ultimate ({faction})",
                         options=options, row=row)

    async def callback(self, interaction):
        self._pview.game.ultimates[self.side] = self.values[0]
        self._pview.rebuild()
        await interaction.response.edit_message(view=self._pview)


class SubmitButton(discord.ui.Button):
    def __init__(self, view):
        self._pview = view
        super().__init__(label="Submit for confirmation", style=discord.ButtonStyle.success,
                         disabled=not view.is_ready(), row=4)

    async def callback(self, interaction):
        await self._pview.submit(interaction)


class PickerView(discord.ui.View):
    """Shown only to the reporter (ephemeral)."""

    def __init__(self, game: PendingGame):
        super().__init__(timeout=300)
        self.game = game
        self.rebuild()

    def is_ready(self):
        g = self.game
        return all(g.factions.values()) and all(g.ultimates.values())

    def rebuild(self):
        self.clear_items()
        g = self.game
        self.add_item(FactionSelect(self, "winner", row=0))
        if g.factions["winner"]:
            self.add_item(UltimateSelect(self, "winner", g.factions["winner"], row=1))
        self.add_item(FactionSelect(self, "loser", row=2))
        if g.factions["loser"]:
            self.add_item(UltimateSelect(self, "loser", g.factions["loser"], row=3))
        self.add_item(SubmitButton(self))

    async def submit(self, interaction):
        g = self.game
        # close the ephemeral picker
        await interaction.response.edit_message(content="Submitted.", view=None)

        # In test mode the match is recorded immediately (no confirmation).
        if config.TEST_MODE:
            res = db.record_match(
                (g.winner.id, g.winner.display_name),
                (g.loser.id, g.loser.display_name),
                g.factions["winner"], g.ultimates["winner"],
                g.factions["loser"], g.ultimates["loser"])
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
                f"🎮 **{g.winner.display_name}** reports defeating **{g.loser.display_name}**.\n"
                f"{g.loser.mention}, react with {CONFIRM_EMOJI} within 5 minutes to confirm — "
                f"otherwise the match will not be recorded.")

        channel = interaction.channel or client.get_channel(interaction.channel_id)
        try:
            msg = await channel.send(content, file=discord.File(path))
        except discord.Forbidden:
            await interaction.followup.send(
                "⚠️ I couldn't post the public message — I'm missing the **Send Messages** "
                "permission in this channel. Ask an admin to grant it, then report again.",
                ephemeral=True)
            return
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

        self.stop()

        if config.TEST_MODE:
            try:
                await publish_leaderboard()
            except Exception:
                traceback.print_exc()
            return

        g.message = msg
        _prune_pending()
        PENDING[msg.id] = g
        g.timeout_task = asyncio.create_task(_expire_game(g))
        try:
            await msg.add_reaction(CONFIRM_EMOJI)
        except discord.Forbidden:
            await interaction.followup.send(
                f"Posted the result, but I'm missing the **Add Reactions** permission, so "
                f"I couldn't add the {CONFIRM_EMOJI}. {g.loser.display_name} can still add "
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
    embed = discord.Embed(
        description=(f"❌ **{game.loser.display_name}** did not confirm within 5 minutes — "
                     f"this match was **not** recorded."),
        color=discord.Color.red())
    try:
        await game.message.edit(content=None, embed=embed, attachments=[])
    except discord.HTTPException:
        pass


async def confirm_game(game: PendingGame):
    if game.done:
        return
    game.done = True
    if game.timeout_task:
        game.timeout_task.cancel()
    w, l = game.winner, game.loser
    res = db.record_match(
        (w.id, w.display_name), (l.id, l.display_name),
        game.factions["winner"], game.ultimates["winner"],
        game.factions["loser"], game.ultimates["loser"],
    )
    PENDING.pop(game.message.id, None)
    try:
        await game.message.edit(
            content=f"✅ Confirmed — **{w.display_name}** defeated **{l.display_name}** "
                    f"({'+' if res['delta'] >= 0 else ''}{res['delta']} ELO).")
    except discord.HTTPException:
        pass
    # Refresh the leaderboard; don't let a failure here undo the recorded result.
    try:
        await publish_leaderboard()
    except Exception:
        traceback.print_exc()


async def defeated(interaction, enemy: discord.Member):
    if config.REPORT_CHANNEL_ID and interaction.channel_id != config.REPORT_CHANNEL_ID:
        await interaction.response.send_message(
            f"Please report games in <#{config.REPORT_CHANNEL_ID}>.", ephemeral=True)
        return
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
    if str(payload.emoji) != CONFIRM_EMOJI:
        return
    game = PENDING.get(payload.message_id)
    if game is None:
        return
    if payload.user_id != game.loser.id:
        return
    await confirm_game(game)


# --------------------------------------------------------------------------
# leaderboard rendering
# --------------------------------------------------------------------------
async def build_leaderboard_images(tag):
    """Render the ladder as an ordered list of image paths:
    [header, rows 1-4, rows 5-8, rows 9-12, faction table].
    Discord caps image height, so the rows are split into chunks of 4 and each
    chunk is its own image (posted as separate stacked messages)."""
    d = config.PREVIEW_DIR
    paths = [await renderer.render_header_async(os.path.join(d, f"lb_{tag}_header.jpg"))]

    players = db.top_players(12)
    if players:
        async with aiohttp.ClientSession() as session:
            avatars = {p["user_id"]: await get_avatar(session, p["user_id"])
                       for p in players}
        entries = model.build_entries(
            players, avatar_resolver=lambda uid: avatars.get(uid))
        for i in range(0, len(entries), 4):
            n = i // 4 + 1
            out = os.path.join(d, f"lb_{tag}_chunk{n}.jpg")
            paths.append(await renderer.render_rows_async(entries[i:i + 4], out))
    return paths


def _cleanup(paths):
    for p in paths:
        try:
            os.remove(p)
        except OSError:
            pass


async def publish_leaderboard():
    """Repost the ladder (header + row chunks + faction table) as stacked
    messages in the leaderboard channel, replacing the bot's previous set."""
    if not config.LEADERBOARD_CHANNEL_ID:
        return
    channel = client.get_channel(config.LEADERBOARD_CHANNEL_ID)
    if channel is None:
        return
    async with _leaderboard_lock:
        paths = await build_leaderboard_images("auto")
        # remove the bot's previous leaderboard messages so order stays correct
        async for msg in channel.history(limit=30):
            if msg.author.id == client.user.id:
                try:
                    await msg.delete()
                except discord.HTTPException:
                    pass
        for p in paths:
            await channel.send(file=discord.File(p))
        _cleanup(paths)


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
    embed.add_field(name="🏰 Player", value=p["name"], inline=True)
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
    # Register commands per-guild (instant) and clear the global scope so commands
    # don't show up twice (once global + once per guild).
    for guild in client.guilds:
        tree.copy_global_to(guild=guild)
        await tree.sync(guild=guild)
    tree.clear_commands(guild=None)
    await tree.sync()
    try:
        await publish_leaderboard()
    except Exception:
        traceback.print_exc()
    mode = " [TEST MODE — no confirmation, test DB]" if config.TEST_MODE else ""
    print(f"Logged in as {client.user} ({client.user.id}){mode}")


if __name__ == "__main__":
    if not config.DISCORD_TOKEN:
        raise SystemExit("Set DISCORD_TOKEN in your environment first.")
    db.init_db()
    delays = [60, 120, 180, 240, 600, 1800, 10800, 86400]
    for attempt in range(1, len(delays) + 2):
        _make_client()
        try:
            client.run(config.DISCORD_TOKEN)
            break
        except discord.errors.HTTPException as e:
            if e.status == 429 and attempt <= len(delays):
                delay = delays[attempt - 1]
                print(f"Rate limited (attempt {attempt}/{len(delays) + 1}), retrying in {delay}s...")
                time.sleep(delay)
            else:
                raise
