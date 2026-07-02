#!/usr/bin/env python3
"""Regression tests for pr-stage / pr-table lock-screen wiring.

Anchored on actual locked articles that bit us:
- agents-that-remember (2026-05-12/13 regression, locked by Idan)
- zergboard-launch (locked by Idan 2026-05-09, still draft state)

Per `feedback_zarticle_required_before_state_claim.md` and
`feedback_locked_article_held_branches.md`, the lock-screen helpers in
pr-stage/run.py and pr-table/run.py MUST flag these as locked when they
appear in a diff — regardless of which worktree the path resolves through.

Earlier wiring bug (2026-05-13): the helper used worktree-resolved absolute
paths, but article_lock's BLOG_MD_DIR is anchored at ~/zerg (canonical).
Worktree paths under /private/tmp/... silently returned None. The fix is to
synthesize a canonical-rooted path before calling file_path_to_slug.

Run with: python3 ~/.claude/skills/pr-stage/test_lock_screen.py
"""
from __future__ import annotations
import importlib.util
import sys
from pathlib import Path


def load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def main() -> int:
    pr_stage = load("pr_stage", "/Users/mattheweisner/.claude/skills/pr-stage/run.py")

    fails = []

    # ── REAL-BUG-INSTANCE tests ──────────────────────────────────────────
    # Each test passes a worktree path that doesn't match BLOG_MD_DIR's
    # canonical anchor; the helper must still resolve via the canonical
    # synthesis. These are the exact bug shapes from 2026-05-13.

    cases = [
        {
            "name": "agents-that-remember in canonical worktree",
            "worktree": Path.home() / "zerg",
            "paths": ["web/src/public/content/blog/agents-that-remember.md"],
            "expect_locked_slugs": ["agents-that-remember"],
        },
        {
            "name": "agents-that-remember in /private/tmp worktree (the bug shape)",
            "worktree": Path("/private/tmp/zerg-some-other-worktree"),
            "paths": ["web/src/public/content/blog/agents-that-remember.md"],
            "expect_locked_slugs": ["agents-that-remember"],
        },
        {
            "name": "zergboard-launch in /private/tmp worktree (the bug that surfaced today)",
            "worktree": Path("/private/tmp/zerg-launch-roadmap"),
            "paths": ["web/src/public/content/blog/zergboard-launch.md"],
            "expect_locked_slugs": ["zergboard-launch"],
        },
        {
            "name": "clean code-only diff — no lock hits",
            "worktree": Path.home() / "zerg",
            "paths": ["api/utils/ops_alerts.py", "web/src/components/Footer.vue"],
            "expect_locked_slugs": [],
        },
        {
            "name": "mixed: clean + locked — locked-only returned",
            "worktree": Path("/private/tmp/zerg-some-other-worktree"),
            "paths": [
                "api/utils/ops_alerts.py",
                "web/src/public/content/blog/agents-that-remember.md",
                "web/src/components/Footer.vue",
            ],
            "expect_locked_slugs": ["agents-that-remember"],
        },
    ]

    for c in cases:
        hits = pr_stage.locked_paths_in_diff(c["worktree"], c["paths"])
        got_slugs = sorted([slug for _, slug in hits])
        expected = sorted(c["expect_locked_slugs"])
        status = "✓" if got_slugs == expected else "✗"
        print(f"{status} {c['name']}")
        print(f"    expected locked slugs: {expected}")
        print(f"    got:                   {got_slugs}")
        if got_slugs != expected:
            fails.append(c["name"])

    if fails:
        print()
        print(f"❌ {len(fails)} failure(s):")
        for f in fails:
            print(f"   - {f}")
        return 1

    print()
    print(f"✓ all {len(cases)} regression tests pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
