#!/usr/bin/python3
"""write_inbox: emit clustered ideas as `_inbox/<category>/<slug>.md` files.

Stage 3 of the seed sweep. Reads clusters.jsonl, writes one file per cluster
into Ideas/_inbox/<auto-category>/. Status defaults to `raw`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "_lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from frontmatter import write_file  # noqa: E402
from idea_io import default_meta  # noqa: E402
from slugify import slugify  # noqa: E402
from usage import log_event  # noqa: E402
from vault_paths import INBOX_DIR, CATEGORIES, workdir  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=None)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    wd = workdir()
    in_path = Path(args.input) if args.input else wd / "clusters.jsonl"
    if not in_path.exists():
        print(f"no clusters at {in_path} — run dedupe.py first", file=sys.stderr)
        return 2

    clusters = [json.loads(line) for line in in_path.read_text().splitlines() if line.strip()]
    if args.limit:
        clusters = clusters[: args.limit]

    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    skipped = 0

    for c in clusters:
        cat = c.get("category") if c.get("category") in CATEGORIES else "research"
        title = (c.get("title") or "(untitled)").strip()
        sources = [f"[[{p}]]" for p in (c.get("source_paths") or [])]

        meta = default_meta(
            title=title,
            category=cat,
            subcategory=c.get("subcategory"),
            tags=[t for t in (c.get("tags") or []) if t],
            status="raw",
            sources=sources,
        )

        body_parts = [
            "## Idea",
            (c.get("one_line") or "").strip(),
            "",
            "## Why interesting",
            (c.get("why_interesting") or "").strip(),
            "",
            "## Open questions",
            "- ",
        ]
        excerpts = c.get("source_excerpts") or []
        if excerpts:
            body_parts += ["", "## Source excerpts"]
            for ex in excerpts:
                body_parts.append(f"> {ex}")
        body = "\n".join(body_parts)

        slug = slugify(title)
        out_dir = INBOX_DIR / cat
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{slug}.md"
        n = 2
        while out_path.exists():
            out_path = out_dir / f"{slug}-{n}.md"
            n += 1
        write_file(out_path, meta, body)
        written += 1

    print(f"wrote {written} files into {INBOX_DIR}")
    print(f"  by category:")
    by_cat: dict[str, int] = {}
    for p in INBOX_DIR.rglob("*.md"):
        by_cat[p.parent.name] = by_cat.get(p.parent.name, 0) + 1
    for k, v in sorted(by_cat.items()):
        print(f"    {k}: {v}")
    print("\nnext: triage.py")
    log_event(
        "write_inbox_run",
        source="write_inbox.py",
        files_written=written,
        by_category=by_cat,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
