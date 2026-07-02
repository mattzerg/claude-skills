"""Zerg blog imagery palette + typography. Single source of truth for templates.

Two named themes per the dual-palette routing rule (feedback_zerg_brand.md):

- `zerg-dark` (DEFAULT): research-blog dark register. Cosmic-depth navy with
  electric blue + amber + green light sources. Used for zergai.com/blog posts.

- `zerg-cream`: Zstack product register. Cream paper with charcoal text,
  burnt-orange accent, zerg-green secondary. Used for Zstack microproduct
  bundles (Zergvert, Zergboard, etc.) that share visual language with their
  product surfaces (~/zerg/<product>/web/).

Pick by audience + product context, NOT preference. Template configs may
override per-stage `color` regardless of the theme. To switch the active theme
programmatically, monkey-patch this module's globals BEFORE importing templates,
or use the helper `apply_theme(name)`.
"""

# Default theme exposed as module-level constants (research-blog DARK).
# Templates read these. Bodies of templates reference p.BG / p.AMBER / etc.

# --- zerg-dark (DEFAULT) ---
BG = "#07111E"          # page background (dark navy)
CARD = "#0E1B2D"        # card / inset surface
AMBER = "#F4A261"       # "before" / first-stage / warm
BLUE = "#44B8FF"        # "middle" / second-stage / cool
GREEN = "#1FC78D"       # "after" / final / success
TEXT = "#EBF1F8"        # primary text on dark
MUTED = "#94A6BA"       # secondary / captions / arrows
FONT = "-apple-system, system-ui, 'Helvetica Neue', sans-serif"


# --- named theme dicts (for switching) ---
THEMES = {
    "zerg-dark": {
        "BG":    "#07111E",
        "CARD":  "#0E1B2D",
        "AMBER": "#F4A261",
        "BLUE":  "#44B8FF",
        "GREEN": "#1FC78D",
        "TEXT":  "#EBF1F8",
        "MUTED": "#94A6BA",
        "FONT":  "-apple-system, system-ui, 'Helvetica Neue', sans-serif",
    },
    "zerg-cream": {
        # Zstack product brand per feedback_zerg_brand.md
        "BG":    "#F5EBDC",  # cream paper
        "CARD":  "#FBF6EE",  # cream-50 inset surface
        "AMBER": "#C84A1A",  # burnt-orange accent (primary)
        "BLUE":  "#1C1C1C",  # charcoal (secondary, replaces electric blue)
        "GREEN": "#2F7D44",  # zerg-green (success / final stage)
        "TEXT":  "#1C1C1C",  # charcoal primary text on cream
        "MUTED": "#52605c",  # warm mid-gray for captions
        "FONT":  "'Space Grotesk', -apple-system, system-ui, sans-serif",
    },
}


def apply_theme(name: str) -> None:
    """Switch the active palette. Call BEFORE importing template modules.

    Usage:
        from blog_imagery.templates import _palette
        _palette.apply_theme("zerg-cream")
        from blog_imagery.templates import funnel  # now uses cream palette
    """
    if name not in THEMES:
        raise ValueError(f"unknown theme {name!r}; choices: {list(THEMES)}")
    g = globals()
    for k, v in THEMES[name].items():
        g[k] = v
