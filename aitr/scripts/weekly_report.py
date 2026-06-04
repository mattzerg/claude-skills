#!/usr/bin/env python3
"""aitr weekly tuning report.

Reads the decisions log + wrong-model-picked corrections and renders a report:
  - pick distribution by task_kind and caller
  - estimated cost spend by model
  - corrections filed this window + the penalties currently active
  - tuning suggestions (frontmatter drift, dominant fallbacks, missing data)

Usage:
    python3 weekly_report.py [--days 7] [--dry-run] [--post]

--dry-run prints to stdout only (default behavior is also stdout; --post fires
to Fake Matt -> Matt DM via the same path llm-feedback digest uses).

Designed to run Fridays via launchd (com.matteisn.aitr-tuning.plist).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL_DIR))

from penalties import (  # noqa: E402
    DEFAULT_DECISIONS_LOG,
    DEFAULT_FEEDBACK_MIRROR_DIRS,
    load_decisions,
    load_penalties,
    load_wrong_model_feedback,
)


def _baseline_pricing(catalog_body: dict | None, baseline_id: str) -> dict | None:
    """Pricing record for the baseline model, or None when unavailable."""
    if not catalog_body:
        return None
    record = next(
        (m for m in (catalog_body.get("models") or []) if m.get("id") == baseline_id),
        None,
    )
    return (record or {}).get("pricing") or None


def _cost_at_current_pricing(catalog_body: dict | None, model_id: str, artifact: int) -> float | None:
    """Estimated cost of `artifact` input tokens (+2000 output) on `model_id` at the
    catalog's CURRENT pricing. None when the model/pricing isn't in the catalog."""
    pricing = _baseline_pricing(catalog_body, model_id)
    if not pricing:
        return None
    in_rate = float(pricing.get("input_per_mtok") or 0.0)
    out_rate = float(pricing.get("output_per_mtok") or 0.0)
    return (artifact * in_rate + 2000 * out_rate) / 1_000_000.0


def compute_savings(
    decisions: list[dict],
    *,
    catalog_body: dict | None = None,
    baseline_id: str = "anthropic__claude-opus-4-8",
) -> dict:
    """Aggregate savings vs the no-router baseline.

    Decisions logged after 2026-06-03 carry native baseline_cost_usd/savings_usd
    fields and are summed as recorded. Older (legacy) records pre-date both the
    baseline fields AND the corrected catalog pricing, so BOTH sides are recomputed
    from current pricing: "at today's prices, what would the routed model mix have
    cost vs running everything on the baseline?" A legacy pick of the baseline model
    itself therefore counts as exactly $0 savings (same model, same price).
    """
    native_savings = 0.0
    native_count = 0
    retro_savings = 0.0
    retro_count = 0
    total_spend = 0.0
    baseline_spend = 0.0
    uncounted = 0

    # Billing-mode split: dollar savings are only REAL for metered (per-token API)
    # callers. flat (Max-plan OAuth) callers cost $0 marginal regardless of model —
    # their "savings" is rate-limit/latency headroom, reported separately so it's
    # never double-counted as real dollars. unknown = pre-billing-mode legacy.
    metered_savings = 0.0
    metered_count = 0
    flat_count = 0
    unknown_count = 0

    for d in decisions:
        if d.get("verb") == "delegate":
            continue

        signal = d.get("signal") or {}
        billing = signal.get("billing_mode", "unknown")

        if "savings_usd" in d:
            actual = float(d.get("estimated_cost_usd") or 0.0)
            sav = float(d.get("savings_usd") or 0.0)
            total_spend += actual
            native_savings += sav
            baseline_spend += float(d.get("baseline_cost_usd") or 0.0)
            native_count += 1
        else:
            # Legacy record: recompute both sides at current catalog pricing
            artifact = int(signal.get("artifact_size_tokens") or 4000)
            baseline_cost = _cost_at_current_pricing(catalog_body, baseline_id, artifact)
            if baseline_cost is None:
                uncounted += 1
                continue
            actual_cost = _cost_at_current_pricing(catalog_body, d.get("model", ""), artifact)
            if actual_cost is None:
                actual_cost = float(d.get("estimated_cost_usd") or 0.0)
            sav = baseline_cost - actual_cost
            total_spend += actual_cost
            baseline_spend += baseline_cost
            retro_savings += sav
            retro_count += 1

        if billing == "metered":
            metered_savings += sav
            metered_count += 1
        elif billing == "flat":
            flat_count += 1
        else:
            unknown_count += 1

    return {
        "baseline_model": baseline_id,
        "total_spend_usd": total_spend,
        "baseline_spend_usd": baseline_spend,
        "total_savings_usd": native_savings + retro_savings,
        "native_count": native_count,
        "retro_count": retro_count,
        "uncounted": uncounted,
        # Billing-mode breakdown — only metered_savings is real dollars
        "metered_savings_usd": metered_savings,
        "metered_count": metered_count,
        "flat_count": flat_count,
        "unknown_count": unknown_count,
    }


def _parse_ts(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        return None


def build_report(
    *,
    decisions_log: Path = DEFAULT_DECISIONS_LOG,
    feedback_dirs: list[Path] | None = None,
    days: int = 7,
    now: datetime | None = None,
) -> str:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    feedback_dirs = feedback_dirs or DEFAULT_FEEDBACK_MIRROR_DIRS

    all_decisions = load_decisions(decisions_log)
    window_decisions = [
        d for d in all_decisions.values()
        if (_parse_ts(d.get("ts", "")) or cutoff) >= cutoff
    ]

    lines = [
        f"# aitr weekly tuning report — {now.date().isoformat()}",
        "",
        f"Window: last {days} days · {len(window_decisions)} picks · {len(all_decisions)} all-time",
        "",
    ]

    if not window_decisions:
        lines += [
            "**No routing decisions in this window.**",
            "",
            "Either nothing invoked aitr this week, or callers are bypassing it. "
            "Check that pr-gate / fakematt-* / agents are wired (grep for `aitr` in their runbooks).",
        ]
        return "\n".join(lines)

    # --- Pick distribution -------------------------------------------------
    by_task: Counter = Counter()
    by_caller: Counter = Counter()
    by_model: Counter = Counter()
    cost_by_model: defaultdict = defaultdict(float)
    delegations = 0

    for d in window_decisions:
        signal = d.get("signal") or {}
        task_kind = signal.get("task_kind", "?")
        caller = d.get("caller") or signal.get("caller") or "?"
        by_task[task_kind] += 1
        by_caller[caller] += 1
        if d.get("verb") == "delegate":
            delegations += 1
            continue
        model = d.get("model", "?")
        by_model[model] += 1
        cost_by_model[model] += float(d.get("estimated_cost_usd") or 0.0)

    lines += ["## Pick distribution", ""]
    lines += ["**By task kind:**", ""]
    for task_kind, count in by_task.most_common():
        lines.append(f"- {task_kind}: {count}")
    lines += ["", "**By caller:**", ""]
    for caller, count in by_caller.most_common():
        lines.append(f"- {caller}: {count}")
    lines += ["", "**By model:**", ""]
    for model, count in by_model.most_common():
        est = cost_by_model[model]
        lines.append(f"- {model}: {count} picks (~${est:.2f} estimated input+output)")
    if delegations:
        lines.append(f"- (delegated out: {delegations})")

    # --- Savings vs baseline -------------------------------------------------
    try:
        from catalog import load_catalog  # noqa: PLC0415 — local import keeps report usable offline
        catalog_body = load_catalog(offline=True).body
    except Exception:
        catalog_body = None
    try:
        from pick import resolve_baseline_model  # noqa: PLC0415
        baseline_id = resolve_baseline_model()
    except Exception:
        baseline_id = "anthropic__claude-opus-4-8"

    savings = compute_savings(window_decisions, catalog_body=catalog_body, baseline_id=baseline_id)
    lines += ["", "## Savings vs baseline", ""]
    lines += [
        f"Baseline (no-router default): `{savings['baseline_model']}`",
        "",
        f"- **Real dollar savings (metered callers only): ${savings['metered_savings_usd']:.2f}** "
        f"across {savings['metered_count']} per-token API picks",
    ]
    # Flat / unknown callers: model choice has $0 marginal cost on Max-plan OAuth,
    # so their "savings" is rate-limit/latency headroom, not dollars. Reported but
    # never summed into the dollar figure.
    if savings["flat_count"]:
        lines.append(
            f"- {savings['flat_count']} flat (Max-plan OAuth) picks — $0 marginal cost; "
            f"routing here buys rate-limit + latency headroom, not dollars"
        )
    if savings["unknown_count"]:
        lines.append(
            f"- {savings['unknown_count']} picks pre-date billing-mode tagging "
            f"(counted as headroom, not dollars)"
        )
    lines += [
        "",
        "_Reference (all callers, assuming hypothetical metered billing):_ "
        f"routed ${savings['total_spend_usd']:.2f} vs ${savings['baseline_spend_usd']:.2f} on baseline "
        f"= ${savings['total_savings_usd']:.2f} notional.",
    ]
    if savings["retro_count"]:
        lines.append(
            f"_({savings['retro_count']} legacy picks estimated retroactively; "
            f"{savings['native_count']} carry native savings fields.)_"
        )

    # --- Corrections + active penalties ------------------------------------
    feedback = load_wrong_model_feedback(feedback_dirs)
    window_feedback = [
        f for f in feedback
        if (_parse_ts(f.get("when", "")) or cutoff) >= cutoff
    ]
    penalties = load_penalties(decisions_log=decisions_log, feedback_dirs=feedback_dirs, now=now)

    lines += ["", "## Corrections (wrong-model-picked)", ""]
    if window_feedback:
        for f in window_feedback:
            did = f.get("aitr_decision_id") or "no-decision-id"
            lines.append(f"- {f.get('when', '?')[:10]} [{did}]: {f.get('feedback', '')[:120]}")
    else:
        lines.append("- none filed this window")

    lines += ["", "**Active penalties:**", ""]
    if penalties:
        for (caller, task_kind, model), value in sorted(penalties.items(), key=lambda kv: kv[1]):
            lines.append(f"- {caller} / {task_kind} / {model}: {value:.2f}")
    else:
        lines.append("- none")

    # --- Tuning suggestions --------------------------------------------------
    lines += ["", "## Tuning suggestions", ""]
    suggestions: list[str] = []

    # Suggestion: catalog source health
    snapshot_picks = sum(1 for d in window_decisions if d.get("catalog_source") == "snapshot")
    if snapshot_picks > len(window_decisions) * 0.5:
        suggestions.append(
            f"{snapshot_picks}/{len(window_decisions)} picks served from the BUNDLED SNAPSHOT — "
            "the live tracker (TRACKER_ORIGIN) is unreachable or aitr.toml is unconfigured. Fix the data backend."
        )

    # Suggestion: single-model dominance
    if by_model:
        top_model, top_count = by_model.most_common(1)[0]
        if top_count >= len(window_decisions) * 0.9 and len(by_model) > 1:
            suggestions.append(
                f"{top_model} won {top_count}/{len(window_decisions)} picks — routing is barely differentiating. "
                "Review routing_table.json weights or task_kind tags."
            )

    # Suggestion: repeated corrections on same caller+task
    correction_keys = Counter(
        (p[0], p[1]) for p in penalties.keys()
    )
    for (caller, task_kind), count in correction_keys.items():
        if count >= 2:
            suggestions.append(
                f"{caller}/{task_kind} has corrections against {count} different models — "
                "the routing rule for this task_kind likely needs a tag or floor change, not just penalties."
            )

    if suggestions:
        for s in suggestions:
            lines.append(f"- {s}")
    else:
        lines.append("- no drift detected")

    return "\n".join(lines)


def post_to_fakematt(report: str) -> bool:
    """Best-effort post via the same path llm-feedback digest uses. Returns success."""
    send_dm = Path.home() / ".claude" / "skills" / "slack-skill" / "scripts" / "send_dm.py"
    if not send_dm.exists():
        print("aitr: slack send_dm.py not found — printing only", file=sys.stderr)
        return False
    try:
        proc = subprocess.run(
            ["python3", str(send_dm), "--channel", "fakematt-self", "--text", report],
            capture_output=True, text=True, timeout=60,
        )
        return proc.returncode == 0
    except (subprocess.TimeoutExpired, OSError) as exc:
        print(f"aitr: post failed ({exc})", file=sys.stderr)
        return False


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="aitr weekly tuning report")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--dry-run", action="store_true", help="print only (default behavior)")
    p.add_argument("--post", action="store_true", help="post to Fake Matt -> Matt DM")
    args = p.parse_args(argv)

    report = build_report(days=args.days)
    print(report)

    if args.post and not args.dry_run:
        ok = post_to_fakematt(report)
        print(f"\n[aitr] posted: {ok}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
