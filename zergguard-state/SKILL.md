---
name: zergguard-state
description: Weekly security-posture dashboard for ZergGuard. One command — "where am I at security-wise right now." Produces a single-page markdown with — device hygiene tick-list (SIP/Gatekeeper/FileVault/macOS), supply-chain rollup (existing security-monitor + zergguard daily), recent flagged events from the past 7d, a 0–100 risk score, and "the one move that would improve it most." Auto-fires Mondays at 7am via LaunchAgent + DMs Fake Matt. Verbs — `python3 dashboard.py` (default; write + DM), `--dry-run` (print, no DM/write). Sibling to `zergguard-audit` (Phase 0) and the daily monitor (Phase 1). Use weekly for posture review; ad-hoc when Matt asks "how's my security state."
---

# zergguard-state

Weekly cybersec posture dashboard. One-page summary.

## Output

```
ZergGuard posture — Week 21
Risk score: 82/100 (Good)

Top move to improve: Review 3 new browser extensions installed last week.

Device hygiene
  ✅ SIP enabled
  ✅ Gatekeeper enabled
  ⚠️ FileVault OFF — enable in System Settings
  ✅ macOS 14.5 (current)

Supply chain (agent-side)
  ✅ 18 plugins pinned; no SHA drift
  ✅ 0 new MCP servers
  ✅ 0 new launchd entries

User-threat surface
  HIGH findings this week: 0
  MED findings: 1 (3 apps installed — all recognized)
  Last full audit: 2026-05-23

IOC watchlist
  1 known-bad domain (cvetochek75.com from 2026-05-01 phishing attempt)
```

## Usage

```bash
python3 ~/.claude/skills/zergguard-state/dashboard.py
python3 ~/.claude/skills/zergguard-state/dashboard.py --dry-run
```

## Scheduling

LaunchAgent at `~/Library/LaunchAgents/com.matteisner.zergguard-weekly.plist` fires Mondays 7am. Writes report to `<report_dir>/dashboard-YYYY-WW.md` + DMs Fake Matt with the 5-line summary.

## Risk score

Heuristic, 0–100:
- 100 baseline
- -15 if FileVault off
- -10 if Gatekeeper off
- -25 if SIP off
- -5 per HIGH finding from last 7d (capped -25)
- -2 per MED finding from last 7d (capped -10)
- -10 if macOS major-version behind latest
- -3 per unrecognized LaunchAgent

The "top move" is whatever single change would recover the most points.

## Read-only

Aggregates from existing skill state files. Never writes anywhere except its own report.
