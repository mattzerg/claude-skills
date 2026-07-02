#!/usr/bin/env python3
"""Shell out to `codex exec` for a Codex-side cross-model review.

Used when the active model is Claude — we ask Codex for the second opinion.
Mirrors the invocation pattern from ~/.claude/skills/codex/SKILL.md verbatim:

    codex exec "<prompt>" -C "<repo>" -s read-only \
        -c 'model_reasoning_effort="high"' \
        --enable web_search_cached \
        --json < /dev/null

Returns the captured stdout (raw text from codex) and a status string.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Tuple


def find_codex_bin() -> str | None:
    """Locate the codex CLI. Returns absolute path or None."""
    for candidate in ("/opt/homebrew/bin/codex", "/usr/local/bin/codex"):
        if Path(candidate).exists() and os.access(candidate, os.X_OK):
            return candidate
    found = shutil.which("codex")
    return found


def invoke_codex(
    prompt: str,
    *,
    repo_root: Path,
    timeout: int = 300,
    effort: str = "high",
) -> Tuple[str, str]:
    """Run `codex exec` with the given prompt. Returns (text, status).

    status is one of: ok, missing-binary, timeout, error.
    On non-ok, text is a human-readable diagnostic instead of model output.
    """
    bin_path = find_codex_bin()
    if not bin_path:
        return ("codex binary not found on PATH (looked in /opt/homebrew/bin, /usr/local/bin, $PATH)", "missing-binary")

    cmd = [
        bin_path,
        "exec",
        prompt,
        "-C", str(repo_root),
        "-s", "read-only",
        "-c", f'model_reasoning_effort="{effort}"',
        "--enable", "web_search_cached",
        "--skip-git-repo-check",
        "--json",
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return (f"codex exec timed out after {timeout}s", "timeout")
    except FileNotFoundError as e:
        return (f"codex exec failed to launch: {e}", "error")

    if proc.returncode != 0:
        diag = proc.stderr.strip() or proc.stdout.strip() or f"exit code {proc.returncode}"
        return (f"codex exec exited non-zero:\n{diag}", "error")

    text = parse_codex_jsonl(proc.stdout)
    return (text, "ok")


def parse_codex_jsonl(raw: str) -> str:
    """Extract the assistant's final text response from codex --json JSONL stream.

    codex emits events like:
      {"type":"item.completed","item":{"id":"item_1","type":"agent_message","text":"..."}}
      {"type":"item.completed","item":{"id":"item_0","type":"error","message":"..."}}
      {"type":"turn.completed","usage":{...}}

    We want the agent_message text(s) concatenated. Errors are surfaced
    inline as well so the caller sees auth / deprecation hiccups.
    """
    pieces: list[str] = []
    errors: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = obj.get("item")
        if isinstance(item, dict):
            item_type = item.get("type")
            if item_type == "agent_message" and isinstance(item.get("text"), str):
                pieces.append(item["text"])
            elif item_type == "error" and isinstance(item.get("message"), str):
                errors.append(item["message"])
            continue
        # Older shapes — try top-level common keys
        for key in ("text", "content", "delta", "message"):
            val = obj.get(key)
            if isinstance(val, str) and val:
                pieces.append(val)
                break
            if isinstance(val, dict):
                inner = val.get("text") or val.get("content")
                if isinstance(inner, str) and inner:
                    pieces.append(inner)
                    break
    out = "\n".join(pieces).strip()
    if not out and errors:
        return "codex error: " + "; ".join(errors)
    # Fall back to raw if nothing parsed — better than empty
    return out or raw.strip()


if __name__ == "__main__":
    import sys
    prompt = sys.stdin.read()
    text, status = invoke_codex(prompt, repo_root=Path.cwd())
    print(f"[status:{status}]")
    print(text)
