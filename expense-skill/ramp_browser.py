#!/usr/bin/python3
"""Ramp browser driver for expense-skill.

NOTE: run with /usr/bin/python3 (where Playwright is installed — same as playwright-skill).

Uses a DEDICATED Playwright persistent profile (sessions/ramp-profile/) so that
no other Claude session / MCP instance can kill or contend with it.

Verbs:
  login       Open a visible browser at app.ramp.com; Matt completes Google SSO once.
              The session persists in the profile for future headless runs.
  check       Verify login state; dump what the Ramp home inbox currently needs.
  reimburse   Create a reimbursement: upload PDF, wait for OCR, set memo
              (re-asserting it after Ramp's AI suggestion fires), set
              "Reimburse from"=None. Stops BEFORE submit unless --submit.

Lessons baked in (from 2026-06-03 session):
  - Ramp's "Filled by Ramp" AI memo suggestion can overwrite a typed memo on
    focus change → set, blur, re-read, re-assert.
  - Receipt OCR takes 10-40s; the page redirects to /details/reimbursements/<id>/draft.
  - First-ever reimbursement triggers a "Where do you live?" modal (residence)
    and possibly a bank-account modal → handled.
  - Never auto-submits. --submit is only passed by expense_skill.py when
    Matt has explicitly confirmed in-session.

All output is JSON on stdout.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

SKILL_DIR = Path(__file__).resolve().parent
PROFILE_DIR = SKILL_DIR / "sessions" / "ramp-profile"
SHOTS_DIR = SKILL_DIR / "output"
LEDGER = SKILL_DIR / "state" / "ledger.jsonl"
RAMP_HOME = "https://app.ramp.com/home"
RAMP_NEW_REIMBURSEMENT = "https://app.ramp.com/details/reimbursements/new"


def _ledger_append(entry: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    entry["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    with open(LEDGER, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _context(headless: bool):
    pw = sync_playwright().start()
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    ctx = pw.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        channel="chrome",            # real Chrome: Google SSO behaves better
        headless=headless,
        viewport={"width": 1440, "height": 900},
        args=["--disable-blink-features=AutomationControlled"],
    )
    return pw, ctx


def _is_signed_in(page) -> bool:
    return "/sign-in" not in page.url


def _shot(page, name: str) -> str:
    SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    path = SHOTS_DIR / f"{name}_{int(time.time())}.png"
    page.screenshot(path=str(path), full_page=True)
    return str(path)


# ---------------------------------------------------------------------------
# login
# ---------------------------------------------------------------------------

def cmd_login(args) -> dict:
    pw, ctx = _context(headless=False)
    try:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(RAMP_HOME, timeout=60_000)
        # Ramp redirects to /sign-in CLIENT-SIDE after load — wait for it to settle
        # before deciding we're already signed in (otherwise false positive).
        page.wait_for_load_state("networkidle", timeout=30_000)
        time.sleep(2)
        if _is_signed_in(page):
            return {"ok": True, "already_signed_in": True}

        print(json.dumps({"status": "waiting_for_login",
                          "message": "Complete the Ramp/Google sign-in in the browser window. "
                                     "Waiting up to 5 minutes..."}), file=sys.stderr)
        # Wait until the URL leaves /sign-in (Matt completes SSO manually)
        deadline = time.time() + 300
        while time.time() < deadline:
            if _is_signed_in(page):
                page.wait_for_load_state("networkidle", timeout=30_000)
                return {"ok": True, "signed_in": True, "url": page.url}
            time.sleep(2)
        return {"ok": False, "error": "login timed out after 5 minutes"}
    finally:
        ctx.close()
        pw.stop()


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------

def cmd_check(args) -> dict:
    pw, ctx = _context(headless=True)
    try:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(RAMP_HOME, timeout=60_000)
        page.wait_for_load_state("networkidle", timeout=30_000)
        if not _is_signed_in(page):
            return {"ok": False, "signed_in": False,
                    "fix": "run: python3 ramp_browser.py login"}

        body = page.inner_text("main", timeout=15_000)
        caught_up = "all caught up" in body.lower()
        # Reimbursements awaiting approval, if shown on home
        awaiting = None
        if "awaiting approval" in body.lower():
            for line in body.splitlines():
                if "awaiting approval" in line.lower():
                    awaiting = line.strip()
                    break
        return {"ok": True, "signed_in": True, "all_caught_up": caught_up,
                "reimbursements": awaiting,
                "screenshot": _shot(page, "ramp_home")}
    finally:
        ctx.close()
        pw.stop()


# ---------------------------------------------------------------------------
# reimburse
# ---------------------------------------------------------------------------

def _dismiss_onboarding_modals(page) -> list[str]:
    """Handle one-time modals: residence question, bank-account prompt."""
    handled = []
    # "Where do you live?" — residence should already be set (Michigan, 2026-06-03),
    # but if it appears, do NOT guess; bail out so a human decides.
    if page.get_by_text("Where do you live?").count() > 0:
        handled.append("residence_modal_present")
    # Bank account prompt → "Get paid outside Ramp" (Matt's standing choice, 2026-06-03)
    outside = page.get_by_role("button", name="Get paid outside Ramp")
    if outside.count() > 0:
        outside.first.click()
        handled.append("chose_get_paid_outside_ramp")
    return handled


def _set_memo_with_reassert(page, memo: str) -> str:
    """Set the memo and defend it against Ramp's AI-suggestion overwrite."""
    memo_box = page.get_by_label("Memo", exact=False).first
    for attempt in range(3):
        memo_box.click()
        memo_box.fill(memo)
        page.keyboard.press("Escape")          # close any suggestion listbox
        page.locator("body").click(position={"x": 5, "y": 5})  # blur
        time.sleep(1.5)                         # let Ramp's AI suggestion race
        current = memo_box.input_value()
        if current == memo:
            return f"memo_set_attempt_{attempt + 1}"
    return f"memo_final_value_differs: {current!r}"


def cmd_reimburse(args) -> dict:
    pdf = Path(args.pdf).expanduser().resolve()
    if not pdf.exists():
        return {"ok": False, "error": f"PDF not found: {pdf}"}

    pw, ctx = _context(headless=not args.visible)
    try:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(RAMP_NEW_REIMBURSEMENT, timeout=60_000)
        page.wait_for_load_state("networkidle", timeout=30_000)
        if not _is_signed_in(page):
            return {"ok": False, "signed_in": False,
                    "fix": "run: python3 ramp_browser.py login"}

        modals = _dismiss_onboarding_modals(page)
        if "residence_modal_present" in modals:
            return {"ok": False, "error": "Ramp is asking for place of residence — "
                                          "needs a human decision. Complete it via 'login' (visible) first.",
                    "screenshot": _shot(page, "residence_modal")}

        # Upload the receipt PDF → Ramp OCRs it and creates a draft
        file_input = page.locator("input[type='file']").first
        file_input.set_input_files(str(pdf))

        # Wait for redirect to the draft page (OCR can take 10-40s)
        try:
            page.wait_for_url("**/details/reimbursements/**", timeout=90_000)
            page.wait_for_load_state("networkidle", timeout=30_000)
        except PWTimeout:
            return {"ok": False, "error": "OCR/draft page never appeared",
                    "screenshot": _shot(page, "ocr_timeout")}

        # Some drafts land on an error shell first — reload once
        if "couldn’t find this content" in page.inner_text("main").lower() or \
           "couldn't find this content" in page.inner_text("main").lower():
            page.reload(timeout=30_000)
            page.wait_for_load_state("networkidle", timeout=30_000)

        draft_url = page.url

        # Extract OCR'd amount/merchant from the heading "$X at MERCHANT"
        heading = page.locator("h2").first.inner_text(timeout=15_000)
        amount, merchant = None, None
        if " at " in heading and heading.startswith("$"):
            amount, merchant = heading.split(" at ", 1)

        # Memo (defended against AI overwrite)
        memo_status = _set_memo_with_reassert(page, args.memo)

        # "Reimburse from" → None (AI fund has reimbursements disabled)
        rf = page.get_by_role("button", name="Reimburse from", exact=False)
        if rf.count() > 0:
            rf.first.click()
            none_opt = page.get_by_role("option", name="None", exact=False)
            if none_opt.count() > 0:
                none_opt.first.click()
            else:
                page.keyboard.press("Escape")

        result = {
            "ok": True,
            "url": draft_url,
            "amount": amount,
            "merchant": merchant,
            "memo": args.memo,
            "memo_status": memo_status,
            "modals_handled": modals,
            "pre_submit_screenshot": _shot(page, "reimbursement_presubmit"),
        }

        if not args.submit:
            result["submitted"] = False
            result["note"] = "DRY RUN — draft saved in Ramp, NOT submitted. Re-run with --submit after confirmation."
            return result

        # --- SUBMIT (only reached when expense_skill.py passed --submit, i.e. Matt confirmed) ---
        submit_btn = page.get_by_role("button", name="Submit", exact=True)
        if submit_btn.count() == 0:
            submit_btn = page.get_by_role("button", name="Save changes", exact=True)
        submit_btn.first.click()
        time.sleep(2)
        _dismiss_onboarding_modals(page)  # bank prompt can fire post-submit
        page.wait_for_load_state("networkidle", timeout=30_000)
        result["submitted"] = True
        result["post_submit_screenshot"] = _shot(page, "reimbursement_postsubmit")
        result["final_url"] = page.url
        return result
    finally:
        ctx.close()
        pw.stop()


# ---------------------------------------------------------------------------
# memo / reconcile — complete EXISTING card transactions (memo + receipt)
#
# The reimburse flow above creates a NEW out-of-pocket reimbursement. These two
# verbs instead COMPLETE an existing Ramp *card* charge that is flagged
# "Missing items" (needs a memo and/or a receipt) — the common weekly case.
# Never use `reimburse` for a charge already on the card; it double-counts.
# ---------------------------------------------------------------------------

TXN_DETAIL = "https://app.ramp.com/details/transactions/{}"
_HEADING_RE = re.compile(r"\$([0-9,]+\.\d{2})\s+at\s+(.+)")


def _read_identity(page):
    """Parse the detail heading '$X at MERCHANT' -> (amount, merchant)."""
    try:
        txt = page.inner_text("main", timeout=15_000)
    except Exception:
        return None, None
    for line in txt.splitlines():
        m = _HEADING_RE.match(line.strip())
        if m:
            return m.group(1), m.group(2).strip()
    return None, None


def _set_detail_memo(page, memo: str) -> str:
    """Open the memo editor (a textarea revealed on click), fill, blur, verify.

    The memo renders as a button until clicked; clicking reveals a focused
    textarea (placeholder 'e.g. Lunch meeting…'). Blur autosaves. We verify the
    text landed and retry — same defend-against-races posture as the reimburse
    memo setter.
    """
    for attempt in range(3):
        trigger = page.get_by_role("button", name="Add a memo", exact=False)
        if trigger.count() == 0:
            trigger = page.get_by_text("Memo", exact=True)
        if trigger.count() == 0:
            return "memo_trigger_not_found"
        trigger.first.click()
        ta = page.locator("textarea")
        try:
            ta.first.wait_for(state="visible", timeout=6_000)
        except PWTimeout:
            continue
        ta.first.click()
        ta.first.fill(memo)
        # The memo editor has explicit Cancel/Save buttons — it does NOT autosave
        # on blur (blurring discards the edit). Must click Save.
        save = page.get_by_role("button", name="Save", exact=True)
        if save.count() == 0:
            save = page.get_by_role("button", name="Save changes", exact=True)
        if save.count():
            save.first.click()
            time.sleep(2)
        else:
            page.keyboard.press("Enter")   # fallback if no Save button
            time.sleep(2)
        if memo[:25] in page.inner_text("main"):
            return f"memo_set_attempt_{attempt + 1}"
    return "memo_uncertain"


def _accept_suggestion(page) -> str:
    """Accept Ramp's pre-drafted AI memo suggestion (one definitive click)."""
    b = page.get_by_role("button", name="Accept suggestion", exact=False)
    if b.count() == 0:
        return "no_suggestion_button"
    b.first.click()
    time.sleep(2)
    return "accepted_suggestion"


def _upload_receipt(page, pdf_path: str) -> str:
    """Upload a receipt PDF to the open transaction; poll until the required
    flag clears (Ramp OCR takes 10-40s)."""
    fi = page.locator("input[type='file']").first
    if fi.count() == 0:
        return "no_file_input"
    fi.set_input_files(pdf_path)
    deadline = time.time() + 60
    while time.time() < deadline:
        if "upload a receipt (required)" not in page.inner_text("main").lower():
            return "receipt_uploaded"
        time.sleep(3)
    return "receipt_upload_unconfirmed"


def _apply_actions(page, spec: dict, submit: bool) -> dict:
    """Assumes `page` is already ON the txn detail. Assert identity, then
    (only when submit) apply receipt/memo/accept-suggestion. Dry-run screenshots
    the current state and reports intended actions without mutating."""
    amount, merchant = _read_identity(page)
    res = {"url": page.url, "ok": True, "found_amount": amount, "found_merchant": merchant}

    # Safety: never write to the wrong transaction.
    if spec.get("expect_amount"):
        want = spec["expect_amount"].lstrip("$")
        if not amount or want not in amount:
            return {**res, "ok": False, "error": "amount_mismatch", "expected": spec["expect_amount"]}
    if spec.get("expect_merchant"):
        if not merchant or spec["expect_merchant"].lower() not in merchant.lower():
            return {**res, "ok": False, "error": "merchant_mismatch", "expected": spec["expect_merchant"]}

    res["missing_before"] = "Missing items" in page.inner_text("main")
    if not submit:
        res["dry_run"] = True
        res["would"] = {k: spec.get(k) for k in ("memo", "accept_suggestion", "receipt_pdf")}
        res["screenshot"] = _shot(page, f"dry_{(merchant or 'txn').split(' ')[0]}")
        return res

    actions = []
    if spec.get("receipt_pdf"):
        if "upload a receipt (required)" not in page.inner_text("main").lower():
            actions.append("receipt_already_present")   # don't duplicate
        else:
            pdf = Path(spec["receipt_pdf"]).expanduser().resolve()
            if not pdf.exists():
                return {**res, "ok": False, "error": f"receipt pdf missing: {pdf}"}
            actions.append(_upload_receipt(page, str(pdf)))
    if spec.get("memo"):
        actions.append(_set_detail_memo(page, spec["memo"]))
    elif spec.get("accept_suggestion"):
        st = _accept_suggestion(page)
        if st == "no_suggestion_button" and spec.get("fallback_memo"):
            st = _set_detail_memo(page, spec["fallback_memo"])
        actions.append(st)
    time.sleep(2)
    res["actions"] = actions
    res["missing_after"] = "Missing items" in page.inner_text("main")
    res["post_screenshot"] = _shot(page, f"done_{(merchant or 'txn').split(' ')[0]}")
    return res


def _scrape_incomplete_uuids(page) -> list:
    """Ordered unique txn UUIDs from the home 'Incomplete expenses' widget."""
    page.goto(RAMP_HOME, timeout=60_000, wait_until="domcontentloaded")
    time.sleep(5)
    out = []
    links = page.locator('a[href^="/details/transactions/"]')
    for i in range(links.count()):
        href = links.nth(i).get_attribute("href")
        if href:
            u = href.split("/")[-1]
            if u not in out:
                out.append(u)
    return out


def cmd_memo(args) -> dict:
    """Complete memo/receipt on ONE existing card transaction."""
    if not args.txn_id and not args.url:
        return {"ok": False, "error": "need --txn-id or --url"}
    spec = {"memo": args.memo, "accept_suggestion": args.accept_suggestion,
            "receipt_pdf": args.receipt_pdf, "expect_merchant": args.expect_merchant,
            "expect_amount": args.expect_amount}
    url = args.url or TXN_DETAIL.format(args.txn_id)
    pw, ctx = _context(headless=not args.visible)
    try:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(url, timeout=60_000, wait_until="domcontentloaded")
        time.sleep(4)
        if not _is_signed_in(page):
            return {"ok": False, "signed_in": False, "fix": "run: python3 ramp_browser.py login"}
        return _apply_actions(page, spec, submit=args.submit)
    finally:
        ctx.close()
        pw.stop()


def cmd_reconcile(args) -> dict:
    """Batch: drain the home 'Incomplete expenses' widget in waves (robust to
    the widget's display cap). Policy: a 'Paypal' charge gets receipt+memo from
    the --plan JSON; every other charge accepts Ramp's AI memo suggestion
    (falling back to a per-merchant default memo when no suggestion exists)."""
    plan = json.loads(Path(args.plan).read_text()) if args.plan else {}
    defaults = plan.get("merchant_default_memo", {})
    custom = plan.get("custom", {})   # {merchant_substr: {memo, receipt_pdf}}

    def _lookup_custom(merchant):
        if not merchant:
            return None
        ml = merchant.lower()
        for k, v in custom.items():
            if k.lower() in ml or ml in k.lower():
                return v
        return None
    pw, ctx = _context(headless=not args.visible)
    results = []
    try:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(RAMP_HOME, timeout=60_000, wait_until="domcontentloaded")
        time.sleep(5)
        if not _is_signed_in(page):
            return {"ok": False, "signed_in": False, "fix": "run: python3 ramp_browser.py login"}
        seen = set()
        for _wave in range(args.max_waves):
            uuids = [u for u in _scrape_incomplete_uuids(page) if u not in seen]
            if not uuids:
                break
            for u in uuids:
                seen.add(u)
                page.goto(TXN_DETAIL.format(u), timeout=60_000, wait_until="domcontentloaded")
                time.sleep(4)
                amount, merchant = _read_identity(page)
                spec = {"expect_merchant": merchant, "expect_amount": amount}
                c = _lookup_custom(merchant)
                if c:
                    spec["memo"] = c.get("memo")
                    if c.get("receipt_pdf"):
                        spec["receipt_pdf"] = c["receipt_pdf"]
                else:
                    spec["accept_suggestion"] = True
                    key = (merchant or "").split(" ")[0]
                    if key in defaults:
                        spec["fallback_memo"] = defaults[key]
                res = _apply_actions(page, spec, submit=args.submit)
                res["uuid"] = u
                results.append(res)
                if args.submit and res.get("ok"):
                    _ledger_append({"action": "filed", "reimburser": "ramp",
                                    "kind": "reconcile-memo",
                                    "merchant": res.get("found_merchant"),
                                    "amount": res.get("found_amount"),
                                    "actions": res.get("actions"),
                                    "missing_after": res.get("missing_after"),
                                    "ramp_url": res.get("url"), "submitted": True})
            if not args.submit:
                break   # dry-run doesn't mutate, so the widget won't change → 1 wave
        return {"ok": True, "submit": args.submit, "count": len(results), "results": results}
    finally:
        ctx.close()
        pw.stop()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("login", help="One-time visible login")
    sp.set_defaults(func=cmd_login)

    sp = sub.add_parser("check", help="Verify login + dump home state")
    sp.set_defaults(func=cmd_check)

    sp = sub.add_parser("reimburse", help="Create a reimbursement draft (submit only with --submit)")
    sp.add_argument("--pdf", required=True)
    sp.add_argument("--memo", required=True)
    sp.add_argument("--submit", action="store_true",
                    help="Actually click Submit (requires upstream confirmation)")
    sp.add_argument("--visible", action="store_true", help="Run with a visible browser")
    sp.set_defaults(func=cmd_reimburse)

    sp = sub.add_parser("memo", help="Complete memo/receipt on ONE existing card txn")
    sp.add_argument("--txn-id", dest="txn_id", help="Ramp transaction UUID")
    sp.add_argument("--url", help="Full /details/transactions/<uuid> URL")
    sp.add_argument("--memo", help="Custom memo text to write")
    sp.add_argument("--accept-suggestion", dest="accept_suggestion", action="store_true",
                    help="Accept Ramp's pre-drafted AI memo suggestion")
    sp.add_argument("--receipt-pdf", dest="receipt_pdf", help="Receipt PDF to upload")
    sp.add_argument("--expect-merchant", dest="expect_merchant",
                    help="Assert the txn merchant before writing (safety)")
    sp.add_argument("--expect-amount", dest="expect_amount",
                    help="Assert the txn amount before writing (safety)")
    sp.add_argument("--submit", action="store_true",
                    help="Actually write (requires upstream confirmation)")
    sp.add_argument("--visible", action="store_true", help="Run with a visible browser")
    sp.set_defaults(func=cmd_memo)

    sp = sub.add_parser("reconcile", help="Drain the home Incomplete-expenses widget in waves")
    sp.add_argument("--plan", help="JSON: {paypal:{memo,receipt_pdf}, merchant_default_memo:{}}")
    sp.add_argument("--max-waves", dest="max_waves", type=int, default=6)
    sp.add_argument("--submit", action="store_true",
                    help="Actually write (requires upstream confirmation)")
    sp.add_argument("--visible", action="store_true", help="Run with a visible browser")
    sp.set_defaults(func=cmd_reconcile)

    args = p.parse_args()
    print(json.dumps(args.func(args), indent=2, default=str))


if __name__ == "__main__":
    main()
