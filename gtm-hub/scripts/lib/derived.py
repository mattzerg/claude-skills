"""Cross-entity derivation: project ↔ decision ↔ metric ↔ content blockers.

The manual `blockers` field on a project is human-written. This module ADDS
derived blockers by scanning each project's `linked_entities` for things that
are currently in an inactive/red state:

- Linked decision with status=open  → "OPEN DECISION: <title>"
- Linked metric with status=not-instrumented → "METRIC RED: <title>"
- Linked content past target_date with status != published/distributed → "CONTENT PAST DUE: <title>"
- Linked experiment past kill_date with status=running → "EXPERIMENT OVERDUE: <id>"

The reverse mapping (decision → projects it blocks) is also computed so the
open-decisions panel can show "this call unblocks projects X, Y" — and so
the decision rule engine can lift priority based on downstream impact.
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Any


# Match the slug embedded in a linked_entities path like "decisions/dec-foo.md"
# or "metrics/wapw.md" or just "wapw" or "dec-foo".
_PATH_SLUG_RE = re.compile(r"(?:.*/)?([a-zA-Z0-9][a-zA-Z0-9_-]*)(?:\.md)?")


def _normalize_link(s: str) -> str:
    """Pull the canonical slug out of a linked_entities string."""
    if not isinstance(s, str):
        return ""
    # Strip trailing parentheticals like "(target 5/19)"
    s = re.sub(r"\s*\([^)]*\).*$", "", s).strip()
    m = _PATH_SLUG_RE.match(s)
    if not m:
        return ""
    return m.group(1)


def _slug_index(entities: list[dict]) -> dict[str, dict]:
    """Map entity id → entity row for fast lookup."""
    return {e.get("id"): e for e in entities if e.get("id")}


def derive_project_blockers(project: dict, by_slug: dict[str, dict], today: dt.date) -> list[str]:
    """Return derived blocker strings for a project based on linked-entity state."""
    derived: list[str] = []
    linked = project.get("linked_entities") or []
    if not isinstance(linked, list):
        return derived
    for raw in linked:
        slug = _normalize_link(str(raw))
        target = by_slug.get(slug)
        if not target:
            continue
        t = target.get("type")
        status = target.get("status")
        title = target.get("title") or slug

        if t == "decision" and status in ("open", "deferred"):
            derived.append(f"OPEN DECISION: {title} (`{slug}`)")
        elif t == "metric" and status == "not-instrumented":
            derived.append(f"METRIC RED: {title}")
        elif t == "experiment" and status == "running":
            kd = target.get("kill_date")
            try:
                if kd and dt.date.fromisoformat(kd) < today:
                    derived.append(f"EXPERIMENT OVERDUE: {target.get('id')} (kill {kd})")
            except (ValueError, TypeError):
                pass
        elif t == "content":
            td = target.get("target_date")
            try:
                if td and dt.date.fromisoformat(td) < today and status not in ("published", "distributed", "parked"):
                    derived.append(f"CONTENT PAST DUE: {title} (target {td}, status={status})")
            except (ValueError, TypeError):
                pass
        elif t == "launch" and status not in ("shipped", "parked"):
            sd = target.get("ship_date")
            try:
                if sd and dt.date.fromisoformat(sd) < today:
                    derived.append(f"LAUNCH PAST DUE: {title} (ship {sd})")
            except (ValueError, TypeError):
                pass
    return derived


def derive_decision_blocks_projects(decision_id: str, projects: list[dict]) -> list[dict]:
    """Find projects whose `linked_entities` reference this decision."""
    if not decision_id:
        return []
    out: list[dict] = []
    for p in projects:
        linked = p.get("linked_entities") or []
        if not isinstance(linked, list):
            continue
        for raw in linked:
            if _normalize_link(str(raw)) == decision_id:
                out.append(p)
                break
    return out


_RAG_SEVERITY = {"green": 0, "amber": 1, "red": 2}


def compute_effective_rag(project: dict, today: dt.date) -> str:
    """Derive a RAG status from observable project state.

    Inputs considered:
      - status (blocked / paused / canceled)
      - target_date vs today (past-due, near, distant)
      - derived_blockers count
      - manual rag field (the author's own assessment)

    Returns one of {red, amber, green}. The final effective_rag is the
    MAX severity of (manual rag, derived rag) — so manual ratings can only
    upgrade severity, never hide a real problem.
    """
    status = project.get("status")
    manual_rag = (project.get("rag") or "").lower()
    derived_blockers = project.get("derived_blockers") or []
    n_blockers = len(derived_blockers) if isinstance(derived_blockers, list) else 0

    # Hard reds
    if status in ("blocked",):
        derived = "red"
    elif status in ("canceled",):
        derived = "green"  # canceled isn't actionable
    elif status in ("shipped",):
        derived = "green"
    else:
        target = project.get("target_date") or ""
        try:
            td = dt.date.fromisoformat(target) if target else None
        except (ValueError, TypeError):
            td = None
        if td and td < today and status not in ("shipped", "canceled"):
            derived = "red"  # past-due
        elif td and (td - today).days <= 7 and n_blockers > 0:
            derived = "red"  # imminent + blocked
        elif td and (td - today).days <= 21 and n_blockers > 0:
            derived = "amber"
        elif n_blockers > 0:
            derived = "amber"
        else:
            derived = "green"

    # max severity wins
    manual_severity = _RAG_SEVERITY.get(manual_rag, -1)
    derived_severity = _RAG_SEVERITY.get(derived, -1)
    if manual_severity > derived_severity:
        return manual_rag
    return derived


def annotate_index(entities: list[dict], today: dt.date | None = None) -> list[dict]:
    """Return a copy of `entities` with derived fields added.

    Two-pass: derived_blockers first (per project), then effective_rag (since
    RAG depends on derived_blockers count), then blocks_projects on decisions
    (which references the now-current rag for icon rendering).
    """
    today = today or dt.date.today()
    by_slug = _slug_index(entities)

    # Pass 1: add derived_blockers + effective_rag to each project
    enriched: list[dict] = []
    for e in entities:
        copy = dict(e)
        if e.get("type") == "project":
            copy["derived_blockers"] = derive_project_blockers(e, by_slug, today)
            copy["effective_rag"] = compute_effective_rag(copy, today)
        enriched.append(copy)

    # Pass 2: blocks_projects on decisions, using enriched projects
    projects = [e for e in enriched if e.get("type") == "project"]
    out: list[dict] = []
    for e in enriched:
        copy = dict(e)
        if e.get("type") == "decision":
            blocked_projects = derive_decision_blocks_projects(e.get("id") or "", projects)
            copy["blocks_projects"] = [
                {
                    "id": p.get("id"),
                    "title": p.get("title"),
                    "target_date": p.get("target_date"),
                    "rag": p.get("effective_rag") or p.get("rag"),
                    "status": p.get("status"),
                }
                for p in blocked_projects
            ]
        out.append(copy)
    return out
