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


RAW_OUTGOING_ROOT = Path(__file__).parent / "raw_outgoing"


def append_to_raw_outgoing(samples: list[dict], account: str) -> int:
    """Append harvested samples to raw_outgoing/<account>/<year>.md — the
    corpus the exemplar-first drafting system (voice_priors.py) reads. Added
    2026-06-02: previously the weekly refresh only updated the vault corpus
    file, so exemplar retrieval slowly went stale."""
    if not samples:
        return 0
    account_short = account.split("@")[0]
    if account == "matthew@zergai.com":
        account_short = "matthew"
    account_dir = RAW_OUTGOING_ROOT / account_short
    account_dir.mkdir(parents=True, exist_ok=True)
    appended = 0
    for s in samples:
        date = (s.get("date") or "")[:10]
        year = date[:4] or str(dt.datetime.now().year)
        year_file = account_dir / f"{year}.md"
        # dedup by msg_id
        if year_file.exists() and s["id"] in year_file.read_text():
            continue
        with open(year_file, "a") as f:
            f.write(f"\n---\ndate: {date}\nto: {s['to']}\n"
                    f"subject: {s.get('subject','')}\nmsg_id: {s['id']}\n---\n\n")
            f.write(s["body"].strip() + "\n")
        appended += 1
    return appended


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
        raw_added = append_to_raw_outgoing(new, account)
        print(f"[refresh] {account}: harvested {len(new)} new, appended {added} "
              f"(vault corpus) + {raw_added} (raw_outgoing)")
        total_added += added

    print(f"[refresh] total new samples: {total_added}")

    # 2026-06-02 voice overhaul: recompute structural priors whenever the
    # corpus refreshes (professional + family segments). Pure Python, no LLM.
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from voice_priors import compute_structural_priors
        compute_structural_priors(force=True)
        personal_dir = Path.home() / ".claude" / "skills" / "fakematt-personal"
        if personal_dir.exists() and TIER_MAP.exists():
            data = json.loads(TIER_MAP.read_text())
            fam = {e.lower() for e in data.get("_excluded", {}).get("members", [])}
            fam.discard("matteisn@gmail.com")
            if fam:
                years = tuple(str(y) for y in range(2018, dt.datetime.now().year + 1))
                compute_structural_priors(
                    force=True, recipient_filter=fam,
                    cache_path=personal_dir / "structural_priors.json",
                    years=years,
                )
        print("[refresh] structural priors recomputed (professional + family)")
    except Exception as e:
        print(f"[refresh] priors recompute failed (non-fatal): {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
