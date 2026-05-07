---
name: fakeidan
description: Apply Idan's review patterns to any artifact — prose, code, video shot list, product spec, launch copy. Anchored on `feedback_idan_pr_review_bar.md` (concrete code/PR patterns from PRs #266/#268/#270/#275/#276/#278) + `idan_review_voice.md` (review-shape canonical doc) + mode-specific catalogs (e.g. techniques.md when reviewing video shot lists). Output is structured & technical, not Idan-voice cosplay — architecture-credits-first; concerns ranked C1/C2/.../S1/S2/...; pre-merge asks numbered; post-merge tracker numbered; closing paragraph by name. Sibling to fakematt-feedback / fakematt-copyedit / fakematt-email. USE PROACTIVELY before any artifact ships externally OR before any video/blog/PR/spec is approved — and as the second-opinion pass after fakematt-* runs.
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

## Default invocation

```bash
python3 ~/.claude/skills/fakeidan/run.py <artifact_path> [<more>...] [flags]

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
