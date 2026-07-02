#!/usr/bin/env python3
"""Stage the web-view bundle: copy index.json + decisions.json + zergboard-cards.json
next to index.html, ready for upload to any static host (Cloudflare Pages,
Fly.io, S3, etc.).

Usage:
    build.py [--out DIR]

Produces:
    <out>/index.html
    <out>/data/index.json
    <out>/data/decisions.json
    <out>/data/zergboard-cards.json   (if present)

Default <out> is `~/.claude/skills/gtm-hub/web/dist/`.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent

# Vault root resolves from $ZERG_VAULT (preferred), then a sensible default for
# Matt's iCloud-backed checkout. Hardcoding the iCloud path breaks for any
# other user and breaks again if iCloud path renames. Override via:
#   ZERG_VAULT=/path/to/Zerg python3 build.py
_DEFAULT_VAULT = Path.home() / "Obsidian/Zerg"
VAULT = Path(os.environ.get("ZERG_VAULT", _DEFAULT_VAULT)).expanduser()
META = VAULT / "MattZerg/Projects/Zerg-Production/Growth/_meta"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=str(SKILL_DIR / "web" / "dist"))
    args = p.parse_args()
    out = Path(args.out)
    data_dir = out / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    src_html = SKILL_DIR / "web" / "index.html"
    if not src_html.exists():
        print(f"missing {src_html}", file=sys.stderr)
        return 1
    shutil.copy2(src_html, out / "index.html")
    print(f"copied index.html → {out / 'index.html'}")
    present: list[str] = []
    missing: list[str] = []
    for name in ("index.json", "decisions.json", "zergboard-cards.json"):
        src = META / name
        if not src.exists():
            print(f"  (skip {name} — not present)")
            missing.append(name)
            continue
        shutil.copy2(src, data_dir / name)
        print(f"copied {name} → {data_dir / name}")
        present.append(name)

    # Build-time defaults for entity-type labels. A new type can be added by
    # editing this dict (no HTML edit needed) — and a vault-side
    # `<META>/types.json` override-file is honored if present, so future
    # vault-only updates work too.
    DEFAULT_TYPES = {
        "experiment":  {"label": "Experiments", "emoji": "🧪"},
        "content":     {"label": "Content",     "emoji": "📝"},
        "prospect":    {"label": "Solutions",   "emoji": "💼"},
        "bd_target":   {"label": "BD",          "emoji": "🤝"},
        "launch":      {"label": "Launches",    "emoji": "🚀"},
        "theme":       {"label": "Themes",      "emoji": "🧭"},
        "metric":      {"label": "Metrics",     "emoji": "📊"},
        "workstream":  {"label": "Workstreams", "emoji": "🧱"},
    }
    types_override = META / "types.json"
    if types_override.exists():
        try:
            override = json.loads(types_override.read_text())
            DEFAULT_TYPES.update(override.get("types", {}) if isinstance(override, dict) else {})
            print(f"  (merged types override from {types_override.name})")
        except json.JSONDecodeError as exc:
            print(f"  (skip types override — invalid JSON: {exc})")

    # _meta.json lets the UI distinguish "no decisions queued (0 rows)" from
    # "decisions.json was missing at build time" — without this, both states
    # render as an identical empty list and the missing-source case stays
    # invisible until someone notices the staleness.
    meta = {
        "generated_at": dt.datetime.now(dt.timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
        "present": present,
        "missing": missing,
        "types": DEFAULT_TYPES,
    }
    (data_dir / "_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"wrote _meta.json (present={len(present)} missing={len(missing)} types={len(DEFAULT_TYPES)})")

    print(f"\nstaged at {out}")
    print(f"preview locally:  cd {out} && python3 -m http.server 8000")
    print(f"upload via wrangler/fly/s3 from {out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
