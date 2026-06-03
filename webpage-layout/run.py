#!/usr/bin/env python3
"""webpage-layout — empirical site grader + auditor + AI-friendly bootstrapper.

Scrapes a corpus of reference URLs, grades each on a 6-axis rubric using Claude
vision, and uses sites scoring 8+ as exemplars. Audit a target URL against the
same rubric to produce severity-tagged findings + concrete fix recipes drawn
from top-scoring exemplars.

Bootstrap mode scaffolds a new public site with the AI-friendly stack day-zero:
llms.txt, llms-full.txt, index.md, robots.txt with AI-bot allowlist, sitemap.xml,
JSON-LD structured data, alternate-link tags, and a single-font accessible CSS
starter.

Usage:
  python3 run.py learn [--force]
  python3 run.py audit URL [--persona personal|fund|advisory|brand_product]
  python3 run.py status
  python3 run.py bootstrap --slug SLUG --domain DOMAIN [--spec spec.json]
"""
import argparse
import base64
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import datetime
import httpx
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
CORPUS = SKILL_DIR / "corpus" / "references.json"
STATE = SKILL_DIR / "state"
SITES = STATE / "sites"
LEARNED = STATE / "learned"
AUDITS = STATE / "audits"
PLAYWRIGHT = Path.home() / ".claude/skills/playwright-skill/playwright_skill.py"
ANTHROPIC_HELPER = Path.home() / ".config/zerg/anthropic_client.py"

RUBRIC_AXES = [
    ("typography", "Typographic identity — does the type system have character + discipline, or is it the AI Inter+Fraunces stencil?"),
    ("hierarchy", "Hierarchical clarity — does one thing dominate per screen? Are headlines doing the visual work?"),
    ("distinctiveness", "Distinctiveness — could you swap the words for a different person/firm and have it still work? If yes, low score."),
    ("color", "Color discipline — restrained palette? Accent ≤5%? Or busy/decorative?"),
    ("density", "Density and whitespace balance — confident content density? Or generic uniform padding?"),
    ("voice", "Voice/structure fit — does the IA reflect the actual story? Or stencil 'Currently / Selected / Testimonials / CTA'?"),
]


def slugify(url: str) -> str:
    s = re.sub(r"^https?://", "", url).rstrip("/")
    s = re.sub(r"[^a-z0-9.-]+", "-", s.lower())
    return s[:80]


def screenshot(url: str, output_path: Path, viewport: str = "desktop") -> bool:
    """Capture a full-page screenshot via Chrome headless (faster + no browser-spawn overhead).

    Uses Chrome headless directly — `playwright-skill` was hanging on cold-start sites and
    spawning a new Chromium per call. Chrome headless via the system Chrome binary is ~3x
    faster and has a true wall-clock timeout we can enforce.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if not Path(chrome).exists():
        chrome = "/Applications/Chromium.app/Contents/MacOS/Chromium"
    if not Path(chrome).exists():
        # fallback to playwright-skill
        cmd = ["python3", str(PLAYWRIGHT), "screenshot", url, "--output", str(output_path), "--full-page"]
    else:
        cmd = [
            chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--no-sandbox", "--virtual-time-budget=8000",
            "--window-size=1280,1800",
            f"--screenshot={output_path}", url,
        ]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=45, text=True)
        ok = output_path.exists() and output_path.stat().st_size > 1024
        if not ok:
            print(f"  screenshot failed for {url}: rc={r.returncode} stderr={r.stderr[:200]}", file=sys.stderr)
        return ok
    except subprocess.TimeoutExpired:
        print(f"  screenshot timeout for {url}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"  screenshot error for {url}: {e}", file=sys.stderr)
        return False


def fetch_html(url: str, output_path: Path) -> bool:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = subprocess.run(
            ["curl", "-sLA", "Mozilla/5.0 (compatible; webpage-layout/1.0)", "--max-time", "30", url],
            capture_output=True, timeout=40, text=True,
        )
        if r.returncode == 0 and len(r.stdout) > 100:
            output_path.write_text(r.stdout)
            return True
    except Exception as e:
        print(f"  html fetch error for {url}: {e}", file=sys.stderr)
    return False


def get_anthropic_client():
    """Load Anthropic client. Prefers Max-plan OAuth (no API credit), falls
    back to API key only if OAuth path fails."""
    # Max-plan OAuth path (preferred — no API credit charged):
    sys.path.insert(0, str(Path(__file__).parent / "_lib"))
    try:
        import max_client  # type: ignore
        return max_client.make_client(source="webpage-layout/audit")
    except Exception as e:
        print(f"  max_client unavailable ({e}); falling back to API key", file=sys.stderr)
    # API-key fallback (charges API credit; only used if OAuth path failed):
    sys.path.insert(0, str(ANTHROPIC_HELPER.parent))
    try:
        import anthropic_client
        return anthropic_client.make_client()
    except Exception:
        import anthropic, os
        key_file = ANTHROPIC_HELPER.parent / "anthropic_key.txt"
        if key_file.exists():
            os.environ["ANTHROPIC_API_KEY"] = key_file.read_text().strip()
        return anthropic.Anthropic()


_GRADING_FALLBACK_MODEL = "claude-sonnet-4-5"
_AITR_SCRIPTS = Path.home() / ".claude" / "skills" / "aitr" / "scripts"
_grading_model_cache = None


def _grading_model() -> str:
    """Vision-grading model via aitr (prose-review + vision required, medium floor);
    loud fallback to the previous hardcoded Sonnet. Memoized — audit loops grading
    many sites route once."""
    global _grading_model_cache
    if _grading_model_cache is None:
        if str(_AITR_SCRIPTS) not in sys.path:
            sys.path.insert(0, str(_AITR_SCRIPTS))
        try:
            from skill_default import aitr_model_or
            _grading_model_cache = aitr_model_or(
                _GRADING_FALLBACK_MODEL,
                task_kind="prose-review",
                caller="webpage-layout",
                quality_floor="medium",
                modality_required="vision",
            )
        except ImportError:
            _grading_model_cache = _GRADING_FALLBACK_MODEL
    return _grading_model_cache


def grade_with_vision(client, url: str, screenshot_path: Path, html_excerpt: str, persona: str) -> dict:
    """Use Claude vision to grade a site on the 6-axis rubric."""
    img_b64 = base64.standard_b64encode(screenshot_path.read_bytes()).decode()

    rubric_lines = "\n".join(f"- **{name}**: {desc}" for name, desc in RUBRIC_AXES)

    sys_prompt = f"""You are a senior web design critic. Grade websites on a 6-axis rubric (1-10 scale, 10=best). Be calibrated and harsh — a 10 is rare.

Rubric:
{rubric_lines}

Output strict JSON only with this shape:
{{
  "scores": {{"typography": int, "hierarchy": int, "distinctiveness": int, "color": int, "density": int, "voice": int}},
  "reasoning": {{"typography": "1-line explanation", "hierarchy": "...", "distinctiveness": "...", "color": "...", "density": "...", "voice": "..."}},
  "winning_patterns": ["short bullet of what this site does well", ...],
  "anti_patterns": ["short bullet of what's stencil/generic/wrong", ...],
  "one_word_personality": "single distinctive word describing the site's personality (or 'generic' if it has none)"
}}"""

    user_prompt = f"""URL: {url}
Persona class: {persona}

HTML excerpt (head + first 3K of body):
```
{html_excerpt[:3500]}
```

Screenshot is attached. Grade the site."""

    # Shared 429-aware retry with exponential backoff + jitter. Skip-mode
    # (ANTHROPIC_429_SKIP_MODE=1) returns a sentinel marker after exhausted
    # retries rather than crashing the whole audit/learn loop. See
    # ~/.config/zerg/anthropic_retry.py and feedback_429_skill_hardening.md.
    sys.path.insert(0, str(Path.home() / ".config" / "zerg"))
    from anthropic_retry import call_with_429_retry, is_429_skip_sentinel, SKIP_MARKER_TEXT

    def _do_call():
        return client.messages.create(
            model=_grading_model(),
            max_tokens=2000,
            system=sys_prompt,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_b64}},
                    {"type": "text", "text": user_prompt},
                ],
            }],
        )

    try:
        msg = call_with_429_retry(_do_call, source="webpage-layout/grade", max_attempts=4)
    except Exception as e:
        return {"error": str(e)[:500]}

    if is_429_skip_sentinel(msg):
        # Skip-mode partial: return a structurally valid grade dict shape
        # with the SKIP marker so cmd_audit/cmd_learn/cmd_monitor can keep
        # iterating across remaining sites instead of crashing the run.
        return {
            "error": SKIP_MARKER_TEXT.format(attempts=msg.get("_attempts", 4)),
            "_429_skipped": True,
            "_attempts": msg.get("_attempts", 4),
        }

    try:
        text = msg.content[0].text
        m = re.search(r"\{[\s\S]+\}", text)
        if m:
            return json.loads(m.group(0))
        return {"error": "no_json_found", "raw": text[:500]}
    except Exception as e:
        return {"error": str(e)[:500]}


def cmd_learn(args):
    refs = json.loads(CORPUS.read_text())
    client = get_anthropic_client()
    total = sum(len(v["urls"]) for v in refs.values())
    done = 0
    print(f"# learn: {total} sites across {len(refs)} persona classes")

    for persona, group in refs.items():
        for entry in group["urls"]:
            url = entry["url"]
            slug = slugify(url)
            site_dir = SITES / persona / slug
            grade_path = site_dir / "grade.json"
            done += 1

            if grade_path.exists() and not args.force:
                print(f"[{done}/{total}] skip {url} (already graded)")
                continue

            print(f"[{done}/{total}] {url}")
            shot = site_dir / "desktop.png"
            html_path = site_dir / "page.html"

            ok_shot = screenshot(url, shot)
            ok_html = fetch_html(url, html_path)
            if not ok_shot:
                print(f"  -> screenshot failed, skipping")
                continue

            html = html_path.read_text()[:6000] if ok_html else ""
            grade = grade_with_vision(client, url, shot, html, persona)
            grade["_url"] = url
            grade["_persona"] = persona
            grade["_note"] = entry.get("note", "")
            grade["_graded_at"] = datetime.utcnow().isoformat() + "Z"
            site_dir.mkdir(parents=True, exist_ok=True)
            grade_path.write_text(json.dumps(grade, indent=2))

            if "error" in grade:
                print(f"  -> grade error: {grade['error']}")
            else:
                avg = sum(grade["scores"].values()) / 6
                print(f"  -> avg {avg:.1f}/10  personality: {grade.get('one_word_personality','?')}")
            time.sleep(2)

    build_learned()
    print(f"# done. Patterns written to {LEARNED / 'patterns.md'}")


def build_learned():
    """Aggregate winning patterns from sites scoring avg ≥7.5 by persona."""
    LEARNED.mkdir(parents=True, exist_ok=True)
    out = ["# Learned patterns (per persona)\n",
           f"_Built {datetime.utcnow().isoformat()}Z from corpus grades._\n"]

    for persona_dir in sorted(SITES.iterdir()):
        if not persona_dir.is_dir():
            continue
        persona = persona_dir.name
        out.append(f"\n## {persona}\n")
        ranked = []
        for site_dir in persona_dir.iterdir():
            gp = site_dir / "grade.json"
            if not gp.exists():
                continue
            g = json.loads(gp.read_text())
            if "scores" not in g:
                continue
            avg = sum(g["scores"].values()) / 6
            ranked.append((avg, g))
        ranked.sort(key=lambda x: -x[0])

        out.append("\n### Ranking\n")
        for avg, g in ranked:
            out.append(f"- **{avg:.1f}** — {g['_url']} — _{g.get('one_word_personality','?')}_")

        # Aggregate winning patterns from top 50%
        cutoff = max(7.0, ranked[len(ranked) // 2][0]) if ranked else 7.0
        winning = []
        for avg, g in ranked:
            if avg >= cutoff:
                for p in g.get("winning_patterns", []):
                    winning.append((avg, g["_url"], p))

        out.append(f"\n### Winning patterns (sites avg ≥ {cutoff:.1f})\n")
        for avg, url, p in winning:
            out.append(f"- {p}  _({url}, {avg:.1f})_")

        # Aggregate anti-patterns from bottom 50%
        bot_cutoff = ranked[len(ranked) // 2][0] if ranked else 7.0
        anti = []
        for avg, g in ranked:
            if avg <= bot_cutoff:
                for p in g.get("anti_patterns", []):
                    anti.append((avg, g["_url"], p))
        if anti:
            out.append(f"\n### Anti-patterns (sites avg ≤ {bot_cutoff:.1f})\n")
            for avg, url, p in anti:
                out.append(f"- {p}  _({url}, {avg:.1f})_")

    (LEARNED / "patterns.md").write_text("\n".join(out))


def cmd_audit(args):
    url = args.url
    persona = args.persona or "personal"
    AUDITS.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    host = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
    out_path = AUDITS / f"{slugify(host)}-{ts}.md"

    audit_dir = AUDITS / "captures" / slugify(host)
    audit_dir.mkdir(parents=True, exist_ok=True)
    shot = audit_dir / f"{ts}.png"
    html = audit_dir / f"{ts}.html"

    print(f"# auditing {url} as persona={persona}")
    if not screenshot(url, shot):
        print("screenshot failed", file=sys.stderr)
        sys.exit(1)
    fetch_html(url, html)

    client = get_anthropic_client()
    html_excerpt = html.read_text()[:6000] if html.exists() else ""
    grade = grade_with_vision(client, url, shot, html_excerpt, persona)
    if "error" in grade:
        print(f"grade error: {grade['error']}", file=sys.stderr)
        sys.exit(2)

    # Compare against top exemplars in the same persona class
    top_exemplars = []
    persona_dir = SITES / persona
    if persona_dir.exists():
        all_grades = []
        for site_dir in persona_dir.iterdir():
            gp = site_dir / "grade.json"
            if gp.exists():
                g = json.loads(gp.read_text())
                if "scores" in g:
                    all_grades.append((sum(g["scores"].values()) / 6, g))
        all_grades.sort(key=lambda x: -x[0])
        top_exemplars = all_grades[:3]

    avg = sum(grade["scores"].values()) / 6
    verdict = "FAIL" if any(s < 6 for s in grade["scores"].values()) else (
        "WARN" if avg < 7 else "PASS"
    )

    md = [f"# webpage-layout audit — {host}", ""]
    md.append(f"**Verdict**: `{verdict}`  ·  **Avg score**: `{avg:.1f}/10`")
    md.append(f"**Target**: {url}")
    md.append(f"**Persona class**: {persona}")
    md.append(f"**Generated**: {datetime.utcnow().isoformat()}Z")
    md.append(f"**Personality**: _{grade.get('one_word_personality','?')}_")
    md.append("")
    md.append("## Per-axis grades\n")
    md.append("| Axis | Score | Reasoning |")
    md.append("|---|---|---|")
    for axis, _ in RUBRIC_AXES:
        s = grade["scores"].get(axis, 0)
        r = grade["reasoning"].get(axis, "")
        md.append(f"| {axis} | **{s}/10** | {r} |")

    md.append("\n## Findings\n")
    findings = []
    for axis, desc in RUBRIC_AXES:
        s = grade["scores"].get(axis, 0)
        r = grade["reasoning"].get(axis, "")
        if s <= 4:
            findings.append(("HIGH", axis, s, r))
        elif s <= 6:
            findings.append(("MEDIUM", axis, s, r))
        elif s <= 7:
            findings.append(("LOW", axis, s, r))
    if findings:
        md.append("| Severity | Axis | Score | Issue |")
        md.append("|---|---|---|---|")
        for sev, axis, s, r in findings:
            md.append(f"| **{sev}** | {axis} | {s}/10 | {r} |")
    else:
        md.append("_No findings — all axes ≥ 8._")

    md.append("\n## Anti-patterns observed\n")
    for ap in grade.get("anti_patterns", []) or ["_(none flagged)_"]:
        md.append(f"- {ap}")

    md.append("\n## What this site does well\n")
    for wp in grade.get("winning_patterns", []) or ["_(none flagged)_"]:
        md.append(f"- {wp}")

    if top_exemplars:
        md.append(f"\n## Top exemplars in `{persona}` class (for reference)\n")
        for ex_avg, ex_g in top_exemplars:
            md.append(f"### {ex_g['_url']} ({ex_avg:.1f}/10)\n")
            md.append(f"_Personality_: {ex_g.get('one_word_personality','?')}\n")
            md.append("**What they do well:**")
            for wp in ex_g.get("winning_patterns", [])[:5]:
                md.append(f"- {wp}")
            md.append("")
    else:
        md.append(f"\n_No exemplars in `{persona}` class yet — run `learn` to populate the corpus._\n")

    out_path.write_text("\n".join(md))
    print(json.dumps({
        "ok": True,
        "verdict": verdict,
        "avg": round(avg, 2),
        "scores": grade["scores"],
        "audit": str(out_path),
    }, indent=2))


def cmd_status():
    refs = json.loads(CORPUS.read_text())
    print("# webpage-layout corpus status\n")
    for persona, group in refs.items():
        graded = 0
        scores = []
        for entry in group["urls"]:
            slug = slugify(entry["url"])
            gp = SITES / persona / slug / "grade.json"
            if gp.exists():
                g = json.loads(gp.read_text())
                if "scores" in g:
                    graded += 1
                    scores.append(sum(g["scores"].values()) / 6)
        avg = sum(scores) / len(scores) if scores else 0
        print(f"  {persona:20s}  {graded:2d}/{len(group['urls']):2d} graded  avg corpus score: {avg:.1f}/10")


MONITOR_DIR = STATE / "monitor"


def cmd_monitor(args):
    """Re-audit a tracked list of URLs, flag regressions vs prior baselines.

    State at state/monitor/:
      - tracked.json — {url, persona, baseline_avg, baseline_scores, last_audited}[]
      - reports/<YYYY-MM-DD>.md — per-run regression report
    """
    MONITOR_DIR.mkdir(parents=True, exist_ok=True)
    (MONITOR_DIR / "reports").mkdir(parents=True, exist_ok=True)
    tracked_path = MONITOR_DIR / "tracked.json"

    # Manage subcommands of monitor: track / list / run
    if args.action == "track":
        tracked = json.loads(tracked_path.read_text()) if tracked_path.exists() else []
        # de-dupe by url
        tracked = [t for t in tracked if t["url"] != args.url]
        tracked.append({
            "url": args.url,
            "persona": args.persona,
            "baseline_avg": None,
            "baseline_scores": None,
            "last_audited": None,
        })
        tracked_path.write_text(json.dumps(tracked, indent=2))
        print(json.dumps({"ok": True, "tracked": len(tracked), "added": args.url}))
        return

    if args.action == "list":
        tracked = json.loads(tracked_path.read_text()) if tracked_path.exists() else []
        print(json.dumps(tracked, indent=2))
        return

    # action == "run"
    tracked = json.loads(tracked_path.read_text()) if tracked_path.exists() else []
    if not tracked:
        print("No tracked URLs. Use: monitor track <url> --persona <persona>", file=sys.stderr)
        sys.exit(1)

    client = get_anthropic_client()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    report_path = MONITOR_DIR / "reports" / f"{today}.md"
    AUDITS.mkdir(parents=True, exist_ok=True)

    md = [f"# webpage-layout monitor — {today}", ""]
    md.append(f"**Tracking**: {len(tracked)} URLs")
    md.append("")
    md.append("| URL | Persona | Score | Δ vs baseline | Verdict |")
    md.append("|---|---|---|---|---|")

    regressions = []
    new_baselines = 0

    for entry in tracked:
        url = entry["url"]
        persona = entry["persona"]
        host = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
        ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        capture_dir = AUDITS / "captures" / slugify(host)
        capture_dir.mkdir(parents=True, exist_ok=True)
        shot = capture_dir / f"monitor-{ts}.png"
        html_path = capture_dir / f"monitor-{ts}.html"

        if not screenshot(url, shot):
            md.append(f"| {url} | {persona} | — | — | **SCREENSHOT FAILED** |")
            continue
        fetch_html(url, html_path)
        excerpt = html_path.read_text()[:6000] if html_path.exists() else ""
        grade = grade_with_vision(client, url, shot, excerpt, persona)
        if "error" in grade:
            md.append(f"| {url} | {persona} | — | — | **GRADE ERROR**: {grade['error'][:60]} |")
            continue

        avg = sum(grade["scores"].values()) / 6
        baseline_avg = entry.get("baseline_avg")
        baseline_scores = entry.get("baseline_scores") or {}

        verdict_pieces = []
        any_axis_below_6 = any(s < 6 for s in grade["scores"].values())
        if any_axis_below_6:
            verdict_pieces.append("⚠ axis<6")
        if baseline_avg is not None:
            delta = avg - baseline_avg
            delta_str = f"{delta:+.2f}"
            if delta <= -0.5:
                verdict_pieces.append("📉 REGRESSION")
                regressions.append((url, baseline_avg, avg, baseline_scores, grade["scores"]))
            elif delta >= 0.5:
                verdict_pieces.append("📈 lift")
        else:
            delta_str = "(baseline)"
            new_baselines += 1
            verdict_pieces.append("baseline set")

        verdict = " · ".join(verdict_pieces) if verdict_pieces else "OK"
        md.append(f"| {url} | {persona} | {avg:.1f} | {delta_str} | {verdict} |")

        # Update baseline only if first run, OR if score went UP (always track ceiling)
        if baseline_avg is None or avg > baseline_avg:
            entry["baseline_avg"] = avg
            entry["baseline_scores"] = grade["scores"]
        entry["last_audited"] = datetime.utcnow().isoformat() + "Z"
        entry["last_avg"] = avg
        entry["last_scores"] = grade["scores"]
        time.sleep(2)

    if regressions:
        md.append("\n## Regressions to investigate\n")
        for url, b_avg, c_avg, b_scores, c_scores in regressions:
            md.append(f"### {url}")
            md.append(f"- baseline {b_avg:.2f} → current {c_avg:.2f} (Δ {c_avg-b_avg:+.2f})")
            for axis in ["typography", "hierarchy", "distinctiveness", "color", "density", "voice"]:
                b = b_scores.get(axis, 0)
                c = c_scores.get(axis, 0)
                if c < b:
                    md.append(f"  - **{axis}**: {b} → {c} ({c-b:+d})")
            md.append("")

    md.append(f"\n_Run completed at {datetime.utcnow().isoformat()}Z. {new_baselines} new baselines set, {len(regressions)} regressions flagged._")
    report_path.write_text("\n".join(md))
    tracked_path.write_text(json.dumps(tracked, indent=2))
    print(json.dumps({
        "ok": True,
        "report": str(report_path),
        "tracked": len(tracked),
        "regressions": len(regressions),
        "new_baselines": new_baselines,
    }, indent=2))


def cmd_bootstrap(args):
    """Scaffold a new AI-friendly static site at ~/<slug>-site/."""
    sys.path.insert(0, str(SKILL_DIR / "templates"))
    import site_template as T

    if args.spec and Path(args.spec).exists():
        spec = json.loads(Path(args.spec).read_text())
    else:
        spec = {}
    spec["slug"] = args.slug
    spec["domain"] = args.domain or f"{args.slug}.com"
    spec.setdefault("title", spec["slug"].replace("-", " ").title())
    spec.setdefault("summary", f"{spec['title']} — placeholder summary, edit me.")
    spec.setdefault("headline", spec["title"])
    spec.setdefault("body_paragraphs", [spec["summary"]])
    spec.setdefault("primary_color", "#0a1641")
    spec.setdefault("accent_color", "#0e7490")
    spec.setdefault("accent_hex_decorative", "#0fbbbb")
    spec.setdefault("headline_font", "Montserrat")
    spec.setdefault("body_font", "Open Sans")
    spec.setdefault("serif_font", "Fraunces")
    spec.setdefault("email", f"hello@{spec['domain']}")
    spec.setdefault("schema_type", "Organization")
    spec.setdefault("person_name", "")
    spec.setdefault("extra_pages", [])
    spec.setdefault("sister_sites", [])

    out_dir = Path(args.out_dir or (Path.home() / f"{args.slug}-site"))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "assets" / "brand").mkdir(parents=True, exist_ok=True)

    files = {
        "index.html": T.render_html(spec),
        "index.md": T.render_markdown(spec),
        "llms.txt": T.render_llms_txt(spec),
        "llms-full.txt": T.render_markdown(spec),
        "robots.txt": T.render_robots(spec),
        "sitemap.xml": T.render_sitemap(spec),
        "style.css": T.render_css(spec),
    }
    for path, content in files.items():
        (out_dir / path).write_text(content)

    # Helpful README so the human knows what was scaffolded
    readme = f"""# {spec['title']}

Bootstrapped {datetime.utcnow().date().isoformat()} via webpage-layout skill.

## What's wired

- `index.html` — canonical HTML with JSON-LD ({spec['schema_type']}) + `<link rel="alternate">` to markdown
- `index.md` — markdown shadow at canonical /index.md URL
- `llms.txt` — short curated summary per [llmstxt.org](https://llmstxt.org)
- `llms-full.txt` — full content as one markdown document
- `robots.txt` — explicit allowlist for {len(T.AI_BOTS)} AI crawlers (GPTBot, ClaudeBot, Perplexity, etc.)
- `sitemap.xml` — lists all pages + AI-friendly endpoints
- `style.css` — single-font accessible starter ({spec['headline_font']} + {spec['body_font']})
- `assets/brand/` — drop logos / favicons here

## Next

1. Edit `index.html` and `index.md` content
2. Drop logo files in `assets/brand/`
3. Deploy: `wrangler pages deploy . --project-name={spec['slug']} --branch=main`
4. After deploy, run an audit: `python3 ~/.claude/skills/webpage-layout/run.py audit https://{spec['domain']} --persona <persona>`
"""
    (out_dir / "README.md").write_text(readme)

    print(json.dumps({
        "ok": True,
        "out_dir": str(out_dir),
        "files_written": list(files.keys()) + ["README.md"],
        "next": f"Edit content, drop assets/brand/ logos, then `cd {out_dir} && wrangler pages deploy . --project-name={spec['slug']} --branch=main`",
    }, indent=2))


def cmd_richness(args):
    """Visual-richness audit: binary check of R1–R10 recipes from recipes/visual-richness.md.
    Output JSON + a short markdown report. Different lens than `audit` (editorial-cleanness rubric);
    use when the question is "is this site bold + colorful enough", not "is this site editorial-clean enough".
    """
    import re
    url = args.url
    slug = slugify(url)
    out_dir = STATE / "richness" / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    # Fetch HTML + concat any same-origin <link rel="stylesheet"> hrefs
    html_path = out_dir / "index.html"
    fetch_html(url, html_path)
    html = html_path.read_text(errors="replace")

    # Extract inline + linked CSS
    inline_styles = "\n".join(re.findall(r"<style\b[^>]*>(.*?)</style>", html, re.DOTALL | re.IGNORECASE))
    inline_scripts = "\n".join(re.findall(r"<script\b[^>]*>(.*?)</script>", html, re.DOTALL | re.IGNORECASE))
    css_links = re.findall(r'<link[^>]+rel=["\']?stylesheet["\']?[^>]+href=["\']([^"\']+)["\']', html, re.IGNORECASE)
    from urllib.parse import urljoin
    css_blob = inline_styles
    for href in css_links:
        if href.startswith("data:"):
            continue
        try:
            full = href if href.startswith("http") else urljoin(url, href)
            r = httpx.get(full, timeout=8, follow_redirects=True)
            if r.status_code == 200 and "css" in r.headers.get("content-type", ""):
                css_blob += "\n/* " + full + " */\n" + r.text
        except Exception:
            pass

    haystack = (html + "\n" + css_blob + "\n" + inline_scripts).lower()
    css = css_blob.lower()
    js = inline_scripts.lower()

    # Recipe detection rules — pattern matching for binary applied/not-applied
    # Each tuple: (id, name, list-of-evidence-checks). Each check is a regex pattern (lowercase).
    recipes = [
        ("R1", "Full-bleed dark gradient band",
         [r"linear-gradient\([^)]+#0[0-9a-f]{5}",  # dark hex
          r"radial-gradient\([^)]+rgba\(",
          r"backdrop-filter:\s*blur"],
         2),  # need ≥ 2 of 3
        ("R2", "Big-number pull-quote moment",
         [r"\.bn-num\b|class=[\"']bn-num",
          r"font-size:\s*clamp\([^)]*[5-9]rem",
          r"-webkit-background-clip:\s*text"],
         2),
        ("R3", "Animated SVG mark (stroke-draw)",
         [r"stroke-dasharray",
          r"stroke-dashoffset",
          r"@keyframes\s+\w*draw"],
         2),
        ("R4", "Animated gradient drop cap",
         [r"\.lede-cap\b|class=[\"']lede-cap",
          r"@keyframes\s+\w*shimmer|cap-shimmer",
          r"-webkit-background-clip:\s*text"],
         2),
        ("R5", "Gradient mesh halo",
         [r"radial-gradient\([^)]+rgba\(",
          r"filter:\s*blur",
          r"::before"],
         2),
        ("R6", "Color-rich hover (lift + shadow)",
         [r":hover[^{]*\{[^}]*transform:\s*translatey\([^)]*-[1-9]",
          r":hover[^{]*\{[^}]*box-shadow:[^}]*rgba",
          r":hover[^{]*\{[^}]*filter:\s*brightness"],
         2),
        ("R7", "Scroll-triggered fade-ins (IntersectionObserver)",
         [r"intersectionobserver",
          r"fade-in-init|fade-in-visible",
          r"prefers-reduced-motion"],
         2),
        ("R8", "Typographic stat strip (anti-stencil)",
         [r"\.stat-band\b",
          r"border-top.*?var\(--rule\)|border-top:\s*1px",
          r"display:\s*flex"],
         2),
        ("R9", "Editorial section ornament (§ on rule)",
         [r"\.ornament\b",
          r"content:\s*[\"']§|content:\s*[\"']\\00a7",
          r"::after.*?translate\(-50%"],
         2),
        ("R10", "Editorial 'currently' sidebar callout",
         [r"\.opening-currently|class=[\"'][^\"']*currently",
          r"\boc-rubric\b|\boc-key\b|\boc-val\b",
          r"currently"],
         2),
    ]

    results = []
    for rid, name, patterns, threshold in recipes:
        hits = []
        for pat in patterns:
            if re.search(pat, haystack):
                hits.append(pat)
        applied = len(hits) >= threshold
        results.append({
            "id": rid, "name": name,
            "applied": applied,
            "hits": len(hits), "threshold": threshold, "checks": len(patterns),
            "evidence": hits[:3],
        })

    applied_count = sum(1 for r in results if r["applied"])
    score_pct = round(applied_count / len(results) * 100)

    # Persona-aware verdict — design-forward sites should hit ≥7 of 10, editorial sites ≥4
    if score_pct >= 70:
        verdict = "BOLD"
    elif score_pct >= 40:
        verdict = "BALANCED"
    else:
        verdict = "EDITORIAL-LEAN"

    report = [f"# visual-richness audit — {url}", ""]
    report.append(f"**Verdict**: `{verdict}`  ·  **Recipes applied**: `{applied_count}/{len(results)}` ({score_pct}%)")
    report.append(f"**Generated**: {datetime.utcnow().isoformat()}Z")
    report.append("")
    report.append("| Recipe | Applied | Hits | Notes |")
    report.append("|---|---|---|---|")
    for r in results:
        mark = "✅" if r["applied"] else "—"
        notes = ", ".join(r["evidence"][:2]) if r["applied"] else "not detected"
        report.append(f"| **{r['id']}** {r['name']} | {mark} | {r['hits']}/{r['checks']} | {notes[:80]} |")
    report.append("")
    report.append("## Reference")
    report.append("Recipes: `~/.claude/skills/webpage-layout/recipes/visual-richness.md`")
    report.append("Detection is heuristic (HTML/CSS pattern match, ~70% accuracy). False negatives more common than false positives.")
    report.append("Production reference (BOLD verdict expected): matteisn.com, vang.capital, vangadvisory.com.")

    report_path = out_dir / "report.md"
    report_path.write_text("\n".join(report))

    print(json.dumps({
        "ok": True,
        "url": url,
        "verdict": verdict,
        "applied": applied_count,
        "total": len(results),
        "score_pct": score_pct,
        "report": str(report_path),
        "results": results,
    }, indent=2))


# Recipe priority order for richness-lift — biggest visual payoff first.
RECIPE_PRIORITY = ["R1", "R2", "R6", "R5", "R7", "R3", "R4", "R10", "R9", "R8"]

# Paste-ready CSS recipe templates with placeholder tokens — substituted from detected brand
RECIPE_TEMPLATES = {
    "R1": """/* R1 — Full-bleed dark gradient band (apply to .ecosystem / .colophon / footer-prelude) */
.full-bleed-band {{
  margin: 6rem 0 0;
  padding: 4rem var(--gutter, 1.5rem) 4.5rem;
  background: linear-gradient(135deg, #050b25 0%, {navy} 50%, {accent} 130%);
  position: relative;
  overflow: hidden;
}}
.full-bleed-band::before {{
  content: "";
  position: absolute;
  inset: 0;
  background-image:
    radial-gradient(circle at 88% 18%, {accent_rgba} 0%, transparent 40%),
    radial-gradient(circle at 8% 92%, rgba(255,255,255,0.05) 0%, transparent 45%);
  pointer-events: none;
}}
.full-bleed-band > * {{ max-width: 56rem; margin: 0 auto; position: relative; z-index: 1; }}
""",
    "R2": """/* R2 — Big-number pull-quote moment */
.big-number {{
  margin: 5rem 0;
  padding: 3.5rem 2.5rem;
  background: linear-gradient(135deg, var(--paper, #fff) 0%, var(--section-bg, #f4f6fb) 100%);
  border-left: 5px solid {accent};
  border-radius: 0 8px 8px 0;
  position: relative;
}}
.bn-row {{ display: grid; grid-template-columns: minmax(0,auto) minmax(0,1fr); gap: 2rem; align-items: center; }}
.bn-num {{
  font-family: var(--serif, "Fraunces", Georgia, serif);
  font-weight: 600;
  font-size: clamp(4rem, 9vw, 7rem);
  line-height: 0.9;
  letter-spacing: -0.04em;
  margin: 0;
  background: linear-gradient(135deg, {navy} 0%, {accent_text} 60%, {accent} 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  font-feature-settings: "tnum" 1, "lnum" 1;
}}
.bn-num em {{ font-style: italic; font-weight: 500; font-size: 0.55em; letter-spacing: -0.02em; }}
.bn-label {{ font-family: var(--serif); font-style: italic; font-size: clamp(1.15rem,1.7vw,1.4rem); color: var(--navy-soft); margin: 0; max-width: 32ch; }}
.bn-tag {{ display: inline-block; font-family: var(--headline); font-size: 0.72rem; font-weight: 600; letter-spacing: 0.18em; text-transform: uppercase; color: {accent_text}; margin-bottom: 0.85rem; }}
""",
    "R6": """/* R6 — Color-rich hover (CV row / portfolio tile) */
.cv-row {{ position: relative; padding-left: 1.1rem; transition: background 0.2s, padding 0.2s; }}
.cv-row::before {{
  content: ""; position: absolute; left: 0; top: 1.1rem; bottom: 1.1rem;
  width: 3px; background: linear-gradient(180deg, {accent} 0%, {navy} 100%);
  opacity: 0; transform: scaleY(0.4); transform-origin: top;
  transition: opacity 0.25s, transform 0.25s; border-radius: 2px;
}}
.cv-row:hover::before {{ opacity: 1; transform: scaleY(1); }}
.cv-row:hover {{ background: linear-gradient(90deg, {accent_rgba_low} 0%, transparent 60%); padding-left: 1.4rem; }}
.port-tile {{ transition: transform 0.25s, box-shadow 0.25s, filter 0.25s; }}
.port-tile:hover {{ transform: translateY(-4px) scale(1.03); box-shadow: 0 16px 32px {accent_rgba}; filter: brightness(1.10) saturate(1.15); }}
""",
    "R5": """/* R5 — Gradient mesh halo (apply to hero ::before) */
.hero {{ position: relative; }}
.hero::before {{
  content: "";
  position: absolute;
  inset: -4rem -4rem auto auto;
  width: 28rem;
  height: 28rem;
  background:
    radial-gradient(circle at 70% 30%, {accent_rgba} 0%, transparent 55%),
    radial-gradient(circle at 30% 80%, {navy_rgba} 0%, transparent 60%);
  pointer-events: none;
  z-index: -1;
  border-radius: 50%;
  filter: blur(20px);
}}
""",
    "R7": """/* R7 — Scroll-triggered fade-ins (CSS + JS) */
.fade-in-init {{
  opacity: 0;
  transform: translateY(20px);
  transition: opacity 0.65s cubic-bezier(0.22,1,0.36,1), transform 0.65s cubic-bezier(0.22,1,0.36,1);
}}
.fade-in-init.fade-in-visible {{ opacity: 1; transform: translateY(0); }}
@media (prefers-reduced-motion: reduce) {{ .fade-in-init {{ opacity: 1; transform: none; transition: none; }} }}

/* JS — paste before </body>: */
/*
<script>
(function () {{
  if (!('IntersectionObserver' in window)) return;
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  var els = document.querySelectorAll('.block, section, .testimonials, .ecosystem, .hero');
  els.forEach(function (el) {{ el.classList.add('fade-in-init'); }});
  var obs = new IntersectionObserver(function (entries) {{
    entries.forEach(function (e) {{
      if (e.isIntersecting) {{ e.target.classList.add('fade-in-visible'); obs.unobserve(e.target); }}
    }});
  }}, {{ threshold: 0.08, rootMargin: '0px 0px -6% 0px' }});
  els.forEach(function (el) {{ obs.observe(el); }});
}})();
</script>
*/
""",
    "R3": """/* R3 — Animated SVG mark (stroke-draw on load) — requires SVG with stroked paths */
.brand-mark path,
.brand-mark circle {{
  stroke-dasharray: 800;
  stroke-dashoffset: 800;
  animation: mark-draw 2.4s ease-out 0.3s forwards;
}}
.brand-mark path:nth-of-type(2) {{ animation-delay: 0.7s; }}
.brand-mark path:nth-of-type(3) {{ animation-delay: 1.0s; }}
.brand-mark circle {{ animation: mark-pop 0.4s ease-out 1.8s backwards; }}
@keyframes mark-draw {{ to {{ stroke-dashoffset: 0; }} }}
@keyframes mark-pop {{ 0% {{ opacity: 0; transform: scale(0.4); transform-origin: center; }} 100% {{ opacity: 1; transform: scale(1); }} }}
@media (prefers-reduced-motion: reduce) {{
  .brand-mark path, .brand-mark circle {{ animation: none; stroke-dashoffset: 0; }}
}}
""",
    "R4": """/* R4 — Animated gradient drop cap. HTML: <span class="lede-cap">H</span>ead of... */
.lede-cap {{
  float: left;
  font-family: var(--serif, "Fraunces", Georgia, serif);
  font-weight: 700;
  font-size: 5rem;
  line-height: 0.82;
  margin: 0.18rem 0.45rem -0.05rem -0.05rem;
  letter-spacing: -0.02em;
  background: linear-gradient(135deg, {navy} 0%, {accent_text} 50%, {accent} 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  background-size: 220% 220%;
  animation: cap-shimmer 1.6s ease-out 0.3s 1 backwards;
}}
@keyframes cap-shimmer {{
  0% {{ background-position: 100% 0%; opacity: 0.4; transform: translateY(4px); }}
  60% {{ opacity: 1; transform: translateY(0); }}
  100% {{ background-position: 0% 100%; }}
}}
@media (prefers-reduced-motion: reduce) {{ .lede-cap {{ animation: none; }} }}
""",
    "R10": """/* R10 — Editorial 'currently' sidebar callout. HTML pattern in recipes/visual-richness.md */
.opening-currently {{ border-top: 1px solid var(--rule, #d8dde8); padding-top: 1.1rem; }}
.oc-rubric {{ font-family: var(--headline); font-size: 0.72rem; font-weight: 600; letter-spacing: 0.18em; text-transform: uppercase; color: var(--navy-faint); margin: 0 0 0.7rem; }}
.opening-currently ul {{ list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.55rem; }}
.opening-currently li {{ display: grid; grid-template-columns: 5rem 1fr; gap: 0.7rem; align-items: baseline; font-size: 0.88rem; line-height: 1.5; color: var(--navy); }}
.opening-currently .oc-key {{ font-family: var(--headline); font-weight: 600; font-size: 0.7rem; letter-spacing: 0.12em; text-transform: uppercase; color: {accent_text}; padding-top: 0.1rem; }}
""",
    "R9": """/* R9 — Editorial section ornament. HTML: <hr class="ornament" aria-hidden="true" /> */
.ornament {{
  border: 0;
  margin: 3.5rem auto 1rem;
  height: 1.6rem;
  position: relative;
  background-image: linear-gradient(var(--rule, #d8dde8), var(--rule, #d8dde8));
  background-position: center center;
  background-repeat: no-repeat;
  background-size: 100% 1px;
  max-width: 8rem;
}}
.ornament::after {{
  content: "§";
  position: absolute; top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  background: var(--paper, #fff);
  padding: 0 0.7rem;
  font-family: var(--serif);
  font-style: italic;
  color: {accent_text};
  font-size: 1.15rem;
}}
""",
    "R8": """/* R8 — Typographic stat strip (replace boxed gradient strip with hairline-rule typographic line) */
.stat-band {{
  list-style: none;
  margin: 1.5rem 0 4rem;
  padding: 1.5rem 0;
  border-top: 1px solid var(--rule, #d8dde8);
  border-bottom: 1px solid var(--rule, #d8dde8);
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 2rem;
  align-items: baseline;
  background: none;  /* remove any prior gradient/box treatment */
}}
.stat-band li {{ display: flex; align-items: baseline; gap: 0.55rem; }}
.stat-num {{ font-family: var(--serif); font-weight: 600; font-size: 1.2rem; color: {navy}; font-feature-settings: "tnum"; }}
.stat-label {{ font-family: var(--body); font-size: 0.92rem; color: var(--navy-faint); line-height: 1.45; }}
""",
}


BRAND_TOKENS = {
    "matteisn": {
        "brand": "matteisn",
        "navy": "#273a96", "navy_rgba": "rgba(39,58,150,0.10)",
        "accent": "#0fbbbb", "accent_text": "#0e7490",
        "accent_rgba": "rgba(15,187,187,0.16)", "accent_rgba_low": "rgba(15,187,187,0.06)",
    },
    "vang": {
        "brand": "vang",
        "navy": "#0a1641", "navy_rgba": "rgba(10,22,65,0.10)",
        "accent": "#4b04af", "accent_text": "#4b04af",
        "accent_rgba": "rgba(75,4,175,0.16)", "accent_rgba_low": "rgba(75,4,175,0.06)",
    },
    "zerg": {
        "brand": "zerg",
        "navy": "#111514", "navy_rgba": "rgba(17,21,20,0.08)",
        "accent": "#b3662f", "accent_text": "#8a4a1f",
        "accent_rgba": "rgba(179,102,47,0.16)", "accent_rgba_low": "rgba(179,102,47,0.06)",
    },
    "generic": {
        "brand": "generic",
        "navy": "#1f2937", "navy_rgba": "rgba(31,41,55,0.10)",
        "accent": "#0891b2", "accent_text": "#0e7490",
        "accent_rgba": "rgba(8,145,178,0.16)", "accent_rgba_low": "rgba(8,145,178,0.06)",
    },
}


def detect_brand(html_or_css: str, url: str = "") -> dict:
    """Match brand by URL hostname (primary) then CSS color signature (fallback).
    Hostname is deterministic — strongly preferred over content-based detection."""
    from urllib.parse import urlparse
    host = urlparse(url).hostname.lower() if url else ""
    if host in ("matteisn.com", "www.matteisn.com"):
        return BRAND_TOKENS["matteisn"]
    if host in ("vang.capital", "www.vang.capital", "vangadvisory.com", "www.vangadvisory.com"):
        return BRAND_TOKENS["vang"]
    if host in ("zergai.com", "www.zergai.com") or host.endswith(".zergai.com"):
        return BRAND_TOKENS["zerg"]
    # CSS color signature fallback
    css_l = html_or_css.lower()
    if "#273a96" in css_l or "#0fbbbb" in css_l or "0e7490" in css_l:
        return BRAND_TOKENS["matteisn"]
    if "#0a1641" in css_l or "#4b04af" in css_l:
        return BRAND_TOKENS["vang"]
    if "#111514" in css_l or "#b3662f" in css_l or "#8a4a1f" in css_l:
        return BRAND_TOKENS["zerg"]
    return BRAND_TOKENS["generic"]


def cmd_richness_lift(args):
    """Auto-suggest top-N missing recipes with paste-ready CSS patch.
    Runs richness audit first, then for each NOT-applied recipe (in priority order),
    emits a starter CSS block with brand tokens substituted from the existing CSS."""
    # Run richness audit silently — capture results
    import io as _io, contextlib as _ctx
    buf = _io.StringIO()
    audit_args = argparse.Namespace(url=args.url, cmd="richness")
    with _ctx.redirect_stdout(buf):
        cmd_richness(audit_args)
    audit = json.loads(buf.getvalue())

    # Re-fetch CSS for brand detection (cheap; cached locally)
    slug = slugify(args.url)
    out_dir = STATE / "richness" / slug
    html = (out_dir / "index.html").read_text(errors="replace") if (out_dir / "index.html").exists() else ""
    brand = detect_brand(html, args.url)

    # Find NOT-applied recipes, sorted by priority
    by_id = {r["id"]: r for r in audit["results"]}
    missing = [rid for rid in RECIPE_PRIORITY if rid in by_id and not by_id[rid]["applied"]]
    top = missing[:args.top]

    out = [
        f"# richness-lift — {args.url}",
        "",
        f"**Current**: `{audit['verdict']}` ({audit['applied']}/{audit['total']} = {audit['score_pct']}%)",
        f"**Brand detected**: `{brand['brand']}` (navy={brand['navy']}, accent={brand['accent']})",
        f"**Top {len(top)} missing recipes** (by visual-payoff priority):",
        "",
    ]
    for rid in top:
        r = by_id[rid]
        out.append(f"- **{rid}** — {r['name']}")
    out.append("")
    out.append("---")
    out.append("")
    out.append("## Paste-ready CSS patch")
    out.append("")
    out.append("Append to your stylesheet, replace generic class names (`.full-bleed-band` / `.cv-row` / `.hero` etc.) with your site's actual class names where noted.")
    out.append("")
    for rid in top:
        if rid in RECIPE_TEMPLATES:
            out.append("```css")
            out.append(RECIPE_TEMPLATES[rid].format(**brand))
            out.append("```")
            out.append("")
    out.append("---")
    out.append("")
    out.append("## Reference")
    out.append("Full recipe library + symptom→recipe table: `~/.claude/skills/webpage-layout/recipes/visual-richness.md`")
    out.append("")
    out.append(f"After applying, re-run `python3 ~/.claude/skills/webpage-layout/run.py richness {args.url}` to verify the lift.")

    patch_path = out_dir / "lift.md"
    patch_path.write_text("\n".join(out))

    print(json.dumps({
        "ok": True,
        "url": args.url,
        "current_score": audit["score_pct"],
        "current_verdict": audit["verdict"],
        "brand_detected": brand["brand"],
        "missing_count": len(missing),
        "top_recipes": top,
        "patch_file": str(patch_path),
    }, indent=2))
    print(f"\n# Patch ready at: {patch_path}")
    print(f"# View: cat {patch_path}")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("learn")
    pl.add_argument("--force", action="store_true")
    pa = sub.add_parser("audit")
    pa.add_argument("url")
    pa.add_argument("--persona", default="personal", choices=["personal", "fund", "advisory", "brand_product"])
    pr = sub.add_parser("richness", help="Binary-check R1–R10 visual-richness recipes against a target URL")
    pr.add_argument("url")
    plift = sub.add_parser("richness-lift", help="Auto-suggest top-N missing recipes with paste-ready CSS patch")
    plift.add_argument("url")
    plift.add_argument("--top", type=int, default=3, help="How many missing recipes to surface (default 3)")
    sub.add_parser("status")
    pb = sub.add_parser("bootstrap", help="Scaffold a new AI-friendly site")
    pb.add_argument("--slug", required=True, help="URL-safe slug (becomes ~/<slug>-site/)")
    pb.add_argument("--domain", help="Domain (defaults to <slug>.com)")
    pb.add_argument("--spec", help="Path to JSON file with site spec overrides")
    pb.add_argument("--out-dir", help="Custom output dir (defaults to ~/<slug>-site/)")
    pm = sub.add_parser("monitor", help="Track + re-audit URLs over time, flag regressions")
    pm_sub = pm.add_subparsers(dest="action", required=True)
    pm_track = pm_sub.add_parser("track", help="Add a URL to the tracked list")
    pm_track.add_argument("url")
    pm_track.add_argument("--persona", default="personal", choices=["personal", "fund", "advisory", "brand_product"])
    pm_sub.add_parser("list", help="Show tracked URLs + last scores")
    pm_sub.add_parser("run", help="Re-audit all tracked URLs and write a regression report")
    args = p.parse_args()
    if args.cmd == "learn":
        cmd_learn(args)
    elif args.cmd == "audit":
        cmd_audit(args)
    elif args.cmd == "status":
        cmd_status()
    elif args.cmd == "bootstrap":
        cmd_bootstrap(args)
    elif args.cmd == "monitor":
        cmd_monitor(args)
    elif args.cmd == "richness":
        cmd_richness(args)
    elif args.cmd == "richness-lift":
        cmd_richness_lift(args)


if __name__ == "__main__":
    main()
