#!/usr/bin/env python3
"""aitr — internal LLM router CLI.

Verbs:
    pick           Return one recommendation (default)
    explain        Return top-3 with rationale
    refresh-cache  Force-refresh the local catalog cache
    list-models    Print the current catalog with key fields
    replay <id>    Print a prior decision by decision_id

Signal: pass either `--signal '<json>'` or repeated `key=value` args.

Exit codes:
    0  success — recommendation emitted
    1  usage error
    2  no candidate satisfies hard constraints
    3  data backend unreachable AND no bundled snapshot — fail-loud
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL_DIR))

from task_signal import (  # noqa: E402
    Signal,
    SignalError,
    parse_kv_args,
    signal_from_json,
    signal_from_kv,
)
from catalog import (  # noqa: E402
    CatalogUnavailable,
    load_catalog,
    load_routing_table,
)
from penalties import load_penalties  # noqa: E402
from ranker import Candidate, RankerError, rank  # noqa: E402


DEFAULT_DECISIONS_LOG = Path.home() / ".local" / "state" / "zerg" / "aitr" / "decisions.log"


def _detect_active_provider() -> str | None:
    """Best-effort sniff of the active session's provider via env vars."""
    if os.environ.get("CLAUDECODE") or any(k.startswith("CLAUDE_CODE_") for k in os.environ):
        return "anthropic"
    if any(k.startswith("CODEX_") for k in os.environ):
        return "openai"
    return None


def _new_decision_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"aitr-{stamp}-{secrets.token_hex(3)}"


def _log_decision(record: dict, *, log_path: Path = DEFAULT_DECISIONS_LOG) -> None:
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError as exc:
        print(f"aitr: failed to write decisions log {log_path}: {exc}", file=sys.stderr)


def _candidate_to_summary(c: Candidate) -> dict:
    return {
        "model": c.model,
        "model_class": c.model_class,
        "provider": c.provider,
        "score": c.score,
        "capability": c.capability,
        "cost_score": c.cost,
        "latency_score": c.latency,
        "estimated_cost_usd": c.estimated_cost_usd,
        "context_window": c.context_window,
        "reason": c.reason,
    }


def _emit(result: dict, *, fmt: str) -> None:
    if fmt in ("json", "both"):
        print(json.dumps(result, indent=2))
    if fmt in ("human", "both"):
        head = (
            f"{result['model']} — {result['reason']} "
            f"(score={result['score']:.2f}, ~${result['estimated_cost_usd']:.4f})"
        )
        print(head, file=sys.stderr)


def _build_signal(args: argparse.Namespace) -> Signal:
    if args.signal:
        return signal_from_json(args.signal)
    return signal_from_kv(parse_kv_args(args.kv))


def _cmd_pick(args: argparse.Namespace, *, explain: bool = False) -> int:
    try:
        signal = _build_signal(args)
    except SignalError as exc:
        print(f"aitr: bad signal: {exc}", file=sys.stderr)
        return 1

    try:
        catalog_src = load_catalog(force_refresh=args.refresh, offline=args.offline)
    except CatalogUnavailable as exc:
        print(f"aitr: {exc}", file=sys.stderr)
        return 3

    routing_table = load_routing_table()
    task_rules = (routing_table.get("task_kinds") or {}).get(signal.task_kind) or {}

    # Image-gen + similar: delegate signal — caller should route OUT to a different skill.
    delegate_to = task_rules.get("delegate_to")
    if delegate_to:
        out = {
            "decision_id": _new_decision_id(),
            "verb": "delegate",
            "delegate_to": delegate_to,
            "reason": f"task_kind={signal.task_kind!r} routes to {delegate_to!r} (not a model pick)",
            "signal": signal.to_dict(),
        }
        _log_decision({**out, "ts": datetime.now(timezone.utc).isoformat(), "caller": signal.caller})
        _emit(out, fmt=args.format)
        return 0

    active_provider = _detect_active_provider() if signal.provider_constraint == "any" else None

    # Feedback corrections (wrong-model-picked) bias future picks away from
    # corrected models. Never fatal — empty dict on any failure.
    penalties = load_penalties()

    try:
        candidates = rank(
            signal.to_dict(),
            catalog_src.body,
            routing_table,
            active_provider=active_provider,
            top_n=5,
            penalties=penalties,
        )
    except RankerError as exc:
        print(f"aitr: {exc}", file=sys.stderr)
        return 2

    top = candidates[0]
    decision_id = _new_decision_id()
    out: dict = {
        "decision_id": decision_id,
        "model": top.model,
        "model_class": top.model_class,
        "provider": top.provider,
        "estimated_cost_usd": top.estimated_cost_usd,
        "reason": top.reason,
        "score": top.score,
        "context_window": top.context_window,
        "catalog_source": catalog_src.source,
        "active_provider": active_provider,
        "signal": signal.to_dict(),
    }
    if explain:
        out["alternatives"] = [_candidate_to_summary(c) for c in candidates[1:]]
        out["routing_rules"] = task_rules

    _log_decision(
        {
            **out,
            "ts": datetime.now(timezone.utc).isoformat(),
            "caller": signal.caller,
        }
    )
    _emit(out, fmt=args.format)
    return 0


def _cmd_refresh_cache(args: argparse.Namespace) -> int:
    try:
        src = load_catalog(force_refresh=True)
        print(f"aitr: catalog refreshed from {src.source}", file=sys.stderr)
        print(json.dumps({"source": src.source, "model_count": len(src.body.get("models") or [])}))
        return 0
    except CatalogUnavailable as exc:
        print(f"aitr: {exc}", file=sys.stderr)
        return 3


def _cmd_list_models(args: argparse.Namespace) -> int:
    try:
        src = load_catalog(offline=args.offline)
    except CatalogUnavailable as exc:
        print(f"aitr: {exc}", file=sys.stderr)
        return 3
    rows = []
    for m in src.body.get("models") or []:
        pricing = m.get("pricing") or {}
        rows.append({
            "id": m.get("id"),
            "provider": m.get("provider"),
            "model_class": m.get("model_class"),
            "status": m.get("status"),
            "context_window": m.get("context_window"),
            "input_per_mtok": pricing.get("input_per_mtok"),
            "output_per_mtok": pricing.get("output_per_mtok"),
            "tags": m.get("tags"),
        })
    print(json.dumps({"source": src.source, "count": len(rows), "models": rows}, indent=2))
    return 0


def _cmd_replay(args: argparse.Namespace) -> int:
    log_path = DEFAULT_DECISIONS_LOG
    if not log_path.exists():
        print(f"aitr: no decisions log at {log_path}", file=sys.stderr)
        return 1
    target = args.decision_id
    with log_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("decision_id") == target:
                print(json.dumps(rec, indent=2))
                return 0
    print(f"aitr: decision_id {target!r} not found in {log_path}", file=sys.stderr)
    return 1


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="aitr",
        description="Pick the right LLM for a task. Recommender, not a gateway.",
    )

    # Global flags live on a parent parser so they're available BEFORE or AFTER
    # the subcommand verb — `aitr --offline pick ...` and `aitr pick --offline ...`
    # both work.
    global_parser = argparse.ArgumentParser(add_help=False)
    global_parser.add_argument("--format", choices=("json", "human", "both"), default="both")
    global_parser.add_argument("--offline", action="store_true",
                               help="Skip the live HTTP fetch; use cache or bundled snapshot only.")
    global_parser.add_argument("--refresh", action="store_true",
                               help="Force a live fetch even if cache is fresh.")

    # Also add them to the top-level parser for `aitr --offline ...` usage.
    p.add_argument("--format", choices=("json", "human", "both"), default="both")
    p.add_argument("--offline", action="store_true")
    p.add_argument("--refresh", action="store_true")

    subs = p.add_subparsers(dest="verb")

    def add_signal_args(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("--signal", help="Signal as a JSON object string.")
        sub.add_argument("kv", nargs="*", help="Signal as key=value pairs.")

    sub_pick = subs.add_parser("pick", parents=[global_parser],
                               help="Return one recommendation (default).")
    add_signal_args(sub_pick)
    sub_explain = subs.add_parser("explain", parents=[global_parser],
                                  help="Return top-3 with rationale.")
    add_signal_args(sub_explain)
    subs.add_parser("refresh-cache", parents=[global_parser],
                    help="Force-refresh the local catalog cache.")
    subs.add_parser("list-models", parents=[global_parser],
                    help="Print the catalog with key fields.")
    sub_replay = subs.add_parser("replay", parents=[global_parser],
                                 help="Print a prior decision by decision_id.")
    sub_replay.add_argument("decision_id")

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_argparser()
    # Default to `pick` if no verb given but kv args are present.
    args_in = list(sys.argv[1:] if argv is None else argv)
    if args_in and args_in[0] not in {"pick", "explain", "refresh-cache", "list-models", "replay"} \
            and not args_in[0].startswith("-"):
        args_in.insert(0, "pick")
    elif not args_in:
        args_in = ["pick"]
    args = parser.parse_args(args_in)

    if args.verb == "explain":
        return _cmd_pick(args, explain=True)
    if args.verb == "refresh-cache":
        return _cmd_refresh_cache(args)
    if args.verb == "list-models":
        return _cmd_list_models(args)
    if args.verb == "replay":
        return _cmd_replay(args)
    # default: pick
    return _cmd_pick(args, explain=False)


if __name__ == "__main__":
    sys.exit(main())
