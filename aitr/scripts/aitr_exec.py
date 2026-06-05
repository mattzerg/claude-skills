"""aitr_exec — pick + execute + log ACTUAL usage.

Two gaps this closes beyond `skill_default.aitr_model_or` (which only picks a model
name and leaves execution to the caller):

  1. Actual-token logging. The caller runs the model; we capture the real
     input/output token counts from the response and append them to an actuals
     log keyed by decision_id. weekly_report joins this so savings stop being
     pure estimates for metered callers.

  2. Cross-provider execution (DORMANT until activated). When aitr picks a
     non-Anthropic model, route through OpenRouter. Gated on BOTH a resolvable
     API key AND an explicit slug mapping — if either is missing, raise
     CrossProviderUnavailable so the caller falls back to an Anthropic re-pick.
     No fuzzy slug guessing: a wrong slug means wrong model + wrong cost, so the
     mapping must be explicit (config below) and validated against OpenRouter's
     public model list before first use.

Stdlib only (urllib), matching catalog.py. The Anthropic execution path is
injected by the caller (so tests mock it and we don't hard-depend on the SDK
or a specific auth route — Max-OAuth vs API key is the caller's concern).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from quality import record_quality

SKILL_DIR = Path(__file__).resolve().parent
ACTUALS_LOG = Path.home() / ".local" / "state" / "zerg" / "aitr" / "actuals.log"
# Explicit id → OpenRouter slug map. Empty until cross-provider is activated.
# Populate from `aitr_exec.py validate-slugs` (checks OpenRouter's public model
# list) before pointing any live caller at a non-Anthropic model.
SLUG_MAP_PATH = SKILL_DIR.parent / "data" / "openrouter_slugs.json"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"


class CrossProviderUnavailable(Exception):
    """Raised when a non-Anthropic pick can't be executed (no key or no slug).
    Callers should catch this and fall back to an Anthropic-only re-pick."""


@dataclass
class ExecResult:
    text: str
    model: str
    decision_id: str
    provider: str
    input_tokens: int
    output_tokens: int
    actual_cost_usd: Optional[float]


# ---- key + slug resolution --------------------------------------------------

def resolve_openrouter_key() -> Optional[str]:
    """OPENROUTER_API_KEY env var, else a keychain entry the user created.
    Returns None when unavailable — never raises, never logs the value."""
    env = os.environ.get("OPENROUTER_API_KEY")
    if env:
        return env
    try:
        proc = subprocess.run(
            ["security", "find-generic-password", "-s", "aitr-openrouter", "-w"],
            capture_output=True, text=True, timeout=5,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def _load_slug_map() -> dict:
    if SLUG_MAP_PATH.exists():
        try:
            return json.loads(SLUG_MAP_PATH.read_text())
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def openrouter_slug(model_id: str) -> Optional[str]:
    """Our catalog id → explicit OpenRouter slug, or None when unmapped."""
    return _load_slug_map().get(model_id)


def fetch_openrouter_model_ids(timeout: float = 8.0) -> list[str]:
    """OpenRouter's public model list (no key needed). Used by validate-slugs to
    confirm a proposed slug actually exists before it's trusted for execution."""
    req = urllib.request.Request(
        f"{OPENROUTER_BASE}/models",
        headers={"Accept": "application/json", "User-Agent": "aitr/0.1"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return [m.get("id", "") for m in body.get("data", []) if m.get("id")]


# ---- actuals logging --------------------------------------------------------

def log_actuals(record: dict, *, log_path: Optional[Path] = None) -> None:
    log_path = log_path or ACTUALS_LOG  # resolve at call time so tests can patch
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError as exc:
        print(f"aitr_exec: failed to write actuals log {log_path}: {exc}", file=sys.stderr)


def _model_pricing(model_id: str) -> Optional[dict]:
    try:
        from catalog import load_catalog  # local import keeps module import light
        cat = load_catalog(offline=True).body
    except Exception:
        return None
    rec = next((m for m in (cat.get("models") or []) if m.get("id") == model_id), None)
    return (rec or {}).get("pricing")


def actual_cost(model_id: str, input_tokens: int, output_tokens: int) -> Optional[float]:
    pricing = _model_pricing(model_id)
    if not pricing:
        return None
    in_rate = float(pricing.get("input_per_mtok") or 0.0)
    out_rate = float(pricing.get("output_per_mtok") or 0.0)
    return (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000.0


# ---- the pick → execute → log path -----------------------------------------

def _pick(signal_kv: dict) -> dict:
    """Run pick.py and return the decision dict."""
    cmd = [sys.executable or "python3", str(SKILL_DIR / "pick.py"), "pick", "--format", "json"]
    for k, v in signal_kv.items():
        if v is not None:
            cmd.append(f"{k}={v}")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError(f"aitr pick failed (exit {proc.returncode}): {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def _openrouter_complete(slug: str, prompt: str, system: Optional[str], max_tokens: int, key: str,
                         timeout: float = 120.0) -> tuple[str, int, int]:
    messages = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": prompt}
    ]
    payload = json.dumps({"model": slug, "messages": messages, "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(
        f"{OPENROUTER_BASE}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "aitr/0.1",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    text = body["choices"][0]["message"]["content"]
    usage = body.get("usage", {})
    return text, int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))


def complete(
    prompt: str,
    *,
    task_kind: str,
    caller: str,
    max_tokens: int = 2000,
    quality_floor: str = "medium",
    system: Optional[str] = None,
    artifact_size_tokens: Optional[int] = None,
    modality_required: Optional[str] = None,
    billing_mode: str = "metered",
    provider_constraint: str = "any",
    anthropic_executor: Optional[Callable[..., tuple[str, int, int]]] = None,
    openrouter_key: Optional[str] = None,
) -> ExecResult:
    """Pick a model for the task, execute it, log actual token usage.

    `anthropic_executor(model, prompt, system, max_tokens) -> (text, in_tok, out_tok)`
    is REQUIRED for Anthropic picks — the caller owns its client/auth. Cross-provider
    (OpenRouter) picks execute here, gated on key + explicit slug; if either is
    missing, raise CrossProviderUnavailable so the caller can re-pick anthropic-only.
    """
    signal = {
        "task_kind": task_kind,
        "caller": caller,
        "quality_floor": quality_floor,
        "billing_mode": billing_mode,
        "provider_constraint": provider_constraint,
    }
    if artifact_size_tokens is not None:
        signal["artifact_size_tokens"] = max(int(artifact_size_tokens), 100)
    if modality_required:
        signal["modality_required"] = modality_required

    decision = _pick(signal)
    model_id = decision["model"]
    decision_id = decision.get("decision_id", "")
    provider = decision.get("provider", "")

    if provider == "anthropic":
        if anthropic_executor is None:
            raise ValueError("anthropic_executor is required for anthropic picks")
        claude_name = model_id[len("anthropic__"):]
    else:
        key = openrouter_key or resolve_openrouter_key()
        slug = openrouter_slug(model_id)
        if not key or not slug:
            # Not an operational failure of the picked model — it's a config gap.
            # Don't record a reliability outcome; let the caller re-pick.
            raise CrossProviderUnavailable(
                f"pick {model_id!r} is non-Anthropic but "
                f"{'no OpenRouter key' if not key else 'no slug mapping'}; caller should re-pick anthropic-only"
            )

    # Operational realized-quality: a model that completes cleanly is more
    # reliable than one that times out / errors / returns nothing. Record both
    # sides (source=aitr-exec) so reputation reflects reliability — bounded and
    # decaying, so a steady baseline is mild but flakiness erodes it fast.
    try:
        if provider == "anthropic":
            text, in_tok, out_tok = anthropic_executor(claude_name, prompt, system, max_tokens)
        else:
            text, in_tok, out_tok = _openrouter_complete(slug, prompt, system, max_tokens, key)
    except Exception as exc:
        if decision_id:
            record_quality(decision_id, "bad", source="aitr-exec",
                           note=f"execution failed: {type(exc).__name__}")
        raise
    if decision_id:
        outcome = "good" if (text and text.strip()) else "bad"
        record_quality(decision_id, outcome, source="aitr-exec",
                       note="clean execution" if outcome == "good" else "empty output")

    cost = actual_cost(model_id, in_tok, out_tok)
    log_actuals({
        "decision_id": decision_id,
        "model": model_id,
        "provider": provider,
        "caller": caller,
        "billing_mode": billing_mode,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "actual_cost_usd": cost,
    })
    return ExecResult(
        text=text, model=model_id, decision_id=decision_id, provider=provider,
        input_tokens=in_tok, output_tokens=out_tok, actual_cost_usd=cost,
    )


# ---- CLI: resolve / validate-slugs (no execution, no spend) -----------------

def _cmd_resolve(argv: list[str]) -> int:
    """Show what complete() WOULD pick + execute for a signal, without running it."""
    from task_signal import parse_kv_args
    kv = parse_kv_args(argv)
    decision = _pick(kv)
    model_id = decision["model"]
    provider = decision.get("provider", "")
    out = {
        "model": model_id,
        "provider": provider,
        "decision_id": decision.get("decision_id"),
        "execution_path": "anthropic (caller-supplied executor)" if provider == "anthropic" else "openrouter",
    }
    if provider != "anthropic":
        out["openrouter_key_available"] = resolve_openrouter_key() is not None
        out["slug"] = openrouter_slug(model_id)
        out["cross_provider_ready"] = bool(out["openrouter_key_available"] and out["slug"])
    print(json.dumps(out, indent=2))
    return 0


def _cmd_validate_slugs(_argv: list[str]) -> int:
    """Check that every slug in the map exists on OpenRouter's public model list."""
    slug_map = _load_slug_map()
    if not slug_map:
        print("no slug map yet (data/openrouter_slugs.json absent or empty)")
        return 0
    try:
        live = set(fetch_openrouter_model_ids())
    except Exception as exc:
        print(f"could not fetch OpenRouter model list: {exc}", file=sys.stderr)
        return 1
    bad = {mid: slug for mid, slug in slug_map.items() if slug not in live}
    for mid, slug in slug_map.items():
        print(f"  {'OK ' if slug in live else 'MISSING'}  {mid} → {slug}")
    return 1 if bad else 0


def main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: aitr_exec.py {resolve|validate-slugs} [signal kv...]", file=sys.stderr)
        return 1
    verb, rest = argv[0], argv[1:]
    if verb == "resolve":
        return _cmd_resolve(rest)
    if verb == "validate-slugs":
        return _cmd_validate_slugs(rest)
    print(f"unknown verb {verb!r}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
