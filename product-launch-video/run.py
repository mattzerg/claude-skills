#!/usr/bin/env python3
"""product-launch-video: plan / audit / list per-launch video plans."""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("error: PyYAML is required (pip install pyyaml)", file=sys.stderr)
    sys.exit(2)

HOME = Path.home()
VAULT = HOME / "Obsidian/Zerg"
GROWTH = VAULT / "MattZerg/Projects/Zerg-Production/Growth"
LAUNCHES_DIR = GROWTH / "launches"
MEASUREMENT_DIR = GROWTH / "measurement"
ZERG_PRODUCTS = HOME / "zerg"
SLUG_RE = re.compile(r"[a-z0-9][a-z0-9-]*")


def _err(msg: str, code: int = 1) -> int:
    print(f"error: {msg}", file=sys.stderr)
    return code


def _default_shot_list(slug): return ZERG_PRODUCTS / slug / "demo-video" / "shot-list.template.json"
def _default_brief(slug):     return LAUNCHES_DIR / f"{slug}.md"
def _default_measurement(slug): return MEASUREMENT_DIR / f"{slug}.yaml"
def _default_out(slug):       return LAUNCHES_DIR / slug / "video-plan.md"


def _read_brief_frontmatter(brief_path: Path) -> dict:
    if not brief_path.exists():
        return {}
    text = brief_path.read_text(encoding="utf-8")
    end = text.find("\n---", 3) if text.startswith("---") else -1
    if end < 0:
        return {}
    try:
        data = yaml.safe_load(text[3:end].lstrip("\n")) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def _load_shot_list(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"shot list not found at {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"shot list at {path} is not a JSON object")
    return data


def _load_measurement(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"measurement spec not found at {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"measurement spec at {path} is not a YAML mapping")
    return data


def _resolve_cta_event(measurement: dict, slug: str) -> str:
    gate = measurement.get("kill_readiness_gate") or {}
    must = gate.get("must_emit_in_prod") or []
    if isinstance(must, list) and must and isinstance(must[0], str) and must[0].strip():
        return must[0].strip()
    bindings = measurement.get("dashboard_bindings") or {}
    line1 = bindings.get("line_1_activated_accounts")
    if isinstance(line1, str) and line1.strip():
        return line1.strip()
    return f"{slug.replace('-', '_')}_signup"


def _product_name(shot_list: dict, brief_fm: dict, slug: str) -> str:
    title = shot_list.get("title") or ""
    if isinstance(title, str) and " — " in title:
        cand = title.split(" — ", 1)[0].strip()
        if cand and "{{" not in cand:
            return cand
    name = brief_fm.get("product")
    return name.strip() if isinstance(name, str) and name.strip() else slug.replace("-", " ").title()


def _coerce_int(v) -> int:
    try:
        return int(v) if v is not None else 0
    except (TypeError, ValueError):
        return 0


def _beats_summary(beats) -> tuple[str, int]:
    if not isinstance(beats, list) or not beats:
        return "(no beats found in shot list)", 0
    parts, total = [], 0
    for beat in beats:
        if not isinstance(beat, dict):
            continue
        label = str(beat.get("label") or beat.get("id") or "beat").strip().lower()
        d = _coerce_int(beat.get("duration_s") if beat.get("duration_s") is not None else beat.get("duration_seconds"))
        total += d
        parts.append(f"{label} ({d}s)")
    return " -> ".join(parts), total


def _aspect_summary(shot_list: dict) -> tuple[str, str]:
    primary, secondaries = "9:16", []
    for v in shot_list.get("variants") or []:
        if not isinstance(v, dict):
            continue
        ar = v.get("aspect_ratio")
        if not isinstance(ar, str):
            continue
        if v.get("primary"):
            primary = ar
        else:
            use = v.get("use") or ""
            secondaries.append(f"{ar} ({use})" if use else ar)
    if not secondaries:
        for ar in shot_list.get("aspects") or []:
            if isinstance(ar, str) and ar != primary:
                secondaries.append(ar)
    return primary, ", ".join(secondaries) if secondaries else "n/a"


PLAN_TEMPLATE = """# {product_name} demo video plan

**Source brief:** [{brief_name}]({brief_rel})
**Source shot list:** `{shot_list_path}`
**Generated:** {today} by `product-launch-video/run.py plan`

## Shot list summary
- Total length: {total_s}s
- Beats: {beats_line}
- Primary aspect: {primary_ar} (Twitter/IG/Reels)
- Variants: {secondary_ar}

## Production routing (per video-production-planner doctrine)
- **Hook + Problem + CTA:** Screen Studio for clean screen + camera composite
- **Demo walkthrough:** Screen Studio or ScreenFlow (per video-production-planner.md)
- **Caption rendering:** caption-burn skill

## Target channels (T+0 launch wave)
- Twitter/X: 9:16 vertical (paste-in vid + 280-char hook)
- LinkedIn: 1:1 square + carousel pull
- YouTube Shorts: 9:16
- Instagram Reels: 9:16 (silent-first; captions burned in)
- Threads/Bluesky: 1:1

## Measurement
- CTA event: `{cta_event}` (per `{measurement_rel}`)
- Tracking: shorten target URL with utm_source per channel (utm_medium=video, utm_campaign={slug}-launch-T0)
- Success threshold: 1% CTR per channel (T+7 day rollup)

## Next steps
1. Generate voiceover via eleven-labs-skill (script in shot-list.template.json)
2. Record screens with Screen Studio per beat
3. Assemble with film-maker-skill or video-editing-director routing
4. Run video-review skill before publishing (10 deterministic auto-checks)
"""


def _render_plan(slug, shot_list, brief_fm, brief_path, shot_list_path, cta_event) -> str:
    beats_line, total_s = _beats_summary(shot_list.get("beats") or [])
    if total_s == 0:
        total_s = _coerce_int(shot_list.get("length_s"))
    primary_ar, secondary_ar = _aspect_summary(shot_list)
    return PLAN_TEMPLATE.format(
        product_name=_product_name(shot_list, brief_fm, slug),
        brief_name=brief_path.name, brief_rel=Path("..") / brief_path.name,
        shot_list_path=shot_list_path, today=_dt.date.today().isoformat(),
        total_s=total_s, beats_line=beats_line, primary_ar=primary_ar,
        secondary_ar=secondary_ar, cta_event=cta_event,
        measurement_rel=f"measurement/{slug}.yaml", slug=slug)


def _rp(flag, default): return Path(flag).expanduser() if flag else default


def cmd_plan(args) -> int:
    slug = args.slug
    if not slug or not SLUG_RE.fullmatch(slug):
        return _err(f"invalid slug: {slug!r} (expected kebab-case)")
    shot_list_path = _rp(args.shot_list, _default_shot_list(slug))
    brief_path = _rp(args.brief, _default_brief(slug))
    measurement_path = _rp(args.measurement, _default_measurement(slug))
    out_path = _rp(args.out, _default_out(slug))
    try:
        shot_list = _load_shot_list(shot_list_path)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        return _err(str(exc))
    if not brief_path.exists():
        return _err(f"launch brief not found at {brief_path}")
    try:
        measurement = _load_measurement(measurement_path)
    except (FileNotFoundError, ValueError, yaml.YAMLError) as exc:
        return _err(str(exc))
    rendered = _render_plan(slug, shot_list, _read_brief_frontmatter(brief_path),
                            brief_path, shot_list_path, _resolve_cta_event(measurement, slug))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered, encoding="utf-8")
    print(f"wrote {out_path}")
    return 0


def cmd_audit(args) -> int:
    slug = args.slug
    if not slug or not SLUG_RE.fullmatch(slug):
        return _err(f"invalid slug: {slug!r} (expected kebab-case)")
    plan_path, shot_list_path, measurement_path = _default_out(slug), _default_shot_list(slug), _default_measurement(slug)
    problems, cta_event = [], None
    if not plan_path.exists():
        problems.append(f"missing video-plan.md at {plan_path}")
    if not shot_list_path.exists():
        problems.append(f"missing shot list at {shot_list_path}")
    else:
        try:
            _load_shot_list(shot_list_path)
        except (ValueError, json.JSONDecodeError) as exc:
            problems.append(f"shot list parse error: {exc}")
    if not measurement_path.exists():
        problems.append(f"missing measurement spec at {measurement_path}")
    else:
        try:
            measurement = _load_measurement(measurement_path)
            cta_event = _resolve_cta_event(measurement, slug)
            names = [ev["name"] for ev in (measurement.get("required_events") or [])
                     if isinstance(ev, dict) and isinstance(ev.get("name"), str)]
            if cta_event and names and cta_event not in names:
                problems.append(f"CTA event {cta_event!r} not declared in required_events of {measurement_path.name}")
        except (ValueError, yaml.YAMLError) as exc:
            problems.append(f"measurement parse error: {exc}")
    if plan_path.exists() and cta_event and cta_event not in plan_path.read_text(encoding="utf-8"):
        problems.append(f"video-plan.md does not cite CTA event {cta_event!r}")
    if problems:
        for p in problems:
            print(f"FAIL: {p}", file=sys.stderr)
        return 1
    print(f"PASS: {slug} video plan present and consistent ({plan_path})")
    return 0


def cmd_list(_args) -> int:
    if not LAUNCHES_DIR.exists():
        print(f"(no launches dir at {LAUNCHES_DIR})")
        return 0
    found = sorted(LAUNCHES_DIR.glob("*/video-plan.md"))
    if not found:
        print("(no video plans found)")
        return 0
    for path in found:
        try:
            mtime = _dt.datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")
        except OSError:
            mtime = "?"
        print(f"{path.parent.name}\t{mtime}\t{path}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="product-launch-video",
                                description="Plan, audit, and list per-launch demo video artifacts.")
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("plan", help="Render video-plan.md for a launch slug.")
    sp.add_argument("slug", nargs="?", help="Launch slug (kebab-case).")
    sp.add_argument("--product", dest="slug_flag", help="Alias for slug.")
    sp.add_argument("--shot-list", dest="shot_list")
    sp.add_argument("--brief", dest="brief")
    sp.add_argument("--measurement", dest="measurement")
    sp.add_argument("--out", dest="out")
    sp.set_defaults(func=cmd_plan)
    sa = sub.add_parser("audit", help="Audit an existing video-plan.md for consistency.")
    sa.add_argument("slug", nargs="?", help="Launch slug (kebab-case).")
    sa.add_argument("--product", dest="slug_flag", help="Alias for slug.")
    sa.set_defaults(func=cmd_audit)
    sub.add_parser("list", help="List per-product video plans.").set_defaults(func=cmd_list)
    return p


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    slug_flag = getattr(args, "slug_flag", None)
    if hasattr(args, "slug"):
        if not args.slug and slug_flag:
            args.slug = slug_flag
        if not args.slug and args.cmd in {"plan", "audit"}:
            return _err(f"{args.cmd}: slug is required (positional or --product)")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
