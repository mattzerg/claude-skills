---
name: experiment-tracker
description: Register, track, and adjudicate growth experiments + A/B tests for the Zerg growth program. Refuses to register an experiment without kill_date + kill_threshold + success_metric (anti-drift guardrail). Reads/writes MattZerg/Projects/Zerg-Production/Growth/experiments.md (top ledger) + Growth/experiments/<id>.md (per-experiment YAML-frontmatter spec). Posts kill-decision prompts to Slack DM at kill_date − 2 ("Kill / scale-A / scale-B / extend? Reply 48h or auto-kill."). Inaction = kill, not extend. Generates RICE-scored backlog from positioning briefs + competitive matrix when asked. USE PROACTIVELY whenever Matt mentions starting an experiment, A/B test, hypothesis test, or "let's try X and see if it works" — and at every Monday RICE prioritization session.
allowed-tools: Bash, Read, Write
---


# Experiment Tracker Skill (v0 stub — Phase 1 Day 14–20 build)

The hypothesis-rigor + kill-discipline backbone of the Zerg growth program. Plan: `~/.claude/plans/i-am-planning-growth-splendid-bee.md`.

## Status

**v0 stub — not yet implemented.** Phase 1 Day 14–20 deliverable. S → M effort (small Phase 1, harden Phase 2).

## What it does

Registers, tracks, and adjudicates growth experiments. **Refuses registration** without the required hypothesis-form fields. Auto-fires kill-decision prompts. Generates RICE-scored backlog candidates from positioning briefs + competitive matrix.

## Modes

### register — start a new experiment

```bash
python3 ~/.claude/skills/experiment-tracker/run.py register \
  --name "homepage-hero-ab" \
  --hypothesis "If we lead with price, then signup conversion will rise because the $19 bundle clarifies value faster than agent-native framing" \
  --variant-a "agent-native hero" \
  --variant-b "price-led hero" \
  --success-metric "signup-conversion" \
  --success-threshold "+15%" \
  --kill-threshold "+3% or negative" \
  --kill-date 2026-05-26 \
  --sample-size 800 \
  --rice 224 \
  --problem P2
```

**Hard-fails** without `success_metric`, `success_threshold`, `kill_threshold`, `kill_date`. The discipline IS the value.

Writes `MattZerg/Projects/Zerg-Production/Growth/experiments/exp-NNN.md` with YAML frontmatter + decision_log section. Appends row to top-level `experiments.md`.

### read — show current experiment state

```bash
python3 ~/.claude/skills/experiment-tracker/run.py read [--id exp-NNN | --status running]
```

Returns the spec + decision log. Used by `growth-dashboard` to populate line #5.

### log — append a weekly read to an experiment

```bash
python3 ~/.claude/skills/experiment-tracker/run.py log --id exp-001 --read "Variant A: 12% conv. Variant B: 14% conv. n=420." --note "trending toward B"
```

Appends row to the experiment's decision_log.

### conclude — adjudicate a finished experiment

```bash
python3 ~/.claude/skills/experiment-tracker/run.py conclude --id exp-001 --verdict scale-B --learning "Price-led hero converts 16% better. Worth global rollout."
```

Sets status to `won` / `killed` / `inconclusive`. Triggers a follow-up Zergboard card if `scale-A` or `scale-B` is the verdict.

### prompt — fire kill-decision prompts

Cron entry:
```
0 9 * * *  python3 ~/.claude/skills/experiment-tracker/run.py prompt
```

Daily 9am. For each running experiment where `kill_date − 2 ≤ today`, posts to Matt's Slack DM:

> exp-001 (homepage-hero-ab) hits kill date 2026-05-26.
> Variant A: 12.1% (n=412). Variant B: 14.3% (n=408).
> Decision: kill / scale-A / scale-B / extend? Reply within 48h or auto-kill.

If no reply in 48h → auto-runs `conclude --verdict killed`.

### backlog — generate RICE-scored experiment candidates

```bash
python3 ~/.claude/skills/experiment-tracker/run.py backlog --from-positioning Marketing/PMM/zergboard-brief.md
```

Reads a positioning brief OR a competitive matrix file → drafts 5–10 hypothesis-shaped experiment ideas → user reviews → registers approved ones.

## YAML frontmatter schema (per-experiment file)

```yaml
---
id: exp-NNN
name: <short>
hypothesis: "If we [change], then [metric] will [direction] because [mechanism]"
variant_a: <description>
variant_b: <description>
traffic_split: 50/50
success_metric: <single named metric from dashboard>
success_threshold: <minimum effect size to declare win>
kill_threshold: <effect size below which to kill>
kill_date: YYYY-MM-DD
sample_size_target: <N>
RICE_score: <reach × impact × confidence / effort>
status: proposed | running | killed | won | inconclusive
problem: P1 | P2 | both
owner: Matt
created: YYYY-MM-DD
concluded: <YYYY-MM-DD or null>
verdict: <kill | scale-A | scale-B | inconclusive | null>
---
```

## Anti-drift contract

- **Refuses to register without `kill_date`, `kill_threshold`, `success_metric`.** No exceptions.
- **Pre-registers success metric** — no moving the goalposts post-data.
- **Concurrent experiment limit:** ≤8 in-flight. CLI warns at 7, refuses at 8.
- **Below 2 in-flight = dashboard turns red.**
- **`prompt` mode runs daily.** Inaction = kill, not extend.
- **Sample size discipline:** if `sample_size_target` exceeds expected traffic in `kill_date` window, CLI warns "test will likely be underpowered" and recommends scope reduction.

## Build phases

- **Phase 1 (Day 14–20):** v0 — `register`, `read`, `log`, `conclude` modes, file-based
- **Phase 1 (Day 22–28):** v0.1 — `prompt` mode + cron wired
- **Phase 1 (Day 25–30):** baseline 3 A/B tests registered (homepage hero, signup CTA, drip subject)
- **Phase 2 (Day 31–60):** v1 — `backlog` mode generating RICE candidates from positioning briefs
- **Phase 2 (Day 60–90):** v1.1 — sample-size calc + power analysis surfaced
- **Phase 3 (Day 91–180):** v2 — meta-analysis across concluded experiments → "what consistently wins"

## Implementation notes

- File-based, no DB
- Read existing `Growth/experiments.md` table; parse YAML frontmatter from per-experiment files
- Use `slack-skill` for `prompt` mode (channel `D0B0T0ETDR8`)
- Cache nothing — always re-read source of truth
- Status transitions: `proposed → running → (won | killed | inconclusive)`
