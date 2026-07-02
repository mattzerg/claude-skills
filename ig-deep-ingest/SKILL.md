---
name: ig-deep-ingest
description: Deep-ingest Instagram reels/posts or screenshots when captions are sparse and the useful artifact may live in audio, on-screen text, comments, or a screenshot. Use for self-sent Instagram AI/tool/setup resources, saved-post deep dives, repo/tool detection from reel frames, and converting opaque IG links into structured Obsidian capture notes before evaluation or implementation.
---

# Instagram Deep Ingest

Use this when an Instagram reel/post needs more than caption parsing. The goal is not to install or adopt anything directly from a reel; the goal is to create a source-backed capture that can be evaluated later.

## Workflow

1. Run the bundled CLI from the skill directory:

```bash
python3 ~/.claude/skills/ig-deep-ingest/scripts/ingest.py ingest URL_OR_FILE...
```

Use `--no-metadata --metadata-only` when you only want to create a capture shell for a blocked/private link without calling `yt-dlp`.

For carousel posts, sparse captions, or repos/tools visible only in UI/comments, use logged-in browser extraction:

```bash
python3 ~/.claude/skills/ig-deep-ingest/scripts/ingest.py ingest \
  --browser --browser-session instagram URL_OR_FILE...
```

If no Instagram session exists yet, run:

```bash
python3 ~/.claude/skills/ig-deep-ingest/scripts/ingest.py login --browser-session instagram
```

Log in manually in the visible browser. The command saves the Playwright session automatically when the Instagram `sessionid` cookie appears.

2. For Gmail self-sent links:

```bash
python3 ~/.claude/skills/ig-deep-ingest/scripts/ingest.py gmail \
  --account matthew@zergai.com \
  --query 'from:matteisn@gmail.com newer_than:45d -in:trash -in:spam'
```

3. For Instagram export backlog:

```bash
python3 ~/.claude/skills/ig-deep-ingest/scripts/ingest.py export \
  --records ~/.cache/ig-mining/records.jsonl \
  --filter needs_deep_dive \
  --max 25
```

4. Read the generated note under `MattZerg/Captures/Instagram-Reel-Ingest/` and route the item into the relevant evaluation note. Do not build/install from a reel without a separate evaluation step.

## What The CLI Extracts

- Instagram shortcode, owner, caption, title, thumbnail, and metadata where available.
- Downloaded video/audio when `yt-dlp` can access it.
- Audio transcript when a local Whisper CLI is available.
- Sampled frames plus OCR text via `ffmpeg`, ImageMagick, and `tesseract`.
- Logged-in browser text, links, comments visible on the page, carousel screenshots, and OCR of those screenshots when `--browser` is used.
- Repo/tool/domain candidates from caption, transcript, OCR, and screenshot text.
- Explicit missing-dependency and fetch-failure statuses, so opaque items remain auditable.

## Dependency Notes

Known-good local tools: `yt-dlp`, `ffmpeg`, `tesseract`, ImageMagick `magick`, and Python Pillow. Scratch media defaults to `/private/tmp/ig-deep-ingest` so it works under Codex's managed filesystem; set `IG_DEEP_INGEST_CACHE` to override.

Transcription is optional. The script uses `IG_DEEP_INGEST_TRANSCRIBE_CMD` if set. Otherwise it tries `whisper`, then `mlx-whisper`. If neither exists, it records `transcript_status: missing_dependency`.

For private/login-walled IG content, pass cookies through `--cookies PATH` or set `IG_DEEP_INGEST_COOKIES`.

For browser extraction, the script reads/writes Playwright storage state from the sibling `playwright-skill/sessions/<session>.json` file in the current stack (`~/.codex/skills` or `~/.claude/skills`).
