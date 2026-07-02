#!/usr/bin/env python3
"""Deep-ingest Instagram reels/posts and screenshots into Obsidian capture notes."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


HOME = Path.home()
SKILL_DIR = Path(__file__).resolve().parents[1]
SKILLS_ROOT = SKILL_DIR.parent
DEFAULT_VAULT = HOME / "Obsidian/Zerg"
VAULT = Path(os.environ.get("IG_DEEP_INGEST_VAULT", DEFAULT_VAULT))
CACHE = Path(os.environ.get("IG_DEEP_INGEST_CACHE", "/private/tmp/ig-deep-ingest"))
CAPTURE_DIR = VAULT / "MattZerg/Captures/Instagram-Reel-Ingest"
GMAIL_SKILL = HOME / ".claude/skills/gmail-skill/gmail_skill.py"
PLAYWRIGHT_SESSIONS = SKILLS_ROOT / "playwright-skill/sessions"

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".tif", ".tiff", ".bmp"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
FALSE_REPO_OWNERS = {
    "http", "https", "www.instagram.com", "instagram.com", "reel", "reels",
    "com", "usr", "bin", "var", "tmp", "Users", "Library", "Mobile",
    "c", "p", "tv", "tags", "privacy", "legal", "instagram",
}
NOISE_DOMAINS = {
    "about.instagram.com", "about.meta.com", "developers.facebook.com",
    "facebook.com", "help.instagram.com", "instagram.com", "meta.ai",
    "meta.com", "threads.com",
}


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def slugify(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-")
    return clean[:80] or hashlib.sha1(value.encode()).hexdigest()[:12]


def sh(cmd: list[str], *, cwd: Path | None = None, timeout: int = 120) -> tuple[int, str, str]:
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError as e:
        return 127, "", str(e)
    except subprocess.TimeoutExpired as e:
        return 124, e.stdout or "", e.stderr or f"timeout after {timeout}s"


def which(name: str) -> str | None:
    return shutil.which(name)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.expanduser().open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def shortcode_from_url(url: str) -> str | None:
    m = re.search(r"instagram\.com/(?:reel|p|tv)/([A-Za-z0-9_-]+)", url)
    return m.group(1) if m else None


def item_id(source: str) -> str:
    if source.startswith("http"):
        sc = shortcode_from_url(source)
        if sc:
            return sc
        host = urlparse(source).netloc.replace("www.", "")
        return f"{slugify(host)}-{hashlib.sha1(source.encode()).hexdigest()[:8]}"
    return Path(source).stem[:80] or hashlib.sha1(source.encode()).hexdigest()[:12]


def extract_urls(text: str) -> list[str]:
    urls = re.findall(r"https?://[^\s<>)\"']+", text or "")
    return [u.rstrip(".,;]") for u in urls]


def candidate_lines(text: str) -> list[str]:
    lines = []
    for line in (text or "").splitlines():
        s = re.sub(r"\s+", " ", line).strip()
        if not s:
            continue
        if re.search(
            r"github|gitlab|repo|install|npm |npx |pip |brew |docker|mcp|modelcontextprotocol|"
            r"tool|extension|open[- ]source|skills?|agents?|workflow|automation|claude|codex|gemini|"
            r"obsidian|browser|vs code|vscode|\.ai|\.dev|\.com|/[A-Za-z0-9_.-]{2,}",
            s,
            re.I,
        ):
            lines.append(s)
    return lines[:200]


def detect_candidates(sources: dict[str, str]) -> list[dict[str, Any]]:
    found: dict[tuple[str, str], dict[str, Any]] = {}

    def add(kind: str, value: str, source: str, evidence: str, confidence: str) -> None:
        key = (kind, value.lower())
        if key not in found:
            found[key] = {
                "kind": kind,
                "value": value,
                "confidence": confidence,
                "sources": [],
                "evidence": [],
            }
        found[key]["sources"].append(source)
        if evidence and evidence not in found[key]["evidence"]:
            found[key]["evidence"].append(evidence[:300])

    for source, text in sources.items():
        if not text:
            continue
        for url in extract_urls(text):
            parsed = urlparse(url)
            host = parsed.netloc.replace("www.", "")
            if host == "github.com":
                parts = [p for p in parsed.path.split("/") if p]
                if len(parts) >= 2:
                    add("github_repo", f"{parts[0]}/{parts[1]}", source, url, "high")
                add("url", url, source, url, "high")
            elif host:
                if host not in NOISE_DOMAINS and not host.endswith(".instagram.com"):
                    add("domain", host, source, url, "medium")

        for line in candidate_lines(text):
            for owner, repo in re.findall(r"(?:https?://)?(?:www\.)?github\.com[/: ]+([A-Za-z0-9_.-]{1,39})/([A-Za-z0-9_.-]{2,100})", line, re.I):
                add("github_repo", f"{owner}/{repo.strip('.')}", source, line, "high")
            for owner, repo in re.findall(r"(?<![\w.-])([A-Za-z0-9_.-]{1,39})/([A-Za-z0-9_.-]{2,100})(?![\w.-])", line):
                if owner in FALSE_REPO_OWNERS or "." in owner:
                    continue
                if source == "browser_links" and re.search(r"instagram\.com/(?:p|reel|tv|explore|legal|accounts|web|popular|c)/", line):
                    continue
                value = f"{owner}/{repo.strip('.')}"
                confidence = "high" if re.search(r"github|repo", line, re.I) else "medium"
                add("repo_like", value, source, line, confidence)
            for cmd in re.findall(r"\b(?:npm|npx|pip|brew|docker)\s+(?:install|add|run|compose)?\s*[^;\n]{2,120}", line, re.I):
                add("install_command", cmd.strip(), source, line, "medium")
            for domain in re.findall(r"\b([A-Za-z0-9-]+\.(?:ai|dev|app|com|io|sh|so|xyz))\b", line):
                domain_l = domain.lower()
                if domain_l not in {"github.com", *NOISE_DOMAINS} and not domain_l.endswith(".instagram.com"):
                    add("domain", domain, source, line, "medium")
            for tool in re.findall(r"\b([A-Za-z0-9_.-]*(?:mcp|modelcontextprotocol)[A-Za-z0-9_.-]*)\b", line, re.I):
                value = tool.strip("._-")
                if len(value) >= 3:
                    add("tool_identifier", value, source, line, "medium")
            for tool in re.findall(
                r"(?:called|tool called|extension called|built with|powered by|behind my|using|like)\s+([A-Z][A-Za-z0-9.+-]*(?:\s+[A-Z][A-Za-z0-9.+-]*){0,3})",
                line,
            ):
                value = re.sub(r"\s+", " ", tool).split(". ")[0].strip(" .,:;\"'")
                if len(value) >= 4:
                    add("tool_mention", value, source, line, "medium")
            known_tools = (
                "Pixel Agents", "Ruflo", "Firecrawl", "Superpowers", "Remotion",
                "Vercel Agent Browser", "Agent Browser", "Claude Blog", "LLM Wiki",
                "Obsidian Skills", "Obsidian skills", "Graphify", "PARA", "QMD",
                "Sunly AI", "Nextgen AI Skills Toolkit", "OpenClaw", "Claude Code status bar",
                "statusline", "Gemini", "Three js",
            )
            for value in known_tools:
                if re.search(rf"(?<!\w){re.escape(value)}(?!\w)", line, re.I):
                    add("tool_mention", value, source, line, "medium")

    return sorted(found.values(), key=lambda x: (x["kind"], x["value"].lower()))


def playwright_state_path(session: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in session)
    return PLAYWRIGHT_SESSIONS / f"{safe}.json"


def canonical_browser_url(url: str) -> str:
    """Use Instagram's post permalink surface to avoid logged-in Reels feed drift."""
    if "instagram.com/" not in url:
        return url
    shortcode = shortcode_from_url(url)
    if not shortcode:
        return url
    return f"https://www.instagram.com/p/{shortcode}/"


def browser_extract(url: str, work: Path, args: argparse.Namespace) -> dict[str, Any]:
    """Extract visible IG text, links, carousel screenshots, and browser cookies."""
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except Exception as e:
        return {"status": "missing_dependency", "tool": "playwright", "error": str(e)}

    shots = work / "browser-screens"
    shots.mkdir(exist_ok=True)
    state = playwright_state_path(args.browser_session)
    state_exists = state.exists()
    browser_url = canonical_browser_url(url)
    result: dict[str, Any] = {
        "status": "started",
        "session": args.browser_session,
        "storage_state": str(state),
        "storage_state_exists": state_exists,
        "url": browser_url,
        "screenshots": [],
        "texts": [],
        "links": [],
        "cookies_file": "",
    }

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=not args.browser_visible,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context_kwargs: dict[str, Any] = {
            "viewport": {"width": 1440, "height": 1800},
            "ignore_https_errors": True,
            "user_agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        if state_exists:
            context_kwargs["storage_state"] = str(state)
        context = browser.new_context(**context_kwargs)
        page = context.new_page()
        try:
            page.goto(browser_url, wait_until="domcontentloaded", timeout=args.browser_timeout_ms)
            page.wait_for_timeout(args.browser_settle_ms)

            for label in (
                "Not Now",
                "Not now",
                "Close",
                "View all comments",
                "Load more comments",
                "View more comments",
                "more",
            ):
                for _ in range(2):
                    try:
                        page.get_by_text(label, exact=True).first.click(timeout=1200)
                        page.wait_for_timeout(800)
                    except Exception:
                        break

            blocked = page.locator("input[name='username']").count() > 0
            if not blocked:
                blocked = page.get_by_text(re.compile(r"Log in|Sign up", re.I)).count() > 0
            article_text = ""
            try:
                article = page.locator("article").first
                if article.count():
                    article_text = article.inner_text(timeout=3000)
            except Exception:
                article_text = ""
            body_text = page.locator("body").inner_text(timeout=5000)
            result["texts"].append({"kind": "article", "text": article_text})
            result["texts"].append({"kind": "body", "text": body_text[:20000]})

            links = page.eval_on_selector_all(
                "a[href]",
                """els => els.slice(0, 500).map(a => ({
                    text: (a.innerText || a.getAttribute('aria-label') || '').trim(),
                    href: a.href
                }))""",
            )
            result["links"] = links

            for idx in range(max(1, args.browser_max_slides)):
                page.wait_for_timeout(700)
                shot = shots / f"slide_{idx + 1:02d}.png"
                page.screenshot(path=str(shot), full_page=False)
                result["screenshots"].append(str(shot))

                clicked = False
                for selector in (
                    "button[aria-label='Next']",
                    "div[role='button'][aria-label='Next']",
                    "svg[aria-label='Next']",
                ):
                    try:
                        loc = page.locator(selector).first
                        if loc.count() == 0:
                            continue
                        if selector.startswith("svg"):
                            loc.locator("xpath=ancestor::*[@role='button' or self::button][1]").click(timeout=1500)
                        else:
                            loc.click(timeout=1500)
                        page.wait_for_timeout(900)
                        clicked = True
                        break
                    except Exception:
                        continue
                if not clicked:
                    break

            cookies = context.cookies()
            cookie_file = work / "browser-cookies.txt"
            cookie_lines = ["# Netscape HTTP Cookie File"]
            for c in cookies:
                domain = c.get("domain", "")
                if "instagram" not in domain:
                    continue
                include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
                path = c.get("path", "/")
                secure = "TRUE" if c.get("secure") else "FALSE"
                expires = int(c.get("expires") or 0)
                cookie_lines.append("\t".join([domain, include_subdomains, path, secure, str(expires), c.get("name", ""), c.get("value", "")]))
            cookie_file.write_text("\n".join(cookie_lines) + "\n", encoding="utf-8")
            result["cookies_file"] = str(cookie_file)
            result["status"] = "login_required" if blocked and not state_exists else "ok"
            state.parent.mkdir(parents=True, exist_ok=True)
            context.storage_state(path=str(state))
        except PlaywrightTimeoutError as e:
            result["status"] = "timeout"
            result["error"] = str(e)
            try:
                shot = shots / "failure.png"
                page.screenshot(path=str(shot), full_page=False)
                result["screenshots"].append(str(shot))
                result["texts"].append({"kind": "failure_body", "text": page.locator("body").inner_text(timeout=2000)[:12000]})
            except Exception:
                pass
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            try:
                shot = shots / "failure.png"
                page.screenshot(path=str(shot), full_page=False)
                result["screenshots"].append(str(shot))
                result["texts"].append({"kind": "failure_body", "text": page.locator("body").inner_text(timeout=2000)[:12000]})
            except Exception:
                pass
        finally:
            context.close()
            browser.close()

    return result


def dump_metadata(url: str, work: Path, cookies: str | None) -> dict[str, Any]:
    if not which("yt-dlp"):
        return {"status": "missing_dependency", "tool": "yt-dlp"}
    cmd = ["yt-dlp", "--dump-json", "--no-playlist"]
    if cookies:
        cmd.extend(["--cookies", cookies])
    cmd.append(url)
    code, out, err = sh(cmd, cwd=work, timeout=90)
    if code != 0:
        return {"status": "failed", "returncode": code, "stderr": err[-2000:]}
    try:
        data = json.loads(out)
        keep = {
            "id", "title", "description", "uploader", "uploader_id", "channel",
            "timestamp", "upload_date", "duration", "webpage_url", "thumbnail",
        }
        return {"status": "ok", **{k: data.get(k) for k in keep if data.get(k) is not None}}
    except Exception as e:
        return {"status": "parse_failed", "error": str(e), "stdout": out[:2000]}


def download_media(url: str, work: Path, cookies: str | None) -> dict[str, Any]:
    if not which("yt-dlp"):
        return {"status": "missing_dependency", "tool": "yt-dlp"}
    out_tpl = str(work / "media.%(ext)s")
    cmd = ["yt-dlp", "--no-playlist", "-f", "bv*+ba/b", "-o", out_tpl]
    if cookies:
        cmd.extend(["--cookies", cookies])
    cmd.append(url)
    code, out, err = sh(cmd, cwd=work, timeout=240)
    files = sorted(work.glob("media.*"))
    if code != 0 or not files:
        return {"status": "failed", "returncode": code, "stderr": err[-2000:], "stdout": out[-1000:]}
    return {"status": "ok", "path": str(files[0]), "stdout": out[-1000:]}


def copy_local_media(path: Path, work: Path) -> dict[str, Any]:
    src = path.expanduser()
    if not src.exists():
        return {"status": "missing", "path": str(src)}
    dst = work / f"input{src.suffix.lower()}"
    shutil.copy2(src, dst)
    return {"status": "ok", "path": str(dst)}


def extract_audio(media: Path, work: Path) -> dict[str, Any]:
    if not which("ffmpeg"):
        return {"status": "missing_dependency", "tool": "ffmpeg"}
    audio = work / "audio.wav"
    cmd = ["ffmpeg", "-y", "-i", str(media), "-vn", "-ac", "1", "-ar", "16000", str(audio)]
    code, _out, err = sh(cmd, timeout=180)
    if code != 0 or not audio.exists():
        return {"status": "failed", "returncode": code, "stderr": err[-2000:]}
    return {"status": "ok", "path": str(audio)}


def transcribe(audio: Path, work: Path) -> dict[str, Any]:
    custom = os.environ.get("IG_DEEP_INGEST_TRANSCRIBE_CMD")
    if custom:
        cmd = custom.format(audio=str(audio), out_dir=str(work))
        code, out, err = sh(["/bin/zsh", "-lc", cmd], timeout=600)
        text = collect_transcript_text(work)
        return {"status": "ok" if code == 0 else "failed", "returncode": code, "text": text or out, "stderr": err[-1000:]}

    if which("whisper"):
        cmd = ["whisper", str(audio), "--model", os.environ.get("IG_DEEP_INGEST_WHISPER_MODEL", "base"), "--output_dir", str(work), "--output_format", "txt"]
        code, out, err = sh(cmd, timeout=900)
        text = collect_transcript_text(work)
        return {"status": "ok" if code == 0 else "failed", "returncode": code, "text": text or out, "stderr": err[-1000:]}

    if which("mlx-whisper"):
        cmd = ["mlx-whisper", str(audio), "--output-dir", str(work)]
        code, out, err = sh(cmd, timeout=900)
        text = collect_transcript_text(work)
        return {"status": "ok" if code == 0 else "failed", "returncode": code, "text": text or out, "stderr": err[-1000:]}

    return {"status": "missing_dependency", "tried": ["IG_DEEP_INGEST_TRANSCRIBE_CMD", "whisper", "mlx-whisper"], "text": ""}


def collect_transcript_text(work: Path) -> str:
    parts = []
    for p in sorted(work.glob("*.txt")):
        if p.name in {"ocr.txt"}:
            continue
        try:
            parts.append(p.read_text(encoding="utf-8", errors="ignore").strip())
        except Exception:
            pass
    return "\n\n".join(x for x in parts if x)


def sample_frames(media: Path, work: Path, fps: str) -> dict[str, Any]:
    frames = work / "frames"
    frames.mkdir(exist_ok=True)
    if media.suffix.lower() in IMAGE_EXTS:
        dst = frames / f"frame_0001{media.suffix.lower()}"
        shutil.copy2(media, dst)
        return {"status": "ok", "frames_dir": str(frames), "count": 1}
    if not which("ffmpeg"):
        return {"status": "missing_dependency", "tool": "ffmpeg"}
    cmd = ["ffmpeg", "-y", "-i", str(media), "-vf", f"fps={fps}", "-q:v", "2", str(frames / "frame_%04d.jpg")]
    code, _out, err = sh(cmd, timeout=240)
    count = len(list(frames.glob("frame_*")))
    if code != 0 or count == 0:
        return {"status": "failed", "returncode": code, "stderr": err[-2000:], "count": count}
    return {"status": "ok", "frames_dir": str(frames), "count": count}


def ocr_frames(frames_dir: Path, work: Path, max_frames: int) -> dict[str, Any]:
    if not which("tesseract"):
        return {"status": "missing_dependency", "tool": "tesseract", "items": []}
    pre = work / "ocr-preprocessed"
    pre.mkdir(parents=True, exist_ok=True)
    items = []
    frames = sorted(frames_dir.glob("frame_*"))
    if not frames:
        frames = sorted(p for p in frames_dir.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    frames = frames[:max_frames]
    for frame in frames:
        source = frame
        if which("magick"):
            tmp = pre / f"{frame.stem}.png"
            code, _out, _err = sh(["magick", str(frame), "-resize", "1800x", "-colorspace", "Gray", "-sharpen", "0x1", str(tmp)], timeout=30)
            if code == 0 and tmp.exists():
                source = tmp
        code, out, err = sh(["tesseract", str(source), "stdout", "--psm", "6"], timeout=45)
        text = re.sub(r"[ \t]+", " ", out).strip()
        if code == 0 and text:
            items.append({"frame": str(frame), "text": text})
        elif code != 0:
            items.append({"frame": str(frame), "error": err[-500:]})
    return {"status": "ok", "items": items, "frames_checked": len(frames)}


def note_path_for(identifier: str) -> Path:
    today = dt.date.today().isoformat()
    return CAPTURE_DIR / f"{today}-{slugify(identifier)}.md"


def md_escape(text: Any) -> str:
    if text is None:
        return ""
    return str(text).replace("\r\n", "\n").strip()


def write_note(result: dict[str, Any]) -> Path:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    path = note_path_for(result["id"])
    meta = result.get("metadata", {})
    browser = result.get("browser", {})
    transcript = result.get("transcript", {})
    ocr_items = result.get("ocr", {}).get("items", [])
    candidates = result.get("candidates", [])

    lines = [
        "---",
        f"title: Instagram deep ingest - {result['id']}",
        "source: ig-deep-ingest",
        f"created: {now_iso()}",
        f"status: {result.get('status', 'captured')}",
        "tags: [instagram, ingest, source-capture]",
        "---",
        "",
        f"# Instagram Deep Ingest - {result['id']}",
        "",
        "## Source",
        "",
        f"- Input: `{result.get('source')}`",
        f"- Work dir: `{result.get('work_dir')}`",
        f"- Source type: `{result.get('source_type')}`",
        f"- Shortcode: `{result.get('shortcode') or ''}`",
        f"- Origin: `{result.get('origin') or ''}`",
        "",
        "## Browser Extraction",
        "",
        f"- Status: `{browser.get('status', '')}`",
        f"- Session: `{browser.get('session', '')}`",
        f"- Storage state existed before run: `{browser.get('storage_state_exists', '')}`",
        f"- Screenshots: `{len(browser.get('screenshots', []))}`",
        f"- Links: `{len(browser.get('links', []))}`",
        f"- Error: {md_escape(browser.get('error') or '')}",
        "",
        "## Metadata",
        "",
        f"- Status: `{meta.get('status', '')}`",
        f"- Uploader: `{meta.get('uploader') or meta.get('uploader_id') or ''}`",
        f"- Title: {md_escape(meta.get('title'))}",
        f"- URL: {md_escape(meta.get('webpage_url'))}",
        "",
        "### Caption / Description",
        "",
        md_escape(meta.get("description") or result.get("caption") or ""),
        "",
        "### Browser Text",
        "",
        md_escape("\n\n".join(x.get("text", "") for x in browser.get("texts", []) if x.get("text"))[:12000]),
        "",
        "### Browser Links",
        "",
    ]
    browser_links = browser.get("links", [])
    if browser_links:
        for link in browser_links[:80]:
            label = md_escape(link.get("text") or link.get("href") or "link")
            lines.append(f"- [{label}]({link.get('href')})")
    else:
        lines.append("No browser links extracted.")

    lines.extend([
        "",
        "## Transcript",
        "",
        f"- Status: `{transcript.get('status', '')}`",
        "",
        md_escape(transcript.get("text") or ""),
        "",
        "## OCR",
        "",
        f"- Status: `{result.get('ocr', {}).get('status', '')}`",
        f"- Frames checked: `{result.get('ocr', {}).get('frames_checked', 0)}`",
        "",
    ])
    if ocr_items:
        for item in ocr_items[:30]:
            lines.extend([
                f"### {Path(item.get('frame', '')).name}",
                "",
                f"`{item.get('frame', '')}`",
                "",
                md_escape(item.get("text") or item.get("error") or ""),
                "",
            ])
    else:
        lines.extend(["No OCR text extracted.", ""])

    lines.extend(["## Detected Candidates", ""])
    if candidates:
        lines.append("| Kind | Value | Confidence | Sources |")
        lines.append("|---|---|---|---|")
        for c in candidates:
            lines.append(f"| {c['kind']} | `{c['value']}` | {c['confidence']} | {', '.join(sorted(set(c['sources'])))} |")
        lines.extend(["", "### Evidence", ""])
        for c in candidates[:40]:
            lines.append(f"- `{c['value']}`: {' | '.join(c.get('evidence', [])[:3])}")
    else:
        lines.append("No repo/tool/domain candidates detected.")

    lines.extend([
        "",
        "## Evaluation",
        "",
        "- Verdict: `unreviewed`",
        "- Integration target: `MattZerg/Skills/setup-ideas-evaluation-2026-06.md`",
        "- Notes:",
        "",
        "## Raw Status",
        "",
        "```json",
        json.dumps(result.get("status_detail", {}), indent=2, ensure_ascii=False),
        "```",
        "",
    ])
    # Atomic write — the vault is live-synced (Obsidian Sync), so a partial write
    # could be observed mid-flush. tmp-in-same-dir + os.replace avoids that.
    tmp = path.with_name("." + path.name + ".tmp")
    tmp.write_text("\n".join(lines), encoding="utf-8")
    os.replace(tmp, path)
    return path


def ingest_one(source: str, args: argparse.Namespace, origin: str | None = None, caption: str | None = None) -> dict[str, Any]:
    identifier = item_id(source)
    work = CACHE / identifier
    work.mkdir(parents=True, exist_ok=True)
    cookies = args.cookies or os.environ.get("IG_DEEP_INGEST_COOKIES")
    result: dict[str, Any] = {
        "id": identifier,
        "source": source,
        "origin": origin,
        "caption": caption,
        "shortcode": shortcode_from_url(source),
        "work_dir": str(work),
        "status": "captured",
        "status_detail": {},
    }

    media_path: Path | None = None
    browser = {"status": "not_run", "screenshots": [], "texts": [], "links": []}
    if source.startswith("http"):
        result["source_type"] = "url"
        if args.browser and "instagram.com/" in source:
            browser = browser_extract(source, work, args)
            result["browser"] = browser
            result["status_detail"]["browser"] = browser
            if not cookies and browser.get("cookies_file"):
                cookies = browser["cookies_file"]
        result["metadata"] = {"status": "skipped"} if args.no_metadata else dump_metadata(source, work, cookies)
        media = download_media(source, work, cookies) if not args.metadata_only else {"status": "skipped"}
        result["status_detail"]["media"] = media
        if media.get("status") == "ok":
            media_path = Path(media["path"])
    else:
        result["source_type"] = "file"
        result["browser"] = browser
        local = copy_local_media(Path(source), work)
        result["metadata"] = {"status": "local_file"}
        result["status_detail"]["media"] = local
        if local.get("status") == "ok":
            media_path = Path(local["path"])

    transcript = {"status": "not_run", "text": ""}
    ocr = {"status": "not_run", "items": [], "frames_checked": 0}
    if media_path:
        if media_path.suffix.lower() in VIDEO_EXTS and not args.no_transcript:
            audio = extract_audio(media_path, work)
            result["status_detail"]["audio"] = audio
            if audio.get("status") == "ok":
                transcript = transcribe(Path(audio["path"]), work)
            else:
                transcript = {"status": "audio_failed", "text": "", "detail": audio}
        elif media_path.suffix.lower() in IMAGE_EXTS:
            transcript = {"status": "not_applicable_image", "text": ""}

        if not args.no_ocr:
            frames = sample_frames(media_path, work, args.fps)
            result["status_detail"]["frames"] = frames
            if frames.get("status") == "ok":
                ocr = ocr_frames(Path(frames["frames_dir"]), work, args.max_ocr_frames)
            else:
                ocr = {"status": "frame_sampling_failed", "items": [], "frames_checked": 0, "detail": frames}
    else:
        transcript = {"status": "no_media", "text": ""}
        ocr = {"status": "no_media", "items": [], "frames_checked": 0}

    if "browser" not in result:
        result["browser"] = browser
    if browser.get("screenshots") and not args.no_ocr:
        browser_ocr = ocr_frames(Path(browser["screenshots"][0]).parent, work / "browser-ocr", args.max_ocr_frames)
        result["status_detail"]["browser_ocr"] = browser_ocr
        if ocr.get("status") in {"not_run", "no_media", "frame_sampling_failed"}:
            ocr = browser_ocr
        else:
            ocr["items"] = ocr.get("items", []) + browser_ocr.get("items", [])
            ocr["frames_checked"] = ocr.get("frames_checked", 0) + browser_ocr.get("frames_checked", 0)

    result["transcript"] = transcript
    result["ocr"] = ocr

    ocr_text = "\n".join(i.get("text", "") for i in ocr.get("items", []))
    browser_text = "\n\n".join(x.get("text", "") for x in browser.get("texts", []) if x.get("text"))
    browser_links = "\n".join(f"{x.get('text', '')} {x.get('href', '')}" for x in browser.get("links", []))
    sources = {
        "caption": caption or result.get("metadata", {}).get("description") or "",
        "title": result.get("metadata", {}).get("title") or "",
        "browser": browser_text,
        "browser_links": browser_links,
        "transcript": transcript.get("text") or "",
        "ocr": ocr_text,
    }
    result["candidates"] = detect_candidates(sources)
    result["note_path"] = str(write_note(result))
    return result


def gmail_urls(args: argparse.Namespace) -> list[dict[str, str]]:
    if not GMAIL_SKILL.exists():
        raise SystemExit(f"gmail skill not found: {GMAIL_SKILL}")
    cmd = ["python3", str(GMAIL_SKILL), "search", args.query, "--max-results", str(args.max), "--account", args.account]
    code, out, err = sh(cmd, timeout=120)
    if code != 0:
        raise SystemExit(f"gmail search failed: {err}")
    payload = json.loads(out)
    rows = []
    for msg in payload.get("results", []):
        blob = "\n".join(str(msg.get(k, "")) for k in ("subject", "snippet"))
        for url in extract_urls(blob):
            if "instagram.com/" in url or args.include_non_ig:
                rows.append({"url": url.replace("&amp;", "&"), "origin": f"gmail:{msg.get('id')}", "caption": msg.get("subject", "")})
    return rows


def export_urls(args: argparse.Namespace) -> list[dict[str, str]]:
    rows = read_jsonl(Path(args.records))
    out = []
    for r in rows:
        cap = r.get("caption") or ""
        include = True
        if args.filter == "needs_deep_dive":
            include = r.get("type") == "reel" and len(cap) < args.caption_chars
        elif args.filter == "caption_empty":
            include = not cap.strip()
        elif args.filter:
            include = args.filter.lower() in json.dumps(r, ensure_ascii=False).lower()
        if include:
            out.append({"url": r["url"], "origin": "instagram-export", "caption": cap})
        if args.max and len(out) >= args.max:
            break
    return out


def run_ingest(args: argparse.Namespace) -> int:
    results = []
    for source in args.sources:
        res = ingest_one(source, args)
        results.append(res)
        print(json.dumps({"source": source, "note_path": res["note_path"], "candidates": res["candidates"]}, ensure_ascii=False))
    return 0


def run_gmail(args: argparse.Namespace) -> int:
    rows = gmail_urls(args)
    for row in rows[: args.max]:
        res = ingest_one(row["url"], args, origin=row["origin"], caption=row.get("caption"))
        print(json.dumps({"source": row["url"], "origin": row["origin"], "note_path": res["note_path"], "candidates": res["candidates"]}, ensure_ascii=False))
    return 0


def run_export(args: argparse.Namespace) -> int:
    rows = export_urls(args)
    for row in rows:
        res = ingest_one(row["url"], args, origin=row["origin"], caption=row.get("caption"))
        print(json.dumps({"source": row["url"], "origin": row["origin"], "note_path": res["note_path"], "candidates": res["candidates"]}, ensure_ascii=False))
    return 0


def run_login(args: argparse.Namespace) -> int:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        print(json.dumps({"success": False, "status": "missing_dependency", "error": str(e)}, ensure_ascii=False))
        return 1

    state = playwright_state_path(args.browser_session)
    state_exists = state.exists()
    deadline = dt.datetime.now() + dt.timedelta(seconds=args.timeout_s)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context_kwargs: dict[str, Any] = {
            "viewport": {"width": 1440, "height": 1200},
            "ignore_https_errors": True,
        }
        if state_exists:
            context_kwargs["storage_state"] = str(state)
        context = browser.new_context(**context_kwargs)
        page = context.new_page()
        page.goto("https://www.instagram.com/accounts/login/", wait_until="domcontentloaded", timeout=45000)
        print(json.dumps({
            "success": False,
            "status": "waiting_for_manual_login",
            "session": args.browser_session,
            "storage_state": str(state),
            "timeout_s": args.timeout_s,
            "instruction": "Log into Instagram in the visible browser window; the session saves automatically when sessionid appears.",
        }, ensure_ascii=False), flush=True)
        success = False
        while dt.datetime.now() < deadline:
            cookies = context.cookies()
            if any(c.get("domain", "").endswith("instagram.com") and c.get("name") == "sessionid" for c in cookies):
                success = True
                break
            page.wait_for_timeout(1500)
        state.parent.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=str(state))
        context.close()
        browser.close()

    print(json.dumps({
        "success": success,
        "status": "logged_in" if success else "timeout_saved_partial_state",
        "session": args.browser_session,
        "storage_state": str(state),
    }, ensure_ascii=False))
    return 0 if success else 2


def add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--cookies", default=None, help="yt-dlp cookies file; defaults to IG_DEEP_INGEST_COOKIES")
    p.add_argument("--fps", default="1/2", help="ffmpeg frame sampling rate, default one frame every 2 seconds")
    p.add_argument("--max-ocr-frames", type=int, default=80)
    p.add_argument("--browser", action="store_true", help="use logged-in Playwright browser extraction for Instagram URLs")
    p.add_argument("--browser-session", default="instagram", help="Playwright session name, default instagram")
    p.add_argument("--browser-visible", action="store_true", help="show browser window, useful for first Instagram login")
    p.add_argument("--browser-timeout-ms", type=int, default=45000)
    p.add_argument("--browser-settle-ms", type=int, default=3500)
    p.add_argument("--browser-max-slides", type=int, default=12)
    p.add_argument("--metadata-only", action="store_true")
    p.add_argument("--no-metadata", action="store_true", help="skip yt-dlp metadata fetch; useful for plumbing tests or blocked IG links")
    p.add_argument("--no-transcript", action="store_true")
    p.add_argument("--no-ocr", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Deep-ingest Instagram reels/posts/screenshots into Obsidian capture notes.")
    sub = p.add_subparsers(dest="cmd", required=True)

    ingest = sub.add_parser("ingest")
    add_common(ingest)
    ingest.add_argument("sources", nargs="+")
    ingest.set_defaults(func=run_ingest)

    gmail = sub.add_parser("gmail")
    add_common(gmail)
    gmail.add_argument("--account", default="matthew@zergai.com")
    gmail.add_argument("--query", required=True)
    gmail.add_argument("--max", type=int, default=20)
    gmail.add_argument("--include-non-ig", action="store_true")
    gmail.set_defaults(func=run_gmail)

    export = sub.add_parser("export")
    add_common(export)
    export.add_argument("--records", required=True)
    export.add_argument("--filter", default="needs_deep_dive")
    export.add_argument("--caption-chars", type=int, default=120)
    export.add_argument("--max", type=int, default=25)
    export.set_defaults(func=run_export)

    login = sub.add_parser("login")
    login.add_argument("--browser-session", default="instagram", help="Playwright session name, default instagram")
    login.add_argument("--timeout-s", type=int, default=600, help="seconds to wait for manual login")
    login.set_defaults(func=run_login)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    CACHE.mkdir(parents=True, exist_ok=True)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
