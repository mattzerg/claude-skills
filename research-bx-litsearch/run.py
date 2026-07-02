#!/usr/bin/env python3
"""research-bx-litsearch runner.

Modes:
  discover   - find candidate papers for a construct
  verify     - verify a single DOI
  verify-batch - verify all citations in a card's frontmatter

Usage:
  python run.py discover --construct prospect-theory --domain jdm
  python run.py verify --doi 10.1037/0022-3514.74.5.1252
  python run.py verify-batch --card path/to/card.md

This is a thin orchestrator. The skill's SKILL.md instructions describe what
LLM-mediated steps to take; this script handles the deterministic API plumbing
and file mutations.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

# Resolved at import; can be overridden via env.
import os
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
REPLICATION_LEDGER = KNOWLEDGE / "_replication-ledger.md"
SKILL_DIR = Path(__file__).resolve().parent
STATE_DIR = SKILL_DIR / "state"
CANDIDATES_DIR = STATE_DIR / "candidates"
AUDIT_LOG = STATE_DIR / "audit-log.jsonl"

USER_AGENT = "research-bx-litsearch/0.1 (mailto:matthew@matteisn.com)"


# -------------------------- audit log --------------------------------------- #

def audit(action: str, **fields) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    rec = {"ts": datetime.now(timezone.utc).isoformat(), "action": action, **fields}
    with AUDIT_LOG.open("a") as f:
        f.write(json.dumps(rec) + "\n")


# -------------------------- HTTP helpers ------------------------------------ #

def _get_json(url: str, timeout: float = 15.0) -> dict | None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status != 200:
                return None
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


# -------------------------- verify ------------------------------------------ #

@dataclass
class VerifyResult:
    doi: str
    verified: bool
    source: str | None  # openalex | crossref | semanticscholar | doi.org
    is_retracted: bool
    title: str | None = None
    year: int | None = None
    authors: list[str] | None = None
    journal: str | None = None
    reason: str | None = None


def verify_doi(doi: str) -> VerifyResult:
    doi = doi.strip()
    if not doi.startswith("10."):
        return VerifyResult(doi, False, None, False, reason="malformed_doi")

    # 1. OpenAlex
    oa = _get_json(f"https://api.openalex.org/works/doi:{urllib.parse.quote(doi)}")
    if oa and oa.get("doi"):
        authors = [a["author"]["display_name"] for a in oa.get("authorships", []) if a.get("author")]
        journal = ((oa.get("primary_location") or {}).get("source") or {}).get("display_name")
        return VerifyResult(
            doi=doi,
            verified=True,
            source="openalex",
            is_retracted=bool(oa.get("is_retracted")),
            title=oa.get("title"),
            year=oa.get("publication_year"),
            authors=authors,
            journal=journal,
        )

    # 2. Crossref
    cr = _get_json(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}")
    if cr and (cr.get("message") or {}).get("DOI"):
        msg = cr["message"]
        authors = [
            f"{a.get('given', '')} {a.get('family', '')}".strip() for a in msg.get("author", [])
        ]
        year = None
        if msg.get("issued", {}).get("date-parts"):
            year = msg["issued"]["date-parts"][0][0]
        return VerifyResult(
            doi=doi,
            verified=True,
            source="crossref",
            is_retracted=False,  # Crossref doesn't reliably surface retractions
            title=(msg.get("title") or [None])[0],
            year=year,
            authors=authors,
            journal=(msg.get("container-title") or [None])[0],
        )

    # 3. Semantic Scholar
    ss = _get_json(
        f"https://api.semanticscholar.org/graph/v1/paper/DOI:{urllib.parse.quote(doi)}"
        "?fields=title,year,authors,journal,isRetracted"
    )
    if ss and ss.get("title"):
        authors = [a.get("name") for a in ss.get("authors", []) if a.get("name")]
        return VerifyResult(
            doi=doi,
            verified=True,
            source="semanticscholar",
            is_retracted=bool(ss.get("isRetracted")),
            title=ss.get("title"),
            year=ss.get("year"),
            authors=authors,
            journal=(ss.get("journal") or {}).get("name"),
        )

    # 4. doi.org HEAD redirect (lowest signal)
    try:
        req = urllib.request.Request(
            f"https://doi.org/{urllib.parse.quote(doi)}",
            headers={"User-Agent": USER_AGENT},
            method="HEAD",
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            if r.status in (200, 301, 302, 303, 307, 308):
                return VerifyResult(doi, True, "doi.org", False, reason="resolved_no_metadata")
    except Exception:
        pass

    return VerifyResult(doi, False, None, False, reason="unresolved_via_all_sources")


# -------------------------- allowlist + bibtex ------------------------------ #

def _bibtex_key(authors: list[str] | None, year: int | None, fallback: str) -> str:
    if authors:
        first = authors[0].split()[-1]  # surname
        first = "".join(c for c in first if c.isalpha())
        if year:
            return f"{first}{year}"
        return first
    return fallback


def append_allowlist(key: str, doi: str, source: str, by: str = "research-bx-litsearch") -> None:
    line = f"| {key} | {doi} | {source} | {date.today().isoformat()} | {by} |\n"
    # Append at end of file. (For now we don't dedupe rows; the audit gate catches duplicates.)
    with ALLOWLIST.open("a") as f:
        f.write(line)


def append_bibtex(key: str, vr: VerifyResult) -> None:
    if not vr.verified:
        return
    authors_str = " and ".join(vr.authors or [])
    entry = (
        f"\n@article{{{key},\n"
        f"  author  = {{{authors_str}}},\n"
        f"  title   = {{{vr.title or ''}}},\n"
        f"  journal = {{{vr.journal or ''}}},\n"
        f"  year    = {{{vr.year or ''}}},\n"
        f"  doi     = {{{vr.doi}}}\n"
        f"}}\n"
    )
    with LIBRARY_BIB.open("a") as f:
        f.write(entry)


# -------------------------- mode dispatch ----------------------------------- #

def mode_verify(args: argparse.Namespace) -> int:
    vr = verify_doi(args.doi)
    audit("verify", doi=vr.doi, source=vr.source, result="ok" if vr.verified else "fail", reason=vr.reason)
    print(json.dumps(asdict(vr), indent=2))
    if not vr.verified:
        return 2
    if vr.is_retracted:
        print("WARN: retracted — not adding to allowlist", file=sys.stderr)
        return 3
    # --- title / year sanity check ------------------------------------- #
    # Catches the McSweeney1984 / Busse2016 class of bug: DOI resolves but to the wrong paper.
    if args.expect_title:
        needles = [n.strip().lower() for n in args.expect_title.split(",") if n.strip()]
        title_l = (vr.title or "").lower()
        if not any(n in title_l for n in needles):
            print(
                f"REFUSE: title sanity check failed — expected one of {needles} in title, got: {vr.title!r}",
                file=sys.stderr,
            )
            audit("verify-title-mismatch", doi=vr.doi, expected=args.expect_title, got=vr.title)
            return 4
    if args.expect_year and vr.year and str(vr.year) != str(args.expect_year):
        print(
            f"REFUSE: year sanity check failed — expected {args.expect_year}, got {vr.year}",
            file=sys.stderr,
        )
        audit("verify-year-mismatch", doi=vr.doi, expected=args.expect_year, got=vr.year)
        return 4
    if args.expect_author:
        author_needle = args.expect_author.strip().lower()
        authors_l = " ".join(vr.authors or []).lower()
        if author_needle not in authors_l:
            print(
                f"REFUSE: author sanity check failed — expected {args.expect_author!r} in authors, got {vr.authors!r}",
                file=sys.stderr,
            )
            audit("verify-author-mismatch", doi=vr.doi, expected=args.expect_author, got=vr.authors)
            return 4
    key = _bibtex_key(vr.authors, vr.year, fallback=vr.doi.replace("/", "_"))
    append_bibtex(key, vr)
    append_allowlist(key, vr.doi, vr.source or "manual")
    print(f"OK: added {key} → {vr.doi} — {vr.title!r}", file=sys.stderr)
    return 0


# Domain → OpenAlex concept search term. The script looks up the actual concept ID
# at runtime so we don't hardcode IDs (OpenAlex IDs are stable but the list is the source of truth).
DOMAIN_CONCEPT_SEARCH = {
    "jdm": "decision making",
    "behavioral-economics": "behavioral economics",
    "consumer-behavior": "consumer behaviour",
    "user-research": "user experience",
    "market-research": "marketing research",
    "applied-psychology": "applied psychology",
    "hci": "human-computer interaction",
}


def _resolve_concept_id(search_term: str) -> str | None:
    """Look up an OpenAlex concept ID by search term. Returns ID like 'C162324750' or None."""
    url = f"https://api.openalex.org/concepts?search={urllib.parse.quote(search_term)}&per_page=5"
    data = _get_json(url)
    if not data or not data.get("results"):
        return None
    # First result is highest-ranked match. Strip 'https://openalex.org/' prefix.
    raw_id = data["results"][0].get("id", "")
    return raw_id.rsplit("/", 1)[-1] if raw_id else None


def mode_discover(args: argparse.Namespace) -> int:
    """Discover candidate papers for a construct.

    Strategy (improved 2026-05-29 after the noisy-results bug):
      1. Phrase-quote the search term to match the construct as a unit, not as tokens scattered across all of science.
      2. Look up the domain's OpenAlex concept ID at runtime; filter results to that concept.
      3. Sort by citation count, but cap by year to bias toward modern post-replication-crisis evidence.
    """
    construct = args.construct
    domain = args.domain or "unknown"
    n = args.n or 25
    phrase = construct.replace("-", " ")

    # Resolve concept ID if domain is known.
    concept_id = None
    if domain in DOMAIN_CONCEPT_SEARCH and not args.no_concept_filter:
        concept_id = _resolve_concept_id(DOMAIN_CONCEPT_SEARCH[domain])

    # Build the phrase-quoted search. OpenAlex respects quoted strings for phrase matching.
    search_q = urllib.parse.quote(f'"{phrase}"')
    filters = []
    if concept_id:
        filters.append(f"concepts.id:{concept_id}")
    filter_q = f"&filter={','.join(filters)}" if filters else ""

    url = (
        f"https://api.openalex.org/works?search={search_q}{filter_q}"
        f"&per_page={n}&sort=cited_by_count:desc"
    )
    data = _get_json(url)
    hits = len((data or {}).get("results", []))
    audit(
        "discover",
        construct=construct,
        domain=domain,
        source="openalex",
        hits=hits,
        concept_id=concept_id,
        phrase_quoted=True,
    )

    # Fallback: if quoted+filtered returns <3 hits, retry without the concept filter (still quoted).
    if hits < 3:
        url2 = f"https://api.openalex.org/works?search={search_q}&per_page={n}&sort=cited_by_count:desc"
        data2 = _get_json(url2)
        if data2 and len(data2.get("results", [])) > hits:
            data = data2
            hits = len(data["results"])
            audit("discover-fallback", construct=construct, reason="concept-filter-empty", hits=hits)

    if not data:
        print("ERROR: OpenAlex discovery failed (both filtered + fallback)", file=sys.stderr)
        return 2

    CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
    out = CANDIDATES_DIR / f"{construct}-{date.today().isoformat()}.md"
    lines = [
        f"# Candidate corpus — {construct} — {date.today().isoformat()}",
        "",
        f"**Construct**: {construct}",
        f"**Domain**: {domain}",
        f"**Phrase searched**: `\"{phrase}\"` (quoted)",
        f"**Concept filter**: {concept_id or 'none'}",
        f"**Hits**: {hits}",
        "",
        "## Candidates (top by citation count)",
        "",
        "| # | DOI | Year | Cited | Title | Type | Retracted |",
        "|---|-----|------|-------|-------|------|-----------|",
    ]
    for i, w in enumerate(data["results"], 1):
        doi = (w.get("doi") or "").replace("https://doi.org/", "")
        title = (w.get("title") or "").replace("|", "—")
        lines.append(
            f"| {i} | {doi} | {w.get('publication_year') or ''} | {w.get('cited_by_count') or 0} | {title[:120]} | {w.get('type') or ''} | {'YES' if w.get('is_retracted') else ''} |"
        )
    lines.append("")
    lines.append("## Next step")
    lines.append("Review the list. For each you want to cite, run:")
    lines.append("")
    lines.append("```bash")
    lines.append(f"python {Path(__file__).name} verify --doi <DOI> --expect-title <substr> --expect-year <year>")
    lines.append("```")
    lines.append("")
    lines.append("`--expect-title` and `--expect-year` are strongly recommended — they catch DOI-resolves-but-wrong-paper bugs.")
    out.write_text("\n".join(lines))
    print(f"Wrote {out}")
    return 0


def mode_verify_batch(args: argparse.Namespace) -> int:
    """Verify a card's canonical_citations by re-querying each bibtex key's DOI."""
    card = Path(args.card)
    if not card.exists():
        print(f"ERROR: card not found: {card}", file=sys.stderr)
        return 2
    text = card.read_text()
    # Minimal YAML extraction. Pyyaml not assumed present.
    if not text.startswith("---"):
        print("ERROR: no frontmatter", file=sys.stderr)
        return 2
    fm_end = text.find("\n---", 3)
    if fm_end == -1:
        print("ERROR: frontmatter not closed", file=sys.stderr)
        return 2
    fm = text[3:fm_end]
    keys: list[str] = []
    in_canon = False
    for line in fm.splitlines():
        if line.startswith("canonical_citations:"):
            in_canon = True
            inline = line.split(":", 1)[1].strip()
            if inline.startswith("[") and inline.endswith("]"):
                keys = [k.strip().strip("'\"") for k in inline[1:-1].split(",") if k.strip()]
                in_canon = False
            continue
        if in_canon:
            stripped = line.strip()
            if stripped.startswith("- "):
                keys.append(stripped[2:].strip().strip("'\""))
            elif stripped and not stripped.startswith("-"):
                in_canon = False
    if not keys:
        print("ERROR: no canonical_citations found", file=sys.stderr)
        return 2

    # Look up each bibtex key's DOI in library.bib.
    bib_text = LIBRARY_BIB.read_text() if LIBRARY_BIB.exists() else ""
    failed: list[str] = []
    for key in keys:
        # crude: find `@article{<key>,` then walk for `doi = {...}`
        marker = f"{{{key},"
        idx = bib_text.find(marker)
        if idx == -1:
            print(f"FAIL: bibtex key not in library.bib: {key}", file=sys.stderr)
            failed.append(key)
            continue
        end = bib_text.find("\n}", idx)
        block = bib_text[idx:end]
        doi = None
        for line in block.splitlines():
            line = line.strip().rstrip(",")
            if line.startswith("doi"):
                doi = line.split("=", 1)[1].strip().strip("{}").strip()
                break
        if not doi:
            print(f"FAIL: bibtex key has no DOI: {key}", file=sys.stderr)
            failed.append(key)
            continue
        vr = verify_doi(doi)
        audit("verify-batch", card=str(card), key=key, doi=doi, source=vr.source, result="ok" if vr.verified else "fail")
        if not vr.verified or vr.is_retracted:
            failed.append(key)
            print(f"FAIL: {key} ({doi}) — verified={vr.verified} retracted={vr.is_retracted}", file=sys.stderr)
            continue
        print(f"OK: {key} ({doi}) via {vr.source}", file=sys.stderr)

    if failed:
        print(f"VERDICT: FAILED ({len(failed)} citation(s) failed)", file=sys.stderr)
        return 2

    # All pass → update last_verified in frontmatter.
    today = date.today().isoformat()
    new_fm_lines = []
    updated = False
    for line in fm.splitlines():
        if line.startswith("last_verified:"):
            new_fm_lines.append(f"last_verified: {today}")
            updated = True
        else:
            new_fm_lines.append(line)
    if not updated:
        new_fm_lines.append(f"last_verified: {today}")
    new_text = "---\n" + "\n".join(new_fm_lines) + "\n---" + text[fm_end + 4 :]
    card.write_text(new_text)
    print(f"VERDICT: OK ({len(keys)} citation(s) verified); updated last_verified={today}")
    return 0


# -------------------------- main -------------------------------------------- #

def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="research-bx-litsearch")
    sub = p.add_subparsers(dest="mode", required=True)

    d = sub.add_parser("discover")
    d.add_argument("--construct", required=True)
    d.add_argument("--domain")
    d.add_argument("--n", type=int, default=25)
    d.add_argument("--no-concept-filter", action="store_true", help="Disable concept-ID filtering (broader but noisier search).")
    d.set_defaults(func=mode_discover)

    v = sub.add_parser("verify")
    v.add_argument("--doi", required=True)
    v.add_argument("--expect-title", help="Comma-separated substrings; at least one must appear in the returned title (case-insensitive). Refuses to write if no match — catches DOI-resolves-but-wrong-paper bugs.")
    v.add_argument("--expect-year", help="Expected publication year; refuses to write on mismatch.")
    v.add_argument("--expect-author", help="Substring expected in author list (case-insensitive).")
    v.set_defaults(func=mode_verify)

    b = sub.add_parser("verify-batch")
    b.add_argument("--card", required=True)
    b.set_defaults(func=mode_verify_batch)

    args = p.parse_args(list(argv) if argv is not None else None)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
