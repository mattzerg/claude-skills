#!/usr/bin/env python3
"""Fake Matt email — learning loop.

For every draft logged by run.py (sent-log.jsonl), check whether Matt has
actually sent a message in that thread since. If yes, fetch the sent body and
diff it against our generated body. Material edits get appended to
`corrections.md`, which the next prompt reads. The skill gets smarter as Matt
edits.

Usage:
    python3 ~/.claude/skills/fakematt-email/learn.py [--max-age-days 30]

Designed to run as a daily cron (suggested 6am).
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
UNPAIRED_LOG = SKILL_DIR / "unpaired.jsonl"
TOKENS_DIR = Path.home() / ".claude" / "skills" / "gmail-skill" / "tokens"
CREDS_FILE = Path.home() / ".claude" / "skills" / "gmail-skill" / "credentials.json"

# Records older than this that still can't pair with a sent message get marked
# unpaired (checked=True, unpaired=True) and written to unpaired.jsonl for
# manual review via fm_corrected.py — instead of being re-queried forever.
UNPAIRED_AFTER_DAYS = 14

# Pairing-confidence floor: if the sent message's similarity to the draft is
# below this, the pairing is wrong or the logged draft body is junk (e.g. a
# CRM meta-note) — logging it as a correction would teach noise. Park instead.
MIN_PAIR_SIMILARITY = 0.2


def list_token_accounts() -> list[str]:
    """All accounts with a Gmail token, e.g. ['matteisn@gmail.com', 'matthew@zergai.com']."""
    accounts = []
    for p in TOKENS_DIR.glob("token_*.json"):
        # token_<user>_<domain>.json → <user>@<domain>
        stem = p.stem[len("token_"):]
        if "_" in stem:
            user, domain = stem.split("_", 1)
            accounts.append(f"{user}@{domain}")
    return accounts


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
    """Strip signature + quoted thread from a sent body."""
    out = []
    for line in body.split("\n"):
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


def find_sent_in_thread(svc, draft_id: str, account: str, after_ts: int):
    """If our draft has been sent (or was discarded + Matt sent his own version),
    find the corresponding sent message from `me` newer than after_ts and return
    its body. Returns None if no sent message yet.
    """
    # Look up the draft → see if it still exists (un-sent) or has become a message
    try:
        d = svc.users().drafts().get(userId="me", id=draft_id, format="metadata").execute()
        # Draft still exists — Matt hasn't sent yet
        thread_id = d.get("message", {}).get("threadId")
        return None, thread_id, "still-draft"
    except Exception:
        # Draft no longer exists — likely discarded or sent. Need to check sent folder.
        pass
    return None, None, "draft-gone"


def find_sent_for_record(svc, record: dict, skip_ids: set | None = None):
    """Given a sent-log record, find the sent message Matt actually sent in that
    thread (newer than the record's timestamp). Skip ids already claimed by an
    earlier record in this pass so a single sent message can't pair with
    multiple drafts.

    Tries progressively looser queries: exact to: match, then any-header match
    (catches cc/bcc, display-name addressing, and forwards), then recipient
    local-part only (catches Matt sending to a sibling address at the same org).
    """
    skip_ids = skip_ids or set()
    to = record["to"]
    after_ts = record["ts"]
    try:
        after_date = dt.datetime.strptime(after_ts[:8], "%Y%m%d").strftime("%Y/%m/%d")
    except Exception:
        after_date = "2026/01/01"

    local_part = to.split("@")[0] if "@" in to else to
    queries = [
        f"in:sent to:{to} after:{after_date}",
        f"in:sent {to} after:{after_date}",
    ]
    # Local-part fallback only when it's distinctive enough to not flood-match.
    if len(local_part) >= 5 and local_part.lower() not in {"hello", "info", "sales", "support", "contact", "admin"}:
        queries.append(f"in:sent {local_part} after:{after_date}")

    seen_ids: set[str] = set()
    for q in queries:
        try:
            res = svc.users().messages().list(userId="me", q=q, maxResults=10).execute()
        except Exception:
            continue
        for m in res.get("messages", []):
            if m["id"] in skip_ids or m["id"] in seen_ids:
                continue
            seen_ids.add(m["id"])
            full = svc.users().messages().get(userId="me", id=m["id"], format="full").execute()
            body = extract_body(full.get("payload", {}))
            cleaned = clean_outgoing(body)
            if len(cleaned) > 30:
                return cleaned, m["id"]
    return None, None


def record_age_days(record: dict) -> int:
    """Age of a sent-log record in days (0 if unparsable)."""
    try:
        ts = dt.datetime.strptime(record["ts"][:8], "%Y%m%d")
        return (dt.datetime.now() - ts).days
    except Exception:
        return 0


def mark_unpaired(record: dict, reason: str = "no-sent-match") -> None:
    """Park a record that can't confidently pair: flag it and append to
    unpaired.jsonl for manual review (fm_corrected.py --sent-file ...)."""
    record["checked"] = True
    record["unpaired"] = True
    with open(UNPAIRED_LOG, "a") as f:
        f.write(json.dumps({
            "ts": record.get("ts"),
            "to": record.get("to"),
            "account": record.get("account"),
            "register": record.get("register"),
            "generated_body": record.get("generated_body", ""),
            "parked": dt.date.today().isoformat(),
            "reason": reason,
        }) + "\n")


def diff_summary(generated: str, sent: str) -> tuple[str, int]:
    """Produce a unified-diff summary + a 'material edit' score (number of
    changed non-whitespace lines)."""
    g_lines = [l.rstrip() for l in generated.splitlines()]
    s_lines = [l.rstrip() for l in sent.splitlines()]
    diff = list(difflib.unified_diff(g_lines, s_lines, lineterm="", n=2))
    # Count material changes: lines starting with + or - (excluding headers + empty)
    changed = sum(1 for l in diff if l.startswith(("+", "-")) and not l.startswith(("+++", "---")) and l[1:].strip())
    return "\n".join(diff), changed


def append_correction(record: dict, sent_body: str, diff_text: str, changed: int) -> None:
    if not CORRECTIONS.exists():
        CORRECTIONS.write_text(
            "# Recent corrections\n\n"
            "When Matt edits a draft before sending, the diff is captured here. "
            "The next prompt sees this. Patterns of edit teach us what to do "
            "differently next time.\n\n"
            "Older corrections age out (>90 days) — see learn.py.\n\n"
            "---\n\n"
        )
    today = dt.date.today().isoformat()
    with open(CORRECTIONS, "a") as f:
        f.write(f"\n## {today} — to {record['to']} (Register {record['register']})\n\n")
        f.write(f"**Original draft:**\n\n```\n{record['generated_body']}\n```\n\n")
        f.write(f"**What Matt sent:**\n\n```\n{sent_body}\n```\n\n")
        if changed:
            f.write(f"**Diff** ({changed} changed lines):\n\n```diff\n{diff_text}\n```\n\n")
        f.write("---\n")


def prune_old_corrections(max_age_days: int = 90) -> None:
    """Drop sections older than max_age_days from corrections.md."""
    if not CORRECTIONS.exists():
        return
    cutoff = dt.date.today() - dt.timedelta(days=max_age_days)
    text = CORRECTIONS.read_text()
    # Split on section headers "## YYYY-MM-DD —"
    sections = re.split(r"(\n## (\d{4}-\d{2}-\d{2}) —[^\n]*\n)", text)
    if len(sections) < 4:
        return  # nothing to prune
    head = sections[0]
    new_parts = [head]
    i = 1
    while i < len(sections) - 1:
        header_full, header_date = sections[i], sections[i + 1]
        body = sections[i + 2] if i + 2 < len(sections) else ""
        try:
            d = dt.date.fromisoformat(header_date)
        except Exception:
            d = dt.date.today()
        if d >= cutoff:
            new_parts.append(header_full + body)
        i += 3
    CORRECTIONS.write_text("".join(new_parts))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-age-days", type=int, default=90,
                    help="prune corrections older than this (default 90)")
    args = ap.parse_args()

    if not SENT_LOG.exists():
        print("[learn] no sent-log yet, nothing to do")
        return 0

    records = []
    with open(SENT_LOG) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                continue

    pending = [r for r in records if not r.get("checked") and not r.get("synthetic")]
    n_synthetic = sum(1 for r in records if r.get("synthetic"))
    print(f"[learn] {len(pending)} unchecked draft(s); {len(records)} total "
          f"({n_synthetic} synthetic skipped)")

    # Reserve sent_msg_ids already claimed by previously-checked records so
    # we don't double-count one sent message against multiple drafts.
    claimed_ids: set[str] = {
        r["sent_msg_id"] for r in records
        if r.get("checked") and r.get("sent_msg_id")
    }

    svc_cache: dict[str, object] = {}
    all_accounts = list_token_accounts()
    updated = 0
    no_sent_yet = 0
    no_generated_body = 0
    parked = 0
    for record in pending:
        account = record.get("account", "matthew@zergai.com")
        # Search the record's account first, then every other account with a
        # token — Matt sometimes sends FM drafts from his other address.
        search_accounts = [account] + [a for a in all_accounts if a != account]

        sent_body, sent_id = None, None
        for acct in search_accounts:
            if acct not in svc_cache:
                svc_cache[acct] = make_service(acct)
            svc = svc_cache[acct]
            if not svc:
                continue
            sent_body, sent_id = find_sent_for_record(svc, record, claimed_ids)
            if sent_body:
                break

        if not any(svc_cache.get(a) for a in search_accounts):
            print(f"[learn] no Gmail token/service for any of {search_accounts}; leaving record unchecked")
            continue

        if sent_id:
            claimed_ids.add(sent_id)
        if not sent_body:
            # Park stale records instead of re-querying them forever.
            if record_age_days(record) >= UNPAIRED_AFTER_DAYS:
                mark_unpaired(record)
                parked += 1
                print(f"[learn] parked unpaired record: to={record['to']} ts={record.get('ts')} "
                      f"(>{UNPAIRED_AFTER_DAYS}d old, no sent match — see unpaired.jsonl)")
            else:
                no_sent_yet += 1
            continue  # not sent yet

        generated = record.get("generated_body", "").strip()
        if not generated:
            no_generated_body += 1
            continue

        # Pairing-confidence guard (see MIN_PAIR_SIMILARITY).
        similarity = difflib.SequenceMatcher(None, generated, sent_body).ratio()
        if similarity < MIN_PAIR_SIMILARITY:
            mark_unpaired(record, reason=f"low-similarity ({similarity:.2f})")
            record["sent_msg_id"] = sent_id
            record["pair_similarity"] = round(similarity, 3)
            parked += 1
            print(f"[learn] parked low-similarity pair: to={record['to']} "
                  f"sim={similarity:.2f} (draft body may be junk or pairing wrong)")
            continue

        diff_text, changed = diff_summary(generated, sent_body)
        if changed >= 2:
            # only log meaningful edits (1 changed line is usually a typo or minor)
            append_correction(record, sent_body, diff_text, changed)
            print(f"[learn] correction logged: to={record['to']}, changed={changed} lines")
            updated += 1
        else:
            print(f"[learn] no material edit: to={record['to']} (changed={changed})")

        record["checked"] = True
        record["sent_msg_id"] = sent_id
        record["edit_distance"] = changed

    # Rewrite sent-log with checked flags
    with open(SENT_LOG, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    prune_old_corrections(args.max_age_days)
    print(f"[learn] {updated} new correction(s) appended.")
    if updated == 0:
        print(
            "[learn] loop ran; no corrections found "
            f"(pending={len(pending)}, no_sent_yet={no_sent_yet}, "
            f"no_generated_body={no_generated_body}, parked_unpaired={parked})"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
