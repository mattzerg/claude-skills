#!/usr/bin/env python3
"""Negative-space corpus sweeper.

Pulls Matt's outgoing email history from Gmail and dumps it as a raw voice
corpus that voice skills can sample at draft time. "Negative space" =
everything FM didn't see (i.e. emails Matt sent without using fakematt-email).

Strategy:
- Paginate Gmail's `in:sent` for the chosen account, oldest first
- Skip auto-replies / no-reply@ / mailer-daemon / heavily-quoted / too-short
- Dedup against fakematt-email/sent-log.jsonl (those ARE FM-produced)
- Strip signatures + quoted threads, keep clean body only
- Output to raw_outgoing/<account>/<year>.md with per-message frontmatter
- State file `sweep_state.json` tracks pagination cursor + counters so the
  sweep is resumable across days

Usage:
    sweep_outgoing.py --account matteisn@gmail.com [--since YYYY-MM-DD]
                      [--max-messages N] [--dry-run] [--reset-state]

Default account: matteisn@gmail.com (10+ years of history).
Default --since: 2015-01-01 (10-year backfill).
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

import socket
import ssl
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import warnings
warnings.filterwarnings("ignore")


# Set a generous default socket timeout so a hung Gmail read doesn't hang
# forever — but is still long enough for slow pages.
socket.setdefaulttimeout(45)


def _with_retry(fn, *, attempts=4, base_delay=2.0):
    """Retry a Gmail API call on transient network errors with exponential
    backoff. Re-raises on the final failure or on non-transient errors."""
    transient = (socket.timeout, ConnectionResetError, ssl.SSLError, TimeoutError, OSError)
    last_exc = None
    for i in range(attempts):
        try:
            return fn()
        except HttpError as e:
            # Gmail rate-limit / quota — back off + retry
            status = getattr(e.resp, "status", None)
            if status in (429, 500, 502, 503, 504):
                last_exc = e
                time.sleep(base_delay * (2 ** i))
                continue
            raise
        except transient as e:
            last_exc = e
            time.sleep(base_delay * (2 ** i))
            continue
    raise last_exc if last_exc else RuntimeError("retry exhausted")

SKILL_DIR = Path(__file__).parent
SENT_LOG = SKILL_DIR / "sent-log.jsonl"
OUTPUT_ROOT = SKILL_DIR / "raw_outgoing"
STATE_FILE = SKILL_DIR / "sweep_state.json"
TOKENS_DIR = Path.home() / ".claude" / "skills" / "gmail-skill" / "tokens"
CREDS_FILE = Path.home() / ".claude" / "skills" / "gmail-skill" / "credentials.json"

MIN_BODY_LEN = 50
PAGE_SIZE = 250  # Gmail API max per list page

AUTOREPLY_SUBJECTS = re.compile(
    r"\b(auto[-\s]?reply|out of office|delivery (status|failure)|"
    r"undeliverable|postmaster|mailer-daemon|automatic reply)\b",
    re.I,
)
NOREPLY_TO = re.compile(r"(no[-\.]?reply|do[-\.]?not[-\.]?reply|"
                        r"postmaster|mailer-daemon|notifications?|notify)@", re.I)


def make_service(account: str):
    candidates = list(TOKENS_DIR.glob(f"token_{account.split('@')[0]}_*.json"))
    if not candidates:
        raise RuntimeError(f"No Gmail token for {account}")
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
        nested = extract_body(p)
        if nested:
            return nested
    return ""


def clean_outgoing(body: str) -> str:
    """Strip signature + quoted thread + boilerplate."""
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
        if re.match(r"^--\s*$", s):  # signature delimiter
            break
        out.append(line)
    return "\n".join(out).strip()


def get_headers(payload) -> dict:
    return {h["name"].lower(): h["value"] for h in payload.get("headers", []) or []}


def parse_date(date_str: str) -> dt.datetime | None:
    """Parse RFC 2822-ish dates from Gmail Date: header."""
    from email.utils import parsedate_to_datetime
    try:
        return parsedate_to_datetime(date_str).astimezone(dt.timezone.utc).replace(tzinfo=None)
    except Exception:
        return None


def already_in_sent_log(msg_id: str, sent_log_ids: set) -> bool:
    return msg_id in sent_log_ids


def load_sent_log_msg_ids() -> set[str]:
    ids: set[str] = set()
    if not SENT_LOG.exists():
        return ids
    for line in SENT_LOG.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("sent_msg_id"):
            ids.add(r["sent_msg_id"])
    return ids


def load_state(account: str) -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        all_state = json.loads(STATE_FILE.read_text())
    except Exception:
        return {}
    return all_state.get(account, {})


def save_state(account: str, state: dict) -> None:
    all_state = {}
    if STATE_FILE.exists():
        try:
            all_state = json.loads(STATE_FILE.read_text())
        except Exception:
            all_state = {}
    all_state[account] = state
    STATE_FILE.write_text(json.dumps(all_state, indent=2))


def append_to_year_file(account: str, msg: dict) -> None:
    out_dir = OUTPUT_ROOT / account.split("@")[0]
    out_dir.mkdir(parents=True, exist_ok=True)
    year = msg["date"][:4]
    out_path = out_dir / f"{year}.md"
    with open(out_path, "a") as f:
        f.write(f"\n---\n")
        f.write(f"date: {msg['date']}\n")
        f.write(f"to: {msg['to']}\n")
        f.write(f"subject: {msg['subject']}\n")
        f.write(f"msg_id: {msg['msg_id']}\n")
        f.write(f"---\n\n")
        f.write(msg["body"])
        f.write("\n")


def should_skip(headers: dict, body: str, sent_log_ids: set, msg_id: str,
                account: str) -> tuple[bool, str]:
    if msg_id in sent_log_ids:
        return True, "in-sent-log (FM-produced)"
    subject = headers.get("subject", "")
    if AUTOREPLY_SUBJECTS.search(subject):
        return True, "auto-reply subject"
    to = headers.get("to", "") + " " + headers.get("cc", "")
    if NOREPLY_TO.search(to):
        return True, "no-reply recipient"
    # Sent-to-self filter — when Matt's own address is the only recipient
    me = account.lower()
    recipients = [r.strip().lower() for r in re.findall(r"<([^>]+)>|([\w\.\-]+@[\w\.\-]+)", to) for r in (r if isinstance(r, str) else "") if r]
    # simpler: just check if `me` is in the to: header AND no other addresses
    addrs = re.findall(r"[\w\.\-]+@[\w\.\-]+", to)
    if addrs and all(a.lower() == me for a in addrs):
        return True, "sent-to-self"
    if not addrs:
        return True, "no recipient"
    if len(body) < MIN_BODY_LEN:
        return True, f"body too short (<{MIN_BODY_LEN} chars)"
    return False, ""


def process_message(svc, msg_id: str, sent_log_ids: set, account: str) -> dict | None:
    try:
        full = _with_retry(
            lambda: svc.users().messages().get(userId="me", id=msg_id, format="full").execute()
        )
    except HttpError as e:
        print(f"[sweep] msg {msg_id} fetch failed: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[sweep] msg {msg_id} transient-fail after retries: {e}", file=sys.stderr)
        return None
    payload = full.get("payload", {})
    headers = get_headers(payload)
    body_raw = extract_body(payload)
    body = clean_outgoing(body_raw)
    skip, reason = should_skip(headers, body, sent_log_ids, msg_id, account)
    if skip:
        return {"_skipped": True, "_reason": reason}
    date_obj = parse_date(headers.get("date", ""))
    if not date_obj:
        return {"_skipped": True, "_reason": "unparseable date"}
    return {
        "msg_id": msg_id,
        "date": date_obj.isoformat()[:10],
        "to": headers.get("to", "")[:200],
        "subject": (headers.get("subject", "") or "(no subject)")[:200],
        "body": body,
    }


def sweep(account: str, since: str | None, max_messages: int | None,
          dry_run: bool, reset_state: bool) -> int:
    svc = make_service(account)
    sent_log_ids = load_sent_log_msg_ids()
    state = {} if reset_state else load_state(account)

    processed_total = state.get("processed_total", 0)
    skipped_total = state.get("skipped_total", 0)
    page_token = state.get("page_token")
    last_run = state.get("last_run")

    query_parts = ["in:sent"]
    if since:
        query_parts.append(f"after:{since.replace('-', '/')}")
    query = " ".join(query_parts)
    print(f"[sweep] account={account} query='{query}' resume_token={page_token!r}", file=sys.stderr)

    total_fetched_this_run = 0
    new_kept = 0
    new_skipped = 0
    skip_reasons: dict[str, int] = {}

    try:
        while True:
            req_kwargs = {"userId": "me", "q": query, "maxResults": PAGE_SIZE}
            if page_token:
                req_kwargs["pageToken"] = page_token
            res = _with_retry(lambda: svc.users().messages().list(**req_kwargs).execute())
            msgs = res.get("messages", []) or []
            if not msgs:
                print("[sweep] no more messages on this page — done", file=sys.stderr)
                page_token = None
                break

            for m in msgs:
                msg_id = m["id"]
                processed = process_message(svc, msg_id, sent_log_ids, account)
                total_fetched_this_run += 1
                if processed and not processed.get("_skipped"):
                    new_kept += 1
                    if not dry_run:
                        append_to_year_file(account, processed)
                else:
                    new_skipped += 1
                    if processed:
                        skip_reasons[processed["_reason"]] = skip_reasons.get(processed["_reason"], 0) + 1

                if max_messages and total_fetched_this_run >= max_messages:
                    break

                # Light rate-limit relief
                if total_fetched_this_run % 50 == 0:
                    time.sleep(0.5)

            if max_messages and total_fetched_this_run >= max_messages:
                print(f"[sweep] hit --max-messages={max_messages}, stopping", file=sys.stderr)
                break

            page_token = res.get("nextPageToken")
            if not page_token:
                print("[sweep] no nextPageToken — fully drained", file=sys.stderr)
                break

            # Save progress between pages so a kill is recoverable
            if not dry_run:
                save_state(account, {
                    "processed_total": processed_total + total_fetched_this_run,
                    "skipped_total": skipped_total + new_skipped,
                    "page_token": page_token,
                    "last_run": dt.datetime.now().isoformat(),
                    "since": since,
                })
            print(f"[sweep] page complete — kept {new_kept}, skipped {new_skipped} so far", file=sys.stderr)

    except KeyboardInterrupt:
        print("[sweep] interrupted by user — state saved, run again to resume", file=sys.stderr)
    finally:
        if not dry_run:
            save_state(account, {
                "processed_total": processed_total + total_fetched_this_run,
                "skipped_total": skipped_total + new_skipped,
                "page_token": page_token,
                "last_run": dt.datetime.now().isoformat(),
                "since": since,
            })

    print(f"\n[sweep] DONE for {account}", file=sys.stderr)
    print(f"  fetched this run: {total_fetched_this_run}", file=sys.stderr)
    print(f"  kept: {new_kept}", file=sys.stderr)
    print(f"  skipped: {new_skipped}", file=sys.stderr)
    if skip_reasons:
        print("  skip breakdown:", file=sys.stderr)
        for r, n in sorted(skip_reasons.items(), key=lambda x: -x[1]):
            print(f"    {n}× {r}", file=sys.stderr)
    print(f"  total processed (cumulative): {processed_total + total_fetched_this_run}", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", default="matteisn@gmail.com")
    ap.add_argument("--since", default="2015-01-01",
                    help="YYYY-MM-DD (default: 2015-01-01 = ~10y backfill)")
    ap.add_argument("--max-messages", type=int,
                    help="cap this run (resumable next time)")
    ap.add_argument("--dry-run", action="store_true",
                    help="don't write output files or update state")
    ap.add_argument("--reset-state", action="store_true",
                    help="ignore saved state, start fresh")
    args = ap.parse_args()
    return sweep(args.account, args.since, args.max_messages,
                 args.dry_run, args.reset_state)


if __name__ == "__main__":
    sys.exit(main())
