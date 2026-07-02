#!/usr/bin/env python3
"""UX flow mapper — multi-screen journey doc with Mermaid + screen table.

Usage:
    python3 ~/.claude/skills/ux-flow-mapper/run.py map \\
        --spec <path-to-spec.yaml> --output <flow-slug>
    python3 ~/.claude/skills/ux-flow-mapper/run.py audit \\
        --url <url> --output <flow-slug> --screens-dir <dir>
    python3 ~/.claude/skills/ux-flow-mapper/run.py compare \\
        --intended <path> --observed <path>
    python3 ~/.claude/skills/ux-flow-mapper/run.py list

Idempotent `map` mode preserves a hand-edited "## Notes" section across re-runs.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

# Override with $ZERG_VAULT for non-author runs (S2 from fakeidan review).
DEFAULT_VAULT = "/Users/mattheweisner/Library/Mobile Documents/iCloud~md~obsidian/Documents/Zerg/MattZerg"
VAULT = Path(os.environ.get("ZERG_VAULT", DEFAULT_VAULT))
GROWTH_DIR = VAULT / "Projects" / "Zstack" / "Growth"
JOURNEYS_DIR = GROWTH_DIR / "journeys"

VALID_SHIP = ("live", "wip", "planned", "deprecated")
VALID_DROP = ("low", "medium", "high")
NOTES_HEADER = "## Notes"
TERMINAL_SENTINELS = {"[*]", "external", "exit"}


def validate_spec(spec: dict) -> list[str]:
    """Single source of truth for spec invariants. Returns a list of error strings.

    Empty list means valid. Both `cmd_map` (YAML spec ingest) and `cmd_audit`
    (JSON manifest ingest) MUST run this before writing anything to disk —
    addresses fakeidan C2/C3 (one validator, applied at every ingest path).
    """
    errors: list[str] = []
    if not spec.get("flow"):
        errors.append("missing required field: flow")
    screens = spec.get("screens") or []
    if not screens:
        errors.append("missing required field: screens (need ≥1)")
        return errors

    seen_ids: set[str] = set()
    for i, sc in enumerate(screens):
        sid = sc.get("id")
        if not sid:
            errors.append(f"screen {i}: missing id")
            continue
        if sid in seen_ids:
            errors.append(f"screen {i}: duplicate id {sid!r}")
        seen_ids.add(sid)
        ship = sc.get("ship_status", "")
        if ship and ship not in VALID_SHIP:
            errors.append(f"screen {sid!r}: invalid ship_status {ship!r} (valid: {VALID_SHIP})")
        drop = sc.get("drop_off_severity", "")
        if drop and drop not in VALID_DROP:
            errors.append(f"screen {sid!r}: invalid drop_off_severity {drop!r} (valid: {VALID_DROP})")

    # Referential check: every exit.to must resolve to a known screen id or sentinel.
    for sc in screens:
        for exit_ in sc.get("exits") or []:
            to = exit_.get("to") if isinstance(exit_, dict) else None
            if not to:
                errors.append(f"screen {sc.get('id','?')!r}: exit missing 'to'")
                continue
            if to not in seen_ids and to not in TERMINAL_SENTINELS:
                errors.append(f"screen {sc.get('id','?')!r}: exit.to {to!r} does not resolve to a known screen id or terminal sentinel ({TERMINAL_SENTINELS})")
    return errors


def parse_spec(text: str) -> dict:
    """Parse a spec file. Accepts JSON or hand-rolled YAML matching the documented schema.

    Convention here matches sibling skills (experiment-tracker / growth-dashboard /
    funnel-analyzer): no PyYAML dependency, hand-rolled minimal parser. To keep this
    safe, we (a) reject input that doesn't match the documented shape rather than
    silently partial-parse (addresses fakeidan C1) and (b) require validate_spec to
    run on the parsed result before any artifact is written.

    Values containing literal `:` MUST be wrapped in double quotes; this parser uses
    `partition(':')` and would otherwise truncate them. The round-trip test in
    tests/test_ux_flow_mapper.py locks this contract in place.
    """
    if text.lstrip().startswith("{"):
        return json.loads(text)
    if not text.startswith("---\n"):
        raise ValueError("spec must start with --- frontmatter or be valid JSON")
    end = text.find("\n---\n", 4)
    if end < 0:
        end = text.rfind("---")
        if end < 4:
            raise ValueError("spec missing closing ---")
    body = text[4:end] if end > 4 else text[4:]

    out: dict = {"screens": []}
    cur_screen: dict | None = None
    in_screens = False
    in_exits = False
    in_errors = False

    for line_num, line in enumerate(body.splitlines(), 1):
        if not line.strip():
            continue
        # Tabs are not allowed — keeps indent semantics unambiguous.
        if "\t" in line:
            raise ValueError(f"line {line_num}: tab characters not allowed (use spaces)")

        if line.rstrip() == "screens:":
            if cur_screen is not None:
                out["screens"].append(cur_screen)
                cur_screen = None
            in_screens = True
            in_exits = in_errors = False
            continue

        if in_screens:
            if line.startswith("  - "):
                if cur_screen is not None:
                    out["screens"].append(cur_screen)
                cur_screen = {"exits": [], "error_states": []}
                in_exits = in_errors = False
                rest = line[4:]
                if ":" in rest:
                    k, _, v = rest.partition(":")
                    cur_screen[k.strip()] = v.strip().strip('"')
                continue

            if cur_screen is None:
                # Outside any screen entry; close out screens and parse top-level
                in_screens = False
            else:
                stripped = line.lstrip()
                if line.startswith("    exits:"):
                    in_exits = True
                    in_errors = False
                    continue
                if line.startswith("    error_states:"):
                    in_errors = True
                    in_exits = False
                    continue
                if in_exits:
                    if line.startswith("      - "):
                        rest = line[8:]
                        if ":" in rest:
                            k, _, v = rest.partition(":")
                            cur_screen["exits"].append({k.strip(): v.strip().strip('"')})
                        continue
                    if line.startswith("        ") and cur_screen["exits"]:
                        k, _, v = stripped.partition(":")
                        cur_screen["exits"][-1][k.strip()] = v.strip().strip('"')
                        continue
                    in_exits = False
                if in_errors:
                    if line.startswith("      - "):
                        cur_screen["error_states"].append(line[8:].strip().strip('"'))
                        continue
                    in_errors = False
                # Plain field on this screen
                if line.startswith("    ") and ":" in line:
                    k, _, v = stripped.partition(":")
                    cur_screen[k.strip()] = v.strip().strip('"')
                    continue
                # Reject indents that don't match the documented schema rather
                # than silently bailing on the screens block.
                if line.startswith(" ") and not line.startswith("    "):
                    raise ValueError(
                        f"line {line_num}: unexpected indent {line!r} inside screens block "
                        f"(expected 4 spaces for fields, 6 for exit/error list items)"
                    )
                # Top-level field after screens block
                in_screens = False

        if not in_screens and ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip().strip('"')

    if cur_screen is not None:
        out["screens"].append(cur_screen)
    return out


def render_mermaid(spec: dict) -> str:
    """Generate stateDiagram-v2 from screens + exits."""
    lines = ["```mermaid", "stateDiagram-v2"]
    screens = spec.get("screens", [])
    if not screens:
        lines.append("    [*] --> end")
    else:
        first_id = screens[0].get("id", "start")
        lines.append(f"    [*] --> {first_id}")
        for sc in screens:
            sid = sc.get("id", "?")
            for exit_ in sc.get("exits", []):
                to = exit_.get("to", "?")
                cond = exit_.get("condition", "")
                cond_part = f": {cond}" if cond else ""
                lines.append(f"    {sid} --> {to}{cond_part}")
    lines.append("```")
    return "\n".join(lines)


def render_screen_table(spec: dict) -> str:
    """Render the screen inventory table. Assumes validate_spec has already run —
    enum values come through unchanged. Single validator (C2 fix)."""
    rows = ["| ID | Name | Purpose | Primary CTA | Ship | Drop-off |",
            "|---|---|---|---|---|---|"]
    for sc in spec.get("screens", []):
        ship = sc.get("ship_status", "?") or "?"
        drop = sc.get("drop_off_severity", "?") or "?"
        rows.append(
            f"| {sc.get('id','?')} | {sc.get('name','?')} | {sc.get('purpose','?')} | "
            f"{sc.get('primary_cta','—')} | {ship} | {drop} |"
        )
    return "\n".join(rows)


def render_error_states(spec: dict) -> str:
    lines = []
    for sc in spec.get("screens", []):
        es = sc.get("error_states") or []
        if es:
            lines.append(f"- `{sc.get('id','?')}`: {', '.join(es)}")
    if not lines:
        return "(none declared)"
    return "\n".join(lines)


def render_journey(spec: dict, preserved_notes: str = "") -> str:
    today = dt.date.today().isoformat()
    flow_id = spec.get("flow", "?")
    fm_lines = ["---",
                f"flow: {flow_id}",
                f"product: {spec.get('product','?')}",
                f"persona: {spec.get('persona','?')}",
                f"ship_status: {spec.get('ship_status','?')}",
                f"generated: {today}",
                "generator: ux-flow-mapper",
                "---"]
    out = "\n".join(fm_lines) + "\n\n"
    out += f"# Flow: {flow_id}\n\n"
    if spec.get("description"):
        out += f"{spec['description']}\n\n"
    out += "## State diagram\n\n"
    out += render_mermaid(spec) + "\n\n"
    out += "## Screen inventory\n\n"
    out += render_screen_table(spec) + "\n\n"
    out += "## Error states\n\n"
    out += render_error_states(spec) + "\n\n"
    out += "## Pair with\n\n"
    out += "- **funnel-analyzer:** define a funnel that walks the primary path through this flow\n"
    out += "- **experiments:** any experiments touching screens above (cross-reference Growth/experiments.md)\n"
    out += "- **cro-auditor:** run on screens marked drop-off=high\n"
    out += "- **fakematt-feedback:** UX audit on any screen marked ship_status=wip before promoting to live\n\n"
    out += f"{NOTES_HEADER}\n\n"
    out += preserved_notes if preserved_notes else "(hand-edit this section — preserved across `map` re-runs)\n"
    return out


def extract_notes(existing: str) -> str:
    """Extract the body of the '## Notes' section from a previous render, if any."""
    if NOTES_HEADER not in existing:
        return ""
    idx = existing.index(NOTES_HEADER) + len(NOTES_HEADER)
    body = existing[idx:].lstrip("\n")
    # Stop at next H2 if any
    next_h2 = re.search(r"^## ", body, flags=re.MULTILINE)
    if next_h2:
        body = body[:next_h2.start()].rstrip() + "\n"
    return body


def _write_sidecar(out_path: Path, spec: dict) -> None:
    """Persist screen IDs + transitions as JSON next to the markdown.

    Addresses fakeidan C4: `compare` reads structured truth from this sidecar
    rather than re-parsing rendered prose.
    """
    sidecar = out_path.with_suffix(".json")
    screens = [sc.get("id") for sc in spec.get("screens", []) if sc.get("id")]
    transitions = []
    for sc in spec.get("screens", []):
        for exit_ in sc.get("exits") or []:
            if isinstance(exit_, dict) and exit_.get("to"):
                transitions.append([sc.get("id"), exit_.get("to")])
    sidecar.write_text(json.dumps({
        "flow": spec.get("flow"),
        "screens": screens,
        "transitions": transitions,
    }, indent=2))


def cmd_map(args: argparse.Namespace) -> int:
    spec_path = Path(args.spec).expanduser()
    if not spec_path.exists():
        print(f"ERROR: spec file not found: {spec_path}", file=sys.stderr)
        return 1
    try:
        spec = parse_spec(spec_path.read_text())
    except (ValueError, json.JSONDecodeError) as e:
        print(f"ERROR: failed to parse spec: {e}", file=sys.stderr)
        return 1

    errors = validate_spec(spec)
    if errors:
        print("ERROR: spec validation failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    JOURNEYS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = JOURNEYS_DIR / f"{args.output}.md"
    preserved = ""
    if out_path.exists():
        preserved = extract_notes(out_path.read_text())

    out_text = render_journey(spec, preserved_notes=preserved)
    out_path.write_text(out_text)
    _write_sidecar(out_path, spec)
    print(f"Wrote journey doc → {out_path}")
    print(f"Screens: {len(spec['screens'])} | Mermaid + table generated.")
    if preserved.strip() and preserved.strip() != "(hand-edit this section — preserved across `map` re-runs)":
        print(f"(preserved hand-edited Notes section)")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    """Phase 1: requires --screens-dir with a screens manifest."""
    screens_dir = Path(args.screens_dir).expanduser() if args.screens_dir else None
    if not screens_dir or not screens_dir.exists():
        print(f"ERROR: --screens-dir required and must exist", file=sys.stderr)
        return 1
    manifest = screens_dir / "screens-manifest.json"
    if not manifest.exists():
        print(f"ERROR: missing {manifest}. Required format:", file=sys.stderr)
        print('  {"flow": "name", "product": "...", "screens": ['
              '{"id":"x","url":"...","screenshot":"x.png","name":"...",'
              '"primary_cta":"...","exits":[...]}]}', file=sys.stderr)
        return 1
    try:
        data = json.loads(manifest.read_text())
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid manifest JSON: {e}", file=sys.stderr)
        return 1

    # Convert manifest → spec format
    spec = {
        "flow": data.get("flow", args.output),
        "product": data.get("product", "?"),
        "persona": data.get("persona", "observed"),
        "ship_status": "live",  # observed is by definition live
        "description": f"Observed flow captured from {args.url}",
        "screens": [],
    }
    for sc in data.get("screens", []):
        spec["screens"].append({
            "id": sc.get("id", ""),
            "name": sc.get("name", "?"),
            "purpose": sc.get("purpose", "(observed)"),
            "primary_cta": sc.get("primary_cta", "—"),
            "ship_status": "live",
            # Empty (not "?") so validate_spec doesn't flag it as invalid enum.
            "drop_off_severity": sc.get("drop_off_severity", ""),
            "exits": sc.get("exits", []),
            "error_states": sc.get("error_states", []),
        })
    if not spec["screens"]:
        print("ERROR: manifest declared no screens", file=sys.stderr)
        return 1

    # C3 fix: same validator runs at this ingest path.
    errors = validate_spec(spec)
    if errors:
        print("ERROR: manifest-built spec validation failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    JOURNEYS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = JOURNEYS_DIR / f"{args.output}.md"
    preserved = ""
    if out_path.exists():
        preserved = extract_notes(out_path.read_text())
    out_path.write_text(render_journey(spec, preserved_notes=preserved))
    _write_sidecar(out_path, spec)
    print(f"Wrote observed journey doc → {out_path}")
    print(f"Screens captured: {len(spec['screens'])}")
    return 0


def _parse_journey(path: Path) -> dict:
    """Extract screen IDs + transitions for `compare`.

    Reads the JSON sidecar written by `_write_sidecar` (fakeidan C4 fix —
    structured truth lives in data, not in rendered prose). Falls back to
    parsing the rendered markdown only when the sidecar is absent (older
    hand-authored journeys), which is the documented compatibility path.
    """
    sidecar = path.with_suffix(".json")
    if sidecar.exists():
        data = json.loads(sidecar.read_text())
        return {
            "screens": set(data.get("screens", [])),
            "transitions": {tuple(t) for t in data.get("transitions", [])},
        }

    # Fallback: hand-authored journeys without sidecar. Parses the rendered
    # surface; warn the caller that this path depends on render stability.
    text = path.read_text()
    screens: set[str] = set()
    transitions: set[tuple[str, str]] = set()
    in_table = False
    for line in text.splitlines():
        if line.startswith("| ID |"):
            in_table = True
            continue
        if in_table:
            if line.startswith("|---"):
                continue
            if not line.startswith("|"):
                in_table = False
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cells:
                screens.add(cells[0])
        m = re.match(r"\s+(\w+) --> (\w+)", line)
        if m:
            from_, to_ = m.group(1), m.group(2)
            if from_ != "[*]" and to_ != "[*]":
                transitions.add((from_, to_))
                screens.add(from_)
                screens.add(to_)
    return {"screens": screens, "transitions": transitions}


def cmd_compare(args: argparse.Namespace) -> int:
    a = Path(args.intended).expanduser()
    b = Path(args.observed).expanduser()
    if not a.exists():
        print(f"ERROR: intended journey not found: {a}", file=sys.stderr)
        return 1
    if not b.exists():
        print(f"ERROR: observed journey not found: {b}", file=sys.stderr)
        return 1
    intended = _parse_journey(a)
    observed = _parse_journey(b)

    print(f"# Compare: {a.stem} (intended) vs {b.stem} (observed)\n")
    only_intended = intended["screens"] - observed["screens"]
    only_observed = observed["screens"] - intended["screens"]
    if only_intended:
        print(f"## Screens in spec but not observed (dead-letter / unreachable)")
        for s in sorted(only_intended):
            print(f"- `{s}` — verify reachable, or remove from spec")
        print()
    if only_observed:
        print(f"## Screens observed but not in spec (drift / unintended)")
        for s in sorted(only_observed):
            print(f"- `{s}` — investigate (unexpected branch?)")
        print()
    intended_t = intended["transitions"]
    observed_t = observed["transitions"]
    only_intended_t = intended_t - observed_t
    only_observed_t = observed_t - intended_t
    if only_intended_t:
        print(f"## Transitions in spec but not observed (skipped paths)")
        for f, t in sorted(only_intended_t):
            print(f"- `{f} → {t}` — flow drives users elsewhere; spec out-of-date or path broken")
        print()
    if only_observed_t:
        print(f"## Transitions observed but not in spec (drift)")
        for f, t in sorted(only_observed_t):
            print(f"- `{f} → {t}` — investigate")
        print()
    if not (only_intended or only_observed or only_intended_t or only_observed_t):
        print("✓ Intended and observed flows match.")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    if not JOURNEYS_DIR.exists() or not list(JOURNEYS_DIR.glob("*.md")):
        print("(no journeys in vault)")
        return 0
    print("| Flow | Product | Ship | Generator |")
    print("|---|---|---|---|")
    for f in sorted(JOURNEYS_DIR.glob("*.md")):
        text = f.read_text()
        meta = {}
        if text.startswith("---\n"):
            end = text.find("\n---\n", 4)
            if end > 0:
                for line in text[4:end].splitlines():
                    if ":" in line:
                        k, _, v = line.partition(":")
                        meta[k.strip()] = v.strip().strip('"')
        print(f"| {meta.get('flow', f.stem)} | {meta.get('product','?')} | "
              f"{meta.get('ship_status','?')} | {meta.get('generator','hand')} |")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="ux-flow-mapper", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    pm = sub.add_parser("map", help="spec YAML/JSON → journey markdown")
    pm.add_argument("--spec", required=True)
    pm.add_argument("--output", required=True, help="flow slug")
    pm.set_defaults(func=cmd_map)

    pa = sub.add_parser("audit", help="manifest-driven observed-flow capture")
    pa.add_argument("--url", required=True)
    pa.add_argument("--output", required=True)
    pa.add_argument("--screens-dir", dest="screens_dir", required=True)
    pa.set_defaults(func=cmd_audit)

    pc = sub.add_parser("compare", help="diff intended vs observed journey docs")
    pc.add_argument("--intended", required=True)
    pc.add_argument("--observed", required=True)
    pc.set_defaults(func=cmd_compare)

    pl = sub.add_parser("list", help="list all journeys in vault")
    pl.set_defaults(func=cmd_list)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
