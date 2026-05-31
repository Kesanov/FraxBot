"""Shared constants, font setup, and the _save rasterizer."""

import os
import sys
import html as _html

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import FACTION_COLORS, faction_base, faction_emoji  # noqa: E402
from cards.model import _latinize

W = 1040

_FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
_FONT_FILES = [
    ("Crimson Pro",      "400", "normal", "CrimsonPro-Regular.ttf"),
    ("Crimson Pro",      "700", "normal", "CrimsonPro-Bold.ttf"),
    ("Crimson Pro",      "400", "italic", "CrimsonPro-Italic.ttf"),
    ("Noto Color Emoji", "400", "normal", "NotoColorEmoji.ttf"),
]
_FONT_FAMILY = "Crimson Pro"
# IMPORTANT: emoji and text must NEVER share a <text> element (not even via <tspan>).
# resvg resolves font-family once per <text> element; if any glyph in the element
# triggers a fallback to _EMOJI_FAMILY, the whole element switches font and regular
# Latin text ends up rendered in Twemoji Mozilla instead of Crimson Pro.
# Fix: put emoji in their own <text font-family="_EMOJI_FAMILY"> elements, text in theirs.
# fonts are loaded via font_files= in svg_to_bytes (resvg ignores @font-face data URIs).
_EMOJI_FAMILY = "Noto Color Emoji"

_FONT_PATHS = [
    os.path.join(_FONT_DIR, fname)
    for _, _, _, fname in _FONT_FILES
    if os.path.exists(os.path.join(_FONT_DIR, fname))
]

_CELL_FILL = 'fill="#1c1410" fill-opacity="0.3"'
_GOLD_EDGE = '#a9743f'
_CELL_STROKE_W = 4
_CELL_STROKE_OPACITY = 0.8

RANK_COLORS = {
    "Champion": "#9c1d1d",
    "Renegade": "#c56d42",
    "Inquisitor": "#8133a0",
    "Paladin": "#44a0ac",
    "Knight": "#5b8ebd",
    "Squire": "#68c7a7",
    "LandLord": "#629c62",
}

_ULTIMATES_DIR = os.path.join(_FONT_DIR, "Ultimates")
_TOWNS_DIR = os.path.join(_FONT_DIR, "Towns")


def _esc(s):
    return _html.escape(str(s))


def _lux_bg():
    return ""


def _save(svg: str, out_path: str, scale: float = 2):
    try:
        import io
        import resvg_py
        from PIL import Image

        png = bytes(resvg_py.svg_to_bytes(
            svg_string=svg, zoom=scale,
            font_files=_FONT_PATHS,
            font_family=_FONT_FAMILY,
        ))
        img = Image.open(io.BytesIO(png)).convert("RGBA")
        webp_path = os.path.splitext(out_path)[0] + ".webp"
        img.save(webp_path, "WEBP", quality=78, method=6)
        return webp_path
    except Exception:
        pass
    svg_path = os.path.splitext(out_path)[0] + ".svg"
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)
    return svg_path


def _local_data_uri(directory: str, filename: str | None) -> str | None:
    import base64
    if not filename:
        return None
    path = os.path.join(directory, filename)
    if not os.path.exists(path):
        return None
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    mime = {"png": "image/png", "gif": "image/gif"}.get(ext, "image/png")
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    return f"data:{mime};base64,{data}"
