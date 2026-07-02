"""Tiny module skills import BEFORE importing consultant_kit, to re-exec under
the shared venv. Used at the top of every consultant skill's run.py:

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path.home() / ".claude/skills/_consultant/python"))
    from _bootstrap_helper import ensure_venv
    ensure_venv(__file__)

After ensure_venv returns, consultant_kit is importable.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SHARED = Path.home() / ".claude/skills/_consultant/python"


def ensure_venv(entry_file: str) -> None:
    venv_py = SHARED / ".venv/bin/python3"
    here = Path(sys.executable).resolve()
    if venv_py.exists() and here != venv_py.resolve():
        subprocess.run(["bash", str(SHARED / "bootstrap.sh")], check=True, capture_output=True)
        os.execv(str(venv_py), [str(venv_py), entry_file, *sys.argv[1:]])
    if str(SHARED) not in sys.path:
        sys.path.insert(0, str(SHARED))
