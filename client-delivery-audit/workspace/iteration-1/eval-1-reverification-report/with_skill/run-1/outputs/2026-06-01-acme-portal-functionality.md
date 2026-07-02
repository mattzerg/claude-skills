---
type: feedback
lane: functionality
target: https://acme-portal.fly.dev
target_kind: live_url
client: Acme Industrial
reviewed_at: 2026-06-01T09:30:00-04:00
build: v7a91d03
prior_run: acme-portal-prior-findings.md
total_findings: 2
critical: 1
high: 1
medium: 0
low: 0
---

# Acme Industrial (acme-portal) — Orders + Fulfillment Functionality Audit — FINDINGS (re-verification)

- **Owner:** Matt Eisner (matt@zergai.com)
- **Run date:** 2026-06-01
- **Target:** https://acme-portal.fly.dev — build **v7a91d03** (prior run: v4f82c1a, 2026-05-25)
- **Scope:** Functional correctness of Orders + Fulfillment, re-verifying the 5 prior findings then sweeping for regressions. Not a design review; UX-only observations are routed out, not reported here.
- **Mode:** Read-only / observational. No live data mutated.
- **Evidence dir:** raw capture in `acme-portal-new-build-observations.md` (overnight walk of v7a91d03).

> **Headline:** This build fixed 3 of 5 prior findings — including the CRITICAL mischarge (ORD-01) and both Orders defects. But it shipped a **new CRITICAL regression**: the fulfillment detail screen now 500s on **all 28 shipments**, fully blocking the Fulfillment module. And the one prior fulfillment defect (FUL-01, delivered-vs-in-transit) is **still broken**. Net: Orders is in good shape; Fulfillment went backward.

## 1. SUMMARY

| Severity (definition) | Count | IDs / titles |
|---|---|---|
| Critical — wrong money/qty or data loss / core flow unusable | 1 | FUL-03 (fulfillment detail 500s on all shipments) |
| High — wrong status/routing/match | 1 | FUL-01 (delivered while carrier says not delivered) |
| Medium — wrong aggregate/filter | 0 | — |
| Low — cosmetic-but-functional | 0 | — |

- **Screens covered:** Orders dashboard + order detail (ORD-2241), Orders list date filter, Open-Orders KPI tile, Fulfillment detail (SHP-*), Customer credit (CUST-014), Payments month-to-date.
- **Interactions exercised:** prior-finding re-checks (5/5), plus regression sweep across fulfillment detail, customer credit math, and payments aggregate.
- **Layer reconciliation:** for every confirmed finding, UI / API / DB were cross-checked. FUL-03 is render-layer only (API returns valid JSON, the screen crashes). FUL-01 reconciles UI==DB but both disagree with the carrier source of truth.
- **Adversarial verification:** every prior finding was re-checked against fresh evidence before new hunting. Two raised candidates (negative credit balance, $0 payments) were adversarially refuted and did not ship — see §7.

## 2. TOP 2 TO FIX FIRST

1. **FUL-03 — Fulfillment detail screen returns HTTP 500 on every one of 28 shipments.** A render path reads `.carrier` off an undefined object; the API itself returns valid JSON. The entire Fulfillment detail view is unreachable. New in v7a91d03.
2. **FUL-01 — Shipment SHP-0092 still shows "delivered" while the carrier says "Out for delivery" as of 2026-06-01 09:00 ET.** The webhook handler still writes `status='delivered'` on every carrier event regardless of type (6 more such writes since 05-25). Carried over unfixed from the prior run.

## 3. COVERAGE MATRIX (no silent gaps)

### Orders
| Item | Status | Notes |
|---|---|---|
| Order total / discount aggregate (ORD-2241) | ✅ Covered | UI/API/DB all = $1,564.00 |
| Open-Orders KPI tile | ✅ Covered | tile/API/DB all = 12 (one new order since last run) |
| Orders list date filter (timezone) | ✅ Covered | 3 dates incl. 11pm ET order — all correct |

### Fulfillment
| Item | Status | Notes |
|---|---|---|
| Shipment status vs carrier (SHP-0092) | ✅ Covered | still wrong — see FUL-01 |
| Fulfillment detail render (all SHP-*) | ✅ Covered | all 28 return 500 — see FUL-03 |
| Tracking-number whitespace (SHP-0088) | 🚫 Blocked | could not re-verify — detail screen 500s before the tracking number renders. Status of prior FUL-02 is **unknown**, not assumed fixed. |

> The fulfillment detail 500 (FUL-03) blocks visual verification of any detail-screen-rendered value, including the prior FUL-02 whitespace defect. FUL-02 is reported below as **blocked / unknown**, not silently closed.

## 4. RE-VERIFICATION OF PRIOR RUN

| # | Prior defect | Status now | Evidence |
|---|---|---|---|
| ORD-01 (Critical) | Order total drops discount line ($1,840 vs $1,564) | ✅ Fixed | UI header = $1,564.00; API `/api/orders/ORD-2241` `total:1564.00` with lines `[1200, 640, -276]`; DB `SUM(amount) WHERE order_id='ord_8821f'` = 1564.00. All three layers agree. |
| ORD-02 (High) | Cancelled orders counted in Open-Orders KPI | ✅ Fixed | Tile = 12; DB `COUNT(*) WHERE status NOT IN ('cancelled','fulfilled')` = 12 (one new order since last run; 3 cancelled correctly excluded); API `/api/orders/stats` `{open:12}`. Matches. |
| FUL-01 (High) | Shipment marked delivered while carrier in-transit | ❌ Still broken | UI/DB still `status='delivered'`, `delivered_at='2026-05-23'`; carrier page 2026-06-01 09:00 ET = "Out for delivery". 6 new webhook events since 05-25 all written `delivered` regardless of event type. See §6. |
| ORD-03 (Medium) | Orders date filter timezone-shifted by one day | ✅ Fixed | `?from=2026-05-28&to=2026-05-28` returns 5; DB `created_at::date AT TIME ZONE 'America/New_York' = '2026-05-28'` = 5; an 11pm ET order is now included correctly across 3 tested dates. |
| FUL-02 (Low) | Tracking number whitespace breaks copy-paste | 🚫 Blocked — unknown | Could not re-verify: the fulfillment detail screen now 500s on every shipment (FUL-03) before the tracking number renders. Listed so it is not silently dropped — re-check once FUL-03 is fixed. |

**Scoreboard: 3 Fixed ✅ · 1 Still broken ❌ · 1 Blocked/unknown 🚫 · 1 new regression (FUL-03).**

## 5. CONFIRMED FINDINGS

### FUL-03 · Fulfillment · CRITICAL · Fulfillment detail screen 500s on all 28 shipments — the entire detail view is unreachable
- URL: https://acme-portal.fly.dev/fulfillment/SHP-* (every shipment, e.g. /fulfillment/SHP-0088)
- Expected: the shipment detail screen renders. Proof: the data is present and valid — `/api/fulfillment/SHP-0088` returns valid JSON.
- Actual: every `/fulfillment/SHP-*` URL returns **HTTP 500** with `Cannot read properties of undefined (reading 'carrier')`. The fulfillment **list** works; the **detail render** crashes. Affects all 28 shipments.
- Layer at fault: render (the detail-view component dereferences `.carrier` on an object that is undefined for the rendered shape, despite the API returning the data).
- Impact: no one can open any shipment detail. Every per-shipment workflow — checking status, tracking number, delivery date — is blocked. This is a full-module outage on the detail surface and a regression introduced in v7a91d03 (the screen worked in v4f82c1a).
- Repro: navigate to any `/fulfillment/SHP-*` URL → observe the 500; then hit `/api/fulfillment/<same id>` → valid JSON returns, confirming the failure is in the render layer, not the data.
- Verification: independent checker confirmed the 500 reproduces on multiple shipment IDs and that the matching API endpoint returns valid JSON — isolating the defect to the render path, not the API or DB. CONFIRMED.
- Fix: guard the `.carrier` access in the fulfillment detail component (the carrier object is on a nested/renamed field in the payload, or null for some shape) — the data exists in the API response, so this is a render-layer null/shape mismatch, not missing data.

### FUL-01 · Fulfillment · HIGH · Shipment SHP-0092 still marked "delivered" while the carrier says "Out for delivery" — webhook writes `delivered` on every event
- URL: https://acme-portal.fly.dev/fulfillment/SHP-0092
- Expected: shipment status should mirror the carrier's latest event. Proof: carrier tracking page checked 2026-06-01 09:00 ET = "Out for delivery" (not delivered).
- Actual (UI + DB agree, both wrong vs source): UI shows `status='delivered'`; DB `shipments` row `status='delivered'`, `delivered_at='2026-05-23'`. Both disagree with the carrier source of truth.
- Layer at fault: ingestion — the webhook handler still writes `status='delivered'` on any carrier event regardless of event type. 6 new carrier events arrived since 2026-05-25 and all 6 were written as `delivered`.
- Impact: a shipment that is still in transit is reported delivered, with a `delivered_at` that predates the actual delivery. Acme (and their customer) believe an order arrived that hasn't — wrong fulfillment status drives wrong customer comms and masks late/lost shipments. Same defect as the prior run; the v7a91d03 build did not touch it.
- Repro: open SHP-0092, compare to the carrier tracking page; inspect the webhook log — 6 events since 05-25, all written `delivered`.
- Verification: re-checked against fresh evidence in this run — carrier state re-pulled (out for delivery), DB row re-read (still delivered), webhook log re-read (event-type-agnostic writes persist). CONFIRMED, carried over from prior run unfixed.
- Fix: branch the webhook handler on carrier event type (only a `delivered`/equivalent terminal event should set `status='delivered'` and stamp `delivered_at`); backfill SHP-0092 and any shipment mis-stamped during the 05-25 → 06-01 window.

## 6. REFUTED / INCONCLUSIVE (did not survive checking)

- **Customer credit balance shows negative "−$2,300.00" (CUST-014).** Raised as a possible math defect. **Refuted:** `credit_limit = 10,000.00`, `SUM(open order totals) = 12,300.00`, and `10,000 − 12,300 = −2,300.00` — the arithmetic is correct and the customer is genuinely over their credit limit. The number is *right*. Whether a bare negative reads clearly to an Acme user (vs. an explicit "over limit by $2,300") is a **UX/presentation** question, not a functionality defect — **routed to the UX lane, not reported here** per the one-lane rule.
- **Payments "Total received this month" = $0.00 (June).** Raised as a possible aggregate bug. **Refuted:** DB `SUM(amount) FROM payments WHERE received_at >= '2026-06-01'` returns 0 rows — no June payments exist yet (run date is June 1). $0.00 is the correct aggregate over an empty set. No defect.

## 7. METHOD & ACCESS (for reproducibility)

- **Source of capture:** this report is a write-up of the overnight agent walk recorded in `acme-portal-new-build-observations.md` (build v7a91d03). No live system or URL was accessed during report authoring — the observations file is treated as the complete capture.
- **Data access (per the capture):** DB read-only via `flyctl ssh` + node pg pool in READ ONLY transactions; API via curl with a replayed login cookie; carrier state via the carrier's public tracking page.
- **Re-verification discipline:** all 5 prior findings were re-checked against fresh evidence before any new-finding sweep (re-verification-first rule). Every prior finding appears in §4; none silently dropped.
- **Coverage:** every in-scope item lands in §3 as Covered / Blocked. The one Blocked item (prior FUL-02) carries its reason and is downstream of FUL-03.
- **Adversarial checking:** two candidate findings (negative credit, $0 payments) were refuted before reporting; both legit explanations are recorded in §6 so the confirmed list stays trustworthy. One UX-flavored observation was routed out of lane rather than reported.
- **Dataset snapshot at run:** 12 open orders, 28 shipments, CUST-014 over limit by $2,300, 0 June payments.

*End of findings. Read-only audit; no live data was mutated.*
