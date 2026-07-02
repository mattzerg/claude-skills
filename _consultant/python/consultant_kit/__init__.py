"""consultant_kit — shared library for the consultant skill family.

Lightweight modules (`brand`, `io`, `cite`, `frontmatter`, `ids`) are eagerly
imported because they have no heavy deps. `chart`, `annotate`, and `layout`
are lazy-imported on first access so skills that only write markdown don't pay
matplotlib + python-pptx import costs.
"""
from __future__ import annotations

from . import brand, cite, frontmatter, ids, io

__all__ = ["brand", "io", "cite", "frontmatter", "ids", "chart", "annotate", "layout"]

_LAZY = {"chart", "annotate", "layout"}


def __getattr__(name: str):
    if name in _LAZY:
        import importlib

        mod = importlib.import_module(__name__ + "." + name)
        globals()[name] = mod
        return mod
    raise AttributeError(name)
