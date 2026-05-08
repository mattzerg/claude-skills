#!/usr/bin/env python3
"""PR gate CI runner — slimmed-down version of ~/.claude/skills/pr-gate/.

Runs in GitHub Actions. Reads the PR diff + body, runs the cap/scrub/review
checks the local skill runs, calls Anthropic API for the LLM review, writes
.pr-gate-review.md (which the workflow posts as a PR comment), and sets
$GITHUB_OUTPUT::high_count.

Required env: ANTHROPIC_API_KEY
Optional env (passed by workflow):
    PR_AUTHOR  — login of the PR author (used for backlog cap query)
    PR_BODY    — current PR body (scanned for AI-coauthor lines)
    PR_NUMBER  — current PR number (excluded from backlog count)
    PR_REPO    — current repo nameWithOwner
    PR_GATE_IDENTITY — optional: matt-personal | matt-led | ai-led
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    from anthropic import Anthropic
except ImportError:
    print("error: anthropic SDK not installed (pip install anthropic)", file=sys.stderr)
    sys.exit(2)

DIFF_FILE = Path(".pr-gate-diff.patch")
FILES_FILE = Path(".pr-gate-files.txt")
REVIEW_OUT = Path(".pr-gate-review.md")
MODEL = os.environ.get("PR_GATE_MODEL", "claude-opus-4-7")
MAX_DIFF_CHARS = 80_000

OPEN_PR_CAP_DEFAULT = 2
OPEN_PR_CAP_URGENT = 3
GITHUB_PERSONAL_ACCOUNT = "matteisn"
GITHUB_AI_ACCOUNT = "mattzerg"
PERSONAL_GITHUB_OWNERS = {"matteisn", "mattheweisner"}

PROSE_PATTERNS = (re.compile(r"\.md$"), re.compile(r"\.mdx$"), re.compile(r"\.txt$"))
CODE_EXTS = (".py", ".ts", ".tsx", ".js", ".jsx", ".vue", ".rs", ".go", ".java", ".rb", ".sql")

LAUNCH_FILE_PATTERNS = (
    re.compile(r"web/src/public/content/blog/.+\.md$"),
    re.compile(r"web/src/constants/blog/posts/(?!index\.).+\.ts$"),
    re.compile(r"Writing/[^/]*[Ll]aunch", re.I),
    re.compile(r"_announcement", re.I),
)

# Asset-preview detection — for PRs that touch content/blog/copy/video/landing,
# the local pr-gate prepends a `<details>` preview block to the PR body. If a
# PR opened without going through pr-gate (or with --no-asset-previews), flag
# as MEDIUM so the reviewer at least sees what's changing visually.
ASSET_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".avif")
ASSET_VIDEO_EXTS = (".mp4", ".mov", ".webm", ".m4v")
ASSET_BLOG_PATTERNS = (
    re.compile(r"(^|/)content/blog/.+\.mdx?$", re.I),
    re.compile(r"(^|/)blog/[^/]+\.mdx?$", re.I),
)
ASSET_LANDING_PATTERNS = (
    re.compile(r"web/src/pages/.+\.vue$"),
    re.compile(r"(^|/)pages/.*landing.*\.(vue|tsx|jsx|html)$", re.I),
    re.compile(r"(^|/)landing-?page", re.I),
)
ASSET_PREVIEW_BODY_MARKERS = ("📎 Asset previews", ".pr-gate-asset-previews.md")

AI_COAUTHOR_PATTERNS = (
    re.compile(r"^\s*Co-?[Aa]uthored-?[Bb]y:\s*Claude\b.*$", re.M),
    re.compile(r"^\s*Co-?[Aa]uthored-?[Bb]y:.*<noreply@anthropic\.com>\s*$", re.M),
    re.compile(r"^\s*Co-?[Aa]uthored-?[Bb]y:.*\bclaude-code\b.*$", re.M | re.I),
    re.compile(r"^\s*🤖\s*Generated with .*Claude.*$", re.M),
    re.compile(r"^\s*Generated with \[Claude Code\].*$", re.M),
)


SYSTEM_PROMPT = """You are simulating two reviewers on this PR diff:

1. **fakeidan** — Idan Beck's PR review patterns. Concrete code/PR review priorities:
   - Match-shape: do callers/types/schemas align?
   - Verify-then-parse: validate before consuming
   - Dedup-before-write
   - Schema invariants (NOT NULL, unique, foreign-key)
   - Money-handling delta (any $, balance, transaction logic)
   - Response-shape consistency
   - Error envelopes
   - Test coverage for new branches

2. **fakematt-copyedit / fakematt-feedback** (when applicable) — Matt's voice + product instincts. For prose surfaces:
   - AI-template tells (em-dash overuse, "Here's the thing", "serves as", parallel triplets)
   - Voice consistency with the Zerg brand
   - "Why now + what this unlocks" framing in PR body if visible
   - Anti-patterns: "I hope this finds you well", "Sincerely," etc.

# Output format

Produce ONE section, in this exact shape:

```
# PR Gate Review

**Diff scope:** N files changed (X code, Y prose, Z other)

## Findings

### [HIGH | MEDIUM | LOW] — <one-line headline>
**File:** path/to/file.py:LINE (if applicable)
**Reviewer:** fakeidan | fakematt-copyedit
**Finding:** <one-paragraph explanation>
**Fix:** <concrete suggested rewrite or action>

### ... (more findings) ...

## Summary

- N HIGH findings (block PR)
- M MEDIUM findings (recommended)
- L LOW findings (FYI)

If no HIGH findings: end with `**Gate verdict: PASS**`. Otherwise `**Gate verdict: BLOCKED**`.
```

# Confidence rubric

- **HIGH** — clear violation of a documented rule (Idan's bar OR AI-tells in prose). Block PR.
- **MEDIUM** — pattern-flagged but context-dependent. Recommend fix; don't block.
- **LOW** — voice/intent ambiguous. FYI only.

# Hard rules

- **Don't invent issues.** If the diff is small/clean, say so and emit zero findings.
- **HIGH findings must cite the rule** they violate (e.g. "violates 'verify-then-parse' from Idan PR review bar").
- Be terse. Code reviewers don't read essays.
"""


def classify(files: list[str]) -> dict:
    out = {"prose": 0, "code": 0, "other": 0, "launch": 0}
    for f in files:
        if any(p.search(f) for p in LAUNCH_FILE_PATTERNS):
            out["launch"] += 1
        if any(p.search(f) for p in PROSE_PATTERNS):
            out["prose"] += 1
        elif any(f.endswith(ext) for ext in CODE_EXTS):
            out["code"] += 1
        else:
            out["other"] += 1
    return out


def count_preview_assets(files: list[str]) -> dict:
    """How many image/video/blog/landing/copy files are in the diff?

    Used to detect PRs that should have an asset-preview block in the body.
    Mirrors classify_assets() in ~/.claude/skills/pr-gate/run.py but without
    needing the per-file status (CI doesn't easily separate add/modify/delete
    here, and a deleted file just won't render — soft check is fine).
    """
    out = {"images": 0, "videos": 0, "blog": 0, "landing": 0, "copy": 0}
    for f in files:
        lf = f.lower()
        if any(lf.endswith(e) for e in ASSET_IMAGE_EXTS):
            out["images"] += 1
        elif any(lf.endswith(e) for e in ASSET_VIDEO_EXTS):
            out["videos"] += 1
        elif any(p.search(f) for p in ASSET_BLOG_PATTERNS):
            out["blog"] += 1
        elif any(p.search(f) for p in ASSET_LANDING_PATTERNS):
            out["landing"] += 1
        elif lf.endswith(".md") or lf.endswith(".mdx"):
            out["copy"] += 1
    return out


def body_has_preview_block(body: str) -> bool:
    if not body:
        return False
    return any(marker in body for marker in ASSET_PREVIEW_BODY_MARKERS)


def open_pr_count(author: str | None, exclude_pr_number: int | None) -> tuple[int, list[dict]]:
    """Query gh for Matt's open PRs across all repos. Excludes the current PR."""
    if not author:
        return 0, []
    try:
        r = subprocess.run(
            ["gh", "search", "prs", f"--author={author}", "--state=open",
             "--json", "number,title,url,repository", "--limit", "50"],
            capture_output=True, text=True, timeout=20,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 0, []
    if r.returncode != 0:
        return 0, []
    try:
        data = json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        return 0, []
    out = []
    for pr in data:
        if exclude_pr_number is not None and pr.get("number") == exclude_pr_number:
            continue
        repo = pr.get("repository", {}) or {}
        out.append({
            "number": pr.get("number"),
            "title": pr.get("title", ""),
            "url": pr.get("url", ""),
            "repo": repo.get("nameWithOwner") or repo.get("name") or "?",
        })
    return len(out), out


def scan_ai_coauthor(text: str) -> int:
    if not text:
        return 0
    n = 0
    for pat in AI_COAUTHOR_PATTERNS:
        n += len(pat.findall(text))
    return n


def required_pr_author(repo: str, identity: str | None) -> tuple[str | None, str | None]:
    """Return (required_author, reason). None means CI cannot infer authorship safely."""
    owner = repo.split("/", 1)[0] if "/" in repo else ""
    normalized = (identity or "").strip().lower()
    if normalized and normalized not in {"matt-personal", "matt-led", "ai-led"}:
        return "__invalid__", f"invalid PR_GATE_IDENTITY={identity}"
    if owner in PERSONAL_GITHUB_OWNERS or normalized == "matt-personal":
        return GITHUB_PERSONAL_ACCOUNT, "Matt personal project"
    if normalized == "matt-led":
        return GITHUB_PERSONAL_ACCOUNT, "Matt-led/heavily supervised PR"
    if normalized == "ai-led":
        return GITHUB_AI_ACCOUNT, "AI/Fake Matt-led PR"
    return None, None


def main() -> int:
    if not DIFF_FILE.exists():
        print("[pr-gate-ci] no diff file — skipping")
        REVIEW_OUT.write_text("# PR Gate Review\n\n_No diff to review._\n")
        _set_output("high_count", "0")
        return 0

    diff = DIFF_FILE.read_text(errors="ignore")[:MAX_DIFF_CHARS]
    files = []
    if FILES_FILE.exists():
        files = [l.strip() for l in FILES_FILE.read_text().splitlines() if l.strip()]
    counts = classify(files)
    print(f"[pr-gate-ci] {len(files)} files: code={counts['code']} prose={counts['prose']} launch={counts['launch']} other={counts['other']}")

    pr_author = os.environ.get("PR_AUTHOR", "").strip()
    pr_body = os.environ.get("PR_BODY", "")
    pr_repo = os.environ.get("PR_REPO", "").strip()
    pr_gate_identity = os.environ.get("PR_GATE_IDENTITY", "").strip()
    pr_number_raw = os.environ.get("PR_NUMBER", "").strip()
    try:
        pr_number = int(pr_number_raw) if pr_number_raw else None
    except ValueError:
        pr_number = None

    backlog_count, backlog_list = open_pr_count(pr_author, pr_number)
    print(f"[pr-gate-ci] backlog: {backlog_count} other open PRs by {pr_author}")

    coauthor_count = scan_ai_coauthor(pr_body)
    if coauthor_count:
        print(f"[pr-gate-ci] PR body has {coauthor_count} AI-coauthor line(s) — flagging")

    pre_findings: list[str] = []
    required_author, identity_reason = required_pr_author(pr_repo, pr_gate_identity)
    if required_author == "__invalid__":
        pre_findings.append(
            f"### [HIGH] — Invalid PR identity configuration\n"
            f"**Reviewer:** pr-gate (identity)\n"
            f"**Finding:** {identity_reason}. Expected one of: `matt-personal`, `matt-led`, `ai-led`.\n"
            f"**Fix:** Update the repository variable `PR_GATE_IDENTITY` or remove it."
        )
    elif required_author and pr_author != required_author:
        pre_findings.append(
            f"### [HIGH] — PR opened by wrong GitHub account\n"
            f"**Reviewer:** pr-gate (identity)\n"
            f"**Finding:** This PR is classified as `{identity_reason}` and must be opened by `{required_author}`, "
            f"but the PR author is `{pr_author or 'unknown'}`.\n"
            f"**Fix:** Close and reopen the PR from `{required_author}`. `skip-pr-gate` should not be used for identity routing."
        )
    elif required_author:
        print(f"[pr-gate-ci] identity OK: {pr_author} ({identity_reason})")

    if backlog_count >= OPEN_PR_CAP_DEFAULT:
        pre_findings.append(
            f"### [MEDIUM] — {backlog_count} other open PRs (cap is {OPEN_PR_CAP_DEFAULT}, {OPEN_PR_CAP_URGENT} with `--urgent`)\n"
            f"**Reviewer:** pr-gate (cap)\n"
            f"**Finding:** Matt has {backlog_count} other open PRs across repos — high backlog grows Idan's review queue. "
            f"Consider folding this into one of:\n"
            + "\n".join(f"  - {pr['repo']}#{pr['number']}: {pr['title']} ({pr['url']})" for pr in backlog_list[:5])
            + ("\n  - …more" if len(backlog_list) > 5 else "")
            + "\n**Fix:** Bundle related work; close this PR or one of the others before review."
        )
    if coauthor_count:
        pre_findings.append(
            f"### [HIGH] — PR body contains {coauthor_count} AI-coauthor line(s)\n"
            f"**Reviewer:** pr-gate (scrub)\n"
            f"**Finding:** Co-Authored-By / 'Generated with Claude' lines must not appear in PRs that flow to Idan. "
            f"The local skill scrubs these automatically; in CI they require manual removal.\n"
            f"**Fix:** `gh pr edit {pr_number or '<number>'} --body-file <new-body.md>` with the AI-coauthor lines removed."
        )
    if counts["launch"]:
        pre_findings.append(
            f"### [MEDIUM] — {counts['launch']} launch file(s) added/changed\n"
            f"**Reviewer:** pr-gate (launch-premise)\n"
            f"**Finding:** Launch-publish PRs require a fresh in-session confirm token (local check, can't run in CI). "
            f"Confirm the launch is current before merge — `feedback_reconfirm_launch_plans.md` from memory.\n"
            f"**Fix:** Verify with Matt that this launch is the current week's plan, not a stale-memory ship."
        )

    asset_counts = count_preview_assets(files)
    n_assets = sum(asset_counts.values())
    if n_assets > 0 and not body_has_preview_block(pr_body):
        breakdown = ", ".join(
            f"{k}={v}" for k, v in asset_counts.items() if v > 0
        )
        pre_findings.append(
            f"### [MEDIUM] — {n_assets} content/asset file(s) without preview block in PR body\n"
            f"**Reviewer:** pr-gate (asset-previews)\n"
            f"**Finding:** This PR touches {breakdown} but the body has no asset-preview block. "
            f"Reviewers can't see the visual diff without clicking through every file. "
            f"`pr-gate` injects this block automatically when used to open PRs.\n"
            f"**Fix:** Re-open via `python3 ~/.claude/skills/pr-gate/run.py …`, "
            f"or run pr-gate locally (`--dry-run`) and paste `.pr-gate-asset-previews.md` "
            f"into the body via `gh pr edit {pr_number or '<number>'} --body-file …`."
        )

    if not diff.strip():
        body_parts = ["# PR Gate Review", "", "_Empty diff._"]
        if pre_findings:
            body_parts.append("\n## Pre-flight findings\n")
            body_parts.extend(pre_findings)
        REVIEW_OUT.write_text("\n".join(body_parts))
        _set_output("high_count", str(sum(1 for f in pre_findings if f.startswith("### [HIGH]"))))
        return 0

    user_msg = (
        f"# PR diff\n\n"
        f"Files changed ({len(files)}): code={counts['code']} prose={counts['prose']} "
        f"launch={counts['launch']} other={counts['other']}\n\n"
        f"```\n{', '.join(files[:30])}\n```\n\n"
        f"## Diff\n\n```diff\n{diff}\n```\n"
    )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    review_text = ""
    if not api_key:
        review_text = (
            "# PR Gate Review\n\n"
            ":warning: `ANTHROPIC_API_KEY` not set — LLM review skipped. "
            "Pre-flight checks below still apply.\n"
        )
        print("[pr-gate-ci] ANTHROPIC_API_KEY missing — soft-pass on LLM review")
    else:
        client = Anthropic(api_key=api_key)
        print(f"[pr-gate-ci] calling {MODEL}…")
        resp = client.messages.create(
            model=MODEL, max_tokens=4000, system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        review_text = "".join(block.text for block in resp.content if block.type == "text")

    # Inject pre-findings + LLM review
    final_parts = [review_text.rstrip()]
    if pre_findings:
        final_parts.append("\n\n## Pre-flight findings\n")
        final_parts.extend(pre_findings)
    final = "\n".join(final_parts).strip() + "\n"
    REVIEW_OUT.write_text(final)
    print(f"[pr-gate-ci] review written: {REVIEW_OUT}")

    high_count = len(re.findall(r"^### \[?HIGH\]?\b", final, re.M))
    blocked = "**Gate verdict: BLOCKED**" in final
    if blocked and high_count == 0:
        high_count = 1
    _set_output("high_count", str(high_count))
    print(f"[pr-gate-ci] HIGH findings: {high_count}")
    return 0


def _set_output(name: str, value: str) -> None:
    out_path = os.environ.get("GITHUB_OUTPUT")
    if out_path:
        with open(out_path, "a") as f:
            f.write(f"{name}={value}\n")


if __name__ == "__main__":
    sys.exit(main())
