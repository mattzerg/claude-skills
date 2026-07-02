#!/usr/bin/env python3
"""gtm doctor — end-to-end health check.

Runs every check in one go and reports red/amber/green per check with the
single command needed to fix each issue. Exit code 0 if all green, 1 if any
red, 2 if any amber.

Checks:
  1. Schema audit          — every entity validates against schema.md
  2. Unit tests            — frontmatter parser + rule engine
  3. Cron error log scan   — recent PermissionError / Traceback in gtm_hub.log
  4. LaunchAgent install   — has the user run launchd/install.sh yet?
  5. Index freshness       — _meta/index.json regenerated recently?
  6. Mirror freshness      — ~/.zerg-vault-mirror/ synced recently?
  7. Decisions queue       — N open · M urgent
  8. Project red count     — projects in 🔴 state requiring attention
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

from lib.entities import META_DIR, _ICLOUD_VAULT, _MIRROR_VAULT  # type: ignore


GTM_HUB_LOG = Path.home() / ".claude" / "fakematt-today" / "gtm_hub.log"
LAUNCHAGENT_DIR = Path.home() / "Library" / "LaunchAgents"
HUB_AGENTS = (
    "com.matteisn.gtm-hub-regenerate",
    "com.matteisn.gtm-hub-post",
    "com.matteisn.gtm-hub-slack-listener",
)
MIRROR_STATE = Path.home() / ".config" / "zerg" / "vault_mirror_state.json"


def _row(status: str, name: str, detail: str, fix: str | None = None) -> dict:
    return {"status": status, "name": name, "detail": detail, "fix": fix}


def check_schema_audit() -> dict:
    res = subprocess.run(
        [sys.executable, str(THIS_DIR / "audit.py")],
        capture_output=True, text=True, check=False,
    )
    last_line = (res.stdout or "").strip().splitlines()[-1] if res.stdout else ""
    if res.returncode == 0:
        return _row("🟢", "schema audit", last_line)
    return _row("🔴", "schema audit", last_line or "audit failed",
                fix="gtm audit  # see errors above")


def check_tests() -> dict:
    res = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", str(THIS_DIR / "tests")],
        capture_output=True, text=True, check=False,
    )
    summary = (res.stderr or "").strip().splitlines()
    last = summary[-1] if summary else ""
    ran = next((s for s in summary if s.startswith("Ran")), "")
    if res.returncode == 0:
        return _row("🟢", "unit tests", f"{ran} → OK")
    return _row("🔴", "unit tests", f"{ran} → {last}",
                fix=f"cd {THIS_DIR.parent} && python3 -m unittest discover -s scripts/tests")


def check_cron_log() -> dict:
    if not GTM_HUB_LOG.exists():
        return _row("🟡", "cron log",
                    "no log yet — cron may not have run",
                    fix="wait for next 15-min tick OR `launchctl kickstart`")
    text = GTM_HUB_LOG.read_text(encoding="utf-8", errors="replace")
    # Only consider lines after the most recent run-start timestamp. Each
    # gtm_hub_regenerate.py invocation emits `[YYYY-MM-DDTHH:MM:SS] gtm-hub
    # regenerate` — we slice from the latest of those forward. Older errors
    # are pre-install / pre-fix history and shouldn't show as current health.
    import re
    lines = text.splitlines()
    start_idx = 0
    for i in range(len(lines) - 1, -1, -1):
        if re.match(r"^\[20\d{2}-\d{2}-\d{2}T", lines[i]):
            start_idx = i
            break
    recent = "\n".join(lines[start_idx:])
    tb_count = recent.count("Traceback")
    perm_count = recent.count("PermissionError")
    if perm_count:
        return _row("🔴", "cron health",
                    f"{perm_count} PermissionError in latest run — cron can't write to iCloud",
                    fix="~/.claude/skills/gtm-hub/launchd/install.sh  # bootstrap FDA-bearing LaunchAgents")
    if tb_count:
        return _row("🟡", "cron health",
                    f"{tb_count} tracebacks in latest run (non-permission)",
                    fix="tail -50 ~/.claude/fakematt-today/gtm_hub.log")
    # Check freshness: last log timestamp
    last_ts_line = next(
        (ln for ln in reversed(tail.splitlines()) if ln.startswith("[") and "T" in ln[:25]),
        None,
    )
    if last_ts_line:
        try:
            stamp = last_ts_line[1:20]
            last = dt.datetime.fromisoformat(stamp)
            age_min = (dt.datetime.now() - last).total_seconds() / 60
            if age_min > 60:
                return _row("🟡", "cron health",
                            f"last run {int(age_min)}m ago (stale)",
                            fix="check LaunchAgent: launchctl list | grep matteisn.gtm")
            return _row("🟢", "cron health", f"last run {int(age_min)}m ago · no recent errors")
        except ValueError:
            pass
    return _row("🟡", "cron health", "no recent timestamp found", fix=None)


def check_launchagents() -> dict:
    res = subprocess.run(["launchctl", "list"], capture_output=True, text=True, check=False)
    loaded = res.stdout if res.returncode == 0 else ""
    installed = []
    bootstrapped = []
    for agent in HUB_AGENTS:
        plist = LAUNCHAGENT_DIR / f"{agent}.plist"
        if plist.exists():
            installed.append(agent)
        if agent in loaded:
            bootstrapped.append(agent)
    if len(bootstrapped) == len(HUB_AGENTS):
        return _row("🟢", "launchd agents",
                    f"{len(bootstrapped)}/{len(HUB_AGENTS)} loaded")
    if not installed:
        return _row("🔴", "launchd agents",
                    "none installed — Slack writes will silently fail",
                    fix="~/.claude/skills/gtm-hub/launchd/install.sh")
    return _row("🟡", "launchd agents",
                f"{len(installed)} installed, {len(bootstrapped)} bootstrapped",
                fix="re-run ~/.claude/skills/gtm-hub/launchd/install.sh from Terminal")


def check_index_freshness() -> dict:
    idx = META_DIR / "index.json"
    if not idx.exists():
        return _row("🔴", "index freshness",
                    "no index.json",
                    fix="gtm regenerate")
    try:
        data = json.loads(idx.read_text(encoding="utf-8"))
        gen_at = data.get("generated_at", "")
        last = dt.datetime.fromisoformat(gen_at)
        age_min = (dt.datetime.now() - last).total_seconds() / 60
        if age_min > 120:
            return _row("🟡", "index freshness",
                        f"index is {int(age_min)}m old",
                        fix="gtm regenerate  # or wait for hourly cron")
        return _row("🟢", "index freshness",
                    f"{data.get('count', '?')} entities · refreshed {int(age_min)}m ago")
    except (OSError, ValueError, KeyError):
        return _row("🟡", "index freshness", "couldn't parse index.json",
                    fix="gtm regenerate")


def check_mirror_freshness() -> dict:
    if not _MIRROR_VAULT.exists():
        return _row("🟡", "vault mirror",
                    "mirror not present — cron reads will fail",
                    fix="launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.matteisn.vault-mirror.plist")
    if not MIRROR_STATE.exists():
        return _row("🟡", "vault mirror", "exists but no sync state recorded")
    try:
        state = json.loads(MIRROR_STATE.read_text(encoding="utf-8"))
        last = state.get("last_sync")
        if not last:
            return _row("🟡", "vault mirror", "no last_sync timestamp")
        last_dt = dt.datetime.fromisoformat(last)
        age_min = (dt.datetime.now() - last_dt).total_seconds() / 60
        if age_min > 30:
            return _row("🟡", "vault mirror", f"synced {int(age_min)}m ago (>15min interval)")
        return _row("🟢", "vault mirror", f"synced {int(age_min)}m ago")
    except (OSError, ValueError):
        return _row("🟡", "vault mirror", "couldn't read sync state")


def check_decisions() -> dict:
    dec_path = META_DIR / "decisions.json"
    idx_path = META_DIR / "index.json"
    if not idx_path.exists():
        return _row("🟡", "decisions", "no index yet")
    try:
        idx = json.loads(idx_path.read_text(encoding="utf-8"))
        today = dt.date.today()
        open_decs = [
            e for e in idx.get("entities", [])
            if e.get("type") == "decision" and e.get("status") in ("open", "deferred")
        ]
        urgent = 0
        for d in open_decs:
            try:
                dl = dt.date.fromisoformat(d.get("deadline") or "")
                if (dl - today).days <= 7:
                    urgent += 1
            except (ValueError, TypeError):
                pass
        if urgent > 0:
            return _row("🟡", "decisions queue",
                        f"{len(open_decs)} open · ⚠ {urgent} due ≤7d",
                        fix="gtm overview  # see top of queue")
        return _row("🟢", "decisions queue", f"{len(open_decs)} open · 0 urgent")
    except (OSError, ValueError):
        return _row("🟡", "decisions queue", "couldn't parse")


def check_projects() -> dict:
    idx_path = META_DIR / "index.json"
    if not idx_path.exists():
        return _row("🟡", "projects", "no index yet")
    try:
        idx = json.loads(idx_path.read_text(encoding="utf-8"))
        projects = [e for e in idx.get("entities", []) if e.get("type") == "project"]
        red = [p for p in projects
               if (p.get("effective_rag") or "").lower() == "red"
               and p.get("status") not in ("shipped", "canceled", "paused")]
        active = [p for p in projects
                  if p.get("status") not in ("shipped", "canceled", "paused")]
        if red:
            return _row("🟡", "projects",
                        f"{len(active)} active · 🔴 {len(red)} red",
                        fix="gtm projects  # see blockers")
        return _row("🟢", "projects", f"{len(active)} active · 0 red")
    except (OSError, ValueError):
        return _row("🟡", "projects", "couldn't parse")


def main() -> int:
    print()
    print("═" * 72)
    print("  🩺 GTM HUB — DOCTOR")
    print("═" * 72)
    print()

    checks = [
        check_schema_audit(),
        check_tests(),
        check_index_freshness(),
        check_mirror_freshness(),
        check_cron_log(),
        check_launchagents(),
        check_decisions(),
        check_projects(),
    ]

    for c in checks:
        print(f"  {c['status']}  {c['name']:<20}  {c['detail']}")
        if c["fix"]:
            print(f"      fix:  {c['fix']}")

    print()
    red = sum(1 for c in checks if c["status"] == "🔴")
    amber = sum(1 for c in checks if c["status"] == "🟡")
    green = sum(1 for c in checks if c["status"] == "🟢")
    print(f"  Summary:  🟢 {green}    🟡 {amber}    🔴 {red}")
    print("═" * 72)
    print()

    if red:
        return 1
    if amber:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
