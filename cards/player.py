"""Builds the `/player` stats card embed.

Split out of main.py: this module owns only the presentation of a player's
breakdown (Elo, winrate, nemesis/scapegoat, and the faction/ultimate/class
grids). It depends on db/config for data and is handed the async name resolver
so it needn't reach back into the Discord client.
"""

import discord

import config
import db

# Classes are shown with a representative ultimate's emoji (no custom class emojis).
CLASS_ULTIMATE = {
    "Warrior": "Might over Magic",
    "Warmage": "Arcane Omniscience",
    "Warlock": "Master of Death",
}


def _wl(r):
    """Bold 'W:L', or blank when the player has no games with this pick."""
    return f"**{r['wins']}:{r['losses']}**" if r["games"] else ""


def _grid_section(embed, label, cells):
    """Render preformatted `cells` as a 3-column table under a banner header.

    Each column is its own inline field (a vertical list), so Discord aligns the
    three columns side by side; cells fill left-to-right, top-to-bottom.
    """
    if not cells:
        cells = ["—"]
    rows = [cells[i:i + 3] for i in range(0, len(cells), 3)]
    # Spread an incomplete final row symmetrically: one cell centered, two on the
    # outer edges, so the table never looks left-heavy.
    last = rows[-1]
    if len(last) == 1:
        rows[-1] = ["​", last[0], "​"]
    elif len(last) == 2:
        rows[-1] = [last[0], "​", last[1]]
    # Full-width banner header (blank field name + the title in the value). It spans
    # the whole card rather than sitting in a column, so all three columns stay equal
    # width, and being inline=False it forces the columns onto a fresh row.
    embed.add_field(name="​", value=f"**<<═ {label} ═════>>**", inline=False)
    for c in range(3):
        # Pad missing cells with a zero-width space so columns stay aligned.
        col = [row[c] if c < len(row) else "​" for row in rows]
        # First cell goes on the field-name line (otherwise wasted as blank). Markdown
        # doesn't render in field names, so strip the bold markers; the remaining rows
        # stay in the value as normal bold white text.
        head = col[0].replace("**", "")
        embed.add_field(name=head, value="\n".join(col[1:]) or "​", inline=True)


async def build_player_embed(interaction, player, resolve_name):
    """Build the `/player` card, or return None if the player has no games.

    `resolve_name` is an async `id -> display name` resolver (REST-backed, so it
    finds opponents that aren't in the member cache).
    """
    p = db.get_player(player.id)
    if p is None:
        return None

    games = p["wins"] + p["losses"]
    winrate = round(100 * p["wins"] / games) if games else 0
    bd = db.player_breakdown(player.id)
    lb_rank = db.leaderboard_rank(player.id)[0]

    # All factions, most-played first (unplayed ones fall to the end with '-').
    factions = sorted(bd["factions"], key=lambda r: r["games"], reverse=True)

    # Color the card by the player's most-played faction (fallback gold).
    top = factions[0] if factions and factions[0]["games"] else None
    color = (discord.Color.from_str(config.FACTION_COLORS[top["faction"]])
             if top else discord.Color.gold())

    embed = discord.Embed(color=color)
    embed.set_author(name=f"{player.display_name}  (Rank #{lb_rank} 🏆)",
                     icon_url=player.display_avatar.url)
    embed.set_thumbnail(url=player.display_avatar.url)
    # paired fields share a row (3 inline fields per row in Discord)
    peak = p["peak_elo"]
    elo_display = f"{p['elo']} ({peak})" if peak is not None else str(p["elo"])
    embed.add_field(name="📊 Elo (Max)", value=f"**{elo_display}**")
    embed.add_field(name="⚔️ Winrate", value=f"**{winrate}% ({games} Total)**")
    # Blank third column completes this row so Nemesis/Scapegoat wrap to the next row
    # with a single row-gap (a full-width spacer field would show two blank lines).
    embed.add_field(name="​", value="​")

    # Nemesis (most-played opponent you trail) and Scapegoat (most-played you lead).
    # Ranked by total games together, not winrate, so a single fluke game can't win.
    # A player in the table has played at least one game, so h2h is never empty.
    # Full-width (own line) so the variable-length opponent names stay out of the
    # 3-column grid and can't affect the faction/ultimate/class column widths.
    h2h = db.head_to_head(player.id)
    for emoji_label, score in (("😈 Nemesis",  lambda r: -(r["wins"] + 1) / (r["games"] + 1)),
                               ("🐑 Scapegoat", lambda r:   r["wins"]      / (r["games"] + 1))):
        r = max(h2h, key=score)
        name = await resolve_name(str(r["opponent_id"])) or f"<@{r['opponent_id']}>"
        embed.add_field(name=emoji_label,
                        value=f"**({r['wins']}:{r['losses']})  **{name} ",
                        inline=False)

    # Guild custom emojis by name, used for ultimate (and class) icons.
    emoji_by_name = {e.name: str(e)
                     for e in (interaction.guild.emojis if interaction.guild else [])}

    def _emoji(ultimate, fallback):
        """Custom emoji for an ultimate's name, falling back when absent."""
        return emoji_by_name.get(config.ultimate_emoji_name(ultimate)) or fallback

    # Factions: emoji + W:L, most-played first.
    _grid_section(embed, "Factions",
                  [f"{emoji_by_name.get(r['faction'], config.FACTION_EMOJI.get(r['faction'], ''))} {_wl(r)}"
                   for r in factions])
    # Classes: shown with their representative ultimate's emoji.
    _grid_section(embed, "Classes",
                  [f"{_emoji(CLASS_ULTIMATE[r['class']], config.CLASS_EMOJI.get(r['class'], r['class']))} {_wl(r)}"
                   for r in bd["classes"]])
    # Ultimates: every one played, sorted by pickrate; emoji only, name as fallback.
    _grid_section(embed, "Ultimates",
                  [f"{_emoji(r['ultimate'], r['ultimate'])} {_wl(r)}"
                   for r in bd["ultimates"]])

    return embed
