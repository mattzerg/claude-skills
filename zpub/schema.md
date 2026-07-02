# zpub Entity Schema

Each publishing entity lives at `MattZerg/Projects/Zerg-Production/Growth/publishing/<id>.md` as YAML frontmatter + free-form body.

## Frontmatter contract

```yaml
---
id: pub-2026-05-zergchat-launch-blog          # required, slug-safe, used as filename
title: "ZergChat Launch Announcement"          # required
type: blog                                     # required; one of:
                                               #   blog | launch | case-study | web-page
                                               #   | video | email | social | one-pager | other
status: review                                 # required; one of:
                                               #   ideating | drafting | review
                                               #   | scheduled | published | distributed | archived
publish_target: 2026-05-15                     # required ISO date; drives RAG date logic
publish_actual: null                           # ISO date set when published
date_confirmed: false                          # default false. Set true ONLY after human says yes.
                                               # Required before status can advance to `scheduled`.
                                               # Per feedback_launch_dates_aspirational.md — target_date is
                                               # aspirational until explicit human confirmation.
owner: matthew                                 # matt | matthew | idan | andre | etc
surfaces:                                      # optional list of where this lives
  - kind: blog
    path: ~/zerg/web/src/public/content/blog/zergchat-launch.md
  - kind: linkedin
    state: scheduled
gates:                                         # per-gate status; key = gate name, value =
  fakematt_copyedit: pending                   # passed | pending | failed | n_a
  fakeidan: n_a
  signoff: pending
  prod_deployed: pending                       # blog/launch only — content SHA reachable from origin/main on the prod site
blockers:                                      # optional list of free-text blockers
  - "Waiting on Idan numbers signoff"
links:                                         # optional list of {label, url}
  - label: Draft
    url: ~/zerg/web/src/public/content/blog/zergchat-launch.md
zergboard_card_id: null                        # set on first sync push
updated_at: 2026-05-10T14:32:00Z               # ISO8601, drives conflict resolution
---

# Free-form body / context for this entry
```

## Defaults applied on `zpub add`

- `id` derived from `<YYYY-MM>-<slug-of-title>` prefixed with `pub-`
- `status` defaults to `drafting`
- `publish_target` required
- `owner` defaults to `matthew`
- `gates` populated from `gates.json` for the chosen `type`, all set to `pending` (or `n_a` if not in the type's required-gate list)
- `updated_at` = now (ISO8601 UTC)

## RAG computation

```
RED if:
  (publish_target < today AND status not in [published, distributed, archived])
  OR any gate value == "failed"
  OR blockers is non-empty

AMBER if (and not RED):
  publish_target within 3 days of today
  OR any required gate is "pending"

YELLOW if (and not RED/AMBER):
  status in [review, scheduled]
  AND (any required gate "pending" OR status == scheduled AND not date_confirmed)

GREEN otherwise
```

## Schedule guard

`zpub set <id> status scheduled` REFUSES unless ALL of:
- `date_confirmed: true` is set on the entry (set via `zpub set <id> date_confirmed true`)
- every required gate per `gates.json` is `passed` or `n_a`

Override with `--force` (requires explicit human YES per
`feedback_publish_status_explicit_yes.md` + `feedback_launch_dates_aspirational.md`).

## Gate-state consistency invariants

`zpub set` refuses any mutation that would leave the entry internally
contradictory. The invariants (enforced by `pipeline.validate_gate_consistency()`):

- `signoff == "passed"` requires `fakeidan == "passed"` AND
  `ledger_clean in {passed, n_a}` AND `imagery_quality in {passed, n_a}`.
- `prod_deployed == "passed"` requires `signoff == "passed"`.
- `status == "scheduled"` requires `date_confirmed == true` AND
  `fakeidan in {passed, n_a}` AND `signoff in {passed, n_a}`.
- `status == "published"` requires `prod_deployed == "passed"`.

Override with `--force-inconsistent` (logged to `_meta/conflicts.log`,
reserved for migration; requires explicit human YES). See
`~/.claude/plans/synchronous-yawning-storm.md` Part A1.

## Visual cue for pencilled dates

A `publish_target` date is "pencilled" when `date_confirmed == false`.
The render wraps such dates in parens — `(May 19)` — and emits a one-line
legend at the top of the table:

```
legend: (parenthesized dates) are pencilled, not confirmed — do not treat as commitments
```

Additionally, when status is `review` AND target is within 3 days AND
`date_confirmed == false`, the RAG color bumps from YELLOW down to AMBER
so the entry reads as uncertain, not ready to ship.

## Status → Zergboard column mapping

| status | column |
|--------|--------|
| ideating, drafting | Drafting |
| review | Review |
| scheduled | Scheduled |
| published, distributed | Published |
| archived | Archived |

## Priority → Zergboard priority

| RAG | priority |
|-----|----------|
| RED | urgent |
| AMBER | high |
| GREEN | medium |
