#!/usr/bin/python3
"""triage: walk Ideas/_inbox/ one item at a time.

Two modes:
  --interactive (default)  : prompt per item — keep / merge / kill / defer / to-task
  --list                   : just list inbox items with metadata, no prompts
  --batch <action>         : apply the same action to all items (use with care)

`keep` promotes via promote.py (status → active, moves to category folder).
`merge` requires `--into <id>` and folds sources into the target.
`kill` archives.
`defer` leaves the item in inbox but bumps `last_touched`.
`to-task` skips the idea stage and routes straight to inbox.md (uses to_task.py).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "_lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from frontmatter import read_file, update_field, write_file  # noqa: E402
from idea_io import today_iso  # noqa: E402
from usage import log_event  # noqa: E402
from vault_paths import INBOX_DIR, VAULT_ROOT  # noqa: E402

SCRIPTS_DIR = Path(__file__).resolve().parent


def list_inbox(category: str | None = None) -> list[Path]:
    if not INBOX_DIR.exists():
        return []
    base = INBOX_DIR / category if category else INBOX_DIR
    if not base.exists():
        return []
    return sorted(base.rglob("*.md"))


def show_item(p: Path, meta: dict, body: str) -> None:
    print("─" * 70)
    print(f"  📥 {p.relative_to(VAULT_ROOT)}")
    print(f"     id: {meta.get('id')}")
    print(f"     title: {meta.get('title')}")
    print(f"     suggested category: {meta.get('category')}")
    print(f"     subcategory: {meta.get('subcategory')}")
    tags = meta.get("tags") or []
    print(f"     tags: {', '.join(tags) if tags else '(none)'}")
    sources = meta.get("sources") or []
    if sources:
        print(f"     sources ({len(sources)}):")
        for s in sources[:5]:
            print(f"       - {s}")
        if len(sources) > 5:
            print(f"       ... +{len(sources)-5} more")
    snippet = (body or "").strip().splitlines()[:6]
    if snippet:
        print("     body:")
        for line in snippet:
            print(f"       {line}")
    print()


def cmd(*args: str) -> int:
    return subprocess.run(args, check=False).returncode


def merge(src: Path, target_id: str) -> int:
    """Append src's sources + body excerpt into target idea, then archive src."""
    from idea_io import find_by_id  # local
    target = find_by_id(target_id, include_inbox=True, include_archive=False)
    if target is None:
        print(f"merge target not found: {target_id}", file=sys.stderr)
        return 2
    src_meta, src_body = read_file(src)
    tgt_meta, tgt_body = read_file(target)
    tgt_meta["sources"] = list({*(tgt_meta.get("sources") or []), *(src_meta.get("sources") or [])})
    tgt_meta["last_touched"] = today_iso()
    extra_excerpt = ""
    if "## Source excerpt" in src_body:
        extra_excerpt = src_body.split("## Source excerpt", 1)[1]
    new_body = tgt_body.rstrip() + "\n\n## Merged from " + src.stem + "\n" + extra_excerpt.strip() + "\n"
    write_file(target, tgt_meta, new_body)
    src.unlink()
    print(f"merged {src.name} → {target.name}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--batch", default=None, choices=("keep", "kill", "defer"))
    ap.add_argument("--limit", type=int, default=0, help="0 = no limit")
    ap.add_argument("--category", default=None, help="restrict to one inbox category (product/content/tooling/personal/research)")
    args = ap.parse_args()

    items = list_inbox(category=args.category)
    if not items:
        print("inbox empty.")
        return 0

    if args.limit:
        items = items[: args.limit]

    if args.list:
        for p in items:
            try:
                meta, body = read_file(p)
            except Exception:
                continue
            show_item(p, meta, body)
        print(f"\n{len(items)} items in inbox.")
        return 0

    if args.batch:
        for p in items:
            if args.batch == "keep":
                cmd(str(SCRIPTS_DIR / "promote.py"), p.stem)
            elif args.batch == "kill":
                cmd(str(SCRIPTS_DIR / "kill.py"), p.stem, "batch-killed")
            elif args.batch == "defer":
                update_field(p, last_touched=today_iso())
        print(f"batch {args.batch}: {len(items)} items")
        return 0

    # interactive
    print(f"{len(items)} items in inbox. Press 'q' anytime to quit.\n")
    for i, p in enumerate(items, 1):
        try:
            meta, body = read_file(p)
        except Exception as e:
            print(f"  skip {p.name}: {e}")
            continue
        print(f"\n[{i}/{len(items)}]")
        show_item(p, meta, body)
        choice = input("  k(eep) / m(erge <id>) / x(kill [reason]) / d(efer) / t(o-task [bucket]) / s(kip) / q(uit): ").strip()
        if not choice or choice == "s":
            continue
        if choice == "q":
            break
        action, _, rest = choice.partition(" ")
        if action == "k":
            cmd(str(SCRIPTS_DIR / "promote.py"), p.stem)
            log_event("triage", source="triage.py", action="keep", id=meta.get("id"))
        elif action == "m":
            target = rest.strip()
            if not target:
                print("  merge needs a target id; skipping")
                continue
            merge(p, target)
            log_event("triage", source="triage.py", action="merge", id=meta.get("id"), into=target)
        elif action == "x":
            cmd(str(SCRIPTS_DIR / "kill.py"), p.stem, rest.strip() or "rejected during triage")
            log_event("triage", source="triage.py", action="kill", id=meta.get("id"))
        elif action == "d":
            update_field(p, last_touched=today_iso())
            log_event("triage", source="triage.py", action="defer", id=meta.get("id"))
            print(f"  deferred {p.name}")
        elif action == "t":
            bucket = rest.strip() or "To Do"
            # to-task expects an existing idea id; promote from inbox first, then to-task
            cmd(str(SCRIPTS_DIR / "promote.py"), p.stem)
            cmd(str(SCRIPTS_DIR / "to_task.py"), p.stem, "--bucket", bucket)
            log_event("triage", source="triage.py", action="to-task", id=meta.get("id"), bucket=bucket)
        else:
            print(f"  unknown: {choice!r}; skipping")

    return 0


if __name__ == "__main__":
    sys.exit(main())
