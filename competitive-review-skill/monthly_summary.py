#!/usr/bin/env python3
"""
After a monthly refresh, walk every MattZerg/Competitive/<category>/ folder, extract
the "What changed" section + headline counts, write a single cross-category summary
note, and post a short digest to Fake Matt self-DM.

Idempotent — produces a dated summary note each month under MattZerg/Competitive/_monthly/.
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL_DIR))
from lib import vault  # noqa: E402

SLACK_CONFIG = Path.home() / ".claude" / "skills" / "slack-skill" / "config.json"
FAKE_MATT_SELF_DM = "D0B109RDJQ6"  # mirror fakematt-today daemons


def parse_index(index_path: Path) -> dict:
    """Pull headline counts and 'What changed' section from a category index.md."""
    text = index_path.read_text(encoding="utf-8")

    def grab(pattern: str) -> str | None:
        m = re.search(pattern, text)
        return m.group(1).strip() if m else None

    summary = {
        "category": index_path.parent.name,
        "n_features": grab(r"Features identified:\*\*\s*(\d+)"),
        "table_stakes": grab(r"Table-stakes gaps:\*\*\s*(\d+)"),
        "diff_parity": grab(r"Differentiator-parity calls:\*\*\s*(\d+)"),
        "whitespace": grab(r"Whitespace opportunities:\*\*\s*(\d+)"),
        "ours": grab(r"Our differentiators:\*\*\s*(\d+)"),
        "drift": grab(r"Spec.site drift items:\*\*\s*(\d+)"),
    }

    # 'What changed' section (only present after a refresh)
    m = re.search(r"##\s*What changed since last review\s*\n+(.*?)(?=\n##|\Z)", text, re.DOTALL)
    summary["what_changed"] = m.group(1).strip() if m else ""
    return summary


def collect_categories() -> list[dict]:
    base = vault.COMPETITIVE_DIR
    if not base.exists():
        return []
    out = []
    for d in sorted(base.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        idx = d / "index.md"
        if not idx.exists():
            continue
        try:
            out.append(parse_index(idx))
        except Exception as e:
            out.append({"category": d.name, "error": str(e)})
    return out


def render_summary_note(rows: list[dict]) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    body = [f"# Monthly Competitive Refresh — {today}\n"]
    body.append("Cross-category snapshot. Each row links to the full category note.\n")

    body.append("## Counts\n")
    body.append("| Category | Features | Table-stakes | Parity | Whitespace | Ours | Drift |")
    body.append("|---|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        if r.get("error"):
            body.append(f"| {r['category']} | err: {r['error'][:40]} | | | | | |")
            continue
        body.append(
            f"| [[Competitive/{r['category']}/index|{r['category']}]] | "
            f"{r.get('n_features','?')} | {r.get('table_stakes','?')} | "
            f"{r.get('diff_parity','?')} | {r.get('whitespace','?')} | "
            f"{r.get('ours','?')} | {r.get('drift','?')} |"
        )

    # Categories with non-empty 'What changed'
    changed = [r for r in rows if r.get("what_changed")]
    if changed:
        body.append("\n## What changed\n")
        for r in changed:
            body.append(f"### {r['category']}")
            body.append(r["what_changed"][:1500])
            body.append("")

    return "\n".join(body)


def render_slack_digest(rows: list[dict]) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [f":bar_chart: *Monthly competitive refresh — {today}*"]
    lines.append(f"Refreshed {len(rows)} categories. Vault: `MattZerg/Competitive/_monthly/{today}.md`")

    # Top 5 changes
    changed = [r for r in rows if r.get("what_changed") and "unchanged" not in r["what_changed"].lower()]
    if changed:
        lines.append("\n*Categories with changes:*")
        for r in changed[:5]:
            first_line = r["what_changed"].split("\n")[0][:120]
            lines.append(f"  • {r['category']}: {first_line}")
    else:
        lines.append("\n_No notable changes detected this month._")
    return "\n".join(lines)


def post_to_slack(message: str) -> None:
    """Post to Fake Matt self-DM. Per project rules: drafts only, never to shared channels.
    Uses slack_sdk WebClient directly (same pattern as fakematt-today daemons)."""
    if not SLACK_CONFIG.exists():
        print(f"[monthly_summary] slack config not at {SLACK_CONFIG}; skipping", file=sys.stderr)
        return
    try:
        import json as _json
        from slack_sdk import WebClient
        cfg = _json.loads(SLACK_CONFIG.read_text())
        token = cfg.get("default", {}).get("token") or cfg.get("token")
        if not token:
            print(f"[monthly_summary] slack token not in config; skipping", file=sys.stderr)
            return
        client = WebClient(token=token)
        client.chat_postMessage(channel=FAKE_MATT_SELF_DM, text=message)
        print(f"[monthly_summary] posted to Fake Matt self-DM", file=sys.stderr)
    except Exception as e:
        print(f"[monthly_summary] slack post error: {e}", file=sys.stderr)


def main():
    rows = collect_categories()
    if not rows:
        print("[monthly_summary] no categories found under MattZerg/Competitive/", file=sys.stderr)
        return

    today = datetime.now().strftime("%Y-%m-%d")
    out_dir = vault.COMPETITIVE_DIR / "_monthly"
    out_dir.mkdir(parents=True, exist_ok=True)
    note_path = out_dir / f"{today}.md"

    note = render_summary_note(rows)
    note_path.write_text(note, encoding="utf-8")
    print(f"[monthly_summary] wrote {note_path}")

    digest = render_slack_digest(rows)
    print(f"\n--- slack digest preview ---\n{digest}\n----")
    post_to_slack(digest)


if __name__ == "__main__":
    main()
