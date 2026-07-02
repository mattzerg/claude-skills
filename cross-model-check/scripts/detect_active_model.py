#!/usr/bin/env python3
"""Detect which LLM session is currently invoking the cross-model-check skill.

Returns 'claude' | 'codex' | 'unknown'. Used by run.py to decide which CLI to
shell out to (we always invoke the OTHER one).
"""
from __future__ import annotations

import os
import sys


CLAUDE_ENV_HINTS = ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_ENTRYPOINT")
CODEX_ENV_HINTS = ("CODEX_SESSION_ID", "CODEX_ENV", "CODEX_HOME")


def active_model() -> str:
    for var in CLAUDE_ENV_HINTS:
        if os.environ.get(var):
            return "claude"
    for var in CODEX_ENV_HINTS:
        if os.environ.get(var):
            return "codex"
    return "unknown"


def other_model(active: str) -> str:
    if active == "claude":
        return "codex"
    if active == "codex":
        return "claude"
    raise ValueError(f"cannot infer other model from active={active!r}")


if __name__ == "__main__":
    print(active_model())
    sys.exit(0)
