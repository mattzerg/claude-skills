#!/usr/bin/env python3
"""Gmail receipt hunting for expense-skill.

Searches both Gmail accounts for receipt-bearing emails and classifies them by
vendor and kind. Composes gmail-skill's CLI (JSON output) rather than
reimplementing auth.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
GMAIL = str(SKILL_DIR.parent / "gmail-skill" / "gmail_skill.py")

DEFAULT_ACCOUNTS = ["matthew@zergai.com", "matteisn@gmail.com"]

# (gmail query fragment, vendor, kind)
VENDOR_QUERIES: list[tuple[str, str, str]] = [
    ("from:booking.com (subject:confirmed OR subject:receipt OR subject:payment OR \"payment successful\")",
     "Booking.com", "travel"),
    ("from:noreply-payments@booking.com", "Booking.com", "travel-payment"),
    ("from:airbnb.com (subject:receipt OR subject:reservation)", "Airbnb", "travel"),
    ("from:stripe.com subject:receipt", "Stripe-billed vendor", "saas"),
    ("from:lemonsqueezy-mail.com subject:receipt", "LemonSqueezy-billed vendor", "saas"),
    ("from:uber.com (subject:trip OR subject:receipt)", "Uber", "rideshare"),
    ("from:lyft.com subject:receipt", "Lyft", "rideshare"),
    ("from:hotels.com OR from:expedia.com (subject:confirmation OR subject:receipt OR subject:itinerary)",
     "Hotels.com/Expedia", "travel"),
    ("subject:(hotel receipt) OR subject:(hotel folio)", "Hotel (direct)", "travel"),
    ("from:tm.openai.com subject:funded", "OpenAI", "saas"),
    ("from:anthropic.com (subject:receipt OR subject:invoice)", "Anthropic", "saas"),
]

AMOUNT_RE = re.compile(r"\$\s?([0-9,]+\.[0-9]{2})")


def _gmail_search(query: str, account: str, max_results: int = 25) -> list[dict]:
    result = subprocess.run(
        ["python3", GMAIL, "search", query, "--max-results", str(max_results),
         "--account", account],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        return []
    try:
        return json.loads(result.stdout).get("results", [])
    except json.JSONDecodeError:
        return []


def _extract_amount(text: str) -> str | None:
    m = AMOUNT_RE.search(text or "")
    return m.group(1) if m else None


def find_receipts(since: str, until: str | None = None, vendor: str | None = None,
                  accounts: list[str] | None = None) -> dict:
    """Search for candidate receipt emails.

    since/until: YYYY-MM-DD (gmail uses YYYY/MM/DD internally).
    vendor: optional filter, substring match against vendor names or a raw
            sender domain (e.g. "booking.com").
    """
    accounts = accounts or DEFAULT_ACCOUNTS
    date_clause = f" after:{since.replace('-', '/')}"
    if until:
        date_clause += f" before:{until.replace('-', '/')}"

    queries = VENDOR_QUERIES
    if vendor:
        v = vendor.lower()
        matched = [q for q in VENDOR_QUERIES if v in q[1].lower() or v in q[0].lower()]
        # unknown vendor → generic sender search
        queries = matched or [(f"from:{vendor} (receipt OR invoice OR confirmation)", vendor, "other")]

    candidates: list[dict] = []
    seen_ids: set[str] = set()
    for account in accounts:
        for query, vendor_name, kind in queries:
            for msg in _gmail_search(query + date_clause, account):
                if msg["id"] in seen_ids:
                    continue
                seen_ids.add(msg["id"])
                candidates.append({
                    "msg_id": msg["id"],
                    "account": account,
                    "vendor": vendor_name,
                    "kind": kind,
                    "subject": msg.get("subject", ""),
                    "from": msg.get("from", ""),
                    "date": msg.get("date", ""),
                    "amount": _extract_amount(msg.get("snippet", "")),
                })

    candidates.sort(key=lambda c: c["date"], reverse=True)
    return {"since": since, "until": until, "count": len(candidates),
            "candidates": candidates}


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--since", required=True)
    p.add_argument("--until")
    p.add_argument("--vendor")
    p.add_argument("--account", action="append")
    a = p.parse_args()
    print(json.dumps(find_receipts(a.since, a.until, a.vendor, a.account), indent=2))
