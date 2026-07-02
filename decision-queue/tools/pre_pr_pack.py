#!/usr/bin/env python3
"""pre_pr_pack.py — build a pre-PR context pack and emit a decision-queue item.

Given a branch name + worktree path, builds a "ship this?" pack:
  - Diff summary (file count, +/-, touched product roots)
  - Applicable feedback rules (matched by file path against idan_feedback_corpus)
  - fakeidan pre-pass (delegates to pr-stage check)
  - "Why this is micro" check (single product? one pSEO file? coherent unit?)

Writes:
  - <worktree>/.pr-prep/context-pack-<branch>.md (human review)
  - ~/.claude/state/pre_pr_packs.jsonl (decision-queue source)

Usage:
  pre_pr_pack.py <worktree-path>
  pre_pr_pack.py /private/tmp/zerg-zb-pseo
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

STATE_DIR = Path.home() / ".claude/state"
PACKS_JSONL = STATE_DIR / "pre_pr_packs.jsonl"
LOG = STATE_DIR / "pre_pr_pack.log"
ZERG_ROOT = Path.home() / "zerg"
PSEO_RE = re.compile(r"public/content/(compare|integrations)/[A-Za-z0-9_-]+\.(md|mdx)$")
WRONG_SURFACE_RE = re.compile(r"web/src/public/content/(compare|integrations)/")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(msg: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as fh:
        fh.write(f"{_now_iso()} {msg}\n")


def _git(args: list[str], cwd: str) -> str:
    try:
        r = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True, timeout=15)
        return r.stdout.strip()
    except Exception:
        return ""


def gather_branch_info(worktree: str) -> dict:
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], worktree)
    head = _git(["rev-parse", "HEAD"], worktree)
    repo_root = _git(["rev-parse", "--show-toplevel"], worktree)
    # Choose base
    base_ref = None
    for ref in ("origin/development", "origin/main", "origin/master"):
        if _git(["rev-parse", "--verify", ref], worktree):
            base_ref = ref
            break
    base = _git(["merge-base", "HEAD", base_ref or "HEAD~1"], worktree)
    files = _git(["diff", "--name-only", f"{base}..HEAD"], worktree).splitlines()
    diffstat = _git(["diff", "--shortstat", f"{base}..HEAD"], worktree)
    commits = _git(["log", "--oneline", f"{base}..HEAD"], worktree).splitlines()
    return {
        "branch": branch,
        "head": head,
        "base_ref": base_ref,
        "base_sha": base,
        "repo_root": repo_root,
        "files": files,
        "files_count": len(files),
        "diffstat": diffstat,
        "commits": commits,
        "commits_count": len(commits),
    }


def micro_check(info: dict) -> dict:
    """Three-axis check: single-product / single-pseo / wrong-surface."""
    files = info["files"]
    repo_root = Path(info["repo_root"])
    # product
    try:
        rel = repo_root.relative_to(ZERG_ROOT.resolve())
        product = rel.parts[0] if rel.parts else None
    except Exception:
        product = None
    pseo_files = [f for f in files if PSEO_RE.search(f)]
    wrong_surface_files = [f for f in files if WRONG_SURFACE_RE.search(f)]
    return {
        "product": product,
        "pseo_files": pseo_files,
        "pseo_count": len(pseo_files),
        "wrong_surface_files": wrong_surface_files,
        "is_micro_pseo": len(pseo_files) <= 1 and not wrong_surface_files,
        "is_single_product": product is not None,  # if under ~/zerg/<X>, it's single by repo
    }


def applicable_rules(info: dict) -> list[str]:
    """Pick feedback rules likely to apply to this PR based on file patterns."""
    rules = []
    files_blob = " ".join(info["files"])
    paths = [
        ("public/content/compare/", "feedback-pseo-zergboard-only-and-incremental-product-pages.md"),
        ("public/content/integrations/", "feedback-pseo-zergboard-only-and-incremental-product-pages.md"),
        ("web/src/public/content/blog/", "feedback_zerg_content_routing.md (single-product → product site)"),
        (".github/workflows/", "composite_pr_workflow.md (CI registration discipline)"),
        ("fly.toml", "composite_pr_and_ship_gates.md (deployment surface)"),
        ("scripts/", "composite_pr_workflow.md (script discipline)"),
    ]
    for pat, rule in paths:
        if pat in files_blob and rule not in rules:
            rules.append(rule)
    # Always-applicable
    rules.append("composite_pr_workflow.md (micro-PR rule)")
    rules.append("composite_pr_and_ship_gates.md (pre-PR ritual)")
    rules.append("idan_feedback_corpus.md (Idan bar)")
    return rules


def try_fakeidan(worktree: str) -> str:
    """Run pr-stage check on this branch. Best-effort; returns brief text."""
    try:
        r = subprocess.run(
            ["/usr/bin/python3", os.path.expanduser("~/.claude/skills/pr-stage/run.py"),
             "check", "branch", "--worktree", worktree, "--briefly"],
            capture_output=True, text=True, timeout=120,
        )
        return (r.stdout + r.stderr)[:4000]
    except Exception as e:
        return f"(pr-stage check skipped: {e})"


def render_pack(info: dict, micro: dict, rules: list[str], fakeidan_brief: str) -> str:
    lines = []
    lines.append(f"# Pre-PR context pack — `{info['branch']}`\n")
    lines.append(f"*Generated: {_now_iso()}*  • Repo: `{info['repo_root']}`\n")
    lines.append(f"- **Base:** `{info['base_ref']}` @ `{info['base_sha'][:8]}`")
    lines.append(f"- **HEAD:** `{info['head'][:8]}`")
    lines.append(f"- **Diffstat:** {info['diffstat'] or '(unknown)'}")
    lines.append(f"- **Files:** {info['files_count']}  • **Commits:** {info['commits_count']}")
    lines.append("")
    lines.append("## Micro-PR check")
    if micro["is_single_product"]:
        lines.append(f"- ✅ Single product (`{micro['product']}`)")
    else:
        lines.append(f"- ⚠ Repo not under `~/zerg/<product>/` — check whether multi-product")
    if micro["is_micro_pseo"]:
        lines.append(f"- ✅ Micro-pSEO: {micro['pseo_count']} compare/integration file(s); no wrong-surface")
    else:
        lines.append(f"- ❌ pSEO violation: {micro['pseo_count']} files, wrong-surface: {len(micro['wrong_surface_files'])}")
        for f in micro["wrong_surface_files"]:
            lines.append(f"  - `{f}`")
    lines.append("")
    lines.append("## Applicable feedback rules")
    for r in rules:
        lines.append(f"- `{r}`")
    lines.append("")
    lines.append("## Files changed")
    for f in info["files"][:50]:
        lines.append(f"- `{f}`")
    if len(info["files"]) > 50:
        lines.append(f"- … +{len(info['files']) - 50} more")
    lines.append("")
    lines.append("## Fakeidan pre-pass")
    lines.append("```")
    lines.append(fakeidan_brief or "(no output)")
    lines.append("```")
    lines.append("")
    lines.append("## Why this is micro (Matt-written justification)")
    lines.append("_Fill in before opening PR. Required by `composite_pr_workflow.md`._")
    lines.append("")
    lines.append("## Decision")
    lines.append("- [ ] Ship — open PR")
    lines.append("- [ ] Refine — apply feedback, rebuild pack")
    lines.append("- [ ] Hold — wait for cap / sibling PR")
    return "\n".join(lines)


def emit_decision_row(info: dict, micro: dict, pack_path: Path) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    micro_status = "✅" if (micro["is_micro_pseo"] and micro["is_single_product"]) else "⚠"
    row = {
        "ts": _now_iso(),
        "kind": "pre_pr_pack",
        "id": f"prep:{info['branch']}",
        "branch": info["branch"],
        "repo_root": info["repo_root"],
        "files_count": info["files_count"],
        "diffstat": info["diffstat"],
        "micro_status": micro_status,
        "pack_path": str(pack_path),
        "context_one_line": f"PR pack ready — `{info['branch']}` ({info['files_count']} files, {micro_status})",
    }
    with PACKS_JSONL.open("a") as fh:
        fh.write(json.dumps(row, default=str) + "\n")
    _log(f"emitted decision row {row['id']} → {PACKS_JSONL.name}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("worktree")
    ap.add_argument("--skip-fakeidan", action="store_true")
    ap.add_argument("--no-emit", action="store_true",
                    help="Don't append to pre_pr_packs.jsonl (just write the pack)")
    args = ap.parse_args()

    worktree = os.path.abspath(args.worktree)
    if not Path(worktree, ".git").exists() and not Path(worktree, "../.git").exists():
        # worktree dirs may have a .git file pointing to worktrees/<name>
        if not Path(worktree, ".git").exists():
            print(json.dumps({"err": f"not a git worktree: {worktree}"}))
            return 1

    info = gather_branch_info(worktree)
    micro = micro_check(info)
    rules = applicable_rules(info)
    fk = "(skipped)" if args.skip_fakeidan else try_fakeidan(worktree)
    md = render_pack(info, micro, rules, fk)

    out_dir = Path(worktree) / ".pr-prep"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"context-pack-{info['branch'].replace('/','_')}.md"
    out_path.write_text(md)
    if not args.no_emit:
        emit_decision_row(info, micro, out_path)
    print(json.dumps({
        "ok": True,
        "branch": info["branch"],
        "files": info["files_count"],
        "pack": str(out_path),
        "micro_ok": micro["is_micro_pseo"] and micro["is_single_product"],
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
