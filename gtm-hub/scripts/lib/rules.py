"""Decision rules. Pure functions over the flat index."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

from .schema import parse_date


@dataclass
class Decision:
    rule: str
    priority: int  # higher = more urgent
    entity_id: str
    entity_type: str
    entity_path: str
    message: str
    # "decision" = a this-week call you need to make.
    # "backlog"  = known cleanup/measurement debt — surface separately so it
    #              doesn't crowd out actionable decisions.
    kind: str = "decision"

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "priority": self.priority,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "entity_path": self.entity_path,
            "message": self.message,
            "kind": self.kind,
        }


def _days_between(a: dt.date, b: dt.date) -> int:
    return (a - b).days


def derive(
    index: list[dict[str, Any]],
    today: dt.date | None = None,
    system_rules: bool = True,
) -> list[Decision]:
    today = today or dt.date.today()
    out: list[Decision] = []

    for row in index:
        etype = row.get("type")
        eid = row.get("id") or ""
        path = row.get("path") or ""
        title = row.get("title") or eid
        status = row.get("status")
        last_touch = parse_date(row.get("last_touch"))

        if etype == "experiment":
            kd = parse_date(row.get("kill_date"))
            if kd and status == "running":
                delta = _days_between(kd, today)
                if delta < 0:
                    out.append(
                        Decision(
                            rule="experiment.kill_overdue",
                            priority=100 + min(30, -delta),
                            entity_id=eid,
                            entity_type=etype,
                            entity_path=path,
                            message=f"OVERDUE conclude {eid} — {title} (kill {kd.isoformat()}, +{-delta}d past)",
                        )
                    )
                elif delta <= 7:
                    out.append(
                        Decision(
                            rule="experiment.kill_approaching",
                            priority=80 - delta,
                            entity_id=eid,
                            entity_type=etype,
                            entity_path=path,
                            message=f"Decide by {kd.isoformat()}: kill / scale / extend — {eid} {title}",
                        )
                    )

        if etype == "bd_target":
            if last_touch and status in ("outreach", "engaged"):
                delta = _days_between(today, last_touch)
                if delta > 14:
                    out.append(
                        Decision(
                            rule="bd.stale_touch",
                            priority=40 + min(40, delta // 7),
                            entity_id=eid,
                            entity_type=etype,
                            entity_path=path,
                            message=f"Re-touch {title} (last contact {last_touch.isoformat()}, +{delta}d)",
                        )
                    )

        if etype == "prospect":
            # Qualified prospect with no proposal out — real obligation, real urgency
            if status == "qualified" and not parse_date(row.get("proposal_out_at")):
                out.append(
                    Decision(
                        rule="prospect.proposal_due",
                        priority=85,
                        entity_id=eid,
                        entity_type=etype,
                        entity_path=path,
                        message=f"Send proposal: {row.get('company') or title}",
                    )
                )
            # High-fit inbound — soft signal, no hard deadline. Down-weighted per
            # Matt feedback 2026-05-11: draft outbound campaigns shouldn't outrank
            # hard-deadline items. Surface as informational, not urgent.
            if status == "inbound":
                score = row.get("score")
                try:
                    score_n = int(score) if score is not None else None
                except (ValueError, TypeError):
                    score_n = None
                if score_n is not None and score_n >= 90:
                    # Soft-signal informational — not a this-week decision.
                    # Tagged backlog so the triage panel stays action-focused.
                    out.append(
                        Decision(
                            rule="prospect.high_score_inbound",
                            priority=25 + min(5, (score_n - 90)),
                            entity_id=eid,
                            entity_type=etype,
                            entity_path=path,
                            message=f"Consider qualifying: {row.get('company') or title} (score {score_n}/100)",
                            kind="backlog",
                        )
                    )
            # Old inbound deserves a triage nudge after 21d (lifted from 14d)
            if status == "inbound" and last_touch:
                delta = _days_between(today, last_touch)
                if delta > 21:
                    # Chronic state, not a this-week call
                    out.append(
                        Decision(
                            rule="prospect.inbound_stale",
                            priority=35 + min(20, delta // 7),
                            entity_id=eid,
                            entity_type=etype,
                            entity_path=path,
                            message=f"Inbound idle {delta}d: {row.get('company') or title}",
                            kind="backlog",
                        )
                    )

        if etype == "content":
            # Imagery gap: drafted content without imagery artifact
            artifacts = row.get("artifacts")
            kind = row.get("kind")
            # We don't carry artifacts in the index envelope, so this rule is best-effort:
            # only fires if we can detect it from envelope hints.
            if status == "drafted" and row.get("kind") not in ("pseo", "newsletter"):
                # Heuristic: drafted blog/launch should have imagery within 7 days of target
                target = parse_date(row.get("target_date"))
                if target and (target - today).days <= 7:
                    out.append(
                        Decision(
                            rule="content.imagery_gap",
                            priority=58,
                            entity_id=eid,
                            entity_type=etype,
                            entity_path=path,
                            message=f"Imagery check before {target.isoformat()}: {title}",
                        )
                    )

            if status == "reviewed":
                sched = parse_date(row.get("scheduled_date"))
                if not sched or sched < today:
                    out.append(
                        Decision(
                            rule="content.schedule_or_publish",
                            priority=55,
                            entity_id=eid,
                            entity_type=etype,
                            entity_path=path,
                            message=f"Schedule/publish: {title}",
                        )
                    )
            # Near-term content target: hard deadline → higher priority than soft signals
            target = parse_date(row.get("target_date"))
            if target and status not in ("published", "distributed", "parked"):
                delta = _days_between(target, today)
                if -3 <= delta <= 14:
                    if delta < 0:
                        msg = f"Content past target ({-delta}d): {title}"
                        prio = 95 + min(5, -delta)  # past-due is highest urgency
                    elif delta <= 1:
                        msg = f"Content target {'today' if delta == 0 else 'tomorrow'}: {title} (status={status})"
                        prio = 90
                    elif delta <= 3:
                        msg = f"Content target in {delta}d: {title} (status={status})"
                        prio = 80 - delta
                    else:
                        msg = f"Content target in {delta}d: {title} (status={status})"
                        prio = 70 - delta
                    out.append(
                        Decision(
                            rule="content.target_near",
                            priority=prio,
                            entity_id=eid,
                            entity_type=etype,
                            entity_path=path,
                            message=msg,
                        )
                    )

        if etype == "launch":
            if status == "ready" and not parse_date(row.get("ship_date")):
                out.append(
                    Decision(
                        rule="launch.ship_date_missing",
                        priority=75,
                        entity_id=eid,
                        entity_type=etype,
                        entity_path=path,
                        message=f"Ship date for {title}?",
                    )
                )
            # Launch with ship_date in next 14d, not yet shipped
            ship = parse_date(row.get("ship_date"))
            if ship and status not in ("shipped", "parked"):
                delta = _days_between(ship, today)
                if -3 <= delta <= 14:
                    if delta < 0:
                        msg = f"Launch past ship date ({-delta}d): {title}"
                        prio = 90 + min(10, -delta)
                    else:
                        msg = f"Launch in {delta}d: {title} (status={status})"
                        prio = 75 - (delta // 2)
                    out.append(
                        Decision(
                            rule="launch.ship_near",
                            priority=prio,
                            entity_id=eid,
                            entity_type=etype,
                            entity_path=path,
                            message=msg,
                        )
                    )

        if etype == "metric":
            if row.get("value") in (None, "") and row.get("instrumentation_owner") == "matt":
                # Measurement debt — known epic, not a this-week decision.
                # Tagged backlog so the decisions panel doesn't bury actionable
                # calls under N "instrument metric X" rows.
                out.append(
                    Decision(
                        rule="metric.not_instrumented",
                        priority=50,
                        entity_id=eid,
                        entity_type=etype,
                        entity_path=path,
                        message=f"Instrument {title}",
                        kind="backlog",
                    )
                )

        if etype == "workstream":
            la = parse_date(row.get("last_activity"))
            if la and status == "hot":
                delta = _days_between(today, la)
                if delta > 14:
                    # Chronic state — hygiene, not a this-week call
                    out.append(
                        Decision(
                            rule="workstream.stale_hot",
                            priority=35,
                            entity_id=eid,
                            entity_type=etype,
                            entity_path=path,
                            message=f"Resume or demote workstream: {title} (idle {delta}d)",
                            kind="backlog",
                        )
                    )

        if etype == "decision" and status == "open":
            deadline = parse_date(row.get("deadline"))
            unblocks = row.get("unblocks") or []
            unblocks_n = len(unblocks) if isinstance(unblocks, list) else 0
            blocks_projects = row.get("blocks_projects") or []
            blocks_n = len(blocks_projects) if isinstance(blocks_projects, list) else 0
            # Lift priority when this decision blocks N projects — downstream impact
            project_bump = min(15, blocks_n * 5)
            if deadline:
                delta = _days_between(deadline, today)
                if delta < 0:
                    prio = 100 + min(10, -delta) + project_bump
                    msg = f"OVERDUE decision ({-delta}d past): {title}"
                elif delta == 0:
                    prio = 99 + project_bump
                    msg = f"DECIDE TODAY: {title}"
                elif delta <= 7:
                    prio = 95 - delta + project_bump
                    msg = f"Decide by {deadline.isoformat()} ({delta}d): {title}"
                elif delta <= 21:
                    prio = 80 - delta + project_bump
                    msg = f"Decision pending — {delta}d to {deadline.isoformat()}: {title}"
                else:
                    prio = 50 + project_bump
                    msg = f"Decision open — {delta}d to {deadline.isoformat()}: {title}"
            else:
                last_touch_date = parse_date(row.get("last_touch"))
                idle = _days_between(today, last_touch_date) if last_touch_date else 0
                prio = 40 + min(20, unblocks_n * 5) + min(10, idle // 7) + project_bump
                msg = f"Decision open: {title}" + (
                    f" (blocks {blocks_n} project{'s' if blocks_n != 1 else ''})" if blocks_n
                    else (f" (unblocks {unblocks_n})" if unblocks_n else "")
                )
            out.append(
                Decision(
                    rule="decision.open",
                    priority=prio,
                    entity_id=eid,
                    entity_type=etype,
                    entity_path=path,
                    message=msg,
                )
            )

    # System-level rules (not per-entity). Disabled in unit tests with fixtures
    # too small to be meaningful.
    if system_rules:
        out.extend(_system_rules(index, today))

    out.sort(key=lambda d: (-d.priority, d.entity_id))
    return out


def _system_rules(index: list[dict[str, Any]], today: dt.date) -> list[Decision]:
    """Rules that depend on aggregate state, not a single entity."""
    out: list[Decision] = []

    # 1. Experiment kill floor — < 2 running is a red signal per growth program
    running = [r for r in index if r.get("type") == "experiment" and r.get("status") == "running"]
    if len(running) < 2:
        out.append(
            Decision(
                rule="system.experiment_kill_floor",
                priority=85,
                entity_id="system",
                entity_type="system",
                entity_path="",
                message=f"Only {len(running)} experiment(s) running — floor is 2. Pull from RICE backlog.",
            )
        )

    # 2. Hot workstream overload — >5 hot = focus gap
    hot = [r for r in index if r.get("type") == "workstream" and r.get("status") == "hot"]
    if len(hot) > 5:
        out.append(
            Decision(
                rule="system.workstream_overload",
                priority=45,
                entity_id="system",
                entity_type="system",
                entity_path="",
                message=f"{len(hot)} hot workstreams — focus gap. Demote some to warm.",
                kind="backlog",
            )
        )

    # 3. No qualified prospects yet (Phase 1 day-by-day forcing function)
    qualified = [r for r in index if r.get("type") == "prospect" and r.get("status") == "qualified"]
    inbound = [r for r in index if r.get("type") == "prospect" and r.get("status") == "inbound"]
    if not qualified and len(inbound) >= 10:
        out.append(
            Decision(
                rule="system.qualification_drought",
                priority=60,
                entity_id="system",
                entity_type="system",
                entity_path="",
                message=f"{len(inbound)} inbound prospects, 0 qualified. Run qualification triage this week.",
                kind="backlog",
            )
        )

    return out


def diversify(decisions: list[dict], limit: int = 5, n_names: int = 3) -> list[tuple[dict, int, list[str]]]:
    """Return (decision, sibling_count, top_sibling_names) triples.

    Keeps the highest-priority decision per rule, capping the visible list at
    `limit`. Sibling count = other entities sharing the same rule.
    `top_sibling_names` = up to `n_names` other entity_ids that fired the same
    rule, so the renderer can show "+5 more: Clay, Decagon, Factory" instead of
    a context-free "+5 more like this".

    Implements `feedback_dashboard_must_drive_action.md` — "lead one action,
    diversify by category, ≤5 visible".
    """
    by_rule: dict[str, list[dict]] = {}
    for d in decisions:
        by_rule.setdefault(d["rule"], []).append(d)
    seen: set[str] = set()
    out: list[tuple[dict, int, list[str]]] = []
    for d in decisions:
        if d["rule"] in seen:
            continue
        seen.add(d["rule"])
        rule_decs = by_rule[d["rule"]]
        siblings = len(rule_decs) - 1
        # rule_decs[0] is the visible decision (first-seen-per-rule, matches `d`
        # by both identity and position). Index past it to get siblings; this
        # stays consistent with the `siblings` count even if upstream ever
        # produces duplicate dict instances.
        # Fallback "?" surfaces a missing entity_id visibly in render rather
        # than silently dropping the sibling row — upstream invariant says
        # entity_id should always be present, so a "?" in the render output
        # is a data-quality flag, not normal.
        other_names = [s.get("entity_id") or "?" for s in rule_decs[1:n_names + 1]]
        out.append((d, siblings, other_names))
        if len(out) >= limit:
            break
    return out
