---
type: feedback
lane: functionality
target: https://acme-portal.fly.dev
target_kind: live_url
client: Acme Industrial
reviewed_at: 2026-06-01T00:00:00-04:00
build: v7a91d03
prior_run: v4f82c1a (2026-05-25)
prior_findings: 5
resolved: 3
still_present: 1
unverifiable: 1
new_findings: 1
---

# Acme Industrial (acme-portal) — Orders + Fulfillment Re-Verification — FINDINGS

- **Owner:** Matt Eisner (matt@zergai.com)
- **Run date:** 2026-06-01
- **Target:** https://acme-portal.fly.dev — build **v7a91d03** (re-verifying prior build v4f82c1a, 2026-05-25)
- **Scope:** Re-verification of the 5 prior Orders + Fulfillment findings, plus triage of new observations captured against the new build.
- **Mode:** Read-only / observational. This run was performed against a static capture of the new build; no live system was accessed.

## 1. SUMMARY

| Prior ID | Severity | Area | Status in v7a91d03 |
|---|---|---|---|
| ORD-01 | Critical | Orders | ✅ RESOLVED |
| ORD-02 | High | Orders | ✅ RESOLVED |
| FUL-01 | High | Fulfillment | ❌ STILL PRESENT |
| ORD-03 | Medium | Orders | ✅ RESOLVED |
| FUL-02 | Low | Fulfillment | ⚠️ UNVERIFIABLE (blocked by NEW-01) |

| New ID | Severity | Area | Status |
|---|---|---|---|
| NEW-01 | Critical | Fulfillment | ❌ NEW REGRESSION |

**Headline:** 3 of 5 prior findings are fixed (including the critical billing bug). 1 high-severity finding (FUL-01) is unchanged. A **new critical regression (NEW-01)** has broken the entire fulfillment detail screen for all 28 shipments — this also blocks re-verification of the low-severity FUL-02. Two additional observations were triaged as **not bugs** (correct behavior) and are documented in Section 4 so they are not re-reported.

**Net severity movement vs. prior run:** Critical 1 → 1 (the old one fixed, a new one introduced), High 2 → 1, Medium 1 → 0, Low 1 → 0 (1 unverifiable).

## 2. RESOLVED — PRIOR FINDINGS NOW FIXED

### ORD-01 · Orders · was CRITICAL · RESOLVED
- **Was:** Order total dropped the negative discount line; ORD-2241 charged $1,840.00 instead of $1,564.00.
- **Now:** All three layers agree at $1,564.00.
  - UI header total: $1,564.00
  - API `/api/orders/ORD-2241` → `{"total": 1564.00, "lines": [1200.00, 640.00, -276.00]}`
  - DB: `SELECT SUM(amount) FROM order_lines WHERE order_id='ord_8821f'` → 1564.00
- **Verdict:** Fixed. The discount line is now included in the aggregate. The customer-facing billing error is resolved.

### ORD-02 · Orders · was HIGH · RESOLVED
- **Was:** Cancelled orders were counted in the "Open Orders" KPI tile (showed 14, should have been 11).
- **Now:** Tile shows "Open Orders: 12" and matches the DB.
  - DB: `SELECT COUNT(*) FROM orders WHERE status NOT IN ('cancelled','fulfilled')` → 12 (one new order created since the prior run; the 3 cancelled orders are still correctly excluded)
  - API `/api/orders/stats` → `{open: 12}`
- **Verdict:** Fixed. Cancelled orders are now excluded from the open count. (The count moved 11 → 12 only because a genuine new order was created between runs — not a regression.)

### ORD-03 · Orders · was MEDIUM · RESOLVED
- **Was:** Orders list date filter was timezone-shifted by one day; orders created 8pm–midnight ET disappeared (UTC boundary bug).
- **Now:** Date filter returns the correct ET-day set.
  - `?from=2026-05-28&to=2026-05-28` → returns 5 orders
  - DB: `SELECT COUNT(*) FROM orders WHERE created_at::date AT TIME ZONE 'America/New_York' = '2026-05-28'` → 5
  - Spot-checked 2 additional dates, including one with an 11pm ET order — now included correctly.
- **Verdict:** Fixed. The filter now compares against the America/New_York day boundary.

## 3. STILL PRESENT & NEW FINDINGS

### FUL-01 · Fulfillment · HIGH · STILL PRESENT (unchanged from prior run)
- URL: https://acme-portal.fly.dev/fulfillment/SHP-0092
- **Was/Is:** Shipment marked `delivered` while the carrier reports it is not delivered.
- **New build evidence:**
  - UI still shows `status='delivered'`.
  - Carrier tracking page (checked 2026-06-01 09:00 ET): **"Out for delivery"** — the package is still NOT delivered.
  - DB: `shipments` row still `status='delivered'`, `delivered_at='2026-05-23'`.
  - Webhook log: **6 new carrier events** since 05-25, all written as `status='delivered'` regardless of event type.
- **Layer at fault:** Ingestion. The webhook handler still writes `delivered` on any carrier callback rather than keying off the event type — the exact root cause from the prior run. No fix was applied.
- **Verdict:** NOT FIXED. Severity remains HIGH. This is now producing recurring data corruption (6 mis-written events in one week). Recommend prioritizing alongside NEW-01.

### NEW-01 · Fulfillment · CRITICAL · NEW REGRESSION — fulfillment detail screen 500s for every shipment
- URL pattern: https://acme-portal.fly.dev/fulfillment/SHP-* (all)
- **Observed:** Every fulfillment detail URL returns **HTTP 500** with `"Cannot read properties of undefined (reading 'carrier')"`. This affects **all 28 shipments**.
- **Scope isolation:**
  - The fulfillment **list** view works.
  - The API `/api/fulfillment/SHP-0088` returns valid JSON — so the data layer is healthy.
  - The failure is in the **detail render** only: the page reads a `carrier` property off an undefined object.
- **Layer at fault:** Render / page component (front-end reads `.carrier` on an undefined object; API payload is fine).
- **Impact:** No shipment detail can be opened. This is a hard regression introduced in v7a91d03 — the prior build's detail screen worked (the prior run inspected SHP-0088/SHP-0092 detail pages directly). It is customer-blocking for any fulfillment workflow.
- **Verdict:** NEW CRITICAL. Recommend immediate fix. This also blocks re-verification of FUL-02 (below).

### FUL-02 · Fulfillment · LOW · UNVERIFIABLE THIS RUN (blocked by NEW-01)
- **Was:** Tracking number rendered with a wrapping space breaking copy-paste ("1Z999AA10 123456784").
- **This run:** Could not be checked — the fulfillment detail screen 500s on every shipment (NEW-01), so the tracking number never renders.
- **Verdict:** Status UNKNOWN. Carry forward and re-verify once NEW-01 is fixed. Not marked resolved.

## 4. TRIAGED — OBSERVATIONS THAT ARE NOT BUGS

The capture included two additional observations that were investigated and determined to be **correct behavior**, not defects. Documented here so they are not mistaken for findings or re-reported.

### NEG-CREDIT (Not a bug) · Customer credit balance shows negative available credit
- /customers/CUST-014 shows "Available credit: −$2,300.00".
- DB: `credit_limit = 10000.00`, `SUM(open order totals) = 12300.00`.
- The arithmetic (10000 − 12300 = −2300) is correct — **the customer is genuinely over their credit limit.** The negative number is accurate, not a display bug.
- **Note (UX, not functional):** This is correct behavior that reads oddly. Out of scope for this functional audit, but the client may want to consider a clearer presentation (e.g., "$2,300.00 over limit") in a future UX pass. No functional finding raised.

### JUNE-PAYMENTS (Not a bug) · Payments screen "Total received this month" = $0.00
- Screen shows $0.00 for June.
- DB: `SELECT SUM(amount) FROM payments WHERE received_at >= '2026-06-01'` → 0 rows.
- No payments have been recorded in June yet (today is June 1). **$0.00 is genuinely correct.** No finding raised.

## 5. METHOD & ACCESS
- This re-verification was performed against the agent's complete static capture of new build **v7a91d03** (observations dated 2026-06-01). **No live system or URL was accessed during report preparation**; all evidence is drawn from the capture.
- Underlying capture method (per the walk): DB read-only queries, API responses, UI state, and carrier tracking comparison.
- Each prior finding was re-checked against current UI + API + DB evidence; resolved findings required all relevant layers to agree.

## 6. RECOMMENDED NEXT ACTIONS (priority order)
1. **NEW-01 (Critical):** Fix the fulfillment detail render crash (undefined `carrier` read) — currently blocks all 28 shipment detail pages.
2. **FUL-01 (High):** Fix the webhook ingestion handler to key off carrier event type; it is actively mis-writing `delivered` (6 bad events in the last week).
3. **FUL-02 (Low):** Re-verify the tracking-number whitespace issue once NEW-01 is resolved (currently un-checkable).
4. Confirm ORD-01 / ORD-02 / ORD-03 fixes hold under regression testing before close-out.

*End of findings. Read-only re-verification against a static capture of build v7a91d03; no live system was accessed and no data was mutated.*
