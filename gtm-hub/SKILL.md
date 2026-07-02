---
name: gtm-hub
description: Unified Zerg GTM operating system. Source of truth for every growth/marketing/content/publishing/sales entity (experiments, content, prospects, BD targets, launches, themes, metrics, workstreams) at `MattZerg/Projects/Zerg-Production/Growth/`. Per-entity markdown files with YAML frontmatter, cross-entity flat index, action-led decision engine, auto-regenerated canonical view at `Growth/README.md`. USE PROACTIVELY whenever Matt asks "where are we on growth", "what needs my decision this week", "what's the GTM state", or before any growth/marketing/launch planning conversation. Pairs with experiment-tracker (writes experiments/), zerg-prospecting (writes prospects/), bd-tracker (writes bd/), content-calendar (writes content/) — eventually subsumes their write paths in Phase 2.
---

# Zerg GTM Hub

Single source of truth + action engine for Zerg's growth/marketing/content/publishing/sales work. Replaces the scattered ledger pattern (`experiments.md`, `prospects.md`, `bd-targets.md`, `content-calendar.md`) with per-entity files under `MattZerg/Projects/Zerg-Production/Growth/` and an auto-regenerated canonical `README.md`.

## Entity types

| Type | Directory | Source |
|---|---|---|
| experiment | `experiments/` | Existing per-file (formalized) |
| content | `content/` | Existing per-file (formalized) |
| prospect | `prospects/` | Split from `prospects.md` |
| bd_target | `bd/` | Split from `bd-targets.md` |
| launch | `launches/` | NEW — tracks `Writing/Launches/` state |
| theme | `themes/` | NEW — `themes.md` becomes index |
| metric | `metrics/` | NEW — one file per KPI w/ history |
| workstream | `workstreams/` | Mirror of `~/.claude/workstreams/state.json` |
| publishing | `publishing/` | NEW — owned by `zpub` skill; bidir-synced to Zergboard "Publishing" board (PUB-*); see `~/.claude/skills/zpub/` |
| launch_backlog | `launch-backlog/` | NEW — serial-launch candidate queue; per-slot files filled by Matt, consumed by `zerg-new-product.sh` bootstrap + `dogfood-walkthrough` picker |
| dogfood | `dogfood/` | dogfood walkthrough state per product (genre-relaxed; non-envelope `_active.txt` + per-product logs) |
| measurement | `measurement/` | per-product Zergalytics measurement spec (genre-relaxed; `<slug>.yaml` files, consumed by funnel-analyzer + growth-dashboard) |

Schema contract: `MattZerg/Projects/Zerg-Production/Growth/_meta/schema.md`.

## Commands

```
gtm-hub regenerate                            rebuild index → decisions → README.md
gtm-hub decisions                             print just the action-led panel
gtm-hub status [TYPE] [--filter status=X]     query state (e.g., status bd --filter status=engaged)
gtm-hub log <ID> <FIELD>=<VALUE> ...          structured update (writes file + reindex)
gtm-hub new <TYPE>                            scaffold new entity with valid frontmatter
gtm-hub audit                                 schema drift, missing kill_dates, stale entities
gtm-hub post                                  weekly digest post to FM→Matt DM (D0B0T0ETDR8)
gtm-hub migrate [--dry-run]                   one-shot migration runner (idempotent)
```

Dispatcher: `python3 ~/.claude/skills/gtm-hub/run.py <command> [args]`.

## Architecture

```
Growth/
├── README.md                ← auto-regenerated canonical view
├── _meta/
│   ├── schema.md              frontmatter contract
│   ├── index.json             cross-entity flat index
│   ├── decisions.json         derived "decisions needed this week"
│   └── render-config.yaml     section ordering + visibility
├── experiments/             exp-NNN.md files (existing)
├── content/                 <slug>.md files (existing)
├── prospects/               <slug>.md files (NEW)
├── bd/                      <slug>.md files (NEW)
├── launches/                <slug>.md files (NEW)
├── themes/                  <slug>.md files (NEW)
├── metrics/                 <slug>.md files (NEW)
├── workstreams/             <slug>.md files (NEW)
├── launch-backlog/          slot-N.md files (NEW) — serial-launch candidate queue
├── dogfood/                 _active.txt + per-product logs (NEW, genre-relaxed)
└── measurement/             <slug>.yaml specs (NEW, genre-relaxed)
```

Skill code:

```
~/.claude/skills/gtm-hub/
├── SKILL.md                 (this file)
├── run.py                   command dispatcher
└── scripts/
    ├── lib/
    │   ├── __init__.py
    │   ├── frontmatter.py   YAML parse/render (no deps)
    │   ├── schema.py        entity type contracts + validation
    │   ├── entities.py      load_all() walker over Growth/
    │   └── rules.py         decision rules (pure functions)
    ├── index.py             build _meta/index.json
    ├── decisions.py         build _meta/decisions.json
    ├── render.py            rewrite Growth/README.md
    ├── migrate.py           split bulk ledgers → per-file
    ├── audit.py             schema drift + stale entity checks
    └── post.py              Slack weekly digest
```

## Action-led rendering

Top panel of `README.md` is the **decisions panel** — ≤5 items, by priority weight, surfaced from `decisions.json`. Rules:

| Rule | Trigger |
|---|---|
| Kill-date approaching | experiment kill_date − today ≤ 7d, status=running |
| Kill-date passed | experiment kill_date < today, status=running |
| Stale BD touch | bd_target last_touch > 14d, status ∈ {outreach, engaged} |
| Qualified prospect, no proposal | prospect status=qualified, !proposal_out_at |
| Content ready, no schedule | content status=reviewed, !scheduled_date OR past |
| Launch ready | launch state=ready, !ship_date |
| Metric red | metric value=null AND instrumentation_owner=matt |
| Workstream stale | workstream last_activity > 14d, status=hot |

Healthy sections hide (`feedback_dashboard_must_drive_action.md`). ASCII bars + tables per `feedback_ascii_layout_patterns_library.md`.

## Cadence

- Hourly: `regenerate` via cron (`~/.claude/fakematt-today/gtm_hub_regenerate.py`) — only rewrites README/index/decisions if state changed.
- Weekly Monday 7am PT: `post` to FM→Matt DM.
- Phase 2: subsume `growth-dashboard`, `fm-ops`, `morning-brief` outputs into unified briefs.

## Reuse anchors

- Frontmatter parser pattern: `~/.claude/skills/experiment-tracker/run.py:44`
- Per-file + index.json: `~/.claude/skills/idea-backlog/scripts/`
- Slack DM post: `~/.claude/skills/growth-dashboard/run.py` (FM→Matt DM `D0B0T0ETDR8`)
- `make_client()` Anthropic OAuth for any LLM-touched paths
