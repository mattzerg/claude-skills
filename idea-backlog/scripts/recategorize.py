#!/usr/bin/python3
"""recategorize: LLM batch pass to assign each idea a category from the new
7-axis taxonomy, with explicit Zerg-vs-personal distinction.

Reads each idea (active or inbox), sends batches of 15 to Sonnet 4.5 with
title + subcategory + tags + verbatim source excerpts (NOT the LLM gloss),
gets back a category assignment per item, updates frontmatter, and moves
the file to the new category folder if it changed.

Usage:
    recategorize.py [--limit N] [--batch-size 15] [--include-inbox] [--include-archive] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ZERG_CFG = Path.home() / ".config" / "zerg"
if str(ZERG_CFG) not in sys.path:
    sys.path.insert(0, str(ZERG_CFG))

_LIB = Path(__file__).resolve().parent / "_lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from frontmatter import read_file, write_file  # noqa: E402
from idea_io import iter_all_ideas  # noqa: E402
from usage import log_event  # noqa: E402
from vault_paths import (  # noqa: E402
    ARCHIVE_DIR,
    CATEGORIES,
    INBOX_DIR,
    VAULT_ROOT,
    category_dir,
)

from routed_model import routed_model  # noqa: E402


def _model() -> str:
    """Model routed via aitr (classify / cheap-ok); falls back loudly to the
    previous hardcoded Sonnet default. Lazy: --dry-run never routes."""
    return routed_model("classify", "idea-backlog-recategorize")


PROMPT = """You are classifying ideas extracted from Matt Eisner's vault into one of 7 categories. Matt is Head of Growth at Zerg AI AND he has many personal-life ideas, side-business ideas, travel/shopping ideas. Distinguish carefully — don't bucket Matt's personal businesses as "Zerg products."

CATEGORIES:

  zerg-product       : New microproducts/features/GTM motions WITHIN the Zerg portfolio
                       (Zergboard, Zergwallet, Zergmail, ZergStack, ZergAlytics, Zerg Solutions).
                       Or explicitly framed as something Zerg should build.

  zerg-content       : Blog posts, launches, social hooks, thesis pieces FOR Zerg.

  zerg-tooling       : Scripts/skills/automations Matt builds for HIS Zerg work
                       (internal-use tools, NOT products to sell).

  personal-venture   : Matt's OWN potential side-business / startup ideas, real estate plays,
                       small businesses, lifestyle businesses, investment vehicles, financial
                       products HE might run or co-found. NOT Zerg products.
                       Examples: bagel shop, Detroit real estate, music studio, side ventures.

  personal-life      : Travel, food, hobbies, family, fitness, lifestyle, life-design,
                       relationships, mental-models for living, learning ideas.

  shopping           : Things to buy, gift ideas, products to try, books/films/music to acquire,
                       material wants. Concrete acquisition-shaped.

  research           : Thought experiments, "what if" essays, intellectual open questions,
                       research papers. Not a product, not a venture.

KEY HEURISTIC: If a "business idea" is clearly something MATT might run himself (small biz, real
estate, side venture), use personal-venture, NOT zerg-product. Zerg-product is reserved for things
within Zerg's portfolio (Zerg* prefixed products) OR things explicitly framed as Zerg should build.

For each item below, return a JSON object with the new category. Return STRICT JSON: an array of {n}
objects, in input order, each with:
  {{ "id": "<idea-id>", "category": "<one of the 7 categories>" }}

Items to classify:
{items}

Return ONLY the JSON array. No prose."""


def parse_excerpts(body: str) -> list[str]:
    out: list[str] = []
    in_section = False
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("## Source excerpt"):
            in_section = True
            continue
        if in_section and s.startswith("## "):
            break
        if in_section and s.startswith(">"):
            out.append(s.lstrip("> ").strip())
    return out


def build_block(idx: int, idea_id: str, title: str, subcategory: str | None, tags: list[str], excerpts: list[str], current_cat: str) -> str:
    src = "; ".join(excerpts[:3])[:300]
    tag_str = ",".join(tags or [])
    return (
        f"\n[{idx}] id: {idea_id}\n"
        f"current category: {current_cat}\n"
        f"title: {title}\n"
        f"subcategory: {subcategory or '(none)'}\n"
        f"tags: {tag_str}\n"
        f"source: {src}\n"
    )


def classify_batch(client, items: list[dict]) -> dict[str, str]:
    blocks = "\n".join(
        build_block(
            i + 1,
            it["id"],
            it["title"],
            it["subcategory"],
            it["tags"],
            it["excerpts"],
            it["current_cat"],
        )
        for i, it in enumerate(items)
    )
    prompt = PROMPT.format(n=len(items), items=blocks)
    msg = client.messages.create(
        model=_model(),
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()
    try:
        rows = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    out: dict[str, str] = {}
    for r in rows:
        if isinstance(r, dict) and r.get("id") and r.get("category") in CATEGORIES:
            out[r["id"]] = r["category"]
    return out


def move_file(p: Path, new_cat: str, in_inbox: bool, in_archive: bool) -> Path:
    """Move file to the right folder for new_cat."""
    if in_archive:
        new_path = ARCHIVE_DIR / new_cat / p.name
    elif in_inbox:
        new_path = INBOX_DIR / new_cat / p.name
    else:
        new_path = category_dir(new_cat) / p.name
    new_path.parent.mkdir(parents=True, exist_ok=True)
    n = 2
    while new_path.exists() and new_path != p:
        new_path = new_path.parent / f"{p.stem}-{n}.md"
        n += 1
    if new_path != p:
        p.rename(new_path)
    return new_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--batch-size", type=int, default=15)
    ap.add_argument("--include-inbox", action="store_true", default=True)
    ap.add_argument("--no-include-inbox", dest="include_inbox", action="store_false")
    ap.add_argument("--include-archive", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    todo: list[tuple[Path, dict, str]] = []
    for p in iter_all_ideas(include_inbox=args.include_inbox, include_archive=args.include_archive):
        try:
            meta, body = read_file(p)
        except Exception:
            continue
        items_data = {
            "id": meta.get("id"),
            "title": meta.get("title") or p.stem,
            "subcategory": meta.get("subcategory"),
            "tags": meta.get("tags") or [],
            "excerpts": parse_excerpts(body),
            "current_cat": meta.get("category"),
        }
        todo.append((p, meta, body, items_data))

    if args.limit:
        todo = todo[: args.limit]

    print(f"items to classify: {len(todo)}")
    if not todo:
        return 0

    if args.dry_run:
        print("(dry-run — sample of first 5)")
        for p, meta, _, _ in todo[:5]:
            print(f"  {meta.get('category'):<12}  {meta.get('title','?')[:60]}")
        return 0

    from max_client import make_client  # noqa
    client = make_client(source="idea-backlog/recategorize")

    started = time.time()
    processed = changed = errors = 0
    bs = args.batch_size

    in_inbox_set = set()
    in_archive_set = set()
    for p, _, _, _ in todo:
        if INBOX_DIR in p.parents:
            in_inbox_set.add(p)
        elif ARCHIVE_DIR in p.parents:
            in_archive_set.add(p)

    for batch_idx in range(0, len(todo), bs):
        batch = todo[batch_idx : batch_idx + bs]
        items = [b[3] for b in batch]
        try:
            mapping = classify_batch(client, items)
        except Exception as e:
            errors += 1
            print(f"  batch {batch_idx//bs} error: {e}", file=sys.stderr)
            continue

        for p, meta, body, _ in batch:
            new_cat = mapping.get(meta.get("id"))
            if not new_cat or new_cat == meta.get("category"):
                processed += 1
                continue
            old_cat = meta.get("category")
            meta["category"] = new_cat
            write_file(p, meta, body)
            try:
                move_file(p, new_cat, p in in_inbox_set, p in in_archive_set)
                changed += 1
            except Exception as e:
                print(f"  move failed for {p.name}: {e}", file=sys.stderr)
            processed += 1

        elapsed = time.time() - started
        print(f"  batch {batch_idx//bs + 1}/{(len(todo)+bs-1)//bs}  processed={processed}  changed={changed}  t={elapsed:.0f}s")

    log_event(
        "recategorize_run",
        source="recategorize.py",
        processed=processed,
        changed=changed,
        errors=errors,
    )
    print(f"\nrecategorize complete:")
    print(f"  processed: {processed}")
    print(f"  changed:   {changed}")
    print(f"  errors:    {errors}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
