#!/usr/bin/env python3
"""expense-skill — personal expense handling CLI.

Verbs:
  inbox    What does Ramp need right now? (parses from:ramp.com emails)
  find     Hunt Gmail for candidate receipts
  prep     Generate a clean receipt PDF from an email or URL
  file     File an expense to a reimburser (dry-run unless --confirmed)
  status   Ledger + fresh inbox merge

All output is JSON. See SKILL.md for the confirmation-gate rules.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
GMAIL = str(SKILL_DIR.parent / "gmail-skill" / "gmail_skill.py")
LEDGER = SKILL_DIR / "state" / "ledger.jsonl"
RAMP_ACCOUNT = "matthew@zergai.com"

sys.path.insert(0, str(SKILL_DIR))
import receipt_finder  # noqa: E402
import receipt_to_pdf  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gmail(args: list[str]) -> dict:
    result = subprocess.run(["python3", GMAIL, *args],
                            capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        return {"error": result.stderr[-300:]}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"error": "non-json gmail output"}


def _ledger_append(entry: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    entry["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    with open(LEDGER, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _ledger_read() -> list[dict]:
    if not LEDGER.exists():
        return []
    return [json.loads(line) for line in LEDGER.read_text().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# inbox — parse Ramp notification emails
# ---------------------------------------------------------------------------

# "$200.00 at Anthropic\r\nMissing memo · 05/30/26" (digest + alert formats)
TXN_RE = re.compile(
    r"\$([0-9,]+\.[0-9]{2})\s+at\s+([A-Za-z0-9 .&'\-]+?)\s*[\r\n]+\s*Missing\s+(memo|receipt|items?)\s*·\s*(\d{2}/\d{2}/\d{2})",
    re.IGNORECASE,
)


def cmd_inbox(args) -> dict:
    """Parse recent Ramp emails into a structured needs list."""
    search = _gmail(["search", f"from:ramp.com newer_than:{args.days}d",
                     "--max-results", "30", "--account", RAMP_ACCOUNT])
    emails = search.get("results", [])

    needs: dict[str, dict] = {}     # key = amount|merchant|date
    reimbursement_signals: list[dict] = []
    newest_digest_date = None

    # Read action-required / digest emails, newest first (they're already sorted)
    for msg in emails:
        subject = msg.get("subject", "")
        if not any(k in subject.lower() for k in
                   ["transaction", "digest", "memo", "receipt", "reimbursement"]):
            continue
        body = _gmail(["read", msg["id"], "--account", RAMP_ACCOUNT]).get("body", "")

        for m in TXN_RE.finditer(body):
            amount, merchant, missing, date = m.group(1), m.group(2).strip(), m.group(3), m.group(4)
            key = f"{amount}|{merchant}|{date}"
            if key not in needs:
                needs[key] = {"amount": f"${amount}", "merchant": merchant,
                              "missing": missing.lower(), "txn_date": date,
                              "first_seen_in": subject, "email_date": msg.get("date")}

        if "reimbursement" in subject.lower():
            reimbursement_signals.append({"subject": subject, "date": msg.get("date"),
                                          "snippet": msg.get("snippet", "")[:200]})
        if "digest" in subject.lower() and newest_digest_date is None:
            newest_digest_date = msg.get("date")

    # Note: emails lag the live app state. Items submitted since the last
    # digest will still appear here — cross-check with the ledger.
    filed_keys = set()
    for entry in _ledger_read():
        if entry.get("action") == "filed" and entry.get("merchant"):
            filed_keys.add(f"{entry.get('amount', '').lstrip('$')}|{entry['merchant']}")

    needs_list = []
    for key, need in needs.items():
        amount_merchant = "|".join(key.split("|")[:2])
        need["possibly_already_filed"] = amount_merchant in filed_keys
        needs_list.append(need)

    return {
        "as_of": time.strftime("%Y-%m-%d %H:%M"),
        "source": f"from:ramp.com last {args.days}d (email lags live app state)",
        "newest_digest": newest_digest_date,
        "transactions_flagged": needs_list,
        "reimbursement_emails": reimbursement_signals,
        "note": "Email is a lagging indicator (and undercounts vs the live app). "
                "For ground truth run: ramp_browser.py check (reads live app via browser). "
                "To clear flags: expense_skill.py file --to ramp --kind memo (per txn) or "
                "ramp_browser.py reconcile (batch).",
    }


# ---------------------------------------------------------------------------
# find / prep — thin wrappers over the modules
# ---------------------------------------------------------------------------

def cmd_find(args) -> dict:
    return receipt_finder.find_receipts(args.since, args.until, args.vendor,
                                        [args.account] if args.account else None)


def cmd_prep(args) -> dict:
    label = args.label or f"receipt_{int(time.time())}"
    if args.merge:
        return receipt_to_pdf.merge_pdfs(args.merge, receipt_to_pdf.OUTPUT_DIR / f"{label}.pdf")
    if args.url:
        return receipt_to_pdf.prep_from_url(args.url, label)
    if args.msg_id and args.account:
        return receipt_to_pdf.prep_from_email(args.msg_id, args.account, label)
    return {"error": "need --url, --merge, or (--msg-id and --account)"}


# ---------------------------------------------------------------------------
# file — dispatch to reimburser channel (confirmation-gated)
# ---------------------------------------------------------------------------

def cmd_file(args) -> dict:
    if args.to != "ramp":
        return {"error": f"reimburser '{args.to}' not yet active (Phase 2). Only 'ramp' works."}

    if args.kind == "reimbursement":
        return _file_ramp_reimbursement(args)
    if args.kind == "receipt-forward":
        return _file_ramp_receipt_forward(args)
    if args.kind == "memo":
        return _file_ramp_memo(args)
    return {"error": f"unknown kind '{args.kind}'"}


def _file_ramp_reimbursement(args) -> dict:
    """Browser channel: create + (optionally) submit a Ramp reimbursement."""
    if not args.pdf or not args.memo:
        return {"error": "reimbursement needs --pdf and --memo"}

    # /usr/bin/python3 — the interpreter with Playwright installed (matches playwright-skill)
    cmd = ["/usr/bin/python3", str(SKILL_DIR / "ramp_browser.py"), "reimburse",
           "--pdf", args.pdf, "--memo", args.memo]
    if args.confirmed:
        cmd.append("--submit")

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    try:
        out = json.loads(result.stdout)
    except json.JSONDecodeError:
        out = {"ok": False, "raw": result.stdout[-500:], "stderr": result.stderr[-500:]}

    if out.get("ok"):
        _ledger_append({"action": "filed" if args.confirmed else "drafted",
                        "reimburser": "ramp", "kind": "reimbursement",
                        "memo": args.memo, "pdf": args.pdf,
                        "amount": out.get("amount"), "merchant": out.get("merchant"),
                        "ramp_url": out.get("url"), "submitted": args.confirmed})
    return out


def _file_ramp_memo(args) -> dict:
    """Browser channel: complete a memo (and/or receipt) on an EXISTING Ramp
    card transaction flagged 'Missing items'. Dry-run unless --confirmed."""
    if not getattr(args, "txn_id", None) and not getattr(args, "url", None):
        return {"error": "memo needs --txn-id or --url"}
    if not (args.memo or getattr(args, "accept_suggestion", False) or args.pdf):
        return {"error": "memo needs --memo, --accept-suggestion, or --pdf (receipt)"}

    cmd = ["/usr/bin/python3", str(SKILL_DIR / "ramp_browser.py"), "memo"]
    if getattr(args, "txn_id", None):
        cmd += ["--txn-id", args.txn_id]
    if getattr(args, "url", None):
        cmd += ["--url", args.url]
    if args.memo:
        cmd += ["--memo", args.memo]
    if getattr(args, "accept_suggestion", False):
        cmd.append("--accept-suggestion")
    if args.pdf:
        cmd += ["--receipt-pdf", args.pdf]
    if getattr(args, "expect_merchant", None):
        cmd += ["--expect-merchant", args.expect_merchant]
    if getattr(args, "expect_amount", None):
        cmd += ["--expect-amount", args.expect_amount]
    if args.confirmed:
        cmd.append("--submit")

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    try:
        out = json.loads(result.stdout)
    except json.JSONDecodeError:
        out = {"ok": False, "raw": result.stdout[-500:], "stderr": result.stderr[-500:]}

    if out.get("ok") and not out.get("dry_run"):
        _ledger_append({"action": "filed" if args.confirmed else "drafted",
                        "reimburser": "ramp", "kind": "memo",
                        "memo": args.memo,
                        "accept_suggestion": getattr(args, "accept_suggestion", False),
                        "receipt_pdf": args.pdf,
                        "amount": out.get("found_amount"), "merchant": out.get("found_merchant"),
                        "ramp_url": out.get("url"), "submitted": args.confirmed})
    return out


def _file_ramp_receipt_forward(args) -> dict:
    """Email channel: forward a vendor receipt email to receipts@ramp.com.

    Dry-run shows what would be forwarded. --confirmed performs the send
    (which is additionally gated by external_action_gate's gmail-send block —
    the parent shell needs ZERG_EXTERNAL_ACTION_OK=gmail-send or a bypass marker).
    """
    if not args.msg_id:
        return {"error": "receipt-forward needs --msg-id (the vendor receipt email)"}
    account = args.account or RAMP_ACCOUNT

    original = _gmail(["read", args.msg_id, "--account", account])
    if "error" in original:
        return {"ok": False, "error": f"could not read {args.msg_id}: {original['error']}"}

    plan = {
        "action": "forward",
        "to": "receipts@ramp.com",
        "from_account": account,
        "original_subject": original.get("subject"),
        "original_from": original.get("from"),
        "original_date": original.get("date"),
    }

    if not args.confirmed:
        return {"ok": True, "dry_run": True, "would_do": plan,
                "note": "Re-run with --confirmed (after Matt approves) to actually forward."}

    # gmail-skill has no native forward verb → send with original body quoted.
    body = (f"Forwarding receipt for Ramp auto-match.\n\n"
            f"---------- Forwarded message ----------\n"
            f"From: {original.get('from')}\nDate: {original.get('date')}\n"
            f"Subject: {original.get('subject')}\n\n{original.get('body', '')}")
    send = _gmail(["send", "--to", "receipts@ramp.com",
                   "--subject", f"Fwd: {original.get('subject', 'Receipt')}",
                   "--body", body, "--account", account])
    ok = "error" not in send
    if ok:
        _ledger_append({"action": "filed", "reimburser": "ramp", "kind": "receipt-forward",
                        "msg_id": args.msg_id, "subject": original.get("subject"),
                        "submitted": True})
    return {"ok": ok, "result": send, "plan": plan}


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def cmd_status(args) -> dict:
    ledger = _ledger_read()
    inbox = cmd_inbox(argparse.Namespace(days=14))
    return {
        "ledger_entries": len(ledger),
        "recent_filings": ledger[-10:],
        "ramp_inbox": inbox,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("inbox", help="What does Ramp need right now?")
    sp.add_argument("--days", type=int, default=30)
    sp.set_defaults(func=cmd_inbox)

    sp = sub.add_parser("find", help="Hunt Gmail for candidate receipts")
    sp.add_argument("--since", required=True, help="YYYY-MM-DD")
    sp.add_argument("--until", help="YYYY-MM-DD")
    sp.add_argument("--vendor")
    sp.add_argument("--account")
    sp.set_defaults(func=cmd_find)

    sp = sub.add_parser("prep", help="Generate receipt PDF")
    sp.add_argument("--msg-id")
    sp.add_argument("--account")
    sp.add_argument("--url")
    sp.add_argument("--merge", nargs="+", help="PDF paths to merge")
    sp.add_argument("--label")
    sp.set_defaults(func=cmd_prep)

    sp = sub.add_parser("file", help="File an expense (dry-run unless --confirmed)")
    sp.add_argument("--to", required=True, help="reimburser profile name (ramp)")
    sp.add_argument("--kind", required=True,
                    choices=["reimbursement", "receipt-forward", "memo"])
    sp.add_argument("--pdf")
    sp.add_argument("--memo")
    sp.add_argument("--msg-id")
    sp.add_argument("--account")
    # --kind memo: complete an existing card charge (see _file_ramp_memo)
    sp.add_argument("--txn-id", dest="txn_id", help="Ramp transaction UUID (kind=memo)")
    sp.add_argument("--url", help="Full txn detail URL (kind=memo)")
    sp.add_argument("--accept-suggestion", dest="accept_suggestion", action="store_true",
                    help="Accept Ramp's AI memo suggestion (kind=memo)")
    sp.add_argument("--expect-merchant", dest="expect_merchant",
                    help="Assert merchant before writing (kind=memo)")
    sp.add_argument("--expect-amount", dest="expect_amount",
                    help="Assert amount before writing (kind=memo)")
    sp.add_argument("--confirmed", action="store_true",
                    help="Perform the external action (requires Matt's in-session approval)")
    sp.set_defaults(func=cmd_file)

    sp = sub.add_parser("status", help="Ledger + inbox merge")
    sp.set_defaults(func=cmd_status)

    args = p.parse_args()
    print(json.dumps(args.func(args), indent=2, default=str))


if __name__ == "__main__":
    main()
