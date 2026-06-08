"""Shared constants, font setup, and the _save rasterizer."""

import os
import re
import sys
import html as _html
from functools import lru_cache
import io
import resvg_py
from PIL import Image

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

_CELL_FILL = 'fill="#1c1410" fill-opacity="0.8"'
_GOLD_EDGE = '#a9743f'
_CELL_STROKE_W = 4
_CELL_STROKE_OPACITY = 0.8


def _cell_border(color=_GOLD_EDGE, width=_CELL_STROKE_W):
    """Shared fill + stroke chrome for every rendered cell (headers, leaderboard
    rows, stat cells, result rows). `color` and `width` may be overridden for
    semantic cells (factions, winner/loser), but the stroke opacity is always
    shared so all cards match. Returns the SVG attribute string for a <rect>."""
    return (f'{_CELL_FILL} stroke="{color}" '
            f'stroke-opacity="{_CELL_STROKE_OPACITY}" stroke-width="{width}"')

_OUTER_PAD      = 20   # horizontal inset for header bars and chunk vertical pad
_HDR_VPAD       = 16   # vertical inset for header bars
_CELL_OUTER_PAD = 30   # horizontal inset for stat/player cells (+10 vs headers)

RANK_COLORS = {
    "Seraph": "#d42c2c",
    "Champion": "#cf4412",
    "Renegade": "#b9621f",
    "Inquisitor": "#ab7827",
    "Paladin": "#40cadd",
    "Knight": "#378fe1",
    "Squire": "#4eab8c",
    "LandLord": "#45a545",
}

_ULTIMATES_DIR = os.path.join(_FONT_DIR, "Ultimates")
_TOWNS_DIR = os.path.join(_FONT_DIR, "Towns")


def _esc(s):
    return _html.escape(str(s))


# --- Mixed text/emoji rendering -------------------------------------------
# resvg resolves font-family once per <text> element, so a single element can
# never hold both Crimson text and emoji (see the warning at the top of this
# module). render_text() splits a string into emoji and non-emoji runs and
# emits each as its own <text> in the right font, positioning them by measuring
# run widths. Pure-text (no emoji) keeps native SVG text-anchor so existing
# layouts are unchanged.

# Pictographic emoji, regional indicators, dingbats, plus ZWJ (200D) and
# variation selectors (FE00-FE0F) so ZWJ/keycap sequences stay in one run.
_EMOJI_RE = re.compile(
    "([\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
    "\U00002B00-\U00002BFF\U00002190-\U000021FF™ℹ〰〽"
    "︀-️‍⃣]+)"
)

# Crimson face per (weight, italic), and the emoji face path, from _FONT_FILES.
_TEXT_FONT_PATHS = {
    ("700", False): "CrimsonPro-Bold.ttf",
    ("400", False): "CrimsonPro-Regular.ttf",
    ("400", True):  "CrimsonPro-Italic.ttf",
}
_EMOJI_FONT_FILE = "NotoColorEmoji.ttf"


def _text_font_path(weight, italic):
    key = ("700", False) if str(weight) == "700" and not italic else \
          ("400", True) if italic else ("400", False)
    return os.path.join(_FONT_DIR, _TEXT_FONT_PATHS[key])


@lru_cache(maxsize=256)
def _pil_font(path, size):
    from PIL import ImageFont
    return ImageFont.truetype(path, int(size))


def _emoji_clusters(seg):
    """Approximate number of rendered emoji glyphs in a run; ZWJ sequences and
    keycaps collapse to one. Color emoji advance roughly one em (square)."""
    return max(1, sum(1 for c in seg if c not in "‍" and not (
        "︀" <= c <= "️")))


def _run_width(is_emoji, seg, size, weight, italic):
    if is_emoji:
        return _emoji_clusters(seg) * size  # color emoji ≈ square em advance
    try:
        return _pil_font(_text_font_path(weight, italic), size).getlength(seg)
    except Exception:
        return len(seg) * size * 0.5


def _font_runs(text):
    """Split into (is_emoji, substring) runs, in order, dropping empties."""
    return [(bool(i % 2), s) for i, s in enumerate(_EMOJI_RE.split(text)) if s]


def render_text(x, y, text, size, fill, weight="700", anchor="start",
                italic=False, extra=""):
    """One or more <text> elements rendering `text` with emoji runs in the emoji
    font and the rest in Crimson. `anchor` is start|middle|end. `extra` is
    appended verbatim to every emitted element (e.g. ' opacity="0.5"')."""
    runs = _font_runs(str(text))
    if not runs:
        return ""

    def _one(is_emoji, seg, ax, svg_anchor):
        fam = _EMOJI_FAMILY if is_emoji else _FONT_FAMILY
        fw = "" if is_emoji else f' font-weight="{weight}"'
        st = ' font-style="italic"' if italic and not is_emoji else ""
        ta = "" if svg_anchor == "start" else f' text-anchor="{svg_anchor}"'
        return (f'<text x="{ax}" y="{y}" font-size="{size}" '
                f'font-family="{fam}"{fw}{st} fill="{fill}"{ta}{extra}'
                f'>{_esc(seg)}</text>')

    # Fast path: a single run can use native SVG anchoring (most accurate).
    if len(runs) == 1:
        return _one(runs[0][0], runs[0][1], x, anchor)

    widths = [_run_width(e, s, size, weight, italic) for e, s in runs]
    total = sum(widths)
    cur = x - total / 2 if anchor == "middle" else \
        x - total if anchor == "end" else x
    parts = []
    for (is_emoji, seg), w in zip(runs, widths):
        parts.append(_one(is_emoji, seg, f"{cur:.1f}", "start"))
        cur += w
    return "".join(parts)


def _lux_bg():
    return ""


def _save(svg: str, out_path: str, scale: float = 1):
    try:
        png = bytes(resvg_py.svg_to_bytes(
            svg_string=svg, zoom=scale,
            font_files=_FONT_PATHS,
            font_family=_FONT_FAMILY,
        ))
        img = Image.open(io.BytesIO(png)).convert("RGBA")
        webp_path = os.path.splitext(out_path)[0] + ".webp"
        img.save(webp_path, "WEBP", quality=78, method=1)
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
