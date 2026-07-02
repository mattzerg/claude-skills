#!/usr/bin/env python3
"""Smoke test for compact-session skill metadata.

Verifies the SKILL.md frontmatter and required body sections are intact.
Pattern mirrors the lightweight verification used by fakematt-copyedit and
other pure-prompt skills — no behavior simulation, just structural checks
that catch corruption / accidental edits.

Run:
    python3 ~/.claude/skills/compact-session/scripts/smoke_test.py

Exits 0 on pass, 1 on any check failure with a printed reason.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent
SKILL_MD = SKILL_DIR / "SKILL.md"
OPENAI_YAML = SKILL_DIR / "agents" / "openai.yaml"

REQUIRED_FRONTMATTER_KEYS = ("name", "description")
REQUIRED_BODY_SECTIONS = (
    "## Why this skill exists",
    "## When to invoke",
    "## Invocation",
    "## What to do when invoked",
    "### Step 1",
    "### Step 2",
    "### Step 3",
    "### Step 4",
    "## What this skill is NOT",
    "## Anti-patterns",
)
SHED_LINE_FRAGMENT = "From here forward I will work from this summary"


def fail(msg: str) -> None:
    print(f"[FAIL] compact-session smoke test: {msg}")
    sys.exit(1)


def main() -> int:
    if not SKILL_MD.is_file():
        fail(f"missing SKILL.md at {SKILL_MD}")

    text = SKILL_MD.read_text()

    # Frontmatter present + parseable.
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        fail("frontmatter missing or malformed")
    frontmatter = match.group(1)

    for key in REQUIRED_FRONTMATTER_KEYS:
        if not re.search(rf"^{re.escape(key)}\s*:", frontmatter, re.MULTILINE):
            fail(f"frontmatter missing required key: {key}")

    name_match = re.search(r"^name\s*:\s*(\S+)", frontmatter, re.MULTILINE)
    if not name_match or name_match.group(1) != "compact-session":
        fail("frontmatter 'name' must equal 'compact-session'")

    desc_match = re.search(r"^description\s*:\s*(.+)$", frontmatter, re.MULTILINE)
    if not desc_match:
        fail("frontmatter 'description' missing")
    description = desc_match.group(1)

    # Validator hard-fail: description cannot contain angle brackets.
    if "<" in description or ">" in description:
        fail("description contains angle brackets (validator will reject)")

    # Trigger condition signal must be explicit so Claude invokes proactively.
    if "USE PROACTIVELY" not in description:
        fail("description missing 'USE PROACTIVELY' trigger signal")

    # Required body sections.
    for section in REQUIRED_BODY_SECTIONS:
        if section not in text:
            fail(f"SKILL.md body missing required section: {section!r}")

    # Load-bearing shed declaration must be present verbatim.
    if SHED_LINE_FRAGMENT not in text:
        fail("SKILL.md missing the load-bearing shed declaration line")

    # openai.yaml sanity check.
    if not OPENAI_YAML.is_file():
        fail(f"missing agents/openai.yaml at {OPENAI_YAML}")
    yaml_text = OPENAI_YAML.read_text()
    if "interface:" not in yaml_text:
        fail("openai.yaml missing 'interface:' wrapper")
    if "$compact-session" not in yaml_text:
        fail("openai.yaml default_prompt should reference $compact-session")

    print("[OK] compact-session smoke test passed")
    print(f"     SKILL.md     : {SKILL_MD}")
    print(f"     openai.yaml  : {OPENAI_YAML}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
