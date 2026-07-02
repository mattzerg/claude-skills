#!/usr/bin/python3
"""mhe_simple_ingest: rule-based ingest of MHE vault files.

LLM extraction is currently rate-limited on Max OAuth (429s on every call).
This script captures one candidate idea per non-trivial MHE file as a
placeholder in `_inbox/`. Each entry preserves the file content as
verbatim source excerpt so triage can promote / kill / merge fast.

Heuristic category assignment:
  Path includes "Shopping List"          → shopping
  Path includes "To Read|To Watch|To Listen" → shopping (acquisition list)
  Path includes "Personal/" or "Knowledge/"  → personal-life
  Path includes "Work/" or "Vang/"           → research (client/work notes)
  Path includes "Crypto/"                    → research
  Title keywords (recipe, food, travel...)   → personal-life
  Title keywords (bagel, biz, real estate)   → personal-venture
  Default                                    → personal-life

Skips files that look like password/credential dumps (long alphanumeric
strings dominate) or are <80 chars.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "_lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from frontmatter import write_file  # noqa: E402
from idea_io import default_meta, today_iso  # noqa: E402
from slugify import slugify  # noqa: E402
from usage import log_event  # noqa: E402
from vault_paths import INBOX_DIR, MHE_VAULT_ROOT, SCAN_EXCLUDE_DIRS  # noqa: E402

MIN_CHARS = 80
MAX_EXCERPT = 1000


def looks_like_creds(body: str) -> bool:
    """True if body is dominated by alphanumeric tokens that look like passwords."""
    lines = [l.strip() for l in body.splitlines() if l.strip()]
    if not lines:
        return False
    cred_like = 0
    for l in lines:
        # Strings 8-40 chars, mostly alphanumeric, no whitespace
        if 8 <= len(l) <= 40 and re.fullmatch(r"[A-Za-z0-9!@#$%^&*()_\-+=]+", l):
            cred_like += 1
    return cred_like >= max(3, len(lines) // 2)


def classify(rel_path: str, title: str, body: str) -> tuple[str, list[str]]:
    """Returns (category, tags)."""
    rp = rel_path.lower()
    t = title.lower()
    b = body.lower()
    tags: list[str] = ["mhe"]

    if "shopping list" in rp or "shopping list" in t:
        return "shopping", tags + ["list"]
    if any(s in rp for s in ("to read.md", "to watch.md", "to listen.md", "to read ", "to watch ", "to listen ")):
        return "shopping", tags + ["list"]
    if rp.startswith("work/") or "vang/" in rp:
        return "research", tags + ["work-history"]
    if rp.startswith("crypto/"):
        return "research", tags + ["crypto"]
    if rp.startswith("personal/") or rp.startswith("knowledge/"):
        return "personal-life", tags + ["mhe-personal"]
    # Title-keyword venture
    if re.search(r"\b(bagel|electrician|slumlord|side.?biz|small.?business|real.?estate|side.?hustle)\b", t, re.IGNORECASE):
        return "personal-venture", tags + ["venture"]
    # Title-keyword travel/food/hobby
    if re.search(r"\b(recipe|food|travel|trip|hobby|fitness|workout|meal|cdmx|berlin|tokyo)\b", t, re.IGNORECASE):
        return "personal-life", tags + ["lifestyle"]
    return "personal-life", tags


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    walked = skipped_short = skipped_creds = ingested = 0
    if not MHE_VAULT_ROOT.exists():
        print(f"MHE vault not found at {MHE_VAULT_ROOT}", file=sys.stderr)
        return 2

    written: list[Path] = []

    for p in sorted(MHE_VAULT_ROOT.rglob("*.md")):
        rel = p.relative_to(MHE_VAULT_ROOT)
        if any(part in SCAN_EXCLUDE_DIRS for part in rel.parts):
            continue
        if not p.is_file():
            continue
        walked += 1
        try:
            body = p.read_text(errors="replace")
        except Exception:
            continue
        if len(body.strip()) < MIN_CHARS:
            skipped_short += 1
            continue
        if looks_like_creds(body):
            skipped_creds += 1
            continue
        title = p.stem  # use filename as title
        cat, tags = classify(str(rel), title, body)

        excerpt = body.strip()
        if len(excerpt) > MAX_EXCERPT:
            excerpt = excerpt[:MAX_EXCERPT].rstrip() + " […]"

        meta = default_meta(
            title=title,
            category=cat,
            subcategory="mhe-vault",
            tags=tags,
            status="raw",
            sources=[f"[[MHE/{rel}]]"],
        )
        body_md = (
            "## Idea\n"
            "(Captured from MHE vault file — review and re-title if it actually represents an idea, "
            "or kill if it's reference material.)\n\n"
            "## Source excerpt\n"
            f"```\n{excerpt}\n```\n"
        )

        slug = slugify(title)
        out_dir = INBOX_DIR / cat
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"mhe-{slug}.md"
        n = 2
        while out_path.exists():
            out_path = out_dir / f"mhe-{slug}-{n}.md"
            n += 1

        if args.dry_run:
            print(f"  [{cat:<16}] {rel}")
        else:
            write_file(out_path, meta, body_md)
            written.append(out_path)
        ingested += 1

    print(f"\nwalked: {walked}")
    print(f"  skipped short: {skipped_short}")
    print(f"  skipped credential-like: {skipped_creds}")
    print(f"  {'would ingest' if args.dry_run else 'ingested'}: {ingested}")
    if not args.dry_run:
        log_event("mhe_simple_ingest", source="mhe_simple_ingest.py", ingested=ingested)
    return 0


if __name__ == "__main__":
    sys.exit(main())
