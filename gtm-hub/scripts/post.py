#!/usr/bin/env python3
"""Post the GTM hub weekly digest to FM→Matt Slack DM (D0B0T0ETDR8).

Dry-run by default; `--post` actually sends. Honors feedback_fakematt_no_autopost.md.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

# Read via the mirror-tolerant META dir so launchd/cron runs don't hit the
# TCC-blocked iCloud path. This script only reads (it posts to Slack).
from lib.entities import READ_META_DIR as META_DIR  # noqa: E402
from lib.rules import diversify  # noqa: E402


FM_MATT_DM = "D0B0T0ETDR8"


def build_digest(index: dict, decisions: dict) -> str:
    today = dt.date.today().isoformat()
    rows = index.get("entities", [])
    ds = decisions.get("decisions", [])
    by_type: dict[str, int] = {}
    for r in rows:
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1
    parts: list[str] = []
    parts.append(f"*Zerg GTM Hub — {today}*")
    parts.append("")
    if ds:
        # Split actionable vs backlog so the Slack post leads with this-week
        # calls instead of debt rows.
        actionable_ds = [d for d in ds if d.get("kind", "decision") != "backlog"]
        backlog_ds = [d for d in ds if d.get("kind") == "backlog"]
        from act import hint_for_decision

        def _render_block(label: str, source: list, vis_limit: int) -> list[str]:
            if not source:
                return []
            visible = diversify(source, limit=vis_limit)
            block: list[str] = [label]
            for i, (d, siblings, names) in enumerate(visible, 1):
                if siblings:
                    shown = ", ".join(f"`{n}`" for n in names)
                    extra = f" +{siblings - len(names)}" if siblings > len(names) else ""
                    tail = f"  _(+{siblings} more: {shown}{extra})_"
                else:
                    tail = ""
                hint = hint_for_decision(d.get("rule", ""), d.get("entity_id", ""))
                hint_str = f"\n   → `{hint}`" if hint else ""
                block.append(f"{i}. {d['message']}{tail}{hint_str}")
            rolled = len(source) - sum(1 + s for _, s, _ in visible)
            if rolled > 0:
                block.append(f"_+{rolled} more in `_meta/decisions.json`_")
            return block

        parts.extend(_render_block("*▶ Decisions needed*", actionable_ds, 5))
        debt_block = _render_block("*📚 Measurement debt*", backlog_ds, 3)
        if debt_block:
            parts.append("")
            parts.extend(debt_block)
    else:
        parts.append("*▶ Decisions needed:* none 🟢")
    parts.append("")
    parts.append("*State*")
    for t in sorted(by_type):
        parts.append(f"  • {t}: {by_type[t]}")
    parts.append("")
    parts.append("_Full view: `Growth/README.md`. Skill: `gtm-hub`._")
    return "\n".join(parts)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--post", action="store_true", help="Actually send (default: dry-run print)")
    p.add_argument("--channel", default=FM_MATT_DM, help="Override Slack DM channel id")
    args = p.parse_args()

    idx = json.loads((META_DIR / "index.json").read_text(encoding="utf-8"))
    dec_path = META_DIR / "decisions.json"
    dec = json.loads(dec_path.read_text(encoding="utf-8")) if dec_path.exists() else {"decisions": []}
    msg = build_digest(idx, dec)

    if not args.post:
        print("=== DRY RUN (use --post to send) ===")
        print(msg)
        return 0

    # Hand-off to slack-skill rather than re-implementing token plumbing.
    import subprocess
    slack_script = Path.home() / ".claude" / "skills" / "slack-skill" / "slack_skill.py"
    if not slack_script.exists():
        print(f"slack-skill not found at {slack_script}; cannot send", file=sys.stderr)
        return 1
    cmd = ["python3", str(slack_script), "send", args.channel, "--message", msg]
    print("running:", " ".join(cmd[:5]), "...")
    res = subprocess.run(cmd, capture_output=True, text=True, env=os.environ.copy())
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr, file=sys.stderr)
        return res.returncode
    print("posted to", args.channel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
