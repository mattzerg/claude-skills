---
name: memory-maintenance
description: Hygiene scan of Matt's 3 memory lanes (env/dotfiles, MHE-personal, Zerg-work) plus the CLAUDE.md files — flags index bloat, orphaned memory files (exist but not in MEMORY.md), dangling index entries (point to missing files), oversized single memories, stale/long-untouched files, and broken [[wikilinks]]. Advisory only: proposes prunes/merges/fixes for confirmation, never auto-deletes. Use when Matt says "check my memory", "is my memory getting bloated", "audit/prune memory", "clean up MEMORY.md", or on a periodic cadence. Lane-aware (Obsidian wikilinks resolve vault-wide; the Zerg index legitimately projects ~/Obsidian/Zerg/MattZerg/_agent_memory).
---

# memory-maintenance

Keeps the 3-lane markdown memory system lean and self-consistent. Complements (does not replace)
the **memory-triage** agent — triage handles cross-runtime Claude/Codex promotion vs
`~/Obsidian/Zerg/MattZerg/_agent_memory`; this skill is narrow hygiene on the markdown lanes themselves.

## Procedure

1. **Scan** (read-only):
   ```
   ~/.claude/skills/self-email-miner/.venv/bin/python ~/.claude/skills/memory-maintenance/check.py
   ```
   (Any python3 works; the self-email-miner venv is just a convenient interpreter.) It prints JSON:
   per-lane `orphans / dangling / oversized / stale / broken_wikilinks`, `idx_lines`, CLAUDE.md sizes,
   and a top-level `flags` list. `flags == ["clean — ..."]` means nothing to do — report and stop.

2. **Interpret each flag** and propose a concrete, lane-correct fix:
   - **orphan** (file exists, not in index) → add a one-line pointer to that lane's `MEMORY.md`
     (env: `- [Title](file.md) — hook`; Obsidian lanes: `[[basename]]` per vault convention).
   - **dangling** (index → missing file) → the memory was deleted/renamed; remove or repoint the index line.
   - **oversized** (single memory > ~6KB) → it's drifted from "one fact" into an essay; propose splitting
     into focused memories or trimming. (Current real example: `project-zerg-team-swag.md`.)
   - **stale** (untouched > 180d) → surface for Matt to confirm still-true or retire; convert relative
     dates to absolute if found.
   - **broken [[wikilink]]** → target doesn't resolve in that vault. Note: cross-lane links (e.g. a
     Zerg memory linking `[[gmail-zergai-access]]` which lives in the env lane) won't resolve in
     Obsidian — either drop the link or note it's an intentional cross-lane pointer.
   - **MEMORY.md / CLAUDE.md too long** → propose pruning the lowest-value lines, not blanket trimming.

3. **Confirm before changing anything.** This skill is advisory — present the proposed edits and let
   Matt approve. Honor the routing rules in `~/.claude/CLAUDE.md` (write each fix to the correct lane's
   absolute path) and the destructive-action-confirm rule. Never bulk-delete.

4. **Apply** approved fixes (edit the relevant `MEMORY.md` / memory file), then re-run `check.py` to
   confirm the flag cleared.

## Notes
- Thresholds live at the top of `check.py` (idx ≤90 lines, memory ≤6KB, stale 180d) — tune there.
- Lane-aware: it resolves Obsidian wikilinks vault-wide and treats the Zerg index's
  `~/Obsidian/Zerg/MattZerg/_agent_memory` projections as valid, so it won't false-flag those.
- Safe to run anytime; read-only until you choose to apply a fix.
