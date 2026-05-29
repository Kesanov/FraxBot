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
    /ladder          -> render the leaderboard on demand.
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
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


@dataclass
class PendingGame:
    winner: discord.Member          # the reporter
    loser: discord.Member           # the enemy who must confirm
    factions: dict = field(default_factory=lambda: {"winner": None, "loser": None})
    ultimates: dict = field(default_factory=lambda: {"winner": None, "loser": None})
    message: discord.Message = None  # the public confirmation message
    done: bool = False
    created: float = field(default_factory=time.monotonic)


# Games awaiting the enemy's 👍, keyed by the public confirmation message id.
PENDING: dict[int, PendingGame] = {}

# Serializes leaderboard updates so the timer and post-game refresh can't race.
_leaderboard_lock = asyncio.Lock()

# Drop pending games the enemy never confirmed after this many seconds.
PENDING_TTL = 24 * 3600

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
        await interaction.response.edit_message(
            content=f"Submitted. Waiting for **{g.loser.display_name}** to confirm with {CONFIRM_EMOJI}.",
            view=None)
        # post the public confirmation message the enemy reacts to
        summary = (
            f"{g.loser.mention}, **{g.winner.display_name}** reports defeating you:\n"
            f"• **{g.winner.display_name}** — {g.factions['winner']} / {g.ultimates['winner']}\n"
            f"• **{g.loser.display_name}** — {g.factions['loser']} / {g.ultimates['loser']}\n"
            f"React {CONFIRM_EMOJI} to confirm the result."
        )
        msg = await interaction.channel.send(summary)
        g.message = msg
        _prune_pending()
        PENDING[msg.id] = g
        try:
            await msg.add_reaction(CONFIRM_EMOJI)
        except discord.HTTPException:
            pass
        self.stop()


async def confirm_game(game: PendingGame):
    if game.done:
        return
    game.done = True
    w, l = game.winner, game.loser
    res = db.record_match(
        (w.id, w.display_name), (l.id, l.display_name),
        game.factions["winner"], game.ultimates["winner"],
        game.factions["loser"], game.ultimates["loser"],
    )
    out = os.path.join(config.PREVIEW_DIR, f"result_{game.message.id}.jpg")
    winner = {"name": w.display_name, "faction": game.factions["winner"],
              "ultimate": game.ultimates["winner"], "elo": res["winner_elo"]}
    loser = {"name": l.display_name, "faction": game.factions["loser"],
             "ultimate": game.ultimates["loser"], "elo": res["loser_elo"]}
    path = await renderer.render_result_async(winner, loser, res["delta"], out)
    await game.message.edit(content="Result confirmed.", attachments=[discord.File(path)])
    try:
        os.remove(path)
    except OSError:
        pass
    PENDING.pop(game.message.id, None)
    # Refresh the leaderboard; don't let a failure here undo the recorded result.
    try:
        await publish_leaderboard()
    except Exception:
        traceback.print_exc()


@tree.command(name="defeated", description="Report that you defeated another player.")
@app_commands.describe(enemy="The player you defeated")
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


@client.event
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
async def build_leaderboard_jpg(out_path):
    players = db.top_players(10)
    if not players:
        return None
    async with aiohttp.ClientSession() as session:
        avatars = {p["user_id"]: await get_avatar(session, p["user_id"]) for p in players}
    entries = model.build_entries(players, avatar_resolver=lambda uid: avatars.get(uid))
    return await renderer.render_leaderboard_async(
        entries, out_path, subheading="Top 10 players")


async def publish_leaderboard():
    """Render and post/edit the leaderboard in the leaderboard channel."""
    if not config.LEADERBOARD_CHANNEL_ID:
        return
    channel = client.get_channel(config.LEADERBOARD_CHANNEL_ID)
    if channel is None:
        return
    async with _leaderboard_lock:
        out = os.path.join(config.PREVIEW_DIR, "ladder_auto.jpg")
        path = await build_leaderboard_jpg(out)
        if not path:
            return
        target = None
        async for msg in channel.history(limit=20):
            if msg.author.id == client.user.id and msg.attachments:
                target = msg
                break
        if target:
            await target.edit(attachments=[discord.File(path)])
        else:
            await channel.send(file=discord.File(path))


@tree.command(name="ladder", description="Show the current ELO ladder.")
async def ladder(interaction):
    await interaction.response.defer()
    out = os.path.join(config.PREVIEW_DIR, f"ladder_{interaction.id}.jpg")
    path = await build_leaderboard_jpg(out)
    if not path:
        await interaction.followup.send("No games recorded yet.")
        return
    await interaction.followup.send(file=discord.File(path))
    try:
        os.remove(path)
    except OSError:
        pass


@client.event
async def on_ready():
    db.init_db()
    await tree.sync()
    try:
        await publish_leaderboard()
    except Exception:
        traceback.print_exc()
    print(f"Logged in as {client.user} ({client.user.id})")


if __name__ == "__main__":
    if not config.DISCORD_TOKEN:
        raise SystemExit("Set DISCORD_TOKEN in your environment first.")
    db.init_db()
    client.run(config.DISCORD_TOKEN)
