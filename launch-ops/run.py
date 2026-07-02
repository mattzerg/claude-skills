#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:
    sys.stderr.write("ERROR: PyYAML required (pip install pyyaml)\n")
    sys.exit(2)


HOME = Path.home()
VAULT_ROOT = HOME / "Obsidian/Zerg/MattZerg"
GROWTH_ROOT = VAULT_ROOT / "Projects" / "Zerg-Production" / "Growth"
LAUNCHES_DIR = GROWTH_ROOT / "launches"
MEASUREMENT_DIR = GROWTH_ROOT / "measurement"
ZERG_ROOT = HOME / "zerg"
SKILLS_ROOT = HOME / ".claude" / "skills"
PRODUCT_DOCS_PY = SKILLS_ROOT / "product-docs-skill" / "run.py"

ZERGLYTICS_BASE = "https://zerglytics.com"
ZERGLYTICS_TIMEOUT = 8
SUBPROCESS_TIMEOUT = 60

SEV_HIGH = "HIGH"
SEV_MED = "MED"
SEV_PASS = "PASS"
SEV_INFO = "INFO"


@dataclass
class Finding:
    gate_id: str
    severity: str
    message: str
    source: str
    title: str = ""


@dataclass
class CheckResult:
    slug: str
    findings: List[Finding] = field(default_factory=list)
    missing_inputs: List[str] = field(default_factory=list)

    def add(self, gate_id: str, severity: str, message: str, source: str, title: str = "") -> None:
        self.findings.append(Finding(gate_id, severity, message, source, title))

    def any_high(self) -> bool:
        return any(f.severity == SEV_HIGH for f in self.findings)


GATE_CATALOG: List[Tuple[str, str, str, str]] = [
    ("G1", "product-docs-present", SEV_HIGH, "canonical-patterns.md §17"),
    ("G2", "measurement-spec-present", SEV_HIGH, "canonical-patterns.md §16"),
    ("G3", "kill_readiness_gate green", SEV_HIGH, "canonical-patterns.md §16"),
    ("G11", "quote-engineering", SEV_HIGH, "launch_distribution_playbook.md gate 11"),
    ("G12", "waitlist-share-CTA", SEV_HIGH, "launch_distribution_playbook.md gate 12"),
    ("G13", "utm-instrumented-links", SEV_HIGH, "launch_distribution_playbook.md gate 13"),
    ("G14", "quote-post-wave-plan", SEV_HIGH, "launch_distribution_playbook.md gate 14"),
    ("G15", "asset-format-match", SEV_HIGH, "launch_distribution_playbook.md gate 15"),
    ("G16", "reposter-DMs-drafted", SEV_HIGH, "launch_distribution_playbook.md gate 16"),
    ("G17", "cadence-calendar-entry", SEV_HIGH, "launch_distribution_playbook.md gate 17"),
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_yaml(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(read_text(path)) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root is not a mapping: {path}")
    return data


def keychain_zerglytics_api_key() -> Optional[str]:
    try:
        res = subprocess.run(
            ["security", "find-generic-password", "-a", "matt", "-s", "ZERGLYTICS_API_KEY", "-w"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if res.returncode == 0:
        key = (res.stdout or "").strip()
        return key or None
    return None


def zerglytics_event_count(event: str, days: int, api_key: Optional[str]) -> Tuple[Optional[int], Optional[str]]:
    qs = urllib.parse.urlencode({"days": days})
    url = f"{ZERGLYTICS_BASE}/api/v1/stats/{urllib.parse.quote(event)}?{qs}"
    req = urllib.request.Request(url)
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(req, timeout=ZERGLYTICS_TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return None, f"URLError: {e.reason}"
    except (TimeoutError, OSError) as e:
        return None, f"network: {e}"
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None, "non-JSON response"
    count = payload.get("count") if isinstance(payload, dict) else None
    if isinstance(count, int):
        return count, None
    return None, "missing 'count' field"


def gate_product_docs(result: CheckResult, slug: str) -> None:
    if not PRODUCT_DOCS_PY.is_file():
        result.add(
            "G1", SEV_HIGH, f"product-docs-skill/run.py missing at {PRODUCT_DOCS_PY}",
            GATE_CATALOG[0][3], "product-docs-present",
        )
        return
    try:
        res = subprocess.run(
            [sys.executable, str(PRODUCT_DOCS_PY), "audit", slug],
            capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        result.add("G1", SEV_HIGH, f"product-docs audit timed out after {SUBPROCESS_TIMEOUT}s",
                   GATE_CATALOG[0][3], "product-docs-present")
        return
    if res.returncode == 0:
        result.add("G1", SEV_PASS, "product-docs audit returned 0 HIGH findings",
                   GATE_CATALOG[0][3], "product-docs-present")
        return
    out = (res.stdout or res.stderr or "").strip().splitlines()
    snippet = next((ln for ln in out if ln.strip()), f"rc={res.returncode}")
    result.add("G1", SEV_HIGH, f"product-docs audit failed: {snippet[:200]}",
               GATE_CATALOG[0][3], "product-docs-present")


def required_event_names(slug: str) -> List[str]:
    return [
        f"{slug}_signup",
        f"{slug}_aha",
        f"{slug}_pro_upgrade",
        f"{slug}_bundle_upgrade",
        f"{slug}_last_active_at",
        f"{slug}_churn_risk",
    ]


def gate_measurement_spec(result: CheckResult, slug: str, measurement: Dict[str, Any], checklist_path: Path) -> None:
    src = GATE_CATALOG[1][3]
    title = "measurement-spec-present"
    req_names = set(required_event_names(slug))
    declared = set()
    for evt in measurement.get("required_events") or []:
        if isinstance(evt, dict) and isinstance(evt.get("name"), str):
            declared.add(evt["name"])
    missing = sorted(req_names - declared)
    if missing:
        result.add("G2", SEV_HIGH, f"measurement YAML missing required events: {', '.join(missing)}", src, title)
        return
    if not checklist_path.is_file():
        result.add("G2", SEV_HIGH, f"checklist missing at {checklist_path}", src, title)
        return
    text = read_text(checklist_path)
    unchecked = re.findall(r"^\s*-\s*\[\s\]", text, flags=re.MULTILINE)
    if unchecked:
        result.add("G2", SEV_HIGH, f"checklist has {len(unchecked)} unchecked box(es)", src, title)
        return
    result.add("G2", SEV_PASS, "measurement YAML + checklist complete (all 6 required events declared, 0 unchecked boxes)",
               src, title)


def gate_kill_readiness(result: CheckResult, measurement: Dict[str, Any]) -> None:
    src = GATE_CATALOG[2][3]
    title = "kill_readiness_gate green"
    gate = measurement.get("kill_readiness_gate") or {}
    if not isinstance(gate, dict):
        result.add("G3", SEV_HIGH, "kill_readiness_gate missing or malformed in measurement YAML", src, title)
        return
    must_emit = gate.get("must_emit_in_prod") or []
    min_events = gate.get("min_events_24h", 1)
    if not isinstance(must_emit, list) or not must_emit:
        result.add("G3", SEV_HIGH, "kill_readiness_gate.must_emit_in_prod is empty", src, title)
        return
    phase = str(measurement.get("launch_phase") or "").strip().lower()
    if phase == "pre-launch":
        result.add(
            "G3", SEV_MED,
            f"pre-launch; informational (will block on launch_phase=shipped transition). events: {', '.join(must_emit)}",
            src, title,
        )
        return
    api_key = keychain_zerglytics_api_key()
    failing: List[str] = []
    unreachable: List[str] = []
    passing: List[str] = []
    for evt in must_emit:
        count, err = zerglytics_event_count(str(evt), days=1, api_key=api_key)
        if err is not None:
            unreachable.append(f"{evt} ({err})")
            continue
        if count is None or count < int(min_events):
            failing.append(f"{evt}={count}")
        else:
            passing.append(f"{evt}={count}")
    if unreachable and not failing and not passing:
        result.add(
            "G3", SEV_MED,
            f"could not verify — Zergalytics unreachable for: {', '.join(unreachable)}",
            src, title,
        )
        return
    if unreachable:
        result.add(
            "G3", SEV_MED,
            f"partial verify — unreachable: {', '.join(unreachable)}; passing: {', '.join(passing) or 'none'}; failing: {', '.join(failing) or 'none'}",
            src, title,
        )
        return
    if failing:
        result.add(
            "G3", SEV_HIGH,
            f"events below min_events_24h={min_events}: {', '.join(failing)}",
            src, title,
        )
        return
    result.add("G3", SEV_PASS, f"all must_emit_in_prod events ≥{min_events}/24h: {', '.join(passing)}", src, title)


def manifest_present(pack_dir: Path) -> bool:
    return (pack_dir / "manifest.md").is_file()


def file_mentions(path: Path, patterns: List[str]) -> bool:
    if not path.is_file():
        return False
    text = read_text(path).lower()
    return any(p.lower() in text for p in patterns)


def gate_quote_engineering(result: CheckResult, brief_path: Path, announcement_path: Path) -> None:
    src = GATE_CATALOG[3][3]
    title = "quote-engineering"
    if not announcement_path.is_file():
        result.add("G11", SEV_MED, "announcement.md not yet produced by launch-pack", src, title)
        return
    patterns = ["quote", "“", "\"", "—"]
    has_quote = file_mentions(announcement_path, ["quote:", "quotes:", "“", "\""])
    has_no_quote_note = file_mentions(brief_path, ["no quotes", "does not warrant quotes", "no-quote"])
    if has_quote or has_no_quote_note:
        result.add("G11", SEV_PASS, "quote markers present in announcement or no-quote decision noted in brief", src, title)
    else:
        result.add("G11", SEV_HIGH, "no quotes detected in announcement.md and no explicit no-quote decision in brief", src, title)


def gate_waitlist_share(result: CheckResult, brief_path: Path, announcement_path: Path) -> None:
    src = GATE_CATALOG[4][3]
    title = "waitlist-share-CTA"
    if not announcement_path.is_file():
        result.add("G12", SEV_MED, "announcement.md not yet produced by launch-pack", src, title)
        return
    has_waitlist = file_mentions(brief_path, ["waitlist"]) or file_mentions(announcement_path, ["waitlist"])
    if not has_waitlist:
        result.add("G12", SEV_PASS, "no waitlist for this launch; gate not applicable", src, title)
        return
    has_share = file_mentions(announcement_path, ["share", "move up", "share-to-move-up"])
    if has_share:
        result.add("G12", SEV_PASS, "waitlist + share-to-move-up CTA detected", src, title)
    else:
        result.add("G12", SEV_HIGH, "waitlist present but share-to-move-up CTA missing from announcement", src, title)


def gate_utm_links(result: CheckResult, distribution_path: Path) -> None:
    src = GATE_CATALOG[5][3]
    title = "utm-instrumented-links"
    if not distribution_path.is_file():
        result.add("G13", SEV_MED, "distribution.md not yet produced by launch-pack", src, title)
        return
    text = read_text(distribution_path).lower()
    if "utm_source=" in text or "utm_medium=" in text or "utm_campaign=" in text:
        result.add("G13", SEV_PASS, "UTM parameters present in distribution.md", src, title)
    else:
        result.add("G13", SEV_HIGH, "no utm_source/utm_medium/utm_campaign tokens found in distribution.md", src, title)


def gate_quote_post_wave(result: CheckResult, distribution_path: Path) -> None:
    src = GATE_CATALOG[6][3]
    title = "quote-post-wave-plan"
    if not distribution_path.is_file():
        result.add("G14", SEV_MED, "distribution.md not yet produced by launch-pack", src, title)
        return
    text = read_text(distribution_path).lower()
    if "quote-post" in text or "quote post" in text or "day-2" in text or "day 2" in text:
        result.add("G14", SEV_PASS, "quote-post wave plan referenced in distribution.md", src, title)
    else:
        result.add("G14", SEV_HIGH, "no quote-post / Day-2 wave plan found in distribution.md", src, title)


def gate_asset_format(result: CheckResult, pack_dir: Path) -> None:
    src = GATE_CATALOG[7][3]
    title = "asset-format-match"
    assets_dir = pack_dir / "assets"
    if not assets_dir.is_dir():
        result.add("G15", SEV_MED, "assets/ directory not yet produced (blog-imagery skill manual step)", src, title)
        return
    images = [p for p in assets_dir.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}]
    if not images:
        result.add("G15", SEV_HIGH, "assets/ exists but contains no image files", src, title)
        return
    result.add("G15", SEV_PASS, f"{len(images)} asset file(s) present in assets/", src, title)


def gate_reposter_dms(result: CheckResult, pack_dir: Path) -> None:
    src = GATE_CATALOG[8][3]
    title = "reposter-DMs-drafted"
    social_dir = pack_dir / "social"
    if not social_dir.is_dir():
        result.add("G16", SEV_MED, "social/ directory not yet produced by social-distribution agent", src, title)
        return
    drafts = list(social_dir.glob("*.md"))
    if not drafts:
        result.add("G16", SEV_HIGH, "social/ exists but contains no draft .md files", src, title)
        return
    result.add("G16", SEV_PASS, f"{len(drafts)} social draft(s) present in social/", src, title)


def gate_cadence_calendar(result: CheckResult, brief_path: Path, distribution_path: Path) -> None:
    src = GATE_CATALOG[9][3]
    title = "cadence-calendar-entry"
    sources_present = [p for p in (brief_path, distribution_path) if p.is_file()]
    if not sources_present:
        result.add("G17", SEV_MED, "brief + distribution.md not yet produced", src, title)
        return
    keys = ["t+1", "t+3", "t+7", "t+30"]
    hits: List[str] = []
    for p in sources_present:
        text = read_text(p).lower()
        for k in keys:
            if k in text and k not in hits:
                hits.append(k)
    if len(hits) >= 2:
        result.add("G17", SEV_PASS, f"cadence touchpoints found: {', '.join(hits)}", src, title)
    else:
        result.add("G17", SEV_HIGH, f"cadence touchpoints insufficient (found {hits or 'none'}; need ≥2 of T+1/T+3/T+7/T+30)", src, title)


def run_check(slug: str) -> Tuple[CheckResult, int]:
    result = CheckResult(slug=slug)

    brief_path = LAUNCHES_DIR / f"{slug}.md"
    measurement_path = MEASUREMENT_DIR / f"{slug}.yaml"
    checklist_path = MEASUREMENT_DIR / f"{slug}.checklist.md"
    pack_dir = LAUNCHES_DIR / slug
    announcement_path = pack_dir / "announcement.md"
    distribution_path = pack_dir / "distribution.md"

    if not brief_path.is_file():
        result.missing_inputs.append(f"brief not found: {brief_path}")
    if not measurement_path.is_file():
        result.missing_inputs.append(f"measurement YAML not found: {measurement_path}")
    if not checklist_path.is_file():
        result.missing_inputs.append(f"measurement checklist not found: {checklist_path}")
    if result.missing_inputs:
        return result, 2

    try:
        measurement = load_yaml(measurement_path)
    except (yaml.YAMLError, ValueError) as e:
        result.missing_inputs.append(f"measurement YAML parse error: {e}")
        return result, 2

    gate_product_docs(result, slug)
    gate_measurement_spec(result, slug, measurement, checklist_path)
    gate_kill_readiness(result, measurement)
    gate_quote_engineering(result, brief_path, announcement_path)
    gate_waitlist_share(result, brief_path, announcement_path)
    gate_utm_links(result, distribution_path)
    gate_quote_post_wave(result, distribution_path)
    gate_asset_format(result, pack_dir)
    gate_reposter_dms(result, pack_dir)
    gate_cadence_calendar(result, brief_path, distribution_path)

    exit_code = 1 if result.any_high() else 0
    return result, exit_code


def format_text(result: CheckResult, exit_code: int) -> str:
    lines: List[str] = [f"launch-ops check — {result.slug}"]
    if result.missing_inputs:
        lines.append("  MISSING INPUTS:")
        for m in result.missing_inputs:
            lines.append(f"    - {m}")
        lines.append("verdict: FAIL (missing required inputs)")
        return "\n".join(lines)
    for f in result.findings:
        sev = f.severity.ljust(4)
        src = f.source
        lines.append(f"  [{sev}] {f.gate_id} {f.title} ({src}) — {f.message}")
    verdict = "FAIL" if exit_code == 1 else "PASS"
    lines.append(f"verdict: {verdict}")
    return "\n".join(lines)


def format_json(result: CheckResult, exit_code: int) -> str:
    payload = {
        "slug": result.slug,
        "exit_code": exit_code,
        "verdict": "PASS" if exit_code == 0 else ("FAIL" if exit_code == 1 else "MISSING_INPUTS"),
        "missing_inputs": result.missing_inputs,
        "findings": [asdict(f) for f in result.findings],
    }
    return json.dumps(payload, indent=2)


def cmd_list(_args: argparse.Namespace) -> int:
    print("launch-ops gates")
    print()
    print(f"  {'ID':<5} {'severity':<6} {'name':<28} source")
    print(f"  {'--':<5} {'------':<6} {'-' * 28:<28} ------")
    for gid, name, sev, src in GATE_CATALOG:
        print(f"  {gid:<5} {sev:<6} {name:<28} {src}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    slug = args.slug if getattr(args, "slug", None) else args.product
    if not slug:
        sys.stderr.write("ERROR: slug required (positional or --product)\n")
        return 2
    result, exit_code = run_check(slug)
    out = format_json(result, exit_code) if args.json else format_text(result, exit_code)
    print(out)
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="launch-ops",
        description="Deterministic launch-readiness gate runner. Reads brief/measurement/manifest; emits per-gate verdicts.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check", help="Run all gates against a slug.")
    p_check.add_argument("slug", nargs="?", help="Launch slug (matches Growth/launches/<slug>.md)")
    p_check.add_argument("--product", help="Alias for slug (compat with launch-pack runner).")
    p_check.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p_check.set_defaults(func=cmd_check)

    p_list = sub.add_parser("list", help="List all gates with severity + source.")
    p_list.set_defaults(func=cmd_list)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
