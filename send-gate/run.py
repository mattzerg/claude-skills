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


# ---------- send-time learning hook ----------
# Reduces FM voice-loop feedback latency from 24h (cron'd learn.py reading the
# Gmail sent folder) to 0. send-gate already has both the original FM draft
# (looked up from sent-log) and the about-to-send body — the cleanest moment
# to capture an in-flight diff. Wrapped in try/except so any failure here is
# silent and never blocks the actual send.

LEARN_SKILL_DIRS = [
    Path.home() / ".claude" / "skills" / "fakematt-email",
    Path.home() / ".claude" / "skills" / "fakematt-personal",
]
LEARN_WINDOW_DAYS = 7
LEARN_MIN_CHANGED_LINES = 2


def _diff_summary(generated: str, sent: str) -> tuple[str, int]:
    import difflib
    g = [l.rstrip() for l in generated.splitlines()]
    s = [l.rstrip() for l in sent.splitlines()]
    diff = list(difflib.unified_diff(g, s, lineterm="", n=2))
    changed = sum(
        1 for l in diff
        if l.startswith(("+", "-")) and not l.startswith(("+++", "---")) and l[1:].strip()
    )
    return "\n".join(diff), changed


def _find_recent_unchecked(sent_log: Path, recipient: str) -> tuple[int, dict, list[dict]] | tuple[None, None, list]:
    if not sent_log.exists():
        return None, None, []
    cutoff = dt.datetime.now() - dt.timedelta(days=LEARN_WINDOW_DAYS)
    records: list[dict] = []
    for line in sent_log.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except Exception:
            continue
    # Walk newest-first, return first unchecked match within the window
    for i in range(len(records) - 1, -1, -1):
        r = records[i]
        if r.get("checked"):
            continue
        if (r.get("to") or "").lower() != recipient.lower():
            continue
        try:
            ts = dt.datetime.strptime((r.get("ts") or "")[:15], "%Y%m%dT%H%M%S")
        except Exception:
            continue
        if ts < cutoff:
            continue
        return i, r, records
    return None, None, records


def _append_correction(corrections: Path, record: dict, sent_body: str,
                       diff_text: str, changed: int) -> None:
    if not corrections.exists():
        corrections.write_text(
            "# Recent corrections\n\n"
            "Diffs of edits Matt made to skill-generated drafts before sending. "
            "Includes send-time captures via send-gate.\n\n---\n\n"
        )
    today = dt.date.today().isoformat()
    register_str = ""
    if record.get("register"):
        register_str = f" (Register {record['register']})"
    elif record.get("tone"):
        register_str = f" (Tone {record['tone']})"
    with open(corrections, "a") as f:
        f.write(f"\n## {today} — to {record.get('to','?')}{register_str}\n\n")
        f.write("_Captured at send-time by send-gate._\n\n")
        f.write(f"**Original draft:**\n\n```\n{record.get('generated_body','').strip()}\n```\n\n")
        f.write(f"**What Matt sent:**\n\n```\n{sent_body.strip()}\n```\n\n")
        if changed:
            f.write(f"**Diff** ({changed} changed lines):\n\n```diff\n{diff_text}\n```\n\n")
        f.write("---\n")


def capture_at_send(recipient: str, sent_body: str) -> dict | None:
    """Best-effort: look up most recent unchecked FM draft to this recipient,
    diff against the about-to-send body, and if material edit, log a correction
    + mark the record checked. Returns the captured payload or None.
    """
    if not recipient or not sent_body or not sent_body.strip():
        return None
    try:
        for sdir in LEARN_SKILL_DIRS:
            sent_log = sdir / "sent-log.jsonl"
            corrections = sdir / "corrections.md"
            idx, record, records = _find_recent_unchecked(sent_log, recipient)
            if record is None:
                continue
            generated = (record.get("generated_body") or "").strip()
            if not generated:
                continue
            diff_text, changed = _diff_summary(generated, sent_body.strip())
            if changed >= LEARN_MIN_CHANGED_LINES:
                _append_correction(corrections, record, sent_body, diff_text, changed)
                record["checked"] = True
                record["edit_distance"] = changed
                record["manual_override"] = True
                record["captured_by"] = "send-gate"
                records[idx] = record
                with open(sent_log, "w") as f:
                    for r in records:
                        f.write(json.dumps(r) + "\n")
                return {
                    "skill": sdir.name,
                    "ts": record.get("ts"),
                    "changed_lines": changed,
                    "to": recipient,
                }
            # Found a match but no material edit → mark checked anyway so cron
            # learn.py doesn't redo the work. edit_distance < threshold.
            record["checked"] = True
            record["edit_distance"] = changed
            record["captured_by"] = "send-gate"
            records[idx] = record
            with open(sent_log, "w") as f:
                for r in records:
                    f.write(json.dumps(r) + "\n")
            return {
                "skill": sdir.name,
                "ts": record.get("ts"),
                "changed_lines": changed,
                "to": recipient,
                "no_material_edit": True,
            }
    except Exception as e:
        print(f"[send-gate] learning hook failed (non-fatal): {e}", file=sys.stderr)
    return None


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

    # Send-time learning — best-effort, never blocks the send.
    capture = capture_at_send(to, body)
    if capture and not capture.get("no_material_edit"):
        print(
            f"[send-gate] captured edit for FM voice loop: "
            f"{capture['changed_lines']} changed line(s) vs draft {capture['ts']} "
            f"({capture['skill']})",
            file=sys.stderr,
        )

    # Pass through
    print("[send-gate] sending…", file=sys.stderr)
    rc = subprocess.call(["python3", str(GMAIL_SKILL), "send"] + passthrough)
    log_send({
        "ts": dt.datetime.now().isoformat(),
        "to": to, "register": register,
        "anti_patterns": len(findings),
        "register_warnings": len(reg_warnings),
        "scrubbed_coauthor_lines": stripped,
        "send_time_capture": capture,
        "exit_code": rc,
    })
    return rc


if __name__ == "__main__":
    sys.exit(main())
