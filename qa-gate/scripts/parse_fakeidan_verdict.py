#!/usr/bin/env python3
"""Extract and validate the verdict from a Fake Idan review."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ALLOWED_VERDICTS = {"Approve", "Recommend changes", "Changes requested"}
VERDICT_PATTERN = "|".join(re.escape(item) for item in sorted(ALLOWED_VERDICTS, key=len, reverse=True))
VERDICT_RE = re.compile(
    rf"^\*\*Verdict:\*\*\s*({VERDICT_PATTERN})\s*$",
)
REVIEW_HEADING_RE = re.compile(r"^# Fake Idan Review:\s+\S")


def parse_verdict(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    if not REVIEW_HEADING_RE.match(lines[0]):
        return None
    if len(lines) < 2:
        return None
    candidate = lines[1]
    match = VERDICT_RE.match(candidate)
    if not match:
        return None
    return match.group(1)


def verdict_error(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "empty review"
    if not REVIEW_HEADING_RE.match(lines[0]):
        return "missing or invalid `# Fake Idan Review: <artifact>` heading"
    if len(lines) < 2:
        return "missing exact `**Verdict:** <verdict>` line after review heading"
    if VERDICT_RE.match(lines[1]) is None:
        return "missing or invalid exact `**Verdict:** <verdict>` line after review heading"
    return None


def has_concerns_section(text: str) -> bool:
    return bool(re.search(r"^## Concerns ranked\s*$", text, flags=re.MULTILINE))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("review_file", help="Fake Idan review markdown file")
    args = parser.parse_args(argv)

    path = Path(args.review_file).expanduser()
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        parser.error(f"could not read review file: {exc}")

    error = verdict_error(text)
    if error is not None:
        parser.error(error)
    verdict = parse_verdict(text)
    if verdict is None:
        parser.error("missing or invalid exact `**Verdict:** <verdict>` line after review heading")
    if not has_concerns_section(text):
        parser.error("missing `## Concerns ranked` section")

    print(verdict)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
