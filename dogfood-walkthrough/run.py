#!/usr/bin/env python3
"""dogfood-walkthrough — proof harness for the serial-launch polish.

Usage:
    python3 ~/.claude/skills/dogfood-walkthrough/run.py pick [--confirm <slug>]
    python3 ~/.claude/skills/dogfood-walkthrough/run.py walk [--station N] [--resume] [--override "<reason>"]
    python3 ~/.claude/skills/dogfood-walkthrough/run.py repair
    python3 ~/.claude/skills/dogfood-walkthrough/run.py scorecard
    python3 ~/.claude/skills/dogfood-walkthrough/run.py doctor
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required. Install: pip3 install pyyaml", file=sys.stderr)
    sys.exit(2)

VAULT = Path("/Users/mattheweisner/Obsidian/Zerg")
GROWTH = VAULT / "MattZerg" / "Projects" / "Zerg-Production" / "Growth"
DOGFOOD_DIR, BACKLOG_DIR = GROWTH / "dogfood", GROWTH / "launch-backlog"
ACTIVE_POINTER = DOGFOOD_DIR / "_active.txt"
MEASUREMENT_DIR, LIFECYCLE_DIR, LAUNCHES_DIR = GROWTH / "measurement", GROWTH / "lifecycle", GROWTH / "launches"
COMPETITIVE_DIR = VAULT / "MattZerg" / "Competitive"
ZERG_ROOT = Path.home() / "zerg"
TEMPLATES_ROOT = ZERG_ROOT / "_templates"
PREFLIGHT_SCRIPT = TEMPLATES_ROOT / "scripts" / "preflight.py"
BOOTSTRAP_SCRIPT = TEMPLATES_ROOT / "scripts" / "zerg-new-product.sh"
SKILLS_ROOT = Path.home() / ".claude" / "skills"
PRODUCT_DOCS_RUN = SKILLS_ROOT / "product-docs-skill" / "run.py"
EMAIL_DRIP_RUN = SKILLS_ROOT / "email-drip" / "run.py"
GROWTH_DASHBOARD_RUN = SKILLS_ROOT / "growth-dashboard" / "run.py"

STATIONS = [
    ("site-bootstrap", "Site bootstrap", "zerg-new-product.sh + preflight.py"),
    ("docs-scaffold", "Docs scaffold", "product-docs-skill scaffold + audit"),
    ("measurement", "Measurement spec", "validate measurement/<slug>.yaml + .checklist.md"),
    ("drip", "Drip wired", "email-drip scaffold + audit"),
    ("launch-pack", "Launch pack", "launch-pack agent (manual handoff for now)"),
    ("demo-video", "Demo video", "product-launch-video plan + video-review"),
    ("distribution", "Distribution", "content-distribution generate + 17 surfaces"),
    ("smoke", "Smoke (post-ship)", "growth-dashboard --product <slug> shows non-stub lines"),
]

REQUIRED_EVENT_SUFFIXES = ["_signup", "_aha", "_pro_upgrade", "_bundle_upgrade", "_last_active_at", "_churn_risk"]
VALID_STATUS_VALUES = {"drafting", "ready", "scheduled", "approved"}
SUBPROC_TIMEOUT = 60

DISTRIBUTION_SURFACE_LABELS = {
    "Twitter/X thread", "LinkedIn long-form", "LinkedIn company page repost",
    "Reddit (per-sub variants)", "Hacker News (Show HN)", "Product Hunt",
    "Instagram", "YouTube (short)", "Threads", "Bluesky", "Mastodon",
    "Discord (per-community)", "Slack communities", "Email newsletter (broadcast)",
    "Blog post (zergai.com or product blog)", "Webflow / docs banner", "Changelog entry",
}

def _today_str() -> str:
    return dt.date.today().isoformat()

def _now_pt_str() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M PT")

def _result(status: str, invoked: str, finding: str, friction=None, repair="none", cited=None) -> dict:
    return {
        "status": status,
        "invoked": invoked,
        "finding": finding,
        "friction": list(friction or []),
        "repair": repair,
        "cited": list(cited or []),
    }

def _parse_frontmatter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        fm = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        fm = {}
    return (fm if isinstance(fm, dict) else {}), parts[2]

def _parse_target_date(value) -> dt.date | None:
    if not value:
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
            try:
                return dt.datetime.strptime(s, fmt).date()
            except ValueError:
                continue
    return None

def _positioning_complete(body: str) -> bool:
    tbd_count = len(re.findall(r"^_TBD_\s*$", body, flags=re.MULTILINE))
    section_count = len(re.findall(r"^##\s+\S", body, flags=re.MULTILINE))
    return section_count > 0 and tbd_count < section_count

def _read_active_slug() -> str | None:
    if not ACTIVE_POINTER.exists():
        return None
    for line in ACTIVE_POINTER.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    return None

def _backlog_path_for(slug: str) -> Path | None:
    if not BACKLOG_DIR.exists():
        return None
    for p in sorted(BACKLOG_DIR.glob("*.md")):
        if p.name.startswith("_"):
            continue
        fm, _ = _parse_frontmatter(p)
        if fm.get("slug") == slug:
            return p
    return None

def _competitive_folder_exists(category: str | None) -> bool:
    return bool(category) and (COMPETITIVE_DIR / category / "positioning.md").exists()

def _candidate_score(fm: dict, target: dt.date | None, today: dt.date) -> tuple:
    rice = fm.get("rice")
    rice_key = -float(rice) if isinstance(rice, (int, float)) else 0.0
    date_key = (target - today).days if target else 9999
    return (rice_key, date_key)

def _gather_candidates() -> tuple[list[dict], list[dict]]:
    matches: list[dict] = []
    near_miss: list[dict] = []
    if not BACKLOG_DIR.exists():
        return matches, near_miss
    today = dt.date.today()
    for path in sorted(BACKLOG_DIR.glob("*.md")):
        if path.name.startswith("_") or path.name == "README.md":
            continue
        fm, body = _parse_frontmatter(path)
        slug = (fm.get("slug") or "").strip()
        product_name = (fm.get("product_name") or "").strip()
        one_liner = (fm.get("one_liner") or "").strip()
        status = (fm.get("status") or "").strip().lower()
        target = _parse_target_date(fm.get("target_launch_date"))
        category = (fm.get("category") or "").strip() or None

        reasons, fails = [], []
        if not slug:
            fails.append("missing slug")
        if not product_name or not one_liner:
            fails.append("frontmatter missing product_name/one_liner")
        else:
            reasons.append("positioning frontmatter complete")
        if target is None:
            fails.append("no target_launch_date")
        else:
            delta = (target - today).days
            if 7 <= delta <= 30:
                reasons.append(f"ship_date in window (+{delta}d)")
            else:
                fails.append(f"ship_date outside 7-30d window ({delta}d)")
        if status in VALID_STATUS_VALUES:
            reasons.append(f"status={status}")
        else:
            fails.append(f"status={status or 'tbd'} not in {sorted(VALID_STATUS_VALUES)}")
        if _positioning_complete(body):
            reasons.append("positioning body has non-_TBD_ sections")
        else:
            fails.append("positioning body is all _TBD_")
        if _competitive_folder_exists(category):
            reasons.append(f"competitive folder present ({category})")

        entry = {
            "path": str(path), "slug": slug, "product_name": product_name, "status": status,
            "target_launch_date": target.isoformat() if target else None,
            "reasons": reasons, "fails": fails,
            "_score": _candidate_score(fm, target, today),
        }
        if not fails:
            matches.append(entry)
        elif slug:
            near_miss.append(entry)
    matches.sort(key=lambda e: e["_score"])
    near_miss.sort(key=lambda e: len(e["fails"]))
    return matches, near_miss

def cmd_pick(args: argparse.Namespace) -> int:
    matches, near_miss = _gather_candidates()
    if args.confirm:
        slug = args.confirm.strip()
        if not _backlog_path_for(slug):
            print(f"ERROR: no backlog entry with slug={slug!r} in {BACKLOG_DIR}", file=sys.stderr)
            return 1
        DOGFOOD_DIR.mkdir(parents=True, exist_ok=True)
        ACTIVE_POINTER.write_text(
            f"# Active dogfood slug (one line, set by: dogfood-walkthrough pick --confirm <slug>)\n{slug}\n",
            encoding="utf-8",
        )
        print(f"OK: wrote active slug={slug} to {ACTIVE_POINTER}")
        return 0

    print(f"# Backlog candidate scan ({_today_str()})")
    print(f"  source: {BACKLOG_DIR}\n")
    if matches:
        print(f"## Matching candidates ({len(matches)})")
        for i, c in enumerate(matches, 1):
            print(f"{i}. {c['slug']} — {c['product_name']}")
            print(f"   path: {c['path']}")
            print(f"   matches: {', '.join(c['reasons'])}")
            print(f"   confirm: dogfood-walkthrough pick --confirm {c['slug']}\n")
        return 0
    print("## No candidates match all 4 criteria.\n")
    if near_miss:
        closest = near_miss[0]
        print(f"Closest near-miss: {closest['slug'] or '(no slug)'} — {closest['product_name'] or '(no name)'}")
        print(f"  path: {closest['path']}")
        if closest["reasons"]:
            print(f"  passes: {', '.join(closest['reasons'])}")
        print(f"  fails: {', '.join(closest['fails'])}")
    else:
        print(f"No backlog entries have a slug yet. Fill `slug` + frontmatter in")
        print(f"`{BACKLOG_DIR}/slot-*.md` then re-run.")
    return 1

def _log_path_for(slug: str) -> Path:
    return DOGFOOD_DIR / f"dogfood-log-{slug}-{_today_str()}.md"

def _all_log_paths(slug: str) -> list[Path]:
    return sorted(DOGFOOD_DIR.glob(f"dogfood-log-{slug}-*.md")) if DOGFOOD_DIR.exists() else []

def _latest_log_path(slug: str) -> Path | None:
    paths = _all_log_paths(slug)
    return paths[-1] if paths else None

def _ensure_log_header(log_path: Path, slug: str) -> None:
    if log_path.exists():
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        f"# Dogfood walkthrough log — {slug}\n\n"
        f"Started: {_now_pt_str()}\n\n"
        f"Per-station status blocks below. Status legend: PASS | THEORETICAL | BROKE.\n\n",
        encoding="utf-8",
    )

def _append_log_block(log_path: Path, idx: int, station_id: str, station_name: str, result: dict) -> None:
    friction = result.get("friction") or []
    cited = result.get("cited") or []
    block = [
        f"## Station {idx} — {station_name}  ({_now_pt_str()})",
        f"- station_id: {station_id}",
        f"- Status: {result['status']}",
        f"- Skill invoked: {result.get('invoked', '')}",
        f"- Finding: {result.get('finding', '')}",
        "- Friction:",
    ]
    block += [f"  - {ln}" for ln in friction] if friction else ["  - (none)"]
    block.append(f"- Repair-needed: {result.get('repair', 'none')}")
    block.append(f"- Cited utilities: {', '.join(cited) if cited else 'none'}")
    block.append("")
    log_path.write_text(log_path.read_text(encoding="utf-8") + "\n".join(block) + "\n", encoding="utf-8")

def _run_subprocess(cmd: list[str]) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=SUBPROC_TIMEOUT, check=False)
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {SUBPROC_TIMEOUT}s"
    except FileNotFoundError as e:
        return 127, "", f"not found: {e}"

def _bullets_from(text: str, limit: int = 6) -> list[str]:
    return [ln.rstrip() for ln in text.splitlines() if ln.strip()][:limit]

def _check_site_bootstrap(slug: str) -> dict:
    cited = [str(BOOTSTRAP_SCRIPT), str(PREFLIGHT_SCRIPT)]
    product_dir = ZERG_ROOT / slug
    if not product_dir.exists():
        return _result("BROKE", f"check {product_dir}", f"product dir not found: {product_dir}",
                       [f"run: bash {BOOTSTRAP_SCRIPT} {slug}"], str(BOOTSTRAP_SCRIPT), cited)
    missing = [str(p) for p in (product_dir / "package.json", product_dir / "nuxt.config.ts") if not p.exists()]
    if missing:
        return _result("BROKE", f"check {product_dir}", f"bootstrap incomplete; missing: {', '.join(missing)}",
                       missing, str(BOOTSTRAP_SCRIPT), cited)
    if not PREFLIGHT_SCRIPT.exists():
        return _result("THEORETICAL", "preflight.py", f"skill not installed at expected path: {PREFLIGHT_SCRIPT}",
                       ["preflight script missing — bootstrap dir checks only"], str(PREFLIGHT_SCRIPT), cited)
    code, out, err = _run_subprocess(["python3", str(PREFLIGHT_SCRIPT), slug, "--strict"])
    combined = (out + "\n" + err).strip()
    high = len(re.findall(r"\bHIGH\b", combined))
    med = len(re.findall(r"\bMED\b", combined))
    invoked = f"preflight.py {slug} --strict"
    if high > 0:
        return _result("BROKE", invoked, f"preflight reports {high} HIGH, {med} MED",
                       _bullets_from(combined), str(PREFLIGHT_SCRIPT), cited)
    if med > 0:
        return _result("THEORETICAL", invoked, f"preflight reports {med} MED (0 HIGH)",
                       _bullets_from(combined), str(PREFLIGHT_SCRIPT), cited)
    return _result("PASS", invoked, "clean", [], "none", cited)

def _run_audit_skill(slug: str, script_path: Path, label: str, broke_repair: str | Path) -> dict:
    cited = [str(script_path)]
    if not script_path.exists():
        return _result("THEORETICAL", f"{label} audit",
                       f"skill not installed at expected path: {script_path}", [], str(script_path), cited)
    code, out, err = _run_subprocess(["python3", str(script_path), "audit", slug])
    combined = (out + "\n" + err).strip()
    if code == 0:
        return _result("PASS", f"{label} audit {slug}", "audit clean", [], "none", cited)
    return _result("BROKE", f"{label} audit {slug}", f"audit exit {code}",
                   _bullets_from(combined), str(broke_repair), cited)

def _check_docs_scaffold(slug: str) -> dict:
    return _run_audit_skill(slug, PRODUCT_DOCS_RUN, "product-docs-skill", ZERG_ROOT / slug / "docs")

def _check_measurement(slug: str) -> dict:
    yaml_path = MEASUREMENT_DIR / f"{slug}.yaml"
    checklist_path = MEASUREMENT_DIR / f"{slug}.checklist.md"
    template_path = MEASUREMENT_DIR / "_template.yaml"
    cited = [str(yaml_path), str(checklist_path), str(template_path)]
    missing = [str(p) for p in (yaml_path, checklist_path) if not p.exists()]
    if missing:
        return _result("BROKE", "measurement spec parse", f"missing files: {len(missing)}",
                       missing, str(template_path), cited)
    try:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        return _result("BROKE", "measurement spec parse", f"YAML parse error: {e}",
                       [str(e)], str(yaml_path), cited)
    required = data.get("required_events") or []
    found = [str(ev["name"]) for ev in required if isinstance(ev, dict) and ev.get("name")]
    missing_evs = [f"{slug}{s}" for s in REQUIRED_EVENT_SUFFIXES if f"{slug}{s}" not in found]
    if missing_evs:
        return _result("BROKE", "measurement spec parse",
                       f"missing canonical events: {len(missing_evs)}", missing_evs, str(yaml_path), cited)
    return _result("PASS", "measurement spec parse",
                   f"6 canonical events present; {len(found)} total required events", [], "none", cited)

def _check_drip(slug: str) -> dict:
    lifecycle_yaml = LIFECYCLE_DIR / f"{slug}.yaml"
    if not lifecycle_yaml.exists():
        return _result("BROKE", "email-drip audit", f"lifecycle config missing: {lifecycle_yaml}",
                       [f"run: python3 {EMAIL_DRIP_RUN} init {slug}"],
                       str(LIFECYCLE_DIR / "_drip-template.yaml"),
                       [str(EMAIL_DRIP_RUN), str(lifecycle_yaml)])
    return _run_audit_skill(slug, EMAIL_DRIP_RUN, "email-drip", lifecycle_yaml)

def _check_launch_pack(slug: str) -> dict:
    pack_dir = LAUNCHES_DIR / slug
    cited = [str(pack_dir), "~/.claude/agents/launch-pack.md"]
    if not pack_dir.exists():
        return _result("THEORETICAL", f"check {pack_dir}",
                       "launch-pack agent not yet invoked for this slug — run via Claude conversational interface",
                       ["dir missing — invoke `launch-pack` agent"], str(pack_dir), cited)
    missing = [str(p) for p in (pack_dir / "announcement.md", pack_dir / "manifest.md") if not p.exists()]
    if missing:
        return _result("THEORETICAL", f"check {pack_dir}",
                       f"launch-pack partial — missing: {', '.join(missing)}", missing, str(pack_dir), cited)
    return _result("PASS", f"check {pack_dir}", "announcement + manifest present", [], "none", cited)

def _check_demo_video(slug: str) -> dict:
    shot_list = ZERG_ROOT / slug / "demo-video" / "shot-list.template.json"
    video_plan = LAUNCHES_DIR / slug / "video-plan.md"
    cited = [str(shot_list), str(video_plan)]
    if not shot_list.exists():
        return _result("BROKE", "demo-video assets check",
                       f"shot-list missing — bootstrap did not copy template: {shot_list}",
                       [str(shot_list)],
                       str(TEMPLATES_ROOT / "zerg-product" / "demo-video" / "shot-list.template.json"), cited)
    try:
        json.loads(shot_list.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return _result("BROKE", "demo-video assets check", f"shot-list malformed JSON: {e}",
                       [str(e)], str(shot_list), cited)
    if not video_plan.exists():
        return _result("THEORETICAL", "demo-video assets check",
                       "shot-list present but no video-plan — launch-pack needs to be run",
                       [f"missing: {video_plan}"], str(video_plan), cited)
    return _result("PASS", "demo-video assets check", "shot-list valid + video-plan present", [], "none", cited)

def _check_distribution(slug: str) -> dict:
    dist_path = LAUNCHES_DIR / slug / "distribution.md"
    cited = [str(dist_path)]
    if not dist_path.exists():
        return _result("THEORETICAL", "distribution surface count",
                       "content-distribution not yet generated for this slug",
                       [f"missing: {dist_path}"], str(dist_path), cited)
    text = dist_path.read_text(encoding="utf-8")
    headers = re.findall(r"(?m)^##\s+(.+?)\s*$", text)
    matched = [h for h in headers if h.strip() in DISTRIBUTION_SURFACE_LABELS]
    count = len(matched)
    expected = len(DISTRIBUTION_SURFACE_LABELS)
    if count != expected:
        missing = sorted(DISTRIBUTION_SURFACE_LABELS - set(matched))
        return _result("BROKE", "distribution surface count",
                       f"surface count={count} (expected {expected})",
                       [f"missing: {m}" for m in missing[:8]] or [f"found: {count}"],
                       str(dist_path), cited)
    return _result("PASS", "distribution surface count", f"{expected} surfaces drafted", [], "none", cited)

def _check_smoke(slug: str) -> dict:
    cited = [str(GROWTH_DASHBOARD_RUN)]
    if not GROWTH_DASHBOARD_RUN.exists():
        return _result("THEORETICAL", "growth-dashboard dry-run",
                       f"skill not installed at expected path: {GROWTH_DASHBOARD_RUN}",
                       [], str(GROWTH_DASHBOARD_RUN), cited)
    code, out, err = _run_subprocess(["python3", str(GROWTH_DASHBOARD_RUN), "dry-run", "--product", slug])
    combined = (out + "\n" + err).strip()
    invoked = f"growth-dashboard dry-run --product {slug}"
    if code not in (0, 1):
        return _result("BROKE", invoked, f"dashboard crashed (exit {code})",
                       _bullets_from(combined), str(GROWTH_DASHBOARD_RUN), cited)
    lines = [ln for ln in combined.splitlines()
             if re.search(r"^\s*(?:[-*]|\d+\.|Line\s*\d)", ln, re.IGNORECASE)]
    head4 = "\n".join(lines[:4]) if lines else combined
    all_todo = bool(head4) and all(
        ("TODO" in ln or "stub" in ln.lower() or "placeholder" in ln.lower() or not ln.strip())
        for ln in head4.splitlines()
    )
    if all_todo or not head4.strip():
        return _result("THEORETICAL", invoked,
                       "kill_readiness_gate not yet green — product has not emitted required events in prod yet",
                       _bullets_from(head4 or combined), "none (post-ship gate)", cited)
    return _result("PASS", invoked, "at least one of lines 1-4 returns non-stub data", [], "none", cited)

STATION_CHECKS = {
    "site-bootstrap": _check_site_bootstrap,
    "docs-scaffold": _check_docs_scaffold,
    "measurement": _check_measurement,
    "drip": _check_drip,
    "launch-pack": _check_launch_pack,
    "demo-video": _check_demo_video,
    "distribution": _check_distribution,
    "smoke": _check_smoke,
}

def _last_attempted_station_idx(log_path: Path) -> int:
    if not log_path.exists():
        return 0
    matches = re.findall(r"^## Station (\d+) —", log_path.read_text(encoding="utf-8"), flags=re.MULTILINE)
    return max((int(m) for m in matches), default=0)

def _last_block_status(log_path: Path) -> tuple[int, str]:
    if not log_path.exists():
        return 0, ""
    blocks = list(_iter_log_blocks(log_path))
    if not blocks:
        return 0, ""
    last = blocks[-1]
    return last["idx"], last["status"]

def cmd_walk(args: argparse.Namespace) -> int:
    slug = _read_active_slug()
    if not slug:
        print("ERROR: no active slug. Set it via `dogfood-walkthrough pick --confirm <slug>`.", file=sys.stderr)
        print(f"       pointer: {ACTIVE_POINTER}", file=sys.stderr)
        return 2
    if not _backlog_path_for(slug):
        print(f"ERROR: active slug={slug!r} has no backlog entry in {BACKLOG_DIR}", file=sys.stderr)
        return 2

    DOGFOOD_DIR.mkdir(parents=True, exist_ok=True)
    log_path = _log_path_for(slug)
    _ensure_log_header(log_path, slug)

    modes_used = sum(bool(x) for x in (args.resume, args.station, args.only))
    if modes_used > 1:
        print("ERROR: --resume, --station, and --only are mutually exclusive", file=sys.stderr)
        return 2

    start_idx = 1
    end_idx = len(STATIONS)
    if args.resume:
        existing = _latest_log_path(slug)
        if existing:
            last_idx, last_status = _last_block_status(existing)
            if last_idx > 0:
                if last_status == "BROKE":
                    start_idx = last_idx
                    print(f"[resume] re-attempting BROKE station {start_idx} in {existing}")
                else:
                    start_idx = max(1, last_idx + 1)
                    print(f"[resume] continuing from station {start_idx} in {existing}")
            log_path = existing
    if args.station:
        start_idx = int(args.station)
    if args.only:
        start_idx = int(args.only)
        end_idx = start_idx
    if start_idx < 1 or start_idx > len(STATIONS):
        print(f"ERROR: station index out of range (1-{len(STATIONS)})", file=sys.stderr)
        return 2

    override_reason = (args.override or "").strip()
    print(f"# dogfood walkthrough — slug={slug}")
    print(f"  log: {log_path}")
    if args.only:
        print(f"  running only station {start_idx}/{len(STATIONS)}\n")
    else:
        print(f"  starting at station {start_idx}/{len(STATIONS)}\n")

    for i in range(start_idx, end_idx + 1):
        station_id, station_name, station_call = STATIONS[i - 1]
        print(f"[{i}/{len(STATIONS)}] {station_name}...")
        result = STATION_CHECKS[station_id](slug)
        status = result["status"]
        if status == "BROKE" and override_reason:
            result["friction"] = list(result.get("friction") or []) + [f"OVERRIDE: {override_reason}"]
            result["finding"] = result["finding"] + f" (override: {override_reason})"
            result["status"] = "THEORETICAL"
            status = "THEORETICAL"
        if not result.get("invoked"):
            result["invoked"] = station_call
        _append_log_block(log_path, i, station_id, station_name, result)
        print(f"    -> {status} — {result.get('finding', '')}")
        if status == "BROKE":
            print(f"\nBROKE at station {i}.")
            print(f"  log: {log_path}")
            print(f"  repair: {result.get('repair', '(see log)')}")
            print(f"  Run `dogfood-walkthrough repair` to fix, then `dogfood-walkthrough walk --resume`.")
            return 1
        override_reason = ""

    print(f"\n# walkthrough complete — slug={slug}")
    print(f"  log: {log_path}")
    print(f"  next: dogfood-walkthrough scorecard")
    return 0

def _iter_log_blocks(log_path: Path):
    text = log_path.read_text(encoding="utf-8")
    pattern = re.compile(r"^## Station (\d+) — (.+?)$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[m.start():end]
        status_m = re.search(r"^- Status:\s*(\S+)", block, re.MULTILINE)
        sid_m = re.search(r"^- station_id:\s*(\S+)", block, re.MULTILINE)
        repair_m = re.search(r"^- Repair-needed:\s*(.+)$", block, re.MULTILINE)
        finding_m = re.search(r"^- Finding:\s*(.+)$", block, re.MULTILINE)
        yield {
            "idx": int(m.group(1)),
            "name": m.group(2).split("  (")[0].strip(),
            "station_id": sid_m.group(1) if sid_m else "",
            "status": (status_m.group(1).strip() if status_m else "UNKNOWN").upper(),
            "repair": (repair_m.group(1).strip() if repair_m else ""),
            "finding": (finding_m.group(1).strip() if finding_m else ""),
        }

def cmd_repair(args: argparse.Namespace) -> int:
    slug = _read_active_slug()
    if not slug:
        print("ERROR: no active slug.", file=sys.stderr)
        return 2
    latest = _latest_log_path(slug)
    if not latest:
        print(f"No log found for slug={slug}. Run `dogfood-walkthrough walk` first.")
        return 1
    broke = [b for b in _iter_log_blocks(latest) if b["status"] == "BROKE"]
    if not broke:
        print(f"No BROKE blocks in {latest}.")
        return 0
    target = broke[-1]
    repair_path = target["repair"]
    print(f"# Latest BROKE — station {target['idx']} ({target['name']})")
    print(f"  finding: {target['finding']}")
    print(f"  repair-needed: {repair_path}")
    print(f"  log: {latest}")
    if not repair_path or repair_path == "none":
        print("  (no repair pointer recorded)")
        return 0
    editor = os.environ.get("EDITOR", "").strip()
    if editor:
        try:
            subprocess.run([editor, repair_path], check=False, timeout=SUBPROC_TIMEOUT)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"  (editor invocation failed: {e})")
    else:
        print(f"  open: {repair_path}")
    return 0

def cmd_scorecard(args: argparse.Namespace) -> int:
    slug = _read_active_slug()
    if not slug:
        print("ERROR: no active slug.", file=sys.stderr)
        return 2
    latest = _latest_log_path(slug)
    if not latest:
        print(f"no log found for active slug ({slug})")
        return 0
    by_station: dict[int, list[dict]] = {}
    for b in _iter_log_blocks(latest):
        by_station.setdefault(b["idx"], []).append(b)

    battle, theoretical, broke, deferred = [], [], [], []
    for i in range(1, len(STATIONS) + 1):
        station_id, station_name, _ = STATIONS[i - 1]
        attempts = by_station.get(i, [])
        if not attempts:
            deferred.append({"idx": i, "name": station_name, "station_id": station_id,
                             "status": "DEFERRED", "repair": "", "finding": ""})
            continue
        oldest_attempt = attempts[0]
        latest_attempt = attempts[-1]
        latest_attempt["name"] = station_name
        latest_attempt["station_id"] = station_id
        latest_status = latest_attempt["status"]
        oldest_status = oldest_attempt["status"]
        if latest_status == "BROKE":
            broke.append(latest_attempt)
        elif latest_status == "THEORETICAL":
            theoretical.append(latest_attempt)
        elif latest_status == "PASS" and oldest_status == "PASS":
            battle.append(latest_attempt)
        elif latest_status == "PASS":
            theoretical.append(latest_attempt)
        else:
            theoretical.append(latest_attempt)

    lines = [
        f"# Dogfood scorecard — {slug} ({_today_str()})",
        "",
        f"Source log: `{latest}`",
        "",
    ]

    def _bucket(title: str, items: list[dict]) -> None:
        lines.append(f"## {title} ({len(items)})")
        if not items:
            lines.append("- (none)")
        else:
            for it in items:
                extra = f" — {it['finding']}" if it.get("finding") else ""
                lines.append(f"- Station {it['idx']} — {it['name']} [{it['status']}]{extra}")
        lines.append("")

    _bucket("Battle-tested", battle)
    _bucket("Theoretical", theoretical)
    _bucket("Broke", broke)
    _bucket("Deferred", deferred)

    lines.append("## Next polish actions")
    if not broke:
        lines.append("- (no BROKE items)")
    else:
        for it in broke:
            lines.append(f"- Station {it['idx']} ({it['name']}): repair `{it['repair']}`")
    lines.append("")

    out_path = DOGFOOD_DIR / f"scorecard-{slug}-{_today_str()}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"# wrote: {out_path}")
    return len(broke)

def cmd_doctor(args: argparse.Namespace) -> int:
    checks: list[tuple[str, bool, str]] = []
    slug = _read_active_slug()
    if slug:
        checks.append(("active pointer", True, f"slug={slug}"))
        entry = _backlog_path_for(slug)
        checks.append(("backlog entry exists", bool(entry),
                       str(entry) if entry else f"no entry with slug={slug} in {BACKLOG_DIR}"))
    else:
        checks.append(("active pointer", False, f"empty: {ACTIVE_POINTER}"))

    paired = [
        ("bootstrap script", BOOTSTRAP_SCRIPT),
        ("preflight script", PREFLIGHT_SCRIPT),
        ("product-docs-skill", PRODUCT_DOCS_RUN),
        ("email-drip skill", EMAIL_DRIP_RUN),
        ("growth-dashboard skill", GROWTH_DASHBOARD_RUN),
        ("measurement template", MEASUREMENT_DIR / "_template.yaml"),
        ("lifecycle template", LIFECYCLE_DIR / "_drip-template.yaml"),
        ("backlog dir", BACKLOG_DIR),
        ("dogfood dir", DOGFOOD_DIR),
    ]
    for name, path in paired:
        ok = path.exists()
        checks.append((name, ok, str(path) if ok else f"missing: {path}"))

    if slug:
        m_path = MEASUREMENT_DIR / f"{slug}.yaml"
        if m_path.exists():
            try:
                yaml.safe_load(m_path.read_text(encoding="utf-8"))
                checks.append(("measurement YAML parses", True, str(m_path)))
            except yaml.YAMLError as e:
                checks.append(("measurement YAML parses", False, f"{m_path}: {e}"))
        else:
            checks.append(("measurement YAML parses", False, f"not yet created: {m_path}"))

    print("# dogfood-walkthrough doctor")
    fail = 0
    for name, ok, detail in checks:
        marker = "OK " if ok else "FAIL"
        print(f"  [{marker}] {name} — {detail}")
        if not ok:
            fail += 1
    print()
    if fail:
        print(f"{fail} check(s) failed. Resolve before running `walk`.")
        return 1
    print("all checks passed.")
    return 0

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dogfood-walkthrough", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    p_pick = sub.add_parser("pick", help="rank backlog candidates; --confirm <slug> writes _active.txt")
    p_pick.add_argument("--confirm", metavar="SLUG", help="write slug to _active.txt")
    p_pick.set_defaults(func=cmd_pick)
    p_walk = sub.add_parser("walk", help="run 8-station walkthrough against active slug")
    p_walk.add_argument("--station", type=int, help="start from station N (1-indexed), run through 8")
    p_walk.add_argument("--only", type=int, help="run ONLY station N (1-indexed), single-station execution")
    p_walk.add_argument("--resume", action="store_true",
                        help="continue from last incomplete OR re-attempt last BROKE station")
    p_walk.add_argument("--override", metavar="REASON", help="force past a BROKE finding")
    p_walk.set_defaults(func=cmd_walk)
    p_repair = sub.add_parser("repair", help="open latest BROKE repair-needed pointer in $EDITOR")
    p_repair.set_defaults(func=cmd_repair)
    p_score = sub.add_parser("scorecard", help="emit readiness scorecard from latest log")
    p_score.set_defaults(func=cmd_scorecard)
    p_doc = sub.add_parser("doctor", help="pre-flight: pointer + paired skills + measurement YAML")
    p_doc.set_defaults(func=cmd_doctor)
    return p

def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)

if __name__ == "__main__":
    sys.exit(main())
