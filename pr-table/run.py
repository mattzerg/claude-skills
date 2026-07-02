#!/usr/bin/env python3
"""pr-table — one-command snapshot of Matt's PR pipeline.

See SKILL.md for full description. Read-only: never mutates worktree, never
posts to GitHub. Outputs markdown to stdout.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_REPO = "Epoch-ML/zerg"
DEFAULT_DAYS = 7
DEFAULT_CAP = 2
ZERG_REPO_PATH = Path.home() / "zerg"

# Multi-repo scope: pr-table scans all of these by default so the "canonical PR list"
# matches Matt's "all Zerg-product repos I have PRs on" mental model. The article-lock
# logic still anchors against ZERG_REPO_PATH (locked-content rules apply to the zerg
# monorepo). New entries should map to a local clone path; if no local clone exists,
# held-branch scanning is silently skipped for that repo.
#
# Each entry maps `repo_full_name` → (local_path, default_branch). Different Zerg-product
# repos use different default branches (zerg = development, zerglytics = main, etc.) so
# the held-branch ahead/behind comparison needs to know which to compare against.
#
# When `--repo X` is passed explicitly, only that repo is scanned (single-repo legacy mode).
KNOWN_REPOS: dict[str, tuple[Path, str]] = {
    "Epoch-ML/zerg": (Path.home() / "zerg", "origin/development"),
    "Epoch-ML/zerglytics": (Path.home() / "Desktop" / "zerglytics", "origin/main"),
    "Epoch-ML/zerg-gg": (Path.home() / "zerg" / "zerg-gg", "origin/main"),
}

# Owner-level safety net: after the KNOWN_REPOS scan, query `gh search prs` for any
# Matt-authored open PR in this owner that ISN'T in KNOWN_REPOS. Surface as a "missed
# coverage" warning so the table never silently undercounts the cap again.
# Repair anchor: feedback_pr_table_repo_coverage.md.
DISCOVERY_OWNER = "Epoch-ML"
DISCOVERY_AUTHOR = "@me"

# Locked-article screen — feedback_locked_article_held_branches.md.
# Surface a "lock" blocker on held branches whose diff touches a locked
# article. They are never promotion candidates.
_ARTICLE_LOCK_LIB = Path.home() / ".config" / "zerg" / "lib"
try:
    if str(_ARTICLE_LOCK_LIB) not in sys.path:
        sys.path.insert(0, str(_ARTICLE_LOCK_LIB))
    import article_lock as _al  # type: ignore  # noqa: E402
except Exception:  # noqa: BLE001 — defensive: hook is hard enforcer
    _al = None


def _locked_paths_in_diff(worktree: Path, base: str) -> list[str]:
    """Return diff paths that touch LOCKED articles. Empty = clean.

    Paths resolved against the canonical zerg checkout, not the worktree —
    article_lock's BLOG_MD_DIR/BLOG_TS_DIR are anchored there and
    file_path_to_slug does prefix matching, not filesystem checks.
    """
    if _al is None:
        return []
    res = subprocess.run(
        ["git", "-C", str(worktree), "diff", "--name-only", f"{base}...HEAD"],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        return []
    hits: list[str] = []
    for p in res.stdout.splitlines():
        p = p.strip()
        if not p:
            continue
        canonical_p = str(ZERG_REPO_PATH / p)
        try:
            slug = _al.file_path_to_slug(canonical_p)
        except Exception:  # noqa: BLE001
            continue
        if slug and _al.is_locked(slug):
            hits.append(p)
    return hits


# ── helpers ─────────────────────────────────────────────────────────────────

def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> str:
    """Run a command, return stdout. Raise on nonzero unless check=False."""
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and res.returncode != 0:
        sys.stderr.write(f"[pr-table] cmd failed: {' '.join(cmd)}\n{res.stderr}")
        return ""
    return res.stdout


def gh_json(args: list[str]) -> list | dict:
    out = run(["gh"] + args)
    if not out.strip():
        return []
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return []


def parse_iso(s: str) -> dt.datetime | None:
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def relative_age(when: dt.datetime | None) -> str:
    if when is None:
        return "—"
    now = dt.datetime.now(dt.timezone.utc)
    delta = now - when.astimezone(dt.timezone.utc)
    secs = int(delta.total_seconds())
    if secs < 60:
        return f"{secs}s ago"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    days = secs // 86400
    if days <= 7:
        return f"{days}d ago"
    return when.astimezone().strftime("%Y-%m-%d")


def truncate(s: str, n: int) -> str:
    s = (s or "").replace("|", "\\|").replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


# ── open PRs ────────────────────────────────────────────────────────────────

@dataclass
class OpenPR:
    number: int
    title: str
    is_draft: bool
    mergeable: str
    merge_state: str
    review_decision: str
    reviews_summary: str
    ci_summary: str
    last_activity: str
    last_actor: str

    def state_cell(self) -> str:
        if self.is_draft:
            return "DRAFT"
        if self.mergeable == "CONFLICTING":
            return "CONFLICTS"
        # mergeable=MERGEABLE, merge_state can be CLEAN/BLOCKED/BEHIND/UNSTABLE/etc.
        if self.merge_state in ("CLEAN", "HAS_HOOKS"):
            return "READY"
        if self.merge_state == "BEHIND":
            return "BEHIND BASE"
        if self.merge_state == "BLOCKED":
            return "BLOCKED"
        if self.merge_state == "UNSTABLE":
            return "UNSTABLE"
        return self.merge_state or "—"


def fetch_open_prs(repo: str) -> list[OpenPR]:
    raw = gh_json([
        "pr", "list",
        "--author=@me", "--state=open",
        f"--repo={repo}",
        "--json", "number,title,url,isDraft,headRefName",
        "--limit", "30",
    ])
    if not isinstance(raw, list):
        return []
    out: list[OpenPR] = []
    for entry in raw:
        num = entry["number"]
        # Pull richer detail per-PR
        detail = gh_json([
            "pr", "view", str(num), f"--repo={repo}",
            "--json", "mergeable,mergeStateStatus,reviewDecision,"
                      "reviews,statusCheckRollup,commits,comments",
        ])
        if not isinstance(detail, dict):
            detail = {}
        # latest review per author
        latest_per_author: dict[str, str] = {}
        latest_review_at: dt.datetime | None = None
        latest_review_actor = ""
        for r in (detail.get("reviews") or []):
            author = (r.get("author") or {}).get("login", "?")
            state = r.get("state", "")
            ts = parse_iso(r.get("submittedAt"))
            if state in ("APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED"):
                latest_per_author[author] = state
            if ts and (latest_review_at is None or ts > latest_review_at):
                latest_review_at = ts
                latest_review_actor = author
        if latest_per_author:
            tokens = []
            for author, state in latest_per_author.items():
                short = {
                    "APPROVED": "✓",
                    "CHANGES_REQUESTED": "✗",
                    "COMMENTED": "💬",
                    "DISMISSED": "—",
                }.get(state, state[:3])
                tokens.append(f"{author}{short}")
            reviews_summary = " ".join(tokens)
        else:
            reviews_summary = "awaiting"
        # CI rollup
        rollup = detail.get("statusCheckRollup") or []
        states = [c.get("conclusion") or c.get("state") for c in rollup]
        if not states:
            ci = "—"
        elif "FAILURE" in states or "CANCELLED" in states or "TIMED_OUT" in states:
            ci = "✗"
        elif "PENDING" in states or "IN_PROGRESS" in states or "QUEUED" in states:
            ci = "⏳"
        elif all(s in ("SUCCESS", "SKIPPED", "NEUTRAL", None) for s in states):
            ci = "✓" if any(s == "SUCCESS" for s in states) else "—"
        else:
            ci = "?"
        # last activity = max of latest commit, latest comment, latest review
        last_at: dt.datetime | None = None
        last_actor = ""
        for c in (detail.get("commits") or []):
            ts = parse_iso(c.get("committedDate") or c.get("authoredDate"))
            if ts and (last_at is None or ts > last_at):
                last_at = ts
                authors = c.get("authors") or []
                last_actor = authors[0].get("login", "") if authors else ""
        for cmt in (detail.get("comments") or []):
            ts = parse_iso(cmt.get("createdAt"))
            if ts and (last_at is None or ts > last_at):
                last_at = ts
                last_actor = (cmt.get("author") or {}).get("login", "")
        if latest_review_at and (last_at is None or latest_review_at > last_at):
            last_at = latest_review_at
            last_actor = latest_review_actor
        last_str = relative_age(last_at)
        out.append(OpenPR(
            number=num,
            title=truncate(entry["title"], 50),
            is_draft=bool(entry.get("isDraft")),
            mergeable=detail.get("mergeable") or "",
            merge_state=detail.get("mergeStateStatus") or "",
            review_decision=detail.get("reviewDecision") or "",
            reviews_summary=reviews_summary,
            ci_summary=ci,
            last_activity=last_str,
            last_actor=last_actor or "—",
        ))
    return out


# ── recent merged / closed ──────────────────────────────────────────────────

def fetch_recent(repo: str, state: str, days: int) -> list[dict]:
    """state ∈ {merged, closed_unmerged}.

    'merged' = closed PRs that were merged.
    'closed_unmerged' = closed PRs that were NOT merged.
    Filters to past `days` days by closedAt.
    """
    # gh pr list state values are open|closed|merged|all
    gh_state = "merged" if state == "merged" else "closed"
    raw = gh_json([
        "pr", "list",
        "--author=@me", f"--state={gh_state}",
        f"--repo={repo}",
        "--json", "number,title,url,mergedAt,closedAt,mergedBy,headRefName,state",
        "--limit", "50",
    ])
    if not isinstance(raw, list):
        return []
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    out = []
    for r in raw:
        if state == "merged":
            ts = parse_iso(r.get("mergedAt"))
        else:
            # closed without merge: state=CLOSED and no mergedAt
            if r.get("mergedAt"):
                continue
            ts = parse_iso(r.get("closedAt"))
        if ts and ts >= cutoff:
            r["_when"] = ts
            out.append(r)
    out.sort(key=lambda r: r["_when"], reverse=True)
    return out


# ── held branches (worktrees with no associated open PR) ────────────────────

@dataclass
class HeldBranch:
    branch: str
    worktree: Path
    surface: str
    ahead: int
    behind: int
    last_commit_at: dt.datetime | None
    last_commit_sha: str
    pre_flight: str
    launch_confirm: str  # "✓ <slug>" if fresh token matches, "" otherwise
    blockers: list[str] = field(default_factory=list)


def parse_worktrees(repo_path: Path) -> list[tuple[Path, str]]:
    out = run(["git", "-C", str(repo_path), "worktree", "list", "--porcelain"], check=False)
    worktrees: list[tuple[Path, str]] = []
    cur_path: Path | None = None
    cur_branch: str = ""
    for line in out.splitlines():
        if line.startswith("worktree "):
            if cur_path:
                worktrees.append((cur_path, cur_branch))
            cur_path = Path(line[len("worktree "):])
            cur_branch = ""
        elif line.startswith("branch "):
            ref = line[len("branch "):]
            cur_branch = ref.replace("refs/heads/", "")
        elif line.startswith("detached"):
            cur_branch = "(detached)"
    if cur_path:
        worktrees.append((cur_path, cur_branch))
    return worktrees


def infer_surface(worktree: Path, base: str = "origin/development") -> str:
    """Guess product surface from the first changed-path prefix."""
    out = run(
        ["git", "-C", str(worktree), "diff", "--name-only", f"{base}...HEAD"],
        check=False,
    )
    paths = [p for p in out.splitlines() if p.strip()]
    if not paths:
        return "—"
    # Count top-level dirs, return the most common
    counts: dict[str, int] = {}
    for p in paths:
        top = p.split("/", 1)[0]
        counts[top] = counts.get(top, 0) + 1
    surface = max(counts, key=counts.get)
    return surface


def ahead_behind(worktree: Path, base: str) -> tuple[int, int]:
    out = run(
        ["git", "-C", str(worktree), "rev-list", "--left-right", "--count",
         f"{base}...HEAD"],
        check=False,
    )
    parts = out.strip().split()
    if len(parts) == 2:
        try:
            return int(parts[1]), int(parts[0])  # ahead, behind
        except ValueError:
            return 0, 0
    return 0, 0


def last_commit(worktree: Path) -> tuple[str, dt.datetime | None]:
    sha = run(["git", "-C", str(worktree), "rev-parse", "--short", "HEAD"],
              check=False).strip()
    when_str = run(
        ["git", "-C", str(worktree), "log", "-1", "--format=%cI", "HEAD"],
        check=False,
    ).strip()
    return sha, parse_iso(when_str)


def read_pre_flight(worktree: Path) -> str:
    """Read .pr-stage/state.json (written by pr-stage check). Returns:
    - 'never' if no state
    - 'stale' if older than 48h or diff_hash doesn't match current HEAD
    - 'fresh (Nh)' if recent and diff matches
    """
    state_path = worktree / ".pr-stage" / "state.json"
    if not state_path.exists():
        return "never"
    try:
        data = json.loads(state_path.read_text())
        ts = parse_iso(data.get("checked_at"))
        if ts is None:
            return "stale"
        age_h = (dt.datetime.now(dt.timezone.utc) - ts.astimezone(dt.timezone.utc)).total_seconds() / 3600
        if age_h > 48:
            return "stale"
        # Compare stored diff hash to current diff hash
        stored_hash = data.get("diff_hash", "")
        if stored_hash:
            import hashlib
            current = run_str(
                ["git", "-C", str(worktree), "diff", "origin/development...HEAD"],
            )
            current_hash = "sha256:" + hashlib.sha256(current.encode()).hexdigest()[:16]
            if stored_hash != current_hash:
                return "stale (diff changed)"
        return f"fresh ({int(age_h)}h)"
    except (json.JSONDecodeError, OSError):
        return "stale"


def run_str(cmd: list[str]) -> str:
    """Run a command, return stdout (or empty on failure)."""
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.stdout if res.returncode == 0 else ""


_LAUNCH_CONFIRM_DIR = Path.home() / ".config" / "zerg" / "launch-confirmed"


def fresh_launch_confirm_for(worktree: Path, surface: str) -> str:
    """Return "✓ <slug>" if a fresh launch-confirm token (within 24h) matches
    this worktree, else "".

    Match rule (per feedback_launch_confirm_slug_namespacing.md):
      - The "any" token always matches.
      - A namespaced token (e.g. "zergwallet-index") matches a worktree iff
        its slug starts with "<surface>-".
      - Bare single-segment slugs (e.g. "index") DO NOT match — they're the
        anti-pattern this rule is meant to prevent.
    """
    if not _LAUNCH_CONFIRM_DIR.exists():
        return ""
    cutoff = dt.datetime.now(dt.timezone.utc).timestamp() - 24 * 3600
    for token in _LAUNCH_CONFIRM_DIR.iterdir():
        if not token.is_file():
            continue
        if token.stat().st_mtime < cutoff:
            continue
        m = re.match(r"\d{4}-\d{2}-\d{2}-(.+)\.txt$", token.name)
        if not m:
            continue
        slug = m.group(1)
        if slug == "any":
            return "✓ any"
        if surface and "-" in slug and slug.startswith(f"{surface}-"):
            return f"✓ {slug}"
    return ""


def fetch_held_branches(
    repo_path: Path,
    open_branch_names: set[str],
    cap_full: bool,
    base: str = "origin/development",
) -> list[HeldBranch]:
    if not repo_path.exists():
        return []
    held: list[HeldBranch] = []
    seen = set()
    for worktree, branch in parse_worktrees(repo_path):
        if not branch or branch == "(detached)":
            continue
        if branch in open_branch_names:
            continue
        # skip the main worktree if it's on a non-PR branch
        if branch.startswith(("development", "main", "master")):
            continue
        if branch in seen:
            continue
        seen.add(branch)
        if not worktree.exists():
            continue
        ahead, behind = ahead_behind(worktree, base)
        if ahead == 0:
            continue  # nothing to PR
        sha, when = last_commit(worktree)
        surface = infer_surface(worktree, base)
        pre_flight = read_pre_flight(worktree)
        launch_confirm = fresh_launch_confirm_for(worktree, surface)
        blockers = []
        locked_hits = _locked_paths_in_diff(worktree, base)
        if locked_hits:
            blockers.append(f"🔒 lock-blocked ({len(locked_hits)})")
        if cap_full:
            blockers.append("cap")
        if behind > 0:
            blockers.append(f"behind {behind}")
        held.append(HeldBranch(
            branch=branch,
            worktree=worktree,
            surface=surface,
            ahead=ahead,
            behind=behind,
            last_commit_at=when,
            last_commit_sha=sha,
            pre_flight=pre_flight,
            launch_confirm=launch_confirm,
            blockers=blockers,
        ))
    # Sort: lock-blocked sink to the bottom (never promotable);
    # then actively-queued (behind == 0) first, then by recency.
    def _sort_key(h: HeldBranch) -> tuple:
        is_locked = 1 if any(b.startswith("🔒") for b in h.blockers) else 0
        is_stale = 1 if h.behind > 0 else 0
        ts = h.last_commit_at
        ts_secs = -ts.timestamp() if ts else 0
        return (is_locked, is_stale, ts_secs)
    held.sort(key=_sort_key)
    return held


# ── render ──────────────────────────────────────────────────────────────────

def render(
    repo: str,
    days: int,
    cap: int,
    open_prs: list[OpenPR],
    held: list[HeldBranch],
    merged: list[dict],
    closed: list[dict],
) -> str:
    lines: list[str] = []
    lines.append(f"# PR pipeline — {repo} — {dt.date.today().isoformat()}")
    lines.append("")
    lines.append(
        f"**Open: {len(open_prs)} / {cap} cap** · "
        f"**Held: {len(held)}** · "
        f"**Merged ({days}d): {len(merged)}** · "
        f"**Closed ({days}d): {len(closed)}**"
    )
    lines.append("")

    # Open PRs
    lines.append("## Open PRs")
    lines.append("")
    if not open_prs:
        lines.append("_(no open PRs)_")
    else:
        lines.append("| # | Title | State | Reviews | CI | Last activity |")
        lines.append("|---|---|---|---|---|---|")
        for p in open_prs:
            lines.append(
                f"| #{p.number} "
                f"| {p.title} "
                f"| {p.state_cell()} "
                f"| {p.reviews_summary} "
                f"| {p.ci_summary} "
                f"| {p.last_activity} ({p.last_actor}) |"
            )
    lines.append("")

    # Held local
    lines.append("## Held local")
    lines.append("")
    if not held:
        lines.append("_(no held branches)_")
    else:
        lines.append("| Branch | Surface | Ahead/Behind | Last commit | Pre-flight | Launch | Blockers |")
        lines.append("|---|---|---|---|---|---|---|")
        for h in held:
            ab = f"+{h.ahead}/-{h.behind}" if h.behind else f"+{h.ahead}"
            blockers = ", ".join(h.blockers) if h.blockers else "—"
            launch = h.launch_confirm or "—"
            age = relative_age(h.last_commit_at)
            lines.append(
                f"| `{truncate(h.branch, 40)}` "
                f"| {h.surface} "
                f"| {ab} "
                f"| {h.last_commit_sha} ({age}) "
                f"| {h.pre_flight} "
                f"| {launch} "
                f"| {blockers} |"
            )
    lines.append("")

    # Merged
    lines.append(f"## Merged in past {days} days")
    lines.append("")
    if not merged:
        lines.append("_(none)_")
    else:
        lines.append("| # | Title | Merged | By |")
        lines.append("|---|---|---|---|")
        for m in merged[:15]:
            who = (m.get("mergedBy") or {}).get("login") or "—"
            lines.append(
                f"| #{m['number']} "
                f"| {truncate(m['title'], 60)} "
                f"| {relative_age(m['_when'])} "
                f"| {who} |"
            )
    lines.append("")

    # Closed without merge
    lines.append(f"## Closed without merge in past {days} days")
    lines.append("")
    if not closed:
        lines.append("_(none)_")
    else:
        lines.append("| # | Title | Closed |")
        lines.append("|---|---|---|")
        for c in closed[:10]:
            lines.append(
                f"| #{c['number']} "
                f"| {truncate(c['title'], 60)} "
                f"| {relative_age(c['_when'])} |"
            )
    lines.append("")

    return "\n".join(lines)


# ── main ────────────────────────────────────────────────────────────────────

def _scan_repo(repo: str, path: Path, base: str, days: int, cap: int, no_held: bool) -> str:
    """Render a single repo's pr-table section."""
    open_pr_raw = gh_json([
        "pr", "list",
        "--author=@me", "--state=open",
        f"--repo={repo}",
        "--json", "number,headRefName",
        "--limit", "30",
    ])
    open_branch_names: set[str] = set()
    if isinstance(open_pr_raw, list):
        open_branch_names = {x["headRefName"] for x in open_pr_raw}

    open_prs = fetch_open_prs(repo)
    cap_full = len(open_prs) >= cap

    merged = fetch_recent(repo, "merged", days)
    closed = fetch_recent(repo, "closed_unmerged", days)

    associated_branches: set[str] = set(open_branch_names)
    history_raw = gh_json([
        "pr", "list",
        "--author=@me", "--state=all",
        f"--repo={repo}",
        "--json", "headRefName",
        "--limit", "100",
    ])
    if isinstance(history_raw, list):
        associated_branches |= {x["headRefName"] for x in history_raw}

    held = [] if no_held else fetch_held_branches(
        path, associated_branches, cap_full, base=base,
    )

    return render(repo, days, cap, open_prs, held, merged, closed)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default=None,
                    help="Scan a single repo (legacy mode). Default: scan all KNOWN_REPOS.")
    ap.add_argument("--days", type=int, default=DEFAULT_DAYS)
    ap.add_argument("--cap", type=int, default=DEFAULT_CAP)
    ap.add_argument("--no-held", action="store_true")
    args = ap.parse_args()

    # Single-repo legacy mode if --repo specified, else scan all known.
    if args.repo:
        target = KNOWN_REPOS.get(args.repo, (ZERG_REPO_PATH, "origin/development"))
        scan_targets = [(args.repo, target[0], target[1])]
    else:
        scan_targets = [(repo, path, base) for repo, (path, base) in KNOWN_REPOS.items()]

    # Coverage safety net (only on full-org scans, not --repo single-repo mode).
    # If `gh search prs --owner Epoch-ML --author=@me --state open` surfaces any
    # repo NOT in KNOWN_REPOS, print a warning at the top so the cap state is honest.
    # Repair anchor: feedback_pr_table_repo_coverage.md.
    coverage_warning = ""
    if not args.repo:
        try:
            res = subprocess.run(
                ["gh", "search", "prs", "--owner", DISCOVERY_OWNER,
                 "--author", DISCOVERY_AUTHOR, "--state", "open",
                 "--limit", "50", "--json", "repository,number,title,url"],
                capture_output=True, text=True, timeout=30,
            )
            if res.returncode == 0:
                discovered = json.loads(res.stdout or "[]")
                known_names = set(KNOWN_REPOS.keys())
                missing: dict[str, list[dict]] = {}
                for pr in discovered:
                    repo_name = pr.get("repository", {}).get("nameWithOwner", "")
                    if repo_name and repo_name not in known_names:
                        missing.setdefault(repo_name, []).append(pr)
                if missing:
                    lines = ["> ⚠️ **Coverage warning** — open PRs found in repos not in KNOWN_REPOS:"]
                    for repo_name, prs in missing.items():
                        for pr in prs:
                            lines.append(f">   - `{repo_name}` #{pr['number']} — {pr['title']}")
                    lines.append("> These are NOT counted in the cap state below. Add to `KNOWN_REPOS` in `~/.claude/skills/pr-table/run.py`.")
                    coverage_warning = "\n".join(lines) + "\n\n"
        except Exception:  # noqa: BLE001 — discovery is advisory, never blocks
            pass

    sections: list[str] = []
    for repo, path, base in scan_targets:
        sections.append(_scan_repo(repo, path, base, args.days, args.cap, args.no_held))

    print(coverage_warning + "\n\n---\n\n".join(sections))
    return 0


if __name__ == "__main__":
    sys.exit(main())
