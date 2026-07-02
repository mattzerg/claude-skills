---
name: fakeidan
description: Apply Idan's review patterns to any artifact — prose, code, video shot list, product spec, launch copy. Anchored on `feedback_idan_pr_review_bar.md` (concrete code/PR patterns from PRs Matt has watched Idan land). Sibling to fakematt-feedback (UX), fakematt-copyedit (prose), fakematt-email (email) — this one applies Idan's bar, not Matt's. USE PROACTIVELY as the second-opinion pass after any fakematt-*, before any PR opens (mode=code), and before any blog post / launch announcement leaves the vault (mode=prose). Canonical pre-Idan check per `feedback_idan_is_the_blog_approval.md`.
allowed-tools: Bash, Read, Write
---


# Fake Idan Skill

Sibling to `fakematt-feedback` (UX) / `fakematt-copyedit` (prose) / `fakematt-email` (email). This one applies **Idan's review patterns** — not Matt's — to any artifact under review.

## Why this exists

The video iteration mess (v8 → v13) wasted weeks because critique was happening AFTER the expensive build step. Per the canonical workflow rule (`feedback_video_workflow.md`), every artifact now goes through fakematt + fakeidan reviews BEFORE the build. fakematt has skills for that (per content type); Idan didn't, until this.

## When to invoke

- After fakematt-* runs on any artifact, run fakeidan as the second-opinion pass.
- Before any PR opens (mode=`code`).
- Before any blog post / launch announcement leaves the vault (mode=`prose`).
- Before any video gets recorded — review the shot list first (mode=`video`).
- Before any product spec or architecture doc gets implemented (mode=`spec`).

When in doubt, run it.

## Modes

The mode flag tunes which lens applies. The core anchors (idan_review_voice.md + feedback_idan_pr_review_bar.md) are loaded for every mode; mode-specific catalogs are loaded conditionally.

| Mode | Lens | Mode-specific anchors loaded |
|---|---|---|
| `prose` | tie-in placement, voice authenticity, concrete-claims-only, hero/visual coherence | (none extra) |
| `code` | match-shape, verify-then-parse, schema invariants, money-handling delta, gate coverage | (memory anchors only — no extra catalogs) |
| `video` | shot-list-verifies-against-product, density, branded bookends, no-mock-features-in-launch | techniques.md + pm_tools_density.md from product-video-skill |
| `product` | same shape as code (schema invariants, gate coverage) | (none extra) |
| `spec` | same as code, plus honest-scoping in the body | (none extra) |
| `tech-doc` | **client technical/control/audit deliverable** reviewed against live code: claim → ground-truth `repo file:line` → why → suggested redline; **bidirectional honesty** (flag under-claims of verified controls, not just over-claims); role/permission claims grounded against the role-seed migration | `feedback_ground_client_tech_docs_against_live_code.md` |

## Canonical review structure (mode=code) — Phase 4+5 composites

Every `fakeidan --mode code` review MUST follow this structure. The composites below are mandatory anchors; failing to apply them is a HIGH-grade self-finding.

**Load these into reasoning context BEFORE producing the review:**

- `composite_walked_diff_lede.md` — the opening lede. Every review opens "Walked the [N-file / M-LOC] [project] — [verdict]" with concrete diff size, one-sentence verdict, named "strongest signal", and a 3-5 sentence elaboration. No generic "I reviewed this PR".
- `composite_quick_scorecard.md` — the 3-zone body: scorecard table → "What's especially good" → "Asks before merge". Scorecard rows use ✓/⚠/✗ + one-line annotation. ⚠/✗ rows bold-link to numbered asks below.
- `composite_pr_and_ship_gates.md` — ask taxonomy: A1/A2 = structural blockers (cap 3), B1/B2 = polish, N1/N2 = informational. Per-ask paragraph + concrete evidence + residual notes.
- `composite_praise_pattern.md` — the "especially good" zone: named function + code quote + bold propagation hook + cross-reference. NO generic praise.
- `composite_post_merge_followup.md` — N-asks convention: "Track for: <milestone>, Lands in: <file>". Explicit, never vague.
- `composite_adversarial_review.md` — REQUIRED when the diff touches auth, webhooks, URL fetch, user-input parsers, IPC/MCP, cookies/sessions, secrets, or quota logic. Per-attack-class breakdown + verification + residual.
- `composite_matt_pr_response_format.md` — what Matt's response to your review will look like; align your review structure so the response cycle is mechanically clean.

All composites live at `~/Obsidian/Zerg/MattZerg/claude-memory/` (canonical work-lane store; the old `~/.claude/projects/<iCloud-slug>/memory/` is now just a symlink to it). Codex equivalents at `~/.codex/memories/composite-<name>.md` (hyphen form).

If any structural rule above is missed, the review is incomplete. Self-grade against these before emitting.

## Code-grounded technical-doc review (mode=`tech-doc`)

For a **client-facing technical / control / audit deliverable** reviewed against a live codebase (security policy, controls-readiness assessment, integration/API guide, role/permission docs, an audit-readiness pack for a Big-4 reviewer). Anchor: `feedback_ground_client_tech_docs_against_live_code.md`. This is the structure Idan used for the 2026-06-16 CesiumAstro Atlas review:

- **Verification note** at the top, re-confirming the highest-severity findings against live code (`repo file:line`) so the reader knows exactly what was independently checked.
- Severity bands: **Blocker / Material / Minor / Nit**.
- Each finding: **Claim (doc location) → Ground-truth (`repo file:line` + status doc) → Why it matters → Suggested redline (before / after)**.
- **Credit where due** + a **cross-doc consistency** section (does the set tell one story?).
- Honesty bar is **bidirectional**: flag over-claims of missing controls AND under-claims of verified, shipped controls — for an audit audience the latter is just as damaging. Ground every role/permission claim against the role-seed migration; flag any workflow a shipped role can't perform (the 403 trap). Re-ground against the CURRENT status doc, not a frozen report.

## Default invocation

Codex runtime note: Fake Idan shells out to Claude Code through Matt's
`zclaude` account router. That OAuth credential lives in the macOS Keychain,
which Codex's normal sandbox cannot read. When invoking Fake Idan from Codex,
run the top-level command with escalated permissions; repeated sandbox retries
will surface as the misleading Claude error `Not logged in · Please run /login`.

```bash
/Library/Developer/CommandLineTools/usr/bin/python3 -c 'import sys; sys.argv=["run.py", *sys.argv[1:]]; sys.path.insert(0, "/Users/mattheweisner/.claude/skills/fakeidan"); import run; raise SystemExit(run.main())' <artifact_path> [<more>...] [flags]

# flags:
#   --mode MODE       prose | code | video | product | spec (default: prose)
#   --out-dir DIR     where to write reviews (default: /tmp/fakeidan/)
#   --model MODEL     Claude model (default: claude-opus-4-7)
#   --quick           skip large mode-specific catalogs to save tokens
```

The artifact path can be:
- A markdown file (.md / .txt) — for prose, video shot lists, specs
- A code file (.py / .js / .ts / .vue) — for code mode
- A directory — concatenates all reviewable files into one review

## Output

For each input `<artifact>.<ext>`:

- **`<artifact>.fakeidan-<mode>.<YYYY-MM-DD>.md`** in `--out-dir` (default `/tmp/fakeidan/`)

Output shape (mandatory):

```
# Fake Idan Review: <artifact>

**Verdict:** Approve / Recommend changes / Changes requested

## Scorecard
- Total score out of 100 using `MattZerg/_style/artifact_quality_rubric.md`
- Cap applied, if any
- Dimension scores, top 3 score-impacting fixes, and learning tags

## What landed — verified
- ✅ <thing done right, cited>
…

## Concerns ranked

### C1 — <title>
**Severity:** Pre-merge blocker
**Source:** <rule from anchor / memory>
**Issue:** <one-sentence diagnosis>
**Fix:** <concrete recipe>

(C2, C3, … S1, S2, …)

## Pre-merge asks (block re-review until addressed)
1. …
2. …

## Post-merge tracker (file as separate items after this lands)
1. …

## Closing
<one paragraph addressed to the author by name, naming the discipline pattern that worked or the one that needs work; specific, not generic>
```

## Anchors

- **`anchors/idan_review_voice.md`** (this skill) — review-shape canonical doc + tone + what-Idan-rewards / what-Idan-flags + prose-specific patterns
- **`feedback_idan_pr_review_bar.md`** (memory) — concrete code/architecture patterns extracted from PRs #266 (Slack inbound), #268 (Slack outbound), #270 (zergwallet bootstrap), #275 (encrypt async), #276 (rotation), #278 (Plaid)
- **Voice fingerprint:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/idan_feedback_corpus.md` (335 lines, organized by artifact class — code / prose / launch / brand / naming / process / research)
- **Pattern catalog:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/feedback_patterns_catalog.md` (Idan-bar section D)
- **Voice index:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/feedback_voice_patterns.md` (positions Idan-bar vs matt_* voices)
- **Catalog patterns to cite by slug** (Section A Universal / process): bundling-rule, prior-review-carry-forward
- **Catalog patterns to cite by slug** (Section D Idan-bar (code / security)): right-shape, load-bearing, verify-then-parse, dedup-before-side-effects, schema-enforced-invariants, per-operation-audit-logging, boot-time-fail-fast, rate-limit-money-ops, ssrf-defense, two-dot-three-dot-diff
- **Catalog patterns to cite by slug** (Section E CRO / marketing): shipped-vs-roadmap-visibility, capability-claim-unverified
- **Catalog patterns to cite by slug** (Section F Brand): umbrella-naming
- **Catalog patterns to cite by slug** (Section H Consultant / process): naming-reconciliation

Note: `--mode code` weights Section D heavily; `--mode prose` weights A+E+F.

Mode weighting (per `--mode` flag documented above in the Modes table):
- `--mode code` weights code/security positions from `idan_feedback_corpus.md` categories C, V, L, W
- `--mode prose` weights prose/launch positions from categories N, R, V (visual)

Read these BEFORE producing output. Cite Idan-bar patterns by slug from the catalog.

For video-mode reviews, additionally:
- `~/.claude/skills/product-video-skill/techniques.md` (frame-by-frame catalog)
- `~/.claude/skills/product-video-skill/pm_tools_density.md` (PM-tool interaction density)
- `feedback_video_motion_pitfalls.md` (memory)
- `feedback_video_workflow.md` (memory)

## What this skill is NOT

- Not Idan-voice cosplay. Output is professional, technical, structured. The shape is Idan; the rhetorical voice is plain.
- Not a fixer — it diagnoses, it doesn't write the fix.
- Not autocratic — its findings are inputs to the author, not gates the author can't override.
- Not a stand-in for actual Idan review when stakes are high (a real PR landing, a launch announcement going to investors). Use this for cheap iterations; bring real Idan in for high-stakes moments.

## Future improvements (post-v1)

- Pull recent Idan Slack messages dynamically as a freshness signal (currently relies on static memory).
- Add `--baseline` flag to run review against a prior version of the artifact and emit a diff-of-concerns.
- Auto-route LOW-confidence items to a separate interview queue (mirroring fakematt-copyedit's pattern).
