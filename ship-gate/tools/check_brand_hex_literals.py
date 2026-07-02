#!/usr/bin/env python3
"""ship-gate brand-hex literal regression check.

After the 2026-05-11 codemod sweep (commit c90e0f3a on Epoch-ML/zerg),
named Tailwind tokens replaced every `bg-[#brand-hex]` arbitrary-class
literal in src/. This tool flags regression: any new commit that adds
back an inline brand-hex literal in a Tailwind utility class context.

Pairs with check_palette.py (palette routing) and the named tokens
declared in ~/zerg/web/tailwind.colors.js + the brand-tokens.md contract.

Tailwind utility prefixes scanned:
    bg | text | border | fill | stroke | ring | divide | placeholder |
    accent | caret | decoration | from | to | via | outline | shadow

Brand hexes flagged (case-insensitive):
    #f4f0e7  →  bg-cream            cream page canvas
    #fffaf0  →  bg-cream-100        cream elevated card
    #111514  →  bg-charcoal /text-  charcoal canvas + body text
    #8a4a1f  →  text-burnt-orange-500  AA-on-cream rust labels
    #d57a32  →  bg-burnt-orange-300    bright accent on charcoal
    #6FBE31  →  bg-green / text-green  brand-green (existing token)

Also flags bare Tailwind DEFAULT-name regressions for the off-brand
DEFAULTs removed 2026-05-11 (PRs A–F). These would now break the
Tailwind build since the DEFAULT key is gone from tailwind.colors.js:
    bg-red      →  use bg-red-600 (or specific numeric)
    bg-slate    →  use bg-slate-800
    bg-yellow   →  use bg-burnt-orange-300/500 (marketing) or bg-yellow-400 (admin)
    bg-teal     →  use bg-cream-100 (or specific numeric if intended)
    bg-blue     →  use bg-cyan-200 (or specific numeric)
    bg-accent-dark → use bg-burnt-orange-500

Usage:
    python3 check_brand_hex_literals.py <path-or-file> [...]
    python3 check_brand_hex_literals.py --diff <base>            # check git diff <base>...HEAD
    python3 check_brand_hex_literals.py --diff-staged             # check git diff --cached

Exit codes:
    0  no brand-hex literals found
    1  brand-hex literals found (regression)
    64 usage error
    70 tool error
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

# Tailwind utility prefixes that take a color argument.
UTILS = "bg|text|border|fill|stroke|ring|divide|placeholder|accent|caret|decoration|from|to|via|outline|shadow"

# (hex regex case-insensitive, named-token replacement, intent)
BRAND_HEXES = [
    (r"f4f0e7", "bg-cream / text-cream",                  "cream page canvas"),
    (r"fffaf0", "bg-cream-100 / text-cream-100",          "cream elevated card"),
    (r"111514", "bg-charcoal / text-charcoal",            "charcoal canvas + body text"),
    (r"8a4a1f", "text-burnt-orange-500",                  "AA-on-cream rust labels"),
    (r"d57a32", "bg-burnt-orange-300",                    "bright accent on charcoal"),
    (r"6fbe31", "bg-green / text-green",                  "brand-green (existing Tailwind token)"),
]

# File extensions that can contain Tailwind utility classes
SCAN_EXTS = {".vue", ".ts", ".tsx", ".js", ".jsx", ".scss", ".css", ".html"}

# Bare Tailwind DEFAULT-name color tokens that were REMOVED from
# tailwind.colors.js on 2026-05-11 (PRs A–F). Components reaching for
# these bare names would now fail Tailwind compilation (or render as
# undefined → fallback to inherit). Use the explicit-numeric / brand-
# token replacements documented in MattZerg/Projects/Zerg-Production/Zstack/brand-tokens.md.
BARE_DEFAULT_REPLACEMENTS = [
    ("red",         "red-600",                       "PR A — red.DEFAULT #cc1d3e removed"),
    ("slate",       "slate-800",                     "PR C — slate.DEFAULT #1a2730 removed"),
    ("yellow",      "burnt-orange-300/500 OR yellow-400",
                                                     "PR B — yellow.DEFAULT #f3c901 removed"),
    ("teal",        "cream-100",                     "PR F — teal.DEFAULT #74B9C3 removed"),
    ("blue",        "cyan-200",                      "PR E — blue.DEFAULT #94F5FB removed"),
    ("accent-dark", "burnt-orange-500",              "PR D — accent-dark #eab308 removed"),
]


def find_hits_in_text(text: str) -> list[tuple[int, str, str, str, str]]:
    """Return list of (line_number, hex_token, util_class, named_replacement, intent)."""
    hits = []
    # 1. Brand-hex Tailwind literals (e.g. bg-[#f4f0e7])
    for hex_pat, replacement, intent in BRAND_HEXES:
        pat = re.compile(
            rf"\b({UTILS})-\[#{hex_pat}\](/\d+)?",
            re.IGNORECASE,
        )
        for m in pat.finditer(text):
            line_no = text.count("\n", 0, m.start()) + 1
            hits.append((line_no, hex_pat, m.group(0), replacement, intent))
    # 2. Bare DEFAULT-name color tokens that no longer exist
    #    Use `(?![\w-])` lookahead (not `\b`) to avoid false-positive on
    #    multi-word classes like `bg-blue-gr` (a backgroundImage utility).
    for token_name, replacement, intent in BARE_DEFAULT_REPLACEMENTS:
        pat = re.compile(
            rf"(?<![\w-])((?:[a-z-]+:)?(?:{UTILS}))-{re.escape(token_name)}(?![\w-])((?:/\d+)?)",
        )
        for m in pat.finditer(text):
            line_no = text.count("\n", 0, m.start()) + 1
            util_class = m.group(0)
            hits.append((line_no, token_name, util_class, f"<util>-{replacement}", intent))
    return hits


def scan_file(path: Path) -> list[tuple[int, str, str, str, str]]:
    if path.suffix.lower() not in SCAN_EXTS:
        return []
    # Skip stash/backup files — they exist to NOT be migrated.
    if ".backup_" in path.name or path.name.endswith(".orig"):
        return []
    try:
        text = path.read_text(errors="ignore")
    except Exception:
        return []
    return find_hits_in_text(text)


def collect_paths(targets: list[str]) -> list[Path]:
    out = []
    for t in targets:
        p = Path(t)
        if p.is_file():
            out.append(p)
        elif p.is_dir():
            out.extend(q for q in p.rglob("*") if q.is_file() and q.suffix.lower() in SCAN_EXTS)
    return out


def diff_changed_files(base: str | None, staged: bool) -> list[Path]:
    if staged:
        cmd = ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"]
    else:
        if not base:
            print("--diff requires a base ref", file=sys.stderr)
            sys.exit(64)
        cmd = ["git", "diff", "--name-only", "--diff-filter=AM", f"{base}...HEAD"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"git diff failed: {e.stderr}", file=sys.stderr)
        sys.exit(70)
    paths = []
    for line in proc.stdout.splitlines():
        p = Path(line.strip())
        if p.is_file() and p.suffix.lower() in SCAN_EXTS:
            paths.append(p)
    return paths


def emit_finding(file_hits: dict[Path, list]) -> None:
    """Print markdown finding block in ship-gate convention."""
    total = sum(len(v) for v in file_hits.values())
    print("# brand-hex literals — REGRESSION")
    print()
    print(f"**{total} inline `<util>-[#brand-hex]` Tailwind literal(s) found** across "
          f"{len(file_hits)} file(s). Use the named brand token instead per "
          f"`MattZerg/Projects/Zerg-Production/Zstack/brand-tokens.md`.")
    print()
    for path, hits in sorted(file_hits.items()):
        print(f"## `{path}`")
        print()
        print("| Line | Found | Use instead | Intent |")
        print("|---|---|---|---|")
        for line_no, _hex, util_class, replacement, intent in hits:
            print(f"| {line_no} | `{util_class}` | `{replacement}` | {intent} |")
        print()
    print("## Fix")
    print()
    print("```bash")
    print("# automated:")
    print("python3 /tmp/brand-codemod.py <file>...")
    print("# or hand-edit per the table above.")
    print("```")
    print()
    print("Then re-run this check to confirm clean.")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="check_brand_hex_literals.py",
        description="Flag inline brand-hex Tailwind class literals on Zerg marketing surfaces.",
    )
    parser.add_argument("paths", nargs="*", help="files or directories to scan")
    parser.add_argument("--diff", metavar="BASE", help="scan files changed in `git diff BASE...HEAD`")
    parser.add_argument("--diff-staged", action="store_true", help="scan files staged for commit")
    args = parser.parse_args()

    if args.diff or args.diff_staged:
        paths = diff_changed_files(args.diff, args.diff_staged)
    elif args.paths:
        paths = collect_paths(args.paths)
    else:
        parser.print_help(sys.stderr)
        return 64

    file_hits: dict[Path, list] = {}
    for p in paths:
        hits = scan_file(p)
        if hits:
            file_hits[p] = hits

    if not file_hits:
        print("# brand-hex literals — CLEAN")
        print()
        print(f"Scanned {len(paths)} file(s); 0 brand-hex Tailwind literal(s) found.")
        return 0

    emit_finding(file_hits)
    return 1


if __name__ == "__main__":
    sys.exit(main())
