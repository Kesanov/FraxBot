"""Configuration for the H5 Frax Discord ELO bot.

Edit the FACTIONS / ULTIMATES lists to match your mod exactly.
Secrets are read from environment variables so they never get committed.
"""

import os
import sys

# Run with `python main.py --test` for a sandbox: a SEPARATE database and no
# confirmation step (matches are recorded immediately).
TEST_MODE = "--test" in sys.argv

# Load a local .env file for debugging (optional). Real hosts should set real
# environment variables instead. Does nothing if python-dotenv isn't installed
# or there's no .env file.
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

# --- Discord ---------------------------------------------------------------
# Set these in your environment before running the bot:
#   PowerShell:  $env:DISCORD_TOKEN = "..."
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")

# Channel where the leaderboard message lives / gets refreshed (nothing else).
LEADERBOARD_CHANNEL_ID = int(os.environ.get("LEADERBOARD_CHANNEL_ID", "0"))

# Channel where rendered result cards are posted. Required.
REPORTS_CHANNEL_ID = int(os.environ.get("REPORTS_CHANNEL_ID", "0"))

# Channel where the daily winrate stats cards are posted.
WINRATE_CHANNEL_ID = int(os.environ.get("WINRATE_CHANNEL_ID", "0"))

# --- Game version ----------------------------------------------------------
# Patch the games are currently played on. Stamped onto every recorded match.
# Bump this when a new balance patch ships. Stats fold older patches into the
# current one via a fixed-size prior (see STAT_PRIOR): each patch's effective
# winrate becomes a STAT_PRIOR-game prior for the next patch.
VERSION = (4, 5, 0)
STAT_PRIOR = 10  # virtual games the previous patch contributes to the next one

# --- ELO -------------------------------------------------------------------
ELO_START = 1000
ELO_K = 60  # even match = ±30 pts
ELO_D = 684  # slope divisor; higher = flatter curve (standard chess uses 400)

# --- Paths -----------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")    # fonts, static assets (committed)
CACHE_DIR = os.path.join(BASE_DIR, "cache")  # DB, rendered images (gitignored)
DB_PATH = os.path.join(CACHE_DIR, "elo_test.sqlite3" if TEST_MODE else "elo.sqlite3")
PREVIEW_DIR = CACHE_DIR

os.makedirs(CACHE_DIR, exist_ok=True)

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

CLASSES = ["Warrior", "Warmage", "Warlock"]

CLASS_EMOJI = {
    "Warrior": "🛡️",
    "Warmage": "🔱",
    "Warlock": "🔮",
}

FACTION_EMOJI = {
    "Haven":       "⛪",
    "Sylvan":      "🌿",
    "Academy":     "🌩️",
    "Dungeon":     "🦇",
    "Necropolis":  "💀",
    "Inferno":     "🔥",
    "Fortress":    "🏔️",
    "Stronghold":  "🪃",
}


def faction_base(faction_class: str) -> str:
    """Extract 'Haven' from 'Haven: Might'."""
    return faction_class.split(": ")[0]



def faction_emoji(faction_class: str) -> str:
    """Return just the class emoji for 'Haven: Warrior' → '⚔️'."""
    if ": " not in faction_class:
        return ""
    cls = faction_class.split(": ", 1)[1]
    return CLASS_EMOJI.get(cls, "")


# Ultimate options — same for all factions.
# "None" is first so players can report a game where no ultimate was reached.
ULTIMATES = [
    "Master of Creation",
    "Master of Death",
    "Master of Destruction",
    "Master of Life",
    "Angelic Alliance",
    "Blood Thirst",
    "Forest Rage",
    "Forgotten Witchcraft",
    "Frax Essence",
    "Mithral Plating",
    "Undying Thirst",
    "Runic Excelence",
    "Runic Protection",
    "Nature's Luck",
    "Absolute Empathy",
    "Might over Magic",
    "Arcane Omniscience",
    "Howl of Terror",
    "Blood Frenzy",
]

def ultimate_emoji_name(ultimate: str) -> str:
    """Custom-emoji name for an ultimate: the name with spaces/punctuation stripped.

    e.g. "Frax Essence" -> "FraxEssence", "Nature's Luck" -> "NaturesLuck".
    Used to look the emoji up by name in the guild at render time.
    """
    return "".join(c for c in ultimate if c.isalnum())


# Theme colors keyed by faction (used by both renderers).
FACTION_COLORS = {
    "Haven":      "#edc452",
    "Sylvan":     "#4caf50",
    "Academy":    "#2196f3",
    "Dungeon":    "#ac3bdd",
    "Necropolis": "#607d8b",
    "Inferno":    "#e53935",
    "Fortress":   "#94FFFA",
    "Stronghold": "#af5104",
}



def rank_title(peak_elo: int | None) -> str:
    """Map a player's peak ELO (None = fewer than 10 games) to a display rank title."""
    if peak_elo is None:
        return "LandLord"
    if peak_elo >= 2000:
        return "Seraph"
    if peak_elo >= 1800:
        return "Champion"
    if peak_elo >= 1600:
        return "Renegade"
    if peak_elo >= 1400:
        return "Inquisitor"
    if peak_elo >= 1200:
        return "Paladin"
    if peak_elo >= 1000:
        return "Knight"
    if peak_elo >= 900:
        return "Squire"
    if peak_elo >= 800:
        return "Footman"
    return "LandLord"
