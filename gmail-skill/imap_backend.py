#!/usr/bin/env python3
"""IMAP/SMTP backend for gmail-skill — OAuth-free permanent access via Google App Password.

Why this exists (2026-06-02): Google's OAuth policy makes permanent consumer-Gmail
API access impossible for unverified apps — Testing mode revokes refresh tokens
every 7 days, and Production mode hard-blocks restricted scopes (Gmail/Drive)
entirely. App passwords (IMAP/SMTP) never expire and are Google-sanctioned.

How routing works: gmail_skill.py checks for tokens/<email>.imap_password.
If present, supported commands dispatch here instead of the Gmail API.
Output JSON exactly matches the API backend so downstream consumers
(gmail-triage, zdesk intake, pull-gmail-labeled) need zero changes.

ID compatibility: Gmail IMAP exposes X-GM-MSGID / X-GM-THRID (uint64). The Gmail
API's message/thread IDs are the lowercase-hex form of the same numbers, so IDs
are interchangeable across both backends in either direction.

Not supported here (require OAuth People API): contacts, other-contacts,
search-contacts, contact. These return a clear error for IMAP accounts.
"""
from __future__ import annotations

import email
import email.policy
import imaplib
import json
import re
import smtplib
import sys
import textwrap
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import make_msgid
from pathlib import Path
from typing import Optional

SKILL_DIR = Path(__file__).parent
TOKENS_DIR = SKILL_DIR / "tokens"

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465

ALL_MAIL = '"[Gmail]/All Mail"'
DRAFTS = '"[Gmail]/Drafts"'

EMAIL_LINE_WIDTH = 72


# ============ Account / credential resolution ============

def imap_password_path(account_email: str) -> Path:
    return TOKENS_DIR / f"{account_email}.imap_password"


def account_uses_imap(account_email: Optional[str]) -> bool:
    """True if this account has an app password on disk (IMAP backend active)."""
    if not account_email or "@" not in account_email:
        return False
    return imap_password_path(account_email).exists()


def get_app_password(account_email: str) -> str:
    return imap_password_path(account_email).read_text().strip()


def imap_accounts() -> list[str]:
    """All accounts configured for the IMAP backend."""
    if not TOKENS_DIR.exists():
        return []
    return [p.name[: -len(".imap_password")] for p in TOKENS_DIR.glob("*.imap_password")]


# ============ Connection helpers ============

def _imap_connect(account_email: str) -> imaplib.IMAP4_SSL:
    M = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    M.login(account_email, get_app_password(account_email))
    return M


def _smtp_connect(account_email: str) -> smtplib.SMTP_SSL:
    S = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30)
    S.login(account_email, get_app_password(account_email))
    return S


# ============ ID conversion (Gmail API hex <-> IMAP X-GM-MSGID decimal) ============

def gm_id_to_hex(gm_id: int | str) -> str:
    """X-GM-MSGID/X-GM-THRID (decimal uint64) -> Gmail API id (lowercase hex, no 0x)."""
    return format(int(gm_id), "x")


def hex_to_gm_id(hex_id: str) -> int:
    """Gmail API id (hex) -> X-GM-MSGID decimal."""
    return int(hex_id, 16)


# ============ Fetch / parse helpers ============

_FETCH_META = "(X-GM-MSGID X-GM-THRID X-GM-LABELS FLAGS BODY.PEEK[HEADER.FIELDS (FROM TO CC BCC SUBJECT DATE MESSAGE-ID)])"
_FETCH_FULL = "(X-GM-MSGID X-GM-THRID X-GM-LABELS FLAGS BODY.PEEK[])"

_ATTR_RE = re.compile(
    rb"X-GM-MSGID (\d+)|X-GM-THRID (\d+)|X-GM-LABELS \((.*?)\)|FLAGS \((.*?)\)", re.DOTALL
)


def _parse_fetch_attrs(raw: bytes) -> dict:
    """Parse X-GM-MSGID, X-GM-THRID, X-GM-LABELS, FLAGS out of a FETCH response line."""
    out = {"msgid": None, "thrid": None, "labels": [], "flags": []}
    for m in _ATTR_RE.finditer(raw):
        if m.group(1):
            out["msgid"] = int(m.group(1))
        elif m.group(2):
            out["thrid"] = int(m.group(2))
        elif m.group(3) is not None:
            out["labels"] = [
                l.strip('"\\') for l in m.group(3).decode(errors="replace").split() if l.strip('"\\')
            ]
        elif m.group(4) is not None:
            out["flags"] = m.group(4).decode(errors="replace").split()
    return out


def _gmail_labels_to_api(labels: list[str], flags: list[str]) -> list[str]:
    """Map IMAP X-GM-LABELS + FLAGS to Gmail-API-style label IDs."""
    out = []
    mapping = {"Inbox": "INBOX", "Sent": "SENT", "Draft": "DRAFT", "Spam": "SPAM",
               "Trash": "TRASH", "Important": "IMPORTANT", "Starred": "STARRED"}
    for l in labels:
        out.append(mapping.get(l, l))
    if "\\Flagged" in flags and "STARRED" not in out:
        out.append("STARRED")
    if "\\Seen" not in flags:
        out.append("UNREAD")
    return out


def _msg_records(M: imaplib.IMAP4_SSL, seq_ids: list[bytes], full: bool = False) -> list[dict]:
    """Fetch message records (attrs + parsed email) for IMAP sequence ids."""
    if not seq_ids:
        return []
    spec = _FETCH_FULL if full else _FETCH_META
    typ, data = M.fetch(b",".join(seq_ids), spec)
    if typ != "OK":
        return []
    records = []
    # imaplib returns [(attrs_bytes, body_bytes), b')', ...] tuples interleaved with closers
    for item in data:
        if not isinstance(item, tuple) or len(item) < 2:
            continue
        attrs = _parse_fetch_attrs(item[0])
        msg = email.message_from_bytes(item[1], policy=email.policy.default)
        records.append({"attrs": attrs, "msg": msg})
    return records


def _decode_body(msg: email.message.EmailMessage) -> str:
    """Extract text body, preferring text/plain (mirrors API backend's decode_body)."""
    body_part = msg.get_body(preferencelist=("plain", "html"))
    if body_part is not None:
        try:
            return body_part.get_content()
        except Exception:
            pass
    # Fallback: walk parts
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            try:
                return part.get_content()
            except Exception:
                continue
    return ""


def _summary(record: dict) -> dict:
    """format_email_summary parity."""
    msg, attrs = record["msg"], record["attrs"]
    body = _decode_body(msg)
    snippet = re.sub(r"\s+", " ", body).strip()[:200]
    return {
        "id": gm_id_to_hex(attrs["msgid"]) if attrs["msgid"] else None,
        "threadId": gm_id_to_hex(attrs["thrid"]) if attrs["thrid"] else None,
        "snippet": snippet,
        "from": str(msg.get("From", "")),
        "to": str(msg.get("To", "")),
        "subject": str(msg.get("Subject", "")),
        "date": str(msg.get("Date", "")),
        "labels": _gmail_labels_to_api(attrs["labels"], attrs["flags"]),
    }


def _full(record: dict) -> dict:
    """format_email_full parity."""
    msg, attrs = record["msg"], record["attrs"]
    body = _decode_body(msg)
    attachments = []
    for part in msg.walk():
        fname = part.get_filename()
        if fname:
            payload = part.get_payload(decode=True) or b""
            attachments.append({
                "filename": fname,
                "mimeType": part.get_content_type(),
                "size": len(payload),
            })
    return {
        "id": gm_id_to_hex(attrs["msgid"]) if attrs["msgid"] else None,
        "threadId": gm_id_to_hex(attrs["thrid"]) if attrs["thrid"] else None,
        "from": str(msg.get("From", "")),
        "to": str(msg.get("To", "")),
        "cc": str(msg.get("Cc", "")),
        "bcc": str(msg.get("Bcc", "")),
        "subject": str(msg.get("Subject", "")),
        "date": str(msg.get("Date", "")),
        "labels": _gmail_labels_to_api(attrs["labels"], attrs["flags"]),
        "body": body,
        "attachments": attachments,
        "snippet": re.sub(r"\s+", " ", body).strip()[:200],
    }


def _quote_imap(value: str) -> str:
    """Quote a string for use as an IMAP search criterion value."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _gm_raw_search(M: imaplib.IMAP4_SSL, query: str) -> list[bytes]:
    """Gmail raw-syntax (X-GM-RAW) search; handles spaces and unicode."""
    try:
        query.encode("ascii")
        typ, data = M.search(None, "X-GM-RAW", _quote_imap(query))
    except UnicodeEncodeError:
        # Non-ASCII query: send as UTF-8 literal
        M.literal = query.encode("utf-8")
        typ, data = M.search("UTF-8", "X-GM-RAW")
    if typ != "OK" or not data or not data[0]:
        return []
    return data[0].split()


def _find_by_hex_id(M: imaplib.IMAP4_SSL, hex_id: str) -> list[bytes]:
    """Locate a message by Gmail API hex id using X-GM-MSGID search (current mailbox)."""
    try:
        gm_id = hex_to_gm_id(hex_id)
    except ValueError:
        return []
    typ, data = M.search(None, "X-GM-MSGID", str(gm_id))
    if typ != "OK" or not data or not data[0]:
        return []
    return data[0].split()


def _wrap_body(body: str, width: int = EMAIL_LINE_WIDTH) -> str:
    """Mirror gmail_skill.wrap_email_body (Superhuman-style wrapping)."""
    paragraphs = body.split("\n\n")
    wrapped = []
    for para in paragraphs:
        lines = []
        for line in para.split("\n"):
            if line.strip():
                lead = len(line) - len(line.lstrip())
                w = textwrap.fill(line.strip(), width=width - lead,
                                  break_long_words=False, break_on_hyphens=False)
                if lead:
                    w = "\n".join(" " * lead + l for l in w.split("\n"))
                lines.append(w)
            else:
                lines.append(line)
        wrapped.append("\n".join(lines))
    return "\n\n".join(wrapped)


# ============ Commands (exact output parity with gmail_skill.py cmd_*) ============

def cmd_list(args):
    account = args.account
    label = (args.label or "INBOX").upper()
    mailbox = "INBOX" if label == "INBOX" else ALL_MAIL
    M = _imap_connect(account)
    try:
        M.select(mailbox, readonly=True)
        if label == "INBOX":
            typ, data = M.search(None, "ALL")
            ids = data[0].split() if (typ == "OK" and data and data[0]) else []
        else:
            # Non-INBOX label: search All Mail by Gmail label
            typ, data = M.search(None, "X-GM-LABELS", _quote_imap(label))
            ids = data[0].split() if (typ == "OK" and data and data[0]) else []
        if not ids:
            print(json.dumps({"results": [], "total": 0}))
            return
        ids = ids[-args.max_results:][::-1]  # newest first, like the API
        records = _msg_records(M, ids, full=False)
        records.reverse()  # fetch returns ascending; present newest first
        email_list = [_summary(r) for r in records]
        # API parity: messages in INBOX carry the INBOX label explicitly
        if label == "INBOX":
            for e in email_list:
                if "INBOX" not in e["labels"]:
                    e["labels"].insert(0, "INBOX")
        print(json.dumps({
            "label": args.label or "INBOX",
            "results": email_list,
            "total": len(email_list),
        }, indent=2))
    finally:
        M.logout()


def cmd_search(args):
    account = args.account
    M = _imap_connect(account)
    try:
        M.select(ALL_MAIL, readonly=True)
        # X-GM-RAW = full Gmail search syntax (from:, subject:, newer_than:, etc.)
        ids = _gm_raw_search(M, args.query)
        if not ids:
            print(json.dumps({"results": [], "total": 0}))
            return
        total_estimate = len(ids)
        ids = ids[-args.max_results:][::-1]
        records = _msg_records(M, ids, full=False)
        records.reverse()
        email_list = [_summary(r) for r in records]
        print(json.dumps({
            "query": args.query,
            "results": email_list,
            "total": len(email_list),
            "resultSizeEstimate": total_estimate,
        }, indent=2))
    finally:
        M.logout()


def cmd_read(args):
    account = args.account
    M = _imap_connect(account)
    try:
        M.select(ALL_MAIL, readonly=True)
        seq = _find_by_hex_id(M, args.email_id)
        if not seq:
            print(json.dumps({"error": f"message {args.email_id} not found"}))
            sys.exit(1)
        records = _msg_records(M, seq[-1:], full=True)
        if not records:
            print(json.dumps({"error": f"could not fetch message {args.email_id}"}))
            sys.exit(1)
        output = _full(records[0]) if args.format == "full" else _summary(records[0])
        print(json.dumps(output, indent=2))
    finally:
        M.logout()


def cmd_attachment(args):
    account = args.account
    M = _imap_connect(account)
    try:
        M.select(ALL_MAIL, readonly=True)
        seq = _find_by_hex_id(M, args.email_id)
        if not seq:
            print(json.dumps({"error": "no attachments found", "email_id": args.email_id}))
            sys.exit(1)
        records = _msg_records(M, seq[-1:], full=True)
        msg = records[0]["msg"]
        parts = [p for p in msg.walk() if p.get_filename()]
        if not parts:
            print(json.dumps({"error": "no attachments found", "email_id": args.email_id}))
            sys.exit(1)
        out_dir = Path(args.out_dir).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)
        saved = []
        for part in parts:
            filename = part.get_filename()
            if args.filename and args.filename != filename:
                continue
            data = part.get_payload(decode=True) or b""
            out_path = out_dir / filename
            out_path.write_bytes(data)
            saved.append({
                "filename": filename,
                "path": str(out_path),
                "size": len(data),
                "mimeType": part.get_content_type(),
            })
        if args.filename and not saved:
            print(json.dumps({
                "error": f"attachment {args.filename!r} not found",
                "available": [p.get_filename() for p in parts],
            }))
            sys.exit(1)
        print(json.dumps({"saved": saved}, indent=2))
    finally:
        M.logout()


def _build_mime(account: str, to: str, subject: str, body: str,
                cc: str = None, bcc: str = None,
                in_reply_to: str = None, references: str = None) -> MIMEText:
    message = MIMEText(_wrap_body(body))
    message["From"] = account
    message["To"] = to
    message["Subject"] = subject
    if cc:
        message["Cc"] = cc
    if bcc:
        message["Bcc"] = bcc
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
        message["References"] = references or in_reply_to
    message["Message-ID"] = make_msgid()
    return message


def _lookup_sent_ids(account: str, rfc_message_id: str) -> tuple[Optional[str], Optional[str]]:
    """After SMTP send, find the Gmail API id/threadId of the sent message via its Message-ID."""
    try:
        M = _imap_connect(account)
        try:
            M.select(ALL_MAIL, readonly=True)
            ids = _gm_raw_search(M, f"rfc822msgid:{rfc_message_id}")
            if not ids:
                return None, None
            typ, fdata = M.fetch(ids[-1], "(X-GM-MSGID X-GM-THRID)")
            attrs = _parse_fetch_attrs(fdata[0] if isinstance(fdata[0], bytes) else fdata[0][0])
            return (gm_id_to_hex(attrs["msgid"]) if attrs["msgid"] else None,
                    gm_id_to_hex(attrs["thrid"]) if attrs["thrid"] else None)
        finally:
            M.logout()
    except Exception:
        return None, None


def cmd_send(args):
    account = args.account
    message = _build_mime(account, args.to, args.subject, args.body, args.cc, args.bcc)
    rfc_id = message["Message-ID"]
    recipients = [args.to]
    if args.cc:
        recipients += [a.strip() for a in args.cc.split(",")]
    if args.bcc:
        recipients += [a.strip() for a in args.bcc.split(",")]
    try:
        S = _smtp_connect(account)
        try:
            S.sendmail(account, recipients, message.as_string())
        finally:
            S.quit()
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
    # Best-effort: resolve the Gmail API ids of what we just sent
    import time
    time.sleep(2)  # give Gmail a beat to index the sent message
    message_id, thread_id = _lookup_sent_ids(account, rfc_id)
    print(json.dumps({
        "success": True,
        "message_id": message_id,
        "thread_id": thread_id,
        "to": args.to,
        "subject": args.subject,
        "from": account,
    }, indent=2))


def cmd_draft(args):
    account = args.account
    in_reply_to = None
    references = None
    # If replying, pull headers from the original message
    if getattr(args, "reply_to_id", None):
        try:
            M = _imap_connect(account)
            try:
                M.select(ALL_MAIL, readonly=True)
                seq = _find_by_hex_id(M, args.reply_to_id)
                if seq:
                    records = _msg_records(M, seq[-1:], full=False)
                    if records:
                        orig = records[0]["msg"]
                        in_reply_to = str(orig.get("Message-ID", "")) or None
                        references = str(orig.get("References", "")) or in_reply_to
            finally:
                M.logout()
        except Exception:
            pass
    message = _build_mime(account, args.to, args.subject, args.body,
                          args.cc, args.bcc, in_reply_to, references)
    try:
        M = _imap_connect(account)
        try:
            M.append(DRAFTS, r"(\Draft)", None, message.as_bytes())
        finally:
            M.logout()
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
    # Resolve the API ids of the appended draft
    message_id, thread_id = _lookup_sent_ids(account, message["Message-ID"])
    print(json.dumps({
        "success": True,
        "draft_id": message_id,   # IMAP has no separate draft id; message id is canonical
        "message_id": message_id,
        "thread_id": thread_id,
        "to": args.to,
        "subject": args.subject,
        "from": account,
        "in_reply_to": in_reply_to,
    }, indent=2))


def _modify_messages(account: str, email_ids: str, action: str,
                     store_cmd: str, store_arg: str, mailbox: str = ALL_MAIL):
    """Shared flag/label modification across comma-separated hex ids."""
    ids = [i.strip() for i in email_ids.split(",")]
    results = []
    M = _imap_connect(account)
    try:
        M.select(mailbox)  # read-write
        for hex_id in ids:
            try:
                seq = _find_by_hex_id(M, hex_id)
                if not seq:
                    results.append({"id": hex_id, "success": False, "error": "not found"})
                    continue
                typ, _ = M.store(seq[-1], store_cmd, store_arg)
                results.append({"id": hex_id, "success": typ == "OK"})
            except Exception as e:
                results.append({"id": hex_id, "success": False, "error": str(e)})
    finally:
        M.logout()
    print(json.dumps({
        "action": action,
        "results": results,
        "total": len(results),
        "successful": sum(1 for r in results if r["success"]),
    }, indent=2))


def cmd_mark_read(args):
    _modify_messages(args.account, args.email_ids, "mark_read", "+FLAGS", r"(\Seen)")


def cmd_mark_unread(args):
    _modify_messages(args.account, args.email_ids, "mark_unread", "-FLAGS", r"(\Seen)")


def cmd_mark_done(args):
    # Archive = remove the \Inbox label via X-GM-LABELS
    _modify_messages(args.account, args.email_ids, "archive", "-X-GM-LABELS", r"(\Inbox)")


def cmd_unarchive(args):
    _modify_messages(args.account, args.email_ids, "unarchive", "+X-GM-LABELS", r"(\Inbox)")


def cmd_star(args):
    _modify_messages(args.account, args.email_ids, "star", "+FLAGS", r"(\Flagged)")


def cmd_unstar(args):
    _modify_messages(args.account, args.email_ids, "unstar", "-FLAGS", r"(\Flagged)")


def cmd_labels(args):
    account = args.account
    M = _imap_connect(account)
    try:
        typ, data = M.list()
        labels = []
        system_map = {
            "INBOX": "INBOX", "[Gmail]/Sent Mail": "SENT", "[Gmail]/Drafts": "DRAFT",
            "[Gmail]/Spam": "SPAM", "[Gmail]/Trash": "TRASH", "[Gmail]/Starred": "STARRED",
            "[Gmail]/Important": "IMPORTANT", "[Gmail]/All Mail": "ALL_MAIL",
        }
        for line in data or []:
            if not line:
                continue
            decoded = line.decode(errors="replace")
            m = re.search(r'"([^"]*)"$|([^ "]+)$', decoded)
            if not m:
                continue
            name = m.group(1) or m.group(2)
            if name == "[Gmail]":
                continue
            is_system = name in system_map
            labels.append({
                "id": system_map.get(name, name),
                "name": name,
                "type": "system" if is_system else "user",
            })
        print(json.dumps({"labels": labels}, indent=2))
    finally:
        M.logout()


def cmd_contacts_unsupported(args):
    print(json.dumps({
        "error": "contacts require the Google People API (OAuth). "
                 "This account uses the IMAP backend (app password) which has no contacts access. "
                 "Use search/list with from:/to: queries instead.",
        "backend": "imap",
    }))
    sys.exit(1)


# Dispatch table used by gmail_skill.py routing
IMAP_COMMANDS = {
    "search": cmd_search,
    "read": cmd_read,
    "attachment": cmd_attachment,
    "list": cmd_list,
    "send": cmd_send,
    "draft": cmd_draft,
    "mark-read": cmd_mark_read,
    "mark-unread": cmd_mark_unread,
    "mark-done": cmd_mark_done,
    "unarchive": cmd_unarchive,
    "star": cmd_star,
    "unstar": cmd_unstar,
    "labels": cmd_labels,
    "contacts": cmd_contacts_unsupported,
    "other-contacts": cmd_contacts_unsupported,
    "search-contacts": cmd_contacts_unsupported,
    "contact": cmd_contacts_unsupported,
}
