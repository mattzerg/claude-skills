# Edit Techniques — A Measured Catalog

Concrete guidance for the **edit/post** layer: pacing, transition grammar, sound design, and silence discipline. Shot recipes and cut-cadence measurements are canonical in `product-video-skill/techniques.md` §2/§3 — cite them, don't restate. This catalog owns *what the editor decides*: transition choice, music structure, mix, and trim.

Source labels: **[M-tech]** = frame/audio data from techniques.md (cite §); **[derived]** = computed or anchored to `_style/video_feedback_corpus.md`.

---

## §1 — Pacing (the audit number) [M-tech §3]

Reconciled cut-density targets (plan with corpus `pacing`; audit with measured MSL):

| Format | corpus cuts/min | MSL [M-tech §3] | reference |
|---|---|---|---|
| Product demo | 12–18 | 2.8s (`cursor-3`) | founder+UI intercut |
| Social / launch | 20–30 | 2.2s (`stripe-reader-s700`) | customer story |
| Talking-head explainer | 6–10 | 11–22s (`linear-agent`,`vercel`) | sustained |

**Asymmetry rule [M-tech §3]:** within a cut, hold UI demos 3–4s and reaction/talk 1.5–2.5s. A flat cadence kills a demo. Audio and visual cuts should sync: on the beat for music-bed videos, on the consonant for narration (corpus `pacing`).

---

## §2 — Transition Grammar [M-tech §3, §9]

**Hard cut is the default.** In all 10 reference videos:

- **Dissolves are rare** — only `linear-releases` 0:10–0:11 and `notion-calendar` 0:35 (~250–400ms). Use a cross-dissolve only as a deliberate, once-per-video move.
- **No whoosh/swish SFX on cuts** — zero examples (§9). If a cut has a whoosh, that's why it reads "stocky." Remove it.
- **Whip-pan-blur** (`whip_pan_blur` §2) is the only frequent "soft" transition — 0.18–0.25s, ~18px motion blur, the blur IS the transition. Pair with a music hit on the blur peak. Energy injection between unrelated scenes only.
- **Match-cut** (`match_cut_pull` §2) hides a cut between two shots that share one geometric element (Notion dock-icon → app). High-effort, high-reward.
- **Smash-to-black** before a title card; the title hard-cuts in on both sides (the title is the cut — §2 `crash_cut_to_title`).

**No fade-in on captions in title-card mode** [M-tech §9]: Linear hard-cuts on the caption.

---

## §3 — Motion on Static Frames [M-tech §2]

A static UI held >2.5s dies without motion. The editor's fixes (cite recipe + params):

- `linear_push_in(1.00→1.04, 2.0–3.0s, linear)` — the workhorse; 6/10 videos. Build-first priority (§10).
- `slow_orbit(15–25°, 1.8–2.4s, ease-in-out)` — premium hero hold; needs 3D mockup.
- `kenburns_macro(1.00→1.12, 3.5–4.0s)` — B-roll/stills only; 3.5s min.
- `ease_out_punch(1.00→1.06, 0.35–0.45s, overshoot bezier)` — cold-cut into a new scene/title card.

**No double-zoom** [M-tech §9]: one push direction at one rate per shot. Never push-in then push-in faster.
**No color overlays on UI** [M-tech §9]: show UI as the user sees it; brand-tinting a UI screen is conspicuously absent from every good video.

---

## §4 — Sound Design [M-tech §6 + corpus]

### Music structure
- One swell per short video, synced to the structural beat. `linear-agent`: ambient drone, one build at ~0:25 matching the first major cut. `linear-releases`: piano/synth crescendos into the "AVAILABLE NOW" typewriter (24–26s), then drops.
- Speech-driven videos (`cursor-3`, `raycast`) run a continuous low-key bed under VO, **no swells** — the talk carries it.
- Customer story (`stripe`): upbeat bed, drums enter at 0:02, intro montage cuts sync to the kick (5 cuts in 2s = 4-on-the-floor) — **but never sync UI feature beats to drums** (§9).

### Music-out + end card [M-tech §6]
The single most consistent technique in the dataset: **brand-frame end cards are paired with 1.2–4.0s of silence (or music decay) on the closing logo.** `linear-agent` 51.0s → 4.0s silence; `linear-releases` 27.6s → 2.5s; `stripe` 72.9s → 1.2s. Always cut the music out under the final beat and hold the logo in silence.

### Mix levels [corpus `audio-levels`]
Dialogue −12 to −6 dBFS peaks; music bed ≥9 dB below dialogue; no clipping any channel; normalize −16 LUFS online (−14 LUFS YouTube). **Music louder than dialogue at any point = the mix is wrong** (corpus anti-pattern, hard rule).

### SFX [M-tech §6]
Used sparingly and source-justified: typewriter clicks (110–130ms apart) under typewriter beats; card-tap click synced to a payment moment. No decorative whooshes.

---

## §5 — Silence & Trim Discipline [corpus `silence-padding`]

- Leading silence ≤0.3s; trailing ≤0.5s.
- Mid-clip silence >1s → B-roll bridge or cut entirely.
- Preserve 0.1–0.2s breathing room around cuts to avoid clipped-consonant artifacts.
- **Jump-cut discipline** (corpus): cut on the breath, not mid-word; preserve room tone across cuts (J/L cut audio); never jump-cut across a thought boundary without a B-roll bridge. >3 jump cuts on one talking-head paragraph = visible glitch.

---

## §6 — Captions in the Edit [corpus `caption-burn-discipline`]

- **Always burn captions into social cuts** (sound-off default); separate SRT/VTT for YouTube + accessibility.
- Captions verbatim-match dialogue (no paraphrase); proof auto-captions for typos (reads as low-effort otherwise).
- Caption typography matches brand; single-line or 2-line max (§9 — no bullet-stack captions).
- **Pipeline hook:** for post-render caption burn-in use the `caption-burn` skill (`run.py burn`), which composites Pillow-rendered PNG overlays via ffmpeg with brand tokens. It exists precisely because a rough cut once shipped silent — run it as the post-assemble caption step.

---

## §7 — Edit Note Output

Default edit-direction note carries, per beat: timecode | shot | hold | motion recipe (cite §2 name+params) | transition out | audio/music state | caption. Plus a top-level: target MSL, music-out timecode, end-card silence length, and the deliverable aspect-ratio variants. Lead a revision with the changed cut, then the material changes and unresolved assumptions.

---

## §8 — Matt's-taste overrides (read `_style/video_feedback_corpus.md` first)

Corpus wins over generic convention. Edit-relevant bindings:

- **`pacing`** / **`jump-cut-discipline`** / **`silence-padding`** — as above; mid-sentence jump cut and >30s single static shot (non-explainer) are anti-patterns.
- **`audio-levels`** — music never louder than dialogue; no clipping.
- **`caption-burn-discipline`** — captions are the highest-leverage review surface (Matt, `#growzth` 2026-05-14: *"Any feedback on captions/content are most useful right now"*). No social cut ships without burned captions.
- **`lower-third-density`** — one per speaker; 4–6s hold; never two simultaneous; restate after a 60s+ gap.
- **`intro-outro-budget`** — intro ≤5s, outro ≤8s; logo sting never longer than the CTA.
- **`feedback-frame-level`** — a single broken hero frame blocks the cut; frame-level findings are binding, not LOW.
- **No autoplay audio** on landing-page hero video (muted-autoplay or click-to-play).
- **No banned terminology** in on-screen text/captions (Zstack-as-umbrella → "Zerg products").
