"""Static-input capture path: PDFs and image folders.

For static inputs we don't have a DOM/console/network/axe surface — the
critique only sees the image plus optional filename hints. Returns
PageCapture-shaped dicts so the rest of the pipeline doesn't care.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .capture import PageCapture


def _split_pdf(pdf: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / pdf.stem
    try:
        subprocess.run(
            ["pdftoppm", "-png", "-r", "120", str(pdf), str(base)],
            check=True, capture_output=True,
        )
    except FileNotFoundError:
        raise RuntimeError("pdftoppm not installed (brew install poppler)")
    return sorted(out_dir.glob(f"{pdf.stem}-*.png"))


def capture_static(paths: list[str], run_dir: Path) -> list[PageCapture]:
    """Each image becomes a 'page'. PDFs are split into pages first."""
    images: list[Path] = []
    shots_dir = run_dir / "screenshots"
    shots_dir.mkdir(parents=True, exist_ok=True)
    for raw in paths:
        p = Path(raw)
        if p.suffix.lower() == ".pdf":
            images.extend(_split_pdf(p, shots_dir / "pdf"))
        else:
            dst = shots_dir / p.name
            shutil.copy2(p, dst)
            images.append(dst)
    captures: list[PageCapture] = []
    for img in images:
        captures.append(PageCapture(
            url=f"file://{img}",
            title=img.stem,
            final_url=f"file://{img}",
            screenshot_desktop=str(img),
            screenshot_mobile=str(img),
            text_content="(static input — no DOM available)",
            links=[],
            primary_cta=None,
            h1=None,
            headings=[],
            forms=[],
        ))
    return captures
