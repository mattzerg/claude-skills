#!/usr/bin/env python3
"""One rotating cross-domain 'today's pick' from recommendations.md.
Date-seeded so it's stable within a day, rotates across days.
Morning-brief snippet (add to the brief assembly):
    pick=$(python3 ~/.claude/skills/personal-recs/daily_pick.py); echo "🎯 Today's pick: $pick"
"""
import os, re, datetime, hashlib

RECS = os.path.expanduser(
    "~/Obsidian/MHE/Personal/Taste-Archive/recommendations.md")


def load_recs():
    if not os.path.exists(RECS):
        return []
    out = []
    for line in open(RECS, encoding="utf-8"):
        m = re.match(r"\s*-\s+\*\*(.+?)\*\*\s*(.*)", line)
        if m:
            title = m.group(1).strip()
            why = re.sub(r"\s+", " ", m.group(2)).strip().lstrip("—-– ")
            if title and "request the spotify" not in title.lower():
                out.append((title, why[:160]))
    return out


def main():
    recs = load_recs()
    if not recs:
        print("(no recommendations yet — run personal-recs recommend)")
        return
    # date-seeded rotation: stable per day, cycles through the list
    day = datetime.date.today().isoformat()
    idx = int(hashlib.md5(day.encode()).hexdigest(), 16) % len(recs)
    title, why = recs[idx]
    print(f"{title}" + (f" — {why}" if why else ""))


if __name__ == "__main__":
    main()
