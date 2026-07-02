"""Zerg brand tokens — source of truth: document-styling-skill/brand.md.

Two-accent system: burnt orange (primary) + brand green (secondary). No third color.
Dual palette: cream (default, Zstack/non-technical) vs charcoal-dark (Zerg parent/technical).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    name: str
    paper: str
    text: str
    accent_primary: str
    accent_primary_alt: str  # AA-compliant on paper
    accent_secondary: str
    accent_secondary_dark: str
    mid_gray: str
    rule_gray: str
    light_gray: str


CREAM = Palette(
    name="zerg-default",
    paper="#f4f0e7",
    text="#111514",
    accent_primary="#b3662f",
    accent_primary_alt="#8a4a1f",
    accent_secondary="#6FBE31",
    accent_secondary_dark="#0a4d33",
    mid_gray="#52605c",
    rule_gray="#dad6cb",
    light_gray="#9aa39d",
)

CHARCOAL = Palette(
    name="zerg-dark",
    paper="#111514",
    text="#f4f0e7",
    accent_primary="#d57a32",
    accent_primary_alt="#b3662f",
    accent_secondary="#6FBE31",
    accent_secondary_dark="#0a4d33",
    mid_gray="#9aa39d",
    rule_gray="#41504c",
    light_gray="#c5cec9",
)


NAVY = Palette(
    name="zerg-navy",
    paper="#ffffff",
    text="#15212e",
    accent_primary="#1F3A5F",
    accent_primary_alt="#16304f",
    accent_secondary="#3a7ca5",
    accent_secondary_dark="#1b4a66",
    mid_gray="#52605c",
    rule_gray="#d3dae2",
    light_gray="#9aa7b3",
)


def get(mode: str = "default") -> Palette:
    """Return the palette by mode. `default`/`cream` → CREAM; `dark`/`charcoal` → CHARCOAL; `navy` → NAVY."""
    m = (mode or "default").lower()
    if m in ("dark", "charcoal", "zerg-dark"):
        return CHARCOAL
    if m in ("navy", "zerg-navy", "zerg-navy-multipage"):
        return NAVY
    return CREAM


def chart_color_cycle(palette: Palette, *, highlight_idx: int | None = None,
                      muted: str | None = None) -> list[str]:
    """Ordered color cycle for matplotlib categorical series.

    If `highlight_idx` is set, every other index is replaced with `muted` (default mid_gray).
    """
    cycle = [
        palette.accent_primary,
        palette.accent_secondary,
        palette.text,
        palette.accent_primary_alt,
        palette.accent_secondary_dark,
        palette.mid_gray,
    ]
    if highlight_idx is None:
        return cycle
    mute = muted or palette.mid_gray
    return [c if i == highlight_idx else mute for i, c in enumerate(cycle)]


# Okabe–Ito color-blind-safe palette (8 colors, ordered).
# Use via `chart-builder --accessible` when audience accessibility is required.
OKABE_ITO = [
    "#E69F00",  # orange
    "#56B4E9",  # sky blue
    "#009E73",  # bluish green
    "#F0E442",  # yellow
    "#0072B2",  # blue
    "#D55E00",  # vermillion
    "#CC79A7",  # reddish purple
    "#000000",  # black
]


def semantic_palette(palette: Palette) -> dict[str, str]:
    """Semantic mapping: positive/negative/neutral/highlight."""
    return {
        "positive": palette.accent_secondary,
        "negative": palette.accent_primary,
        "neutral": palette.mid_gray,
        "highlight": palette.accent_primary,
        "anchor": palette.text,
    }


def matplotlib_rcparams(mode: str = "default") -> dict:
    """rcParams to apply at import time. Caller does plt.rcParams.update(...)."""
    p = get(mode)
    return {
        "figure.facecolor": p.paper,
        "axes.facecolor": p.paper,
        "axes.edgecolor": p.text,
        "axes.labelcolor": p.text,
        "axes.titlecolor": p.text,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.titlepad": 14,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.color": p.mid_gray,
        "ytick.color": p.mid_gray,
        "text.color": p.text,
        "font.family": "sans-serif",
        "font.sans-serif": ["Space Grotesk", "Helvetica Neue", "Arial", "DejaVu Sans"],
        "font.size": 10,
        "axes.titlesize": 13,
        "axes.labelsize": 9,
        "legend.frameon": False,
        "legend.fontsize": 9,
        "grid.color": p.rule_gray,
        "grid.linewidth": 0.6,
        "savefig.facecolor": p.paper,
        "savefig.edgecolor": "none",
        "savefig.dpi": 180,
    }
