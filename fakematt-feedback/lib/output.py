"""Output writers — Obsidian note (MattZerg/Feedback/) + Slack self-DM digest.

Self-DM channel: D0B109RDJQ6 (Fake Matt's bot).
NEVER auto-post to shared channels — drafts only, into Matt's self-DM.
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
from pathlib import Path
from typing import Any

def _resolve_vault_root() -> Path:
    """Live vault is ~/Obsidian/Zerg/MattZerg; the iCloud path was retired 2026-06-24.
    Prefer the live path, fall back to the legacy iCloud path only if it still exists."""
    primary = Path.home() / "Obsidian" / "Zerg" / "MattZerg"
    if primary.exists():
        return primary
    legacy = (
        Path.home()
        / "Library" / "Mobile Documents" / "iCloud~md~obsidian" / "Documents" / "Zerg" / "MattZerg"
    )
    return legacy if legacy.exists() else primary


VAULT_ROOT = _resolve_vault_root()
FEEDBACK_DIR = VAULT_ROOT / "Feedback"
SCREENSHOT_DIR = FEEDBACK_DIR / "_screenshots"

FAKE_MATT_SELF_DM = "D0B109RDJQ6"
SLACK_SKILL_CONFIG = Path.home() / ".claude" / "skills" / "slack-skill" / "config.json"


def _now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _today_slug() -> str:
    return dt.date.today().strftime("%Y-%m-%d")


def _copy_screenshots_to_vault(findings: list[dict], run_id: str) -> dict[str, str]:
    """Copy referenced screenshots into MattZerg/Feedback/_screenshots/<run_id>/.
    Returns map old_abs_path → vault-relative `_screenshots/...` path for embedding.
    """
    target_dir = SCREENSHOT_DIR / run_id
    target_dir.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, str] = {}
    for f in findings:
        src = (f.get("location") or {}).get("screenshot")
        if not src or src in mapping:
            continue
        src_path = Path(src)
        if not src_path.exists():
            continue
        dst = target_dir / src_path.name
        if not dst.exists():
            try:
                shutil.copy2(src_path, dst)
            except Exception:
                continue
        mapping[src] = f"_screenshots/{run_id}/{src_path.name}"
    return mapping


def _frontmatter(target: str, kind: str, captures: list[Any], findings: list[dict], flows: list[str]) -> str:
    sev_count = {"P0": 0, "P1": 0, "P2": 0}
    for f in findings:
        sev_count[f.get("severity", "P2")] = sev_count.get(f.get("severity", "P2"), 0) + 1
    lines = [
        "---",
        "type: feedback",
        f"target: {target}",
        f"target_kind: {kind}",
        f"reviewed_at: {_now_iso()}",
        f"pages_scanned: {len(captures)}",
        f"total_findings: {len(findings)}",
        f"p0: {sev_count['P0']}",
        f"p1: {sev_count['P1']}",
        f"p2: {sev_count['P2']}",
        f"flows_exercised: [{', '.join(flows)}]" if flows else "flows_exercised: []",
        "---",
    ]
    return "\n".join(lines)


def _principle_provenance_table(findings: list[dict], principle_lookup: dict[str, dict]) -> str:
    seen: dict[str, dict] = {}
    for f in findings:
        for pid in f.get("principle_provenance") or []:
            if pid in principle_lookup and pid not in seen:
                seen[pid] = principle_lookup[pid]
    if not seen:
        return ""
    out = ["## Principle provenance", "", "| ID | Rule | Citation |", "| --- | --- | --- |"]
    for pid, p in sorted(seen.items()):
        out.append(f"| `{pid}` | {p.get('rule','')} | {p.get('citation','')} |")
    return "\n".join(out) + "\n"


def _voice_provenance_table(findings: list[dict], voice_lookup: dict[str, dict]) -> str:
    seen: dict[str, dict] = {}
    for f in findings:
        vid = f.get("voice_provenance")
        if vid and vid in voice_lookup and vid not in seen:
            seen[vid] = voice_lookup[vid]
    if not seen:
        return ""
    out = ["## Voice provenance", "", "| ID | Source | Excerpt |", "| --- | --- | --- |"]
    for vid, q in sorted(seen.items()):
        excerpt = q.get("text", "")[:120].replace("\n", " ").replace("|", "\\|")
        src_path = Path(q.get("source_path", "")).name
        out.append(f"| `{vid}` | {src_path} | {excerpt}… |")
    return "\n".join(out) + "\n"


def write_obsidian_note(
    target: str,
    kind: str,
    captures: list,
    findings: list[dict],
    rejected: list[dict],
    flows: list[str],
    run_id: str,
    voice_lookup: dict[str, dict],
    principle_lookup: dict[str, dict],
    *,
    product_hint: str | None = None,
) -> Path:
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    screenshot_map = _copy_screenshots_to_vault(findings, run_id)

    fm = _frontmatter(target, kind, captures, findings, flows)
    site_wide = [f for f in findings if f.get("is_site_wide")]
    page_specific = [f for f in findings if not f.get("is_site_wide")]
    by_severity: dict[str, list[dict]] = {"P0": [], "P1": [], "P2": []}
    for f in page_specific:
        by_severity.setdefault(f.get("severity", "P2"), []).append(f)

    sev_counts = {"P0": 0, "P1": 0, "P2": 0}
    for f in findings:
        sev_counts[f.get("severity", "P2")] = sev_counts.get(f.get("severity", "P2"), 0) + 1

    body: list[str] = []
    body.append(f"# {product_hint or 'Product'} feedback — {_today_slug()}")
    body.append("")
    body.append(f"**Target.** {target}")
    summary = f"**Pages.** {len(captures)} · **Findings.** {len(findings)} (P0={sev_counts['P0']} P1={sev_counts['P1']} P2={sev_counts['P2']})"
    if site_wide:
        summary += f" · **Site-wide.** {len(site_wide)}"
    body.append(summary)
    body.append("")

    if sev_counts["P0"]:
        # Prefer site-wide P0s + highest-merged in the headline trio
        p0_all = [f for f in findings if f.get("severity") == "P0"]
        p0_all.sort(key=lambda f: (not f.get("is_site_wide", False), -f.get("merged_count", 1)))
        body.append("## If I only fix three things")
        for f in p0_all[:3]:
            tag = " (site-wide)" if f.get("is_site_wide") else ""
            body.append(f"1. **{f.get('finding','').strip()}**{tag}")
            body.append(f"   - Fix: {f.get('suggested_fix','').strip()}")
        body.append("")

    def _render_block(f: dict) -> None:
        sev = f.get("severity", "P2")
        cat = f.get("category", "general")
        mode = f.get("mode")
        mode_tag = f" · {mode}" if mode else ""
        site_tag = " _[site-wide]_" if f.get("is_site_wide") else ""
        body.append(f"### {sev} — {cat}{mode_tag}{site_tag}")
        loc = f.get("location") or {}
        affected = f.get("affected_pages") or []
        if affected:
            body.append(f"**Affected pages ({len(affected)}).**")
            for url in affected[:8]:
                body.append(f"- {url}")
            if len(affected) > 8:
                body.append(f"- …and {len(affected) - 8} more")
        elif loc.get("url"):
            line = f"**Where.** {loc['url']}"
            if loc.get("selector"):
                line += f" — `{loc['selector']}`"
            body.append(line)
        screenshot = loc.get("screenshot")
        if screenshot and screenshot in screenshot_map:
            body.append(f"![[{screenshot_map[screenshot]}]]")
        body.append(f"**Finding.** {f.get('finding','').strip()}")
        body.append(f"**Fix.** {f.get('suggested_fix','').strip()}")
        if f.get("role_assumption") and f["role_assumption"] not in ("None", None):
            body.append(f"**Role.** {f['role_assumption']}")
        vp = f.get("voice_provenance") or "—"
        pps = f.get("principle_provenance") or []
        if isinstance(pps, str):
            pps = [pps]
        body.append(f"**Provenance.** voice=`{vp}` · principles=`{'`, `'.join(pps) if pps else '—'}`")
        if f.get("merged_count", 1) > 1:
            body.append(f"_Merged from {f['merged_count']} per-page findings._")
        body.append("")

    if site_wide:
        body.append("## Site-wide issues")
        body.append("")
        body.append("_These findings showed up across 3+ pages. Fixing one likely fixes all of them._")
        body.append("")
        sev_rank = {"P0": 0, "P1": 1, "P2": 2}
        for f in sorted(site_wide, key=lambda f: (sev_rank.get(f.get("severity", "P2"), 3), -f.get("merged_count", 1))):
            _render_block(f)

    body.append("## Per-page findings")
    body.append("")
    for sev in ("P0", "P1", "P2"):
        if not by_severity[sev]:
            continue
        body.append(f"### {sev}")
        body.append("")
        for f in by_severity[sev]:
            _render_block(f)

    body.append(_voice_provenance_table(findings, voice_lookup))
    body.append(_principle_provenance_table(findings, principle_lookup))

    if rejected:
        body.append("## Rejected (missing provenance)")
        for r in rejected[:20]:
            f = r.get("finding", {})
            body.append(f"- _{r.get('reason')}_: {str(f.get('finding',''))[:160]}")

    out_path = FEEDBACK_DIR / f"{_today_slug()}-{(product_hint or 'site')}.md"
    out_path.write_text(fm + "\n\n" + "\n".join(body) + "\n", encoding="utf-8")
    return out_path


def render_slack_digest(target: str, findings: list[dict], obsidian_path: Path) -> str:
    """Top 5 P0/P1 findings for self-DM. Mirrors fakematt-today/digest.py tone."""
    today = _today_slug()
    p0_p1 = [f for f in findings if f.get("severity") in ("P0", "P1")]
    top = sorted(p0_p1, key=lambda f: ({"P0": 0, "P1": 1}.get(f.get("severity"), 2), 0))[:5]
    lines = [
        f"*Fake Matt feedback — {today}*",
        f"_{target} • {len(findings)} findings ({sum(1 for f in findings if f.get('severity')=='P0')} P0, {sum(1 for f in findings if f.get('severity')=='P1')} P1)_",
        "",
        "*Top 5*",
    ]
    if not top:
        lines.append("• _no P0/P1 findings_")
    else:
        for f in top:
            sev = f.get("severity", "P?")
            cat = f.get("category", "")
            line = (f.get("finding", "") or "").strip().replace("\n", " ")[:240]
            lines.append(f"• *{sev}* _{cat}_ — {line}")
    lines.append("")
    lines.append(f"_Full note: `{obsidian_path}`_")
    return "\n".join(lines)


def post_self_dm(text: str) -> dict:
    """Post to Fake Matt's self-DM. NEVER to a shared channel."""
    if not SLACK_SKILL_CONFIG.exists():
        return {"_error": f"slack config missing: {SLACK_SKILL_CONFIG}"}
    try:
        from slack_sdk import WebClient
    except ImportError:
        return {"_error": "slack_sdk not installed"}
    cfg = json.loads(SLACK_SKILL_CONFIG.read_text())
    token = cfg.get("default", {}).get("token") or cfg.get("token")
    if not token:
        return {"_error": "no slack token in config"}
    client = WebClient(token=token)
    try:
        res = client.chat_postMessage(channel=FAKE_MATT_SELF_DM, text=text)
        return {"ok": True, "ts": res["ts"]}
    except Exception as exc:
        return {"_error": str(exc)[:300]}


def build_voice_lookup() -> dict[str, dict]:
    p = Path.home() / ".claude" / "feedback-corpus" / "voice" / "quotes.json"
    if not p.exists():
        return {}
    try:
        return {q["id"]: q for q in json.loads(p.read_text(encoding="utf-8"))}
    except Exception:
        return {}


def build_principle_lookup() -> dict[str, dict]:
    p = Path.home() / ".claude" / "feedback-corpus" / "principles" / "citations.json"
    if not p.exists():
        return {}
    try:
        return {item["principle_id"]: item for item in json.loads(p.read_text(encoding="utf-8"))}
    except Exception:
        return {}
