"""Vault-canonical path resolution for engagement artifacts."""
from __future__ import annotations

import os
import re
from pathlib import Path

VAULT_ROOT = Path(
    os.environ.get(
        "ZERG_VAULT_ROOT",
        "/Users/mattheweisner/Obsidian/Zerg/MattZerg",
    )
)

ENGAGEMENTS_ROOT = VAULT_ROOT / "Engagements"

VALID_MODES = ("client", "pm", "ops", "life")
LIFE_DIR = "_personal"


def slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")[:64]


def engagement_dir(slug: str, mode: str = "ops") -> Path:
    """Resolve the engagement folder.

    client → Engagements/clients/<slug>/
    life   → Engagements/_personal/<slug>/  (air-gapped)
    pm     → Engagements/pm/<slug>/
    ops    → Engagements/ops/<slug>/
    """
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {VALID_MODES}; got {mode!r}")
    if mode == "client":
        # client engagements live under the client-first home since 2026-06-10
        clients_root = VAULT_ROOT / "Clients"
        if clients_root.exists():
            for d in clients_root.iterdir():
                if d.is_dir() and slug.lower().startswith(d.name.lower().replace("-", "")[:6]):
                    return d / "engagement" / slug
        return ENGAGEMENTS_ROOT / "clients" / slug
    if mode == "life":
        return ENGAGEMENTS_ROOT / LIFE_DIR / slug
    return ENGAGEMENTS_ROOT / mode / slug


def phase_dir(slug: str, mode: str, phase: str) -> Path:
    """Resolve a phase subdirectory. phase ∈ {scqa, issue-tree, hypotheses, frameworks,
    storyline, analysis, deliverable, 01-...09-...}."""
    return engagement_dir(slug, mode) / phase


def out_dir(engagement: str | None = None, mode: str = "ops", tmp: bool = False) -> Path:
    """Default output directory for a skill. With --tmp, writes to /tmp/consultant/<skill>/."""
    if tmp or not engagement:
        return Path("/tmp/consultant")
    return engagement_dir(engagement, mode)


def dated_filename(slug: str, suffix: str = "md", date: str | None = None) -> str:
    """`<slug>-YYYY-MM-DD.<suffix>`"""
    import datetime as _dt

    d = date or _dt.date.today().isoformat()
    return f"{slug}-{d}.{suffix}"


def ensure_engagement(slug: str, mode: str = "ops") -> Path:
    """Create the engagement folder tree and return the root path."""
    root = engagement_dir(slug, mode)
    for sub in (
        "",
        "05-analysis/data",
        "05-analysis/charts",
        "05-analysis",
        "08-deliverable",
    ):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root
