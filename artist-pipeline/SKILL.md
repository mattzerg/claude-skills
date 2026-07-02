---
name: artist-pipeline
description: 'Operate the AI-music artist roster (HALO STATIC, DIM VIGIL, future siblings) at MattZerg/Artists/. Wraps the shared engine (Artists/engine/): steered-Suno batch generation via apiframe, A&R ledger + verdicts, cue-sheeted audition montages, EP assembly/preview/final-export, and new-artist scaffolding. USE PROACTIVELY when Matt says "new batch", "regen <lane> for <artist>", "keeper review", "montage", "audition reel", "assemble/preview the EP", "new artist", "music pipeline", "how are the EPs", or names HALO STATIC / DIM VIGIL / a track lane. Never generates without explicit go (credits), never judges audio quality (Matt-only), never publishes/uploads anywhere (release positioning unresolved).'
---

# Artist Pipeline Skill

Thin wrapper over `~/Obsidian/Zerg/MattZerg/Artists/engine/`. Read
`Artists/HANDOFF.md` before non-trivial work — it holds the dead-ends
("WHAT FAILED — do not re-derive") and open decisions.

## Hard rules
1. **No POST without Matt's go.** Generation spends apiframe credits (~12/gen,
   2 variants). `run_batch.py` preflights the balance (GET /v2/me); always run
   `--dry-run` first and show Matt the payload + credit cost before a live run.
2. **Audio verdicts are Matt's only.** Agents never set keeper/killed from
   their own judgment — build the montage, hand over the cue sheet, wait.
3. **Steering lives in `Artists/<slug>/artist.toml`** (styles + extra negatives;
   engine COMMON_NEG is prepended). Never inline prompts. After any engine or
   config change: `python3 Artists/engine/selftest.py`.
4. **Never publish/upload/distribute.** Bandcamp AI ban + Spotify disclosure
   question is an unresolved open decision in HANDOFF.md.
5. Suno rules that cost real time to learn: non-custom mode + instrumental only
   (custom_mode sings the style words); genre descriptors, never living-artist
   names (content filter kills the job); refs are prompt intelligence only,
   never audio-seeded.

## Command crib (run from `MattZerg/Artists/`)
| Verb | Command |
|---|---|
| Check credits | `python3 engine/credits.py` |
| Preview a batch (free) | `python3 engine/run_batch.py --artist <slug> [--lanes a,b] --dry-run` |
| Run a batch (SPENDS, gated) | `python3 engine/run_batch.py --artist <slug> --lanes <lane> --n 1` |
| A&R state | `python3 engine/ledger.py show --artist all [--pending]` (or read `<slug>/ledger.md`) |
| Record Matt's verdict | `python3 engine/ledger.py verdict <track_id> keeper\|killed --note "..."` |
| Decision montage + cue sheet | `python3 engine/make_montage.py --artist <slug> --decision` |
| EP preview + tracklist | `python3 engine/assemble_ep.py --artist <slug>` |
| EP final exports (all-keeper gate) | `python3 engine/assemble_ep.py --artist <slug> --final --mp3` |
| New artist | `python3 engine/new_artist.py <slug> --name "NAME" --prefix XX` |
| Engine sanity after changes | `python3 engine/selftest.py` |

## Where things live
- `Artists/HANDOFF.md` — history, WHAT FAILED, open decisions (read first)
- `Artists/<slug>/artist.toml` — steering · `ledger.jsonl`/`ledger.md` — A&R state
- `Artists/<slug>/auditions/` — versioned reels + cue sheets for Matt
- `Artists/<slug>/releases/<CATALOG>/ep.toml` — sequence · previews/tracklists beside it
- `Artists/<slug>/batches/batch-*.json` — generation manifests (payload, jobIds, credits before/after)

## Typical loops
**A&R round:** montage `--decision` → Matt listens against the cue sheet →
`ledger.py verdict` per track → if a lane died, `run_batch.py --lanes <lane>`
(gated) → repeat until all EP slots are keepers.

**EP close:** edit `ep.toml` order/titles → `assemble_ep.py` preview → Matt
approves sequence → `--final --mp3`.

**New sibling:** `new_artist.py` → fill artist.toml lanes + negatives (push AWAY
from existing siblings) → brief from stub → `--dry-run` → gated first batch.
