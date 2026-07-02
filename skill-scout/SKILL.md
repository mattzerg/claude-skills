---
name: skill-scout
description: Discover, score, and triage new claude-code skills shared by the community. Polls GitHub (known skill repos + topic search) and Anthropic's claude-plugins marketplace for new candidates, scores each on a value+safety rubric, and surfaces only high-quality ones to Matt's FM DM for review. Never auto-installs — Matt approves each. USE PROACTIVELY weekly (or when Matt asks "any new skills worth grabbing"); also runnable on-demand. Pairs with `audit_skills_usage.py` which audits *installed* skills — this one audits the *outside world*.
---

# skill-scout

**Purpose.** Skills shared by the community pop up daily on GitHub, Twitter, HN, and Anthropic's plugin marketplace. Most aren't relevant to Matt's stack; some are gems. `skill-scout` automates the discovery + first-pass safety/value filter so only high-signal candidates reach FM DM.

## Sources polled

1. **Anthropic claude-plugins marketplace** — `~/.claude/plugins/cache/claude-plugins-official/` (already on disk). Compare against locally enabled list to find newly added plugins.
2. **Known skill repos** — `idanbeck/claude-skills` (upstream), `anthropic-quickstarts`, `mattzerg/claude-skills` (origin), plus a configurable allowlist in `state/sources.yaml`. Polls commits since last run.
3. **GitHub topic search** — `gh search repos --topic claude-skill --sort updated --limit 30` for novel repos. Filtered by stars + recent activity.
4. **Self-sent Gmail links** — normalized rows in `state/gmail-self-sent-links.jsonl` from emails Matt sends to himself for later tool triage. These are scored like other candidates but never auto-installed.

## Scoring rubric

Each candidate gets a 0-10 score across **value** and **safety**.

**Value (0-5):**
- Fills a known gap (Matt's `MattZerg/Tasks/` or `Ideas/` mentions it): +2
- High community signal (stars > 50, or 3+ Anthropic-team contributors): +1
- Read-only or low-blast-radius: +1
- Documented invocation pattern (SKILL.md present): +1

**Safety (0-5):**
- No requested credentials beyond standard OAuth: +1
- No destructive Bash patterns (rm -rf, force-push, drop table) in code grep: +1
- License is permissive (MIT/Apache): +1
- No outbound network calls to non-API endpoints: +1
- No telemetry / phone-home behavior: +1

Promotion threshold: total **≥ 7/10** AND safety **≥ 4/5**.

## Usage

```
scout.py poll                — scan all sources, list new candidates (don't post)
scout.py poll --post         — also DM scored candidates ≥ promotion threshold
scout.py poll --no-gmail-links — skip curated self-sent Gmail link candidates
scout.py ingest-gmail-links  — search recent sent mail to matthew@zergai.com, extract links, fetch non-social linked pages for additional URLs, and update the curated Gmail-link source
scout.py ingest-gmail-links --days 14 --max-results 25 — normal weekly self-sent-link ingestion
scout.py review <slug>       — deep-evaluate one candidate (README + risk-grep)
scout.py plan <slug>         — preview files/state, conflicts, overlap, and manual install command
scout.py accept <slug>       — same preview as plan; does not change state unless --confirm is passed
scout.py accept <slug> --confirm — after reviewing the plan, mark accepted (still does not install)
scout.py reject <slug> <why> — mark rejected with reason
scout.py state               — show current state (seen / accepted / rejected counts)
```

## Output

- **State file:** `~/.claude/skills/skill-scout/state/seen.jsonl` (every candidate ever seen, with score + decision)
- **Curated input file:** `~/.claude/skills/skill-scout/state/gmail-self-sent-links.jsonl` (one JSON object per candidate extracted from Matt's self-sent emails)
- **Vault dossier:** `MattZerg/Skills/scouted-YYYY-WW.md` per ISO week — table of new candidates
- **FM DM ping:** only when ≥1 candidate passes promotion threshold

## Anti-patterns

- **Never auto-install.** `git clone` or `gh plugin install` happens only on explicit `scout.py accept`.
- **Preview before accept.** `accept` is preview-only by default. It lists the files/state that would change, existing conflicts, overlap recommendation, warnings, and the manual command. Use `--confirm` only after reviewing that plan.
- **Never grant secrets.** A candidate that asks for an API key during install is auto-rejected with safety=0.
- **Never silent-skip.** Every candidate gets logged to `seen.jsonl` with a verdict so re-discoveries are deduped.
- **Keep extracted links actionable.** Gmail ingestion filters page-shell assets, CDN files, badges, and social app shells so review output stays focused on repos, docs, packages, issues, releases, and relevant external references.

## Overlap detection (`overlap <slug>`)

Compares a scouted candidate against installed skills using **TF-IDF weighted Jaccard** + domain-keyword count.

**How it works.** At call time, we compute IDF (inverse document frequency) over the whole installed-skills corpus — tokens appearing in most skills (description/automatic/configured) get low IDF, rare domain-specific tokens (puppeteer/grafana/dispatcher) get high IDF. The comparison metric is `sum(IDF(shared tokens)) / sum(IDF(union))` — normalized 0-1.

**Output classes:**
- 🔀 **BLEND** — weighted-Jaccard ≥ 0.20 AND ≥2 domain keywords. Fold techniques into existing skill.
- 🧩 **SIBLING** — weighted-Jaccard ≥ 0.08 AND ≥1 domain keyword, OR ≥4 rare shared tokens. Install separately + cross-reference.
- 🆕 **STANDALONE** — closest match below both thresholds. Install fresh.

**Domain keyword** = shared token with IDF ≥ 3.5 (appears in roughly ≤3 of all installed skills).

**Verified 2026-05-11** across 9 Anthropic marketplace candidates: 7 obviously correct, 1 borderline, 1 false-positive (chrome-devtools-mcp ↔ whatsapp-skill share Puppeteer vocabulary; technically true but operationally unrelated).

**Known limitations:**
- Two skills using the same underlying tech (Puppeteer, Stripe API, OAuth) can score high even if their use cases differ — classifier doesn't know intent.
- Candidate descriptions from `plugin.json` are sometimes thin; richer matching requires README text.
- Long-term: replace TF-IDF with semantic embeddings (Anthropic API call) for proper domain-intent similarity. Probably ~20¢ per poll; worth it once accuracy matters.

## Anchored on

- `audit_skills_usage.py` (sibling — audits *installed* skills' usage)
- `feedback_dashboard_must_drive_action.md` (HIGH PRIORITY — only ping FM DM when there's a real action)
- `project_skills_repo_setup.md` (memory — confirms current upstream/origin layout)
