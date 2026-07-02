#!/usr/bin/env python3
"""Log a 👍/👎 on a recommendation → recs-feedback.jsonl (the learning signal).
Usage: feedback.py "<rec text or keyword>" up|down [note]
Next `personal-recs refresh` reads this and downweights 👎 patterns, leans into 👍.
"""
import sys, os, json, datetime

LOG = os.path.expanduser(
    "~/Obsidian/MHE/Personal/Taste-Archive/recs-feedback.jsonl")


def main():
    if len(sys.argv) < 3 or sys.argv[2] not in ("up", "down"):
        print('usage: feedback.py "<rec>" up|down [note]')
        sys.exit(1)
    rec, rating = sys.argv[1], sys.argv[2]
    note = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else ""
    # date passed in env to stay deterministic-friendly; else today
    stamp = os.environ.get("FEEDBACK_DATE") or datetime.date.today().isoformat()
    row = {"date": stamp, "rec": rec, "rating": rating, "note": note}
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    n = sum(1 for _ in open(LOG, encoding="utf-8"))
    print(f"logged {rating} on: {rec}  ({n} total ratings)")


if __name__ == "__main__":
    main()
