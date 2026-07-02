#!/usr/bin/env python3
"""
caption_lint.py — pre-approval lint for Detroit-hub (and any curation-hub) captions.

Implements the anti-patterns from MattZerg/Projects/detroit-hub/voice/caption-patterns.md.
Returns JSON with score, ok, findings. Rejects (ok=false) below threshold.

Usage:
    echo "🔥🔥🔥 incredible night" | caption_lint.py
    caption_lint.py --file path/to/draft.txt
    caption_lint.py --text "tag a friend who needs this"

Exit codes:
    0 — pass (no findings, or score >= threshold)
    1 — fail (score < threshold OR explicit hard-block pattern matched)
    2 — usage error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_THRESHOLD = 70

# Each rule: (id, severity, regex/match, finding-string, points-deducted)
# severities: HARD (auto-fail regardless of score), HIGH (-25), MED (-15), LOW (-7)

RULES: list[tuple[str, str, str, str, int]] = [
    # HARD BLOCKS — auto-fail, regardless of total score
    ("emoji-bait-fire", "HARD",
     r"(🔥\s*){3,}",
     "Triple-or-more 🔥 — generic emoji-bait", 100),
    ("slaps", "HARD",
     r"\b(this\s+(track|set|tune|mix)?\s*slaps)\b",
     "'this slaps' — generic engagement filler", 100),
    ("tag-a-friend", "HARD",
     r"\btag\s+a\s+friend\b",
     "'tag a friend' — engagement-bait", 100),
    ("name-a-better", "HARD",
     r"\bname\s+a\s+better\b",
     "'name a better' — engagement-bait", 100),
    ("comment-below", "HARD",
     r"\bcomment\s+(below|your)\b",
     "'comment below' / 'comment your' — engagement-bait", 100),
    ("drop-a-x", "HARD",
     r"\bdrop\s+a\s+(🎵|🔥|💯|👇)",
     "'drop a [emoji]' — engagement-bait", 100),
    ("pov-framing", "HARD",
     r"\bPOV:\s",
     "'POV:' framing — TikTok grammar import", 100),
    ("clickbait-nobody-talks", "HARD",
     r"\bnobody\s+(talks|knows|tells)\s+(about|you)\b",
     "'nobody talks/knows/tells about' — clickbait framing", 100),
    ("clickbait-real-reason", "HARD",
     r"\bthe\s+real\s+reason\b",
     "'the real reason' — clickbait framing", 100),
    ("clickbait-they-dont", "HARD",
     r"\bwhat\s+they\s+don'?t\s+(tell|want|show)\b",
     "'what they don't tell/want/show' — clickbait framing", 100),
    ("narrate-image-photo", "HARD",
     r"^(here'?s\s+a\s+photo\s+of|this\s+is\s+a\s+photo\s+of)",
     "Caption narrates the image", 100),
    ("narrate-image-when", "HARD",
     r"^(this\s+is\s+when|here'?s\s+when)\b",
     "Caption narrates the image ('this is when…')", 100),

    # HIGH (-25)
    ("hashtag-wall", "HIGH",
     r"(#\w+\s*){6,}",
     "6+ hashtags — hashtag wall (algo deprioritized in 2026)", 25),
    ("emoji-pile", "HIGH",
     r"([\U0001F300-\U0001F9FF☀-➿]\s*){5,}",
     "5+ consecutive emojis — emoji pile", 25),
    ("all-caps-shout", "HIGH",
     r"\b[A-Z]{4,}\s+[A-Z]{4,}\b",
     "Multiple all-caps words in a row — shouty emphasis (skip; lineups OK)", 25),
    ("festival-mush", "HIGH",
     r"\b(RAGED|UNREAL|INSANE|FIRE|LIT|VIBES?\s+ONLY|MOOD)\b",
     "Festival-influencer mush vocabulary", 25),

    # MED (-15)
    ("hashtag-mid", "MED",
     r"(#\w+\s*){3,5}",
     "3-5 hashtags — keep <3, prefer caption keywords", 15),
    ("emoji-mid", "MED",
     r"([\U0001F300-\U0001F9FF☀-➿]\s*){3,4}",
     "3-4 consecutive emojis — drop to 1-2", 15),
    ("crew-without-context", "MED",
     r"\b(our\s+crew|the\s+team|the\s+squad)\b",
     "'our crew/the team/the squad' — only after account has earned a 'we'", 15),
    ("yall", "MED",
     r"\by'?all\b",
     "'y'all' — not the register for this account", 15),

    # LOW (-7)
    ("multi-sentence-short", "LOW",
     None,  # handled in code: short caption with 3+ sentences
     "Multi-sentence on a short post — one sentence usually wins", 7),
    ("trailing-cta", "LOW",
     r"\b(link\s+in\s+bio|swipe\s+up|tap\s+the\s+link)\b",
     "Generic trailing CTA — use a specific reason instead", 7),
]


def lint(text: str, threshold: int = DEFAULT_THRESHOLD) -> dict:
    findings: list[dict] = []
    score = 100
    hard_blocked = False

    text_norm = text.strip()
    lower = text_norm.lower()

    for rule_id, severity, pattern, msg, deduct in RULES:
        if pattern is None:
            # multi-sentence-short — heuristic
            if rule_id == "multi-sentence-short":
                if len(text_norm) <= 120:
                    # count sentence terminators
                    n = len(re.findall(r"[.!?]\s+\w|[.!?]$", text_norm))
                    if n >= 3:
                        findings.append({
                            "rule": rule_id, "severity": severity, "message": msg
                        })
                        score -= deduct
            continue

        flags = re.IGNORECASE if rule_id not in {"all-caps-shout", "festival-mush"} else 0
        if re.search(pattern, text_norm, flags):
            findings.append({
                "rule": rule_id, "severity": severity, "message": msg
            })
            if severity == "HARD":
                hard_blocked = True
            else:
                score -= deduct

    score = max(0, score)
    ok = (not hard_blocked) and (score >= threshold)

    return {
        "ok": ok,
        "score": score,
        "threshold": threshold,
        "hard_blocked": hard_blocked,
        "findings": findings,
        "char_count": len(text_norm),
        "word_count": len(text_norm.split()),
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Detroit hub caption lint")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--file", type=Path, help="Read caption from file")
    g.add_argument("--text", help="Caption text inline")
    p.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD)
    p.add_argument("--quiet", action="store_true", help="JSON only, no human-readable")
    args = p.parse_args()

    if args.file:
        text = args.file.read_text()
    elif args.text:
        text = args.text
    else:
        text = sys.stdin.read()

    result = lint(text, threshold=args.threshold)

    if args.quiet:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(result, indent=2))
        if not result["ok"]:
            if result["hard_blocked"]:
                print(f"\n❌ HARD BLOCK — {len([f for f in result['findings'] if f['severity']=='HARD'])} blocker(s)", file=sys.stderr)
            else:
                print(f"\n❌ score {result['score']} < threshold {result['threshold']}", file=sys.stderr)
        else:
            print(f"\n✅ score {result['score']} — pass", file=sys.stderr)

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
