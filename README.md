# H55 Discord ELO bot (FraxBot)

An ELO ladder bot for the Heroes V 5.5 community. Players report 1v1 results
(picking faction + ultimate for both sides), and the bot keeps an ELO table with
auto-refreshing top-10 leaderboard cards rendered as JPG from SVG.

## Layout

```
discord/
  main.py           Discord bot entry point: /report + /ladder + auto leaderboard
  config.py         Tokens, factions, ULTIMATES list, ELO params  <- edit me
  elo.py            ELO math
  db.py             SQLite storage (players, matches)
  preview.py        Render sample cards locally, no Discord needed
  cards/
    model.py        Player rows -> display entries (rank, winrate, avatars)
    svg_renderer.py SVG card builder + resvg/Pillow -> JPG rasterizer
  preview_output/   Generated images land here
  data/             SQLite db (created at runtime)
```

## Rendering

Cards are built as SVG and rasterized to **JPG** with **resvg** (`resvg-py`, a
self-contained cross-platform wheel — no system libraries) plus Pillow. The same
`pip install` works on Windows and on any Linux host, which makes it free-host
friendly: no Chromium, no `apt-get`.

## 1. Preview the visuals locally (no Discord)

```powershell
pip install -r requirements.txt
python preview.py
```

Open `preview_output/leaderboard.jpg` and `preview_output/result.jpg`.

## 2. Configure

Edit [config.py](config.py):
- **`ULTIMATES`** — replace the placeholder names with the real H55 ultimates per faction.
- `ELO_START` (1000) and `ELO_K` (32) for tuning.
- `rank_title()` thresholds for the rank labels.

## 3. Invite the bot (Discord Developer Portal)

1. https://discord.com/developers/applications → **New Application**.
2. **Bot** tab → **Reset Token** → copy it into `DISCORD_TOKEN`.
3. **Privileged Gateway Intents**: leave all **OFF** — the bot only uses default
   intents (`guilds`, `guild messages`, `guild reactions`).
4. **OAuth2 → URL Generator**:
   - Scopes: **`bot`**, **`applications.commands`**
   - Bot permissions:
     - **Send Messages** — post confirmation/result messages
     - **Embed Links** / **Attach Files** — upload the card JPGs
     - **Add Reactions** — add the 👍 the enemy confirms with
     - **Read Message History** — find & edit the existing leaderboard message
   - Open the generated URL, pick your server, **Authorize**.
5. Make sure the bot's role can see and post in **both** the report and
   leaderboard channels.

## 4. Run the bot

```powershell
$env:DISCORD_TOKEN = "your-bot-token"
$env:REPORT_CHANNEL_ID = "123456789012345678"        # where players run /game
$env:LEADERBOARD_CHANNEL_ID = "987654321098765432"   # where the ladder is auto-posted
python main.py
```

Two channels:
- **Report channel** (`REPORT_CHANNEL_ID`) — where players run `/game`. If unset,
  `/game` works in any channel.
- **Leaderboard channel** (`LEADERBOARD_CHANNEL_ID`) — only the auto-updating
  ladder card lives here.

Commands (slash):
- `/defeated @enemy` — the caller claims a win. Both players pick faction +
  ultimate, then the **enemy confirms by reacting 👍**. On confirmation the match
  is recorded, a result card is posted, and the leaderboard refreshes.
- `/ladder` — render the current top-10 on demand.

The leaderboard is drawn once on startup and refreshed after every confirmed
game, editing its last message in the leaderboard channel.

## 5. Deploying on free hosting

```
pip install -r requirements.txt
python main.py
```

No system packages needed. The SQLite db lives in `data/elo.sqlite3` — mount it
on a persistent volume so ratings survive restarts.
