#!/usr/bin/python3
"""weekly_digest: Sun 9am cron → Fake Matt self-DM with the week's idea snapshot.

Picks:
  - 3 idle-but-promising (status=active, last_touched > 60d ago, conviction ≥ medium)
  - 1 newest capture from past 7 days
  - Triage queue size + 1 random untriaged item

Posts ONE Slack message to the Fake Matt → Matt DM (D0B0T0ETDR8). Mirrors the
fakematt-today digest pattern.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_LIB = _SCRIPTS / "_lib"
for p in (_LIB, _SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import metrics as _metrics  # noqa: E402
from frontmatter import read_file  # noqa: E402
from idea_io import iter_all_ideas  # noqa: E402
from usage import log_event, read_events  # noqa: E402
from vault_paths import VAULT_ROOT, INBOX_DIR  # noqa: E402

FAKE_MATT_SELF_DM = "D0B0T0ETDR8"
SKILLS_DIR = Path.home() / ".claude" / "skills"


def load_slack_token() -> str | None:
    cfg = SKILLS_DIR / "slack-skill" / "config.json"
    if not cfg.exists():
        return None
    try:
        import sys as _zs, pathlib as _zp; _zs.path.insert(0, str(_zp.Path.home()/".config"/"zerg")); from slack_token import slack_token
        return slack_token()
    except Exception:
        return None


def build_message() -> str:
    today = dt.date.today()

    idle: list[tuple[dict, Path]] = []
    fresh: list[tuple[dict, Path]] = []

    for p in iter_all_ideas(include_inbox=False, include_archive=False):
        try:
            meta, _ = read_file(p)
        except Exception:
            continue
        status = meta.get("status")
        conviction = meta.get("conviction")
        try:
            lt_str = meta.get("last_touched") or meta.get("created") or ""
            lt = dt.date.fromisoformat(lt_str)
        except Exception:
            continue
        try:
            cr = dt.date.fromisoformat(meta.get("created") or lt_str)
        except Exception:
            cr = lt

        if status == "active" and conviction in ("medium", "high") and (today - lt).days >= 60:
            idle.append((meta, p))
        if (today - cr).days <= 7:
            fresh.append((meta, p))

    idle.sort(key=lambda r: (r[0].get("conviction") == "high"), reverse=True)
    idle = idle[:3]
    fresh.sort(key=lambda r: r[0].get("created", ""), reverse=True)
    new_pick = fresh[:1]

    inbox_items: list[Path] = []
    if INBOX_DIR.exists():
        inbox_items = list(INBOX_DIR.rglob("*.md"))
    triage_count = len(inbox_items)
    triage_pick: Path | None = random.choice(inbox_items) if inbox_items else None

    lines = [f"*Idea backlog — {today.isoformat()}*", ""]

    if idle:
        lines.append("*💤 Idle, worth revisiting:*")
        for meta, p in idle:
            rel = p.relative_to(VAULT_ROOT)
            days_idle = (today - dt.date.fromisoformat(meta.get("last_touched") or meta.get("created"))).days
            lines.append(f"  • _{meta.get('title','?')}_ — {meta.get('category','?')} / {days_idle}d idle\n     → `{rel}`")
        lines.append("")

    if new_pick:
        meta, p = new_pick[0]
        rel = p.relative_to(VAULT_ROOT)
        lines.append("*🌱 New this week:*")
        lines.append(f"  • _{meta.get('title','?')}_ — {meta.get('category','?')}\n     → `{rel}`")
        lines.append("")

    if triage_count:
        lines.append(f"*📥 Triage queue:* {triage_count} items waiting")
        if triage_pick:
            try:
                meta, _ = read_file(triage_pick)
                lines.append(f"  • Random pick: _{meta.get('title','?')}_ — `{triage_pick.relative_to(VAULT_ROOT)}`")
            except Exception:
                pass
        lines.append("  Run `/idea-backlog triage` when you have 10 minutes.")
        lines.append("")

    if not (idle or new_pick or triage_count):
        lines.append("(Quiet week — backlog is clean.)")

    # 7-day usage snapshot
    import datetime as _dt
    week_ago = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=7)
    summary = _metrics.summarize(read_events(), week_ago)
    parts: list[str] = []
    if summary["captures"]["total"]:
        parts.append(f"{summary['captures']['total']} captured")
    if summary["recalls"]["total"]:
        parts.append(f"{summary['recalls']['total']} recalls")
    if summary["triage"]["total"]:
        parts.append(f"{summary['triage']['total']} triaged")
    if summary["auto_suggests"]["total"]:
        parts.append(f"{summary['auto_suggests']['total']} auto-surfaced")
    if parts:
        lines.append("")
        lines.append(f"*📊 last 7d:* {' · '.join(parts)}")

    return "\n".join(lines).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print only; don't post to Slack")
    args = ap.parse_args()

    body = build_message()
    if not body:
        print("nothing to digest.")
        return 0

    if args.dry_run:
        print("--- DRY RUN ---")
        print(body)
        return 0

    token = load_slack_token()
    if not token:
        print("no slack token; printing instead", file=sys.stderr)
        print(body)
        return 1

    try:
        from slack_sdk import WebClient
    except ImportError:
        print("slack_sdk not installed; printing instead", file=sys.stderr)
        print(body)
        return 1

    client = WebClient(token=token)
    res = client.chat_postMessage(channel=FAKE_MATT_SELF_DM, text=body)
    log_event("weekly_digest", source="weekly_digest.py", ts=res.get("ts"), bytes=len(body))
    print(f"posted to {FAKE_MATT_SELF_DM}: ts={res['ts']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
