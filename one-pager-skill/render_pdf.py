#!/usr/bin/env python3
"""One-pager PDF renderer — tighter CSS than the shared blog renderer.

Usage:
    python3 ~/.claude/skills/one-pager-skill/render_pdf.py <markdown.md> [<more.md>...]

Writes <input>.pdf next to each source file (vault-side render, not /tmp).
Strips frontmatter and HTML comments before rendering — those are author/scaffolder
notes that should not appear in the printed leave-behind.
"""
from __future__ import annotations

import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

import markdown

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

CSS = """
<style>
  @page { size: Letter; margin: 0.4in 0.45in; }
  html, body { margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    font-size: 9.5pt;
    line-height: 1.3;
    color: #1a1a1a;
  }
  h1 {
    font-size: 18pt;
    margin: 0 0 3pt 0;
    padding-bottom: 3pt;
    border-bottom: 2px solid #1a1a1a;
    letter-spacing: -0.01em;
  }
  h2 {
    font-size: 10pt;
    margin: 7pt 0 3pt 0;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #333;
    border-bottom: 1px solid #d0d0d0;
    padding-bottom: 1pt;
  }
  h3 { font-size: 10pt; margin: 6pt 0 2pt 0; }
  p { margin: 0 0 4pt 0; }
  blockquote {
    margin: 3pt 0 6pt 0;
    padding: 3pt 8pt;
    border-left: 3px solid #555;
    color: #333;
    font-size: 10pt;
    background: #fafafa;
  }
  blockquote p { margin: 0; }
  ul, ol { margin: 1pt 0 4pt 0; padding-left: 16pt; }
  li { margin: 1pt 0; }
  table { border-collapse: collapse; margin: 3pt 0 6pt 0; font-size: 9pt; width: 100%; }
  th, td { border: 1px solid #d0d0d0; padding: 2pt 5pt; text-align: left; vertical-align: top; }
  th { background: #f4f4f4; font-weight: 600; }
  hr { border: none; border-top: 1px solid #ddd; margin: 6pt 0; }
  strong { color: #000; }
  em { color: #444; }
  code { font-family: 'SF Mono', Menlo, Consolas, monospace; font-size: 9pt; background: #f4f4f4; padding: 0 3pt; border-radius: 2pt; }
  a { color: #0366d6; text-decoration: none; }
  h2 + p:last-of-type { margin-bottom: 0; }
</style>
"""


FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n", re.DOTALL)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def clean_markdown(text: str) -> str:
    text = FRONTMATTER_RE.sub("", text, count=1)
    text = HTML_COMMENT_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
    return text


def render_one(md_path: Path) -> Path:
    raw = md_path.read_text()
    cleaned = clean_markdown(raw)
    html_body = markdown.markdown(cleaned, extensions=["tables", "fenced_code"])
    html = f"""<!doctype html>
<html><head><meta charset='utf-8'><title>{md_path.stem}</title>{CSS}</head>
<body>
{html_body}
</body></html>"""

    html_path = md_path.with_suffix(".one-pager.html") if md_path.suffix == ".md" else md_path.with_suffix(".html")
    # Avoid the .one-pager.one-pager.html collision when input is already <slug>.one-pager.md
    if md_path.name.endswith(".one-pager.md"):
        html_path = md_path.with_name(md_path.name.replace(".one-pager.md", ".one-pager.html"))
    html_path.write_text(html)

    # Versioned filename per feedback_label_iteration_versions.md so Matt
    # can distinguish iterations in Finder.
    out_dir = html_path.parent
    stem = html_path.stem
    pdf_path = html_path.with_suffix(".pdf")
    try:
        sys_path_zerg = "/Users/mattheweisner/.config/zerg"
        if sys_path_zerg not in sys.path:
            sys.path.insert(0, sys_path_zerg)
        from version_path import next_version_path
        pdf_path = next_version_path(out_dir, stem, "pdf")
    except Exception:
        pass
    file_url = "file://" + urllib.parse.quote(str(html_path.resolve()))
    subprocess.run(
        [
            CHROME,
            "--headless",
            "--disable-gpu",
            "--no-margins",
            "--no-pdf-header-footer",
            f"--print-to-pdf={pdf_path}",
            file_url,
        ],
        check=True,
        stderr=subprocess.DEVNULL,
    )
    # Post-render: strip blank pages per feedback_review_pack_one_file.md
    try:
        from strip_blank_pages import strip_blank_pages
        n = strip_blank_pages(pdf_path)
        if n:
            print(f"  stripped {n} blank page(s)")
    except Exception as e:
        print(f"  (blank-page strip skipped: {e})")
    print(str(pdf_path))
    return pdf_path


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: render_pdf.py <markdown.md> [<more.md>...]", file=sys.stderr)
        return 2
    paths = [Path(p) for p in sys.argv[1:]]
    pdfs = []
    for p in paths:
        if not p.exists():
            print(f"MISSING: {p}", file=sys.stderr)
            continue
        pdfs.append(render_one(p))
    if pdfs:
        subprocess.run(["open", "-a", "Preview"] + [str(p) for p in pdfs])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
