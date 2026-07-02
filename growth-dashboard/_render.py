"""Rendering helpers extracted from run.py for line-budget reasons."""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path


PENDING_MARKERS = ("_(no data —", "(no data —", "_(populate", "_(Phase ", "_(Matt fills",
                   "no prospects.md", "no Case-Studies dir", "no measurement specs", "no funnel data",
                   "no signup", "no drip-state", "no zerglytics_domain")
AT_RISK_MARKERS = ("REGRESSION", "📉", "🔴", "⚠", "flag RED")
HEALTHY_MARKERS = ("✅", "(OK)")


def classify(text: str) -> str:
    if any(m in text for m in PENDING_MARKERS):
        return "pending"
    if any(m in text for m in AT_RISK_MARKERS):
        return "at_risk"
    if any(m in text for m in HEALTHY_MARKERS):
        return "healthy"
    return "info"


def strip_numbering(text: str) -> str:
    return re.sub(r"^\d+\.\s*\*\*", "**", text)


def label_and_body(text: str) -> tuple[str, str]:
    m = re.match(r"^\d+\.\s*\*\*([^*]+?):?\*\*\s*(.*)", text, re.S)
    return (m.group(1).strip(), m.group(2).strip()) if m else (text, "")


def action_for(label: str, body: str) -> str:
    body = re.sub(r"\s+", " ", body).strip().rstrip(".")
    if label.startswith("Solutions pipeline"):
        total = re.search(r"(\d+) total", body)
        qual = re.search(r"qualified\+ (\d+)", body)
        if total and qual:
            n = int(qual.group(1))
            return (f"{n} qualified prospect{'s' if n != 1 else ''} out of {total.group(1)} inbound — "
                    f"push qualified-stage forward this week.")
    if label.startswith("Case-study"):
        return "Case-study captures need attention — sweep status / NDA verification on all open briefs."
    if label.startswith("Active experiments"):
        if "0 in flight" in body:
            return "No experiments running — floor is 2. Scope and register two from the RICE backlog."
        return f"Experiments due for kill-check: {body}."
    return f"{label}: {body}"


def content_distribution_line(vault: Path) -> str:
    metrics_dir = vault / "Projects" / "Zerg-Production" / "Growth" / "metrics"
    files = list(metrics_dir.glob("*-engagement.md")) if metrics_dir.exists() else []
    if not files:
        return "8. **Content distribution coverage:** _(no data — release_thread metrics not yet populated)_"
    cutoff = dt.date.today() - dt.timedelta(days=7)
    by_slug: dict[str, dict[str, int]] = {}
    for f in files:
        try:
            text = f.read_text()
        except OSError:
            continue
        m = re.search(r"^slug:\s*([\w\-]+)-engagement", text, re.MULTILINE)
        slug = m.group(1) if m else f.stem.replace("-engagement", "")
        totals = {"hn_points": 0, "hn_comments": 0, "x_likes": 0, "reddit_score": 0}
        for ln in text.splitlines():
            row = re.match(r"\|\s*\w+\s*\|\s*(\d{4}-\d{2}-\d{2})T[^|]*\|\s*\w+\s*\|\s*(\w+)\s*\|\s*([\d.]+)\s*\|", ln)
            if not row:
                continue
            try:
                if dt.date.fromisoformat(row.group(1)) < cutoff:
                    continue
            except ValueError:
                continue
            metric, val = row.group(2), row.group(3)
            if metric in totals:
                totals[metric] = max(totals[metric], int(float(val)))
        eng = sum(totals.values())
        if eng > 0:
            by_slug[slug] = {**totals, "_total": eng}
    if not by_slug:
        return "8. **Content distribution coverage (last 7d):** _(metrics files present but no data in window)_"
    parts = [f"8. **Content distribution coverage (last 7d, {len(by_slug)} posts tracked):**"]
    for slug, m in sorted(by_slug.items(), key=lambda kv: -kv[1]["_total"])[:3]:
        bits = []
        if m.get("hn_points"): bits.append(f"HN {m['hn_points']}pt/{m.get('hn_comments', 0)}c")
        if m.get("x_likes"): bits.append(f"X {m['x_likes']} likes")
        if m.get("reddit_score"): bits.append(f"Reddit {m['reddit_score']}")
        parts.append(f"   - {slug}: {' · '.join(bits) if bits else 'no engagement'}")
    return "\n".join(parts)


def assemble(week_label: str, raw_lines: list[str], for_slack: bool, log_target) -> str:
    today = dt.date.today().isoformat()
    classified: list[tuple[str, str, str, str]] = []
    for full in raw_lines:
        header = full.splitlines()[0]
        label, body = label_and_body(header)
        if "\n" in full and label.startswith("Case-study"):
            row_count = len([ln for ln in full.splitlines()[1:] if ln.strip().startswith("- ")])
            body = f"{row_count} brief{'s' if row_count != 1 else ''} open · NDA / status drift suspected"
        classified.append((classify(full), label, body, full))

    at_risk = [t for t in classified if t[0] == "at_risk"]
    healthy = [t for t in classified if t[0] == "healthy"]
    info = [t for t in classified if t[0] == "info"]
    pending = [t for t in classified if t[0] == "pending"]

    out = [f"# Zerg Growth Dashboard — {week_label} ({today})", "",
           "_Action-led; ≤5 visible lines on first read._", ""]

    primary = None
    for prefix in ("Solutions pipeline", "Case-study-in-flight", "Active experiments"):
        primary = next((t for t in at_risk if t[1].startswith(prefix)), None)
        if primary:
            break
    if not primary and at_risk:
        primary = at_risk[0]
    if primary:
        action = action_for(primary[1], primary[2])
        out.append(f"🎯 **THIS WEEK:** {action}")
        log_target("growth", action, source="growth_line", source_ref=primary[1])
    else:
        out.append("✅ **All green this week — no growth-line escalations.**")
    out.append("")

    secondary = [t for t in at_risk if t is not primary][:2]
    if secondary:
        out.append("**Also at risk:**")
        for _, label, body, _full in secondary:
            out.append(f"- {action_for(label, body)}")
        out.append("")

    if info:
        out.append("**Signal:**")
        for _, label, body, full in info:
            if "\n" in full:
                out.append(f"- **{label.lower()}:** {body}")
                for sub in full.splitlines()[1:]:
                    out.append(f"  {sub.strip()}")
            elif body:
                out.append(f"- **{label.lower()}:** {re.sub(chr(10), ' ', body)[:160]}")
        out.append("")

    if healthy:
        out.append(f"✅ _Healthy: {', '.join(t[1].lower() for t in healthy)}._")
    if pending:
        out.append(f"🚧 _Pending instrumentation ({len(pending)}): {', '.join(t[1].lower() for t in pending)}._")

    out += ["", "_Reply with what to fix or `all good`._"]

    case_study_full = next((t[3] for t in classified if t[1].startswith("Case-study")), None)
    if case_study_full and "\n" in case_study_full and not for_slack:
        out += ["", "<details><summary>Case-study breakdown</summary>", "",
                strip_numbering(case_study_full), "", "</details>"]
    return "\n".join(out)
