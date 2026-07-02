"""Source-citation helpers. Every quantitative claim carries inline tag or
machine-readable citation. Client-mode deck refuses to render with surviving
`[needs-verification]` tags.
"""
from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, asdict

NEEDS_VERIFICATION = "[needs-verification]"
NV_PAT = re.compile(r"\[needs-verification\]")
INLINE_SOURCE_PAT = re.compile(r"\[source:\s*([^\]]+)\]")


@dataclass
class Citation:
    claim: str
    source: str
    url: str = ""
    accessed: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def inline(self) -> str:
        """`[source: <source>]` tag to embed inline."""
        return f"[source: {self.source}]"


def new(claim: str, source: str, url: str = "", accessed: str | None = None) -> Citation:
    return Citation(
        claim=claim,
        source=source,
        url=url,
        accessed=accessed or _dt.date.today().isoformat(),
    )


def needs_verification(text: str) -> bool:
    """Return True if any `[needs-verification]` tag remains in the text."""
    return bool(NV_PAT.search(text))


def count_unverified(text: str) -> int:
    return len(NV_PAT.findall(text))


def extract_inline_sources(text: str) -> list[str]:
    """Return the list of source labels found inline as `[source: ...]`."""
    return INLINE_SOURCE_PAT.findall(text)


def validate_for_client(text: str) -> tuple[bool, str]:
    """Return (ok, reason). Client-mode deliverable must have zero `[needs-verification]` tags."""
    n = count_unverified(text)
    if n:
        return (False, f"{n} `[needs-verification]` tag(s) present — block client deliverable")
    return (True, "ok")
