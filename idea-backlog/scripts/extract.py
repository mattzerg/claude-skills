#!/usr/bin/python3
"""extract: walk vault notes, ask Sonnet 4.6 to extract distinct ideas.

Stage 1 of the seed sweep. Resumable.

Output:
  ~/.claude/skills/idea-backlog/_workdir/raw_extracts.jsonl  (one row per idea)
  ~/.claude/skills/idea-backlog/_workdir/_done.txt           (processed paths)
  ~/.claude/skills/idea-backlog/_workdir/_errors.jsonl       (per-file errors)
  Ideas/_meta/extraction-log.md                               (run summary)

Each row in raw_extracts.jsonl:
  {
    "title": "...",
    "category": "product|content|tooling|personal|research",
    "subcategory": "...",
    "tags": [...],
    "one_line": "...",
    "why_interesting": "...",
    "source_excerpt": "...",
    "source_path": "Apple Notes/notes/business-ideas.md",
    "source_lines": [12, 28]
  }

Cost-conscious: skips files with <80 chars; chunks large files into 12k-char
windows to avoid 200k-token contexts. Estimated full-vault sweep: ~$2.50–$4.00
on Sonnet 4.6, ~10–25 minutes wall.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Iterator

# Make ~/.config/zerg importable for anthropic_client
ZERG_CFG = Path.home() / ".config" / "zerg"
if str(ZERG_CFG) not in sys.path:
    sys.path.insert(0, str(ZERG_CFG))

_LIB = Path(__file__).resolve().parent / "_lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from usage import log_event  # noqa: E402
from vault_paths import (  # noqa: E402
    VAULT_ROOT,
    MHE_VAULT_ROOT,
    SCAN_EXCLUDE_DIRS,
    SCAN_EXCLUDE_FILES,
    workdir,
    EXTRACTION_LOG,
)

from routed_model import routed_model  # noqa: E402

MAX_CHARS_PER_CHUNK = 12000
MIN_FILE_CHARS = 80


def _model() -> str:
    """Model routed via aitr (structured-extract / cheap-ok); falls back loudly
    to the previous hardcoded Sonnet default. Lazy: --dry-run never routes."""
    return routed_model("structured-extract", "idea-backlog-extract")

EXTRACT_PROMPT = """You are extracting IDEAS from Matt Eisner's personal vault. Matt is Head of Growth at Zerg AI, AND he has many personal-life ideas, side-business ideas, travel/shopping ideas, etc. Distinguish carefully — don't bucket personal-business ideas as "Zerg products."

An "idea" is something the writer might want to build, write, try, pursue, or buy.

Return STRICT JSON: an array of 0..N idea objects. Each object has:
  title           : 4-12 word noun phrase (no markdown)
  category        : one of: zerg-product | zerg-content | zerg-tooling | personal-venture | personal-life | shopping | research
  subcategory     : short free-text grouping (e.g. "zergwallet", "real-estate", "travel")
  tags            : 1-5 lowercase keyword tags
  one_line        : single sentence pitch
  why_interesting : 1-3 sentences on why it matters / what's the hook
  source_excerpt  : a verbatim quote (≤25 words) from the note showing where this idea lives

DO NOT extract:
  - To-do items / committed tasks
  - Meeting notes, reminders, calendar items
  - Pure status reports, daily logs
  - Code snippets without conceptual content
  - Recipes (unless framed as a recipe-system idea)

CATEGORIES — read carefully:

  zerg-product       : New microproducts/features/GTM motions WITHIN the Zerg portfolio
                       (Zergboard, Zergwallet, Zergmail, ZergStack, ZergAlytics, Zerg Solutions, etc.)
                       OR explicitly framed as something Zerg should build.

  zerg-content       : Blog posts, launch announcements, social hooks, thesis pieces FOR Zerg.
                       Anything Matt would write/publish on behalf of Zerg.

  zerg-tooling       : Scripts, skills, automations, vault infra Matt builds for his Zerg work.
                       Internal-use tools, not products to sell.

  personal-venture   : Matt's OWN potential side-business / startup ideas, real estate plays,
                       small businesses, lifestyle businesses, investment vehicles, financial
                       products HE might run or co-found — not Zerg products.
                       Examples: "bagel shop", "Detroit slumlord real estate", "basement music
                       studio", "small electrician business", "personal finance product Matt
                       could spin out". If it's a venture for HIM, not Zerg, this category.

  personal-life      : Travel, food, hobbies, family, fitness, lifestyle, life-design,
                       relationships, mental-models for living, learning ideas, social plans.
                       NOT business-shaped — purely about Matt's life.

  shopping           : Things to buy, gift ideas, products to try, items to acquire,
                       material wants, books to read, films to watch, music to listen to.
                       Concrete acquisition-shaped, not venture-shaped.

  research           : Thought experiments, "what if" essays, intellectual open questions,
                       research papers Matt might write/explore. Not a product, not a venture.

If a "business idea" is clearly something MATT might run himself (one-off shop, personal real estate
play, side business), use personal-venture, NOT zerg-product. Zerg-product is reserved for things
inside the Zerg portfolio.

If no ideas, return [].

NOTE PATH: {path}

NOTE BODY:
---
{body}
---

Return ONLY the JSON array. No prose before/after."""


def iter_vault_files(roots: list[Path]) -> Iterator[Path]:
    for root in roots:
        if not root.exists():
            continue
        for p in sorted(root.rglob("*.md")):
            try:
                rel = p.relative_to(root)
            except ValueError:
                continue
            parts = rel.parts
            if any(part in SCAN_EXCLUDE_DIRS for part in parts):
                continue
            if len(parts) == 1 and parts[0] in SCAN_EXCLUDE_FILES:
                continue
            if p.is_file() and p.stat().st_size > MIN_FILE_CHARS:
                yield p


def chunk(text: str, *, size: int = MAX_CHARS_PER_CHUNK) -> list[str]:
    if len(text) <= size:
        return [text]
    out: list[str] = []
    cursor = 0
    while cursor < len(text):
        end = min(cursor + size, len(text))
        # Prefer to split on a blank line if possible
        if end < len(text):
            slice_text = text[cursor:end]
            split_at = slice_text.rfind("\n\n")
            if split_at > size // 2:
                end = cursor + split_at
        out.append(text[cursor:end])
        cursor = end
    return out


def extract_chunk(client, path_label: str, body: str) -> tuple[list[dict], dict]:
    """Returns (ideas, usage). Empty list on parse failure."""
    msg = client.messages.create(
        model=_model(),
        max_tokens=4000,
        messages=[
            {"role": "user", "content": EXTRACT_PROMPT.format(path=path_label, body=body)},
        ],
    )
    raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()
    try:
        ideas = json.loads(raw)
        if not isinstance(ideas, list):
            ideas = []
    except json.JSONDecodeError:
        ideas = []
    usage = {
        "input_tokens": getattr(msg.usage, "input_tokens", 0),
        "output_tokens": getattr(msg.usage, "output_tokens", 0),
        "cache_creation_input_tokens": getattr(msg.usage, "cache_creation_input_tokens", 0),
        "cache_read_input_tokens": getattr(msg.usage, "cache_read_input_tokens", 0),
    }
    return ideas, usage


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--include-mhe", action="store_true", help="also sweep MHE vault")
    ap.add_argument("--limit", type=int, default=0, help="0 = no limit")
    ap.add_argument("--paths", default=None, help="comma-separated path filters (substring match on relative path)")
    ap.add_argument("--dry-run", action="store_true", help="list files that WOULD be processed; no LLM calls")
    ap.add_argument("--reset", action="store_true", help="clear _done.txt and start fresh")
    args = ap.parse_args()

    wd = workdir()
    out_jsonl = wd / "raw_extracts.jsonl"
    done_log = wd / "_done.txt"
    err_log = wd / "_errors.jsonl"

    if args.reset:
        for f in (out_jsonl, done_log, err_log):
            if f.exists():
                f.unlink()
        print("reset: cleared workdir")

    done: set[str] = set()
    if done_log.exists():
        done = set(done_log.read_text().splitlines())

    roots = [VAULT_ROOT]
    if args.include_mhe:
        roots.append(MHE_VAULT_ROOT)

    files = list(iter_vault_files(roots))
    if args.paths:
        filters = [s.strip() for s in args.paths.split(",") if s.strip()]
        files = [p for p in files if any(f in str(p) for f in filters)]

    todo = [p for p in files if str(p) not in done]
    if args.limit:
        todo = todo[: args.limit]

    print(f"found {len(files)} markdown files; {len(todo)} pending; {len(done)} already done")
    if args.dry_run:
        for p in todo[:50]:
            print(f"  {p.relative_to(roots[0]) if roots[0] in p.parents else p}")
        if len(todo) > 50:
            print(f"  ... +{len(todo)-50} more")
        return 0

    if not todo:
        print("nothing to do.")
        return 0

    from max_client import make_client  # noqa: E402
    client = make_client(source="idea-backlog/extract")

    total_in = total_out = total_ideas = 0
    started = time.time()

    out_fh = out_jsonl.open("a", encoding="utf-8")
    done_fh = done_log.open("a", encoding="utf-8")
    err_fh = err_log.open("a", encoding="utf-8")

    try:
        for i, p in enumerate(todo, 1):
            try:
                rel = str(p.relative_to(roots[0])) if roots[0] in p.parents else str(p)
            except ValueError:
                rel = str(p)
            try:
                body = p.read_text(errors="replace")
            except Exception as e:
                err_fh.write(json.dumps({"path": rel, "error": f"read: {e}"}) + "\n")
                continue
            if len(body) < MIN_FILE_CHARS:
                done_fh.write(str(p) + "\n")
                continue

            file_ideas: list[dict] = []
            for ci, ch in enumerate(chunk(body)):
                try:
                    ideas, usage = extract_chunk(client, rel, ch)
                except Exception as e:
                    err_fh.write(json.dumps({"path": rel, "chunk": ci, "error": str(e)}) + "\n")
                    continue
                total_in += usage["input_tokens"]
                total_out += usage["output_tokens"]
                for idea in ideas:
                    if not isinstance(idea, dict) or not idea.get("title"):
                        continue
                    idea["source_path"] = rel
                    file_ideas.append(idea)

            for idea in file_ideas:
                out_fh.write(json.dumps(idea, ensure_ascii=False) + "\n")
            done_fh.write(str(p) + "\n")
            done_fh.flush()
            out_fh.flush()
            total_ideas += len(file_ideas)

            elapsed = time.time() - started
            print(f"[{i:>3}/{len(todo)}] {rel}  ideas={len(file_ideas)}  cum={total_ideas}  in={total_in}  out={total_out}  t={elapsed:.0f}s")
    finally:
        out_fh.close()
        done_fh.close()
        err_fh.close()

    cost_est = (total_in / 1_000_000) * 3.0 + (total_out / 1_000_000) * 15.0
    summary = (
        f"\n## {datetime.now().isoformat(timespec='seconds')} — extract\n"
        f"- model: {_model()}\n"
        f"- files processed: {len(todo)}\n"
        f"- raw ideas extracted: {total_ideas}\n"
        f"- input tokens: {total_in:,}  output tokens: {total_out:,}\n"
        f"- est cost: ${cost_est:.2f}\n"
    )
    EXTRACTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with EXTRACTION_LOG.open("a") as fh:
        fh.write(summary)

    print(summary)
    print(f"raw extracts: {out_jsonl}")
    print(f"next: dedupe.py")
    log_event(
        "extract_run",
        source="extract.py",
        files_processed=len(todo),
        ideas_extracted=total_ideas,
        input_tokens=total_in,
        output_tokens=total_out,
        cost_usd=round(cost_est, 2),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
