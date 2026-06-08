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

_CELL_FILL = 'fill="#3d3d3d" fill-opacity="1.0"'
_GOLD_EDGE = '#a9743f'
_CELL_STROKE_W = 4
_CELL_STROKE_OPACITY = 1.


# Shared <defs> injected once per document by _save(): a vertical metallic
# gradient for the gold frame (bright top edge -> dark bronze bottom, reads as a
# lit bevel) and a soft drop shadow that lifts cells off the parchment.
_DEFS = (
    '<defs>'
    '<linearGradient id="goldEdge" x1="0" y1="0" x2="0" y2="1">'
    '<stop offset="0" stop-color="#cca263"/>'
    '<stop offset="0.5" stop-color="#a9743f"/>'
    '<stop offset="1" stop-color="#6e4523"/>'
    '</linearGradient>'
    '<filter id="cellShadow" x="-20%" y="-20%" width="140%" height="140%">'
    '<feDropShadow dx="0" dy="3" stdDeviation="3" '
    'flood-color="#000000" flood-opacity="0.45"/>'
    '</filter>'
    '</defs>'
)

# Light tint for the inner bevel highlight line.
_BEVEL_HILITE = "#f6e4b0"


def _cell(x, y, w, h, rx, color=_GOLD_EDGE, width=_CELL_STROKE_W):
    """Full cell chrome as one or more <rect> elements: a soft drop shadow, a
    metallic gradient stroke for the gold frame (semantic colors stay solid),
    and a thin inner highlight inset from the edge that gives the border a
    beveled, polished-metal look. Gradient + shadow live in the shared _DEFS."""
    stroke = "url(#goldEdge)" if color == _GOLD_EDGE else color
    inset = max(width / 2 + 1, 2)
    ir = max(rx - inset, 0)
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
        f'{_CELL_FILL} stroke="{stroke}" stroke-opacity="{_CELL_STROKE_OPACITY}" '
        f'stroke-width="{width}" filter="url(#cellShadow)"/>'
        f'<rect x="{x + inset}" y="{y + inset}" width="{w - 2 * inset}" '
        f'height="{h - 2 * inset}" rx="{ir}" fill="none" '
        f'stroke="{_BEVEL_HILITE}" stroke-opacity="0.25" stroke-width="1"/>'
    )

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
_EMOJI_FONT_PATH = os.path.join(_FONT_DIR, "NotoColorEmoji.ttf")


def _text_font_path(weight, italic):
    key = ("700", False) if str(weight) == "700" and not italic else \
          ("400", True) if italic else ("400", False)
    return os.path.join(_FONT_DIR, _TEXT_FONT_PATHS[key])


@lru_cache(maxsize=256)
def _pil_font(path, size):
    from PIL import ImageFont
    return ImageFont.truetype(path, int(size))


def _run_width(is_emoji, seg, size, weight, italic):
    """Advance width of a run, measured with the same font resvg will use, so
    adjacent runs (e.g. 🔥 + streak number) don't overlap."""
    path = _EMOJI_FONT_PATH if is_emoji else _text_font_path(weight, italic)
    try:
        return _pil_font(path, size).getlength(seg)
    except Exception:
        # Color emoji advance ≈ 1.25 em; plain text ≈ 0.5 em per char.
        return len(seg) * size * (1.25 if is_emoji else 0.5)


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


def render_engraved(x, y, text, size, fill, weight="700", anchor="middle",
                    italic=False, shadow="#000000", highlight="#ffe9a8"):
    """Title text that looks carved into the surface (3D inward / inset). Assumes
    a light source from the top: a dark edge peeks above each glyph and a light
    edge below it. Layers, back to front: dark copy nudged up, light copy nudged
    down, then the real fill on top. Offset scales with font size."""
    d = max(1, round(size / 28))
    return (
        render_text(x, y - d, text, size, shadow, weight, anchor, italic,
                    extra=' opacity="0.6"')
        + render_text(x, y + d, text, size, highlight, weight, anchor, italic,
                      extra=' opacity="0.28"')
        + render_text(x, y, text, size, fill, weight, anchor, italic)
    )


def _lux_bg():
    return ""


def _save(svg: str, out_path: str, scale: float = 1):
    # Inject the shared gradient/shadow defs right after the opening <svg ...> tag
    # (the first '>' reliably closes it — no '>' appears in the attribute values).
    if "url(#goldEdge)" in svg or "url(#cellShadow)" in svg:
        svg = svg.replace(">", ">" + _DEFS, 1)
    try:
        png = bytes(resvg_py.svg_to_bytes(
            svg_string=svg, zoom=scale,
            font_files=_FONT_PATHS,
            font_family=_FONT_FAMILY,
        ))
        img = Image.open(io.BytesIO(png)).convert("RGBA")
        webp_path = os.path.splitext(out_path)[0] + ".webp"
        img.save(webp_path, "WEBP", quality=80, method=1)
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
