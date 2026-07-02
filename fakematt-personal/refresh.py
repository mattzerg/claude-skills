#!/usr/bin/env python3
"""Fake Matt personal email — corpus refresh.

Pulls last 7 days of sent mail to EXCLUDED-list addresses (family/close friends),
strips quoted threads, and appends to MattZerg/_style/personal_voice_corpus.md.

Designed to run as a weekly cron (Sundays at 5:30am, 30min after the
fakematt-email refresh — they share Gmail tokens but write to different corpora).

Usage:
    python3 ~/.claude/skills/fakematt-personal/refresh.py [--days N]
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import re
import sys
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import warnings
warnings.filterwarnings("ignore")

def _vault_root() -> Path:
    """Prefer the live Obsidian vault (canonical); fall back to legacy iCloud or the
    TCC mirror. Pre-2026-06-30 this hardcoded the iCloud path, which became a near-
    empty shell after the vault moved to ~/Obsidian/Zerg — so corpus appends landed
    in the shell while canonical went stale. See _audit-2026-06-30-nobody-reads-code.md §4."""
    canonical = Path.home() / "Obsidian" / "Zerg" / "MattZerg"
    icloud = Path("/Users/mattheweisner/Library/Mobile Documents/iCloud~md~obsidian/Documents/Zerg/MattZerg")
    mirror = Path.home() / ".zerg-vault-mirror" / "MattZerg"
    for cand in (canonical, icloud, mirror):
        try:
            if cand.exists() and any(cand.iterdir()):
                return cand
        except (PermissionError, OSError):
            continue
    return canonical


VAULT_ROOT = _vault_root()
CORPUS = VAULT_ROOT / "_style" / "personal_voice_corpus.md"
TIER_MAP = Path.home() / ".claude" / "skills" / "fakematt-email" / "tier_map.json"
TOKENS = Path.home() / ".claude" / "skills" / "gmail-skill" / "tokens"
CREDS_FILE = Path.home() / ".claude" / "skills" / "gmail-skill" / "credentials.json"
ACCOUNTS = ["matteisn@gmail.com", "matthew@zergai.com"]


def make_service(account: str):
    candidates = list(TOKENS.glob(f"token_{account.split('@')[0]}_*.json"))
    if not candidates:
        return None
    with open(candidates[0]) as f:
        tok = json.load(f)
    with open(CREDS_FILE) as f:
        cred = json.load(f)
    ci = cred.get("installed") or cred.get("web") or cred
    creds = Credentials(
        token=tok["access_token"], refresh_token=tok.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=ci["client_id"], client_secret=ci["client_secret"],
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
    out = []
    for line in body.split("\n"):
        s = line.strip()
        if s == "_____________________________": break
        if re.match(r"^On .* wrote:$", s): break
        if s.startswith(">"): break
        if re.match(r"^Sent (from|with) ", s): break
        out.append(line)
    return "\n".join(out).strip()


def is_personal_prose(body: str) -> bool:
    """Aggressive filter — personal corpus should NOT include technical/log paste."""
    if len(body) < 40: return False
    if 'GMT' in body and body.count('GMT') > 1: return False
    if 'googleapis' in body.lower(): return False
    if 'TypeError' in body or 'Universal Analytics' in body: return False
    if body.count('https://') > 2: return False
    if body.count('error') > 1: return False
    return True


def load_excluded() -> set[str]:
    """Load the EXCLUDED list from fakematt-email's tier_map (these are personal)."""
    if not TIER_MAP.exists():
        return set()
    with open(TIER_MAP) as f:
        m = json.load(f)
    return {x.lower().strip() for x in m.get("_excluded", {}).get("members", [])}


def load_known_ids() -> set[str]:
    if not CORPUS.exists():
        return set()
    return set(re.findall(r"<!-- gmail_id:([0-9a-f]+) -->", CORPUS.read_text()))


def harvest(svc, account: str, days: int, known: set[str], excluded: set[str]) -> list[dict]:
    after_date = (dt.date.today() - dt.timedelta(days=days)).strftime("%Y/%m/%d")
    res = svc.users().messages().list(userId="me", q=f"in:sent after:{after_date}", maxResults=300).execute()
    new = []
    for m in res.get("messages", []):
        if m["id"] in known:
            continue
        try:
            full = svc.users().messages().get(userId="me", id=m["id"], format="full").execute()
            h = {x["name"]: x["value"] for x in full.get("payload", {}).get("headers", [])}
            to = h.get("To", "")
            em = re.search(r"<([^>]+)>", to) or re.match(r"^(\S+@\S+)", to)
            addr = em.group(1).lower().strip().rstrip(",") if em else ""
            if addr not in excluded:
                continue  # only personal-list addresses
            body = extract_body(full.get("payload", {}))
            cleaned = clean_outgoing(body)
            if not is_personal_prose(cleaned):
                continue
            new.append({
                "id": m["id"], "account": account, "to": addr,
                "subject": h.get("Subject", ""), "date": h.get("Date", ""),
                "body": cleaned,
            })
        except Exception as e:
            print(f"  fetch {m['id']} failed: {e}", file=sys.stderr)
    return new


def append_to_corpus(samples: list[dict]) -> int:
    if not samples:
        return 0
    samples.sort(key=lambda x: x.get("date", ""))
    with open(CORPUS, "a") as f:
        for s in samples:
            f.write(f"\n## To {s['to']} ({s['account']}) | {s['date'][:16]} | \"{s['subject'][:60]}\"\n")
            f.write(f"<!-- gmail_id:{s['id']} -->\n\n")
            f.write(s["body"] + "\n\n---\n\n")
    return len(samples)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    args = ap.parse_args()

    excluded = load_excluded()
    if not excluded:
        print("[refresh] no EXCLUDED list found in tier_map — aborting")
        return 1

    known = load_known_ids()
    total = 0
    for account in ACCOUNTS:
        svc = make_service(account)
        if not svc:
            print(f"[refresh] no token for {account}")
            continue
        new = harvest(svc, account, args.days, known, excluded)
        added = append_to_corpus(new)
        print(f"[refresh] {account}: {added} new personal samples")
        total += added
    print(f"[refresh] total: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
