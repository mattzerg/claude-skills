#!/usr/bin/env python3
"""Send gate — lightweight pre-flight before `gmail-skill send`.

Per feedback_gate_thresholds.md: this gate is intentionally MUCH lighter than
pr-gate. Soft-warn by default; hard-block only with --strict.

Usage:
    python3 ~/.claude/skills/send-gate/run.py [gmail-skill-send-args] [gate-flags]

Gate flags:
    --strict       hard-block on any soft-warn (default: warn + send)
    --dry-run      run gate, print findings, do NOT send
    --skip-gate    bypass entirely (logged)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).parent
LOG = SKILL_DIR / "logs" / "sends.log"
GMAIL_SKILL = Path.home() / ".claude" / "skills" / "gmail-skill" / "gmail_skill.py"
TIER_MAP = Path.home() / ".claude" / "skills" / "fakematt-email" / "tier_map.json"

# AI-template anti-patterns — the gate's main value
ANTI_PATTERNS = [
    (re.compile(r"i hope this email finds you well", re.I),
     'Use "Hope all is well!" instead — the AI-template version is a Matt anti-pattern.'),
    (re.compile(r"please don'?t hesitate to reach out", re.I),
     'Use "Let me know if you have any questions" — the "don\'t hesitate" form is templatey.'),
    (re.compile(r"^\s*(Sincerely|Regards|Kind regards|Warm regards|Best regards),?\s*$", re.M | re.I),
     'Use "Best," — formal closers are off-voice for Matt.'),
    (re.compile(r"\b[A-Z]{4,}\b"),
     "ALL-CAPS for emphasis is off-voice — use *italics* (asterisks) instead."),
    (re.compile(r"\bI trust this finds you\b", re.I),
     'Same family as "hope this email finds you well" — anti-pattern. Drop or rephrase.'),
]

# AI-coauthor lines to silently scrub (never appear in outbound)
COAUTHOR_PATTERNS = [
    re.compile(r"^Co-Authored-By:\s*Claude.*$", re.I | re.M),
    re.compile(r"^.*Generated with Claude Code.*$", re.I | re.M),
    re.compile(r"^.*Co-Authored-By:\s*Claude\s*<[^>]*>.*$", re.I | re.M),
]


def parse_args():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-gate", action="store_true")
    args, passthrough = ap.parse_known_args()
    return args, passthrough


def extract_field(passthrough: list[str], flag_short: str, flag_long: str) -> str | None:
    """Find the value for --to / --body / etc in the passthrough list."""
    for i, arg in enumerate(passthrough):
        if arg in (flag_long, flag_short):
            if i + 1 < len(passthrough):
                return passthrough[i + 1]
        elif arg.startswith(f"{flag_long}="):
            return arg[len(flag_long) + 1:]
    return None


def replace_field(passthrough: list[str], flag_short: str, flag_long: str, new_value: str) -> list[str]:
    out = []
    skip_next = False
    for i, arg in enumerate(passthrough):
        if skip_next:
            skip_next = False
            continue
        if arg in (flag_long, flag_short):
            out.append(arg)
            out.append(new_value)
            skip_next = True
        elif arg.startswith(f"{flag_long}="):
            out.append(f"{flag_long}={new_value}")
        else:
            out.append(arg)
    return out


def lookup_register(email: str | None) -> str | None:
    if not email or not TIER_MAP.exists():
        return None
    addr = email.lower().strip()
    with open(TIER_MAP) as f:
        m = json.load(f)
    for reg in ("A", "B", "C"):
        if addr in [x.lower() for x in m[reg]["members"]]:
            return reg
    if addr in [x.lower() for x in m["_excluded"]["members"]]:
        return "EXCLUDED"
    return None


def scrub_coauthor(body: str) -> tuple[str, int]:
    """Strip AI-coauthor lines silently. Return (cleaned, count_stripped)."""
    count = 0
    for p in COAUTHOR_PATTERNS:
        cleaned, n = p.subn("", body)
        count += n
        body = cleaned
    return re.sub(r"\n{3,}", "\n\n", body).strip() + "\n", count


def scan_anti_patterns(body: str) -> list[tuple[str, str]]:
    """Return list of (matched_snippet, reason) for each anti-pattern hit."""
    findings = []
    for pattern, reason in ANTI_PATTERNS:
        m = pattern.search(body)
        if m:
            findings.append((m.group(0)[:80], reason))
    return findings


def register_warnings(register: str | None, body: str) -> list[str]:
    """Soft-warn on register-greeting/closer mismatches."""
    warnings = []
    if not register:
        return warnings
    first_line = (body.lstrip().splitlines() + [""])[0].strip()
    if register == "A" and re.match(r"^Hey\b", first_line, re.I):
        warnings.append("Register A (formal-warm) — Matt uses 'Hi <Name>,' here, not 'Hey'.")
    if register == "C" and re.search(r"^Best,\s*\n+\s*Matthew\s*$", body, re.M | re.I):
        warnings.append("Register C (casual-pro) — drop 'Best, Matthew' or use 'Matt'; full formal close is off-key for peer contacts.")
    if register == "EXCLUDED" and "Best,\n\nMatthew" in body:
        warnings.append("Recipient is EXCLUDED (family/close friend) — route through fakematt-personal voice instead of professional.")
    return warnings


def log_send(record: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(record) + "\n")


def main() -> int:
    args, passthrough = parse_args()

    body = extract_field(passthrough, "-b", "--body") or ""
    to = extract_field(passthrough, "-t", "--to") or ""

    if args.skip_gate:
        log_send({"ts": dt.datetime.now().isoformat(), "to": to, "skipped": True, "args": shlex.join(passthrough)})
        if args.dry_run:
            print("[send-gate] --skip-gate + --dry-run: nothing to do")
            return 0
        return subprocess.call(["python3", str(GMAIL_SKILL), "send"] + passthrough)

    # Silent scrub: strip AI-coauthor lines from body
    cleaned_body, stripped = scrub_coauthor(body)
    if stripped:
        print(f"[send-gate] scrubbed {stripped} AI-coauthor line(s) from body", file=sys.stderr)
        passthrough = replace_field(passthrough, "-b", "--body", cleaned_body)
        body = cleaned_body

    # Run scans
    register = lookup_register(to)
    findings = scan_anti_patterns(body)
    reg_warnings = register_warnings(register, body)

    # Print findings
    if findings or reg_warnings:
        print(f"\n[send-gate] {len(findings) + len(reg_warnings)} warning(s) for send to {to or '(unspecified)'}:", file=sys.stderr)
        for snippet, reason in findings:
            print(f"  • anti-pattern: \"{snippet}\" — {reason}", file=sys.stderr)
        for w in reg_warnings:
            print(f"  • register: {w}", file=sys.stderr)
        if args.strict:
            print("[send-gate] --strict: BLOCKED. Fix and re-run.", file=sys.stderr)
            return 1
    else:
        print(f"[send-gate] clean — no findings for send to {to or '(unspecified)'}", file=sys.stderr)

    if args.dry_run:
        print("[send-gate] --dry-run: not sending.", file=sys.stderr)
        return 0

    # Pass through
    print("[send-gate] sending…", file=sys.stderr)
    rc = subprocess.call(["python3", str(GMAIL_SKILL), "send"] + passthrough)
    log_send({
        "ts": dt.datetime.now().isoformat(),
        "to": to, "register": register,
        "anti_patterns": len(findings),
        "register_warnings": len(reg_warnings),
        "scrubbed_coauthor_lines": stripped,
        "exit_code": rc,
    })
    return rc


if __name__ == "__main__":
    sys.exit(main())
