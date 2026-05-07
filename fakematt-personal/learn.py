#!/usr/bin/env python3
"""Fake Matt personal email — learning loop.

Mirror of fakematt-email/learn.py for the personal skill. Diffs logged drafts
vs. actual sent body, appends to corrections.md.

Usage:
    python3 ~/.claude/skills/fakematt-personal/learn.py [--max-age-days 90]
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import difflib
import json
import re
import sys
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import warnings
warnings.filterwarnings("ignore")

SKILL_DIR = Path(__file__).parent
SENT_LOG = SKILL_DIR / "sent-log.jsonl"
CORRECTIONS = SKILL_DIR / "corrections.md"
TOKENS_DIR = Path.home() / ".claude" / "skills" / "gmail-skill" / "tokens"
CREDS_FILE = Path.home() / ".claude" / "skills" / "gmail-skill" / "credentials.json"


def make_service(account: str):
    candidates = list(TOKENS_DIR.glob(f"token_{account.split('@')[0]}_*.json"))
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
        try: return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="ignore")
        except: pass
    for p in payload.get("parts", []) or []:
        if p.get("mimeType", "").startswith("text/plain"):
            data = p.get("body", {}).get("data")
            if data:
                try: return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                except: pass
        s = extract_body(p)
        if s: return s
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


def find_sent_for_record(svc, record):
    to = record["to"]
    after_ts = record["ts"]
    try:
        after_date = dt.datetime.strptime(after_ts[:8], "%Y%m%d").strftime("%Y/%m/%d")
    except Exception:
        after_date = "2026/01/01"
    q = f"in:sent to:{to} after:{after_date}"
    res = svc.users().messages().list(userId="me", q=q, maxResults=10).execute()
    for m in res.get("messages", []):
        full = svc.users().messages().get(userId="me", id=m["id"], format="full").execute()
        body = extract_body(full.get("payload", {}))
        cleaned = clean_outgoing(body)
        if len(cleaned) > 30:
            return cleaned, m["id"]
    return None, None


def diff_summary(generated, sent):
    g = [l.rstrip() for l in generated.splitlines()]
    s = [l.rstrip() for l in sent.splitlines()]
    diff = list(difflib.unified_diff(g, s, lineterm="", n=2))
    changed = sum(1 for l in diff if l.startswith(("+", "-")) and not l.startswith(("+++", "---")) and l[1:].strip())
    return "\n".join(diff), changed


def append_correction(record, sent_body, diff_text, changed):
    if not CORRECTIONS.exists():
        CORRECTIONS.write_text(
            "# Recent corrections (personal)\n\n"
            "Diff log of edits Matt makes to fakematt-personal drafts before sending.\n"
            "Older entries (>90 days) are pruned automatically.\n\n---\n\n"
        )
    today = dt.date.today().isoformat()
    with open(CORRECTIONS, "a") as f:
        f.write(f"\n## {today} — to {record['to']}\n\n")
        f.write(f"**Original draft:**\n\n```\n{record['generated_body']}\n```\n\n")
        f.write(f"**What Matt sent:**\n\n```\n{sent_body}\n```\n\n")
        if changed:
            f.write(f"**Diff** ({changed} changed lines):\n\n```diff\n{diff_text}\n```\n\n")
        f.write("---\n")


def prune_old_corrections(max_age_days=90):
    if not CORRECTIONS.exists():
        return
    cutoff = dt.date.today() - dt.timedelta(days=max_age_days)
    text = CORRECTIONS.read_text()
    sections = re.split(r"(\n## (\d{4}-\d{2}-\d{2}) —[^\n]*\n)", text)
    if len(sections) < 4:
        return
    head = sections[0]
    new_parts = [head]
    i = 1
    while i < len(sections) - 1:
        header_full, header_date = sections[i], sections[i + 1]
        body = sections[i + 2] if i + 2 < len(sections) else ""
        try:
            d = dt.date.fromisoformat(header_date)
        except:
            d = dt.date.today()
        if d >= cutoff:
            new_parts.append(header_full + body)
        i += 3
    CORRECTIONS.write_text("".join(new_parts))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-age-days", type=int, default=90)
    args = ap.parse_args()
    if not SENT_LOG.exists():
        print("[learn] no sent-log yet"); return 0
    records = []
    with open(SENT_LOG) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try: records.append(json.loads(line))
            except: continue
    pending = [r for r in records if not r.get("checked")]
    print(f"[learn] {len(pending)} unchecked / {len(records)} total")

    svc_cache = {}
    updated = 0
    for record in pending:
        account = record.get("account", "matteisn@gmail.com")
        if account not in svc_cache:
            svc_cache[account] = make_service(account)
        svc = svc_cache[account]
        if not svc: continue
        sent_body, sent_id = find_sent_for_record(svc, record)
        if not sent_body: continue
        generated = record.get("generated_body", "").strip()
        if not generated: continue
        diff_text, changed = diff_summary(generated, sent_body)
        if changed >= 2:
            append_correction(record, sent_body, diff_text, changed)
            print(f"[learn] correction logged: to={record['to']} changed={changed}")
            updated += 1
        else:
            print(f"[learn] no material edit: to={record['to']}")
        record["checked"] = True
        record["sent_msg_id"] = sent_id
        record["edit_distance"] = changed
    with open(SENT_LOG, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    prune_old_corrections(args.max_age_days)
    print(f"[learn] {updated} new corrections appended")
    return 0


if __name__ == "__main__":
    sys.exit(main())
