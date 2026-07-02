#!/usr/bin/env python3
"""llm-wiki — Karpathy LLM Wiki distiller: raw/ sources -> LLM-distilled wiki/ of
interlinked Obsidian articles + index, with outputs/ for shareable deliverables.

The agent reads the compact wiki, never the raw originals again — that's the
token-saving payoff. This script owns the deterministic plumbing (scaffold,
ingest incl. defuddle for URLs, plan the article worklist, rebuild the index,
status). The distillation step itself (writing wiki articles from raw) is LLM
work, guided by the per-KB CLAUDE.md schema + the worklist.

Pure stdlib + subprocess (defuddle for URLs). Writes only under the KB root.

Usage:
    distill.py init   <kb> [--root DIR]
    distill.py ingest <kb> <path-or-url> [more...] [--root DIR]
    distill.py plan   <kb> [--root DIR]      # propose wiki articles from raw/
    distill.py index  <kb> [--root DIR]      # rebuild wiki/index.md
    distill.py status <kb> [--root DIR]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
DEFAULT_ROOT = (HOME / "Obsidian/Zerg"
                / "MattZerg" / "KnowledgeBases")

SCHEMA = """\
# CLAUDE.md — knowledge-base operating rules for `{kb}`

This is a Karpathy-style LLM Wiki. Three folders:
- `raw/` — source material (papers, scraped articles, notes, data). Append-only;
  never edit raw files, only add. Each has YAML frontmatter with `source` + `added`.
- `wiki/` — YOUR distilled output. One Obsidian-flavored markdown article per
  concept. Encyclopedia tone, dense, deduplicated. Cross-link with `[[wikilinks]]`.
  `wiki/index.md` summarizes the whole KB (rebuilt by `distill.py index`).
- `outputs/` — deliverables built FROM the wiki (briefs, decks, posts).

## Distillation rules (raw -> wiki)
1. Read `wiki/_worklist.md` for the proposed articles + which raw sources feed each.
2. For each article: read ONLY its mapped raw sources, write a dense `wiki/<Concept>.md`
   with frontmatter (`tags`, `sources:` list), encyclopedia-style body, and
   `[[wikilinks]]` to related articles.
3. Deduplicate across articles — one fact lives in one place; link, don't repeat.
4. After writing, run `distill.py index {kb}` to refresh the index.
5. Once distilled, downstream tasks read `wiki/` only — never re-read `raw/`.

## Don't
- Don't edit raw/. Don't let wiki articles balloon — distill, don't copy.
- Don't invent facts not in the mapped raw sources; cite them in `sources:`.
"""


def kb_root(args) -> Path:
    return Path(args.root).expanduser() if args.root else DEFAULT_ROOT


def kb_dir(args) -> Path:
    return kb_root(args) / args.kb


def slugify(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", s).strip().lower()
    return re.sub(r"[\s_-]+", "-", s)[:60] or "untitled"


def cmd_init(args):
    d = kb_dir(args)
    for sub in ("raw", "wiki", "outputs"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    schema = d / "CLAUDE.md"
    if not schema.exists():
        schema.write_text(SCHEMA.format(kb=args.kb))
    manifest = d / "raw" / "_manifest.json"
    if not manifest.exists():
        manifest.write_text("[]\n")
    idx = d / "wiki" / "index.md"
    if not idx.exists():
        idx.write_text(f"# {args.kb} — wiki index\n\n_No articles yet. Run `plan` then distill._\n")
    print(f"[init] {d}\n   raw/ wiki/ outputs/ + CLAUDE.md ready")
    return 0


def _manifest(d: Path) -> list:
    p = d / "raw" / "_manifest.json"
    try:
        return json.loads(p.read_text())
    except Exception:
        return []


def _save_manifest(d: Path, rows: list):
    (d / "raw" / "_manifest.json").write_text(json.dumps(rows, indent=2) + "\n")


def cmd_ingest(args):
    d = kb_dir(args)
    raw = d / "raw"
    if not raw.exists():
        raise SystemExit(f"KB not initialized: {d} (run `init` first)")
    rows = _manifest(d)
    seen = {r.get("source") for r in rows}
    added = 0
    for src in args.sources:
        if src in seen:
            print(f"   skip (already ingested): {src}")
            continue
        if src.startswith("http://") or src.startswith("https://"):
            slug = slugify(src.split("//", 1)[-1])
            dest = raw / f"{slug}.md"
            try:
                out = subprocess.run(["defuddle", "parse", src, "--md"],
                                     capture_output=True, text=True, timeout=120)
                body = out.stdout.strip() or "<defuddle returned empty>"
            except Exception as e:
                body = f"<defuddle failed: {e}>"
            dest.write_text(f"---\nsource: {src}\nadded: ingest\n---\n\n{body}\n")
        else:
            sp = Path(src).expanduser()
            if not sp.exists():
                print(f"   skip (not found): {src}")
                continue
            dest = raw / f"{slugify(sp.stem)}{sp.suffix or '.md'}"
            shutil.copy2(sp, dest)
        rows.append({"source": src, "file": dest.name})
        seen.add(src)
        added += 1
        print(f"   + {dest.name}  <- {src}")
    _save_manifest(d, rows)
    print(f"[ingest] {added} added; {len(rows)} raw sources total")
    return 0


def _first_heading(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("# ").strip()
    return ""


def cmd_plan(args):
    d = kb_dir(args)
    raw = d / "raw"
    files = [p for p in raw.glob("*") if p.suffix.lower() in (".md", ".txt") and not p.name.startswith("_")]
    if not files:
        raise SystemExit(f"no raw sources in {raw} (ingest first)")
    items = []
    for p in files:
        text = p.read_text(errors="replace")
        title = _first_heading(text) or p.stem.replace("-", " ").title()
        items.append((title, p.name))
    lines = [f"# {args.kb} — wiki worklist", "",
             "Proposed articles (one per concept). Map each to its raw sources, then",
             "distill per `CLAUDE.md`. Merge near-duplicate titles into one article.", ""]
    for title, fname in sorted(items):
        lines.append(f"- [ ] **[[{title}]]**  ← `raw/{fname}`")
    lines += ["", f"_{len(items)} raw sources → ~{len(set(t for t,_ in items))} candidate articles._",
              "_Cluster related sources into single articles; don't make one stub per file._"]
    out = d / "wiki" / "_worklist.md"
    out.write_text("\n".join(lines) + "\n")
    print(f"[plan] wrote {out} ({len(items)} candidates)")
    return 0


def cmd_index(args):
    d = kb_dir(args)
    wiki = d / "wiki"
    arts = [p for p in wiki.glob("*.md") if p.name not in ("index.md", "_worklist.md")]
    lines = [f"# {args.kb} — wiki index", "",
             f"{len(arts)} articles. The agent reads these, not `raw/`.", ""]
    for p in sorted(arts):
        text = p.read_text(errors="replace")
        title = _first_heading(text) or p.stem
        summary = ""
        for ln in text.splitlines():
            s = ln.strip()
            if s and not s.startswith("#") and not s.startswith("---") and ":" not in s[:12]:
                summary = s[:120]
                break
        lines.append(f"- [[{p.stem}|{title}]] — {summary}")
    (wiki / "index.md").write_text("\n".join(lines) + "\n")
    print(f"[index] rebuilt {wiki/'index.md'} ({len(arts)} articles)")
    return 0


def cmd_status(args):
    d = kb_dir(args)
    if not d.exists():
        raise SystemExit(f"no such KB: {d}")
    raw = list((d / "raw").glob("*")) if (d / "raw").exists() else []
    raw = [p for p in raw if not p.name.startswith("_")]
    wiki = [p for p in (d / "wiki").glob("*.md") if p.name not in ("index.md", "_worklist.md")] if (d / "wiki").exists() else []
    outs = list((d / "outputs").glob("*")) if (d / "outputs").exists() else []
    newest_raw = max((p.stat().st_mtime for p in raw), default=0)
    newest_wiki = max((p.stat().st_mtime for p in wiki), default=0)
    stale = newest_raw > newest_wiki and wiki
    print(f"[status] {d.name}: raw={len(raw)} wiki={len(wiki)} outputs={len(outs)}")
    print(f"   {'STALE — raw newer than wiki; re-distill' if stale else 'wiki up to date with raw'}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Karpathy LLM Wiki distiller (raw/wiki/outputs).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("init", "plan", "index", "status"):
        sp = sub.add_parser(name)
        sp.add_argument("kb")
        sp.add_argument("--root", default=None)
    sp = sub.add_parser("ingest")
    sp.add_argument("kb")
    sp.add_argument("sources", nargs="+")
    sp.add_argument("--root", default=None)
    args = ap.parse_args(argv)
    return {"init": cmd_init, "ingest": cmd_ingest, "plan": cmd_plan,
            "index": cmd_index, "status": cmd_status}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
