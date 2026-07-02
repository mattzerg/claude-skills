#!/usr/bin/env python3
"""codex_files — extract per-session file-touched data from Codex JSONL.

Phase 7 vector B (extension of vector 3). Walks every Codex session and
extracts paths Codex referenced (sed/cat/rg/apply_patch). Writes a sidecar
`codex_files.jsonl` and exposes a `recent-files` view.

Layout (sidecar in codex_corpus/):
  ~/.claude/state/codex_corpus/
    files.jsonl   — per-line {session_id, ts, cwd, file_paths:[...], cmd_count}

Run modes
---------
  codex_files.py backfill [--days 30]    — re-walk all sessions in window
  codex_files.py recent  [--hours 24]    — show recent file touches
  codex_files.py conflict <path>         — does Codex have an active session touching <path>?

Why: the codex_corpus session-level index says "Codex was in cwd X" but
doesn't say WHICH FILE. With this we can answer "is Codex actively editing
the file I'm about to edit?" That's the conflict-detection signal.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from collections import Counter
from pathlib import Path

HOME = Path.home()
SESSIONS_ROOT = HOME / ".codex/sessions"
CORPUS_DIR = HOME / ".claude/state/codex_corpus"
OUT = CORPUS_DIR / "files.jsonl"

# Path-shape regexes. Capture file-ish tokens from shell commands.
# Prioritized: extension-suffixed > absolute-looking > simple slug-paths
PATH_RES = [
    # Files with extensions (.py, .md, .ts, .json, .yaml, .sql, .toml, .lock, .sh, .rs, .go, .tsx, .jsx, .html, .css)
    re.compile(r"(?:^|[\s'\"=(|;&])((?:[\w\-./]+)?[\w\-]+\.(?:py|md|ts|tsx|js|jsx|json|yaml|yml|sql|toml|lock|sh|rs|go|html|css|env|conf|cfg|ini|txt|astro|vue|svelte))(?=[\s'\"<>):;|&]|$)"),
    # Absolute paths under home
    re.compile(r"(/Users/[\w\-./]+)"),
    # Relative paths with at least one slash, no extension required (e.g., zergvert/api/db)
    re.compile(r"(?:^|[\s'\"=(])(?P<path>[\w\-]+(?:/[\w\-]+){1,4})(?=[\s'\"<>):;|&]|$)"),
]

NOISE = {
    "sed", "cat", "rg", "ls", "head", "tail", "grep", "awk", "find", "mkdir", "rm",
    "cd", "pwd", "echo", "git", "npm", "yarn", "pnpm", "python3", "py", "node",
    "true", "false", "exit", "set", "export", "source", "test", "1,340p", "1,180p",
    "0/1", "tcp", "udp", "yaml", "json",
}


def iter_sessions() -> list[Path]:
    if not SESSIONS_ROOT.exists():
        return []
    return sorted(SESSIONS_ROOT.rglob("rollout-*.jsonl"))


def extract_paths(text: str) -> set[str]:
    """Pull file-path candidates from a shell command or tool-input string."""
    out: set[str] = set()
    if not text:
        return out
    for r in PATH_RES:
        for m in r.finditer(text):
            p = (m.group(1) if m.lastindex else m.group(0)).strip("'\"")
            if not p or p in NOISE or p.startswith("-"):
                continue
            # Reject obvious noise (numbers, short tokens, command flags)
            if len(p) < 3 or p.isdigit():
                continue
            # Strip trailing punctuation
            p = p.rstrip(".,;:)")
            out.add(p)
    return out


PATCH_FILE_RE = re.compile(r"\*\*\* (?:Update|Add|Delete) File: (.+)$", re.M)


def parse_session(path: Path) -> dict | None:
    meta = None
    paths: Counter = Counter()
    mutated_paths: Counter = Counter()  # paths Codex actually MODIFIED via apply_patch
    cmd_count = 0
    patch_count = 0
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if r.get("type") == "session_meta" and meta is None:
                    meta = r.get("payload", {})
                    continue
                if r.get("type") != "response_item":
                    continue
                p = r.get("payload", {})
                payload_type = p.get("type")

                # function_call (exec_command) — file READS
                if payload_type == "function_call":
                    args_raw = p.get("arguments", "")
                    if not args_raw:
                        continue
                    cmd_count += 1
                    cmd_text = args_raw
                    try:
                        if isinstance(args_raw, str):
                            a = json.loads(args_raw)
                            cmd_text = a.get("cmd", "") or a.get("command", "") or args_raw
                    except Exception:
                        cmd_text = args_raw
                    if not isinstance(cmd_text, str):
                        continue
                    for p_str in extract_paths(cmd_text):
                        paths[p_str] += 1

                # custom_tool_call with name=apply_patch — file MUTATIONS
                elif payload_type == "custom_tool_call" and p.get("name") == "apply_patch":
                    patch_text = p.get("input", "") or ""
                    if not isinstance(patch_text, str):
                        continue
                    patch_count += 1
                    for m in PATCH_FILE_RE.finditer(patch_text):
                        path_str = m.group(1).strip()
                        mutated_paths[path_str] += 1
                        paths[path_str] += 1  # mutated paths also count as touched
    except OSError:
        return None
    if not meta:
        return None
    top_paths = [p for p, _ in paths.most_common(20)]
    top_mutated = [p for p, _ in mutated_paths.most_common(15)]
    return {
        "session_id": meta.get("id", path.stem),
        "ts": meta.get("timestamp", ""),
        "cwd": meta.get("cwd", ""),
        "cmd_count": cmd_count,
        "patch_count": patch_count,
        "file_paths": top_paths,
        "mutated_paths": top_mutated,
        "path_freq": dict(paths.most_common(20)),
    }


def cmd_backfill(args) -> int:
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=args.days)
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    # Fresh write — replace entirely
    entries: list[dict] = []
    sessions = iter_sessions()
    sys.stderr.write(f"[codex_files] walking {len(sessions)} sessions, cutoff {cutoff.isoformat()}\n")
    n_parsed = 0
    for path in sessions:
        # Date-from-filename heuristic
        m = re.search(r"rollout-(\d{4}-\d{2}-\d{2})T", path.name)
        if m:
            try:
                d = dt.datetime.fromisoformat(m.group(1))
                if d < cutoff.replace(tzinfo=None):
                    continue
            except Exception:
                pass
        entry = parse_session(path)
        if not entry:
            continue
        entries.append(entry)
        n_parsed += 1
    # Sort by ts descending
    entries.sort(key=lambda e: e.get("ts", ""), reverse=True)
    OUT.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n")
    total_paths = sum(len(e["file_paths"]) for e in entries)
    print(f"[codex_files] wrote {n_parsed} sessions, ~{total_paths} unique-path mentions → {OUT}")
    return 0


def load_files() -> list[dict]:
    if not OUT.exists():
        return []
    out = []
    for line in OUT.read_text(errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def cmd_recent(args) -> int:
    entries = load_files()
    if not entries:
        print("(empty — run backfill first)")
        return 0
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=args.hours)
    print(f"# Codex files touched in last {args.hours}h")
    n = 0
    for e in entries:
        try:
            tm = dt.datetime.fromisoformat(e["ts"].replace("Z", "+00:00"))
        except Exception:
            continue
        if tm < cutoff:
            continue
        n += 1
        cwd = (e.get("cwd") or "").replace(str(HOME), "~")
        sid = (e.get("session_id") or "?")[:8]
        ts_s = tm.strftime("%m-%d %H:%M")
        files = ", ".join(e["file_paths"][:8])
        print(f"{ts_s}  {sid}  {cwd[-40:]:40}  cmds={e.get('cmd_count',0):3}")
        if files:
            print(f"             files: {files[:200]}")
    print(f"\n[codex_files] {n} session(s)", file=sys.stderr)
    return 0


def cmd_conflict(args) -> int:
    """Does Codex have an active session touching <path>?"""
    entries = load_files()
    if not entries:
        print("(empty — run backfill first)")
        return 1
    target = args.path.lower()
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=args.hours)
    hits = []
    for e in entries:
        try:
            tm = dt.datetime.fromisoformat(e["ts"].replace("Z", "+00:00"))
        except Exception:
            continue
        if tm < cutoff:
            continue
        for fp in e.get("file_paths", []):
            if target in fp.lower():
                hits.append((tm, e, fp))
                break
    if not hits:
        print(f"NO RECENT CODEX ACTIVITY on '{args.path}' (last {args.hours}h)")
        return 0
    # Separate mutations from reads
    mutated = []
    read_only = []
    target_l = args.path.lower()
    for tm, e, fp in hits:
        if any(target_l in mp.lower() or mp.lower() in target_l for mp in e.get("mutated_paths", [])):
            mutated.append((tm, e, fp))
        else:
            read_only.append((tm, e, fp))
    print(f"⚠ {len(hits)} Codex session(s) touched '{args.path}' in last {args.hours}h:")
    if mutated:
        print(f"\n  🔴 MUTATIONS ({len(mutated)} session(s) actually MODIFIED files):")
        for tm, e, fp in mutated[:5]:
            sid = (e.get("session_id") or "?")[:8]
            cwd = (e.get("cwd") or "").replace(str(HOME), "~")
            print(f"    {tm.strftime('%Y-%m-%d %H:%M')}  session={sid}  cwd={cwd[-40:]}")
            print(f"       matched path: {fp}  (patch_count={e.get('patch_count', 0)})")
    if read_only:
        print(f"\n  🟡 READS ONLY ({len(read_only)} session(s) inspected but did not modify):")
        for tm, e, fp in read_only[:5]:
            sid = (e.get("session_id") or "?")[:8]
            print(f"    {tm.strftime('%Y-%m-%d %H:%M')}  session={sid}  matched: {fp}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd")

    bf = sub.add_parser("backfill")
    bf.add_argument("--days", type=int, default=30)
    bf.set_defaults(func=cmd_backfill)

    r = sub.add_parser("recent")
    r.add_argument("--hours", type=int, default=24)
    r.set_defaults(func=cmd_recent)

    c = sub.add_parser("conflict")
    c.add_argument("path")
    c.add_argument("--hours", type=int, default=6)
    c.set_defaults(func=cmd_conflict)

    args = p.parse_args()
    if not getattr(args, "func", None):
        p.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
