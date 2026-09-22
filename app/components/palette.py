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
PALE_TIE = "#fef08a"

# Table fills: background plus the text colour that stays legible on it.
FILL_GOOD = f"background-color: {PALE_GOOD}; color: #14532d"
FILL_CAUTION = f"background-color: {PALE_CAUTION}; color: #7c2d12"
FILL_BAD = "background-color: #fecaca; color: #7f1d1d"
MUTED = "color: #9ca3af"   # present but not to be relied on

# An exact Speed tie, which is a coin flip rather than a band you cannot resolve --
# so it is yellow and not the orange FILL_CAUTION already spends on "Depends". The
# two sit in the same table and mean different things: "Depends" is the verdict
# against a threat's whole range, a tie is a single benchmark landing on your number.
FILL_TIE = f"background-color: {PALE_TIE}; color: #713f12"

# Overlays, appended to a fill rather than replacing it. CSS takes the last
# declaration, so the colour here wins over the fill's own and the background stays.
#
# ONLY THREE PROPERTIES SURVIVE. Streamlit's dataframe grid draws to a canvas and
# reads just `color`, `background-color` and `font-weight` off the Styler; borders,
# italics and everything else are dropped silently, with no warning and no visible
# difference to say so. Anything added here has to live inside those three.
UNRELIABLE = "color: #6b7280"          # present, but the build behind it is split
# The Choice Scarf marker. It used to be a green fill, which stopped being available
# once every Speed cell started carrying a good/bad colour of its own. A border would
# be the natural second channel and is not one of the three, so it is bold blue text
# instead: legible on every fill underneath it, and the background is left free to go
# on meaning who moves first.
SCARF_MARK = "color: #0c4a6e; font-weight: 700"


def discrete_scale(colors: list[str]) -> list[list]:
    """A Plotly colorscale with hard edges, one band per colour."""
    n = len(colors)
    scale = []
    for i, c in enumerate(colors):
        scale += [[i / n, c], [(i + 1) / n, c]]
    return scale
