# expense-skill — Handoff (built 2026-06-03, ~4am EDT)

## Status: Phase 1 built + verified. ONE manual step left for Matt.

### ⏳ The one thing Matt must do (1 min, at his machine)
The dedicated Ramp browser profile isn't logged in yet. SSO timed out **3×** across
sessions (5-min window each) — likely because Matt was away and/or the Google sign-in
opens as a **separate popup window** (easy to miss behind the main Ramp tab) with no
existing Google session in the fresh profile. Run once, watch for the popup, complete it:

```bash
/usr/bin/python3 ~/.claude/skills/expense-skill/ramp_browser.py login
/usr/bin/python3 ~/.claude/skills/expense-skill/ramp_browser.py check   # verify
```

Until this is done, the **browser channel** (reimbursements) is unavailable. Everything
else works.

**If the login keeps fighting (offered, not yet done):** harden `cmd_login` in
`ramp_browser.py` — bump the wait from 300s → 900s and add popup-window handling
(watch `ctx.on("page")` for the Google SSO popup, poll all pages for sign-in completion,
not just the main tab's URL). ~10-min fix. Do this if Matt reports a 4th timeout.

### Real acceptance test
Next Ramp weekly digest (~Thursday). Matt says **"clear my ramp inbox"** → skill runs
end-to-end with one confirmation.

---

## What was built
`~/.claude/skills/expense-skill/` — a skill (not agent/daemon). Pipeline **find → prep → file → track**,
dispatched per reimburser profile.

| File | Role |
|------|------|
| `SKILL.md` | Frontmatter, verbs, confirmation-gate rules |
| `expense_skill.py` | CLI: `inbox` \| `find` \| `prep` \| `file` \| `status` |
| `receipt_finder.py` | Gmail receipt hunt, both accounts (`find`) |
| `receipt_to_pdf.py` | email/URL → clean PDF; Booking.com receipt-link extraction (`prep`) |
| `ramp_browser.py` | Playwright, **dedicated** profile `sessions/ramp-profile/` (`file` browser channel) — run with `/usr/bin/python3` |
| `profiles/ramp.yaml` | Active reimburser |
| `profiles/{vang-advisory,d4727}.yaml` | Phase 2 stubs |
| `state/ledger.jsonl` | Append-only filing log (currently empty) |

## Verified working
- `inbox` — parses `from:ramp.com` emails into flagged-transaction list (notes email lags live app)
- `find` — found all SFBA trip receipts across both Gmail accounts
- `prep` — regenerated WAFER 450 receipt PDF identical to the manual one (auto-extracted the
  `secure.booking.com/payment_receipt.html?auth_key=` official-receipt link)
- `external_action_gate_hook.py` — added `expense-file` + `ramp-submit` block patterns (Matt-approved);
  all 7 pattern tests pass; gate is live (it even blocked a test command containing the trigger string)

## file verb safety
- Dry-run by default; `--confirmed` required for any external action; **never auto-submits**.
- `--confirmed`/`--submit` are additionally hard-gated by external_action_gate.

## Phase 2 (later) — Vang Advisory + d4727
Expenses tracked in Google Drive folders + a Google Sheet. Profiles are stubbed; need the
Drive folder IDs + Sheet IDs + column schema. Then `file --to vang-advisory` =
drive-skill upload + google-sheets-skill append. Process differs per company/reimburser —
that's why the profile abstraction exists.

## Phase 3 (only if needed)
Ramp API (developer.ramp.com) — requires Idan (admin) to create an API client. Replaces the
browser channel. Draft the ask to Idan only after Phase 1 proves out.

## Lessons baked in
1. **Never use chrome-devtools MCP for Ramp** — 5 concurrent Claude sessions fight over one
   Chrome profile; tabs kept dying mid-flow tonight. Dedicated Playwright persistent context instead.
2. **Ramp AI memo race** — "Filled by Ramp" suggestion overwrites a typed memo on focus change.
   `ramp_browser.py` sets → blurs → re-reads → re-asserts (up to 3×).
3. **Ramp app state lags notification emails** — `inbox` flags this; ground truth is `ramp_browser check`.
4. **Ramp auto-attaches receipts** for known SaaS vendors (Anthropic, OpenAI, etc.) — memo-only needed there.

## Tonight's original task (DONE)
- 2 hotel reimbursements submitted, awaiting Idan: WAFER 450 $338.46 + SureStayPlus $453.24 = $791.70.
  Payout "outside Ramp." SureStayPlus memo is Ramp's generic AI text (editable if Matt cares).
- All flagged card transactions cleared ("all caught up").
- Receipt PDFs archived at `~/Downloads/ramp-invoices-2026-06/`.
- Plan file: `~/.claude/plans/ramp-has-asked-me-valiant-frog.md`.
