#!/usr/bin/env python3
"""monthly_audit — cron entrypoint: run harness-audit across BOTH stacks
(~/.claude and ~/.codex), write a combined dated report, and DM Matt via
Fake Matt → Slack ONLY if there are HIGH findings.

Wired via crontab (monthly). Fail-open: never raises into cron.
"""
from __future__ import annotations

import datetime as _dt
import json
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
sys.path.insert(0, str(Path(__file__).resolve().parent))
import scan  # noqa: E402

ROOTS = [HOME / ".claude", HOME / ".codex"]
SLACK = HOME / ".claude" / "skills" / "slack-skill" / "slack_skill.py"
SLACK_CFG = HOME / ".claude" / "skills" / "slack-skill" / "config.json"


def send_fm_dm(message: str) -> None:
    try:
        ch = json.loads(SLACK_CFG.read_text()).get("default", {}).get("fm_dm_channel")
        if not ch:
            return
        subprocess.run(["/usr/bin/python3", str(SLACK), "send", ch, "--message", message],
                       capture_output=True, text=True, timeout=60)
    except Exception:
        pass


def main() -> int:
    by_root = {}
    for root in ROOTS:
        if root.exists():
            by_root[root] = scan.run_scan(root)

    highs = [(r, f) for r, fs in by_root.items() for f in fs if f.severity == "HIGH"]
    today = _dt.date.today().strftime("%Y%m%d")
    when = _dt.date.today().isoformat()

    lines = [f"# harness-audit monthly — {when}", ""]
    total_h = total_m = 0
    for root, fs in by_root.items():
        h = sum(1 for f in fs if f.severity == "HIGH")
        m = sum(1 for f in fs if f.severity == "MED")
        total_h += h
        total_m += m
        lines.append(f"## {root}  ({h} HIGH · {m} MED · {len(fs)} total)")
        for f in sorted(fs, key=lambda x: scan.SEV_ORDER.get(x.severity, 9)):
            loc = f.path + (f":{f.line}" if f.line else "")
            lines.append(f"- [{f.severity}] {f.category} {loc} — {f.detail}")
        lines.append("")
    report = HOME / ".claude" / "logs" / f"harness-audit-monthly-{today}.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines) + "\n")

    if highs:
        head = (f":rotating_light: *harness-audit monthly* — {len(highs)} HIGH finding(s) "
                f"across your stacks ({total_m} MED). Full report: `{report}`")
        items = "\n".join(f"• [{r.name}] {f.category} {f.path}:{f.line} — {f.detail}"
                          for r, f in highs[:15])
        send_fm_dm(head + "\n" + items)

    print(f"monthly harness-audit: {total_h} HIGH · {total_m} MED across "
          f"{len(by_root)} stacks → {report}"
          + (" (DM sent)" if highs else " (no HIGH; no DM)"))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:  # never break cron
        print(f"monthly_audit error (fail-open): {e}", file=sys.stderr)
        raise SystemExit(0)
