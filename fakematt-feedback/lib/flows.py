"""Flow discovery — order: spec-driven → auto-crawl → confirm gate → free-form.

For v1, the auto-crawl in capture.py covers the baseline. This module wraps
the four discovery modes the plan calls for, exposed so run.py can compose them.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

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
ZSTACK_DIR = VAULT_ROOT / "Projects" / "Zstack"


# ----- spec-driven -----


def from_zstack(product_hint: str) -> list[str]:
    """Parse Projects/Zstack/<product>.md for declared flows.

    Recognized markers: '## Flows', '## User journeys', '## User flows',
    'Flow:' inline tags. Returns ordered flow names.
    """
    if not product_hint:
        return []
    spec = ZSTACK_DIR / f"{product_hint}.md"
    if not spec.exists():
        # case-insensitive
        for p in ZSTACK_DIR.glob("*.md"):
            if p.stem.lower() == product_hint.lower():
                spec = p
                break
        else:
            return []
    text = spec.read_text(encoding="utf-8", errors="ignore")
    flows: list[str] = []
    capturing = False
    for line in text.splitlines():
        if re.match(r"^##\s+(Flows|User journeys|User flows|Key flows)\b", line, re.I):
            capturing = True
            continue
        if capturing and line.startswith("## "):
            break
        if capturing:
            m = re.match(r"^\s*[-*\d.]+\s+(.+)$", line)
            if m:
                flows.append(m.group(1).strip().split(" — ")[0][:80])
    return flows


# ----- Matt-confirms gate -----


def confirm_flows(flows: list[str], *, no_confirm: bool = False) -> list[str]:
    """Print proposed flow list; let Matt edit via stdin.

    For interactive runs only. In `--no-confirm` mode, return `flows` as-is.
    Mirrors competitive-review-skill's gating pattern.
    """
    if no_confirm or not flows:
        return flows
    print("\n[gate] Proposed flow list:")
    for i, f in enumerate(flows, 1):
        print(f"  {i}. {f}")
    print("\nEnter flow numbers to KEEP (e.g. '1,3,5') or press Enter to keep all.")
    print("Add new flows by typing them on separate lines (end with empty line).")
    raw = sys.stdin.readline().strip() if sys.stdin.isatty() else ""
    if not raw:
        return flows
    keep_idx: set[int] = set()
    extra: list[str] = []
    for tok in re.split(r"[,\s]+", raw):
        if tok.isdigit():
            keep_idx.add(int(tok))
        elif tok:
            extra.append(tok)
    kept = [flows[i - 1] for i in sorted(keep_idx) if 1 <= i <= len(flows)] if keep_idx else flows
    return kept + extra


# ----- free-form (curious-user walk) -----


def freeform_extra_targets(captures: list, max_extra: int = 3) -> list[str]:
    """After scripted flows, propose a few unexplored URLs to capture.

    Heuristic: pick URLs from cap.links that match interesting keywords
    (pricing, docs, api, changelog, careers, blog, demo).
    """
    interesting = re.compile(r"(pricing|docs?|api|changelog|careers?|blog|demo|trial|status)", re.I)
    seen = {c.final_url for c in captures} | {c.url for c in captures}
    candidates: list[str] = []
    for c in captures:
        for link in c.links:
            if link in seen or link in candidates:
                continue
            if interesting.search(link):
                candidates.append(link)
                if len(candidates) >= max_extra:
                    return candidates
    return candidates


# ----- merge + dedup -----


def merge_flow_lists(*sources: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for src in sources:
        for f in src:
            key = f.lower().strip()
            if key in seen or not key:
                continue
            seen.add(key)
            out.append(f)
    return out
