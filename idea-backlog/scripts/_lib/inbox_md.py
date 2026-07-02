"""Read/write helpers for MattZerg/Tasks/inbox.md.

The file uses markdown tables under bucket headers:
  ## To Do                                   → 4-col table (#, Item, Domain, Why now)
  ## Should Do                               → 4-col (same)
  ## Reminders / Alerts / Opportunities      → varies
  ## Relevant Ideas                          → has ### sub-buckets, 3-col (#, Idea, Note / Source)
  ## Done                                    → 4-col (Item, Domain, Completed, Note)

Goal: parse rows in a way that lets us locate a target by # OR by substring of
Item, and replace its row with a strikethrough+link line. Also append a new
row at the bottom of a chosen bucket's table.

This is intentionally light — we do NOT preserve perfect formatting; we
rewrite the affected table cleanly while leaving non-table sections untouched.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from vault_paths import TASKS_INBOX

H2_RE = re.compile(r"^##\s+(?P<title>.+?)\s*$")
H3_RE = re.compile(r"^###\s+(?P<title>.+?)\s*$")


@dataclass
class Row:
    cells: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "| " + " | ".join(self.cells) + " |"


@dataclass
class Section:
    h2: str
    h3: str | None
    pre_lines: list[str] = field(default_factory=list)  # lines before the table
    header: list[str] = field(default_factory=list)  # table header cells
    sep: str = ""  # the "|---|---|" line as-is
    rows: list[Row] = field(default_factory=list)
    post_lines: list[str] = field(default_factory=list)  # blank lines / paragraph after table

    def has_table(self) -> bool:
        return bool(self.header)

    def find_row(self, needle: str) -> int | None:
        """Return row index matching by # cell or by substring in any cell (case-insensitive)."""
        needle_l = needle.strip().lower()
        for i, r in enumerate(self.rows):
            if not r.cells:
                continue
            first = r.cells[0].strip()
            if first == needle_l or first == needle:
                return i
            for c in r.cells:
                if needle_l in c.lower():
                    return i
        return None


def _split_row(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def parse() -> list[Section]:
    """Parse Tasks/inbox.md into ordered sections (one per h2 / h3 with a table)."""
    if not TASKS_INBOX.exists():
        return []
    lines = TASKS_INBOX.read_text().splitlines()
    sections: list[Section] = []
    cur = Section(h2="(preamble)", h3=None)

    in_table = False
    for line in lines:
        h2 = H2_RE.match(line)
        h3 = H3_RE.match(line)
        if h2:
            sections.append(cur)
            cur = Section(h2=h2.group("title"), h3=None, pre_lines=[line])
            in_table = False
            continue
        if h3:
            sections.append(cur)
            cur = Section(h2=cur.h2, h3=h3.group("title"), pre_lines=[line])
            in_table = False
            continue
        s = line.strip()
        is_table_line = s.startswith("|") and s.endswith("|")
        if is_table_line:
            cells = _split_row(line)
            if not cur.header:
                cur.header = cells
            elif not cur.sep and set("".join(cells)) <= set("- :"):
                cur.sep = line
            else:
                cur.rows.append(Row(cells=cells))
            in_table = True
        else:
            if in_table:
                cur.post_lines.append(line)
            else:
                cur.pre_lines.append(line)
    sections.append(cur)
    # First section is preamble — drop empty
    return [s for s in sections if s.pre_lines or s.header]


def render(sections: list[Section]) -> str:
    out: list[str] = []
    for sec in sections:
        out.extend(sec.pre_lines)
        if sec.has_table():
            out.append("| " + " | ".join(sec.header) + " |")
            if sec.sep:
                out.append(sec.sep)
            else:
                out.append("|" + "|".join(["---"] * len(sec.header)) + "|")
            for r in sec.rows:
                out.append(r.text)
        out.extend(sec.post_lines)
    return "\n".join(out).rstrip() + "\n"


def find_section(sections: list[Section], h2: str, h3: str | None = None) -> Section | None:
    for s in sections:
        if s.h2 == h2 and (h3 is None or s.h3 == h3):
            return s
    return None


def find_row_anywhere(sections: list[Section], needle: str) -> tuple[Section, int] | None:
    for s in sections:
        if not s.has_table():
            continue
        idx = s.find_row(needle)
        if idx is not None:
            return s, idx
    return None


def write(sections: list[Section]) -> None:
    TASKS_INBOX.write_text(render(sections))
