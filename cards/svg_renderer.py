"""Backward-compatible re-export shim.

All logic has been split into:
  svg_base.py        — constants, _save, _local_data_uri
  svg_primitives.py  — layout constants, _d_* drawing helpers
  svg_leaderboard.py — leaderboard + match-result renderers
  svg_stats.py       — stats card renderers
"""

from cards.svg_base import *  # noqa: F401, F403
from cards.svg_primitives import *  # noqa: F401, F403
from cards.svg_leaderboard import (  # noqa: F401
    render_header,
    render_rows,
    render_faction_table,
    render_result,
    render_elo_curve,
    render_header_async,
    render_rows_async,
    render_faction_table_async,
    render_result_async,
)
from cards.svg_stats import (  # noqa: F401
    render_stats_header_img,
    render_ult_section_img,
    render_faction_section_img,
    render_class_section_img,
    render_stats_card,
    render_stats_card_async,
)
