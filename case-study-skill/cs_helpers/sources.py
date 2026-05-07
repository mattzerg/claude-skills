"""Vault-side evidence gathering for the case-study skill.

`gather_evidence(client, vault_root)` walks a deterministic priority list of vault
locations and returns:

  (evidence_blob, evidence_meta)

`evidence_blob` is a single string of provenance-tagged snippets ready to splice
into a Claude prompt. `evidence_meta` is a small dict with counts so the
session-summary file can report how much was actually found.

Linear / Zergboard pulls are intentionally NOT done here — those skills already
exist as siblings, and the case-study skill defers to the agent (or a follow-up
manual step) to enrich the brief with tracker data. The capture prompt instructs
the model to emit `gaps[]` entries pointing at trackers that should be queried.
"""
from __future__ import annotations

import re
from pathlib import Path

# Priority-ordered vault locations to scan for client mentions.
# Each entry is (relative_path_from_vault_root, weight, scan_kind).
#   scan_kind: "file"     — read the whole file if it exists
#              "table_row"— read the file, extract rows mentioning the client
#              "grep_dir" — recursive grep within a directory, with a per-file snippet limit
SOURCE_RULES: list[tuple[str, str, str]] = [
    ("Companies/{client}.md",                                    "HIGH",   "file"),
    ("Epoch/Projects/Client Pipeline.md",                        "HIGH",   "table_row"),
    ("Epoch/Projects/Product Glossary.md",                       "HIGH",   "table_row"),
    ("Notes/Testimonials.md",                                    "HIGH",   "table_row"),
    ("Conversations/Claude",                                     "MEDIUM", "grep_dir"),
    ("Conversations/Slack",                                      "MEDIUM", "grep_dir"),
    ("Roadmap",                                                  "MEDIUM", "grep_dir"),
    ("Projects",                                                 "MEDIUM", "grep_dir"),
]

# Cap how much we splice into the prompt, both per-file and overall.
PER_FILE_SNIPPET_CHARS = 2_500
PER_DIR_FILE_LIMIT = 8
TOTAL_BLOB_CHAR_BUDGET = 60_000


def slugify(text: str) -> str:
    """Same convention as the launch-announcement skill — lowercase, alnum, hyphenated."""
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:60] or "engagement").rstrip("-")


def _grep_table_rows(path: Path, client: str) -> str:
    """Return lines mentioning the client (case-insensitive) plus 1 line of context above."""
    if not path.exists():
        return ""
    needle = client.lower()
    out_lines: list[str] = []
    lines = path.read_text(errors="replace").splitlines()
    for i, line in enumerate(lines):
        if needle in line.lower():
            ctx_start = max(0, i - 1)
            ctx_end = min(len(lines), i + 4)
            chunk = "\n".join(lines[ctx_start:ctx_end])
            out_lines.append(f"L{i+1}:\n{chunk}")
    return "\n\n".join(out_lines)[:PER_FILE_SNIPPET_CHARS]


def _grep_dir(dirpath: Path, client: str) -> list[tuple[Path, str]]:
    """Find files in dirpath containing client name; return list of (file_path, snippet)."""
    if not dirpath.exists() or not dirpath.is_dir():
        return []
    needle = client.lower()
    hits: list[tuple[Path, str]] = []
    for path in sorted(dirpath.rglob("*.md")):
        try:
            text = path.read_text(errors="replace")
        except (OSError, UnicodeDecodeError):
            continue
        if needle not in text.lower():
            continue
        # Pull out a focused snippet around the first match, with surrounding context.
        idx = text.lower().find(needle)
        start = max(0, idx - 600)
        end = min(len(text), idx + 1200)
        snippet = text[start:end]
        if start > 0:
            snippet = "…" + snippet
        if end < len(text):
            snippet = snippet + "…"
        hits.append((path, snippet[:PER_FILE_SNIPPET_CHARS]))
        if len(hits) >= PER_DIR_FILE_LIMIT:
            break
    return hits


def gather_evidence(client: str, *, vault_root: Path) -> tuple[str, dict]:
    """Walk SOURCE_RULES and assemble a provenance-tagged evidence blob."""
    sections: list[str] = []
    sources_scanned = 0
    snippets = 0

    for rel_pattern, weight, kind in SOURCE_RULES:
        sources_scanned += 1
        if kind == "file":
            # The {client} placeholder may need different casings; try a few.
            candidates = [
                vault_root / rel_pattern.format(client=client),
                vault_root / rel_pattern.format(client=client.title()),
                vault_root / rel_pattern.format(client=slugify(client).replace("-", "")),
            ]
            for path in candidates:
                if path.exists():
                    sections.append(_format_section(path, weight, path.read_text(errors="replace")[:PER_FILE_SNIPPET_CHARS]))
                    snippets += 1
                    break

        elif kind == "table_row":
            path = vault_root / rel_pattern
            chunk = _grep_table_rows(path, client)
            if chunk:
                sections.append(_format_section(path, weight, chunk, hint="rows-mentioning-client"))
                snippets += 1

        elif kind == "grep_dir":
            dirpath = vault_root / rel_pattern
            for path, snippet in _grep_dir(dirpath, client):
                sections.append(_format_section(path, weight, snippet, hint="snippet-around-first-mention"))
                snippets += 1

        # Budget cap.
        if sum(len(s) for s in sections) > TOTAL_BLOB_CHAR_BUDGET:
            sections.append(
                f"\n[BUDGET CAP REACHED — stopped scanning at source #{sources_scanned}. "
                f"{snippets} snippets gathered. Run again with a narrower client name to dig deeper.]\n"
            )
            break

    if not sections:
        sections.append(
            f"NO EVIDENCE FOUND for client '{client}' in the standard vault locations. "
            "The brief should flag this as a hard gap: capture cannot proceed without raw material. "
            "Suggest the user create at least a `Companies/<client>.md` stub and add a row to "
            "`Epoch/Projects/Client Pipeline.md` before re-running."
        )

    blob = "\n\n".join(sections)
    meta = {
        "sources_scanned": sources_scanned,
        "snippets": snippets,
        "blob_chars": len(blob),
    }
    return blob, meta


def _format_section(path: Path, weight: str, body: str, *, hint: str | None = None) -> str:
    header = f"### SOURCE: {path}\nWEIGHT: {weight}"
    if hint:
        header += f"\nHINT: {hint}"
    return f"{header}\n\n{body.strip()}"
