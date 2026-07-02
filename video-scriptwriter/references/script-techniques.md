# Script Techniques — A Measured Catalog

A concrete, measurable catalog for writing video scripts (VO, on-screen copy, hooks, beats). Numbers come from three sources, labelled per claim:

- **[M-vo]** = measured from YouTube word-level auto-caption timing across `replit-agent4`, `vercel-workflows`, `raycast-glaze`, `cursor-3` (the VO-bearing videos in the reference set; the two Linear videos have **no VO** by design). Method: word timestamps deduped, speaking spans = words with <2.0s inter-word gap, words ÷ speaking-time.
- **[M-tech]** = measured frame data carried from `product-video-skill/techniques.md` (beat durations §7, cut grammar §3, caption sizing §4, music/silence §6). Cite the section.
- **[derived]** = computed from the two measured layers (e.g. words-per-beat = cadence × beat duration) or anchored to `_style/video_feedback_corpus.md`. Not independently frame-verified.

This is the script layer. For shot order use `video-shot-sequencer`, for frames use `video-storyboarder`, for edit/pace use `video-editing-director`. The canonical shot/cut/caption measurements live in `product-video-skill/techniques.md` — don't restate them here, cite them.

---

## §1 — VO Cadence (the load-bearing number)

**[M-vo] Spoken VO runs 2.3–2.7 words/sec (140–165 wpm) for scripted/explainer narration, up to ~3.4 words/sec (~200 wpm) for fast conversational two-person dialogue.**

| Video | words/sec | wpm | register |
|---|---:|---:|---|
| `replit-agent4` | 2.71 | 163 | scripted founder monologue, cinematic |
| `vercel-workflows` | 2.45 | 147 | explainer, deliberate |
| `raycast-glaze` | 2.35 | 141 | conversational talking-head |
| `cursor-3` | 3.39 | 203 | unscripted two-founder dialogue (fast) |

**Use the slow end (2.3–2.5 w/s) when you write the script.** People read their own scripts faster than they should; budgeting at 2.5 w/s leaves room for the breaths and silence-holds the edit needs. Conversational dialogue self-accelerates to 3+ w/s, but you cannot *write* to that rate — it only happens when two people talk over each other unscripted.

### Words-per-beat budget [derived] (at 2.5 w/s, the writing rate)

| Beat duration | VO word budget | Use |
|---|---:|---|
| 3s hook | **≤ 8 words** | first line; see §2 |
| 5s beat | ~12 words | one idea + its proof |
| 8s beat | ~20 words | a fuller explanation beat |
| 30s video (~22s speaking, 8s silence/cards) | **~55 words total VO** | a tight product-launch cut |
| 60s video (~48s speaking) | **~110–120 words VO** | founder/demo intercut |

If your draft VO exceeds the budget, you have too many ideas — cut to one controlling idea (corpus rule, §`hook-in-first-3s` neighbor), don't speed-read.

---

## §2 — Hook Lines (first 3 seconds)

The corpus rule `hook-in-first-3s` is binding: the first 3s carry the question, the result, or the visual surprise. At 2.5 w/s that is **≤ 8 spoken words** [derived from §1], or a single on-screen line. Patterns measured in the set:

- **Visual-only cold open [M-tech].** `linear-agent` and `linear-releases` open on a tilted UI / data-flow viz with **zero words** for the first 4.7s (techniques.md §7) — the motion is the hook. Use when you have a strong hero mockup; write *no* VO for beat 1, only the on-screen micro-label.
- **Result-first line.** Open on the outcome ("X now ships itself"), not the company. Banned openers (corpus anti-patterns): "Hi I'm…", "Today we're going to…", "Welcome to…", "We're excited to…".
- **Named-shift line.** Name the capability plainly in ≤8 words. `cursor-3` opens conversationally but lands the premise inside the first sentence.

**Always write ≥2 alternate hooks** for social/ad/launch/homepage (current SKILL.md rule 5) — the opener carries most of the retention risk and you cannot A/B a single draft.

---

## §3 — VO vs On-Screen-Copy Split

Don't narrate what the viewer can read or plainly see (current SKILL.md standard). Measured division of labor:

- **[M-tech] Title-card videos carry meaning in the cards, not VO.** `linear-releases` (techniques.md §4) uses 2 black title cards ("PLAN AND TRACK RELEASES", "AVAILABLE NOW") as the structural spine and **no VO at all**. The script here is *on-screen copy*: mono caps, ≤4 words/card, held 1.5–2.2s [M-tech §2 `crash_cut_to_title`].
- **[M-tech] Talking-head videos carry meaning in VO**, with on-screen text reduced to lower-thirds (name/role) and live UI captions. `vercel-workflows`, `raycast-glaze` (techniques.md §5: 80–90% talking-head).
- **Rule [derived]:** pick one carrier per beat. If the card says it, the VO doesn't; if the VO says it, the card shows proof, not the same words. The only measured exception is accessibility/sound-off captions (corpus `caption-burn-discipline`), which verbatim-match VO by design.

### On-screen copy sizing [M-tech §4]
- Title-card line: mono caps, ~3.5–5.5% of frame height, letterspacing 0.08–0.10em, single line (2 lines max — corpus `on-screen-text-readability`, ≥24pt @1080p).
- Never a bullet stack. `techniques.md §9`: no caption is more than 2 lines; the only multi-item example (Replit's 4 pillars) is spatially separated, not stacked.

---

## §4 — Beat Structures by Format

Use these in place of the prose sketches in `script-patterns.md`. Each gives a measured beat budget. The closest reference video is named so you can re-derive.

### Product launch (title-card spine) — closest: `linear-releases` [M-tech §7]
~30s, no/low VO. Beats: HOOK viz (4–5s) → TITLE card 1 (1.7s) → FEATURE (5–6s) → TITLE card 2 (1.5s) → FEATURE (6–8s) → TYPEWRITER "AVAILABLE NOW" (3–4s, music-out under it) → LOGO (2.5–4s silence, corpus end-card pattern). On-screen copy total: ~12–16 words across 2–3 cards.

### Founder + UI demo intercut — closest: `cursor-3` [M-tech §7]
45–60s, VO-driven. Two-shot hold opens (5–6s, hook in first sentence) → lower-third slides up at ~5s → UI demo beats hold **3–4s** (reading time) intercut with two-shot reactions at **1.5–2.5s**. VO budget ~110–120 words for 60s [derived §1]. Don't violate the asymmetry: UI holds longer than talk.

### Explainer / single-feature — closest: `vercel-workflows` [M-tech §7]
Long talking-head holds (10–25s+) over one sustained idea, then a long UI demo. VO at the slow 2.45 w/s end. Cut density is low (MSL ~22s, §3) — the script must sustain attention by itself, so front-load the payoff.

### Founder-led announcement — closest: `replit-agent4` [M-tech §7]
Cinematic monologue (2.7 w/s) intercut with B-roll. Opens on a B-roll establishing shot + 2-line caption, founder monologue holds 8–15s, B-roll inserts 2–3s. Belief → tension → evidence → invitation, kept tied to visible proof.

### Case study / customer story — closest: `stripe-reader-s700` [M-tech §7]
Interview-driven; before-state → constraint → intervention → after-state → quoted proof. Don't invent metrics — mark `[needs source]` (current SKILL.md rule). Ends on partner-logo lockup (corpus, customer-story only).

### Social short [derived + corpus]
First frame legible as a paused thumbnail (corpus `hook-in-first-3s` + storyboarder §). One mechanic per video. Punchline early. Burned-in captions mandatory (corpus `caption-burn-discipline`).

---

## §5 — Matt's-taste overrides (read `_style/video_feedback_corpus.md` first)

Where generic SaaS scripting convention and Matt's corpus disagree, **the corpus wins.** Load it before drafting. The script-relevant bindings:

- **`hook-in-first-3s`** — no logo sting >1s before content; result/question up front. Binding.
- **`voice-cosplay-guard`** — VO scripts for Matt-narrated video follow `_style/professional_voice.md` (Zerg) / `personal_voice.md` (personal). **Skill-generated VO drafts never cosplay Matt-voice** — emit a structured draft Matt reads in his own voice. No "Here's the thing", no parallel triplets, no "transformative" (CLAUDE.md voice rules).
- **`product-as-the-product`** — the script's first product beat leads with the primary affordance, not chrome/settings/login.
- **`intro-outro-budget`** — intro ≤5s (prefer 3), outro ≤8s; skip intro entirely on <30s social cuts.
- **Banned terminology** — never use Zstack-as-umbrella phrasing for the product family in any VO line, on-screen text, or caption. Use "Zerg products" (see `zerg_product_terminology_hook.py`).
- **Cadence-over-perfection** — Matt, `#growzth` 2026-04-14: ship a tight 3-second opener and keep a steady production cycle; don't agonize over a perfect 30s intro.
