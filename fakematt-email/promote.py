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

ICLOUD_VAULT = Path("/Users/mattheweisner/Obsidian/Zerg/MattZerg")
LEARNED_REL = "_style/learned_patterns.md"
# Kept for log/back-compat display; actual write goes through _write_learned().
LEARNED = ICLOUD_VAULT / LEARNED_REL


def _write_learned(content: str) -> str:
    """Write learned_patterns.md so it durably lands in the CANONICAL iCloud vault.

    Interactive context: direct iCloud write works (TCC allows).
    Cron/launchd context: direct write raises PermissionError → stage via
    vault_path.vault_write(); the vault_flush LaunchAgent (FDA-bearing,
    every 60s) lands it in iCloud, and vault_mirror then syncs iCloud→mirror.

    NEVER write the mirror directly: vault_mirror's one-way iCloud→mirror
    sync reverts mirror-side writes within 15 minutes. That was the bug that
    kept learned_patterns.md frozen at 2026-05-08 (fixed 2026-06-03).
    """
    target = ICLOUD_VAULT / LEARNED_REL
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return str(target)
    except (PermissionError, OSError):
        sys.path.insert(0, str(Path.home() / ".config" / "zerg"))
        from vault_path import vault_write
        staged = vault_write(LEARNED_REL, content)
        return f"{staged} (staged → vault_flush lands it in iCloud within ~60s)"


EMAIL_CORRECTIONS = Path.home() / ".claude" / "skills" / "fakematt-email" / "corrections.md"
PERSONAL_CORRECTIONS = Path.home() / ".claude" / "skills" / "fakematt-personal" / "corrections.md"
COPYEDIT_CORRECTIONS = Path.home() / ".claude" / "skills" / "fakematt-copyedit" / "corrections.md"
FEEDBACK_CORRECTIONS = Path.home() / ".claude" / "skills" / "fakematt-feedback" / "corrections.md"
LAUNCH_CORRECTIONS = Path.home() / ".claude" / "skills" / "launch-announcement" / "corrections.md"
SLACK_CORRECTIONS = Path.home() / ".claude" / "skills" / "fakematt-slack" / "corrections.md"

# Prose-mined rules (from mine_prose.py, LLM-extracted).
EXTRACTED_FILES = [
    Path.home() / ".claude" / "skills" / s / "corrections.extracted.md"
    for s in ("fakematt-email", "fakematt-personal", "fakematt-copyedit",
              "fakematt-feedback", "launch-announcement", "fakematt-slack")
]


def parse_corrections(path: Path) -> list[dict]:
    """Parse a corrections.md into entries: list of {date, recipient, original, sent, diff}."""
    if not path.exists():
        return []
    text = path.read_text()
    entries = []
    # Sections are: ## YYYY-MM-DD — to <recipient> ...
    # "Original draft" label is matched loosely: learn.py historically wrote
    # "**Original draft (skill output):**" while fm_corrected.py writes
    # "**Original draft:**" — both must parse.
    pattern = re.compile(
        r"## (\d{4}-\d{2}-\d{2}) — to (\S+).*?\n\n"
        r"\*\*Original draft[^*\n]*\*\*\n+```\n(.*?)\n```\n+"
        r"\*\*What Matt sent[^*\n]*\*\*\n+```\n(.*?)\n```",
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


def find_repeated_patterns(
    all_entries: list[dict],
    recipient_threshold: int = 3,
    occurrence_threshold: int = 4,
) -> list[dict]:
    """Find patterns crossing one of two promotion thresholds.

    A pattern promotes if EITHER:
      - it appears in ≥recipient_threshold distinct recipients
        (broad signal — Matt prefers X across the board), OR
      - it occurs ≥occurrence_threshold times total
        (narrow but strong signal — repeat edits to the same correspondent).

    Each pattern is tagged with which rule fired so the file stays auditable.
    """
    sig_to_occurrences = defaultdict(list)
    for entry in all_entries:
        for removed, added in extract_substitutions(entry["original"], entry["sent"]):
            sig = (normalize(removed), normalize(added))
            sig_to_occurrences[sig].append({
                "recipient": entry["recipient"],
                "date": entry["date"],
                "removed": removed,
                "added": added,
            })

    learned = []
    for (_sig_r, _sig_a), occs in sig_to_occurrences.items():
        recipients = {o["recipient"] for o in occs}
        rule = None
        if len(recipients) >= recipient_threshold:
            rule = "cross-recipient"
        elif len(occs) >= occurrence_threshold:
            rule = "high-frequency"
        if not rule:
            continue
        learned.append({
            "removed": occs[0]["removed"],
            "added": occs[0]["added"],
            "count": len(occs),
            "recipient_count": len(recipients),
            "recipients": sorted(recipients),
            "dates": sorted({o["date"] for o in occs}),
            "rule": rule,
        })
    # Sort: cross-recipient first (broader signal), then by recipient count, then total count
    learned.sort(key=lambda x: (0 if x["rule"] == "cross-recipient" else 1,
                                -x["recipient_count"], -x["count"]))
    return learned


def collect_prose_mined() -> str:
    """Concatenate all skill `corrections.extracted.md` bodies (skipping their
    YAML frontmatter + lead title) into a single section."""
    blocks = []
    for path in EXTRACTED_FILES:
        if not path.exists() or path.stat().st_size < 200:
            continue
        text = path.read_text()
        # Drop YAML frontmatter
        text = re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.S)
        # Drop the lead "# Prose-mined Voice Rules" + intro paragraph
        text = re.sub(r"^# Prose-mined Voice Rules\n.*?(?=^## )", "", text, count=1, flags=re.S | re.M)
        skill_label = path.parent.name.replace("fakematt-", "").replace("-", " ")
        blocks.append(f"### From `{skill_label}`\n\n{text.strip()}\n")
    return "\n".join(blocks)


def write_learned_patterns(patterns: list[dict], rec_threshold: int, occ_threshold: int) -> str:
    today = dt.date.today().isoformat()
    out = []
    out.append("---")
    out.append("title: Matt Eisner — Learned Voice Patterns")
    out.append("source: AUTO-GENERATED by promote.py (do not hand-edit)")
    out.append(f"updated: {today}")
    out.append(f"thresholds: ≥{rec_threshold} distinct recipients OR ≥{occ_threshold} total occurrences")
    out.append("---\n")
    out.append("# Learned Voice Patterns\n")
    out.append(
        "Patterns Matt has consistently applied when editing skill-generated drafts before "
        "sending. A pattern promotes when EITHER it appears across "
        f"≥{rec_threshold} distinct recipients (broad signal) OR it occurs "
        f"≥{occ_threshold} times in total (narrow but strong signal). All voice skills "
        "load this file as an anchor on every run.\n"
    )
    out.append(
        "**Do not hand-edit this file.** Add manual rules to `voice_universals.md` instead. "
        "This file is rebuilt by `promote.py` daily.\n"
    )
    if not patterns:
        out.append(
            f"\n## (No diff-mined patterns yet)\n\nThe corrections corpus hasn't crossed the "
            f"≥{rec_threshold} distinct recipients OR ≥{occ_threshold} total occurrences "
            "threshold. As Matt edits more drafts, this section will populate.\n"
        )
    else:
        out.append(f"## Diff-mined patterns ({len(patterns)} promoted)\n")
        for i, p in enumerate(patterns, 1):
            tag = ("cross-recipient" if p["rule"] == "cross-recipient"
                   else "high-frequency single-recipient")
            out.append(
                f"\n### Pattern {i} — {tag}: "
                f"{p['recipient_count']} recipient(s), {p['count']} occurrence(s)"
            )
            out.append(f"\n**Skill output (replace this):**\n```\n{p['removed'] or '(empty)'}\n```")
            out.append(f"\n**Matt's preferred (use this):**\n```\n{p['added'] or '(removes the line)'}\n```")
            recs_str = ", ".join(p["recipients"][:5])
            if len(p["recipients"]) > 5:
                recs_str += f", +{len(p['recipients'])-5} more"
            out.append(f"\n_Seen in: {recs_str}._\n")

    # Append prose-mined rules from mine_prose.py output (richer, captures the WHY)
    prose = collect_prose_mined()
    if prose:
        out.append("\n## Prose-mined rules (LLM-extracted from hand-written corrections)\n")
        out.append(prose)

    return _write_learned("\n".join(out))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipient-threshold", type=int, default=3,
                    help="distinct recipients needed for cross-recipient promotion (default 3)")
    ap.add_argument("--occurrence-threshold", type=int, default=4,
                    help="total occurrences needed for high-frequency promotion (default 4)")
    # Back-compat: --threshold maps to recipient-threshold
    ap.add_argument("--threshold", type=int, default=None, help=argparse.SUPPRESS)
    args = ap.parse_args()

    rec_t = args.threshold if args.threshold is not None else args.recipient_threshold
    occ_t = args.occurrence_threshold

    all_entries = (
        parse_corrections(EMAIL_CORRECTIONS)
        + parse_corrections(PERSONAL_CORRECTIONS)
        + parse_corrections(COPYEDIT_CORRECTIONS)
        + parse_corrections(FEEDBACK_CORRECTIONS)
        + parse_corrections(LAUNCH_CORRECTIONS)
        + parse_corrections(SLACK_CORRECTIONS)
    )
    print(f"[promote] {len(all_entries)} total (email + personal + copyedit + feedback + launch-announcement + slack)")

    if not all_entries:
        print("[promote] no corrections yet — writing empty learned_patterns.md")
        wrote = write_learned_patterns([], rec_t, occ_t)
        print(f"[promote] wrote {wrote}")
        return 0

    patterns = find_repeated_patterns(all_entries, rec_t, occ_t)
    cross = sum(1 for p in patterns if p["rule"] == "cross-recipient")
    freq = sum(1 for p in patterns if p["rule"] == "high-frequency")
    print(f"[promote] {len(patterns)} promoted ({cross} cross-recipient ≥{rec_t}, {freq} high-frequency ≥{occ_t})")
    wrote = write_learned_patterns(patterns, rec_t, occ_t)
    print(f"[promote] wrote {wrote}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
