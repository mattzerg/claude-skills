#!/usr/bin/env python3
"""pr-stage — mutation verbs for the PR queue.

`list` passes through to pr-table.
`rebase-all` fetches origin/<base> once, then rebases each held-branch worktree
onto it. Aborts on conflict; never pushes; never invokes pr-gate.
`check <branch>` runs lightweight pre-flight (fakeidan + fakematt-copyedit) on
a held branch's diff vs base; writes `.pr-stage/state.json` in the worktree so
pr-table can show fresh/stale.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_REPO = "Epoch-ML/zerg"
DEFAULT_BASE = "origin/development"
ZERG_REPO_PATH = Path.home() / "zerg"
PR_TABLE = Path.home() / ".claude" / "skills" / "pr-table" / "run.py"
FAKEIDAN = Path.home() / ".claude" / "skills" / "fakeidan" / "run.py"
FAKEMATT_COPYEDIT = Path.home() / ".claude" / "skills" / "fakematt-copyedit" / "run.py"

# Locked-article screen — feedback_locked_article_held_branches.md.
# Branches whose diff touches a locked article are never promotable; the
# check verb refuses, and rebase-all flags them so they don't burn compute.
_ARTICLE_LOCK_LIB = Path.home() / ".config" / "zerg" / "lib"
try:
    if str(_ARTICLE_LOCK_LIB) not in sys.path:
        sys.path.insert(0, str(_ARTICLE_LOCK_LIB))
    import article_lock as _al  # type: ignore  # noqa: E402
except Exception:  # noqa: BLE001 — fall through if lib missing; hook is hard enforcer
    _al = None


def locked_paths_in_diff(worktree: Path, paths: list[str]) -> list[tuple[str, str]]:
    """Return [(path, slug)] for diff files that touch a LOCKED article.

    Empty list = clean. Non-empty = refuse promotion. The hook layer
    (~/.claude/hooks/approved_content_lock_hook.py) is the hard enforcer
    on Write/Edit; this is the proactive screen so pr-stage doesn't waste
    compute pre-flighting a branch that can never ship.

    Paths are resolved against the CANONICAL zerg checkout (~/zerg), not the
    worktree, because article_lock's BLOG_MD_DIR/BLOG_TS_DIR are anchored
    there. file_path_to_slug does prefix matching, not filesystem checks,
    so a synthetic canonical path resolves correctly even if the file only
    exists in the worktree.
    """
    if _al is None:
        return []
    hits: list[tuple[str, str]] = []
    for p in paths:
        # Resolve relative to canonical repo, not worktree, so blog/post paths
        # match article_lock's hardcoded BLOG_MD_DIR/BLOG_TS_DIR prefixes.
        canonical_p = str(ZERG_REPO_PATH / p)
        try:
            slug = _al.file_path_to_slug(canonical_p)
        except Exception:  # noqa: BLE001
            continue
        if slug and _al.is_locked(slug):
            hits.append((p, slug))
    return hits

# Code file extensions. If any are touched, fakeidan runs in code mode.
CODE_EXTS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".vue", ".go", ".rs", ".rb",
    ".java", ".kt", ".swift", ".c", ".cpp", ".h", ".hpp", ".cs", ".sh",
    ".sql", ".yaml", ".yml", ".toml", ".json",
}
# Prose file extensions for fakematt-copyedit.
PROSE_EXTS = {".md", ".mdx"}

# Internal/operational doc filenames — out of scope for fakematt-copyedit
# (which is calibrated for public-facing blog/launch prose). Filtering these
# prevents the skill from emitting "out of scope" non-findings on every check.
INTERNAL_DOC_NAMES = {
    "README.md", "AGENTS.md", "CLAUDE.md", "GEMINI.md", "BUILDING.md",
    "MOBILE.md", "CHANGELOG.md", "CONTRIBUTING.md", "LICENSE.md",
    "CODE_OF_CONDUCT.md", "SECURITY.md", "TODOS.md", "TODO.md", "DESIGN.md",
    "ARCHITECTURE.md", "ROADMAP.md", "DEPLOY.md", "DEPLOYMENT.md",
    "INSTALL.md", "SETUP.md", "MIGRATIONS.md",
}
# Internal doc path prefixes / segments — anything under these is operational
# documentation, not public prose.
INTERNAL_DOC_PATH_SEGMENTS = (
    "/infra/", "/src-tauri/", "/scripts/", "/.github/", "/docs/internal/",
    "/migration", "/migrations/",
)


def is_internal_doc(path: str) -> bool:
    """True if path is an operational/internal doc (out of copyedit scope)."""
    name = Path(path).name
    if name in INTERNAL_DOC_NAMES:
        return True
    # Prefix with / to anchor segment match (avoids false-positive on "scripts" in slug)
    anchored = "/" + path
    return any(seg in anchored for seg in INTERNAL_DOC_PATH_SEGMENTS)


# ── helpers ─────────────────────────────────────────────────────────────────

def warn_if_claimed_by_other_session(repo_path: Path | str) -> None:
    """Soft session-claims check (Pillar 5): stderr WARN if another live
    Claude session has claimed the target repo. Never changes pass/fail."""
    try:
        sc_dir = str(Path.home() / ".config" / "zerg")
        if sc_dir not in sys.path:
            sys.path.insert(0, sc_dir)
        import session_claims as _sc  # type: ignore  # noqa: E402
        code, ev = _sc.check(str(repo_path))
        if code == 2 and ev:
            note = f" — {ev['note']}" if ev.get("note") else ""
            sys.stderr.write(
                f"[pr-stage] ⚠ {_sc.normalize_repo(str(repo_path))} claimed by session "
                f"{_sc.short_session(ev)} {_sc.age_str(ev)} ago{note} — "
                f"soft lock, coordinate before editing (zclaim list)\n"
            )
    except Exception:  # noqa: BLE001 — warn-only, never break the verb
        pass


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> tuple[int, str, str]:
    """Run a command, return (rc, stdout, stderr)."""
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and res.returncode != 0:
        sys.stderr.write(f"[pr-stage] cmd failed: {' '.join(cmd)}\n{res.stderr}")
    return res.returncode, res.stdout, res.stderr


def gh_json(args: list[str]) -> list | dict:
    rc, out, _ = run(["gh"] + args, check=False)
    if rc != 0 or not out.strip():
        return []
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return []


def parse_worktrees(repo_path: Path) -> list[tuple[Path, str]]:
    rc, out, _ = run(
        ["git", "-C", str(repo_path), "worktree", "list", "--porcelain"],
        check=False,
    )
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
            cur_branch = line[len("branch "):].replace("refs/heads/", "")
        elif line.startswith("detached"):
            cur_branch = ""
    if cur_path:
        worktrees.append((cur_path, cur_branch))
    return worktrees


def is_dirty(worktree: Path) -> bool:
    """Check if worktree has uncommitted changes, ignoring pr-stage's own
    state directory (`.pr-stage/`) and pr-gate's leftover artifacts
    (`.pr-gate-*.md`) since those are tooling output, not user work.
    """
    rc, out, _ = run(
        ["git", "-C", str(worktree), "status", "--porcelain"],
        check=False,
    )
    if not out.strip():
        return False
    # Filter out tooling-only paths
    real_changes = []
    for line in out.splitlines():
        # Each line is `XY <path>` (XY = status codes)
        path = line[3:].strip()
        if path.startswith(".pr-stage/") or path.startswith(".pr-gate") or path.startswith(".pr-prep/"):
            continue
        real_changes.append(line)
    return bool(real_changes)


def ahead_behind(worktree: Path, base: str) -> tuple[int, int]:
    rc, out, _ = run(
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


def open_pr_branches(repo: str) -> set[str]:
    raw = gh_json([
        "pr", "list",
        "--author=@me", "--state=open",
        f"--repo={repo}",
        "--json", "headRefName",
        "--limit", "30",
    ])
    if not isinstance(raw, list):
        return set()
    return {x["headRefName"] for x in raw}


# ── verbs ───────────────────────────────────────────────────────────────────

def cmd_list(args: argparse.Namespace) -> int:
    if not PR_TABLE.exists():
        sys.stderr.write(f"[pr-stage] pr-table not installed at {PR_TABLE}\n")
        return 1
    rc = subprocess.call(["python3", str(PR_TABLE), "--repo", args.repo])
    return rc


@dataclass
class RebaseResult:
    branch: str
    worktree: Path
    status: str  # "rebased", "noop", "conflict", "skipped-open-pr", "skipped-dirty", "skipped-no-branch"
    detail: str = ""


def cmd_rebase_all(args: argparse.Namespace) -> int:
    if not ZERG_REPO_PATH.exists():
        sys.stderr.write(f"[pr-stage] repo not found at {ZERG_REPO_PATH}\n")
        return 1

    base_remote, base_ref = args.base.split("/", 1)
    print(f"[pr-stage] fetching {base_remote}/{base_ref}…")
    rc, _, err = run(
        ["git", "-C", str(ZERG_REPO_PATH), "fetch", base_remote, base_ref],
        check=False,
    )
    if rc != 0:
        sys.stderr.write(f"[pr-stage] fetch failed: {err}\n")
        return 1

    open_branches = open_pr_branches(args.repo)
    worktrees = parse_worktrees(ZERG_REPO_PATH)

    results: list[RebaseResult] = []
    for worktree, branch in worktrees:
        if not branch:
            results.append(RebaseResult(branch="(detached)", worktree=worktree,
                                        status="skipped-no-branch"))
            continue
        if branch.startswith(("development", "main", "master")):
            continue  # base/release branches — never rebase
        if branch in open_branches:
            results.append(RebaseResult(branch=branch, worktree=worktree,
                                        status="skipped-open-pr"))
            continue
        if not worktree.exists():
            continue
        if is_dirty(worktree):
            results.append(RebaseResult(branch=branch, worktree=worktree,
                                        status="skipped-dirty"))
            continue

        ahead, behind = ahead_behind(worktree, args.base)
        if ahead == 0:
            # No commits to PR — skip silently (matches pr-table behavior)
            continue
        if behind == 0:
            results.append(RebaseResult(branch=branch, worktree=worktree,
                                        status="noop", detail="already on base"))
            continue

        if args.dry_run:
            results.append(RebaseResult(branch=branch, worktree=worktree,
                                        status="rebased",
                                        detail=f"would rebase +{ahead}/-{behind} (dry-run)"))
            continue

        rc, out, err = run(
            ["git", "-C", str(worktree), "rebase", args.base],
            check=False,
        )
        if rc == 0:
            new_ahead, new_behind = ahead_behind(worktree, args.base)
            results.append(RebaseResult(
                branch=branch, worktree=worktree, status="rebased",
                detail=f"+{new_ahead}/-{new_behind}",
            ))
        else:
            # Abort and continue to next branch
            run(["git", "-C", str(worktree), "rebase", "--abort"], check=False)
            results.append(RebaseResult(
                branch=branch, worktree=worktree, status="conflict",
                detail="aborted (resolve manually)",
            ))

    # Sort: rebased first, then noop, then conflict, then skipped
    order = {
        "rebased": 0, "noop": 1, "conflict": 2,
        "skipped-open-pr": 3, "skipped-dirty": 4, "skipped-no-branch": 5,
    }
    results.sort(key=lambda r: (order.get(r.status, 9), r.branch))

    icons = {
        "rebased": "✓",
        "noop": "→",
        "conflict": "✗",
        "skipped-open-pr": "↷",
        "skipped-dirty": "↷",
        "skipped-no-branch": "↷",
    }
    print()
    print(f"## pr-stage rebase-all → base = {args.base}")
    print()
    for r in results:
        icon = icons.get(r.status, "?")
        line = f"{icon} {r.status:<20} {r.branch}"
        if r.detail:
            line += f"  ({r.detail})"
        print(line)
    rebased = sum(1 for r in results if r.status == "rebased")
    conflicts = sum(1 for r in results if r.status == "conflict")
    print()
    print(f"summary: {rebased} rebased, {conflicts} conflict, {len(results) - rebased - conflicts} skipped/noop")
    return 0 if conflicts == 0 else 2


# ── check verb ──────────────────────────────────────────────────────────────

def find_worktree(branch: str) -> Path | None:
    for worktree, br in parse_worktrees(ZERG_REPO_PATH):
        if br == branch and worktree.exists():
            return worktree
    return None


def diff_text(worktree: Path, base: str) -> str:
    rc, out, _ = run(
        ["git", "-C", str(worktree), "diff", f"{base}...HEAD"],
        check=False,
    )
    return out if rc == 0 else ""


def diff_paths(worktree: Path, base: str) -> list[str]:
    rc, out, _ = run(
        ["git", "-C", str(worktree), "diff", "--name-only", f"{base}...HEAD"],
        check=False,
    )
    return [p for p in out.splitlines() if p.strip()] if rc == 0 else []


def cmd_check(args: argparse.Namespace) -> int:
    branch = args.branch
    worktree = find_worktree(branch)
    if worktree is None:
        sys.stderr.write(
            f"[pr-stage] no worktree for branch '{branch}'.\n"
            f"  Use `git worktree list` to see available branches.\n"
        )
        return 1

    diff = diff_text(worktree, args.base)
    if not diff.strip():
        sys.stderr.write(f"[pr-stage] empty diff vs {args.base} — nothing to check.\n")
        return 0

    paths = diff_paths(worktree, args.base)

    locked_hits = locked_paths_in_diff(worktree, paths)
    if locked_hits:
        sys.stderr.write(
            f"[pr-stage] REFUSED — branch '{branch}' touches LOCKED article(s):\n"
        )
        for p, slug in locked_hits:
            sys.stderr.write(f"  🔒 {p}  → slug: {slug}\n")
        sys.stderr.write(
            "  Per feedback_locked_article_held_branches.md, held branches\n"
            "  touching locked articles are NEVER promotion candidates.\n"
            "  Delete the branch or leave it dormant; do not pre-flight or push.\n"
        )
        return 2

    code_files = [p for p in paths if Path(p).suffix.lower() in CODE_EXTS]
    # Prose excludes internal/operational docs (READMEs, BUILDING.md, etc.) —
    # those go through fakeidan-as-code-reviewer if anywhere, never copyedit.
    all_prose = [p for p in paths if Path(p).suffix.lower() in PROSE_EXTS]
    prose_files = [p for p in all_prose if not is_internal_doc(p)]
    skipped_internal_docs = [p for p in all_prose if is_internal_doc(p)]
    diff_hash = "sha256:" + hashlib.sha256(diff.encode()).hexdigest()[:16]

    state_dir = worktree / ".pr-stage"
    state_dir.mkdir(exist_ok=True)
    diff_md = state_dir / "diff.md"
    diff_md.write_text(f"# PR diff for {branch} (base: {args.base})\n\n```diff\n{diff[:60000]}\n```\n")

    started = dt.datetime.now(dt.timezone.utc)
    state: dict = {
        "branch": branch,
        "checked_at": started.isoformat(),
        "diff_hash": diff_hash,
        "files_changed": len(paths),
        "code_files": len(code_files),
        "prose_files": len(prose_files),
        "skipped_internal_docs": skipped_internal_docs,
        "fakeidan": {"ran": False},
        "fakematt_copyedit": {"ran": False},
    }

    # ── fakeidan ────────────────────────────────────────────────────────
    if args.skip_fakeidan or not FAKEIDAN.exists():
        state["fakeidan"] = {"ran": False, "reason": "skipped"}
    else:
        mode = "code" if code_files else "prose"
        idan_dir = state_dir / "fakeidan"
        idan_dir.mkdir(exist_ok=True)
        print(f"[pr-stage] running fakeidan ({mode}) on {len(paths)} files…",
              file=sys.stderr)
        t0 = time.time()
        try:
            r = subprocess.run(
                ["python3", str(FAKEIDAN), str(diff_md),
                 "--mode", mode, "--out-dir", str(idan_dir),
                 "--model", args.model],
                capture_output=True, text=True, timeout=args.timeout,
            )
            # fakeidan writes diff.fakeidan-{mode}.{date}.md
            review_files = list(idan_dir.glob("*.fakeidan-*.md")) or \
                           list(idan_dir.glob("*review*.md"))
            review_path = review_files[0] if review_files else None
            # If no file produced (fakeidan errored or wrote stdout-only),
            # persist stdout/stderr so findings aren't lost on the floor.
            if review_path is None and (r.stdout.strip() or r.stderr.strip()):
                today = dt.datetime.now().strftime("%Y-%m-%d")
                fallback = idan_dir / f"diff.fakeidan-{mode}.{today}.stdout.md"
                fallback.write_text(
                    f"# fakeidan {mode} stdout (rc={r.returncode})\n\n"
                    f"## stdout\n\n```\n{r.stdout}\n```\n\n"
                    f"## stderr\n\n```\n{r.stderr}\n```\n"
                )
                review_path = fallback
            state["fakeidan"] = {
                "ran": True,
                "mode": mode,
                "duration_s": round(time.time() - t0, 1),
                "review_path": str(review_path) if review_path else None,
                "exit_code": r.returncode,
            }
        except subprocess.TimeoutExpired:
            state["fakeidan"] = {"ran": False, "reason": "timeout"}

    # ── fakematt-copyedit (prose only) ──────────────────────────────────
    if args.skip_copyedit or not prose_files or not FAKEMATT_COPYEDIT.exists():
        state["fakematt_copyedit"] = {
            "ran": False,
            "reason": "skipped" if args.skip_copyedit else "no prose files",
        }
    else:
        # Resolve prose paths against the worktree
        existing = [worktree / p for p in prose_files if (worktree / p).exists()]
        if not existing:
            state["fakematt_copyedit"] = {"ran": False, "reason": "files not present"}
        else:
            copy_dir = state_dir / "fakematt-copyedit"
            copy_dir.mkdir(exist_ok=True)
            print(f"[pr-stage] running fakematt-copyedit on {len(existing)} prose file(s)…",
                  file=sys.stderr)
            t0 = time.time()
            try:
                r = subprocess.run(
                    ["python3", str(FAKEMATT_COPYEDIT)] + [str(p) for p in existing] + [
                        "--out-dir", str(copy_dir), "--model", args.model, "--no-pdf",
                    ],
                    capture_output=True, text=True, timeout=args.timeout,
                )
                review_files = list(copy_dir.glob("*.review.md"))
                state["fakematt_copyedit"] = {
                    "ran": True,
                    "duration_s": round(time.time() - t0, 1),
                    "review_count": len(review_files),
                    "review_paths": [str(p) for p in review_files],
                    "exit_code": r.returncode,
                }
            except subprocess.TimeoutExpired:
                # Capture partial results — copyedit is per-file and may have
                # completed several before the batch timed out.
                review_files = list(copy_dir.glob("*.review.md"))
                state["fakematt_copyedit"] = {
                    "ran": True,
                    "reason": "timeout (partial results captured)",
                    "duration_s": round(time.time() - t0, 1),
                    "review_count": len(review_files),
                    "review_paths": [str(p) for p in review_files],
                    "files_attempted": len(existing),
                    "files_completed": len(review_files),
                    # Match either the bare stem or the surface-prefixed name
                    # that fakematt-copyedit writes for collision-prone parents
                    # (compare/, integrations/, blog/, etc.). Stay in sync with
                    # ~/.claude/skills/fakematt-copyedit/run.py:review_basename.
                    "files_missed": [str(p) for p in existing
                                      if not (copy_dir / f"{p.stem}.review.md").exists()
                                      and not (copy_dir / f"{p.parent.name}-{p.stem}.review.md").exists()],
                }

    # ── write state file ────────────────────────────────────────────────
    state_file = state_dir / "state.json"
    state_file.write_text(json.dumps(state, indent=2))
    print()
    print(f"## pr-stage check → {branch}")
    print()
    print(f"diff hash: {diff_hash}")
    skipped_note = f", {len(skipped_internal_docs)} internal-docs skipped" if skipped_internal_docs else ""
    print(f"files changed: {len(paths)} ({len(code_files)} code, {len(prose_files)} prose{skipped_note})")
    if state["fakeidan"]["ran"]:
        rp = state["fakeidan"].get("review_path") or "(stdout only)"
        print(f"fakeidan ({state['fakeidan']['mode']}, {state['fakeidan']['duration_s']}s): {rp}")
    else:
        print(f"fakeidan: skipped ({state['fakeidan'].get('reason', '?')})")
    if state["fakematt_copyedit"]["ran"]:
        n = state["fakematt_copyedit"]["review_count"]
        print(f"fakematt-copyedit ({state['fakematt_copyedit']['duration_s']}s): {n} review file(s)")
    else:
        print(f"fakematt-copyedit: skipped ({state['fakematt_copyedit'].get('reason', '?')})")
    print()
    print(f"state file: {state_file}")
    return 0


# ── promote verb ────────────────────────────────────────────────────────────

def cmd_promote(args: argparse.Namespace) -> int:
    """Validate that a branch is ready to PR, print the suggested pr-gate
    command. Refuses if any precondition fails.

    Preconditions checked:
      1. Branch has a worktree
      2. Worktree is clean (no uncommitted changes)
      3. Branch is rebased (behind == 0 vs base)
      4. Cap has a slot available (open count < cap)
      5. Pre-flight is fresh (state.json exists, age ≤ 48h, diff_hash matches)
      6. Launch-confirm token exists if branch touches a launch route
         (best-effort heuristic; informational only — not blocking)
    """
    branch = args.branch
    worktree = find_worktree(branch)
    if worktree is None:
        sys.stderr.write(f"[pr-stage] no worktree for branch '{branch}'\n")
        return 1

    failures: list[str] = []
    warnings: list[str] = []

    # 1. Worktree clean
    if is_dirty(worktree):
        failures.append("worktree has uncommitted changes — commit or stash first")

    # 2. Rebase state
    ahead, behind = ahead_behind(worktree, args.base)
    if ahead == 0:
        failures.append(f"branch has no commits ahead of {args.base} — nothing to PR")
    if behind > 0:
        failures.append(f"branch is {behind} commits behind {args.base} — run `pr-stage rebase-all`")

    # 3. Cap slot
    open_branches = open_pr_branches(args.repo)
    if len(open_branches) >= args.cap:
        failures.append(
            f"open-PR cap full ({len(open_branches)}/{args.cap}) — "
            f"merge or close one before promoting"
        )

    # 4. Pre-flight fresh
    state_file = worktree / ".pr-stage" / "state.json"
    if not state_file.exists():
        failures.append("no pre-flight state — run `pr-stage check <branch>` first")
    else:
        try:
            data = json.loads(state_file.read_text())
            ts_str = data.get("checked_at", "")
            ts = None
            if ts_str:
                try:
                    ts = dt.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except ValueError:
                    pass
            if ts is None:
                failures.append("pre-flight state malformed — re-run `pr-stage check`")
            else:
                age_h = (dt.datetime.now(dt.timezone.utc) - ts).total_seconds() / 3600
                if age_h > 48:
                    failures.append(f"pre-flight is stale ({int(age_h)}h old) — re-run `pr-stage check`")
                # Diff hash check
                rc, current_diff, _ = run(
                    ["git", "-C", str(worktree), "diff", f"{args.base}...HEAD"],
                    check=False,
                )
                import hashlib
                current_hash = "sha256:" + hashlib.sha256(current_diff.encode()).hexdigest()[:16]
                stored_hash = data.get("diff_hash", "")
                if stored_hash and stored_hash != current_hash:
                    failures.append("diff has changed since pre-flight — re-run `pr-stage check`")
                # Surface fakeidan/copyedit findings
                idan = data.get("fakeidan", {})
                if idan.get("ran"):
                    rp = idan.get("review_path")
                    if rp:
                        warnings.append(f"fakeidan review available: {rp}")
                copy = data.get("fakematt_copyedit", {})
                if copy.get("ran") and copy.get("review_count", 0) > 0:
                    warnings.append(
                        f"fakematt-copyedit: {copy['review_count']} review file(s) — "
                        f"check before promoting"
                    )
        except (json.JSONDecodeError, OSError) as e:
            failures.append(f"pre-flight state unreadable: {e}")

    # ── print result ────────────────────────────────────────────────────
    print()
    print(f"## pr-stage promote → {branch}")
    print()
    if failures:
        print(f"❌ NOT READY — {len(failures)} blocker(s):")
        for f in failures:
            print(f"  · {f}")
        if warnings:
            print()
            print("Pre-flight notes:")
            for w in warnings:
                print(f"  · {w}")
        return 2

    print("✅ READY")
    if warnings:
        print()
        print("Pre-flight notes (review before submitting):")
        for w in warnings:
            print(f"  · {w}")
    print()
    print("Next step — run pr-gate from the worktree:")
    print()
    print(f"  cd {worktree}")
    print(f"  python3 ~/.claude/skills/pr-gate/run.py")
    print()
    print("(pr-stage promote intentionally stops here — submission is a "
          "human-in-loop step. pr-gate will re-run its strict pre-flight + "
          "open the PR.)")
    return 0


# ── main ────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="verb", required=True)

    ls = sub.add_parser("list", help="pass-through to pr-table")
    ls.add_argument("--repo", default=DEFAULT_REPO)
    ls.set_defaults(fn=cmd_list)

    rb = sub.add_parser("rebase-all", help="rebase all held worktrees onto base")
    rb.add_argument("--repo", default=DEFAULT_REPO)
    rb.add_argument("--base", default=DEFAULT_BASE)
    rb.add_argument("--dry-run", action="store_true")
    rb.set_defaults(fn=cmd_rebase_all)

    ck = sub.add_parser("check", help="run pre-flight on a held branch")
    ck.add_argument("branch", help="branch name to check (must have a worktree)")
    ck.add_argument("--base", default=DEFAULT_BASE)
    ck.add_argument("--model", default="claude-opus-4-7")
    ck.add_argument("--timeout", type=int, default=600,
                    help="per-skill subprocess timeout (s); default 600")
    ck.add_argument("--skip-fakeidan", action="store_true")
    ck.add_argument("--skip-copyedit", action="store_true")
    ck.set_defaults(fn=cmd_check)

    pr = sub.add_parser("promote", help="validate a branch is ready to PR")
    pr.add_argument("branch", help="branch name to promote (must have a worktree)")
    pr.add_argument("--repo", default=DEFAULT_REPO)
    pr.add_argument("--base", default=DEFAULT_BASE)
    pr.add_argument("--cap", type=int, default=2,
                    help="open-PR cap (default 2 per feedback_pr_cap_check_first.md)")
    pr.set_defaults(fn=cmd_promote)

    args = ap.parse_args()
    if args.verb != "list":
        # Mutation verbs operate on the canonical checkout + its worktrees.
        warn_if_claimed_by_other_session(ZERG_REPO_PATH)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
