#!/usr/bin/python3
"""score: grade each inbox idea on depth + viability via Sonnet 4.5.

Adds two new frontmatter fields:
  depth      : 1-5  (how developed the idea is in source material)
  viability  : 1-5  (how plausibly this could work as a venture/feature/content)
  scored_at  : ISO date

Batches 10 items per LLM call to amortize prompt overhead. Resumable.

Usage:
    score.py [--limit N] [--batch-size 10] [--dry-run]

Cost estimate: ~$1 across all 1,388 inbox items, ~30 min wall.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ZERG_CFG = Path.home() / ".config" / "zerg"
if str(ZERG_CFG) not in sys.path:
    sys.path.insert(0, str(ZERG_CFG))

_LIB = Path(__file__).resolve().parent / "_lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from frontmatter import read_file, write_file  # noqa: E402
from usage import log_event  # noqa: E402
from vault_paths import INBOX_DIR  # noqa: E402

from routed_model import routed_model  # noqa: E402


def _model() -> str:
    """Model routed via aitr (classify / cheap-ok); falls back loudly to the
    previous hardcoded Sonnet default. Lazy: --dry-run never routes."""
    return routed_model("classify", "idea-backlog-score")


SCORING_PROMPT = """You are scoring a batch of {n} extracted "ideas" from Matt Eisner's personal vault. Each was extracted by an LLM from his notes, and now needs a quality score so the long tail can be filtered.

For EACH item, rate two dimensions on a 1-5 scale based ONLY on what's actually in the source material (the verbatim source excerpts shown — NOT the LLM-generated commentary):

DEPTH (how developed the idea is in the source):
  1 = one-line mention, throwaway
  2 = a sentence or two, no specifics
  3 = paragraph-level, some mechanics mentioned
  4 = multiple specifics (names, numbers, mechanisms, examples)
  5 = fully fleshed concept with hook, mechanics, and target

VIABILITY (how plausibly this could work in the world):
  1 = vague / not really an idea / already-done thing / impossible
  2 = exists but undifferentiated, weak hook
  3 = plausible but uncertain, would need work
  4 = clear opportunity, real differentiator visible
  5 = obvious win or already partially proven

Return STRICT JSON: an array of {n} objects, in the same order as input. Each object:
  {{ "id": "<idea-id>", "depth": <1-5>, "viability": <1-5>, "kill": <true|false> }}

Set kill=true only if depth=1 AND viability<=2 (clearly throwaway). Otherwise kill=false.

Items to score:
{items}

Return ONLY the JSON array. No prose."""


def build_item_block(idx: int, idea_id: str, title: str, sources: list[str], excerpts: list[str]) -> str:
    src = "\n  ".join(f"- {s}" for s in sources[:5])
    exc = "\n  ".join(f"> {e}" for e in excerpts[:5])
    return (
        f"\n[{idx}] id: {idea_id}\n"
        f"title: {title}\n"
        f"sources:\n  {src}\n"
        f"verbatim source excerpts:\n  {exc}\n"
    )


def parse_excerpts(body: str) -> list[str]:
    out: list[str] = []
    in_section = False
    for line in body.splitlines():
        if line.strip().startswith("## Source excerpt"):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section and line.strip().startswith(">"):
            out.append(line.strip().lstrip("> ").strip())
    return out


def score_batch(client, items: list[dict]) -> dict[str, dict]:
    """Returns {id: {depth, viability, kill}} mapping. Empty dict on parse failure."""
    blocks = "\n".join(
        build_item_block(i + 1, it["id"], it["title"], it["sources"], it["excerpts"])
        for i, it in enumerate(items)
    )
    prompt = SCORING_PROMPT.format(n=len(items), items=blocks)

    msg = client.messages.create(
        model=_model(),
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()
    try:
        scores = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return {s.get("id"): s for s in scores if isinstance(s, dict) and s.get("id")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="0 = no limit")
    ap.add_argument("--batch-size", type=int, default=10)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rescore", action="store_true", help="re-score items even if already scored")
    args = ap.parse_args()

    if not INBOX_DIR.exists():
        print("inbox empty — nothing to score.")
        return 0

    files = sorted(INBOX_DIR.rglob("*.md"))
    todo: list[tuple[Path, dict, str]] = []
    for p in files:
        try:
            meta, body = read_file(p)
        except Exception:
            continue
        if not args.rescore and meta.get("depth") is not None:
            continue
        excerpts = parse_excerpts(body)
        todo.append((p, meta, body))

    if args.limit:
        todo = todo[: args.limit]

    print(f"inbox: {len(files)} items; pending score: {len(todo)}")
    if args.dry_run:
        for p, meta, _ in todo[:8]:
            print(f"  {meta.get('id')}  {meta.get('title','?')[:60]}")
        return 0
    if not todo:
        print("nothing to score.")
        return 0

    from max_client import make_client  # noqa
    client = make_client(source="idea-backlog/score")

    started = time.time()
    total_in = total_out = scored = killed = promoted_high = promoted_med = 0

    bs = args.batch_size
    for batch_idx in range(0, len(todo), bs):
        batch = todo[batch_idx : batch_idx + bs]
        items = []
        for p, meta, body in batch:
            items.append({
                "id": meta.get("id"),
                "title": meta.get("title") or p.stem,
                "sources": meta.get("sources") or [],
                "excerpts": parse_excerpts(body),
            })

        try:
            scores = score_batch(client, items)
            usage = None  # capture from message? skip for now
        except Exception as e:
            print(f"  batch {batch_idx//bs} error: {e}", file=sys.stderr)
            continue

        # Update files
        today = datetime.now().date().isoformat()
        for p, meta, body in batch:
            s = scores.get(meta.get("id"))
            if not s:
                continue
            depth = int(s.get("depth", 0)) if s.get("depth") is not None else None
            viability = int(s.get("viability", 0)) if s.get("viability") is not None else None
            kill_flag = bool(s.get("kill", False))
            if depth is None or viability is None:
                continue
            meta["depth"] = depth
            meta["viability"] = viability
            meta["scored_at"] = today
            write_file(p, meta, body)
            scored += 1
            if kill_flag:
                killed += 1
            elif depth >= 4 and viability >= 4:
                promoted_high += 1
            elif depth >= 3 and viability >= 3:
                promoted_med += 1

        elapsed = time.time() - started
        print(f"  batch {batch_idx//bs + 1}/{(len(todo)+bs-1)//bs}  scored cum={scored}  t={elapsed:.0f}s")

    log_event(
        "score_run",
        source="score.py",
        scored=scored,
        kill_flagged=killed,
        promote_high_eligible=promoted_high,
        promote_med_eligible=promoted_med,
    )
    print(f"\nscored: {scored}")
    print(f"  kill-flagged (depth=1, viability<=2): {killed}")
    print(f"  promote-high eligible (>=4/>=4):       {promoted_high}")
    print(f"  promote-medium eligible (>=3/>=3):     {promoted_med}")
    print(f"  remaining noise/uncertain:             {scored - killed - promoted_high - promoted_med}")
    print("\nnext: batch_triage.py --apply-scores  (to actually move things)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
