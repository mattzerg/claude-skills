#!/usr/bin/env python3
"""ZergGuard identity audit — HIBP + 2FA + browser passwords."""

from __future__ import annotations

import argparse
import getpass
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

LIB = Path.home() / ".config" / "zerg-guard" / "lib"
sys.path.insert(0, str(LIB))

import config as cfgmod  # noqa: E402
from findings import Finding, sort_findings, counts  # noqa: E402
from chrome_passwords import all_saved_logins  # noqa: E402
from hibp import password_pwned_count, breach_lookup  # noqa: E402

TWO_FA_LIST_PATH = Path.home() / ".config" / "zerg-guard" / "2fa_status.toml"

HIGH_STAKES_DOMAINS = [
    # Banks
    "chase.com", "bankofamerica.com", "wellsfargo.com", "citi.com",
    "capitalone.com", "americanexpress.com",
    # Email
    "gmail.com", "icloud.com", "outlook.com", "fastmail.com", "proton.me",
    # Apple
    "apple.com", "appleid.apple.com",
    # Crypto
    "coinbase.com", "kraken.com", "binance.com", "gemini.com",
    # Dev
    "github.com", "gitlab.com", "npmjs.com", "pypi.org",
    # Hosting
    "aws.amazon.com", "console.cloud.google.com", "fly.io", "vercel.com",
    # Password managers
    "1password.com", "bitwarden.com",
]


def host_of(url: str) -> str:
    try:
        return urlparse(url if "://" in url else "http://" + url).hostname or ""
    except Exception:
        return ""


def check_browser_logins() -> tuple[list[Finding], dict[str, set[str]]]:
    """Return findings + per-browser set of hostnames."""
    findings: list[Finding] = []
    per_browser: dict[str, set[str]] = {}
    by_browser = all_saved_logins()
    for browser, logins in by_browser.items():
        hosts = {host_of(l["origin_url"]) for l in logins if host_of(l["origin_url"])}
        per_browser[browser] = hosts
        if logins:
            findings.append(
                Finding(
                    severity="INFO",
                    title=f"{browser}: {len(logins)} saved login(s) across {len(hosts)} site(s)",
                    detail="Saved-login inventory (metadata only; passwords not extracted).",
                    evidence=sorted(hosts)[:15],
                )
            )
    return findings, per_browser


def check_2fa(per_browser: dict[str, set[str]]) -> list[Finding]:
    """For each HIGH_STAKES domain that appears in saved logins, flag if 2fa_status doesn't confirm enrollment."""
    findings: list[Finding] = []
    confirmed: set[str] = set()
    if TWO_FA_LIST_PATH.exists():
        try:
            import tomllib
            data = tomllib.loads(TWO_FA_LIST_PATH.read_text())
            for k, v in data.get("enabled", {}).items():
                if v:
                    confirmed.add(k.lower())
        except Exception:
            pass

    all_hosts: set[str] = set().union(*per_browser.values()) if per_browser else set()
    flagged = []
    for stake in HIGH_STAKES_DOMAINS:
        # Check if any saved login matches this stake
        matched = any(stake in h for h in all_hosts)
        if matched and stake not in confirmed:
            flagged.append(stake)
    if flagged:
        findings.append(
            Finding(
                severity="HIGH",
                title=f"{len(flagged)} high-stakes service(s) with no confirmed 2FA",
                detail=(
                    "You have saved logins for these sites but haven't confirmed 2FA "
                    "enrollment in `~/.config/zerg-guard/2fa_status.toml`. Either "
                    "enable 2FA (recommended) or mark as enrolled in the config."
                ),
                recommendation=(
                    "Open each site → Settings → Security → enable 2FA "
                    "(authenticator app preferred over SMS). Then mark `enabled = true` "
                    "in `~/.config/zerg-guard/2fa_status.toml`."
                ),
                evidence=flagged[:10],
            )
        )
    else:
        findings.append(
            Finding(
                severity="INFO",
                title="No high-stakes services missing 2FA confirmation",
                detail="All high-stakes services either confirmed in 2fa_status.toml or absent from saved logins.",
            )
        )
    return findings


def check_email_breaches(cfg) -> list[Finding]:
    findings: list[Finding] = []
    import os
    if not os.environ.get("HIBP_API_KEY"):
        findings.append(
            Finding(
                severity="INFO",
                title="HIBP email-breach lookup skipped (no API key)",
                detail="Set HIBP_API_KEY env to enable. Paid subscription required from haveibeenpwned.com.",
            )
        )
        return findings
    for email in cfg.emails:
        breaches = breach_lookup(email)
        if breaches is None:
            findings.append(
                Finding(
                    severity="LOW",
                    title=f"HIBP lookup failed for {email}",
                    detail="API call failed; check HIBP_API_KEY validity + rate limit.",
                )
            )
        elif breaches:
            names = [b.get("Name", "?") for b in breaches[:10]]
            findings.append(
                Finding(
                    severity="HIGH",
                    title=f"{email} appears in {len(breaches)} known breach(es)",
                    detail="Treat any password reused on these services as compromised. Rotate immediately.",
                    recommendation="For each breach, identify the service, change the password, and ensure 2FA is enabled.",
                    evidence=names,
                )
            )
        else:
            findings.append(
                Finding(
                    severity="INFO",
                    title=f"{email} not in any known breach (HIBP)",
                    detail="Email has not been seen in any breach indexed by HIBP.",
                )
            )
    return findings


def write_report(cfg, findings: list[Finding]) -> Path:
    cfg.report_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    path = cfg.report_dir / f"identity-{today}.md"
    c = counts(findings)
    today_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# ZergGuard identity audit — {today_str}",
        "",
        f"Findings: HIGH={c.get('HIGH', 0)}  MED={c.get('MED', 0)}  "
        f"LOW={c.get('LOW', 0)}  INFO={c.get('INFO', 0)}",
        "",
        "---",
        "",
    ]
    for f in sort_findings(findings):
        lines.append(f.to_md())
        lines.append("")
    path.write_text("\n".join(lines))
    return path


def cmd_check_password(password: str) -> int:
    count = password_pwned_count(password)
    if count < 0:
        print("ERROR: network/API failure")
        return 2
    if count == 0:
        print(f"SAFE: password not seen in HIBP breach corpus")
        return 0
    print(f"PWNED: password appears in {count} known breaches — DO NOT USE")
    return 1


def cmd_setup_2fa_list() -> int:
    if not TWO_FA_LIST_PATH.exists():
        TWO_FA_LIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        content = ["# Mark which high-stakes services have 2FA enabled.\n", "[enabled]\n"]
        for d in HIGH_STAKES_DOMAINS:
            content.append(f'"{d}" = false\n')
        TWO_FA_LIST_PATH.write_text("".join(content))
    import subprocess
    subprocess.run(["open", str(TWO_FA_LIST_PATH)])
    print(f"Opened {TWO_FA_LIST_PATH} for editing.")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="zergguard-identity")
    ap.add_argument("--check-password", help="K-anonymity HIBP check on a password (not sent plaintext)")
    ap.add_argument("--setup-2fa-list", action="store_true")
    args = ap.parse_args(argv)

    if args.check_password is not None:
        pw = args.check_password
        if pw == "":
            pw = getpass.getpass("Password (not echoed): ")
        return cmd_check_password(pw)
    if args.setup_2fa_list:
        return cmd_setup_2fa_list()

    cfg = cfgmod.load()
    findings: list[Finding] = []
    browser_findings, per_browser = check_browser_logins()
    findings.extend(browser_findings)
    findings.extend(check_2fa(per_browser))
    findings.extend(check_email_breaches(cfg))

    path = write_report(cfg, findings)
    print(f"Report → {path}", file=sys.stderr)
    c = counts(findings)
    print(
        f"identity: HIGH={c.get('HIGH', 0)}  MED={c.get('MED', 0)}  "
        f"LOW={c.get('LOW', 0)}  INFO={c.get('INFO', 0)}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
