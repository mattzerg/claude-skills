#!/usr/bin/env python3
"""One rotating 'starved personal lane' nudge for the morning brief.

Sibling to daily_pick.py. Where daily_pick surfaces a taste *pick* (what to
watch/cook/read), this surfaces a *life lane that's going untended* — grounded
in real workstreams staleness, never fabricated. Date-seeded so it's stable
within a day and rotates across days.

Grounding sources (read-only):
  - ~/.claude/workstreams/state.json  → per-lane bucket + actionable counts
  - MHE/Personal/Taste-Archive/recommendations.md → optional taste cross-link
    for lanes that map to a taste domain (travel / shopping / research)

Privacy: emits lane name + integer counts + a pointer only. No raw $ figures,
no addresses, no relationship specifics — those stay in the deep tier. The
recommendations.md it cross-links is already leak-guard-scanned (SHAREABLE).

Morning-brief usage (one compact row; brief truncates detail):
    python3 ~/.claude/skills/personal-recs/starved_nudge.py
"""
import datetime
import hashlib
import json
import os
import re

STATE = os.path.expanduser("~/.claude/workstreams/state.json")
RECS = os.path.expanduser(
    "~/Obsidian/MHE/Personal/Taste-Archive/recommendations.md")

# Lanes worth nudging as "life going untended". Excludes tooling/admin lanes
# (personal-systems, personal-email) and empty placeholders. Maps each to a
# pointer the brief can hand off to.
LANE_HINTS = {
    "personal-finance": ("💸", "/workstreams show personal-finance"),
    "personal-4727": ("🏠", "/workstreams show personal-4727"),
    "personal-network": ("🤝", "/workstreams show personal-network"),
    "personal-health": ("🩺", "/workstreams show personal-health"),
    "personal-home": ("🏠", "/workstreams show personal-home"),
    "personal-shopping": ("🛒", "/personal-recs recommend cook"),
    "personal-research": ("📚", "/personal-recs recommend read"),
    "travel": ("✈️", "/personal-recs recommend travel"),
    "personal-games": ("🎮", "/workstreams show personal-games"),
}

# Lanes that map onto a recommendations.md section, for an optional taste cross-link.
LANE_RECS_SECTION = {
    "travel": "Travel",
    "personal-shopping": "Cook",
    "personal-research": "Read",
}

STALE_BUCKETS = {"stale", "parked"}


def load_lanes():
    """Return [(lane_id, actionable_count)] for nudge-worthy stale/parked lanes."""
    if not os.path.exists(STATE):
        return []
    try:
        state = json.load(open(STATE, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    out = []
    for lid, w in state.get("workstreams", {}).items():
        if lid not in LANE_HINTS:
            continue
        if w.get("bucket") not in STALE_BUCKETS:
            continue
        actionable = (w.get("counts") or {}).get("actionable", 0)
        if actionable <= 0:
            continue
        out.append((lid, actionable))
    # Busiest-untended first; ties broken by lane id for determinism.
    out.sort(key=lambda t: (-t[1], t[0]))
    return out


def recs_section_pick(section: str) -> str:
    """First bolded item from a recommendations.md section, or '' if absent."""
    if not os.path.exists(RECS):
        return ""
    in_section = False
    for line in open(RECS, encoding="utf-8"):
        if line.startswith("## "):
            in_section = section.lower() in line.lower()
            continue
        if in_section:
            m = re.match(r"\s*-\s+\*\*(.+?)\*\*", line)
            if m:
                return m.group(1).strip()
    return ""


def nudge_line():
    """Return (emoji, label, detail) for the rotating starved-lane nudge, or None."""
    lanes = load_lanes()
    if not lanes:
        return None
    # Date-seeded rotation across the top lanes so the nudge varies day to day
    # while staying weighted toward the busiest-untended ones (top 4 eligible).
    pool = lanes[:4]
    day = datetime.date.today().isoformat()
    idx = int(hashlib.md5(day.encode()).hexdigest(), 16) % len(pool)
    lane_id, actionable = pool[idx]
    emoji, pointer = LANE_HINTS[lane_id]
    label = lane_id.replace("personal-", "").replace("-", " ")
    detail = f"{actionable} untended → {pointer}"
    # Optional taste cross-link for life lanes that map to a taste domain.
    section = LANE_RECS_SECTION.get(lane_id)
    if section:
        pick = recs_section_pick(section)
        if pick:
            detail = f"{actionable} untended · try {pick} → {pointer}"
    return (emoji, f"lane: {label}", detail)


def main():
    n = nudge_line()
    if not n:
        print("(no starved lanes — all personal lanes fresh)")
        return
    emoji, label, detail = n
    print(f"{emoji} {label}: {detail}")


if __name__ == "__main__":
    main()
