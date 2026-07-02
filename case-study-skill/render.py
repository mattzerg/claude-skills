#!/usr/bin/env python3
"""Marketing-grade case study renderer — Stripe / Vercel / OpenAI customer-story register.

Reads a vault case-study markdown + optional sidecar `<slug>.meta.json` for
hero stats / about-customer profile / quote / architecture diagram, applies
Zerg-styled CSS, renders single PDF via Chrome headless. Output filenames are
auto-versioned (`<slug>-v<N>-YYYY-MM-DD.pdf`) so iterations don't overwrite.

Usage:
    python3 /tmp/render_case_study.py <case-study.md> [--draft] [--version vN]

Sidecar JSON schema (optional, looks up <slug>.meta.json next to the .md):
{
  "stats": [
    {"value": "Apr 15, 2026", "label": "v2 orchestration milestone"},
    {"value": "1",            "label": "unified observability tab"}
  ],
  "about": {
    "industry":   "Enterprise software",
    "engagement": "Active delivery",
    "started":    "April 2026",
    "owner":      "Andre Ricardo",
    "products":   "ZCloud, ZTC"
  },
  "exec_summary": [
    "Bullet 1",
    "Bullet 2",
    "Bullet 3"
  ],
  "context": "About-the-customer paragraph(s) for Industry section.",
  "architecture_svg": "<svg>...</svg>",
  "pull_quote": {"text": "...", "speaker": "Name", "title": "Title", "company": "Company"},
  "related": [
    {"client": "CesiumAstro", "headline": "Atlas live in AWS GovCloud",   "status": "in capture"},
    {"client": "Andesite",    "headline": "Metamorph automates connectors","status": "NDA gated"}
  ]
}
"""
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path
import urllib.parse
import markdown

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

CSS = r"""
<style>
  @page { size: Letter; margin: 0.4in 0.6in 0.5in 0.6in; }

  :root {
    --ink:        #111514;       /* Zerg charcoal (live-site) */
    --ink-soft:   #1f2522;
    --ink-medium: #41504c;
    --muted:      #52605c;       /* Zerg mid-gray (live-site) */
    --rule:       #dad6cb;       /* Zerg rule-gray (~rgba(17,21,20,0.15) on cream) */
    --rule-soft:  #ECECEC;
    --accent:     #b3662f;       /* Zerg burnt orange (live-site primary) */
    --accent-2:   #8a4a1f;       /* darker burnt rust (AA-contrast on cream) */
    --accent-bg:  rgba(179,102,47,0.08);
    --soft-bg:    #f4f0e7;       /* Zerg cream paper (live-site bg) */
    --warn-bg:    #fff8e1;
    --warn-ink:   #8a6d00;
    --warn-rule:  #f0e0a0;
  }

  * { box-sizing: border-box; }

  body {
    font-family: 'Space Grotesk', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, sans-serif;
    font-size: 10.5pt;
    line-height: 1.6;
    color: var(--ink-soft);
    margin: 0;
    padding: 0;
  }

  /* ---------- Brand bar ---------- */
  .brand-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0 0 10pt 0;
    margin-bottom: 18pt;
    border-bottom: 1px solid var(--rule);
    font-size: 9pt;
    text-transform: uppercase;
    letter-spacing: 0.10em;
  }
  .brand-bar .lockup {
    display: flex;
    align-items: center;
    gap: 10pt;
  }
  .brand-bar .lockup .zerg-mark {
    background: var(--ink);
    color: #fff;
    padding: 3pt 7pt;
    font-weight: 700;
    letter-spacing: 0.18em;
    border-radius: 2pt;
    font-size: 8pt;
  }
  .brand-bar .lockup .x { color: var(--muted); font-weight: 400; }
  .brand-bar .lockup .client {
    font-weight: 600;
    color: var(--ink);
    letter-spacing: 0.14em;
  }
  .brand-bar .right {
    color: var(--muted);
    font-size: 8.5pt;
    font-weight: 500;
  }

  /* ---------- Hero ---------- */
  .hero { margin: 6pt 0 22pt 0; }
  .hero .eyebrow {
    font-size: 9pt;
    font-weight: 700;
    color: var(--accent);
    text-transform: uppercase;
    letter-spacing: 0.16em;
    margin-bottom: 8pt;
  }
  .hero h1 {
    font-size: 30pt;
    line-height: 1.15;
    font-weight: 800;
    color: var(--ink);
    margin: 0 0 14pt 0;
    letter-spacing: -0.02em;
    max-width: 7.5in;
  }
  .hero .dek {
    font-size: 13.5pt;
    line-height: 1.5;
    color: var(--ink-medium);
    margin: 0;
    font-weight: 400;
    max-width: 7in;
  }
  .hero .dek p { margin: 0; }

  /* ---------- Stats strip ---------- */
  .stats-strip {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0;
    border-top: 1px solid var(--rule);
    border-bottom: 1px solid var(--rule);
    margin: 22pt 0 24pt 0;
    padding: 16pt 0;
  }
  .stats-strip .stat {
    padding: 0 14pt;
    border-right: 1px solid var(--rule-soft);
  }
  .stats-strip .stat:last-child { border-right: none; }
  .stats-strip .stat .value {
    font-size: 19pt;
    font-weight: 800;
    color: var(--ink);
    line-height: 1.1;
    letter-spacing: -0.01em;
    margin-bottom: 4pt;
  }
  .stats-strip .stat .label {
    font-size: 8.5pt;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    line-height: 1.35;
  }

  /* ---------- Two-column intro: exec summary + about box ---------- */
  .intro-grid {
    display: grid;
    grid-template-columns: 1.6fr 1fr;
    gap: 24pt;
    margin: 0 0 24pt 0;
  }
  .intro-grid .summary h2 {
    margin-top: 0;
  }
  .intro-grid .summary ul {
    list-style: none;
    padding: 0;
    margin: 8pt 0 0 0;
  }
  .intro-grid .summary li {
    position: relative;
    padding: 0 0 9pt 18pt;
    font-size: 11pt;
    line-height: 1.5;
    color: var(--ink-soft);
  }
  .intro-grid .summary li::before {
    content: "";
    position: absolute;
    left: 0;
    top: 8pt;
    width: 6pt;
    height: 6pt;
    background: var(--accent);
    border-radius: 50%;
  }

  .about-box {
    background: var(--soft-bg);
    border: 1px solid var(--rule);
    border-radius: 4pt;
    padding: 18pt 18pt;
    font-size: 9.5pt;
  }
  .about-box .label {
    font-size: 8pt;
    color: var(--accent);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    margin-bottom: 12pt;
  }
  .about-box dl { margin: 0; padding: 0; }
  .about-box dt {
    font-size: 8pt;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin: 8pt 0 2pt 0;
    font-weight: 600;
  }
  .about-box dt:first-of-type { margin-top: 0; }
  .about-box dd {
    margin: 0 0 0 0;
    color: var(--ink);
    font-weight: 500;
    line-height: 1.4;
  }

  /* ---------- Section headers with eyebrows ---------- */
  h2 {
    font-size: 11pt;
    font-weight: 700;
    color: var(--ink);
    margin: 28pt 0 14pt 0;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    padding-top: 14pt;
    border-top: 1px solid var(--rule);
    position: relative;
  }
  h2 .num {
    color: var(--accent);
    font-weight: 800;
    margin-right: 10pt;
    font-size: 10pt;
    letter-spacing: 0.08em;
  }
  h2.no-rule { border-top: none; padding-top: 0; }

  h3 {
    font-size: 11pt;
    font-weight: 700;
    color: var(--ink);
    margin: 16pt 0 6pt 0;
  }

  p { margin: 0 0 11pt 0; }
  p strong:first-child { color: var(--ink); }

  /* ---------- Phase timeline cards ---------- */
  .phases {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12pt;
    margin: 14pt 0 18pt 0;
  }
  .phases .phase {
    border: 1px solid var(--rule);
    border-radius: 4pt;
    padding: 12pt 14pt;
    background: #fff;
  }
  .phases .phase .num {
    font-size: 8pt;
    color: var(--accent);
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    margin-bottom: 4pt;
  }
  .phases .phase .name {
    font-size: 10.5pt;
    font-weight: 700;
    color: var(--ink);
    margin-bottom: 6pt;
  }
  .phases .phase .date {
    font-size: 8.5pt;
    color: var(--muted);
    margin-bottom: 8pt;
    font-weight: 500;
  }
  .phases .phase .body {
    font-size: 9.5pt;
    line-height: 1.5;
    color: var(--ink-medium);
  }

  /* ---------- Architecture diagram wrapper ---------- */
  .architecture {
    margin: 18pt 0 22pt 0;
    padding: 18pt;
    background: var(--soft-bg);
    border: 1px solid var(--rule);
    border-radius: 4pt;
    text-align: center;
  }
  .architecture .caption {
    font-size: 9pt;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.10em;
    font-weight: 600;
    margin-top: 12pt;
  }
  .architecture svg { max-width: 100%; height: auto; }

  /* ---------- Stack-used callout ---------- */
  .stack-callout {
    background: var(--accent-bg);
    border-left: 3px solid var(--accent);
    padding: 14pt 18pt;
    margin: 18pt 0;
    border-radius: 2pt;
  }
  .stack-callout h3 {
    margin: 0 0 8pt 0;
    color: var(--accent);
    font-size: 8.5pt;
    text-transform: uppercase;
    letter-spacing: 0.14em;
  }
  .stack-callout ul { margin: 0; padding-left: 16pt; }
  .stack-callout li { margin: 4pt 0; font-size: 10.5pt; }
  .stack-callout strong { color: var(--ink); font-weight: 700; }

  /* ---------- Pull quote ---------- */
  .pullquote {
    margin: 24pt 0;
    padding: 22pt 26pt;
    background: var(--soft-bg);
    border-left: 3px solid var(--accent);
    border-radius: 2pt;
  }
  .pullquote .quote {
    font-size: 14pt;
    line-height: 1.45;
    color: var(--ink);
    font-style: italic;
    margin: 0 0 14pt 0;
    font-weight: 500;
  }
  .pullquote .quote::before { content: "\201C"; font-size: 22pt; color: var(--accent); margin-right: 4pt; line-height: 0; vertical-align: -8pt; }
  .pullquote .quote::after  { content: "\201D"; font-size: 22pt; color: var(--accent); margin-left: 4pt;  line-height: 0; vertical-align: -8pt; }
  .pullquote .attribution {
    font-size: 9pt;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
  }
  .pullquote .attribution strong { color: var(--ink); font-weight: 700; }
  .pullquote.placeholder .quote { color: var(--muted); font-style: italic; }
  .pullquote.placeholder .attribution { color: var(--warn-ink); }

  /* ---------- Results ---------- */
  .results-block ul {
    list-style: none;
    padding-left: 0;
    margin: 8pt 0 0 0;
  }
  .results-block li {
    background: var(--soft-bg);
    border-left: 2px solid var(--accent);
    padding: 12pt 16pt;
    margin: 8pt 0;
    border-radius: 2pt;
  }
  .results-block li strong {
    color: var(--ink);
    display: block;
    margin-bottom: 4pt;
    font-size: 11pt;
    font-weight: 700;
  }
  .results-block li em {
    color: var(--muted);
    font-style: italic;
    font-size: 9.5pt;
  }

  /* Generic body lists */
  ul { margin: 4pt 0 11pt 0; padding-left: 22pt; }
  li { margin: 4pt 0; }
  li strong { color: var(--ink); }

  /* ---------- CTA box ---------- */
  .cta-box {
    background: var(--ink);
    color: #ffffff;
    padding: 24pt 26pt;
    margin: 30pt 0 18pt 0;
    border-radius: 4pt;
    display: grid;
    grid-template-columns: 1.6fr auto;
    gap: 24pt;
    align-items: center;
  }
  .cta-box h2 {
    color: #ffffff;
    border: none;
    padding: 0;
    margin: 0 0 6pt 0;
    font-size: 15pt;
    text-transform: none;
    letter-spacing: -0.005em;
    font-weight: 700;
  }
  .cta-box p { margin: 0; font-size: 10.5pt; line-height: 1.5; color: #cbd2dd; }
  .cta-box .button {
    display: inline-block;
    background: #fff;
    color: var(--ink);
    padding: 10pt 20pt;
    border-radius: 3pt;
    font-weight: 700;
    text-decoration: none;
    border: none;
    font-size: 10.5pt;
    letter-spacing: 0.02em;
    white-space: nowrap;
  }

  /* ---------- Related case studies ---------- */
  .related {
    margin-top: 24pt;
    padding-top: 18pt;
    border-top: 1px solid var(--rule);
  }
  .related .title {
    font-size: 9pt;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-weight: 700;
    margin-bottom: 10pt;
  }
  .related .grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12pt;
  }
  .related .card {
    border: 1px solid var(--rule);
    border-radius: 4pt;
    padding: 12pt 14pt;
  }
  .related .card .client {
    font-size: 9pt;
    color: var(--accent);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.10em;
    margin-bottom: 4pt;
  }
  .related .card .head {
    font-size: 10.5pt;
    line-height: 1.35;
    color: var(--ink);
    font-weight: 600;
    margin-bottom: 4pt;
  }
  .related .card .status {
    font-size: 8.5pt;
    color: var(--muted);
    font-style: italic;
  }

  /* ---------- Recommended quotes (page 2, internal use) ---------- */
  .page-break { page-break-before: always; }
  .rq-page {
    padding-top: 8pt;
  }
  .rq-eyebrow {
    background: var(--warn-bg);
    color: var(--warn-ink);
    border: 1px solid var(--warn-rule);
    padding: 6pt 10pt;
    font-size: 8pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    border-radius: 2pt;
    margin-bottom: 16pt;
    text-align: center;
  }
  .rq-h2 {
    font-size: 17pt;
    font-weight: 800;
    color: var(--ink);
    margin: 0 0 8pt 0;
    letter-spacing: -0.01em;
    border: none;
    padding: 0;
    text-transform: none;
  }
  .rq-intro {
    font-size: 10pt;
    color: var(--ink-medium);
    line-height: 1.55;
    max-width: 6.5in;
    margin: 0 0 22pt 0;
  }
  .rq-cards { display: grid; grid-template-columns: 1fr; gap: 14pt; }
  .rq-card {
    border: 1px solid var(--rule);
    border-left: 3px solid var(--accent);
    border-radius: 3pt;
    padding: 16pt 20pt;
    background: #ffffff;
    page-break-inside: avoid;
  }
  .rq-num {
    font-size: 8pt;
    color: var(--accent);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-bottom: 8pt;
  }
  .rq-quote {
    font-size: 12pt;
    line-height: 1.5;
    color: var(--ink);
    font-style: italic;
    font-weight: 500;
    margin: 0 0 10pt 0;
  }
  .rq-attribution {
    font-size: 9pt;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
    margin-bottom: 12pt;
  }
  .rq-rationale {
    font-size: 9pt;
    line-height: 1.5;
    color: var(--ink-medium);
    background: var(--soft-bg);
    padding: 8pt 12pt;
    border-radius: 2pt;
  }
  .rq-rationale strong { color: var(--ink); font-weight: 700; }

  /* Footer */
  .footer-note {
    margin-top: 18pt;
    padding-top: 10pt;
    border-top: 1px solid var(--rule);
    font-size: 8pt;
    color: var(--muted);
    text-align: center;
    letter-spacing: 0.08em;
  }

  /* Misc */
  a { color: var(--accent); text-decoration: none; border-bottom: 1px solid var(--accent); }
  hr { border: none; border-top: 1px solid var(--rule); margin: 24pt 0; }

  /* ---------- Page-break discipline: no card/box may cross a page boundary ---------- */
  .stats-strip,
  .about-box,
  .intro-grid .summary,
  .phases .phase,
  .architecture,
  .stack-callout,
  .pullquote,
  .results-block li,
  .cta-box,
  .related,
  .related .card,
  .rq-card {
    page-break-inside: avoid;
    break-inside: avoid;
  }
  h2, h3 { page-break-after: avoid; break-after: avoid; }

  /* Draft watermark */
  .draft-banner {
    background: var(--warn-bg);
    color: var(--warn-ink);
    text-align: center;
    padding: 5pt;
    font-size: 8pt;
    text-transform: uppercase;
    letter-spacing: 0.20em;
    font-weight: 700;
    border-bottom: 1px solid var(--warn-rule);
    margin: -0.4in -0.6in 18pt -0.6in;
  }
</style>
"""


def parse_md(path: Path) -> tuple[dict, str]:
    text = path.read_text()
    fm = {}
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            for line in text[3:end].strip().splitlines():
                if ":" in line and not line.startswith(" ") and not line.startswith("-"):
                    k, _, v = line.partition(":")
                    fm[k.strip()] = v.strip().strip('"').strip("'")
            text = text[end + 4:].lstrip()
    return fm, text


def strip_internal_sections(body: str) -> str:
    cut_markers = [
        "\n## Drafting notes for the author",
        "\n---\n\n## Drafting notes",
        "\n## Drafting notes",
    ]
    for marker in cut_markers:
        idx = body.find(marker)
        if idx != -1:
            body = body[:idx].rstrip()
            break
    body = re.sub(r"\n+---\s*$", "", body).rstrip()
    return body


def strip_wikilinks(text: str) -> str:
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", lambda m: m.group(1).split("/")[-1], text)
    return text


def render_phases(body: str) -> tuple[str, str]:
    """Find `**Phase N — Name (date).** body` patterns under the Approach H2 and pull
    them out into a styled timeline grid.

    Returns (modified_body, phases_html). If no phases are found, phases_html is empty.
    """
    pattern = re.compile(
        r"\*\*Phase\s+(\d+)\s*[—-]\s*([^(]+?)\s*\(([^)]+)\)\.\*\*\s+(.+?)(?=\n\n\*\*Phase|\n\n##|\Z)",
        re.DOTALL,
    )
    phases = []
    for m in pattern.finditer(body):
        phases.append({
            "num": m.group(1).strip(),
            "name": m.group(2).strip(),
            "date": m.group(3).strip(),
            "body": m.group(4).strip(),
        })
    if not phases:
        return body, ""
    body = pattern.sub("", body)
    cards = []
    for p in phases:
        cards.append(f"""
        <div class="phase">
          <div class="num">Phase {p['num']}</div>
          <div class="name">{p['name']}</div>
          <div class="date">{p['date']}</div>
          <div class="body">{markdown.markdown(p['body'])[3:-4]}</div>
        </div>
        """)
    return body, f'<div class="phases">{"".join(cards)}</div>'


def transform_stack_used(html: str) -> str:
    pattern = re.compile(r"<h3>Stack used</h3>\s*(<ul>.*?</ul>)", re.DOTALL | re.IGNORECASE)
    return pattern.sub(lambda m: f'<div class="stack-callout"><h3>Zerg stack used</h3>{m.group(1)}</div>', html)


def transform_results_block(html: str) -> str:
    pattern = re.compile(r"(<h2[^>]*>Results.*?</h2>)(\s*<p>.*?</p>)?\s*(<ul>.*?</ul>)", re.DOTALL | re.IGNORECASE)
    def replace(m):
        return f'{m.group(1)}<div class="results-block">{m.group(2) or ""}{m.group(3)}</div>'
    return pattern.sub(replace, html)


def transform_cta(html: str) -> str:
    pattern = re.compile(r"<h2[^>]*>(Ready[^<]*)</h2>\s*(<p>.*?</p>)", re.DOTALL | re.IGNORECASE)
    def replace(m):
        # Pull out [Talk to Zerg](url) link from the paragraph if present
        para = m.group(2)
        link_match = re.search(r'<a href="([^"]+)"[^>]*>([^<]+)</a>', para)
        link_html = ""
        if link_match:
            link_html = f'<a class="button" href="{link_match.group(1)}">{link_match.group(2)} &rarr;</a>'
            # Replace the inline link in paragraph with the visible text only
            para = re.sub(r'<a href="[^"]+"[^>]*>([^<]+)</a>\.?\s*', "", para, count=1)
        body_inner = f'<div><h2>{m.group(1)}</h2>{para}</div>'
        return f'<div class="cta-box">{body_inner}{link_html}</div>'
    return pattern.sub(replace, html)


SECTION_NUMBERS = {
    "About the customer": "01",
    "The challenge":      "02",
    "Why Zerg":           "03",
    "Approach":           "04",
    "What Zerg built":    "05",
    "Architecture":       "06",
    "Results":            "07",
    "What's next":        "08",
}


def add_section_numbers(html: str) -> str:
    """Prefix matching <h2> blocks with eyebrow numbering."""
    def replace(m):
        title = m.group(1).strip()
        # match SECTION_NUMBERS by case-insensitive prefix
        for k, v in SECTION_NUMBERS.items():
            if title.lower().startswith(k.lower()):
                return f'<h2><span class="num">{v}</span>{title}</h2>'
        return m.group(0)
    return re.sub(r"<h2>(.*?)</h2>", replace, html, flags=re.DOTALL)


def first_h2_no_rule(html: str) -> str:
    """First numbered H2 should not have a top border/padding (since stats strip + intro grid
    already create a strong visual separator)."""
    return re.sub(r"<h2>", "<h2>", html, count=1)


def render_stats_strip(stats: list[dict]) -> str:
    if not stats:
        return ""
    cells = []
    for s in stats[:4]:
        cells.append(f'<div class="stat"><div class="value">{s["value"]}</div><div class="label">{s["label"]}</div></div>')
    return f'<div class="stats-strip">{"".join(cells)}</div>'


def render_about_box(about: dict) -> str:
    """About-the-customer sidebar. Project-owner field is intentionally NOT rendered
    (template-level decision, 2026-05-06): identifying individual Zerg engineers
    in customer-facing case studies isn't appropriate for the genre.
    """
    if not about:
        return ""
    rows = []
    label_map = [
        ("industry",   "Industry"),
        ("size",       "Size"),
        ("location",   "Location"),
        ("founded",    "Founded"),
        ("engagement", "Engagement"),
        ("started",    "Started"),
        # ("owner", "Zerg owner") — INTENTIONALLY OMITTED. See above.
        ("products",   "Products used"),
    ]
    for k, label in label_map:
        if k in about and about[k]:
            rows.append(f"<dt>{label}</dt><dd>{about[k]}</dd>")
    return f'<div class="about-box"><div class="label">About the customer</div><dl>{"".join(rows)}</dl></div>'


def render_intro_grid(exec_summary: list[str], about_box_html: str) -> str:
    if not exec_summary and not about_box_html:
        return ""
    summary_html = ""
    if exec_summary:
        items = "".join(f"<li>{b}</li>" for b in exec_summary)
        summary_html = f'<div class="summary"><h2 class="no-rule"><span class="num">00</span>At a glance</h2><ul>{items}</ul></div>'
    return f'<div class="intro-grid">{summary_html}{about_box_html}</div>'


def render_pullquote(q):
    if not q:
        return ""
    if q.get("placeholder"):
        cls = "pullquote placeholder"
        text = q.get("text", "Pull quote pending capture from named customer contact.")
        attrib = q.get("attribution", "Quote capture in flight")
    else:
        cls = "pullquote"
        text = q.get("text", "")
        speaker = q.get("speaker", "")
        title = q.get("title", "")
        company = q.get("company", "")
        attrib = f'<strong>{speaker}</strong>'
        if title:
            attrib += f' &middot; {title}'
        if company:
            attrib += f', {company}'
    return f'<div class="{cls}"><div class="quote">{text}</div><div class="attribution">{attrib}</div></div>'


def render_architecture(svg: str, caption: str = "Engagement architecture") -> str:
    if not svg:
        return ""
    return f'<div class="architecture">{svg}<div class="caption">{caption}</div></div>'


def render_recommended_quotes(quotes):
    """Page-2 block: 3 quote-shape options for the customer contact to pick from
    or rephrase. Internal-facing — included on the rendered PDF when a verbatim
    quote isn't yet captured, so Idan can show the contact 'here are the shapes
    we'd want; pick one or write your own in this register.'
    """
    if not quotes:
        return ""
    cards = []
    for i, q in enumerate(quotes[:3], start=1):
        cards.append(
            f'<div class="rq-card">'
            f'<div class="rq-num">Option {i} · {q.get("angle", "")}</div>'
            f'<div class="rq-quote">"{q.get("text", "")}"</div>'
            f'<div class="rq-attribution">— {q.get("attribution", "[Title], [Client]")}</div>'
            f'<div class="rq-rationale"><strong>Why this shape:</strong> {q.get("rationale", "")}</div>'
            f'</div>'
        )
    return f'''
<div class="page-break"></div>
<div class="rq-page">
  <div class="rq-eyebrow">FOR INTERNAL USE — NOT PART OF PUBLISHED CASE STUDY</div>
  <h2 class="rq-h2">Recommended quote shapes for customer contact</h2>
  <p class="rq-intro">Three quote framings the customer contact could pick from or rephrase. Designed to be shared with the named contact at the client when requesting a quote — gives them a starting point so the ask isn't open-ended. The contact's actual words go in the published case study; these are scaffolding only.</p>
  <div class="rq-cards">{"".join(cards)}</div>
</div>'''


def render_related(related: list[dict]) -> str:
    if not related:
        return ""
    cards = []
    for r in related:
        cards.append(
            f'<div class="card">'
            f'<div class="client">{r.get("client", "")}</div>'
            f'<div class="head">{r.get("headline", "")}</div>'
            f'<div class="status">{r.get("status", "")}</div>'
            f'</div>'
        )
    return f'<div class="related"><div class="title">More Zerg customer stories</div><div class="grid">{"".join(cards)}</div></div>'


def next_version(out_dir: Path, slug: str) -> str:
    """Walk out_dir for prior renders of `slug` and return next vN."""
    out_dir.mkdir(exist_ok=True, parents=True)
    pat = re.compile(rf"^{re.escape(slug)}-v(\d+)(?:-\d{{4}}-\d{{2}}-\d{{2}})?\.pdf$")
    highest = 0
    for f in out_dir.iterdir():
        m = pat.match(f.name)
        if m:
            highest = max(highest, int(m.group(1)))
    return f"v{highest + 1}"


def check_unapplied_feedback(md_path, target_version, force=False):
    """Refuse to render if reviewer-feedback artifacts next to the draft
    aren't marked applied. Fixes the May-2026 Durable failure mode where
    Idan's fakeidan ship-blockers lived only in Slack and the next render
    pass shipped without them.

    Convention: a feedback file at `<parent>/<slug>.fakeidan-feedback-YYYY-MM-DD.md`
    (or `.fakematt-feedback-*.md`, `.fakeidan-copyedit-*.md`, `.fakematt-copyedit-*.md`,
    or `.feedback-*.md`) MUST carry an `applied_in: vN` frontmatter line once its
    notes are folded into the draft. Render refuses while the line is missing or
    points at a version older than the one we're rendering.

    Bypass with --force-unapplied-feedback (intentional only).
    """
    slug = md_path.stem
    parent = md_path.parent
    patterns = [
        f"{slug}.fakeidan-feedback-*.md",
        f"{slug}.fakematt-feedback-*.md",
        f"{slug}.fakeidan-copyedit-*.md",
        f"{slug}.fakematt-copyedit-*.md",
        f"{slug}.feedback-*.md",
    ]
    candidates = []
    for p in patterns:
        candidates.extend(parent.glob(p))
    candidates = sorted(set(candidates))
    if not candidates:
        return
    unapplied = []
    for fb in candidates:
        try:
            text = fb.read_text(errors="ignore")
        except Exception:
            continue
        m = re.search(r"^applied_in:\s*(\S+)\s*$", text, re.M)
        if not m:
            unapplied.append((fb, "missing `applied_in:` frontmatter line"))
            continue
        applied = m.group(1).strip()
        if target_version:
            try:
                a_num = int(applied.lstrip("v"))
                t_num = int(target_version.lstrip("v"))
                if a_num < t_num:
                    unapplied.append((fb, f"applied_in: {applied} predates target render version {target_version}"))
            except ValueError:
                pass
    if not unapplied:
        return
    lines = ["", "REFUSING TO RENDER: unapplied feedback artifacts next to draft.", ""]
    for fb, reason in unapplied:
        lines.append(f"  - {fb.name}")
        lines.append(f"      {reason}")
    lines.append("")
    lines.append("Fix: apply the feedback to the draft, then add to the feedback file's")
    lines.append(f"frontmatter:  applied_in: {target_version or 'vN'}")
    lines.append("")
    lines.append("Override (only when intentionally re-rendering with feedback pending):")
    lines.append("  --force-unapplied-feedback")
    lines.append("")
    print("\n".join(lines), file=sys.stderr)
    if not force:
        sys.exit(2)


def render(md_path, draft=False, version=None):
    fm, body = parse_md(md_path)
    body = strip_internal_sections(body)
    body = strip_wikilinks(body)

    # Sidecar meta (rich elements not expressible in plain markdown)
    meta_path = md_path.with_suffix("").with_name(md_path.stem + ".meta.json")
    meta = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())

    # Pull title (first H1) and dek (first blockquote) out of body for hero treatment
    h1_match = re.search(r"^# (.+?)\n", body, re.MULTILINE)
    dek_match = re.search(r"^> (.+?)(?:\n(?!>)|\Z)", body, re.MULTILINE | re.DOTALL)

    title = h1_match.group(1).strip() if h1_match else fm.get("client", "Case Study")
    dek = ""
    if dek_match:
        dek = "\n".join(line.lstrip("> ").lstrip(">") for line in dek_match.group(1).split("\n")).strip()

    if h1_match:
        body = body[: h1_match.start()] + body[h1_match.end():]
    body = re.sub(r"^> (.+?)(?:\n(?!>)|\Z)", "", body, count=1, flags=re.MULTILINE | re.DOTALL).lstrip()

    # Inject "About the customer" prose section AFTER the dek/intro grid but BEFORE "The challenge"
    if "context" in meta and meta["context"]:
        # Find first occurrence of "## The challenge" and insert before it
        ctx_block = f"\n\n## About the customer\n\n{meta['context']}\n\n"
        body = re.sub(r"\n## The challenge", ctx_block + "## The challenge", body, count=1)

    # Inject pullquote after "What Zerg built" section (or after Approach if WZB absent)
    pq_html = render_pullquote(meta.get("pull_quote"))

    # Pull phases out before HTML conversion
    body, phases_html = render_phases(body)

    body_html = markdown.markdown(body, extensions=["tables", "fenced_code"])

    # Inject phases right after the Approach H2's body (if found, the H2 is now followed by a stripped paragraph)
    if phases_html:
        body_html = re.sub(
            r"(<h2[^>]*>Approach.*?</h2>\s*<p>.*?</p>)",
            r"\1" + phases_html,
            body_html,
            count=1,
            flags=re.DOTALL | re.IGNORECASE,
        )
        # If no <p> followed Approach, insert after the H2 directly
        if phases_html not in body_html:
            body_html = re.sub(
                r"(<h2[^>]*>Approach.*?</h2>)",
                r"\1" + phases_html,
                body_html,
                count=1,
                flags=re.IGNORECASE,
            )

    # Inject architecture diagram after "What Zerg built" first paragraph
    arch_html = render_architecture(meta.get("architecture_svg", ""), meta.get("architecture_caption", "Engagement architecture"))
    if arch_html:
        body_html = re.sub(
            r"(<h2[^>]*>What Zerg built.*?</h2>\s*<p>.*?</p>)",
            r"\1" + arch_html,
            body_html,
            count=1,
            flags=re.DOTALL | re.IGNORECASE,
        )

    # Inject pullquote AFTER the stack-used callout (which sits inside "What Zerg built")
    body_html = transform_stack_used(body_html)
    if pq_html:
        body_html = re.sub(
            r'(</div>\s*)(<h2[^>]*>Results)',
            r"\1" + pq_html + r"\2",
            body_html,
            count=1,
            flags=re.DOTALL | re.IGNORECASE,
        )

    body_html = transform_results_block(body_html)
    body_html = transform_cta(body_html)
    body_html = add_section_numbers(body_html)

    # Build header pieces from frontmatter + meta
    client = fm.get("client", "")
    sector = fm.get("sector", "").replace("-", " ").title()
    timeframe = fm.get("timeframe", "")

    stats_html = render_stats_strip(meta.get("stats", []))
    about_html = render_about_box(meta.get("about", {}))
    intro_grid_html = render_intro_grid(meta.get("exec_summary", []), about_html)
    related_html = render_related(meta.get("related", []))
    rq_html = render_recommended_quotes(meta.get("recommended_quotes", []))

    draft_banner = (
        '<div class="draft-banner">DRAFT &middot; For internal review and approval &middot; not for external distribution</div>'
        if draft else ""
    )

    full_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{client} customer story</title>{CSS}</head>
<body>
{draft_banner}

<div class="brand-bar">
  <div class="lockup">
    <span class="zerg-mark">ZERG</span>
    <span class="x">&times;</span>
    <span class="client">{client.upper()}</span>
  </div>
  <div class="right">Customer Story{' &middot; ' + sector if sector else ''}{' &middot; ' + timeframe if timeframe else ''}</div>
</div>

<div class="hero">
  <h1>{title}</h1>
  <div class="dek"><p>{dek}</p></div>
</div>

{stats_html}

{intro_grid_html}

{body_html}

{related_html}

<div class="footer-note">
  &copy; Zerg AI &middot; zergai.com &middot; {client} customer story
</div>

{rq_html}

</body></html>"""

    out_dir = Path("/tmp/case_study_pdf")
    out_dir.mkdir(exist_ok=True)
    today = dt.date.today().isoformat()
    ver = version or next_version(out_dir, md_path.stem)
    out_stem = f"{md_path.stem}-{ver}-{today}"
    html_path = out_dir / f"{out_stem}.html"
    pdf_path = out_dir / f"{out_stem}.pdf"
    html_path.write_text(full_html)

    file_url = "file://" + urllib.parse.quote(str(html_path.resolve()))
    subprocess.run(
        [CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
         f"--print-to-pdf={pdf_path}", file_url],
        check=True, capture_output=True,
    )
    # Post-render: strip blank pages per feedback_review_pack_one_file.md
    try:
        sys_path_zerg = "/Users/mattheweisner/.config/zerg"
        if sys_path_zerg not in sys.path:
            sys.path.insert(0, sys_path_zerg)
        from strip_blank_pages import strip_blank_pages
        n = strip_blank_pages(pdf_path)
        if n:
            print(f"  stripped {n} blank page(s)")
    except Exception as e:
        print(f"  (blank-page strip skipped: {e})")
    return pdf_path


if __name__ == "__main__":
    is_draft = "--draft" in sys.argv
    no_open = "--no-open" in sys.argv
    force_unapplied = "--force-unapplied-feedback" in sys.argv
    version = None
    if "--version" in sys.argv:
        i = sys.argv.index("--version")
        if i + 1 < len(sys.argv):
            version = sys.argv[i + 1]
    args = [a for i, a in enumerate(sys.argv[1:], start=1)
            if a not in ("--draft", "--no-open", "--version", "--force-unapplied-feedback")
            and (i == 0 or sys.argv[i - 1] != "--version")]
    if not args:
        print(
            "Usage: render_case_study.py <case-study.md> [--draft] [--no-open] "
            "[--version vN] [--force-unapplied-feedback]",
            file=sys.stderr,
        )
        sys.exit(1)
    md_path = Path(args[0])
    if not md_path.exists():
        print(f"MISSING: {md_path}", file=sys.stderr)
        sys.exit(1)
    check_unapplied_feedback(md_path, version, force=force_unapplied)
    pdf = render(md_path, draft=is_draft, version=version)
    print(pdf)
    if not no_open:
        subprocess.run(["open", "-a", "Preview", str(pdf)])
