#!/usr/bin/env python3
"""Voice infrastructure health check.

Single one-shot status reporter for the whole fakematt-* voice system. Run
it manually for a snapshot, or wire it into a daily cron + Slack post if you
want a recurring health beacon.

Reports:
  - Corpus freshness (last gmail_id timestamp in each corpus)
  - tier_map size + auto-classified additions count
  - sent-log size + unchecked records (for both email + personal)
  - corrections.md size + most-recent entry date
  - Last cron run timestamps (refresh / learn / smoke) per skill
  - Anchor file existence (universals + voice docs)

Usage:
    python3 ~/.claude/skills/fakematt-email/voice_status.py
"""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
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
EMAIL_SKILL = Path.home() / ".claude" / "skills" / "fakematt-email"
PERSONAL_SKILL = Path.home() / ".claude" / "skills" / "fakematt-personal"


def file_age(p: Path) -> str:
    if not p.exists():
        return "MISSING"
    age = dt.datetime.now() - dt.datetime.fromtimestamp(p.stat().st_mtime)
    days, sec = age.days, age.seconds
    if days > 0: return f"{days}d ago"
    h, m = sec // 3600, (sec % 3600) // 60
    if h > 0: return f"{h}h{m}m ago"
    return f"{m}m ago"


def corpus_last_id_date(corpus: Path) -> str:
    if not corpus.exists():
        return "MISSING"
    text = corpus.read_text()
    # Look for the last `## ... | YYYY-MM-DD` header
    matches = re.findall(r"## To .+\|\s*(\w+,?\s+\d+\s+\w+\s+\d{4})", text)
    if matches:
        return matches[-1]
    return "(no dated entries)"


def jsonl_stats(p: Path) -> tuple[int, int]:
    """Return (total, unchecked)."""
    if not p.exists():
        return 0, 0
    total = unchecked = 0
    with open(p) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                r = json.loads(line)
                total += 1
                if not r.get("checked"):
                    unchecked += 1
            except Exception:
                pass
    return total, unchecked


def tier_map_stats(p: Path) -> tuple[int, int, int, int]:
    """Return (A_count, B_count, C_count, auto_classified_count)."""
    if not p.exists():
        return (0, 0, 0, 0)
    with open(p) as f:
        m = json.load(f)
    counts = {}
    autos = 0
    for r in ("A", "B", "C"):
        counts[r] = len(m.get(r, {}).get("members", []))
        autos += len(m.get(r, {}).get("_autoclassified", {}))
    return counts["A"], counts["B"], counts["C"], autos


def main() -> int:
    print("=" * 60)
    print(f"VOICE INFRASTRUCTURE STATUS  {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Anchor files
    print("\n## Anchor files")
    for p, label in [
        (VAULT / "_style" / "voice_universals.md", "voice_universals.md"),
        (VAULT / "_style" / "professional_voice.md", "professional_voice.md"),
        (VAULT / "_style" / "personal_voice.md", "personal_voice.md"),
        (VAULT / "_style" / "subject_patterns.md", "subject_patterns.md"),
        (VAULT / "_style" / "writing_style.md", "writing_style.md"),
    ]:
        size = p.stat().st_size if p.exists() else 0
        print(f"  {label:<32} {size:>6}b   updated {file_age(p)}")

    # Corpora
    print("\n## Corpora")
    for p, label in [
        (VAULT / "_style" / "professional_voice_corpus.md", "professional"),
        (VAULT / "_style" / "personal_voice_corpus.md", "personal"),
    ]:
        if p.exists():
            text = p.read_text()
            count = text.count("## To ")
            last = corpus_last_id_date(p)
            print(f"  {label:<14} {count:>3} samples   last entry: {last}   updated {file_age(p)}")
        else:
            print(f"  {label:<14} MISSING")

    # Tier map
    print("\n## tier_map.json")
    a, b, c, auto = tier_map_stats(EMAIL_SKILL / "tier_map.json")
    print(f"  A (formal-warm): {a}")
    print(f"  B (mid-casual):  {b}")
    print(f"  C (casual-pro):  {c}")
    print(f"  auto-classified: {auto}")

    # sent-log + corrections per skill
    for skill_dir, label in [(EMAIL_SKILL, "email"), (PERSONAL_SKILL, "personal")]:
        print(f"\n## {label} skill")
        sl = skill_dir / "sent-log.jsonl"
        cor = skill_dir / "corrections.md"
        total, unchecked = jsonl_stats(sl)
        print(f"  sent-log:    {total} total, {unchecked} unchecked   ({file_age(sl)})")
        if cor.exists():
            cor_size = cor.stat().st_size
            text = cor.read_text()
            entries = len(re.findall(r"^## \d{4}-\d{2}-\d{2} —", text, re.M))
            print(f"  corrections: {entries} entries, {cor_size}b   updated {file_age(cor)}")
        else:
            print(f"  corrections: (none yet)")
        # log files
        log_dir = skill_dir / "logs"
        if log_dir.exists():
            for log_name in ("refresh.log", "learn.log", "smoke.log"):
                lp = log_dir / log_name
                if lp.exists():
                    print(f"  logs/{log_name:<12} {file_age(lp)}")
                else:
                    print(f"  logs/{log_name:<12} not yet run")

    # Cron entries
    print("\n## Crons")
    try:
        out = subprocess.check_output(["crontab", "-l"], text=True)
        for line in out.split("\n"):
            if "fakematt-" in line and "skills" in line:
                print(f"  {line.strip()[:100]}")
    except Exception as e:
        print(f"  (crontab read failed: {e})")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
