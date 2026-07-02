---
type: template
name: client-delivery-audit-GOAL
created: 2026-06-01
source: Michael Chen's ca-org AP/SupplyChain audit GOAL file (see source-artifacts/michael-audit-GOAL-2026-05-31.txt)
lanes: [functionality, ux]
used_by: ~/.claude/skills/client-delivery-audit/
---

# Client-Delivery Audit — GOAL Template

Generalized from Michael's ca-org audit GOAL (the one Idan flagged as the bar). Fill the `{{placeholders}}`,
delete the lane you're not running, and hand the result to an agent (`/workflow`, `client-delivery-audit` skill,
or Codex `/goal`). One self-contained mission an agent can execute end-to-end without further clarification.

> **The two lanes are complementary, never overlapping:**
> - **FUNCTIONALITY lane** (Michael's): does the math/behavior work? Numbers, matching, routing, drilldowns.
> - **UX lane** (Matt's): can a human use it? Comprehension, task flow, hierarchy, evidence-backed design findings.
> A finding belongs in exactly one lane. Functionality findings never include design nits; UX findings never
> re-litigate math. If a visual defect corrupts data/meaning, it's functionality.

================================================================================
GOAL FILE — {{CLIENT}} ({{app-slug}}) {{LANE}} AUDIT: {{MODULES IN SCOPE}}
================================================================================

Owner:        {{auditor name + email}}
Created:      {{YYYY-MM-DD}}
Status:       READY TO EXECUTE
Repo:         {{local repo path, if available}}
Target app:   {{live URL}}   ({{hosting: Fly/AWS/etc, region}})
Prior run:    {{path to previous FINDINGS file, or "none — first run"}}

--------------------------------------------------------------------------------
0. PRIME DIRECTIVE — DO NOT ALTER THE DATA   (NON-NEGOTIABLE — READ THIS FIRST)
--------------------------------------------------------------------------------
This is a SHARED, LIVE app that the team and possibly the client are actively
reviewing against real data. THE AUDIT IS STRICTLY READ-ONLY / OBSERVATIONAL.

  HARD STOP — DO NOT, under any circumstances:
    - create, edit, approve, reject, post, submit, import, upload, or delete ANY record
    - run any write (UPDATE / INSERT / DELETE / DDL / truncate / seed / reset) against the DB,
      or run any repo script that writes data
    - trigger any action that recomputes / regenerates / re-ingests / promotes / rebuilds state
    - change settings, roles, thresholds, or integrations
    - disturb other reviewers' sessions or log anyone out

  Verify write/action behavior WITHOUT executing it: read the code + API contract, inspect
  (via network capture) which endpoint a button would hit, and reason about whether it WOULD
  behave correctly. If a bug can only be CONFIRMED by mutating, do NOT mutate — record it as
  SUSPECTED / UNVERIFIED (clearly tagged, with the reason) and CONTINUE.

  When in doubt: observe, don't touch. One wrong click on shared live data is far worse than
  a missed finding.

  {{If this is a disposable/local environment where mutation is safe, replace this section with:
  "MUTATION ALLOWED — this is a disposable environment ({{details}}). Exercise create/edit/approve
  flows end-to-end, but reset state after each test via {{reset command}}."}}

--------------------------------------------------------------------------------
0b. OPERATING MODE — FULLY AUTONOMOUS  (RUN END-TO-END, NEVER PAUSE)
--------------------------------------------------------------------------------
Execute this entire goal from start to finish WITHOUT stopping, asking, or waiting for approval.
There is NO human in the loop during the run.

  - Never pause for confirmation, clarification, or sign-off. Make the most reasonable
    assumption, write it down in the report, and keep going.
  - If a screen is blocked, a value is ambiguous, a credential is missing, or a path is
    unavailable: record it (coverage item BLOCKED + why, or finding tagged UNVERIFIED) and
    move to the next item — do NOT halt the run.
  - DONE = the FINDINGS deliverable (Section 6) is fully written with the coverage matrix
    complete. Run continuously until then.

--------------------------------------------------------------------------------
1. MISSION
--------------------------------------------------------------------------------

### LANE A — FUNCTIONALITY  (delete if running UX lane)

Audit {{modules}} of the live {{client}} app for PURE FUNCTIONAL CORRECTNESS. Drive the real UI,
click through every screen and interaction, and verify that numbers, math, and behaviors are
correct against the underlying data (database + source files + API). Produce a complete,
evidence-backed defect report. Then run independent CHECKING agents that try to refute every
claimed finding before it is reported.

THIS IS A FUNCTIONALITY AUDIT, NOT A DESIGN REVIEW.
  - IN SCOPE:  Does the math add up? Does clicking X do what it should? Do totals, aggregates,
               buckets, match results, rollups, and statuses agree with source data? Do
               links/drilldowns land on the right record? Are filters/sorts/search/pagination
               correct?
  - OUT OF SCOPE: Visual design, spacing, colors, typography, copywriting, layout, responsiveness.
               ({{UX reviewer name}}'s lane — do not report unless a visual defect corrupts
               data/meaning.)

### LANE B — UX / DESIGN  (delete if running functionality lane)

Audit {{modules}} of the live {{client}} app for USABILITY AND COMPREHENSION, with the same
evidence discipline as a functionality audit. Walk every screen as each persona ({{personas,
e.g. "AP clerk", "approver", "exec reviewer"}}), attempt the real tasks they would perform, and
report where the interface blocks, misleads, or slows them. Every finding must be evidence-backed
(screenshot + heuristic/principle citation), severity-ranked by user impact, and survive an
adversarial "is this actually a problem or reviewer taste?" check.

THIS IS A UX AUDIT, NOT A FUNCTIONALITY AUDIT.
  - IN SCOPE:  Task completion paths (can the persona do the job?), information hierarchy &
               comprehension (do they understand what they're looking at?), navigation/wayfinding,
               state communication (loading/empty/error states), trust signals (does displayed
               data look credible?), accessibility blockers, copy clarity.
  - OUT OF SCOPE: Whether the numbers are mathematically correct against the DB ({{functionality
               reviewer name}}'s lane). Exception: if a UX choice makes CORRECT data LOOK wrong
               (e.g. ambiguous label causes misreading), that's UX — report it.

--------------------------------------------------------------------------------
2. ACCESS / CREDENTIALS
--------------------------------------------------------------------------------
Login:    {{login URL}}
User:     {{email}}
Pass:     {{password or path to credential, e.g. "see ~/.config/zerg/secrets/{{client}}.env"}}
Role:     {{role + what it can access}}

Navigation gotchas: {{e.g. "product switcher is the logo top-left", "ignore the legacy HR section"}}

Browser tooling: {{agent-browser / playwright-skill / chrome-devtools}}
  - REQUIRED: unique session name {{client}}-{{lane}}-audit{{N}}; never reuse another context's session.
  - Cleanup on success AND failure; never close --all.

--------------------------------------------------------------------------------
3. SOURCES OF TRUTH  (verify the UI against these, in priority order)
--------------------------------------------------------------------------------

### Functionality lane

A. Live database (authoritative). VERIFIED ACCESS PATH (from probing round — update each engagement):
   {{exact commands that work, e.g. the Fly MPG in-container node+pg pattern. Include what does
   NOT work so the agent doesn't burn time: "flyctl postgres connect does NOT work because..."}}
   ⚠ NEVER import/instantiate the app's own DB layer (it may run migrations/bootstrap writes).
   Always open your own read-only connection; wrap EVERY query in BEGIN TRANSACTION READ ONLY … ROLLBACK.

B. Live API responses (fast cross-check of what the UI *should* render):
   {{endpoint list / pattern, e.g. /api/{{module}}/...}}
   Auth for curl: {{how to get the session cookie — note httpOnly quirks}}

C. Original source data: {{where the ingested source files live; note if unreachable}}

Three-layer rule: UI == API == DB == SOURCE. A break at any layer is a finding; identify WHICH
layer broke (render bug vs API bug vs ingestion/math bug).

NO-STALL DEFAULT: pick the highest tier available and proceed — never block waiting for data access.
  1. Primary = live DB (read-only SELECTs)
  2. Fallback = UI == API internal-consistency + math self-consistency
  3. Source files if reachable, for ingestion-correctness questions

DATA-STATE OBSERVED ({{date of probing round}} — recalibrate, may change):
{{which modules have real data vs empty; where the money findings will live; what math cannot be
exercised on live data — say so explicitly in the coverage matrix rather than implying it was checked}}

### UX lane

A. The personas + their tasks (Section 4B) — ground truth for "does this work for a human".
B. Heuristic corpus: {{e.g. fakematt-feedback principles corpus, NN/g heuristics, WCAG 2.2 AA}} —
   every finding cites the principle it violates (provenance IDs, e.g. p-0002).
C. The client's own stated goals for the delivery: {{quote them, e.g. "exec demo on {{date}}",
   "AP clerk daily driver"}}. Severity is judged against THESE, not generic taste.
D. Prior UX findings file ({{path}}) — for re-verification.

--------------------------------------------------------------------------------
4. SCOPE — WHAT TO COVER
--------------------------------------------------------------------------------

### 4A. Functionality lane — screens & interactions
{{Checklist of every screen/module, e.g.:
  [ ] Index/dashboard — KPI tiles, totals, queue counts reconcile to DB
  [ ] {{Entity}} list + detail — line items sum to totals; statuses; links
  [ ] {{Matching/computation feature}} — quantities and amounts reconcile; tolerances; exceptions
  [ ] Reports — bucket boundaries; bucket sums == totals
  [ ] Search / filter / sort / pagination correctness on every list
}}

For each screen: snapshot → read displayed numbers → exercise ONLY NON-MUTATING interactions →
re-snapshot → record values for cross-check.

### 4B. UX lane — personas × tasks
{{For each persona, the tasks they must complete, e.g.:
  Persona: AP clerk
  [ ] Find all invoices needing attention today (how many clicks/seconds? any dead ends?)
  [ ] Understand WHY an invoice is blocked (is the reason visible and comprehensible?)
  [ ] Trace an invoice back to its PO and receipt (drilldown path obvious?)
  Persona: Approver
  [ ] Understand what they're approving and why it routed to them
  [ ] Distinguish a real duplicate from a false positive using only what's on screen
  Persona: Exec reviewer (client stakeholder seeing this for the first time)
  [ ] Land on the dashboard and correctly state what the numbers mean within 60 seconds
  [ ] Trust check: does anything LOOK broken/placeholder/lorem-ipsum even if it works?
}}

For each persona×task: walk it, screenshot each step, note friction (extra clicks, ambiguity,
misleading labels, missing states), record time-to-complete and dead-ends.

Plus per-screen sweep:
  [ ] Empty states (do they explain, or just show nothing?)
  [ ] Loading states (spinners vs layout shift vs blank)
  [ ] Error states (can they be triggered read-only? if not, inspect code → SUSPECTED)
  [ ] Responsive behavior at {{breakpoints}}
  [ ] Keyboard navigation + screen-reader labels on core flows (WCAG AA blockers only)

--------------------------------------------------------------------------------
5. METHOD (phased — both lanes)
--------------------------------------------------------------------------------
EXECUTION PRIORITY (so an interrupted run has already covered what matters most):

  Functionality: 1) money/qty correctness → 2) routing/status → 3) navigation/drilldowns →
                 4) list mechanics. Parts before dashboards/rollups.
  UX:            1) task-blocking findings (persona cannot complete the job) → 2) comprehension/
                 trust (misleads or looks broken) → 3) friction (slows but doesn't block) →
                 4) polish. Client-demo-critical screens before admin screens.

PHASE 0 — Recon (no claims yet)
  - Establish access per Section 3; map each UI screen to its API endpoint(s) and table(s)
    (functionality) or to its persona×tasks (UX).
  - RE-VERIFICATION FIRST if a prior FINDINGS file exists: re-check every prior finding against
    the current build, mark Fixed / Still-broken with evidence, before hunting new findings.

PHASE 1 — Drive & capture
  - Walk everything in Section 4. Capture: URL, what was done, what was observed (numbers/
    screenshots), and the evidence behind it (API payload + DB value / heuristic citation).
  - Log RAW OBSERVATIONS with exact figures/screenshots — no conclusions yet.

PHASE 2 — Reconcile
  - Functionality: compute expected from DB/source for every captured number; tag PASS/FAIL/
    UNCERTAIN with screen, field, displayed, expected, delta, layer-at-fault, repro steps.
  - UX: convert observations into findings; tag each with persona, task, severity (by user
    impact), principle citation, and repro steps.

PHASE 3 — Adversarial verification (CHECKING agents)
  - For EACH candidate finding, spawn an independent checking agent whose job is to REFUTE it:
    - Functionality: re-run the query, re-load the screen, check for filter/timezone/rounding/
      units explanations, confirm it reproduces.
    - UX: argue the design is intentional/acceptable — is this a real user problem or reviewer
      taste? Does a heuristic actually back it? Would the persona genuinely be blocked/misled?
  - Default to "not a real finding" unless the checker independently confirms. Only findings
    that survive refutation are reported as CONFIRMED. Multiple checkers on high-impact claims.

PHASE 4 — Report (Section 6).

--------------------------------------------------------------------------------
6. DELIVERABLE
--------------------------------------------------------------------------------
Write findings to: {{output path, default:
  MattZerg/Feedback/YYYY-MM-DD-{{app-slug}}-{{lane}}.md}}
(+ evidence dir: screenshots, payloads, queries)

Report structure (BOTH lanes — this shape is the bar):
  - SUMMARY: counts by severity + the headline in 2 sentences.
      Functionality severity: Critical = wrong money/qty or data loss; High = wrong status/
        routing/match; Medium = wrong aggregate/filter; Low = cosmetic-but-functional.
      UX severity: Critical = persona cannot complete a core task / data misread guaranteed;
        High = task completable only with outside help or misleads on first read; Medium =
        significant friction or trust damage; Low = polish.
  - TOP N TO FIX FIRST: quick wins, ordered by (client impact ÷ fix effort).
  - COVERAGE MATRIX: every Section-4 item marked Covered / Blocked / Skipped (with reason).
    NO SILENT GAPS.
  - RE-VERIFICATION OF PRIOR RUN (if applicable): every prior finding → Fixed / Still broken,
    each with evidence. Listed so nothing is silently dropped.
  - CONFIRMED FINDINGS, each with:
      ID | module/screen | severity | one-line title
      Expected (with proof: DB query / source value / principle citation)
      Actual (displayed value / screenshot / payload)
      Layer at fault (functionality: render/API/ingestion · UX: IA/copy/state/interaction)
      Repro steps | Verification: how the checking agent confirmed it | Concrete fix
  - REFUTED / INCONCLUSIVE: claims that did NOT survive checking, so they aren't silently dropped.
  - METHOD & ACCESS: exactly how to reproduce (for the next run and for the client).

--------------------------------------------------------------------------------
7. SUCCESS CRITERIA
--------------------------------------------------------------------------------
  - Every Section-4 item exercised or explicitly marked blocked with a reason (no silent truncation).
  - Every reported finding is reproducible, evidence-backed, names its layer/cause, and survived
    adversarial checking.
  - No out-of-lane findings in the report (route them to the right reviewer instead).
  - Prior findings re-verified, not assumed.
  - A "top N quick wins" list the builder can act on without reading the whole report.

--------------------------------------------------------------------------------
8. CONSTRAINTS & GUARDRAILS
--------------------------------------------------------------------------------
  - READ-ONLY IS THE LAW (Section 0) unless explicitly replaced with the disposable-env variant.
  - DB access is SELECT-ONLY, in READ ONLY transactions, via your own connection.
  - Known-immature areas ({{list them}}): still record findings but tag accordingly, not as hard bugs.
  - Browser session isolation rules exactly; clean up on success AND failure.
  - Never mutate to confirm a finding — SUSPECTED/UNVERIFIED and move on.
  - Output stays local. Never auto-post to client channels — Matt sends it himself.
================================================================================
END OF GOAL TEMPLATE
================================================================================
