#!/usr/bin/env python3
"""Action verbs — collapse decision→action into one command.

Usage:
    act.py qualify <prospect-id> [--note "..."]
    act.py kill <experiment-id> --learning "..."
    act.py win <experiment-id> --variant A|B --learning "..."
    act.py publish <content-id> [--url URL]
    act.py engage <bd-id> [--note "..."]
    act.py ship <launch-id> --date YYYY-MM-DD
    act.py close-won <prospect-id> [--value $X]
    act.py close-lost <prospect-id> [--reason "..."]

Each verb:
  1. validates source entity status (forward-only transitions)
  2. updates status + last_touch + verb-specific fields
  3. auto-regenerates index/decisions/README
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

from lib import frontmatter  # noqa: E402
from lib.entities import load_one  # noqa: E402


TODAY = dt.date.today().isoformat()


@dataclass
class Verb:
    name: str
    entity_type: str
    allowed_from: set[str]
    target_status: str
    description: str
    arg_parser: Callable[[argparse.ArgumentParser], None]
    build_updates: Callable[[argparse.Namespace], dict[str, Any]]


def _no_args(p: argparse.ArgumentParser) -> None:
    pass


def _kill_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--learning", required=True, help="What did we learn?")


def _win_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--variant", required=True, choices=["A", "B"])
    p.add_argument("--learning", required=True)


def _publish_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--url", help="published URL")


def _ship_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--date", required=True, help="ship date YYYY-MM-DD")


def _note_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--note", help="touch note")


def _close_lost_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--reason", help="why lost")


def _decide_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("option_key", help="key of the chosen option (see entity file)")
    p.add_argument("--rationale", help="why this option (optional)")
    p.add_argument("--dry-run", action="store_true", help="preview cascade without applying")


def _close_won_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--value", type=int, help="deal value (USD)")


def _kill_updates(ns: argparse.Namespace) -> dict[str, Any]:
    return {
        "status": "killed",
        "verdict": "kill",
        "concluded": TODAY,
        "learning": ns.learning,
    }


def _win_updates(ns: argparse.Namespace) -> dict[str, Any]:
    return {
        "status": "won",
        "verdict": f"scale-{ns.variant}",
        "concluded": TODAY,
        "learning": ns.learning,
    }


def _publish_updates(ns: argparse.Namespace) -> dict[str, Any]:
    updates: dict[str, Any] = {"status": "published", "published_date": TODAY}
    if ns.url:
        updates["published_url"] = ns.url
    return updates


def _ship_updates(ns: argparse.Namespace) -> dict[str, Any]:
    try:
        dt.date.fromisoformat(ns.date)
    except ValueError:
        raise SystemExit(f"--date {ns.date!r} is not ISO YYYY-MM-DD")
    return {"status": "scheduled", "ship_date": ns.date}


def _close_won_updates(ns: argparse.Namespace) -> dict[str, Any]:
    updates: dict[str, Any] = {"status": "won", "closed_at": TODAY}
    if ns.value is not None:
        updates["proposed_value"] = ns.value
    return updates


def _close_lost_updates(ns: argparse.Namespace) -> dict[str, Any]:
    updates: dict[str, Any] = {"status": "lost", "closed_at": TODAY}
    if ns.reason:
        updates["lost_reason"] = ns.reason
    return updates


VERBS: dict[str, Verb] = {
    "qualify": Verb(
        name="qualify",
        entity_type="prospect",
        allowed_from={"inbound"},
        target_status="qualified",
        description="prospect inbound → qualified",
        arg_parser=_note_args,
        build_updates=lambda ns: {"status": "qualified", "next_action": ns.note or "Schedule discovery call"},
    ),
    "engage": Verb(
        name="engage",
        entity_type="bd_target",
        allowed_from={"planned", "outreach"},
        target_status="engaged",
        description="bd_target → engaged",
        arg_parser=_note_args,
        build_updates=lambda ns: {"status": "engaged", "next_action": ns.note or "Continue conversation"},
    ),
    "kill": Verb(
        name="kill",
        entity_type="experiment",
        allowed_from={"running", "proposed"},
        target_status="killed",
        description="experiment → killed (with --learning)",
        arg_parser=_kill_args,
        build_updates=_kill_updates,
    ),
    "win": Verb(
        name="win",
        entity_type="experiment",
        allowed_from={"running"},
        target_status="won",
        description="experiment → won (with --variant + --learning)",
        arg_parser=_win_args,
        build_updates=_win_updates,
    ),
    "publish": Verb(
        name="publish",
        entity_type="content",
        allowed_from={"drafted", "reviewed", "scheduled"},
        target_status="published",
        description="content → published",
        arg_parser=_publish_args,
        build_updates=_publish_updates,
    ),
    "ship": Verb(
        name="ship",
        entity_type="launch",
        allowed_from={"drafting", "ready"},
        target_status="scheduled",
        description="launch → scheduled (with --date)",
        arg_parser=_ship_args,
        build_updates=_ship_updates,
    ),
    "close-won": Verb(
        name="close-won",
        entity_type="prospect",
        allowed_from={"qualified", "scoped", "proposal-out"},
        target_status="won",
        description="prospect → won",
        arg_parser=_close_won_args,
        build_updates=_close_won_updates,
    ),
    "close-lost": Verb(
        name="close-lost",
        entity_type="prospect",
        allowed_from={"qualified", "scoped", "proposal-out", "inbound"},
        target_status="lost",
        description="prospect → lost",
        arg_parser=_close_lost_args,
        build_updates=_close_lost_updates,
    ),
    "decide": Verb(
        name="decide",
        entity_type="decision",
        allowed_from={"open", "deferred"},
        target_status="decided",
        description="decision → decided (with chosen option-key)",
        arg_parser=_decide_args,
        build_updates=lambda ns: {
            "status": "decided",
            "decided": ns.option_key,
            "decided_at": TODAY,
            **({"rationale": ns.rationale} if ns.rationale else {}),
        },
    ),
    "defer": Verb(
        name="defer",
        entity_type="decision",
        allowed_from={"open"},
        target_status="deferred",
        description="decision → deferred (kick the can)",
        arg_parser=_note_args,
        build_updates=lambda ns: {
            "status": "deferred",
            **({"defer_reason": ns.note} if ns.note else {}),
        },
    ),
}


def hint_for_decision(rule: str, entity_id: str) -> str | None:
    """Return a suggested `gtm act <verb> <id>` string for a given decision rule."""
    rule_to_verb = {
        "experiment.kill_overdue": ("kill", '--learning "fill in"'),
        "experiment.kill_approaching": ("kill", '--learning "fill in"'),
        "prospect.high_score_inbound": ("qualify", ""),
        "prospect.inbound_stale": ("qualify", ""),
        "prospect.proposal_due": ("close-won", ""),
        "content.target_near": ("publish", ""),
        "content.schedule_or_publish": ("publish", ""),
        "launch.ship_date_missing": ("ship", "--date YYYY-MM-DD"),
        "launch.ship_near": ("ship", "--date YYYY-MM-DD"),
        "bd.stale_touch": ("engage", ""),
        # decision.open uses the `decide` shorthand (also available as `act decide`)
        "decision.open": ("decide", "<option-key>"),
    }
    pair = rule_to_verb.get(rule)
    if not pair or not entity_id:
        return None
    verb, args = pair
    # `decide` has a top-level shorthand alias
    prefix = "gtm decide" if verb == "decide" else f"gtm act {verb}"
    if verb == "decide":
        return f"{prefix} {entity_id}{' ' + args if args else ''}"
    return f"{prefix} {entity_id}{' ' + args if args else ''}"


def run(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    verb_name = argv[0]
    if verb_name not in VERBS:
        print(f"unknown verb: {verb_name}\n", file=sys.stderr)
        print("Available verbs:")
        for v in VERBS.values():
            print(f"  {v.name:<12} {v.description}")
        return 2

    verb = VERBS[verb_name]
    p = argparse.ArgumentParser(prog=f"gtm-hub act {verb.name}", description=verb.description)
    p.add_argument("entity_id")
    verb.arg_parser(p)
    ns = p.parse_args(argv[1:])

    entity = load_one(ns.entity_id)
    if not entity:
        print(f"entity {ns.entity_id!r} not found", file=sys.stderr)
        return 1
    if entity.type != verb.entity_type:
        print(
            f"verb {verb.name!r} expects type={verb.entity_type}, got {entity.type}",
            file=sys.stderr,
        )
        return 1
    current = entity.meta.get("status")
    if current not in verb.allowed_from:
        print(
            f"verb {verb.name!r} requires source status ∈ {sorted(verb.allowed_from)}; "
            f"current = {current!r}",
            file=sys.stderr,
        )
        return 1

    updates = verb.build_updates(ns)
    updates["last_touch"] = TODAY
    dry_run = bool(getattr(ns, "dry_run", False))

    # CASCADE preview/execute for the `decide` verb (only verb that supports cascade today)
    cascade_log: list[str] = []
    if verb.name == "decide":
        from lib.cascade import execute as _cascade_execute  # local import
        cascade_spec = entity.meta.get("cascade")
        cascade_log = _cascade_execute(cascade_spec, ns.option_key, dry_run=dry_run)

    if dry_run:
        title = entity.meta.get("title") or entity.id
        print(f"=== DRY RUN — would record {verb.name} on {entity.id} ===")
        print(f"  {entity.type} {entity.id} ({title[:50]}): {current} → {verb.target_status}")
        for k, v in updates.items():
            if k in ("status", "last_touch"):
                continue
            print(f"    {k}: {v}")
        if cascade_log:
            print(f"\n  CASCADE ({len(cascade_log)} action{'s' if len(cascade_log) != 1 else ''}):")
            for line in cascade_log:
                print(line)
        else:
            print("  (no cascade defined for this option)")
        print("\nRe-run without --dry-run to apply.")
        return 0

    # Apply the primary mutation
    text = Path(entity.path).read_text(encoding="utf-8")
    new_text = frontmatter.update_in_text(text, updates)
    # Write to canonical iCloud path (may differ from read path if mirror was used)
    write_path = _canonical_write_path(entity.path)
    write_path.write_text(new_text, encoding="utf-8")

    title = entity.meta.get("title") or entity.id
    print(
        f"✓ {entity.type} {entity.id} ({title[:50]}): "
        f"{current} → {verb.target_status}"
    )
    for k, v in updates.items():
        if k in ("status", "last_touch"):
            continue
        print(f"    {k}: {v}")
    if cascade_log:
        print(f"\nCascade applied ({len(cascade_log)} action{'s' if len(cascade_log) != 1 else ''}):")
        for line in cascade_log:
            print(line)

    # Auto-regenerate
    import subprocess
    rc = subprocess.run(
        [sys.executable, str(THIS_DIR.parent / "run.py"), "regenerate"],
        capture_output=True,
        text=True,
    )
    if rc.returncode != 0:
        print("warning: regenerate failed", file=sys.stderr)
        print(rc.stderr, file=sys.stderr)
    return 0


def _canonical_write_path(read_path: str) -> Path:
    """Map any read path (mirror or iCloud) to the canonical iCloud write path."""
    from lib.entities import GROWTH_DIR, READ_GROWTH_DIR
    p = Path(read_path)
    try:
        rel = p.resolve().relative_to(READ_GROWTH_DIR.resolve())
        return GROWTH_DIR / rel
    except (ValueError, OSError):
        return p


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
