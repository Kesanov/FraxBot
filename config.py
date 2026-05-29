"""Configuration for the H5 Frax Discord ELO bot.

Edit the FACTIONS / ULTIMATES lists to match your mod exactly.
Secrets are read from environment variables so they never get committed.
"""

import os

# --- Discord ---------------------------------------------------------------
# Set these in your environment before running the bot:
#   PowerShell:  $env:DISCORD_TOKEN = "..."
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")

# Channel where the leaderboard message lives / gets refreshed (nothing else).
LEADERBOARD_CHANNEL_ID = int(os.environ.get("LEADERBOARD_CHANNEL_ID", "0"))

# Channel where players run /defeated to report results. If 0, works anywhere.
REPORT_CHANNEL_ID = int(os.environ.get("REPORT_CHANNEL_ID", "0"))

# --- ELO -------------------------------------------------------------------
ELO_START = 1000
ELO_K = 32

# --- Game data -------------------------------------------------------------
# The 8 standard factions. Order here = order shown in the dropdown.
FACTIONS = [
    "Haven",
    "Sylvan",
    "Academy",
    "Dungeon",
    "Necropolis",
    "Inferno",
    "Fortress",
    "Stronghold",
]

# Per-faction ultimate options shown in the second dropdown.
# >>> EDIT THESE to the real Frax ultimate ability names. <<<
# Keep "None" first so a player can report that no ultimate was reached.
ULTIMATES = {
    "Haven":      ["None", "Last Stand", "Holy Word", "Retribution"],
    "Sylvan":     ["None", "Rain of Arrows", "Imbue Arrow", "Nature's Wrath"],
    "Academy":    ["None", "Wall of Fog", "Mark of the Wizard", "Arcane Omniscience"],
    "Dungeon":    ["None", "Empowered Spells", "Twilight", "Elemental Vision"],
    "Necropolis": ["None", "Eternal Servitude", "Howl of Terror", "Dead Man's Curse"],
    "Inferno":    ["None", "Urgash's Call", "Fire of Hell", "Lord of the Pit"],
    "Fortress":   ["None", "Wary Stance", "Runelore", "Father Sky's Wrath"],
    "Stronghold": ["None", "Powerful Blow", "Father of Thunder", "Rage of the Elements"],
}

# Theme colors keyed by faction (used by both renderers).
FACTION_COLORS = {
    "Haven":      "#d9b44a",
    "Sylvan":     "#4caf50",
    "Academy":    "#2196f3",
    "Dungeon":    "#7b1fa2",
    "Necropolis": "#607d8b",
    "Inferno":    "#e53935",
    "Fortress":   "#795548",
    "Stronghold": "#ef6c00",
}

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "elo.sqlite3")
PREVIEW_DIR = os.path.join(BASE_DIR, "preview_output")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PREVIEW_DIR, exist_ok=True)


def rank_title(elo: int) -> str:
    """Map an ELO value to a display rank title."""
    if elo >= 1600:
        return "Grandmaster"
    if elo >= 1400:
        return "Master"
    if elo >= 1250:
        return "Veteran"
    if elo >= 1100:
        return "Knight"
    if elo >= 950:
        return "Squire"
    return "Recruit"
