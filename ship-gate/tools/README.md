# ship-gate brand-discipline tools

Four helper scripts that turn the four documented Zerg brand rules into runnable
checks. Each emits a markdown finding block + an exit code so they can be wired
into ship-gate's gate-class procedures (see `../SKILL.md`).

| Tool | Rule it enforces | Anchor memory |
|---|---|---|
| `check_richness.py` | Visual-richness recipes R1–R10 applied to marketing pages | `project_visual_richness_recipes.md` |
| `check_blog_imagery_coherence.py` | Body-SVG posts must use SVG-coded hero / LinkedIn / X | `feedback_blog_imagery_coherence.md` |
| `check_metadata_drift.py` | Body MD ↔ `.ts` excerpt ↔ `seo.description` ↔ alt-text agree | `feedback_blog_metadata_drift.md` |
| `check_palette.py` | Cream `#f4f0e7` for Zstack/non-tech, charcoal `#111514` for Zerg-parent/tech | `feedback_zerg_brand.md` |

## Exit code convention

All four scripts use the same convention so ship-gate can branch on them:

| Code | Verdict | Ship-gate mapping |
|---|---|---|
| 0    | green / N/A | clear |
| 1    | yellow      | soft warn — usable for internal review |
| 2    | red         | hard block — do not ship externally |
| 64   | usage error | wrong args |
| 70   | tool error  | upstream tool failed (e.g. webpage-layout missing) |

## Running a single check

```bash
python3 ~/.claude/skills/ship-gate/tools/check_richness.py            "https://zergai.com/"
python3 ~/.claude/skills/ship-gate/tools/check_palette.py    classify "https://zergboard.com/pricing"
python3 ~/.claude/skills/ship-gate/tools/check_palette.py    audit    "https://zergai.com/"
python3 ~/.claude/skills/ship-gate/tools/check_blog_imagery_coherence.py  ~/zerg/web/src/public/content/blog/build-now.md
python3 ~/.claude/skills/ship-gate/tools/check_metadata_drift.py          build-now
```

## Notes / gotchas

- `check_richness.py` shells out to `webpage-layout/run.py richness <url>`,
  which depends on `httpx`. The wrapper uses `/usr/bin/python3` (system
  python carries the dep). Same pattern as `feedback_fakematt_feedback_8000px_fix.md`.
- `check_metadata_drift.py` heuristics: high-confidence drift (CamelCase
  / all-caps acronyms / digit-bearing tokens) is a hard block; single-cap
  paraphrase candidates ("Beat", "Deep", "Explore") are soft warnings to
  prompt manual verification rather than blocking on common verb-starts.
- `check_palette.py` returns `OTHER` for personal sites (matteisn / vang)
  and Zerg client surfaces — they carry their own brands and the
  cream/charcoal rule does not apply. Ship-gate should skip the palette
  check on those.
- All four are read-only; none modify project files or post anywhere.

## Wiring status (updated 2026-07-02)

- `../run.py` is the canonical runner — it maps artifact type → applicable
  checks and converts any crash/timeout/unparseable output into a synthetic
  HIGH finding (fail-closed). Run checks individually only when debugging.
- `ship-gate/SKILL.md` references these tools in the relevant Gate-class blocks.
- The 2026-05-09 deferred landing-page/one-pager palette wiring is resolved:
  `check_palette.py classify` fires via `run.py`'s applicability map for
  page/pdf/image/launch artifacts. See `../SKILL.md` → History.
