---
name: cv-tailor
description: Generate a tailored CV draft for a specific job description by pulling from Matt's Career/ vault folder (CV Diff Matrix, Narrative, Best-of variant, Skills Evolution, Recommendations, Honors). Reads a JD file or pasted text and outputs a tailored CV draft + a tailoring brief explaining what was kept, dropped, and emphasized. Use this whenever Matt mentions applying to a role, asks "tailor a CV for X," or pastes a job description. Does NOT auto-send — output is a markdown draft Matt manually composes into a .docx by editing one of the source variants.
allowed-tools: Bash, Read, Write
---

# CV Tailor Skill

Builds tailored CV drafts for specific job applications by composing from Matt's structured career data.

## When to invoke

- Matt pastes a job description and asks for a CV
- Matt says "tailor a CV for [role/company]"
- Matt is preparing an application and mentions the target role
- Before any CV is sent — even if Matt has manually picked a variant — run this to surface bullet swaps he might miss

## Inputs

The skill reads from `~/Obsidian/Zerg/MattZerg/Career/` in Matt's Obsidian vault:

| File | Purpose |
|---|---|
| `Career/CV Versions/extracts/Matthew Eisner CV - Nov 2025 (Best).md` | Default starting point — best-of synthesis |
| `Career/CV Diff Matrix.md` | Variant comparison (Crypto / General / Growth) — what to borrow when |
| `Career/Narrative.md` | Career arc, recurring patterns, receipts |
| `Career/Skills Evolution.md` | All skills + tools across CV history (with first-appearance dates) |
| `Career/Recommendations Received.md` | 8 LI recs (use as supporting evidence in cover-letter language) |
| `Career/Honors.md` | MarCom 2017 Gold (the one award) |
| `Career/Publications.md` | Many Labs Replication (1,400+ citations) |
| `Career/Vang Capital/Portfolio.md` + `Portfolio Contacts.md` | 32 investments + their contacts |
| `Career/Vang Advisory/Completed Projects.md` | 86 client engagements |

## Two modes

### tailor — generate a tailored CV from a JD

```bash
python3 ~/.claude/skills/cv-tailor/run.py tailor <jd.md> [--role-slug NAME]
```

The script:
1. Reads the JD file
2. Loads all source files listed above into a single context dump
3. Writes that context dump to `/tmp/cv-tailor/<slug>/brief.md`
4. The parent agent then synthesizes a tailored CV based on the brief

The agent should:
- Identify the role's primary axis (crypto / growth / product / strategy / VC / accelerator-ops)
- Pick a base variant from the Diff Matrix (or the Best-of as default)
- Swap in the strongest bullet from each section per the role's axis
- Reorder Skills to lead with role-relevant ones
- Trim Experience entries that don't fit the audience (e.g., drop Algorand entry for non-crypto roles)
- Output to `/tmp/cv-tailor/<slug>/cv.md` + `/tmp/cv-tailor/<slug>/tailoring-notes.md`

### review — audit a CV against a JD

```bash
python3 ~/.claude/skills/cv-tailor/run.py review <cv.md> <jd.md>
```

Loads the CV + JD into a brief and asks the agent to identify:
- Mismatch between CV claims and JD requirements
- Missing keywords from JD that exist in Skills Evolution but aren't in the CV
- Bullet ordering that buries the most relevant wins
- Sections that should be cut for length

## Output structure

```
/tmp/cv-tailor/<role-slug>/
├── brief.md              # context dump for the agent
├── cv.md                 # tailored CV draft (markdown)
├── tailoring-notes.md    # what was kept/dropped/swapped and why
└── jd-source.md          # copy of original JD for reference
```

## Composition guide (for the parent agent)

Use the Diff Matrix's "What to borrow when" §9 as the primary playbook. Order of operations:

1. **Headline/Summary**: pick from Crypto / General / Growth, sharpen with role-specific keywords from JD
2. **Skills**: lead with 2-3 JD keywords; pull rest from Best variant Skills Evolution
3. **Tools**: prune to JD-relevant tools; keep generative AI + automation always
4. **Investment / Innovation sidebar**: trim to 4-5 most relevant entries
5. **Experience entries**:
   - Always include Vang, Dinari, Samba TV (recent)
   - Include Algorand EU entry only if crypto/web3/accelerator role
   - For Vang: pick 3 bullets from the Vang section per role (Diff Matrix §5)
   - For Dinari: pick 3-4 bullets per role (always include partnerships if crypto)
6. **Other Previous Work**: keep the 4-line list compact

## Never

- Auto-send anywhere
- Modify the source `.docx` files (those are sacred — only `fix_nov_cvs.py` touches them)
- Invent bullets that aren't grounded in Matt's actual history
- Use AI-tells (em-dash overuse, "serves as," "stands as a testament") — see CLAUDE.md AI Writing Cleanup

## Pair with

- `fakematt-copyedit` — run after tailoring to clean the prose at the sentence level
- `fakematt-feedback` — run on the tailored CV as a final structural check
