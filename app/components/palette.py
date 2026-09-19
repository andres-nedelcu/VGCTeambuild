"""One colour system for all four visuals.

The invariant every visual keeps: **green means good for Andres.** The defensive
grid and the coverage grid therefore run their ramps in opposite directions -- being
hit for 4x is bad, hitting for 4x is good -- and that inversion is expressed here by
naming the two ends once, instead of two hand-maintained hex lists that have to be
kept as mirror images of each other.

Heatmaps take the bare ramps; styled dataframes take the FILL_* rules, which carry an
explicit text colour because these light backgrounds must stay readable on the dark
theme too.
"""

from __future__ import annotations

# The effectiveness ladder every grid shares.
LEVELS = [0.0, 0.25, 0.5, 1.0, 2.0, 4.0]
LABELS = ["0", "¼", "½", "", "2", "4"]

NONE = "#4b5563"      # grey: no interaction at all, so neither good nor bad
GOOD_STRONG = "#15803d"
GOOD_SOFT = "#86efac"
NEUTRAL = "#f3f4f6"
BAD_SOFT = "#fb923c"
BAD_STRONG = "#dc2626"

# Ramps over LEVELS. The only difference is which end is good for you.
DEFENDING = [NONE, GOOD_STRONG, GOOD_SOFT, NEUTRAL, BAD_SOFT, BAD_STRONG]
ATTACKING = [NONE, BAD_STRONG, BAD_SOFT, NEUTRAL, GOOD_SOFT, GOOD_STRONG]

PALE_GOOD = "#bbf7d0"
PALE_CAUTION = "#fed7aa"

# Table fills: background plus the text colour that stays legible on it.
FILL_GOOD = f"background-color: {PALE_GOOD}; color: #14532d"
FILL_CAUTION = f"background-color: {PALE_CAUTION}; color: #7c2d12"
FILL_BAD = "background-color: #fecaca; color: #7f1d1d"
MUTED = "color: #9ca3af"   # present but not to be relied on


def discrete_scale(colors: list[str]) -> list[list]:
    """A Plotly colorscale with hard edges, one band per colour."""
    n = len(colors)
    scale = []
    for i, c in enumerate(colors):
        scale += [[i / n, c], [(i + 1) / n, c]]
    return scale
