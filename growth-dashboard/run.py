#!/usr/bin/env python3
"""Growth dashboard — auto-generate the Monday 7am weekly review.

Usage:
    python3 ~/.claude/skills/growth-dashboard/run.py [--week YYYY-WW] [--no-post] [--verbose]

Reads:
  - Zergalytics public API (Phase 2 — TODO; Phase 1 stub)
  - MattZerg/Projects/Zstack/Growth/experiments.md + experiments/*.md
  - MattZerg/Projects/Zstack/Growth/prospects.md
  - MattZerg/Projects/Zstack/Case-Studies/*.md
  - MattZerg/Projects/Zstack/Growth/links.md
  - Stripe webhooks (Phase 2 — TODO)

Writes:
  - MattZerg/Projects/Zstack/Growth/weekly/YYYY-MM-DD.md
  - Slack DM via slack-skill (--no-post to skip)
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
import time
from pathlib import Path

def _resolve_vault_root(sub: str = "Zerg/MattZerg") -> Path:
    """Live vault is ~/Obsidian/<sub>; the iCloud path was retired 2026-06-24.
    Prefer the live path, fall back to the legacy iCloud path only if it still exists."""
    primary = Path.home() / "Obsidian" / sub
    if primary.exists():
        return primary
    legacy = (
        Path.home()
        / "Library" / "Mobile Documents" / "iCloud~md~obsidian" / "Documents" / sub
    )
    return legacy if legacy.exists() else primary


VAULT = _resolve_vault_root("Zerg/MattZerg")
GROWTH_DIR = VAULT / "Projects" / "Zstack" / "Growth"
EXPERIMENTS_DIR = GROWTH_DIR / "experiments"
WEEKLY_DIR = GROWTH_DIR / "weekly"
PROSPECTS_FILE = GROWTH_DIR / "prospects.md"
LINKS_FILE = GROWTH_DIR / "links.md"
CASE_STUDIES_DIR = VAULT / "Projects" / "Zstack" / "Case-Studies"
SLACK_SKILL = Path.home() / ".claude" / "skills" / "slack-skill" / "slack_skill.py"
FAKE_MATT_DM = "D0B0T0ETDR8"  # FM → Matt DM (per memory)


def parse_yaml_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}
    fm_block = text[4:end]
    meta: dict[str, str] = {}
    for line in fm_block.splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        v = v.strip()
        if v.startswith('"') and v.endswith('"'):
            v = v[1:-1]
        meta[k.strip()] = v
    return meta


def read_experiments() -> list[dict[str, str]]:
    if not EXPERIMENTS_DIR.exists():
        return []
    out = []
    for f in sorted(EXPERIMENTS_DIR.glob("exp-*.md")):
        if f.name.startswith("_"):
            continue
        meta = parse_yaml_frontmatter(f.read_text())
        if meta.get("id"):
            out.append(meta)
    return out


def days_until(date_str: str) -> int | None:
    try:
        kd = dt.date.fromisoformat(date_str)
        return (kd - dt.date.today()).days
    except ValueError:
        return None


def line_active_experiments() -> str:
    rows = read_experiments()
    running = [r for r in rows if r.get("status") == "running"]
    if not running:
        return "5. **Active experiments:** 0 in flight. Floor is 2 — flag RED."
    parts = [f"5. **Active experiments:** {len(running)} in flight"]
    for r in running:
        d = days_until(r.get("kill_date", ""))
        d_str = f"{d}d" if d is not None else "?"
        parts.append(
            f"   - {r['id']} ({r.get('name','?')}): kill in {d_str} | metric={r.get('success_metric','?')} | thresh={r.get('success_threshold','?')}"
        )
    return "\n".join(parts)


def line_solutions_pipeline() -> str:
    if not PROSPECTS_FILE.exists():
        return "6. **Solutions pipeline:** (no prospects.md found — TODO)"
    txt = PROSPECTS_FILE.read_text()
    # Count rows by stage
    stages = {"inbound": 0, "qualified": 0, "scoped": 0, "proposal-out": 0, "won": 0, "lost": 0}
    rows = [ln for ln in txt.splitlines() if ln.startswith("|") and not ln.startswith("|---") and "Stage" not in ln and "_(populate" not in ln]
    for ln in rows:
        cells = [c.strip() for c in ln.split("|")[1:-1]]
        if len(cells) >= 2:
            stage = cells[1]
            if stage in stages:
                stages[stage] += 1
    total = sum(stages.values())
    if total == 0:
        return "6. **Solutions pipeline:** 0 prospects (Phase 1 — populating via `network-reach`)"
    qual_or_more = sum(stages[s] for s in ("qualified", "scoped", "proposal-out", "won"))
    return (f"6. **Solutions pipeline:** {total} total | "
            f"qualified+ {qual_or_more} | proposal-out {stages['proposal-out']} | "
            f"won {stages['won']} | lost {stages['lost']}")


def line_case_studies() -> str:
    if not CASE_STUDIES_DIR.exists():
        return "7. **Case-study-in-flight:** (no Case-Studies dir found — TODO)"
    parts = ["7. **Case-study-in-flight:**"]
    for f in sorted(CASE_STUDIES_DIR.glob("*.md")):
        if f.name.startswith("_"):
            continue
        txt = f.read_text()
        client = f.stem
        # crude state machine
        m = re.search(r"\*\*Status:\*\*\s*(\w+)", txt)
        status = m.group(1) if m else "unknown"
        nda_m = re.search(r"\*\*NDA:\*\*\s*([\w-]+)", txt)
        nda = nda_m.group(1) if nda_m else "?"
        parts.append(f"   - {client}: status={status} nda={nda}")
    return "\n".join(parts)


def line_top_sources() -> str:
    if not LINKS_FILE.exists():
        return "4. **Top 3 sources:** (links.md empty — TODO instrument with `utm-attribution`)"
    txt = LINKS_FILE.read_text()
    rows = [ln for ln in txt.splitlines() if ln.startswith("|") and not ln.startswith("|---") and "Date" not in ln]
    if not rows:
        return "4. **Top 3 sources:** (no links generated yet)"
    src_counts: dict[str, int] = {}
    for ln in rows:
        cells = [c.strip() for c in ln.split("|")[1:-1]]
        if len(cells) >= 3:
            src = cells[2]
            src_counts[src] = src_counts.get(src, 0) + 1
    top = sorted(src_counts.items(), key=lambda kv: -kv[1])[:3]
    return "4. **Top 3 sources by links generated** (Phase 1 proxy for activated; Zergalytics-resolved Phase 2): " + ", ".join(f"{s} ({n})" for s, n in top)


def render_dashboard(week_label: str, verbose: bool) -> str:
    today = dt.date.today().isoformat()
    out = [
        f"# Zerg Growth Dashboard — {week_label} ({today})",
        "",
        "Auto-generated by `growth-dashboard` skill v0.",
        "",
        "## North Star",
        "",
        "- **Zstack WAPW:** _(no data — Zergalytics integration TODO Phase 1 Day 25-30)_",
        "- **Solutions QPV (trailing 30d):** _(no data — populate from `prospects.md` weighted $)_",
        "",
        "## Lines",
        "",
        "1. **Activated accounts this week:** _(no data — Zergalytics aha-event taxonomy TODO Phase 1 Day 1-3)_",
        "",
        "2. **Paid conversions:** _(no data — Stripe webhook integration TODO Phase 2)_",
        "",
        "3. **Activation rate (signed-up → activated, 7d cohort):** _(no data — see line 1)_",
        "",
        line_top_sources(),
        "",
        line_active_experiments(),
        "",
        line_solutions_pipeline(),
        "",
        line_case_studies(),
        "",
        "8. **Content distribution coverage (last week's blog → 14 surfaces):** _(no data — `content-distribution` skill Phase 2)_",
        "",
        "9. **Email program health:** _(no data — list size + broadcast metrics Phase 2 once `email-drip` ships)_",
        "",
        "10. **Referral metrics:** _(Phase 2+ — K-factor + Solutions referrals)_",
        "",
        "11. **Open question of the week:** _(Matt fills weekly)_",
        "",
        "## What moves to red this week",
        "",
        "- _(populated when ≥1 line crosses kill_threshold or is critically empty)_",
        "",
        "## What's GREEN",
        "",
        "- _(populated when ≥1 line beats success_threshold W/W)_",
        "",
    ]
    return "\n".join(out)


FAILURES_LOG = Path.home() / ".claude" / "skills" / "growth-dashboard" / "logs" / "post-failures.log"
GMAIL_SKILL = Path.home() / ".claude" / "skills" / "gmail-skill" / "gmail_skill.py"
FALLBACK_EMAIL = "matteisn@gmail.com"


def post_to_slack(content: str, week_label: str) -> bool:
    """Post to Slack with retry + 2-channel fallback if all retries fail.

    Anti-drift: if Slack is down Monday morning, the dashboard would silently miss
    a week without 2-channel notification. Retry 3x with backoff; on full failure,
    write to logs/post-failures.log AND email Matt via gmail-skill.
    """
    if not SLACK_SKILL.exists():
        _record_post_failure(week_label, "slack-skill not found at expected path", content)
        return False
    body = content
    if len(body) > 35000:
        body = body[:35000] + "\n\n_(truncated — see full file in vault)_"
    msg = f"📊 Growth dashboard — {week_label}\n\n```\n{body}\n```"

    last_err = ""
    for attempt, delay in enumerate([0, 5, 25], start=1):
        if delay:
            time.sleep(delay)
        try:
            subprocess.run(
                ["python3", str(SLACK_SKILL), "send", FAKE_MATT_DM, msg],
                check=True, capture_output=True, text=True, timeout=30,
            )
            if attempt > 1:
                print(f"INFO: Slack post succeeded on attempt {attempt}.", file=sys.stderr)
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            last_err = (e.stderr if hasattr(e, "stderr") and e.stderr else str(e)) or "unknown"
            print(f"WARN: Slack post attempt {attempt} failed: {last_err[:200]}", file=sys.stderr)

    # All retries failed: log + email fallback
    _record_post_failure(week_label, last_err, content)
    _email_fallback(week_label, last_err)
    return False


def _record_post_failure(week_label: str, err: str, content: str) -> None:
    """Append every failed post to logs/post-failures.log so the failure mode isn't silent."""
    FAILURES_LOG.parent.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().isoformat(timespec="seconds")
    with FAILURES_LOG.open("a") as f:
        f.write(f"\n=== {ts} — {week_label} — Slack post FAILED ===\n")
        f.write(f"error: {err[:500]}\n")
        f.write(f"content_len: {len(content)} chars\n")
        f.write(f"vault_file: Growth/weekly/{dt.date.today().isoformat()}.md\n")


def _email_fallback(week_label: str, err: str) -> bool:
    """Email Matt directly when Slack post fails. 2-channel notification."""
    if not GMAIL_SKILL.exists():
        print("WARN: gmail-skill not found; cannot send email fallback.", file=sys.stderr)
        return False
    subject = f"[Growth Dashboard] Slack post FAILED — {week_label}"
    body = (
        f"The Monday weekly growth dashboard post failed to land in Slack.\n\n"
        f"Week: {week_label}\n"
        f"Error: {err[:500]}\n"
        f"Vault file (still written): MattZerg/Projects/Zstack/Growth/weekly/{dt.date.today().isoformat()}.md\n\n"
        f"Failure log: {FAILURES_LOG}\n\n"
        f"This is a 2-channel fallback so a Slack outage doesn't silently swallow the week's review."
    )
    try:
        subprocess.run(
            ["python3", str(GMAIL_SKILL), "send", "--to", FALLBACK_EMAIL,
             "--subject", subject, "--body", body],
            check=True, capture_output=True, text=True, timeout=30,
        )
        print(f"INFO: Email fallback sent to {FALLBACK_EMAIL}.", file=sys.stderr)
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        err_text = (e.stderr if hasattr(e, "stderr") and e.stderr else str(e))
        print(f"WARN: Email fallback also failed: {err_text[:200]}", file=sys.stderr)
        return False


def main() -> int:
    p = argparse.ArgumentParser(prog="growth-dashboard", description=__doc__)
    p.add_argument("--week", help="ISO week label like 2026-W19 (default: current)")
    p.add_argument("--no-post", action="store_true", help="don't post to Slack DM")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    today = dt.date.today()
    if args.week:
        week_label = args.week
    else:
        iso_year, iso_week, _ = today.isocalendar()
        week_label = f"{iso_year}-W{iso_week:02d}"

    content = render_dashboard(week_label, args.verbose)

    WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
    out_file = WEEKLY_DIR / f"{today.isoformat()}.md"
    out_file.write_text(content)
    print(f"Wrote {out_file}")

    if not args.no_post:
        ok = post_to_slack(content, week_label)
        if ok:
            print(f"Posted to Slack DM {FAKE_MATT_DM}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
