#!/usr/bin/env python3
"""Fake Matt email skill — corpus refresh.

Pulls last 7 days of sent mail from both Gmail accounts, strips quoted threads,
and appends new outgoing samples to MattZerg/_style/professional_voice_corpus.md.

Designed to run as a weekly cron job (Sundays at 4am, alongside the existing
fakematt-feedback corpus refreshers).

Usage:
    python3 ~/.claude/skills/fakematt-email/refresh.py [--days N]
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import re
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import warnings
warnings.filterwarnings("ignore")

def _resolve_vault_root(sub: str = "Zerg/MattZerg") -> Path:
    """Live vault is ~/Obsidian/<sub>; the iCloud path was retired 2026-06-24.
    Prefer the live path, fall back to the legacy iCloud path only if it still exists."""
    primary = Path.home() / "Obsidian" / sub
    if primary.exists():
        return primary
    legacy = (
        Path.home()
        / "Library" / "Mobile Documents" / "iCloud~md~obsidian" / "Documents" / sub
    )
    return legacy if legacy.exists() else primary


VAULT_ROOT = _resolve_vault_root("Zerg/MattZerg")
CORPUS = VAULT_ROOT / "_style" / "professional_voice_corpus.md"
TIER_MAP = Path(__file__).parent / "tier_map.json"
TOKENS = Path.home() / ".claude" / "skills" / "gmail-skill" / "tokens"
CREDS_FILE = Path.home() / ".claude" / "skills" / "gmail-skill" / "credentials.json"
ACCOUNTS = ["matteisn@gmail.com", "matthew@zergai.com"]


def make_service(account: str):
    tok_file = TOKENS / f"token_{account.replace('@','_').replace('.','_').lower().replace('@','_')}.json"
    # Token files use underscores instead of dots/at-signs
    candidates = list(TOKENS.glob(f"token_{account.split('@')[0]}_*.json"))
    if not candidates:
        return None
    with open(candidates[0]) as f:
        tok = json.load(f)
    with open(CREDS_FILE) as f:
        cred = json.load(f)
    ci = cred.get("installed") or cred.get("web") or cred
    creds = Credentials(
        token=tok["access_token"],
        refresh_token=tok.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=ci["client_id"],
        client_secret=ci["client_secret"],
        scopes=tok.get("scope", "").split(),
    )
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def extract_body(payload):
    if payload.get("body", {}).get("data"):
        try:
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="ignore")
        except Exception:
            pass
    for p in payload.get("parts", []) or []:
        if p.get("mimeType", "").startswith("text/plain"):
            data = p.get("body", {}).get("data")
            if data:
                try:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                except Exception:
                    pass
        s = extract_body(p)
        if s:
            return s
    return ""


def clean_outgoing(body: str) -> str:
    """Remove signature + quoted previous messages from a sent email body."""
    lines = body.split("\n")
    out = []
    for line in lines:
        s = line.strip()
        if s == "_____________________________":
            break
        if re.match(r"^On .* wrote:$", s):
            break
        if s.startswith(">"):
            break
        if re.match(r"^Sent (from|with) ", s):
            break
        out.append(line)
    return "\n".join(out).strip()


def load_known_ids() -> set[str]:
    """Track which message IDs are already in the corpus to avoid duplicates."""
    if not CORPUS.exists():
        return set()
    text = CORPUS.read_text()
    return set(re.findall(r"<!-- gmail_id:([0-9a-f]+) -->", text))


def lookup_register(addr: str) -> str | None:
    if not addr:
        return None
    addr = addr.lower().strip()
    with open(TIER_MAP) as f:
        m = json.load(f)
    for reg in ("A", "B", "C"):
        if addr in [x.lower() for x in m[reg]["members"]]:
            return reg
    if addr in [x.lower() for x in m["_excluded"]["members"]]:
        return "EXCLUDED"
    return None


def harvest(svc, account: str, days: int, known: set[str]) -> list[dict]:
    """Pull recent sent emails, return new outgoing samples."""
    after_date = (dt.date.today() - dt.timedelta(days=days)).strftime("%Y/%m/%d")
    res = svc.users().messages().list(userId="me", q=f"in:sent after:{after_date}", maxResults=500).execute()
    msg_list = res.get("messages", [])
    new = []

    def fetch(eid):
        try:
            full = svc.users().messages().get(userId="me", id=eid, format="full").execute()
            h = {x["name"]: x["value"] for x in full.get("payload", {}).get("headers", [])}
            body = extract_body(full.get("payload", {}))
            cleaned = clean_outgoing(body)
            if len(cleaned) < 40:
                return None
            to = h.get("To", "")
            em = re.search(r"<([^>]+)>", to) or re.match(r"^(\S+@\S+)", to)
            addr = em.group(1).lower().strip().rstrip(",") if em else ""
            register = lookup_register(addr)
            if register == "EXCLUDED":
                return None
            return {
                "id": eid, "account": account, "to": addr,
                "subject": h.get("Subject", ""), "date": h.get("Date", ""),
                "body": cleaned, "register": register,
            }
        except Exception as e:
            print(f"  fetch {eid} failed: {e}", file=sys.stderr)
            return None

    # Sequential to avoid SSL session-reuse contention seen on macOS Python 3.9 + LibreSSL.
    # A weekly cron has no speed pressure.
    for m in msg_list:
        if m["id"] in known:
            continue
        r = fetch(m["id"])
        if r:
            new.append(r)
    return new


def append_to_corpus(samples: list[dict]) -> int:
    if not samples:
        return 0
    samples.sort(key=lambda x: x.get("date", ""))
    with open(CORPUS, "a") as f:
        for s in samples:
            reg = s.get("register") or "?"
            f.write(f"\n## To {s['to']} (Register {reg}, {s['account']}) | {s['date'][:16]} | \"{s['subject'][:60]}\"\n")
            f.write(f"<!-- gmail_id:{s['id']} -->\n\n")
            f.write(s["body"] + "\n\n---\n\n")
    return len(samples)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7, help="how far back to look (default 7)")
    args = ap.parse_args()

    known = load_known_ids()
    total_added = 0
    for account in ACCOUNTS:
        svc = make_service(account)
        if not svc:
            print(f"[refresh] no token for {account}, skipping", file=sys.stderr)
            continue
        new = harvest(svc, account, args.days, known)
        added = append_to_corpus(new)
        print(f"[refresh] {account}: harvested {len(new)} new, appended {added}")
        total_added += added

    print(f"[refresh] total new samples: {total_added}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
