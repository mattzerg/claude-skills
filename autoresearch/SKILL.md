---
name: autoresearch
description: Measure a skill's quality + cost on a frozen set of golden cases, and A/B a candidate edit so you keep only validated improvements (higher pass-rate, or equal pass-rate at lower token cost). The Karpathy autoresearch pattern — frozen eval + editable target + keep-only-wins + a log of everything tried — applied to skill improvement. USE PROACTIVELY before/after editing any skill ("is this edit actually better?", "did my change regress the skill?", "tune this skill", "A/B these two SKILL.md versions"), or as the scorer in an autonomous improvement loop. Also reusable for any editable-artifact + frozen-metric loop (email reply-rate, landing conversion).
---

# autoresearch

Stop improving skills by vibes. This harness gives the missing piece: an objective,
repeatable measurement of a skill against golden cases, and an A/B that keeps a
candidate edit only when the numbers actually improve.

Adapted from `karpathy/autoresearch` (evaluated 2026-06-07 — see
`MattZerg/Skills/setup-ideas-evaluation-2026-06.md`). Complements Matt's existing
`skill_timing.py` / `audit_skills_usage.py` (which measure *live* usage) — this
measures a skill *under controlled cases*, with keep/revert.

## Usage

```bash
# Measure a skill on its golden cases (smoke/no-spend default runner = echo)
python3 ~/.claude/skills/autoresearch/run.py eval \
    --skill grill-me --cases ~/.claude/skills/autoresearch/examples/grill-me.cases.yaml \
    --runner claude

# A/B a candidate edit; prints KEEP/REVERT, restores the original automatically
python3 ~/.claude/skills/autoresearch/run.py ab \
    --skill grill-me --cases <cases.yaml> --variant /tmp/grill-me.candidate.md \
    --runner claude

# On a KEEP, write the variant live:
python3 ~/.claude/skills/autoresearch/run.py ab ... --variant ... --apply
```

**Runners:** `echo` (no-spend smoke — verifies the harness; assertions on prompt
text still work), `claude` (`claude -p`), `zclaude` (account-routed). Real
measurement needs `claude`/`zclaude`.

**Metric:** pass-rate (primary) → mean est-tokens (tiebreak, lower wins beyond
`--tol`, default 2%) → mean wall. A/B always restores the original SKILL.md before
deciding; `--apply` is the only thing that writes it live.

## Cases file (the frozen eval)

YAML or JSON list. Each case: a `prompt` + one assertion:
- `expect: ["substring", ...]` — all must appear in the output
- `expect_regex: "..."` — regex must match
- `expect_absent: [...]` — none may appear (regression guard)

Example: `examples/grill-me.cases.yaml`.

## The loop

See `PROGRAM.md` — baseline → hypothesize one change → A/B → keep wins only → log →
repeat. **Do not edit the golden cases to pass** (that's overfitting). Change one
thing per experiment.

## Anti-patterns
- Don't chase a skill that's already 1.0 pass-rate at low cost — churn isn't improvement.
- Don't compound edits in one A/B — you won't know which change mattered.
- Don't trust a KEEP on a 1-case eval; use ≥3 cases so a single flake can't flip it.
- Real spend: `claude`/`zclaude` runners invoke the model per case — keep case sets small.
