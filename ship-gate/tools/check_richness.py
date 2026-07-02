#!/usr/bin/env python3
"""ship-gate visual-richness check (B1).

Wraps webpage-layout's `richness` audit and emits a ship-gate-shaped verdict
(green / yellow / red) for marketing-page or launch-page surfaces.

Per memory/project_visual_richness_recipes.md and
~/.claude/skills/webpage-layout/recipes/visual-richness.md, R1-R10 are the
recipes for "more eye-catching" lifts on Zerg-style pages.

Thresholds (calibrated against webpage-layout/run.py:cmd_richness verdict):
    >= 7 of 10 applied -> GREEN  (BOLD)
    4-6 of 10 applied -> YELLOW (BALANCED)
    <= 3 of 10 applied -> RED    (EDITORIAL-LEAN)

Usage:
    python3 check_richness.py <url>

Exit codes: 0 green, 1 yellow, 2 red, 70 tool error.
"""
import json
import subprocess
import sys
from pathlib import Path

WEBPAGE_LAYOUT = Path.home() / ".claude/skills/webpage-layout/run.py"
# webpage-layout depends on httpx, which lives on system python (matches the
# pattern in memory/feedback_fakematt_feedback_8000px_fix.md).
SYSTEM_PYTHON = "/usr/bin/python3"


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: check_richness.py <url>", file=sys.stderr)
        return 64
    url = sys.argv[1]
    if not WEBPAGE_LAYOUT.exists():
        print(f"webpage-layout skill missing at {WEBPAGE_LAYOUT}", file=sys.stderr)
        return 70
    python = SYSTEM_PYTHON if Path(SYSTEM_PYTHON).exists() else sys.executable
    proc = subprocess.run(
        [python, str(WEBPAGE_LAYOUT), "richness", url],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if proc.returncode != 0:
        print("# visual-richness — ERROR")
        print()
        print(f"richness audit exited {proc.returncode}.")
        if proc.stderr:
            print()
            print("```")
            print(proc.stderr.strip()[:600])
            print("```")
        return 70
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        print("# visual-richness — ERROR")
        print()
        print(f"could not parse audit output: {exc}")
        return 70

    applied = int(data.get("applied", 0))
    total = int(data.get("total", 10))
    pct = int(data.get("score_pct", 0))
    verdict = data.get("verdict", "?")

    if applied >= 7:
        status, exit_code = "GREEN", 0
    elif applied >= 4:
        status, exit_code = "YELLOW", 1
    else:
        status, exit_code = "RED", 2

    not_applied = [r for r in data.get("results", []) if not r.get("applied")]

    print(f"# visual-richness — {status}")
    print()
    print(f"**URL**: {url}")
    print(f"**Verdict**: `{verdict}` · **Applied**: `{applied}/{total}` ({pct}%)")
    print()
    if status == "GREEN":
        print("Marketing surface clears the visual-richness bar. No action.")
    else:
        print("**Missing recipes** (R1-R10):")
        for r in not_applied[:6]:
            print(f"- **{r['id']}** {r['name']}")
        print()
        print(f"Lift: `python3 {WEBPAGE_LAYOUT} richness-lift {url}`")
        if status == "RED":
            print()
            print("**Hard block** for external marketing ship — fewer than 4 recipes applied.")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
