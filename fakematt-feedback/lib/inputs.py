"""Resolve the user's target into a normalized spec the rest of the pipeline understands.

Adapters supported:
- live_url: any http(s)://… (default path through capture.crawl_and_capture)
- local_url: localhost / 127.0.0.1 (port-up precheck before crawl)
- figma: figma://<file-key>[/<frame-id>] — fetched via figma-skill, frames rendered as PNGs
- static: /path/to/folder OR /path/to/file.pdf — image-only critique, no browser
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

TargetKind = Literal["live_url", "local_url", "figma", "static"]


@dataclass
class TargetSpec:
    kind: TargetKind
    raw: str
    canonical: str
    product_hint: str | None = None  # used to find Projects/Zstack/<product>.md
    figma_key: str | None = None
    figma_frame: str | None = None
    static_paths: list[str] | None = None


def _product_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    base = host.split(":")[0]
    base = base.removeprefix("www.")
    base = base.split(".")[0]
    return base or "site"


def _resolve_static(path: str) -> TargetSpec:
    p = Path(os.path.expanduser(path)).resolve()
    if not p.exists():
        raise FileNotFoundError(f"static target not found: {p}")
    if p.is_file():
        if p.suffix.lower() == ".pdf":
            return TargetSpec(kind="static", raw=path, canonical=str(p), static_paths=[str(p)], product_hint=p.stem)
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            return TargetSpec(kind="static", raw=path, canonical=str(p), static_paths=[str(p)], product_hint=p.stem)
        raise ValueError(f"unsupported static file type: {p.suffix}")
    images = sorted(
        str(c) for c in p.iterdir()
        if c.is_file() and c.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".pdf"}
    )
    if not images:
        raise FileNotFoundError(f"no images/PDFs in {p}")
    return TargetSpec(kind="static", raw=path, canonical=str(p), static_paths=images, product_hint=p.name)


def _resolve_figma(raw: str) -> TargetSpec:
    rest = raw.removeprefix("figma://")
    parts = rest.split("/", 1)
    file_key = parts[0]
    frame = parts[1] if len(parts) > 1 else None
    if not file_key:
        raise ValueError(f"figma:// requires a file key: figma://<key>[/<frame>]")
    return TargetSpec(
        kind="figma",
        raw=raw,
        canonical=f"figma://{file_key}" + (f"/{frame}" if frame else ""),
        figma_key=file_key,
        figma_frame=frame,
        product_hint=f"figma-{file_key[:8]}",
    )


def resolve(raw: str) -> TargetSpec:
    if raw.startswith(("http://localhost", "http://127.0.0.1", "https://localhost")):
        return TargetSpec(kind="local_url", raw=raw, canonical=raw, product_hint=_product_from_url(raw))
    if raw.startswith(("http://", "https://")):
        return TargetSpec(kind="live_url", raw=raw, canonical=raw, product_hint=_product_from_url(raw))
    if raw.startswith("figma://"):
        return _resolve_figma(raw)
    if raw.startswith(("/", "~", "./")) or os.path.exists(raw):
        return _resolve_static(raw)
    raise ValueError(f"Cannot resolve target: {raw!r}")
