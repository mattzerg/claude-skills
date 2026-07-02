"""max_client: Anthropic SDK client wired to Matt's Claude Code Max plan
OAuth token instead of an API key.

By default reads the LIVE OAuth credential from macOS Keychain at
  service: "Claude Code-credentials"
  account: "mattheweisner"

For long-running scripts that should NOT compete with the active Claude Code
session for Max-plan rate limits, you can pass `account="<label>"` (or set
env var `IDEA_BACKLOG_MAX_ACCOUNT`) and we read the stashed OAuth blob from
  ~/.config/anthropic-router/max-creds/<label>/keychain.json
without disturbing the live Keychain entry.

It's a JSON blob with `claudeAiOauth.accessToken`. The Anthropic Python SDK
accepts that as `auth_token=` and sends it as `Authorization: Bearer <token>`,
which the api.anthropic.com endpoint accepts for Max-plan SDK calls.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

KEYCHAIN_SERVICE = "Claude Code-credentials"
KEYCHAIN_ACCOUNT = "mattheweisner"
ANTHROPIC_BETA_HEADER = "oauth-2025-04-20"
STASH_ROOT = Path.home() / ".config" / "anthropic-router" / "max-creds"


def _read_live_oauth_blob() -> str:
    r = subprocess.run(
        ["security", "find-generic-password",
         "-s", KEYCHAIN_SERVICE, "-a", KEYCHAIN_ACCOUNT, "-w"],
        capture_output=True, text=True, check=False,
    )
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError(
            f"Could not read Keychain entry {KEYCHAIN_SERVICE}/{KEYCHAIN_ACCOUNT}. "
            "Either the Max plan isn't authenticated (`claude /login`) or Keychain access denied."
        )
    return r.stdout.strip()


def _read_stashed_oauth_blob(label: str) -> str:
    p = STASH_ROOT / label / "keychain.json"
    if not p.exists():
        raise RuntimeError(
            f"Stashed account {label!r} not found at {p}. "
            f"Available: {[d.name for d in STASH_ROOT.iterdir() if d.is_dir()]}"
        )
    return p.read_text()


def _access_token(account: str | None) -> str:
    blob = _read_stashed_oauth_blob(account) if account else _read_live_oauth_blob()
    try:
        data = json.loads(blob)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"OAuth blob isn't JSON: {e}") from e
    oauth = data.get("claudeAiOauth") or {}
    tok = oauth.get("accessToken")
    if not tok:
        raise RuntimeError("OAuth blob has no claudeAiOauth.accessToken")
    return tok


def make_client(*, source: str | None = None, account: str | None = None, **client_kwargs: Any):
    """Return an anthropic.Anthropic client authenticated to the Max plan.

    `account` (or env IDEA_BACKLOG_MAX_ACCOUNT) selects a STASHED OAuth
    credential by label so scripts don't share the live session's rate limits.
    """
    try:
        import anthropic
    except ImportError as e:
        raise ImportError("anthropic SDK not installed. `pip3 install anthropic`.") from e

    if account is None:
        account = os.environ.get("IDEA_BACKLOG_MAX_ACCOUNT") or None

    token = _access_token(account)
    client_kwargs.setdefault("auth_token", token)
    client_kwargs.setdefault("default_headers", {})
    headers = dict(client_kwargs["default_headers"])
    headers.setdefault("anthropic-beta", ANTHROPIC_BETA_HEADER)
    client_kwargs["default_headers"] = headers
    return anthropic.Anthropic(**client_kwargs)
