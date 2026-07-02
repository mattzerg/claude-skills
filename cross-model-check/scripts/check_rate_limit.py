#!/usr/bin/env python3
"""Lightweight pre-flight check: is the OTHER model rate-limited?

If the cross-check would just fail with a usage error, skip rather than block
the gate. Returns a tuple (ok: bool, reason: str). ok=False -> skip; reason is
a short human-readable string for the gate to record.

Conservative — only returns False on clear-cut signals. Soft failures default
to ok=True so the cross-check fires and reports the real error.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Tuple


CODEX_USAGE_ROUTER = Path.home() / ".claude" / "skills" / "codex-usage-router" / "scripts" / "codex_usage_router.py"


def codex_available() -> Tuple[bool, str]:
    """Check if Codex looks usable. Tries the usage router first."""
    if not CODEX_USAGE_ROUTER.exists():
        return (True, "codex-usage-router not installed; firing cross-check blind")

    try:
        proc = subprocess.run(
            ["python3", str(CODEX_USAGE_ROUTER), "status", "--json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return (True, "codex-usage-router timed out; firing cross-check blind")
    except FileNotFoundError:
        return (True, "python3 not found; firing cross-check blind")

    if proc.returncode != 0:
        return (True, f"codex-usage-router exited {proc.returncode}; firing cross-check blind")

    try:
        obj = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return (True, "codex-usage-router returned non-JSON; firing cross-check blind")

    # Defensive — codex_usage_router.py output shape may evolve. We're looking
    # for any explicit rate-limit / over-cap signal. Anything else = proceed.
    status_str = (obj.get("status") or obj.get("state") or "").lower()
    if "rate" in status_str and ("limit" in status_str or "exceed" in status_str):
        return (False, f"codex rate-limited per usage-router: {status_str}")

    cap_pct = obj.get("cap_pct") or obj.get("usage_pct")
    try:
        if cap_pct is not None and float(cap_pct) >= 0.98:
            return (False, f"codex usage at {float(cap_pct)*100:.0f}% cap; skipping cross-check")
    except (TypeError, ValueError):
        pass

    return (True, "codex available")


def claude_available() -> Tuple[bool, str]:
    """Check if Claude headless CLI looks usable.

    No equivalent usage-router for Claude yet, so we only check binary presence.
    Auth issues will surface as a subprocess error and be reported as exit-3.
    """
    from .invoke_claude import find_claude_bin  # type: ignore  # noqa
    bin_path = find_claude_bin()
    if not bin_path:
        return (False, "claude binary not found")
    return (True, "claude binary present")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "codex"
    if target == "codex":
        ok, reason = codex_available()
    elif target == "claude":
        # avoid relative import when run as __main__
        sys.path.insert(0, str(Path(__file__).parent))
        from invoke_claude import find_claude_bin
        bin_path = find_claude_bin()
        ok, reason = (bool(bin_path), f"claude bin: {bin_path or 'not found'}")
    else:
        print(f"unknown target: {target}", file=sys.stderr)
        sys.exit(2)
    print(json.dumps({"available": ok, "reason": reason}))
    sys.exit(0 if ok else 3)
