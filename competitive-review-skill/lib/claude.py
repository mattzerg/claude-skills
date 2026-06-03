"""Claude LLM wrapper with two paths:

1. Anthropic SDK path (when ANTHROPIC_API_KEY env is set) — explicit prompt caching
   on system prompts, streaming for early failure detection, structured retry on
   rate-limit/transient errors.

2. Claude CLI subprocess path (default fallback) — uses `--output-format json` for
   structured output, shorter per-call timeouts with backoff retry instead of one
   giant blocking wait.

Public API (preserved for back-compat):
    call_claude(prompt, *, model=..., system=..., timeout=...)
        -> raw text
    call_claude_json(prompt, *, model=..., system=..., timeout=...)
        -> parsed JSON (dict | list)
    extract_json(raw)
        -> parse JSON from prose-wrapped output

The original `timeout` arg is kept as the OUTER budget (across retries). Per-attempt
timeout is min(120s, timeout / max_retries).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

CLAUDE_BIN = str(Path.home() / ".local" / "bin" / "claude")
# Fallback when aitr (the internal model router) is unavailable. Callers that pass
# an explicit model= always win; otherwise calls route via aitr (research / medium).
DEFAULT_MODEL = "claude-sonnet-4-6"

_AITR_SCRIPTS = Path.home() / ".claude" / "skills" / "aitr" / "scripts"
_routed_model_cache: Optional[str] = None


def _routed_default_model() -> str:
    """aitr-routed model for competitive-review calls; loud fallback to DEFAULT_MODEL."""
    global _routed_model_cache
    if _routed_model_cache is None:
        if str(_AITR_SCRIPTS) not in sys.path:
            sys.path.insert(0, str(_AITR_SCRIPTS))
        try:
            from skill_default import aitr_model_or
            _routed_model_cache = aitr_model_or(
                DEFAULT_MODEL,
                task_kind="research",
                caller="competitive-review-skill",
                quality_floor="medium",
            )
        except ImportError:
            _routed_model_cache = DEFAULT_MODEL
    return _routed_model_cache

# Tunables
MAX_RETRIES = 3
PER_ATTEMPT_TIMEOUT_CAP = 300   # never wait more than 5 min on a single attempt
BACKOFF_SECONDS = (5, 30, 90)   # exponential backoff between retries


# ============================================================================
# JSON extraction (unchanged from previous version)
# ============================================================================

def extract_json(raw: str) -> Optional[dict | list]:
    """Strip markdown fences and surrounding prose, return parsed JSON or None."""
    raw = re.sub(r"^```(?:json)?\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    for opener, closer in (("{", "}"), ("[", "]")):
        first = raw.find(opener)
        last = raw.rfind(closer)
        if first != -1 and last > first:
            candidate = raw[first : last + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
    return None


# ============================================================================
# SDK path
# ============================================================================

def _sdk_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _call_sdk(prompt: str, system: Optional[str], model: str, timeout: int) -> str:
    """Anthropic SDK path with prompt caching on the system prompt (when present).

    The system prompt benefits the most from caching since it's static across calls
    (e.g. "you are a competitive intelligence analyst extracting…"). User prompts
    vary per call so are not cached.
    """
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path.home() / ".config" / "zerg"))
    from anthropic_client import make_client

    client = make_client(timeout=timeout, source="competitive-review")
    kwargs: dict = {
        "model": model,
        "max_tokens": 8192,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = [
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}},
        ]

    resp = client.messages.create(**kwargs)
    parts = []
    for block in resp.content:
        if hasattr(block, "text"):
            parts.append(block.text)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts)


# ============================================================================
# CLI subprocess path
# ============================================================================

def _call_cli(prompt: str, system: Optional[str], model: str, timeout: int) -> str:
    """CLI subprocess path. Uses --output-format json for structured response.

    Concatenates system + user prompt as one input (stdin) when system is provided,
    since `claude --print` doesn't expose a separate system flag.
    """
    full_input = prompt if not system else f"{system}\n\n---\n\n{prompt}"
    cmd = [CLAUDE_BIN, "--print", "--model", model, "--tools", "", "--output-format", "json"]
    result = subprocess.run(
        cmd,
        input=full_input,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI exit {result.returncode}: {result.stderr.strip()[:500]}")
    # JSON output: parse and pull `result` field
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        # Older CLI versions may emit plain text under text mode — return raw
        return result.stdout.strip()
    if payload.get("is_error"):
        raise RuntimeError(f"Claude CLI returned error: {payload.get('result','?')}")
    return (payload.get("result") or "").strip()


# ============================================================================
# Top-level call with retry + backoff
# ============================================================================

def call_claude(
    prompt: str,
    *,
    system: Optional[str] = None,
    model: Optional[str] = None,
    timeout: int = 600,
) -> str:
    """Public API. Routes to SDK or CLI based on env. Retries on transient failures.

    `model=None` (default) routes via aitr; pass an explicit model to override.
    `timeout` is the OUTER budget. Each attempt is bounded to min(timeout, 300s);
    we retry up to MAX_RETRIES times within the outer budget.
    """
    model = model or _routed_default_model()
    use_sdk = _sdk_available()
    deadline = time.monotonic() + timeout
    last_err: Optional[Exception] = None

    for attempt in range(MAX_RETRIES):
        remaining = max(30, deadline - time.monotonic())
        per_attempt = int(min(remaining, PER_ATTEMPT_TIMEOUT_CAP))
        try:
            if use_sdk:
                return _call_sdk(prompt, system, model, per_attempt)
            return _call_cli(prompt, system, model, per_attempt)
        except subprocess.TimeoutExpired as e:
            last_err = e
            print(
                f"[claude] attempt {attempt+1}/{MAX_RETRIES} timed out after {per_attempt}s",
                file=sys.stderr,
            )
        except Exception as e:
            last_err = e
            msg = str(e)[:200]
            print(f"[claude] attempt {attempt+1}/{MAX_RETRIES} failed: {msg}", file=sys.stderr)

        # Backoff if we have time and another attempt
        if attempt < MAX_RETRIES - 1 and time.monotonic() < deadline:
            sleep_for = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)]
            sleep_for = min(sleep_for, max(1, deadline - time.monotonic() - 30))
            if sleep_for > 0:
                time.sleep(sleep_for)

    raise RuntimeError(f"Claude CLI failed after {MAX_RETRIES} attempts: {last_err}")


def call_claude_json(
    prompt: str,
    *,
    system: Optional[str] = None,
    model: Optional[str] = None,
    timeout: int = 600,
) -> dict | list:
    """Call Claude and parse JSON from the response. Raises if no JSON extractable."""
    raw = call_claude(prompt, system=system, model=model, timeout=timeout)
    parsed = extract_json(raw)
    if parsed is None:
        raise ValueError(f"Could not extract JSON from output:\n{raw[:1500]}")
    return parsed
