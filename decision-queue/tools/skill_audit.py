#!/usr/bin/env python3
"""skill_audit.py — dead-skill 90d audit.

Reads ~/.claude/state/skill_invocations.jsonl and ~/.claude/skills/*/SKILL.md.
Lists skills with zero invocations in last 90d. Emits a report + a decision
queue item per deprecation candidate.

Verbs:
  skill_audit.py                 # full audit, write report + queue items
  skill_audit.py --days 30       # tighter window
  skill_audit.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

INV = Path.home() / ".claude/state/skill_invocations.jsonl"
SKILLS_DIR = Path.home() / ".claude/skills"
PACKS_JSONL = Path.home() / ".claude/state/composite_proposals.jsonl"
CALIB_DIR = Path(os.path.expanduser(
    "~/Obsidian/Zerg/"
    "MattZerg/_style/calibration"
))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_week() -> str:
    now = datetime.now(timezone.utc)
    iy, iw, _ = now.isocalendar()
    return f"{iy}-W{iw:02d}"


def load_invocations(days: int) -> Counter:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    counts: Counter = Counter()
    if not INV.exists():
        return counts
    with INV.open() as fh:
        for line in fh:
            try:
                r = json.loads(line)
                ts = datetime.fromisoformat(r.get("ts", "").replace("Z", "+00:00"))
                if ts < cutoff:
                    continue
                skill = r.get("skill", "")
                if not skill:
                    continue
                counts[skill] += 1
            except Exception:
                continue
    return counts


def installed_skills() -> dict[str, str]:
    """Map skill_name -> first-line description from SKILL.md."""
    out: dict[str, str] = {}
    if not SKILLS_DIR.exists():
        return out
    for d in sorted(SKILLS_DIR.iterdir()):
        if not d.is_dir():
            continue
        sm = d / "SKILL.md"
        if not sm.exists():
            continue
        desc = ""
        try:
            text = sm.read_text()
            # Try frontmatter description
            m = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
            if m:
                desc = m.group(1).strip().strip('"').strip("'")[:120]
        except Exception:
            pass
        out[d.name] = desc
    return out


def emit_queue_rows(dead: list[str], descs: dict[str, str], label: str, cap: int = 10) -> int:
    """Cap emissions to avoid flooding the queue.

    skill_invocations.jsonl undercounts (only Skill-tool path; ignores /commands
    + agent-dispatched skill use). Surface only a SINGLE summary row pointing
    to the calibration report — let Matt review before per-skill decisions.
    """
    PACKS_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with PACKS_JSONL.open("a") as fh:
        row = {
            "ts": _now_iso(),
            "label": label,
            "kind": "composite_proposal",
            "id": f"skill_audit:{label}:summary",
            "theme": f"Skill audit — {len(dead)} candidates dormant",
            "size": len(dead),
            "composite_hint": "skill audit report — Matt to review",
            "samples": [
                f"Review report: MattZerg/_style/calibration/skill-audit-90d-{label}.md",
                f"Top dormant: " + ", ".join(dead[:8]),
                "Likely undercount: skill_invocations.jsonl misses /command + agent dispatches",
            ],
        }
        fh.write(json.dumps(row, default=str) + "\n")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    counts = load_invocations(args.days)
    installed = installed_skills()
    fired = set(counts.keys())
    all_installed = set(installed.keys())
    dead = sorted(all_installed - fired)
    used = sorted(all_installed & fired, key=lambda s: -counts[s])

    label = _iso_week()
    out = CALIB_DIR / f"skill-audit-{args.days}d-{label}.md"

    lines = [f"# Skill audit — {args.days}-day window — {label}\n"]
    lines.append(f"*Generated: {_now_iso()}*  • Source: `~/.claude/state/skill_invocations.jsonl`\n")
    lines.append("> **Calibration caveat:** `skill_invocations.jsonl` only captures invocations via the `Skill` tool. It UNDERCOUNTS skills used via slash-commands, agent dispatches, and direct Python execution. Treat the dead-skill list below as a *candidate* list — verify each against `skill_fire_rates.py` and `~/.claude/logs/hook-fires.jsonl` before deprecating.")
    lines.append("")
    lines.append(f"- Installed skills: **{len(all_installed)}**")
    lines.append(f"- Fired in {args.days}d: **{len(used)}**")
    lines.append(f"- DEAD (zero invocations in {args.days}d): **{len(dead)}**")
    lines.append("")
    lines.append(f"## Top 10 most-used skills ({args.days}d)")
    lines.append("")
    lines.append("| Skill | Invocations |")
    lines.append("|---|---|")
    for sk in used[:10]:
        lines.append(f"| `{sk}` | {counts[sk]} |")
    lines.append("")
    lines.append(f"## Dead skills ({len(dead)} candidates for deprecation/consolidation)")
    lines.append("")
    if not dead:
        lines.append("_None._")
    else:
        lines.append("| Skill | Description |")
        lines.append("|---|---|")
        for sk in dead:
            d = installed.get(sk, "")
            lines.append(f"| `{sk}` | {d[:80]} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Recommendation framework")
    lines.append("")
    lines.append("For each dead skill, choose:")
    lines.append("- **Deprecate** — remove SKILL.md or move to `~/.claude/skills/_deprecated/`")
    lines.append("- **Consolidate** — merge into a sibling skill (note in target SKILL.md)")
    lines.append("- **Keep idle** — explicitly tagged as low-frequency-but-required (rare)")
    md = "\n".join(lines)

    if args.dry_run:
        print(md[:2400])
        print("---END PREVIEW---")
        print(f"would write: {out}")
        print(f"would emit {len(dead)} decision-queue items")
        return 0

    CALIB_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(md)
    n_queued = emit_queue_rows(dead, installed, label)
    print(json.dumps({
        "ok": True,
        "file": str(out),
        "installed": len(all_installed),
        "fired": len(used),
        "dead": len(dead),
        "queued": n_queued,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
