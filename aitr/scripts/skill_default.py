"""skill_default — aitr-backed model defaulting for script-driven skills.

Skills with a `--model` flag import this to resolve their default:

    sys.path.insert(0, str(Path.home() / ".claude" / "skills" / "aitr" / "scripts"))
    try:
        from skill_default import aitr_model_or
    except ImportError:
        def aitr_model_or(fallback, **kwargs):
            return fallback

    # argparse: change default to None so "explicit --model" is distinguishable
    p.add_argument("--model", default=None)
    ...
    if args.model is None:
        args.model = aitr_model_or(
            DEFAULT_MODEL,
            task_kind="prose-review",
            caller="fakematt-copyedit",
            quality_floor="high-stakes",
        )

Behavior: explicit --model wins (never calls aitr) > aitr pick > fallback (loud).
Returned values are claude CLI model names (e.g. "claude-opus-4-8"), mapped from
aitr's `anthropic__<name>` IDs. aitr failures never raise — the fallback is
returned with a loud stderr warning.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

AITR_PICK = Path(__file__).resolve().parent / "pick.py"


def detect_billing_mode() -> str:
    """Best-effort billing mode for the CURRENT process.

    "metered" when a per-token Anthropic API key is present in the environment
    (the SDK path callers like competitive-review / fakematt-feedback take when
    keyed) — model choice then saves real dollars. Otherwise "flat": Max-plan
    OAuth / CLI / Codex subscription, where model choice is $0 marginal.

    Note: this is a PROXY. Callers that always use Max-OAuth (max_client) should
    pass billing_mode="flat" explicitly rather than rely on this — a globally-set
    ANTHROPIC_API_KEY would otherwise mislabel them. Use this only in callers
    whose executor actually keys off the same env var.
    """
    return "metered" if os.environ.get("ANTHROPIC_API_KEY") else "flat"


def _to_claude_model_name(aitr_model_id: str) -> Optional[str]:
    """Map aitr model IDs to claude CLI model names.

    anthropic__claude-opus-4-8 → claude-opus-4-8. Non-anthropic IDs → None
    (caller's executor can't reach them)."""
    if aitr_model_id.startswith("anthropic__"):
        return aitr_model_id[len("anthropic__"):]
    return None


def aitr_pick_or(
    fallback: str,
    *,
    task_kind: str,
    caller: str,
    quality_floor: str = "medium",
    artifact_size_tokens: Optional[int] = None,
    modality_required: Optional[str] = None,
    billing_mode: str = "flat",
    timeout: int = 30,
    runner=None,
) -> tuple:
    """Return (picked claude model name, decision_id), or (`fallback`, None) loudly on any failure.

    Always constrains to anthropic-only since callers execute via the claude CLI
    (Max-plan OAuth) — hence `billing_mode` defaults to "flat": model choice here
    saves rate-limit/latency headroom, not dollars. Pass billing_mode="metered"
    from callers that execute on a per-token API key so the weekly report credits
    their dollar savings. `runner` injects a fake subprocess.run for tests.
    """
    run = runner or subprocess.run

    if not AITR_PICK.exists():
        print(f"[aitr] not installed — using fallback model {fallback}", file=sys.stderr)
        return fallback, None

    cmd = [
        sys.executable or "python3", str(AITR_PICK), "pick",
        f"task_kind={task_kind}",
        f"caller={caller}",
        f"quality_floor={quality_floor}",
        f"billing_mode={billing_mode}",
        "provider_constraint=anthropic-only",
        "--format", "json",
    ]
    if artifact_size_tokens is not None:
        cmd.insert(-2, f"artifact_size_tokens={max(int(artifact_size_tokens), 100)}")
    if modality_required:
        cmd.insert(-2, f"modality_required={modality_required}")

    try:
        proc = run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"[aitr] timed out after {timeout}s — using fallback model {fallback} (LOUD)", file=sys.stderr)
        return fallback, None
    except OSError as exc:
        print(f"[aitr] failed to launch ({exc}) — using fallback model {fallback} (LOUD)", file=sys.stderr)
        return fallback, None

    if proc.returncode != 0:
        print(
            f"[aitr] exit {proc.returncode} — using fallback model {fallback} (LOUD: routing not optimized)",
            file=sys.stderr,
        )
        return fallback, None

    try:
        pick = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print(f"[aitr] unparseable output — using fallback model {fallback}", file=sys.stderr)
        return fallback, None

    model_id = pick.get("model", "")
    claude_name = _to_claude_model_name(model_id)
    if not claude_name:
        print(
            f"[aitr] picked non-anthropic model {model_id!r} despite constraint — "
            f"using fallback model {fallback}",
            file=sys.stderr,
        )
        return fallback, None

    reason = pick.get("reason", "")
    decision_id = pick.get("decision_id", "")
    print(f"[aitr] {caller}: {claude_name} ({reason}) [decision: {decision_id}]", file=sys.stderr)
    return claude_name, decision_id


def aitr_model_or(fallback: str, **kwargs) -> str:
    """Backward-compatible wrapper: returns just the model name.
    Use aitr_pick_or when you also need the decision_id (e.g. to record a
    realized-quality outcome against the pick)."""
    return aitr_pick_or(fallback, **kwargs)[0]


def record_outcome(
    decision_id: Optional[str],
    outcome: str,
    *,
    source: str,
    note: Optional[str] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    model_id: Optional[str] = None,
    timeout: int = 15,
    runner=None,
) -> None:
    """Close the routing loop for a prior aitr_pick_or() decision.

    Call after the picked model ran: outcome "good" (delivered), "bad"
    (errored/unusable), or "mixed". When real token counts are known, pass
    them with the aitr model_id (anthropic__…) to also feed the actuals log.
    Best-effort: never raises, no-op when decision_id is None.
    """
    if not decision_id:
        return
    run = runner or subprocess.run
    base = [sys.executable or "python3", str(AITR_PICK)]
    try:
        rq = run(
            [*base, "record-quality", decision_id, outcome,
             "--source", source, *(["--note", note] if note else [])],
            capture_output=True, text=True, timeout=timeout,
        )
        if rq.returncode != 0:
            print(f"[aitr] record-quality failed (exit {rq.returncode}) — non-blocking", file=sys.stderr)
        if model_id and input_tokens is not None and output_tokens is not None:
            ra = run(
                [*base, "record-actuals", decision_id, "--model", model_id,
                 "--input-tokens", str(int(input_tokens)),
                 "--output-tokens", str(int(output_tokens)),
                 "--caller", source],
                capture_output=True, text=True, timeout=timeout,
            )
            if ra.returncode != 0:
                print(f"[aitr] record-actuals failed (exit {ra.returncode}) — non-blocking", file=sys.stderr)
    except (subprocess.TimeoutExpired, OSError) as exc:
        print(f"[aitr] outcome recording failed ({exc}) — non-blocking", file=sys.stderr)
