#!/usr/bin/env python3
"""Open the workstreams manifest in $EDITOR; validate on save."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


MANIFEST = Path.home() / ".config" / "zerg" / "workstreams.yaml"
COLLECT = Path.home() / ".claude" / "workstreams" / "collect.py"


def main(argv: list[str]) -> int:
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "vi"
    rc = subprocess.call([editor, str(MANIFEST)])
    if rc != 0:
        print(f"editor exited rc={rc}; not validating", file=sys.stderr)
        return rc
    return subprocess.call(["/usr/bin/python3", str(COLLECT), "--validate-manifest"])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
