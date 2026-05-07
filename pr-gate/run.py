#!/usr/bin/env python3
"""PR gate — wraps `gh pr create` with mandatory fakematt + fakeidan pre-flight.

Usage:
    python3 ~/.claude/skills/pr-gate/run.py [gh-pr-create-args...] [gate-flags...]

Gate flags (all optional):
    --base BRANCH        base branch (default: development; falls back to main)
    --skip-copyedit      skip fakematt-copyedit
    --skip-fakeidan      skip fakeidan (DON'T DO THIS)
    --urgent             raise the open-PR cap from 2 to 3 for this open (logged)
    --force              override HIGH findings or backlog cap (logged)
    --dry-run            run gate + print verdict, don't actually open

All other args are forwarded to `gh pr create` verbatim.

Two enforced rules beyond fake-skill reviews:
  - Open-PR cap: max 2 open PRs by Matt at once across all repos (3 with --urgent).
    Bundle into an existing PR; don't multiply Idan's review queue.
  - No AI coauthors: `Co-Authored-By: Claude` lines and "Generated with Claude
    Code" footers are silently scrubbed from --body / --body-file before invoking gh.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_DIR = Path(__file__).parent
LOG_DIR = SKILL_DIR / "logs"
OVERRIDE_LOG = LOG_DIR / "overrides.log"

FAKEIDAN = Path.home() / ".claude" / "skills" / "fakeidan" / "run.py"
FAKEMATT_COPYEDIT = Path.home() / ".claude" / "skills" / "fakematt-copyedit" / "run.py"
LAUNCH_ANNOUNCEMENT = Path.home() / ".claude" / "skills" / "launch-announcement" / "run.py"
LAUNCH_PREMISE = SKILL_DIR / "launch_premise.py"

# Path patterns that indicate prose vs code
PROSE_PATTERNS = (
    re.compile(r"\.md$"),
    re.compile(r"\.mdx$"),
    re.compile(r"\.txt$"),
)
LAUNCH_POST_PATTERNS = (
    re.compile(r"Writing/[^/]*[Ll]aunch", re.I),
    re.compile(r"content/blog/.*launch", re.I),
    re.compile(r"_announcement", re.I),
)
CODE_EXTS = (".py", ".ts", ".tsx", ".js", ".jsx", ".vue", ".rs", ".go", ".java", ".rb", ".c", ".cpp", ".h", ".sql")


def parse_args():
    """Split argv into gate flags + gh-pr-create passthrough."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--base", default=None)
    parser.add_argument("--skip-copyedit", action="store_true")
    parser.add_argument("--skip-fakeidan", action="store_true")
    parser.add_argument("--urgent", action="store_true",
                        help="raise open-PR cap from 2 to 3 (logged)")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--gate-help", action="store_true",
                        help="show gate-specific help, then exit (--help passes to gh pr create)")
    args, passthrough = parser.parse_known_args()
    if args.gate_help:
        print(__doc__)
        sys.exit(0)
    return args, passthrough


def detect_base() -> str:
    """Find the most likely base branch — prefer development, then main."""
    for cand in ("development", "main", "master"):
        r = subprocess.run(["git", "show-ref", "--verify", f"refs/remotes/origin/{cand}"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            return cand
    return "main"


def changed_files(base: str) -> list[str]:
    r = subprocess.run(["git", "diff", "--name-only", f"origin/{base}...HEAD"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return []
    return [f.strip() for f in r.stdout.splitlines() if f.strip()]


def full_diff(base: str) -> str:
    r = subprocess.run(["git", "diff", f"origin/{base}...HEAD"],
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def classify(files: list[str]) -> dict:
    """Return {prose: [paths], launch: [paths], code: [paths], other: [paths]}."""
    out = {"prose": [], "launch": [], "code": [], "other": []}
    for f in files:
        if any(p.search(f) for p in LAUNCH_POST_PATTERNS):
            out["launch"].append(f)
            out["prose"].append(f)
        elif any(p.search(f) for p in PROSE_PATTERNS):
            out["prose"].append(f)
        elif any(f.endswith(ext) for ext in CODE_EXTS):
            out["code"].append(f)
        else:
            out["other"].append(f)
    return out


def has_high_findings(text: str) -> tuple[bool, list[str]]:
    """Heuristic: look for 'HIGH' confidence/severity markers in review output.

    Also fail-closed on tooling failures: if a fake-skill timed out or crashed
    we must NOT count that as "0 HIGH" — silence isn't success. Treat any
    timeout/crash sentinel as a synthetic HIGH so the gate blocks.
    """
    if re.search(r"timeout — gate FAIL-CLOSED|FAIL-CLOSED|timeout\)$", text, re.M):
        return (True, ["**HIGH** (gate fail-closed: review tool timed out — re-run with longer timeout or split the diff)"])
    lines = text.splitlines()
    high_lines = []
    for i, line in enumerate(lines):
        # Common patterns the fake-skills emit
        if re.search(r"\*\*Confidence:\*\*\s*HIGH\b", line):
            high_lines.append(line)
        elif re.search(r"\bC1\b|\bC2\b|\bC3\b|\bC4\b|\bC5\b", line) and re.search(r"^###\s", line):
            # fakeidan's pre-merge ask numbering — C-prefixed = required-before-merge
            high_lines.append(line)
        elif re.search(r"^- \*\*HIGH\*\*", line):
            high_lines.append(line)
    return (len(high_lines) > 0, high_lines)


def run_fakeidan(base: str, classification: dict, out_dir: Path, model: str = "claude-opus-4-7") -> tuple[Path, str]:
    """Run fakeidan on the full diff. Mode = code if any code files, else prose."""
    out_dir.mkdir(parents=True, exist_ok=True)
    mode = "code" if classification["code"] else "prose"
    diff_text = full_diff(base)
    if not diff_text.strip():
        return None, "(empty diff — skipped fakeidan)"
    diff_file = out_dir / "diff.md"
    diff_file.write_text(f"# PR diff (base: origin/{base})\n\n```diff\n{diff_text[:60000]}\n```\n")
    try:
        r = subprocess.run(
            ["python3", str(FAKEIDAN), str(diff_file),
             "--mode", mode, "--out-dir", str(out_dir), "--model", model],
            capture_output=True, text=True, timeout=300,
        )
        # fakeidan writes a review file; capture stdout as a fallback
        review_files = list(out_dir.glob("*review*.md"))
        review_text = review_files[0].read_text() if review_files else r.stdout
        return (review_files[0] if review_files else None), review_text
    except subprocess.TimeoutExpired:
        return None, "(fakeidan timeout — gate FAIL-CLOSED)"


def run_copyedit(prose_files: list[str], out_dir: Path, model: str = "claude-opus-4-7") -> tuple[list[Path], str]:
    """Run fakematt-copyedit on prose files."""
    if not prose_files:
        return [], "(no prose touched — skipped copyedit)"
    existing = [Path(f) for f in prose_files if Path(f).exists()]
    if not existing:
        return [], "(prose files not found locally — skipped copyedit)"
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        r = subprocess.run(
            ["python3", str(FAKEMATT_COPYEDIT)] + [str(p) for p in existing] + [
                "--out-dir", str(out_dir), "--model", model, "--no-pdf",
            ],
            capture_output=True, text=True, timeout=300,
        )
        review_files = list(out_dir.glob("*.review.md"))
        text = "\n\n---\n\n".join(p.read_text() for p in review_files) if review_files else r.stdout
        return review_files, text
    except subprocess.TimeoutExpired:
        return [], "(copyedit timeout — gate FAIL-CLOSED)"


def run_launch_review(launch_files: list[str], out_dir: Path, model: str = "claude-opus-4-7") -> tuple[list[Path], str]:
    """Run launch-announcement review on launch-post files."""
    if not launch_files:
        return [], "(no launch posts touched — skipped)"
    existing = [Path(f) for f in launch_files if Path(f).exists()]
    if not existing:
        return [], "(launch files not found locally — skipped)"
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        r = subprocess.run(
            ["python3", str(LAUNCH_ANNOUNCEMENT), "review"] + [str(p) for p in existing] + [
                "--out-dir", str(out_dir), "--model", model, "--no-pdf",
            ],
            capture_output=True, text=True, timeout=300,
        )
        review_files = list(out_dir.glob("*.review.md"))
        text = "\n\n---\n\n".join(p.read_text() for p in review_files) if review_files else r.stdout
        return review_files, text
    except subprocess.TimeoutExpired:
        return [], "(launch review timeout — gate FAIL-CLOSED)"


def write_gate_review(repo_root: Path, sections: list[tuple[str, str, list[str]]]) -> Path:
    """Write `.pr-gate-review.md` summarizing all findings."""
    out_path = repo_root / ".pr-gate-review.md"
    today = dt.datetime.now().isoformat(timespec="seconds")
    lines = [
        f"# PR Gate Review — {today}",
        "",
        "Pre-flight check before opening this PR. The gate refuses to open until HIGH findings are addressed (or `--force` overrides).",
        "",
    ]
    for section_name, full_text, high_lines in sections:
        lines.append(f"## {section_name}")
        lines.append("")
        if high_lines:
            lines.append(f"**HIGH findings ({len(high_lines)}):**")
            for hl in high_lines:
                lines.append(f"- {hl.strip()[:200]}")
            lines.append("")
        else:
            lines.append("_No HIGH findings._")
            lines.append("")
        lines.append("<details><summary>Full review</summary>")
        lines.append("")
        lines.append(full_text[:5000])
        lines.append("")
        lines.append("</details>")
        lines.append("")
    out_path.write_text("\n".join(lines))
    return out_path


OPEN_PR_CAP_DEFAULT = 2
OPEN_PR_CAP_URGENT = 3

# Patterns that mark AI coauthors in commit messages or PR bodies.
# Conservative: only matches lines that explicitly call out an LLM/agent. Human
# coauthors with names that happen to contain "claude" (the human name) won't
# match because they won't have the "Claude Code" / "<noreply@anthropic" markers.
AI_COAUTHOR_PATTERNS = (
    re.compile(r"^\s*Co-?[Aa]uthored-?[Bb]y:\s*Claude\b.*$", re.M),
    re.compile(r"^\s*Co-?[Aa]uthored-?[Bb]y:.*<noreply@anthropic\.com>\s*$", re.M),
    re.compile(r"^\s*Co-?[Aa]uthored-?[Bb]y:.*\bclaude-code\b.*$", re.M | re.I),
    re.compile(r"^\s*🤖\s*Generated with .*Claude.*$", re.M),
    re.compile(r"^\s*Generated with \[Claude Code\].*$", re.M),
)


def current_branch_pr_url() -> str | None:
    """If the cwd-branch already has an open PR, return its URL; else None.

    Used to exclude the in-flight PR from the backlog count — pushing more
    commits to an open PR doesn't grow Idan's review queue.
    """
    try:
        r = subprocess.run(
            ["gh", "pr", "view", "--json", "url,state"],
            capture_output=True, text=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    import json
    try:
        data = json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return None
    if (data.get("state") or "").upper() == "OPEN":
        return data.get("url")
    return None


def count_open_prs(exclude_url: str | None = None) -> tuple[int, list[dict]]:
    """Return (count, [{number,title,url,repo}, ...]) of Matt's open PRs across all repos.

    `exclude_url` skips the in-flight PR for this branch so re-pushing to an
    existing PR doesn't trip the cap.

    Uses `gh search prs` so it spans every repo Matt has open work in, not just
    the cwd. If gh is missing or the call fails, returns (0, []) and logs to
    stderr — fail-open here would defeat the cap, so callers should treat a
    failure as "unknown" and the caller decides how strict to be. We currently
    fail-open with a warning; the cap is a soft anti-clutter rule, not a
    correctness invariant.
    """
    try:
        r = subprocess.run(
            ["gh", "search", "prs", "--author=@me", "--state=open",
             "--json", "number,title,url,repository", "--limit", "50"],
            capture_output=True, text=True, timeout=20,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"[pr-gate] WARN: could not query open PRs ({e}); skipping cap", file=sys.stderr)
        return 0, []
    if r.returncode != 0:
        print(f"[pr-gate] WARN: gh search prs failed ({r.stderr.strip()[:200]}); skipping cap",
              file=sys.stderr)
        return 0, []
    import json
    try:
        data = json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        return 0, []
    out = []
    for pr in data:
        url = pr.get("url", "")
        if exclude_url and url == exclude_url:
            continue
        repo = pr.get("repository", {}) or {}
        out.append({
            "number": pr.get("number"),
            "title": pr.get("title", ""),
            "url": url,
            "repo": repo.get("nameWithOwner") or repo.get("name") or "?",
        })
    return len(out), out


def scrub_ai_coauthors(text: str) -> tuple[str, int]:
    """Strip AI-coauthor lines and Claude-generated footers. Return (clean, n_stripped)."""
    if not text:
        return text, 0
    n = 0
    for pat in AI_COAUTHOR_PATTERNS:
        text, k = pat.subn("", text)
        n += k
    # Collapse the runs of blank lines those substitutions leave behind.
    text = re.sub(r"\n{3,}", "\n\n", text).rstrip() + "\n"
    return text, n


def scrub_passthrough_body(passthrough: list[str], tmp_dir: Path) -> tuple[list[str], int]:
    """Scrub --body / --body-file values inline. Returns (new_passthrough, n_stripped).

    For --body, replaces the value in place. For --body-file, reads the file,
    scrubs, writes a sibling temp file, and rewrites the arg to point at it.
    Leaves the original file untouched (Matt may want it as a draft).
    """
    out = list(passthrough)
    total = 0
    i = 0
    while i < len(out):
        a = out[i]
        if a == "--body" and i + 1 < len(out):
            cleaned, k = scrub_ai_coauthors(out[i + 1])
            out[i + 1] = cleaned
            total += k
            i += 2
            continue
        if a.startswith("--body="):
            cleaned, k = scrub_ai_coauthors(a[len("--body="):])
            out[i] = "--body=" + cleaned
            total += k
            i += 1
            continue
        if a == "--body-file" and i + 1 < len(out):
            src = Path(out[i + 1])
            if src.exists():
                try:
                    cleaned, k = scrub_ai_coauthors(src.read_text())
                except OSError:
                    i += 2
                    continue
                if k > 0:
                    tmp_dir.mkdir(parents=True, exist_ok=True)
                    tmp = tmp_dir / f"body-scrubbed-{src.name}"
                    tmp.write_text(cleaned)
                    out[i + 1] = str(tmp)
                    total += k
            i += 2
            continue
        if a.startswith("--body-file="):
            src = Path(a[len("--body-file="):])
            if src.exists():
                try:
                    cleaned, k = scrub_ai_coauthors(src.read_text())
                except OSError:
                    i += 1
                    continue
                if k > 0:
                    tmp_dir.mkdir(parents=True, exist_ok=True)
                    tmp = tmp_dir / f"body-scrubbed-{src.name}"
                    tmp.write_text(cleaned)
                    out[i] = "--body-file=" + str(tmp)
                    total += k
            i += 1
            continue
        i += 1
    return out, total


def log_override(reason: str, gh_args: list[str]) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    today = dt.datetime.now().isoformat(timespec="seconds")
    with open(OVERRIDE_LOG, "a") as f:
        f.write(f"{today}\toverride={reason}\targs={shlex.join(gh_args)}\n")


def main() -> int:
    args, passthrough = parse_args()
    base = args.base or detect_base()

    # Find repo root
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if r.returncode != 0:
        print("error: not in a git repo", file=sys.stderr)
        return 2
    repo_root = Path(r.stdout.strip())

    print(f"[pr-gate] base=origin/{base}", file=sys.stderr)

    # Open-PR cap — block before doing any expensive review work.
    # Exclude the current branch's existing PR (if any) so re-pushing to an
    # in-flight PR doesn't trip the cap.
    cap = OPEN_PR_CAP_URGENT if args.urgent else OPEN_PR_CAP_DEFAULT
    in_flight = current_branch_pr_url()
    if in_flight:
        print(f"[pr-gate] this branch already has open PR: {in_flight} (excluded from cap)", file=sys.stderr)
    open_count, open_prs = count_open_prs(exclude_url=in_flight)
    if open_count >= cap and not args.force:
        print(f"\n[pr-gate] BLOCKED — you already have {open_count} open PR(s); cap is {cap}"
              f"{' (--urgent)' if args.urgent else ''}.", file=sys.stderr)
        print(f"[pr-gate] Bundle this work into one of these instead of opening a new PR:", file=sys.stderr)
        for pr in open_prs:
            print(f"  • {pr['repo']}#{pr['number']}  {pr['title']}", file=sys.stderr)
            print(f"    {pr['url']}", file=sys.stderr)
        print(f"\n[pr-gate] Options:", file=sys.stderr)
        print(f"  • Fold this branch into one of the PRs above (preferred).", file=sys.stderr)
        if not args.urgent:
            print(f"  • Pass --urgent to raise the cap to {OPEN_PR_CAP_URGENT} (logged).", file=sys.stderr)
        print(f"  • Pass --force to override entirely (logged).", file=sys.stderr)
        return 1
    if open_count >= cap and args.force:
        log_override(f"force-backlog-cap-{open_count}-of-{cap}", passthrough)
        print(f"[pr-gate] FORCED open at backlog={open_count} (cap {cap}) — logged.", file=sys.stderr)
    if args.urgent:
        log_override(f"urgent-backlog-{open_count}", passthrough)
        print(f"[pr-gate] --urgent: cap raised to {cap} (logged).", file=sys.stderr)

    files = changed_files(base)
    if not files:
        print(f"[pr-gate] no changes vs origin/{base} — nothing to gate", file=sys.stderr)
        if not args.dry_run:
            with tempfile.TemporaryDirectory() as scrub_tmp:
                scrubbed, n = scrub_passthrough_body(passthrough, Path(scrub_tmp))
                if n:
                    print(f"[pr-gate] stripped {n} AI-coauthor line(s) from PR body", file=sys.stderr)
                return subprocess.call(["gh", "pr", "create"] + scrubbed)
        return 0

    classification = classify(files)
    print(f"[pr-gate] {len(files)} changed files: code={len(classification['code'])} prose={len(classification['prose'])} launch={len(classification['launch'])}", file=sys.stderr)

    # Launch-premise gate: hard-block PRs that publish new launch content without a fresh confirm token.
    # Runs FIRST, fail-closed, before fake-skill reviews. Cheap (no API calls).
    # Override path: --force (still logs).
    if LAUNCH_PREMISE.exists():
        print("[pr-gate] running launch-premise gate…", file=sys.stderr)
        premise_rc = subprocess.call(
            ["python3", str(LAUNCH_PREMISE), "--base", base],
        )
        if premise_rc != 0 and not args.force:
            print("[pr-gate] BLOCKED by launch-premise gate.", file=sys.stderr)
            print("[pr-gate] Override with --force (logged).", file=sys.stderr)
            return 1
        if premise_rc != 0 and args.force:
            log_override("force-launch-premise", passthrough)
            print("[pr-gate] FORCED past launch-premise gate (logged)", file=sys.stderr)

    sections = []
    with tempfile.TemporaryDirectory() as tmpd:
        out_dir = Path(tmpd)

        # Run fakeidan
        if not args.skip_fakeidan and FAKEIDAN.exists():
            print("[pr-gate] running fakeidan…", file=sys.stderr)
            _, idan_text = run_fakeidan(base, classification, out_dir / "fakeidan")
            high, lines = has_high_findings(idan_text)
            sections.append(("fakeidan", idan_text, lines))

        # Run fakematt-copyedit on prose
        if not args.skip_copyedit and classification["prose"] and FAKEMATT_COPYEDIT.exists():
            print(f"[pr-gate] running fakematt-copyedit on {len(classification['prose'])} prose file(s)…", file=sys.stderr)
            _, copy_text = run_copyedit(classification["prose"], out_dir / "copyedit")
            high, lines = has_high_findings(copy_text)
            sections.append(("fakematt-copyedit", copy_text, lines))

        # Run launch-announcement review on launch posts
        if classification["launch"] and LAUNCH_ANNOUNCEMENT.exists():
            print(f"[pr-gate] running launch-announcement review on {len(classification['launch'])} launch file(s)…", file=sys.stderr)
            _, launch_text = run_launch_review(classification["launch"], out_dir / "launch")
            high, lines = has_high_findings(launch_text)
            sections.append(("launch-announcement", launch_text, lines))

        gate_review = write_gate_review(repo_root, sections)

    total_high = sum(len(lines) for _, _, lines in sections)
    print(f"[pr-gate] review written to {gate_review}", file=sys.stderr)
    print(f"[pr-gate] total HIGH findings: {total_high}", file=sys.stderr)

    if total_high > 0 and not args.force:
        print(f"\n[pr-gate] BLOCKED — {total_high} HIGH finding(s) must be addressed before opening this PR.", file=sys.stderr)
        print(f"[pr-gate] See {gate_review} for details.", file=sys.stderr)
        print(f"[pr-gate] Override with --force (logged to {OVERRIDE_LOG})", file=sys.stderr)
        return 1

    if total_high > 0 and args.force:
        log_override(f"force-with-{total_high}-HIGH", passthrough)
        print(f"[pr-gate] FORCED open despite {total_high} HIGH findings (logged)", file=sys.stderr)

    if args.dry_run:
        print("[pr-gate] --dry-run: not opening PR", file=sys.stderr)
        return 0

    print("[pr-gate] gate passed — calling gh pr create", file=sys.stderr)
    with tempfile.TemporaryDirectory() as scrub_tmp:
        scrubbed, n = scrub_passthrough_body(passthrough, Path(scrub_tmp))
        if n:
            print(f"[pr-gate] stripped {n} AI-coauthor line(s) from PR body", file=sys.stderr)
        return subprocess.call(["gh", "pr", "create"] + scrubbed)


if __name__ == "__main__":
    sys.exit(main())
