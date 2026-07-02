---
type: goal
name: client-delivery-audit-GOAL
client: Durable Robotics
app-slug: durable-billing
lane: functionality
created: 2026-06-01
status: READY TO EXECUTE
source: instantiated from ~/.claude/skills/client-delivery-audit/references/goal-template.md (Michael Chen's ca-org audit GOAL)
---

# Client-Delivery Audit — Durable Robotics billing app — FUNCTIONALITY lane

> This is the FUNCTIONALITY lane: does the math/behavior work? Numbers, payment application,
> aging buckets, status workflow, drilldowns. The UX/design lane is OUT OF SCOPE here — Matt
> is covering UX feedback separately. A finding belongs in exactly one lane; do not report
> design nits. If a visual defect corrupts data/meaning, it IS functionality — report it.

================================================================================
GOAL FILE — DURABLE ROBOTICS (durable-billing) FUNCTIONALITY AUDIT: Invoices, Payments, Customer Balances
================================================================================

Owner:        client-delivery-audit agent (run on behalf of Matt Eisner, matteisn@gmail.com / matt@zergai.com)
Created:      2026-06-01
Status:       READY TO EXECUTE
Repo:         ~/clients/durable-billing  (local checkout — may be slightly behind prod; treat prod as authoritative)
Target app:   https://durable-billing.fly.dev   (Fly app `durable-billing`, region ord — Nuxt 3 + Nitro server routes, Fly-managed Postgres)
Prior run:    none — first run (no prior FINDINGS file exists for this app)
Handoff:      client hands off Thursday — this audit gates that handoff

--------------------------------------------------------------------------------
0. PRIME DIRECTIVE — DO NOT ALTER THE DATA   (NON-NEGOTIABLE — READ THIS FIRST)
--------------------------------------------------------------------------------
This is a SHARED, LIVE app. The Durable ops team (4 active users) is entering REAL invoices and
REAL payments into it daily — $84,312.50 in payments was applied last week. THE AUDIT IS STRICTLY
READ-ONLY / OBSERVATIONAL.

  HARD STOP — DO NOT, under any circumstances:
    - create, edit, send, mark-paid, void, approve, post, submit, import, upload, or delete ANY
      invoice, payment, customer, credit note, or statement
    - click the "Statement export" button or any export/generate/recompute control — it is UNKNOWN
      whether it generates server-side state (see DATA-STATE); treat it as a write until proven otherwise
    - run any write (UPDATE / INSERT / DELETE / DDL / truncate / seed / reset / migration) against
      the DB, or run any repo script that writes data
    - trigger any action that recomputes / regenerates / re-ingests / promotes / rebuilds state
    - change settings, roles, thresholds, or integrations
    - disturb the ops team's sessions or log anyone out (you are super admin — be especially careful)

  Verify write/action behavior WITHOUT executing it: read the code + API contract, inspect (via
  network capture) which endpoint a button would hit, and reason about whether it WOULD behave
  correctly. If a bug can only be CONFIRMED by mutating, do NOT mutate — record it as
  SUSPECTED / UNVERIFIED (clearly tagged, with the reason) and CONTINUE.

  When in doubt: observe, don't touch. One wrong click on shared live money data is far worse than
  a missed finding.

--------------------------------------------------------------------------------
0b. OPERATING MODE — FULLY AUTONOMOUS  (RUN END-TO-END, NEVER PAUSE)
--------------------------------------------------------------------------------
Execute this entire goal from start to finish WITHOUT stopping, asking, or waiting for approval.
There is NO human in the loop during the run.

  - Never pause for confirmation, clarification, or sign-off. Make the most reasonable assumption,
    write it down in the report, and keep going.
  - If a screen is blocked, a value is ambiguous, a credential is missing, or a path is unavailable:
    record it (coverage item BLOCKED + why, or finding tagged UNVERIFIED) and move to the next item
    — do NOT halt the run.
  - DONE = the FINDINGS deliverable (Section 6) is fully written with the coverage matrix complete.
    Run continuously until then.

--------------------------------------------------------------------------------
1. MISSION  (FUNCTIONALITY lane)
--------------------------------------------------------------------------------
Audit the Invoices, Payments, and Customer Balances modules of the live Durable Robotics billing app
for PURE FUNCTIONAL CORRECTNESS. Drive the real UI, click through every screen and non-mutating
interaction, and verify that numbers, math, and behaviors are correct against the underlying data
(Postgres DB + API responses + repo source). Produce a complete, evidence-backed defect report.
Then run independent CHECKING agents that try to refute every claimed finding before it is reported.

THIS IS A FUNCTIONALITY AUDIT, NOT A DESIGN REVIEW.
  - IN SCOPE:  Does the math add up? Do invoice line items + tax sum to the invoice total? Does the
               invoice status workflow (draft → sent → paid → overdue) reflect reality? Do payments
               (including PARTIAL payments) apply correctly against invoices? Do per-customer
               outstanding balances reconcile to invoices minus payments? Are the aging buckets
               (0-30 / 31-60 / 61-90 / 90+) computed from the correct dates with correct boundaries,
               and do bucket sums == the customer's total outstanding? Are filters/sorts/search/
               pagination on every list correct? Do drilldowns/links land on the right record?
  - OUT OF SCOPE: Visual design, spacing, colors, typography, copywriting, layout, responsiveness.
               (Matt is covering UX separately — do not report unless a visual defect corrupts
               data/meaning.)

CLIENT-CRITICAL QUESTION (drives severity): Jamie on the Durable side explicitly asked
"can we trust the balances screen for month-end close?" The Customer Balances module — outstanding
balances + aging buckets + statement totals — is the headline. Prioritize proving or disproving its
correctness. Money correctness on Payments (real $84K+ flowing) is the other top priority.

--------------------------------------------------------------------------------
2. ACCESS / CREDENTIALS
--------------------------------------------------------------------------------
Login:    https://durable-billing.fly.dev/login
User:     matt@zergai.com
Pass:     see ~/.config/zerg/secrets/durable.env  (NEVER echo the password into the report or logs)
Role:     super admin — can see all modules and all customers' data. With great access comes the
          read-only prime directive; do not exercise admin-only mutations.

Navigation gotchas:
  - "Credit Notes" appears in the nav but 404s — believed UNRELEASED. Do not chase it as a bug;
    record it as out-of-scope/blocked (unreleased) in the coverage matrix.
  - "Statement export" button on Customer Balances: UNKNOWN whether it writes server-side state.
    Do NOT click it. Inspect the code/endpoint it would hit and reason about behavior instead.

Browser tooling: playwright-skill OR chrome-devtools (whichever is available).
  - REQUIRED: unique session name `durable-billing-functionality-audit1`; never reuse another
    context's browser session.
  - Cleanup the session on success AND failure; never close --all (other reviewers may be live).

--------------------------------------------------------------------------------
3. SOURCES OF TRUTH  (verify the UI against these, in priority order)
--------------------------------------------------------------------------------

A. Live database (authoritative). VERIFIED ACCESS PATH (from the 2026-06-01 probing round):
   - Get the connection string:
       flyctl ssh console -a durable-billing -C "printenv DATABASE_URL"
   - There is NO psql binary in the container, BUT node + the app's `pg` driver are present.
     Run read-only queries via a one-off node script INSIDE the container (or from your own host
     if the DATABASE_URL is reachable), opening YOUR OWN pg client with the connection string.
   ⚠ DO NOT import/instantiate the app's own DB layer `server/utils/db.ts` — it RUNS PENDING
     MIGRATIONS on first import (a write). Always open your own raw `pg` connection.
   - Wrap EVERY query in:  BEGIN TRANSACTION READ ONLY; … ; ROLLBACK;   (SELECT-only, no writes ever)
   - Tables to expect (infer exact names from the schema / repo `server/`): invoices, invoice line
     items, payments, payment-to-invoice applications, customers. Confirm names before querying.

B. Live API responses (fast cross-check of what the UI *should* render):
   - Endpoint pattern (Nitro server routes): `/api/billing/{invoices,payments,customers,balances,aging}.get`
     Responses are JSON and the UI renders straight from them — so UI == API should hold unless a
     render bug intervenes; a UI≠API gap is itself a finding.
   - Auth for curl: the session cookie is `db_session` and is httpOnly (NOT readable from JS).
     To get it: replay the login POST to `/api/auth/login` with email/password (from
     ~/.config/zerg/secrets/durable.env); the response sets `db_session`. Reuse that cookie on
     subsequent GETs. Read-only GETs only.

C. Original source data / repo: local checkout at ~/clients/durable-billing — read the Nitro
   server route handlers and any aging/balance computation code to confirm WHICH layer a defect
   lives in (ingestion/compute vs API vs render). Repo may lag prod; prod DB + prod API win on
   any disagreement.

Three-layer rule: UI == API == DB == SOURCE. A break at any layer is a finding; identify WHICH
layer broke (render bug vs API bug vs compute/ingestion bug).

NO-STALL DEFAULT: pick the highest tier available and proceed — never block waiting for data access.
  1. Primary = live DB (read-only SELECTs)
  2. Fallback = UI == API internal-consistency + math self-consistency (line items vs total,
     payments vs balance, bucket sums vs total)
  3. Repo source for compute/ingestion-correctness questions (e.g. aging-bucket boundary logic)

DATA-STATE OBSERVED (2026-06-01 probing round — recalibrate before relying on it; the ops team is
adding records daily so exact counts WILL change):
  - 47 invoices, 31 payments, 12 customers.
  - Payments module has REAL money: ~$84,312.50 applied by the ops team last week → this is where
    the money-correctness findings will live. Exercise it first.
  - SUSPECTED AGING BUG (highest-priority lead): on the aging report, Apex Manufacturing showed
    $12,400 in the 31-60 bucket, but their OLDEST unpaid invoice is dated 2026-05-18 — only 14 days
    old as of 2026-06-01, which should land in the 0-30 bucket, not 31-60. Reconcile every aging
    bucket against invoice dates from the DB. Determine the bucket boundary logic (is it invoice
    date vs due date? off-by-one on the boundary? wrong "as of" date?) and which layer computes it.
  - Statement export: NOT exercised in probing (button not clicked — may write server state).
    Verify via code-read only; mark its math UNVERIFIED if it cannot be proven read-only.
  - Credit Notes screen 404s — unreleased; out of scope (coverage = Blocked: unreleased).

--------------------------------------------------------------------------------
4. SCOPE — WHAT TO COVER  (functionality)
--------------------------------------------------------------------------------
Checklist of every screen/module + interaction. For EACH screen: snapshot → read displayed numbers
→ exercise ONLY NON-MUTATING interactions → re-snapshot → record values for cross-check against
API + DB.

  Invoices
  [ ] Invoice list — counts, status badges, any list totals/KPIs reconcile to DB
  [ ] Invoice detail — line items SUM to the subtotal; tax computed correctly; subtotal + tax == total
  [ ] Tax handling — verify the tax rate/amount math per invoice (rounding, multi-line, exemptions)
  [ ] Status workflow — draft → sent → paid → overdue: does the displayed status match reality?
      (e.g. is an invoice past its due date with no/partial payment correctly "overdue"? is a fully
       paid invoice "paid"?) Read-only: infer the transition rules from code; do NOT change a status.
  [ ] List mechanics — search / filter (by status, customer, date) / sort / pagination correctness

  Payments  (TOP PRIORITY — real money)
  [ ] Payment list — count and total reconcile to DB; last-week total ≈ $84,312.50 sanity check
  [ ] Payment detail — amount, date, method, and which invoice(s) it applies to
  [ ] Application against invoices — a payment reduces the right invoice's outstanding by the right
      amount; over-application / mis-application is a Critical finding
  [ ] PARTIAL payments — a partial payment leaves the correct remaining balance on the invoice AND
      the invoice is in the correct status (not flipped to "paid" prematurely)
  [ ] One payment split across multiple invoices / multiple payments on one invoice, if present
  [ ] List mechanics — search / filter / sort / pagination

  Customer Balances  (HEADLINE — Jamie's month-end-close trust question)
  [ ] Per-customer outstanding balance == sum(that customer's invoice totals) − sum(payments applied)
  [ ] Aging buckets 0-30 / 31-60 / 61-90 / 90+ — each invoice/amount lands in the CORRECT bucket
      given the correct date basis and boundary; verify the Apex Manufacturing $12,400 lead above
  [ ] Bucket SUMS == the customer's total outstanding (no amount lost or double-counted across buckets)
  [ ] Aging totals across ALL customers reconcile to the system-wide outstanding total
  [ ] Boundary correctness: exactly which date drives aging (invoice date vs due date), and the
      "as of" date used; confirm the day-count boundary is right (e.g. day 30 vs 31)
  [ ] Statement export — DO NOT click. Read the handler in ~/clients/durable-billing; verify the
      statement's balance/aging math matches the screen by reasoning over the code; tag UNVERIFIED
      if it cannot be confirmed read-only
  [ ] List mechanics — search / filter / sort / pagination on the customers/balances list

  Cross-module reconciliation
  [ ] Sum of all customer outstanding balances == sum(all invoice totals) − sum(all payments applied)
  [ ] An invoice marked paid has applied payments == its total; an overdue one is genuinely past due & unpaid

--------------------------------------------------------------------------------
5. METHOD (phased)
--------------------------------------------------------------------------------
EXECUTION PRIORITY (so an interrupted run has already covered what matters most):
  1) money/qty correctness (Payments application + partial payments; Customer Balances + aging) →
  2) routing/status (invoice status workflow correctness) →
  3) navigation/drilldowns (links land on the right record) →
  4) list mechanics (search/filter/sort/pagination).
  Parts before dashboards: prove individual invoice/payment/balance math before any rollup.

PHASE 0 — Recon (no claims yet)
  - Establish DB + API access per Section 3. Map each in-scope screen to its API endpoint(s) and
    DB table(s). Confirm exact table/column names from the schema/repo.
  - No prior FINDINGS file exists → no re-verification step this run. (This GOAL file becomes the
    regression suite for the next build: future runs re-verify this run's findings FIRST.)

PHASE 1 — Drive & capture
  - Walk everything in Section 4. For each: record URL, action taken, observed value (number/
    screenshot), and the evidence behind it (API JSON payload + DB SELECT result). RAW observations
    only — no conclusions yet. Capture exact figures; do not round away discrepancies.

PHASE 2 — Reconcile
  - For every captured number, compute expected from DB/source and tag PASS / FAIL / UNCERTAIN with:
    screen, field, displayed value, expected value, delta, layer-at-fault (render / API / compute-
    ingestion), and exact repro steps. Aging buckets and payment application get line-by-line tables.

PHASE 3 — Adversarial verification (CHECKING agents)
  - For EACH candidate finding, spawn an independent checking agent whose job is to REFUTE it:
    re-run the DB query, re-load the screen/API, and check for innocent explanations — timezone on
    the aging "as of" date, rounding on tax, units, a filter hiding rows, due-date-vs-invoice-date
    basis, partial-payment edge cases. Confirm it reproduces.
  - Default to "NOT a real finding" unless the checker independently confirms. Only survivors ship
    as CONFIRMED. Put MULTIPLE checkers on the high-impact claims (aging math, payment application,
    balances) since those gate Jamie's month-end-close trust. Refuted claims are LISTED, not dropped.

PHASE 4 — Report (Section 6).

--------------------------------------------------------------------------------
6. DELIVERABLE
--------------------------------------------------------------------------------
Write findings to: MattZerg/Feedback/2026-06-01-durable-billing-functionality.md
(+ an evidence dir alongside it: screenshots, API payloads, DB query results)

NOTE for this test run: keep output in the audit run's outputs directory; do NOT write to the
real vault / MattZerg / Feedback paths.

Report structure (this shape is the bar):
  - SUMMARY: counts by severity + the headline in 2 sentences, explicitly answering Jamie's
    "can we trust the balances screen for month-end close?" question.
      Functionality severity: Critical = wrong money/qty or data loss; High = wrong status/routing/
        match; Medium = wrong aggregate/filter; Low = cosmetic-but-functional.
  - TOP N TO FIX FIRST: quick wins ordered by (client impact ÷ fix effort) — builder-actionable
    without reading the whole report.
  - COVERAGE MATRIX: every Section-4 item marked Covered / Blocked / Skipped (with reason).
    NO SILENT GAPS. Credit Notes = Blocked (unreleased). Statement export = Blocked-read-only
    (not clickable without mutation risk) or Covered-via-code-read, whichever applies.
  - RE-VERIFICATION OF PRIOR RUN: N/A — first run. (State this explicitly; nothing dropped silently.)
  - CONFIRMED FINDINGS, each with:
      ID | module/screen | severity | one-line title
      Expected (proof: DB query + result, or API payload, or source compute logic)
      Actual (displayed value / screenshot / payload)
      Layer at fault (render / API / compute-ingestion)
      Repro steps | Verification: how the checking agent confirmed it | Concrete fix
  - REFUTED / INCONCLUSIVE: candidate claims that did NOT survive checking (e.g. if the Apex aging
    figure turns out to have an innocent explanation), so they aren't silently dropped.
  - METHOD & ACCESS: exactly how to reproduce (DB access path, API auth replay, queries used) — for
    the next run and for the client's builder.

--------------------------------------------------------------------------------
7. SUCCESS CRITERIA
--------------------------------------------------------------------------------
  - Every Section-4 item exercised or explicitly marked Blocked with a reason (no silent truncation).
  - The Apex Manufacturing aging lead is resolved to a CONFIRMED finding or REFUTED with evidence.
  - Jamie's month-end-close trust question is answered directly in the SUMMARY, backed by the
    balances + aging reconciliation.
  - Every reported finding is reproducible, evidence-backed, names its layer/cause, and survived
    adversarial checking.
  - No out-of-lane (UX/design) findings in the report.
  - A "Top N quick wins" list the client's builder can act on before Thursday's handoff.

--------------------------------------------------------------------------------
8. CONSTRAINTS & GUARDRAILS
--------------------------------------------------------------------------------
  - READ-ONLY IS THE LAW (Section 0). This is shared live money data with 4 active users.
  - DB access is SELECT-ONLY, in READ ONLY transactions, via your OWN raw pg connection. NEVER
    import the app's `server/utils/db.ts` (it runs migrations on import).
  - Do NOT click "Statement export" or any export/recompute control — verify by code-read instead.
  - Known-immature / unreleased areas: Credit Notes (404s) — out of scope, record as Blocked.
  - Browser session isolation: name it `durable-billing-functionality-audit1`; clean up on success
    AND failure; never close --all.
  - Never mutate to confirm a finding — tag SUSPECTED/UNVERIFIED and move on.
  - Output stays local. Never auto-post to any Durable channel — Matt sends it himself.
================================================================================
END OF GOAL FILE
================================================================================
