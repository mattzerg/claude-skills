"""Stable IDs that propagate through the engagement pipeline.

Issue-tree leaves get hierarchical IDs (L1.1, L1.1.2). Hypothesis rows, framework
outputs, and minto supporting lines all reference these so consultant-deck can
self-audit upstream chains.
"""
from __future__ import annotations

import re

LEAF_PAT = re.compile(r"^L(\d+)(?:\.(\d+))*$")


def child(parent: str, index: int) -> str:
    """Return the child leaf ID. child('L1', 2) → 'L1.2'."""
    if parent in ("", "L0", "root"):
        return f"L{index}"
    if not parent.startswith("L"):
        parent = f"L{parent}"
    return f"{parent}.{index}"


def parent(leaf: str) -> str | None:
    """Return the parent leaf ID, or None if leaf is top-level. parent('L1.2.3') → 'L1.2'."""
    if not leaf.startswith("L"):
        return None
    parts = leaf[1:].split(".")
    if len(parts) <= 1:
        return None
    return "L" + ".".join(parts[:-1])


def depth(leaf: str) -> int:
    """Return depth. L1 → 1, L1.2 → 2, L1.2.3 → 3."""
    if not leaf.startswith("L"):
        return 0
    return len(leaf[1:].split("."))


def is_leaf_id(s: str) -> bool:
    return bool(LEAF_PAT.match(s))


def hypothesis_id(leaf: str) -> str:
    """H-prefixed hypothesis ID derived from leaf. L1.2 → H1.2."""
    if leaf.startswith("L"):
        return "H" + leaf[1:]
    return f"H{leaf}"


def chart_id(slug: str, recipe: str, n: int = 1) -> str:
    """Stable chart ID: <slug>-<recipe>-<n>."""
    return f"{slug}-{recipe}-{n:02d}"
