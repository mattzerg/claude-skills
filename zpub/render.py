#!/usr/bin/env python3
"""render — narrow ASCII table for zpub. No box-drawing borders.

Per `feedback_zpub_table_render.md`:
- Lead with the next-move callout (one line)
- ONE table, all entries, sorted by RAG severity then publish date
- Plain ASCII alignment; header underlined; no per-row separators (denser)
- Columns: RAG | WHEN | TYPE | TITLE | NEEDS  (≤95 chars wide)
"""
from __future__ import annotations

import datetime as dt
from typing import Iterable
from zoneinfo import ZoneInfo

from zpub import Entry, _parse_iso_date, is_in_flight, rag_state, required_gates
from pipeline import load_cache

PT = ZoneInfo("America/Los_Angeles")

MARK = {"red": "🔴", "amber": "🟠", "yellow": "🟡", "green": "🟢"}
RAG_ORDER = {"red": 0, "amber": 1, "yellow": 2, "green": 3}

COL = {"when": 12, "type": 5, "title": 40, "needs": 30, "pipe": 6}
STAGE_GLYPH = {"passed": "●", "failed": "○", "n_a": "·", "unknown": "?"}


def _pipeline_for(entry, cache: dict) -> dict | None:
    """Return cached pipeline state for an entry, or None if absent or stale schema."""
    if entry.type != "blog":
        return None
    return cache.get("entries", {}).get(entry.id)


def _pipe_glyphs(state: dict) -> str:
    return "".join(STAGE_GLYPH[s["state"]] for s in state.get("stages", []))


def _pipe_summary(state: dict) -> str:
    """Short next-action text from pipeline state (overrides gate-based NEEDS)."""
    nb = state.get("next_blocker")
    if not nb:
        hi = state.get("highest_completed", -1)
        if hi == 5:
            return "✓ LIVE on prod"
        return ""
    return nb

TYPE_CODE = {
    "blog":       "BLOG ",
    "launch":     "LNCH ",
    "case-study": "CASE ",
    "web-page":   "WEB  ",
    "video":      "VIDEO",
    "email":      "EMAIL",
    "social":     "SOCL ",
    "one-pager":  "PAGE ",
    "other":      "OTHR ",
}


def _days_relative(target, today):
    if not target:
        return "  —"
    d = (target - today).days
    return f"-{-d}d" if d < 0 else f"+{d}d"


def _when_cell(target, today):
    if not target:
        return "no date     "
    date = f"{target.strftime('%b')} {target.day:>2}"
    return f"{date}  {_days_relative(target, today):>4}"


def _when_cell_for_entry(e, today):
    """Render `target` with a visual cue when the date is pencilled, not committed.

    Per ~/.claude/plans/synchronous-yawning-storm.md A3: when status is
    review/scheduled and date_confirmed is false, wrap the date in parens
    so the reader can't mistake it for a commitment.
    """
    target = _parse_iso_date(e.publish_target)
    base = _when_cell(target, today)
    if (target and not getattr(e, "date_confirmed", False)
            and e.status in ("review", "scheduled")
            and e.status not in ("published", "distributed", "archived")):
        return f"({base.strip()})".ljust(len(base))
    return base


def _terse_blocker(blockers):
    if not blockers:
        return ""
    return blockers[0].split("(per ")[0].rstrip(" —-·")


def _needs_cell(e: Entry) -> str:
    """Compose the NEEDS column.

    Priority order (per ~/.claude/plans/synchronous-yawning-storm.md A4):
      1. fakeidan pending  → "awaiting Idan review" — the next-move blocker
         most often gates everything downstream on a blog.
      2. failed gate       → "✗ <gate>" — explicit redo target.
      3. blocker           → terse blocker line.
      4. ideating          → "needs draft".
      5. all-passed        → "✓ ready".
      6. other pending     → "<gate> (passed/total)".
    """
    parts = []
    req = required_gates(e.type)
    passed = sum(1 for g in req if e.gates.get(g) == "passed")
    failed = [g for g in req if e.gates.get(g) == "failed"]
    pending = next((g for g in req if e.gates.get(g, "pending") == "pending"), None)

    if "fakeidan" in req and e.gates.get("fakeidan", "pending") == "pending":
        parts.append("awaiting Idan review")
    elif failed:
        parts.append(f"✗ {failed[0]}")
    elif e.blockers:
        parts.append(_terse_blocker(e.blockers))
    elif e.status == "ideating":
        parts.append("needs draft")
    elif passed == len(req) and req:
        parts.append("✓ ready")
    elif pending:
        parts.append(f"{pending} ({passed}/{len(req)})")
    return " · ".join(parts) or "—"


def _truncate(s, n):
    if len(s) <= n:
        return s
    cut = s[: n - 1].rsplit(" ", 1)[0]
    if len(cut) < n - 6:
        cut = s[: n - 1]
    return cut + "…"


def render_table(entries: Iterable[Entry], *, all_view: bool = False,
                 reds_only: bool = False, max_visible: int = 5,
                 pipeline_cache: dict | None = None) -> str:
    today = dt.datetime.now(PT).date()
    pipeline_cache = pipeline_cache if pipeline_cache is not None else {}
    enriched = []
    counts: dict[str, int] = {"red": 0, "amber": 0, "yellow": 0, "green": 0}
    for e in entries:
        color, _ = rag_state(e)
        # In-flight entries are surfaced in their own section, not the work table —
        # exclude from counts so the header reflects actionable work only.
        if not is_in_flight(e)[0]:
            counts[color] = counts.get(color, 0) + 1
        enriched.append((e, color))

    if reds_only:
        reds = [(e, c) for (e, c) in enriched if c == "red"]
        reds.sort(key=lambda t: (_parse_iso_date(t[0].publish_target) or dt.date.max, t[0].id))
        rows = reds[:max_visible]
        if not rows:
            return ""
        return _render(rows, today, header=f"{len(rows)} BLOCKED")

    if not enriched:
        return "(no entries yet — `zpub add` to create one)"

    # Split off in-flight entries first — they get their own DO NOT TOUCH section
    # per feedback_check_in_flight_across_silos.md. Never mixed into work rows.
    in_flight_rows = sorted(
        [(e, c) for (e, c) in enriched if is_in_flight(e)[0]],
        key=lambda t: _parse_iso_date(t[0].publish_target) or dt.date.max,
    )
    work_rows = [(e, c) for (e, c) in enriched if not is_in_flight(e)[0]]

    visible = work_rows if all_view else [(e, c) for (e, c) in work_rows if c != "green"]

    # Scheduled = has date, sorted asc; backlog = no date, sorted by progress (most-done first)
    PROGRESS = {"green": 0, "yellow": 1, "amber": 2, "red": 3}
    scheduled = sorted(
        [(e, c) for (e, c) in visible if _parse_iso_date(e.publish_target)],
        key=lambda t: _parse_iso_date(t[0].publish_target),
    )
    backlog = sorted(
        [(e, c) for (e, c) in visible if not _parse_iso_date(e.publish_target)],
        key=lambda t: (PROGRESS[t[1]], t[0].id),
    )

    out: list[str] = []
    nm = _next_move([(e, c) for (e, c) in enriched if not is_in_flight(e)[0]], today)
    if nm:
        out.append(f"▶ NEXT: {nm}")
        out.append("")

    has_pencilled = any(
        _parse_iso_date(e.publish_target)
        and not getattr(e, "date_confirmed", False)
        and e.status in ("review", "scheduled")
        for e, _ in enriched
    )
    if has_pencilled:
        out.append("legend: (parenthesized dates) are pencilled, not confirmed — do not treat as commitments")
        out.append("")

    if in_flight_rows:
        out.append(_render_in_flight(in_flight_rows, today, pipeline_cache))
        out.append("")

    summary = []
    if counts.get("red"):    summary.append(f"{counts['red']} RED")
    if counts.get("amber"):  summary.append(f"{counts['amber']} AMBER")
    if counts.get("yellow"): summary.append(f"{counts['yellow']} YELLOW")
    if all_view and counts.get("green"):
        summary.append(f"{counts['green']} GREEN")
    elif counts.get("green"):
        summary.append(f"{counts['green']} green hidden")
    header = "PUBLISHING — " + " · ".join(summary or ["empty"])

    if scheduled and backlog:
        out.append(_render(scheduled, today, header=header, cache=pipeline_cache))
        out.append("")  # break
        out.append(_render(backlog, today, header=f"BACKLOG ({len(backlog)}) — most progress first",
                           cache=pipeline_cache))
    elif scheduled:
        out.append(_render(scheduled, today, header=header, cache=pipeline_cache))
    else:
        out.append(_render(backlog, today, header=header, cache=pipeline_cache))

    return "\n".join(out)


def _render_in_flight(rows, today, cache: dict):
    """Dedicated section above the work table — replaces the old 'AUTO-PUBLISH' lie
    with verified pipeline state for blog entries (cache-backed)."""
    out = [f"IN FLIGHT ({len(rows)}) — pipeline state below; blog rows verified from real signals"]
    head = (f"   {'WHEN':<{COL['when']}}  {'TYPE':<{COL['type']}}  "
            f"{'PIPE':<{COL['pipe']}}  {'TITLE':<{COL['title']}}  STATE")
    out.append(head)
    out.append("─" * (len(head) + COL["needs"]))
    for e, _ in rows:
        target = _parse_iso_date(e.publish_target)
        when = _when_cell_for_entry(e, today) if target else "—           "
        state = _pipeline_for(e, cache)
        if state:
            glyphs = _pipe_glyphs(state)
            hi = state.get("highest_completed", -1)
            if hi == 5:
                marker_color = "🟢"
                state_text = "✓ LIVE on prod"
            elif hi >= 4:
                marker_color = "🟡"
                state_text = _pipe_summary(state)
            else:
                marker_color = "🟠"
                state_text = _pipe_summary(state)
        else:
            glyphs = " " * COL["pipe"]
            marker_color = "🟢"
            state_text = (f"→ {e.status}" if e.status != "scheduled"
                          else f"→ status:{e.status} (no pipeline check for type={e.type})")
        out.append(
            f"{marker_color} {when:<{COL['when']}}  "
            f"{TYPE_CODE.get(e.type, 'OTHR '):<{COL['type']}}  "
            f"{glyphs:<{COL['pipe']}}  "
            f"{_truncate(e.title, COL['title']):<{COL['title']}}  "
            f"{_truncate(state_text, COL['needs'] + 30)}"
        )
    return "\n".join(out)


def _render(rows, today, *, header, cache: dict | None = None):
    cache = cache if cache is not None else {}
    out = [header]
    head = (f"   {'WHEN':<{COL['when']}}  {'TYPE':<{COL['type']}}  "
            f"{'PIPE':<{COL['pipe']}}  {'TITLE':<{COL['title']}}  NEEDS")
    out.append(head)
    out.append("─" * (len(head) + COL["needs"]))
    for e, color in rows:
        target = _parse_iso_date(e.publish_target)
        state = _pipeline_for(e, cache)
        if state:
            glyphs = _pipe_glyphs(state)
            needs = _pipe_summary(state) or _needs_cell(e)
        else:
            glyphs = " " * COL["pipe"]
            needs = _needs_cell(e)
        out.append(
            f"{MARK[color]} {_when_cell_for_entry(e, today):<{COL['when']}}  "
            f"{TYPE_CODE.get(e.type, 'OTHR '):<{COL['type']}}  "
            f"{glyphs:<{COL['pipe']}}  "
            f"{_truncate(e.title, COL['title']):<{COL['title']}}  "
            f"{_truncate(needs, COL['needs'] + 20)}"
        )
    return "\n".join(out)


def _next_move(enriched, today):
    """Single highest-priority next-move callout."""
    # 1) imminent (today/tomorrow) — fix open blocker, else confirm gate
    for e, c in enriched:
        if c == "green":
            continue
        target = _parse_iso_date(e.publish_target)
        if target and (target - today).days <= 1:
            if e.blockers:
                return f"fix \"{e.title}\" — {_terse_blocker(e.blockers)}"
            pending = [g for g in required_gates(e.type) if e.gates.get(g, "pending") == "pending"]
            if pending:
                return (f"confirm `{pending[0]}` on \"{e.title}\" → "
                        f"`zpub set {e.id} gates.{pending[0]} passed`")
            return f"ship \"{e.title}\""
    # 2) any imminent (≤7d) blocker
    for e, c in enriched:
        target = _parse_iso_date(e.publish_target)
        if e.blockers and target and (target - today).days <= 7 and c != "green":
            return f"fix \"{e.title}\" — {_terse_blocker(e.blockers)}"
    # 3) any blocker on a scheduled item
    for e, c in enriched:
        if e.blockers and _parse_iso_date(e.publish_target) and c != "green":
            return f"unblock \"{e.title}\" — {_terse_blocker(e.blockers)}"
    # 4) ideating → start draft
    for e, c in enriched:
        if c == "red" and e.status == "ideating":
            return f"start draft on \"{e.title}\""
    return None
