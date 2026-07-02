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


# Markdown extensions: `attr_list` lets headings carry stable explicit anchors
# (`## Contact Sheet {#contacts}`); `toc` honors those ids, auto-generates the
# rest, and replaces a literal `[TOC]` line with a linked Contents tree —
# Chrome preserves the internal anchors as clickable links in the PDF.
MD_EXTENSIONS = ["tables", "fenced_code", "attr_list", "toc"]
MD_EXTENSION_CONFIGS = {"toc": {"title": "Contents", "toc_depth": "2-3"}}

# `> [!warning] text` / `[!note]` / `[!info]` blockquotes become classed
# callout boxes (themes style .callout-warning etc. with a ::before label).
CALLOUT_RE = re.compile(r"<blockquote>\s*<p>\[!(\w+)\]\s*(?:<br\s*/?>\s*)?", re.IGNORECASE)


def apply_callouts(body_html: str) -> str:
    # python-markdown coalesces adjacent callout blockquotes (one blank line
    # between them) into a single <blockquote> with multiple <p>. Split each
    # blockquote into one classed callout box per `[!type]` marker so adjacent
    # callouts render as distinct boxes (and lists inside a callout survive).
    def _split(m):
        inner = m.group(1)
        chunks = re.split(r"(<p>\s*\[!\w+\]\s*(?:<br\s*/?>)?\s*)", inner)
        if len(chunks) <= 1:
            return m.group(0)  # plain blockquote, no callout marker
        out = []
        lead = chunks[0].strip()
        if lead:
            out.append(f"<blockquote>\n{lead}\n</blockquote>")
        i = 1
        while i < len(chunks):
            ctype = re.search(r"\[!(\w+)\]", chunks[i]).group(1).lower()
            content = chunks[i + 1] if i + 1 < len(chunks) else ""
            out.append(f'<blockquote class="callout callout-{ctype}">\n<p>{content.lstrip()}</blockquote>')
            i += 2
        return "\n".join(out)

    body_html = re.sub(r"<blockquote>(.*?)</blockquote>", _split, body_html, flags=re.DOTALL)
    return re.sub(r"<p>\s*</p>", "", body_html)


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

# Multi-page shell for review packs / launch packs / any multi-page doc.
# No .page container (it clips overflow + forces one-page sizing). No
# header-band / hero / footer-band / chip-strip — those are one-pager furniture.
# The theme owns all styling. Source markdown can include inline
# <section class="cover">, <section class="tldr">, and `\newpage` markers
# (converted to <div class="page-break"></div>).
MULTIPAGE_HTML_SHELL = """<!doctype html>
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
<main>
{header_html}{body_html}
</main>
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


def build_multipage_header(meta: dict) -> str:
    """Branded header band for multi-page docs (renders on page 1).

    Chrome's CLI print path can't render a running CSS header, so the brand
    band lives at the top of the flowing content; the running footer (brand +
    page number) is stamped on every page post-render (stamp_page_numbers).
    Gated on brand_line/tagline so generic multi-page packs that don't set
    those stay exactly as they were.
    """
    brand_line = (meta.get("brand_line") or "").strip()
    tagline = (meta.get("tagline") or "").strip()
    if not brand_line and not tagline:
        return ""
    left = (
        f'<span style="font-weight:700;font-size:11.5px;letter-spacing:.04em;'
        f'text-transform:uppercase;color:var(--accent,#1F3A5F);">{brand_line}</span>'
        if brand_line else "<span></span>"
    )
    right = (
        f'<span style="font-size:10.5px;color:var(--mid-gray,#5a6b86);text-align:right;">{tagline}</span>'
        if tagline else ""
    )
    return (
        '<div class="mp-brand-band" style="display:flex;justify-content:space-between;'
        'align-items:baseline;gap:24px;border-bottom:2px solid var(--accent,#1F3A5F);'
        'padding-bottom:7px;margin-bottom:22px;">'
        f'{left}{right}</div>'
    )


def render_one(md_path: Path, theme: str, accent_override: str | None, strict_one_page: bool, layout: str = "single-page", out_dir: Path | None = None) -> Path:
    raw = md_path.read_text()
    meta, body = parse_frontmatter(raw)

    # Frontmatter beats CLI for theme + accent + layout
    theme = meta.get("theme") or theme
    accent_override = meta.get("accent") or accent_override
    layout = meta.get("layout") or layout

    theme_path = THEMES_DIR / f"{theme}.css"
    if not theme_path.exists():
        print(f"ERROR: theme '{theme}' not found at {theme_path}", file=sys.stderr)
        sys.exit(2)
    # Resolve @import in theme CSS by inlining (Chrome headless from data/file URLs is finicky w/ relative imports)
    theme_css = inline_imports(theme_path)

    accent_override_css = ""
    if accent_override:
        accent_override_css = f"<style>:root {{ --accent: {accent_override}; --accent-soft: {accent_override}1a; }}</style>"

    if layout == "multi-page":
        # Multi-page mode: body owns the structure (cover, tldr, parts).
        # Convert `\newpage` markers to page-break divs.
        body = clean_body(body)
        body = body.replace("\\newpage", '<div class="page-break"></div>')
        # md_in_html lets <section markdown="1"> blocks contain markdown
        # (e.g., the cover/tldr sections in a multi-page review pack).
        body_html = markdown.markdown(
            body,
            extensions=MD_EXTENSIONS + ["md_in_html"],
            extension_configs=MD_EXTENSION_CONFIGS,
        )
        body_html = apply_callouts(body_html)
        # Auto-tag `Part N — ...` H1s with class="part" so the theme can border them.
        body_html = re.sub(r'<h1([^>]*)>(Part \d+[^<]*)</h1>', r'<h1\1 class="part">\2</h1>', body_html)
        title = meta.get("title", md_path.stem)
        html = MULTIPAGE_HTML_SHELL.format(
            title=title,
            theme_css=theme_css,
            accent_override=accent_override_css,
            header_html=build_multipage_header(meta),
            body_html=body_html,
        )
    else:
        # Single-page mode: original one-pager shell with header-band + hero + footer.
        h1, dek, body = extract_h1_and_dek(body)
        if "title" in meta and not h1:
            h1 = meta["title"]
        if "tagline" in meta and not dek:
            dek = meta["tagline"]
        if not h1:
            h1 = md_path.stem

        body = clean_body(body)
        body_html = markdown.markdown(body, extensions=MD_EXTENSIONS, extension_configs=MD_EXTENSION_CONFIGS)
        body_html = apply_callouts(body_html)

        eyebrow = meta.get("eyebrow")
        eyebrow_html = f'<div class="eyebrow">{eyebrow}</div>' if eyebrow else ""

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

    out_dir = out_dir or md_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
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
    if layout == "multi-page":
        stamp_page_numbers(pdf_path, footer_text=(meta.get("footer_line") or "").strip() or None)
        wire_internal_links(pdf_path, html)

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


def stamp_page_numbers(pdf_path: Path, footer_text: str | None = None) -> None:
    """Stamp a running footer + 'Page N of M' bottom-center on multi-page PDFs.

    Chrome's CLI print path ignores CSS @page margin-boxes, so counters (and
    any running brand/confidential footer) can't live in CSS. When footer_text
    is given it is drawn on every page above the page number — this is how a
    branded multi-page doc gets its running 'Confidential — Prepared for …'
    line. Needs pypdf + reportlab; silently skips when either is absent.
    Runs AFTER trim_blank_trailing_pages so the total is the shipped count.
    """
    try:
        import io
        from pypdf import PdfReader, PdfWriter
        from reportlab.pdfgen import canvas
    except ImportError:
        return
    try:
        reader = PdfReader(str(pdf_path))
        total = len(reader.pages)
        if total < 2:
            return
        # Sanitize to WinAnsi-safe punctuation so the standard Helvetica stamp
        # never fails (which would drop the page numbers too).
        safe_footer = None
        if footer_text:
            safe_footer = (footer_text.replace("—", "—").replace("–", "–")
                           .replace("’", "'").replace("‘", "'"))
        writer = PdfWriter()
        for i, page in enumerate(reader.pages):
            w = float(page.mediabox.width)
            h = float(page.mediabox.height)
            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=(w, h))
            c.setFont("Helvetica", 7)
            c.setFillColorRGB(0.45, 0.47, 0.46)
            if safe_footer:
                c.drawCentredString(w / 2, 30, safe_footer)
                c.drawCentredString(w / 2, 18, f"Page {i + 1} of {total}")
            else:
                c.drawCentredString(w / 2, 24, f"Page {i + 1} of {total}")
            c.save()
            buf.seek(0)
            page.merge_page(PdfReader(buf).pages[0])
            writer.add_page(page)
        with open(pdf_path, "wb") as f:
            writer.write(f)
    except Exception as e:
        print(f"page-numbers: skipped ({e})", file=sys.stderr)


def wire_internal_links(pdf_path: Path, full_html: str) -> None:
    """Make Chrome's internal `#anchor` links actually clickable.

    Chrome's `--print-to-pdf` emits internal links as named-destination
    references (`/Dest /anchor-id`) but never writes the `/Names → /Dests`
    table, so the links resolve to nothing — TOC and cross-references look
    like dead text. Rebuild that table: map each anchor id to the page its
    heading text lands on (by matching the clean text right after the id's
    tag against extracted page text) and register a named destination so the
    link jumps to the right page. Needs pypdf; silently no-ops if absent or
    on any failure (never breaks a render).
    """
    try:
        import html as _html
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        return
    try:
        def _strip(s: str) -> str:
            return re.sub(r"<[^>]+>", " ", s)

        def _norm(s: str) -> str:
            return re.sub(r"\s+", " ", _html.unescape(s)).strip()

        def _despace(s: str) -> str:
            # Drop ordered-list / section ordinal markers ("4. ", "1. ") so a
            # heading like "4. FAQ" followed by an <ol> still matches the page
            # text (Chrome renders the list markers; the HTML source does not).
            return re.sub(r"\b\d+\.\s+", "", s)

        # anchor id -> signature: the clean text right after the id's tag close
        sigs: dict[str, str] = {}
        for m in re.finditer(r'id="([^"]+)"', full_html):
            aid = m.group(1)
            gt = full_html.find(">", m.end())
            if gt < 0:
                continue
            txt = _despace(_norm(_strip(full_html[gt + 1: gt + 1 + 300])))
            if len(txt) >= 4:
                sigs[aid] = txt[:30].lower()
        if not sigs:
            return

        reader = PdfReader(str(pdf_path))
        pages = [_despace(_norm(_strip(p.extract_text() or ""))).lower() for p in reader.pages]

        def _find(sig: str):
            for probe in (sig[:22], sig[:14]):
                if not probe:
                    continue
                for pi, pt in enumerate(pages):
                    if probe in pt:
                        return pi
            return None

        mapped = {a: _find(s) for a, s in sigs.items()}
        mapped = {a: pi for a, pi in mapped.items() if pi is not None}
        if not mapped:
            return

        writer = PdfWriter()
        for p in reader.pages:
            writer.add_page(p)
        for aid, pi in mapped.items():
            try:
                writer.add_named_destination(aid, pi)
            except Exception:
                pass
        with open(pdf_path, "wb") as f:
            writer.write(f)
    except Exception as e:
        print(f"wire-internal-links: skipped ({e})", file=sys.stderr)


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
    p.add_argument("--layout", choices=("single-page", "multi-page"), default="single-page",
                   help="single-page (default; uses one-pager shell) | multi-page (for review packs, launch packs)")
    p.add_argument("--audit", choices=("auto", "on", "off"), default="auto",
                   help="auto (default; ON for multi-page) | on (force) | off (skip). Pre-render: crop light edge strips from inline PNGs. Post-render: run audit_pack.py and fail on HIGH findings.")

    args = p.parse_args()

    # auto-audit policy: multi-page → on, single-page → off (one-pagers have separate strict-one-page gate)
    audit_on = args.audit == "on" or (args.audit == "auto" and args.layout == "multi-page")

    # PRE-RENDER: crop light edge strips from any inline PNGs referenced in the markdown.
    # Live-site SVG-to-PNG conversions often ship with whitespace baked into the bottom edge
    # (invisible on the live dark page background; visible as a white bar in a multipage PDF).
    if audit_on:
        crop_script = Path.home() / ".config" / "zerg" / "crop_image_padding.py"
        if crop_script.exists():
            for raw in args.paths:
                src = Path(raw)
                if not src.exists():
                    continue
                body = src.read_text()
                # extract markdown image paths and HTML <img src> paths
                import re as _re
                md_paths = _re.findall(r"!\[[^\]]*\]\(([^)]+)\)", body)
                html_paths = _re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', body)
                for ref in set(md_paths + html_paths):
                    # skip URLs (only crop local paths)
                    if ref.startswith(("http:", "https:", "data:")):
                        continue
                    img_path = (src.parent / ref).resolve() if not ref.startswith("/") else Path(ref)
                    if img_path.is_file() and img_path.suffix.lower() in (".png", ".jpg", ".jpeg"):
                        subprocess.run(["python3", str(crop_script), str(img_path), "--only-light", "--tolerance", "6"],
                                       capture_output=True)
        else:
            print("WARN: ~/.config/zerg/crop_image_padding.py not found — skipping pre-render image crop", file=sys.stderr)

    pdfs: list[Path] = []
    for raw in args.paths:
        path = Path(raw)
        if not path.exists():
            print(f"MISSING: {path}", file=sys.stderr)
            continue
        pdf = render_one(path, args.theme, args.accent, args.strict_one_page, args.layout,
                         out_dir=Path(args.out_dir).expanduser() if args.out_dir else None)
        pdfs.append(pdf)

    # POST-RENDER: hard audit for multi-page packs.
    if audit_on and pdfs:
        audit_script = Path.home() / ".config" / "zerg" / "audit_pack.py"
        if audit_script.exists():
            any_fail = False
            for pdf in pdfs:
                print(f"\n=== audit_pack.py {pdf.name} ===", file=sys.stderr)
                rc = subprocess.run(["python3", str(audit_script), str(pdf)]).returncode
                if rc != 0:
                    any_fail = True
            if any_fail:
                print("\n✗ audit failed — NOT opening Preview. Fix findings and re-render.\n"
                      "   Override (rare): pass --audit off.", file=sys.stderr)
                return 1
        else:
            print("WARN: ~/.config/zerg/audit_pack.py not found — skipping post-render audit", file=sys.stderr)

    if pdfs and not args.no_open:
        subprocess.run(["open", "-a", "Preview"] + [str(p) for p in pdfs])
    return 0 if pdfs else 1


if __name__ == "__main__":
    raise SystemExit(main())
