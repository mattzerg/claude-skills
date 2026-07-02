#!/usr/bin/env python3
"""PR gate — wraps `gh pr create` with mandatory qa-gate + fakematt pre-flight.

Usage:
    python3 ~/.claude/skills/pr-gate/run.py [gh-pr-create-args...] [gate-flags...]

Gate flags (all optional):
    --base BRANCH        base branch (default: development; falls back to main)
    --skip-copyedit      skip fakematt-copyedit
    --skip-fakeidan      skip qa-gate/fakeidan (DON'T DO THIS)
    --fast               pre-push fast path: skip LLM reviews; keep identity/cap/scrub/launch checks
    --mode MODE          qa-gate/fakeidan mode: auto, code, prose, or both
    --urgent             raise the open-PR cap from 2 to 3 for this open (logged)
    --force              override HIGH findings or backlog cap (logged)
    --dry-run            run gate + print verdict, don't actually open
    --matt-personal      route this PR through matteisn
    --matt-led           route this PR through matteisn
    --ai-led             route this PR through mattzerg unless personal
    --no-prior-review    logged escape hatch when no prior reviewed surface overlaps
    --no-cross-model     skip the cross-model-check (codex second-opinion) section.
                         Off by default — always-on cross-model verification is the
                         point. Use only for rate-limit conservation or CI smoke.
    --no-cache           bypass the 30-min sub-skill result cache. Forces fakeidan,
                         cross-model-check, fakematt-copyedit, and launch-announcement
                         to re-run from scratch even if the diff hash is unchanged.

All other args are forwarded to `gh pr create` verbatim.

Two enforced rules beyond fake-skill reviews:
  - GitHub identity routing: Matt personal projects and Matt-led/heavily supervised
    PRs use matteisn; AI/Fake Matt-led Zerg/company PRs use mattzerg.
  - Open-PR cap: max 2 open PRs by Matt at once across Epoch-ML/* repos
    (3 with --urgent). Bundle into an existing PR; don't multiply Idan's review queue.
  - No AI coauthors: `Co-Authored-By: Claude` lines and "Generated with Claude
    Code" footers are silently scrubbed from --body / --body-file before invoking gh.
    Matching lines in commit messages block locally until the commits are reworded.
"""
from __future__ import annotations

import argparse
import datetime as dt
from html import escape
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import urllib.parse
from pathlib import Path

SKILL_DIR = Path(__file__).parent
LOG_DIR = SKILL_DIR / "logs"
OVERRIDE_LOG = LOG_DIR / "overrides.log"

QA_GATE = Path.home() / ".codex" / "skills" / "qa-gate" / "scripts" / "run_fakeidan.py"
QA_GATE_VALIDATE_MANIFEST = Path.home() / ".codex" / "skills" / "qa-gate" / "scripts" / "validate_manifest.py"
FAKEMATT_COPYEDIT = Path.home() / ".claude" / "skills" / "fakematt-copyedit" / "run.py"
LAUNCH_ANNOUNCEMENT = Path.home() / ".claude" / "skills" / "launch-announcement" / "run.py"
CROSS_MODEL_CHECK = Path.home() / ".claude" / "skills" / "cross-model-check" / "run.py"
LAUNCH_PREMISE = SKILL_DIR / "launch_premise.py"
GITHUB_PERSONAL_ACCOUNT = "matteisn"
GITHUB_AI_ACCOUNT = "mattzerg"
PERSONAL_GITHUB_OWNERS = {"matteisn", "mattheweisner"}
MATTZERG_TOKEN_FILE = Path.home() / ".config" / "zerg" / "gh_token"
GH_ENV_OVERRIDE: dict[str, str] | None = None

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
CODE_EXTS = (
    ".py", ".ts", ".tsx", ".js", ".jsx", ".vue", ".rs", ".go", ".java",
    ".rb", ".c", ".cpp", ".h", ".sql", ".sh", ".bash", ".zsh",
)
CONFIG_EXTS = (".json", ".yaml", ".yml", ".toml", ".lock", ".env")
CODE_BASENAMES = {"Makefile", "Dockerfile", "Brewfile"}

# Workflow-only path patterns — files that exist purely for a single dev's
# local environment. A PR whose diff is 100% these paths violates
# feedback_prs_for_products_not_workflow.md: Zerg product repos ship product
# or content, not personal workflow. Mixed diffs (any non-workflow file) pass.
WORKFLOW_PATH_PATTERNS = (
    re.compile(r"(^|/)\.claude/"),
    re.compile(r"(^|/)\.codex/"),
    re.compile(r"(^|/)\.vscode/"),
    re.compile(r"(^|/)\.idea/"),
    re.compile(r"(^|/)\.devcontainer/"),
    re.compile(r"(^|/)\.editorconfig$"),
    re.compile(r"(^|/)infra/docker-compose.*\.ya?ml$", re.I),
)

# Asset preview classification — independent from prose/code classification.
# A blog markdown file is BOTH "prose" (triggers fakematt-copyedit) AND "blog"
# (triggers a preview block in the PR body). Same file, two purposes.
ASSET_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".avif")
ASSET_VIDEO_EXTS = (".mp4", ".mov", ".webm", ".m4v")
BLOG_PATH_PATTERNS = (
    re.compile(r"(^|/)content/blog/.+\.mdx?$", re.I),
    re.compile(r"MattZerg/Writing/.+\.mdx?$", re.I),
    re.compile(r"(^|/)blog/[^/]+\.mdx?$", re.I),
)
LANDING_PATH_PATTERNS = (
    re.compile(r"(^|/)web/src/pages/.+\.(vue|tsx|jsx)$", re.I),
    re.compile(r"(^|/)pages/.*landing.*\.(vue|tsx|jsx|html)$", re.I),
    re.compile(r"(^|/)landing-?pages?/", re.I),
)
ASSET_PREVIEW_FILE = ".pr-gate-asset-previews.md"
FULL_REVIEW_FILE = ".pr-gate-review-full.md"
DIFF_REVIEW_CHAR_LIMIT = 150000  # bumped 60k→150k 2026-05-29 (pSEO 95KB diff truncated review)
PRIOR_REVIEW_RE = re.compile(r"^##\s+Prior[\s-]review\s+items\s+carried\s+forward\s*$", re.I | re.M)


def parse_args():
    """Split argv into gate flags + gh-pr-create passthrough."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--base", default=None)
    parser.add_argument("--skip-copyedit", action="store_true")
    parser.add_argument("--skip-fakeidan", action="store_true")
    parser.add_argument("--fast", action="store_true",
                        help="fast-path mode: identity + cap + AI-coauthor scrub + launch-premise only. "
                             "Skips qa-gate/fakeidan + fakematt-copyedit + launch-announcement (LLM calls). "
                             "Use in pre-push hook to avoid SSH idle-timeout dropping the connection.")
    parser.add_argument("--mode", choices=("auto", "code", "prose", "both"), default="auto",
                        help="qa-gate/fakeidan review mode. auto runs both code and prose passes for mixed diffs.")
    parser.add_argument("--urgent", action="store_true",
                        help="raise open-PR cap from 2 to 3 (logged)")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--matt-personal", action="store_true",
                        help="mark repo/project as Matt personal work; requires matteisn")
    parser.add_argument("--matt-led", action="store_true",
                        help="mark PR as Matt-led or heavily supervised; requires matteisn")
    parser.add_argument("--ai-led", action="store_true",
                        help="mark PR as AI/Fake Matt-led; requires mattzerg unless personal")
    parser.add_argument("--no-asset-previews", action="store_true",
                        help="suppress auto-generated asset preview block in PR body")
    parser.add_argument("--no-prior-review", action="store_true",
                        help="logged escape hatch when no prior fakeidan-reviewed surface overlaps this PR")
    parser.add_argument("--no-cross-model", action="store_true",
                        help="skip cross-model-check (codex second-opinion). Off by default — "
                             "always-on cross-model verification is the whole point of the skill. "
                             "Use only for rate-limit conservation or CI smoke runs.")
    parser.add_argument("--no-cache", action="store_true",
                        help="bypass the 30-min sub-skill result cache. Forces fakeidan, "
                             "cross-model-check, fakematt-copyedit, and launch-announcement "
                             "to re-run from scratch even if the diff hash is unchanged from a "
                             "prior gate run on this branch.")
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


def github_remote_owner() -> str | None:
    """Infer the GitHub remote owner from origin, if this is a GitHub repo."""
    r = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    url = r.stdout.strip()
    m = re.search(r"github\.com[:/]([^/]+)/[^/]+(?:\.git)?$", url)
    if m:
        return m.group(1)
    return None


def _parse_gh_auth_account(text: str, returncode: int) -> str | None:
    """Parse a usable active account from `gh auth status` output.

    This is necessarily tied to gh's human-readable status markers. When a
    token is available, `gh api user --jq .login` is the authoritative fallback.
    """
    text = strip_ansi(text)
    accounts: list[str] = []
    for block in re.finditer(
        r"✓ Logged in to github\.com account\s+([^\s()]+).*?(?=\n\s*[✓✗✘!⚠]|\Z)",
        text,
        flags=re.S,
    ):
        accounts.append(block.group(1))
        if re.search(r"^\s+-\s+Active account:\s+true\s*$", block.group(0), flags=re.M):
            return block.group(1)
    # Older gh output can omit Active account. This fallback is intentionally
    # lossy in multi-account installs; verify_github_identity still checks name.
    if returncode == 0 and accounts:
        return accounts[0]
    m = re.search(r"Logged in to github\.com account\s+([^\s()]+)", text)
    if returncode == 0 and m:
        return m.group(1)
    return None


def strip_ansi(text: str) -> str:
    text = re.sub(r"\x1B\[[0-9;]*[mK]", "", text)
    return re.sub(r"\x1B\][^\x07\x1B]*(?:\x07|\x1B\\)", "", text)


def active_github_account(required_account: str | None = None) -> tuple[str | None, str]:
    """Return (account, raw_status) from gh auth status."""
    try:
        r = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True, timeout=15)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return None, str(e)
    text = (r.stdout or "") + "\n" + (r.stderr or "")
    parsed = _parse_gh_auth_account(text, r.returncode)
    if parsed:
        return parsed, text

    env = os.environ.copy()
    should_try_mattzerg_fallback = (
        required_account == GITHUB_AI_ACCOUNT
        and "GH_TOKEN" not in env
        and "GITHUB_TOKEN" not in env
        and MATTZERG_TOKEN_FILE.exists()
    )
    if should_try_mattzerg_fallback:
        st = MATTZERG_TOKEN_FILE.stat()
        if st.st_mode & 0o077:
            return None, (
                text
                + f"\n[pr-gate] ERROR: {MATTZERG_TOKEN_FILE} has overly open permissions "
                + f"({oct(st.st_mode & 0o777)}). Must be mode 600."
            )
        try:
            token = MATTZERG_TOKEN_FILE.read_text().strip()
            env["GH_TOKEN"] = token
        except OSError:
            return None, text
        try:
            status = subprocess.run(
                ["gh", "auth", "status"], capture_output=True, text=True, timeout=15, env=env
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            return None, text + "\n" + str(e)
        fallback_text = (status.stdout or "") + "\n" + (status.stderr or "")
        parsed = _parse_gh_auth_account(fallback_text, status.returncode)
        if parsed:
            set_gh_env_override(token)
            return parsed, fallback_text
        try:
            api = subprocess.run(
                ["gh", "api", "user", "--jq", ".login"],
                capture_output=True, text=True, timeout=15, env=env,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            return None, text + "\n" + str(e)
        if api.returncode == 0 and api.stdout.strip():
            set_gh_env_override(token)
            return api.stdout.strip(), fallback_text
        text += "\n" + fallback_text + "\n" + (api.stderr or api.stdout or "")
    return None, text


def set_gh_env_override(token: str) -> None:
    global GH_ENV_OVERRIDE
    GH_ENV_OVERRIDE = {"GH_TOKEN": token}


def gh_env() -> dict[str, str] | None:
    if not GH_ENV_OVERRIDE:
        return None
    env = os.environ.copy()
    env.update(GH_ENV_OVERRIDE)
    return env


def required_github_account(args) -> tuple[str, str]:
    """Decide which GitHub account must be active before PR operations."""
    owner = github_remote_owner()
    is_personal = args.matt_personal or (owner in PERSONAL_GITHUB_OWNERS)
    if is_personal:
        return GITHUB_PERSONAL_ACCOUNT, "Matt personal project"
    if args.matt_led:
        return GITHUB_PERSONAL_ACCOUNT, "Matt-led/heavily supervised PR"
    if args.ai_led:
        return GITHUB_AI_ACCOUNT, "AI/Fake Matt-led PR"
    # pr-gate is normally run by agents; default non-personal agent-led work to mattzerg.
    return GITHUB_AI_ACCOUNT, "default agent-led non-personal PR"


def verify_github_identity(args) -> bool:
    required, reason = required_github_account(args)
    active, status = active_github_account(required)
    if active == required:
        print(f"[pr-gate] GitHub identity OK: {active} ({reason})", file=sys.stderr)
        return True
    print("[pr-gate] BLOCKED — wrong GitHub account for this PR context.", file=sys.stderr)
    print(f"[pr-gate] Required: {required} ({reason})", file=sys.stderr)
    print(f"[pr-gate] Active: {active or 'unknown'}", file=sys.stderr)
    print("[pr-gate] Switch accounts first, e.g. `gh auth switch --user "
          f"{required}`, then rerun pr-gate.", file=sys.stderr)
    if not active:
        print(f"[pr-gate] gh auth status output:\n{status[:1000]}", file=sys.stderr)
    return False


def changed_files(base: str) -> tuple[list[str], str | None]:
    r = subprocess.run(["git", "diff", "--name-only", f"origin/{base}...HEAD"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return [], (r.stderr or r.stdout or f"git diff failed with return code {r.returncode}").strip()
    return [f.strip() for f in r.stdout.splitlines() if f.strip()], None


def diff_names(base: str, separator: str) -> set[str] | None:
    r = subprocess.run(["git", "diff", "--name-only", f"origin/{base}{separator}HEAD"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return {f.strip() for f in r.stdout.splitlines() if f.strip()}


def stale_base_blocker(base: str) -> str | None:
    """Return a blocker message when three-dot review diff diverges from merge diff."""
    three_dot = diff_names(base, "...")
    two_dot = diff_names(base, "..")
    if three_dot is None or two_dot is None:
        return (
            f"Unable to verify branch base against origin/{base}; git diff failed. "
            "Fetch/rebase or inspect the repository state, then rerun pr-gate."
        )
    if three_dot == two_dot:
        return None
    return (
        f"Branch base is stale: origin/{base}...HEAD has {len(three_dot)} file(s), "
        f"but origin/{base}..HEAD has {len(two_dot)} file(s). "
        f"Fetch and rebase onto origin/{base}, then rerun pr-gate: "
        f"`git fetch origin {base} && git rebase origin/{base}`."
    )


def refresh_base_ref(base: str) -> str | None:
    """Best-effort fetch so stale-base checks use a fresh origin/<base> ref."""
    try:
        r = subprocess.run(
            ["git", "fetch", "origin", base, "--quiet"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return str(e)
    if r.returncode != 0:
        return (r.stderr or r.stdout or f"git fetch failed with return code {r.returncode}").strip()
    return None


def full_diff(base: str) -> str:
    r = subprocess.run(["git", "diff", f"origin/{base}...HEAD"],
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def commit_messages(base: str) -> str:
    r = subprocess.run(
        ["git", "log", f"origin/{base}..HEAD", "--format=%B%n---%n"],
        capture_output=True,
        text=True,
    )
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
        elif (
            any(f.endswith(ext) for ext in CODE_EXTS)
            or any(f.endswith(ext) for ext in CONFIG_EXTS)
            or f.endswith(".env.example")
            or Path(f).name in CODE_BASENAMES
        ):
            out["code"].append(f)
        else:
            out["other"].append(f)
    return out


def launch_premise_missing(classification: dict) -> bool:
    return bool(classification["launch"]) and not LAUNCH_PREMISE.exists()


def is_workflow_only_diff(files: list[str]) -> bool:
    """True iff every changed file matches a workflow-only path pattern.

    Mixed diffs (any non-workflow file) return False — only blocks the clear
    100%-workflow case. See feedback_prs_for_products_not_workflow.md.
    """
    if not files:
        return False
    return all(
        any(p.search(f) for p in WORKFLOW_PATH_PATTERNS)
        for f in files
    )


def is_zerg_product_repo(owner: str | None) -> bool:
    """Workflow-only rule applies to Zerg product repos, not Matt personal repos."""
    if not owner:
        return False
    return owner not in PERSONAL_GITHUB_OWNERS


_TOOL_FAILURE_PATTERN = re.compile(
    r"timeout — gate FAIL-CLOSED|FAIL-CLOSED|timeout\)$|DIFF TRUNCATED|UNABLE_TO_RUN",
    re.M,
)


def is_tool_failure_text(text: str) -> bool:
    """True if `text` is a sub-skill tool-failure sentinel.

    Used to gate cache.put(): we must NEVER cache a failure as if it were a
    successful review. Without this guard, a single qa-gate / copyedit timeout
    leaves a poisoned cache entry that satisfies subsequent runs as a cache
    hit and never gets re-tried.
    """
    if not text:
        return True
    return bool(_TOOL_FAILURE_PATTERN.search(text))


def has_high_findings(text: str) -> tuple[bool, list[str]]:
    """Heuristic: look for 'HIGH' confidence/severity markers in review output.

    Also fail-closed on tooling failures: if a fake-skill timed out or crashed
    we must NOT count that as "0 HIGH" — silence isn't success. Treat any
    timeout/crash sentinel as a synthetic HIGH so the gate blocks.
    """
    if re.search(r"timeout — gate FAIL-CLOSED|FAIL-CLOSED|timeout\)$", text, re.M):
        return (True, ["**HIGH** (gate fail-closed: review tool timed out — re-run with longer timeout or split the diff)"])
    if "DIFF TRUNCATED" in text:
        return (True, ["**HIGH** (DIFF TRUNCATED — qa-gate did not review the full diff)"])
    lines = text.splitlines()
    high_lines = []
    in_explicit_high_block = False
    # fakematt-copyedit emits `### F<n> — <title>` followed within ~8 lines by
    # `**Confidence:** HIGH`. Without this lookahead, copyedit HIGHs were
    # counted as zero by pr-gate (2026-05-29).
    pending_finding_header: str | None = None
    lines_since_header = 0
    for line in lines:
        if pending_finding_header is not None:
            lines_since_header += 1
            if re.search(r"^\*\*Confidence:\*\*\s*HIGH\b", line):
                high_lines.append(pending_finding_header)
                pending_finding_header = None
                lines_since_header = 0
            elif re.search(r"^\*\*Confidence:\*\*\s*(MEDIUM|LOW)\b", line):
                pending_finding_header = None
                lines_since_header = 0
            elif lines_since_header > 8:
                pending_finding_header = None
                lines_since_header = 0
        if re.search(r"^\*\*HIGH findings \(\d+\):\*\*$", line):
            in_explicit_high_block = True
            continue
        if in_explicit_high_block:
            if not line.strip():
                in_explicit_high_block = False
                continue
            if line.startswith("- "):
                high_lines.append(line)
                continue
            if line.startswith("<details>"):
                in_explicit_high_block = False
                continue
            in_explicit_high_block = False
        # Canonical fakeidan uses an em dash; accept dash variants defensively.
        if re.search(r"^### C\d+\s+[\u2014\u2013-]\s+\S", line):
            # fakeidan's pre-merge ask numbering — C-prefixed = required-before-merge
            high_lines.append(line)
        elif re.search(r"^- \*\*HIGH\*\*", line):
            high_lines.append(line)
        elif re.search(r"^### F\d+\s+[—–-]\s+\S", line):
            # fakematt-copyedit finding header; confirm next few lines mark HIGH
            pending_finding_header = line
            lines_since_header = 0
    return (len(high_lines) > 0, high_lines)


def render_qa_gate_review(payload: dict, review_text: str) -> str:
    """Render qa-gate JSON plus fakeidan review text for .pr-gate-review.md."""
    verdict = payload.get("verdict", "UNABLE_TO_RUN")
    status = payload.get("status", "BLOCKED")
    manifest_path = payload.get("manifest_path", "")
    review_files = payload.get("review_files") or []
    lines = [
        "# qa-gate result",
        "",
        f"- `qa-gate status`: {status}",
        f"- `fakeidan verdict`: {verdict}",
        f"- `qa-gate manifest`: {manifest_path}",
    ]
    if payload.get("error"):
        lines.append(f"- `qa-gate error`: {payload['error']}")
    if review_files:
        lines.append("- `fakeidan output paths`:")
        for path in review_files:
            lines.append(f"  - {path}")
    if verdict != "Approve":
        lines.extend(["", f"- **HIGH** qa-gate verdict is `{verdict}`; manifest: {manifest_path}"])
    if review_text:
        lines.extend(["", "---", "", review_text])
    return "\n".join(lines)


def format_diff_for_review(base: str, diff_text: str) -> tuple[str, bool]:
    content = diff_text[:DIFF_REVIEW_CHAR_LIMIT]
    truncated = len(diff_text) > DIFF_REVIEW_CHAR_LIMIT
    if truncated:
        content += (
            "\n\n[DIFF TRUNCATED - reviewed first "
            f"{DIFF_REVIEW_CHAR_LIMIT} of {len(diff_text)} chars; remaining diff not reviewed]"
        )
    return f"# PR diff (base: origin/{base})\n\n```diff\n{content}\n```\n", truncated


def fakeidan_modes(args, classification: dict) -> list[str]:
    """Pick qa-gate/fakeidan lenses for the current diff."""
    if args.mode == "code":
        return ["code"]
    if args.mode == "prose":
        return ["prose"]
    if args.mode == "both":
        return ["code", "prose"]
    if classification["code"] and classification["prose"]:
        return ["code", "prose"]
    if classification["prose"]:
        return ["prose"]
    return ["code"]


def run_fakeidan(
    base: str,
    classification: dict,
    out_dir: Path,
    model: str = "claude-sonnet-4-6",
    mode: str | None = None,
    diff_text: str | None = None,
) -> tuple[Path | None, str]:
    """Run qa-gate's fakeidan wrapper on the full diff. Mode = code if any code files, else prose."""
    out_dir.mkdir(parents=True, exist_ok=True)
    review_mode = mode or ("code" if classification["code"] else "prose")
    if diff_text is None:
        diff_text = full_diff(base)
    if not diff_text.strip():
        return None, "(git diff returned empty — gate FAIL-CLOSED)"
    diff_file = out_dir / "diff.md"
    diff_review_text, diff_truncated = format_diff_for_review(base, diff_text)
    diff_file.write_text(diff_review_text)
    if not QA_GATE.exists():
        return None, "(qa-gate runner missing — gate FAIL-CLOSED)"
    # pr-gate runs cross-model-check itself as a sibling section — tell qa-gate
    # not to double-fire its own xmodel pass.
    qa_env = os.environ.copy()
    qa_env["QA_GATE_SKIP_XMODEL"] = "1"
    try:
        r = subprocess.run(
            [
                "python3", str(QA_GATE), str(diff_file),
                "--mode", review_mode,
                "--quick",
                "--model", model,
                "--timeout", "300",  # bumped 120→300 2026-05-29 (pSEO diff truncated)
                "--max-attempts", "1",
            ],
            capture_output=True, text=True, timeout=900, env=qa_env,  # 600→900
        )
        try:
            payload = json.loads(r.stdout or "{}")
        except json.JSONDecodeError:
            return None, f"(qa-gate emitted invalid JSON — gate FAIL-CLOSED)\n\nstdout:\n{r.stdout}\n\nstderr:\n{r.stderr}"
        manifest_path = payload.get("manifest_path")
        if manifest_path and QA_GATE_VALIDATE_MANIFEST.exists():
            validation = subprocess.run(
                ["python3", str(QA_GATE_VALIDATE_MANIFEST), str(manifest_path)],
                capture_output=True, text=True, timeout=30,
            )
            if validation.returncode != 0:
                payload["verdict"] = "UNABLE_TO_RUN"
                payload["status"] = "BLOCKED"
                payload["error"] = "qa-gate manifest validation failed: " + (validation.stdout or validation.stderr)
        elif manifest_path:
            payload["verdict"] = "UNABLE_TO_RUN"
            payload["status"] = "BLOCKED"
            payload["error"] = (
                f"qa-gate returned manifest at {manifest_path} but validator missing "
                f"at {QA_GATE_VALIDATE_MANIFEST}; gate FAIL-CLOSED"
            )
        review_files = [Path(path) for path in payload.get("review_files") or []]
        review_text = ""
        for review_file in review_files:
            if not review_file.exists():
                print(f"[pr-gate] ERROR: qa-gate review file missing: {review_file}", file=sys.stderr)
                review_text += f"\n**ERROR**: qa-gate review file missing: {review_file}\n"
                continue
            review_text += review_file.read_text(errors="replace") + "\n"
        rendered = render_qa_gate_review(payload, review_text)
        if diff_truncated:
            rendered = (
                f"- **HIGH** DIFF TRUNCATED: reviewed first {DIFF_REVIEW_CHAR_LIMIT} "
                f"of {len(diff_text)} chars; remaining diff not reviewed\n\n"
                + rendered
            )
        return (review_files[0] if review_files else None), rendered
    except subprocess.TimeoutExpired:
        return None, "(qa-gate/fakeidan timeout — gate FAIL-CLOSED)"


def changed_paths_existing(files: list[str], repo_root: Path | None = None) -> list[Path]:
    """Resolve git-diff relative paths against repo root, not process CWD."""
    root = repo_root or Path.cwd()
    existing: list[Path] = []
    for f in files:
        path = Path(f)
        candidate = path if path.is_absolute() else root / path
        if candidate.exists():
            existing.append(candidate)
    return existing


def run_copyedit(
    prose_files: list[str],
    out_dir: Path,
    model: str = "claude-opus-4-7",
    repo_root: Path | None = None,
) -> tuple[list[Path], str]:
    """Run fakematt-copyedit on prose files."""
    if not prose_files:
        return [], "(no prose touched — skipped copyedit)"
    existing = changed_paths_existing(prose_files, repo_root)
    if not existing:
        return [], "(prose files not found locally — skipped copyedit)"
    if not FAKEMATT_COPYEDIT.exists():
        return [], "(fakematt-copyedit runner missing — gate FAIL-CLOSED)"
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        r = subprocess.run(
            ["python3", str(FAKEMATT_COPYEDIT)] + [str(p) for p in existing] + [
                "--out-dir", str(out_dir), "--model", model, "--no-pdf",
            ],
            capture_output=True, text=True, timeout=1200,  # 600→1200 2026-05-29 (9-file pSEO review timed out)
        )
        review_files = list(out_dir.glob("*.review.md"))
        if not review_files:
            detail = "\n".join(part for part in (r.stdout.strip(), r.stderr.strip()) if part)
            return [], "(fakematt-copyedit produced no review files — gate FAIL-CLOSED)" + (f"\n\n{detail}" if detail else "")
        text = "\n\n---\n\n".join(p.read_text() for p in review_files)
        return review_files, text
    except subprocess.TimeoutExpired:
        return [], "(copyedit timeout — gate FAIL-CLOSED)"


def run_launch_review(
    launch_files: list[str],
    out_dir: Path,
    model: str = "claude-opus-4-7",
    repo_root: Path | None = None,
) -> tuple[list[Path], str]:
    """Run launch-announcement review on launch-post files."""
    if not launch_files:
        return [], "(no launch posts touched — skipped)"
    existing = changed_paths_existing(launch_files, repo_root)
    if not existing:
        return [], "(launch files not found locally — skipped)"
    if not LAUNCH_ANNOUNCEMENT.exists():
        return [], "(launch-announcement runner missing — gate FAIL-CLOSED)"
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        r = subprocess.run(
            ["python3", str(LAUNCH_ANNOUNCEMENT), "review"] + [str(p) for p in existing] + [
                "--out-dir", str(out_dir), "--model", model, "--no-pdf",
            ],
            capture_output=True, text=True, timeout=600,
        )
        review_files = list(out_dir.glob("*.review.md"))
        if not review_files:
            detail = "\n".join(part for part in (r.stdout.strip(), r.stderr.strip()) if part)
            return [], "(launch-announcement produced no review files — gate FAIL-CLOSED)" + (f"\n\n{detail}" if detail else "")
        text = "\n\n---\n\n".join(p.read_text() for p in review_files)
        return review_files, text
    except subprocess.TimeoutExpired:
        return [], "(launch review timeout — gate FAIL-CLOSED)"


def cross_model_mode(classification: dict) -> str:
    """Pick the xmodel prompt template based on the diff classification."""
    if classification.get("launch"):
        return "launch"
    if classification.get("prose") and not classification.get("code"):
        return "prose"
    if classification.get("code"):
        return "code"
    return "generic"


def run_cross_model(
    base: str,
    classification: dict,
    out_dir: Path,
    repo_root: Path,
    timeout: int = 300,
) -> tuple[Path | None, str]:
    """Run cross-model-check on the diff. Returns (review_path, review_text)."""
    if not CROSS_MODEL_CHECK.exists():
        return None, "(cross-model-check runner missing — informational, not blocking)"

    # Pick a representative artifact: prefer first prose file for prose/launch mode,
    # otherwise dump the full diff into a temp file and review that.
    mode = cross_model_mode(classification)
    out_dir.mkdir(parents=True, exist_ok=True)

    if mode in ("prose", "launch") and classification.get(mode):
        candidates = changed_paths_existing(classification[mode], repo_root)
        if candidates:
            artifact = candidates[0]
        else:
            artifact = None
    else:
        artifact = None

    if artifact is None:
        # No specific file — write the full diff to a tmp file and review it
        diff_text = full_diff(base)
        if not diff_text.strip():
            return None, "(no diff to cross-check — skipped)"
        diff_path = out_dir / "xmodel-diff.patch"
        diff_path.write_text(diff_text, encoding="utf-8")
        artifact = diff_path

    try:
        r = subprocess.run(
            [
                "python3", str(CROSS_MODEL_CHECK), str(artifact),
                "--mode", mode,
                "--from", "claude",
                "--diff", f"origin/{base}",
                "--out-dir", str(out_dir),
                "--timeout", str(timeout),
                "--repo-root", str(repo_root),
            ],
            capture_output=True, text=True, timeout=timeout + 30,
        )
    except subprocess.TimeoutExpired:
        return None, "(cross-model-check timeout — informational, not blocking)"

    # Exit codes: 0 clean, 2 HIGH, 3 skipped, 1 usage error
    if r.returncode == 1:
        detail = (r.stderr.strip() or r.stdout.strip())[:500]
        return None, f"(cross-model-check usage error — informational)\n\n{detail}"

    # stdout is the review file path
    out_path_str = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    review_path = Path(out_path_str) if out_path_str else None
    if review_path is None or not review_path.exists():
        # Fall back to any file produced in out_dir
        candidates = sorted(out_dir.glob("*.xmodel.*.md"))
        review_path = candidates[-1] if candidates else None

    if review_path is None:
        detail = (r.stderr.strip() or r.stdout.strip())[:500]
        return None, f"(cross-model-check produced no review file — informational)\n\n{detail}"

    text = review_path.read_text(encoding="utf-8")
    # Exit-3 = skipped: scrub any stray HIGH bullets so the gate doesn't block on a skip
    if r.returncode == 3:
        text = re.sub(r"(##\s+HIGH\s*\n)(.*?)(\n##\s+)", r"\1\3", text, count=1, flags=re.S)
    # Transform xmodel's `## HIGH\n- foo\n- bar` into pr-gate's recognized
    # `**HIGH findings (N):**\n- foo\n- bar` so has_high_findings() picks it up.
    high_match = re.search(r"^##\s+HIGH\s*\n((?:(?:[-*]\s+.*|.*?)\n)*?)(?=^##\s+|\Z)",
                           text, re.M)
    if high_match:
        body = high_match.group(1)
        bullets = [ln for ln in body.splitlines() if ln.strip().startswith(("- ", "* "))]
        # Skip placeholder bullets
        bullets = [b for b in bullets if b.strip(" -*").strip().lower() not in ("", "...", "none", "n/a")]
        if bullets:
            header = f"**HIGH findings ({len(bullets)}):**"
            replacement = "\n".join([header, *bullets, ""])
            text = text[:high_match.start()] + replacement + text[high_match.end():]
    return review_path, text


def file_status_map(base: str) -> dict[str, str]:
    """Map changed-file path → status letter (M/A/D/R/...) vs origin/<base>.

    Used to skip deleted files when building previews — embedding a raw URL for
    a file that no longer exists on the branch is just a 404 in the PR body.
    """
    r = subprocess.run(["git", "diff", "--name-status", f"origin/{base}...HEAD"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return {}
    out: dict[str, str] = {}
    for line in r.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            out[parts[-1]] = parts[0][0]
    return out


def classify_assets(files: list[str], status: dict[str, str]) -> dict:
    """Bucket changed files into preview-worthy categories.

    Independent of classify(): a blog .md is BOTH "prose" (fakematt-copyedit)
    and "blog" (preview block). Deleted files are dropped.
    """
    out: dict[str, list[str]] = {"images": [], "videos": [], "blog": [], "landing": [], "copy": []}
    for f in files:
        if status.get(f) == "D":
            continue
        lf = f.lower()
        if any(lf.endswith(e) for e in ASSET_IMAGE_EXTS):
            out["images"].append(f)
        elif any(lf.endswith(e) for e in ASSET_VIDEO_EXTS):
            out["videos"].append(f)
        elif any(p.search(f) for p in BLOG_PATH_PATTERNS):
            out["blog"].append(f)
        elif any(p.search(f) for p in LANDING_PATH_PATTERNS):
            out["landing"].append(f)
        elif lf.endswith(".md") or lf.endswith(".mdx"):
            out["copy"].append(f)
    return out


def repo_owner_name() -> tuple[str | None, str | None]:
    r = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True)
    if r.returncode != 0:
        return None, None
    url = r.stdout.strip()
    m = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$", url)
    if m:
        return m.group(1), m.group(2)
    return None, None


def current_branch_name() -> str | None:
    r = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip() and r.stdout.strip() != "HEAD":
        return r.stdout.strip()
    return None


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Tiny YAML frontmatter parser. Handles flat key: value pairs only.

    Anything more structured (lists, nested maps) is left to the body — the
    preview only needs title/description/hero, all of which are flat strings.
    """
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_lines = text[3:end].strip().splitlines()
    body = text[end + 4:].lstrip("\n")
    fm: dict[str, str] = {}
    for line in fm_lines:
        if ":" not in line or line.startswith((" ", "\t", "-", "#")):
            continue
        k, _, v = line.partition(":")
        fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm, body


def first_words(text: str, n: int = 80) -> str:
    plain = re.sub(r"`[^`]+`", " ", text)
    plain = re.sub(r"<[^>]+>", " ", plain)
    plain = re.sub(r"[*_\[\]()#]", " ", plain)
    words = re.sub(r"\s+", " ", plain).strip().split()
    return " ".join(words[:n]) + ("…" if len(words) > n else "")


def _url_quote_path(p: str) -> str:
    return "/".join(urllib.parse.quote(seg) for seg in p.split("/"))


def build_asset_previews(
    repo_root: Path,
    base: str,
    assets: dict,
    owner: str | None,
    repo: str | None,
    branch: str | None,
) -> str | None:
    """Render a `<details>`-wrapped preview block for content/blog/copy/video assets.

    Returns None if no assets in scope. URLs use raw.githubusercontent.com so
    images render inline once the branch is on origin (gh pr create pushes
    automatically). For dry-run, branch may not be pushed yet, and private repos
    may 404 without GitHub auth; links still preview structurally.
    """
    branch_url = urllib.parse.quote(branch, safe="/") if branch else None
    raw_base = (
        f"https://raw.githubusercontent.com/{owner}/{repo}/{branch_url}"
        if owner and repo and branch_url else None
    )
    blob_base = (
        f"https://github.com/{owner}/{repo}/blob/{branch_url}"
        if owner and repo and branch_url else None
    )

    parts: list[str] = []
    total = sum(len(v) for v in assets.values())
    if total == 0:
        return None

    if assets["images"]:
        rows = []
        # Cap at 12 to avoid PR body bloat; typical changes have fewer than 5.
        for img in assets["images"][:12]:
            url = f"{raw_base}/{_url_quote_path(img)}" if raw_base else img
            rows.append(
                f'<a href="{escape(url, quote=True)}"><img src="{escape(url, quote=True)}" '
                f'alt="{escape(Path(img).name, quote=True)}" width="240"></a>'
                f'<br><sub><code>{escape(img)}</code></sub>'
            )
        more = ""
        if len(assets["images"]) > 12:
            more = f"\n\n_+{len(assets['images']) - 12} more image(s) not shown_"
        caveat = "_Images render once the branch is pushed to origin; private repos may require GitHub auth._"
        parts.append(f"### Images ({len(assets['images'])})\n\n{caveat}\n\n" + " &nbsp; ".join(rows) + more)

    if assets["videos"]:
        rows = []
        for v in assets["videos"]:
            url = (
                f"https://github.com/{owner}/{repo}/raw/{branch_url}/{_url_quote_path(v)}"
                if owner and repo and branch_url else v
            )
            rows.append(f"- [`{Path(v).name}`]({url}) — `{v}`")
        parts.append(
            f"### Videos ({len(assets['videos'])})\n\n"
            "Click to open the inline player on GitHub.\n\n" + "\n".join(rows)
        )

    if assets["blog"]:
        # Cap at 4; longer lists are noted below instead of expanding the body.
        for b in assets["blog"][:4]:
            p = repo_root / b
            if not p.exists():
                continue
            try:
                text = p.read_text(errors="replace")
            except OSError:
                continue
            fm, body = parse_frontmatter(text)
            title = fm.get("title", Path(b).stem)
            desc = fm.get("description") or fm.get("summary") or ""
            hero = (
                fm.get("hero") or fm.get("image")
                or fm.get("ogImage") or fm.get("heroImage")
            )
            block = [f"### Blog: {title}", "", f"`{b}`"]
            if hero and raw_base:
                hero_url = (
                    hero if hero.startswith("http")
                    else f"{raw_base}/{_url_quote_path(hero.lstrip('/'))}"
                )
                block.append("")
                block.append(f'<img src="{escape(hero_url, quote=True)}" alt="hero" width="480">')
            if desc:
                block.append("")
                block.append(f"> {desc}")
            block.append("")
            block.append(first_words(body, 80))
            parts.append("\n".join(block))
        if len(assets["blog"]) > 4:
            parts.append(f"_+{len(assets['blog']) - 4} more blog file(s) not shown_")

    if assets["landing"]:
        rows = []
        for f in assets["landing"][:10]:
            url = f"{blob_base}/{_url_quote_path(f)}" if blob_base else f
            rows.append(f"- [`{f}`]({url})")
        if len(assets["landing"]) > 10:
            rows.append(f"_+{len(assets['landing']) - 10} more landing page(s) not shown_")
        parts.append(
            f"### Landing pages ({len(assets['landing'])})\n\n"
            "Verify on the deploy preview before merging.\n\n" + "\n".join(rows)
        )

    if assets["copy"]:
        rows = []
        for f in assets["copy"][:4]:
            d = subprocess.run(
                ["git", "diff", f"origin/{base}...HEAD", "--unified=2", "--", f],
                capture_output=True, text=True,
            ).stdout
            hunk_lines = [
                ln for ln in d.splitlines()
                if ln.startswith(("@@", "+", "-")) and not ln.startswith(("+++", "---"))
            ]
            if not hunk_lines:
                continue
            shown = "\n".join(hunk_lines[:40])
            more = "" if len(hunk_lines) <= 40 else f"\n… (+{len(hunk_lines) - 40} more lines)"
            rows.append(
                f"<details><summary><code>{f}</code></summary>\n\n"
                f"```diff\n{shown}{more}\n```\n\n</details>"
            )
        if rows:
            more = ""
            if len(assets["copy"]) > 4:
                more = f"\n\n_+{len(assets['copy']) - 4} more copy file(s) not shown_"
            parts.append(f"### Copy ({len(assets['copy'])})\n\n" + "\n\n".join(rows) + more)

    if not parts:
        return None

    return (
        "<details>\n"
        f"<summary>📎 Asset previews — {total} file(s) (click to expand)</summary>\n\n"
        + "\n\n".join(parts)
        + "\n\n</details>\n"
    )


def inject_asset_previews(passthrough: list[str], previews: str, tmp_dir: Path) -> tuple[list[str], bool]:
    """Prepend `previews` to whatever --body / --body-file is in passthrough.

    Returns (new_passthrough, injected). When neither flag is present (gh would
    open $EDITOR), returns (passthrough, False) — caller writes the previews to
    a sibling file and tells the user where it is.
    """
    out = list(passthrough)
    i = 0
    while i < len(out):
        a = out[i]
        if a == "--body" and i + 1 < len(out):
            out[i + 1] = previews + "\n" + out[i + 1]
            return out, True
        if a.startswith("--body="):
            out[i] = "--body=" + previews + "\n" + a[len("--body="):]
            return out, True
        if a == "--body-file" and i + 1 < len(out):
            src = Path(out[i + 1])
            if not src.exists():
                print(f"[pr-gate] WARN: --body-file {src} does not exist; skipping preview injection", file=sys.stderr)
                return out, False
            try:
                original = src.read_text()
            except OSError as e:
                print(
                    f"[pr-gate] WARN: could not read {src} for asset preview injection ({e}); skipping",
                    file=sys.stderr,
                )
                return out, False
            tmp_dir.mkdir(parents=True, exist_ok=True)
            tmp = tmp_dir / f"body-with-previews-{src.name}"
            tmp.write_text(previews + "\n" + original)
            out[i + 1] = str(tmp)
            return out, True
        if a.startswith("--body-file="):
            src = Path(a[len("--body-file="):])
            if not src.exists():
                print(f"[pr-gate] WARN: --body-file {src} does not exist; skipping preview injection", file=sys.stderr)
                return out, False
            try:
                original = src.read_text()
            except OSError as e:
                print(
                    f"[pr-gate] WARN: could not read {src} for asset preview injection ({e}); skipping",
                    file=sys.stderr,
                )
                return out, False
            tmp_dir.mkdir(parents=True, exist_ok=True)
            tmp = tmp_dir / f"body-with-previews-{src.name}"
            tmp.write_text(previews + "\n" + original)
            out[i] = "--body-file=" + str(tmp)
            return out, True
        i += 1
    return out, False


def write_gate_review(repo_root: Path, sections: list[tuple[str, str, list[str]]]) -> Path:
    """Write `.pr-gate-review.md` summarizing all findings."""
    out_path = repo_root / ".pr-gate-review.md"
    full_path = repo_root / FULL_REVIEW_FILE
    today = dt.datetime.now().isoformat(timespec="seconds")
    lines = [
        f"# PR Gate Review — {today}",
        "",
        "Pre-flight check before opening this PR. The gate refuses to open until HIGH findings are addressed (or `--force` overrides).",
        "",
    ]
    full_lines = [f"# PR Gate Full Review — {today}", ""]
    for section_name, full_text, high_lines in sections:
        lines.append(f"## {section_name}")
        lines.append("")
        full_lines.append(f"## {section_name}")
        full_lines.append("")
        full_lines.append(full_text)
        full_lines.append("")
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
        detail = full_text[:5000]
        if len(full_text) > 5000:
            detail += f"\n\n...[truncated - {len(full_text) - 5000} chars not shown; full review: {FULL_REVIEW_FILE}]"
        lines.append(detail)
        lines.append("")
        lines.append("</details>")
        lines.append("")
    full_path.write_text("\n".join(full_lines))
    out_path.write_text("\n".join(lines))
    return out_path


OPEN_PR_CAP_DEFAULT = 2
OPEN_PR_CAP_URGENT = 3
OPEN_PR_CAP_OWNER = "Epoch-ML"
# Repos exempt from the open-PR cap. The cap exists to throttle Idan's review
# queue on the main `Epoch-ML/zerg` monorepo. Solo / Matt-owned standalone
# repos under Epoch-ML/* that Idan doesn't review against the same cadence
# should not count. 2026-05-29: zerg-gg added per Matt — it's a separate small
# repo (URL shortener) outside the monorepo review queue.
OPEN_PR_CAP_EXEMPT_REPOS = frozenset({
    "Epoch-ML/zerg-gg",
})

# Patterns that mark AI coauthors in commit messages or PR bodies.
# Conservative: only matches lines that explicitly call out an LLM/agent.
AI_COAUTHOR_PATTERNS = (
    re.compile(r"^\s*Co-?[Aa]uthored-?[Bb]y:.*<noreply@anthropic\.com>\s*$", re.M),
    re.compile(r"^\s*Co-?[Aa]uthored-?[Bb]y:.*\bclaude-code\b.*$", re.M | re.I),
    re.compile(r"^\s*Co-?[Aa]uthored-?[Bb]y:.*\bClaude\b.*@anthropic[.-][^>\s]+.*$", re.M | re.I),
    re.compile(r"^\s*🤖\s*Generated with .*Claude.*$", re.M),
    re.compile(r"^\s*[Gg]enerated\s+(?:by|with)\s+.*\bClaude\b.*$", re.M),
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
            capture_output=True, text=True, timeout=10, env=gh_env(),
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    try:
        data = json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return None
    if (data.get("state") or "").upper() == "OPEN":
        return data.get("url")
    return None


def count_open_prs(exclude_url: str | None = None) -> tuple[int, list[dict]]:
    """Return (count, [{number,title,url,repo}, ...]) of Matt's open Epoch-ML PRs.

    `exclude_url` skips the in-flight PR for this branch so re-pushing to an
    existing PR doesn't trip the cap.

    The cap is scoped to Idan-reviewed Epoch-ML/* PRs, not personal or solo
    repos. If gh is missing or the call fails, returns (0, []) and logs to
    stderr; the cap is a soft anti-clutter rule, not a correctness invariant.
    """
    try:
        r = subprocess.run(
            ["gh", "search", "prs", "--author=@me", "--state=open",
             "--json", "number,title,url,repository", "--limit", "50"],
            capture_output=True, text=True, timeout=20, env=gh_env(),
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"[pr-gate] WARN: could not query open PRs ({e}); skipping cap", file=sys.stderr)
        return 0, []
    if r.returncode != 0:
        print(f"[pr-gate] WARN: gh search prs failed ({r.stderr.strip()[:200]}); skipping cap",
              file=sys.stderr)
        return 0, []
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
        repo_name = repo.get("nameWithOwner") or repo.get("name") or "?"
        if not repo_name.lower().startswith(f"{OPEN_PR_CAP_OWNER.lower()}/"):
            continue
        if repo_name in OPEN_PR_CAP_EXEMPT_REPOS:
            continue
        out.append({
            "number": pr.get("number"),
            "title": pr.get("title", ""),
            "url": url,
            "repo": repo_name,
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
                except OSError as e:
                    print(
                        f"[pr-gate] WARN: could not read {src} for AI-coauthor scrub ({e}); lines may pass through",
                        file=sys.stderr,
                    )
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
                except OSError as e:
                    print(
                        f"[pr-gate] WARN: could not read {src} for AI-coauthor scrub ({e}); lines may pass through",
                        file=sys.stderr,
                    )
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


def passthrough_body_text(passthrough: list[str]) -> str | None:
    i = 0
    while i < len(passthrough):
        arg = passthrough[i]
        if arg == "--body" and i + 1 < len(passthrough):
            return passthrough[i + 1]
        if arg.startswith("--body="):
            return arg[len("--body="):]
        if arg == "--body-file" and i + 1 < len(passthrough):
            try:
                return Path(passthrough[i + 1]).read_text()
            except OSError as e:
                return f"[unreadable --body-file: {e}]"
        if arg.startswith("--body-file="):
            try:
                return Path(arg[len("--body-file="):]).read_text()
            except OSError as e:
                return f"[unreadable --body-file: {e}]"
        i += 1
    return None


def prior_review_blocker(passthrough: list[str]) -> str | None:
    body = passthrough_body_text(passthrough)
    if body and PRIOR_REVIEW_RE.search(body):
        return None
    return (
        "[pr-gate] BLOCKED — PR body is missing a prior-review carry-forward section.\n\n"
        "Add:\n\n"
        "## Prior-review items carried forward\n\n"
        "| # | Finding | Source PR | Resolution |\n"
        "|---|---------|-----------|------------|\n"
        "| B1 | ... | #292 | addressed in commit abc |\n\n"
        "If this PR genuinely has no overlapping prior fakeidan-reviewed surface, rerun with "
        "`--no-prior-review` (logged)."
    )


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

    # Soft session-claims check (Pillar 5): WARN if another live Claude
    # session has claimed this repo. Never changes pass/fail.
    try:
        _sc_dir = str(Path.home() / ".config" / "zerg")
        if _sc_dir not in sys.path:
            sys.path.insert(0, _sc_dir)
        import session_claims as _sc  # type: ignore  # noqa: E402
        _code, _ev = _sc.check(str(repo_root))
        if _code == 2 and _ev:
            _note = f" — {_ev['note']}" if _ev.get("note") else ""
            print(
                f"[pr-gate] ⚠ {repo_root} claimed by session {_sc.short_session(_ev)} "
                f"{_sc.age_str(_ev)} ago{_note} — soft lock, coordinate before editing "
                f"(zclaim list)",
                file=sys.stderr,
            )
    except Exception:  # noqa: BLE001 — warn-only, never break the gate
        pass

    print(f"[pr-gate] base=origin/{base}", file=sys.stderr)

    if not verify_github_identity(args):
        return 1

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
        if open_count >= OPEN_PR_CAP_DEFAULT:
            log_override(f"urgent-backlog-{open_count}", passthrough)
            print(f"[pr-gate] --urgent: cap raised to {cap} (logged).", file=sys.stderr)
        else:
            print(f"[pr-gate] --urgent: cap raised to {cap} (no override needed at backlog={open_count}).", file=sys.stderr)

    fetch_warning = refresh_base_ref(base)
    if fetch_warning:
        print(
            f"[pr-gate] WARN: could not refresh origin/{base} before stale-base check "
            f"({fetch_warning}); using existing local ref "
            f"(stale-base check may miss commits landed on {base} since last fetch).",
            file=sys.stderr,
        )

    stale_message = stale_base_blocker(base)
    if stale_message:
        print(f"[pr-gate] BLOCKED — {stale_message}", file=sys.stderr)
        return 1

    files, files_error = changed_files(base)
    if files_error:
        print(f"[pr-gate] BLOCKED — unable to list changed files vs origin/{base}: {files_error}", file=sys.stderr)
        return 1
    if not files:
        print(f"[pr-gate] no changes vs origin/{base} — nothing to gate", file=sys.stderr)
        if not args.dry_run:
            with tempfile.TemporaryDirectory() as scrub_tmp:
                scrubbed, n = scrub_passthrough_body(passthrough, Path(scrub_tmp))
                if n:
                    print(f"[pr-gate] stripped {n} AI-coauthor line(s) from PR body", file=sys.stderr)
                if args.no_prior_review:
                    log_override("no-prior-review-section", scrubbed)
                    print("[pr-gate] --no-prior-review: skipping prior-review section check (logged).", file=sys.stderr)
                else:
                    prior_blocker = prior_review_blocker(scrubbed)
                    if prior_blocker:
                        print(prior_blocker, file=sys.stderr)
                        return 1
                return subprocess.call(["gh", "pr", "create"] + scrubbed, env=gh_env())
        return 0

    classification = classify(files)
    print(f"[pr-gate] {len(files)} changed files: code={len(classification['code'])} prose={len(classification['prose'])} launch={len(classification['launch'])}", file=sys.stderr)

    # Workflow-only block — Zerg product repos ship product or content, not
    # personal workflow. See feedback_prs_for_products_not_workflow.md.
    repo_owner, _ = repo_owner_name()
    if is_zerg_product_repo(repo_owner) and is_workflow_only_diff(files):
        if not args.force:
            print(
                "\n[pr-gate] BLOCKED — diff is 100% personal-workflow paths "
                f"(.claude/, .codex/, .vscode/, .idea/, .devcontainer/, "
                f".editorconfig, infra/docker-compose*.yml).",
                file=sys.stderr,
            )
            print(
                "[pr-gate] Zerg product repos ship product or content, not "
                "personal-workflow changes. See feedback_prs_for_products_not_workflow.md.",
                file=sys.stderr,
            )
            print("[pr-gate] Files in this diff:", file=sys.stderr)
            for f in files:
                print(f"  • {f}", file=sys.stderr)
            print(
                "\n[pr-gate] Options:\n"
                "  • Manage this change locally (don't push). Workflow tweaks live in "
                "~/.config/, personal scripts, or local-only branches.\n"
                "  • If this PR genuinely ships product/content alongside workflow files, "
                "include the product/content file in the diff so the gate sees mixed scope.\n"
                "  • Pass --force to override (logged).",
                file=sys.stderr,
            )
            return 1
        log_override(f"force-workflow-only-diff-{len(files)}-files", passthrough)
        print(
            f"[pr-gate] FORCED past workflow-only-diff block ({len(files)} files) — logged.",
            file=sys.stderr,
        )

    _, commit_coauthors = scrub_ai_coauthors(commit_messages(base))
    if commit_coauthors and not args.force:
        print(
            f"[pr-gate] BLOCKED — found {commit_coauthors} AI-coauthor/generated-with-Claude "
            "line(s) in commit messages.",
            file=sys.stderr,
        )
        print(
            f"[pr-gate] Reword commits before opening the PR: `git rebase -i origin/{base}`.",
            file=sys.stderr,
        )
        print("[pr-gate] Override with --force (logged).", file=sys.stderr)
        return 1
    if commit_coauthors and args.force:
        log_override(f"force-ai-coauthor-commit-lines-{commit_coauthors}", passthrough)
        print(
            f"[pr-gate] FORCED past {commit_coauthors} AI-coauthor line(s) in commit messages (logged).",
            file=sys.stderr,
        )

    # Auto-asset-preview block: scan diff for content/blog/copy/video/landing/image
    # changes and build a collapsible markdown block that gets prepended to the
    # PR body. Suppressed by --no-asset-previews; otherwise opt-out via the diff
    # itself (no assets → no block).
    asset_preview_md: str | None = None
    if not args.no_asset_previews:
        status = file_status_map(base)
        assets = classify_assets(files, status)
        n_assets = sum(len(v) for v in assets.values())
        if n_assets > 0:
            owner, repo_name = repo_owner_name()
            branch = current_branch_name()
            asset_preview_md = build_asset_previews(
                repo_root, base, assets, owner, repo_name, branch,
            )
            if asset_preview_md:
                print(
                    f"[pr-gate] asset previews: images={len(assets['images'])} "
                    f"videos={len(assets['videos'])} blog={len(assets['blog'])} "
                    f"landing={len(assets['landing'])} copy={len(assets['copy'])}",
                    file=sys.stderr,
                )
                preview_path = repo_root / ASSET_PREVIEW_FILE
                preview_path.write_text(asset_preview_md)
                print(f"[pr-gate] asset preview block written to {preview_path}", file=sys.stderr)

    # Launch-premise gate: hard-block PRs that publish new launch content without a fresh confirm token.
    # Runs FIRST, fail-closed, before fake-skill reviews. Cheap (no API calls).
    # Override path: --force (still logs).
    if launch_premise_missing(classification):
        print(f"[pr-gate] BLOCKED — launch files touched but launch-premise gate is missing at {LAUNCH_PREMISE}.", file=sys.stderr)
        if not args.force:
            return 1
        log_override("force-launch-premise-missing", passthrough)
        print("[pr-gate] FORCED past missing launch-premise gate (logged)", file=sys.stderr)
    elif LAUNCH_PREMISE.exists():
        print("[pr-gate] running launch-premise gate…", file=sys.stderr)
        premise = subprocess.run(
            ["python3", str(LAUNCH_PREMISE), "--base", base],
            capture_output=True, text=True,
        )
        premise_rc = premise.returncode
        if premise_rc != 0 and not args.force:
            print("[pr-gate] BLOCKED by launch-premise gate.", file=sys.stderr)
            detail = "\n".join(part for part in (premise.stdout.strip(), premise.stderr.strip()) if part)
            if detail:
                print(detail, file=sys.stderr)
            print("[pr-gate] Override with --force (logged).", file=sys.stderr)
            return 1
        if premise_rc != 0 and args.force:
            log_override("force-launch-premise", passthrough)
            print("[pr-gate] FORCED past launch-premise gate (logged)", file=sys.stderr)

    sections = []

    # Hypothesis check — Step 4 of plans/what-are-gaps-in-velvety-ripple.md.
    # HIGH finding when the PR touches loop-relevant infrastructure but lacks a
    # measurable Hypothesis line in the body. Soft: --force overrides like
    # every other HIGH path. Cheap (no API).
    try:
        sys.path.insert(0, str(SKILL_DIR))
        from hypothesis_check import check as _hyp_check, _read_body as _hyp_read_body
        _hyp_body = _hyp_read_body(
            next((v for k, v in zip(passthrough, passthrough[1:]) if k == "--body"), None)
            or next((a[len("--body="):] for a in passthrough if a.startswith("--body=")), None),
            next((v for k, v in zip(passthrough, passthrough[1:]) if k == "--body-file"), None)
            or next((a[len("--body-file="):] for a in passthrough if a.startswith("--body-file=")), None),
        )
        _hyp_needed, _hyp_passed, _hyp_finding = _hyp_check(files, _hyp_body)
        if _hyp_needed and not _hyp_passed:
            print(f"[pr-gate] hypothesis-check HIGH finding (override with --force)", file=sys.stderr)
            sections.append(("hypothesis-check", _hyp_finding, [_hyp_finding.splitlines()[0]]))
        elif _hyp_needed:
            print(f"[pr-gate] hypothesis-check PASS", file=sys.stderr)
    except Exception as e:
        print(f"[pr-gate] hypothesis-check skipped (error: {e})", file=sys.stderr)

    if args.fast:
        # Fast-path: identity + cap + AI-coauthor + launch-premise + asset previews
        # have already run above. Skip the LLM reviews — they're the part that
        # makes the pre-push hook long enough for GitHub to drop the SSH
        # connection mid-hook. Full LLM gate runs at `gh pr create` time and in
        # the slower local `gh pr create` wrapper path.
        print("[pr-gate] --fast: skipping LLM reviews (qa-gate/fakeidan, copyedit, launch-announcement)", file=sys.stderr)
        gate_review = None
    else:
        with tempfile.TemporaryDirectory() as tmpd:
            out_dir = Path(tmpd)

            # --- Phase A cache setup ---
            # 30-min cache keyed on (branch, diff_hash, subskill[, mode]). On
            # cache hit we reuse the prior review_text and skip the subprocess
            # call entirely. has_high_findings() still runs against the cached
            # text so HIGH gating stays intact across cached rounds.
            sys.path.insert(0, str(SKILL_DIR))
            try:
                import cache as gate_cache  # type: ignore
            except ImportError:
                gate_cache = None  # type: ignore
            cache_branch = current_branch_name() or "HEAD"
            review_diff_for_hash = full_diff(base)
            diff_hash = (
                gate_cache.diff_hash_of(review_diff_for_hash)
                if (gate_cache and review_diff_for_hash) else None
            )
            use_cache = not args.no_cache and gate_cache is not None and diff_hash is not None
            if args.no_cache:
                print("[pr-gate] --no-cache: cache bypassed; all sub-skills run fresh", file=sys.stderr)
            elif use_cache:
                print(f"[pr-gate] cache key: branch={cache_branch} diff_hash={diff_hash}", file=sys.stderr)

            # Run qa-gate/fakeidan
            if not args.skip_fakeidan and QA_GATE.exists():
                review_modes = fakeidan_modes(args, classification)
                review_diff = review_diff_for_hash or full_diff(base)
                for review_mode in review_modes:
                    cached = gate_cache.get(cache_branch, diff_hash, "fakeidan", review_mode) if use_cache else None
                    if cached is not None:
                        print(f"[pr-gate] [cache-hit] qa-gate/fakeidan ({review_mode}) — reusing prior review", file=sys.stderr)
                        idan_text = cached
                    else:
                        print(f"[pr-gate] running qa-gate/fakeidan ({review_mode})…", file=sys.stderr)
                        _, idan_text = run_fakeidan(
                            base,
                            classification,
                            out_dir / f"fakeidan-{review_mode}",
                            mode=review_mode,
                            diff_text=review_diff,
                        )
                        if use_cache and not is_tool_failure_text(idan_text):
                            gate_cache.put(cache_branch, diff_hash, "fakeidan", idan_text, review_mode)
                        elif use_cache:
                            print(f"[pr-gate] [cache-skip-put] qa-gate/fakeidan ({review_mode}) tool failure — not caching", file=sys.stderr)
                    high, lines = has_high_findings(idan_text)
                    section_name = (
                        f"qa-gate/fakeidan ({review_mode})"
                        if len(review_modes) > 1 else "qa-gate/fakeidan"
                    )
                    sections.append((section_name, idan_text, lines))
            elif not args.skip_fakeidan:
                missing = "(qa-gate runner missing — gate FAIL-CLOSED)"
                high, lines = has_high_findings(missing)
                sections.append(("qa-gate/fakeidan", missing, lines))

            # Run fakematt-copyedit on prose
            if not args.skip_copyedit and classification["prose"] and FAKEMATT_COPYEDIT.exists():
                cached = gate_cache.get(cache_branch, diff_hash, "fakematt-copyedit") if use_cache else None
                if cached is not None:
                    print(f"[pr-gate] [cache-hit] fakematt-copyedit — reusing prior review", file=sys.stderr)
                    copy_text = cached
                else:
                    print(f"[pr-gate] running fakematt-copyedit on {len(classification['prose'])} prose file(s)…", file=sys.stderr)
                    _, copy_text = run_copyedit(classification["prose"], out_dir / "copyedit", repo_root=repo_root)
                    if use_cache and not is_tool_failure_text(copy_text):
                        gate_cache.put(cache_branch, diff_hash, "fakematt-copyedit", copy_text)
                    elif use_cache:
                        print("[pr-gate] [cache-skip-put] fakematt-copyedit tool failure — not caching", file=sys.stderr)
                high, lines = has_high_findings(copy_text)
                sections.append(("fakematt-copyedit", copy_text, lines))

            # Run launch-announcement review on launch posts
            if classification["launch"] and LAUNCH_ANNOUNCEMENT.exists():
                cached = gate_cache.get(cache_branch, diff_hash, "launch-announcement") if use_cache else None
                if cached is not None:
                    print(f"[pr-gate] [cache-hit] launch-announcement — reusing prior review", file=sys.stderr)
                    launch_text = cached
                else:
                    print(f"[pr-gate] running launch-announcement review on {len(classification['launch'])} launch file(s)…", file=sys.stderr)
                    _, launch_text = run_launch_review(classification["launch"], out_dir / "launch", repo_root=repo_root)
                    if use_cache and not is_tool_failure_text(launch_text):
                        gate_cache.put(cache_branch, diff_hash, "launch-announcement", launch_text)
                    elif use_cache:
                        print("[pr-gate] [cache-skip-put] launch-announcement tool failure — not caching", file=sys.stderr)
                high, lines = has_high_findings(launch_text)
                sections.append(("launch-announcement", launch_text, lines))

            # Run cross-model-check (Codex second-opinion on the diff). Phase B:
            # skip when the diff has no code/prose/launch (e.g., pure config),
            # since xmodel's value-add is reasoning about the artifact substance.
            xmodel_skipped_scope = (
                not args.no_cross_model
                and not (classification.get("code") or classification.get("prose") or classification.get("launch"))
            )
            if not args.no_cross_model and not xmodel_skipped_scope and CROSS_MODEL_CHECK.exists():
                xmode = cross_model_mode(classification)
                cached = gate_cache.get(cache_branch, diff_hash, "cross-model", xmode) if use_cache else None
                if cached is not None:
                    print(f"[pr-gate] [cache-hit] cross-model-check ({xmode}) — reusing prior review", file=sys.stderr)
                    xmodel_text = cached
                else:
                    print("[pr-gate] running cross-model-check (codex second-opinion)…", file=sys.stderr)
                    _, xmodel_text = run_cross_model(
                        base, classification, out_dir / "xmodel", repo_root=repo_root,
                    )
                    if use_cache and not is_tool_failure_text(xmodel_text):
                        gate_cache.put(cache_branch, diff_hash, "cross-model", xmodel_text, xmode)
                    elif use_cache:
                        print(f"[pr-gate] [cache-skip-put] cross-model-check ({xmode}) tool failure — not caching", file=sys.stderr)
                high, lines = has_high_findings(xmodel_text)
                sections.append(("cross-model-check [XMODEL]", xmodel_text, lines))
            elif args.no_cross_model:
                print("[pr-gate] --no-cross-model: skipping codex second-opinion (logged)", file=sys.stderr)
                log_override("no-cross-model", passthrough)
            elif xmodel_skipped_scope:
                print("[pr-gate] cross-model-check skipped (diff has no code/prose/launch substance)", file=sys.stderr)

            gate_review = write_gate_review(repo_root, sections)

    total_high = sum(len(lines) for _, _, lines in sections)
    if gate_review is not None:
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
        with tempfile.TemporaryDirectory() as scrub_tmp:
            scrubbed, n = scrub_passthrough_body(passthrough, Path(scrub_tmp))
            if n:
                print(f"[pr-gate] stripped {n} AI-coauthor line(s) from PR body", file=sys.stderr)
            if args.no_prior_review:
                log_override("no-prior-review-section-dry-run", scrubbed)
                print("[pr-gate] --no-prior-review: skipping prior-review section check (logged).", file=sys.stderr)
            else:
                prior_blocker = prior_review_blocker(scrubbed)
                if prior_blocker:
                    print(prior_blocker, file=sys.stderr)
                    return 1
        print("[pr-gate] --dry-run: not opening PR", file=sys.stderr)
        if asset_preview_md:
            print(
                f"[pr-gate] asset preview block ready at {repo_root / ASSET_PREVIEW_FILE} "
                "(would be prepended to --body / --body-file on real run)",
                file=sys.stderr,
            )
        return 0

    print("[pr-gate] gate passed — calling gh pr create", file=sys.stderr)
    with tempfile.TemporaryDirectory() as work_tmp:
        work = Path(work_tmp)
        passthrough_in = passthrough
        if asset_preview_md:
            passthrough_in, injected = inject_asset_previews(
                passthrough_in, asset_preview_md, work / "body-with-previews",
            )
            if injected:
                print("[pr-gate] asset preview block prepended to PR body", file=sys.stderr)
            else:
                print(
                    "[pr-gate] no --body/--body-file to prepend into; "
                    f"editor will open. Paste from {repo_root / ASSET_PREVIEW_FILE} if you want previews.",
                    file=sys.stderr,
                )
        scrubbed, n = scrub_passthrough_body(passthrough_in, work / "scrub")
        if n:
            print(f"[pr-gate] stripped {n} AI-coauthor line(s) from PR body", file=sys.stderr)
        if args.no_prior_review:
            log_override("no-prior-review-section", scrubbed)
            print("[pr-gate] --no-prior-review: skipping prior-review section check (logged).", file=sys.stderr)
        else:
            prior_blocker = prior_review_blocker(scrubbed)
            if prior_blocker:
                print(prior_blocker, file=sys.stderr)
                return 1
        return subprocess.call(["gh", "pr", "create"] + scrubbed, env=gh_env())


if __name__ == "__main__":
    sys.exit(main())
