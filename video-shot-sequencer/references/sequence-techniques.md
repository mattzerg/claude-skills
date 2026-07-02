# Sequence Techniques — A Measured Catalog

Concrete guidance for **ordering** beats and budgeting their durations — turning a script/concept into a timed shot sequence. This catalog owns *ordering, per-beat duration, and b-roll-to-hero ratio*. It does **not** restate shot recipes or cut cadence — those are canonical in `product-video-skill/techniques.md` §2 (recipes) and §3 (MSL). Cite them.

Source labels: **[M-tech]** = frame data from techniques.md (cite section); **[derived]** = computed or anchored to `_style/video_feedback_corpus.md`.

---

## §1 — Per-Beat Duration Budgets [M-tech §3, §7]

The single most useful measured fact: **hold time is asymmetric by beat type.** Don't space every beat evenly.

| Beat type | Hold | Source |
|---|---|---|
| UI demo (high complexity) | **3–4s** | §3 (Cursor holds 3–4s for reading time) |
| Two-shot / interview reaction | **1.5–2.5s** | §7 `cursor-3` |
| Title card | **1.5–2.2s** | §2 `crash_cut_to_title` |
| Floating-UI hero (slow_orbit) | **4–8s** | §7 `linear-agent` |
| B-roll / establishing (Ken Burns) | **≥3.5s** | §2 `kenburns_macro` (below this = twitchy) |
| Talking-head sustain (explainer) | **8–25s** | §7 `vercel`, `replit` |
| Typewriter final beat | 3–4s | §7 `linear-releases` |
| End card / logo | 2.5–4s (often silence) | §6 |

**Rule [M-tech §3]:** UI holds longer than talk. In `cursor-3` the UI/talk asymmetry (3–4s vs 1.5–2.5s) is *why* the demo breathes. Never give a complex UI frame the same 1.5s you give a reaction shot.

---

## §2 — Cut Cadence by Format [M-tech §3]

Cite, don't re-measure. From techniques.md §3 (MSL = mean shot length) reconciled with corpus `pacing`:

| Format | MSL [M-tech §3] | ≈ cuts/min [derived] | corpus `pacing` target |
|---|---|---|---|
| Title-card launch (`linear-releases`) | 6.0s | ~10 | — |
| Continuous-camera hero (`linear-agent`) | 11.0s | ~5 | 6–10 (talking-head explainer) |
| Founder + UI intercut (`cursor-3`) | 2.8s | ~21 | 12–18 (product demo) |
| Customer story (`stripe-reader-s700`) | 2.2s | ~27 | 20–30 (social/launch) |
| Explainer (`vercel`) | 22s | ~3 | 6–10 |

**Reconciliation note [derived]:** the corpus `pacing` thresholds (12–18 demo / 20–30 social / 6–10 explainer cuts-min) and the measured MSLs agree once you map format→reference. Use the corpus thresholds when planning; use the MSL when auditing an existing cut.

Hard cuts are the default; dissolves are rare (only 2 of 10 videos, §3). Whoosh SFX on cuts: **zero** in the dataset (§9) — don't sequence one in.

---

## §3 — Ordering Patterns (named)

Each is a measured beat order with the closest reference. Pick by format, then drop your script beats into the slots.

### `title_card_spine` — closest `linear-releases` [M-tech §7]
`HOOK viz → TITLE 1 → FEATURE → TITLE 2 → FEATURE → TYPEWRITER → LOGO(silence)`.
The title cards ARE the structure (the cut is the section header). ~30s, 8 beats, MSL ~6s. Use when you have 2–3 features with existing mockups/logos.

### `founder_ui_intercut` — closest `cursor-3` [M-tech §7]
`TWO-SHOT(hook) → +lower-third → UI demo → two-shot beat → UI demo → … → wrap two-shot → END`.
Strict asymmetry: UI 3–4s, talk 1.5–2.5s. 45–60s. Use when a person launches the product on-camera.

### `monologue_broll_intercut` — closest `replit-agent4` [M-tech §7]
`B-ROLL establishing(+caption) → MONOLOGUE 8–15s → B-roll insert 2–3s → MONOLOGUE → …`.
Cinematic. The B-roll covers the cuts so the monologue feels continuous. Use for founder-led announcement / brand-leaning launch.

### `montage_then_hold` — closest `stripe-reader-s700` [M-tech §7]
`MUSIC-INTRO MONTAGE (5 cuts in 2s, sync to kick) → location card → interview/B-roll intercut 2–3s → proof close-ups → wrap → partner-logo lockup`.
Densest open in the set. Use for customer story / co-launch. **Music sync is for the montage/B-roll only, never for UI feature beats** (§9).

### `visual_hero_loop` — closest `linear-agent` [M-tech §7]
`TILTED UI → COMMAND → ISSUE LIST → ARCHITECTURE PULLBACK → CARD ZOOM → CRASH-OUT → TITLE → LOGO`. No VO, music-driven, loops cleanly. 22–28s. Highest-prestige, hardest to produce (needs 3D mockup pipeline). MSL ~11s — very few cuts, each beat earns its long hold.

---

## §4 — B-roll-to-Hero Ratio [M-tech §5]

From techniques.md §5 (frame-content mix): **almost no good launch is >70% real UI.** Sequence enough non-UI coverage:

- Pure-UI launch <30s → ~20–32% brand-frame beats (title cards).
- Customer story → ~25/25/25/25 UI / brand-frame / interview / B-roll.
- Founder launch → 50–90% talking-head + B-roll inserts.

Coverage floor [corpus `shot-list-coverage`]: every video pack needs ≥1 talking-head OR hero, ≥3 B-roll, ≥1 screen-record (if a product demo), + a hero close-up if launch-class. A single-source sequence (e.g. talking-head only) is fragile — one failed take kills it.

---

## §5 — Sequencing Rules

1. **Open on motion, not chrome** (corpus `hook-in-first-3s` + `product-as-the-product`): beat 1 is the hook — hero motion or the result, never a logo sting >1s or a settings screen.
2. **Vary composition beat-to-beat** [M-tech §9]: don't repeat the same composition mode back-to-back (e.g. two `slow_orbit` shots at the same scale read as one stuck shot). "Same" = same recipe + same scale + same subject.
3. **One push-direction per shot** [M-tech §9]: never push-in then push-in faster within a beat.
4. **End-card in silence** [M-tech §6]: pair the closing logo with 1.2–4.0s of silence/music-decay — the single most consistent technique in the dataset.
5. **Budget intro/outro** [corpus `intro-outro-budget`]: intro ≤5s, outro ≤8s; skip intro on <30s social.

---

## §6 — Matt's-taste overrides (read `_style/video_feedback_corpus.md` first)

Corpus wins over generic convention. Sequence-relevant bindings:

- **`pacing`** — cuts/minute calibrated to format; >30s of single static shot in a non-explainer format fails; audio/visual cuts should sync (on the beat for music-bed, on the consonant for narration).
- **`shot-list-coverage`** — coverage floor above; missing coverage = fragile single-source cut.
- **`product-as-the-product`** — the first product beat leads with the primary affordance.
- **`hook-in-first-3s`** — beat 1 is the hook.
- **No banned terminology** in title-card beats (Zstack-as-umbrella → "Zerg products").
- **Cadence-over-perfection** (Matt, `#growzth` 2026-04-14) — a tight, shippable sequence beats an over-engineered one that never ships.
