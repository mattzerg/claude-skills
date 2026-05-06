#!/usr/bin/env python3
"""cv-tailor — load all of Matt's career source files into a brief.md
that the parent agent can synthesize a tailored CV from.

Usage:
    python3 ~/.claude/skills/cv-tailor/run.py tailor <jd.md> [--role-slug NAME]
    python3 ~/.claude/skills/cv-tailor/run.py review <cv.md> <jd.md>
"""
from __future__ import annotations
import argparse
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

VAULT = Path('/Users/mattheweisner/Library/Mobile Documents/iCloud~md~obsidian/Documents')
CAREER = VAULT / 'Zerg' / 'MattZerg' / 'Career'
OUT_BASE = Path('/tmp/cv-tailor')

SOURCE_FILES = [
    ('Best variant (default starting point)', CAREER / 'CV Versions' / 'extracts' / 'Matthew Eisner CV - Nov 2025 (Best).md'),
    ('Diff Matrix (variant comparison)', CAREER / 'CV Diff Matrix.md'),
    ('Career Narrative (arc + patterns)', CAREER / 'Narrative.md'),
    ('Skills Evolution (skills × CV history)', CAREER / 'Skills Evolution.md'),
    ('Recommendations Received', CAREER / 'Recommendations Received.md'),
    ('Honors', CAREER / 'Honors.md'),
    ('Publications', CAREER / 'Publications.md'),
    ('Vang Capital Portfolio', CAREER / 'Vang Capital' / 'Portfolio.md'),
    ('Vang Advisory Completed Projects', CAREER / 'Vang Advisory' / 'Completed Projects.md'),
]

VARIANT_FILES = [
    ('Crypto variant', CAREER / 'CV Versions' / 'extracts' / 'Matthew Eisner CV - Nov 2025 (Crypto).md'),
    ('General variant', CAREER / 'CV Versions' / 'extracts' / 'Matthew Eisner CV - Nov 2025 (General).md'),
    ('Growth variant', CAREER / 'CV Versions' / 'extracts' / 'Matthew Eisner CV - Nov 2025 (Growth).md'),
]


def slugify(s: str) -> str:
    s = re.sub(r'[^a-z0-9-]+', '-', s.lower()).strip('-')
    return s[:60] or 'untitled'


def load(p: Path) -> str:
    if not p.exists():
        return f'_(missing: {p})_'
    return p.read_text(encoding='utf-8')


def cmd_tailor(args):
    jd_path = Path(args.jd)
    if not jd_path.exists():
        print(f'JD file not found: {jd_path}', file=sys.stderr)
        sys.exit(1)

    jd_text = jd_path.read_text(encoding='utf-8')
    role_slug = args.role_slug or slugify(jd_path.stem)
    out_dir = OUT_BASE / role_slug
    out_dir.mkdir(parents=True, exist_ok=True)

    # Copy JD for reference
    shutil.copy(jd_path, out_dir / 'jd-source.md')

    # Build brief
    brief = ['# CV Tailoring Brief', '',
             f'**Role**: `{role_slug}`',
             f'**JD source**: `{jd_path.name}`',
             f'**Generated**: {datetime.now().isoformat(timespec="seconds")}',
             '',
             '---',
             '',
             '## Job Description',
             '',
             jd_text,
             '',
             '---',
             '',
             '## Synthesis instructions',
             '',
             '1. Read the JD above and identify the role\'s primary axis (crypto / growth / product / strategy / VC / accelerator-ops).',
             '2. Pick a base variant from §"Diff Matrix" or use the "Best variant" as default.',
             '3. Swap in the strongest bullet from each section per the role\'s axis.',
             '4. Reorder Skills to lead with role-relevant ones (use JD keywords).',
             '5. Trim Experience entries that don\'t fit the audience.',
             '6. Output to `cv.md` + `tailoring-notes.md` in this same directory.',
             '7. After drafting, run `fakematt-copyedit` on `cv.md` for a sentence-level pass.',
             '',
             '## Output paths',
             '',
             f'- Tailored CV → `{out_dir}/cv.md`',
             f'- Tailoring notes (what changed and why) → `{out_dir}/tailoring-notes.md`',
             '',
             '---',
             '',
             '## Source files',
             '']

    for label, path in SOURCE_FILES:
        brief.append(f'### {label}')
        brief.append(f'_File: `{path.relative_to(VAULT)}`_')
        brief.append('')
        brief.append(load(path))
        brief.append('')
        brief.append('---')
        brief.append('')

    brief.append('## Variant baselines (for direct quotes)')
    brief.append('')
    for label, path in VARIANT_FILES:
        brief.append(f'### {label}')
        brief.append('')
        brief.append(load(path))
        brief.append('')
        brief.append('---')
        brief.append('')

    (out_dir / 'brief.md').write_text('\n'.join(brief), encoding='utf-8')
    print(f'Brief written: {out_dir / "brief.md"}')
    print(f'JD copied: {out_dir / "jd-source.md"}')
    print()
    print(f'Next: synthesize {out_dir / "cv.md"} + {out_dir / "tailoring-notes.md"} from the brief.')


def cmd_review(args):
    cv_path = Path(args.cv)
    jd_path = Path(args.jd)
    for p, label in [(cv_path, 'CV'), (jd_path, 'JD')]:
        if not p.exists():
            print(f'{label} file not found: {p}', file=sys.stderr)
            sys.exit(1)

    role_slug = args.role_slug or slugify(jd_path.stem)
    out_dir = OUT_BASE / f'review-{role_slug}'
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(cv_path, out_dir / 'cv-source.md')
    shutil.copy(jd_path, out_dir / 'jd-source.md')

    brief = ['# CV Review Brief', '',
             f'**Role**: `{role_slug}`', f'**CV**: `{cv_path.name}`', f'**JD**: `{jd_path.name}`',
             f'**Generated**: {datetime.now().isoformat(timespec="seconds")}', '',
             '## Review goals',
             '',
             '1. Identify mismatches between CV claims and JD requirements',
             '2. Surface JD keywords that exist in Skills Evolution but aren\'t in the CV',
             '3. Flag bullet ordering that buries the most-relevant wins',
             '4. Identify sections that should be cut for length',
             '',
             '## Output',
             '',
             f'Write `{out_dir}/review.md` — bullet list of findings, each with severity + suggested fix.',
             '',
             '---',
             '',
             '## Job Description', '', jd_path.read_text(encoding='utf-8'),
             '', '---', '',
             '## CV under review', '', cv_path.read_text(encoding='utf-8'),
             '', '---', '',
             '## Reference: Skills Evolution',
             '',
             load(CAREER / 'Skills Evolution.md'),
             '', '---', '',
             '## Reference: Diff Matrix',
             '',
             load(CAREER / 'CV Diff Matrix.md')]

    (out_dir / 'brief.md').write_text('\n'.join(brief), encoding='utf-8')
    print(f'Review brief written: {out_dir / "brief.md"}')


def main():
    parser = argparse.ArgumentParser(prog='cv-tailor')
    sub = parser.add_subparsers(dest='cmd', required=True)
    p_tailor = sub.add_parser('tailor', help='Tailor a CV for a JD')
    p_tailor.add_argument('jd', help='Path to job description (markdown or text)')
    p_tailor.add_argument('--role-slug', help='Optional slug for output directory')
    p_review = sub.add_parser('review', help='Review an existing CV against a JD')
    p_review.add_argument('cv', help='Path to CV markdown')
    p_review.add_argument('jd', help='Path to job description')
    p_review.add_argument('--role-slug', help='Optional slug for output directory')

    args = parser.parse_args()
    if args.cmd == 'tailor':
        cmd_tailor(args)
    elif args.cmd == 'review':
        cmd_review(args)


if __name__ == '__main__':
    main()
