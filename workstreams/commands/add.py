#!/usr/bin/env python3
"""Append a new workstream to the manifest, interactively or from CLI args.

Usage:
  add.py                                                 # interactive prompts
  add.py --id <id> --name "<name>" [--scope zerg|personal|mixed]
        [--keyword foo --keyword bar] [--vault MattZerg/X]
        [--text-regex 'pat'] [--cwd ~/some/dir] [--notes 'why']

Writes to ~/.config/zerg/workstreams.yaml just BEFORE the catchall entry.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


MANIFEST = Path.home() / ".config" / "zerg" / "workstreams.yaml"


def _prompt(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"{prompt}{suffix}: ").strip()
    return val or default


def _yaml_block(args) -> str:
    lines = [
        f"  - id: {args.id}",
        f"    name: \"{args.name}\"",
        f"    scope: {args.scope}",
        "    status: active",
    ]
    if args.notes:
        lines.append(f"    notes: \"{args.notes}\"")
    sel_lines: list[str] = []
    if args.text_regex:
        sel_lines.append(f"      inbox_text_regex: \"{args.text_regex}\"")
    if args.domain_regex:
        sel_lines.append(f"      inbox_domain_regex: \"{args.domain_regex}\"")
    if args.vault:
        sel_lines.append("      vault_folders:")
        for v in args.vault:
            sel_lines.append(f"        - \"{v}\"")
    if args.pr_repo:
        sel_lines.append("      pr_repos: [" + ", ".join(args.pr_repo) + "]")
    if sel_lines:
        lines.append("    selectors:")
        lines.extend(sel_lines)
    sess_lines = []
    if args.cwd:
        sess_lines.append(f"      cwd: \"{args.cwd}\"")
    if args.keyword:
        sess_lines.append("      name_keywords: [" + ", ".join(f"\"{k}\"" for k in args.keyword) + "]")
    if sess_lines:
        lines.append("    session:")
        lines.extend(sess_lines)
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="add a workstream to the manifest")
    parser.add_argument("--id")
    parser.add_argument("--name")
    parser.add_argument("--scope", default="zerg", choices=["zerg", "personal", "mixed"])
    parser.add_argument("--keyword", action="append", default=[])
    parser.add_argument("--vault", action="append", default=[])
    parser.add_argument("--text-regex", default="")
    parser.add_argument("--domain-regex", default="")
    parser.add_argument("--pr-repo", action="append", default=[])
    parser.add_argument("--cwd", default="")
    parser.add_argument("--notes", default="")
    args = parser.parse_args(argv)

    if not args.id:
        args.id = _prompt("workstream id (kebab-case, e.g. 'new-thing')")
    if not re.match(r"^[a-z][a-z0-9-]*$", args.id or ""):
        print(f"invalid id: {args.id!r} — must be kebab-case [a-z][a-z0-9-]*", file=sys.stderr)
        return 1
    if not args.name:
        args.name = _prompt("display name", default=args.id.replace("-", " ").title())
    if not any([args.text_regex, args.domain_regex, args.vault, args.keyword, args.pr_repo]):
        print("(at least one selector recommended; press enter to skip)")
        if not args.text_regex:
            args.text_regex = _prompt("inbox text regex (matches Item text)")
        if not args.domain_regex:
            args.domain_regex = _prompt("inbox Domain-column regex")
        if not args.keyword:
            kw = _prompt("session name keywords (comma-separated)")
            args.keyword = [k.strip() for k in kw.split(",") if k.strip()]

    text = MANIFEST.read_text()
    # Insert just before the first `- id: <catchall>` line (find catchall by `catchall: true`)
    # We simply look for the workstream that has catchall: true and insert above it.
    pattern = re.compile(r"(\n  - id: \S+\n(?:.*\n)*?    catchall: true\b)")
    m = pattern.search(text)
    if not m:
        print("could not locate catchall entry in manifest; aborting", file=sys.stderr)
        return 2
    block = "\n" + _yaml_block(args)
    new_text = text[:m.start()] + block + text[m.start():]
    MANIFEST.write_text(new_text)
    print(f"appended workstream {args.id!r} to {MANIFEST}")
    print()
    print("validating manifest...")
    import subprocess
    return subprocess.call(["/usr/bin/python3", str(Path.home() / ".claude" / "workstreams" / "collect.py"), "--validate-manifest"])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
