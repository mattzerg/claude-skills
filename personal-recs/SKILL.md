---
name: personal-recs
description: Matt's explainable, cross-domain personal recommendation engine (watch / cook / travel / read / music). Reads the Unified Taste Archive (`MHE/Personal/Taste-Archive/taste-archive.yaml`) + operating profile, and emits recommendations where EVERY rec cites its evidence from the mined corpus. Verbs — `recommend [domain]` (serve/regenerate recs), `daily` (one rotating cross-domain pick for the morning brief), `feedback <rec> <up|down>` (log a rating to tune future recs), `refresh` (regenerate recs after new data lands). USE PROACTIVELY when Matt asks "what should I watch/cook/read", "where should I travel", "recommend me something", "today's pick", or after new taste data is mined. Personal vault only — never post to Zergboard/Slack/public Zerg surfaces.
---

# personal-recs

Explainable, cross-domain recommendation engine over Matt's mined taste corpus. The differentiator vs. Spotify/Netflix is **explainability + cross-domain** ("AI-as-CFO applied to taste") — every rec must cite the evidence that produced it.

## Data (read these)
- **Taste-graph data layer (authoritative, generated):** `MHE/Personal/Taste-Archive/taste-graph.yaml` — entity counts, top entities by affinity, cross-source confirmation counts, and data leaderboards (incl. music `top_artists_by_plays` from Spotify 2012→now). Generated from the taste-graph pipeline SQLite by `scripts/export_taste_archive.py`. **Source of truth for structured taste data.** Refreshed weekly + on `refresh`.
- **Taste archive (curated overlay):** `MHE/Personal/Taste-Archive/taste-archive.yaml` — hand-curated cross-source verdicts, producer identity, and signals the pipeline doesn't model (photo locations, IG creators). Read alongside the data layer; when numbers disagree, the generated `taste-graph.yaml` wins.
- **Current recs:** `MHE/Personal/Taste-Archive/recommendations.md`.
- **Profile:** `MattZerg/Notes/Data-Mining/Personal-Operating-Profile.md` + `profile-data.yaml` (deep tier; obfuscated).
- **Feedback log:** `MHE/Personal/Taste-Archive/recs-feedback.jsonl` (created by `feedback`).

## Verbs

| Verb | What it does |
|---|---|
| `recommend [domain]` | Show current recs (optionally filter: watch/cook/travel/read/music). To REGENERATE, read `taste-graph.yaml` (data) + `taste-archive.yaml` (curation) + feedback log, then produce fresh recs — each citing evidence — and rewrite `recommendations.md`. |
| `daily` | `python3 ~/.claude/skills/personal-recs/daily_pick.py` — prints ONE rotating cross-domain pick (date-seeded) for the morning brief. |
| `feedback "<rec text>" up\|down` | `python3 ~/.claude/skills/personal-recs/feedback.py "<rec>" <up\|down>` — appends to `recs-feedback.jsonl`. Down-rated patterns get downweighted on next regen. |
| `refresh` | Regenerate the data layer FIRST: `python3 -m scripts.export_taste_archive` (from the taste-graph project: `MattZerg/Research/datasets/taste-graph`) — this re-reads the pipeline SQLite into `taste-graph.yaml`. Then read it + feedback log and regenerate `recommendations.md`, noting what changed. The taste-graph weekly cron also runs this automatically. |

## Hard rules
- **Every rec cites its evidence.** No generic recs. Prefer entities with high cross-source confirmation (`sources` length in `taste-graph.yaml`) and high affinity.
- **Honor feedback.** Read `recs-feedback.jsonl` before regenerating; drop/downweight 👎 patterns, lean into 👍.
- **Privacy:** personal vault (MHE) only. Never surface on Zergboard/Slack/public Zerg surfaces. No sensitive financials/exact-location/relationships in recs.
- **Landed sources (2026-06-09):** Spotify (2012→now, `top_artists_by_plays`), Amazon orders, and Instagram saves are now mined into the data layer — music is no longer thin. **Still pending:** iTunes XML, Netflix watched-history, Goodreads, Uber — fold in on arrival.

## Integration points
- **Morning brief:** add a daily pick by calling `daily_pick.py` (one line) — see `daily_pick.py` header for the morning-brief snippet.
- **zhub:** `taste-graph.yaml` (generated) + `taste-archive.yaml` (curated) + `MattZerg/Notes/Data-Mining/profile-data.yaml` are the ingestable data layer.
- **Refresh cadence:** the taste-graph weekly LaunchAgent (`com.matteisn.taste-graph`, Sun) re-mines + regenerates `taste-graph.yaml` automatically; run `refresh` manually after a new export lands.
