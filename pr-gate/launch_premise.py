#!/usr/bin/env python3
"""Launch-premise gate — refuses to open a PR that publishes new launch content
unless Matt has written a fresh in-session confirmation token.

Why this exists:
    On 2026-05-06, a prior session recorded "Idan signed off, Wed ship" in memory
    for a Zergboard launch. Today's session acted on that record and opened 4 PRs
    (1 of which got merged) — but Agent Intelligence was the actual launch and
    Zergboard wasn't ready. Memory was a snapshot, not a standing greenlight.

    This module hard-blocks the failure mode: a new blog post + new blog metadata
    entry can't get to `gh pr create` without Matt confirming TODAY (in-session,
    by hand) that this launch is current.

Triggers (any one of):
    1. New file added in `web/src/public/content/blog/*.md`
    2. New file added in `web/src/constants/blog/posts/*.ts` (excluding index.ts)

Pass condition:
    A file in `~/.config/zerg/launch-confirmed/` exists with mtime in the last
    24 hours AND its slug matches one of the new files (basename match, soft).

    OR: any token in that dir with mtime < 12h old (broad in-session confirm).

Override: `--force` on pr-gate (already logged via existing override path).
"""
from __future__ import annotations

import datetime as dt
import os
import re
import sys
import time
from pathlib import Path

CONFIRM_DIR = Path.home() / ".config" / "zerg" / "launch-confirmed"
CONFIRM_HELPER = Path.home() / ".config" / "zerg" / "confirm_launch.py"

# Trigger patterns — adding ANY new file matching these = launch-publish PR
NEW_FILE_TRIGGERS = (
    re.compile(r"web/src/public/content/blog/[^/]+\.md$"),
    re.compile(r"web/src/constants/blog/posts/(?!index\.ts$)(?!types\.ts$)[^/]+\.ts$"),
)

# Modification triggers — these need confirmation when the diff is large
# (small typo edits don't trigger; copy refreshes that look like a launch do)
MODIFY_TRIGGERS = (
    # zergboard / zmail / etc landing pages — front page hero copy
    re.compile(r"^(zergboard|zmail|zergsend|zergwallet|zerglytics|zergcal|zergchat)/pages/index\.vue$"),
    re.compile(r"^web/src/pages/index\.vue$"),
)
MODIFY_LINE_THRESHOLD = 60  # added lines — heuristic for "this is a copy launch"

# Confirmation token freshness windows
SLUG_MATCH_WINDOW_HOURS = 24
ANY_TOKEN_WINDOW_HOURS = 12


def changed_files_with_status(base: str) -> list[tuple[str, str]]:
    """Return [(status, path)] for diff vs origin/<base>. Status: A/M/D/R..."""
    import subprocess
    r = subprocess.run(
        ["git", "diff", "--name-status", f"origin/{base}...HEAD"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        return []
    out = []
    for line in r.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            out.append((parts[0][0], parts[-1].strip()))  # take first char of status
    return out


def added_lines_per_file(base: str) -> dict[str, int]:
    """Return {path: added_line_count} for diff vs origin/<base>."""
    import subprocess
    r = subprocess.run(
        ["git", "diff", "--numstat", f"origin/{base}...HEAD"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        return {}
    out = {}
    for line in r.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].isdigit():
            out[parts[2].strip()] = int(parts[0])
    return out


def detect_launch_content(base: str) -> list[tuple[str, str]]:
    """Return list of (reason, path) tuples that flag this PR as a launch-publish."""
    flagged: list[tuple[str, str]] = []
    files = changed_files_with_status(base)
    added = added_lines_per_file(base)

    for status, path in files:
        # New-file triggers
        if status == "A":
            for pat in NEW_FILE_TRIGGERS:
                if pat.search(path):
                    flagged.append(("new-launch-content-file", path))
                    break

        # Modify-with-volume triggers (landing-page hero copy refresh)
        if status in ("A", "M"):
            for pat in MODIFY_TRIGGERS:
                if pat.search(path):
                    if added.get(path, 0) >= MODIFY_LINE_THRESHOLD:
                        flagged.append(("landing-page-copy-refresh", path))
                    break

    return flagged


def slug_from_path(path: str) -> str:
    """Extract a stable slug from a flagged file path."""
    name = Path(path).stem
    # Drop common prefixes/suffixes
    name = re.sub(r"-(launch|companion|post|announcement)$", "", name)
    return name.lower()


def fresh_confirmation_tokens(window_hours: float) -> list[Path]:
    """Return tokens in CONFIRM_DIR with mtime within the window."""
    if not CONFIRM_DIR.exists():
        return []
    cutoff = time.time() - (window_hours * 3600)
    return [p for p in CONFIRM_DIR.iterdir()
            if p.is_file() and p.stat().st_mtime >= cutoff]


def check_confirmation(flagged: list[tuple[str, str]]) -> tuple[bool, str]:
    """Decide if a fresh confirmation exists for this launch.

    Returns (passed, reason).
    """
    if not flagged:
        return True, "no-launch-content"

    flagged_slugs = {slug_from_path(p) for _, p in flagged}

    # Tier 1: token whose name matches a flagged slug, mtime < 24h
    slug_match = fresh_confirmation_tokens(SLUG_MATCH_WINDOW_HOURS)
    for tok in slug_match:
        tok_slug = tok.stem.lower()
        # Token name format: YYYY-MM-DD-<slug>.txt → strip date prefix
        tok_slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", tok_slug)
        for fs in flagged_slugs:
            if tok_slug == fs or tok_slug in fs or fs in tok_slug:
                return True, f"slug-matched-token={tok.name}"

    # Tier 2: any token < 12h old (broad in-session confirm)
    broad = fresh_confirmation_tokens(ANY_TOKEN_WINDOW_HOURS)
    if broad:
        # Read the token to check if Matt explicitly named "any" or matched slugs
        for tok in broad:
            try:
                content = tok.read_text().lower()
                if "any" in content or "all" in content:
                    return True, f"broad-confirm-token={tok.name}"
            except Exception:
                pass

    return False, f"no-fresh-confirmation (need slug in {flagged_slugs})"


def block_message(flagged: list[tuple[str, str]], reason: str) -> str:
    """Construct the user-facing block message."""
    today = dt.date.today().isoformat()
    flagged_paths = "\n".join(f"  - {reason}: {path}" for reason, path in flagged)
    suggested_slug = slug_from_path(flagged[0][1]) if flagged else "your-launch"

    return f"""
[launch-premise-gate] BLOCKED

This PR publishes new launch content:

{flagged_paths}

The pr-gate refuses to open it without an in-session confirmation that this
is the launch you're shipping THIS week (not a stale plan from a prior session).

WHY THIS GATE EXISTS:
  On 2026-05-06, a prior session recorded "Idan signed off, Wed ship" in memory
  for a Zergboard launch. Today's session acted on that record and opened 4 PRs
  (1 of which got merged) — but Agent Intelligence was the actual launch.
  Memory was a snapshot, not a standing greenlight. This gate prevents that
  failure mode.

HOW TO PASS:
  Run this command IN A TERMINAL (not via Claude) to confirm you actually want
  to ship this launch today:

      python3 ~/.config/zerg/confirm_launch.py {suggested_slug}

  This writes a token at:
      ~/.config/zerg/launch-confirmed/{today}-{suggested_slug}.txt

  Then re-run pr-gate. The gate accepts the token and proceeds.

OVERRIDE (logged):
      pr-gate ... --force

Reason: {reason}
""".strip()


def main() -> int:
    """CLI entry: check premise gate, exit 0 = pass, 1 = block."""
    import argparse
    parser = argparse.ArgumentParser(description="Launch-premise gate")
    parser.add_argument("--base", default="development",
                        help="base branch (default: development)")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    flagged = detect_launch_content(args.base)
    passed, reason = check_confirmation(flagged)

    if passed:
        if not args.quiet:
            if flagged:
                print(f"[launch-premise] PASS — {reason}", file=sys.stderr)
            else:
                print("[launch-premise] PASS — no launch-publish content in diff",
                      file=sys.stderr)
        return 0

    print(block_message(flagged, reason), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
