---
name: zergboard-skill
description: Read and manage Zergboard cards, boards, and workspaces. Use when the user asks to check Zergboard, view cards, find tasks, check sprint/cycle status, manage work items, invite guests, or interact with their Zergboard boards from the CLI.
allowed-tools: Bash, Read
---

# Zergboard Skill — Card & Board Management

Read, search, and manage Zergboard cards via the REST API. Lists workspaces (organizations), boards, cards, comments; supports create / update / move / reorder; works with workspace members and per-board guests.

## First-Time Setup (~2 minutes)

### 1. Create an API token

In the Zergboard UI:

1. Sign in at https://zergboard.fly.dev (or your local instance)
2. Open the CLI README's instructions — or use the Zergboard CLI directly:

   ```bash
   cd zerg-stack/zergboard/cli/zb
   go build -o zb && ./zb login --email you@example.com --password '...'
   ./zb token create --name claude --org-id <org-id> --scopes org:read,org:write,org:admin
   ```

3. Copy the printed token (starts with `zb_`).

### 2. Save token

```bash
mkdir -p ~/.claude/skills/zergboard-skill
cat > ~/.claude/skills/zergboard-skill/config.json <<EOF
{
  "base_url": "https://zergboard.fly.dev",
  "api_token": "zb_..._...",
  "default_organization_id": "<optional-uuid>"
}
EOF
```

`base_url` defaults to `https://zergboard.fly.dev` if omitted. `default_organization_id` is optional — when set, commands that take a workspace can use the default. Tokens may also be workspace-bound (created with `--org-id`); when bound, every call must reference that workspace.

## Commands

All commands print JSON to stdout for easy piping.

### My cards

Cards assigned to me across every board I can see (workspace member or board guest).

```bash
python3 ~/.claude/skills/zergboard-skill/zergboard_skill.py my-cards [--status STATUS] [--limit N]
```

`--status`: `todo` · `in_progress` · `done` · `canceled`

### Workspaces

```bash
python3 ~/.claude/skills/zergboard-skill/zergboard_skill.py workspaces
```

### Boards

```bash
python3 ~/.claude/skills/zergboard-skill/zergboard_skill.py boards [WORKSPACE]
```

`WORKSPACE` accepts a workspace name, slug, or UUID; defaults to the configured `default_organization_id`.

### Cards on a board

```bash
python3 ~/.claude/skills/zergboard-skill/zergboard_skill.py cards BOARD [--status STATUS] [--priority P] [--limit N]
```

`BOARD` accepts a board UUID, name, or card prefix (e.g. `CES`).

### Card details

```bash
python3 ~/.claude/skills/zergboard-skill/zergboard_skill.py card CARD_ID
```

`CARD_ID` accepts the card UUID or its external id (e.g. `CES-1`).

### Cycles (sprints)

Active cycle:

```bash
python3 ~/.claude/skills/zergboard-skill/zergboard_skill.py cycle BOARD
```

All cycles for a board:

```bash
python3 ~/.claude/skills/zergboard-skill/zergboard_skill.py cycles BOARD [--limit N]
```

### Search

```bash
python3 ~/.claude/skills/zergboard-skill/zergboard_skill.py search "query" [--workspace WORKSPACE] [--board BOARD] [--limit N]
```

Substring match across title, description, and external id.

### Create a card

```bash
python3 ~/.claude/skills/zergboard-skill/zergboard_skill.py create BOARD --title "Title" \
  [--description "..."] [--priority urgent|high|medium|low] [--column "Backlog"] [--assignee EMAIL]
```

If `--column` is omitted the card is placed in the first column.

### Update a card

```bash
python3 ~/.claude/skills/zergboard-skill/zergboard_skill.py update CARD_ID \
  [--title "..."] [--description "..."] [--priority P] [--due 2026-05-01] [--estimate 3]
```

### Move a card to a different column

```bash
python3 ~/.claude/skills/zergboard-skill/zergboard_skill.py move CARD_ID --column "In Progress" [--position 0]
```

### Reorder cards within a column

```bash
python3 ~/.claude/skills/zergboard-skill/zergboard_skill.py reorder CARD1 CARD2 CARD3 ...
```

All cards must currently be in the same column. The first id ends up at the top of the lane.

### Comments

```bash
python3 ~/.claude/skills/zergboard-skill/zergboard_skill.py comments CARD_ID
python3 ~/.claude/skills/zergboard-skill/zergboard_skill.py comment CARD_ID --body "..."
```

### Invite a guest to a board

```bash
python3 ~/.claude/skills/zergboard-skill/zergboard_skill.py invite-guest BOARD --email guest@example.com [--role viewer|editor|admin]
```

If the email belongs to an existing user they're added immediately; otherwise an invite link is emailed.

## Output

All commands emit JSON. Card output includes:
- `external_id` — the human-readable id (e.g. `CES-1`)
- `title`, `description`
- `status`, `priority`, `state_kind`, `state_name`
- `column_name`
- `board_id`, `board_name`, `board_card_prefix`
- `organization_id`, `organization_name`

## Status / Priority values

Status (board state kind):
- `todo` — Not yet started
- `in_progress` — Active work
- `done` — Completed
- `canceled` — Won't do

Priority:
- `urgent`
- `high`
- `medium`
- `low`

## Requirements

Python standard library only.

## Security

- Tokens don't expire by default but can be revoked from the Zergboard UI under workspace settings → API tokens.
- Stored locally in `~/.claude/skills/zergboard-skill/config.json`.
- Workspace-bound tokens cannot reach boards in other workspaces.

## Related

- API surface: `zerg-stack/zergboard/README.md`
- Zergboard repo: `zerg-stack/zergboard`
- CLI source: `zerg-stack/zergboard/cli/zb` (Go + Bubble Tea)
