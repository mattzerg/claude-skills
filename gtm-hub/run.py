#!/usr/bin/env python3
"""gtm-hub command dispatcher.

Usage:
    gtm-hub <command> [args]

Commands:
    regenerate              rebuild index → decisions → README.md
    decisions               print just the action-led panel
    status [TYPE]           list entities (optional --filter field=value)
    log <ID> KEY=VALUE ...  structured update to a single entity
    new <TYPE>              scaffold new entity with valid frontmatter
    audit                   schema drift + stale-entity check
    post [--post]           weekly digest to FM→Matt DM (dry-run by default)
    migrate [--dry-run]     split bulk ledgers into per-entity files
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
SCRIPTS = THIS_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS))

from lib import frontmatter  # noqa: E402
from lib.entities import GROWTH_DIR, META_DIR, load_all, load_one  # noqa: E402
from lib.schema import DIR_FOR_TYPE, STATUS_VALUES, parse_date  # noqa: E402


TODAY = dt.date.today().isoformat()


def _run(*cmd: str) -> int:
    return subprocess.run([sys.executable, *cmd], check=False).returncode


def cmd_regenerate(_: list[str]) -> int:
    rc = _run(str(SCRIPTS / "index.py"))
    if rc:
        return rc
    rc = _run(str(SCRIPTS / "decisions.py"))
    if rc:
        return rc
    rc = _run(str(SCRIPTS / "render.py"))
    if rc:
        return rc
    return _run(str(SCRIPTS / "regen_ledgers.py"))


def cmd_regen_ledgers(_: list[str]) -> int:
    return _run(str(SCRIPTS / "regen_ledgers.py"))


def cmd_decisions(_: list[str]) -> int:
    """Show open human-curated decisions FIRST, then rule-derived triage."""
    import datetime as dt

    today = dt.date.today()
    open_decs = [
        e for e in load_all()
        if e.type == "decision" and e.meta.get("status") in ("open", "deferred")
    ]
    if open_decs:
        def _key(e):
            d = e.meta.get("deadline")
            try:
                dl = dt.date.fromisoformat(d) if d else None
            except (ValueError, TypeError):
                dl = None
            if dl:
                return (0, (dl - today).days, e.id)
            return (1, 0, e.id)
        open_decs.sort(key=_key)
        n = len(open_decs)
        print()
        print("═" * 70)
        print(f"  🤔 OPEN DECISIONS — YOUR PLATE ({n})")
        print("═" * 70)
        for i, e in enumerate(open_decs, 1):
            m = e.meta
            title = m.get("title") or e.id
            deadline_str = m.get("deadline") or ""
            urgency_line = "⚪ no deadline"
            if deadline_str:
                try:
                    dl = dt.date.fromisoformat(deadline_str)
                    delta = (dl - today).days
                    long_date = dl.strftime("%b %-d, %Y")
                    if delta < 0:
                        urgency_line = f"🔴 OVERDUE by {-delta}d (was {long_date})"
                    elif delta == 0:
                        urgency_line = f"🔴 DUE TODAY ({long_date})"
                    elif delta <= 7:
                        urgency_line = f"🟠 DUE {long_date} ({delta} day{'s' if delta != 1 else ''})"
                    elif delta <= 21:
                        urgency_line = f"🟡 due {long_date} ({delta} days)"
                    else:
                        urgency_line = f"🟢 due {long_date} ({delta} days)"
                except ValueError:
                    urgency_line = f"deadline {deadline_str}"
            unblocks = m.get("unblocks") or []
            unblocks_n = len(unblocks) if isinstance(unblocks, list) else 0
            unblocks_str = f" · unblocks {unblocks_n}" if unblocks_n else ""
            status_pill = "" if m.get("status") == "open" else f" · [{m.get('status')}]"

            print()
            print(f"  ┌─ DECISION {i} of {n} {'─' * (52 - len(str(i)) - len(str(n)))}")
            print(f"  │  {title}")
            print(f"  │  {urgency_line}{unblocks_str}{status_pill}")
            print(f"  └{'─' * 58}")
            print()

            question = m.get("question") or ""
            if question:
                print("  The call:")
                for q_line in str(question).strip().splitlines():
                    print(f"    {q_line}")
                print()

            context = m.get("context") or ""
            if context:
                print("  Why it matters:")
                for c_line in str(context).strip().splitlines():
                    print(f"    {c_line}")
                print()

            options = m.get("options") or []
            if isinstance(options, list) and options:
                print("  Options:")
                for opt_i, opt in enumerate(options):
                    if not isinstance(opt, dict):
                        continue
                    letter = chr(ord("A") + opt_i) if opt_i < 26 else f"#{opt_i+1}"
                    key = opt.get("key", "?")
                    label = opt.get("label", key)
                    print(f"    {letter}. {label}")
                    impl = opt.get("implications")
                    if impl:
                        for impl_line in str(impl).strip().splitlines():
                            print(f"       {impl_line}")
                    print(f"       → gtm decide {e.id} {key}")
                    print()

            if isinstance(unblocks, list) and unblocks:
                print("  Downstream impact — unblocks:")
                for u in unblocks:
                    print(f"    · {u}")
                print()

            print(f"  Not ready? → gtm defer {e.id}")
            print()
        print("═" * 70)

    dec_path = META_DIR / "decisions.json"
    if not dec_path.exists():
        print("no decisions.json yet — run `gtm-hub regenerate`", file=sys.stderr)
        return 1
    payload = json.loads(dec_path.read_text(encoding="utf-8"))
    rule_decisions = [d for d in payload.get("decisions", []) if d.get("rule") != "decision.open"]

    # Split decisions vs backlog (per kind), then diversify each so N firings
    # of the same rule collapse to one row with "+N more: name1, name2, name3".
    # Matches the README render (render.py § render_decisions / render_debt).
    sys.path.insert(0, str(SCRIPTS))
    from lib.rules import diversify  # noqa: E402

    actionable = [d for d in rule_decisions if d.get("kind", "decision") != "backlog"]
    backlog = [d for d in rule_decisions if d.get("kind") == "backlog"]
    visible_actionable = diversify(actionable, limit=5)
    visible_backlog = diversify(backlog, limit=3)

    def _print_block(title: str, visible: list, full: list, footer: str | None = None) -> None:
        n_signals = len(full)
        n_rules = len(visible)
        print()
        print(f"  ▶ {title} — {n_signals} signal{'s' if n_signals != 1 else ''} · {n_rules} rule{'s' if n_rules != 1 else ''}")
        print(f"  {'─' * 68}")
        for d, siblings, names in visible:
            print(f"  [{d['priority']:>3}]  {d['rule']:<32}  {d['message']}")
            if siblings:
                shown = ", ".join(names)
                extra = f" +{siblings - len(names)}" if siblings > len(names) else ""
                print(f"         └─ also: {shown}{extra}")
        rolled = n_signals - sum(1 + s for _, s, _ in visible)
        if rolled > 0:
            print(f"         _(+{rolled} more across other rules — see `_meta/decisions.json`)_")
        if footer:
            print(f"  _{footer}_")

    if visible_actionable:
        _print_block("TRIAGE (rule-derived signals)", visible_actionable, actionable)
    else:
        print()
        print("  ▶ TRIAGE — quiet 🟢")

    if visible_backlog:
        _print_block(
            "MEASUREMENT DEBT",
            visible_backlog,
            backlog,
            footer="Known cleanup epics — not this-week calls.",
        )
    print()
    return 0


def cmd_status(args: list[str]) -> int:
    p = argparse.ArgumentParser(prog="gtm-hub status")
    p.add_argument("type", nargs="?")
    p.add_argument("--filter", action="append", default=[], help="field=value (repeatable)")
    ns = p.parse_args(args)
    entities = load_all()
    if ns.type:
        entities = [e for e in entities if e.type == ns.type]
    for flt in ns.filter:
        if "=" not in flt:
            continue
        k, _, v = flt.partition("=")
        entities = [e for e in entities if str(e.meta.get(k, "")) == v]
    print(f"{len(entities)} match")
    for e in entities[:50]:
        status = e.meta.get("status", "—")
        title = (e.meta.get("title") or e.id)[:60]
        last = e.meta.get("last_touch") or "—"
        print(f"  {e.type:<11} {e.id:<28} {status:<14} {last:<12} {title}")
    if len(entities) > 50:
        print(f"  ... +{len(entities) - 50} more")
    return 0


def cmd_log(args: list[str]) -> int:
    if len(args) < 2:
        print("usage: gtm-hub log <id> KEY=VALUE [KEY=VALUE ...]", file=sys.stderr)
        return 2
    entity_id = args[0]
    updates: dict[str, object] = {}
    for kv in args[1:]:
        if "=" not in kv:
            print(f"bad arg {kv!r} — expected KEY=VALUE", file=sys.stderr)
            return 2
        k, _, v = kv.partition("=")
        if v.lower() in ("null", "none", ""):
            updates[k] = None
        elif v.lstrip("-").isdigit():
            updates[k] = int(v)
        else:
            updates[k] = v
    entity = load_one(entity_id)
    if not entity:
        print(f"entity {entity_id!r} not found", file=sys.stderr)
        return 1
    updates.setdefault("last_touch", TODAY)
    text = Path(entity.path).read_text(encoding="utf-8")
    new_text = frontmatter.update_in_text(text, updates)
    Path(entity.path).write_text(new_text, encoding="utf-8")
    print(f"updated {entity.path}")
    print(f"  {updates}")
    return cmd_regenerate([])


def cmd_new(args: list[str]) -> int:
    p = argparse.ArgumentParser(prog="gtm-hub new")
    p.add_argument("type", choices=list(DIR_FOR_TYPE))
    p.add_argument("--id", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--status", default=None)
    p.add_argument("--owner", default="matt")
    ns = p.parse_args(args)
    dir_name = DIR_FOR_TYPE[ns.type]
    path = GROWTH_DIR / dir_name / f"{ns.id}.md"
    if path.exists():
        print(f"already exists: {path}", file=sys.stderr)
        return 1
    status = ns.status
    if status is None:
        # default to first allowed
        allowed = sorted(STATUS_VALUES.get(ns.type, set()))
        status = allowed[0] if allowed else "proposed"
    elif status not in STATUS_VALUES.get(ns.type, set()):
        print(
            f"status {status!r} not allowed for {ns.type} — valid: {sorted(STATUS_VALUES.get(ns.type, set()))}",
            file=sys.stderr,
        )
        return 2
    meta = {
        "id": ns.id,
        "type": ns.type,
        "title": ns.title,
        "status": status,
        "owner": ns.owner,
        "created": TODAY,
        "last_touch": TODAY,
    }
    body = f"\n# {ns.title}\n\n_(fill in)_\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frontmatter.render(meta) + body, encoding="utf-8")
    print(f"created {path}")
    return cmd_regenerate([])


def cmd_audit(_: list[str]) -> int:
    return _run(str(SCRIPTS / "audit.py"))


def cmd_doctor(_: list[str]) -> int:
    """End-to-end health check. Exit 0 green · 1 red · 2 amber."""
    return _run(str(SCRIPTS / "doctor.py"))


def cmd_post(args: list[str]) -> int:
    return _run(str(SCRIPTS / "post.py"), *args)


def cmd_migrate(args: list[str]) -> int:
    return _run(str(SCRIPTS / "migrate.py"), *args)


def cmd_act(args: list[str]) -> int:
    """Action verbs: qualify / kill / win / publish / engage / ship / close-won / close-lost / decide / defer.

    Run `gtm-hub act` with no args to see the full list.
    """
    return _run(str(SCRIPTS / "act.py"), *args)


def cmd_overview(_: list[str]) -> int:
    """One-shot comprehensive view: dashboard summary + decisions + projects + triage + debt.

    Designed for Slack — fits in a single message. Action-led structure:
      1. RED FLAGS (one-liner)
      2. OPEN DECISIONS (3 compact cards with action commands)
      3. PROJECTS (RAG table, active only)
      4. TRIAGE TOP-3 (this-week calls)
      5. DEBT TOP-3 (chronic state)
    """
    import datetime as dt

    today = dt.date.today()
    # Read from index.json directly — it has annotate_index() applied
    # (effective_rag, derived_blockers, blocks_projects all available).
    idx_path = META_DIR / "index.json"
    if idx_path.exists():
        entities = json.loads(idx_path.read_text(encoding="utf-8")).get("entities", [])
    else:
        entities = [_envelope(e) for e in load_all()]

    # --- Compute ---
    day = max(1, min(30, (today - dt.date(2026, 5, 5)).days + 1))
    metrics = [e for e in entities if e["type"] == "metric"]
    metrics_red = [m for m in metrics if m.get("status") == "not-instrumented"]
    open_decs = [
        e for e in entities
        if e["type"] == "decision" and e.get("status") in ("open", "deferred")
    ]
    urgent_decs = []
    for d in open_decs:
        try:
            dl = dt.date.fromisoformat(d.get("deadline") or "")
            if (dl - today).days <= 7:
                urgent_decs.append(d)
        except (ValueError, TypeError):
            pass
    projects = [e for e in entities if e["type"] == "project"]
    active_projects = [
        p for p in projects
        if p.get("status") not in ("shipped", "canceled", "paused")
    ]
    red_projects = [p for p in active_projects if (p.get("effective_rag") or "").lower() == "red"]

    # Load decisions.json for triage + debt
    dec_path = META_DIR / "decisions.json"
    rule_decisions = []
    backlog = []
    if dec_path.exists():
        payload = json.loads(dec_path.read_text(encoding="utf-8"))
        all_decs = payload.get("decisions", [])
        rule_decisions = [d for d in all_decs if d.get("kind") != "backlog" and d.get("rule") != "decision.open"]
        backlog = [d for d in all_decs if d.get("kind") == "backlog"]

    # --- Render ---
    print()
    print("═" * 72)
    print(f"  ⚡ GTM HUB — OVERVIEW ({today.isoformat()})")
    print("═" * 72)
    print()

    # Red flags one-liner
    flags = []
    if red_projects:
        flags.append(f"🔴 {len(red_projects)} project{'s' if len(red_projects) != 1 else ''} red")
    if urgent_decs:
        flags.append(f"⚠ {len(urgent_decs)} decision{'s' if len(urgent_decs) != 1 else ''} due ≤7d")
    if metrics_red:
        flags.append(f"📊 {len(metrics_red)} metrics not instrumented")
    if flags:
        print(f"  🚨 {'  ·  '.join(flags)}")
        print()
    print(f"  Phase 1 Day {day}/30 · {30 - day}d left")
    print()

    # Open decisions (compact)
    def _sort_key(e):
        try:
            dl = dt.date.fromisoformat(e.get("deadline") or "")
            return (0, (dl - today).days)
        except (ValueError, TypeError):
            return (1, 0)
    open_decs.sort(key=_sort_key)

    if open_decs:
        print(f"  🤔 OPEN DECISIONS — your plate ({len(open_decs)})")
        print(f"  {'─' * 68}")
        for i, e in enumerate(open_decs, 1):
            m = e
            title = m.get("title") or e.get("id")
            deadline_str = m.get("deadline") or ""
            urgency = ""
            if deadline_str:
                try:
                    dl = dt.date.fromisoformat(deadline_str)
                    delta = (dl - today).days
                    if delta < 0:
                        urgency = f"🔴 OVERDUE {-delta}d"
                    elif delta == 0:
                        urgency = "🔴 DUE TODAY"
                    elif delta <= 7:
                        urgency = f"🟠 due in {delta}d"
                    elif delta <= 21:
                        urgency = f"🟡 due in {delta}d"
                    else:
                        urgency = f"🟢 due in {delta}d"
                except ValueError:
                    pass
            else:
                urgency = "⚪ no deadline"
            opts = m.get("options") or []
            opt_keys = [o.get("key", "?") for o in opts if isinstance(o, dict)]
            opts_str = " | ".join(opt_keys) if opt_keys else "—"
            print(f"  {i}. {urgency}  {title}")
            print(f"     gtm decide {e.get('id')} [{opts_str}]")
        print()

    # Projects (RAG table, active only)
    if active_projects:
        def _proj_key(p):
            rag_order = {"red": 0, "amber": 1, "green": 2}
            rag = rag_order.get((p.get("effective_rag") or "").lower(), 3)
            td = p.get("target_date") or ""
            try:
                dl = dt.date.fromisoformat(td) if td else None
            except (ValueError, TypeError):
                dl = None
            return (rag, (dl - today).days if dl else 9999, p.get("id") or "")
        active_projects.sort(key=_proj_key)
        print(f"  📋 PROJECTS — in flight ({len(active_projects)})")
        print(f"  {'─' * 68}")
        for p in active_projects:
            rag = (p.get("effective_rag") or "").lower()
            icon = {"red": "🔴", "amber": "🟡", "green": "🟢"}.get(rag, "⚪")
            title = (p.get("title") or p.get("id") or "")[:50]
            target = p.get("target_date") or "—"
            blockers = p.get("derived_blockers") or []
            blockers_n = len(blockers) if isinstance(blockers, list) else 0
            blockers_str = f" · {blockers_n} 🚧" if blockers_n else ""
            print(f"  {icon} {title:<50}  target {target}{blockers_str}")
        print()

    # Triage top-3 (this-week calls — kind=decision rules)
    if rule_decisions:
        shown = min(3, len(rule_decisions))
        print(f"  ▶ TRIAGE — this-week calls ({shown} of {len(rule_decisions)})")
        print(f"  {'─' * 68}")
        for d in rule_decisions[:3]:
            print(f"  · {d.get('message', '?')}")
        if len(rule_decisions) > 3:
            print(f"    _+{len(rule_decisions) - 3} more in `gtm decisions`_")
        print()

    # Debt top-3 (chronic state)
    if backlog:
        # Diversify by rule for the top-3
        seen = set()
        compact = []
        for d in backlog:
            if d.get("rule") in seen:
                continue
            seen.add(d.get("rule"))
            compact.append(d)
            if len(compact) >= 3:
                break
        shown = min(3, len(backlog), len(compact))
        print(f"  📚 MEASUREMENT DEBT ({shown} of {len(backlog)})")
        print(f"  {'─' * 68}")
        for d in compact:
            print(f"  · {d.get('message', '?')}")
        rolled = len(backlog) - len(compact)
        if rolled > 0:
            print(f"    _+{rolled} more chronic items_")
        print()

    print("═" * 72)
    print("  Drill in:  gtm decisions · gtm projects · gtm dashboard · gtm status <type>")
    print()
    return 0


def cmd_dashboard(_: list[str]) -> int:
    """Terminal-rendered top-level dashboard: phase progress, NSMs, pipeline counts, red flags."""
    import datetime as dt
    from lib.schema import parse_date as _pd
    entities = [_envelope(e) for e in load_all()]
    today = dt.date.today()

    day = (today - dt.date(2026, 5, 5)).days + 1
    day = max(1, min(30, day))
    days_left = max(0, 30 - day)

    def _count(t, status_set=None):
        out = [e for e in entities if e["type"] == t]
        if status_set:
            out = [e for e in out if e.get("status") in status_set]
        return len(out)

    bar_w = 20
    pct = day / 30
    bar = "▓" * int(pct * bar_w) + "░" * (bar_w - int(pct * bar_w))

    metrics = [e for e in entities if e["type"] == "metric"]
    metrics_red = [m for m in metrics if m.get("status") == "not-instrumented"]
    open_decs = [e for e in entities if e["type"] == "decision" and e.get("status") in ("open", "deferred")]
    urgent_decs = []
    for d in open_decs:
        dl = _pd(d.get("deadline"))
        if dl and (dl - today).days <= 7:
            urgent_decs.append(d)
    projects = [e for e in entities if e["type"] == "project"]
    projects_blocked = [p for p in projects if p.get("status") == "blocked"]

    print()
    print("═" * 72)
    print(f"  ⚡ GTM HUB — DASHBOARD ({today.isoformat()})")
    print("═" * 72)
    print()
    print(f"  Phase 1 — Growth Program            {bar}  Day {day}/30 · {days_left}d left")
    print()
    print("  NORTH-STAR METRICS")
    for slug in ("wapw", "qpv"):
        m = next((mm for mm in metrics if mm["id"] == slug), None)
        if not m:
            continue
        title = (m.get("title") or slug.upper())[:48]
        val = m.get("value")
        if val in (None, ""):
            print(f"    {title:<48} ░░░░░░░░░░  NOT INSTRUMENTED")
        else:
            print(f"    {title:<48} {val} / target {m.get('target', '—')}")
    print()
    print("  PIPELINE COUNTS                          ACTIVE       TOTAL")
    print(f"    🤔 Open decisions                       {len(open_decs):<4}         {len(open_decs):<4}" + (f"  · ⚠ {len(urgent_decs)} urgent" if urgent_decs else ""))
    print(f"    📋 Projects                             {len(projects)-len([p for p in projects if p.get('status') in ('shipped','canceled','paused')]):<4}         {len(projects):<4}" + (f"  · 🔴 {len(projects_blocked)} blocked" if projects_blocked else ""))
    print(f"    🧪 Experiments running                  {_count('experiment', {'running'}):<4}         {_count('experiment'):<4}")
    print(f"    📝 Content active                       {_count('content', {'drafted','reviewed','scheduled'}):<4}         {_count('content'):<4}")
    print(f"    🤝 BD active                            {_count('bd_target', {'outreach','engaged'}):<4}         {_count('bd_target'):<4}")
    print(f"    💼 Solutions qualified+                 {_count('prospect', {'qualified','scoped','proposal-out','won'}):<4}         {_count('prospect'):<4}")
    print(f"    🚀 Launches active                      {_count('launch', {'drafting','ready','scheduled'}):<4}         {_count('launch'):<4}")
    print(f"    📊 Metrics instrumented                 {len(metrics)-len(metrics_red):<4}         {len(metrics):<4}" + (f"  · 🔴 {len(metrics_red)} red" if metrics_red else ""))
    print()

    flags = []
    if metrics_red:
        flags.append(f"{len(metrics_red)} metrics not instrumented")
    if urgent_decs:
        flags.append(f"{len(urgent_decs)} decision{'s' if len(urgent_decs) != 1 else ''} due in ≤7d")
    if projects_blocked:
        flags.append(f"{len(projects_blocked)} project{'s' if len(projects_blocked) != 1 else ''} blocked")
    if flags:
        print(f"  🚨 RED FLAGS:  {'  ·  '.join(flags)}")
        print()
    print("═" * 72)
    print(f"  Next: gtm decisions · gtm projects · gtm status <type>")
    print()
    return 0


def _envelope(e):
    from lib.schema import envelope_view
    return envelope_view(e)


def cmd_projects(_: list[str]) -> int:
    """Terminal project tracker — table + per-project blocker detail."""
    import datetime as dt
    today = dt.date.today()
    projects = [_envelope(e) for e in load_all() if e.type == "project"]
    if not projects:
        print("(no projects defined)")
        return 0

    def _key(p):
        rag_order = {"red": 0, "amber": 1, "green": 2, None: 3}
        rag = rag_order.get(p.get("rag"))
        if p.get("status") == "blocked":
            rag = 0
        td = p.get("target_date") or ""
        try:
            dl = dt.date.fromisoformat(td) if td else None
        except (ValueError, TypeError):
            dl = None
        deadline_sort = (dl - today).days if dl else 9999
        return (rag, deadline_sort, p.get("id") or "")
    projects.sort(key=_key)

    active = [p for p in projects if p.get("status") not in ("shipped", "canceled", "paused")]
    print()
    print("═" * 80)
    print(f"  📋 PROJECTS — IN FLIGHT ({len(active)} active)")
    print("═" * 80)
    print()
    print(f"  {'RAG':<4}{'Project':<48}{'Target':<12}{'Progress':<10}{'Blockers'}")
    print(f"  {'-'*4}{'-'*48}{'-'*12}{'-'*10}{'-'*10}")
    for p in active:
        rag = p.get("rag") or ""
        if p.get("status") == "blocked":
            icon = "🔴"
        else:
            icon = {"red": "🔴", "amber": "🟡", "green": "🟢"}.get(rag, "⚪")
        title = (p.get("title") or p.get("id") or "")[:46]
        target = p.get("target_date") or "—"
        prog = p.get("progress_pct")
        prog_str = f"{prog}%" if prog is not None else "—"
        blockers = p.get("blockers") or []
        blockers_n = len(blockers) if isinstance(blockers, list) else 0
        blockers_str = f"{blockers_n} 🚧" if blockers_n else "—"
        print(f"  {icon}  {title:<46}{target:<12}{prog_str:<10}{blockers_str}")
    print()

    # Detail for red/blocked projects
    flagged = [p for p in active if p.get("rag") == "red" or p.get("status") == "blocked"]
    if flagged:
        print(f"  PROJECTS NEEDING ATTENTION:")
        print()
        for p in flagged[:5]:
            title = p.get("title") or p["id"]
            status = p.get("status")
            target = p.get("target_date") or "no deadline"
            print(f"  🔴 {title}  ({status} · target {target})")
            summary = p.get("status_summary")
            if summary:
                for s_line in str(summary).strip().splitlines():
                    print(f"     {s_line}")
            blockers = p.get("blockers") or []
            if blockers:
                print(f"     Blockers:")
                for b in blockers:
                    print(f"       🚧 {b}")
            print()
    print("═" * 80)
    return 0


def cmd_decide(args: list[str]) -> int:
    """Shorthand for `gtm-hub act decide <id> <option-key>`."""
    return _run(str(SCRIPTS / "act.py"), "decide", *args)


def cmd_defer(args: list[str]) -> int:
    """Shorthand for `gtm-hub act defer <id>`."""
    return _run(str(SCRIPTS / "act.py"), "defer", *args)


def cmd_web(args: list[str]) -> int:
    """Build the web-view bundle (HTML + JSON data) for static-hosting upload."""
    return _run(str(SKILL_DIR / "web" / "build.py"), *args) if False else _run(
        str(THIS_DIR / "web" / "build.py"), *args
    )


def cmd_zergboard(args: list[str]) -> int:
    """Zergboard sync.

    Subcommands:
        sync [--dry-run]                          pull cards + auto-link entities
        create <entity-id> [--board NAME] [--dry-run]
                                                  create one card for an entity
        create-missing --type TYPE [--status S,S] [--board NAME] [--dry-run]
                                                  bulk-create cards for unlinked entities
    """
    if not args or args[0] in ("help", "-h", "--help"):
        print(cmd_zergboard.__doc__)
        return 0
    sub = args[0]
    if sub == "sync":
        return _run(str(SCRIPTS / "sync_zergboard.py"), *args[1:])
    if sub == "create":
        return _run(str(SCRIPTS / "create_zergboard_card.py"), *args[1:])
    if sub == "create-missing":
        return _run(str(SCRIPTS / "create_zergboard_card.py"), "--missing", *args[1:])
    print(f"unknown zergboard subcommand: {sub}", file=sys.stderr)
    return 2


COMMANDS = {
    "regenerate": cmd_regenerate,
    "regen-ledgers": cmd_regen_ledgers,
    "decisions": cmd_decisions,
    "dashboard": cmd_dashboard,
    "projects": cmd_projects,
    "overview": cmd_overview,
    "status": cmd_status,
    "log": cmd_log,
    "new": cmd_new,
    "act": cmd_act,
    "decide": cmd_decide,
    "defer": cmd_defer,
    "audit": cmd_audit,
    "doctor": cmd_doctor,
    "post": cmd_post,
    "migrate": cmd_migrate,
    "zergboard": cmd_zergboard,
    "web": cmd_web,
}


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd = argv[1]
    if cmd not in COMMANDS:
        print(f"unknown command: {cmd}\n", file=sys.stderr)
        print(__doc__)
        return 2
    return COMMANDS[cmd](argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
