---
name: zergaudience-skill
description: Read-only access to Zerg's canonical contact + signup data inside ZergAudience (`~/zerg/zergaudience/`). Every signup / waitlist entry / newsletter sub / contact-form ping across the zstack lands here, so this is the source of truth for "who is paying / on the waitlist / inbound" — NOT a separate CRM. Verbs — `summary` (workspace-level counts), `recent [--days N]` (new contacts), `for-product <slug>` (filter by primary_source_product), `for-source <source>` (account_creation/newsletter_form/contact_form/inbound_email/waitlist/csv_import/api), `lookup <email-or-substring>` (find a contact). Connects via psql against `$ZERGAUDIENCE_DATABASE_URL` or defaults to local `postgres://localhost/zergaudience`. Pairs with growth-dashboard / morning-brief / standup — feed real signup signal into the weekly dashboard.
---

# zergaudience-skill

Read-only psql wrapper against the ZergAudience `contacts` table. **This is today's canonical answer to "who signed up / who is in the pipe."** ZergCRM is positioning-doc only; contact data really lives here.

## Setup

Reads from Postgres. By default connects to `postgres://localhost/zergaudience?sslmode=disable` (matches ZergAudience local-dev convention). Override with:

```bash
export ZERGAUDIENCE_DATABASE_URL='postgres://...'
```

For prod read access, get a read-only Fly Postgres URL from Idan and export it.

## Verbs

### `summary [--ws zerg]`
Workspace count rollup — total contacts, by `primary_source`, by `status`, last 7d / 30d signups.

```bash
python3 ~/.claude/skills/zergaudience-skill/read_audience.py summary
```

### `recent [--days N] [--limit N]`
New contacts in the last N days (default 7), newest first.

```bash
python3 ~/.claude/skills/zergaudience-skill/read_audience.py recent --days 7
```

### `for-product <product>`
Filter by `primary_source_product` — e.g. `zergboard`, `zergvert`, `zergai`, `tycoon`.

```bash
python3 ~/.claude/skills/zergaudience-skill/read_audience.py for-product zergvert
```

### `for-source <source>`
Filter by `primary_source` — one of `account_creation`, `newsletter_form`, `contact_form`, `inbound_email`, `waitlist`, `csv_import`, `api`.

```bash
python3 ~/.claude/skills/zergaudience-skill/read_audience.py for-source waitlist
```

### `lookup <email-or-name>`
Find a contact by email substring or first/last name.

```bash
python3 ~/.claude/skills/zergaudience-skill/read_audience.py lookup "idan"
```

## Output

Per-row: `[first-seen] <email>  <first> <last>  src=<source>  product=<product>  utm=<first-source>  status=<status>`.

## When to use

- **PROACTIVELY** before claiming "no one is on the waitlist for X" or "no signups today."
- `growth-dashboard` weekly run — replace mock signup numbers with real query.
- `morning-brief` — surface new signups from overnight.
- `standup` — populate Marketing lane's "<N> new waitlist signups for <product>."
- prospect/BD triage — check if a target lead has already signed up somewhere.

## Read-only

Issues only `SELECT` statements. Never `INSERT`, `UPDATE`, `DELETE`, `DROP`. If `$ZERGAUDIENCE_DATABASE_URL` points at a writable role, that's not enforced here — keep DB hygiene by using a read-only role for the var.

## Reference

- Schema: `~/zerg/zergaudience/db/schema.sql`
- Audience taxonomy: `MattZerg/Projects/Zerg-Production/Zstack/zergaudience-audience-taxonomy.md`
- Project memory: `feedback_zstack_subsumes_external_tools.md` — ZergAudience is the canonical lifecycle/CRM today.
