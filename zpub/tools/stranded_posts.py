#!/usr/bin/env python3
"""
stranded_posts.py — catch blog posts that are scheduled/published on `development`
but not yet on `main` (prod), so a passed publish date never silently slips again.

WHY THIS EXISTS
---------------
zergai.com builds from `main`; `development` is the integration branch. A post is
"published" by setting status="published" + a scheduledPublishAt date in its
`web/src/constants/blog/posts/<slug>.ts` and merging to development — but it only
goes LIVE after a manual `development -> main` prod sync. When that sync lags
(it ran 2026-05-19 then sat ~6 weeks), every post whose scheduled date passed is
silently stranded: the date lapses, someone re-pencils it forward, repeat.
"Nobody Reads Code Anymore" slipped 6/10 -> 6/16 -> 6/30 this exact way.

This check reads the repo as source-of-truth (no dependence on the zpub id<->slug
mapping): for each post on `development` that is absent from `main`, it parses the
scheduled date and flags anything whose date has passed (overdue) or is imminent.
It also reports how stale `main` is.

LIMITATION: this inspects the build-time/static tier (the `.ts` + `.md` in git).
The blog also has a runtime DB tier (api/blog BlogPost + admin API); if/when posts
are published via the DB (see _proposal-decouple-blog-deploys.md), this should also
query `/api/blog/posts/state/` to avoid false "stranded" reports for DB-published posts.

Exit code: 0 = nothing overdue; 1 = at least one OVERDUE stranded post (so it can
gate a cron / session-briefing line).

USAGE
-----
  python3 stranded_posts.py                # uses local origin refs (fast)
  python3 stranded_posts.py --fetch        # refresh origin/development + origin/main first (accurate)
  python3 stranded_posts.py --repo ~/zerg  # override repo location
  python3 stranded_posts.py --json         # machine-readable

WIRING (recommended, not auto-installed — wiring a cron/hook is a system change):
  - session briefing: add a line that runs this with --fetch and prints the summary
  - or a LaunchAgent mirroring com.zerg.zpub-sync cadence
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys

POSTS_DIR = "web/src/constants/blog/posts"
DEV = "origin/development"
MAIN = "origin/main"

DATE_RE = re.compile(r'(scheduledPublishAt|publishedAt)\s*:\s*new Date\(\s*["\']([^"\']+)["\']')
STATUS_RE = re.compile(r'status\s*:\s*["\']([^"\']+)["\']')
DRAFT_RE = re.compile(r'draft\s*:\s*(true|false)')


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", repo, *args],
        capture_output=True, text=True,
    )


def find_repo(start):
    r = git(start, "rev-parse", "--show-toplevel")
    if r.returncode != 0:
        return None
    return r.stdout.strip()


def ls_posts(repo, ref):
    r = git(repo, "ls-tree", "-r", "--name-only", ref, "--", POSTS_DIR + "/")
    if r.returncode != 0:
        return set()
    return {p for p in r.stdout.splitlines() if p.endswith(".ts") and "/index" not in p}


def show(repo, ref, path):
    r = git(repo, "show", f"{ref}:{path}")
    return r.stdout if r.returncode == 0 else ""


def parse_post(src):
    """Pull the effective publish date + status out of a post .ts blob."""
    status = None
    m = STATUS_RE.search(src)
    if m:
        status = m.group(1)
    draft = None
    m = DRAFT_RE.search(src)
    if m:
        draft = (m.group(1) == "true")
    # Prefer scheduledPublishAt; fall back to publishedAt.
    dates = {k: v for k, v in DATE_RE.findall(src)}
    raw = dates.get("scheduledPublishAt") or dates.get("publishedAt")
    when = None
    if raw:
        try:
            when = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=dt.timezone.utc)
        except ValueError:
            when = None
    return status, draft, when, raw


def main_age_days(repo):
    r = git(repo, "log", "-1", "--format=%cI", MAIN)
    if r.returncode != 0 or not r.stdout.strip():
        return None, None
    when = dt.datetime.fromisoformat(r.stdout.strip())
    age = (dt.datetime.now(dt.timezone.utc) - when.astimezone(dt.timezone.utc)).days
    return when, age


def run(argv=None):
    ap = argparse.ArgumentParser(description="Flag blog posts stranded on development (not yet on prod/main).")
    ap.add_argument("--repo", default=os.path.expanduser("~/zerg"))
    ap.add_argument("--fetch", action="store_true", help="refresh origin/development + origin/main first")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--stale-days", type=int, default=14, help="flag main as stale beyond N days (default 14)")
    args = ap.parse_args(argv)

    repo = find_repo(args.repo)
    if not repo:
        print(f"stranded_posts: not a git repo at {args.repo}", file=sys.stderr)
        return 2

    if args.fetch:
        git(repo, "fetch", "--quiet", "origin", "development", "main")

    dev_posts = ls_posts(repo, DEV)
    main_posts = ls_posts(repo, MAIN)
    stranded_paths = sorted(dev_posts - main_posts)

    now = dt.datetime.now(dt.timezone.utc)
    main_when, main_age = main_age_days(repo)

    rows = []
    for path in stranded_paths:
        slug = os.path.basename(path)[:-3]
        status, draft, when, raw = parse_post(show(repo, DEV, path))
        # Both "published" and "queued" mean "live or will auto-go-live": the
        # Celery promote task targets `WHERE status='queued' AND scheduled_publish_at<=now`.
        # Missing "queued" would silently skip a stranded scheduled post.
        scheduled = (status in ("published", "queued")) and not draft
        if scheduled and when is not None:
            classup = "OVERDUE" if when <= now else "QUEUED"
        elif scheduled:
            classup = "SCHEDULED-NO-DATE"
        else:
            classup = "DEV-ONLY"  # draft / not marked published — fine to sit on dev
        rows.append({
            "slug": slug, "path": path, "status": status, "draft": draft,
            "scheduled_at": raw, "class": classup,
            "days_overdue": (now - when).days if (when and when <= now) else None,
        })

    overdue = [r for r in rows if r["class"] == "OVERDUE"]

    if args.json:
        print(json.dumps({
            "main_last_sync": main_when.isoformat() if main_when else None,
            "main_age_days": main_age,
            "main_stale": (main_age is not None and main_age > args.stale_days),
            "dev_post_count": len(dev_posts),
            "main_post_count": len(main_posts),
            "stranded": rows,
        }, indent=2))
        return 1 if overdue else 0

    icon = {"OVERDUE": "🔴", "QUEUED": "🟠", "SCHEDULED-NO-DATE": "🟠", "DEV-ONLY": "·"}
    print("== blog prod-sync monitor ==")
    stale_tag = "  ⚠ STALE" if (main_age is not None and main_age > args.stale_days) else ""
    print(f"main last synced: {main_when.date() if main_when else '?'} ({main_age}d ago){stale_tag}")
    print(f"posts: development={len(dev_posts)}  main={len(main_posts)}  stranded={len(stranded_paths)}")
    if not stranded_paths:
        print("  (nothing stranded — development and main agree on posts)")
    for r in sorted(rows, key=lambda x: (x["class"] != "OVERDUE", x["slug"])):
        od = f"  +{r['days_overdue']}d overdue" if r["days_overdue"] is not None else ""
        date = r["scheduled_at"] or "—"
        print(f"  {icon.get(r['class'],'?')} {r['class']:<10} {r['slug']:<36} sched={date}{od}  status={r['status']}")
    if overdue:
        print(f"\n  ↳ next: {len(overdue)} post(s) past their publish date but absent from main →")
        print(f"          trigger the development→main prod sync (Idan), then verify the canonical URL live.")
    return 1 if overdue else 0


if __name__ == "__main__":
    sys.exit(run())
