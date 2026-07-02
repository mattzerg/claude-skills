# Skill Graveyard Archive — 2026-06-10 (Agent-C early pass)

Executed as Agent-C (Skills) of Matt's approved system-hygiene plan. Branch: `skills-graveyard-2026-06-10` (cut from `matt/gtm-hub-debt-section` HEAD; Matt's uncommitted feature work left unstaged and untouched).

Plain-copy safety backup (pre-move, includes untracked config files): `~/Backups/skills-graveyard-2026-06-10/`.

## Selection rule

`disabled in settings.json skills.disabled` AND `0 fires in window` (per `~/.zerg/effectiveness/skill_fire_rates_latest.csv`) AND **no reference** in: crontab, `~/Library/LaunchAgents/*.plist`, `~/.claude/agents/*.md`, settings.json hooks, settings.local.json, `~/.claude/hooks/*`, any surviving skill's files (enabled SKILL.md + kept-disabled skills' md/py/sh — fixpoint check), codex sync script, `~/zerg/claude-skills-private/sync.sh`, `~/.config/zerg-guard/lib/*.py`, `~/.claude/fakematt-today/*.py`, `~/.codex/skills/` mirror.

54 disabled → 10 archived, 44 kept (36 traced + 8 fixpoint-blocked).

## Archived (10)

| Skill | Notes |
|---|---|
| `alexa-skill` | was "keep-on-hand" in 2026-06-01 pass; untraced, 0-fire |
| `amazon-skill` | was "keep-on-hand"; untraced, 0-fire |
| `blink-skill` | was "keep-on-hand"; untraced, 0-fire |
| `brand-guide-creator` | 1 fire 2026-05-07 (pre-disable); untracked-only in git, added fresh |
| `fal-music-skill` | untraced, 0-fire; `config.json` kept on disk, NOT committed |
| `gif-builder` | was "keep-seasonal"; untracked-only in git, added fresh |
| `notion-skill` | untraced, 0-fire; `config.json` + `oauth_client.json` kept on disk, NOT committed (credentials) |
| `suno-skill` | untraced, 0-fire |
| `twilio-sms` | was "keep-on-hand"; untraced, 0-fire |
| `wyze-skill` | was "keep-on-hand"; untraced, 0-fire |

## Un-archive

`git mv _archive/graveyard-2026-06-10/<name> <name>` (or `git revert` the archive commit). Settings.json `skills.disabled` was intentionally NOT edited — entries for archived skills are inert.

## Kept-but-disabled highlights (traced)

- `growth-dashboard`, `experiment-tracker` — **live crontab jobs run their run.py weekly/daily**
- `zergguard-state` — LaunchAgent `com.matteisner.zergguard-weekly` executes its dashboard.py
- `zergguard-audit` — referenced by `~/.config/zerg-guard/lib/daily_monitor.py`
- `zmail` — referenced by `~/.claude/hooks/external_action_gate_hook.py` + mining_to_composite.py
- the Zstack terminology skill (last entry in skills.disabled) — referenced by two terminology hooks in `~/.claude/hooks/`
- `fm-corrected`, `fm-ops`, `bd-tracker` — referenced by fakematt-today daemons
- video cluster (`video-*`, `caption-burn`, `capture-validator`, `film-maker-skill`, `eleven-labs-skill`) — composed by enabled `product-launch-video`, `creative-prereq`, `qa-gate`, `ship-gate`, `review-pack`
- `google-sheets-skill` — code-level dependency of `google-slides-skill/slides_skill.py`
