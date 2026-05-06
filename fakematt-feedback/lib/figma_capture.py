"""Figma-input capture path. Renders frames as PNGs via figma-skill.

Stub — relies on figma-skill being callable. When figma-skill ships an SDK
shape we can import it directly; for now we shell out to its CLI.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .capture import PageCapture

FIGMA_SKILL = Path.home() / ".claude" / "skills" / "figma-skill"


def capture_figma(file_key: str, frame: str | None, run_dir: Path) -> list[PageCapture]:
    """Stub: pulls frames via figma-skill, renders to PNGs in run_dir/screenshots/.

    Until figma-skill exposes a stable CLI for "render all frames in file <key>
    to <dir>", this raises NotImplementedError with a clear pointer.
    """
    raise NotImplementedError(
        "figma adapter needs figma-skill render subcommand. Open the Figma file, "
        "export the frames you want reviewed, then run: "
        f"`fakematt-feedback ~/Downloads/<frames-folder>/`"
    )
