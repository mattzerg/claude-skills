"""autonomy.py — resolve an entity's autonomy verdict.

Resolution order (per ~/.config/zerg/autonomy.yaml):
  1. Entity-level `autonomy:` frontmatter (auto | needs_matt | blocked_external)
  2. Class default from autonomy.yaml
  3. fallback (needs_matt)

Used by decision-queue/aggregate.py and downstream by triage + morning-brief.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None  # type: ignore

AUTONOMY_CONFIG = Path(os.path.expanduser("~/.config/zerg/autonomy.yaml"))

VALID_VERDICTS = {"auto", "needs_matt", "blocked_external"}


@dataclass
class AutonomyResolution:
    verdict: str  # auto | needs_matt | blocked_external
    source: str   # entity | class:<name> | fallback
    why: str      # one-line rationale
    class_name: Optional[str] = None


_config_cache: Optional[dict] = None


def _load_config() -> dict:
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    if not AUTONOMY_CONFIG.exists():
        _config_cache = {"classes": {}, "fallback": {"default": "needs_matt", "why": "no config"}}
        return _config_cache
    if yaml is None:
        # Minimal parse fallback if PyYAML missing — accept only as last resort
        _config_cache = {"classes": {}, "fallback": {"default": "needs_matt", "why": "yaml missing"}}
        return _config_cache
    with AUTONOMY_CONFIG.open() as fh:
        _config_cache = yaml.safe_load(fh) or {}
    if "classes" not in _config_cache:
        _config_cache["classes"] = {}
    if "fallback" not in _config_cache:
        _config_cache["fallback"] = {"default": "needs_matt", "why": "no fallback in config"}
    return _config_cache


def resolve(
    *,
    entity_autonomy: Optional[str] = None,
    entity_class: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> AutonomyResolution:
    """Resolve verdict for an entity.

    entity_autonomy: value from frontmatter `autonomy:` field if present
    entity_class:    classifier name (e.g., 'pseo_publish', 'content_draft')
    tags:            optional tag list — `[blocked:idan]` etc forces blocked_external
    """
    # Tag-based hard override
    if tags:
        for t in tags:
            t_norm = t.strip().lower().strip("[]")
            if t_norm.startswith("blocked:") or t_norm.startswith("waiting:"):
                target = t_norm.split(":", 1)[1] if ":" in t_norm else "external"
                return AutonomyResolution(
                    verdict="blocked_external",
                    source=f"tag:{t_norm}",
                    why=f"Waiting on {target}; not Matt's decision yet.",
                )

    # Entity-level override
    if entity_autonomy:
        v = entity_autonomy.strip().lower()
        if v in VALID_VERDICTS:
            return AutonomyResolution(
                verdict=v,
                source="entity",
                why="explicit entity frontmatter",
            )

    cfg = _load_config()

    # Class default
    if entity_class:
        cls = cfg["classes"].get(entity_class)
        if cls:
            v = cls.get("default", "needs_matt").strip().lower()
            if v not in VALID_VERDICTS:
                v = "needs_matt"
            return AutonomyResolution(
                verdict=v,
                source=f"class:{entity_class}",
                why=cls.get("why", "(no rationale in config)"),
                class_name=entity_class,
            )

    # Fallback
    fb = cfg.get("fallback", {})
    return AutonomyResolution(
        verdict=fb.get("default", "needs_matt"),
        source="fallback",
        why=fb.get("why", "unclassified; safer to ask"),
    )


# --- Convenience classifiers ---

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def parse_frontmatter(text: str) -> dict:
    """Quick YAML frontmatter extract; returns {} on miss."""
    m = _FRONTMATTER_RE.match(text)
    if not m or yaml is None:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except Exception:
        return {}


def classify_zpub_entry(fm: dict) -> str:
    """Map a zpub frontmatter dict to an autonomy class name."""
    t = (fm.get("type") or "").lower()
    status = (fm.get("status") or "").lower()
    if t == "pseo":
        if status in ("review", "scheduled", "published"):
            return "pseo_publish"
        return "content_draft"
    if status in ("ideating", "drafting"):
        return "content_draft"
    return "content_publish"


def classify_gtm_entity(folder: str, fm: dict) -> str:
    """Map a gtm-hub entity to an autonomy class."""
    folder = folder.strip("/").lower()
    status = (fm.get("status") or "").lower()
    if folder.startswith("experiments"):
        return "experiment_launch" if status == "running" else "experiment_design"
    if folder.startswith("prospects") or folder.startswith("bd"):
        if status == "outreach_drafted":
            return "prospect_outreach"
        return "prospect_enrichment"
    if folder.startswith("content"):
        return classify_zpub_entry(fm)
    if folder.startswith("launches"):
        return "content_publish"
    return "vault_organization"


def classify_inbox_row(row_text: str) -> Optional[str]:
    """Best-effort classify an inbox.md row by tags + verb heuristics.

    Returns class name or None (-> fallback)."""
    rt = row_text.lower()
    if "[blocked:idan]" in rt:
        return "idan_review_gate"
    if "[blocked:vendor]" in rt or "[waiting:" in rt:
        return "vendor_response"
    if "[blocked:matt-review]" in rt:
        return None  # explicitly needs Matt — fallback handles
    # Verb sniff
    if any(v in rt for v in ("draft email", "send email", "reply to", "respond to")):
        return "external_send"
    if any(v in rt for v in ("open pr", "ship pr", "create pr")):
        return "pr_creation"
    if "publish" in rt and ("post" in rt or "blog" in rt or "launch" in rt):
        return "content_publish"
    return None
