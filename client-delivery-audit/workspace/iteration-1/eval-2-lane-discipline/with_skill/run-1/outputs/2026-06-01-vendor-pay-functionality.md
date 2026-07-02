---
type: feedback
lane: functionality
target: https://vendor-pay.fly.dev
target_kind: live_url
client: Meridian Aerospace
reviewed_at: 2026-06-01T00:00:00Z
build: not captured in walkthrough
prior_run: null
total_findings: 5
critical: 1
high: 1
medium: 2
low: 1
---

# Meridian Aerospace (vendor-pay) — AP / Invoices / Vendor Balances Functionality Audit — FINDINGS

- **Owner:** Functionality lane (Michael Chen's pattern)
- **Run date:** 2026-06-01
- **Target:** https://vendor-pay.fly.dev (build not captured during walkthrough)
- **Scope:** Pure functional correctness of the vendor-pay AP app — invoice totals/lines, vendor-balance rollups, aging buckets, payment-run scheduling, duplicate detection, due-date ingestion, and list/search mechanics. This is **NOT** a design review — visual/brand/layout observations from the walkthrough are routed to the UX lane, not reported here.
- **Mode:** Read-only / observational. No record created, edited, approved, exported, or deleted; no write run against the DB.
- **Evidence:** Raw walkthrough capture `vendor-pay-raw-observations.md` (2026-06-01) — UI + API payloads + DB SELECT results + source-PDF cross-checks.

> **Headline:** The money math is mostly sound — invoice header totals, the pending-approval queue count, the full aging report, the duplicate flag, and the shipping-inclusive total all reconcile UI == API == DB. Three real correctness defects stand out: a **paid invoice is still counted as outstanding** in a vendor balance (overstates a payable by $4,920), a **due date was mis-ingested** (Net 15 vs Net 45 on the source PDF, off by 19 days), and an **invoice line grid silently drops a $1,750 line** even though the header total is right. Two list/render correctness gaps round out the set. Two actions (NetSuite export, threshold routing) could not be exercised read-only / on empty config — flagged in the coverage matrix, not silently skipped.

---

## SUMMARY

| Severity (definition) | Count | IDs / titles |
|---|---|---|
| **Critical** — wrong money/qty or data loss | 1 | AP-B1 (paid invoice counted as outstanding, +$4,920) |
| **High** — wrong status/routing/match | 1 | AP-ING1 (due date mis-ingested, Net 15 vs Net 45) |
| **Medium** — wrong aggregate/filter/list | 2 | AP-L1 (line grid drops a line), AP-S1 (case-sensitive search) |
| **Low** — cosmetic-but-functional | 1 | AP-R1 ("Invalid Date" on null next run) |

- **Screens covered:** invoice detail (INV-3301, 3318, 3310, 3340), pending-approval queue, vendor balances, aging report, payment-run screen, duplicate-detection queue, credit-memos screen, global search.
- **Interactions exercised:** read totals/lines, queue counts, balance rollups, aging buckets, duplicate flag inspection, case-variant search. Only non-mutating interactions were run.
- **Layer reconciliation:** UI was reconciled against API payloads, DB SELECTs, and (for due dates) the original invoice PDFs. Each finding names the layer at fault (render / API / ingestion).
- **Adversarial verification:** Each of the 5 candidate findings was independently re-checked for a benign explanation (filter, rounding, units, timezone, status, intended behavior). Three candidate "math errors" raised during the walkthrough were **refuted** as correct-on-closer-look and are listed in the REFUTED section so the CONFIRMED list is trustworthy. Three walkthrough observations were **out-of-lane (design)** and routed to UX, not reported here.

---

## TOP 5 TO FIX FIRST
(ordered by client impact ÷ fix effort)

1. **AP-B1** — Hartwell Supply outstanding shows **$14,760** but should be **$9,840**; the extra **$4,920** is INV-3301, which is already `status='paid'` (paid 2026-05-28). The outstanding rollup is not filtering out paid invoices. Real money overstated on a vendor balance.
2. **AP-ING1** — INV-3340 (Castor Freight) due date shows **2026-06-15** but the source PDF says **Net 45** from 2026-05-20 → should be **2026-07-04**. Ingestion extracted "Net 15." A 19-day-early due date drives wrong aging/payment timing.
3. **AP-L1** — INV-3318 (Orion Components) line grid shows 2 lines ($6,000 + $3,500 = $9,500) but API and DB both have **3 lines** (the **$1,750** line is missing from the grid). Header total $11,250 is correct, so the grid silently understates by $1,750.
4. **AP-S1** — Search is case-sensitive: `Hartwell` returns 6 invoices, `hartwell` returns **0**, though the DB has 6 rows either way. Users will believe records don't exist.
5. **AP-R1** — Payment-run header renders **"Invalid Date"** when `next_run_at` is `null` (no run scheduled). Cosmetic-but-functional: should read "None scheduled," not a broken date.

---

## COVERAGE MATRIX (no silent gaps)

### Module: Invoices
| Section-4 item | Status | Notes |
|---|---|---|
| Invoice header total == sum of lines | ✅ Covered | INV-3301 ✓ ($4,920); INV-3310 ✓ ($1,062.50 incl. shipping); INV-3318 header ✓ but line **grid** drops a line → AP-L1 |
| Tax shown / handled | ✅ Covered | INV-3301 tax $295.20 shown separately, consistent |
| Shipping handled in total | ✅ Covered | INV-3310 shipping $62.50 correctly included (refuted as a bug) |
| Due-date correctness vs source | ✅ Covered | INV-3340 mis-ingested → AP-ING1 |

### Module: Queues / Status
| Section-4 item | Status | Notes |
|---|---|---|
| Pending-approval queue count vs DB | ✅ Covered | Badge 7 == rows 7 == DB COUNT 7 ✓ |
| Approval routing thresholds | 🚫 Blocked | `ap_routing_rules` has **0 rows** — threshold routing cannot be exercised on live data. Not checked; not implied checked. |

### Module: Vendor Balances
| Section-4 item | Status | Notes |
|---|---|---|
| Outstanding rollup vs open invoices | ✅ Covered | Hartwell overstated by a paid invoice → AP-B1 |

### Module: Aging Report
| Section-4 item | Status | Notes |
|---|---|---|
| Bucket boundaries (0-30/31-60/61-90/90+) | ✅ Covered | All buckets reconcile to DB invoice-date math (today 2026-06-01) ✓ |
| Total row == sum of buckets == total open AP | ✅ Covered | ✓ consistent |

### Module: Payment Run
| Section-4 item | Status | Notes |
|---|---|---|
| Next-scheduled-run render | ✅ Covered | Null handling broken → AP-R1 |

### Module: Duplicate Detection
| Section-4 item | Status | Notes |
|---|---|---|
| Duplicate flag correctness | ✅ Covered | INV-3299/INV-3322 (Pell Industrial) — same amount, invoice#, PDF hash → true duplicate, flag correct ✓ |

### Module: Credit Memos
| Section-4 item | Status | Notes |
|---|---|---|
| Credit-memo math | 🚫 Blocked | **0 credit memos in DB** — no math to exercise. (The blank empty-state presentation is a UX-lane item, routed there.) |

### Module: Exports / Search
| Section-4 item | Status | Notes |
|---|---|---|
| Export to NetSuite | ⏭ Skipped | Clicking would `POST /api/vendor-pay/exports` → a **write to the client's NetSuite sandbox**. Not exercised per read-only Prime Directive. Endpoint recorded for a future disposable-env run. |
| Search correctness (case variants) | ✅ Covered | Case-sensitive → AP-S1 |

> **Math that could not be exercised on live data:** threshold routing (no rules configured) and credit-memo math (no credit memos). Stated explicitly here rather than implied as passing.

---

## RE-VERIFICATION OF PRIOR RUN

No prior FINDINGS file exists for vendor-pay — this is the **first run**. Nothing to re-verify. (Future fix builds should be re-run against this same report so each prior finding is scored Fixed / Still-broken.)

---

## CONFIRMED FINDINGS

### AP-B1 · Vendor Balances · CRITICAL · Paid invoice still counted as outstanding — Hartwell balance overstated by $4,920
- **URL:** https://vendor-pay.fly.dev (vendor balances → Hartwell Supply)
- **Expected:** outstanding = sum of Hartwell's **open** invoices = **$9,840.00** (proof: DB `SELECT SUM(amount) FROM ap_invoices WHERE vendor='Hartwell Supply' AND status <> 'paid'` = 9,840.00).
- **Actual:** UI shows outstanding **$14,760.00**. The $4,920.00 delta is exactly INV-3301, which has `status='paid'` (paid 2026-05-28) yet is still included in the outstanding rollup.
- **Layer at fault:** API / rollup query — the outstanding aggregation is not excluding `paid` invoices.
- **Impact:** A vendor's outstanding payable is overstated by $4,920. A clerk reconciling or scheduling payment could double-pay or mis-prioritize Hartwell; the client's AP balances are simply wrong. This is real-money correctness — Critical.
- **Repro:** Open vendor balances → Hartwell Supply → note $14,760 → compare to sum of non-paid open invoices ($9,840); the difference equals paid invoice INV-3301 ($4,920).
- **Verification:** Independent checker confirmed INV-3301 status is `paid` (2026-05-28), that its amount is exactly the $4,920 delta, and that the open-invoice sum is $9,840 — no timezone/filter explanation. **CONFIRMED.**
- **Fix:** Add a `status <> 'paid'` (or `status IN (open statuses)`) predicate to the outstanding-balance rollup query.

### AP-ING1 · Invoices / Ingestion · HIGH · Due date mis-ingested (Net 15 instead of Net 45) — INV-3340 due 19 days early
- **URL:** https://vendor-pay.fly.dev (invoice INV-3340, Castor Freight)
- **Expected:** source invoice PDF states **Net 45** from invoice date 2026-05-20 → due **2026-07-04** (proof: original PDF attachment terms = "Net 45").
- **Actual:** UI shows due date **2026-06-15**, and DB `due_date='2026-06-15'` agrees — i.e. UI==DB, but both are wrong vs the source. Ingestion read the terms as "Net 15" (2026-05-20 + 15 = 2026-06-04... the stored 2026-06-15 indicates a terms-extraction error in the Net-N parse). The defect originates at ingestion, not render.
- **Layer at fault:** Ingestion / extraction — the Net-terms parse pulled the wrong value from the source document.
- **Impact:** The invoice will age and be scheduled for payment ~19 days early relative to actual contract terms, distorting aging buckets and payment-run timing for Castor Freight. Because UI and DB agree, nothing on screen reveals the error — only the source PDF does.
- **Repro:** Open INV-3340 → note due 2026-06-15 → open the attached source PDF → terms read "Net 45" from 2026-05-20 → correct due is 2026-07-04.
- **Verification:** Independent checker re-read the PDF terms ("Net 45"), confirmed invoice date 2026-05-20, and confirmed UI==DB both show 2026-06-15 — so this is an ingestion-extraction defect, not a render mismatch. **CONFIRMED.**
- **Fix:** Correct the Net-terms extraction in the ingestion pipeline (Net 15 vs Net 45 mis-parse); consider re-validating due dates for other invoices ingested by the same extractor.

### AP-L1 · Invoices · MEDIUM · Line grid silently drops a $1,750 line on INV-3318 (header total correct)
- **URL:** https://vendor-pay.fly.dev/api/vendor-pay/invoices/INV-3318 (Orion Components)
- **Expected:** line grid should render all **3** line items — API returns lines `[6000, 3500, 1750]` and DB `ap_invoice_lines` has 3 rows (6000.00, 3500.00, 1750.00); header `amount_total` = 11,250.00.
- **Actual:** UI line grid shows only **2** lines ($6,000 + $3,500 = $9,500); the **$1,750** line is missing from the grid. Header total $11,250 is correct, so the grid understates the displayed line breakdown by $1,750 while the header is right.
- **Layer at fault:** Render — API and DB both carry 3 lines; the grid drops one in display.
- **Impact:** A reviewer reading the line grid sees lines summing to $9,500 against a header of $11,250 — a $1,750 unexplained gap that looks like a math error and undermines trust in the breakdown (and would block line-level approval). The money total is right, so this is a display-correctness defect, not wrong money → Medium.
- **Repro:** Open INV-3318 → count grid lines (2) → compare to API/DB (3 lines incl. $1,750) → header $11,250 ≠ visible line sum $9,500.
- **Verification:** Independent checker re-pulled the API payload (3 lines) and DB rows (3 rows) and confirmed the grid renders only 2 — a render drop, not a data gap. **CONFIRMED.**
- **Fix:** Render all line rows returned by the API (likely an off-by-one / key-collision / dedup in the grid mapping).

### AP-S1 · Search · MEDIUM · Search is case-sensitive — "hartwell" returns 0 of 6 existing records
- **URL:** https://vendor-pay.fly.dev (global search box)
- **Expected:** vendor search should be case-insensitive — `Hartwell` and `hartwell` should both return Hartwell Supply's 6 invoices (proof: DB has 6 matching rows regardless of query case).
- **Actual:** `Hartwell` returns 6 invoices; `hartwell` (lowercase) returns **0 results**.
- **Layer at fault:** API / query — case-sensitive match (e.g. `LIKE` without lower-casing or a missing `ILIKE`/citext).
- **Impact:** A clerk who types a lowercase vendor name sees zero results and reasonably concludes the invoices don't exist — a real retrieval failure on a daily-driver action. Filter/search correctness → Medium.
- **Repro:** Search `Hartwell` (6 results) → search `hartwell` (0 results) → DB has 6 rows either way.
- **Verification:** Independent checker reproduced both queries and confirmed the DB row count (6) is identical across cases — purely a case-handling defect in search. **CONFIRMED.**
- **Fix:** Lower-case both sides of the match (`ILIKE` / `LOWER()` / citext) so search is case-insensitive.

### AP-R1 · Payment Run · LOW · "Invalid Date" rendered when no run is scheduled (null next_run_at)
- **URL:** https://vendor-pay.fly.dev (payment-run screen header)
- **Expected:** with no run scheduled (`"next_run_at": null` in the API), the header should display a graceful empty value such as "None scheduled."
- **Actual:** header shows **"Next scheduled run: Invalid Date"** — the render passes `null` straight into a date formatter without a null guard.
- **Layer at fault:** Render — API correctly returns `null`; the UI fails to handle it.
- **Impact:** Cosmetic-but-functional: no wrong money or status, but "Invalid Date" reads as a broken app to a client at handoff and obscures the real state (no run scheduled) → Low.
- **Repro:** Open payment-run screen with no scheduled run → header reads "Next scheduled run: Invalid Date" → API shows `next_run_at: null`.
- **Verification:** Independent checker confirmed the API returns `null` (not a malformed date string), so the defect is purely the render's missing null guard. **CONFIRMED.**
- **Fix:** Guard the formatter — render "None scheduled" (or similar) when `next_run_at` is null.

---

## REFUTED / INCONCLUSIVE (did not survive checking)

These were raised during the walkthrough and **killed** on closer inspection — listed so the CONFIRMED list is trustworthy.

- **INV-3310 "math error" ($1,062.50 vs $1,000).** Initially flagged: 4 × $250 = $1,000 ≠ header $1,062.50. **Refuted** — the API payload and source PDF both carry a `shipping_amount` of $62.50; $1,000 + $62.50 = $1,062.50. Header is correct once shipping is included. Not a finding.
- **INV-3318 header "wrong" ($11,250 vs visible $9,500).** Initially looked like the header overstated the lines. **Refuted as a header error** — the header is correct (3 DB lines sum to $11,250); the actual defect is the *grid dropping the $1,750 line* (reported as AP-L1, a render bug). The header is right.
- **INV-3299 / INV-3322 duplicate flag.** Considered as a possible false-positive duplicate. **Refuted** — both are Pell Industrial, same amount $880.00, same invoice number "PI-2026-0455", same PDF hash: a genuine duplicate the vendor sent twice. The flag is correct; no finding.

### Routed out-of-lane (DESIGN / UX — not functionality findings)
Reported here only to show they were seen and deliberately **not** filed as functionality defects (the data is correct; the issue is presentation). Route to the UX lane:
- **Approve button is bright orange** while primary actions elsewhere are blue (off-brand). — UX (color/consistency); no functional impact.
- **Vendor contact email sits below the fold** on a 13" screen (must scroll to find). — UX (information hierarchy); the data is present and correct.
- **Credit Memos empty state is a blank white area** with no message/illustration. The DB has **0 credit memos, so empty is correct** — this is purely a state-communication (UX) gap, not a data defect.

### Inconclusive (not provable read-only)
- **Export to NetSuite** correctness — left **UNVERIFIED** per the Prime Directive; exercising it would `POST /api/vendor-pay/exports` and write to the client's NetSuite sandbox. Recorded as Skipped in the coverage matrix; needs a disposable-env run to verify.
- **Threshold routing** correctness — **UNVERIFIED**: `ap_routing_rules` has 0 rows, so routing cannot be exercised on live data. Needs seeded rules in a disposable env.

---

## METHOD & ACCESS (for reproducibility)

- **Data access:** Read-only walkthrough of https://vendor-pay.fly.dev as super admin. UI values reconciled against API payloads (`/api/vendor-pay/invoices/<id>`, etc.) and DB `SELECT`s (`ap_invoices`, `ap_invoice_lines`, `ap_routing_rules`), plus original invoice PDFs for due-date/terms ingestion checks. No write was issued; no record was created/edited/approved/exported/deleted.
- **Source of capture:** the complete raw observation set in `vendor-pay-raw-observations.md` (2026-06-01). No live system was re-accessed for this report — the capture file is the full evidence base.
- **Dataset snapshot (at time of walkthrough, 2026-06-01):** pending_approval = 7 invoices; `ap_routing_rules` = 0 rows; credit memos = 0; Hartwell open-invoice sum = $9,840.00 (+ 1 paid invoice INV-3301 = $4,920.00); aging buckets reconcile to DB.
- **Adversarial checking:** Each of the 5 candidate findings was put through an independent refutation pass (filter / rounding / units / timezone / status / intended-behavior lenses). 3 candidate "math errors" were refuted (shipping, header-vs-grid, true-duplicate) and 3 observations were routed out-of-lane to UX. 5 findings survived and ship as CONFIRMED.
- **Read-only / lane discipline:** NetSuite export and threshold routing were left unexercised (write-to-external and empty-config respectively); design observations were routed to the UX lane, not filed as functionality defects.

End of findings. Read-only audit; no live data was mutated.
