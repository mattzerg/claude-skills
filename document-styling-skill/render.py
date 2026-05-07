#!/usr/bin/env python3
"""Branded PDF renderer for one-pagers and short docs.

Reads a markdown file with optional frontmatter, wraps it in the 5-zone visual
template (header band → hero → body → optional chip strip → footer band), applies
a theme (zerg-default | zerg-navy | zerg-warm), and renders to PDF via
Chrome headless with web fonts loaded.

Usage:
    python3 ~/.claude/skills/document-styling-skill/render.py <markdown.md> [<more.md>...] [flags]
    python3 ~/.claude/skills/document-styling-skill/render.py list

Flags:
    --theme NAME       zerg-default (default) | zerg-navy | zerg-warm
    --accent HEX       override accent without picking a theme
    --out-dir DIR      output directory (default: next to source)
    --no-open          skip Preview open
    --strict-one-page  fail loud if rendered > 1 page (auto-on for *.one-pager.md)

Frontmatter the renderer reads (all optional):
    title:        H1 if not in body
    tagline:      dek under H1
    brand_line:   top-right of header band (e.g. "Zerg AI")
    contact_line: top-right of header band line 2
    footer_line:  centered footer text
    chip_strip:   YAML list of chip labels
    theme:        zerg-default | zerg-navy | zerg-warm (overrides --theme)
    accent:       hex override
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

import markdown
import yaml

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

SKILL_ROOT = Path.home() / ".claude" / "skills" / "document-styling-skill"
THEMES_DIR = SKILL_ROOT / "themes"
ASSETS_DIR = SKILL_ROOT / "assets"
DEFAULT_LOGO_SVG = ASSETS_DIR / "logo-zerg.svg"
DEFAULT_LOGO_URL = "https://zergai.com"

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    body = text[m.end():]
    return meta, body


def extract_h1_and_dek(body: str) -> tuple[str | None, str | None, str]:
    """Pull the first H1 and first blockquote out of the body. Return (h1, dek, remaining_body)."""
    h1 = None
    dek = None
    lines = body.splitlines()
    out: list[str] = []
    skip_blank_after_h1 = False
    consumed_dek = False
    for line in lines:
        if h1 is None and line.startswith("# "):
            h1 = line[2:].strip()
            skip_blank_after_h1 = True
            continue
        if skip_blank_after_h1 and line.strip() == "":
            skip_blank_after_h1 = False
            continue
        if not consumed_dek and line.startswith("> "):
            dek_line = line[2:].strip()
            dek = (dek + " " + dek_line).strip() if dek else dek_line
            continue
        if dek and line.startswith("> "):
            dek_line = line[2:].strip()
            dek = (dek + " " + dek_line).strip()
            continue
        if dek and not consumed_dek and line.strip() == "":
            consumed_dek = True
            continue
        if dek and not consumed_dek and not line.startswith("> "):
            consumed_dek = True
            out.append(line)
            continue
        out.append(line)
    return h1, dek, "\n".join(out).strip() + "\n"


def clean_body(body: str) -> str:
    body = HTML_COMMENT_RE.sub("", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip() + "\n"


HTML_SHELL = """<!doctype html>
<html><head>
<meta charset="utf-8">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&display=swap">
<style>{theme_css}</style>
{accent_override}
</head>
<body>
<div class="page">
  <header class="header-band">
    <div class="wordmark">{wordmark_html}</div>
    <div class="brand-meta">{brand_meta_html}</div>
  </header>

  <section class="hero">
    {eyebrow_html}
    <h1>{h1}</h1>
    {dek_html}
  </section>

  <section class="body">
{body_html}
  </section>

  {chip_strip_html}

  <footer class="footer-band">
    {footer_html}
  </footer>
</div>
</body></html>
"""


def build_chip_strip(chips: list[str] | None) -> str:
    if not chips:
        return ""
    chip_html = "".join(f'<span class="chip">{c}</span>' for c in chips)
    return f'<section class="chip-strip">{chip_html}</section>'


def build_brand_meta(meta: dict) -> str:
    brand_line = meta.get("brand_line")
    contact_line = meta.get("contact_line")
    if not brand_line and not contact_line:
        return ""
    parts = []
    if brand_line:
        parts.append(brand_line)
    if contact_line:
        # auto-wrap email + url in anchors when present
        c = contact_line
        c = re.sub(r"([\w.+-]+@[\w-]+\.[\w.-]+)", r'<a href="mailto:\1">\1</a>', c)
        c = re.sub(r"\b(zergai\.com[\w/.-]*)", r'<a href="https://\1">\1</a>', c)
        parts.append(c)
    return '<div>' + '</div><div>'.join(parts) + '</div>'


def build_wordmark(meta: dict, h1: str | None) -> str:
    """Render the Zerg logo SVG (inline) wrapped in an anchor.

    Frontmatter:
        wordmark_url: link target (default https://zergai.com)
        wordmark_logo: path to alternate logo SVG (default assets/logo-zerg.svg)
        product_tag: optional small text after the logo (e.g. "Solutions" or "Stack")
                     when the doc is a sub-brand and the logo alone is ambiguous
    """
    url = meta.get("wordmark_url") or DEFAULT_LOGO_URL
    logo_path = Path(meta.get("wordmark_logo") or DEFAULT_LOGO_SVG)
    if not logo_path.is_absolute():
        logo_path = ASSETS_DIR / logo_path.name
    if logo_path.exists():
        svg_inline = logo_path.read_text()
    else:
        # Fallback to text wordmark if logo missing
        wm = meta.get("wordmark") or meta.get("title") or h1 or ""
        return f'<a href="{url}">{wm}</a>'

    product_tag = meta.get("product_tag")
    tag_html = f'<span class="product-tag">{product_tag}</span>' if product_tag else ""
    return f'<a href="{url}">{svg_inline}{tag_html}</a>'


def build_footer(meta: dict) -> str:
    line = meta.get("footer_line")
    if not line:
        return ""
    # Replace bullet/middot conventions with styled separators
    parts = re.split(r"\s*[·•|]\s*", line.strip())
    return '<span class="sep">·</span>'.join(f"<span>{p}</span>" for p in parts)


def render_one(md_path: Path, theme: str, accent_override: str | None, strict_one_page: bool) -> Path:
    raw = md_path.read_text()
    meta, body = parse_frontmatter(raw)

    # Frontmatter beats CLI for theme + accent
    theme = meta.get("theme") or theme
    accent_override = meta.get("accent") or accent_override

    theme_path = THEMES_DIR / f"{theme}.css"
    if not theme_path.exists():
        print(f"ERROR: theme '{theme}' not found at {theme_path}", file=sys.stderr)
        sys.exit(2)
    # Resolve @import in theme CSS by inlining (Chrome headless from data/file URLs is finicky w/ relative imports)
    theme_css = inline_imports(theme_path)

    h1, dek, body = extract_h1_and_dek(body)
    if "title" in meta and not h1:
        h1 = meta["title"]
    if "tagline" in meta and not dek:
        dek = meta["tagline"]
    if not h1:
        h1 = md_path.stem

    body = clean_body(body)
    body_html = markdown.markdown(body, extensions=["tables", "fenced_code"])

    eyebrow = meta.get("eyebrow")
    eyebrow_html = f'<div class="eyebrow">{eyebrow}</div>' if eyebrow else ""

    accent_override_css = ""
    if accent_override:
        accent_override_css = f"<style>:root {{ --accent: {accent_override}; --accent-soft: {accent_override}1a; }}</style>"

    html = HTML_SHELL.format(
        title=h1,
        theme_css=theme_css,
        accent_override=accent_override_css,
        wordmark_html=build_wordmark(meta, h1),
        brand_meta_html=build_brand_meta(meta),
        eyebrow_html=eyebrow_html,
        h1=h1,
        dek_html=f'<p class="dek">{dek}</p>' if dek else "",
        body_html=body_html,
        chip_strip_html=build_chip_strip(meta.get("chip_strip")),
        footer_html=build_footer(meta),
    )

    out_dir = md_path.parent
    base = md_path.stem
    if base.endswith(".one-pager"):
        base = base[:-len(".one-pager")]
        suffix = ".one-pager"
    else:
        suffix = ""
    html_path = out_dir / f"{base}{suffix}.branded.html"
    pdf_path = out_dir / f"{base}{suffix}.branded.pdf"

    html_path.write_text(html)

    file_url = "file://" + urllib.parse.quote(str(html_path.resolve()))
    subprocess.run(
        [
            CHROME,
            "--headless",
            "--disable-gpu",
            "--no-margins",
            "--no-pdf-header-footer",
            "--virtual-time-budget=2500",
            f"--print-to-pdf={pdf_path}",
            file_url,
        ],
        check=True,
        stderr=subprocess.DEVNULL,
    )

    trim_blank_trailing_pages(pdf_path)

    if strict_one_page and md_path.name.endswith(".one-pager.md"):
        pages = page_count(pdf_path)
        if pages and pages > 1:
            print(
                f"WARNING: {pdf_path.name} rendered {pages} pages after blank-trim. Tighten content or theme spacing.",
                file=sys.stderr,
            )

    print(str(pdf_path))
    return pdf_path


def trim_blank_trailing_pages(pdf_path: Path) -> None:
    """Strip trailing pages that have no extractable text or visible content.

    Matt's rule: never ship a PDF with a blank trailing page. Uses pypdf if
    available; falls back silently if not installed.
    """
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        return
    try:
        reader = PdfReader(str(pdf_path))
        if len(reader.pages) <= 1:
            return
        # Walk backwards: find last page with non-trivial text content.
        last_real = len(reader.pages) - 1
        while last_real > 0:
            try:
                text = (reader.pages[last_real].extract_text() or "").strip()
            except Exception:
                text = ""
            if len(text) >= 8:  # eight chars = "real" content; trims footer-only or empty pages
                break
            last_real -= 1
        if last_real == len(reader.pages) - 1:
            return  # nothing to trim
        writer = PdfWriter()
        for i in range(last_real + 1):
            writer.add_page(reader.pages[i])
        with open(pdf_path, "wb") as f:
            writer.write(f)
    except Exception as e:
        print(f"trim-blank-pages: skipped ({e})", file=sys.stderr)


def inline_imports(theme_path: Path) -> str:
    """Inline @import url(\"foo.css\") chains so Chrome headless reliably picks up styles."""
    seen: set[Path] = set()
    def _resolve(p: Path) -> str:
        if p in seen:
            return ""
        seen.add(p)
        text = p.read_text()
        def _replace(m):
            target = m.group(1)
            target_path = (p.parent / target).resolve()
            if target_path.exists():
                return _resolve(target_path)
            return m.group(0)
        return re.sub(r'@import\s+url\("([^"]+)"\)\s*;?', _replace, text)
    return _resolve(theme_path)


def page_count(pdf_path: Path) -> int | None:
    try:
        result = subprocess.run(
            ["mdls", "-raw", "-name", "kMDItemNumberOfPages", str(pdf_path)],
            capture_output=True, text=True,
        )
        s = result.stdout.strip()
        if s and s != "(null)":
            return int(s)
    except Exception:
        return None
    return None


def cmd_list() -> int:
    print("Available themes:\n")
    for theme_file in sorted(THEMES_DIR.glob("*.css")):
        name = theme_file.stem
        text = theme_file.read_text()
        accent_match = re.search(r"--accent:\s*(#[0-9a-fA-F]+)", text)
        accent = accent_match.group(1) if accent_match else "(inherited)"
        print(f"  {name:<18} accent: {accent}")
    print("\nFrontmatter the renderer reads (all optional):")
    print("  title, tagline, brand_line, contact_line, footer_line, chip_strip, eyebrow, theme, accent")
    return 0


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "list":
        return cmd_list()

    p = argparse.ArgumentParser(description="Render branded PDFs from markdown.")
    p.add_argument("paths", nargs="+", help="markdown files to render")
    p.add_argument("--theme", default="zerg-default")
    p.add_argument("--accent", default=None)
    p.add_argument("--out-dir", default=None)
    p.add_argument("--no-open", action="store_true")
    p.add_argument("--strict-one-page", action="store_true", default=True)

    args = p.parse_args()

    pdfs: list[Path] = []
    for raw in args.paths:
        path = Path(raw)
        if not path.exists():
            print(f"MISSING: {path}", file=sys.stderr)
            continue
        pdf = render_one(path, args.theme, args.accent, args.strict_one_page)
        pdfs.append(pdf)

    if pdfs and not args.no_open:
        subprocess.run(["open", "-a", "Preview"] + [str(p) for p in pdfs])
    return 0 if pdfs else 1


if __name__ == "__main__":
    raise SystemExit(main())
