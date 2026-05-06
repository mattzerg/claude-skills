#!/usr/bin/env python3
"""network-reach — surface CRM contacts for outbound networking.

Usage:
    python3 ~/.claude/skills/network-reach/run.py target <query> [--limit N]
    python3 ~/.claude/skills/network-reach/run.py weekly [--limit N]
"""
from __future__ import annotations
import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

VAULT = Path('/Users/mattheweisner/Library/Mobile Documents/iCloud~md~obsidian/Documents')
MZ = VAULT / 'Zerg' / 'MattZerg'
PEOPLE_DIRS = [MZ / 'People', MZ / 'People' / 'CRM']
OUT_BASE = Path('/tmp/network-reach')


def normalize(s: str) -> str:
    return re.sub(r'[^a-z0-9]', '', s.lower()) if s else ''


def parse_field(text: str, field: str) -> str:
    m = re.search(rf'^{re.escape(field)}:\s*(.+)$', text, re.MULTILINE)
    if not m:
        return ''
    val = m.group(1).strip().strip('"').strip("'")
    return val


def parse_company(text: str) -> str:
    val = parse_field(text, 'company')
    if not val:
        return ''
    wm = re.match(r'\[\[(?:Companies|Firms)/([^\]\|]+?)(?:\|[^\]]+)?\]\]', val)
    return wm.group(1) if wm else val


def load_contacts():
    """Yields dict per CRM contact."""
    for d in PEOPLE_DIRS:
        if not d.exists():
            continue
        rel = d.relative_to(MZ)
        for p in d.iterdir():
            if not p.is_file() or p.suffix != '.md' or p.name.startswith('_'):
                continue
            text = p.read_text(encoding='utf-8')
            company = parse_company(text)
            tier = parse_field(text, 'tier')
            try: tier_n = int(tier) if tier else 99
            except ValueError: tier_n = 99
            score = parse_field(text, 'relationship_score')
            try: score_n = int(score) if score else 0
            except ValueError: score_n = 0
            priority = parse_field(text, 'outreach_priority')
            relationship = parse_field(text, 'relationship')
            role = parse_field(text, 'role')
            email = parse_field(text, 'email')
            flags = parse_field(text, 'flags')
            era = parse_field(text, 'how_we_met')
            last = parse_field(text, 'last_contact')
            days = parse_field(text, 'days_since_last_contact')
            try: days_n = int(days) if days else 99999
            except ValueError: days_n = 99999
            linkedin = parse_field(text, 'linkedin')
            # Extract notes section (## Notes block)
            notes = ''
            nm = re.search(r'## Notes\s*\n\n(.+?)(?:\n##|\Z)', text, re.DOTALL)
            if nm:
                notes = nm.group(1).strip()[:400]
            yield {
                'path': f'{rel}/{p.stem}',
                'name': p.stem,
                'company': company,
                'company_norm': normalize(company),
                'tier': tier_n,
                'score': score_n,
                'priority': priority,
                'relationship': relationship,
                'role': role,
                'email': email,
                'flags': flags,
                'era': era,
                'last_contact': last,
                'days_since': days_n,
                'linkedin': linkedin,
                'notes': notes,
                'is_connector': 'referrer' in flags.lower() or relationship == 'Connector',
                'is_investor_flag': 'investor' in flags.lower(),
            }


# -------- target mode

def cmd_target(args):
    contacts = list(load_contacts())
    target_norm = normalize(args.query)
    slug = re.sub(r'[^a-z0-9-]+', '-', args.query.lower()).strip('-')[:50]

    direct = []
    for c in contacts:
        if c['company_norm'] and (target_norm in c['company_norm'] or c['company_norm'] in target_norm):
            direct.append(c)
    direct.sort(key=lambda c: (c['tier'], -c['score']))

    # Connectors — referrer flag or Connector relationship, sorted by score
    connectors = [c for c in contacts if c['is_connector']]
    connectors.sort(key=lambda c: -c['score'])
    connectors = connectors[:20]

    # Investors with high score (might know about target)
    investors = [c for c in contacts if c['is_investor_flag']]
    investors.sort(key=lambda c: -c['score'])
    investors = investors[:15]

    out_dir = OUT_BASE / f'target-{slug}'
    out_dir.mkdir(parents=True, exist_ok=True)

    out = ['# Network Reach Brief — Target', '',
           f'**Target**: `{args.query}`',
           f'**Generated**: {datetime.now().isoformat(timespec="seconds")}',
           '', '## Synthesis instructions for parent agent',
           '',
           '1. Pick the top 5–10 best-bet warm contacts from the candidate lists below.',
           '2. For each, draft 2–3 sentence outreach lines using their notes/era as context.',
           '3. Group by warmth: 🟢 last-contact <1y · 🟡 1–3y · ⚪ 3+ years (need long-time-no-talk framing).',
           '4. Output to `candidates.md` in this directory.',
           '5. Avoid AI-tells: no "Hope this finds you well", no "Just wanted to reach out". Reference shared context.',
           '',
           '---', '',
           f'## Direct contacts at "{args.query}" ({len(direct)} found)', '']

    if direct:
        for c in direct[:30]:
            out.append(f'### [[{c["path"]}|{c["name"]}]]')
            line = []
            if c['role']: line.append(f'_{c["role"]}_')
            if c['company']: line.append(f'@ {c["company"]}')
            if c['tier'] < 99: line.append(f'Tier {c["tier"]}')
            if c['score']: line.append(f'score {c["score"]}')
            if c['priority']: line.append(c['priority'])
            if c['days_since'] < 99999: line.append(f'{c["days_since"]}d since contact')
            out.append(' · '.join(line))
            if c['era']: out.append(f'_Met:_ {c["era"]}')
            if c['email']: out.append(f'_Email:_ `{c["email"]}`')
            if c['linkedin']: out.append(f'_LinkedIn:_ {c["linkedin"]}')
            if c['notes']:
                out.append('')
                out.append('> ' + c['notes'].replace('\n', '\n> '))
            out.append('')
    else:
        out.append('_(no direct contacts in CRM — escalate to connector list)_')
        out.append('')

    out.append(f'## Top connectors / referrers (top 20 by score)')
    out.append('')
    for c in connectors:
        line = f'- [[{c["path"]}|{c["name"]}]]'
        if c['role'] and c['company']:
            line += f' — {c["role"]} @ {c["company"]}'
        if c['score']: line += f' · score {c["score"]}'
        if c['days_since'] < 99999: line += f' · {c["days_since"]}d ago'
        if c['era']: line += f' · {c["era"]}'
        out.append(line)
    out.append('')

    out.append(f'## Top investor-flagged contacts (may know target if VC-relevant)')
    out.append('')
    for c in investors[:10]:
        line = f'- [[{c["path"]}|{c["name"]}]]'
        if c['role'] and c['company']:
            line += f' — {c["role"]} @ {c["company"]}'
        if c['score']: line += f' · score {c["score"]}'
        out.append(line)

    (out_dir / 'brief.md').write_text('\n'.join(out), encoding='utf-8')
    print(f'Brief: {out_dir / "brief.md"}')
    print(f'  Direct contacts at "{args.query}": {len(direct)}')
    print(f'  Connectors loaded: {len(connectors)}')
    print(f'  Investors loaded: {len(investors)}')
    print(f'\nNext: parent agent reads brief.md → writes candidates.md with ranked list + outreach drafts.')


# -------- weekly mode

def cmd_weekly(args):
    contacts = list(load_contacts())

    # Filter: Tier 1 or 2, OR outreach_priority HIGH/WARM/MAINTAIN, AND days_since >= 90
    HOT_PRIORITIES = {'HIGH', 'WARM', 'MAINTAIN'}
    candidates = []
    for c in contacts:
        is_top = c['tier'] in (1, 2) or c['priority'] in HOT_PRIORITIES
        if not is_top:
            continue
        if c['days_since'] < 90:
            continue  # recently contacted, skip
        if c['days_since'] >= 99999:
            continue  # no last_contact data
        candidates.append(c)

    # Score = days_since × tier_weight × score
    def rank(c):
        tier_weight = {1: 3.0, 2: 2.0}.get(c['tier'], 1.0)
        return c['days_since'] * tier_weight * (c['score'] or 50)

    candidates.sort(key=rank, reverse=True)
    top = candidates[:args.limit]

    slug = datetime.now().strftime('%Y-%m-%d')
    out_dir = OUT_BASE / f'weekly-{slug}'
    out_dir.mkdir(parents=True, exist_ok=True)

    out = ['# Weekly Re-engagement Priorities', '',
           f'**Generated**: {datetime.now().isoformat(timespec="seconds")}',
           f'**Pool size**: {len(candidates)} contacts qualifying',
           f'**Showing**: top {len(top)} by (days_since × tier × score)',
           '', '## Synthesis instructions',
           '',
           'For each candidate below, draft a re-engagement message (2-3 sentences):',
           '- Reference specific shared context (Vang project, era, mutual contact)',
           '- Name a concrete reason to reconnect (catch-up, ask, intro)',
           '- Choose a format (LinkedIn DM / email / coffee)',
           '',
           'Group output as:',
           '- 🔴 Overdue (180+ days, Tier 1) — re-engage this week',
           '- 🟡 Slipping (90-180 days, Tier 1-2)',
           '- 🟢 Maintenance (90+ days, HIGH/WARM priority but lower tier)',
           '', '---', '',
           '## Candidates', '']

    for i, c in enumerate(top, 1):
        out.append(f'### {i}. [[{c["path"]}|{c["name"]}]]')
        line = []
        if c['role']: line.append(f'_{c["role"]}_')
        if c['company']: line.append(f'@ {c["company"]}')
        if c['tier'] < 99: line.append(f'Tier {c["tier"]}')
        if c['score']: line.append(f'score {c["score"]}')
        if c['priority']: line.append(c['priority'])
        line.append(f'**{c["days_since"]}d since contact**')
        out.append(' · '.join(line))
        out.append('')
        if c['era']: out.append(f'_Met via:_ {c["era"]}')
        if c['email']: out.append(f'_Email:_ `{c["email"]}`')
        if c['linkedin']: out.append(f'_LinkedIn:_ {c["linkedin"]}')
        if c['notes']:
            out.append('')
            out.append('> ' + c['notes'].replace('\n', '\n> '))
        out.append('')

    (out_dir / 'brief.md').write_text('\n'.join(out), encoding='utf-8')
    print(f'Brief: {out_dir / "brief.md"}')
    print(f'  Pool size: {len(candidates)}')
    print(f'  Top picks: {len(top)}')


def main():
    parser = argparse.ArgumentParser(prog='network-reach')
    sub = parser.add_subparsers(dest='cmd', required=True)
    p_target = sub.add_parser('target', help='Find paths to a target')
    p_target.add_argument('query', help='Target company name (or role keyword)')
    p_target.add_argument('--limit', type=int, default=20)
    p_weekly = sub.add_parser('weekly', help='Generate top re-engagement list')
    p_weekly.add_argument('--limit', type=int, default=10)

    args = parser.parse_args()
    if args.cmd == 'target':
        cmd_target(args)
    elif args.cmd == 'weekly':
        cmd_weekly(args)


if __name__ == '__main__':
    main()
