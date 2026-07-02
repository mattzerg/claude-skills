---
type: feedback
lane: functionality
target: https://acme-portal.fly.dev
target_kind: live_url
client: Acme Industrial
reviewed_at: 2026-05-25T22:14:00-04:00
build: v4f82c1a
prior_run: null
total_findings: 5
critical: 1
high: 2
medium: 1
low: 1
---

# Acme Industrial (acme-portal) — Orders + Fulfillment Functionality Audit — FINDINGS

- **Owner:** Matt Eisner (matt@zergai.com)
- **Run date:** 2026-05-25
- **Target:** https://acme-portal.fly.dev — build v4f82c1a
- **Scope:** Functional correctness of Orders + Fulfillment. Not a design review.
- **Mode:** Read-only / observational.

## 1. SUMMARY

| Severity | Count | IDs |
|---|---|---|
| Critical | 1 | ORD-01 |
| High | 2 | ORD-02, FUL-01 |
| Medium | 1 | ORD-03 |
| Low | 1 | FUL-02 |

## 2. CONFIRMED FINDINGS

### ORD-01 · Orders · CRITICAL · Order total drops discount line — customer charged $1,840.00 instead of $1,564.00
- URL: https://acme-portal.fly.dev/orders/ORD-2241
- Expected: lines $1,200 + $640 − $276 (15% volume discount) = $1,564.00. Proof: `SELECT amount FROM order_lines WHERE order_id='ord_8821f'` → 3 rows incl. discount row −276.00
- Actual (UI + API agree): header total $1,840.00 — the negative discount line is excluded from the SUM
- Layer at fault: API aggregate (orders.get.ts sums only `amount > 0` lines)
- Repro: open ORD-2241 → compare header total to line grid
- Verification: checker re-summed DB lines, ruled out tax, confirmed reproducible. CONFIRMED.

### ORD-02 · Orders · HIGH · Cancelled orders still count in the "Open Orders" KPI tile
- URL: https://acme-portal.fly.dev/orders (dashboard)
- Expected: KPI "Open Orders: 14" should exclude 3 cancelled orders → 11. Proof: `SELECT COUNT(*) FROM orders WHERE status NOT IN ('cancelled','fulfilled')` → 11
- Actual: tile shows 14; API /api/orders/stats returns {open: 14}
- Layer at fault: API (stats endpoint filters only on `fulfilled`)
- Repro: cancel filter on orders list shows 3 cancelled; tile still says 14
- Verification: checker confirmed count query and reproduced. CONFIRMED.

### FUL-01 · Fulfillment · HIGH · Shipment marked "delivered" while carrier API says in-transit
- URL: https://acme-portal.fly.dev/fulfillment/SHP-0092
- Expected: status should mirror carrier webhook payload (last event: in_transit, 2026-05-24)
- Actual: UI + DB show status='delivered', delivered_at=2026-05-23 (BEFORE the in-transit event)
- Layer at fault: ingestion (webhook handler writes delivered on any 200 from carrier, not on event type)
- Repro: open SHP-0092, compare to carrier tracking page
- Verification: checker pulled webhook log rows, confirmed event sequence. CONFIRMED.

### ORD-03 · Orders · MEDIUM · Orders list date filter is timezone-shifted by one day
- URL: https://acme-portal.fly.dev/orders?from=2026-05-20&to=2026-05-20
- Expected: filtering to 2026-05-20 should return the 4 orders created that day (ET)
- Actual: returns 2 — the two orders created after 8pm ET are excluded (UTC boundary)
- Layer at fault: API (date filter compares UTC timestamps to date-only strings)
- Repro: filter to any single day; orders created 8pm–midnight ET disappear
- Verification: checker reproduced with 3 different dates. CONFIRMED.

### FUL-02 · Fulfillment · LOW · Tracking number rendered with extra whitespace breaking copy-paste
- URL: https://acme-portal.fly.dev/fulfillment/SHP-0088
- Expected: tracking number "1Z999AA10123456784" as a contiguous string
- Actual: rendered with a wrapping space ("1Z999AA10 123456784") — copy-paste into UPS fails
- Layer at fault: render (CSS word-break on a span)
- Repro: copy tracking number from any shipment detail → paste
- Verification: checker confirmed in 2 browsers. CONFIRMED (cosmetic-but-functional).

## 3. METHOD & ACCESS
- DB read-only via flyctl ssh + node pg pool, READ ONLY transactions
- API via curl with replayed login cookie
- All findings survived independent checker refutation

*End of findings. Read-only audit; no live data was mutated.*
