#!/usr/bin/env python3
"""creative-prereq: pre-flight ritual gate before creative artifact generation.

Sibling to pr-gate (code) / send-gate (email) / qa-gate (engineering). Forces the
"brainstorm 3, pick one, check rules, write prompt, self-review, fire, review"
ritual BEFORE any image/prose/social/video generation tool fires.

Usage:
    creative-prereq prepare <artifact-type> --slug <slug> [--source <path>]
    creative-prereq validate <checklist-path>
    creative-prereq gate --slug <slug> [--artifact-type hero-image]

artifact-type: hero-image | prose-draft | social-copy | video-shot-list | other

The `gate` subcommand is invoked by a PreToolUse hook in ~/.claude/settings.json
before any creative-tool bash invocation. It honors CREATIVE_PREREQ_BYPASS=1 env
var for genuine one-offs (testing prompts, debugging renderers); otherwise it
requires a fresh (<6h) complete checklist at /tmp/creative-prereq/<slug>-*.md.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path

SKILL_DIR = Path(__file__).parent
CHECKLIST_DIR = SKILL_DIR / "checklists"
WORK_DIR = Path("/tmp/creative-prereq")
LOG_PATH = Path.home() / ".claude/creative-prereq/log.jsonl"
GATE_STALENESS_SECONDS = 6 * 60 * 60  # 6 hours
BYPASS_ENV_VAR = "CREATIVE_PREREQ_BYPASS"


def prepare(artifact_type: str, slug: str, source: str = "") -> Path:
    """Stage a checklist for an artifact. Returns path to the new checklist."""
    template = CHECKLIST_DIR / f"{artifact_type}.md"
    if not template.exists():
        # Fall back to hero-image template for unknown types
        template = CHECKLIST_DIR / "hero-image.md"
        if not template.exists():
            print(f"ERROR: no template for artifact-type={artifact_type}", file=sys.stderr)
            return Path()

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    out_path = WORK_DIR / f"{slug}-{artifact_type}.checklist.md"

    body = template.read_text()
    body = body.replace("{{SLUG}}", slug)
    body = body.replace("{{SOURCE}}", source or "(not provided)")
    body = body.replace("{{DATE}}", dt.datetime.now().strftime("%Y-%m-%d %H:%M %Z"))

    out_path.write_text(body)
    _log("prepare", {"artifact_type": artifact_type, "slug": slug, "path": str(out_path)})
    return out_path


def validate(checklist_path: Path) -> tuple[bool, list[str]]:
    """Validate that a checklist is fully filled in (no [TO FILL] markers left).

    Returns (passed, violations). violations is a list of section labels that
    still contain [TO FILL] markers.
    """
    if not checklist_path.exists():
        return False, [f"checklist not found: {checklist_path}"]
    text = checklist_path.read_text()
    # Find all [TO FILL] occurrences, with surrounding context
    violations: list[str] = []
    current_section = "(preamble)"
    for line in text.splitlines():
        if line.startswith("## Step "):
            current_section = line.strip("# ").strip()
        if "[TO FILL]" in line:
            violations.append(f"{current_section}: {line.strip()[:120]}")
    passed = len(violations) == 0
    _log("validate", {
        "path": str(checklist_path),
        "passed": passed,
        "violation_count": len(violations),
    })
    return passed, violations


GATE_STALENESS_SECONDS = 6 * 60 * 60
BYPASS_ENV_VAR = "CREATIVE_PREREQ_BYPASS"


def gate(slug: str, artifact_type: str = "hero-image") -> tuple[bool, str]:
    """PreToolUse gate: block creative-tool calls without a fresh checklist.

    Honors CREATIVE_PREREQ_BYPASS=1 env var for genuine one-offs. Otherwise
    requires /tmp/creative-prereq/<slug>-<artifact-type>.checklist.md to exist,
    be complete (no [TO FILL] markers), and be fresh (mtime within 6 hours).
    """
    import os, time
    if os.environ.get(BYPASS_ENV_VAR) == "1":
        _log("gate", {"slug": slug, "passed": True, "bypass": True})
        return True, f"[creative-prereq] BYPASS via {BYPASS_ENV_VAR}=1 — gate skipped"

    checklist_path = WORK_DIR / f"{slug}-{artifact_type}.checklist.md"
    if not checklist_path.exists():
        _log("gate", {"slug": slug, "passed": False, "reason": "missing"})
        return False, (
            f"[creative-prereq] GATE BLOCKED: no checklist at {checklist_path}\n"
            f"  Run: creative-prereq prepare {artifact_type} --slug {slug}\n"
            f"  Override (one-off only): prefix with {BYPASS_ENV_VAR}=1"
        )

    age = time.time() - checklist_path.stat().st_mtime
    if age > GATE_STALENESS_SECONDS:
        _log("gate", {"slug": slug, "passed": False, "reason": "stale", "age_h": age / 3600})
        return False, (
            f"[creative-prereq] GATE BLOCKED: checklist stale ({age/3600:.1f}h old, max 6h)\n"
            f"  Path: {checklist_path}\n"
            f"  Re-validate or `touch {checklist_path}` if decisions still apply"
        )

    passed, violations = validate(checklist_path)
    if not passed:
        _log("gate", {"slug": slug, "passed": False, "reason": "incomplete", "n": len(violations)})
        msg = f"[creative-prereq] GATE BLOCKED: {len(violations)} [TO FILL] markers in {checklist_path}"
        for v in violations[:5]:
            msg += f"\n    - {v}"
        if len(violations) > 5:
            msg += f"\n    ... +{len(violations) - 5} more"
        return False, msg

    marker = WORK_DIR / f"{slug}.gate-passed"
    marker.write_text(dt.datetime.now().isoformat(timespec="seconds") + "\n")
    _log("gate", {"slug": slug, "passed": True, "checklist": str(checklist_path)})
    return True, f"[creative-prereq] GATE PASSED for slug={slug} (age {age/60:.0f}min)"


def _log(action: str, payload: dict) -> None:
    """Append to ~/.claude/creative-prereq/log.jsonl. Fire-and-forget."""
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        row = {"ts": dt.datetime.now().isoformat(timespec="seconds"), "action": action, **payload}
        with LOG_PATH.open("a") as f:
            f.write(json.dumps(row) + "\n")
    except OSError:
        pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="creative-prereq")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_prep = sub.add_parser("prepare", help="Stage a new pre-flight checklist")
    p_prep.add_argument("artifact_type", choices=[
        "hero-image", "prose-draft", "social-copy", "video-shot-list", "other",
    ])
    p_prep.add_argument("--slug", required=True)
    p_prep.add_argument("--source", default="")

    p_val = sub.add_parser("validate", help="Validate a checklist is fully filled in")
    p_val.add_argument("checklist", type=Path)

    p_gate = sub.add_parser("gate", help="PreToolUse gate: block creative-tool calls without a fresh checklist")
    p_gate.add_argument("--slug", required=True)
    p_gate.add_argument("--artifact-type", default="hero-image", dest="artifact_type")

    args = parser.parse_args(argv)

    if args.cmd == "prepare":
        out = prepare(args.artifact_type, args.slug, args.source)
        if not out:
            return 2
        print(f"checklist: {out}")
        print(f"open: {out}")
        return 0

    if args.cmd == "validate":
        passed, violations = validate(args.checklist)
        if passed:
            print(f"✓ checklist complete: {args.checklist}")
            return 0
        print(f"✗ checklist INCOMPLETE: {args.checklist}", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    if args.cmd == "gate":
        passed, msg = gate(args.slug, args.artifact_type)
        if passed:
            print(msg)
            return 0
        print(msg, file=sys.stderr)
        return 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
