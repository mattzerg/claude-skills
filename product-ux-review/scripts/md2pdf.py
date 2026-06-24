#!/usr/bin/env python3
import sys, re, html, subprocess, os

src, out_pdf = sys.argv[1], sys.argv[2]
text = open(src, encoding="utf-8").read()

# strip YAML frontmatter
fm = {}
if text.startswith("---"):
    end = text.find("\n---", 3)
    if end != -1:
        block = text[3:end]
        text = text[end+4:]
        for line in block.splitlines():
            m = re.match(r"^(\w[\w_]*):\s*(.*)$", line)
            if m: fm[m.group(1)] = m.group(2).strip()

def inline(s):
    s = html.escape(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\*\w])\*([^*]+)\*(?![\*\w])", r"<em>\1</em>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    return s

lines = text.split("\n")
out = []
i = 0
in_list = False

def close_list():
    global in_list
    if in_list:
        out.append("</ul>"); in_list = False

while i < len(lines):
    ln = lines[i]
    # fenced code block (``` ... ```) — preserve whitespace (ASCII mocks, code)
    if re.match(r"^\s*```", ln):
        close_list()
        i += 1
        buf = []
        while i < len(lines) and not re.match(r"^\s*```", lines[i]):
            buf.append(html.escape(lines[i])); i += 1
        i += 1  # skip closing fence
        out.append("<pre><code>" + "\n".join(buf) + "</code></pre>")
        continue
    # table block
    if "|" in ln and i+1 < len(lines) and re.match(r"^\s*\|?[\s:|-]+\|?\s*$", lines[i+1]) and "-" in lines[i+1]:
        close_list()
        header = [c.strip() for c in ln.strip().strip("|").split("|")]
        out.append('<table><thead><tr>' + "".join(f"<th>{inline(c)}</th>" for c in header) + "</tr></thead><tbody>")
        i += 2
        while i < len(lines) and "|" in lines[i] and lines[i].strip():
            cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in cells) + "</tr>")
            i += 1
        out.append("</tbody></table>")
        continue
    # headings
    m = re.match(r"^(#{1,6})\s+(.*)$", ln)
    if m:
        close_list()
        lvl = len(m.group(1)); out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>"); i += 1; continue
    # hr
    if re.match(r"^---+\s*$", ln):
        close_list(); out.append("<hr>"); i += 1; continue
    # blockquote
    if ln.startswith(">"):
        close_list()
        buf = []
        while i < len(lines) and lines[i].startswith(">"):
            buf.append(lines[i].lstrip(">").strip()); i += 1
        out.append("<blockquote>" + inline(" ".join(buf)) + "</blockquote>"); continue
    # list item
    m = re.match(r"^\s*[-*]\s+(.*)$", ln)
    if m:
        if not in_list: out.append("<ul>"); in_list = True
        out.append(f"<li>{inline(m.group(1))}</li>"); i += 1; continue
    # numbered list -> treat as ordered
    m = re.match(r"^\s*\d+\.\s+(.*)$", ln)
    if m:
        if not in_list: out.append("<ul class='ol'>"); in_list = True
        out.append(f"<li>{inline(m.group(1))}</li>"); i += 1; continue
    # blank
    if not ln.strip():
        close_list(); i += 1; continue
    # paragraph — gather consecutive plain lines so inline spans (bold/code) can wrap across newlines
    close_list()
    buf = [ln]; i += 1
    def is_special(s):
        return (not s.strip()) or s.startswith((">", "#")) or re.match(r"^\s*[-*]\s+", s) or \
               re.match(r"^\s*\d+\.\s+", s) or re.match(r"^---+\s*$", s) or \
               ("|" in s and (i+1 <= len(lines)))
    while i < len(lines) and lines[i].strip() and not (
        lines[i].startswith((">", "#")) or re.match(r"^\s*[-*]\s+", lines[i]) or
        re.match(r"^\s*\d+\.\s+", lines[i]) or re.match(r"^---+\s*$", lines[i]) or
        ("|" in lines[i])):
        buf.append(lines[i]); i += 1
    out.append(f"<p>{inline(' '.join(b.strip() for b in buf))}</p>")

close_list()
body = "\n".join(out)
title = fm.get("product","ZergChat") + " — UX FINDINGS"

doc = f"""<!doctype html><html><head><meta charset="utf-8"><title>{title}</title>
<style>
@page {{ size: A4; margin: 16mm 14mm; }}
* {{ box-sizing: border-box; }}
body {{ font-family: -apple-system, "Inter", "Segoe UI", Helvetica, Arial, sans-serif; color:#1a1a1a; font-size:10.5px; line-height:1.5; }}
h1 {{ font-size:20px; color:#C0392B; border-bottom:3px solid #C0392B; padding-bottom:6px; margin:18px 0 10px; page-break-before: always; }}
h1:first-of-type {{ page-break-before: avoid; }}
h2 {{ font-size:14px; color:#922b21; margin:18px 0 6px; border-bottom:1px solid #e3c4bf; padding-bottom:3px; }}
h3 {{ font-size:11.5px; color:#7a2018; margin:12px 0 4px; }}
p {{ margin:5px 0; }}
ul {{ margin:5px 0 5px 16px; padding:0; }}
li {{ margin:2px 0; }}
code {{ font-family:"SFMono-Regular", Menlo, Consolas, monospace; background:#f4eceb; color:#922b21; padding:1px 4px; border-radius:3px; font-size:9.5px; }}
pre {{ background:#f7f4f3; border:1px solid #e2d8d6; border-radius:5px; padding:9px 11px; overflow-x:auto; margin:8px 0; page-break-inside:avoid; }}
pre code {{ background:none; color:#1a1a1a; padding:0; font-size:8.2px; line-height:1.35; white-space:pre; }}
strong {{ color:#111; }}
blockquote {{ margin:8px 0; padding:7px 12px; background:#fbf3f2; border-left:3px solid #C0392B; color:#444; font-size:10px; }}
hr {{ border:none; border-top:1px solid #ddd; margin:14px 0; }}
table {{ border-collapse:collapse; width:100%; margin:8px 0; font-size:9px; }}
th {{ background:#C0392B; color:#fff; text-align:left; padding:5px 7px; font-weight:600; }}
td {{ border:1px solid #e2e2e2; padding:4px 7px; vertical-align:top; }}
tr:nth-child(even) td {{ background:#faf6f5; }}
a {{ color:#922b21; }}
.meta {{ color:#888; font-size:9px; margin-bottom:10px; }}
h2, h3, table {{ page-break-inside: avoid; }}
</style></head><body>
<div class="meta">From {fm.get('from','Matt Eisner')} → {fm.get('to','Michael Chen')} · build: {fm.get('build','pr-433')} · {fm.get('created','')}</div>
{body}
</body></html>"""

html_path = "/tmp/zergchat-findings.html"
open(html_path, "w", encoding="utf-8").write(doc)

chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
subprocess.run([chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                f"--print-to-pdf={out_pdf}", "file://"+html_path], check=True,
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print("PDF:", out_pdf, "exists:", os.path.exists(out_pdf), "bytes:", os.path.getsize(out_pdf) if os.path.exists(out_pdf) else 0)
