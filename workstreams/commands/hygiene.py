#!/usr/bin/env python3
"""Run session hygiene analysis. Thin shim → ~/.claude/workstreams/session_hygiene.py."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    target = Path.home() / ".claude" / "workstreams" / "session_hygiene.py"
    os.execv("/usr/bin/python3", ["/usr/bin/python3", str(target), *argv])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
