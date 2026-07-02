#!/usr/bin/env python3
"""ZergGuard Phase 0 audit — one-shot Mac compromise scan."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

LIB = Path.home() / ".config" / "zerg-guard" / "lib"
sys.path.insert(0, str(LIB))

import config as cfgmod  # noqa: E402
from findings import Finding, sort_findings, counts  # noqa: E402
from ioc import (  # noqa: E402
    KNOWN_BAD_DOMAINS,
    is_suspicious_process,
    scan_shell_line,
    url_is_known_bad,
)
from notify import notify  # noqa: E402


def _parse_floor(cfg) -> datetime | None:
    if not cfg.attack_window_floor:
        return None
    try:
        return datetime.fromisoformat(cfg.attack_window_floor).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


# ---- Check: browser history for known-bad URLs ----

BROWSER_SPECS = {
    "chrome": {
        "db": Path.home() / "Library/Application Support/Google/Chrome/Default/History",
        "sql": "SELECT url, title FROM urls WHERE url LIKE ?",
    },
    "brave": {
        "db": Path.home() / "Library/Application Support/BraveSoftware/Brave-Browser/Default/History",
        "sql": "SELECT url, title FROM urls WHERE url LIKE ?",
    },
    "safari": {
        "db": Path.home() / "Library/Safari/History.db",
        "sql": "SELECT i.url, v.title FROM history_items i JOIN history_visits v ON v.history_item = i.id WHERE i.url LIKE ?",
    },
}


def check_browser_ioc(cfg) -> list[Finding]:
    findings: list[Finding] = []
    domains = KNOWN_BAD_DOMAINS + cfg.extra_domains
    if not domains:
        return findings
    for browser in cfg.browsers:
        spec = BROWSER_SPECS.get(browser)
        if not spec or not spec["db"].exists():
            continue
        tmp = Path(tempfile.gettempdir()) / f"zergguard-{browser}.db"
        try:
            shutil.copy2(spec["db"], tmp)
            conn = sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)
        except (OSError, sqlite3.Error):
            continue
        try:
            for domain in domains:
                pat = f"%{domain}%"
                rows = conn.execute(spec["sql"], (pat,)).fetchall()
                if rows:
                    evidence = [f"{browser}: {url}" for url, _title in rows[:5]]
                    findings.append(
                        Finding(
                            severity="HIGH",
                            title=f"Known-bad domain in {browser} history: {domain}",
                            detail=(
                                f"The domain `{domain}` appears in your {browser} browsing history. "
                                "This domain is on the ZergGuard known-bad list (added because it was "
                                "used in a real phishing attack against you). If you visited it, the "
                                "malware likely ran. Treat the device as potentially compromised."
                            ),
                            recommendation=(
                                "1) Disconnect from the network. 2) Change passwords for any account "
                                "you've logged into since the visit, using a different device. "
                                "3) Consider a full macOS reinstall. 4) Reply here for help."
                            ),
                            evidence=evidence,
                        )
                    )
        finally:
            conn.close()
    if not findings:
        findings.append(
            Finding(
                severity="INFO",
                title="Browser history clean of known-bad domains",
                detail=f"Scanned {len(cfg.browsers)} browser(s) against {len(domains)} known-bad domain(s); no matches.",
            )
        )
    return findings


# ---- Check: LaunchAgents/Daemons inventory ----

LAUNCH_PATHS = [
    Path.home() / "Library" / "LaunchAgents",
    Path("/Library/LaunchAgents"),
    Path("/Library/LaunchDaemons"),
]


def check_launch_agents(cfg) -> list[Finding]:
    findings: list[Finding] = []
    floor = _parse_floor(cfg)
    recent: list[tuple[Path, datetime]] = []
    total = 0
    for d in LAUNCH_PATHS:
        if not d.exists():
            continue
        try:
            for p in d.iterdir():
                if p.suffix != ".plist":
                    continue
                total += 1
                try:
                    mt = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
                except OSError:
                    continue
                if floor and mt >= floor:
                    recent.append((p, mt))
        except PermissionError:
            findings.append(
                Finding(
                    severity="LOW",
                    title=f"Cannot read {d}",
                    detail="No read permission. Skipped — usually not load-bearing.",
                )
            )
    if recent:
        # Filter out known-safe prefixes for the HIGH bucket. These are
        # apps Matt explicitly installs or are bundled by Apple/major vendors.
        known_safe_prefixes = (
            "com.zerg.",
            "com.matteisner.",  # Matt's user-LaunchAgent prefix
            "com.matteisn.",    # historical typo prefix; keep for back-compat
            "com.apple.",
            "com.codex.",
            "com.google.keystone",  # Chrome auto-updater
            "homebrew.",
            "us.zoom.",
            "com.docker.",
            "com.microsoft.",
        )
        suspicious = [(p, m) for p, m in recent if not p.name.startswith(known_safe_prefixes)]
        if suspicious:
            evidence = [f"{p} (mtime {m.isoformat()})" for p, m in suspicious[:10]]
            findings.append(
                Finding(
                    severity="HIGH",
                    title=f"{len(suspicious)} unrecognized LaunchAgent(s) created in attack window",
                    detail=(
                        "These plist files were created or modified after your attack-window floor "
                        f"({cfg.attack_window_floor or 'unset'}) and don't match known-safe "
                        f"prefixes ({', '.join(known_safe_prefixes)}). They may be persistence "
                        "installed by malware."
                    ),
                    recommendation=(
                        "Open each plist and look at the `ProgramArguments` line — if you don't "
                        "recognize the program path, screenshot it and reply here. Do not delete "
                        "before checking — some legitimate apps install plists too."
                    ),
                    evidence=evidence,
                )
            )
        benign_recent = [(p, m) for p, m in recent if p.name.startswith(known_safe_prefixes)]
        if benign_recent:
            findings.append(
                Finding(
                    severity="INFO",
                    title=f"{len(benign_recent)} known-safe LaunchAgent(s) in attack window",
                    detail="Recognized Zerg/Apple-owned LaunchAgents; expected.",
                    evidence=[f"{p.name}" for p, _ in benign_recent[:5]],
                )
            )
    findings.append(
        Finding(
            severity="INFO",
            title=f"LaunchAgents/Daemons total count: {total}",
            detail="Sanity baseline. Future audits will diff against this.",
        )
    )
    return findings


# ---- Check: Login Items via AppleScript ----


def check_login_items() -> list[Finding]:
    try:
        result = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to get the name of every login item'],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return [Finding(severity="LOW", title="Login Items check timed out", detail="")]
    items = (result.stdout or "").strip()
    if not items:
        return [Finding(severity="INFO", title="No Login Items configured", detail="")]
    item_list = [i.strip() for i in items.split(",") if i.strip()]
    return [
        Finding(
            severity="INFO",
            title=f"{len(item_list)} Login Item(s) configured",
            detail="Items launched at login. Verify each is recognized.",
            evidence=item_list,
        )
    ]


# ---- Check: Running processes against IOC patterns ----


def check_running_processes(cfg) -> list[Finding]:
    try:
        result = subprocess.run(
            ["ps", "-axww", "-o", "pid,user,command"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        return [Finding(severity="LOW", title="ps timed out", detail="")]
    flagged: list[str] = []
    self_pid = str(os.getpid())
    self_path = "zergguard-audit"
    for line in (result.stdout or "").splitlines()[1:]:
        # Skip our own audit process + grep helpers (they contain IOC strings
        # because they're searching FOR them).
        if self_path in line or "ugrep" in line or self_pid in line.split()[:1]:
            continue
        match = is_suspicious_process(line, cfg.extra_process_patterns)
        if match:
            flagged.append(f"{line.strip()}  ← matched /{match}/")
    if flagged:
        return [
            Finding(
                severity="HIGH",
                title=f"{len(flagged)} process(es) match known-stealer patterns",
                detail=(
                    "These running processes have names that match patterns associated with "
                    "macOS infostealer malware. False positives are possible (e.g. dev tools "
                    "named 'loader')."
                ),
                recommendation=(
                    "Check each PID: `ps -p <PID>` for full command. If unfamiliar, "
                    "Activity Monitor → Force Quit. Reply with the process list for help."
                ),
                evidence=flagged[:10],
            )
        ]
    return [Finding(severity="INFO", title="No suspicious processes detected", detail="")]


# ---- Check: recent /Applications/ ----


def check_recent_apps(cfg) -> list[Finding]:
    floor = _parse_floor(cfg)
    if not floor:
        return []
    apps_dir = Path("/Applications")
    if not apps_dir.exists():
        return []
    recent = []
    for p in apps_dir.iterdir():
        if not p.name.endswith(".app"):
            continue
        try:
            mt = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if mt >= floor:
            recent.append((p, mt))
    if not recent:
        return [Finding(severity="INFO", title="No apps installed in attack window", detail="")]
    recent.sort(key=lambda x: x[1], reverse=True)
    return [
        Finding(
            severity="MED",
            title=f"{len(recent)} app(s) installed/modified in attack window",
            detail=(
                "Apps with mtimes inside the configured attack window. Most are legitimate updates; "
                "check anything you don't recognize."
            ),
            recommendation="Review the list. If you don't recognize an app, look it up before launching.",
            evidence=[f"{p.name} ({m.strftime('%Y-%m-%d')})" for p, m in recent[:15]],
        )
    ]


# ---- Check: browser extensions ----


def check_browser_extensions(cfg) -> list[Finding]:
    findings: list[Finding] = []
    paths = {
        "chrome": Path.home() / "Library/Application Support/Google/Chrome/Default/Extensions",
        "brave": Path.home() / "Library/Application Support/BraveSoftware/Brave-Browser/Default/Extensions",
    }
    total_ext = 0
    extension_evidence: list[str] = []
    for browser, p in paths.items():
        if not p.exists():
            continue
        try:
            exts = list(p.iterdir())
        except OSError:
            continue
        for ext_dir in exts:
            if ext_dir.is_dir():
                total_ext += 1
                extension_evidence.append(f"{browser}: {ext_dir.name}")
    if total_ext:
        findings.append(
            Finding(
                severity="INFO",
                title=f"{total_ext} browser extension(s) installed",
                detail="Extension IDs across Chromium-family browsers. Verify each is known to you.",
                evidence=extension_evidence[:20],
            )
        )
    return findings


# ---- Check: SSH state ----


def check_ssh() -> list[Finding]:
    ssh = Path.home() / ".ssh"
    if not ssh.exists():
        return [Finding(severity="INFO", title="No ~/.ssh directory", detail="")]
    findings: list[Finding] = []
    auth_keys = ssh / "authorized_keys"
    if auth_keys.exists():
        try:
            content = auth_keys.read_text()
            lines = [l for l in content.splitlines() if l.strip() and not l.startswith("#")]
            findings.append(
                Finding(
                    severity="MED" if lines else "INFO",
                    title=f"~/.ssh/authorized_keys contains {len(lines)} key(s)",
                    detail=(
                        "These are public keys allowed to SSH INTO your Mac. If unrecognized, "
                        "remove them. If you don't use SSH to your Mac at all, this file shouldn't exist."
                    ),
                    recommendation="Open `~/.ssh/authorized_keys` and verify each key is yours.",
                    evidence=[l[:80] + "…" if len(l) > 80 else l for l in lines[:5]],
                )
            )
        except OSError:
            pass
    try:
        contents = sorted(p.name for p in ssh.iterdir())
        findings.append(
            Finding(
                severity="INFO",
                title="~/.ssh inventory",
                detail="Files in your SSH directory.",
                evidence=contents,
            )
        )
    except OSError:
        pass
    return findings


# ---- Check: shell RC hashes ----


def check_shell_rc(cfg) -> list[Finding]:
    findings: list[Finding] = []
    for rc in cfg.shell_rc_files:
        if not rc.exists():
            continue
        try:
            data = rc.read_bytes()
        except OSError:
            continue
        digest = hashlib.sha256(data).hexdigest()[:16]
        size = len(data)
        findings.append(
            Finding(
                severity="INFO",
                title=f"{rc.name} hash + size",
                detail=f"sha256={digest}  size={size}B",
                evidence=[str(rc)],
            )
        )
    return findings


# ---- Check: open network listeners ----


def check_open_ports() -> list[Finding]:
    try:
        result = subprocess.run(
            ["lsof", "-iTCP", "-sTCP:LISTEN", "-P", "-n"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    lines = (result.stdout or "").splitlines()[1:]
    if not lines:
        return [Finding(severity="INFO", title="No listening TCP ports", detail="")]
    # Filter to non-loopback to highlight externally-exposed
    external = [l for l in lines if "127.0.0.1" not in l and "::1" not in l]
    findings: list[Finding] = []
    findings.append(
        Finding(
            severity="INFO",
            title=f"{len(lines)} listening TCP port(s); {len(external)} externally-bound",
            detail="Services listening on the network. External-bound (non-loopback) are worth verifying.",
            evidence=external[:10] if external else lines[:5],
        )
    )
    return findings


# ---- Check: device hygiene ----


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def check_device_hygiene() -> list[Finding]:
    findings: list[Finding] = []
    sip = _run(["csrutil", "status"])
    if sip:
        enabled = "enabled" in sip.lower()
        findings.append(
            Finding(
                severity="INFO" if enabled else "HIGH",
                title=f"SIP (System Integrity Protection) — {'enabled' if enabled else 'DISABLED'}",
                detail=sip,
                recommendation="" if enabled else "Re-enable SIP from Recovery Mode unless you intentionally disabled it.",
            )
        )
    gk = _run(["spctl", "--status"])
    if gk:
        enabled = "enabled" in gk.lower()
        findings.append(
            Finding(
                severity="INFO" if enabled else "MED",
                title=f"Gatekeeper — {'enabled' if enabled else 'disabled'}",
                detail=gk,
                recommendation="" if enabled else "Re-enable via `sudo spctl --master-enable`.",
            )
        )
    fv = _run(["fdesetup", "status"])
    if fv:
        on = "is on" in fv.lower()
        findings.append(
            Finding(
                severity="INFO" if on else "MED",
                title=f"FileVault — {'on' if on else 'OFF'}",
                detail=fv,
                recommendation="" if on else "Turn on FileVault in System Settings → Privacy & Security.",
            )
        )
    macos = _run(["sw_vers", "-productVersion"])
    if macos:
        findings.append(
            Finding(severity="INFO", title=f"macOS version: {macos}", detail="")
        )
    return findings


# ---- Check: zsh history red flags ----


def check_zsh_history() -> list[Finding]:
    hist = Path.home() / ".zsh_history"
    if not hist.exists():
        return []
    try:
        data = hist.read_text(errors="replace")
    except OSError:
        return []
    flagged: list[tuple[int, str, str]] = []
    for i, line in enumerate(data.splitlines(), start=1):
        # Strip EXTENDED_HISTORY prefix `: timestamp:dur;`
        m = re.match(r"^: \d+:\d+;(.*)$", line)
        cmd = m.group(1) if m else line
        for _pat, why in scan_shell_line(cmd):
            flagged.append((i, why, cmd[:200]))
            break
    if flagged:
        return [
            Finding(
                severity="HIGH",
                title=f"{len(flagged)} suspicious line(s) in zsh history",
                detail=(
                    "These shell commands match patterns commonly used to deliver malware "
                    "(curl piped to shell, base64-decoded payloads, etc.). A line being here "
                    "means it was entered — not necessarily executed (you may have Ctrl-C'd)."
                ),
                recommendation=(
                    "Review each. If you don't remember running it, you probably Ctrl-C'd "
                    "(safe) or pasted then deleted (also safe). If you ran it knowingly for a "
                    "legitimate reason, ignore. If you ran it unknowingly, treat as compromise — "
                    "use the browser-history check finding below to confirm."
                ),
                evidence=[f"line {i}: [{why}] {cmd}" for i, why, cmd in flagged[:10]],
            )
        ]
    return [Finding(severity="INFO", title="No zsh history red flags", detail="")]


# ---- Report assembly ----


def render_report(cfg, findings: list[Finding]) -> str:
    c = counts(findings)
    high = c.get("HIGH", 0)
    med = c.get("MED", 0)
    low = c.get("LOW", 0)
    info = c.get("INFO", 0)
    headline = "🚨 ACTION REQUIRED" if high else ("⚠️ Review recommended" if med else "✅ Clean audit")
    today = datetime.now().strftime("%Y-%m-%d %H:%M %Z")
    lines = [
        f"# ZergGuard audit — {today}",
        "",
        f"**Verdict**: {headline}",
        "",
        f"Findings: HIGH={high}  MED={med}  LOW={low}  INFO={info}",
        "",
        "---",
        "",
    ]
    for f in sort_findings(findings):
        lines.append(f.to_md())
        lines.append("")
    return "\n".join(lines)


def render_dm_summary(findings: list[Finding]) -> str:
    high = [f for f in findings if f.severity == "HIGH"]
    if not high:
        return ""
    lines = [f"ZergGuard found {len(high)} HIGH finding(s):"]
    for f in high[:5]:
        lines.append(f"• {f.title}")
    lines.append("Full report in vault Security/.")
    return "\n".join(lines)


def write_report(cfg, content: str) -> Path:
    cfg.report_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    path = cfg.report_dir / f"audit-{today}.md"
    path.write_text(content)
    return path


# ---- Entrypoint ----


def setup_interactive() -> int:
    print("ZergGuard setup walks you through ~/.config/zerg-guard/config.toml.")
    print("Defaults are already set for Matt. Edit the file directly to customize.")
    print(f"Open: {cfgmod.CONFIG_PATH}")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="zergguard-audit")
    ap.add_argument("--dry-run", action="store_true", help="don't write report, just print")
    ap.add_argument("--setup", action="store_true", help="open setup")
    ap.add_argument("--last", action="store_true", help="print last audit report")
    args = ap.parse_args(argv)

    if args.setup:
        return setup_interactive()

    cfg = cfgmod.load()

    if args.last:
        latest = None
        if cfg.report_dir.exists():
            md_files = sorted(cfg.report_dir.glob("audit-*.md"))
            latest = md_files[-1] if md_files else None
        if not latest:
            print("(no prior audit found)")
            return 0
        print(latest.read_text())
        return 0

    print("Running ZergGuard audit…", file=sys.stderr)
    findings: list[Finding] = []
    findings += check_browser_ioc(cfg)
    findings += check_launch_agents(cfg)
    findings += check_login_items()
    findings += check_running_processes(cfg)
    findings += check_recent_apps(cfg)
    findings += check_browser_extensions(cfg)
    findings += check_ssh()
    findings += check_shell_rc(cfg)
    findings += check_open_ports()
    findings += check_device_hygiene()
    findings += check_zsh_history()

    report = render_report(cfg, findings)

    if args.dry_run:
        print(report)
        return 0

    path = write_report(cfg, report)
    print(f"Report → {path}", file=sys.stderr)

    dm = render_dm_summary(findings)
    if dm:
        notify(cfg, "ZergGuard HIGH-severity findings", dm)

    c = counts(findings)
    print(
        f"HIGH={c.get('HIGH', 0)}  MED={c.get('MED', 0)}  "
        f"LOW={c.get('LOW', 0)}  INFO={c.get('INFO', 0)}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
