#!/usr/bin/env python3
"""Validate installed Codex skills and common skill metadata conventions."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


AUX_DOC_NAMES = {
    "README.md",
    "CHANGELOG.md",
    "INSTALLATION_GUIDE.md",
    "QUICK_REFERENCE.md",
}
MAX_SKILL_NAME_LENGTH = 64
ALLOWED_FRONTMATTER_KEYS = {"name", "description", "license", "allowed-tools", "metadata"}


def default_root() -> Path:
    return Path.home() / ".codex" / "skills"


def find_skill_dirs(root: Path, include_system: bool) -> list[Path]:
    candidates = [p for p in root.iterdir() if p.is_dir()]
    if include_system and (root / ".system").is_dir():
        candidates.extend(p for p in (root / ".system").iterdir() if p.is_dir())
    return sorted(p for p in candidates if (p / "SKILL.md").is_file())


def find_validator(root: Path) -> Path:
    validator = root / ".system" / "skill-creator" / "scripts" / "quick_validate.py"
    if not validator.is_file():
        raise FileNotFoundError(f"Missing validator: {validator}")
    return validator


def extract_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    frontmatter = text[4:end]
    values: dict[str, str] = {}
    for line in frontmatter.splitlines():
        if ":" not in line or line.startswith(" "):
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def validate_skill_fallback(skill_dir: Path) -> tuple[bool, str]:
    """Minimal local equivalent of quick_validate.py when PyYAML is unavailable."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return False, "SKILL.md not found"

    content = skill_md.read_text()
    if not content.startswith("---"):
        return False, "No YAML frontmatter found"

    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return False, "Invalid frontmatter format"

    frontmatter = extract_frontmatter(content)
    unexpected = set(frontmatter) - ALLOWED_FRONTMATTER_KEYS
    if unexpected:
        allowed = ", ".join(sorted(ALLOWED_FRONTMATTER_KEYS))
        return (
            False,
            f"Unexpected key(s) in SKILL.md frontmatter: {', '.join(sorted(unexpected))}. "
            f"Allowed properties are: {allowed}",
        )

    if "name" not in frontmatter:
        return False, "Missing 'name' in frontmatter"
    if "description" not in frontmatter:
        return False, "Missing 'description' in frontmatter"

    name = frontmatter.get("name", "").strip()
    if not re.match(r"^[a-z0-9-]+$", name):
        return False, f"Name '{name}' should be hyphen-case"
    if name.startswith("-") or name.endswith("-") or "--" in name:
        return False, f"Name '{name}' cannot start/end with hyphen or contain consecutive hyphens"
    if len(name) > MAX_SKILL_NAME_LENGTH:
        return False, f"Name is too long ({len(name)} characters)"

    description = frontmatter.get("description", "").strip()
    if "<" in description or ">" in description:
        return False, "Description cannot contain angle brackets (< or >)"
    if len(description) > 1024:
        return False, f"Description is too long ({len(description)} characters)"

    return True, "Skill is valid! (fallback validator)"


def extract_default_prompt(metadata: str) -> str | None:
    match = re.search(r"^\s*default_prompt:\s*(.+?)\s*$", metadata, re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip().strip("'\"")


def validate_skill(skill_dir: Path, validator: Path) -> tuple[bool, str]:
    result = subprocess.run(
        [sys.executable, str(validator), str(skill_dir)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if "ModuleNotFoundError: No module named 'yaml'" in result.stdout:
        return validate_skill_fallback(skill_dir)
    return result.returncode == 0, result.stdout.strip()


def audit_skill(skill_dir: Path, validator: Path, strict_metadata: bool) -> list[str]:
    issues: list[str] = []
    skill_name = skill_dir.name

    ok, output = validate_skill(skill_dir, validator)
    if not ok:
        issues.append(f"validation failed: {output}")

    text = (skill_dir / "SKILL.md").read_text()
    frontmatter = extract_frontmatter(text)
    declared_name = frontmatter.get("name")
    if declared_name and declared_name != skill_name:
        issues.append(f"name mismatch: frontmatter has {declared_name!r}")

    metadata_path = skill_dir / "agents" / "openai.yaml"
    if metadata_path.exists():
        metadata = metadata_path.read_text()
        if not metadata.lstrip().startswith("interface:"):
            issues.append("agents/openai.yaml missing interface wrapper")
        default_prompt_value = extract_default_prompt(metadata)
        if default_prompt_value is None:
            issues.append("agents/openai.yaml missing default_prompt")
        elif f"${skill_name}" not in default_prompt_value:
            issues.append("default_prompt does not mention $skill-name")
    elif strict_metadata:
        issues.append("missing agents/openai.yaml")

    for path in skill_dir.rglob("*"):
        if path.is_file() and path.name in AUX_DOC_NAMES:
            issues.append(f"auxiliary doc present: {path.relative_to(skill_dir)}")

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_root(), help="Codex skills root")
    parser.add_argument(
        "--no-system",
        action="store_true",
        help="Skip .system skills under the skills root",
    )
    parser.add_argument(
        "--strict-metadata",
        action="store_true",
        help="Flag skills without agents/openai.yaml",
    )
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    validator = find_validator(root)
    skills = find_skill_dirs(root, include_system=not args.no_system)

    failed = 0
    for skill_dir in skills:
        issues = audit_skill(skill_dir, validator, args.strict_metadata)
        if issues:
            failed += 1
            print(f"[FAIL] {skill_dir.name}")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print(f"[OK]   {skill_dir.name}")

    print()
    print(f"Checked {len(skills)} skills; {failed} with issues.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
