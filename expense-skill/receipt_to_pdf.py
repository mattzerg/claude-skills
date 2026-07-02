#!/usr/bin/env python3
"""Receipt → PDF generation for expense-skill.

Sources:
  - Gmail message (IMAP or OAuth account) → HTML → headless Chrome PDF
  - Booking.com emails: prefer the embedded `payment_receipt.html?auth_key=` /
    confirmation links (official printable receipt) over the raw email body
  - Any URL → headless Chrome PDF
  - Merge N PDFs → 1 (macOS Automator join)

All functions return dicts (JSON-serializable). No external Python deps.
"""
from __future__ import annotations

import email
import email.policy
import html as html_mod
import json
import re
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
GMAIL_SKILL_DIR = SKILL_DIR.parent / "gmail-skill"
OUTPUT_DIR = SKILL_DIR / "output"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
AUTOMATOR_JOIN = "/System/Library/Automator/Combine PDF Pages.action/Contents/MacOS/join"

# Links inside emails that render an official receipt without login.
RECEIPT_LINK_PATTERNS = [
    re.compile(r"https://secure\.booking\.com/payment_receipt\.html\?[^\"'\s<>]+"),
    re.compile(r"https://secure\.booking\.com/tpi_confirmation[^\"'\s<>]+"),
    re.compile(r"https://secure\.booking\.com/app_link/mybooking\.html\?[^\"'\s<>]+"),
]


def _ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Email HTML fetching (both gmail-skill backends)
# ---------------------------------------------------------------------------

def fetch_email_html(msg_id: str, account: str) -> str:
    """Return the text/html body of a Gmail message, via whichever backend
    gmail-skill uses for this account (IMAP app-password or OAuth API)."""
    sys.path.insert(0, str(GMAIL_SKILL_DIR))
    import imap_backend as ib  # type: ignore

    if ib.account_uses_imap(account):
        return _fetch_html_imap(msg_id, account, ib)
    return _fetch_html_oauth(msg_id, account)


def _fetch_html_imap(msg_id: str, account: str, ib) -> str:
    M = ib._imap_connect(account)
    try:
        M.select('"[Gmail]/All Mail"', readonly=True)
        seq = ib._find_by_hex_id(M, msg_id)
        if not seq:
            raise LookupError(f"message {msg_id} not found in {account}")
        _typ, data = M.fetch(seq[0], "(RFC822)")
        msg = email.message_from_bytes(data[0][1], policy=email.policy.default)
    finally:
        M.logout()
    return _html_part(msg)


def _fetch_html_oauth(msg_id: str, account: str) -> str:
    """OAuth accounts: use gmail-skill's stored token with the Gmail API (raw
    format). Some token files lack embedded client_id/client_secret (newer
    gmail-skill auth stores client creds separately) → the direct read raises
    ValueError. Fall back to shelling out to gmail_skill.py read, which resolves
    creds the same way the rest of the skill does (2026-07-02 fix)."""
    import base64

    token_file = GMAIL_SKILL_DIR / "tokens" / f"token_{account.replace('@', '_')}.json"
    try:
        from google.oauth2.credentials import Credentials  # type: ignore
        from googleapiclient.discovery import build  # type: ignore

        if not token_file.exists():
            raise FileNotFoundError(f"no gmail-skill token for {account}: {token_file}")
        creds = Credentials.from_authorized_user_file(str(token_file))
        service = build("gmail", "v1", credentials=creds)
        raw = service.users().messages().get(userId="me", id=msg_id, format="raw").execute()
        msg = email.message_from_bytes(
            base64.urlsafe_b64decode(raw["raw"]), policy=email.policy.default
        )
        return _html_part(msg)
    except Exception:
        return _fetch_html_via_gmail_cli(msg_id, account)


def _fetch_html_via_gmail_cli(msg_id: str, account: str) -> str:
    """Resilient fallback: read the message body via gmail-skill's own CLI."""
    gmail = GMAIL_SKILL_DIR / "gmail_skill.py"
    r = subprocess.run(["python3", str(gmail), "read", msg_id, "--account", account],
                       capture_output=True, text=True, timeout=120)
    try:
        body = json.loads(r.stdout).get("body", "")
    except json.JSONDecodeError:
        raise RuntimeError(f"gmail-skill read failed for {msg_id}: {r.stderr[-200:]}")
    low = body.lower()
    if any(tag in low for tag in ("<html", "<table", "<div", "<body")):
        return body
    return f"<pre>{html_mod.escape(body)}</pre>"


def _html_part(msg: email.message.EmailMessage) -> str:
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            return part.get_content()
    # fall back to plain text wrapped in <pre>
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            return f"<pre>{html_mod.escape(part.get_content())}</pre>"
    raise ValueError("no html or text part in message")


# ---------------------------------------------------------------------------
# Receipt link extraction
# ---------------------------------------------------------------------------

def extract_receipt_links(html: str) -> list[str]:
    """Find official-receipt URLs embedded in an email's HTML."""
    text = html_mod.unescape(html)
    links: list[str] = []
    for pattern in RECEIPT_LINK_PATTERNS:
        for m in pattern.finditer(text):
            url = m.group(0)
            if url not in links:
                links.append(url)
    return links


# ---------------------------------------------------------------------------
# PDF rendering
# ---------------------------------------------------------------------------

def url_to_pdf(url: str, out_path: Path) -> dict:
    _ensure_output_dir()
    out_path = Path(out_path)
    result = subprocess.run(
        [CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
         f"--print-to-pdf={out_path}", url],
        capture_output=True, text=True, timeout=120,
    )
    ok = out_path.exists() and out_path.stat().st_size > 1000
    return {"ok": ok, "pdf": str(out_path), "source": url,
            "error": None if ok else result.stderr[-500:]}


def html_to_pdf(html_content: str, out_path: Path, label: str = "receipt") -> dict:
    _ensure_output_dir()
    tmp_html = OUTPUT_DIR / f"_{label}.html"
    tmp_html.write_text(html_content)
    result = url_to_pdf(f"file://{tmp_html}", out_path)
    result["source"] = f"email-html ({label})"
    return result


def merge_pdfs(pdf_paths: list[str], out_path: Path) -> dict:
    out_path = Path(out_path)
    if not Path(AUTOMATOR_JOIN).exists():
        # graceful fallback: just use the first PDF
        Path(pdf_paths[0]).rename(out_path)
        return {"ok": True, "pdf": str(out_path), "merged": False,
                "note": "Automator join unavailable; used first PDF only"}
    subprocess.run([AUTOMATOR_JOIN, "-o", str(out_path), *pdf_paths],
                   check=True, capture_output=True, timeout=60)
    return {"ok": out_path.exists(), "pdf": str(out_path), "merged": True}


# ---------------------------------------------------------------------------
# Top-level prep: email → best-possible receipt PDF
# ---------------------------------------------------------------------------

def prep_from_email(msg_id: str, account: str, label: str) -> dict:
    """Produce the best receipt PDF for an email: official receipt link if one
    exists, otherwise the rendered email itself. If both exist, merge them."""
    html = fetch_email_html(msg_id, account)
    links = extract_receipt_links(html)
    pieces: list[dict] = []

    if links:
        for i, link in enumerate(links[:2]):  # at most 2 link renders
            piece = url_to_pdf(link, OUTPUT_DIR / f"{label}_link{i}.pdf")
            if piece["ok"]:
                pieces.append(piece)

    email_pdf = html_to_pdf(html, OUTPUT_DIR / f"{label}_email.pdf", label)
    if email_pdf["ok"]:
        pieces.append(email_pdf)

    if not pieces:
        return {"ok": False, "error": "no PDF could be generated", "msg_id": msg_id}

    final = OUTPUT_DIR / f"{label}.pdf"
    if len(pieces) == 1:
        Path(pieces[0]["pdf"]).rename(final)
        merged = {"ok": True, "pdf": str(final), "merged": False}
    else:
        merged = merge_pdfs([p["pdf"] for p in pieces], final)

    return {"ok": merged["ok"], "pdf": str(final), "msg_id": msg_id,
            "account": account, "sources": [p["source"] for p in pieces]}


def prep_from_url(url: str, label: str) -> dict:
    return url_to_pdf(url, OUTPUT_DIR / f"{label}.pdf")


if __name__ == "__main__":
    # Minimal CLI for direct testing; the real entry point is expense_skill.py prep
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--msg-id")
    p.add_argument("--account")
    p.add_argument("--url")
    p.add_argument("--label", default="receipt")
    a = p.parse_args()
    if a.url:
        print(json.dumps(prep_from_url(a.url, a.label), indent=2))
    elif a.msg_id and a.account:
        print(json.dumps(prep_from_email(a.msg_id, a.account, a.label), indent=2))
    else:
        p.error("need --url or (--msg-id and --account)")
