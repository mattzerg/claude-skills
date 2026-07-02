# Vendor-Pay App — Functionality Findings Report

**Client:** Meridian Aerospace
**Lane:** Functionality
**Source:** Read-only super-admin walkthrough of https://vendor-pay.fly.dev, cross-checked against API payloads and the backing database
**Walkthrough date:** 2026-06-01
**Handoff target:** Friday 2026-06-05
**Basis:** Raw observations capture (15 items). No live system was re-accessed for this report; the observations file is the complete capture.

---

## Summary

The functionality walkthrough surfaced **5 confirmed defects**, of which **2 are data-integrity issues** that misstate money owed and should block handoff until fixed. **5 checks passed** clean (totals, queue counts, aging math, duplicate detection, shipping math). **2 areas could not be exercised** under the read-only constraint and need a follow-up pass before sign-off.

Three additional observations from the capture are presentation/design issues, not functionality defects; they are listed in an appendix and routed out of this lane.

### Severity counts

| Severity | Count |
|---|---|
| High (data integrity / blocks handoff) | 2 |
| Medium | 3 |
| Coverage gap (could not test) | 2 |
| Passed | 5 |

---

## High-severity findings

### F-1 — Vendor balance rollup counts a paid invoice (outstanding overstated)
**Observation #4.** The Vendor Balances screen shows Hartwell Supply outstanding at **$14,760.00**. The database sum of their *open* invoices is **$9,840.00**. The $4,920.00 difference is exactly INV-3301, which has `status='paid'` (paid 2026-05-28) but is still included in the outstanding rollup.

**Impact:** The app reports money as owed that has already been paid. This is a financial-correctness bug that affects vendor balances and, by extension, anything downstream that trusts those balances (payment decisions, reconciliation). High severity for an AP product.

**Recommendation:** Exclude `status='paid'` (and any other terminal/settled statuses) from the outstanding-balance aggregation. Audit the rollup query across all vendors, not just Hartwell — this is likely systemic, not isolated to one vendor.

### F-2 — Invoice line grid drops a line item (INV-3318)
**Observation #2.** INV-3318 (Orion Components) has a header total of **$11,250.00**, which is correct: the API returns `amount_total: 11250.00` and three line rows (6000, 3500, 1750), and the DB has all three rows. But the **UI line grid renders only two lines** ($6,000 + $3,500 = $9,500), silently omitting the $1,750 line.

**Impact:** The header total no longer reconciles to the visible lines ($9,500 shown vs $11,250 header), which reads to an approver as a math error and undermines trust in the invoice detail. The underlying data is intact, so this is a rendering/display defect, not a data-loss bug — but it is exactly the kind of discrepancy an AP approver is trained to stop on.

**Recommendation:** Fix the line-grid rendering to display all lines returned by the API. Investigate why the third line is dropped (off-by-one in pagination/slicing, a filter on the line array, or a render key collision are common causes). Add a guard/test asserting that the sum of rendered lines equals the header total.

---

## Medium-severity findings

### F-3 — Payment run header renders "Invalid Date" when no run is scheduled
**Observation #7.** The Payment Run screen header shows **"Next scheduled run: Invalid Date."** The API returns `next_run_at: null` (no run is actually scheduled). The render path does not handle the null case and feeds it straight into a date formatter.

**Impact:** Cosmetic-looking but reads as a broken screen, and it appears on a core operational surface. It will be visible to the client on day one of handoff.

**Recommendation:** Handle the null case explicitly — render "No run scheduled" (or equivalent) instead of formatting a null date.

### F-4 — Due-date ingestion extracted wrong payment term (Net 15 vs Net 45)
**Observation #8.** INV-3340 (Castor Freight): UI and DB both show due date **2026-06-15**. The source PDF says **Net 45** from an invoice date of 2026-05-20, so the correct due date is **2026-07-04**. The ingestion pipeline extracted "Net 15" instead of "Net 45," producing a due date ~19 days too early.

**Impact:** A wrong due date drives the aging report, payment scheduling, and early/late-payment behavior. The UI and DB agree, so this would *not* be caught by a UI-vs-DB consistency check — it is an extraction-accuracy problem at ingestion. One confirmed instance suggests the term-parsing logic may misread other invoices too.

**Recommendation:** Fix the term-extraction logic (likely an OCR/parse confusion between "15" and "45," or a default-to-Net-15 fallback). Run a reconciliation sweep comparing extracted terms against source PDFs across the invoice set to size the blast radius before handoff. Note that this defect is invisible to the aging-report check in F-pass below, because aging is computed correctly *from* the (wrong) stored due date.

### F-5 — Search is case-sensitive
**Observation #11.** Searching **"Hartwell"** returns Hartwell Supply's 6 invoices. Searching **"hartwell"** (lowercase) returns **0 results**, even though the DB has the same 6 rows either way.

**Impact:** Core search behaves unpredictably for end users; case-exact matching is not what an AP clerk expects when typing a vendor name. Low data risk but a real usability/functionality defect on a primary navigation path.

**Recommendation:** Make the search comparison case-insensitive (lower/upper-fold both sides, or use a case-insensitive collation / `ILIKE`).

---

## Coverage gaps (could not be exercised under read-only)

These were intentionally not tested because the walkthrough was read-only. They are **not** passes — they are untested and need a follow-up pass (in a sandbox / with write permission) before sign-off.

### G-1 — Export to NetSuite not exercised
**Observation #13.** The "Export to NetSuite" action targets `POST /api/vendor-pay/exports`, which would push data into the client's NetSuite sandbox (a write to an external system). Per read-only rules it was not clicked. Export correctness is unverified.

**Recommendation:** Exercise this against the NetSuite sandbox in a controlled write-enabled pass before handoff, and validate the exported payload against expected NetSuite field mappings.

### G-2 — Approval routing thresholds not exercisable
**Observation #14.** `ap_routing_rules` has **0 rows**, so threshold-based approval routing cannot be exercised against live data. The feature's behavior is therefore unverified.

**Recommendation:** Confirm with the client whether routing rules are expected to be configured at handoff. If so, seed representative rules and test threshold routing end-to-end. If the empty table is itself a setup gap, flag it for the handoff checklist.

---

## Checks that passed

These were verified consistent across UI, API, and DB and require no action:

- **Observation #1 — INV-3301 totals.** Header $4,920.00 = line items ($2,400 + $1,800 + $720); tax $295.20 shown separately; API and DB (`ap_invoice_lines` sums to 4920.00) all agree.
- **Observation #3 — Pending Approval queue count.** Badge says 7, table has 7 rows, `COUNT(*) WHERE status='pending_approval'` = 7.
- **Observation #6 — Aging report math.** 0-30 bucket $22,400 matches DB invoice-date math (as of today 2026-06-01); 31-60, 61-90, 90+ buckets all match; total row = sum of buckets = total open AP. (Note the caveat in F-4: aging math is correct, but is computed from stored due dates that can be wrong upstream.)
- **Observation #10 — Duplicate detection.** INV-3299 and INV-3322 flagged as duplicates: same vendor (Pell Industrial), same amount ($880.00), same invoice number ("PI-2026-0455"), same PDF hash. Confirmed a true duplicate (vendor sent twice); flag is correct.
- **Observation #15 — INV-3310 total.** Header $1,062.50 initially looked like a math error vs the $1,000 line sum (4 × $250), but the API payload and PDF both include a `shipping_amount` of $62.50; $1,000 + $62.50 = $1,062.50. Correct.

---

## Appendix — Observations routed out of the functionality lane

The following items from the capture are **presentation/design issues, not functionality defects**, and belong to the design/UX lane rather than this report. Listed here only so they are not lost:

- **Observation #5** — Approve button is bright orange while primary actions elsewhere are blue; off-brand inconsistency.
- **Observation #9** — Vendor detail page pushes the contact email below the fold on a 13" screen; requires scrolling.
- **Observation #12** — Credit Memos empty state shows a blank white area with no message or illustration. (Functionally the empty state is *correct* — 0 credit memos in the DB — so there is no functionality defect; the gap is purely the missing empty-state treatment, which is a design concern.)

---

## Recommendation for handoff

**Do not hand off until F-1 and F-2 are fixed and verified** — both misrepresent invoice/balance figures on an accounts-payable product, where financial correctness is the whole value proposition. F-3, F-4, and F-5 should be fixed in the same pass; F-4 in particular warrants a reconciliation sweep to size its blast radius. Close coverage gaps G-1 and G-2 with a write-enabled sandbox pass before sign-off.
