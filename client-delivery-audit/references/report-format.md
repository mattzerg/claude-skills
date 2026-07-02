# FINDINGS Report Format

The exact structure every client-delivery-audit report follows. Modeled on Michael Chen's
ca-org FINDINGS PDFs (v1 2026-05-31, v2 2026-06-01) — the shape Idan called the bar.

Output path: `MattZerg/Feedback/YYYY-MM-DD-<app-slug>-<lane>.md`
Frontmatter: follow the existing `MattZerg/Feedback/` convention:

```yaml
---
type: feedback
lane: functionality | ux
target: <live URL>
target_kind: live_url
client: <client name>
reviewed_at: <ISO timestamp>
build: <build id/hash if visible>
prior_run: <path to prior FINDINGS file or null>
total_findings: N
critical: N
high: N
medium: N
low: N
---
```

## Report sections (in this order)

### 1. Title + header block
`# <Client> (<app-slug>) — <Modules> <Lane> Audit — FINDINGS`

Bullets: Owner · Run date · Target (URL + build) · Scope (one sentence, explicitly what this is NOT) ·
Mode (read-only/observational) · Evidence dir.

If there's headline context (e.g. "this build fixed almost everything from the prior run"), put it
in a callout box right under the header — the reader should get the story in 10 seconds.

### 2. SUMMARY
Severity table: | Severity (definition) | Count | IDs/titles |

Then bullets: screens covered · interactions exercised · layer reconciliation statement ·
adversarial verification statement (how many checkers, what survived/was refuted).

### 3. TOP N TO FIX FIRST
Numbered list, ordered by (client impact ÷ fix effort). Each item: ID + one-line description +
the number that makes it concrete. This is the section the builder acts on without reading further.

### 4. COVERAGE MATRIX (no silent gaps)
One table per module: | Section-4 item | Status (✅ Covered / 🚫 Blocked / ⏭ Skipped) | Notes |

Every Blocked/Skipped row carries the reason. If a whole category of math could not be exercised
(e.g. empty data), say so in a callout — never imply it was checked.

### 5. RE-VERIFICATION OF PRIOR RUN (when a prior FINDINGS file exists)
| # | Prior defect | Status now (✅ Fixed / ❌ Still broken) | Evidence |

Every prior finding appears here. "Listed so they are not silently dropped."

### 6. CONFIRMED FINDINGS
Each finding, in severity order:

```
### <ID> · <Module/Screen> · <SEVERITY> · <one-line title>
- URL: <exact URL>
- Expected: <value/behavior> (proof: <DB query / API payload / principle citation + persona task>)
- Actual: <displayed value / observed behavior> (<screenshot ref / payload ref>)
- Layer at fault: <render / API / ingestion-math>  (UX lane: <IA / copy / state / interaction>)
- Impact: <what goes wrong for the client, in their terms — money, blocked task, misread data>
- Repro: <steps>
- Verification: <how the independent checker confirmed it> — CONFIRMED
- Fix: <concrete, codebase-aware if repo access exists>
```

ID conventions: `<MODULE>-<TYPE><N>` e.g. AP-D1 (duplicates), AP-L1 (line items), AP-M1 (matching),
SC-IMP (supply-chain import). UX lane: `UX-<persona initial><N>` e.g. UX-C1 (clerk), UX-E2 (exec).

### 7. REFUTED / INCONCLUSIVE (did not survive checking)
Each claim that was raised and killed: what was claimed, why it was refuted (the legit explanation),
or why it's inconclusive (e.g. "not provable read-only — left UNVERIFIED per Prime Directive").
This section is what makes the CONFIRMED list trustworthy.

### 8. METHOD & ACCESS (for reproducibility)
- How data access worked (exact commands, read-only pattern)
- How API/UI was driven (tool + session name)
- Dataset snapshot (row counts at time of run)
- Adversarial checking setup (how many agents, what lenses)
- Closing line: "End of findings. Read-only audit; no live data was mutated."

## Example finding (functionality lane — from Michael's v2)

### AP-D1 · Duplicates · HIGH · Distinct partial invoice mislabeled an "exact" 100% sha256 duplicate → blocks a real $372.48 payable
- URL: https://ca-org.fly.dev/accounts-payable/invoices/apinv_a949545d... and /accounts-payable/duplicates
- What's wrong: BW Industrial Sales has two genuinely distinct invoices both numbered 309160-0001 under PO018080 ($873.44 and $372.48, different sha256, different dates). The dedup engine flags the $372.48 invoice as a duplicate of the $873.44 with match_type='exact', score=1.0.
- Expected: a vendor+invoice-number match between documents with different sha256 and different amounts is at best fuzzy/potential, not "exact". (proof: classifier at server/utils/accountsPayableOperations.ts:373-407 requires byte-identical sha256 OR amountScore ≥ 0.995; here amountSimilarity = 0.4265)
- Actual (UI + API + DB agree): invoice sits on hold in the duplicate queue with a "Duplicate 100% · exact" badge.
- Layer at fault: API / ingestion logic — the dedup query matches on vendor+invoice# branch but unconditionally writes match_type='exact', score=1.
- Impact: a legitimate $372.48 payable is blocked and presented with false "100% exact" evidence — a reviewer would reasonably reject it (under-payment risk).
- Repro: open the $372.48 invoice → see the on-hold blocker; compare the two invoices' sha256.
- Verification: independent checker re-pulled both sha256, the dup row, receipts/PO lines; found the correct classifier is bypassed in the ingestion path; computed amountSimilarity = 0.4265. CONFIRMED.

## Example finding (UX lane — same rigor)

### UX-A1 · Approvals · HIGH · Approver cannot tell WHY an invoice routed to them — approval reads as arbitrary
- URL: https://<app>/accounts-payable/approvals
- Expected: an approver persona should understand the routing reason (e.g. ">$10k tier → ap_lead") from the approval card itself. (proof: persona task "Understand what they're approving and why" — failed in 2/2 walkthrough attempts; NN/g heuristic #1 visibility of system status)
- Actual: card shows amount + vendor + Approve/Reject. No tier, no rule, no threshold shown. (screenshot: shots/run1/approvals-card.png)
- Layer at fault: IA / missing context on the approval surface
- Impact: approver either rubber-stamps (control failure) or has to ask in Slack (delivery looks unfinished to client)
- Repro: log in as approver-role account → open Approvals → inspect any pending card
- Verification: second checker walked the same task cold and also could not state the routing reason; confirmed the data EXISTS in the API payload (ap_approval_steps.required_amount_threshold) so this is purely a surface gap. CONFIRMED.
- Fix: render the matched rule ("Routed: amount $12,400 > $10,000 → ap_lead tier") on the card; data is already in the payload.
