#!/usr/bin/env python3
"""Shell out to `claude -p` for a Claude-side cross-model review.

Used when the active model is Codex — we ask Claude for the second opinion.
Uses the headless `claude -p <prompt>` form with `--output-format stream-json`
so we can extract the final assistant text reliably.

Returns the captured assistant text and a status string.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Tuple


def find_claude_bin() -> str | None:
    """Locate the claude CLI. Returns absolute path or None.

    Order matters: prefer ~/.config/zerg/zclaude (Matt's account router) so the
    cross-check participates in the same auth flow as the rest of the stack.
    Fall back to plain `claude` on PATH.
    """
    zclaude = Path.home() / ".config" / "zerg" / "zclaude"
    if zclaude.exists() and os.access(zclaude, os.X_OK):
        return str(zclaude)
    found = shutil.which("claude")
    return found


def invoke_claude(
    prompt: str,
    *,
    timeout: int = 300,
    model: str | None = None,
    cwd: Path | None = None,
) -> Tuple[str, str]:
    """Run `claude -p` with the given prompt. Returns (text, status).

    status is one of: ok, missing-binary, timeout, error.

    Side channel: when the CLI's JSON result carries a `usage` block, the
    parsed {input_tokens, output_tokens} land in `invoke_claude.last_usage`
    (None otherwise) — callers feed it to aitr's record-actuals.
    """
    invoke_claude.last_usage = None
    bin_path = find_claude_bin()
    if not bin_path:
        return (
            "claude binary not found (looked for ~/.config/zerg/zclaude, then $PATH). "
            "Install Claude Code CLI or symlink zclaude to make the cross-check work from Codex.",
            "missing-binary",
        )

    cmd = [bin_path, "-p", prompt, "--output-format", "json"]
    if model:
        cmd.extend(["--model", model])

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return (f"claude -p timed out after {timeout}s", "timeout")
    except FileNotFoundError as e:
        return (f"claude -p failed to launch: {e}", "error")

    if proc.returncode != 0:
        diag = proc.stderr.strip() or proc.stdout.strip() or f"exit code {proc.returncode}"
        return (f"claude -p exited non-zero:\n{diag}", "error")

    text = parse_claude_json(proc.stdout)
    invoke_claude.last_usage = parse_claude_usage(proc.stdout)
    return (text, "ok")


def parse_claude_usage(raw: str) -> dict | None:
    """Extract {input_tokens, output_tokens} from `claude -p --output-format json`
    output. Returns None when usage isn't present/parseable."""
    try:
        obj = json.loads(raw.strip())
    except (json.JSONDecodeError, AttributeError):
        return None
    usage = obj.get("usage") if isinstance(obj, dict) else None
    if not isinstance(usage, dict):
        return None
    in_tok = usage.get("input_tokens")
    out_tok = usage.get("output_tokens")
    if isinstance(in_tok, (int, float)) and isinstance(out_tok, (int, float)):
        # Include cache reads/writes in input — they're real prompt tokens.
        cache_in = sum(
            v for k, v in usage.items()
            if k in ("cache_read_input_tokens", "cache_creation_input_tokens")
            and isinstance(v, (int, float))
        )
        return {"input_tokens": int(in_tok + cache_in), "output_tokens": int(out_tok)}
    return None


def parse_claude_json(raw: str) -> str:
    """Extract the assistant's text from `claude -p --output-format json` output.

    The single-result JSON shape is roughly {"result": "<text>", "is_error": false, ...}.
    Older versions may use {"content": [{"text": "..."}]} or just emit plain text.
    """
    raw = raw.strip()
    if not raw:
        return ""
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return raw  # plain-text fallback
    if isinstance(obj, dict):
        if isinstance(obj.get("result"), str):
            return obj["result"]
        content = obj.get("content")
        if isinstance(content, list):
            pieces = []
            for c in content:
                if isinstance(c, dict) and isinstance(c.get("text"), str):
                    pieces.append(c["text"])
            if pieces:
                return "\n".join(pieces)
        if isinstance(obj.get("text"), str):
            return obj["text"]
    return raw


if __name__ == "__main__":
    import sys
    prompt = sys.stdin.read()
    text, status = invoke_claude(prompt)
    print(f"[status:{status}]")
    print(text)
