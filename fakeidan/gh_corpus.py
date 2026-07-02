#!/usr/bin/env python3
"""gh_corpus — backfill GitHub PR comments + reviews into a local searchable corpus.

Phase 6.B of ~/.claude/plans/how-can-we-make-ticklish-quilt.md. Sibling to
slack_corpus.py. Same goals — searchable per-author corpus of decisions,
voice, and concerns, but from GitHub.

Layout
------
~/.claude/state/gh_corpus/
    <owner>__<repo>/
        pr-NNNN.jsonl        — one line per comment/review on that PR
    _index.jsonl             — flat {ts, repo, pr, author, kind, snippet} per line
    _meta.json               — last_pull_at per repo + per-PR updated_at fingerprint

Each comment line: {pr, kind, author, ts, body, path?, line?}
  kind ∈ {review-comment, review-summary, issue-comment, review-state}

Run modes
---------
  gh_corpus.py backfill [--months 12] [--orgs Epoch-ML,mattzerg] [--max-prs 200]
  gh_corpus.py update                                 # incremental, only PRs updated since last pull
  gh_corpus.py search TERM [--author idanbeck] [--repo zerg] [--since YYYY-MM-DD]
  gh_corpus.py voice --author idanbeck [--since YYYY-MM-DD]    # extract author voice patterns
  gh_corpus.py stats

Rate limit: gh's authenticated rate is 5000 req/hr. Budget: ~3 calls per PR
(list + comments + reviews) × ~100 PRs × ~20 repos = ~6000 calls. Run as
manual one-shot, not cron, for the first pass.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Iterator

HOME = Path.home()
CORPUS = HOME / ".claude/state/gh_corpus"
INDEX = CORPUS / "_index.jsonl"
META = CORPUS / "_meta.json"

DEFAULT_ORGS = ["Epoch-ML", "mattzerg", "matteisn"]
SKIP_REPOS = {"matteisn/.github", "Epoch-ML/.github"}


def _gh(args: list[str], timeout: int = 60) -> str:
    try:
        r = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=timeout)
        return r.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def list_repos(org: str) -> list[dict]:
    out = _gh(["repo", "list", org, "--limit", "100", "--json", "name,nameWithOwner,createdAt,isArchived,pushedAt"])
    if not out:
        return []
    try:
        return [r for r in json.loads(out) if not r.get("isArchived")]
    except json.JSONDecodeError:
        return []


def list_prs(repo: str, since: dt.datetime, max_prs: int = 200) -> list[dict]:
    out = _gh([
        "pr", "list", "--repo", repo, "--state", "all", "--limit", str(max_prs),
        "--json", "number,createdAt,updatedAt,closedAt,author,title,state",
    ])
    if not out:
        return []
    try:
        prs = json.loads(out)
    except json.JSONDecodeError:
        return []
    cutoff = since.isoformat()
    return [p for p in prs if (p.get("updatedAt") or "") >= cutoff]


def pr_comments(repo: str, pr_number: int) -> list[dict]:
    """Pull review-comments + reviews + issue-comments for a PR."""
    comments: list[dict] = []
    # Inline review comments
    out = _gh(["api", f"repos/{repo}/pulls/{pr_number}/comments?per_page=100"], timeout=30)
    if out:
        try:
            for c in json.loads(out):
                comments.append({
                    "pr": pr_number,
                    "kind": "review-comment",
                    "author": (c.get("user") or {}).get("login"),
                    "ts": c.get("created_at"),
                    "body": c.get("body") or "",
                    "path": c.get("path"),
                    "line": c.get("line"),
                })
        except json.JSONDecodeError:
            pass
    # Top-level reviews (with state + body)
    out = _gh(["api", f"repos/{repo}/pulls/{pr_number}/reviews?per_page=100"], timeout=30)
    if out:
        try:
            for r in json.loads(out):
                comments.append({
                    "pr": pr_number,
                    "kind": "review-summary",
                    "author": (r.get("user") or {}).get("login"),
                    "ts": r.get("submitted_at"),
                    "body": r.get("body") or "",
                    "state": r.get("state"),  # APPROVED / REQUEST_CHANGES / COMMENTED
                })
        except json.JSONDecodeError:
            pass
    # Issue comments (general discussion under the PR)
    out = _gh(["api", f"repos/{repo}/issues/{pr_number}/comments?per_page=100"], timeout=30)
    if out:
        try:
            for c in json.loads(out):
                comments.append({
                    "pr": pr_number,
                    "kind": "issue-comment",
                    "author": (c.get("user") or {}).get("login"),
                    "ts": c.get("created_at"),
                    "body": c.get("body") or "",
                })
        except json.JSONDecodeError:
            pass
    return comments


def load_meta() -> dict:
    if META.exists():
        try:
            return json.loads(META.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_meta(meta: dict) -> None:
    META.parent.mkdir(parents=True, exist_ok=True)
    META.write_text(json.dumps(meta, indent=2))


def write_pr(repo: str, pr_number: int, comments: list[dict]) -> int:
    if not comments:
        return 0
    safe_repo = repo.replace("/", "__")
    pr_dir = CORPUS / safe_repo
    pr_dir.mkdir(parents=True, exist_ok=True)
    path = pr_dir / f"pr-{pr_number}.jsonl"
    # Idempotent: skip if file exists and we wrote it already this run
    if path.exists():
        existing = path.read_text(errors="ignore").splitlines()
        if len(existing) >= len(comments):
            return 0
    path.write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in comments) + "\n", encoding="utf-8")
    return len(comments)


def update_index(repo: str, pr_number: int, comments: list[dict]) -> None:
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for c in comments:
        snippet = (c.get("body") or "").replace("\n", " ").strip()[:120]
        lines.append(json.dumps({
            "ts": c.get("ts"),
            "repo": repo,
            "pr": pr_number,
            "author": c.get("author"),
            "kind": c.get("kind"),
            "state": c.get("state"),
            "snippet": snippet,
        }))
    if lines:
        with INDEX.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


def cmd_backfill(args) -> int:
    CORPUS.mkdir(parents=True, exist_ok=True)
    INDEX.write_text("") if INDEX.exists() and args.fresh else None  # only fresh on demand
    cutoff_dt = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=args.months * 30)

    orgs = [o.strip() for o in args.orgs.split(",") if o.strip()]
    meta = load_meta()

    total_prs = 0
    total_comments = 0
    for org in orgs:
        sys.stderr.write(f"[gh_corpus] {org}: listing repos...\n")
        repos = list_repos(org)
        sys.stderr.write(f"[gh_corpus] {org}: {len(repos)} non-archived repos\n")
        for r in repos:
            repo = r["nameWithOwner"]
            if repo in SKIP_REPOS:
                continue
            sys.stderr.write(f"[gh_corpus] {repo}: listing PRs...\n")
            prs = list_prs(repo, cutoff_dt, args.max_prs)
            sys.stderr.write(f"[gh_corpus] {repo}: {len(prs)} PRs in window\n")
            repo_meta = meta.setdefault(repo, {"prs": {}})
            for pr in prs:
                pr_num = pr["number"]
                updated = pr.get("updatedAt", "")
                # Idempotent: skip if we already pulled this PR at this updatedAt
                if repo_meta["prs"].get(str(pr_num)) == updated:
                    continue
                comments = pr_comments(repo, pr_num)
                # Skip PRs with 0 comments to keep corpus tight
                if comments:
                    write_pr(repo, pr_num, comments)
                    update_index(repo, pr_num, comments)
                    total_comments += len(comments)
                repo_meta["prs"][str(pr_num)] = updated
                total_prs += 1
                if total_prs % 10 == 0:
                    sys.stderr.write(f"[gh_corpus]   processed {total_prs} PRs ({total_comments} comments) so far\n")
                    save_meta(meta)
                time.sleep(0.1)  # gentle on the API
            repo_meta["last_pull_at"] = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
            save_meta(meta)
    print(f"[gh_corpus] backfill complete: {total_prs} PRs scanned, {total_comments} comments stored")
    return 0


def cmd_update(args) -> int:
    """Incremental: re-list PRs per repo, only pull PRs whose updatedAt is newer than stored."""
    meta = load_meta()
    if not meta:
        sys.stderr.write("[gh_corpus] no prior backfill — run `backfill` first\n")
        return 1
    cutoff_dt = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=60)
    total = 0
    for repo, repo_meta in meta.items():
        sys.stderr.write(f"[gh_corpus] {repo}: checking for updates...\n")
        prs = list_prs(repo, cutoff_dt, 100)
        for pr in prs:
            pr_num = pr["number"]
            updated = pr.get("updatedAt", "")
            if repo_meta["prs"].get(str(pr_num)) == updated:
                continue
            comments = pr_comments(repo, pr_num)
            if comments:
                write_pr(repo, pr_num, comments)
                update_index(repo, pr_num, comments)
                total += len(comments)
            repo_meta["prs"][str(pr_num)] = updated
        repo_meta["last_pull_at"] = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    save_meta(meta)
    print(f"[gh_corpus] update complete: +{total} comments")
    return 0


def cmd_search(args) -> int:
    if not INDEX.exists():
        sys.stderr.write("[gh_corpus] no index — run `backfill` first\n")
        return 1
    term = (args.term or "").lower()
    author = args.author
    repo_filter = args.repo
    since_dt = None
    if args.since:
        try:
            since_dt = dt.datetime.fromisoformat(args.since)
        except ValueError:
            sys.stderr.write(f"[gh_corpus] bad --since: {args.since}\n")
            return 1
    matches = 0
    for line in INDEX.read_text(errors="ignore").splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if term and term not in (r.get("snippet") or "").lower():
            continue
        if author and r.get("author") != author:
            continue
        if repo_filter and repo_filter not in (r.get("repo") or ""):
            continue
        if since_dt and r.get("ts"):
            try:
                tm = dt.datetime.fromisoformat(r["ts"].replace("Z", "+00:00"))
                if tm.replace(tzinfo=None) < since_dt:
                    continue
            except ValueError:
                continue
        state = f" [{r.get('state')}]" if r.get("state") else ""
        print(f"{(r.get('ts') or '?')[:10]}  {r.get('repo'):28}  #{r.get('pr'):<4}  {r.get('author'):14}{state}  {r.get('snippet')}")
        matches += 1
        if matches >= (args.limit or 50):
            break
    print(f"\n[gh_corpus] {matches} match(es)", file=sys.stderr)
    return 0


# Reuse concern catalog from ingest_recent for voice extraction
sys.path.insert(0, str(Path(__file__).parent))
try:
    from ingest_recent import CONCERN_PATTERNS, FAKE_IDAN_PREFIX  # type: ignore
except Exception:
    CONCERN_PATTERNS = {}
    FAKE_IDAN_PREFIX = re.compile(r"\[fake idan\]", re.I)


def cmd_voice(args) -> int:
    """Walk all per-PR jsonl files, extract author's classified concerns + samples."""
    if not CORPUS.exists():
        return 1
    since_dt = None
    if args.since:
        try:
            since_dt = dt.datetime.fromisoformat(args.since)
        except ValueError:
            return 1
    counter: Counter = Counter()
    examples: dict[str, list[tuple]] = {k: [] for k in CONCERN_PATTERNS}
    seen_total = 0
    seen_real = 0
    for pr_file in CORPUS.glob("*/pr-*.jsonl"):
        for line in pr_file.read_text(errors="ignore").splitlines():
            try:
                c = json.loads(line)
            except json.JSONDecodeError:
                continue
            if c.get("author") != args.author:
                continue
            seen_total += 1
            body = c.get("body") or ""
            if FAKE_IDAN_PREFIX.search(body):
                continue
            if since_dt and c.get("ts"):
                try:
                    tm = dt.datetime.fromisoformat(c["ts"].replace("Z", "+00:00"))
                    if tm.replace(tzinfo=None) < since_dt:
                        continue
                except ValueError:
                    continue
            seen_real += 1
            for cat, regex in CONCERN_PATTERNS.items():
                if regex.search(body):
                    counter[cat] += 1
                    if len(examples[cat]) < 3:
                        repo = pr_file.parent.name.replace("__", "/")
                        quote = body.replace("\n", " ").strip()[:160]
                        examples[cat].append((f"{repo}#{c.get('pr')}", quote))
    print(f"# Voice corpus for @{args.author}")
    print(f"")
    print(f"Seen: {seen_total} total comments · {seen_real} real (non-fake-idan)")
    print(f"")
    print(f"## Concern distribution")
    if not counter:
        print(f"- (none classified)")
    for cat, n in counter.most_common():
        print(f"- **{cat}**: {n}")
    print(f"")
    print(f"## Sample quotes")
    for cat, samples in examples.items():
        if not samples:
            continue
        print(f"### {cat}")
        for ref, quote in samples:
            print(f"- `{ref}` — {quote}")
        print()
    return 0


def cmd_merge_signal(args) -> int:
    """Per-author: which PRs got APPROVED vs REQUEST_CHANGES?
    Phase 8 vector B.6 — turn the merge-outcome state into approval-probability signal.

    Default: filters fake-idan paste-backs (recursive-drift risk). Pass
    --include-fake to count them too.

    --per-pattern: for each concern category, show APPROVED-rate. Patterns
    with low approval rates are ones Idan historically blocks on.
    """
    if not CORPUS.exists():
        sys.stderr.write("[gh_corpus] no corpus — run backfill first\n")
        return 1
    since_dt = None
    if args.since:
        try:
            since_dt = dt.datetime.fromisoformat(args.since)
        except ValueError:
            return 1

    by_state: dict[str, list[dict]] = {"APPROVED": [], "CHANGES_REQUESTED": [], "COMMENTED": []}
    skipped_fake = 0
    for pr_file in CORPUS.glob("*/pr-*.jsonl"):
        for line in pr_file.read_text(errors="ignore").splitlines():
            try:
                c = json.loads(line)
            except json.JSONDecodeError:
                continue
            if c.get("author") != args.author:
                continue
            if c.get("kind") != "review-summary":
                continue
            state = c.get("state") or ""
            if state not in by_state:
                continue
            body = c.get("body") or ""
            if not args.include_fake and FAKE_IDAN_PREFIX.search(body):
                skipped_fake += 1
                continue
            if since_dt and c.get("ts"):
                try:
                    tm = dt.datetime.fromisoformat(c["ts"].replace("Z", "+00:00")).replace(tzinfo=None)
                    if tm < since_dt:
                        continue
                except ValueError:
                    continue
            repo = pr_file.parent.name.replace("__", "/")
            by_state[state].append({
                "repo": repo,
                "pr": c.get("pr"),
                "ts": c.get("ts", "")[:10],
                "body": body.replace("\n", " ")[:160],
                "body_full": body,
            })

    total = sum(len(v) for v in by_state.values())
    approved = len(by_state["APPROVED"])
    changes_req = len(by_state["CHANGES_REQUESTED"])
    commented = len(by_state["COMMENTED"])

    print(f"# Merge signal for @{args.author}")
    print()
    print(f"Total reviews counted: **{total}**" + ("" if args.include_fake else f"  _(filtered {skipped_fake} fake-idan paste-backs)_"))
    print(f"  APPROVED:          {approved} ({100*approved/total:.0f}%)" if total else "  no reviews")
    print(f"  CHANGES_REQUESTED: {changes_req} ({100*changes_req/total:.0f}%)" if total else "")
    print(f"  COMMENTED:         {commented} ({100*commented/total:.0f}%)" if total else "")
    print()

    if args.per_pattern and CONCERN_PATTERNS:
        # Per-concern: how often is each concern category mentioned in each state?
        # An approval-blocking pattern = high CHANGES_REQ rate when present, low when absent.
        print(f"## Per-pattern approval rate")
        print()
        print(f"| Pattern | seen in APPR | seen in CHG | seen in CMT | approval-rate-when-present |")
        print(f"|---|---:|---:|---:|---:|")
        rows = []
        for cat, regex in CONCERN_PATTERNS.items():
            seen_appr = sum(1 for r in by_state["APPROVED"] if regex.search(r["body_full"]))
            seen_chg = sum(1 for r in by_state["CHANGES_REQUESTED"] if regex.search(r["body_full"]))
            seen_cmt = sum(1 for r in by_state["COMMENTED"] if regex.search(r["body_full"]))
            seen_total = seen_appr + seen_chg + seen_cmt
            if seen_total == 0:
                continue
            appr_rate = 100 * seen_appr / seen_total
            rows.append((cat, seen_appr, seen_chg, seen_cmt, appr_rate, seen_total))
        # Sort by approval rate ascending (lowest = hardest-to-pass concern)
        rows.sort(key=lambda r: (r[4], -r[5]))
        for cat, sa, sc, sm, rate, _ in rows:
            print(f"| `{cat}` | {sa} | {sc} | {sm} | {rate:.0f}% |")
        print()
        print(f"_Read: patterns near the TOP of the table are concerns Idan flagged but the PR did NOT get APPROVED — the harder-to-pass historic blockers. Patterns at the bottom are concerns he raised on PRs that still merged — softer / informational._")
        print()

    if changes_req:
        print(f"## PRs where {args.author} requested changes (the harder-to-pass patterns)")
        print()
        for r in by_state["CHANGES_REQUESTED"][:8]:
            print(f"- `{r['ts']}` {r['repo']}#{r['pr']} — {r['body']}")
        print()
    if approved:
        print(f"## Sample of APPROVED reviews (the bar that passed)")
        print()
        for r in by_state["APPROVED"][-8:]:  # most recent
            print(f"- `{r['ts']}` {r['repo']}#{r['pr']} — {r['body']}")
    return 0


def cmd_stats(args) -> int:
    meta = load_meta()
    if not meta:
        print("(empty — run backfill)")
        return 0
    total_prs = 0
    print(f"{'repo':35}  {'PRs':>5}  {'last_pull_at'}")
    print("-" * 80)
    for repo, info in sorted(meta.items(), key=lambda x: -len(x[1].get("prs", {}))):
        n = len(info.get("prs", {}))
        total_prs += n
        print(f"{repo:35}  {n:>5}  {info.get('last_pull_at', '?')}")
    print("-" * 80)
    print(f"{'TOTAL':35}  {total_prs:>5} PRs tracked")
    if INDEX.exists():
        comment_count = sum(1 for _ in INDEX.open())
        print(f"\nIndex rows: {comment_count}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd")

    bf = sub.add_parser("backfill")
    bf.add_argument("--months", type=int, default=12)
    bf.add_argument("--orgs", default=",".join(DEFAULT_ORGS))
    bf.add_argument("--max-prs", type=int, default=200)
    bf.add_argument("--fresh", action="store_true", help="wipe index before backfill")
    bf.set_defaults(func=cmd_backfill)

    up = sub.add_parser("update")
    up.set_defaults(func=cmd_update)

    s = sub.add_parser("search")
    s.add_argument("term")
    s.add_argument("--author")
    s.add_argument("--repo")
    s.add_argument("--since")
    s.add_argument("--limit", type=int, default=50)
    s.set_defaults(func=cmd_search)

    v = sub.add_parser("voice")
    v.add_argument("--author", required=True)
    v.add_argument("--since")
    v.set_defaults(func=cmd_voice)

    m = sub.add_parser("merge-signal", help="extract APPROVED vs REQUEST_CHANGES patterns per author")
    m.add_argument("--author", required=True)
    m.add_argument("--since")
    m.add_argument("--include-fake", action="store_true",
                   help="include [fake idan] paste-back reviews (default: filtered)")
    m.add_argument("--per-pattern", action="store_true",
                   help="show APPROVED-rate per concern category (B.6)")
    m.set_defaults(func=cmd_merge_signal)

    st = sub.add_parser("stats")
    st.set_defaults(func=cmd_stats)

    args = p.parse_args()
    if not getattr(args, "func", None):
        p.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
