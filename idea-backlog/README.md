# idea-backlog skill

Categorized idea repository for Matt. Vault data lives at `MattZerg/Ideas/`. Spec at `MattZerg/Projects/idea-backlog.md`.

## Quick reference

```bash
# Capture a new idea
/usr/bin/python3 ~/.claude/skills/idea-backlog/scripts/capture.py \
  "Title :: optional one-line body" \
  --category product --tags zerg,growth --conviction high --effort m

# Recall (searches ideas + Tasks/inbox.md)
/usr/bin/python3 ~/.claude/skills/idea-backlog/scripts/recall.py "topic"

# Demote a stale Tasks/inbox.md row to an idea
/usr/bin/python3 ~/.claude/skills/idea-backlog/scripts/from_task.py "Brand pillars" --dry-run
/usr/bin/python3 ~/.claude/skills/idea-backlog/scripts/from_task.py "Brand pillars"

# Promote an idea to a task in Tasks/inbox.md
/usr/bin/python3 ~/.claude/skills/idea-backlog/scripts/to_task.py <idea-id> --bucket "To Do"

# Lifecycle
/usr/bin/python3 ~/.claude/skills/idea-backlog/scripts/touch.py <idea-id>
/usr/bin/python3 ~/.claude/skills/idea-backlog/scripts/promote.py <idea-id> --category content
/usr/bin/python3 ~/.claude/skills/idea-backlog/scripts/kill.py <idea-id> "reason here"

# Triage the inbox
/usr/bin/python3 ~/.claude/skills/idea-backlog/scripts/triage.py            # interactive
/usr/bin/python3 ~/.claude/skills/idea-backlog/scripts/triage.py --list     # just list

# Initial seed sweep — three stages
/usr/bin/python3 ~/.claude/skills/idea-backlog/scripts/extract.py --dry-run
/usr/bin/python3 ~/.claude/skills/idea-backlog/scripts/extract.py            # ~$4-5, ~25 min
/usr/bin/python3 ~/.claude/skills/idea-backlog/scripts/dedupe.py
/usr/bin/python3 ~/.claude/skills/idea-backlog/scripts/write_inbox.py

# Maintenance
/usr/bin/python3 ~/.claude/skills/idea-backlog/scripts/rebuild_index.py
/usr/bin/python3 ~/.claude/skills/idea-backlog/scripts/weekly_digest.py --dry-run
```

## Cron / launchd

```bash
# Install both jobs
ln -sf ~/.claude/skills/idea-backlog/cron/com.matteisn.idea-backlog.rebuild-index.plist ~/Library/LaunchAgents/
ln -sf ~/.claude/skills/idea-backlog/cron/com.matteisn.idea-backlog.weekly-digest.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.matteisn.idea-backlog.rebuild-index.plist
launchctl load ~/Library/LaunchAgents/com.matteisn.idea-backlog.weekly-digest.plist

# Verify
launchctl list | grep idea-backlog

# Tail logs
tail -f ~/.claude/skills/idea-backlog/_workdir/cron-*.log
```

## Files

- `scripts/` — entry points (capture / recall / extract / dedupe / write_inbox / triage / promote / kill / touch / from_task / to_task / rebuild_index / weekly_digest)
- `scripts/_lib/` — shared helpers (frontmatter, slugify, idea_io, vault_paths, inbox_md)
- `_workdir/` — extraction state, cron logs (resumable)
- `cron/` — launchd plists

## Anchors

- `MattZerg/Projects/idea-backlog.md` — full design spec
- `MattZerg/Ideas/_meta/schema.md` — frontmatter contract
- `MattZerg/Ideas/README.md` — Dataview dashboard
- Memory: `project_idea_backlog.md`, `feedback_idea_backlog_surfacing.md`
