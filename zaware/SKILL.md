---
name: zaware
description: "Work-awareness toolkit — ask the system about projects, people, and what to look at. Built for the system roadmap (entity-resolver-backed). Verbs — `project <name>` (state-of-X dossier: standup cadence + real PRs + people), `ask \"<question>\"` (NL \"what's the state of X / what is Idan on\"), `who <person>` (their projects + repos + PR activity), `anomalies` (proactive \"what to look at\": quiet projects, dropped-off people, aging decisions), `roster`, `refresh` (re-mine standup + people-graph), `health` (repeat-correction rate + log-repair loop + memory parity). USE PROACTIVELY when Matt asks \"what's the state of <project>\", \"what is <person> working on\", \"what should I look at\", \"what went quiet\", or wants project/client/workflow awareness. Personal/work — reads local mined corpora; never posts."
---

# zaware — work-awareness toolkit

One front door to the awareness + measurement tools (all in `~/.config/zerg/`, entity-resolver-backed).

## Run
```bash
python3 ~/.config/zerg/zaware.py <verb> [args]
```

## Verbs
| Verb | What | Tool |
|---|---|---|
| `project <name>` | state-of-X dossier (standup cadence + real PRs + resolved people; fakeidan paste-backs filtered) | `zstate_deep.py` |
| `ask "<question>"` | NL question over awareness data, cite-or-abstain | `ask_system.py` |
| `who <person>` | person → projects + repos + PR activity (A1-resolved) | `people_graph.py` |
| `anomalies` | proactive "what to look at": quiet projects, dropped-off people, aging decisions | `anomaly_brief.py` |
| `roster` | full people roster ranked by activity | `people_graph.py` |
| `refresh` | re-mine #standup + rebuild people-graph | `standup_miner.py`, `people_graph.py` |
| `health` | repeat-correction rate + log-repair loop + memory parity | measurement scripts |

## Data
- `~/.zerg/awareness/standup_projects.jsonl` (A3 #standup mine), `people_graph.jsonl` (I8)
- `~/.claude/state/{gh_corpus,slack_corpus,decisions_pending.jsonl}`
- Entity resolution: `~/.config/zerg/entity_resolver/` (A1 keystone)

## Notes
- Read-only over local corpora. Never posts to shared surfaces.
- `refresh` is on-demand; an auto-refresh cron + a morning-brief anomaly block are persistence installs (need explicit auth).
- Canonical roadmap: `MattZerg/Projects/Zerg-Production/System-Roadmap/`.
