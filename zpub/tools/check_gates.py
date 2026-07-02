#!/usr/bin/env python3
"""check_gates.py — auto-evaluate the `imagery_quality` and `ledger_clean`
gates for a zpub blog entry.

Pairs with the gates added to `_meta/gates.json` per
`MattZerg/_style/blog_template_rules.md` §7.

Usage:
    python3 ~/.claude/skills/zpub/tools/check_gates.py <id>
    python3 ~/.claude/skills/zpub/tools/check_gates.py <id> --apply  # zpub set automatically
    python3 ~/.claude/skills/zpub/tools/check_gates.py --all-blogs --apply  # one-shot sweep

`imagery_quality`:
    passed  — hero referenced in surfaces passes validate_hero.py
    failed  — hero present but fails validation
    pending — entry is in-flight and no hero referenced
    n_a     — entry status is published / distributed / archived

`ledger_clean`:
    passed  — feedback ledger exists with zero [open|HIGH] lines
    failed  — ledger has at least one [open|HIGH] line
    pending — no ledger file exists for an in-flight entry
    n_a     — entry status is published / distributed / archived
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR))
from slug_util import slug_candidates  # noqa: E402 — shared with pipeline.py

VAULT_ROOT = Path.home() / "Obsidian/Zerg"  # post-migration live vault root (contains MattZerg/)
PUB_DIR = VAULT_ROOT / "MattZerg/Projects/Zerg-Production/Growth/publishing"
INDEX_PATH = PUB_DIR / "_meta/index.json"
LEDGER_DIR = VAULT_ROOT / "MattZerg/Writing/_reviews"
VALIDATE_HERO = Path.home() / ".claude/skills/blog-imagery/tools/validate_hero.py"

TERMINAL_STATUSES = {"published", "distributed", "archived"}


def load_index() -> list[dict]:
    data = json.loads(INDEX_PATH.read_text())
    return data.get("entries", []) if isinstance(data, dict) else data


def _read_entry_yaml(entry_id: str) -> dict:
    """Read the canonical YAML frontmatter for an entry. Index.json only
    carries a subset (no `approval` block), so for signoff decisions we MUST
    read the source file. Per the gigacontext-2026-05-19 incident — the
    approval block is the truth, index.json is a cache.
    """
    path = PUB_DIR / f"{entry_id}.md"
    if not path.exists():
        return {}
    try:
        text = path.read_text()
    except OSError:
        return {}
    # Stdlib YAML is unavailable; use a tiny regex-based extractor for the
    # approval block (only what evaluate_signoff needs).
    approval: dict = {}
    m = re.search(r"^approval:\s*\n((?:[ \t]+.*\n?)+)", text, re.MULTILINE)
    if m:
        block = m.group(1)
        for line in block.splitlines():
            kv = re.match(r"^\s{2,4}(\w+):\s*(.*?)\s*$", line)
            if not kv:
                continue
            key, raw = kv.group(1), kv.group(2)
            if raw == "true":
                approval[key] = True
            elif raw == "false":
                approval[key] = False
            else:
                approval[key] = raw.strip('"\'')
    return {"approval": approval}


def find_entry(entry_id: str) -> dict | None:
    for entry in load_index():
        if entry.get("id") == entry_id:
            # Merge the on-disk approval block in — signoff evaluation needs it.
            merged = dict(entry)
            file_data = _read_entry_yaml(entry_id)
            if file_data.get("approval"):
                merged["approval"] = file_data["approval"]
            return merged
    return None


def _expand(p: str) -> Path:
    return Path(p.replace("~", str(Path.home()))).expanduser()


BLOG_IMG_DIR = Path.home() / "zerg/web/src/public/images/blog"


def hero_path_from_surfaces(entry: dict) -> tuple[Path | None, list[Path]]:
    """Find the hero image path for an entry.

    Returns (hero_path, tried) — `tried` lists every candidate path checked,
    so a miss can report exactly what was looked for (actionable failure)
    instead of a bare "not found".

    Explicit hero/image surfaces win; otherwise slug candidates from
    slug_util (shared with pipeline.py) are tried as <slug>-hero.png.
    """
    surfaces = entry.get("surfaces", []) or []
    tried: list[Path] = []
    for surf in surfaces:
        if not isinstance(surf, dict):
            continue
        kind = (surf.get("kind") or "").lower()
        path = surf.get("path")
        if not path:
            continue
        if "hero" in kind or "image" in kind or "imagery" in kind:
            explicit = _expand(path)
            return explicit, [explicit]

    for slug in slug_candidates(entry.get("id", ""), surfaces):
        candidate = BLOG_IMG_DIR / f"{slug}-hero.png"
        tried.append(candidate)
        if candidate.exists():
            return candidate, tried
    return None, tried


def ledger_path_for(entry_id: str) -> Path:
    return LEDGER_DIR / f"{entry_id}.feedback-ledger.md"


def evaluate_imagery_quality(entry: dict) -> tuple[str, str]:
    status = entry.get("status", "")
    if status in TERMINAL_STATUSES:
        return "n_a", "entry is terminal status; gate is n_a"
    hero, tried = hero_path_from_surfaces(entry)
    if hero is None:
        tried_str = ", ".join(p.name for p in tried) or "<no slug candidates derivable>"
        return "pending", (
            f"no hero found; tried {tried_str} in {BLOG_IMG_DIR} — "
            f"fix: generate the hero there, or add an explicit surface "
            f"{{kind: hero, path: …}} to {entry.get('id')}"
        )
    if not hero.exists():
        return "pending", (
            f"hero path not found: {hero} — fix: generate it or correct the "
            f"hero surface path on {entry.get('id')}"
        )
    result = subprocess.run(
        ["python3", str(VALIDATE_HERO), str(hero), "--json"],
        capture_output=True,
        text=True,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return "pending", f"validate_hero crashed: {result.stderr.strip() or result.stdout[:120]}"
    if payload.get("ok"):
        return "passed", f"hero {hero.name} passes validation"
    findings = payload.get("findings", [])
    return "failed", "hero validation failed: " + "; ".join(findings[:3])


def evaluate_signoff(entry: dict, computed: dict) -> tuple[str, str]:
    """Read signoff from the canonical approval block, NOT from validator state.

    Signoff is a human gate (Matt + Idan). The canonical record is the
    `approval` block on the entry YAML — locked=true + locked_by={matt,idan}
    means the human approved. This evaluator MUST respect that record and
    never auto-flip signoff based on a downstream validator firing. The
    gigacontext-2026-05-19 incident: Idan locked-and-approved at 18:18:55Z,
    then 30 minutes later a `validate_hero.py` aspect-band misfire caused
    this evaluator to overwrite his signoff. That was wrong. See
    `feedback_matt_approval_preserves_state.md` and
    `feedback_validator_calibrates_to_matt.md`.

    Rule:
      - approval.locked=true + locked_by in {matt, idan} → signoff=passed.
      - Otherwise → return whatever the gates field currently says (no change).
        Signoff transitions are human-only; never auto-flipped by this tool.

    `computed` is retained for API parity but no longer drives the decision.
    """
    status = entry.get("status", "")
    if status in TERMINAL_STATUSES:
        return "n_a", "entry is terminal status; gate is n_a"

    approval = entry.get("approval", {}) or {}
    if approval.get("locked") is True and approval.get("locked_by") in ("matt", "idan"):
        who = approval.get("locked_by")
        at = approval.get("locked_at", "?")
        return "passed", f"approval block: locked_by={who} at {at} — canonical signoff"

    gates = entry.get("gates", {}) or {}
    current = gates.get("signoff", "pending")
    return current, "no approval lock; signoff transitions are human-only"


LEDGER_TEMPLATE = """# Feedback ledger — {entry_id}

Format: `- [open|SEVERITY] <finding> (<source>, <date>)` → flip `open` to
`done` when addressed. `ledger_clean` passes when zero `[open|HIGH]` lines remain.

## Findings

(none yet)
"""


def scaffold_ledger(entry_id: str) -> Path:
    """Create an empty feedback ledger so ledger_clean stops hanging on
    file-absence. Never overwrites an existing ledger."""
    ledger = ledger_path_for(entry_id)
    if not ledger.exists():
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_text(LEDGER_TEMPLATE.format(entry_id=entry_id))
    return ledger


def evaluate_ledger_clean(entry: dict) -> tuple[str, str]:
    status = entry.get("status", "")
    if status in TERMINAL_STATUSES:
        return "n_a", "entry is terminal status; gate is n_a"
    ledger = ledger_path_for(entry["id"])
    if not ledger.exists():
        return "pending", (
            f"no ledger at {ledger.relative_to(VAULT_ROOT)} — "
            f"fix: check_gates.py {entry['id']} --scaffold-ledger"
        )
    text = ledger.read_text()
    open_high = re.findall(r"^\s*-\s*\[open\|HIGH\]", text, re.MULTILINE)
    if open_high:
        return "failed", f"ledger has {len(open_high)} open HIGH item(s)"
    return "passed", "ledger has no open HIGH items"


def apply_gate(entry_id: str, gate_name: str, value: str) -> bool:
    zpub_py = SKILL_DIR / "zpub.py"
    # check_gates is the canonical-state evaluator — it computes the correct
    # gate values from observable signals (hero validation, ledger HIGH items,
    # prerequisite chain) and writes them. By design it may transit through
    # contradictory intermediate states during a multi-gate update, so we
    # pass --force-inconsistent (logged to _meta/conflicts.log) and
    # --override-in-flight. See ~/.claude/plans/synchronous-yawning-storm.md A1/A2.
    args = ["python3", str(zpub_py), "set", entry_id, f"gates.{gate_name}", value,
            "--force-inconsistent", "--override-in-flight"]
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ! zpub set failed for {entry_id}.{gate_name}: {result.stderr.strip()}",
              file=sys.stderr)
        return False
    return True


def evaluate_one(entry_id: str, apply: bool = False, scaffold: bool = False) -> dict:
    entry = find_entry(entry_id)
    if not entry:
        return {"id": entry_id, "error": "no such entry"}

    if scaffold and entry.get("status") not in TERMINAL_STATUSES:
        scaffold_ledger(entry_id)

    iq_status, iq_reason = evaluate_imagery_quality(entry)
    lc_status, lc_reason = evaluate_ledger_clean(entry)
    so_status, so_reason = evaluate_signoff(
        entry, {"imagery_quality": iq_status, "ledger_clean": lc_status}
    )
    result = {
        "id": entry_id,
        "type": entry.get("type"),
        "entry_status": entry.get("status"),
        "imagery_quality": {"value": iq_status, "reason": iq_reason},
        "ledger_clean": {"value": lc_status, "reason": lc_reason},
        "signoff": {"value": so_status, "reason": so_reason},
    }

    if apply and entry.get("type") == "blog":
        # Order matters: write signoff FIRST so any "signoff=passed without
        # prereqs" contradiction is repaired before we touch the leaf gates.
        applied = {"signoff": apply_gate(entry_id, "signoff", so_status)}
        applied["imagery_quality"] = apply_gate(entry_id, "imagery_quality", iq_status)
        applied["ledger_clean"] = apply_gate(entry_id, "ledger_clean", lc_status)
        result["applied"] = applied
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("id", nargs="?", help="entry id (omit with --all-blogs)")
    ap.add_argument("--apply", action="store_true",
                    help="also call zpub set to persist the computed gate values")
    ap.add_argument("--scaffold-ledger", action="store_true",
                    help="create an empty feedback ledger when missing (never overwrites)")
    ap.add_argument("--all-blogs", action="store_true",
                    help="sweep every blog-type entry")
    ap.add_argument("--json", action="store_true",
                    help="emit JSON instead of text")
    args = ap.parse_args()

    if not args.id and not args.all_blogs:
        ap.error("provide an id or --all-blogs")

    results: list[dict] = []
    if args.all_blogs:
        for entry in load_index():
            if entry.get("type") != "blog":
                continue
            results.append(evaluate_one(entry["id"], apply=args.apply,
                                        scaffold=args.scaffold_ledger))
    else:
        results.append(evaluate_one(args.id, apply=args.apply,
                                    scaffold=args.scaffold_ledger))

    if args.json:
        print(json.dumps(results, indent=2))
        return 0

    for r in results:
        if "error" in r:
            print(f"[ERROR] {r['id']}: {r['error']}")
            continue
        print(f"{r['id']}  ({r['entry_status']})")
        for gate in ("imagery_quality", "ledger_clean", "signoff"):
            g = r[gate]
            marker = {"passed": "✓", "failed": "✗", "pending": "·", "n_a": "—"}.get(g["value"], "?")
            print(f"  {marker} {gate:18s} {g['value']:8s} {g['reason']}")
        if "applied" in r:
            print(f"  applied: signoff={r['applied'].get('signoff')}, "
                  f"imagery_quality={r['applied'].get('imagery_quality')}, "
                  f"ledger_clean={r['applied'].get('ledger_clean')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
