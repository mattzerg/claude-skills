---
name: expense-skill
description: Personal expense handling across reimbursers (Ramp first; Vang Advisory and d4727 later). Finds receipts in Gmail, generates clean receipt PDFs from emails/booking sites, parses what Ramp needs, preps memos, and files reimbursements with confirmation gates. Use when Matt asks "clear my ramp inbox", "what does ramp need", "file my expenses", "expense this trip", "submit hotel reimbursements", "find the receipt for X", or when a Ramp digest email flags transactions with missing items.
allowed-tools: Bash, Read, Write
---

# Expense Skill — Personal Expense Handling

Pipeline: **find → prep → file → track**, dispatched per reimburser profile (`profiles/*.yaml`).

## CRITICAL: Filing Confirmation Required

**Before filing ANY expense (Ramp submission, email forward, sheet append), you MUST get explicit user confirmation.**

1. Show the complete expense details: amount, merchant, dates, memo, receipt file, destination
2. Ask: "File this to <reimburser>?"
3. ONLY file AFTER explicit confirmation ("yes", "submit", "go ahead")
4. NEVER file without confirmation — even in rapid-fire mode, even if Matt asked to "file everything" earlier in the session

`file` without `--confirmed` always runs as a dry-run. The `--confirmed` flag is what the external action gate checks.

## Commands

All commands output JSON. `$SKILL` = `~/.claude/skills/expense-skill`.

### What does Ramp need right now?

```bash
python3 $SKILL/expense_skill.py inbox [--days 30]
```

Parses `from:ramp.com` emails (weekly digests + per-transaction alerts) into a structured list of
transactions needing memos/receipts, plus reimbursements awaiting approval.

### Find candidate receipts

```bash
python3 $SKILL/expense_skill.py find --since 2026-04-20 [--until DATE] [--vendor booking.com] [--account EMAIL]
```

Hunts both Gmail accounts for receipt-bearing emails (booking sites, Stripe/LemonSqueezy receipts,
hotels, rideshare, SaaS vendors). Classifies by vendor, amount, date.

### Prep a receipt PDF

```bash
# From an email (works for both OAuth and IMAP accounts)
python3 $SKILL/expense_skill.py prep --msg-id 19dc1079716039a5 --account matteisn@gmail.com [--label wafer450]

# From a URL (booking confirmation pages, vendor receipt pages)
python3 $SKILL/expense_skill.py prep --url "https://secure.booking.com/payment_receipt.html?auth_key=..." [--label hotel]

# Merge multiple PDFs into one receipt
python3 $SKILL/expense_skill.py prep --merge a.pdf b.pdf --label combined
```

Output PDFs land in `$SKILL/output/`. For Booking.com emails, the prep step auto-extracts the
`payment_receipt.html?auth_key=` link and renders that (official receipt) instead of the raw email.

### File an expense

```bash
# Reimbursement to Ramp (browser channel) — dry-run by default
python3 $SKILL/expense_skill.py file --to ramp --kind reimbursement \
  --pdf $SKILL/output/hotel.pdf --memo "Hotel for Zerg onboarding ..." [--confirmed]

# Receipt for an existing Ramp card transaction (email-forward channel)
python3 $SKILL/expense_skill.py file --to ramp --kind receipt-forward \
  --msg-id <receipt-email-id> --account matthew@zergai.com [--confirmed]
```

Without `--confirmed`: fills everything, screenshots the pre-submit state, does NOT submit/send.
With `--confirmed`: performs the external action (gated by external_action_gate hook).

### Complete an existing card charge (memo / receipt)

Most weekly flags are **existing Ramp card charges** marked "Missing items" (need a memo
and/or receipt) — NOT out-of-pocket reimbursements. Do **not** use `--kind reimbursement`
for these; it creates a new reimbursement and double-counts. Use `--kind memo`:

```bash
# One charge: accept Ramp's AI memo suggestion (safety: assert it's the right txn)
python3 $SKILL/expense_skill.py file --to ramp --kind memo \
  --txn-id <uuid> --accept-suggestion \
  --expect-merchant Anthropic --expect-amount 200.00 [--confirmed]

# One charge: custom memo + upload a receipt PDF
python3 $SKILL/expense_skill.py file --to ramp --kind memo \
  --url https://app.ramp.com/details/transactions/<uuid> \
  --memo "DeepSeek API credits — $50 top-up (Zerg)" \
  --pdf $SKILL/output/deepseek-paypal.pdf [--confirmed]
```

The memo editor has explicit Cancel/**Save** buttons (no autosave on blur — the driver clicks
Save). Identity is asserted (`--expect-*`) before any write so it can never memo the wrong charge.

### Reconcile the whole queue in one shot (weekly)

```bash
# Ground truth first (email UNDERCOUNTS — the live widget is authoritative):
/usr/bin/python3 $SKILL/ramp_browser.py check

# Drain the home "Incomplete expenses" widget in waves (robust to its display cap).
# Dry-run (no writes) — preview intended action per charge:
/usr/bin/python3 $SKILL/ramp_browser.py reconcile --plan $SKILL/state/reconcile_plan.json
# Real run (gated — see below): add --submit
/usr/bin/python3 $SKILL/ramp_browser.py reconcile --plan $SKILL/state/reconcile_plan.json --submit
```

`reconcile_plan.json` shape:
```json
{
  "custom": { "Paypal": {"memo": "...", "receipt_pdf": "/abs/path.pdf"},
              "Obsidian": {"memo": "...", "receipt_pdf": "/abs/path.pdf"} },
  "merchant_default_memo": { "Anthropic": "...", "Fal": "..." }
}
```
Policy: a merchant matched in `custom` gets that memo (+ receipt); every other charge accepts
Ramp's AI suggestion (falling back to `merchant_default_memo` when no suggestion exists).

**Gate note:** `--submit` (and `expense_skill file --confirmed`) is blocked by
`external_action_gate_hook.py` — Claude cannot self-authorize. Matt runs the `--submit` command
himself (a normal terminal has no gate), or relaunches with
`ZERG_EXTERNAL_ACTION_OK=ramp-memo-submit` and lets Claude run it.

### Status

```bash
python3 $SKILL/expense_skill.py status
```

Merges the local ledger (`state/ledger.jsonl`) with a fresh `inbox` parse.

## Ramp browser channel

`ramp_browser.py` uses a **dedicated Playwright persistent profile** at `$SKILL/sessions/ramp-profile/`
(never the shared chrome-devtools MCP profile — multiple Claude sessions fight over it).

One-time login (note: `/usr/bin/python3` — that's where Playwright lives):

```bash
/usr/bin/python3 $SKILL/ramp_browser.py login    # opens visible browser; Matt completes Google SSO once
```

Known Ramp UI behaviors handled:
- Ramp's AI memo suggestion can overwrite a typed memo on focus change → memo is set, blurred, re-read, and re-asserted
- Receipt OCR takes 10-40s after upload → polled until the draft form appears
- "Reimburse from" only offers None (AI fund has reimbursements disabled) → set to None

## Reimburser profiles

- `profiles/ramp.yaml` — Epoch AI Inc via Ramp (active)
- `profiles/vang-advisory.yaml` — Phase 2 (Drive folder + Sheet)
- `profiles/d4727.yaml` — Phase 2 (Drive folder + Sheet)

## Security notes

- Filing actions are blocked by `~/.claude/hooks/external_action_gate_hook.py` unless `--confirmed` is present AND Matt approved in-session
- Playwright session (Ramp login) lives in `sessions/` (mode 700); treat like a credential
- The ledger contains amounts/merchants only — no card numbers, no credentials
