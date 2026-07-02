#!/usr/bin/env python3
"""Summarize local Codex rate-limit usage and optionally switch accounts."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CODEX_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
CONFIG_PATH = CODEX_HOME / "account-router" / "accounts.json"


@dataclass
class Usage:
    account_id: str
    label: str
    primary_used: float | None
    secondary_used: float | None
    primary_resets_at: int | None
    secondary_resets_at: int | None
    plan_type: str | None
    source: str
    timestamp: str
    is_current: bool = False
    switch_command: str | None = None

    def score(self) -> tuple[float, float]:
        return (
            self.primary_used if self.primary_used is not None else 1.0,
            self.secondary_used if self.secondary_used is not None else 1.0,
        )


def load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc


def load_account_config() -> dict[str, dict[str, str]]:
    data = load_json(CONFIG_PATH) or {}
    accounts = data.get("accounts", {})
    if not isinstance(accounts, dict):
        raise SystemExit(f"{CONFIG_PATH} must contain an object at key 'accounts'")
    return accounts


def current_account_id() -> str | None:
    auth = load_json(CODEX_HOME / "auth.json") or {}
    tokens = auth.get("tokens") if isinstance(auth, dict) else None
    if isinstance(tokens, dict):
        account_id = tokens.get("account_id")
        if isinstance(account_id, str):
            return account_id
    return None


def iter_session_files(limit: int) -> list[Path]:
    sessions = CODEX_HOME / "sessions"
    if not sessions.exists():
        return []
    files = [p for p in sessions.rglob("*.jsonl") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]


def extract_usage(files: list[Path], account_cfg: dict[str, dict[str, str]]) -> dict[str, Usage]:
    current = current_account_id()
    latest: dict[str, Usage] = {}
    for path in files:
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = row.get("payload", {})
            rate_limits = payload.get("rate_limits") if isinstance(payload, dict) else None
            if not isinstance(rate_limits, dict):
                continue
            account_id = str(rate_limits.get("account_id") or rate_limits.get("limit_id") or "unknown")
            primary = rate_limits.get("primary") or {}
            secondary = rate_limits.get("secondary") or {}
            cfg = account_cfg.get(account_id, {})
            usage = Usage(
                account_id=account_id,
                label=cfg.get("label", account_id),
                primary_used=_as_float(primary.get("used_percent")),
                secondary_used=_as_float(secondary.get("used_percent")),
                primary_resets_at=_as_int(primary.get("resets_at")),
                secondary_resets_at=_as_int(secondary.get("resets_at")),
                plan_type=rate_limits.get("plan_type"),
                source=str(path),
                timestamp=str(row.get("timestamp", "")),
                is_current=(account_id == current),
                switch_command=cfg.get("switch_command"),
            )
            prev = latest.get(account_id)
            if prev is None or usage.timestamp > prev.timestamp:
                latest[account_id] = usage
    if current and current not in latest:
        cfg = account_cfg.get(current, {})
        latest[current] = Usage(
            account_id=current,
            label=cfg.get("label", current),
            primary_used=None,
            secondary_used=None,
            primary_resets_at=None,
            secondary_resets_at=None,
            plan_type=None,
            source=str(CODEX_HOME / "auth.json"),
            timestamp="",
            is_current=True,
            switch_command=cfg.get("switch_command"),
        )
    return latest


def _as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _as_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    return None


def fmt_percent(value: float | None) -> str:
    if value is None:
        return "unknown"
    return f"{value * 100:.1f}%"


def fmt_reset(value: int | None) -> str:
    if value is None:
        return "-"
    return datetime.fromtimestamp(value, timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")


def choose_best(usages: dict[str, Usage]) -> Usage | None:
    if not usages:
        return None
    return sorted(usages.values(), key=lambda item: item.score())[0]


def print_status(usages: dict[str, Usage], as_json: bool) -> None:
    best = choose_best(usages)
    if as_json:
        print(json.dumps({
            "best_account_id": best.account_id if best else None,
            "accounts": [usage_to_dict(u) for u in sorted(usages.values(), key=lambda item: item.score())],
            "config_path": str(CONFIG_PATH),
        }, indent=2))
        return
    if not usages:
        print("No rate-limit events found in local Codex session logs.")
        print(f"Add labels/switch commands at: {CONFIG_PATH}")
        return
    print("Codex usage by observed account:")
    for usage in sorted(usages.values(), key=lambda item: item.score()):
        marker = "current" if usage.is_current else "       "
        print(
            f"- {marker} {usage.label} ({usage.account_id}) "
            f"primary={fmt_percent(usage.primary_used)} "
            f"secondary={fmt_percent(usage.secondary_used)} "
            f"plan={usage.plan_type or '-'} "
            f"primary_reset={fmt_reset(usage.primary_resets_at)}"
        )
    if best:
        print(f"\nRecommended account: {best.label} ({best.account_id})")
        if best.is_current:
            print("Current account is already the lowest-usage observed account.")
        elif best.switch_command:
            print(f"Configured switch command: {best.switch_command}")
        else:
            print(f"No switch_command configured. Add one in {CONFIG_PATH}.")


def usage_to_dict(usage: Usage) -> dict[str, Any]:
    return {
        "account_id": usage.account_id,
        "label": usage.label,
        "primary_used_percent": usage.primary_used,
        "secondary_used_percent": usage.secondary_used,
        "primary_resets_at": usage.primary_resets_at,
        "secondary_resets_at": usage.secondary_resets_at,
        "plan_type": usage.plan_type,
        "timestamp": usage.timestamp,
        "is_current": usage.is_current,
        "has_switch_command": bool(usage.switch_command),
        "source": usage.source,
    }


def cmd_status(args: argparse.Namespace) -> int:
    cfg = load_account_config()
    usages = extract_usage(iter_session_files(args.session_files), cfg)
    print_status(usages, args.json)
    return 0


def cmd_switch(args: argparse.Namespace) -> int:
    cfg = load_account_config()
    usages = extract_usage(iter_session_files(args.session_files), cfg)
    best = choose_best(usages)
    if best is None:
        print("No observed account usage found; cannot choose a target.", file=sys.stderr)
        return 2
    if best.is_current:
        print(f"Already on recommended account: {best.label} ({best.account_id})")
        return 0
    if not best.switch_command:
        print(f"Recommended account has no switch_command: {best.label} ({best.account_id})", file=sys.stderr)
        print(f"Configure it in {CONFIG_PATH}", file=sys.stderr)
        return 3
    print(f"Switching to {best.label} ({best.account_id})")
    print(f"Running: {best.switch_command}")
    if args.dry_run:
        return 0
    return subprocess.call(shlex.split(best.switch_command))


def cmd_init_config(_: argparse.Namespace) -> int:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if CONFIG_PATH.exists():
        print(f"Config already exists: {CONFIG_PATH}")
        return 0
    current = current_account_id() or "replace-with-account-id"
    data = {
        "accounts": {
            current: {
                "label": "current-codex-account",
                "switch_command": "codex login --device-auth",
            }
        }
    }
    CONFIG_PATH.write_text(json.dumps(data, indent=2) + "\n")
    print(f"Created {CONFIG_PATH}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-files", type=int, default=80, help="Recent session files to scan")
    sub = parser.add_subparsers(required=True)

    status = sub.add_parser("status", help="Show observed account usage")
    status.add_argument("--json", action="store_true", help="Emit JSON")
    status.set_defaults(func=cmd_status)

    switch = sub.add_parser("switch", help="Switch to the recommended lower-usage account")
    switch.add_argument("--dry-run", action="store_true", help="Print command without running it")
    switch.set_defaults(func=cmd_switch)

    init = sub.add_parser("init-config", help="Create an account label/switch config template")
    init.set_defaults(func=cmd_init_config)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
