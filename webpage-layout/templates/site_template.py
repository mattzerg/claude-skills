"""Site scaffold templates for `webpage-layout bootstrap`.

Renders all files needed for an AI-friendly static site:
  - index.html (with JSON-LD + alternate links + brand fonts)
  - index.md (markdown shadow)
  - llms.txt + llms-full.txt
  - robots.txt (with AI bot allowlist)
  - sitemap.xml
  - style.css starter (single-font system, accessible defaults)

Each template takes a Spec dict and returns the file content as a string.
"""
from __future__ import annotations
import json
from typing import TypedDict


class Spec(TypedDict, total=False):
    slug: str             # 'matteisn', 'vang-capital', 'my-project'
    domain: str           # 'matteisn.com'
    title: str            # 'Matthew Eisner'
    summary: str          # one-line description
    persona: str          # personal | fund | advisory | brand_product | other
    headline: str         # hero text
    body_paragraphs: list # list of paragraphs for the body
    primary_color: str    # hex e.g. '#0a1641'
    accent_color: str     # hex e.g. '#0e7490'
    accent_hex_decorative: str  # hex e.g. '#0fbbbb' (may fail AA)
    headline_font: str    # google/bunny font name e.g. 'Montserrat'
    body_font: str        # google/bunny font name e.g. 'Open Sans'
    serif_font: str       # optional editorial serif e.g. 'Fraunces'
    email: str            # contact email
    schema_type: str      # 'Person' | 'Organization' | 'ProfessionalService'
    person_name: str      # for Person/Organization founder context
    extra_pages: list     # list of {slug, label, url} for nav
    sister_sites: list    # list of {url, name, tag}


AI_BOTS = [
    "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User",
    "anthropic-ai", "PerplexityBot", "Perplexity-User", "Google-Extended",
    "Applebot-Extended", "Amazonbot", "Bytespider", "CCBot", "cohere-ai",
    "Diffbot", "FacebookBot", "Meta-ExternalAgent", "Meta-ExternalFetcher",
    "YouBot", "omgili", "ImagesiftBot",
]


def render_robots(spec: Spec) -> str:
    domain = spec["domain"]
    bot_block = "\n".join(f"User-agent: {b}\nAllow: /\n" for b in AI_BOTS)
    return f"""# {domain} — open to all crawlers including LLMs.
# See /llms.txt for an LLM-friendly summary and /llms-full.txt for the full content.

User-agent: *
Allow: /

{bot_block}
Sitemap: https://{domain}/sitemap.xml
"""


def render_sitemap(spec: Spec) -> str:
    domain = spec["domain"]
    today = "2026-05-07"
    urls = [
        ("/", today, "monthly", "1.0"),
        ("/llms.txt", today, "monthly", "0.8"),
        ("/llms-full.txt", today, "monthly", "0.7"),
        ("/index.md", today, "monthly", "0.7"),
    ]
    for p in spec.get("extra_pages") or []:
        urls.append((p["url"], today, "weekly", "0.9"))
    body = "\n".join(
        f"  <url>\n    <loc>https://{domain}{u}</loc>\n    <lastmod>{m}</lastmod>\n    <changefreq>{f}</changefreq>\n    <priority>{p}</priority>\n  </url>"
        for u, m, f, p in urls
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{body}
</urlset>
"""


def render_jsonld(spec: Spec) -> str:
    domain = spec["domain"]
    schema_type = spec.get("schema_type") or "Person"
    name = spec.get("person_name") or spec.get("title", "")

    if schema_type == "Person":
        graph = {
            "@type": "Person",
            "@id": f"https://{domain}/#person",
            "name": name,
            "url": f"https://{domain}",
            "description": spec.get("summary", ""),
            "email": spec.get("email", ""),
        }
    elif schema_type == "Organization":
        graph = {
            "@type": "Organization",
            "@id": f"https://{domain}/#org",
            "name": spec.get("title"),
            "url": f"https://{domain}",
            "description": spec.get("summary", ""),
            "email": spec.get("email", ""),
        }
        if name:
            graph["founder"] = {"@type": "Person", "name": name}
    else:  # ProfessionalService and others
        graph = {
            "@type": schema_type,
            "@id": f"https://{domain}/#org",
            "name": spec.get("title"),
            "url": f"https://{domain}",
            "description": spec.get("summary", ""),
            "email": spec.get("email", ""),
        }

    site = {
        "@type": "WebSite",
        "@id": f"https://{domain}/#website",
        "url": f"https://{domain}",
        "name": spec.get("title"),
        "description": spec.get("summary", ""),
        "publisher": {"@id": graph["@id"]},
        "inLanguage": "en",
    }

    out = {"@context": "https://schema.org", "@graph": [graph, site]}
    return json.dumps(out, indent=2)


def render_html(spec: Spec) -> str:
    domain = spec["domain"]
    title = spec.get("title", domain)
    summary = spec.get("summary", "")
    headline = spec.get("headline", title)
    body_paragraphs = spec.get("body_paragraphs") or [summary]
    headline_font = spec.get("headline_font", "Montserrat")
    body_font = spec.get("body_font", "Open Sans")
    serif_font = spec.get("serif_font") or ""
    email = spec.get("email", "")
    extra_pages = spec.get("extra_pages") or []
    sister_sites = spec.get("sister_sites") or []

    # font import
    fonts_param = f"{headline_font.lower().replace(' ', '-')}:400,500,600,700|{body_font.lower().replace(' ', '-')}:400,600"
    if serif_font:
        fonts_param += f"|{serif_font.lower().replace(' ', '-')}:400,500,600,400i,500i"

    nav_links = " · ".join(
        f'<a href="{p["url"]}">{p["label"]}</a>' for p in extra_pages
    )
    if email:
        nav_links += (' · ' if nav_links else '') + f'<a href="mailto:{email}">Email</a>'

    body_html = "\n      ".join(f"<p class=\"prose-large\">{p}</p>" for p in body_paragraphs)

    sister_html = ""
    if sister_sites:
        items = "\n      ".join(
            f'<li><a href="{s["url"]}"><span class="eco-name">{s["name"]}</span><span class="eco-tag">{s.get("tag","")}</span></a></li>'
            for s in sister_sites
        )
        sister_html = f"""
  <section class="ecosystem">
    <p class="ecosystem-rubric">Other places</p>
    <ul class="ecosystem-list">
      {items}
    </ul>
  </section>
"""

    jsonld = render_jsonld(spec)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <meta name="description" content="{summary}" />
  <meta property="og:title" content="{title}" />
  <meta property="og:description" content="{summary}" />
  <meta property="og:type" content="website" />
  <meta property="og:url" content="https://{domain}" />
  <meta name="twitter:card" content="summary_large_image" />
  <link rel="preconnect" href="https://fonts.bunny.net" />
  <link href="https://fonts.bunny.net/css?family={fonts_param}&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="/style.css?v=1" />
  <link rel="alternate" type="text/markdown" href="/index.md" title="Markdown version" />
  <link rel="alternate" type="text/plain" href="/llms.txt" title="LLM-friendly summary" />
  <script type="application/ld+json">
{jsonld}
  </script>
</head>
<body>

  <header class="masthead">
    <a class="wordmark" href="/" aria-label="{title}"><strong>{title}</strong></a>
    <nav class="masthead-nav">{nav_links}</nav>
  </header>

  <main>

    <section class="opening">
      <h1 class="lede">{headline}</h1>
    </section>

    <section class="block">
      {body_html}
    </section>

    <section class="block colophon">
      <p class="rubric">Reach</p>
      <p class="prose-large">
        Email <a href="mailto:{email}">{email}</a>.
      </p>
    </section>

  </main>
{sister_html}
  <footer class="site-foot">
    <p>&copy; <span id="year">2026</span> {title}.</p>
  </footer>

  <script>document.getElementById('year').textContent = new Date().getFullYear();</script>
</body>
</html>
"""


def render_markdown(spec: Spec) -> str:
    title = spec.get("title", spec["domain"])
    summary = spec.get("summary", "")
    body_paragraphs = spec.get("body_paragraphs") or [summary]
    email = spec.get("email", "")

    body = "\n\n".join(body_paragraphs)
    return f"""# {title}

{summary}

{body}

## Reach

Email: {email}
"""


def render_llms_txt(spec: Spec) -> str:
    title = spec.get("title", spec["domain"])
    summary = spec.get("summary", "")
    domain = spec["domain"]
    sister_sites = spec.get("sister_sites") or []
    sister_lines = "\n".join(f"- [{s['name']}]({s['url']}): {s.get('tag','')}" for s in sister_sites)
    extra_pages = spec.get("extra_pages") or []
    page_lines = "\n".join(f"- [{p['label']}](https://{domain}{p['url']})" for p in extra_pages)
    sister_block = ("\n\n## Sister properties\n\n" + sister_lines) if sister_lines else ""

    return f"""# {title}

> {summary}

## Source URLs

- [Home](https://{domain}/) — main page
{page_lines}
- [llms-full.txt](https://{domain}/llms-full.txt) — full content as markdown
- [index.md](https://{domain}/index.md) — markdown shadow of the homepage
{sister_block}

## Contact

- Email: {spec.get('email', '')}
"""


def render_css(spec: Spec) -> str:
    primary = spec.get("primary_color", "#0a1641")
    accent = spec.get("accent_color", "#0e7490")
    accent_dec = spec.get("accent_hex_decorative", "#0fbbbb")
    headline = spec.get("headline_font", "Montserrat")
    body = spec.get("body_font", "Open Sans")
    serif = spec.get("serif_font") or ""

    serif_var = f'"{serif}"' if serif else f'"{body}"'
    return f"""/* Bootstrap-generated stylesheet — single-font system, AA-compliant accent.
   Replace tokens to taste; the structure is sound for AI-friendly + accessible. */

:root {{
  --primary: {primary};
  --accent: {accent};               /* WCAG-AA-compliant text/link variant */
  --accent-decorative: {accent_dec}; /* gradients, borders, larger type */
  --rule: #d8dde8;
  --paper: #ffffff;
  --section-bg: #f4f6fb;
  --headline: "{headline}", -apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif;
  --body: "{body}", -apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif;
  --serif: {serif_var}, Georgia, "Times New Roman", serif;
  --gutter: clamp(1.25rem, 4vw, 3rem);
  --measure: 38rem;
}}

* {{ box-sizing: border-box; }}
* {{ overflow-wrap: break-word; }}

html, body {{
  margin: 0;
  padding: 0;
  background: var(--paper);
  color: var(--primary);
  font-family: var(--body);
  font-size: 17px;
  line-height: 1.6;
  overflow-x: hidden;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}}

a {{
  color: var(--primary);
  text-decoration: underline;
  text-decoration-color: var(--accent);
  text-decoration-thickness: 1.5px;
  text-underline-offset: 3px;
  transition: color 0.15s, text-decoration-thickness 0.15s;
}}
a:hover {{ color: var(--accent); text-decoration-thickness: 2.5px; }}

main {{
  max-width: 56rem;
  margin: 0 auto;
  padding: 0 var(--gutter);
}}

.masthead {{
  max-width: 56rem;
  margin: 0 auto;
  padding: 1.5rem var(--gutter) 1.25rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--rule);
}}
.wordmark {{
  text-decoration: none;
  font-family: var(--headline);
  font-size: 1.05rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: var(--primary);
}}
.masthead-nav a {{
  font-family: var(--headline);
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--primary);
  text-decoration: none;
  margin-left: 1.5rem;
}}
.masthead-nav a:hover {{ color: var(--accent); }}

.opening {{ margin: 4rem 0 3rem; }}
.lede {{
  font-family: var(--serif);
  font-weight: 500;
  font-style: italic;
  font-size: clamp(1.8rem, 4vw, 2.8rem);
  line-height: 1.18;
  letter-spacing: -0.02em;
  margin: 0;
  max-width: 22ch;
  color: var(--primary);
}}

.block {{
  margin: 0 0 4rem;
  padding-top: 2.5rem;
  border-top: 1px solid var(--rule);
}}

.rubric {{
  font-family: var(--headline);
  font-size: 0.85rem;
  font-weight: 600;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--accent);
  margin: 0 0 1.5rem;
}}

.prose-large {{
  font-family: var(--body);
  font-size: 1.1rem;
  line-height: 1.65;
  max-width: 38rem;
  margin: 0 0 1.25rem;
}}

.colophon {{ text-align: left; }}

.ecosystem {{
  max-width: 56rem;
  margin: 5rem auto 0;
  padding: 2rem var(--gutter) 0;
  border-top: 1px solid var(--rule);
}}
.ecosystem-rubric {{
  font-family: var(--headline);
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--accent);
  margin: 0 0 1.25rem;
}}
.ecosystem-list {{
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
}}
.ecosystem-list a {{
  display: block;
  padding: 1rem 1.1rem;
  text-decoration: none;
  border: 1px solid var(--rule);
  border-radius: 6px;
}}
.ecosystem-list a:hover {{ border-color: var(--accent); }}
.eco-name {{ display: block; font-family: var(--headline); font-weight: 600; color: var(--primary); }}
.eco-tag {{ display: block; font-size: 0.78rem; color: #6a7493; margin-top: 0.15rem; }}

.site-foot {{
  background: var(--primary);
  color: rgba(255,255,255,0.78);
  margin: 5rem 0 0;
  padding: 1.5rem var(--gutter);
  font-family: var(--body);
  font-size: 0.85rem;
}}
.site-foot p {{ max-width: 56rem; margin: 0 auto; }}

@media (max-width: 800px) {{
  .masthead {{ flex-direction: column; align-items: flex-start; gap: 0.75rem; }}
  .masthead-nav a {{ margin-left: 0; margin-right: 1.25rem; }}
  .ecosystem-list {{ grid-template-columns: 1fr; }}
  .lede, .prose-large {{ max-width: 100%; }}
}}
"""
