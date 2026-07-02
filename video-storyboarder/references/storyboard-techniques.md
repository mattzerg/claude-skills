# Storyboard Techniques — A Measured Catalog

Concrete, measurable guidance for text storyboards, frame plans, and animatics. The storyboard's job is to lock **composition** before production — what's in frame, where, how big, and whether the frame survives crop to 9:16 / 1:1.

Source labels:
- **[M-tech]** = frame measurements carried from `product-video-skill/techniques.md` (caption sizing §4, frame-content ratios §5, shot recipes §2, per-video frames §7). Cite the section.
- **[derived]** = computed from measured data or anchored to `_style/video_feedback_corpus.md`.

Composition jargon the old template left undefined is defined in §1 so a board is unambiguous.

---

## §1 — Frame Vocabulary (defined)

- **Focal subject** — the single element the viewer's eye must land on in this frame. Exactly one per frame (corpus + techniques.md §9: one subject of attention). If a frame has two candidate focal subjects, it's two frames.
- **Proof invariant** — the thing this frame must show to be *believable* as proof, regardless of styling. E.g. for a "the agent did it" beat, the proof invariant is the visible result state (PR created, card moved), not the button that triggered it. If the proof invariant isn't legible in the frame, the frame fails even if it looks good.
- **Safe area** — the central region that survives every aspect-ratio crop you'll ship. Keep focal subject + on-screen text inside the **9:16 safe column** (center ~56% width of a 16:9 master) when the cut ships vertical (corpus `aspect-ratio-platform-fit`).
- **Brand-frame** — title card / logo card / interstitial pure-color frame (techniques.md §5). Carries copy or logo, never UI.
- **Hold** — how long the frame is on screen. Drives reading time; see §4.

---

## §2 — First-Frame Composition (the thumbnail rule)

The first frame is a paused thumbnail in autoplay feeds — it must be legible at rest (current SKILL.md rule). Measured opening-frame patterns:

- **[M-tech §7] Tilted floating UI.** `linear-agent` opens on a Linear sidebar tilted **12°** in deep black space; `linear-releases` opens on a data-flow viz. Focal subject is the lit UI rectangle; everything else is vignette. Reads as premium and is legible paused.
- **[M-tech §7] Two-shot establishing.** `cursor-3` opens on a locked two-shot, subjects centered, library background. Legible paused; identity lands when the lower-third arrives at ~5s.
- **[M-tech §7] B-roll establishing + caption.** `replit-agent4` opens on an aerial with a 2-line location caption bottom-right.
- **Anti-pattern [corpus `product-as-the-product`]:** never open the first frame on settings / login / empty state / a sidebar-only chrome view. The primary affordance leads.

---

## §3 — Focal-Subject Framing & Sizing [M-tech §4]

On-screen text sizes are measured as **% of frame height @1080p** in techniques.md §4. Use them as the storyboard's sizing contract:

| Element | Size (% frame ht) | Source |
|---|---|---|
| Title-card line (mono caps) | 3.5–5.5% | §4 `linear-releases` |
| Big display word (e.g. "NEW YORK") | ~12% | §4 `stripe-reader-s700` |
| Countdown numeral / hero number | ~25% | §4 `figma-config2024` |
| Lower-third name | 2.6–2.8% | §4 `cursor-3`/`vercel` |
| Lower-third role | 1.4–1.6% | §4 |
| 2-line B-roll location caption | ~1.8% / ~1.4% | §4 `replit-agent4` |

**Floor [corpus `on-screen-text-readability`]:** never below 24pt @1080p (≈2.2% frame ht); contrast ≥4.5:1 at every frame the text appears; never text on motion-heavy background without a panel/scrim/blur behind it. Lower-thirds use scrim or transparent gradient — **never drop shadows** (techniques.md §9).

### Proof close-ups
For a proof beat, the storyboard must crop in so the proof invariant is legible. `stripe-reader-s700` uses macro hardware close-ups and in-product UI captions for its proof beats (§7). Corpus rule: close-ups for proof; don't try to prove with a full-screen app view where the result is 40px tall.

---

## §4 — Hold Time = Reading Time [M-tech §3 + corpus]

A frame's hold must give the viewer time to read/comprehend it:

- **UI demo frame:** hold **3–4s** (techniques.md §3: Cursor holds 3–4s on UI demos because complexity is high). Below ~2.5s a static UI dies — pair with a `linear_push_in` (§2) to keep it alive.
- **Title card:** 1.5–2.2s (§2 `crash_cut_to_title`).
- **B-roll / establishing:** Ken Burns minimum 3.5s or it reads twitchy (§2 `kenburns_macro`).
- **Text line:** ≥2s readable hold (corpus `on-screen-text-readability`).
- **End card:** 2.5–4s, often in silence (§6).

Mark the hold on every frame. A board without holds can't be timed.

---

## §5 — Frame-Content Mix [M-tech §5]

techniques.md §5 measures how runtime splits across UI / mockup / brand-frame / people / B-roll. The storyboard insight: **almost no good launch video is more than ~70% real UI** — there's always cinematic cover. Plan brand-frames and B-roll as structural frames, not afterthoughts:

- Pure-UI launch <30s → 20–32% brand-frame (title cards as beats).
- Customer story → ~25/25/25/25 UI / brand-frame / interview / B-roll.
- Founder launch → 50–90% talking-head with B-roll inserts.

If your board is 100% UI screens, it's structurally fragile (corpus `shot-list-coverage`): add a hero close-up, a brand-frame, and ≥1 B-roll.

---

## §6 — Aspect-Ratio Planning [corpus `aspect-ratio-platform-fit`]

Decide variants at the **board** stage, not after the edit. Master 16:9; plan crops for 9:16 (TikTok/Reels/Shorts), 1:1 (LinkedIn/X feed), 4:5 (IG in-feed).

- Keep focal subject + text in the 9:16 safe column on any frame that will ship vertical.
- Never crop a talking-head's head off in 9:16 — frame the master with vertical headroom.
- Captions positioned for 1:1 must not fall outside the 9:16 safe zone (corpus anti-pattern).
- Mark each frame's `aspect-ratio note`: which crops it must survive and where the safe-area risk is.

---

## §7 — Fidelity Levels (when to use which)

- **Text board** — table: frame # | hold | focal subject | composition | proof invariant | on-screen text | aspect note. Fastest; use for internal review.
- **Production board** — add camera/screen move (cite the §2 recipe by name, e.g. `slow_orbit 15°`), depth/vignette, required assets, transition out.
- **Animatic notes** — add timing to match the script's beat budget (scriptwriter §1) and the target MSL (editing-director).
- **Prompt board** — for AI-generated frames (`film-maker-skill` / `nano-banana`): one prompt per frame, style keywords consistent across frames, focal subject + composition + lighting explicit.

---

## §8 — Matt's-taste overrides (read `_style/video_feedback_corpus.md` first)

Where generic convention and Matt's corpus disagree, **the corpus wins.** Load it before boarding. Storyboard-relevant bindings:

- **`feedback-frame-level`** — frame-level mistakes are **binding**. A single bad hero frame blocks the cut. Matt, codex 2026-05-11: *"this frame looks bad with the green highlight not actually outlining the card properly. please make sure mistakes like this dont keep happening."* Every visual element must do the load-bearing job the frame asks of it (the proof invariant). Storyboard QA catches this before production.
- **`on-screen-text-readability`** — mobile playback caps resolution; thumb-scroll caps reading time. A frame that's "readable on the edit-suite monitor" routinely fails in the field. Board for the phone.
- **`product-as-the-product`** — first product frame shows the primary affordance, not chrome.
- **`lower-third-density`** — one lower-third per speaker intro; never two simultaneous; never over a text-heavy frame.
- **No banned terminology** in any on-screen text/title card (Zstack-as-umbrella → use "Zerg products").
