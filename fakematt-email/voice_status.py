#!/usr/bin/env python3
"""Voice infrastructure health check.

Single one-shot status reporter for the whole fakematt-* voice system. Run
it manually for a snapshot, or wire it into a daily cron + Slack post if you
want a recurring health beacon.

Reports:
  - Corpus freshness (last gmail_id timestamp in each corpus)
  - tier_map size + auto-classified additions count
  - sent-log size + pending/stale/abandoned records (for both email + personal)
  - corrections.md size + most-recent entry date
  - Last cron run timestamps (refresh / learn / smoke) per skill
  - Anchor file existence (universals + voice docs)

Usage:
    python3 ~/.claude/skills/fakematt-email/voice_status.py
"""
from __future__ import annotations

import datetime as dt
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

VAULT = Path("/Users/mattheweisner/Obsidian/Zerg/MattZerg")
EMAIL_SKILL = Path.home() / ".claude" / "skills" / "fakematt-email"
PERSONAL_SKILL = Path.home() / ".claude" / "skills" / "fakematt-personal"
CLAUDE_SKILLS = Path.home() / ".claude" / "skills"
CODEX_SKILLS = Path.home() / ".codex" / "skills"
WRAPPER = Path.home() / ".claude" / "feedback-corpus" / "lib" / "claude.py"

DRIFT_FILES = {
    "fakematt-email": [
        "SKILL.md",
        "run.py",
        "smoke_test.py",
        "learn.py",
        "refresh.py",
        "promote.py",
        "voice_status.py",
        "sent_log_audit.py",
        "tier_map.json",
        "agents/openai.yaml",
    ],
    "fakematt-personal": [
        "SKILL.md",
        "run.py",
        "smoke_test.py",
        "learn.py",
        "refresh.py",
        "agents/openai.yaml",
    ],
    "fakematt-operator": [
        "SKILL.md",
        "scripts/intake_bridge.py",
        "references/intake-routing.md",
        "agents/openai.yaml",
    ],
}


def file_age(p: Path) -> str:
    if not p.exists():
        return "MISSING"
    age = dt.datetime.now() - dt.datetime.fromtimestamp(p.stat().st_mtime)
    days, sec = age.days, age.seconds
    if days > 0: return f"{days}d ago"
    h, m = sec // 3600, (sec % 3600) // 60
    if h > 0: return f"{h}h{m}m ago"
    return f"{m}m ago"


def corpus_last_id_date(corpus: Path) -> str:
    if not corpus.exists():
        return "MISSING"
    text = corpus.read_text()
    # Look for the last `## ... | YYYY-MM-DD` header
    matches = re.findall(r"## To .+\|\s*(\w+,?\s+\d+\s+\w+\s+\d{4})", text)
    if matches:
        return matches[-1]
    return "(no dated entries)"


def jsonl_stats(p: Path) -> tuple[int, int]:
    """Return (total, unchecked)."""
    if not p.exists():
        return 0, 0
    total = unchecked = 0
    with open(p) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                r = json.loads(line)
                total += 1
                if not r.get("checked"):
                    unchecked += 1
            except Exception:
                pass
    return total, unchecked


def jsonl_status(p: Path) -> tuple[int, int, int]:
    """Return (total, unchecked_non_synthetic, synthetic)."""
    if not p.exists():
        return 0, 0, 0
    total = unchecked = synthetic = 0
    with open(p) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            total += 1
            if r.get("synthetic"):
                synthetic += 1
            elif not r.get("checked"):
                unchecked += 1
    return total, unchecked, synthetic


def parse_sent_log_ts(raw: str | None) -> dt.datetime | None:
    if not raw:
        return None
    for fmt in ("%Y%m%dT%H%M%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(raw[: len(dt.datetime.now().strftime(fmt))], fmt)
        except ValueError:
            continue
    return None


def sent_log_status(p: Path, *, stale_days: int) -> dict[str, int]:
    stats = {
        "total": 0,
        "pending": 0,
        "stale": 0,
        "abandoned": 0,
        "synthetic": 0,
        "invalid": 0,
    }
    if not p.exists():
        return stats
    cutoff = dt.datetime.now() - dt.timedelta(days=stale_days)
    with open(p) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                stats["invalid"] += 1
                continue
            stats["total"] += 1
            if row.get("synthetic"):
                stats["synthetic"] += 1
            if row.get("abandoned"):
                stats["abandoned"] += 1
            if row.get("checked") or row.get("synthetic"):
                continue
            stats["pending"] += 1
            row_ts = parse_sent_log_ts(row.get("ts"))
            if row_ts and row_ts <= cutoff:
                stats["stale"] += 1
    return stats


def tier_map_stats(p: Path) -> tuple[int, int, int, int]:
    """Return (A_count, B_count, C_count, auto_classified_count)."""
    if not p.exists():
        return (0, 0, 0, 0)
    with open(p) as f:
        m = json.load(f)
    counts = {}
    autos = 0
    for r in ("A", "B", "C"):
        counts[r] = len(m.get(r, {}).get("members", []))
        autos += len(m.get(r, {}).get("_autoclassified", {}))
    return counts["A"], counts["B"], counts["C"], autos


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def check_skill_drift() -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for skill, rels in DRIFT_FILES.items():
        for rel in rels:
            codex = CODEX_SKILLS / skill / rel
            claude = CLAUDE_SKILLS / skill / rel
            if not codex.exists() and not claude.exists():
                continue
            if not codex.exists():
                rows.append((skill, rel, "MISSING in .codex"))
            elif not claude.exists():
                rows.append((skill, rel, "MISSING in .claude"))
            elif sha256(codex) != sha256(claude):
                rows.append((skill, rel, "DIFF"))
    return rows


def load_wrapper_defaults() -> tuple[str, str, str]:
    if not WRAPPER.exists():
        return "MISSING", "MISSING", "wrapper file not found"
    text = WRAPPER.read_text(errors="ignore")
    model_match = re.search(r'^DEFAULT_MODEL\s*=\s*["\']([^"\']+)["\']', text, re.M)
    bin_match = re.search(r'^CLAUDE_BIN\s*=\s*(.+)$', text, re.M)
    model = model_match.group(1) if model_match else "UNKNOWN"
    return model, str(Path.home() / ".config" / "zerg" / "zclaude"), bin_match.group(1).strip() if bin_match else "UNKNOWN"


def run_model_probe(model: str) -> tuple[bool, str]:
    sys.path.insert(0, str(Path.home() / ".claude" / "feedback-corpus"))
    try:
        from lib.claude import CLAUDE_BIN, call_claude  # type: ignore
    except Exception as exc:
        return False, f"wrapper import failed: {type(exc).__name__}: {exc}"
    try:
        out = call_claude("Say OK only.", model=model, timeout=45)
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    ok = "OK" in out.upper()
    return ok, f"bin={CLAUDE_BIN}\noutput={out[:500]}"


def log_tail(path: Path, n: int = 3) -> str:
    if not path.exists():
        return "not yet run"
    lines = [line.rstrip() for line in path.read_text(errors="ignore").splitlines() if line.strip()]
    return "\n".join(lines[-n:]) if lines else "(empty log)"


def learn_status(path: Path) -> str:
    if not path.exists():
        return "loop did not run"
    text = path.read_text(errors="ignore")
    if "correction logged" in text:
        return "corrections found"
    if re.search(r"\[learn\]\s+0\s+new corrections? appended", text):
        return "loop ran; no corrections found"
    if "no sent-log yet" in text:
        return "loop ran; no sent-log"
    return "loop ran; inspect log"


def launchagent_status() -> list[str]:
    rows: list[str] = []
    try:
        out = subprocess.check_output(["launchctl", "list"], text=True, stderr=subprocess.STDOUT, timeout=10)
        rows.extend(line.strip() for line in out.splitlines() if "fakematt" in line.lower())
    except Exception as exc:
        rows.append(f"(launchctl list failed: {type(exc).__name__}: {exc})")
    return rows or ["(no fakematt LaunchAgents loaded)"]


def main() -> int:
    ap = argparse.ArgumentParser(description="Fake Matt voice infrastructure health check.")
    ap.add_argument("--doctor", action="store_true", help="include drift/model/LaunchAgent diagnostics and exit nonzero on critical failures")
    ap.add_argument("--stale-sent-log-days", type=int, default=7, help="warn when unchecked sent-log rows are at least this old")
    args = ap.parse_args()
    failures: list[str] = []
    warnings: list[str] = []

    print("=" * 60)
    print(f"VOICE INFRASTRUCTURE STATUS  {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    if args.doctor:
        print("\n## Skill copy drift")
        drift = check_skill_drift()
        if drift:
            failures.append("skill copy drift")
            for skill, rel, status in drift:
                print(f"  {skill:<20} {rel:<32} {status}")
        else:
            print("  OK: checked .codex/.claude files match for runtime docs/scripts")

        print("\n## Claude wrapper / model")
        model, expected_bin, wrapper_expr = load_wrapper_defaults()
        print(f"  wrapper: {WRAPPER} ({file_age(WRAPPER)})")
        print(f"  default model: {model}")
        print(f"  expected launcher: {expected_bin} ({'OK' if Path(expected_bin).exists() else 'MISSING'})")
        print(f"  CLAUDE_BIN expression: {wrapper_expr}")
        ok, detail = run_model_probe(model)
        print(f"  model probe: {'OK' if ok else 'FAILED'}")
        print("\n".join(f"    {line}" for line in detail.splitlines()))
        if not ok:
            failures.append("model probe failed")

    # Anchor files
    print("\n## Anchor files")
    for p, label in [
        (VAULT / "_style" / "voice_universals.md", "voice_universals.md"),
        (VAULT / "_style" / "professional_voice.md", "professional_voice.md"),
        (VAULT / "_style" / "personal_voice.md", "personal_voice.md"),
        (VAULT / "_style" / "subject_patterns.md", "subject_patterns.md"),
        (VAULT / "_style" / "writing_style.md", "writing_style.md"),
    ]:
        size = p.stat().st_size if p.exists() else 0
        print(f"  {label:<32} {size:>6}b   updated {file_age(p)}")

    # Corpora
    print("\n## Corpora")
    for p, label in [
        (VAULT / "_style" / "professional_voice_corpus.md", "professional"),
        (VAULT / "_style" / "personal_voice_corpus.md", "personal"),
    ]:
        if p.exists():
            text = p.read_text()
            count = text.count("## To ")
            last = corpus_last_id_date(p)
            print(f"  {label:<14} {count:>3} samples   last entry: {last}   updated {file_age(p)}")
        else:
            print(f"  {label:<14} MISSING")

    # Tier map
    print("\n## tier_map.json")
    a, b, c, auto = tier_map_stats(EMAIL_SKILL / "tier_map.json")
    print(f"  A (formal-warm): {a}")
    print(f"  B (mid-casual):  {b}")
    print(f"  C (casual-pro):  {c}")
    print(f"  auto-classified: {auto}")

    # sent-log + corrections per skill
    for skill_dir, label in [(EMAIL_SKILL, "email"), (PERSONAL_SKILL, "personal")]:
        print(f"\n## {label} skill")
        sl = skill_dir / "sent-log.jsonl"
        cor = skill_dir / "corrections.md"
        sl_stats = sent_log_status(sl, stale_days=args.stale_sent_log_days)
        print(
            "  sent-log:    {total} total, {pending} pending, {stale} stale, "
            "{abandoned} abandoned, {synthetic} synthetic   ({age})".format(
                **sl_stats,
                age=file_age(sl),
            )
        )
        if args.doctor and sl_stats["stale"]:
            warnings.append(
                f"{label} stale sent-log backlog: {sl_stats['stale']} "
                f"(run sent_log_audit.py --days {args.stale_sent_log_days} --apply)"
            )
        if cor.exists():
            cor_size = cor.stat().st_size
            text = cor.read_text()
            entries = len(re.findall(r"^## \d{4}-\d{2}-\d{2} —", text, re.M))
            print(f"  corrections: {entries} entries, {cor_size}b   updated {file_age(cor)}")
        else:
            print(f"  corrections: (none yet)")
        # log files
        log_dir = skill_dir / "logs"
        if log_dir.exists():
            for log_name in ("refresh.log", "learn.log", "smoke.log"):
                lp = log_dir / log_name
                if lp.exists():
                    status = f" | {learn_status(lp)}" if log_name == "learn.log" else ""
                    print(f"  logs/{log_name:<12} {file_age(lp)}{status}")
                    if args.doctor:
                        tail = log_tail(lp)
                        for line in tail.splitlines():
                            print(f"    {line[:180]}")
                else:
                    print(f"  logs/{log_name:<12} not yet run")
                    if args.doctor and log_name in {"learn.log", "smoke.log"}:
                        failures.append(f"{label} {log_name} missing")

    # Cron entries
    print("\n## Scheduled jobs")
    try:
        out = subprocess.check_output(["crontab", "-l"], text=True)
        for line in out.split("\n"):
            if "fakematt-" in line and "skills" in line:
                print(f"  {line.strip()[:100]}")
    except Exception as e:
        print(f"  (crontab read failed: {e})")

    if args.doctor:
        print("\n## LaunchAgents")
        for row in launchagent_status():
            print(f"  {row}")

        print("\n## Doctor result")
        if warnings:
            print("  WARN")
            for warning in sorted(set(warnings)):
                print(f"  - {warning}")
        if failures:
            print("  FAIL")
            for failure in sorted(set(failures)):
                print(f"  - {failure}")
            return 1
        print("  OK")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
