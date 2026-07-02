"""YAML frontmatter read/write for idea files.

Uses python-frontmatter when available; falls back to a minimal parser to keep
the skill runnable without extra deps when iterating fast.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import yaml  # PyYAML — usually present
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL)


def parse(text: str) -> tuple[dict[str, Any], str]:
    """Return (metadata, body). Empty dict if no frontmatter."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    raw, body = m.group(1), m.group(2)
    if yaml is None:
        return _naive_yaml(raw), body
    return yaml.safe_load(raw) or {}, body


def dump(meta: dict[str, Any], body: str) -> str:
    """Render a markdown file with YAML frontmatter."""
    if yaml is None:
        raw = _naive_yaml_dump(meta)
    else:
        raw = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).rstrip()
    return f"---\n{raw}\n---\n\n{body.lstrip()}"


def read_file(path: Path) -> tuple[dict[str, Any], str]:
    return parse(path.read_text())


def write_file(path: Path, meta: dict[str, Any], body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump(meta, body))


def update_field(path: Path, **fields: Any) -> dict[str, Any]:
    """Patch frontmatter fields on an existing file. Returns updated meta."""
    meta, body = read_file(path)
    meta.update(fields)
    write_file(path, meta, body)
    return meta


def _naive_yaml(raw: str) -> dict[str, Any]:
    """Minimal fallback parser for `key: value` lines."""
    out: dict[str, Any] = {}
    for line in raw.splitlines():
        line = line.rstrip()
        if not line or line.startswith("#") or line.startswith(" "):
            continue
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        out[k.strip()] = v.strip().strip('"\'') or None
    return out


def _naive_yaml_dump(meta: dict[str, Any]) -> str:
    lines = []
    for k, v in meta.items():
        if v is None:
            lines.append(f"{k}: null")
        elif isinstance(v, list):
            if not v:
                lines.append(f"{k}: []")
            else:
                lines.append(f"{k}:")
                for item in v:
                    lines.append(f'  - "{item}"')
        elif isinstance(v, str) and (":" in v or "#" in v or v.startswith("[")):
            lines.append(f'{k}: "{v}"')
        else:
            lines.append(f"{k}: {v}")
    return "\n".join(lines)
