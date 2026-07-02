---
name: content-release
description: >-
  Post-publish content release orchestrator. Given a published blog/content slug,
  runs the derivative-artifact loop: verify live, scrape live as source of truth,
  download imagery, crop edge artifacts, assemble review pack, audit, version,
  archive to vault, and flip zpub state. Use when a piece has just gone live and
  Matt asks for the pack, archive, distribution surfaces, or team version.
---

# Content Release

The post-publish counterpart to `content-production`. Where content-production owns ideate → draft → review → imagery → publish-gate (pre-publish), content-release owns the loop that runs **after** a piece is live: build the canonical archive artifacts, version them, and flip the publishing state to GREEN.

## Why this exists

The agents-that-remember launch on 2026-05-12 surfaced a recurring failure mode: ad-hoc post-publish artifact assembly. Live URL guessed wrong. Stale local imagery used instead of live. White edge strips not cropped. Wasted-space pages slipped through. Versioned filename forgotten. Vault archive not staged. zpub state not flipped. Each of these has its own memory rule, but the rules don't fire when there's no orchestrator holding them.

This skill is that orchestrator. It composes existing primitives — it does not re-implement them.

## When to invoke

Trigger when ANY of these are true:

- A blog/content slug just went live and Matt asks for "the pack", "the archive", "the team version", "the launch deck", "ship the post-publish surfaces"
- Matt mentions a slug + verb like "release", "package up", "distribute", "archive", "version the launch"
- Before sending the pack to anyone external (team / investors / customer)
- Before flipping `zpub` to GREEN on a post-publish entry

Do NOT invoke for:

- Pre-publish work — use `content-production` instead
- One-off social copy without a pack — use `social-distribution` agent
- Editing the body content of a live post — that's a republish, not a release; route through Idan + main←dev sync

## What it does

```
content-release <slug>
  STEP 0 — Lock preflight (NEW 2026-05-13)
    python3 ~/.config/zerg/zerg_approve.py status <slug>
    Refuses to proceed unless:
      - approval.locked is true
      - all HIGH-severity findings in <slug>.feedback.jsonl have status `applied`
    Override: --allow-unlocked (emergencies only — see feedback_approved_posts_locked.md)

  STEP 1 — Resolve canonical URL
    python3 ~/.config/zerg/zergai_blog_url.py <slug> --check-live --json
    Halts if not live (override: --force-not-live for staging)

  STEP 2 — Scrape live page (source-of-truth per feedback_live_is_content_source_of_truth.md)
    chrome-devtools navigate_page → evaluate_script → extract:
      - title, author, publishedTime
      - article body markdown
      - all <img src> URLs (hero, body, author headshot)
      - og:image, twitter:image meta

  STEP 3 — Download imagery
    curl each live <img src> → ~/Downloads/<slug>-release/imagery/
    Also pull social cards (LinkedIn / X) from web/src/public/images/blog/

  STEP 4 — Crop edge artifacts
    python3 ~/.config/zerg/crop_image_padding.py <each png> --only-light --tolerance 6
    Strips light/white edge strips baked into live PNGs

  STEP 5 — Pull approved social pack
    Look for MattZerg/Writing/<slug>-social-*.md
    If not found → halt; ask Matt to confirm or create
    Per feedback_approved_posts_locked.md — frozen content, do not edit

  STEP 6 — Assemble pack source MD
    Cover → TLDR/metadata → Part 1 Blog body (with inline live imagery) →
    Part 2 Social pack → Part 3 Reshare bank → Part 4 Asset map → Part 5 Ship checklist
    Format per feedback_internal_review_pack_format.md
    Theme by audience (zerg-dark-multipage for research/technical; zerg-default-multipage for Zstack/non-technical)

  STEP 7 — Render via document-styling-skill
    python3 ~/.claude/skills/document-styling-skill/render.py \
      <source.md> --theme <theme> --layout multi-page --no-open
    Renderer auto-runs crop_image_padding + audit_pack (HARD GATE)

  STEP 8 — Version + stage
    Filename: <slug>-pack-v<N>-YYYY-MM-DD.pdf (enforced via version_path.py)
    Stage to:
      - ~/Downloads/ (Matt-facing)
      - MattZerg/Writing/exports/ (vault canonical)
      - MattZerg/Brand/assets/collateral/launch-packs/ (collateral archive)

  STEP 9 — Flip zpub state
    zpub set <id> status published
    zpub set <id> gates.distribution: passed (if social URLs already logged)

  STEP 10 — Kick off post-publish release-thread loop (added 2026-05-13)
    python3 ~/.config/zerg/release_thread.py capture <slug> --blog-url <live-url>
    # Then prompt Matt for posted social URLs (X/LI/HN/Reddit) as they go up;
    # `publish_live_poller.py` (hourly launchd) auto-detects live blogs via
    # the hero-asset HEAD check and invokes release_thread itself — STEP 10
    # is the manual fallback when content-release is run interactively.
    #
    # Full loop spec: feedback_post_publish_release_thread.md
    # Once URLs land, run: scrape → diff → schedule → slack (each gated).

  STEP 11 — Open Preview ONCE (final artifact only)
    Per feedback_open_files_once.md
```

## Verbs

| Verb | Purpose |
|------|---------|
| `release <slug>` | Run the full 10-step loop |
| `status <slug>` | Read-only — show current release state (zpub entry, last pack version, live URL, gate status) |
| `assets <slug>` | Just steps 1–4 (resolve + scrape + download + crop). Halts before pack assembly. Use when you want fresh live imagery without rebuilding the pack. |
| `audit <slug>` | Run audit_pack.py against the latest pack version + report. Read-only. |

## Run

```bash
python3 ~/.claude/skills/content-release/run.py <verb> <slug> [flags]
```

Flags:
- `--force-not-live` — proceed even if zergai.com returns non-200 (CDN cache lag, staging preview)
- `--theme <name>` — override theme auto-pick
- `--out-dir <path>` — override `~/Downloads/<slug>-release/` working directory
- `--no-zpub` — skip zpub state flip (when zpub entry doesn't exist yet)
- `--dry-run` — show what would happen, don't write or render

## Output discipline

- ONE final canonical PDF per release version (per `feedback_review_pack_one_file.md`)
- Versioned filename (per `feedback_label_iteration_versions.md`)
- Open Preview ONCE at the end (per `feedback_open_files_once.md`)
- Live URL is the source of truth (per `feedback_live_is_content_source_of_truth.md`)
- Approved content (social pack, body) is FROZEN (per `feedback_approved_posts_locked.md`)
- Never auto-posts to LinkedIn / X / etc — that's `social-distribution`'s territory after sign-off

## What this skill does NOT do

- **Does not publish to zergai.com.** That's Idan's manual `main` ← `development` sync.
- **Does not post social copy.** Social posting is manual (LinkedIn-skill / twitter-skill on explicit confirmation).
- **Does not rewrite body or social content.** Frozen per approval. If the live body has drifted from local sources, the skill REPORTS the drift but never edits.
- **Does not create the pre-publish artifacts.** That's `content-production`.

## Pairs with

- `content-production` — pre-publish counterpart (the other half of the lifecycle)
- `zpub` — bidirectional state mirror (this skill writes to it)
- `document-styling-skill` — owns the visual treatment + auto-audit
- `zergai_blog_url.py`, `crop_image_padding.py`, `audit_pack.py` — the leaf utilities under `~/.config/zerg/`
- `review-pack` — generic review-pack format reference (this skill is the content-specific specialization)

## Anchors

- `~/.claude/projects/.../memory/composite_content_release.md` — bundled rules
- `~/.claude/projects/.../memory/composite_multipage_pdf.md` — PDF render rules
- `~/.claude/projects/.../memory/feedback_live_is_content_source_of_truth.md`
- `~/.claude/projects/.../memory/feedback_source_before_assert.md`
- `~/.claude/projects/.../memory/feedback_internal_review_pack_format.md`
