#!/usr/bin/env python3
"""Print the right `zclaude --resume <sid>` (or new-session) command for a workstream.

Thin shim — delegates to ~/.claude/workstreams/resume.py.

Usage:
  resume.py <ws-id>
  resume.py <ws-id> --json
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    target = Path.home() / ".claude" / "workstreams" / "resume.py"
    os.execv("/usr/bin/python3", ["/usr/bin/python3", str(target), *argv])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
