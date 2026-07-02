#!/usr/bin/env python3
"""ZergGuard onboarding wizard. First-run setup or reconfigure."""

from __future__ import annotations

import sys
from pathlib import Path

CFG = Path.home() / ".config" / "zerg-guard" / "config.toml"

DEFAULT = """\
# ZergGuard config

[identity]
emails = ["{email}"]
display_name = "{name}"

[output]
report_dir = "{report_dir}"
state_dir = "{state_dir}"

[notify]
method = "{notify}"
fakematt_slack_channel = "{slack}"

[audit]
allow_sudo = false
attack_window_floor = "{floor}"
browsers = ["chrome", "safari", "brave"]
shell_rc_files = ["~/.zshrc", "~/.zshenv", "~/.bash_profile", "~/.profile", "~/.bashrc"]

[ioc]
extra_domains = []
extra_process_patterns = []
"""


def ask(prompt: str, default: str) -> str:
    raw = input(f"{prompt} [{default}]: ").strip()
    return raw or default


def main() -> int:
    print("ZergGuard setup\n---")
    if CFG.exists():
        print(f"Existing config at {CFG}")
        if ask("Overwrite? (y/n)", "n").lower() != "y":
            print("Keeping existing config. Edit manually or run setup again.")
            return 0
    email = ask("Your email", "you@example.com")
    name = ask("Display name", "User")
    report_dir = ask("Where should reports be written", str(Path.home() / "Documents" / "ZergGuard"))
    state_dir = ask("Where should state files live", str(Path.home() / ".config" / "zerg-guard"))
    notify_choice = ask("Notification method (fakematt-slack | macos-notification | stdout-only)", "macos-notification")
    slack = ""
    if notify_choice == "fakematt-slack":
        slack = ask("Fake Matt Slack DM channel ID", "")
    floor = ask("Attack window floor date (YYYY-MM-DD; leave blank for none)", "")

    CFG.parent.mkdir(parents=True, exist_ok=True)
    CFG.write_text(DEFAULT.format(
        email=email, name=name,
        report_dir=report_dir, state_dir=state_dir,
        notify=notify_choice, slack=slack, floor=floor,
    ))
    print(f"\nWrote {CFG}")
    print("\nNext steps:")
    print("  1) python3 ~/.claude/skills/zergguard-audit/audit.py     # first audit")
    print("  2) python3 ~/.claude/skills/zergguard-identity/audit.py  # identity baseline")
    print("  3) python3 ~/.claude/skills/zergguard-identity/audit.py --setup-2fa-list")
    print("  4) launchctl load ~/Library/LaunchAgents/com.matteisner.zergguard-*.plist")
    return 0


if __name__ == "__main__":
    sys.exit(main())
