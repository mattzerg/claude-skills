#!/usr/bin/env python3
"""aitr model selection for cross-model-check.

When `--model` is not explicitly passed, cross-model-check asks aitr
(~/.claude/skills/aitr) which model the REVIEWER should use, based on the
review mode, artifact size, and the reviewer's provider.

Failure posture: aitr is an enhancement, not a gate dependency. Any aitr
failure (missing, timeout, exit 2/3) is recorded LOUDLY in the returned note
(which lands in the review file header + stderr) but never blocks the
cross-check itself. This honors aitr's "never silently default" rule — the
default is taken, but it is not silent.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

AITR_PICK = Path.home() / ".claude" / "skills" / "aitr" / "scripts" / "pick.py"

# cross-model-check --mode → aitr task_kind
MODE_TO_TASK_KIND = {
    "code": "code-review",
    "prose": "prose-review",
    "launch": "prose-review",
    "email": "prose-review",
    "generic": "refute",
}

# aitr model IDs → claude CLI --model values. Aliases preferred over full IDs
# so the account router (zclaude) can still resolve tier-level quota weighting.
AITR_TO_CLAUDE_MODEL = {
    "anthropic__claude-opus-4-8": "opus",
    "anthropic__claude-opus-4-7": "opus",
    "anthropic__claude-sonnet-4-6": "sonnet",
    "anthropic__claude-haiku-4-5": "haiku",
}


def aitr_pick_for_reviewer(
    mode: str,
    reviewer: str,
    artifact_chars: int,
    *,
    timeout: int = 30,
    runner=None,
) -> Tuple[Optional[str], Optional[str], str, Optional[str]]:
    """Ask aitr which model the reviewer should use.

    Returns (claude_model, codex_effort, note, decision_id):
      - claude_model: value for `claude -p --model …` (only set when reviewer=claude)
      - codex_effort: "high" | "xhigh" (only set when reviewer=codex)
      - note: human-readable record of what happened — ALWAYS set
      - decision_id: aitr decision id when a pick was APPLIED (else None) — pass
        to record_review_outcome() after the review so the routing reputation
        loop learns from the result

    Never raises. `runner` injects a fake subprocess.run for tests.
    """
    run = runner or subprocess.run

    if not AITR_PICK.exists():
        return None, None, "aitr not installed — reviewer default model (routing not optimized)", None

    task_kind = MODE_TO_TASK_KIND.get(mode, "refute")
    provider = "anthropic-only" if reviewer == "claude" else "openai-only"
    artifact_tokens = max(artifact_chars // 4, 100)

    cmd = [
        "python3", str(AITR_PICK), "pick",
        f"task_kind={task_kind}",
        "caller=cross-model-check",
        "quality_floor=high-stakes",
        f"artifact_size_tokens={artifact_tokens}",
        "billing_mode=flat",
        f"provider_constraint={provider}",
        "--format", "json",
    ]
    try:
        proc = run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, None, (
            f"aitr timed out after {timeout}s — reviewer default model "
            "(LOUD: routing not optimized)"
        ), None
    except OSError as exc:
        return None, None, f"aitr failed to launch ({exc}) — reviewer default model (LOUD)", None

    if proc.returncode == 3:
        return None, None, (
            "aitr exit 3: catalog unreachable AND no bundled snapshot — "
            "reviewer default model (LOUD: fix aitr data backend)"
        ), None
    if proc.returncode == 2:
        return None, None, (
            "aitr exit 2: no candidate satisfied hard constraints — "
            "reviewer default model (consider relaxing the signal)"
        ), None
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip()[:200]
        return None, None, f"aitr exit {proc.returncode} ({detail}) — reviewer default model", None

    try:
        pick = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None, None, "aitr returned unparseable JSON — reviewer default model", None

    model_id = pick.get("model", "")
    model_class = pick.get("model_class", "")
    reason = pick.get("reason", "")
    decision_id = pick.get("decision_id", "")

    if reviewer == "claude":
        claude_model = AITR_TO_CLAUDE_MODEL.get(model_id)
        if claude_model is None and model_id.startswith("anthropic__"):
            # Unknown anthropic model — pass the bare model name through;
            # the claude CLI accepts full model IDs too.
            claude_model = model_id.removeprefix("anthropic__")
        if claude_model is None:
            return None, None, (
                f"aitr picked non-anthropic model {model_id!r} for a claude reviewer — "
                "ignoring (constraint mismatch); reviewer default model"
            ), None
        note = f"aitr → {model_id} for {task_kind} ({reason}) [decision: {decision_id}]"
        return claude_model, None, note, (decision_id or None)

    if reviewer == "codex" and not model_id.startswith("openai__"):
        return None, None, (
            f"aitr picked non-openai model {model_id!r} for a codex reviewer — "
            "ignoring (constraint mismatch); reviewer default effort"
        ), None

    # reviewer == codex: codex exec has no per-model pin; aitr's pick maps to
    # reasoning effort. Pro-class picks get xhigh, everything else high.
    effort = "xhigh" if "pro" in model_class.lower() else "high"
    note = f"aitr → {model_id} ⇒ codex effort={effort} for {task_kind} ({reason}) [decision: {decision_id}]"
    return None, effort, note, (decision_id or None)


def record_review_outcome(
    decision_id: Optional[str],
    outcome: str,
    *,
    note: str = "",
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    timeout: int = 15,
    runner=None,
) -> None:
    """Close the routing feedback loop: record how an aitr-picked reviewer
    actually performed (good = review delivered; bad = errored/timed out), and
    real token usage when the executor reported it.

    Best-effort by design: any failure prints to stderr and returns — outcome
    recording must never affect the gate result. No-op when decision_id is None
    (the pick wasn't applied, so the outcome isn't attributable to it).
    """
    if not decision_id:
        return
    run = runner or subprocess.run
    base = ["python3", str(AITR_PICK)]
    try:
        rq = run(
            [*base, "record-quality", decision_id, outcome,
             "--source", "cross-model-check", *(["--note", note] if note else [])],
            capture_output=True, text=True, timeout=timeout,
        )
        if rq.returncode != 0:
            print(f"[xmodel] record-quality failed (exit {rq.returncode}) — non-blocking", file=sys.stderr)
        if input_tokens is not None and output_tokens is not None:
            # record-actuals needs the aitr model id; replay the decision to get it.
            rp = run([*base, "replay", decision_id, "--format", "json"],
                     capture_output=True, text=True, timeout=timeout)
            model_id = ""
            if rp.returncode == 0:
                try:
                    model_id = json.loads(rp.stdout).get("model", "")
                except json.JSONDecodeError:
                    model_id = ""
            if model_id:
                ra = run(
                    [*base, "record-actuals", decision_id, "--model", model_id,
                     "--input-tokens", str(int(input_tokens)),
                     "--output-tokens", str(int(output_tokens)),
                     "--caller", "cross-model-check", "--billing-mode", "flat"],
                    capture_output=True, text=True, timeout=timeout,
                )
                if ra.returncode != 0:
                    print(f"[xmodel] record-actuals failed (exit {ra.returncode}) — non-blocking", file=sys.stderr)
    except (subprocess.TimeoutExpired, OSError) as exc:
        print(f"[xmodel] outcome recording failed ({exc}) — non-blocking", file=sys.stderr)
