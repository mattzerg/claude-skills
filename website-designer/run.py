#!/usr/bin/env python3
"""website-designer skill — brief + review modes."""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime

SKILL_DIR = Path(__file__).resolve().parent
OUT_BASE = Path("/tmp/website-designer")


def load_text(p):
    return Path(p).read_text() if Path(p).exists() else ""


def cmd_brief(args):
    site = args.target
    persona = args.persona
    out_dir = OUT_BASE / site
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "brief.md"

    principles = load_text(SKILL_DIR / "principles.md")
    anti = load_text(SKILL_DIR / "anti-patterns.md")

    body = f"""# Design brief — {site}

**Persona**: {persona}
**Generated**: {datetime.now().isoformat(timespec='seconds')}

## Distinctiveness ledger (REQUIRED — fill before coding)

Every site Claude designs must declare 3+ distinctive details that are NOT in the AI personal-site stencil.
Examples Matt has greenlit: hand-set kerning on wordmark, an off-grid image, a non-rectangular section,
a footnote-style aside, an unusual one-shot color callout, real photography (not stock).

- D1: ___________________________________________
- D2: ___________________________________________
- D3: ___________________________________________

Reference exemplars to study (Matt rates 8+/10):

- See `corpus/personal-sites.md`, `corpus/agency-sites.md`, `corpus/fund-sites.md`
- Read at least 3 references before writing a single line of HTML.

## Hard constraints (auto-fail at review)

- No animated gradient blob art
- No 4-number stat strip
- No "Hero → Currently → Selected → Testimonials → CTA → Footer" stencil structure
- No Inter + Fraunces italic-headline as the type system
- No `padding: 96px 0;` everywhere (rhythm > uniform)
- No 4-column corporate footer
- No hover-up-card with soft shadow as the only interaction

## Sign-off criteria

The site is done when:
- Distinctiveness ledger has 3 declared items, all visible in the rendered output
- `python3 ~/.claude/skills/website-designer/run.py review <url>` returns no HIGH findings
- A skim test ("describe this site in one specific word") yields a non-generic adjective

---

## Reference: Principles

{principles}

---

## Reference: Anti-patterns

{anti}
"""
    out.write_text(body)
    print(json.dumps({"ok": True, "brief": str(out)}))


def detect_anti_patterns(html, css):
    """Static text-based scan for known stencil tells."""
    findings = []

    blob_keywords = ["art-blob", "blob-1", "blob-2", "@keyframes float", "art-shape"]
    if any(k in css for k in blob_keywords):
        findings.append({
            "severity": "HIGH",
            "id": "AP-1",
            "name": "blob-hero",
            "evidence": "CSS contains `.art-blob` / `@keyframes float` / animated decorative shape",
            "fix": "Delete all `.art-blob*` rules and `@keyframes float`. Replace hero art with one piece of real photography or omit hero art entirely.",
        })

    if re.search(r"stat-?(strip|number|label)", html + css, re.I) or "stats-strip" in html:
        # Count numbers in stat strip
        stat_count = len(re.findall(r'class=["\']stat-number["\']', html))
        if stat_count >= 3:
            findings.append({
                "severity": "HIGH",
                "id": "AP-2",
                "name": "4-stat-strip",
                "evidence": f"`.stats-strip` with {stat_count} stat-number elements",
                "fix": "Remove the stats strip. If the numbers matter, embed ONE specific stat in a sentence in the hero or as a pull quote.",
            })

    if "Inter:" in html and "Fraunces:" in html:
        if "serif italic" in html or 'class="serif italic"' in html:
            findings.append({
                "severity": "HIGH",
                "id": "AP-3",
                "name": "AI-default-type-pairing",
                "evidence": "Inter+Fraunces loaded from Google Fonts + Fraunces-italic used in headline",
                "fix": "Replace with: (a) single-font system using Söhne/Ranade/Mona Sans/IBM Plex/GT America, OR (b) Inter paired with EB Garamond/Tiempos/IBM Plex Serif (NOT Fraunces), OR (c) Fraunces without the italic-headline.",
            })
        else:
            findings.append({
                "severity": "MEDIUM",
                "id": "AP-3",
                "name": "AI-default-type-pairing",
                "evidence": "Inter+Fraunces loaded — common AI-stencil pairing",
                "fix": "Consider replacing Fraunces with EB Garamond/Tiempos, or going single-font.",
            })

    section_labels = re.findall(r'<p class="section-kicker[^"]*">([^<]+)</p>', html)
    generic_kickers = ["What we help with", "Selected", "How we work", "Get in touch", "Testimonials", "Currently"]
    if any(any(g.lower() in s.lower() for g in generic_kickers) for s in section_labels):
        findings.append({
            "severity": "HIGH",
            "id": "AP-4 + AP-7",
            "name": "stencil-section-order + kicker-eyebrow",
            "evidence": f"Section kickers: {section_labels}",
            "fix": "Drop the kickers entirely. Restructure sections around a non-stencil organization specific to this person/firm — not the textbook 'Currently / Selected / Testimonials / CTA' rhythm.",
        })

    if re.search(r"transform:\s*translateY\(-?\d+px\)", css) and "box-shadow" in css:
        findings.append({
            "severity": "MEDIUM",
            "id": "AP-5",
            "name": "hover-up-cards",
            "evidence": "`transform: translateY` + `box-shadow` hover pattern in CSS",
            "fix": "Drop the hover-lift. Either no hover effect, or one tied to specific content (border-flicker, content reveal). Generic uniform hover is dead.",
        })

    if re.search(r"--bg-alt:\s*#f[0-9a-f]{5}", css, re.I):
        findings.append({
            "severity": "MEDIUM",
            "id": "AP-6",
            "name": "soft-tint-alt-section",
            "evidence": "CSS variable `--bg-alt` with subtle off-white tint",
            "fix": "Either pure white throughout, or commit to high-contrast section breaks (white vs. deep-color, or full-bleed photo).",
        })

    testimonial_count = html.count("testimonial-card") + html.count("testimonial ")
    if testimonial_count == 3:
        findings.append({
            "severity": "MEDIUM",
            "id": "AP-8",
            "name": "3-equal-testimonial-cards",
            "evidence": "3 equal testimonial cards in a row",
            "fix": "One huge pull quote OR zero testimonials OR testimonials integrated as inline asides. Not 3 equal cards.",
        })

    footer_cols = html.count('class="footer-col"')
    if footer_cols >= 3:
        findings.append({
            "severity": "MEDIUM",
            "id": "AP-9",
            "name": "4-col-footer-with-labels",
            "evidence": f"{footer_cols}-column footer with labelled lists",
            "fix": "Replace with 1-line footer (copyright + 1 link) OR a maximalist footer that's part of the design (not org-chart layout).",
        })

    if 'class="btn btn-primary"' in html and 'class="btn btn-secondary"' in html:
        findings.append({
            "severity": "MEDIUM",
            "id": "AP-10",
            "name": "pill-button-pair",
            "evidence": "Hero has filled+outline button pair",
            "fix": "Single button OR no buttons (email address as styled inline link). Filled+outline pair is template.",
        })

    if re.search(r'class="service-num">\s*0\d', html):
        findings.append({
            "severity": "LOW",
            "id": "AP-11",
            "name": "numbered-service-cards",
            "evidence": "01 / 02 / 03 numbering on service cards",
            "fix": "Drop the numbers, or replace with something specific (years, names, single-word identifiers).",
        })

    if re.search(r"\.cta-section[\s\S]{0,300}background:\s*(?:#1[0-2]|#0[0-9a-f]|var\(--ink\))", css, re.I):
        findings.append({
            "severity": "MEDIUM",
            "id": "AP-13",
            "name": "gradient-CTA-section",
            "evidence": "Dark/accent full-bleed CTA section",
            "fix": "Replace with email-as-inline-link in body, OR sticky-footer email visible always. Dark CTA section is template.",
        })

    container_padding = re.findall(r"padding:\s*(\d+)px\s+0", css)
    if container_padding and len(set(container_padding)) <= 1 and container_padding[0] in ("96", "100", "120"):
        findings.append({
            "severity": "MEDIUM",
            "id": "AP-15 + Principle 13",
            "name": "uniform-section-padding",
            "evidence": f"Section padding repeated as `{container_padding[0]}px 0` on multiple sections",
            "fix": "Vary section heights: hero might be 400px, services 800px, quote 200px, portfolio 1200px. Rhythm > uniform.",
        })

    return findings


def cmd_review(args):
    target = args.target
    site_name = args.site_name or re.sub(r"^https?://(www\.)?", "", target).split("/")[0].replace(".", "-")
    out_dir = OUT_BASE / site_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "review.md"

    # Try to find local source by inferring from site_name
    src_dir = None
    candidates = [
        Path.home() / f"{site_name}-site",
        Path.home() / site_name.replace("-", ""),
        Path.home() / site_name,
    ]
    for c in candidates:
        if c.exists() and (c / "index.html").exists():
            src_dir = c
            break

    if args.source:
        src_dir = Path(args.source)

    html = ""
    css = ""
    if src_dir and (src_dir / "index.html").exists():
        html = (src_dir / "index.html").read_text()
        css_path = src_dir / "style.css"
        if css_path.exists():
            css = css_path.read_text()

    findings = detect_anti_patterns(html, css) if html else []

    # Distinctiveness check
    distinct_score = 0
    distinct_notes = []
    if html:
        # Non-Inter+Fraunces font system (counts if neither default present, OR a non-default font present)
        non_default_fonts = ["Söhne", "Ranade", "Mona Sans", "Fraktion", "Tiempos", "IBM Plex",
                             "EB Garamond", "Geist", "Newsreader", "JetBrains Mono", "Geist Mono",
                             "Source Serif", "Söhne Mono", "Manrope", "Inter Tight", "DM Sans",
                             "Space Grotesk", "Crimson", "Playfair", "Cormorant"]
        has_non_default = any(f in html for f in non_default_fonts)
        has_inter_fraunces = "Inter:" in html and "Fraunces:" in html
        if has_non_default and not has_inter_fraunces:
            distinct_score += 1
            distinct_notes.append("custom font system (non-default pairing)")
        elif has_inter_fraunces:
            distinct_notes.append("DOWNGRADE: Inter+Fraunces still present")

        # Single-font system (no sans+serif pair) — strong distinctiveness signal
        font_imports = re.findall(r"family=([A-Za-z+]+)", html)
        non_mono_fonts = [f for f in font_imports if "Mono" not in f and "JetBrains" not in f and "Plex+Mono" not in f.replace(" ", "+")]
        if len(non_mono_fonts) == 1:
            distinct_score += 1
            distinct_notes.append("single-font system (one display face + optional mono)")

        # Non-card structure — typographic list
        if any(c in html for c in ["class=\"cv\"", "class=\"ledger\"", "class=\"case\""]):
            distinct_score += 1
            distinct_notes.append("typographic list structure (not a card grid)")

        # Custom hero / no buttons
        if 'class="hero-cta"' not in html and 'class="btn btn-primary"' not in html:
            distinct_score += 1
            distinct_notes.append("no hero button-pair (text-led or inline links)")

        # Off-grid framing on photo
        if "::after" in css and "border" in css and ("portrait" in css or "hero-photo-frame" in css):
            distinct_score += 1
            distinct_notes.append("off-grid frame on portrait/hero")

        # Mono in masthead / rubric — editorial register
        if "masthead-meta" in html or "rubric" in html:
            distinct_score += 1
            distinct_notes.append("editorial masthead/rubric pattern")

        # Italic accent in case names or lead — intentional, not stencil-italic-headline
        if 'class="thesis-lead"' in html or 'class="thesis"' in html:
            distinct_score += 1
            distinct_notes.append("custom thesis hero (no kicker+headline+lede+buttons stencil)")

    if distinct_score < 3:
        findings.append({
            "severity": "HIGH",
            "id": "DIST",
            "name": "distinctiveness-deficit",
            "evidence": f"Distinctiveness score: {distinct_score}/3 — {distinct_notes or 'no distinctive details detected'}",
            "fix": "Add at least 3 distinctive details NOT in the AI personal-site stencil. Examples: hand-set wordmark kerning, an off-grid image, a footnote/aside that interrupts, a one-shot color callout, real photography, custom font system, non-rectangular section.",
        })

    high = [f for f in findings if f["severity"] == "HIGH"]
    medium = [f for f in findings if f["severity"] == "MEDIUM"]
    low = [f for f in findings if f["severity"] == "LOW"]

    pass_signal = "FAIL" if high else ("PASS-WITH-FIXES" if medium else "PASS")

    md = [f"# Website-designer review — {site_name}", ""]
    md.append(f"**Verdict**: `{pass_signal}`")
    md.append(f"**Source**: {src_dir or '(no local source found)'}")
    md.append(f"**Target**: {target}")
    md.append(f"**Generated**: {datetime.now().isoformat(timespec='seconds')}")
    md.append("")
    md.append(f"**Counts**: {len(high)} HIGH, {len(medium)} MEDIUM, {len(low)} LOW")
    md.append("")
    if pass_signal == "FAIL":
        md.append("**This design is NOT ready to ship.** All HIGH findings must be addressed before claiming this site is 'pretty' or 'done.'")
        md.append("")

    for label, items in (("HIGH (ship-blocker)", high), ("MEDIUM (loose end)", medium), ("LOW (polish)", low)):
        if not items:
            continue
        md.append(f"## {label}")
        md.append("")
        for f in items:
            md.append(f"### {f['id']}: {f['name']}")
            md.append(f"**Evidence**: {f['evidence']}")
            md.append("")
            md.append(f"**Fix**: {f['fix']}")
            md.append("")

    if not findings:
        md.append("## No findings")
        md.append("")
        md.append("Static scan found no anti-patterns. Run a visual review next (graphic-layout + fakematt-feedback) to confirm.")

    out.write_text("\n".join(md))
    print(json.dumps({
        "ok": True,
        "verdict": pass_signal,
        "high": len(high),
        "medium": len(medium),
        "low": len(low),
        "review": str(out),
    }))


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="mode", required=True)

    pb = sub.add_parser("brief")
    pb.add_argument("--target", required=True)
    pb.add_argument("--persona", required=True)
    pb.add_argument("--references", default="")

    pr = sub.add_parser("review")
    pr.add_argument("target", help="URL or local path")
    pr.add_argument("--site-name", default="")
    pr.add_argument("--source", default="", help="local source dir override")

    args = p.parse_args()
    if args.mode == "brief":
        cmd_brief(args)
    else:
        cmd_review(args)


if __name__ == "__main__":
    main()
