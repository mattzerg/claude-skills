"""YAML frontmatter parser/renderer with no third-party deps.

Supports the subset we need:
- scalars (str, int, float, bool, null)
- ISO dates (as strings — caller parses)
- inline lists `[a, b, c]`
- block lists `- item` (scalars or mappings)
- mappings `key: value` (nested via indent)
- block-literal scalars (`key: |` with indented body)
"""
from __future__ import annotations

import re
from typing import Any


def _parse_scalar(raw: str) -> Any:
    """Parse a single YAML scalar value into Python types."""
    v = raw.strip()
    if v == "" or v in ("null", "~"):
        return None
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    if re.fullmatch(r"-?\d+", v):
        try:
            return int(v)
        except ValueError:
            pass
    if re.fullmatch(r"-?\d+\.\d+", v):
        try:
            return float(v)
        except ValueError:
            pass
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(p) for p in _split_csv(inner)]
    return v


def _split_csv(s: str) -> list[str]:
    """Split on commas, respecting quoted strings."""
    out: list[str] = []
    buf = ""
    in_quote: str | None = None
    for ch in s:
        if in_quote:
            buf += ch
            if ch == in_quote:
                in_quote = None
        elif ch in ('"', "'"):
            buf += ch
            in_quote = ch
        elif ch == ",":
            out.append(buf)
            buf = ""
        else:
            buf += ch
    if buf:
        out.append(buf)
    return [p.strip() for p in out]


def _indent_of(line: str) -> int:
    n = 0
    for ch in line:
        if ch == " ":
            n += 1
        elif ch == "\t":
            n += 4
        else:
            break
    return n


def _collect_block_scalar(lines: list[str], i: int, base_indent: int) -> tuple[str, int]:
    """Read a block-literal (`|`) value starting at line i.

    Returns (joined_text, next_line_index). The base_indent is the indent of
    the parent key; the block's lines must be indented strictly more.
    """
    out: list[str] = []
    j = i
    block_indent: int | None = None
    while j < len(lines):
        line = lines[j]
        if not line.strip():
            out.append("")
            j += 1
            continue
        ind = _indent_of(line)
        if ind <= base_indent:
            break
        if block_indent is None:
            block_indent = ind
        if ind < block_indent:
            break
        out.append(line[block_indent:])
        j += 1
    # Strip trailing blank lines
    while out and not out[-1].strip():
        out.pop()
    return ("\n".join(out), j)


def _parse_block(lines: list[str], i: int, base_indent: int) -> tuple[Any, int]:
    """Parse a block starting at line i. Returns (value, next_index).

    `base_indent` is the parent key's indent; children must be indented more.
    Detects list vs mapping by first non-blank child line.
    """
    # Find first non-blank child
    j = i
    while j < len(lines) and not lines[j].strip():
        j += 1
    if j >= len(lines):
        return None, j
    first = lines[j]
    ind = _indent_of(first)
    if ind <= base_indent:
        return None, j
    stripped = first.lstrip()

    if stripped.startswith("- "):
        # List
        out_list: list[Any] = []
        item_indent = ind
        k = j
        while k < len(lines):
            line = lines[k]
            if not line.strip():
                k += 1
                continue
            ln_ind = _indent_of(line)
            if ln_ind < item_indent:
                break
            ln_stripped = line.lstrip()
            if ln_ind == item_indent and ln_stripped.startswith("- "):
                # New list item
                tail = ln_stripped[2:]
                if not tail.strip():
                    # Mapping items follow on next lines under this `- `
                    k += 1
                    item_val, k = _parse_block(lines, k, item_indent)
                    out_list.append(item_val)
                    continue
                # `- key: value` shorthand → first key of an inline mapping;
                # subsequent indented lines extend the mapping.
                if ":" in tail and not (tail.startswith('"') or tail.startswith("'")) and not tail.startswith("["):
                    key, _, val = tail.partition(":")
                    key = key.strip()
                    val = val.strip()
                    item_dict: dict[str, Any] = {}
                    if val == "":
                        # Look further indented for nested value
                        k += 1
                        nested, k = _parse_block(lines, k, item_indent + 2)
                        item_dict[key] = nested
                    elif val == "|":
                        k += 1
                        block, k = _collect_block_scalar(lines, k, item_indent + 2)
                        item_dict[key] = block
                    else:
                        item_dict[key] = _parse_scalar(val)
                        k += 1
                    # Continue picking up sibling keys at indent > item_indent
                    while k < len(lines):
                        sline = lines[k]
                        if not sline.strip():
                            k += 1
                            continue
                        s_ind = _indent_of(sline)
                        if s_ind <= item_indent:
                            break
                        s_stripped = sline.lstrip()
                        if ":" not in s_stripped:
                            break
                        sk, _, sv = s_stripped.partition(":")
                        sk = sk.strip()
                        sv = sv.strip()
                        if sv == "":
                            k += 1
                            nested, k = _parse_block(lines, k, s_ind)
                            item_dict[sk] = nested
                        elif sv == "|":
                            k += 1
                            block, k = _collect_block_scalar(lines, k, s_ind)
                            item_dict[sk] = block
                        else:
                            item_dict[sk] = _parse_scalar(sv)
                            k += 1
                    out_list.append(item_dict)
                else:
                    out_list.append(_parse_scalar(tail))
                    k += 1
            else:
                # Continuation of previous item (should have been consumed inside the loop above)
                k += 1
        return out_list, k

    # Mapping
    out_map: dict[str, Any] = {}
    map_indent = ind
    k = j
    while k < len(lines):
        line = lines[k]
        if not line.strip():
            k += 1
            continue
        ln_ind = _indent_of(line)
        if ln_ind < map_indent:
            break
        ln_stripped = line.lstrip()
        if ":" not in ln_stripped:
            k += 1
            continue
        key, _, val = ln_stripped.partition(":")
        key = key.strip()
        val = val.strip()
        if val == "":
            k += 1
            nested, k = _parse_block(lines, k, map_indent)
            out_map[key] = nested
        elif val == "|":
            k += 1
            block, k = _collect_block_scalar(lines, k, map_indent)
            out_map[key] = block
        else:
            out_map[key] = _parse_scalar(val)
            k += 1
    return out_map, k


def parse(text: str) -> tuple[dict[str, Any], str]:
    """Parse `text` and return (frontmatter_dict, body_str)."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        end2 = text.find("\n---", 4)
        if end2 < 0:
            return {}, text
        end = end2
    fm_block = text[4:end]
    rest_start = text.find("\n", end + 4)
    body = text[rest_start + 1 :] if rest_start > 0 else ""

    lines = fm_block.splitlines()
    meta: dict[str, Any] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if _indent_of(line) > 0:
            # Not a top-level key (shouldn't happen at top level after a block parse)
            i += 1
            continue
        if ":" not in line:
            i += 1
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if val == "":
            i += 1
            nested, i = _parse_block(lines, i, 0)
            meta[key] = nested
        elif val == "|":
            i += 1
            block, i = _collect_block_scalar(lines, i, 0)
            meta[key] = block
        else:
            meta[key] = _parse_scalar(val)
            i += 1
    return meta, body


def _render_scalar(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    needs_quote = any(c in s for c in [":", "#"]) or s.startswith(("-", "[", "{", "!", "|", ">", "?", "*", "&"))
    if needs_quote:
        esc = s.replace('"', '\\"')
        return f'"{esc}"'
    return s


def render(meta: dict[str, Any]) -> str:
    """Render frontmatter dict as `---\\n...\\n---\\n` block."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            if not v:
                lines.append(f"{k}: []")
            else:
                lines.append(f"{k}:")
                for item in v:
                    if isinstance(item, dict):
                        # Render dict items as block-mapping under `-`
                        first = True
                        for ik, iv in item.items():
                            iv_rendered = _render_scalar(iv)
                            # Multi-line scalars get block-literal
                            if isinstance(iv, str) and "\n" in iv:
                                prefix = "  - " if first else "    "
                                lines.append(f"{prefix}{ik}: |")
                                for ln in iv.splitlines():
                                    lines.append(f"      {ln}")
                            else:
                                prefix = "  - " if first else "    "
                                lines.append(f"{prefix}{ik}: {iv_rendered}")
                            first = False
                    else:
                        lines.append(f"  - {_render_scalar(item)}")
        elif isinstance(v, dict):
            lines.append(f"{k}:")
            for sk, sv in v.items():
                if isinstance(sv, str) and "\n" in sv:
                    lines.append(f"  {sk}: |")
                    for ln in sv.splitlines():
                        lines.append(f"    {ln}")
                else:
                    lines.append(f"  {sk}: {_render_scalar(sv)}")
        elif isinstance(v, str) and "\n" in v:
            lines.append(f"{k}: |")
            for ln in v.splitlines():
                lines.append(f"  {ln}")
        else:
            rs = _render_scalar(v)
            if rs == "":
                lines.append(f"{k}:")
            else:
                lines.append(f"{k}: {rs}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def update_in_text(text: str, updates: dict[str, Any]) -> str:
    """Parse, merge updates into frontmatter, re-render preserving body."""
    meta, body = parse(text)
    meta.update(updates)
    return render(meta) + body
