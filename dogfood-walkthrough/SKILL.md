---
name: dogfood-walkthrough
description: Proof harness for the serial-launch polish. Picks a backlog product matching readiness criteria (ship_date in window, status approved/ready/scheduled/drafting, positioning brief complete, optional competitive folder), then walks it through 8 sequential stations (site bootstrap → docs scaffold → measurement spec → drip wired → launch pack → demo video → distribution → smoke), hard-stopping on BROKE findings, capturing per-station friction to `Growth/dogfood/dogfood-log-<slug>-YYYY-MM-DD.md`, and emitting a readiness scorecard (Battle-tested / Theoretical / Broke / Deferred) to `Growth/dogfood/scorecard-<slug>-YYYY-MM-DD.md`. Orchestrates calls to existing skills (`zstack-product`, `product-docs-skill`, `email-drip`, `growth-dashboard`) plus the bootstrap script + preflight — never reinvents them. USE PROACTIVELY before declaring the serial-launch pipeline polish complete OR before bootstrapping product #2 in a serial-launch run. Never auto-fixes — outputs findings + repair pointers.
---


# dogfood-walkthrough

The validation layer for the serial-launch polish. Until one product walks through every station cleanly, every template upstream is theoretical.

## When to use

- Before declaring the polish push complete.
- Before bootstrapping product #2 in a serial-launch run (the scorecard must be zero-BROKE first).
- After any template edit upstream (`measurement/_template.yaml`, `lifecycle/_drip-template.yaml`, `~/zerg/_templates/zerg-product/`) — re-walk to confirm the fix held.
- When Matt asks "is the pipeline ready" / "have we dogfooded it" / "which polish items are real vs theoretical".

## Verbs

### `pick`

```
python3 ~/.claude/skills/dogfood-walkthrough/run.py pick
python3 ~/.claude/skills/dogfood-walkthrough/run.py pick --confirm <slug>
```

Crawls `Growth/launch-backlog/*.md` (skipping `_*.md`), filters by readiness criteria, prints ranked candidates with reasoning. `--confirm <slug>` writes the slug to `Growth/dogfood/_active.txt`.

**Picker criteria (priority order):**
1. `target_launch_date` within 7–30 days from today
2. `status` ∈ {drafting, ready, scheduled, approved}
3. Positioning brief complete — frontmatter has `product_name` + `one_liner`; body sections not all `_TBD_`
4. (Optional) `MattZerg/Competitive/<category>/positioning.md` exists for the product's category
5. Tie-break: RICE score from parent campaign if present, else earliest `target_launch_date`

### `walk`

```
python3 ~/.claude/skills/dogfood-walkthrough/run.py walk
python3 ~/.claude/skills/dogfood-walkthrough/run.py walk --station N
python3 ~/.claude/skills/dogfood-walkthrough/run.py walk --resume
python3 ~/.claude/skills/dogfood-walkthrough/run.py walk --override "<reason>"
```

Runs the 8 stations sequentially against the active slug. Appends a status block per station to the log. Hard-stops on BROKE (exits non-zero). `--station N` (1-indexed) starts from station N. `--resume` continues from the last incomplete station (parses latest log). `--override` logs the reason, marks the station THEORETICAL, and continues.

### `repair`

```
python3 ~/.claude/skills/dogfood-walkthrough/run.py repair
```

Finds the latest log, locates the most-recent BROKE block, prints the repair-needed pointer, and opens it in `$EDITOR` (falls back to printing the path).

### `scorecard`

```
python3 ~/.claude/skills/dogfood-walkthrough/run.py scorecard
```

Reads the latest log, buckets stations into Battle-tested / Theoretical / Broke / Deferred, prints to stdout + writes `Growth/dogfood/scorecard-<slug>-YYYY-MM-DD.md`. Exit code = count of Broke items.

### `doctor`

```
python3 ~/.claude/skills/dogfood-walkthrough/run.py doctor
```

Pre-flight check: active pointer resolves to a real backlog entry; every required station-paired skill/script exists at the expected path; the chosen product's measurement YAML parses. Prints pass/fail per check, exits non-zero on any fail.

## 8 stations

| # | Station | Calls | Pass condition |
|---|---|---|---|
| 1 | Site bootstrap | `zerg-new-product.sh` + `preflight.py` | 0 HIGH preflight findings |
| 2 | Docs scaffold | `product-docs-skill scaffold` + `audit` | 7 canonical sections present |
| 3 | Measurement spec | YAML + checklist parse; 6 required events | schema valid; canonical event names |
| 4 | Drip wired | `email-drip` scaffold + audit | 5 Stream A templates render |
| 5 | Launch pack | `launch-pack` agent (manual handoff for now) | announcement + manifest exist |
| 6 | Demo video | `product-launch-video plan` + `video-review` | shot list valid; video-plan present |
| 7 | Distribution | `content-distribution generate` | 17 surfaces drafted |
| 8 | Smoke (post-ship) | `growth-dashboard --product <slug>` | lines 1–4 return non-stub |

## Stop-the-line conditions per station

- **1 site-bootstrap**: missing `~/zerg/<slug>/{package.json,nuxt.config.ts}`; preflight HIGH > 0.
- **2 docs-scaffold**: `product-docs-skill audit` exits non-zero.
- **3 measurement**: missing YAML/checklist; YAML doesn't parse; any of the 6 canonical event names absent.
- **4 drip**: `email-drip audit` exits non-zero.
- **5 launch-pack**: not BROKE — flagged THEORETICAL when launch artifacts missing (manual until launch-pack is fully script-driven).
- **6 demo-video**: shot-list template not copied (BROKE — bootstrap regression).
- **7 distribution**: `distribution.md` present but surface count ≠ 17 (BROKE).
- **8 smoke**: deferred until product has shipped + emitted events — THEORETICAL if dashboard returns all-TODO.

## Output paths

- `Growth/dogfood/_active.txt` — active slug pointer (one-line)
- `Growth/dogfood/dogfood-log-<slug>-YYYY-MM-DD.md` — append-only walk log
- `Growth/dogfood/scorecard-<slug>-YYYY-MM-DD.md` — scorecard snapshot

## Pair-with

- **`pr-gate`** refuses polish-followup PRs that don't close at least one scorecard BROKE item. Wire this on first BROKE.
- **`fakeidan mode=code`** should review `run.py` on first use — the harness itself is load-bearing.
- **`launch-pack` agent** owns station 5 once Matt invokes it via the conversational interface; this skill only verifies its outputs.
- **`zstack-product audit`** complements station 1 — preflight is the lightweight check; the full audit runs deeper canonical-pattern checks.
