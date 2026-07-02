#!/usr/bin/env python3
"""skill-scout: discover, score, and triage new claude-code skills.

See SKILL.md for the full design + rubric. This script implements:
  poll  — scan sources, log new candidates, optionally DM ≥ threshold
  review <slug>      — deeper risk-grep on a candidate
  accept <slug>      — mark accepted
  reject <slug> <why> — mark rejected
  state — show counts

Sources currently wired:
  • Anthropic claude-plugins cache (~/.claude/plugins/cache/claude-plugins-official/)
  • Known skill repos via `gh repo view` (allowlist in state/sources.yaml)
  • Curated self-sent Gmail links (state/gmail-self-sent-links.jsonl)
  • Optional: gh topic search (--include-topic-search)

Safety: NEVER auto-installs. Every accept-decision still requires Matt to
run the actual install command (printed but not executed).
"""
from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

PT = ZoneInfo("America/Los_Angeles")
SCRIPT_DIR = Path(__file__).resolve().parent
STATE_DIR = SCRIPT_DIR / "state"
SEEN_PATH = STATE_DIR / "seen.jsonl"
SOURCES_PATH = STATE_DIR / "sources.yaml"
GMAIL_SELF_SENT_LINKS_PATH = STATE_DIR / "gmail-self-sent-links.jsonl"
LOGS_DIR = SCRIPT_DIR / "logs"

VAULT = Path("/Users/mattheweisner/Obsidian/Zerg/MattZerg")
VAULT_SKILLS_DIR = VAULT / "Skills"

PLUGINS_CACHE = Path.home() / ".claude" / "plugins" / "cache" / "claude-plugins-official"
INSTALLED_SKILLS_DIR = Path.home() / ".claude" / "skills"
GMAIL_SKILL = Path.home() / ".claude" / "skills" / "gmail-skill" / "gmail_skill.py"
GOOGLE_SKILL_PYTHON = Path.home() / ".claude" / "skills" / "gcal-skill" / ".venv" / "bin" / "python"

FAKE_MATT_DM = "D0B0T0ETDR8"
SLACK_SKILL = Path.home() / ".claude" / "skills" / "slack-skill" / "slack_skill.py"

PROMOTION_THRESHOLD = 7  # total score
SAFETY_THRESHOLD = 4     # safety alone

DEFAULT_KNOWN_REPOS = [
    "idanbeck/claude-skills",
    "anthropic-quickstarts/claude-cookbooks",
    "mattzerg/claude-skills",
]

# Destructive patterns that auto-reduce safety score
DESTRUCTIVE_PATTERNS = [
    r"rm\s+-rf\s+[/\$]",
    r"git push --force\s+(?!.*matt/)",
    r"DROP TABLE",
    r"kubectl delete\s+(?:--all|ns|namespace)",
    r"shutil\.rmtree\(\s*['\"]/",
    r"os\.system\(\s*['\"]\s*rm",
]
SECRET_REQUEST_PATTERNS = [
    r"API_KEY\s*=",
    r"prompt.*[Pp]aste.*token",
    r"input\(.*password",
]
URL_RE = re.compile(r"https?://[^\s<>'\")\]]+")
HREF_RE = re.compile(r"""href=["']([^"']+)["']""", re.IGNORECASE)
MARKDOWN_LINK_RE = re.compile(r"""(?:(?:https?://[^\s<>'")\]]+)|(?:\[[^\]]+\]\((https?://[^)]+)\)))""")
NOISY_LINK_HOSTS = {
    "github.githubassets.com",
    "avatars.githubusercontent.com",
    "github-cloud.s3.amazonaws.com",
    "img.shields.io",
    "user-images.githubusercontent.com",
}
NOISY_LINK_SUFFIXES = (".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".xml")


def load_seen() -> dict:
    out: dict = {}
    if SEEN_PATH.exists():
        for ln in SEEN_PATH.read_text(errors="replace").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                row = json.loads(ln)
                out[row["slug"]] = row
            except (json.JSONDecodeError, KeyError):
                continue
    return out


def append_seen(row: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with SEEN_PATH.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


# ---------- source: claude-plugins marketplace ----------

def candidates_from_plugins_cache() -> list[dict]:
    if not PLUGINS_CACHE.exists():
        return []
    out = []
    for plugin_dir in PLUGINS_CACHE.iterdir():
        if not plugin_dir.is_dir():
            continue
        plugin_name = plugin_dir.name
        # Each subdir is a version (e.g., 0.5.3)
        versions = sorted([p.name for p in plugin_dir.iterdir() if p.is_dir()])
        if not versions:
            continue
        latest = versions[-1]
        plugin_json = plugin_dir / latest / ".claude-plugin" / "plugin.json"
        meta = {}
        if plugin_json.exists():
            try:
                meta = json.loads(plugin_json.read_text())
            except (OSError, json.JSONDecodeError):
                pass
        out.append({
            "slug": f"plugin:{plugin_name}",
            "source": "claude-plugins-official",
            "name": meta.get("name", plugin_name),
            "version": latest,
            "description": meta.get("description", ""),
            "url": f"https://github.com/anthropics/claude-plugins/tree/main/{plugin_name}",
            "local_path": str(plugin_dir / latest),
        })
    return out


# ---------- source: known repos via gh ----------

def candidates_from_known_repos(repos: list[str]) -> list[dict]:
    out = []
    for repo in repos:
        try:
            res = subprocess.run(
                ["gh", "repo", "view", repo, "--json",
                 "name,description,owner,url,stargazerCount,pushedAt,licenseInfo,isFork"],
                capture_output=True, text=True, timeout=15,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            continue
        if res.returncode != 0:
            continue
        try:
            d = json.loads(res.stdout)
        except json.JSONDecodeError:
            continue
        out.append({
            "slug": f"repo:{repo}",
            "source": "known-repo",
            "name": d.get("name"),
            "description": d.get("description") or "",
            "url": d.get("url"),
            "stars": d.get("stargazerCount", 0),
            "pushed_at": d.get("pushedAt"),
            "license": (d.get("licenseInfo") or {}).get("name", "unknown"),
            "is_fork": d.get("isFork", False),
        })
    return out


# ---------- source: curated Gmail self-sent links ----------

def candidates_from_gmail_self_sent_links(path: Path = GMAIL_SELF_SENT_LINKS_PATH) -> list[dict]:
    """Load manually-curated tool candidates from Matt's self-sent Gmail links.

    This deliberately reads normalized JSONL rather than querying Gmail inside
    the scout. Gmail ingestion can happen through the live connector, then
    `poll` scores and dedupes the resulting rows with the normal safety rules.
    """
    if not path.exists():
        return []

    out: list[dict] = []
    for idx, ln in enumerate(path.read_text(errors="replace").splitlines(), start=1):
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        try:
            row = json.loads(ln)
        except json.JSONDecodeError as exc:
            print(f"[warn] invalid JSON in {path}:{idx}: {exc}", file=sys.stderr)
            continue

        slug = row.get("slug")
        if not slug:
            name = row.get("name") or row.get("tool") or f"gmail-link-{idx}"
            slug = "gmail-link:" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

        out.append({
            "slug": slug,
            "source": "gmail-self-sent-links",
            "name": row.get("name") or row.get("tool") or slug.split(":", 1)[-1],
            "description": row.get("description") or "",
            "url": row.get("url") or row.get("original_url") or "",
            "original_url": row.get("original_url") or row.get("url") or "",
            "resolved_urls": row.get("resolved_urls") or [],
            "tool_names": row.get("tool_names") or [],
            "message_ids": row.get("message_ids") or [],
            "subjects": row.get("subjects") or [],
            "sent_at": row.get("sent_at"),
            "recommendation": row.get("recommendation", "watch"),
            "requires_secret": bool(row.get("requires_secret", False)),
            "fills_known_gap": bool(row.get("fills_known_gap", False)),
            "documented": bool(row.get("documented", False)),
            "low_blast_radius": bool(row.get("low_blast_radius", False)),
            "opaque_source": bool(row.get("opaque_source", False)),
            "license": row.get("license", "unknown"),
        })
    return out


def _existing_gmail_link_rows(path: Path = GMAIL_SELF_SENT_LINKS_PATH) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    if not path.exists():
        return rows
    for ln in path.read_text(errors="replace").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        try:
            row = json.loads(ln)
        except json.JSONDecodeError:
            continue
        slug = row.get("slug")
        if slug:
            rows[slug] = row
    return rows


def _run_gmail_skill(args: list[str]) -> dict:
    if not GMAIL_SKILL.exists():
        raise FileNotFoundError(f"missing Gmail skill script: {GMAIL_SKILL}")
    py = str(GOOGLE_SKILL_PYTHON if GOOGLE_SKILL_PYTHON.exists() else "python3")
    cmd = [py, str(GMAIL_SKILL), *args]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if res.returncode != 0:
        raise RuntimeError(f"gmail-skill failed: {' '.join(cmd)}\n{res.stderr or res.stdout}")
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"gmail-skill returned non-JSON output: {exc}\n{res.stdout[:500]}") from exc


def _extract_urls(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for url in URL_RE.findall(text or ""):
        cleaned = url.rstrip(".,;:!?)]}>")
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            out.append(cleaned)
    return out


def _fetch_page_links(url: str, limit: int) -> list[str]:
    """Best-effort extraction of links from a linked page.

    Skips social surfaces that require auth or return app shells; captures only
    absolute http(s) links and keeps output bounded for scout state hygiene.
    """
    host = urlparse(url).netloc.lower()
    if "instagram.com" in host or "facebook.com" in host or "tiktok.com" in host:
        return []
    if host == "github.com":
        parts = [p for p in urlparse(url).path.split("/") if p]
        if len(parts) >= 2:
            owner, repo = parts[0], parts[1]
            for branch in ("main", "master", "HEAD"):
                raw = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/README.md"
                links = _fetch_text_links(raw, url, limit)
                if links:
                    return links
    try:
        req = Request(url, headers={"User-Agent": "skill-scout/1.0"})
        with urlopen(req, timeout=15) as resp:
            content_type = resp.headers.get("content-type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                return []
            html = resp.read(750_000).decode("utf-8", errors="replace")
    except Exception:
        return []

    out: list[str] = []
    seen: set[str] = set()
    for href in HREF_RE.findall(html):
        absolute = urljoin(url, href).split("#", 1)[0]
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        if _is_noisy_link(absolute):
            continue
        if absolute == url or absolute in seen:
            continue
        seen.add(absolute)
        out.append(absolute)
        if len(out) >= limit:
            break
    return out


def _fetch_text_links(url: str, base_url: str, limit: int) -> list[str]:
    try:
        req = Request(url, headers={"User-Agent": "skill-scout/1.0"})
        with urlopen(req, timeout=15) as resp:
            text = resp.read(750_000).decode("utf-8", errors="replace")
    except Exception:
        return []

    out: list[str] = []
    seen: set[str] = set()
    for match in MARKDOWN_LINK_RE.finditer(text):
        candidate = match.group(1) or match.group(0)
        cleaned = candidate.rstrip(".,;:!?)]}>")
        absolute = urljoin(base_url, cleaned).split("#", 1)[0]
        parsed = urlparse(absolute)
        if absolute.rstrip("/") == base_url.rstrip("/"):
            continue
        if parsed.scheme not in {"http", "https"} or absolute in seen or _is_noisy_link(absolute):
            continue
        seen.add(absolute)
        out.append(absolute)
        if len(out) >= limit:
            break
    return out


def _is_noisy_link(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    return host in NOISY_LINK_HOSTS or path.endswith(NOISY_LINK_SUFFIXES)


def _clean_links(urls: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if not url or _is_noisy_link(url) or url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


def _slugify_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-") or "unknown"


def _classify_gmail_tool_link(urls: list[str], subject: str, body: str) -> dict:
    text = " ".join([subject or "", body or "", " ".join(urls)]).lower()
    primary = urls[0] if urls else ""
    host = urlparse(primary).netloc.lower()

    if "typeui" in text or "48 design skill" in text:
        return {
            "slug": "gmail-link:typeui",
            "name": "TypeUI",
            "description": "CLI and registry pattern for generating design skills and DESIGN.md files for Claude, Codex, Cursor, and other AI coding tools.",
            "resolved_urls": [
                "https://www.typeui.sh/docs",
                "https://github.com/bergside/typeui",
                "https://github.com/bergside/awesome-design-skills",
            ],
            "recommendation": "rebuild-pattern",
            "requires_secret": False,
            "fills_known_gap": True,
            "documented": True,
            "low_blast_radius": True,
        }

    known = [
        ("chrome-devtools-mcp", "Chrome DevTools MCP", "MCP server for browser inspection, console/network debugging, screenshots, and performance analysis through Chrome DevTools.", "https://github.com/ChromeDevTools/chrome-devtools-mcp", "evaluate-now", False, True, True),
        ("firecrawl", "Firecrawl MCP Server", "MCP server exposing Firecrawl web search, scrape, crawl, map, and extraction primitives for agent research workflows.", "https://github.com/firecrawl/firecrawl-mcp-server", "on-demand-only", True, True, False),
        ("playwright-mcp", "Playwright MCP", "MCP server for browser automation and web interaction using Playwright accessibility snapshots rather than screenshots.", "https://github.com/microsoft/playwright-mcp", "defer-existing-playwright-skill", False, False, True),
        ("glif", "Glif MCP Server", "MCP server for running Glif creative workflows, including media and image-generation style use cases.", "https://github.com/glifxyz/glif-mcp-server", "defer-creative-only", True, False, False),
        ("modelcontextprotocol", "Model Context Protocol docs", "Canonical MCP documentation and concepts used as the reference for Zergboard and Zerg product MCP planning.", "https://modelcontextprotocol.io/docs/getting-started/intro", "canonical-reference", False, True, True),
    ]
    for needle, name, desc, canonical_url, recommendation, requires_secret, fills_gap, low_blast in known:
        if needle in text:
            return {
                "slug": f"gmail-link:{_slugify_name(name)}",
                "name": name,
                "description": desc,
                "resolved_urls": [canonical_url],
                "recommendation": recommendation,
                "requires_secret": requires_secret,
                "fills_known_gap": fills_gap,
                "documented": True,
                "low_blast_radius": low_blast,
            }

    opaque = "instagram.com" in host
    if opaque:
        digest = hashlib.sha1(primary.encode()).hexdigest()[:10]
        return {
            "slug": f"gmail-link:instagram-{digest}",
            "name": subject or "Instagram tool lead",
            "description": "Opaque Instagram lead from Matt self-sent Gmail link; exact caption/comments/link targets require logged-in scan.",
            "resolved_urls": urls,
            "recommendation": "watch",
            "requires_secret": False,
            "fills_known_gap": False,
            "documented": False,
            "low_blast_radius": True,
            "opaque_source": True,
        }

    host_name = host.removeprefix("www.") or "unknown-link"
    return {
        "slug": f"gmail-link:{_slugify_name(host_name)}",
        "name": subject or host_name,
        "description": f"Self-sent Gmail link candidate from {host_name}; needs review before install or rebuild decision.",
        "resolved_urls": urls,
        "recommendation": "watch",
        "requires_secret": False,
        "fills_known_gap": False,
        "documented": bool(urls),
        "low_blast_radius": True,
    }


# ---------- scoring ----------

def score_candidate(cand: dict, installed_names: set) -> dict:
    value = 0
    safety = 5  # start full, deduct on red flags
    rationale: list[str] = []

    # Already-installed → skip (treat as "seen, score 0")
    short_name = cand["slug"].split(":")[-1].split("/")[-1]
    if short_name in installed_names:
        return {"value": 0, "safety": 5, "total": 0, "rationale": ["already-installed"], "decision": "skip"}

    # Stars / activity
    stars = cand.get("stars", 0)
    if stars >= 50:
        value += 1
        rationale.append(f"{stars}⭐ — community traction")

    # Has descriptive metadata
    desc = (cand.get("description") or "").strip()
    if len(desc) >= 30:
        value += 1
        rationale.append("good description")

    if cand["source"] == "gmail-self-sent-links":
        value += 1
        rationale.append("curated from Matt self-sent link")
        if cand.get("fills_known_gap"):
            value += 2
            rationale.append("fills known Zerg/Codex gap")
        if cand.get("documented"):
            value += 1
            rationale.append("documented source")
        if cand.get("low_blast_radius"):
            value += 1
            rationale.append("low blast radius")
        if cand.get("requires_secret"):
            safety -= 1
            rationale.append("⚠ requires secret or API key")
        if cand.get("opaque_source"):
            safety -= 1
            rationale.append("⚠ source link not fully extractable")

    # Documented (SKILL.md / plugin.json) — plugins-cache items already have plugin.json
    if cand["source"] == "claude-plugins-official":
        value += 1
        rationale.append("Anthropic-curated")

    # License check
    lic = (cand.get("license") or "").lower()
    if any(t in lic for t in ("mit", "apache", "bsd", "isc")):
        safety += 0  # neutral — already at 5
        rationale.append(f"permissive license ({lic})")
    elif lic and lic not in ("unknown", "none"):
        safety -= 1
        rationale.append(f"non-permissive license ({lic})")

    # Is it a fork? Forks are higher risk
    if cand.get("is_fork"):
        safety -= 1
        rationale.append("⚠ fork — verify upstream provenance")

    # Local-code-scan red flags if local_path available
    local = cand.get("local_path")
    if local:
        path = Path(local)
        if path.exists():
            try:
                blob = ""
                for f in path.rglob("*"):
                    if f.is_file() and f.suffix in (".py", ".sh", ".md", ".js", ".ts"):
                        try:
                            blob += f.read_text(errors="replace")
                        except OSError:
                            continue
                        if len(blob) > 500_000:
                            break
                for pat in DESTRUCTIVE_PATTERNS:
                    if re.search(pat, blob):
                        safety -= 1
                        rationale.append(f"⚠ destructive pattern: {pat}")
                        break
                for pat in SECRET_REQUEST_PATTERNS:
                    if re.search(pat, blob):
                        safety -= 1
                        rationale.append(f"⚠ requests credentials inline: {pat}")
                        break
            except OSError:
                pass

    value = max(0, min(5, value))
    safety = max(0, min(5, safety))
    total = value + safety
    promote = total >= PROMOTION_THRESHOLD and safety >= SAFETY_THRESHOLD
    if cand["source"] == "gmail-self-sent-links":
        rec = (cand.get("recommendation") or "").lower()
        if rec.startswith("defer") or rec in {"on-demand-only", "canonical-reference", "watch"}:
            promote = False
            rationale.append(f"curation verdict: {rec}")
    return {
        "value": value, "safety": safety, "total": total,
        "rationale": rationale, "decision": "promote" if promote else "watch",
    }


def installed_skill_names() -> set:
    if not INSTALLED_SKILLS_DIR.exists():
        return set()
    return {p.name for p in INSTALLED_SKILLS_DIR.iterdir() if p.is_dir()}


# ---------- commands ----------

def cmd_poll(args) -> int:
    seen = load_seen()
    installed = installed_skill_names()
    cands: list[dict] = []
    cands.extend(candidates_from_plugins_cache())
    if not args.no_gmail_links:
        cands.extend(candidates_from_gmail_self_sent_links())
    if not args.no_repos:
        cands.extend(candidates_from_known_repos(DEFAULT_KNOWN_REPOS))

    now = dt.datetime.now(PT)
    new_promoted: list[dict] = []
    new_watch: list[dict] = []
    for c in cands:
        if c["slug"] in seen and not args.rescore:
            continue
        scoring = score_candidate(c, installed)
        c.update(scoring)
        c["ts"] = now.isoformat(timespec="seconds")
        append_seen(c)
        if c["decision"] == "promote":
            new_promoted.append(c)
        elif c["decision"] == "watch":
            new_watch.append(c)

    # Render
    print(f"# skill-scout · poll {now.strftime('%a %b %-d %-I:%M %p PT')}\n")
    print(f"_Scanned {len(cands)} candidates, {len(new_promoted)} new promoted, {len(new_watch)} new watch._\n")

    if new_promoted:
        print(f"## 🟢 Promoted ({len(new_promoted)})\n")
        print("| Slug | Score | Source | Rationale |")
        print("|---|---|---|---|")
        for c in new_promoted:
            print(f"| `{c['slug']}` | {c['total']}/10 (v{c['value']}+s{c['safety']}) | {c['source']} | {'; '.join(c['rationale'][:3])} |")
        print()

    if new_watch:
        print(f"## 🟡 Watch ({len(new_watch)})\n")
        print("| Slug | Score | Source | Rationale |")
        print("|---|---|---|---|")
        for c in new_watch:
            print(f"| `{c['slug']}` | {c['total']}/10 | {c['source']} | {'; '.join(c['rationale'][:2])} |")
        print()

    if args.post and new_promoted and SLACK_SKILL.exists():
        msg = f"🎁 *skill-scout — {len(new_promoted)} new promoted*\n"
        for c in new_promoted[:5]:
            msg += f"\n• `{c['slug']}` — {c['total']}/10 — {c.get('description','')[:80]}"
        try:
            subprocess.run(
                ["/usr/bin/python3", str(SLACK_SKILL), "send", FAKE_MATT_DM, "-m", msg],
                check=True, capture_output=True, text=True, timeout=30,
            )
            print(f"[posted] to {FAKE_MATT_DM}")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"[warn] post failed: {e}", file=sys.stderr)

    if args.vault:
        iso_year, iso_week, _ = now.isocalendar()
        VAULT_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        vp = VAULT_SKILLS_DIR / f"scouted-{iso_year}-W{iso_week:02d}.md"
        # Re-render to vault
        with vp.open("a") as f:
            f.write(f"\n# Poll {now.isoformat(timespec='seconds')}\n\n")
            for c in new_promoted + new_watch:
                f.write(f"- `{c['slug']}` — {c['total']}/10 — {c.get('description','')[:80]}\n")
        print(f"[saved] {vp}")

    return 0


def cmd_state(_args) -> int:
    seen = load_seen()
    by_decision: dict[str, int] = {}
    for r in seen.values():
        by_decision[r.get("decision", "?")] = by_decision.get(r.get("decision", "?"), 0) + 1
    print(f"# skill-scout · state\n")
    print(f"Total seen: **{len(seen)}**")
    for d, n in sorted(by_decision.items()):
        print(f"  · {d}: {n}")
    return 0


def cmd_ingest_gmail_links(args) -> int:
    """Search Matt's sent mail for self-sent tool links and normalize them."""
    after = (dt.datetime.now(PT) - dt.timedelta(days=args.days)).strftime("%Y/%m/%d")
    query = args.query or f'in:sent to:{args.to} after:{after} (http OR https)'
    search_args = ["search", query, "--max-results", str(args.max_results)]
    if args.account:
        search_args.extend(["--account", args.account])
    search = _run_gmail_skill(search_args)
    messages = search.get("results", [])

    existing = _existing_gmail_link_rows()
    rows = dict(existing)
    created: list[dict] = []
    updated: list[dict] = []
    skipped_no_links = 0

    for msg in messages:
        msg_id = msg.get("id")
        if not msg_id:
            continue
        read_args = ["read", msg_id]
        if args.account:
            read_args.extend(["--account", args.account])
        full = _run_gmail_skill(read_args)
        subject = full.get("subject") or msg.get("subject") or ""
        body = full.get("body") or ""
        snippet = full.get("snippet") or msg.get("snippet") or ""
        snippet_urls = _clean_links(_extract_urls(snippet))
        body_urls = _clean_links(_extract_urls(body))
        # Gmail's full HTML body can include unfurled preview assets. Prefer the
        # snippet's visible URL when present; it usually reflects Matt's actual
        # pasted link.
        urls = snippet_urls or body_urls
        if not urls:
            skipped_no_links += 1
            continue
        extracted_urls: list[str] = []
        if args.fetch_pages:
            for url in urls[: args.max_pages]:
                extracted_urls.extend(_fetch_page_links(url, args.max_page_links))
            extracted_urls = _clean_links(extracted_urls)

        classified = _classify_gmail_tool_link(urls, subject, body)
        existing_row = rows.get(classified["slug"], {})
        message_ids = list(dict.fromkeys([*(existing_row.get("message_ids") or []), msg_id]))
        subjects = list(dict.fromkeys([*(existing_row.get("subjects") or []), subject]))
        resolved_urls = _clean_links([*(classified.get("resolved_urls") or []), *urls, *extracted_urls])
        row = {
            **existing_row,
            **classified,
            "url": (classified.get("resolved_urls") or urls)[0],
            "original_url": existing_row.get("original_url") or urls[0],
            "resolved_urls": resolved_urls,
            "extracted_urls": extracted_urls or existing_row.get("extracted_urls") or [],
            "message_ids": message_ids,
            "subjects": subjects,
            "sent_at": full.get("date") or msg.get("date"),
        }
        if classified.get("slug") in existing:
            updated.append(row)
        else:
            created.append(row)
        rows[classified["slug"]] = row

    print(f"# skill-scout · ingest-gmail-links\n")
    print(f"Query: `{query}`")
    print(f"Messages scanned: {len(messages)}")
    print(f"Candidates created: {len(created)}")
    print(f"Candidates updated: {len(updated)}")
    print(f"Messages without links: {skipped_no_links}\n")

    for row in created + updated:
        suffix = ""
        if row.get("extracted_urls"):
            suffix = f" ({len(row['extracted_urls'])} page links)"
        print(f"- `{row['slug']}` — {row.get('recommendation', 'watch')} — {row.get('name')}{suffix}")

    if args.dry_run:
        print("\n[dry-run] no files written")
        return 0

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with GMAIL_SELF_SENT_LINKS_PATH.open("w") as f:
        for slug in sorted(rows):
            f.write(json.dumps(rows[slug], ensure_ascii=False) + "\n")
    print(f"\n[saved] {GMAIL_SELF_SENT_LINKS_PATH}")
    return 0


def _tokenize(text: str) -> set[str]:
    """Lowercase word tokens, drop short noise."""
    return {w for w in re.findall(r"[a-z][a-z0-9-]{3,}", (text or "").lower())
            if w not in {"skill", "claude", "code", "this", "that", "with", "from", "into",
                         "have", "uses", "when", "what", "which", "where", "your", "matt"}}


def _extract_skill_md_text(skill_dir: Path) -> str:
    """Pull comparable text from an installed skill (SKILL.md + README + sub-docs)."""
    parts: list[str] = []
    for name in ("SKILL.md", "README.md", "Readme.md", "readme.md"):
        f = skill_dir / name
        if f.exists():
            try:
                parts.append(f.read_text(errors="replace")[:5000])
            except OSError:
                pass
    # Also pull descriptions from common metadata files
    for name in ("plugin.json", ".claude-plugin/plugin.json", "config.json"):
        f = skill_dir / name
        if f.exists():
            try:
                d = json.loads(f.read_text())
                parts.append(d.get("description", ""))
                parts.extend(d.get("keywords", []) or [])
            except (OSError, json.JSONDecodeError):
                pass
    return "\n".join(parts)


def _candidate_summary(slug: str, seen: dict) -> str:
    """Build a comparable text blob for a scouted candidate."""
    rec = seen.get(slug, {})
    parts = [rec.get("name", ""), rec.get("description", "")]
    local = rec.get("local_path")
    if local:
        path = Path(local)
        # Pull descriptions from plugin.json + any README
        pj = path / ".claude-plugin" / "plugin.json"
        if pj.exists():
            try:
                d = json.loads(pj.read_text())
                parts.append(d.get("description", ""))
                parts.extend(d.get("keywords", []) or [])
            except (OSError, json.JSONDecodeError):
                pass
        for readme_name in ("README.md", "Readme.md", "readme.md"):
            rd = path / readme_name
            if rd.exists():
                try:
                    parts.append(rd.read_text(errors="replace")[:5000])
                except OSError:
                    pass
                break
    return "\n".join(parts)


def _candidate_from_seen(slug: str, seen: Optional[dict] = None) -> Optional[dict]:
    seen = seen or load_seen()
    rec = seen.get(slug)
    if rec:
        return rec

    # `seen.jsonl` only captures candidates after poll. For freshly ingested
    # Gmail rows, allow planning directly from the curated source.
    for cand in candidates_from_gmail_self_sent_links():
        if cand.get("slug") == slug:
            installed = installed_skill_names()
            cand.update(score_candidate(cand, installed))
            return cand
    return None


def _build_idf(installed_dir: Path) -> dict[str, float]:
    """Compute IDF (inverse document frequency) for every token across all
    installed SKILL.md+README corpora. Tokens that appear in MANY skills
    (generic boilerplate like 'description', 'session', 'changes') get a
    low IDF — they don't discriminate. Tokens that appear in FEW skills
    (domain-specific like 'webhook', 'kubernetes', 'figma') get a high IDF.
    """
    import math
    doc_freq: dict[str, int] = {}
    n_docs = 0
    if not installed_dir.exists():
        return {}
    for sd in installed_dir.iterdir():
        if not sd.is_dir():
            continue
        text = _extract_skill_md_text(sd)
        if not text:
            continue
        n_docs += 1
        toks = _tokenize(text)
        for t in toks:
            doc_freq[t] = doc_freq.get(t, 0) + 1
    if n_docs == 0:
        return {}
    # IDF = log((N+1) / (df+1)) + 1  — smoothed
    return {t: math.log((n_docs + 1) / (df + 1)) + 1 for t, df in doc_freq.items()}


def _overlap_analysis(slug: str, seen: Optional[dict] = None) -> dict:
    seen = seen or load_seen()
    cand = _candidate_from_seen(slug, seen)
    if cand and slug not in seen:
        seen = {**seen, slug: cand}

    cand_text = _candidate_summary(slug, seen)
    if not cand_text.strip() and cand:
        cand_text = "\n".join([cand.get("name", ""), cand.get("description", "")])
    if not cand_text.strip():
        cand_text = slug
    cand_tokens = _tokenize(cand_text)
    if not cand_tokens:
        return {"status": "no_tokens", "scores": [], "recommendation": "UNKNOWN", "best": None}

    if not INSTALLED_SKILLS_DIR.exists():
        return {"status": "no_installed_skills", "scores": [], "recommendation": "STANDALONE", "best": None}

    idf = _build_idf(INSTALLED_SKILLS_DIR)
    # Domain-specific token = appears in ≤3 skills (high IDF). Threshold derived
    # from a corpus of ~110 skills.
    DOMAIN_IDF_THRESHOLD = 3.5

    scores: list[dict] = []
    for skill_dir in INSTALLED_SKILLS_DIR.iterdir():
        if not skill_dir.is_dir() or skill_dir.name == slug.split(":")[-1]:
            continue
        skill_text = _extract_skill_md_text(skill_dir)
        if not skill_text:
            continue
        skill_tokens = _tokenize(skill_text)
        if not skill_tokens:
            continue
        intersection = cand_tokens & skill_tokens
        union = cand_tokens | skill_tokens
        if not intersection or not union:
            continue
        jaccard = len(intersection) / len(union)
        # Weighted Jaccard: sum(IDF of intersection) / sum(IDF of union)
        # Normalizes for document size — a small candidate sharing 5 rare
        # tokens with a huge installed skill no longer dominates.
        idf_inter = sum(idf.get(t, 1.0) for t in intersection)
        idf_union = sum(idf.get(t, 1.0) for t in union)
        weighted_jaccard = idf_inter / idf_union if idf_union > 0 else 0.0
        domain_kws = [t for t in intersection if idf.get(t, 0) >= DOMAIN_IDF_THRESHOLD]
        domain_kws.sort(key=lambda t: -idf.get(t, 0))
        top_kw = domain_kws[:5] if domain_kws else sorted(intersection, key=lambda t: -idf.get(t, 1.0))[:5]
        scores.append({
            "name": skill_dir.name,
            "jaccard": jaccard,
            "weighted_jaccard": weighted_jaccard,
            "idf_inter": idf_inter,
            "n_domain": len(domain_kws),
            "kws": ", ".join(top_kw),
        })

    scores.sort(key=lambda s: -s["weighted_jaccard"])
    top = scores[:5]
    if not top:
        return {"status": "ok", "scores": [], "recommendation": "STANDALONE", "best": None}

    best = top[0]
    # Weighted Jaccard is normalized 0-1. Thresholds tuned empirically:
    #   ≥0.20  — high shared domain content (BLEND)
    #   ≥0.08  — partial overlap (SIBLING)
    #   <0.08  — STANDALONE
    # Domain-kw count is a secondary signal — only promotes if multiple rare tokens match.
    recommendation = "STANDALONE"
    if best["weighted_jaccard"] >= 0.20 and best["n_domain"] >= 2:
        recommendation = "BLEND"
    elif best["weighted_jaccard"] >= 0.08 and best["n_domain"] >= 1:
        recommendation = "SIBLING"
    elif best["n_domain"] >= 4:
        # Override: many rare tokens shared even if normalized score is low
        recommendation = "SIBLING"

    return {"status": "ok", "scores": top, "recommendation": recommendation, "best": best}


def cmd_overlap(args) -> int:
    """Compare a scouted candidate against installed skills via TF-IDF weighted overlap.

    For each installed skill, compute IDF-weighted token overlap between
    candidate and skill. Tokens shared by many skills count for less; rare
    domain-specific tokens count for more.
    """
    analysis = _overlap_analysis(args.slug)

    print(f"# Overlap analysis · `{args.slug}`\n")
    print(f"_Comparing via TF-IDF across {len(analysis['scores'])} installed skills._\n")

    if analysis["status"] == "no_tokens":
        print(f"no usable tokens for {args.slug}")
        return 1

    if not analysis["scores"]:
        print("🆕 **STANDALONE** — no installed skill has measurable overlap. Install fresh.")
        return 0

    print("| Installed skill | Wtd-J | Jaccard | Domain kw | Top shared (rarest first) |")
    print("|---|---|---|---|---|")
    for s in analysis["scores"]:
        print(f"| `{s['name']}` | {s['weighted_jaccard']:.2f} | {s['jaccard']:.2f} | {s['n_domain']} | {s['kws']} |")

    recommendation = analysis["recommendation"]
    best = analysis["best"]
    print()
    if recommendation == "BLEND":
        print(f"🔀 **Recommendation: BLEND with `{best['name']}`** — weighted-Jaccard {best['weighted_jaccard']:.2f}, {best['n_domain']} domain kw.")
        print(f"   Action: read both READMEs side by side. Cherry-pick the techniques `{args.slug}`")
        print(f"   does better (rarest shared: {best['kws']}) and fold into `{best['name']}/SKILL.md`.")
        print(f"   Do NOT install `{args.slug}` as a separate skill.")
    elif recommendation == "SIBLING":
        print(f"🧩 **Recommendation: SIBLING of `{best['name']}`** — related but distinct (weighted-Jaccard {best['weighted_jaccard']:.2f}, {best['n_domain']} domain kw).")
        print(f"   Action: install `{args.slug}` as a separate skill. Add cross-reference in both SKILL.md.")
    else:
        print(f"🆕 **Recommendation: STANDALONE** — closest match `{best['name']}` weighted-Jaccard {best['weighted_jaccard']:.2f}, {best['n_domain']} domain kw.")
        print(f"   Action: install fresh.")
    return 0


def _github_repo_from_url(url: str) -> Optional[str]:
    parsed = urlparse(url or "")
    if parsed.netloc.lower() != "github.com":
        return None
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2:
        return None
    owner, repo = parts[0], parts[1].removesuffix(".git")
    if owner and repo:
        return f"{owner}/{repo}"
    return None


def _candidate_repo(cand: dict) -> Optional[str]:
    if cand.get("slug", "").startswith("repo:"):
        return cand["slug"].split(":", 1)[1]
    for url in [cand.get("url"), cand.get("original_url"), *(cand.get("resolved_urls") or [])]:
        repo = _github_repo_from_url(url or "")
        if repo:
            return repo
    return None


def _target_skill_name(cand: dict) -> str:
    repo = _candidate_repo(cand)
    if repo:
        return _slugify_name(repo.split("/", 1)[1])
    return _slugify_name(cand.get("name") or cand.get("slug", "").split(":", 1)[-1])


def _local_candidate_files(cand: dict, limit: int = 20) -> list[str]:
    local = cand.get("local_path")
    if not local:
        return []
    root = Path(local)
    if not root.exists():
        return []
    files: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = str(path.relative_to(root))
        if rel.startswith(("node_modules/", ".git/")):
            continue
        files.append(rel)
        if len(files) >= limit:
            break
    return files


def _read_enabled_plugin_names() -> set[str]:
    settings = Path.home() / ".claude" / "settings.json"
    if not settings.exists():
        return set()
    try:
        text = settings.read_text(errors="replace")
    except OSError:
        return set()
    names = set(re.findall(r"claude-plugins-official[:/@]([a-zA-Z0-9_.-]+)|([a-zA-Z0-9_.-]+)@claude-plugins-official", text))
    return {a or b for a, b in names if a or b}


def _install_plan(cand: dict) -> dict:
    slug = cand["slug"]
    source = cand.get("source", "")
    repo = _candidate_repo(cand)
    target_name = _target_skill_name(cand)
    overlap = _overlap_analysis(slug)
    rec = (cand.get("recommendation") or "").lower()
    warnings: list[str] = []
    files: list[str] = []
    conflicts: list[str] = []
    commands: list[str] = []
    action = "review-only"
    target_path = ""

    if cand.get("decision") == "watch" or rec in {"watch", "on-demand-only", "canonical-reference"} or rec.startswith("defer"):
        warnings.append(f"candidate is currently `{cand.get('decision', 'unknown')}` / `{cand.get('recommendation', 'unknown')}`; do not install without a fresh human decision")
    if cand.get("requires_secret"):
        warnings.append("requires a secret/API key; installation must not prompt for inline secret entry")
    if cand.get("opaque_source"):
        warnings.append("source is opaque; inspect the original linked content before accepting")

    if rec == "rebuild-pattern":
        action = "mine-pattern"
        files.append("No third-party files should be copied automatically")
        files.append("Expected output is a Zerg-owned skill/doc/code patch based on the useful pattern")
    elif rec in {"watch", "on-demand-only", "canonical-reference"} or rec.startswith("defer"):
        action = "review-only"
        files.append("No files should be copied for this curated verdict")
        if repo:
            files.append(f"Reference repo only: https://github.com/{repo}")
    elif slug == "gmail-link:chrome-devtools-mcp":
        action = "enable-plugin"
        commands.append("/plugin enable chrome-devtools-mcp@claude-plugins-official")
        files.append("Claude plugin registry/settings: enables plugin entry")
        conflicts.append("Chrome DevTools MCP may already be enabled; verify with `claude mcp list`")
    elif slug.startswith("plugin:"):
        plugin = slug.split(":", 1)[1]
        action = "enable-plugin"
        commands.append(f"/plugin enable {plugin}@claude-plugins-official")
        files.append("Claude plugin registry/settings: enables plugin entry")
        local = cand.get("local_path")
        if local:
            files.append(f"Reads cached plugin files from {local}")
            files.extend(f"  - {rel}" for rel in _local_candidate_files(cand, limit=12))
        if plugin in _read_enabled_plugin_names():
            conflicts.append(f"`{plugin}` appears to already be enabled in Claude settings")
    elif repo:
        action = "clone-skill"
        target_path = str(INSTALLED_SKILLS_DIR / target_name)
        commands.append(f"git clone https://github.com/{repo}.git {target_path}")
        files.append(f"Would create directory: {target_path}")
        if Path(target_path).exists():
            conflicts.append(f"target directory already exists: {target_path}")
    elif source == "gmail-self-sent-links":
        action = "mine-pattern"
        files.append("No automatic file copy inferred from this Gmail candidate")
        if rec == "rebuild-pattern":
            files.append("Expected output is a Zerg-owned skill/doc patch, not third-party install")
    else:
        files.append("No install target inferred")

    best = overlap.get("best")
    if overlap.get("recommendation") == "BLEND" and best:
        conflicts.append(f"overlap recommends BLEND with `{best['name']}` instead of standalone install")
    elif overlap.get("recommendation") == "SIBLING" and best:
        conflicts.append(f"related installed skill: `{best['name']}`; add cross-references if accepted")

    return {
        "slug": slug,
        "name": cand.get("name") or slug,
        "source": source,
        "score": cand.get("total"),
        "decision": cand.get("decision"),
        "action": action,
        "target_path": target_path,
        "commands": commands,
        "files": files,
        "warnings": warnings,
        "conflicts": conflicts,
        "overlap": overlap,
    }


def _render_install_plan(plan: dict) -> None:
    print(f"# install plan · `{plan['slug']}`\n")
    print(f"Name: {plan['name']}")
    print(f"Source: {plan['source']}")
    print(f"Current decision: {plan.get('decision')}")
    if plan.get("score") is not None:
        print(f"Score: {plan['score']}/10")
    print(f"Action: {plan['action']}")

    print("\n## Files / State")
    for item in plan["files"] or ["No file or state changes inferred."]:
        print(f"- {item}")

    print("\n## Conflicts")
    for item in plan["conflicts"] or ["No direct conflicts found."]:
        print(f"- {item}")

    overlap = plan["overlap"]
    print("\n## Overlap")
    print(f"Recommendation: {overlap.get('recommendation')}")
    for row in overlap.get("scores", [])[:3]:
        print(f"- `{row['name']}` — Wtd-J {row['weighted_jaccard']:.2f}, domain kw {row['n_domain']}: {row['kws']}")

    print("\n## Manual Command")
    if plan["commands"]:
        for command in plan["commands"]:
            print(f"- `{command}`")
    else:
        print("- No install command. Mine/rebuild the pattern manually.")

    if plan["warnings"]:
        print("\n## Warnings")
        for item in plan["warnings"]:
            print(f"- {item}")


def cmd_review(args) -> int:
    seen = load_seen()
    if args.slug not in seen:
        print(f"slug not in seen: {args.slug}", file=sys.stderr)
        return 1
    r = seen[args.slug]
    print(f"# {args.slug}")
    print(f"\nSource: {r.get('source')}")
    print(f"Score: {r.get('total')}/10 (value={r.get('value')}, safety={r.get('safety')})")
    print(f"URL: {r.get('url')}")
    if r.get("original_url") and r.get("original_url") != r.get("url"):
        print(f"Original URL: {r.get('original_url')}")
    if r.get("resolved_urls"):
        print("\nResolved URLs:")
        for url in r.get("resolved_urls", []):
            print(f"- {url}")
    if r.get("message_ids"):
        print(f"\nSource email IDs: {', '.join(r.get('message_ids', []))}")
    print(f"\nRationale:")
    for rs in r.get("rationale", []):
        print(f"- {rs}")
    if r.get("local_path"):
        path = Path(r["local_path"])
        skill_md = path / ".claude-plugin" / "plugin.json"
        if skill_md.exists():
            print(f"\nPlugin manifest:\n```\n{skill_md.read_text()[:800]}\n```")
    return 0


def cmd_accept(args) -> int:
    seen = load_seen()
    cand = _candidate_from_seen(args.slug, seen)
    if not cand:
        print(f"slug not in seen: {args.slug}", file=sys.stderr)
        return 1

    plan = _install_plan(cand)
    _render_install_plan(plan)

    if not args.confirm:
        print("\n[preview-only] no state changed. Re-run with `--confirm` to mark accepted after reviewing this plan.")
        return 0

    accepted = {
        **cand,
        "decision": "accepted",
        "ts": dt.datetime.now(PT).isoformat(),
        "note": args.note or "",
        "install_plan": {
            "action": plan["action"],
            "target_path": plan["target_path"],
            "commands": plan["commands"],
            "conflicts": plan["conflicts"],
            "warnings": plan["warnings"],
            "overlap_recommendation": plan["overlap"].get("recommendation"),
        },
    }
    append_seen(accepted)
    print(f"\nMarked accepted: {args.slug}")
    return 0


def cmd_plan(args) -> int:
    cand = _candidate_from_seen(args.slug)
    if not cand:
        print(f"slug not in seen: {args.slug}", file=sys.stderr)
        return 1
    _render_install_plan(_install_plan(cand))
    return 0


def cmd_reject(args) -> int:
    append_seen({"slug": args.slug, "decision": "rejected",
                 "reason": args.reason, "ts": dt.datetime.now(PT).isoformat()})
    print(f"Marked rejected: {args.slug} — {args.reason}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_poll = sub.add_parser("poll", help="Scan sources, score new candidates")
    p_poll.add_argument("--post", action="store_true", help="DM promoted candidates to FM channel")
    p_poll.add_argument("--vault", action="store_true", help="Append to weekly vault dossier")
    p_poll.add_argument("--no-repos", action="store_true", help="Skip known-repo polling")
    p_poll.add_argument("--no-gmail-links", action="store_true", help="Skip curated self-sent Gmail link candidates")
    p_poll.add_argument("--rescore", action="store_true", help="Re-score already-seen candidates")
    p_poll.set_defaults(func=cmd_poll)
    p_state = sub.add_parser("state", help="Show counts by decision")
    p_state.set_defaults(func=cmd_state)
    p_ingest = sub.add_parser("ingest-gmail-links", help="Ingest self-sent Gmail tool links into the curated candidate source")
    p_ingest.add_argument("--to", default="matthew@zergai.com", help="Recipient address used for self-sent tool links")
    p_ingest.add_argument("--days", type=int, default=30, help="How far back to scan sent mail")
    p_ingest.add_argument("--max-results", type=int, default=25, help="Maximum matching messages to scan")
    p_ingest.add_argument("--account", help="Gmail account to search")
    p_ingest.add_argument("--query", help="Override Gmail search query")
    p_ingest.add_argument("--fetch-pages", action=argparse.BooleanOptionalAction, default=True, help="Fetch non-social linked pages and extract additional links")
    p_ingest.add_argument("--max-pages", type=int, default=3, help="Maximum original URLs per email to fetch")
    p_ingest.add_argument("--max-page-links", type=int, default=30, help="Maximum extracted links to keep per fetched page")
    p_ingest.add_argument("--dry-run", action="store_true", help="Print candidates without writing JSONL")
    p_ingest.set_defaults(func=cmd_ingest_gmail_links)
    p_review = sub.add_parser("review", help="Deep-evaluate a candidate")
    p_review.add_argument("slug")
    p_review.set_defaults(func=cmd_review)
    p_plan = sub.add_parser("plan", help="Preview install/conflict plan for a candidate")
    p_plan.add_argument("slug")
    p_plan.set_defaults(func=cmd_plan)
    p_accept = sub.add_parser("accept", help="Preview install plan; with --confirm, mark accepted (does NOT install)")
    p_accept.add_argument("slug")
    p_accept.add_argument("--note", default="")
    p_accept.add_argument("--confirm", action="store_true", help="After showing the plan, append an accepted decision to state")
    p_accept.set_defaults(func=cmd_accept)
    p_reject = sub.add_parser("reject", help="Mark candidate rejected with reason")
    p_reject.add_argument("slug")
    p_reject.add_argument("reason")
    p_reject.set_defaults(func=cmd_reject)
    p_overlap = sub.add_parser("overlap", help="Recommend BLEND / SIBLING / STANDALONE for a candidate")
    p_overlap.add_argument("slug")
    p_overlap.set_defaults(func=cmd_overlap)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
