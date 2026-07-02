#!/usr/bin/env python3
"""One-shot migration: split prospects.md + bd-targets.md into per-entity files.

Also normalizes existing experiments/ frontmatter, seeds metric files for the
known NSMs, and seeds workstream/launch/theme directories.

Idempotent: re-running with existing per-file entities is safe (skip if file exists
unless --force).
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path
from typing import Any

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

from lib import frontmatter  # noqa: E402
from lib.entities import GROWTH_DIR  # noqa: E402


TODAY = dt.date.today().isoformat()


def slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


def write_entity(path: Path, meta: dict[str, Any], body: str, *, force: bool, dry_run: bool) -> str:
    if path.exists() and not force:
        return "skip"
    if dry_run:
        return "would-write"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = frontmatter.render(meta) + body
    path.write_text(text, encoding="utf-8")
    return "wrote"


# ---------- prospects.md ----------

PROSPECT_ROW = re.compile(r"^\|\s*([^|]+?)\s*\|")


def parse_prospects(text: str) -> list[dict[str, Any]]:
    """Parse the prospects.md table. Returns list of frontmatter dicts."""
    rows: list[dict[str, Any]] = []
    in_table = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("|") and "Company" in s and "Stage" in s:
            in_table = True
            continue
        if in_table:
            if not s.startswith("|"):
                in_table = False
                continue
            if set(s) <= set("|-: "):  # separator row
                continue
            parts = [p.strip() for p in s.strip("|").split("|")]
            if len(parts) < 8:
                continue
            company, stage, source, owner, last_touch, next_action, referrer, notes = parts[:8]
            if company.lower() == "company":
                continue
            slug = slugify(company)
            # Try to lift a score from notes
            score = None
            mscore = re.search(r"score\s+(\d+)/100", notes)
            if mscore:
                score = int(mscore.group(1))
            # Category guess from notes
            category = None
            mcat = re.search(r"\b(ai-dev-platform|customer-agent-platform|enterprise-ai-platform|agent-workflow-platform|generated-app-platform|ai-app-builder|ai-customer-agent|ai-gtm-workflow|ai-workflow-agent)\b", notes)
            if mcat:
                category = mcat.group(1)
            rows.append({
                "id": slug,
                "type": "prospect",
                "title": company,
                "status": stage,
                "owner": owner.lower() if owner else "matt",
                "created": last_touch or TODAY,
                "last_touch": last_touch or TODAY,
                "company": company,
                "source": source,
                "score": score,
                "category": category,
                "referrer": None if referrer in ("TBD", "—", "") else referrer,
                "next_action": next_action,
                "notes": notes,
            })
    return rows


def migrate_prospects(dry_run: bool, force: bool) -> tuple[int, int]:
    src = GROWTH_DIR / "prospects.md"
    if not src.exists():
        return 0, 0
    rows = parse_prospects(src.read_text(encoding="utf-8"))
    out_dir = GROWTH_DIR / "prospects"
    wrote = skipped = 0
    for r in rows:
        slug = r["id"]
        body = f"\n# {r['title']}\n\n{r.get('notes') or ''}\n"
        meta = {k: v for k, v in r.items() if k != "notes"}
        result = write_entity(out_dir / f"{slug}.md", meta, body, force=force, dry_run=dry_run)
        if result == "skip":
            skipped += 1
        else:
            wrote += 1
    return wrote, skipped


# ---------- bd-targets.md ----------

BD_CATEGORY_HEADERS = {
    "Integration partners": "integration",
    "Co-marketing partners": "co-marketing",
    "Podcast guesting": "podcast",
    "Ecosystem positioning": "ecosystem",
}


def parse_bd(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    current_cat: str | None = None
    in_table = False
    podcast_table = False
    for line in text.splitlines():
        # Match category header
        for header, cat in BD_CATEGORY_HEADERS.items():
            if line.startswith("## " + header):
                current_cat = cat
                in_table = False
                podcast_table = (cat == "podcast")
                break
        if current_cat is None:
            continue
        s = line.strip()
        if s.startswith("|") and ("Target" in s or "Why" in s or "Audience" in s):
            in_table = True
            continue
        if in_table:
            if not s.startswith("|"):
                in_table = False
                continue
            if set(s) <= set("|-: "):
                continue
            parts = [re.sub(r"\*\*", "", p).strip() for p in s.strip("|").split("|")]
            if len(parts) < 4:
                continue
            if parts[0].lower() in ("target", ""):
                continue
            target = parts[0]
            if podcast_table:
                # | Target | Audience | Pitch angle | Owner | Next |
                if len(parts) < 5:
                    continue
                audience = parts[1]
                why = parts[2]
                owner = parts[3]
                next_action = parts[4]
                status = "planned"
            else:
                # | Target | Status | Why | Owner | Next |
                if len(parts) < 5:
                    continue
                status = parts[1] or "planned"
                why = parts[2]
                owner = parts[3]
                next_action = parts[4]
                audience = None
            slug = slugify(target)
            rows.append({
                "id": slug,
                "type": "bd_target",
                "title": target,
                "status": status,
                "owner": owner.lower().split("+")[0].strip() or "matt",
                "created": TODAY,
                "last_touch": TODAY,
                "target": target,
                "category": current_cat,
                "audience": audience,
                "why": why,
                "next_action": next_action,
                "template_variant": {"integration": "integration", "co-marketing": "co-marketing", "podcast": "podcast", "ecosystem": "co-marketing"}[current_cat],
            })
    return rows


def migrate_bd(dry_run: bool, force: bool) -> tuple[int, int]:
    src = GROWTH_DIR / "bd-targets.md"
    if not src.exists():
        return 0, 0
    rows = parse_bd(src.read_text(encoding="utf-8"))
    out_dir = GROWTH_DIR / "bd"
    wrote = skipped = 0
    for r in rows:
        slug = r["id"]
        body = f"\n# {r['title']}\n\n## Why\n\n{r.get('why', '')}\n\n## Next\n\n{r.get('next_action', '')}\n"
        meta = {k: v for k, v in r.items() if k not in ("why", "next_action") or True}
        result = write_entity(out_dir / f"{slug}.md", meta, body, force=force, dry_run=dry_run)
        if result == "skip":
            skipped += 1
        else:
            wrote += 1
    return wrote, skipped


# ---------- content normalization ----------


def normalize_content(dry_run: bool) -> int:
    """Bring existing content-calendar files into hub schema.

    Maps `type: blog|launch|pseo-compare|...` → `kind`, sets `type: content`,
    mirrors `state` → `status`, ensures envelope fields exist.
    """
    cdir = GROWTH_DIR / "content"
    if not cdir.exists():
        return 0
    touched = 0
    for f in sorted(cdir.glob("*.md")):
        if f.name.startswith("_"):
            continue
        text = f.read_text(encoding="utf-8")
        meta, body = frontmatter.parse(text)
        if not meta:
            continue
        changes: dict[str, Any] = {}
        if meta.get("type") and meta.get("type") != "content":
            changes["kind"] = meta["type"]
            changes["type"] = "content"
        elif "type" not in meta:
            changes["type"] = "content"
        if "id" not in meta:
            changes["id"] = meta.get("slug") or f.stem
        if "status" not in meta and "state" in meta:
            changes["status"] = meta["state"]
        if "last_touch" not in meta:
            lt = TODAY
            slip_log = meta.get("slip_log")
            if isinstance(slip_log, list) and slip_log:
                last_entry = slip_log[-1]
                mdate = re.match(r"\d{4}-\d{2}-\d{2}", str(last_entry))
                if mdate:
                    lt = mdate.group(0)
            elif meta.get("created"):
                lt = str(meta["created"])
            changes["last_touch"] = lt
        if isinstance(meta.get("owner"), str) and meta["owner"][:1].isupper():
            changes["owner"] = meta["owner"].lower()
        if not changes:
            continue
        if dry_run:
            touched += 1
            continue
        new_meta = dict(meta)
        new_meta.update(changes)
        f.write_text(frontmatter.render(new_meta) + body, encoding="utf-8")
        touched += 1
    return touched


# ---------- experiments normalization ----------

def normalize_experiments(dry_run: bool) -> int:
    exp_dir = GROWTH_DIR / "experiments"
    if not exp_dir.exists():
        return 0
    touched = 0
    for f in sorted(exp_dir.glob("exp-*.md")):
        if f.name.startswith("_"):
            continue
        text = f.read_text(encoding="utf-8")
        meta, body = frontmatter.parse(text)
        if not meta:
            continue
        # Add envelope fields if missing, never overwrite real data
        changes = {}
        if "type" not in meta:
            changes["type"] = "experiment"
        if "title" not in meta and "name" in meta:
            changes["title"] = meta["name"]
        if "last_touch" not in meta:
            # use started/concluded/created/today (first non-empty)
            for k in ("concluded", "started", "created"):
                v = meta.get(k)
                if v not in (None, ""):
                    changes["last_touch"] = v
                    break
            if "last_touch" not in changes:
                changes["last_touch"] = TODAY
        if "owner" not in meta:
            changes["owner"] = "matt"
        # Normalize RICE_score → rice_score
        if "RICE_score" in meta and "rice_score" not in meta:
            changes["rice_score"] = meta["RICE_score"]
        # Normalize phase
        if "phase" not in meta and "problem" in meta:
            problem = meta.get("problem")
            if problem and not meta.get("phase"):
                # default phase-1 for kill_date within phase-1 window, else phase-2-c1
                changes["phase"] = "phase-1" if dt.date.fromisoformat("2026-05-05") <= (
                    __import__("datetime").date.fromisoformat(meta.get("kill_date") or "2026-06-13")
                    if (meta.get("kill_date") or "") else dt.date(2026, 6, 13)
                ) <= dt.date(2026, 6, 13) else "phase-2-c1"
        if not changes:
            continue
        if dry_run:
            touched += 1
            continue
        new_meta = dict(meta)
        new_meta.update(changes)
        # Move RICE_score → rice_score
        new_meta.pop("RICE_score", None)
        f.write_text(frontmatter.render(new_meta) + body, encoding="utf-8")
        touched += 1
    return touched


# ---------- seed new entity types ----------

NSM_SEEDS = [
    {
        "id": "wapw",
        "title": "Weekly Active Pro Workspaces (WAPW)",
        "category": "nsm",
        "unit": "count",
        "value": None,
        "target": 50,
        "instrumentation_owner": "matt",
        "source_system": "zergalytics",
    },
    {
        "id": "qpv",
        "title": "Qualified Pipeline Value — 30d trailing",
        "category": "nsm",
        "unit": "USD",
        "value": None,
        "target": 100000,
        "instrumentation_owner": "matt",
        "source_system": "manual",
    },
]

SUPPORTING_METRIC_SEEDS = [
    {"id": "activated-accounts", "title": "Activated accounts (weekly)", "unit": "count"},
    {"id": "paid-conversions", "title": "Paid conversions (weekly)", "unit": "count"},
    {"id": "activation-rate", "title": "Signup → activation rate", "unit": "%"},
    {"id": "k-factor", "title": "Product referral K-factor", "unit": "ratio"},
]


def seed_metrics(dry_run: bool, force: bool) -> tuple[int, int]:
    out_dir = GROWTH_DIR / "metrics"
    wrote = skipped = 0
    for seed in NSM_SEEDS + SUPPORTING_METRIC_SEEDS:
        slug = seed["id"]
        meta = {
            "id": slug,
            "type": "metric",
            "title": seed["title"],
            "status": "instrumented" if seed.get("value") not in (None, "") else "not-instrumented",
            "owner": "matt",
            "created": TODAY,
            "last_touch": TODAY,
            "slug": slug,
            "display_name": seed["title"],
            "unit": seed["unit"],
            "value": seed.get("value"),
            "target": seed.get("target"),
            "category": seed.get("category"),
            "instrumentation_owner": seed.get("instrumentation_owner", "matt"),
            "source_system": seed.get("source_system", "manual"),
        }
        body = f"\n# {seed['title']}\n\n## History\n\n_(populate as values land)_\n"
        result = write_entity(out_dir / f"{slug}.md", meta, body, force=force, dry_run=dry_run)
        if result == "skip":
            skipped += 1
        else:
            wrote += 1
    return wrote, skipped


def seed_launches(dry_run: bool, force: bool) -> tuple[int, int]:
    out_dir = GROWTH_DIR / "launches"
    seeds = [
        {
            "id": "zergboard-public-launch",
            "title": "Zergboard public launch",
            "status": "drafting",
            "product": "Zergboard",
            "channels": ["product-hunt", "hacker-news", "twitter", "linkedin", "reddit"],
        },
    ]
    wrote = skipped = 0
    for s in seeds:
        meta = {
            "id": s["id"],
            "type": "launch",
            "title": s["title"],
            "status": s["status"],
            "owner": "matt",
            "created": TODAY,
            "last_touch": TODAY,
            "slug": s["id"],
            "product": s["product"],
            "ship_date": None,
            "channels": s.get("channels", []),
        }
        body = f"\n# {s['title']}\n\n_See `Writing/Launches/` for announcement draft._\n"
        result = write_entity(out_dir / f"{s['id']}.md", meta, body, force=force, dry_run=dry_run)
        if result == "skip":
            skipped += 1
        else:
            wrote += 1
    return wrote, skipped


def seed_themes(dry_run: bool, force: bool) -> tuple[int, int]:
    out_dir = GROWTH_DIR / "themes"
    # Per the existing themes.md the inbox is empty — just create the directory marker.
    out_dir.mkdir(parents=True, exist_ok=True)
    readme = out_dir / "_about.md"
    if readme.exists():
        return 0, 1
    content = "# Themes\n\nOne file per validated/tracked theme. See `../themes.md` for the methodology framework.\n"
    if dry_run:
        return 1, 0
    readme.write_text(content, encoding="utf-8")
    return 1, 0


def seed_workstreams(dry_run: bool, force: bool) -> tuple[int, int]:
    """Mirror ~/.claude/workstreams/state.json. Always overwrites — it's a mirror."""
    out_dir = GROWTH_DIR / "workstreams"
    out_dir.mkdir(parents=True, exist_ok=True)
    readme = out_dir / "_about.md"
    if not readme.exists() and not dry_run:
        readme.write_text(
            "# Workstreams\n\nMirror of `~/.claude/workstreams/state.json`. Refreshed by `gtm-hub regenerate`.\n",
            encoding="utf-8",
        )
    state_path = Path.home() / ".claude" / "workstreams" / "state.json"
    if not state_path.exists():
        return (0, 0)
    import json
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return (0, 0)
    wrote = skipped = 0
    workstreams = state.get("workstreams") if isinstance(state, dict) else state
    if not isinstance(workstreams, dict):
        return wrote, skipped
    for slug, info in workstreams.items():
        if not isinstance(info, dict):
            continue
        slug_s = slugify(str(slug))
        bucket = info.get("bucket")
        if bucket not in {"hot", "warm", "stale", "parked"}:
            bucket = "warm"
        last_ts = info.get("last_touched")
        if isinstance(last_ts, (int, float)) and last_ts > 0:
            last_activity = dt.date.fromtimestamp(float(last_ts)).isoformat()
        else:
            last_activity = None
        counts = info.get("counts") or {}
        open_items = counts.get("total") if isinstance(counts, dict) else None
        meta = {
            "id": slug_s,
            "type": "workstream",
            "title": info.get("name") or str(slug),
            "status": bucket,
            "owner": "matt",
            "created": TODAY,
            "last_touch": last_activity or TODAY,
            "slug": slug_s,
            "last_activity": last_activity,
            "open_items": open_items,
        }
        body = f"\n# {info.get('name') or slug}\n\n_Mirror — source: `~/.claude/workstreams/state.json` (bucket: {bucket})._\n"
        # Mirrors always overwrite.
        result = write_entity(out_dir / f"{slug_s}.md", meta, body, force=True, dry_run=dry_run)
        if result == "skip":
            skipped += 1
        else:
            wrote += 1
    return wrote, skipped


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="Print plan; don't write.")
    p.add_argument("--force", action="store_true", help="Overwrite existing per-entity files.")
    args = p.parse_args()

    if args.dry_run:
        print("=== DRY RUN ===")

    summary: list[tuple[str, int, int]] = []

    pw, ps = migrate_prospects(args.dry_run, args.force)
    summary.append(("prospects", pw, ps))
    bw, bs = migrate_bd(args.dry_run, args.force)
    summary.append(("bd", bw, bs))
    nw = normalize_experiments(args.dry_run)
    summary.append(("experiments (normalize)", nw, 0))
    cw = normalize_content(args.dry_run)
    summary.append(("content (normalize)", cw, 0))
    mw, ms = seed_metrics(args.dry_run, args.force)
    summary.append(("metrics seed", mw, ms))
    lw, ls = seed_launches(args.dry_run, args.force)
    summary.append(("launches seed", lw, ls))
    tw, ts = seed_themes(args.dry_run, args.force)
    summary.append(("themes seed", tw, ts))
    ww, ws_ = seed_workstreams(args.dry_run, args.force)
    summary.append(("workstreams mirror", ww, ws_))

    print()
    label_w = max(len(s[0]) for s in summary)
    for label, wrote, skipped in summary:
        verb = "would-write" if args.dry_run else "wrote"
        print(f"{label:<{label_w}}  {verb}: {wrote:>3}   skipped: {skipped:>3}")
    if args.dry_run:
        print("\nRe-run without --dry-run to apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
