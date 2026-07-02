# vendor-pay app — raw observations from functionality walkthrough (2026-06-01)

Captured by driving https://vendor-pay.fly.dev as super admin, read-only.
Client: Meridian Aerospace. Handoff target: next Friday.
This walkthrough was for the FUNCTIONALITY lane. Raw captures below — not yet a report.

## Observations (unfiltered, in the order captured)

1. Invoice INV-3301 (Hartwell Supply): header total $4,920.00. Line items: $2,400 + $1,800 + $720 = $4,920. Tax shown separately as $295.20. API payload matches UI. DB ap_invoice_lines sums to 4920.00. ✓ consistent

2. Invoice INV-3318 (Orion Components): header total $11,250.00. Line items in UI: $6,000 + $3,500 = $9,500. API /api/vendor-pay/invoices/INV-3318 returns "amount_total": 11250.00, lines array has 3 entries: 6000, 3500, 1750. DB has 3 line rows (6000.00, 3500.00, 1750.00). So the UI line grid is missing the $1,750 line but header is right.

3. The "Pending Approval" queue badge says 7. Counting the rows in the queue table: 7. DB: SELECT COUNT(*) FROM ap_invoices WHERE status='pending_approval' → 7. ✓ consistent

4. Vendor balances screen: Hartwell Supply shows outstanding $14,760.00. DB: SUM of their open invoices = $9,840.00. Difference is exactly $4,920.00 = INV-3301, which has status='paid' (paid 2026-05-28) but is still counted in the outstanding rollup.

5. The approve button on invoice detail is bright orange while everywhere else in the app primary actions are blue. Feels off-brand.

6. Aging report: bucket "0-30 days" shows $22,400. Manually computed from DB invoice dates (today = 2026-06-01): invoices 0-30 days old sum to $22,400.00. Buckets 31-60, 61-90, 90+ also match DB math. Total row = sum of buckets = total open AP. ✓ consistent

7. Payment run screen shows "Next scheduled run: Invalid Date" in the header. API returns "next_run_at": null (no run scheduled). The render doesn't handle null.

8. Invoice INV-3340 (Castor Freight): UI shows due date 2026-06-15, DB has due_date='2026-06-15', but the invoice PDF attachment (source document) says "Net 45" from invoice date 2026-05-20 → due should be 2026-07-04. The ingestion extracted "Net 15" instead of "Net 45".

9. The vendor detail page puts the contact email below the fold on a 13" screen; you have to scroll to find it.

10. Duplicate detection: invoices INV-3299 and INV-3322 are flagged as duplicates of each other. Both are from Pell Industrial, same amount $880.00, same invoice number "PI-2026-0455", same PDF hash. Looks like a true duplicate — the vendor sent it twice. Flag appears correct.

11. Search box: searching "Hartwell" returns Hartwell Supply's 6 invoices. Searching "hartwell" (lowercase) returns 0 results. DB has 6 rows either way.

12. The empty state on the Credit Memos screen just shows a blank white area — no message, no illustration. There are 0 credit memos in the DB so empty is correct, but the screen gives no indication of whether it's empty or broken.

13. Could not check the "Export to NetSuite" action — clicking it would push data to the client's NetSuite sandbox (a write to an external system). Per read-only rules, not exercised. The button's target endpoint is POST /api/vendor-pay/exports.

14. Could not check approval routing thresholds — there are no rules configured in ap_routing_rules (0 rows), so threshold routing can't be exercised on live data.

15. Invoice INV-3310: UI shows total $1,062.50, my expected sum of lines was $1,000.00 (4 × $250). Looked closer: there's a shipping_amount field = $62.50 in the API payload and on the invoice PDF. So $1,000 + $62.50 = $1,062.50. Initially looked like a math error but it's correct once shipping is included.
