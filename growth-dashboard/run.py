#!/usr/bin/env python3
"""Growth dashboard — auto-generate the Monday 7am weekly review.

Usage:
    python3 ~/.claude/skills/growth-dashboard/run.py generate [--week YYYY-WW] [--no-post] [--verbose] [--product slug]
    python3 ~/.claude/skills/growth-dashboard/run.py dry-run [--product slug]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".claude"))
try:
    from action_led_targets.log import log_target  # type: ignore
except ImportError:
    def log_target(*_a, **_k) -> None:
        return None

sys.path.insert(0, str(Path.home() / ".config" / "zerg"))
from vault_path import vault_root, vault_write  # type: ignore  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _render  # type: ignore  # noqa: E402

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None

VAULT = vault_root()
GROWTH_DIR = VAULT / "Projects" / "Zerg-Production" / "Growth"
EXPERIMENTS_DIR = GROWTH_DIR / "experiments"
MEASUREMENT_DIR = GROWTH_DIR / "measurement"
WEEKLY_REL = "Projects/Zerg-Production/Growth/weekly"
PROSPECTS_FILE = GROWTH_DIR / "prospects.md"
CASE_STUDIES_DIR = VAULT / "Clients"  # client-first home since 2026-06-10; case studies live in Clients/<Name>/case-study/
SLACK_SKILL = Path.home() / ".claude" / "skills" / "slack-skill" / "slack_skill.py"
GMAIL_SKILL = Path.home() / ".claude" / "skills" / "gmail-skill" / "gmail_skill.py"
FAILURES_LOG = Path.home() / ".claude" / "skills" / "growth-dashboard" / "logs" / "post-failures.log"
FAKE_MATT_DM = "D0B0T0ETDR8"
FALLBACK_EMAIL = "matteisn@gmail.com"
ZERGLYTICS_BASE = os.environ.get("ZERGLYTICS_BASE_URL", "https://zerglytics.fly.dev")


def parse_yaml_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}
    meta: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip().strip('"')
    return meta


def read_experiments() -> list[dict[str, str]]:
    if not EXPERIMENTS_DIR.exists():
        return []
    out = []
    for f in sorted(EXPERIMENTS_DIR.glob("exp-*.md")):
        if f.name.startswith("_"):
            continue
        meta = parse_yaml_frontmatter(f.read_text())
        if meta.get("id"):
            out.append(meta)
    return out


def days_until(date_str: str) -> int | None:
    try:
        return (dt.date.fromisoformat(date_str) - dt.date.today()).days
    except ValueError:
        return None


def _zerglytics_api_key() -> str | None:
    key = os.environ.get("ZERGLYTICS_API_KEY")
    if key:
        return key.strip()
    try:
        r = subprocess.run(
            ["security", "find-generic-password", "-a", "matt", "-s", "ZERGLYTICS_API_KEY", "-w"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return None


def zerglytics_call(path: str, params: dict) -> dict:
    key = _zerglytics_api_key()
    if not key:
        raise RuntimeError(
            "Set ZERGLYTICS_API_KEY in env or "
            "`security add-generic-password -a matt -s ZERGLYTICS_API_KEY -w <key>`"
        )
    qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    url = f"{ZERGLYTICS_BASE.rstrip('/')}{path}" + (f"?{qs}" if qs else "")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
            last_err = e
            if attempt < 2:
                time.sleep(1.0)
    raise RuntimeError(f"zerglytics {path} failed: {last_err}")


def _shallow_yaml(text: str) -> dict:
    out: dict = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line or line.startswith(" ") or ":" not in line:
            continue
        k, _, v = line.partition(":")
        v = v.strip()
        if v and not v.startswith("["):
            out[k.strip()] = v.strip('"').strip("'")
    return out


def load_measurement_specs() -> dict[str, dict]:
    if not MEASUREMENT_DIR.exists():
        return {}
    specs: dict[str, dict] = {}
    for f in sorted(MEASUREMENT_DIR.glob("*.yaml")):
        if f.name.startswith("_"):
            continue
        try:
            text = f.read_text()
            spec = (yaml.safe_load(text) or {}) if yaml else _shallow_yaml(text)
        except Exception as e:  # noqa: BLE001
            print(f"WARN: failed to parse {f.name}: {e}", file=sys.stderr)
            continue
        slug = spec.get("product_id") or f.stem
        if slug and not str(slug).startswith("PLACEHOLDER"):
            specs[str(slug)] = spec
    return specs


def _todo(slug: str, evt: str, why: str = "not yet emitting") -> str:
    return f"(no data — TODO: {slug}_{evt} {why})"


def _safe_call(path: str, params: dict, verbose: bool) -> dict | None:
    try:
        return zerglytics_call(path, params)
    except RuntimeError as e:
        if verbose:
            print(f"WARN: {e}", file=sys.stderr)
        return None


def _sum_stats(payload: dict | None, event: str) -> int | None:
    if not payload:
        return None
    # New per-event endpoint: /api/v1/stats/<event> returns {"count": N, ...}
    c = payload.get("count")
    if isinstance(c, (int, float)):
        return int(c)
    # Backward-compat: old dashboard payload shape (top-12 goals list)
    stats = payload.get("stats") or payload.get("totals") or {}
    if isinstance(stats, dict):
        for k in (event, "count", "pageviews", "visitors"):
            v = stats.get(k)
            if isinstance(v, (int, float)):
                return int(v)
    for g in (payload.get("goals") or []):
        if isinstance(g, dict) and g.get("name") == event:
            cc = g.get("count") or g.get("visitors")
            if isinstance(cc, (int, float)):
                return int(cc)
    return None


def _binding(spec: dict, key: str, default):
    return (spec.get("dashboard_bindings") or {}).get(key, default)


def _events_for(slug: str, spec: dict, line_key: str, default_events: list[str]) -> list[str]:
    val = _binding(spec, line_key, None)
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        return [val]
    return default_events


def _stat_line(specs, verbose, num: int, label: str, line_key: str, default_evts, todo_evt: str) -> str:
    if not specs:
        return f"{num}. **{label}:** _(no measurement specs yet — populate Growth/measurement/<slug>.yaml)_"
    parts: list[str] = []
    total, saw_any = 0, False
    for slug, spec in specs.items():
        events = _events_for(slug, spec, line_key, [e.format(slug=slug) for e in default_evts])
        ptotal, psaw = 0, False
        for evt in events:
            c = _sum_stats(_safe_call(f"/api/v1/stats/{urllib.parse.quote(evt, safe='')}", {"days": 7}, verbose), evt)
            if c is not None:
                psaw = True; ptotal += c
        if not psaw:
            parts.append(f"   - {slug}: {_todo(slug, todo_evt)}")
        else:
            saw_any = True; total += ptotal
            parts.append(f"   - {slug}: {ptotal}")
    header = f"{num}. **{label} (7d):** {total} total" if saw_any else f"{num}. **{label} (7d):**"
    return "\n".join([header, *parts])


def _breakdown_line(specs, verbose, num: int, label: str, event_tmpl: str, dim: str, top: int,
                    fmt_row, empty_msg: str) -> str:
    if not specs:
        return f"{num}. **{label}:** _(no measurement specs yet)_"
    parts = [f"{num}. **{label}:**"]
    saw_any = False
    for slug, spec in specs.items():
        binding = _binding(spec, f"line_{num}_top_sources" if num == 4 else "", {}) if num == 4 else {}
        event = (binding or {}).get("event", event_tmpl.format(slug=slug)) if isinstance(binding, dict) else event_tmpl.format(slug=slug)
        eff_top = (binding or {}).get("top", top) if isinstance(binding, dict) else top
        eff_dim = (binding or {}).get("dim", dim) if isinstance(binding, dict) else dim
        payload = _safe_call("/api/v1/breakdown", {"event": event, "dim": eff_dim, "days": 7, "top": eff_top}, verbose)
        if not payload:
            parts.append(f"   - {slug}: {_todo(slug, 'signup_breakdown')}"); continue
        results = payload.get("results") or []
        if not results:
            parts.append(f"   - {slug}: {_todo(slug, 'signup', 'no signups in window')}"); continue
        saw_any = True
        parts.append(f"   - {slug}: {fmt_row(results, eff_top)}")
    if not saw_any and len(parts) == 1:
        return f"{num}. **{label}:** _({empty_msg})_"
    return "\n".join(parts)


def line_1_activated(specs, verbose):
    return _stat_line(specs, verbose, 1, "Activated accounts this week", "line_1_activated_accounts",
                      ["{slug}_aha"], "aha")


def line_2_paid(specs, verbose):
    return _stat_line(specs, verbose, 2, "Paid conversions", "line_2_paid_conversions",
                      ["{slug}_pro_upgrade", "{slug}_bundle_upgrade"], "pro/bundle_upgrade")


def line_3_activation_rate(specs, verbose):
    if not specs:
        return "3. **Activation rate:** _(no measurement specs yet)_"
    parts = ["3. **Activation rate (signed-up → activated, 7d):**"]
    saw_any = False
    for slug, spec in specs.items():
        domain = spec.get("zerglytics_domain")
        if not domain:
            parts.append(f"   - {slug}: (no zerglytics_domain in spec)"); continue
        payload = _safe_call("/api/site/funnel", {"domain": domain, "funnel": "acquisition", "days": 7}, verbose)
        steps = (payload or {}).get("steps") or (payload or {}).get("funnel") or []
        if isinstance(steps, list) and len(steps) >= 2:
            first = steps[0].get("count") if isinstance(steps[0], dict) else None
            last = steps[-1].get("count") if isinstance(steps[-1], dict) else None
            if isinstance(first, (int, float)) and first > 0 and isinstance(last, (int, float)):
                parts.append(f"   - {slug}: {100.0 * last / first:.1f}% ({int(last)}/{int(first)})")
                saw_any = True; continue
        parts.append(f"   - {slug}: {_todo(slug, 'acquisition_funnel')}")
    if not saw_any and len(parts) == 1:
        return "3. **Activation rate:** _(no funnel data)_"
    return "\n".join(parts)


def line_4_top_sources(specs, verbose):
    return _breakdown_line(
        specs, verbose, 4, "Top 3 sources by signups (7d)", "{slug}_signup", "utm_source", 3,
        lambda results, top: ", ".join(f"{r.get('value')}({r.get('count')})" for r in results[:top]),
        "no signup breakdown data",
    )


def line_9_email(specs, verbose):
    return _breakdown_line(
        specs, verbose, 9, "Email program health (drip state breakdown, 7d)",
        "{slug}_signup", "email_drip_state", 10,
        lambda results, top: ", ".join(f"{r.get('value')}={r.get('count')}" for r in results),
        "no drip-state data",
    )


def line_10_referral(specs, verbose):
    def fmt(results, _top):
        total = sum(int(r.get("count", 0)) for r in results)
        referral = sum(int(r.get("count", 0)) for r in results if r.get("value") == "referral")
        return f"{referral}/{total} ({100.0 * referral / total:.1f}%)" if total else "no signups"
    return _breakdown_line(
        specs, verbose, 10, "Referral metrics (referral signups / total signups, 7d)",
        "{slug}_signup", "utm_medium", 50, fmt, "no signup data",
    )


def line_content_distribution() -> str:
    return _render.content_distribution_line(VAULT)


def line_active_experiments() -> str:
    running = [r for r in read_experiments() if r.get("status") == "running"]
    if not running:
        return "5. **Active experiments:** 0 in flight. Floor is 2 — flag RED."
    parts = [f"5. **Active experiments:** {len(running)} in flight"]
    for r in running:
        d = days_until(r.get("kill_date", ""))
        d_str = f"{d}d" if d is not None else "?"
        parts.append(f"   - {r['id']} ({r.get('name', '?')}): kill in {d_str} | metric={r.get('success_metric', '?')} | thresh={r.get('success_threshold', '?')}")
    return "\n".join(parts)


def line_solutions_pipeline() -> str:
    if not PROSPECTS_FILE.exists():
        return "6. **Solutions pipeline:** (no prospects.md found — TODO)"
    txt = PROSPECTS_FILE.read_text()
    stages = {"inbound": 0, "qualified": 0, "scoped": 0, "proposal-out": 0, "won": 0, "lost": 0}
    for ln in txt.splitlines():
        if not (ln.startswith("|") and not ln.startswith("|---") and "Stage" not in ln and "_(populate" not in ln):
            continue
        cells = [c.strip() for c in ln.split("|")[1:-1]]
        if len(cells) >= 2 and cells[1] in stages:
            stages[cells[1]] += 1
    total = sum(stages.values())
    if total == 0:
        return "6. **Solutions pipeline:** 0 prospects (Phase 1 — populating via `network-reach`)"
    qual_plus = sum(stages[s] for s in ("qualified", "scoped", "proposal-out", "won"))
    return (f"6. **Solutions pipeline:** {total} total | qualified+ {qual_plus} | "
            f"proposal-out {stages['proposal-out']} | won {stages['won']} | lost {stages['lost']}")


def line_case_studies() -> str:
    if not CASE_STUDIES_DIR.exists():
        return "7. **Case-study-in-flight:** (no Case-Studies dir found — TODO)"
    rows: list[tuple[str, str, str]] = []
    for f in sorted(CASE_STUDIES_DIR.glob("*/case-study/*.md")):
        if f.name.startswith("_"):
            continue
        txt = f.read_text()
        status_m = re.search(r"\*\*Status:\*\*\s*(\w+)", txt)
        nda_m = re.search(r"\*\*NDA:\*\*\s*([\w-]+)", txt)
        rows.append((f.stem, status_m.group(1) if status_m else "unknown", nda_m.group(1) if nda_m else "?"))
    drift = [r for r in rows if r[1] == "unknown" or r[2] in ("?", "unverified")]
    header = (f"7. **Case-study-in-flight:** 🔴 {len(drift)}/{len(rows)} briefs in drift (status=unknown or NDA unverified)"
              if rows and len(drift) >= max(2, len(rows) // 2) else "7. **Case-study-in-flight:**")
    return "\n".join([header, *[f"   - {c}: status={s} nda={n}" for c, s, n in rows]])


def render_dashboard(week_label: str, verbose: bool, for_slack: bool, product_filter: str | None) -> str:
    specs = load_measurement_specs()
    if product_filter:
        specs = {k: v for k, v in specs.items() if k == product_filter}
    raw_lines = [
        line_1_activated(specs, verbose),
        line_2_paid(specs, verbose),
        line_3_activation_rate(specs, verbose),
        line_4_top_sources(specs, verbose),
        line_active_experiments(),
        line_solutions_pipeline(),
        line_case_studies(),
        line_content_distribution(),
        line_9_email(specs, verbose),
        line_10_referral(specs, verbose),
        "11. **Open question of the week:** _(Matt fills weekly)_",
    ]
    return _render.assemble(week_label, raw_lines, for_slack, log_target)


def _record_post_failure(week_label: str, err: str, content: str) -> None:
    FAILURES_LOG.parent.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().isoformat(timespec="seconds")
    with FAILURES_LOG.open("a") as f:
        f.write(f"\n=== {ts} — {week_label} — Slack post FAILED ===\n")
        f.write(f"error: {err[:500]}\ncontent_len: {len(content)} chars\n")
        f.write(f"vault_file: Growth/weekly/{dt.date.today().isoformat()}.md\n")


def _email_fallback(week_label: str, err: str) -> None:
    if not GMAIL_SKILL.exists():
        return
    subject = f"[Growth Dashboard] Slack post FAILED — {week_label}"
    body = (f"The Monday weekly growth dashboard post failed to land in Slack.\n\n"
            f"Week: {week_label}\nError: {err[:500]}\n"
            f"Vault file (still written): MattZerg/Projects/Zerg-Production/Growth/weekly/{dt.date.today().isoformat()}.md\n")
    try:
        subprocess.run(["python3", str(GMAIL_SKILL), "send", "--to", FALLBACK_EMAIL,
                        "--subject", subject, "--body", body],
                       check=True, capture_output=True, text=True, timeout=30)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass


def post_to_slack(content: str, week_label: str) -> bool:
    if not SLACK_SKILL.exists():
        _record_post_failure(week_label, "slack-skill not found", content)
        return False
    body = content[:35000] + ("\n\n_(truncated — see full file in vault)_" if len(content) > 35000 else "")
    msg = f"📊 Growth dashboard — {week_label}\n\n```\n{body}\n```"
    last_err = ""
    for attempt, delay in enumerate([0, 5, 25], start=1):
        if delay:
            time.sleep(delay)
        try:
            subprocess.run(["python3", str(SLACK_SKILL), "send", FAKE_MATT_DM, "-m", msg],
                           check=True, capture_output=True, text=True, timeout=30)
            if attempt > 1:
                print(f"INFO: Slack post succeeded on attempt {attempt}.", file=sys.stderr)
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            last_err = (e.stderr if hasattr(e, "stderr") and e.stderr else str(e)) or "unknown"
            print(f"WARN: Slack attempt {attempt} failed: {last_err[:200]}", file=sys.stderr)
    _record_post_failure(week_label, last_err, content)
    _email_fallback(week_label, last_err)
    return False


def _week_label() -> str:
    y, w, _ = dt.date.today().isocalendar()
    return f"{y}-W{w:02d}"


def cmd_generate(args) -> int:
    week_label = args.week or _week_label()
    vault_content = render_dashboard(week_label, args.verbose, False, args.product)
    slack_content = render_dashboard(week_label, args.verbose, True, args.product)
    out_file = vault_write(f"{WEEKLY_REL}/{dt.date.today().isoformat()}.md", vault_content)
    print(f"Wrote {out_file}")
    if not args.no_post and post_to_slack(slack_content, week_label):
        print(f"Posted to Slack DM {FAKE_MATT_DM}.")
    return 0


def cmd_dry_run(args) -> int:
    print(render_dashboard(args.week or _week_label(), args.verbose, False, args.product))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="growth-dashboard", description=__doc__)
    sub = p.add_subparsers(dest="verb")
    for verb, fn in (("generate", cmd_generate), ("dry-run", cmd_dry_run)):
        sp = sub.add_parser(verb)
        sp.add_argument("--week")
        sp.add_argument("--verbose", action="store_true")
        sp.add_argument("--product")
        if verb == "generate":
            sp.add_argument("--no-post", action="store_true")
        sp.set_defaults(fn=fn)
    args = p.parse_args()
    if not args.verb:
        return cmd_generate(argparse.Namespace(week=None, verbose=False, product=None, no_post=False))
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
