# Acme portal — raw observations against new build v7a91d03 (2026-06-01)

Agent walked the new build overnight. Raw captures below — NOT yet a report.
Prior findings file: acme-portal-prior-findings.md (build v4f82c1a, 2026-05-25)

## Re-checks of prior finding areas

### ORD-2241 (was ORD-01, the discount drop)
- UI header total now shows $1,564.00
- API /api/orders/ORD-2241 → {"total": 1564.00, "lines": [1200.00, 640.00, -276.00]}
- DB: SELECT SUM(amount) FROM order_lines WHERE order_id='ord_8821f' → 1564.00
- All three layers agree now.

### Open Orders KPI tile (was ORD-02)
- Tile shows "Open Orders: 12"
- DB: SELECT COUNT(*) FROM orders WHERE status NOT IN ('cancelled','fulfilled') → 12 (one new order was created since last run; 3 cancelled still excluded)
- API /api/orders/stats → {open: 12}
- Matches.

### SHP-0092 (was FUL-01, the delivered-vs-in-transit shipment)
- UI still shows status='delivered'
- Carrier tracking page (checked 2026-06-01 09:00 ET): "Out for delivery" — so still NOT delivered
- DB: shipments row still has status='delivered', delivered_at='2026-05-23'
- Webhook log: 6 new carrier events since 05-25, all written as status='delivered' regardless of event type
- Same behavior as before.

### Orders date filter (was ORD-03)
- ?from=2026-05-28&to=2026-05-28 → returns 5 orders
- DB: SELECT COUNT(*) FROM orders WHERE created_at::date AT TIME ZONE 'America/New_York' = '2026-05-28' → 5
- Tried 2 more dates incl. one with an 11pm ET order — included correctly now.

### Tracking number whitespace (was FUL-02)
- Could not check: the fulfillment detail screen now 500s on every shipment (see new observation below)

## New observations

### Fulfillment detail screen 500s
- Every URL /fulfillment/SHP-* returns HTTP 500 ("Cannot read properties of undefined (reading 'carrier')")
- API /api/fulfillment/SHP-0088 returns valid JSON
- So the list works, the detail render crashes. Affects all 28 shipments.

### Customer credit balance shows negative available credit
- /customers/CUST-014 shows "Available credit: −$2,300.00"
- DB: credit_limit = 10000.00, SUM(open order totals) = 12300.00
- So the math 10000 − 12300 = −2300 is arithmetically correct — customer is genuinely over their limit
- Question: is showing a negative number a bug, or correct behavior that just reads oddly?

### Payments screen "Total received this month" = $0.00
- Screen shows $0.00 for June
- DB: SELECT SUM(amount) FROM payments WHERE received_at >= '2026-06-01' → 0 rows (no payments recorded in June yet — today is June 1)
- The $0 appears to be genuinely correct.
