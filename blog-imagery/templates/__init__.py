"""Brand-coherent SVG templates for Zerg blog imagery.

Each template module exposes:
    render(config: dict) -> str       # returns SVG markup
    DEFAULT_VIEWBOX: tuple[int, int]  # native viewBox dimensions
    DESCRIPTION: str                  # one-line human description
    EXAMPLE_CONFIG: dict              # minimal valid config for the template

Templates derived from the agents-that-remember post (2026-05-05). All share
the same brand palette so heroes/body/social read as one campaign.
"""
from . import stat_card, funnel, tree

REGISTRY = {
    "stat-card": stat_card,
    "funnel": funnel,
    "tree": tree,
}


def get(name: str):
    if name not in REGISTRY:
        raise KeyError(f"Unknown template '{name}'. Available: {list(REGISTRY)}")
    return REGISTRY[name]
