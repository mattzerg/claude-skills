#!/usr/bin/env python3
"""cross-model-check — ask the OTHER LLM for a second pass on an artifact.

Usage:
    python3 ~/.claude/skills/cross-model-check/run.py <artifact-path> \
        [--mode {code,prose,launch,email,generic}] \
        [--from {claude,codex}] \
        [--primary-review PATH] \
        [--diff REF | --diff-file PATH] \
        [--out-dir DIR] \
        [--timeout SECONDS] \
        [--effort {high,xhigh}] \
        [--repo-root PATH] \
        [--model MODEL]

Exit codes:
    0  cross-check ran, no HIGH findings
    1  usage error
    2  cross-check ran, HIGH findings present (gate-blocking signal)
    3  cross-check skipped (other model unavailable / rate-limited / binary missing)

Writes a markdown finding file to <out-dir>/<artifact-name>.xmodel.<YYYY-MM-DD>.md
(default out-dir: /tmp/xmodel/). Caller (pr-gate, qa-gate, or human) reads HIGH
sections via the existing pr-gate regex.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Tuple

SKILL_DIR = Path(__file__).parent
PROMPTS_DIR = SKILL_DIR / "scripts" / "prompts"
SCRIPTS_DIR = SKILL_DIR / "scripts"

# Allow importing helper modules without packaging gymnastics
sys.path.insert(0, str(SCRIPTS_DIR))
from detect_active_model import active_model, other_model  # noqa: E402
from invoke_codex import invoke_codex  # noqa: E402
from invoke_claude import invoke_claude  # noqa: E402
from check_rate_limit import codex_available  # noqa: E402
from aitr_select import aitr_pick_for_reviewer, record_review_outcome  # noqa: E402

VALID_MODES = ("code", "prose", "launch", "email", "generic")
VALID_FROM = ("claude", "codex")
DEFAULT_OUT_DIR = Path("/tmp/xmodel")
HIGH_HEADER_RE = re.compile(r"^##\s+HIGH\s*$", re.M)
VERDICT_RE = re.compile(r"^\*\*Verdict:\*\*\s*(Concur|Challenge|Mixed)\s*$", re.M | re.I)
# Match pr-gate's convention so huge artifacts/diffs don't blow up the prompt
# or trigger the other model's context-window failure mode silently.
ARTIFACT_CHAR_LIMIT = 60000
DIFF_CHAR_LIMIT = 60000


def _truncate(text: str, limit: int, label: str) -> str:
    if len(text) <= limit:
        return text
    head = text[:limit]
    return f"{head}\n\n<<TRUNCATED — {label} exceeded {limit} chars; reviewed first {limit} only>>"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="cross-model-check — second opinion from the other LLM")
    p.add_argument("artifact", help="Path to the file under review")
    p.add_argument("--mode", choices=VALID_MODES, default="generic")
    p.add_argument("--from", dest="from_", choices=VALID_FROM,
                   help="Which model is invoking (auto-detected from env if omitted)")
    p.add_argument("--primary-review", help="Path to the primary model's prior review (optional)")
    p.add_argument("--diff", help="Git ref to diff against (e.g. origin/main)")
    p.add_argument("--diff-file", help="Pre-computed diff file path")
    p.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    p.add_argument("--timeout", type=int, default=300)
    p.add_argument("--effort", default="high", choices=("high", "xhigh"))
    p.add_argument("--repo-root", help="Repo root for codex -C (default: cwd or detected)")
    p.add_argument("--model", help="Pin Claude model when invoking claude -p (e.g. sonnet, opus). "
                                   "When omitted, aitr picks the reviewer model.")
    p.add_argument("--no-aitr", action="store_true",
                   help="Skip aitr model selection; use reviewer defaults.")
    return p.parse_args()


def resolve_from(arg_from: str | None) -> str:
    if arg_from:
        return arg_from
    detected = active_model()
    if detected == "unknown":
        raise SystemExit(
            "[xmodel] cannot determine active model from env. "
            "Pass --from claude OR --from codex explicitly."
        )
    return detected


def read_artifact(path: Path) -> str:
    if not path.exists():
        raise SystemExit(f"[xmodel] artifact not found: {path}")
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"<binary artifact at {path} — not previewed; reviewer received path only>"
    return _truncate(raw, ARTIFACT_CHAR_LIMIT, "artifact")


def read_optional(path_str: str | None) -> str:
    if not path_str:
        return ""
    p = Path(path_str)
    if not p.exists():
        return f"<file not found: {p}>"
    raw = p.read_text(encoding="utf-8", errors="replace")
    return _truncate(raw, ARTIFACT_CHAR_LIMIT, f"context file {p.name}")


def compute_diff(ref: str | None, repo_root: Path) -> str:
    if not ref:
        return ""
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "diff", f"{ref}...HEAD"],
            capture_output=True, text=True, timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return f"<git diff failed: {e}>"
    if proc.returncode != 0:
        return f"<git diff returned {proc.returncode}: {proc.stderr.strip()}>"
    return _truncate(proc.stdout, DIFF_CHAR_LIMIT, "diff")


def detect_repo_root(start: Path) -> Path:
    try:
        proc = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10,
        )
        if proc.returncode == 0:
            return Path(proc.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return start


def build_prompt(mode: str, primary: str, reviewer: str, *,
                 artifact: str, diff: str, primary_review: str) -> str:
    template_path = PROMPTS_DIR / f"{mode}.md"
    if not template_path.exists():
        template_path = PROMPTS_DIR / "generic.md"
    template = template_path.read_text(encoding="utf-8")
    return (
        template
        .replace("{reviewer_model}", reviewer.capitalize())
        .replace("{primary_model}", primary.capitalize())
        .replace("{artifact}", artifact)
        .replace("{diff}", diff or "<no diff supplied>")
        .replace("{primary_review}", primary_review or "<no prior review supplied>")
    )


def has_high_findings(text: str) -> Tuple[bool, list[str]]:
    """Return (has_high, list_of_high_bullet_lines).

    We look for a `## HIGH` header followed by bullet lines until the next
    `## ` header. Empty HIGH sections (header followed by next header or
    only blank lines) do NOT count as findings.
    """
    if not HIGH_HEADER_RE.search(text):
        return (False, [])
    lines = text.splitlines()
    in_high = False
    found: list[str] = []
    for line in lines:
        if HIGH_HEADER_RE.match(line):
            in_high = True
            continue
        if in_high and line.startswith("## "):
            break
        if in_high:
            stripped = line.strip()
            if stripped.startswith("- ") or stripped.startswith("* "):
                # Skip empty bullets and placeholder dashes
                content = stripped[2:].strip()
                if content and content not in ("...", "none", "n/a", "N/A"):
                    found.append(stripped)
    return (bool(found), found)


def extract_verdict(text: str) -> str:
    m = VERDICT_RE.search(text)
    return m.group(1).title() if m else "Unknown"


def write_review(out_dir: Path, artifact_name: str, *,
                 reviewer: str, primary: str, mode: str,
                 model_output: str, status: str,
                 model_selection: str = "") -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    out_path = out_dir / f"{artifact_name}.xmodel.{today}.md"
    verdict = extract_verdict(model_output) if status == "ok" else "Unknown"
    selection_line = f"**Model selection:** {model_selection}\n" if model_selection else ""
    body = (
        f"# Cross-Model Check — {artifact_name}\n\n"
        f"**Reviewer:** {reviewer}\n"
        f"**Primary author/model:** {primary}\n"
        f"**Mode:** {mode}\n"
        f"**Date:** {today}\n"
        f"**Verdict:** {verdict}\n"
        f"**Status:** {status}\n"
        f"{selection_line}\n"
        "---\n\n"
        f"{model_output}\n"
    )
    out_path.write_text(body, encoding="utf-8")
    return out_path


def skip_review(out_dir: Path, artifact_name: str, *, reviewer: str, primary: str,
                mode: str, reason: str) -> Path:
    """Write an informational skip-record. Returns the path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    out_path = out_dir / f"{artifact_name}.xmodel.{today}.md"
    body = (
        f"# Cross-Model Check — {artifact_name}\n\n"
        f"**Reviewer:** {reviewer}\n"
        f"**Primary author/model:** {primary}\n"
        f"**Mode:** {mode}\n"
        f"**Date:** {today}\n"
        f"**Verdict:** Skipped\n"
        f"**Status:** skipped — {reason}\n\n"
        "## HIGH\n\n"
        "## MEDIUM\n\n"
        "## LOW\n\n"
        f"## Notes\n- Cross-model check skipped: {reason}\n"
    )
    out_path.write_text(body, encoding="utf-8")
    return out_path


def main() -> int:
    args = parse_args()
    try:
        primary = resolve_from(args.from_)
    except SystemExit as e:
        print(str(e), file=sys.stderr)
        return 1
    reviewer = other_model(primary)

    artifact_path = Path(args.artifact).expanduser().resolve()
    artifact_name = artifact_path.name
    artifact_text = read_artifact(artifact_path)
    primary_review = read_optional(args.primary_review)
    repo_root = Path(args.repo_root).expanduser().resolve() if args.repo_root else detect_repo_root(artifact_path.parent)

    if args.diff_file:
        diff_text = read_optional(args.diff_file)
    else:
        diff_text = compute_diff(args.diff, repo_root)

    out_dir = Path(args.out_dir).expanduser()

    # Pre-flight: is the OTHER model usable?
    if reviewer == "codex":
        ok, reason = codex_available()
        if not ok:
            out_path = skip_review(out_dir, artifact_name, reviewer=reviewer,
                                   primary=primary, mode=args.mode, reason=reason)
            print(f"[xmodel] skipped — {reason}", file=sys.stderr)
            print(str(out_path))
            return 3
    elif reviewer == "claude":
        # invoke_claude.find_claude_bin handles missing-binary inline; no pre-flight here
        pass

    # Model selection: explicit --model wins; otherwise ask aitr which model the
    # reviewer should use. aitr failures never block the cross-check — they are
    # recorded loudly in the review header instead.
    picked_model = args.model
    picked_effort = args.effort
    aitr_decision_id = None  # set only when an aitr pick is actually APPLIED
    if args.model:
        model_selection = f"manual --model {args.model}"
    elif args.no_aitr:
        model_selection = "aitr disabled via --no-aitr — reviewer default"
    else:
        aitr_model, aitr_effort, aitr_note, aitr_did = aitr_pick_for_reviewer(
            args.mode, reviewer, len(artifact_text) + len(diff_text),
        )
        model_selection = aitr_note
        print(f"[xmodel] model selection: {aitr_note}", file=sys.stderr)
        if aitr_model:
            picked_model = aitr_model
            aitr_decision_id = aitr_did
        # Only let aitr raise effort from the default; an explicit --effort xhigh stays.
        if aitr_effort and args.effort == "high":
            picked_effort = aitr_effort
            aitr_decision_id = aitr_did

    prompt = build_prompt(args.mode, primary=primary, reviewer=reviewer,
                          artifact=artifact_text, diff=diff_text,
                          primary_review=primary_review)

    if reviewer == "codex":
        text, status = invoke_codex(prompt, repo_root=repo_root,
                                    timeout=args.timeout, effort=picked_effort)
    elif reviewer == "claude":
        text, status = invoke_claude(prompt, timeout=args.timeout,
                                     model=picked_model, cwd=repo_root)
    else:
        print(f"[xmodel] unsupported reviewer: {reviewer}", file=sys.stderr)
        return 1

    if status in ("missing-binary", "timeout"):
        # timeout reflects on the picked model (too slow for the task) — record it.
        # missing-binary is environmental, not the model's fault — record nothing.
        if status == "timeout":
            record_review_outcome(aitr_decision_id, "bad",
                                  note=f"reviewer timed out ({args.mode}, {args.timeout}s)")
        out_path = skip_review(out_dir, artifact_name, reviewer=reviewer,
                               primary=primary, mode=args.mode, reason=f"{status}: {text}")
        print(f"[xmodel] skipped — {status}", file=sys.stderr)
        print(str(out_path))
        return 3

    if status == "error":
        record_review_outcome(aitr_decision_id, "bad",
                              note=f"reviewer errored ({args.mode}): {text[:120]}")
        out_path = skip_review(out_dir, artifact_name, reviewer=reviewer,
                               primary=primary, mode=args.mode, reason=f"error: {text}")
        print(f"[xmodel] errored — {text[:200]}", file=sys.stderr)
        print(str(out_path))
        return 3

    out_path = write_review(out_dir, artifact_name, reviewer=reviewer,
                            primary=primary, mode=args.mode,
                            model_output=text, status=status,
                            model_selection=model_selection)

    has_high, highs = has_high_findings(text)

    # Close the routing loop: the picked reviewer delivered a usable review.
    # (HIGH findings are the reviewer doing its job, not a bad pick.)
    usage = getattr(invoke_claude, "last_usage", None) if reviewer == "claude" else None
    record_review_outcome(
        aitr_decision_id, "good",
        note=f"review delivered ({args.mode}, verdict={extract_verdict(text)}, HIGH={len(highs)})",
        input_tokens=(usage or {}).get("input_tokens"),
        output_tokens=(usage or {}).get("output_tokens"),
    )

    print(f"[xmodel] {reviewer} reviewed {artifact_name} ({args.mode}) — verdict={extract_verdict(text)}, HIGH={len(highs)}", file=sys.stderr)
    print(f"[xmodel] review: {out_path}", file=sys.stderr)
    print(str(out_path))

    return 2 if has_high else 0


if __name__ == "__main__":
    sys.exit(main())
