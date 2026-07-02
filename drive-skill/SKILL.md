---
name: drive-skill
description: Read-only access to Matt's Google Drive. Use when the user asks to search my Drive, read this Google Doc, list my Drive files, find a file in Drive, open a spreadsheet/doc/slide from Drive, pull text out of a Google Doc, or look up a Drive document. Supports multiple Google accounts.
allowed-tools: Bash, Read
---


# Drive Skill - Google Drive Read Access

Search, list, and read files from Google Drive: Google Docs, Sheets, Slides,
PDFs, folders, and plain-text files. Read-only — this skill never writes,
deletes, or shares anything.

Default account: `matteisn@gmail.com`.

## Auth model (important)

This skill reuses the existing **gmail-skill** OAuth tokens. The gmail-skill
token already carries the broad `https://www.googleapis.com/auth/drive` scope,
which is a superset of the `drive.readonly` scope this skill needs. Because of
that, no separate browser sign-in is required — Drive access works immediately.

Resolution order in `get_credentials`:
1. This skill's own token at `~/.claude/skills/drive-skill/tokens/token_<email>.json` (if drive-scoped).
2. A reusable gmail-skill token at `~/.claude/skills/gmail-skill/tokens/token_<email>.json` (if drive-scoped).
3. Otherwise, an interactive browser OAuth flow (see "One-time auth" below).

Tokens auto-refresh; refreshed access tokens are written back to whichever file
they came from. Background jobs (no TTY) will refuse to open a browser and emit
a clear `google_oauth_interactive_required` error instead of hanging.

### One-time auth (only if the gmail token ever loses Drive scope)

If `accounts` shows `drive_scope: false` for an account, run this ONCE in an
interactive terminal (it opens a browser):

```
python3 ~/.claude/skills/drive-skill/drive_skill.py auth --account matteisn@gmail.com
```

This grants `drive.readonly` and stores a token in this skill's own `tokens/`.

## CLI

All commands print JSON to stdout. Run with `python3`.

```
python3 ~/.claude/skills/drive-skill/drive_skill.py <verb> [...]
```

### accounts
List accounts available to this skill, with which token source backs each and
whether it has Drive scope.

```
python3 ~/.claude/skills/drive-skill/drive_skill.py accounts
```

### list
Recent files, newest first (`modifiedTime desc`).

```
python3 ~/.claude/skills/drive-skill/drive_skill.py list [--account EMAIL] [--max N] [--owner me]
```
- `--max` default 25.
- `--owner me` restricts to files Matt owns (default: everything visible, including shared).
- Fields per file: `id`, `name`, `mimeType`, `modifiedTime`, `owners`, `webViewLink`.

### search
Full-text + filename search via the Drive `q` parameter
(`fullText contains` OR `name contains`).

```
python3 ~/.claude/skills/drive-skill/drive_skill.py search "QUERY" [--account EMAIL] [--max N] [--type doc|sheet|slide|pdf|folder]
```
- `--type` filters to a single MIME type.

### read
Extract a file's text content. Prints a JSON header (id, name, mimeType,
exportedAs, modifiedTime, webViewLink), then `---`, then the content.

```
python3 ~/.claude/skills/drive-skill/drive_skill.py read FILE_ID [--account EMAIL] [--format md|txt]
```
- Google Docs → exported as `text/markdown` (`--format md`, default) or `text/plain` (`--format txt`).
- Google Sheets → exported as CSV.
- Google Slides → exported as `text/plain`.
- Plain-text / JSON / XML files → downloaded directly.
- Folders → returns an `is_folder` error pointing you to `list`/`search`.
- Binary types with no text export (images, video, native Office) → returns an
  `unsupported_type` error with the `webViewLink`.

## Examples

```
# "list my Drive files"
python3 ~/.claude/skills/drive-skill/drive_skill.py list --max 10

# "search my Drive for the Q3 plan"
python3 ~/.claude/skills/drive-skill/drive_skill.py search "Q3 plan" --type doc

# "read this Google Doc"
python3 ~/.claude/skills/drive-skill/drive_skill.py read 1MTC4pf0s1elhxc5Z9AaOLDY-2v6YitYuWuTZ8DSfiDE

# files Matt owns, newest first
python3 ~/.claude/skills/drive-skill/drive_skill.py list --owner me --max 20

# a different account
python3 ~/.claude/skills/drive-skill/drive_skill.py search "invoice" --account matthew@zergai.com
```

## Notes
- Read-only by design. There are no write/delete/share verbs.
- File IDs come from `list`/`search` output (the `id` field) or from a Drive URL
  (the long token after `/d/`).
- Multi-account: pass `--account EMAIL`. Available accounts come from
  `accounts`.
