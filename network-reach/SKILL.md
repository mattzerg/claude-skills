---
name: network-reach
description: Mine Matt's Obsidian CRM (~2200 People/CRM/ contacts + ~30 curated People/) to surface networking opportunities. Two modes — `target <query>` (find existing CRM contacts AT a target company OR 1-hop connectors who likely know someone there) and `weekly` (generate top-10 re-engagement priorities from Tier 1/2 contacts with high days-since-last-contact). Use whenever Matt mentions a target company, a job he's pursuing, an LP/investor he wants to reach, or asks "who do I know who can help with X." Outputs ranked candidate lists + draft outreach lines. Never auto-sends.
allowed-tools: Bash, Read, Write
---

# Network Reach Skill

Sibling to `cv-tailor`. Where cv-tailor handles _inbound_ ("I have a JD, build me a CV"), this skill handles _outbound_ ("I want to reach this company/person, who in my network can help").

## When to invoke

- Matt names a target company / role / LP / investor / firm
- Matt asks "who do I know at X"
- Matt asks "who should I re-engage this week"
- Before any outreach push (LinkedIn DMs, intro emails, fundraising outreach) — to surface warm contacts before going cold
- After a `cv-tailor` run, automatically — to suggest network paths into the same target

## Sources

| File | Purpose |
|---|---|
| `~/Obsidian/Zerg/MattZerg/People/CRM/*.md` (~2170 files) | Bulk CRM, frontmatter has tier/score/priority/flags/last_contact/days_since/relationship/role/company |
| `~/Obsidian/Zerg/MattZerg/People/*.md` (~26 curated) | Hand-curated tier-1 contacts |
| `MHE/People/CRM/*.md` (~9 family/personal) | Personal contacts |
| `~/Obsidian/Zerg/MattZerg/Career/Vang Capital/Portfolio Contacts.md` | 74 portfolio-company contacts (cross-referenced) |
| `~/Obsidian/Zerg/MattZerg/Career/Vang Capital/LP Outreach.md` | 145 LP candidates Matt's already approached |
| `~/Obsidian/Zerg/MattZerg/Career/Experience by Company.md` | 310 unique companies × 22 multi-relationship |

## Modes

### target — find paths to a company/person

```bash
python3 ~/.claude/skills/network-reach/run.py target "Anthropic"
python3 ~/.claude/skills/network-reach/run.py target "Andreessen Horowitz"
python3 ~/.claude/skills/network-reach/run.py target --role "Head of Growth" --keywords "fintech crypto"
```

Output → `/tmp/network-reach/<slug>/brief.md`:

1. **Direct contacts** — CRM contacts whose `company:` matches target (case-insensitive, alias-aware)
2. **Connectors / referrers** — Top 20 CRM contacts where `flags:` includes `referrer` OR `relationship:` is `Connector`, sorted by relationship_score
3. **Adjacent companies** — Companies in CRM that share investors/founders/clients with the target (via `Career/Experience by Company.md`)
4. **Past Vang touchpoints** — If target is a Vang portfolio company / past consulting client / past LP, surface it

The parent agent then synthesizes:
- Ranked list of best-bet warm contacts
- Suggested outreach line for each (using their `notes:` field for context)
- Risk flags (e.g., contact was last touched 5+ years ago — outreach needs "long-time-no-talk" framing)

### weekly — top re-engagement priorities

```bash
python3 ~/.claude/skills/network-reach/run.py weekly [--limit 10]
```

Filters CRM:
- Tier 1 + Tier 2 contacts (closest relationships)
- OR `outreach_priority: HIGH | WARM | MAINTAIN`
- AND `days_since_last_contact >= 90` (3+ months)

Sorts by (days_since × tier_weight × score). Outputs the top N with their backstory pulled from frontmatter notes for each.

The parent agent suggests:
- Re-engagement angle ("hi from Vang days; I'm now at Zerg AI" or "saw your X update on LinkedIn")
- Format (LinkedIn DM / email / coffee invite / intro to someone in their world)
- Priority (this week / this month / nice-to-have)

## Output format

```
/tmp/network-reach/<slug>/
├── brief.md              # full context dump for the agent
├── candidates.md         # ranked list with outreach drafts
└── (target mode) target.md  # the input target restated
```

## Composition guide (for parent agent)

For `target` mode, the priority order:

1. **Direct contact at target** — score: warm if `last_contact < 1y`, cool if 1-3y, cold if 3y+
2. **Direct contact ex-target** — they used to be there; less direct but still warm
3. **Connector with portfolio overlap** — they invested in the target's space
4. **Connector with role overlap** — they hire/advise in this kind of role
5. **Generic Tier-1 connector** — high score, broad network

For each suggested contact, draft a 2-3 sentence outreach line that:
- References a specific shared context (Vang project, accelerator program, mutual contact, recent LinkedIn activity)
- Names the target ask plainly ("intro to [person]" or "5-min call about [X]")
- Avoids AI-tells (no "I hope this finds you well", "wanted to reach out")

For `weekly` mode, group output:
- 🔴 Overdue (180+ days, Tier 1) — re-engage this week
- 🟡 Slipping (90-180 days, Tier 1-2)
- 🟢 Maintenance (60-90 days, HIGH/WARM priority)

## Never

- Auto-send to LinkedIn / email / SMS
- Generate outreach for cold (Tier 4 / LOW priority) contacts at scale — that's spam
- Use "Hi [Name]" templates without the contact-specific context line — that's worse than not reaching out
- Pull from MHE personal contacts unless explicitly scoped (those are family/personal)

## Pair with

- `cv-tailor` — when targeting a role, run cv-tailor first then network-reach with same target to surface warm intro paths
- `gmail-skill` — after generating outreach drafts, can use gmail-skill to create drafts (NOT send — drafts only, Matt reviews)
- `linkedin-skill` — same pattern; create draft DMs, don't auto-fire
