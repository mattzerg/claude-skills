"""Hypothesis-line check for pr-gate.

Step 4 of ~/.claude/plans/what-are-gaps-in-velvety-ripple.md.

Posture: HIGH finding when triggered, NOT a hard block on its own. Matt can
override with --force (the existing pr-gate override path).

Trigger: PR touches files in any "memory/skills/agents/hooks" directory:
  - _agent_memory/  (vault)
  - .claude/skills/
  - .claude/agents/
  - .claude/hooks/
  - .codex/memories/
  - .config/zerg/   (when the change touches loop infrastructure)

Required: PR body contains a `Hypothesis:` line in the form:
  Hypothesis: <change> reduces <metric> by <amount> within <window>

The structure is enforced loosely — any line starting with `Hypothesis:` that
mentions a metric (some number or named metric like "corrections",
"fire-rate", "pass-rate") passes the check. Empty / placeholder lines fail.

Why: arxiv 2601.22025 ("When 'Better' Prompts Hurt") showed prompt
"improvements" regressing extraction pass-rate from 100% to ~90%. Rules
deployed without an explicit, measurable hypothesis are vibes. Over time
this builds the empirical ledger the system currently lacks.
"""
from __future__ import annotations
import re
from pathlib import Path
from typing import Iterable


TRIGGER_PATTERNS = [
    re.compile(r"(?:^|/)_agent_memory/"),
    re.compile(r"(?:^|/)\.claude/skills/"),
    re.compile(r"(?:^|/)\.claude/agents/"),
    re.compile(r"(?:^|/)\.claude/hooks/"),
    re.compile(r"(?:^|/)\.codex/memories/"),
    re.compile(r"(?:^|/)\.config/zerg/"),
]

# Hypothesis line must:
#  - start with `Hypothesis:`
#  - contain at least one signal word (reduce / increase / improve / cuts / shrinks)
#    OR a numeric percentage / count
#  - mention something measurable (metric noun)
HYPOTHESIS_LINE = re.compile(r"^\s*Hypothesis:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
METRIC_TOKENS = {
    "reduce", "reduces", "reduced", "reduction",
    "increase", "increases", "increased",
    "improve", "improves", "improved", "improvement",
    "cut", "cuts", "shrink", "shrinks",
    "raise", "raises", "drop", "drops",
    "%", "percent",
    "correction", "corrections",
    "fire-rate", "fire rate", "fires",
    "pass-rate", "pass rate", "pass",
    "graveyard",
    "skill", "agent", "hook",  # weak but helps anchor scope
}
NUMERIC = re.compile(r"\b\d{1,3}\b")
PLACEHOLDER = re.compile(r"<(change|metric|amount|window)>|TBD|TODO|FILL|<.+?>", re.I)


def needs_hypothesis(files: Iterable[str]) -> bool:
    """True iff any changed file matches a hypothesis-required path."""
    for f in files:
        for pat in TRIGGER_PATTERNS:
            if pat.search(f):
                return True
    return False


def parse_hypothesis(body: str) -> tuple[bool, str]:
    """Returns (valid, explanation). The body may contain multiple Hypothesis
    lines; first valid one passes."""
    if not body:
        return False, "no PR body provided"
    matches = HYPOTHESIS_LINE.findall(body)
    if not matches:
        return False, "no `Hypothesis:` line found in PR body"
    for m in matches:
        text = m.strip()
        if not text:
            continue
        if PLACEHOLDER.search(text):
            continue
        # Check for at least one metric token OR a numeric value
        text_lc = text.lower()
        has_metric_token = any(tok in text_lc for tok in METRIC_TOKENS)
        has_numeric = bool(NUMERIC.search(text))
        if has_metric_token or has_numeric:
            return True, text
    return False, f"Hypothesis line(s) found but none contain a measurable metric/numeric anchor (got: {matches[0][:100]!r})"


def check(files: Iterable[str], body: str) -> tuple[bool, str, str]:
    """Main entry. Returns (needed, passed, finding_text)."""
    needed = needs_hypothesis(files)
    if not needed:
        return False, True, ""
    valid, explanation = parse_hypothesis(body)
    if valid:
        return True, True, f"Hypothesis line accepted: {explanation[:200]}"
    # Build a HIGH finding text in the format pr-gate's reviewers use
    triggering = []
    for f in files:
        for pat in TRIGGER_PATTERNS:
            if pat.search(f):
                triggering.append(f)
                break
    return True, False, (
        f"[HIGH] Hypothesis line missing or invalid.\n"
        f"  Why: this PR touches loop-relevant infrastructure ({len(triggering)} file(s)) — "
        f"changes here without a stated, measurable hypothesis create unmeasurable drift.\n"
        f"  Fix: add a line to the PR body in the form:\n"
        f"    Hypothesis: <change> reduces <metric> by <amount> within <window>\n"
        f"  Example:\n"
        f"    Hypothesis: instrumenting correction_capture_inline reduces unmeasurable-rule "
        f"corrections by 50% within 30 days\n"
        f"  Detail: {explanation}\n"
        f"  Override: rerun pr-gate with --force (the override is logged)."
    )


def _read_body(args_body: str | None, args_body_file: str | None) -> str:
    """Helper: read body text from either --body or --body-file."""
    if args_body:
        return args_body
    if args_body_file:
        try:
            return Path(args_body_file).read_text()
        except Exception:
            return ""
    return ""


if __name__ == "__main__":
    import argparse, sys
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", nargs="*", default=[], help="changed file paths")
    ap.add_argument("--body", default=None)
    ap.add_argument("--body-file", default=None)
    args = ap.parse_args()
    body = _read_body(args.body, args.body_file)
    needed, passed, finding = check(args.files, body)
    if not needed:
        print("[hypothesis-check] not required for this diff")
        sys.exit(0)
    if passed:
        print("[hypothesis-check] PASS")
        print(finding)
        sys.exit(0)
    print("[hypothesis-check] HIGH finding:")
    print(finding)
    sys.exit(1)
