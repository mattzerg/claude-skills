# gtm-hub — daily-use reference

The 1-sentence pitch: the hub is a unified GTM operating system — one place that
tracks every growth/marketing/content/sales/publishing entity at Zerg, surfaces
the decisions you need to make, and propagates one decision through every
downstream entity that should reflect it.

See [`SKILL.md`](./SKILL.md) for the structural overview. This file is the
how-do-I-use-it reference for daily-use commands and common workflows.

## The 4 commands you'll actually run

| When you want… | Run |
|---|---|
| Morning-of: full picture in one glance | `gtm-hub overview` |
| Just the decisions on your plate | `gtm-hub decisions` |
| Is the hub healthy? Are crons running? | `gtm-hub doctor` |
| Force a fresh README + index + decisions | `gtm-hub regenerate` |

Everything else (mutation verbs, queries, sync, migrate) is below.

In Slack, type any of these prefixed with `gtm` in your FM-Matt DM
(`D0B0T0ETDR8`). The Slack listener picks it up within 5 minutes and replies
with the same output you'd see in terminal.

## The decision-to-action loop

This is the daily workflow the hub was built around.

```
1.  Read morning brief (7am M-F)              — top 2 decisions appear inline
2.  `gtm-hub overview`                        — see all 7 with deadlines + options
3.  Pick one, dry-run the cascade             — `gtm-hub decide <id> <option> --dry-run`
4.  Apply                                     — same command without --dry-run
5.  Hub auto-regenerates                      — projects that referenced the decision
                                                drop it from `derived_blockers`,
                                                effective_rag re-computes
6.  Tomorrow's brief shows 1 fewer decision   — loop
```

### Live example

```bash
gtm-hub decide dec-zergboard-launch-framing zergboard --dry-run
```

Output (truncated):
```
CASCADE (5 actions):
  would-set zergboard-launch.md: framing_lane=product-first
  would-append to zergboard-launch.md § Notes: Framing decided: Zergboard product-first
  would-set zergboard-public-launch.md: framing=product-first
  would-append to zergboard-public-launch.md § Notes: ...
  would-set proj-zergboard-launch.md: status=in-progress  ← unblocks the project
```

Drop the `--dry-run` to apply.

## How to add things

### A new decision

```bash
gtm-hub new decision --id dec-foo --title "Decide foo or bar?"
# Then edit the file to add question, options, deadline, cascade
```

The decision file lives at `Growth/decisions/dec-foo.md`. Edit
to add the substance. See `dec-zergboard-launch-framing.md` for a fully-specced
example with a cascade block.

### A new entity (any type)

```bash
gtm-hub new experiment   --id exp-NNN --title "Hypothesis X"
gtm-hub new content      --id <slug>  --title "Blog title"
gtm-hub new prospect     --id <slug>  --title "Account name"
gtm-hub new bd_target    --id <slug>  --title "Partner name"
gtm-hub new launch       --id <slug>  --title "Launch name"
gtm-hub new project      --id proj-X  --title "Initiative"
gtm-hub new metric       --id <slug>  --title "KPI name"
```

But: for **experiments**, **content**, **BD**, and **prospects**, prefer the
domain skill (`experiment-tracker register`, `content-calendar add`, etc.).
They write hub-compliant envelopes and carry additional anti-drift guardrails
(experiment-tracker refuses registration without kill_date + kill_threshold +
success_metric).

### A new project

Projects don't yet have a domain skill — use `gtm-hub new project` and edit
the file. Required fields:

```yaml
id: proj-<slug>
type: project
title: "Initiative name"
status: planned         # planned | in-progress | blocked | shipped | paused
owner: matt
rag: amber              # author's view; system can promote but not demote
target_date: 2026-06-15
linked_entities:
  - decisions/dec-X.md
  - launches/<slug>.md
  - content/<slug>.md
```

Once linked_entities is populated, `derived_blockers` and `blocks_projects`
auto-compute on next regen.

## Common verbs (full list)

```
gtm-hub regenerate                            rebuild index → decisions → README → ledgers
gtm-hub dashboard                             at-a-glance state
gtm-hub overview                              dashboard + decisions + projects + triage + debt
gtm-hub decisions                             open + rule-triage decisions
gtm-hub projects                              active projects w/ derived blockers
gtm-hub status [TYPE] [--filter F=V]          query entities
gtm-hub log <id> KEY=VALUE ...                structured frontmatter update
gtm-hub act <verb> <id> [args]                semantic action (qualify/kill/publish/...)
gtm-hub decide <id> <option-key> [--dry-run]  record decision + cascade
gtm-hub defer <id>                            mark decision deferred
gtm-hub new <type> --id X --title "..."       scaffold
gtm-hub audit                                 schema drift + envelope check
gtm-hub doctor                                end-to-end health (cron, mirror, LaunchAgents)
gtm-hub post [--post]                         weekly Slack digest (dry-run default)
gtm-hub regen-ledgers                         rewrite prospects.md/bd-targets.md/experiments.md
gtm-hub migrate [--dry-run]                   one-shot bulk-ledger → per-entity split
gtm-hub web                                   stage dist/ for Fly deploy
gtm-hub zergboard sync                        pull cards into _meta/zergboard-cards.json
gtm-hub zergboard create <id>                 create one card for a hub entity
gtm-hub zergboard create-missing --type T --status S,S
```

## Cascade spec format

Decisions can carry an optional `cascade` block. When `gtm-hub decide <id>
<option>` runs, the matching cascade applies — `set` (frontmatter field
updates) and `append` (text into named markdown sections) on each referenced
entity.

```yaml
cascade:
  <option-key>:
    - entity: <id-or-relpath-or-abspath>
      set:
        field_a: value_a
        field_b: value_b
      append:
        Notes: "2026-05-11 — line to add under ## Notes"
    - entity: <next entity>
      ...
```

The cascade engine resolves entity refs in this order:
1. Exact entity id (`dec-foo`, `proj-bar`, etc.)
2. Growth-relative path (`launches/zergboard.md`)
3. Absolute path

Mirror-side reads are mapped to canonical iCloud writes — you never need to
worry about iCloud vs mirror paths at the cascade level.

## Common-issue fixes

### Doctor shows 🔴 cron health + 🔴 launchd agents

The 3 LaunchAgents need FDA-bearing parentage. Run install.sh **from
Terminal.app** (not from Claude Code, not via cron):

```bash
~/.claude/skills/gtm-hub/launchd/install.sh
```

This is idempotent — safe to re-run. It bootouts existing agents, copies the
plists, bootstraps with FDA inherited from your interactive shell, comments
out matching crontab entries. About 5 seconds total.

Verify with:
```bash
launchctl kickstart -k gui/$(id -u)/com.matteisn.gtm-hub-regenerate
tail -5 ~/.claude/fakematt-today/gtm_hub.log
```

A clean `wrote .../index.json — N entities` (no PermissionError) confirms it.

### Doctor shows 🟡 index freshness

Index is more than 60 min old. Either:
- LaunchAgent isn't running → run install.sh
- Run `gtm-hub regenerate` once manually to refresh

### Doctor shows 🔴 vault mirror

The `~/.zerg-vault-mirror/` LaunchAgent isn't syncing. See
[`project_vault_mirror.md`](../../projects/.../memory/project_vault_mirror.md)
in memory for the bootstrap procedure. Mirror is what makes the hub
cron-readable.

### Decision file looks broken in panel

Run `gtm-hub audit`. The validator catches missing envelope fields and bad
status values. Open the file, fix the flagged field, re-run audit. If the file
has zpub-style frontmatter (genre `type:`, `updated_at` timestamps), it's
loose-validated — only `id`, `title`, `status`, `owner` are required.

### gtm-hub command unrecognized in Slack

The listener hasn't loaded yet, or it crashed. Check:
```bash
launchctl list | grep matteisn.gtm-hub-slack-listener
tail -20 ~/.claude/fakematt-today/gtm_slack.log
```

## File layout

```
~/.claude/skills/gtm-hub/
├── SKILL.md                  structural overview (this dir)
├── USAGE.md                  ← you are here
├── run.py                    command dispatcher (gtm-hub <command>)
├── launchd/                  LaunchAgent plists + install.sh
├── web/                      static SPA bundle + Fly.io deploy
└── scripts/
    ├── lib/
    │   ├── frontmatter.py    YAML parse/render
    │   ├── schema.py         entity contracts + validation
    │   ├── entities.py       READ_VAULT (mirror-tolerant) vs VAULT (canonical writes)
    │   ├── rules.py          decision rules → decisions.json
    │   ├── derived.py        cross-entity blockers, RAG, blocks_projects
    │   └── cascade.py        decision-cascade executor
    ├── index.py              build _meta/index.json
    ├── decisions.py          build _meta/decisions.json
    ├── render.py             rewrite Growth/README.md
    ├── doctor.py             end-to-end health check
    ├── audit.py              schema validator CLI
    ├── act.py                semantic action verbs
    ├── overview.py           comprehensive single-shot view
    ├── migrate.py            bulk-ledger → per-entity split
    ├── regen_ledgers.py      reverse: per-entity → bulk ledger
    ├── sync_zergboard.py     pull cards into cache
    ├── create_zergboard_card.py
    └── post.py               weekly Slack digest

MattZerg/Projects/Zerg-Production/Growth/
├── README.md                 auto-regenerated canonical view
├── _meta/
│   ├── index.json            cross-entity flat index
│   ├── decisions.json        derived decisions + backlog
│   ├── render-config.yaml    section ordering + row caps
│   ├── zergboard-cards.json  Zergboard card cache
│   └── schema.md             frontmatter contract
├── experiments/   content/   prospects/   bd/         per-entity files
├── launches/      themes/    metrics/     workstreams/
├── decisions/     projects/  publishing/
└── prospects.md   bd-targets.md   experiments.md      ← auto-regen'd bulk ledgers
```

## Wiring with sibling skills

| Skill | Relationship |
|---|---|
| `experiment-tracker` | Writes `experiments/<id>.md` w/ hub envelope. Use `register/log/conclude/start` instead of `gtm-hub new experiment` for the kill-date guardrail. |
| `content-calendar` | Writes `content/<id>.md` w/ hub envelope. Use `add/transition/slip` instead of `gtm-hub new content`. |
| `bd-tracker` | Reads/writes `bd/<id>.md` per-file (no longer the bulk ledger). |
| `zerg-prospecting` | `export` writes `prospects/<id>.md` directly. |
| `zpub` | Owns `publishing/<id>.md` (its own envelope; hub indexes read-only). |
| `growth-dashboard` | Legacy Mon-7am Slack post; gtm-hub's Mon-7:15am post is the side-by-side. Retire after 3-week comparison. |
| `morning-brief` | Embeds top-2 decisions inline via `_gtm_hub_rows()`. |
| `zergboard-skill` | gtm-hub `zergboard sync` + `zergboard create` shell out to this. |

## When to use the hub vs. direct entity edit

| Situation | Best path |
|---|---|
| Logging a touch on a BD target | `bd-tracker log "Target Name" --note "..."` |
| Registering a new experiment | `experiment-tracker register --name ... --kill-date ...` |
| Recording a decision you made | `gtm-hub decide <id> <option>` |
| Ad-hoc field update on any entity | `gtm-hub log <id> field=value` |
| Quick read of state | `gtm-hub overview` |
| Adding context to a decision file | edit the .md file directly, then `gtm-hub regenerate` |

## Memory anchor

The canonical session history of how the hub got built lives at
`~/.claude/projects/.../memory/project_gtm_hub.md` — 13 phases over a single
2026-05-10/11 build session. Read it to understand WHY a thing is shaped the
way it is. Read THIS file (USAGE.md) for WHAT to type to do something.
