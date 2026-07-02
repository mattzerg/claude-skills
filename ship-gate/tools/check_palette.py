#!/usr/bin/env python3
"""ship-gate dual-palette router (B4).

Per memory/feedback_zerg_brand.md the Zerg dual-palette routing rule is:

    cream     #f4f0e7   -> page canvas (Zstack / product / non-technical)
              #fffaf0   -> elevated card / inner panel on cream (paper-white sibling)
    charcoal  #111514   -> Zerg parent + technical / research / developer-facing
    burnt-orange #b3662f, green #6FBE31, Space Grotesk -> shared accents

This router takes a URL OR a local file path and answers two questions:
    1. classify  -> which palette SHOULD this surface use?
    2. audit     -> does the rendered HTML/CSS match the expected palette?

Personal sites (matteisn.com, vang.capital, vangadvisory.com) and Zerg client
case-study pages carry their own brands and are out of scope - the router
returns palette="other" for them so ship-gate can skip the check.

Usage:
    python3 check_palette.py classify <url-or-path>
    python3 check_palette.py audit    <url> [--expect cream|charcoal]

Exit codes: 0 ok / matched, 1 mismatch, 64 usage error, 70 tool error.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

CREAM = "#f4f0e7"          # page canvas
CREAM_CARD = "#fffaf0"     # elevated card / inner panel on cream (paper-white lift)
CHARCOAL = "#111514"

# (regex pattern on URL or absolute path, expected_palette, reason)
ROUTING_RULES = [
    (r"^https?://(www\.)?zergboard\.com(/|$)", "cream", "zergboard.com is a Zstack product surface"),
    (r"^https?://[^/]*\.zergboard\.com(/|$)", "cream", "zergboard subdomain inherits product palette"),
    (r"^https?://zergboard-preview\.pages\.dev(/|$)", "cream", "Zergboard preview deploy mirrors zergboard.com"),
    (r"^https?://zerglytics(-epoch)?\.fly\.dev(/|$)", "cream", "Zerglytics is a Zstack product surface"),
    # zergai.com is the Zerg PARENT brand surface — per feedback_zerg_brand.md
    # dual-palette rule, parent brand defaults to charcoal. Sub-pages that target
    # non-technical buyers (solutions, pricing if it lands here, etc.) are the
    # exception and use cream.
    (r"^https?://(www\.)?zergai\.com/(solutions|pricing|customers|case-studies)", "cream", "zergai non-technical buyer surface"),
    (r"^https?://(www\.)?zergai\.com(/|$|/blog|/docs|/research|/developers|/api)", "charcoal", "zergai parent-brand surface"),
    (r"^/Users/[^/]+/zerg/zergboard/", "cream", "local zergboard product source"),
    (r"^/Users/[^/]+/zerg/web/src/public/content/blog/.*\b(research|technical|engineering|whitepaper)\b", "charcoal", "technical blog post under zerg/web"),
    (r"^/Users/[^/]+/zerg/web/", "cream", "zerg/web marketing surface defaults to cream"),
    # personal sites + client case-studies opt out
    (r"^https?://(www\.)?matteisn\.com", "other", "personal Eisner brand"),
    (r"^https?://(www\.)?vang(capital|advisory|\.capital)", "other", "Vang brand"),
    (r"^https?://(www\.)?cesiumastro\.|^https?://(www\.)?andesite\.|^https?://(www\.)?durable\.", "other", "client surface"),
]


def classify(target: str) -> tuple[str, str]:
    for pattern, palette, reason in ROUTING_RULES:
        if re.search(pattern, target):
            return palette, reason
    return "unknown", "no routing rule matched — add one to check_palette.py"


def fetch_rendered(url: str) -> str:
    proc = subprocess.run(
        ["curl", "-sLA", "Mozilla/5.0 (compatible; ship-gate/1.0)", "--max-time", "30", url],
        capture_output=True,
        text=True,
        timeout=40,
    )
    return proc.stdout if proc.returncode == 0 else ""


def detect_dominant_bg(html: str) -> str | None:
    """Heuristic: look for *background* signals only (not text-color references).
    Looks for Tailwind `bg-[#hex]` arbitrary classes and explicit
    `background[-color]: #hex` CSS rules; ignores raw hex tokens that may live
    in text/border/icon contexts. Returns "cream", "charcoal", or None.
    """
    haystack = html.lower()
    # Cream is a TWO-HEX system on Zerg surfaces: #f4f0e7 page canvas
    # + #fffaf0 elevated-card/inner-panel paper-white sibling. Both count
    # as cream-system signals so a card-heavy page doesn't get misread.
    cream_patterns = [
        r"bg-\[\s*#f4f0e7",                                # Tailwind bg-[#f4f0e7]
        r"bg-\[\s*#fffaf0",                                # Tailwind bg-[#fffaf0] (elevated card)
        r"background(?:-color)?\s*:\s*#f4f0e7",            # CSS rule
        r"background(?:-color)?\s*:\s*#fffaf0",            # CSS rule (elevated card)
        r"background(?:-color)?\s*:\s*rgb\(\s*244\s*,\s*240\s*,\s*231",
        r"background(?:-color)?\s*:\s*rgb\(\s*255\s*,\s*250\s*,\s*240",
    ]
    charcoal_patterns = [
        r"bg-\[\s*#111514",
        r"background(?:-color)?\s*:\s*#111514",
        r"background(?:-color)?\s*:\s*rgb\(\s*17\s*,\s*21\s*,\s*20",
    ]
    cream_hits = sum(len(re.findall(p, haystack)) for p in cream_patterns)
    charcoal_hits = sum(len(re.findall(p, haystack)) for p in charcoal_patterns)
    if cream_hits == 0 and charcoal_hits == 0:
        return None
    # Many Zerg pages legitimately mix charcoal sections (CTA / hero band) with
    # a cream body. The detector cannot tell which one is the primary palette
    # from raw frequency, so any mixed-palette page returns None and requests
    # manual review rather than emitting a confident MISMATCH.
    if cream_hits > 0 and charcoal_hits > 0:
        return None
    return "cream" if cream_hits > charcoal_hits else "charcoal"


def cmd_classify(args: argparse.Namespace) -> int:
    palette, reason = classify(args.target)
    print(f"# palette — {palette.upper()}")
    print()
    print(f"**Target**: {args.target}")
    print(f"**Expected palette**: `{palette}`")
    print(f"**Reason**: {reason}")
    if palette == "cream":
        print(f"**Hex**: `{CREAM}` background, charcoal text, accents per feedback_zerg_brand.md")
    elif palette == "charcoal":
        print(f"**Hex**: `{CHARCOAL}` background, cream text, accents per feedback_zerg_brand.md")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    expected = args.expect
    if expected is None:
        expected, reason = classify(args.target)
        if expected in ("other", "unknown"):
            print(f"# palette — SKIP")
            print()
            print(f"**Target**: {args.target}")
            print(f"**Reason**: {reason}; surface is out of dual-palette scope.")
            return 0
    if not args.target.startswith("http"):
        print("audit mode requires an http(s) URL", file=sys.stderr)
        return 64
    html = fetch_rendered(args.target)
    if not html:
        print("# palette — ERROR")
        print()
        print(f"could not fetch {args.target}")
        return 70
    detected = detect_dominant_bg(html)
    if detected is None:
        print(f"# palette — UNKNOWN")
        print()
        print(f"**Target**: {args.target}")
        print(f"**Expected**: `{expected}`")
        print("Could not infer a primary palette from `bg-[...]` / `background-color:` rules.")
        print("This is normal for pages that legitimately mix cream and charcoal sections")
        print("(e.g., cream body + charcoal CTA band). Manual review required.")
        return 1
    if detected == expected:
        print(f"# palette — MATCH")
        print()
        print(f"**Target**: {args.target}")
        print(f"**Expected**: `{expected}` · **Detected**: `{detected}`")
        return 0
    print(f"# palette — MISMATCH")
    print()
    print(f"**Target**: {args.target}")
    print(f"**Expected**: `{expected}` · **Detected**: `{detected}`")
    print()
    print(f"Per memory/feedback_zerg_brand.md, this surface should render with the `{expected}` palette.")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="check_palette.py")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_classify = sub.add_parser("classify", help="print expected palette for a URL or path")
    p_classify.add_argument("target")
    p_audit = sub.add_parser("audit", help="fetch URL and verify dominant palette")
    p_audit.add_argument("target")
    p_audit.add_argument("--expect", choices=["cream", "charcoal"], default=None)
    args = parser.parse_args()
    if args.cmd == "classify":
        return cmd_classify(args)
    if args.cmd == "audit":
        return cmd_audit(args)
    return 64


if __name__ == "__main__":
    sys.exit(main())
