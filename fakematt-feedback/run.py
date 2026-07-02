#!/usr/bin/env python3
"""fakematt-feedback CLI entry.

Usage:
  run.py <target> [--max-pages N] [--no-confirm] [--out PATH]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.capture import crawl_and_capture
from lib.critique import DEFAULT_MODEL as CRITIQUE_DEFAULT_MODEL
from lib.critique import critique_page, validate_findings

# aitr-backed model defaulting for the critique phase (vision-heavy prose review).
sys.path.insert(0, str(Path.home() / ".claude" / "skills" / "aitr" / "scripts"))
try:
    from skill_default import aitr_model_or  # type: ignore
except ImportError:
    def aitr_model_or(fallback, **kwargs):  # type: ignore
        return fallback
from lib.dedupe import dedupe_findings
from lib.flows import confirm_flows, from_zstack, merge_flow_lists
from lib.inconsistency import find_inconsistencies
from lib.inputs import resolve
from lib.static_capture import capture_static
from lib.output import (
    build_principle_lookup,
    build_voice_lookup,
    post_self_dm,
    render_slack_digest,
    write_obsidian_note,
)
from lib.voice import (
    PRINCIPLES_CITATIONS,
    VOICE_QUOTES,
    load_principles_block,
    load_voice_block,
)

SKILL_ROOT = Path(__file__).resolve().parent
STATE_ROOT = SKILL_ROOT / "state"
SENT_LOG = SKILL_ROOT / "sent-log.jsonl"

# Owned-domain whitelist — only these get learn-loop tracking.
# Other targets (CesiumAstro, Michael's zergboard-preview, competitors) are reference-only
# per memory: feedback_fakematt_scope.md.
OWNED_DOMAINS = (
    "zergai.com", "zerg.ai",
    "zergboard-preview.pages.dev",
    "zerglytics.fly.dev",
    "localhost", "127.0.0.1",
)


def _is_owned(target_url: str) -> bool:
    from urllib.parse import urlparse
    try:
        host = (urlparse(target_url).hostname or "").lower()
    except Exception:
        return False
    return any(host == d or host.endswith("." + d) or host.startswith(d) for d in OWNED_DOMAINS)


def _log_sent_attempt(record: dict) -> None:
    try:
        with open(SENT_LOG, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[sent-log] {e}", file=sys.stderr)


def _load_id_set(path: Path, key: str) -> set[str]:
    if not path.exists():
        return set()
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
        return {item[key] for item in items if key in item}
    except Exception:
        return set()


def _render_finding(out: list[str], f: dict, *, header_severity: str | None = None) -> None:
    """Render one finding block. If `header_severity` is provided, it's used
    in the section header — otherwise pulled from the finding itself."""
    sev = header_severity or f.get("severity", "P2")
    cat = f.get("category", "general")
    mode = f.get("mode")
    mode_tag = f" · {mode}" if mode else ""
    site_tag = " _[site-wide]_" if f.get("is_site_wide") else ""
    out.append(f"### {sev} — {cat}{mode_tag}{site_tag}")
    loc = f.get("location") or {}
    affected = f.get("affected_pages") or []
    if affected:
        out.append(f"- **Affected pages ({len(affected)}):**")
        for url in affected[:8]:
            out.append(f"  - {url}")
        if len(affected) > 8:
            out.append(f"  - …and {len(affected) - 8} more")
    elif loc.get("url"):
        sel = loc.get("selector") or ""
        out.append(f"- **Where:** {loc['url']}" + (f" (`{sel}`)" if sel else ""))
    if loc.get("screenshot"):
        out.append(f"- ![]({loc['screenshot']})")
    out.append(f"- **Finding:** {f.get('finding', '').strip()}")
    out.append(f"- **Fix:** {f.get('suggested_fix', '').strip()}")
    if f.get("role_assumption") and f["role_assumption"] != "None":
        out.append(f"- **Role:** {f['role_assumption']}")
    vp = f.get("voice_provenance") or "—"
    pps = f.get("principle_provenance", [])
    if isinstance(pps, str):
        pps = [pps]
    out.append(f"- **Provenance:** voice=`{vp}` · principles=`{'`, `'.join(pps) if pps else '—'}`")
    if f.get("merged_count", 1) > 1:
        out.append(f"- _Merged from {f['merged_count']} per-page findings._")
    out.append("")


def render_markdown(target: str, captures: list, all_findings: list, all_rejected: list, dedupe_stats: dict | None = None) -> str:
    """Render the report. Surfaces site-wide issues at the top, then per-page
    findings grouped by severity. Each finding block mentions affected pages
    if it was merged across multiple."""
    site_wide = [f for f in all_findings if f.get("is_site_wide")]
    page_specific = [f for f in all_findings if not f.get("is_site_wide")]

    by_severity: dict[str, list[dict]] = {"P0": [], "P1": [], "P2": []}
    for f in page_specific:
        by_severity.setdefault(f.get("severity", "P2"), []).append(f)

    out: list[str] = []
    out.append(f"# Fake Matt feedback — {target}")
    out.append("")
    summary = f"_Reviewed {dt.datetime.now().strftime('%Y-%m-%d %H:%M %Z').strip()}; {len(captures)} pages, {len(all_findings)} findings"
    if dedupe_stats and dedupe_stats.get("merged_count"):
        summary += f" (deduped from {dedupe_stats['input_count']}, merged {dedupe_stats['merged_count']})"
    if all_rejected:
        summary += f", {len(all_rejected)} rejected for missing provenance"
    out.append(summary + "._")
    out.append("")

    sev_counts = {"P0": 0, "P1": 0, "P2": 0}
    for f in all_findings:
        sev_counts[f.get("severity", "P2")] = sev_counts.get(f.get("severity", "P2"), 0) + 1
    site_wide_count = len(site_wide)
    out.append(f"**Severity:** P0={sev_counts['P0']} · P1={sev_counts['P1']} · P2={sev_counts['P2']}{f' · site-wide={site_wide_count}' if site_wide_count else ''}")
    out.append("")

    if sev_counts["P0"]:
        # If I only fix three things — pick top P0s, prefer site-wide
        p0_all = [f for f in all_findings if f.get("severity") == "P0"]
        p0_all.sort(key=lambda f: (not f.get("is_site_wide", False), -f.get("merged_count", 1)))
        out.append("## If I only fix three things")
        for f in p0_all[:3]:
            tag = " (site-wide)" if f.get("is_site_wide") else ""
            out.append(f"- {f.get('finding', '').strip()}{tag}")
            out.append(f"  - **Fix:** {f.get('suggested_fix', '').strip()}")
        out.append("")

    if site_wide:
        out.append("## Site-wide issues")
        out.append("")
        out.append("_These findings showed up across 3+ pages. Fixing one likely fixes all of them._")
        out.append("")
        for f in sorted(site_wide, key=lambda f: ({"P0": 0, "P1": 1, "P2": 2}.get(f.get("severity", "P2"), 3), -f.get("merged_count", 1))):
            _render_finding(out, f)

    out.append("## Per-page findings")
    out.append("")
    for sev in ("P0", "P1", "P2"):
        if not by_severity[sev]:
            continue
        out.append(f"### {sev}")
        out.append("")
        for f in by_severity[sev]:
            _render_finding(out, f)

    if all_rejected:
        out.append("## Rejected (missing provenance)")
        for r in all_rejected[:20]:
            f = r.get("finding", {})
            out.append(f"- _{r.get('reason')}_: {str(f.get('finding', ''))[:160]}")
    return "\n".join(out)


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("target", help="URL | http://localhost:port | figma://<key> | /path/to/screenshots")
    p.add_argument("--max-pages", type=int, default=8, help="Auto-crawl page limit")
    p.add_argument("--no-confirm", action="store_true", help="Skip gates (for scheduled use)")
    p.add_argument("--out", default=None, help="Override output markdown path (default: state/<run-id>/report.md)")
    p.add_argument("--no-vault", action="store_true", help="Skip writing to MattZerg/Feedback/")
    p.add_argument("--no-slack", action="store_true", help="Skip self-DM digest")
    p.add_argument("--session", default=None, help="Session name in skill sessions/ dir (persistent_context for auth)")
    p.add_argument("--persona", default=None, choices=[None, "super-admin", "admin", "end-user", "external-viewer"],
                   help="Viewer role context — gates what edit/admin controls get flagged as bugs")
    p.add_argument("--target-kind", default=None, choices=[None, "marketing-page", "internal-tool", "b2b-saas-product", "client-deliverable", "dashboard"],
                   help="What kind of target this is — picks the evaluation rubric (internal tools won't get marketing-CRO critique)")
    args = p.parse_args(argv)

    target = resolve(args.target)
    print(f"[input] kind={target.kind} canonical={target.canonical} product_hint={target.product_hint}")

    spec_flows = from_zstack(target.product_hint or "") if target.product_hint else []
    if spec_flows:
        print(f"[flows] spec from Zstack: {spec_flows}")
    flows = confirm_flows(spec_flows, no_confirm=args.no_confirm)
    flows = merge_flow_lists(flows)

    run_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S") + f"-{target.product_hint}"
    run_dir = STATE_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    session_dir = None
    if args.session:
        session_dir = SKILL_ROOT / "sessions" / args.session
        if not session_dir.exists():
            print(f"[session] {session_dir} does not exist — run login_session.py first")
            return 1
        print(f"[session] using {session_dir}")

    if target.kind == "static":
        print(f"[capture] static assets → {run_dir}")
        captures = capture_static(target.static_paths or [target.canonical], run_dir)
    else:
        print(f"[capture] crawling up to {args.max_pages} pages → {run_dir}")
        captures = crawl_and_capture(target.canonical, run_dir, max_pages=args.max_pages, session_dir=session_dir)
    print(f"[capture] captured {len(captures)} pages")
    if not captures:
        print("[capture] nothing captured — exiting")
        return 1

    voice_block = load_voice_block()
    principles_block = load_principles_block()
    voice_ids = _load_id_set(VOICE_QUOTES, "id")
    principle_ids = _load_id_set(PRINCIPLES_CITATIONS, "principle_id")
    print(f"[corpus] voice quotes={len(voice_ids)} principles={len(principle_ids)}")

    # Model resolution for the critique phase: aitr pick > lib default (loud fallback).
    # vision required — critique reasons about screenshots + visual layout.
    critique_model = aitr_model_or(
        CRITIQUE_DEFAULT_MODEL,
        task_kind="prose-review",
        caller="fakematt-feedback",
        quality_floor="medium",
        modality_required="vision",
    )

    all_findings: list[dict] = []
    all_rejected: list[dict] = []
    for cap in captures:
        payload = cap.to_payload()
        print(f"[critique] {cap.url}")
        raw = critique_page(
            voice_block, principles_block, payload,
            persona=args.persona, target_kind=args.target_kind,
            model=critique_model,
        )
        kept, rejected = validate_findings(raw, voice_ids, principle_ids)
        for f in kept:
            f.setdefault("location", {}).setdefault("url", cap.final_url)
            if not f["location"].get("screenshot"):
                f["location"]["screenshot"] = cap.screenshot_desktop
        all_findings.extend(kept)
        all_rejected.extend(rejected)

    # Cross-page inconsistency scan — catches drift like name-format
    # variation across the same URL template, which per-page critique
    # can't see in isolation.
    inconsistency_findings = find_inconsistencies(captures)
    if inconsistency_findings:
        print(f"[inconsistency] {len(inconsistency_findings)} cross-page findings")
        all_findings.extend(inconsistency_findings)

    # Dedupe: merge identical findings across pages into one with
    # affected_pages list. The lang-attribute issue gets flagged once
    # per template (5x) and should collapse to one site-wide finding.
    pre_dedupe_count = len(all_findings)
    all_findings, dedupe_stats = dedupe_findings(all_findings)
    if dedupe_stats["merged_count"]:
        print(f"[dedupe] {pre_dedupe_count} → {dedupe_stats['output_count']} findings ({dedupe_stats['merged_count']} merged, {dedupe_stats['site_wide_count']} site-wide)")

    insights_path = run_dir / "insights.json"
    insights_path.write_text(json.dumps({
        "target": target.canonical,
        "kind": target.kind,
        "captures": [c.to_payload() for c in captures],
        "findings": all_findings,
        "rejected": all_rejected,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[output] insights → {insights_path}")

    md_path = Path(args.out) if args.out else run_dir / "report.md"
    md_path.write_text(render_markdown(target.canonical, captures, all_findings, all_rejected, dedupe_stats) + "\n", encoding="utf-8")
    print(f"[output] report → {md_path}")

    if not args.no_vault:
        vlookup = build_voice_lookup()
        plookup = build_principle_lookup()
        vault_path = write_obsidian_note(
            target=target.canonical,
            kind=target.kind,
            captures=captures,
            findings=all_findings,
            rejected=all_rejected,
            flows=flows,
            run_id=run_id,
            voice_lookup=vlookup,
            principle_lookup=plookup,
            product_hint=target.product_hint,
        )
        print(f"[vault] {vault_path}")

        if not args.no_slack:
            digest = render_slack_digest(target.canonical, all_findings, vault_path)
            slack_res = post_self_dm(digest)
            if slack_res.get("ok"):
                print(f"[slack] self-DM posted ts={slack_res['ts']}")
            else:
                print(f"[slack] skipped: {slack_res.get('_error', 'unknown')}")

    # Learning loop instrumentation — log per-page snapshots only for owned targets.
    if _is_owned(target.canonical):
        page_snapshots = []
        for cap in captures:
            payload = cap.to_payload()
            text = (payload.get("body_text") or payload.get("text") or "")[:6000]
            page_snapshots.append({
                "url": cap.final_url,
                "text_hash": hash(text) & 0xffffffff,
                "text_snippet": text,
            })
        _log_sent_attempt({
            "ts": dt.datetime.now().strftime("%Y%m%dT%H%M%S"),
            "run_id": run_id,
            "target": target.canonical,
            "owned": True,
            "finding_count": len(all_findings),
            "page_snapshots": page_snapshots,
            "checked": False,
        })
        print(f"[sent-log] tracked {len(page_snapshots)} page snapshots (target is owned)")
    else:
        print(f"[sent-log] {target.canonical} is not owned — skipping learning loop")
    return 0


if __name__ == "__main__":
    sys.exit(main())
