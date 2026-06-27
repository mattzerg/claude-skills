#!/usr/bin/env python3
"""Voice promotion loop — turn repeated corrections into learned rules.

Runs daily after `learn.py` (which appends individual diffs to corrections.md).
This script scans BOTH skills' corrections.md files, extracts substitution
patterns, counts repeats across recipients, and rebuilds
`MattZerg/_style/learned_patterns.md` with patterns that have crossed the
"learned" threshold (≥3 distinct corrections).

Both fakematt-email/run.py and fakematt-personal/run.py load
learned_patterns.md as an anchor on every run, so promoted rules
auto-influence future drafts without any manual curation step.

Usage:
    python3 ~/.claude/skills/fakematt-email/promote.py [--threshold N]

Threshold default = 3 (a pattern must show up across 3 distinct corrections
to be promoted). Lower = more sensitive, higher = more conservative.
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import re
import sys
from collections import Counter, defaultdict
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
LEARNED = VAULT / "_style" / "learned_patterns.md"
EMAIL_CORRECTIONS = Path.home() / ".claude" / "skills" / "fakematt-email" / "corrections.md"
PERSONAL_CORRECTIONS = Path.home() / ".claude" / "skills" / "fakematt-personal" / "corrections.md"
COPYEDIT_CORRECTIONS = Path.home() / ".claude" / "skills" / "fakematt-copyedit" / "corrections.md"
FEEDBACK_CORRECTIONS = Path.home() / ".claude" / "skills" / "fakematt-feedback" / "corrections.md"
LAUNCH_CORRECTIONS = Path.home() / ".claude" / "skills" / "launch-announcement" / "corrections.md"


def parse_corrections(path: Path) -> list[dict]:
    """Parse a corrections.md into entries: list of {date, recipient, original, sent, diff}."""
    if not path.exists():
        return []
    text = path.read_text()
    entries = []
    # Sections are: ## YYYY-MM-DD — to <recipient> ...
    pattern = re.compile(
        r"## (\d{4}-\d{2}-\d{2}) — to (\S+).*?\n\n"
        r"\*\*Original draft:.*?\*\*\n+```\n(.*?)\n```\n+"
        r"\*\*What Matt sent:.*?\*\*\n+```\n(.*?)\n```",
        re.S,
    )
    for m in pattern.finditer(text):
        entries.append({
            "date": m.group(1),
            "recipient": m.group(2),
            "original": m.group(3).strip(),
            "sent": m.group(4).strip(),
        })
    return entries


def normalize(s: str) -> str:
    """Normalize whitespace + lowercase for pattern matching."""
    return re.sub(r"\s+", " ", s.lower()).strip()


def extract_substitutions(original: str, sent: str) -> list[tuple[str, str]]:
    """Find (removed, added) substring pairs by aligning the two texts.

    Uses SequenceMatcher to find replace ops, returns pairs where
    both sides have meaningful content.
    """
    o_lines = original.splitlines()
    s_lines = sent.splitlines()
    matcher = difflib.SequenceMatcher(None, o_lines, s_lines)
    subs = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "replace":
            removed = "\n".join(o_lines[i1:i2]).strip()
            added = "\n".join(s_lines[j1:j2]).strip()
            if 5 <= len(removed) <= 200 and 0 <= len(added) <= 200:
                subs.append((removed, added))
        elif tag == "delete":
            removed = "\n".join(o_lines[i1:i2]).strip()
            if 5 <= len(removed) <= 200:
                subs.append((removed, ""))
        elif tag == "insert":
            added = "\n".join(s_lines[j1:j2]).strip()
            if 5 <= len(added) <= 200:
                subs.append(("", added))
    return subs


def find_repeated_patterns(all_entries: list[dict], threshold: int = 3) -> list[dict]:
    """Find patterns that recur across ≥threshold distinct entries.

    Two patterns are "the same" if their normalized signatures match.
    Returns list of {signature, removed, added, count, recipients, dates}.
    """
    sig_to_occurrences = defaultdict(list)
    for entry in all_entries:
        for removed, added in extract_substitutions(entry["original"], entry["sent"]):
            # Build a signature — normalize whitespace + case so minor variation doesn't fragment counts
            sig = (normalize(removed), normalize(added))
            sig_to_occurrences[sig].append({
                "recipient": entry["recipient"],
                "date": entry["date"],
                "removed": removed,
                "added": added,
            })

    learned = []
    for (sig_removed, sig_added), occs in sig_to_occurrences.items():
        # Distinct recipients
        recipients = {o["recipient"] for o in occs}
        if len(recipients) >= threshold:
            learned.append({
                "removed": occs[0]["removed"],
                "added": occs[0]["added"],
                "count": len(occs),
                "recipient_count": len(recipients),
                "recipients": sorted(recipients),
                "dates": sorted({o["date"] for o in occs}),
            })
    learned.sort(key=lambda x: -x["recipient_count"])
    return learned


def write_learned_patterns(patterns: list[dict], threshold: int) -> None:
    today = dt.date.today().isoformat()
    LEARNED.parent.mkdir(parents=True, exist_ok=True)
    out = []
    out.append("---")
    out.append("title: Matt Eisner — Learned Voice Patterns")
    out.append("source: AUTO-GENERATED by promote.py (do not hand-edit)")
    out.append(f"updated: {today}")
    out.append(f"threshold: pattern must appear in ≥{threshold} distinct corrections to be listed here")
    out.append("---\n")
    out.append("# Learned Voice Patterns\n")
    out.append(
        "Patterns Matt has consistently applied when editing skill-generated drafts before "
        "sending. When a substitution recurs across 3+ different recipients, it crosses the "
        "promotion threshold and lands here. All voice skills load this file as an anchor on "
        "every run, so these patterns auto-influence future drafts.\n"
    )
    out.append(
        "**Do not hand-edit this file.** Add manual rules to `voice_universals.md` instead. "
        "This file is rebuilt by `promote.py` daily.\n"
    )
    if not patterns:
        out.append(f"\n## (No patterns yet)\n\nThe corrections corpus is too thin or too varied to have crossed the ≥{threshold} threshold. As Matt edits more drafts, this file will populate.\n")
    else:
        out.append(f"## {len(patterns)} promoted pattern(s)\n")
        for i, p in enumerate(patterns, 1):
            out.append(f"\n### Pattern {i} — appears in {p['recipient_count']} distinct correspondents")
            out.append(f"\n**Skill output (replace this):**\n```\n{p['removed'] or '(empty)'}\n```")
            out.append(f"\n**Matt's preferred (use this):**\n```\n{p['added'] or '(removes the line)'}\n```")
            recs_str = ", ".join(p["recipients"][:5])
            if len(p["recipients"]) > 5:
                recs_str += f", +{len(p['recipients'])-5} more"
            out.append(f"\n_Seen in: {recs_str}._\n")
    LEARNED.write_text("\n".join(out))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=int, default=3,
                    help="min distinct recipients for a pattern to be learned (default 3)")
    args = ap.parse_args()

    all_entries = (
        parse_corrections(EMAIL_CORRECTIONS)
        + parse_corrections(PERSONAL_CORRECTIONS)
        + parse_corrections(COPYEDIT_CORRECTIONS)
        + parse_corrections(FEEDBACK_CORRECTIONS)
        + parse_corrections(LAUNCH_CORRECTIONS)
    )
    print(f"[promote] {len(all_entries)} total (email + personal + copyedit + feedback + launch-announcement)")

    if not all_entries:
        print("[promote] no corrections yet — writing empty learned_patterns.md")
        write_learned_patterns([], args.threshold)
        return 0

    patterns = find_repeated_patterns(all_entries, args.threshold)
    print(f"[promote] {len(patterns)} patterns crossed threshold (≥{args.threshold} distinct correspondents)")
    write_learned_patterns(patterns, args.threshold)
    print(f"[promote] wrote {LEARNED}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
