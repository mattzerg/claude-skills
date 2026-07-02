---
name: self-email-miner
description: Mine the matthew@zergai.com inbox for links/content Matt emailed himself (from matteisn@gmail.com or matthew@zergai.com) about AI setup, Obsidian, agents, skills, Claude Code, MCP, and automation. Deep-extracts what each item actually is — transcribes videos (Whisper), reads on-screen/in-frame text from scene frames, fetches articles/repos, reads image attachments — then appends to the master log + actionables in the MHE vault and archives processed messages. Use when Matt says "mine my self-emails", "check what I sent myself", "process my saved reels/links", "update the self-email log", or on a schedule. Idempotent via a cursor of processed ids.
---

# self-email-miner

Recurring miner for the content Matt emails himself. Builds and maintains:
- `~/Obsidian/MHE/Personal/self-email-log.md` — deep-extracted catalog (newest first)
- `~/Obsidian/MHE/Personal/self-email-index.md` — scannable table
- `~/Obsidian/MHE/Personal/self-email-actionables.md` — installs/ideas/inspiration/improvements

Intelligence (what each item *is*, what's actionable) lives in YOU, the running session.
`miner.py` does the mechanical, idempotent parts (search-since-cursor, attachment download, archive).

## Prereqs (already installed on the always-on Mac)
`ffmpeg`, `yt-dlp`, `tesseract` (brew); `mlx-whisper` + `gallery-dl` in `./.venv`. Inbox access via
`~/.claude/skills/gmail-skill` (OAuth token for matthew@zergai.com). If a tool is missing, see the
env-lane memory note `[[self-email-miner]]` for the install list.

## Procedure

1. **Harvest new items** (only emails not yet in the cursor):
   ```
   ~/.claude/skills/self-email-miner/.venv/bin/python ~/.claude/skills/self-email-miner/miner.py harvest
   ```
   → writes `~/.claude/state/self-email-miner/fresh_items.json` and prints the fresh count.
   If `fresh_count` is 0, report "nothing new" and stop.

2. **Classify each fresh item** by `_type`:
   - IG **reel** / YouTube / TikTok / Loom / X video (`/reel/`, video hosts)
   - IG **post** (`/p/`) — image carousel (login-walled; use caption only)
   - **web** — article / GitHub repo / Reddit (non-IG URL)
   - **image-attach** / **voicememo** — attachment present
   - **skip** — "FM weekly" digests, calendar invites, pure lead-magnet bait (log briefly, still archive)

3. **Deep-extract** (the part that finds what's "hidden in the video"):
   - **video** → `bash ~/.claude/skills/self-email-miner/extract_media.sh "<url>" ~/.claude/state/self-email-miner/work/<id>`
     then **Read** `…/work/<id>/contact.jpg` (frame grid — read burned-in captions AND on-screen
     docs/tool-names/terminal/UI) and `…/transcript.txt`. Whisper mishears "Claude"→"Cloud"; correct it.
     The downscaled contact sheet can DROP small text (GitHub URLs in address bars, repo owners). When a
     reel shows repos/URLs/dense lists, re-run `extract_hires.sh "<url>" <dir>` (full 720p frames +
     tesseract OCR pre-filter) and Read the full-res `…/hires/s_*.png` to catch them. Also: "Claude" on
     screen is sometimes actually **Codex** — verify the app shown vs. the narration.
   - **IG post (carousel)** → the caption is often pure bait; the real content is on the SLIDES.
     Download the slide images authenticated:
     `gallery-dl --cookies-from-browser chrome:Default -D ~/.claude/state/self-email-miner/work/<id>/carousel "<url>"`
     (Matt's IG session lives in the Chrome **Default** profile; scope to instagram.com only.) Montage
     with `magick montage … carousel_sheet.jpg` and **Read every slide** — capture tool/repo/step lists.
     Also check for **embedded video slides**: `find …/carousel -name '*.mp4'` → run them through the
     video pipeline (ffmpeg audio → mlx_whisper + frame-read). Only if auth fails, fall back to
     `yt-dlp --skip-download --write-info-json` caption and flag `caption-only`.
   - **web** → WebFetch the URL (for GitHub, also fetch the README; strip tracking query params on failure).
   - **image-attach** → Read the image file in `…/work/<id>/`.
   - **voicememo** (.m4a) → `ffmpeg -i in.m4a -ar 16000 -ac 1 out.wav` then
     `./.venv/bin/mlx_whisper --model mlx-community/whisper-base-mlx out.wav --output-format txt`.

4. **For each item, capture** (same schema as the result files): what_it_is, tools_named[],
   techniques[], category[], actionable_for_env (none/low/med/high), actionable_note,
   extraction_quality, hidden_finds. Be factual, name specific tools/MCPs/skills/repos.

5. **Append to the vault docs** (newest first): add a section to `self-email-log.md`, a row to
   `self-email-index.md`, and fold genuinely new actionables into `self-email-actionables.md`
   (dedupe against what's already there — many creators repeat the same idea). Route **work** content
   (e.g. client deliverables) to the Zerg lane, not the personal actionables. Don't bulk-add bait.

6. **Commit** (archive processed messages + advance the cursor so they never reprocess):
   ```
   ~/.claude/skills/self-email-miner/.venv/bin/python ~/.claude/skills/self-email-miner/miner.py commit <id1> <id2> ...
   ```
   Only commit ids you actually logged. `--no-archive` to skip archiving (e.g. dry run).

7. **Report**: counts, top new high-value actionables, anything that failed extraction.

## Notes
- **Idempotent**: re-running is safe — the cursor skips already-processed ids; a second immediate run
  is a no-op.
- **Stopgap rule**: on Matt's stopgap Mac do NOT load the scheduled launchd job — run on demand only.
  The job belongs on the always-on Mac. See `[[self-email-miner]]` (env memory).
- Large media auto-deletes after extraction (extract_media.sh keeps only transcript + caption +
  contact sheet).

## Source 2: Slack (ai-tools-tracker, added 2026-06-26)
Mine the Epoch-ML/Zerg Slack for teammate AI-tool posts. Use the claude.ai Slack MCP
(`slack_search_public_and_private`, `response_format:concise`, `include_context:false` to avoid huge
output). AI-signal channels: `#relevant-tech-news`, `#dev_git`, `#dev`, `#standup`, `#ztc`. Per-term
keyword searches (space=AND, no OR): `github.com`, `MCP`, `skill`, `claude code`, `plugin`, `hooks`.
Capture {permalink, author, channel, ts, tool/repo, why}; filter to adoptable AI tooling (skip
product/client chatter, internal-repo PR noise, and NEVER store secrets/passwords). Idempotent via the
shared cursor `~/.claude/state/ai-tools-tracker/cursor.json` (processed slack ts).

## Destination (both sources) — the Zerg database, not just MHE
Write distinct tools as `status: raw` schema files to `~/Obsidian/Zerg/MattZerg/Ideas/_inbox/tooling/`
(per `Ideas/_meta/schema.md`, category `zerg-tooling`, carry a `verdict:` field) + a dated
`Skills/scouted-*.md` poll block resolving the opaque `gmail-link:instagram-*` rows. Stage tools for the
main-Mac **ai-tracker** corpus in `~/dotfiles/staged-skills/`. Reconcile with `skill-scout` (don't
double-ingest the same Gmail links — this enriches what it sees).
