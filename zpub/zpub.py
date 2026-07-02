#!/usr/bin/env python3
"""zpub — Publishing/Content Board CLI.

Source of truth lives in MattZerg/Projects/Zerg-Production/Growth/publishing/<id>.md as
YAML frontmatter + free-form body. Bidirectionally syncs to a Zergboard
"Publishing" board (PUB-* prefix) via a fenced <!-- zpub:state --> block.

Verbs:
  zpub                      action-led RAG table (reds first, hide greens)
  zpub all                  full table
  zpub <id>                 entry detail
  zpub add                  wizard to create new entry
  zpub set <id> KEY VALUE   update entry field
  zpub sync                 bidirectional sync with Zergboard
  zpub open <id>            open vault entry in $EDITOR
  zpub bootstrap-board      one-time create the Publishing board
  zpub --reds-only [--max=N]  compact reds-only view (used by morning-brief)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

SKILL_DIR = Path(__file__).resolve().parent
VAULT_ROOT = Path(
    "/Users/mattheweisner/Obsidian/Zerg"
)
PUB_DIR = VAULT_ROOT / "MattZerg/Projects/Zerg-Production/Growth/publishing"
META_DIR = PUB_DIR / "_meta"
INDEX_PATH = META_DIR / "index.json"
GATES_PATH = META_DIR / "gates.json"
CONFLICTS_PATH = META_DIR / "conflicts.log"
BOARD_CONFIG = SKILL_DIR / "board.json"
GATES_SKILL_PATH = SKILL_DIR / "gates.json"

PT = ZoneInfo("America/Los_Angeles")

VALID_TYPES = [
    "blog", "launch", "case-study", "web-page", "video",
    "email", "social", "one-pager", "other",
]
VALID_STATUSES = [
    "ideating", "drafting", "review", "scheduled",
    "published", "distributed", "archived",
]
VALID_GATE_VALUES = ["passed", "pending", "failed", "n_a"]

STATUS_TO_COLUMN = {
    "ideating": "Drafting",
    "drafting": "Drafting",
    "review": "Review",
    "scheduled": "Scheduled",
    "published": "Published",
    "distributed": "Published",
    "archived": "Archived",
}

DEFAULT_COLUMNS = ["Drafting", "Review", "Scheduled", "Published", "Archived"]


# ---------- Tiny YAML frontmatter parser ----------
# We avoid PyYAML dep — frontmatter we write ourselves stays in a
# predictable subset (scalars, lists of scalars, lists of single-key dicts).

class YamlError(Exception):
    pass


def _parse_scalar(s: str) -> Any:
    s = s.strip()
    if s == "" or s == "null" or s == "~":
        return None
    if s == "[]":
        return []
    if s == "{}":
        return {}
    if s.lower() == "true":
        return True
    if s.lower() == "false":
        return False
    # Double-quoted: defer to json.loads so \uXXXX, \n, etc. decode correctly.
    if s.startswith('"') and s.endswith('"') and len(s) >= 2:
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return s[1:-1]
    if s.startswith("'") and s.endswith("'") and len(s) >= 2:
        return s[1:-1]
    if re.match(r"^-?\d+$", s):
        return int(s)
    if re.match(r"^-?\d+\.\d+$", s):
        return float(s)
    return s


def _is_quoted_scalar(s: str) -> bool:
    s = s.strip()
    return (
        (s.startswith('"') and s.endswith('"') and len(s) >= 2)
        or (s.startswith("'") and s.endswith("'") and len(s) >= 2)
    )


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Return (frontmatter_dict, body_str)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_text = text[3:end].lstrip("\n")
    body = text[end + 4:].lstrip("\n")
    return _parse_yaml_block(fm_text), body


def _parse_yaml_block(text: str) -> dict[str, Any]:
    """Parse the small YAML subset we use. Recursive on nested mappings."""
    lines = text.splitlines()
    result: dict[str, Any] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        # top-level key (no leading whitespace)
        if not line.startswith((" ", "\t")):
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
            if not m:
                raise YamlError(f"Bad line: {line!r}")
            key, rest = m.group(1), m.group(2)
            if rest.strip() == "":
                # nested mapping or list — collect indented children
                children: list[str] = []
                j = i + 1
                while j < len(lines) and (lines[j] == "" or lines[j].startswith((" ", "\t"))):
                    children.append(lines[j])
                    j += 1
                if not children or all(not c.strip() for c in children):
                    result[key] = None
                else:
                    # detect list vs map by first non-blank child
                    first = next(c for c in children if c.strip())
                    stripped = first.lstrip()
                    if stripped.startswith("- "):
                        result[key] = _parse_yaml_list(children)
                    else:
                        # dedent and recurse
                        dedented = _dedent_block(children)
                        result[key] = _parse_yaml_block(dedented)
                i = j
                continue
            else:
                result[key] = _parse_scalar(rest)
                i += 1
                continue
        i += 1
    return result


def _dedent_block(lines: list[str]) -> str:
    """Strip the common leading indent."""
    indents = [len(l) - len(l.lstrip()) for l in lines if l.strip()]
    if not indents:
        return ""
    n = min(indents)
    out = []
    for l in lines:
        if not l.strip():
            out.append("")
        else:
            out.append(l[n:])
    return "\n".join(out)


def _parse_yaml_list(lines: list[str]) -> list[Any]:
    """Parse a YAML list (each item is `- scalar` or `- key: value` block)."""
    items: list[Any] = []
    # First, group by item: each '- ...' starts a new item; subsequent
    # indented lines (without leading '-') belong to the item.
    groups: list[list[str]] = []
    current: list[str] = []
    base_indent = None
    for l in lines:
        if not l.strip():
            if current:
                current.append(l)
            continue
        stripped = l.lstrip()
        indent = len(l) - len(stripped)
        if stripped.startswith("- "):
            if current:
                groups.append(current)
            base_indent = indent
            current = [l]
        else:
            if current is None:
                continue
            current.append(l)
    if current:
        groups.append(current)

    for grp in groups:
        first = grp[0].lstrip()
        # Remove the leading "- "
        head = first[2:].rstrip()
        rest = grp[1:]
        # Quoted scalars (which may legally contain ':') are atomic.
        if not rest and (_is_quoted_scalar(head) or ":" not in head):
            items.append(_parse_scalar(head))
            continue
        # Build a synthetic block: head becomes first key:value if it has ':'
        block_lines = []
        if head:
            block_lines.append(head)
        for r in rest:
            # strip the per-item indent (base_indent + 2)
            n = (len(grp[0]) - len(grp[0].lstrip())) + 2
            block_lines.append(r[n:] if len(r) >= n else r.lstrip())
        block = "\n".join(block_lines)
        if ":" in block.splitlines()[0]:
            items.append(_parse_yaml_block(block))
        else:
            items.append(_parse_scalar(block))
    return items


def dump_frontmatter(data: dict[str, Any]) -> str:
    """Emit YAML frontmatter for our subset. Stable key order."""
    lines = ["---"]
    # canonical key order — anything else trailing
    canonical = [
        "id", "title", "type", "status", "publish_target", "publish_actual",
        "owner", "surfaces", "gates", "blockers", "links",
        "zergboard_card_id", "updated_at",
    ]
    seen: set[str] = set()
    for k in canonical:
        if k in data:
            lines.extend(_dump_pair(k, data[k]))
            seen.add(k)
    for k in data:
        if k not in seen:
            lines.extend(_dump_pair(k, data[k]))
    lines.append("---")
    return "\n".join(lines) + "\n"


def _dump_pair(key: str, value: Any, indent: int = 0) -> list[str]:
    pad = "  " * indent
    if value is None:
        return [f"{pad}{key}: null"]
    if isinstance(value, bool):
        return [f"{pad}{key}: {'true' if value else 'false'}"]
    if isinstance(value, (int, float)):
        return [f"{pad}{key}: {value}"]
    if isinstance(value, str):
        return [f"{pad}{key}: {_dump_scalar(value)}"]
    if isinstance(value, list):
        if not value:
            # Skip empty lists entirely — keeps frontmatter clean and avoids
            # `[]` literal round-trip ambiguity in our hand-rolled parser.
            return []
        out = [f"{pad}{key}:"]
        for item in value:
            if isinstance(item, dict):
                # First key on same line as "- "
                items = list(item.items())
                first_k, first_v = items[0]
                out.append(f"{pad}  - {first_k}: {_dump_scalar(first_v) if isinstance(first_v, str) else first_v}")
                for k2, v2 in items[1:]:
                    out.append(f"{pad}    {k2}: {_dump_scalar(v2) if isinstance(v2, str) else v2}")
            else:
                out.append(f"{pad}  - {_dump_scalar(item) if isinstance(item, str) else item}")
        return out
    if isinstance(value, dict):
        out = [f"{pad}{key}:"]
        for k2, v2 in value.items():
            out.extend(_dump_pair(k2, v2, indent + 1))
        return out
    return [f"{pad}{key}: {value}"]


def _dump_scalar(s: str) -> str:
    if s == "":
        return '""'
    if any(ch in s for ch in [":", "#", "\n"]) or s.strip() != s:
        return json.dumps(s)
    if s.lower() in {"true", "false", "null", "yes", "no", "on", "off", "~"}:
        return f'"{s}"'
    if re.match(r"^-?\d+(\.\d+)?$", s):
        return f'"{s}"'
    return s


# ---------- Entity model ----------

@dataclass
class Entry:
    id: str
    title: str
    type: str
    status: str
    publish_target: Optional[str] = None        # ISO date YYYY-MM-DD
    publish_actual: Optional[str] = None
    owner: str = "matthew"
    surfaces: list[dict[str, Any]] = field(default_factory=list)
    gates: dict[str, str] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    links: list[dict[str, Any]] = field(default_factory=list)
    zergboard_card_id: Optional[str] = None
    updated_at: str = ""
    body: str = ""
    date_confirmed: bool = False  # per feedback_launch_dates_aspirational: target_date is aspirational until human confirms
    # Frontmatter keys this model doesn't know about (e.g. the human `approval`
    # lock block written per the gigacontext-2026-05-19 incident). MUST round-trip
    # through save_entry — before this field existed, any `zpub set` silently
    # deleted the approval block from the rewritten frontmatter.
    extra: dict[str, Any] = field(default_factory=dict)
    _path: Optional[Path] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "status": self.status,
            "publish_target": self.publish_target,
            "publish_actual": self.publish_actual,
            "date_confirmed": self.date_confirmed,
            "owner": self.owner,
            "surfaces": self.surfaces,
            "gates": self.gates,
            "blockers": self.blockers,
            "links": self.links,
            "zergboard_card_id": self.zergboard_card_id,
            "updated_at": self.updated_at,
        }
        for k, v in self.extra.items():
            if k not in d:
                d[k] = v
        return d


def _parse_iso8601(s: str) -> Optional[dt.datetime]:
    if not s:
        return None
    try:
        s2 = s.replace("Z", "+00:00")
        return dt.datetime.fromisoformat(s2)
    except ValueError:
        return None


def _parse_iso_date(s: Any) -> Optional[dt.date]:
    if not s:
        return None
    if isinstance(s, dt.date):
        return s
    s = str(s).strip()
    try:
        return dt.date.fromisoformat(s[:10])
    except ValueError:
        return None


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_ENTRY_FM_KEYS = {
    "id", "title", "type", "status", "publish_target", "publish_actual",
    "owner", "surfaces", "gates", "blockers", "links", "zergboard_card_id",
    "updated_at", "date_confirmed",
}


def load_entry(path: Path) -> Entry:
    text = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    e = Entry(
        id=fm.get("id") or path.stem,
        title=fm.get("title") or "(untitled)",
        type=fm.get("type") or "other",
        status=fm.get("status") or "drafting",
        publish_target=str(fm["publish_target"]) if fm.get("publish_target") else None,
        publish_actual=str(fm["publish_actual"]) if fm.get("publish_actual") else None,
        owner=fm.get("owner") or "matthew",
        surfaces=fm.get("surfaces") or [],
        gates=fm.get("gates") or {},
        blockers=fm.get("blockers") or [],
        links=fm.get("links") or [],
        zergboard_card_id=fm.get("zergboard_card_id"),
        updated_at=fm.get("updated_at") or "",
        body=body,
        date_confirmed=bool(fm.get("date_confirmed", False)),
        extra={k: v for k, v in fm.items() if k not in _ENTRY_FM_KEYS},
    )
    e._path = path
    return e


def save_entry(e: Entry) -> Path:
    PUB_DIR.mkdir(parents=True, exist_ok=True)
    path = e._path or (PUB_DIR / f"{e.id}.md")
    fm = dump_frontmatter(e.to_dict())
    body = e.body if e.body.endswith("\n") or not e.body else e.body + "\n"
    path.write_text(fm + "\n" + body, encoding="utf-8")
    e._path = path
    rebuild_index()
    return path


def all_entries() -> list[Entry]:
    if not PUB_DIR.exists():
        return []
    out = []
    for p in sorted(PUB_DIR.glob("*.md")):
        if p.name.startswith("_") or p.parent.name == "_meta":
            continue
        try:
            out.append(load_entry(p))
        except Exception as ex:  # noqa: BLE001
            print(f"warn: failed to parse {p.name}: {ex}", file=sys.stderr)
    return out


def find_entry(ident: str) -> Optional[Entry]:
    """Resolve by full id, by suffix match, or by Zergboard external id (PUB-N)."""
    entries = all_entries()
    # Exact id
    for e in entries:
        if e.id == ident:
            return e
    # Substring on id or title
    lc = ident.lower()
    matches = [e for e in entries if lc in e.id.lower() or lc in e.title.lower()]
    if len(matches) == 1:
        return matches[0]
    return None


def rebuild_index() -> None:
    META_DIR.mkdir(parents=True, exist_ok=True)
    entries = all_entries()
    payload = {
        "generated_at": now_iso(),
        "count": len(entries),
        "entries": [e.to_dict() | {"_path": str(e._path) if e._path else None} for e in entries],
    }
    INDEX_PATH.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


# ---------- RAG ----------

def load_gates_config() -> dict[str, list[str]]:
    if GATES_PATH.exists():
        try:
            return json.loads(GATES_PATH.read_text())
        except json.JSONDecodeError:
            pass
    return json.loads(GATES_SKILL_PATH.read_text())


def required_gates(entry_type: str) -> list[str]:
    cfg = load_gates_config()
    return cfg.get(entry_type, cfg.get("other", ["signoff"]))


def rag_state(e: Entry) -> tuple[str, list[str]]:
    """4-state RAG.

    RED    = status `ideating` (no draft) OR any required gate `failed`
    AMBER  = status `drafting` (rough draft, work-in-progress)
    YELLOW = status `review` or `scheduled` (polishing / awaiting approval)
    GREEN  = terminal status OR all required gates passed
    """
    reasons: list[str] = []
    is_terminal = e.status in ("published", "distributed", "archived")
    if is_terminal:
        return "green", [e.status]

    failed = [k for k, v in e.gates.items() if v == "failed"]
    if failed:
        return "red", [f"gate failed: {', '.join(failed)}"]

    if e.status == "ideating":
        reasons.append("needs draft")
        if e.blockers:
            reasons.append(e.blockers[0])
        return "red", reasons

    required = required_gates(e.type)
    pending = [g for g in required if e.gates.get(g, "pending") == "pending"]
    schedule_unconfirmed = e.status == "scheduled" and not e.date_confirmed

    if not pending and not e.blockers and not schedule_unconfirmed:
        return "green", ["all gates passed"]

    if e.blockers:
        reasons.append(e.blockers[0])
    if schedule_unconfirmed:
        reasons.append("publish date not confirmed by human")
    if pending:
        reasons.append(f"gate pending: {pending[0]}")

    color = "yellow" if e.status in ("review", "scheduled") else "amber"

    # Pencilled-near-term bump-down: review + within 3 days + date_confirmed=false
    # should NOT look polished — render AMBER so the eye reads "uncertain", not
    # "ready to ship." See ~/.claude/plans/synchronous-yawning-storm.md A3.
    if color == "yellow" and e.status == "review" and not e.date_confirmed:
        target = _parse_iso_date(e.publish_target)
        if target:
            today = dt.datetime.now(PT).date()
            if (target - today).days <= 3:
                color = "amber"
                reasons.append("near-term date is pencilled, not confirmed")

    # Phantom-date guard (Matt 2026-06-08): a near-term publish_target on an
    # entry that is not actually drafted — status `drafting`/`ideating` with
    # ZERO required gates passed — is a false commitment. It must read RED, not
    # a benign amber, so a skeleton can never masquerade as "ships in N days."
    # Cheap (no file I/O): "0 gates passed + near date + not in review" is the
    # signal. See feedback_zpub_phantom_date.md.
    target = _parse_iso_date(e.publish_target)
    if target and e.status in ("ideating", "drafting"):
        days_out = (target - dt.datetime.now(PT).date()).days
        gates_passed = sum(1 for v in e.gates.values() if v == "passed")
        if days_out <= 3 and gates_passed == 0:
            return "red", [
                "⚠ phantom date: near-term slot but not drafted "
                "(0 gates passed) — draft it or clear the date"
            ] + reasons

    return color, reasons


IN_FLIGHT_STATUSES = ("scheduled", "published", "distributed", "archived")


def is_in_flight(e: Entry) -> tuple[bool, str]:
    """Terminal-state check across status + surfaces.

    An entry is IN FLIGHT when it is already moving toward (or past) publish
    and is not a candidate for further work. Per
    `feedback_check_in_flight_across_silos.md` — proposing work on an in-flight
    entry implies undoing progress already made.

    Returns (in_flight, reason). Reason is the human-readable marker that
    triggered the check.
    """
    if e.status in IN_FLIGHT_STATUSES:
        return True, f"status={e.status}"
    for s in e.surfaces:
        path = (s.get("path") or "").lower()
        kind = (s.get("kind") or "").lower()
        if "approved-pr" in kind or "merged-pr" in kind:
            return True, f"surface: {s.get('kind')}"
        if "approved" in path and "merged" in path:
            return True, "merged-approved PR surface"
    return False, ""


def next_move(e: Entry) -> str:
    """Suggest the single next move for a red entry."""
    if e.blockers:
        return f"resolve: {e.blockers[0]}"
    failed = [k for k, v in e.gates.items() if v == "failed"]
    if failed:
        return f"redo gate: {failed[0]}"
    target = _parse_iso_date(e.publish_target)
    today = dt.datetime.now(PT).date()
    if target and target < today and e.status not in ("published", "distributed", "archived"):
        return f"publish OR push date: zpub set {e.id} publish_target YYYY-MM-DD"
    return f"open: zpub open {e.id}"


# ---------- Commands ----------

CACHE_STALE_SECONDS = 15 * 60  # default render auto-refreshes if cache older than 15m


def _ensure_pipeline_fresh(entries: list[Entry]) -> dict:
    """Load the pipeline cache; if absent/stale, regenerate inline before render.

    Cheaper than a launchd cron (which would hit the iCloud TCC trap), and
    self-healing — the data Matt sees is at most 15 minutes old. Takes the
    pre-loaded entry list so we don't double-parse the publishing dir.
    """
    from pipeline import load_cache, check_pipeline, save_cache
    raw = load_cache(PUB_DIR)
    gen = raw.get("_generated_at") if isinstance(raw, dict) else None
    stale = True
    if gen:
        try:
            gen_dt = dt.datetime.fromisoformat(gen.replace("Z", "+00:00"))
            age = (dt.datetime.now(dt.timezone.utc) - gen_dt).total_seconds()
            stale = age > CACHE_STALE_SECONDS
        except ValueError:
            stale = True
    if not stale:
        return raw
    blogs = [e for e in entries if e.type == "blog"]
    states = {e.id: check_pipeline(e) for e in blogs}
    save_cache(PUB_DIR, states)
    # Auto-flip prod_deployed gate same as `zpub refresh` would.
    for e in blogs:
        st = states[e.id]
        on_main = st.stages[4].state == "passed"
        target = "passed" if on_main else "pending"
        if "prod_deployed" in required_gates(e.type) and e.gates.get("prod_deployed") != target:
            e.gates["prod_deployed"] = target
            e.updated_at = now_iso()
            save_entry(e)
    return load_cache(PUB_DIR)


def cmd_list(args: argparse.Namespace) -> None:
    from render import render_table  # local import — render.py is a sibling
    entries = all_entries()
    cache = _ensure_pipeline_fresh(entries) if not getattr(args, "skip_pipeline", False) else {}
    print(render_table(
        entries,
        all_view=args.all,
        reds_only=args.reds_only,
        max_visible=args.max,
        pipeline_cache=cache,
    ))


def cmd_show(args: argparse.Namespace) -> None:
    e = find_entry(args.id)
    if not e:
        print(f"no entry matching: {args.id}", file=sys.stderr)
        sys.exit(1)
    color, reasons = rag_state(e)
    color_emoji = {"red": "🔴", "amber": "🟠", "yellow": "🟡", "green": "🟢"}.get(color, "•")
    print(f"{color_emoji} {e.id}  {e.title}")
    print(f"   type:   {e.type}")
    print(f"   status: {e.status}")
    if e.publish_target:
        print(f"   target: {e.publish_target}")
    if e.publish_actual:
        print(f"   actual: {e.publish_actual}")
    print(f"   owner:  {e.owner}")
    if e.gates:
        print("   gates:")
        for k, v in e.gates.items():
            print(f"     - {k}: {v}")
    if e.blockers:
        print("   blockers:")
        for b in e.blockers:
            print(f"     - {b}")
    if e.surfaces:
        print("   surfaces:")
        for s in e.surfaces:
            kind = s.get("kind", "?")
            extra = s.get("path") or s.get("state") or s.get("url") or ""
            print(f"     - {kind}: {extra}")
    if e.links:
        print("   links:")
        for l in e.links:
            print(f"     - {l.get('label', '?')}: {l.get('url', '')}")
    if e.zergboard_card_id:
        cfg = json.loads(BOARD_CONFIG.read_text()) if BOARD_CONFIG.exists() else {}
        board_id = cfg.get("board_id", "")
        print(f"   zergboard: https://zergboard.fly.dev/?board={board_id}&card={e.zergboard_card_id}")
    print(f"   updated: {e.updated_at}")
    print(f"   reasons: {'; '.join(reasons) if reasons else '(none)'}")
    if e.body.strip():
        print()
        print(e.body.rstrip())


def cmd_add(args: argparse.Namespace) -> None:
    """Wizard. Either reads --title/--type/--target flags or prompts (TTY only)."""
    interactive = sys.stdin.isatty()

    def get(flag_val: Optional[str], prompt: str, default: str = "") -> str:
        if flag_val:
            return flag_val
        if interactive:
            return _prompt(prompt, default=default)
        return default

    title = get(args.title, "Title: ")
    if not title:
        print("title required (pass --title)", file=sys.stderr)
        sys.exit(1)
    type_ = get(args.type, f"Type ({'|'.join(VALID_TYPES)}): ", default="blog")
    if type_ not in VALID_TYPES:
        print(f"invalid type: {type_}", file=sys.stderr)
        sys.exit(1)
    target = get(args.target, "Publish target (YYYY-MM-DD or 'tbd'): ", default="tbd")
    if target.lower() in ("tbd", "none", "null", ""):
        target = None
    elif not _parse_iso_date(target):
        print(f"invalid date: {target} (pass --target YYYY-MM-DD or 'tbd')", file=sys.stderr)
        sys.exit(1)
    owner = get(args.owner, "Owner: ", default="matthew")
    status = args.status or "drafting"

    today = dt.date.today()
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50]
    eid = args.id or f"pub-{today.strftime('%Y-%m')}-{slug}"

    # Default gates: every required gate -> pending; everything else absent
    gates = {g: "pending" for g in required_gates(type_)}

    e = Entry(
        id=eid,
        title=title,
        type=type_,
        status=status,
        publish_target=target,
        owner=owner,
        gates=gates,
        updated_at=now_iso(),
        body="",
    )
    path = save_entry(e)
    print(f"created {e.id}")
    print(f"  → {path}")
    color, reasons = rag_state(e)
    color_emoji = {"red": "🔴", "amber": "🟠", "yellow": "🟡", "green": "🟢"}.get(color, "•")
    print(f"  → {color_emoji} {color.upper()} ({'; '.join(reasons) if reasons else 'on track'})")


def cmd_set(args: argparse.Namespace) -> None:
    e = find_entry(args.id)
    if not e:
        print(f"no entry matching: {args.id}", file=sys.stderr)
        sys.exit(1)

    key, value = args.field, args.value

    in_flight, reason = is_in_flight(e)
    guarded = key.startswith("gates.") or key in ("status", "blocker.add")
    if in_flight and guarded and not getattr(args, "override_in_flight", False):
        print(f"refused: {e.id} is IN FLIGHT ({reason}). "
              f"Mutating `{key}` would back-track progress already made.",
              file=sys.stderr)
        print(f"         Re-run with --override-in-flight if you really mean it "
              f"(requires explicit human YES per feedback_publish_status_explicit_yes).",
              file=sys.stderr)
        sys.exit(2)

    if key.startswith("gates."):
        gate = key.split(".", 1)[1]
        if value not in VALID_GATE_VALUES:
            print(f"invalid gate value: {value} (must be one of {VALID_GATE_VALUES})", file=sys.stderr)
            sys.exit(1)
        e.gates[gate] = value
    elif key == "blocker.add":
        e.blockers.append(value)
    elif key == "blocker.clear":
        e.blockers = []
    elif key == "status":
        if value not in VALID_STATUSES:
            print(f"invalid status: {value}", file=sys.stderr)
            sys.exit(1)
        if value == "scheduled" and not getattr(args, "force", False):
            missing = []
            if not e.date_confirmed:
                missing.append("date_confirmed is false — run `zpub set <id> date_confirmed true` ONLY after human says yes")
            required = required_gates(e.type)
            for g in required:
                gv = e.gates.get(g, "pending")
                if gv not in ("passed", "n_a"):
                    missing.append(f"gate `{g}` is {gv} (must be passed or n_a)")
            if missing:
                print(f"refused: cannot mark {e.id} `scheduled`:", file=sys.stderr)
                for m in missing:
                    print(f"  - {m}", file=sys.stderr)
                print(f"  Re-run with --force to override (requires explicit human YES "
                      f"per feedback_publish_status_explicit_yes + feedback_launch_dates_aspirational).",
                      file=sys.stderr)
                sys.exit(2)
        e.status = value
        if value in ("published", "distributed") and not e.publish_actual:
            e.publish_actual = dt.date.today().isoformat()
    elif key == "type":
        if value not in VALID_TYPES:
            print(f"invalid type: {value}", file=sys.stderr)
            sys.exit(1)
        e.type = value
    elif key == "title":
        e.title = value
    elif key == "publish_target":
        if not _parse_iso_date(value):
            print(f"invalid date: {value}", file=sys.stderr)
            sys.exit(1)
        e.publish_target = value
        # Phantom-date warning (Matt 2026-06-08): scheduling an undrafted entry
        # near-term is almost always a mistake. Warn (non-blocking) at set time.
        tgt = _parse_iso_date(value)
        gates_passed = sum(1 for v in e.gates.values() if v == "passed")
        if tgt and e.status in ("ideating", "drafting") and gates_passed == 0:
            days_out = (tgt - dt.datetime.now(PT).date()).days
            if days_out <= 3:
                print(f"⚠ phantom date: {e.id} is `{e.status}` with 0 gates passed but "
                      f"you set a target {days_out}d out. It's not drafted — this will "
                      f"render RED. Draft it first or pick a realistic date.", file=sys.stderr)
    elif key == "publish_actual":
        e.publish_actual = value
    elif key == "owner":
        e.owner = value
    elif key == "date_confirmed":
        if value.lower() not in ("true", "false"):
            print(f"invalid date_confirmed value: {value} (must be true or false)", file=sys.stderr)
            sys.exit(1)
        e.date_confirmed = value.lower() == "true"
    elif key == "approval.locked":
        # Human approval lock (per the gigacontext-2026-05-19 incident: the
        # canonical signoff record; validators must never flip it). This verb
        # replaces hand-editing the YAML block. Locking stamps locked_at;
        # set approval.locked_by first (or after) so check_gates honors it.
        if value.lower() not in ("true", "false"):
            print(f"invalid approval.locked value: {value} (must be true or false)", file=sys.stderr)
            sys.exit(1)
        approval = e.extra.setdefault("approval", {})
        if value.lower() == "true":
            approval["locked"] = True
            approval.setdefault("locked_at", now_iso())
        else:
            approval["locked"] = False
    elif key == "approval.locked_by":
        if value not in ("matt", "idan"):
            print(f"invalid approval.locked_by: {value} (must be matt or idan — "
                  f"signoff is a human gate)", file=sys.stderr)
            sys.exit(1)
        e.extra.setdefault("approval", {})["locked_by"] = value
    else:
        print(f"unknown field: {key}", file=sys.stderr)
        print(f"  supported: status, type, title, publish_target, publish_actual,")
        print(f"             date_confirmed, owner, gates.<name>, blocker.add, blocker.clear,")
        print(f"             approval.locked, approval.locked_by")
        sys.exit(1)

    e.updated_at = now_iso()

    # Gate-state consistency invariants — refuse any mutation that would
    # leave the entry internally contradictory (e.g. signoff=passed while
    # fakeidan=pending). Bypass via --force-inconsistent for migration only;
    # logged to CONFLICTS_PATH. See ~/.claude/plans/synchronous-yawning-storm.md A1.
    from pipeline import validate_gate_consistency
    violations = validate_gate_consistency(e)
    if violations and not getattr(args, "force_inconsistent", False):
        print(f"refused: gate-consistency violation on {e.id} after `{key} = {value}`:",
              file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        print(f"  Re-run with --force-inconsistent to override (logged; reserved for migration).",
              file=sys.stderr)
        sys.exit(2)
    if violations:
        try:
            CONFLICTS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with CONFLICTS_PATH.open("a") as fh:
                fh.write(f"{now_iso()}\t{e.id}\tforce-inconsistent\t{key}={value}\t"
                         f"{'; '.join(violations)}\n")
        except OSError:
            pass

    save_entry(e)
    print(f"updated {e.id}: {key} = {value}")


def cmd_open(args: argparse.Namespace) -> None:
    e = find_entry(args.id)
    if not e:
        print(f"no entry matching: {args.id}", file=sys.stderr)
        sys.exit(1)
    editor = os.environ.get("EDITOR", "open")
    subprocess.run([editor, str(e._path)])


def cmd_status(args: argparse.Namespace) -> None:
    """Live pipeline check for one entry."""
    from pipeline import check_pipeline, render_status  # local — sibling module
    e = find_entry(args.id)
    if not e:
        print(f"no entry matching: {args.id}", file=sys.stderr)
        sys.exit(1)
    if e.type != "blog":
        print(f"pipeline check is blog-only for now (entry type={e.type})", file=sys.stderr)
        sys.exit(2)
    state = check_pipeline(e)
    print(render_status(state, title=e.title))


def cmd_refresh(args: argparse.Namespace) -> None:
    """Refresh pipeline cache for every blog entry."""
    from pipeline import check_pipeline, save_cache, STAGE_LABELS  # local
    entries = [e for e in all_entries() if e.type == "blog"]
    states: dict[str, Any] = {}
    autoflipped: list[str] = []
    for e in entries:
        state = check_pipeline(e)
        states[e.id] = state
        # Auto-derive `prod_deployed` gate from stage 5 (on_main_branch).
        on_main = state.stages[4].state == "passed"
        target = "passed" if on_main else "pending"
        current = e.gates.get("prod_deployed")
        if "prod_deployed" in required_gates(e.type) and current != target:
            e.gates["prod_deployed"] = target
            e.updated_at = now_iso()
            save_entry(e)
            autoflipped.append(f"{e.id}: prod_deployed {current or '(unset)'} -> {target}")
    path = save_cache(PUB_DIR, states)
    summary = {"passed": 0, "partial": 0, "blocked": 0}
    for s in states.values():
        if s.highest_completed == len(STAGE_LABELS) - 1:
            summary["passed"] += 1
        elif s.highest_completed >= 2:
            summary["partial"] += 1
        else:
            summary["blocked"] += 1
    print(f"refreshed {len(states)} blog entries → {path.relative_to(VAULT_ROOT)}")
    print(f"  live on prod: {summary['passed']}  ·  partial: {summary['partial']}  ·  blocked at gates/draft: {summary['blocked']}")
    if autoflipped:
        print(f"  auto-flipped prod_deployed gate on {len(autoflipped)} entries:")
        for line in autoflipped:
            print(f"    - {line}")


def cmd_pipeline(args: argparse.Namespace) -> None:
    """Render the cached pipeline state for every blog entry as a table.

    Reads `_meta/pipeline.json`. If --live, refreshes first.
    """
    from pipeline import load_cache, STAGE_LABELS, check_pipeline, save_cache
    if getattr(args, "live", False):
        entries = [e for e in all_entries() if e.type == "blog"]
        states_obj = {e.id: check_pipeline(e) for e in entries}
        save_cache(PUB_DIR, states_obj)
        cache = {k: v.as_dict() for k, v in states_obj.items()}
        generated_at = "just now (live)"
    else:
        raw = load_cache(PUB_DIR)
        if not raw:
            print("no pipeline cache — run `zpub refresh` first (or `zpub pipeline --live`)", file=sys.stderr)
            sys.exit(2)
        cache = raw.get("entries", {})
        generated_at = raw.get("_generated_at", "unknown")

    # Build id -> title lookup from the entry files (cache only stores entry_id).
    titles = {e.id: e.title for e in all_entries()}

    rows = sorted(cache.items(), key=lambda kv: (-kv[1]["highest_completed"], kv[0]))

    stage_glyphs = {"passed": "●", "failed": "○", "n_a": "·", "unknown": "?"}
    print(f"BLOG PIPELINE  (as of {generated_at})")
    print(f"  stages: 1=draft 2=gates 3=on-dev 4=live-dev 5=on-main 6=live-prod\n")
    # Per `feedback_label_options_for_quick_pick.md` — number rows A/B/C... so Matt can
    # reply with one letter to drill in via `zpub status <id>`.
    LABELS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    print(f"     {'PIPE':<8} {'ID':<46} {'NEXT':<60}")
    print("     " + "─" * 116)
    label_map = []
    for i, (eid, st) in enumerate(rows):
        glyphs = "".join(stage_glyphs[s["state"]] for s in st["stages"])
        title = titles.get(eid, "")
        nb = (st.get("next_blocker") or "")[:60]
        label = LABELS[i] if i < len(LABELS) else " "
        print(f"  [{label}] {glyphs:<8} {eid:<46} {nb}")
        label_map.append((label, eid, title))
    print()
    print(f"  ● = passed   ○ = failed   · = n/a   ? = unknown")
    print(f"  drill in: `zpub status <id>`  (e.g. `zpub status {rows[0][0] if rows else '<id>'}`)")


def cmd_in_flight(args: argparse.Namespace) -> None:
    e = find_entry(args.id)
    if not e:
        print(f"no entry matching: {args.id}", file=sys.stderr)
        sys.exit(1)
    in_flight, reason = is_in_flight(e)
    if in_flight:
        print(f"IN FLIGHT — DO NOT TOUCH  ({reason})")
        if e.publish_target:
            print(f"  auto-publish target: {e.publish_target}")
        print(f"  status: {e.status}")
        sys.exit(0)
    else:
        print(f"not in flight (status={e.status})")
        sys.exit(1)


def cmd_sync(args: argparse.Namespace) -> None:
    from sync import run_sync
    run_sync(direction=args.direction, dry_run=args.dry_run)


def cmd_bootstrap_board(args: argparse.Namespace) -> None:
    from sync import bootstrap_board
    bootstrap_board(force=args.force)


def cmd_index(_args: argparse.Namespace) -> None:
    rebuild_index()
    entries = all_entries()
    counts = {"red": 0, "amber": 0, "green": 0}
    for e in entries:
        color, _ = rag_state(e)
        counts[color] += 1
    print(f"reindexed {len(entries)} entries → {INDEX_PATH}")
    print(f"  RED: {counts['red']}  AMBER: {counts['amber']}  GREEN: {counts['green']}")


def _prompt(msg: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"{msg}{suffix}").strip()
    return val or default


# ---------- Argparse ----------

def main() -> None:
    p = argparse.ArgumentParser(prog="zpub", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--all", action="store_true", help="Show greens too")
    p.add_argument("--reds-only", action="store_true",
                   help="Compact reds-only view (used by morning-brief)")
    p.add_argument("--max", type=int, default=5, help="Max visible rows (default 5)")
    p.add_argument("--version", action="version", version="zpub 0.1.0")

    sub = p.add_subparsers(dest="cmd")

    sa = sub.add_parser("all", help="Full table including greens")
    sa.set_defaults(func=lambda a: cmd_list(argparse.Namespace(all=True, reds_only=False, max=999)))

    show = sub.add_parser("show", help="Entry detail")
    show.add_argument("id")
    show.set_defaults(func=cmd_show)

    add = sub.add_parser("add", help="Create new entry (wizard)")
    add.add_argument("--title")
    add.add_argument("--type", choices=VALID_TYPES)
    add.add_argument("--target", help="publish_target YYYY-MM-DD")
    add.add_argument("--owner")
    add.add_argument("--status", choices=VALID_STATUSES)
    add.add_argument("--id", help="Override auto-generated id")
    add.set_defaults(func=cmd_add)

    setp = sub.add_parser("set", help="Update an entry field")
    setp.add_argument("id")
    setp.add_argument("field", help="status | type | title | publish_target | publish_actual | date_confirmed | owner | gates.<name> | blocker.add | blocker.clear | approval.locked | approval.locked_by")
    setp.add_argument("value")
    setp.add_argument("--override-in-flight", action="store_true",
                       help="Force mutation on an in-flight entry. Requires explicit human YES.")
    setp.add_argument("--force", action="store_true",
                       help="Bypass schedule guard (date_confirmed + all-gates-passed). Requires explicit human YES.")
    setp.add_argument("--force-inconsistent", action="store_true",
                       help="Bypass gate-consistency invariants (e.g. signoff while fakeidan=pending). "
                            "Logged to _meta/conflicts.log. Reserved for migration; requires explicit human YES.")
    setp.set_defaults(func=cmd_set)

    op = sub.add_parser("open", help="Open vault entry in $EDITOR")
    op.add_argument("id")
    op.set_defaults(func=cmd_open)

    st = sub.add_parser("status", help="Live pipeline check for one blog entry")
    st.add_argument("id")
    st.set_defaults(func=cmd_status)

    rf = sub.add_parser("refresh", help="Refresh pipeline cache for all blog entries")
    rf.set_defaults(func=cmd_refresh)

    pl = sub.add_parser("pipeline", help="Pipeline state table for every blog entry (uses cache; --live to refresh)")
    pl.add_argument("--live", action="store_true", help="Refresh cache first")
    pl.set_defaults(func=cmd_pipeline)

    inf = sub.add_parser("in-flight", help="Check if entry is in flight (terminal/untouchable)")
    inf.add_argument("id")
    inf.set_defaults(func=cmd_in_flight)

    sy = sub.add_parser("sync", help="Bidirectional sync with Zergboard")
    sy.add_argument("direction", nargs="?", choices=["push", "pull", "both"], default="both")
    sy.add_argument("--dry-run", action="store_true")
    sy.set_defaults(func=cmd_sync)

    bs = sub.add_parser("bootstrap-board", help="One-time create Publishing board")
    bs.add_argument("--force", action="store_true",
                    help="Overwrite existing board.json (does NOT delete the live board)")
    bs.set_defaults(func=cmd_bootstrap_board)

    idx = sub.add_parser("index", help="Rebuild _meta/index.json")
    idx.set_defaults(func=cmd_index)

    args, extra = p.parse_known_args()

    # Default: list view. If first positional looks like an entry id, show.
    if not args.cmd:
        if extra and extra[0].startswith("pub-"):
            args = argparse.Namespace(id=extra[0])
            cmd_show(args)
            return
        cmd_list(args)
        return

    args.func(args)


if __name__ == "__main__":
    main()
