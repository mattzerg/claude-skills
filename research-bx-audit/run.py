#!/usr/bin/env python3
"""research-bx-audit — validate behavioral-sciences knowledge layer.

Usage:
  python run.py card <path>
  python run.py corpus
  python run.py pre-commit <path1> [<path2> ...]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

VAULT = Path(
    os.environ.get(
        "MATTZERG_VAULT",
        "/Users/mattheweisner/Obsidian/Zerg/MattZerg",
    )
)
KNOWLEDGE = VAULT / "_knowledge" / "behavioral-sciences"
CITATIONS_DIR = KNOWLEDGE / "_citations"
LIBRARY_BIB = CITATIONS_DIR / "library.bib"
ALLOWLIST = CITATIONS_DIR / "verified-doi-allowlist.md"
LEDGER = KNOWLEDGE / "_replication-ledger.md"

REQUIRED_FRONTMATTER = [
    "construct",
    "domain",
    "canonical_citations",
    "boundary_conditions",
    "replication_status",
    "last_verified",
    "confidence",
]
VALID_DOMAINS = {
    "jdm",
    "behavioral-economics",
    "consumer-behavior",
    "user-research",
    "market-research",
    "applied-psychology",
    "hci",
}
VALID_STATUS = {"robust", "mixed", "failed", "contested", "untested", "weakened"}
VALID_CONFIDENCE = {"high", "medium", "low"}
REQUIRED_SECTIONS = [
    "## Definition",
    "## Canonical evidence",
    "## Boundary conditions",
    "## Replication status",
    "## Applied examples",
    "## When NOT to invoke",
]


def parse_frontmatter(text: str) -> dict | None:
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    fm_text = text[3:end]
    fm: dict = {}
    current_key: str | None = None
    for raw in fm_text.splitlines():
        line = raw.rstrip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(" ") and current_key:
            stripped = line.strip()
            if stripped.startswith("- "):
                fm.setdefault(current_key, [])
                if isinstance(fm[current_key], list):
                    fm[current_key].append(stripped[2:].strip().strip("'\""))
            continue
        if ":" in line:
            k, _, v = line.partition(":")
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


def load_bibtex_keys() -> set[str]:
    if not LIBRARY_BIB.exists():
        return set()
    keys = set()
    # Unicode-aware: bibtex keys can contain Unicode letters (e.g., Kühberger1998).
    # Stop at the comma that terminates the key.
    for m in re.finditer(r"@\w+\{([^,\s]+),", LIBRARY_BIB.read_text()):
        keys.add(m.group(1))
    return keys


def load_allowlist_keys() -> set[str]:
    if not ALLOWLIST.exists():
        return set()
    keys = set()
    for line in ALLOWLIST.read_text().splitlines():
        if line.startswith("| ") and " | " in line[2:]:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if cells and cells[0] not in {"BibTeX Key", "---", ""} and not cells[0].startswith("-"):
                keys.add(cells[0])
    return keys


def load_blacklist_constructs() -> set[str]:
    if not LEDGER.exists():
        return set()
    constructs = set()
    for m in re.finditer(r"^###\s+([a-z0-9-]+)\s*$", LEDGER.read_text(), re.MULTILINE):
        constructs.add(m.group(1))
    return constructs


def audit_card(path: Path, ctx: dict) -> tuple[bool, list[str]]:
    failures: list[str] = []
    warnings: list[str] = []

    if not path.exists():
        return False, [f"L1: card not found"]

    text = path.read_text()
    fm = parse_frontmatter(text)
    if fm is None:
        return False, ["L1: frontmatter parse error"]

    # L2 — required fields
    for k in REQUIRED_FRONTMATTER:
        if k not in fm:
            failures.append(f"L2: missing frontmatter field `{k}`")

    # L3 — domain matches folder
    parent_folder = path.parent.name
    fm_domain = fm.get("domain")
    if fm_domain and fm_domain != parent_folder:
        failures.append(f"L3: domain `{fm_domain}` does not match folder `{parent_folder}`")
    if fm_domain and fm_domain not in VALID_DOMAINS:
        failures.append(f"L3: domain `{fm_domain}` not a valid domain")

    # L4/L5 — canonical_citations
    canon = fm.get("canonical_citations") or []
    if not isinstance(canon, list):
        canon = []
    if not canon:
        failures.append("L4: canonical_citations is empty (≥1 required)")
    for key in canon:
        if key not in ctx["bibtex_keys"]:
            failures.append(f"L4: bibtex key `{key}` not in library.bib")
        if key not in ctx["allowlist_keys"]:
            failures.append(f"L5: bibtex key `{key}` not in verified-doi-allowlist.md")

    # L6 — contested_by
    contested = fm.get("contested_by") or []
    if not isinstance(contested, list):
        contested = []
    for key in contested:
        if key not in ctx["bibtex_keys"]:
            failures.append(f"L6: contested_by key `{key}` not in library.bib")
        if key not in ctx["allowlist_keys"]:
            failures.append(f"L6: contested_by key `{key}` not in verified-doi-allowlist.md")

    # L7 — non-robust must have contested_by
    status = fm.get("replication_status")
    if status in {"mixed", "failed", "contested", "weakened"} and not contested:
        failures.append(f"L7: replication_status={status} requires non-empty contested_by")

    # L8 — body sections
    for sec in REQUIRED_SECTIONS:
        if sec not in text:
            failures.append(f"L8: missing required section `{sec}`")

    # L9 — last_verified
    lv = fm.get("last_verified")
    if lv:
        try:
            lv_date = datetime.strptime(str(lv), "%Y-%m-%d").date()
            if lv_date > date.today():
                failures.append(f"L9: last_verified `{lv}` is in the future")
            elif (date.today() - lv_date).days > 180:
                warnings.append(f"X5: last_verified `{lv}` is >180 days old (stale)")
        except ValueError:
            failures.append(f"L9: last_verified `{lv}` not a valid YYYY-MM-DD date")

    # L10 — confidence vs status
    conf = fm.get("confidence")
    if conf and conf not in VALID_CONFIDENCE:
        failures.append(f"L10: confidence `{conf}` not in {VALID_CONFIDENCE}")
    if status == "failed" and conf == "high":
        failures.append("L10: replication_status=failed cannot have confidence=high")
    if status == "robust" and conf == "low":
        failures.append("L10: replication_status=robust should have confidence=high or medium, not low")

    # X1/X2 — blacklist consistency
    construct = fm.get("construct")
    if construct and construct in ctx["blacklist_constructs"] and status != "failed":
        failures.append(f"X1: construct `{construct}` is on replication ledger blacklist but status is `{status}`, must be `failed`")

    # X3 — related_cards dangle (treated as WARNING during seeding, not a hard fail)
    related = fm.get("related_cards") or []
    if not isinstance(related, list):
        related = []
    for r in related:
        # look up under any domain folder
        candidates = list(KNOWLEDGE.glob(f"*/{r}.md"))
        if not candidates:
            warnings.append(f"X3: related_card `{r}` does not resolve to any card file (will resolve when card lands)")

    return (not failures), failures + warnings


def mode_card(args: argparse.Namespace) -> int:
    ctx = {
        "bibtex_keys": load_bibtex_keys(),
        "allowlist_keys": load_allowlist_keys(),
        "blacklist_constructs": load_blacklist_constructs(),
    }
    path = Path(args.path)
    ok, msgs = audit_card(path, ctx)
    print(f"{'PASS' if ok else 'FAIL'} — {path.name}")
    for m in msgs:
        prefix = "  ⚠️" if (m.startswith("X5") or m.startswith("X3")) else "  ✗"
        print(f"{prefix} {m}")
    return 0 if ok else 2


def mode_corpus(args: argparse.Namespace) -> int:
    ctx = {
        "bibtex_keys": load_bibtex_keys(),
        "allowlist_keys": load_allowlist_keys(),
        "blacklist_constructs": load_blacklist_constructs(),
    }
    cards = []
    for domain in VALID_DOMAINS:
        domain_dir = KNOWLEDGE / domain
        if not domain_dir.exists():
            continue
        for p in sorted(domain_dir.glob("*.md")):
            if p.name.startswith("_"):
                continue
            cards.append(p)

    if not cards:
        print("INFO: no cards in knowledge layer yet (Phase 2 not yet run)")
        print("VERDICT: PASS (empty corpus)")
        return 0

    passed = 0
    failed = 0
    warned = 0
    rows = []
    for p in cards:
        ok, msgs = audit_card(p, ctx)
        warns = sum(1 for m in msgs if m.startswith("X5") or m.startswith("X3"))
        if ok:
            passed += 1
            if warns:
                warned += 1
        else:
            failed += 1
        rows.append((p, ok, msgs))

    print(f"# Audit Report — {date.today().isoformat()}")
    print()
    print("## Summary")
    print(f"- Cards scanned: {len(cards)}")
    print(f"- Pass: {passed}")
    print(f"- Warnings (stale only): {warned}")
    print(f"- Fail: {failed}")
    print(f"- Verdict: {'PASS' if failed == 0 else 'FAIL'}")
    print()
    print("## Per-card")
    for p, ok, msgs in rows:
        rel = p.relative_to(KNOWLEDGE)
        print(f"### `{rel}` — {'PASS' if ok else 'FAIL'}")
        for m in msgs:
            prefix = "⚠️" if (m.startswith("X5") or m.startswith("X3")) else "✗"
            print(f"- {prefix} {m}")
        print()
    return 0 if failed == 0 else 2


def mode_pre_commit(args: argparse.Namespace) -> int:
    ctx = {
        "bibtex_keys": load_bibtex_keys(),
        "allowlist_keys": load_allowlist_keys(),
        "blacklist_constructs": load_blacklist_constructs(),
    }
    all_ok = True
    for p in args.paths:
        path = Path(p)
        if path.suffix != ".md":
            continue
        if "behavioral-sciences" not in str(path):
            continue
        if path.name.startswith("_"):
            continue
        ok, msgs = audit_card(path, ctx)
        print(f"{'PASS' if ok else 'FAIL'} — {path}")
        for m in msgs:
            prefix = "⚠️" if (m.startswith("X5") or m.startswith("X3")) else "✗"
            print(f"  {prefix} {m}")
        all_ok = all_ok and ok
    return 0 if all_ok else 2


def main(argv=None):
    p = argparse.ArgumentParser(prog="research-bx-audit")
    sub = p.add_subparsers(dest="mode", required=True)

    c = sub.add_parser("card")
    c.add_argument("path")
    c.set_defaults(func=mode_card)

    s = sub.add_parser("corpus")
    s.set_defaults(func=mode_corpus)

    pc = sub.add_parser("pre-commit")
    pc.add_argument("paths", nargs="+")
    pc.set_defaults(func=mode_pre_commit)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
