#!/usr/bin/env python3
"""advise-bx runner — retrieval layer for the behavioral-sciences advisor.

The actual analysis is LLM-mediated (per SKILL.md). This runner handles the
deterministic retrieval: load relevant cards by applies_to_zerg tag + domain
filter, load the replication ledger, emit a structured prompt-pack ready for
the LLM to apply against a target artifact.

Modes:
  load      - load cards relevant to artifact-type tags; emit prompt-pack
  which     - given a situation description, return top candidate cards
  refuse    - given a proposed recommendation, check for blacklist invocation

Usage:
  python run.py load --tags pricing,copy [--domain behavioral-economics] --target path/to/artifact.md
  python run.py which "situation description"
  python run.py refuse "proposed recommendation text"
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

VAULT = Path(
    os.environ.get(
        "MATTZERG_VAULT",
        "/Users/mattheweisner/Obsidian/Zerg/MattZerg",
    )
)
KNOWLEDGE = VAULT / "_knowledge" / "behavioral-sciences"
LEDGER = KNOWLEDGE / "_replication-ledger.md"
SKILL_DIR = Path(__file__).resolve().parent
STATE_DIR = SKILL_DIR / "state"
LOG = STATE_DIR / "advise-log.jsonl"

VALID_DOMAINS = {
    "jdm",
    "behavioral-economics",
    "consumer-behavior",
    "user-research",
    "market-research",
    "applied-psychology",
    "hci",
}


def parse_frontmatter(text: str) -> dict | None:
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    fm: dict = {}
    current_key: str | None = None
    for line in text[3:end].splitlines():
        line_stripped = line.rstrip()
        if not line_stripped or line_stripped.startswith("#"):
            continue
        if line.startswith(" ") and current_key:
            s = line.strip()
            if s.startswith("- "):
                fm.setdefault(current_key, [])
                if isinstance(fm[current_key], list):
                    fm[current_key].append(s[2:].strip().strip("'\""))
            continue
        if ":" in line_stripped:
            k, _, v = line_stripped.partition(":")
            k = k.strip()
            v = v.strip()
            current_key = k
            if v.startswith("[") and v.endswith("]"):
                items = [s.strip().strip("'\"") for s in v[1:-1].split(",") if s.strip()]
                fm[k] = items
                current_key = None
            elif v:
                fm[k] = v
                current_key = None
            else:
                fm[k] = []
    return fm


def load_all_cards() -> list[tuple[Path, dict, str]]:
    """Return list of (path, frontmatter, body) for every committed card."""
    cards = []
    for domain in VALID_DOMAINS:
        domain_dir = KNOWLEDGE / domain
        if not domain_dir.exists():
            continue
        for p in sorted(domain_dir.glob("*.md")):
            if p.name.startswith("_"):
                continue
            text = p.read_text()
            fm = parse_frontmatter(text)
            if fm is None:
                continue
            body = text[text.find("\n---", 3) + 4 :].lstrip()
            cards.append((p, fm, body))
    return cards


def load_blacklist() -> set[str]:
    """Return constructs on the replication-ledger blacklist (status: failed)."""
    if not LEDGER.exists():
        return set()
    constructs = set()
    text = LEDGER.read_text()
    # Match `### <construct-name>` followed by "Status: failed" within ~10 lines.
    for m in re.finditer(r"^###\s+([a-z0-9-]+)\s*$", text, re.MULTILINE):
        construct = m.group(1)
        # Look ahead for the status line
        tail = text[m.end() : m.end() + 1500]
        status_match = re.search(r"\*\*Status\*\*:\s*(\w+)", tail)
        if status_match and status_match.group(1).lower() == "failed":
            constructs.add(construct)
    return constructs


def filter_cards(cards, tags: set[str], domains: set[str] | None) -> list:
    """Filter cards by applies_to_zerg tag and optional domain."""
    matched = []
    for path, fm, body in cards:
        if domains and fm.get("domain") not in domains:
            continue
        card_tags = set(fm.get("applies_to_zerg") or [])
        if tags and not (card_tags & tags):
            continue
        matched.append((path, fm, body))
    return matched


def log_action(action: str, **fields) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    rec = {"ts": datetime.now(timezone.utc).isoformat(), "action": action, **fields}
    with LOG.open("a") as f:
        f.write(json.dumps(rec) + "\n")


def mode_load(args: argparse.Namespace) -> int:
    cards = load_all_cards()
    if not cards:
        print("ERROR: knowledge layer is empty; advisor cannot operate.", file=sys.stderr)
        return 4

    tags = set(args.tags.split(",")) if args.tags else set()
    domains = set(args.domain.split(",")) if args.domain else None
    if domains:
        bad = domains - VALID_DOMAINS
        if bad:
            print(f"ERROR: invalid domain(s): {bad}", file=sys.stderr)
            return 2

    relevant = filter_cards(cards, tags, domains)
    blacklist = load_blacklist()

    log_action(
        "load",
        target=args.target,
        tags=sorted(tags),
        domains=sorted(domains) if domains else None,
        cards_loaded=len(relevant),
        blacklist_size=len(blacklist),
    )

    # Emit a structured prompt-pack for the LLM to apply
    print("# advise-bx prompt-pack")
    print()
    print(f"**Target**: {args.target or '<inline>'}")
    print(f"**Tags**: {sorted(tags) or '(any)'}")
    print(f"**Domains**: {sorted(domains) if domains else '(all 7)'}")
    print(f"**Cards loaded**: {len(relevant)}")
    print(f"**Blacklist (refuse to invoke positively)**: {sorted(blacklist)}")
    print()
    print("## Relevant cards")
    print()
    for path, fm, _body in relevant:
        rel = path.relative_to(KNOWLEDGE)
        status = fm.get("replication_status", "?")
        applies = fm.get("applies_to_zerg") or []
        print(f"- `{rel}` (status: **{status}**, applies: {applies})")
        # Brief description from frontmatter
        for related in (fm.get("related_cards") or [])[:2]:
            print(f"    related: {related}")
    print()
    print("## Instructions for LLM")
    print()
    print("Apply each loaded card to the target artifact per `SKILL.md`:")
    print("- Each finding cites ≥1 card; each card cites ≥1 DOI-verified source.")
    print("- Refuse to invoke blacklisted constructs as positive recommendations.")
    print("- Surface replication-status hedging in-line for non-robust cards.")
    print("- Use academic-reviewer register per `MattZerg/_style/expert_voice_behavioral_sciences.md`.")
    print()
    if args.target:
        target = Path(args.target)
        if target.exists():
            print("## Target content (read-only)")
            print()
            print("```")
            print(target.read_text())
            print("```")
        else:
            print(f"WARN: target {args.target} not found", file=sys.stderr)
    return 0


def mode_which(args: argparse.Namespace) -> int:
    """Given a situation description, return top candidate cards via keyword matching."""
    cards = load_all_cards()
    if not cards:
        print("ERROR: knowledge layer is empty.", file=sys.stderr)
        return 4
    situation = args.situation.lower()
    keywords = set(re.findall(r"[a-z]{4,}", situation))

    scored = []
    for path, fm, body in cards:
        score = 0
        construct = fm.get("construct", "")
        if any(k in construct for k in keywords):
            score += 5
        body_lower = body.lower()
        for k in keywords:
            score += body_lower.count(k)
        if score:
            scored.append((score, path, fm))

    scored.sort(reverse=True, key=lambda x: x[0])
    top = scored[:5]
    log_action("which", situation=args.situation, top=[p.name for _, p, _ in top])

    print(f"# Top {len(top)} candidate cards for: {args.situation!r}")
    print()
    for score, path, fm in top:
        rel = path.relative_to(KNOWLEDGE)
        print(f"- `{rel}` (score={score}, status={fm.get('replication_status', '?')})")
    return 0


def mode_refuse(args: argparse.Namespace) -> int:
    """Check whether a proposed recommendation invokes a blacklisted construct."""
    proposal = args.proposal.lower()
    blacklist = load_blacklist()
    hits = [c for c in blacklist if c.replace("-", " ") in proposal or c in proposal]
    log_action("refuse-check", proposal=args.proposal, hits=hits)
    if hits:
        print(f"REFUSE: proposal invokes blacklisted construct(s): {hits}")
        print()
        print("See _replication-ledger.md for replication-failure context.")
        print("Use better-supported alternatives per `advise-bx/references/anti-patterns.md`.")
        return 3
    print("OK: no blacklisted constructs detected in proposal.")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="advise-bx")
    sub = p.add_subparsers(dest="mode", required=True)

    pl = sub.add_parser("load")
    pl.add_argument("--tags", help="Comma-separated applies_to_zerg tags (e.g., 'pricing,copy')")
    pl.add_argument("--domain", help="Comma-separated domain filter")
    pl.add_argument("--target", help="Path to artifact to include inline")
    pl.set_defaults(func=mode_load)

    pw = sub.add_parser("which")
    pw.add_argument("situation")
    pw.set_defaults(func=mode_which)

    pr = sub.add_parser("refuse")
    pr.add_argument("proposal")
    pr.set_defaults(func=mode_refuse)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
