# GOAL — Durable Robotics Billing App: Pre-Delivery Functionality Audit

**Client:** Durable Robotics
**App:** durable-billing (Fly app `durable-billing`, region `ord`)
**Live URL:** https://durable-billing.fly.dev
**Repo (local checkout):** `~/clients/durable-billing` (may be slightly behind prod)
**Lane:** Functionality (does the math add up, do the workflows behave correctly)
**Handoff deadline:** Thursday (recon completed 2026-06-01)
**Audience for deliverable:** Durable Robotics ops/handoff team (Jamie is the named stakeholder)

This GOAL file is self-contained. An agent should be able to execute it end-to-end without asking the human any further questions. Everything needed is in this file plus the linked recon notes (`fixtures/durable-billing-app-notes.md`). The probing/recon round is already done — treat the notes as the complete recon. Do **not** re-probe or re-discover; verify and report.

---

## 0. PRIME DIRECTIVE — READ ONLY, DO NO HARM

**This is a SHARED LIVE production app. The Durable ops team (4 active users) is entering real invoices daily, and real money is flowing — $84,312.50 in payments were applied last week.**

The single most important rule of this audit:

> **Never mutate state. Never create, edit, delete, or transition any record. Never trigger any action that could write to the database, send anything to a customer, or change anything an ops user would see.**

Concrete read-only constraints derived from recon:

- **DO NOT** create/edit/delete/transition invoices, payments, customers, balances, or statements.
- **DO NOT** click buttons whose behavior is unknown until you have confirmed (by reading the route handler in the repo) that they are pure reads. In particular, the **Statement export button was NOT clicked during recon** because it is unknown whether it generates server-side state — do not click it on the live app. Verify its behavior by reading the server route in the local repo first; only then decide if a read-only confirmation is even possible.
- **DO NOT** use the app's own DB helper `server/utils/db.ts` for queries. **It runs pending migrations on first import** — importing it against the live DB could mutate the schema/data. This is a hard hazard.
- **DO NOT** POST/PUT/PATCH/DELETE to any `/api/*` route. The only allowed mutating call is the documented login POST to `/api/auth/login` to obtain a session (read access), and even that should be used sparingly.

If a check cannot be performed without risking a write, mark it **BLOCKED (would require mutation)** and report it rather than performing it.

---

## 1. OPERATING MODE — AUTONOMOUS

Run this audit start-to-finish without pausing for human input. You have everything you need.

- Do not ask clarifying questions. Make a documented assumption and proceed; record assumptions in the deliverable.
- Do not wait for approval between phases.
- When a fact is uncertain, resolve it by going to ground truth (DB → API → repo → UI, see §3) rather than asking.
- If you genuinely cannot resolve something (blocked by the read-only directive, missing access, unreleased feature), record it as **BLOCKED / INCONCLUSIVE** with the reason and move on. A blocked item is a reportable result, not a reason to stop.

### Access (from recon — already verified to work)

- **Login:** matt@zergai.com, password in `~/.config/zerg/secrets/durable.env`. Role: **super admin**.
- **Session:** cookie `db_session`, httpOnly (not readable from JS). To call APIs programmatically, replay the login POST to `/api/auth/login` with email/password — the response sets `db_session`. Reuse that cookie for read-only `GET`s.
- **API surface:** `GET /api/billing/{invoices,payments,customers,balances,aging}` — JSON responses; the UI renders straight from these.
- **DB connection string:** `flyctl ssh console -a durable-billing -C "printenv DATABASE_URL"`. No `psql` in the container, but `node` + the app's `pg` driver are available. **Query through `pg` directly with read-only SQL (SELECT only) — never via `server/utils/db.ts`** (migration hazard, see §0).
- **Repo:** `~/clients/durable-billing` — read source to understand intended logic (tax math, aging bucket boundaries, status workflow, statement export behavior). Treat as possibly slightly behind prod; cross-check against live API/DB when it matters.

---

## 2. SCOPE — LANE BOUNDARIES

### IN SCOPE (functionality lane — this audit)

Does the math add up, and do the workflows behave correctly across these three modules plus the edge screens:

1. **Invoices** — list + detail, line items, tax handling, status workflow (draft → sent → paid → overdue).
2. **Payments** — payment records, application against invoices, partial payments.
3. **Customer balances** — per-customer outstanding balance, aging buckets (0-30 / 31-60 / 61-90 / 90+), statement export.

Plus edge screens surfaced in recon:
- **Aging report screen** (suspected bucket-math bug — see §4 priority).
- **Statement export** (behavior unconfirmed — read-only verification only).
- **Credit Notes screen** (currently 404s — likely unreleased; confirm and report status).

### OUT OF SCOPE (do NOT report on these)

- **UX / visual / design feedback.** Matt is covering UX/design feedback in a separate lane. Do not raise styling, layout, copy, color, spacing, or "feels off" observations. If you notice a design issue, drop it or note "routed to UX lane" — do not write it up as a finding here.
- Performance/load, security pentesting, infra/devops, and accessibility are out of scope unless a defect directly produces an **incorrect financial result** (then it's a functionality finding).

---

## 3. GROUND-TRUTH RULES — LAYERED VERIFICATION

The UI "renders straight from" the API, so a correct-looking screen is not proof. For every claim about behavior or a number, establish ground truth at the lowest layer that settles the question, then trace upward:

**Layer order (lowest = most authoritative):**

1. **DB layer** — read-only `SELECT` against the live Postgres via `pg` (the source of record for amounts, dates, statuses, balances).
2. **API layer** — the `GET /api/billing/*` JSON the UI consumes (does the API faithfully represent the DB?).
3. **Repo/logic layer** — the Nuxt/Nitro server route source in `~/clients/durable-billing` (what is the *intended* computation — tax, aging buckets, status transitions, statement generation?).
4. **UI layer** — what the rendered screen shows the ops user.

**Rules:**

- A finding is only **CONFIRMED** when it is reproduced at the data/logic layer, not merely observed in the UI. State *which layer(s)* the proof comes from.
- When the UI and a lower layer disagree, the discrepancy itself is the finding; pinpoint where (DB↔API, API↔UI, or logic↔data) it diverges.
- Distinguish three outcomes per check: **CONFIRMED bug** (proven at a layer), **REFUTED / not-a-bug** (intended behavior, proven), **BLOCKED / INCONCLUSIVE** (could not verify without mutation or access — give the reason).
- Every confirmed finding must carry: proof (the query/route/response that demonstrates it), repro steps, the layer(s) the divergence lives at, and a severity.

---

## 4. PRIORITY — JAMIE'S MONTH-END-CLOSE QUESTION

Jamie (Durable side) asked specifically:

> **"Can we trust the balances screen for month-end close?"**

This is the headline question the deliverable must answer directly and defensibly. The customer-balances and aging modules are therefore the **top priority**. The known lead:

- **Aging bucket math is suspect.** Apex Manufacturing showed **$12,400 in the 31-60 bucket**, but their oldest unpaid invoice is dated **2026-05-18 — only 14 days ago** (as of 2026-06-01), which should fall in **0-30**. Run this down to ground truth:
  - Read the bucketing logic in the repo (what date is it bucketing on — invoice date, due date, something else? what are the boundary conditions / off-by-one risks?).
  - `SELECT` Apex's invoices, payments, and computed balance from the DB and recompute the buckets by hand.
  - Compare hand-computed buckets ↔ API `aging` response ↔ UI. Locate exactly where the $12,400 lands wrong.
  - Generalize: is this an Apex-specific data artifact or a systemic bucketing bug? Check at least a few other customers.
- The deliverable must give Jamie a clear, evidence-backed verdict on whether the balances screen is trustworthy for month-end close, with the specific defects (if any) blocking that trust.

---

## 5. COVERAGE CHECKLIST — leave no silent gaps

Every item below must end with an explicit status (CONFIRMED bug / REFUTED / BLOCKED / VERIFIED-OK). The coverage matrix in the deliverable must list all of them — no item silently dropped.

**Invoices**
- [ ] List view reflects DB (count, statuses) — current state: 47 invoices.
- [ ] Detail view: line items sum correctly to subtotal.
- [ ] Tax handling: tax computed correctly per intended logic (verify against repo math, not just the displayed number).
- [ ] Status workflow integrity: draft → sent → paid → overdue. Are statuses correct given dates/payments (e.g., is "overdue" derived correctly from due date; is "paid" consistent with applied payments)? **Verify by reading state, not by transitioning anything.**

**Payments** (real money — extra care, read-only)
- [ ] Payment records reconcile to DB — current state: 31 payments; ~$84,312.50 applied last week.
- [ ] Application against invoices: each payment maps to the right invoice(s); applied totals don't exceed invoice totals.
- [ ] Partial payments: remaining balance after a partial payment is computed correctly.

**Customer balances + aging (PRIORITY — see §4)**
- [ ] Per-customer outstanding balance = invoices − applied payments, recomputed from DB. Current state: 12 customers.
- [ ] Aging buckets (0-30 / 31-60 / 61-90 / 90+) computed correctly; run the Apex Manufacturing case to ground (§4).
- [ ] Bucketing date basis and boundary conditions match intent (no off-by-one at bucket edges).
- [ ] **Statement export** — confirm behavior **by reading the route source first** (does it generate/persist server-side state?). If pure read, optionally verify output correctness against DB; if it writes state, mark **BLOCKED (read-only directive)** and report what the code does instead of clicking it.

**Edge screens**
- [ ] **Credit Notes screen** — nav link 404s; confirm it's unreleased (check repo for a stubbed/missing route) and report status. Flag whether it should be hidden from nav before handoff.
- [ ] Any other nav entry that errors or dead-ends — note and status it.

**Cross-module consistency**
- [ ] Invoice statuses ↔ payments ↔ balances tell one consistent story (e.g., a "paid" invoice contributes $0 to the customer's outstanding balance; an unpaid invoice's amount shows in the right aging bucket).

---

## 6. METHOD — PHASED, ENDING IN ADVERSARIAL VERIFICATION

**Phase A — Orient (no live writes).**
Read the recon notes and the relevant repo source (billing routes, tax logic, aging bucketing, status derivation, statement export, credit-notes route). Build the expected/intended model of each computation before touching live data. Establish read-only access (login replay for cookie; `DATABASE_URL` for `pg` SELECTs).

**Phase B — Pull ground truth (read-only).**
Snapshot the relevant DB state with SELECTs (invoices, payments, customers, balances, aging inputs) and the corresponding `GET /api/billing/*` responses. Keep raw evidence for the report.

**Phase C — Reconcile layer-by-layer.**
For each coverage item, recompute the expected result from DB + repo logic, then compare against API and UI. Record CONFIRMED / REFUTED / BLOCKED / VERIFIED-OK with proof and layer. Resolve the Apex aging case (§4) fully.

**Phase D — Adversarial verification (mandatory final phase).**
Before writing the deliverable, try to break your own conclusions:
- For each **CONFIRMED bug**: attempt to disprove it. Is there a benign explanation (data entry by ops, intended business rule, timezone/date-rounding, a definition of "aging" that's actually correct)? Only keep it confirmed if it survives.
- For each **VERIFIED-OK / REFUTED**: attempt to find a counterexample (another customer, another invoice, a boundary date) that breaks it. A single happy-path pass is not sufficient.
- For each **BLOCKED**: confirm it's truly blocked by the read-only directive/access (not laziness) and state precisely what would be needed to verify.
- Re-test bucket boundaries with edge dates (exactly 30/31/60/61/90 days) by reasoning over DB dates — never by mutating records.
- Sanity-check totals roll up: sum of per-customer balances vs. sum of (invoices − payments); aging buckets per customer sum to that customer's outstanding balance.

Only findings that survive Phase D go in the report as confirmed.

---

## 7. DELIVERABLE SPEC

Produce a single markdown **FINDINGS report** for the Durable handoff team containing:

1. **Header** — app, lane (functionality), date, build/recon basis, read-only confirmation ("no state was mutated"), and the live data snapshot used (47 invoices / 31 payments / 12 customers).
2. **Executive summary** — lead with the direct answer to Jamie's question: *Can the balances screen be trusted for month-end close?* (Yes / No / Yes-with-caveats), with the deciding evidence.
3. **Findings** — each as: ID, title, severity (Critical / High / Medium / Low), module, **status (CONFIRMED / REFUTED / BLOCKED)**, the **layer(s)** the divergence lives at, **proof** (query/route/response excerpt), and **repro steps**. Order by severity.
4. **Aging deep-dive** — the Apex Manufacturing case worked end to end (intended logic, DB facts, recomputed buckets, where it diverges), generalized to whether it's systemic.
5. **Coverage matrix** — every item in §5 with its explicit status. No silent gaps; blocked items shown as blocked with reasons.
6. **Refuted / not-a-bug** — checks that looked suspicious but proved correct (kept so the client sees they were examined).
7. **Blocked / inconclusive** — items not verifiable under the read-only directive or access limits, each with the reason and what would unblock it (notably the Statement export if it writes state, and Credit Notes if unreleased).
8. **Assumptions** — every assumption made while running autonomously.
9. **Handoff recommendation** — go / no-go for Thursday from a functionality standpoint, and any must-fix-before-handoff items.

Save the report as a markdown file in the same outputs directory. Do not write anywhere else.

---

## 8. SUCCESS CRITERIA

The audit is done well when:

- **No live state was mutated.** The read-only prime directive (§0) held throughout — including not clicking the statement export and never importing `server/utils/db.ts`.
- **Jamie's month-end-close question is answered directly** with layered evidence, and the Apex aging discrepancy is resolved to ground truth (systemic vs. one-off) rather than left as "looks off."
- **All three modules + the three edge screens are covered** with explicit statuses; the coverage matrix has **no silent gaps**.
- **Every confirmed finding is proven at the data/logic layer** (not just observed in the UI), with proof, repro, layer, and severity — and survived adversarial Phase D.
- **Lane discipline held:** zero design/UX findings in the report; only functionality (correctness of math and workflows).
- The report is **self-contained and actionable** for the Thursday handoff, with a clear go/no-go and must-fix list.
