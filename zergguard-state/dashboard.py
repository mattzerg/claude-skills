#!/usr/bin/env python3
"""ZergGuard Phase 3 — weekly posture dashboard."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

LIB = Path.home() / ".config" / "zerg-guard" / "lib"
sys.path.insert(0, str(LIB))
AUDIT_DIR = Path.home() / ".claude" / "skills" / "zergguard-audit"
sys.path.insert(0, str(AUDIT_DIR))

import config as cfgmod  # noqa: E402
from notify import notify  # noqa: E402
import audit  # noqa: E402
from ioc import KNOWN_BAD_DOMAINS  # noqa: E402


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def hygiene_lines() -> tuple[list[str], int]:
    """Return list of tick lines + deductions for risk score."""
    deduct = 0
    lines = []
    sip = _run(["csrutil", "status"])
    if sip:
        ok = "enabled" in sip.lower()
        lines.append(f"  {'✅' if ok else '🚨'} SIP {'enabled' if ok else 'DISABLED'}")
        if not ok:
            deduct += 25
    gk = _run(["spctl", "--status"])
    if gk:
        ok = "enabled" in gk.lower()
        lines.append(f"  {'✅' if ok else '⚠️'} Gatekeeper {'enabled' if ok else 'disabled'}")
        if not ok:
            deduct += 10
    fv = _run(["fdesetup", "status"])
    if fv:
        ok = "is on" in fv.lower()
        lines.append(f"  {'✅' if ok else '⚠️'} FileVault {'on' if ok else 'OFF — enable in System Settings'}")
        if not ok:
            deduct += 15
    macos = _run(["sw_vers", "-productVersion"])
    if macos:
        lines.append(f"  · macOS {macos}")
    return lines, deduct


def supply_chain_lines() -> list[str]:
    sm_state = Path.home() / ".config" / "zerg" / "security-monitor" / "state.json"
    if not sm_state.exists():
        return ["  · (security-monitor baseline not found; run that audit first)"]
    try:
        data = json.loads(sm_state.read_text())
    except (OSError, json.JSONDecodeError):
        return ["  · (security-monitor state unreadable)"]
    plugins = data.get("plugins") or {}
    mcp = data.get("mcp_servers") or {}
    cron_entries = data.get("cron") or []
    return [
        f"  · {len(plugins)} plugin(s) pinned",
        f"  · {len(mcp)} MCP server(s) configured",
        f"  · {len(cron_entries)} user cron entry/entries",
    ]


def recent_audit_findings_summary(cfg) -> tuple[list[str], int, int]:
    """Read last 7 days of audit-*.md files from report_dir. Return summary lines + HIGH count + MED count."""
    high = 0
    med = 0
    audits = []
    if cfg.report_dir.exists():
        cutoff = datetime.now() - timedelta(days=7)
        for p in sorted(cfg.report_dir.glob("audit-*.md")):
            try:
                stem_date = datetime.strptime(p.stem.replace("audit-", ""), "%Y-%m-%d")
            except ValueError:
                continue
            if stem_date < cutoff:
                continue
            audits.append(p)
            txt = p.read_text(errors="replace")
            for line in txt.splitlines():
                if line.startswith("Findings:"):
                    for tok in line.split():
                        if tok.startswith("HIGH="):
                            high += int(tok.split("=")[1])
                        elif tok.startswith("MED="):
                            med += int(tok.split("=")[1])
                    break
    lines = [
        f"  · {len(audits)} audit(s) in last 7d",
        f"  · HIGH findings (rolled up): {high}",
        f"  · MED findings (rolled up): {med}",
    ]
    return lines, high, med


def derive_score_and_top_move(cfg, hygiene_deduct: int, high_count: int, med_count: int) -> tuple[int, str]:
    """100 baseline, deduct by config."""
    score = 100 - hygiene_deduct
    score -= min(high_count * 5, 25)
    score -= min(med_count * 2, 10)
    score = max(0, score)

    # "Top move" — biggest single deduction we can recover
    if hygiene_deduct >= 25:
        return score, "Re-enable SIP from Recovery Mode (biggest single risk)."
    if hygiene_deduct >= 15:
        return score, "Turn on FileVault: System Settings → Privacy & Security."
    if hygiene_deduct >= 10:
        return score, "Re-enable Gatekeeper: `sudo spctl --master-enable`."
    if high_count > 0:
        return score, "Review last week's HIGH findings — see audit reports in vault Security/."
    if med_count > 0:
        return score, "Review last week's MED findings (apps/extensions changed)."
    return score, "Nothing pressing. Keep the daily monitor running."


def label(score: int) -> str:
    if score >= 90:
        return "Excellent"
    if score >= 75:
        return "Good"
    if score >= 60:
        return "Watch"
    if score >= 40:
        return "Concerning"
    return "Critical"


def render(cfg, score: int, top_move: str, hygiene: list[str], chain: list[str],
           recent: list[str]) -> str:
    week = datetime.now().isocalendar()
    lines = [
        f"# ZergGuard posture — Week {week.week}, {datetime.now().strftime('%Y-%m-%d')}",
        "",
        f"**Risk score**: {score}/100 ({label(score)})",
        "",
        f"**Top move to improve**: {top_move}",
        "",
        "## Device hygiene",
        *hygiene,
        "",
        "## Supply chain (agent-side)",
        *chain,
        "",
        "## User-threat surface (past 7d)",
        *recent,
        "",
        "## IOC watchlist",
        f"  · {len(KNOWN_BAD_DOMAINS)} known-bad domain(s) being watched",
        "",
        f"_Generated by zergguard-state at {datetime.now().isoformat(timespec='seconds')}._",
    ]
    return "\n".join(lines)


def write_report(cfg, content: str) -> Path:
    cfg.report_dir.mkdir(parents=True, exist_ok=True)
    week = datetime.now().isocalendar()
    path = cfg.report_dir / f"dashboard-{datetime.now().year}-W{week.week:02d}.md"
    path.write_text(content)
    return path


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="zergguard-state")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    cfg = cfgmod.load()
    hygiene, hyg_deduct = hygiene_lines()
    chain = supply_chain_lines()
    recent, high_count, med_count = recent_audit_findings_summary(cfg)
    score, top_move = derive_score_and_top_move(cfg, hyg_deduct, high_count, med_count)
    report = render(cfg, score, top_move, hygiene, chain, recent)

    if args.dry_run:
        print(report)
        return 0

    path = write_report(cfg, report)
    print(f"Report → {path}", file=sys.stderr)

    dm = (
        f"ZergGuard posture: {score}/100 ({label(score)})\n"
        f"Top move: {top_move}\n"
        f"Full report in vault Security/."
    )
    notify(cfg, f"ZergGuard weekly posture: {score}/100", dm)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
