#!/usr/bin/env python3
"""Discover likely quality commands for a repository.

This helper does not execute commands. It inspects common project metadata and
prints POSIX-shell candidate checks for a human/Codex agent to choose from.
"""

from __future__ import annotations

import argparse
import configparser
import json
import re
import shlex
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

try:
    import tomllib
except ImportError:  # pragma: no cover - exercised on Python < 3.11.
    tomllib = None


CANONICAL_CHECKS = [
    "test",
    "lint",
    "typecheck",
    "check",
    "build",
]

SCRIPT_PRIORITY = [
    "test",
    "test:unit",
    "test:integration",
    "test:e2e",
    "typecheck",
    "type-check",
    "lint",
    "check",
    "build",
    "format:check",
]

MAKE_TARGET_PRIORITY = [
    *CANONICAL_CHECKS,
    "type-check",
    "fmt-check",
    "format-check",
]

CI_PATHS = [
    ".github/workflows",
    ".circleci",
    ".gitlab-ci.yml",
    "azure-pipelines.yml",
    "buildkite.yml",
]


@dataclass(frozen=True)
class Candidate:
    command: str
    source: str
    reason: str


@dataclass(frozen=True)
class WarningItem:
    source: str
    message: str


@dataclass(frozen=True)
class Discovery:
    commands: list[Candidate]
    warnings: list[WarningItem]
    ci: list[str]


def existing(path: Path, names: Iterable[str]) -> list[Path]:
    return [path / name for name in names if (path / name).exists()]


def package_runner(package_json: dict) -> tuple[str | None, WarningItem | None]:
    raw = package_json.get("packageManager")
    if raw is None:
        return "npm", WarningItem(
            "package.json",
            "packageManager unset; defaulting command suggestions to npm, verify the repo runner before executing",
        )

    manager = str(raw).strip().lower().split("@", 1)[0]
    # Allow-list is load-bearing: candidates are printed as shell strings for humans.
    if manager in {"npm", "pnpm", "yarn", "bun"}:
        return manager, None
    return None, WarningItem(
        "package.json",
        f"unrecognized packageManager value `{raw}`; skipping package script suggestions",
    )


def script_command(runner: str, script: str) -> str:
    # Runner is allow-listed by package_runner; script names remain shell-quoted.
    if runner == "npm":
        return f"npm run {shlex.quote(script)}"
    return f"{runner} run {shlex.quote(script)}"


def discover_package_json(root: Path) -> tuple[list[Candidate], list[WarningItem]]:
    path = root / "package.json"
    if not path.exists():
        return [], []
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return [], [WarningItem("package.json", f"could not parse package.json: {exc}")]

    scripts = data.get("scripts", {})
    if not isinstance(scripts, dict):
        return [], []

    runner, package_manager_warning = package_runner(data)
    candidates: list[Candidate] = []
    warnings: list[WarningItem] = []
    if package_manager_warning is not None:
        warnings.append(package_manager_warning)
    if runner is None:
        return [], warnings
    seen: set[str] = set()
    for name in SCRIPT_PRIORITY:
        if name in scripts:
            seen.add(name)
            candidates.append(
                Candidate(script_command(runner, name), "package.json", f"script `{name}` exists")
            )

    for name in sorted(scripts):
        lowered = name.lower()
        if name in seen:
            continue
        if any(token in lowered for token in ("test", "lint", "type", "check", "build")):
            candidates.append(
                Candidate(script_command(runner, name), "package.json", f"quality-like script `{name}` exists")
            )
    return candidates, warnings


def discover_python(root: Path) -> tuple[list[Candidate], list[WarningItem]]:
    markers = existing(root, ["pyproject.toml", "pytest.ini", "tox.ini", "setup.cfg"])
    has_tests = any((root / name).exists() for name in ("tests", "test"))
    candidates: list[Candidate] = []
    warnings: list[WarningItem] = []

    if has_tests:
        candidates.append(Candidate("pytest", "tests/", "tests directory found"))

    for path in markers:
        if path.name == "pyproject.toml":
            pyproject_candidates, pyproject_warnings = discover_pyproject(path)
            candidates.extend(pyproject_candidates)
            warnings.extend(pyproject_warnings)
        elif path.name in {"pytest.ini", "tox.ini", "setup.cfg"}:
            candidates.extend(discover_python_ini(path))
    return candidates, warnings


def discover_pyproject(path: Path) -> tuple[list[Candidate], list[WarningItem]]:
    if tomllib is None:
        return [], [
            WarningItem(
                path.name,
                "tomllib unavailable on Python < 3.11; pyproject.toml discovery skipped",
            )
        ]
    try:
        data = tomllib.loads(safe_read(path))
    except tomllib.TOMLDecodeError:
        return [], []

    tool = data.get("tool", {})
    if not isinstance(tool, dict):
        return [], []

    candidates: list[Candidate] = []
    pytest_tool = tool.get("pytest")
    if isinstance(pytest_tool, dict) and "ini_options" in pytest_tool:
        candidates.append(Candidate("pytest", path.name, "[tool.pytest.ini_options] found"))
    if "ruff" in tool:
        candidates.append(Candidate("ruff check .", path.name, "[tool.ruff] found"))
    if "mypy" in tool:
        candidates.append(Candidate("mypy .", path.name, "[tool.mypy] found"))
    if "pyright" in tool:
        candidates.append(Candidate("pyright", path.name, "[tool.pyright] found"))
    return candidates, []


def discover_python_ini(path: Path) -> list[Candidate]:
    parser = configparser.ConfigParser()
    try:
        parser.read_string(safe_read(path))
    except configparser.Error:
        return []

    sections = {section.lower() for section in parser.sections()}
    candidates: list[Candidate] = []
    if path.name == "pytest.ini" or "tool:pytest" in sections or "pytest" in sections:
        candidates.append(Candidate("pytest", path.name, "pytest configuration section found"))
    if "tool:ruff" in sections or "ruff" in sections:
        candidates.append(Candidate("ruff check .", path.name, "ruff configuration section found"))
    if "mypy" in sections or "tool:mypy" in sections:
        candidates.append(Candidate("mypy .", path.name, "mypy configuration section found"))
    if "pyright" in sections or "tool:pyright" in sections:
        candidates.append(Candidate("pyright", path.name, "pyright configuration section found"))
    return candidates


def discover_make(root: Path) -> list[Candidate]:
    path = root / "Makefile"
    if not path.exists():
        return []

    targets: set[str] = set()
    for line in safe_read(path).splitlines():
        if not line:
            continue
        # NOTE: backslash-continuation .PHONY declarations are not parsed.
        if line.startswith(".PHONY:"):
            for token in line.partition(":")[2].split():
                if re.fullmatch(r"[A-Za-z0-9_.-]+", token):
                    targets.add(token)
            continue
        if line.startswith(("\t", ".")):
            continue
        head, sep, _ = line.partition(":")
        if not sep or "=" in head:
            continue
        for token in head.split():
            if re.fullmatch(r"[A-Za-z0-9_.-]+", token):
                targets.add(token)

    candidates: list[Candidate] = []
    for target in MAKE_TARGET_PRIORITY:
        if target in targets:
            candidates.append(Candidate(f"make {target}", "Makefile", f"target `{target}` exists"))
    return candidates


def discover_common(root: Path) -> list[Candidate]:
    candidates: list[Candidate] = []
    if (root / "Cargo.toml").exists():
        candidates.extend(
            [
                Candidate("cargo test", "Cargo.toml", "Rust crate/workspace found"),
                Candidate("cargo fmt --check", "Cargo.toml", "Rust formatting check is commonly paired with cargo projects"),
                Candidate("cargo clippy --all-targets --all-features", "Cargo.toml", "Rust lint command is commonly paired with cargo projects"),
            ]
        )
    if (root / "go.mod").exists():
        candidates.extend(
            [
                Candidate("go test ./...", "go.mod", "Go module found"),
                Candidate("gofmt -l .", "go.mod", "Go formatting check is commonly paired with Go modules"),
                Candidate("go vet ./...", "go.mod", "Go static analysis command is commonly paired with Go modules"),
            ]
        )
    return candidates


def discover_ci(root: Path) -> list[str]:
    found: list[str] = []
    for name in CI_PATHS:
        path = root / name
        if path.exists():
            found.append(name)
    return found


def safe_read(path: Path) -> str:
    try:
        return path.read_text(errors="replace")
    except OSError:
        return ""


def dedupe(candidates: Iterable[Candidate]) -> list[Candidate]:
    by_command: dict[str, Candidate] = {}
    result: list[Candidate] = []
    for candidate in candidates:
        existing_candidate = by_command.get(candidate.command)
        if existing_candidate is None:
            by_command[candidate.command] = candidate
            result.append(candidate)
            continue
        merged = Candidate(
            candidate.command,
            merge_unique(existing_candidate.source, candidate.source),
            merge_unique(existing_candidate.reason, candidate.reason, separator="; "),
        )
        by_command[candidate.command] = merged
        result[result.index(existing_candidate)] = merged
    return result


def merge_unique(left: str, right: str, *, separator: str = ", ") -> str:
    values = []
    for value in [*left.split(separator), *right.split(separator)]:
        if value and value not in values:
            values.append(value)
    return separator.join(values)


def render_markdown(root: Path, candidates: list[Candidate], warnings: list[WarningItem], ci_files: list[str]) -> str:
    lines = [f"# QA Command Discovery: {root}", ""]
    if warnings:
        lines.append("## Warnings")
        for warning in warnings:
            lines.append(f"- `{warning.source}` - {warning.message}")
        lines.append("")

    if candidates:
        lines.append("## Candidate Commands")
        for candidate in candidates:
            lines.append(f"- `{candidate.command}` ({candidate.source}) - {candidate.reason}")
    else:
        lines.append("No candidate commands found from common project metadata.")

    if ci_files:
        lines.extend(["", "## CI Configs To Inspect"])
        for item in ci_files:
            lines.append(f"- `{item}`")

    lines.extend(
        [
            "",
            "These are candidates, not proof they should all run. Choose commands based on changed files and risk tier.",
        ]
    )
    return "\n".join(lines)


def discover(root: Path) -> Discovery:
    package_candidates, package_warnings = discover_package_json(root)
    python_candidates, python_warnings = discover_python(root)
    commands = dedupe(
        [
            *package_candidates,
            *python_candidates,
            *discover_make(root),
            *discover_common(root),
        ]
    )
    return Discovery(commands=commands, warnings=[*package_warnings, *python_warnings], ci=discover_ci(root))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", help="repository root to inspect")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of Markdown")
    args = parser.parse_args(argv)

    root = Path(args.root).expanduser().resolve()
    result = discover(root)

    if args.json:
        print(json.dumps({
            "root": str(root),
            "commands": [asdict(item) for item in result.commands],
            "warnings": [asdict(item) for item in result.warnings],
            "ci": result.ci,
        }, indent=2))
    else:
        print(render_markdown(root, result.commands, result.warnings, result.ci))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
