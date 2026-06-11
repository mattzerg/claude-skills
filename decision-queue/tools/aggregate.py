#!/usr/bin/env python3
"""aggregate.py — single canonical view of every decision pending Matt's input.

Reads from:
  - gtm-hub `_meta/decisions.json` (kind=decision items)
  - zpub entries with autonomy resolution = needs_matt
  - Tasks/inbox.md rows tagged [blocked:matt-review]
  - pr-table state (held branches + review-requested PRs)

Writes:
  - MattZerg/Tasks/decisions_pending.md   (human-readable canonical)
  - ~/.claude/state/decisions_pending.jsonl (machine-readable for serve.py)

Each output item:
  {id, source, entity_path, age_days, age_human, class, suggested_default,
   verdict_source, why, context_one_line, choices: [...], deadline?: iso}
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
LIB_DIR = SCRIPT_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from autonomy import (  # noqa: E402
    resolve,
    parse_frontmatter,
    classify_zpub_entry,
    classify_gtm_entity,
    classify_inbox_row,
)

# launchd-safe vault I/O: reads resolve through the mirror, writes are staged
# for the vault-flush LaunchAgent. Direct iCloud writes fail under TCC.
sys.path.insert(0, str(Path.home() / ".config" / "zerg"))
from vault_path import vault_path, vault_write  # noqa: E402

VAULT = Path(os.path.expanduser(
    "~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Zerg"
))
VAULT_MIRROR = Path(os.path.expanduser("~/.zerg-vault-mirror"))
GROWTH = vault_path("Projects/Zerg-Production/Growth")
TASKS_DIR = vault_path("Tasks")
# Vault-relative output path for the staged write.
DECISIONS_MD_REL = "Tasks/decisions_pending.md"
STATE_DIR = Path(os.path.expanduser("~/.claude/state"))
DECISIONS_JSONL = STATE_DIR / "decisions_pending.jsonl"
DECISIONS_LOG = STATE_DIR / "decisions_log.jsonl"


@dataclass
class DecisionItem:
    id: str
    source: str          # "gtm-hub" | "zpub" | "inbox" | "pr-table"
    entity_path: str
    entity_id: str
    age_days: float
    age_human: str
    autonomy_class: Optional[str]
    autonomy_verdict: str   # auto | needs_matt | blocked_external
    verdict_source: str
    why: str
    context_one_line: str
    choices: list[str] = field(default_factory=lambda: ["yes", "no", "defer-1d", "details"])
    suggested_default: str = "details"
    deadline: Optional[str] = None
    priority: int = 50
    raw: dict = field(default_factory=dict)


# ---------- helpers ----------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _age_days(ts: datetime) -> float:
    return (_now() - ts).total_seconds() / 86400.0


def _age_human(d: float) -> str:
    if d < 1:
        h = int(d * 24)
        return f"{h}h"
    if d < 14:
        return f"{int(d)}d"
    return f"{int(d/7)}w"


def _parse_dt(s) -> Optional[datetime]:
    if s is None or s == "":
        return None
    # YAML may parse YYYY-MM-DD as datetime.date or datetime.datetime
    if hasattr(s, "isoformat") and not isinstance(s, str):
        try:
            return s if isinstance(s, datetime) else datetime(s.year, s.month, s.day, tzinfo=timezone.utc)
        except Exception:
            return None
    s = str(s).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except Exception:
        try:
            return datetime.fromisoformat(s + "T00:00:00+00:00")
        except Exception:
            return None


def _truncate(s: str, n: int = 140) -> str:
    s = s.strip().replace("\n", " ")
    s = re.sub(r"\s+", " ", s)
    return s if len(s) <= n else s[:n - 1] + "…"


def _entity_mtime(path: Path) -> datetime:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except FileNotFoundError:
        return _now()


# ---------- gtm-hub decisions ----------

def from_gtm_hub() -> Iterable[DecisionItem]:
    """gtm-hub already runs the decision engine; consume its output."""
    paths = [
        VAULT / "MattZerg/Projects/Zerg-Production/Growth/_meta/decisions.json",
        VAULT_MIRROR / "MattZerg/Projects/Zerg-Production/Growth/_meta/decisions.json",
    ]
    src = next((p for p in paths if p.exists()), None)
    if not src:
        return
    try:
        data = json.loads(src.read_text())
    except Exception as e:
        print(f"[aggregate] failed to read gtm-hub decisions: {e}", file=sys.stderr)
        return
    for d in data.get("decisions", []):
        if d.get("kind") != "decision":
            continue
        ent_path = d.get("entity_path") or ""
        entity_class = None
        autonomy_fm = None
        if ent_path and Path(ent_path).exists():
            try:
                text = Path(ent_path).read_text()
                fm = parse_frontmatter(text)
                autonomy_fm = fm.get("autonomy")
                folder_rel = str(Path(ent_path).parent.relative_to(GROWTH)) if str(GROWTH) in ent_path else "content"
                entity_class = classify_gtm_entity(folder_rel, fm)
            except Exception:
                pass
        verdict = resolve(entity_autonomy=autonomy_fm, entity_class=entity_class)
        if verdict.verdict != "needs_matt":
            continue
        mtime = _entity_mtime(Path(ent_path)) if ent_path else _now()
        age = _age_days(mtime)
        yield DecisionItem(
            id=f"gtm:{d.get('rule', 'unknown')}:{d.get('entity_id', 'noid')}",
            source="gtm-hub",
            entity_path=ent_path,
            entity_id=d.get("entity_id", ""),
            age_days=age,
            age_human=_age_human(age),
            autonomy_class=entity_class,
            autonomy_verdict=verdict.verdict,
            verdict_source=verdict.source,
            why=verdict.why,
            context_one_line=_truncate(d.get("message", "")),
            choices=["yes ship", "no skip", "defer-3d", "details"],
            suggested_default="details",
            priority=int(d.get("priority", 50)),
            raw=d,
        )


# ---------- zpub ----------

PUB_DIR = GROWTH / "publishing"


def from_zpub() -> Iterable[DecisionItem]:
    if not PUB_DIR.exists():
        return
    for path in sorted(PUB_DIR.glob("pub-*.md")):
        try:
            text = path.read_text()
        except Exception:
            continue
        fm = parse_frontmatter(text)
        if not fm:
            continue
        status = (fm.get("status") or "").lower()
        # We're interested in entries that are mid-pipeline, not published or done
        if status in ("published", "killed", "archived"):
            continue
        autonomy_fm = fm.get("autonomy")
        cls = classify_zpub_entry(fm)
        verdict = resolve(entity_autonomy=autonomy_fm, entity_class=cls)
        if verdict.verdict != "needs_matt":
            continue
        # Only surface zpub items that are actually awaiting a Matt-decision step:
        # gates.signoff = pending, or status = review with gates pending, or blockers exist
        gates = fm.get("gates") or {}
        signoff = str(gates.get("signoff", "")).lower() if isinstance(gates, dict) else ""
        pr_gate = str(gates.get("pr_gate", "")).lower() if isinstance(gates, dict) else ""
        blockers = fm.get("blockers") or []
        actionable = (
            signoff in ("pending", "needed")
            or pr_gate in ("pending", "blocked")
            or (status == "review" and (signoff != "passed"))
            or (status == "drafting" and len(blockers) > 0)
        )
        if not actionable:
            continue
        target_raw = fm.get("publish_target")
        target_dt = _parse_dt(target_raw)
        target = target_dt.date().isoformat() if target_dt else ""
        # build the context line
        title = fm.get("title") or fm.get("id") or path.stem
        ctx_bits = [f"{title}"]
        if target:
            ctx_bits.append(f"target={target}")
        if signoff:
            ctx_bits.append(f"signoff={signoff}")
        if pr_gate:
            ctx_bits.append(f"pr_gate={pr_gate}")
        if blockers:
            ctx_bits.append(f"blockers={len(blockers)}")
        context_line = _truncate(" • ".join(ctx_bits))
        mtime = _entity_mtime(path)
        age = _age_days(mtime)
        # priority: closer target = higher
        priority = 50
        if target_dt:
            days_to_target = (target_dt - _now()).total_seconds() / 86400.0
            if days_to_target < 0:
                priority = 95
            elif days_to_target < 3:
                priority = 85
            elif days_to_target < 7:
                priority = 70
        yield DecisionItem(
            id=f"zpub:{fm.get('id', path.stem)}",
            source="zpub",
            entity_path=str(path),
            entity_id=fm.get("id", path.stem),
            age_days=age,
            age_human=_age_human(age),
            autonomy_class=cls,
            autonomy_verdict=verdict.verdict,
            verdict_source=verdict.source,
            why=verdict.why,
            context_one_line=context_line,
            choices=["yes signoff", "no revise", "defer-3d", "details"],
            suggested_default="details",
            deadline=target or None,
            priority=priority,
            raw={"status": status, "type": fm.get("type"), "blockers": blockers},
        )


# ---------- inbox.md ----------

INBOX = vault_path("Tasks/inbox.md")
INBOX_ROW = re.compile(r"^\s*[-*]\s+(?!\*)(.+)$")


def from_inbox() -> Iterable[DecisionItem]:
    if not INBOX.exists():
        return
    text = INBOX.read_text()
    mtime = _entity_mtime(INBOX)
    age = _age_days(mtime)
    for i, raw_line in enumerate(text.splitlines()):
        m = INBOX_ROW.match(raw_line)
        if not m:
            continue
        line = m.group(1)
        low = line.lower()
        # Only matt-review tagged items go to decision queue;
        # blocked:idan / waiting:* go to "waiting" surface elsewhere
        if "[blocked:matt-review]" not in low:
            continue
        cls = classify_inbox_row(line) or "vault_organization"
        # Force needs_matt for these tagged items
        verdict = resolve(entity_autonomy="needs_matt", entity_class=cls)
        ctx = _truncate(re.sub(r"\[(blocked|waiting):[^\]]+\]", "", line))
        yield DecisionItem(
            id=f"inbox:L{i+1}",
            source="inbox",
            entity_path=str(INBOX),
            entity_id=f"L{i+1}",
            age_days=age,
            age_human=_age_human(age),
            autonomy_class=cls,
            autonomy_verdict=verdict.verdict,
            verdict_source="entity",
            why="Matt-review tag",
            context_one_line=ctx,
            choices=["yes done", "no skip", "defer-1d", "details"],
            suggested_default="details",
            priority=60,
            raw={"row": raw_line, "lineno": i + 1},
        )


# ---------- personal data OS nudges ----------

PERSONAL_NUDGES = STATE_DIR / "personal_nudges_pending.jsonl"


def _decided_ids() -> set[str]:
    """Ids already acted on (from decisions_log.jsonl) so acted nudges drop off."""
    out: set[str] = set()
    if not DECISIONS_LOG.exists():
        return out
    try:
        for line in DECISIONS_LOG.open():
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("id"):
                out.add(rec["id"])
    except Exception:
        pass
    return out


def from_personal_os() -> Iterable[DecisionItem]:
    """Nudges 'act'-ed from the Personal Data OS dashboard (:8789).

    The dashboard appends `{id, context, domain, created, deadline?, priority?}`
    to personal_nudges_pending.jsonl; this folds them into the same queue the
    :8788 swipe UI + morning-brief decision row read — one shared queue, the
    push+pull unification. Acted/dismissed ids (in decisions_log.jsonl) drop off.
    """
    if not PERSONAL_NUDGES.exists():
        return
    decided = _decided_ids()
    for line in PERSONAL_NUDGES.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        nid = d.get("id")
        if not nid or nid in decided:
            continue
        created = _parse_dt(d.get("created")) or _now()
        age = _age_days(created)
        yield DecisionItem(
            id=nid,
            source="personal-os",
            entity_path="http://127.0.0.1:8789/",
            entity_id=d.get("domain", "personal"),
            age_days=age,
            age_human=_age_human(age),
            autonomy_class="personal_nudge",
            autonomy_verdict="needs_matt",
            verdict_source="personal-os",
            why="Acted from the Personal Data OS dashboard",
            context_one_line=_truncate(d.get("context", "")),
            choices=["yes do it", "no skip", "defer-3d", "details"],
            suggested_default="details",
            deadline=d.get("deadline"),
            priority=int(d.get("priority", 45)),
            raw=d,
        )


# ---------- zhub stale-backlog sweep ----------

ZHUB_SWEEP_PENDING = STATE_DIR / "zhub_sweep_pending.jsonl"


def from_zhub_sweep():
    """Stale-task verdicts staged by `zhub sweep` — keep/park/drop per task.

    zhub stages each stale task (no human touch in 14+ days) with a Haiku
    suggestion; swiped answers are applied back to the spine by the hourly
    `zhub sweep --apply` (drop → state=dropped, park-30d → snooze, keep →
    never re-staged). Decided ids (decisions_log.jsonl) drop off here.
    """
    if not ZHUB_SWEEP_PENDING.exists():
        return
    decided = _decided_ids()
    for line in ZHUB_SWEEP_PENDING.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        sid = d.get("id")
        if not sid or sid in decided:
            continue
        created = _parse_dt(d.get("created")) or _now()
        age = _age_days(created)
        task_age = d.get("age_days")
        suggested = d.get("suggested", "keep")
        yield DecisionItem(
            id=sid,
            source="zhub-sweep",
            entity_path="http://127.0.0.1:7777/feed?lens=stale",
            entity_id=d.get("entity_id", ""),
            age_days=age,
            age_human=_age_human(age),
            autonomy_class="task_hygiene",
            autonomy_verdict="needs_matt",
            verdict_source="zhub-sweep",
            why=f"suggests {suggested}: " + _truncate(d.get("why", ""), 120),
            context_one_line=_truncate(
                f"[{task_age:.0f}d stale] {d.get('title', '')}" if task_age is not None else d.get("title", "")
            ),
            choices=["drop", "park-30d", "keep"],
            suggested_default=suggested if suggested in ("drop", "keep") else "park-30d",
            priority=40,
            raw=d,
        )


# ---------- pre-PR context packs (P1.5) ----------

PRE_PR_PACKS = STATE_DIR / "pre_pr_packs.jsonl"


def from_pre_pr_packs() -> Iterable[DecisionItem]:
    """Read pre_pr_packs.jsonl emitted by pre_pr_pack.py."""
    if not PRE_PR_PACKS.exists():
        return
    seen = set()
    rows = []
    # Read whole file; keep only last entry per branch (id)
    with PRE_PR_PACKS.open() as fh:
        for line in fh:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    # Most recent wins
    for r in reversed(rows):
        if r.get("kind") != "pre_pr_pack":
            continue
        rid = r.get("id")
        if rid in seen:
            continue
        seen.add(rid)
        # Skip rows older than 7d
        try:
            ts = datetime.fromisoformat(r.get("ts").replace("Z", "+00:00"))
            age = _age_days(ts)
            if age > 7:
                continue
        except Exception:
            continue
        yield DecisionItem(
            id=rid,
            source="pre-pr",
            entity_path=r.get("pack_path", ""),
            entity_id=r.get("branch", ""),
            age_days=age,
            age_human=_age_human(age),
            autonomy_class="pr_creation",
            autonomy_verdict="needs_matt",
            verdict_source="class:pr_creation",
            why="PR creation is the Idan-facing surface; Matt confirms intent before push.",
            context_one_line=_truncate(r.get("context_one_line", "")),
            choices=["yes ship", "no refine", "hold", "details"],
            suggested_default="details" if r.get("micro_status") != "✅" else "yes ship",
            priority=80,
            raw=r,
        )


# ---------- composite proposals (mining→queue, Q0.1) ----------

COMPOSITE_PROPOSALS = STATE_DIR / "composite_proposals.jsonl"

# S2.1 — defense-in-depth noise filter at the queue layer. Even though
# mining_to_composite.py now gates n-gram quality at generation time, older
# rows (and downstream `draft:*` rows derived from them) already sit in
# composite_proposals.jsonl. Reject common-English / PR-review-chrome phrase
# proposals here so they never reach the decision queue. A phrase survives if
# it carries a domain term OR clears a high generic-instance bar.
_PHRASE_STOPLIST = {
    "rather than", "feel free", "before merge", "make sure", "quick surface",
    "especially good", "quick prior-review", "quick review", "prior review",
    "review surface", "looks good", "good catch", "nice work", "well done",
    "makes sense", "take care", "let know", "happy help", "small nit",
    "minor nit", "post-merge tracker", "post merge", "sounds good",
    "great work", "left comment", "left comments", "couple things",
    "few things", "one thing", "high level", "low level", "good point",
}
_COMMON_ENGLISH = {
    "rather", "than", "feel", "free", "before", "after", "make", "made",
    "makes", "making", "sure", "quick", "quickly", "surface", "surfaces",
    "especially", "good", "better", "best", "great", "nice", "well",
    "really", "very", "much", "more", "most", "less", "least", "prior",
    "review", "reviews", "reviewed", "reviewing", "looks", "look", "looking",
    "sense", "sounds", "sound", "point", "points", "thing", "things",
    "catch", "work", "works", "working", "done", "happy", "help", "care",
    "small", "minor", "major", "couple", "few", "high", "level", "left",
    "right", "comment", "comments", "merge", "merged", "merging", "tracker",
}
_DOMAIN_TERM_ROOTS = (
    "zerg", "zstack", "zergalytics", "zergscholar", "zergboard", "zergguard",
    "zergaudience", "epoch-ml", "academy",
    "zapps", "zmail", "zpub", "zboard", "zergvert", "zergchat", "zergdesk",
    "zergbox", "zergmeeting", "zergwallet", "zergschool", "zerguniversity",
    "zergai", "zerglytics", "zergsend",
)
_DOMAIN_TERMS = {
    "composite", "autonomy", "mining", "decision", "decisions", "queue",
    "gtm-hub", "zpub", "pr-gate", "ship-gate", "qa-gate", "send-gate",
    "skill", "skills", "hook", "hooks", "cron", "launchd", "launchctl",
    "vault", "frontmatter", "dataview", "corpus", "proposal", "proposals",
    "adversarial", "sweep", "calibration", "telemetry", "fakematt",
    "fakeidan", "diff", "lede", "scorecard", "signoff", "rebase",
    "worktree", "schema", "pipeline", "aggregate", "regen", "audit",
}
_GENERIC_PHRASE_MIN_INSTANCES = 25
# Skill-audit summaries and draft rows backed by a real audit report are
# legitimate even though their "theme" reads like prose; never noise-filter
# these id namespaces.
_NOISE_EXEMPT_ID_PREFIXES = ("skill_audit:", "draft:skill-")


def _is_product_tok(t: str) -> bool:
    return any(root in t for root in _DOMAIN_TERM_ROOTS)


def _is_technical_tok(t: str) -> bool:
    return t in _DOMAIN_TERMS


def _theme_is_domain(theme: str) -> bool:
    """A theme carries real domain signal if it has ≥1 technical noun. A theme
    that is ONLY product/org names (no technical noun) is brand co-occurrence,
    not an actionable theme — not treated as domain here."""
    toks = [t.lower() for t in re.split(r"[\s/]+", theme) if t]
    return any(_is_technical_tok(t) for t in toks)


def _proposal_is_noise(rid: str, theme: str, size: int) -> bool:
    """True if this composite proposal is a common-English / chrome phrase, or a
    bare product-name co-occurrence, with no actionable domain signal that fails
    to clear the generic-instance bar."""
    if any(rid.startswith(p) for p in _NOISE_EXEMPT_ID_PREFIXES):
        return False
    # Normalize a "Review draft: rather than" theme down to its phrase.
    phrase = re.sub(r"^review draft:\s*", "", (theme or "").strip(), flags=re.I)
    phrase = phrase.strip().lower()
    if _theme_is_domain(phrase):
        return False
    toks = [t for t in re.split(r"[\s/]+", phrase) if t]
    # Bare product/org co-occurrence (e.g. "epoch-ml zerg") with no technical
    # noun → not an actionable theme; require the high generic bar.
    if toks and all(_is_product_tok(t) for t in toks):
        return size < _GENERIC_PHRASE_MIN_INSTANCES
    all_common = bool(toks) and all(t in _COMMON_ENGLISH for t in toks)
    if phrase in _PHRASE_STOPLIST or all_common:
        return size < _GENERIC_PHRASE_MIN_INSTANCES
    # Two-word generic phrase with no domain anchor → still require high bar.
    if len(toks) <= 2:
        return size < _GENERIC_PHRASE_MIN_INSTANCES
    return False


def from_composite_proposals() -> Iterable[DecisionItem]:
    """Read composite_proposals.jsonl emitted by mining_to_composite.py.

    Two kinds:
      kind=composite_proposal — propose a new feedback/composite rule
      kind=autonomy_upgrade   — propose flipping an autonomy class default
    """
    if not COMPOSITE_PROPOSALS.exists():
        return
    seen = set()
    rows = []
    with COMPOSITE_PROPOSALS.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    # Most recent label wins for each id (idempotent across weekly re-runs)
    for r in reversed(rows):
        rid = r.get("id")
        if not rid or rid in seen:
            continue
        seen.add(rid)
        try:
            ts = datetime.fromisoformat(r.get("ts", "").replace("Z", "+00:00"))
            age = _age_days(ts)
            if age > 21:  # mining proposals older than 3 weeks are stale
                continue
        except Exception:
            continue
        kind = r.get("kind", "")
        if kind == "composite_proposal":
            theme = r.get("theme", "?")
            size = r.get("size", 0)
            # S2.1 — drop common-English / PR-review-chrome noise proposals that
            # have no domain signal and don't clear the high generic bar.
            try:
                if _proposal_is_noise(rid, theme, int(size or 0)):
                    continue
            except Exception:
                pass
            hint = r.get("composite_hint") or "(new composite — name it)"
            ctx = _truncate(f"Composite proposal: `{theme}` ({size} instances) → {hint}")
            choices = ["yes draft", "no skip", "defer-7d", "details"]
            priority = 55 + min(30, size)  # bigger cluster = higher priority
        elif kind == "autonomy_upgrade":
            cls = r.get("class", "?")
            answer = r.get("top_answer", "?")
            n = r.get("n", 0)
            ratio = r.get("ratio", 0.0)
            ctx = _truncate(
                f"Autonomy upgrade: `{cls}` → top answer `{answer}` "
                f"({n} rows, {int(ratio*100)}% same)"
            )
            choices = ["yes flip", "no keep", "defer-7d", "details"]
            priority = 75
        else:
            continue
        yield DecisionItem(
            id=rid,
            source="mining",
            entity_path=str(COMPOSITE_PROPOSALS),
            entity_id=rid,
            age_days=age,
            age_human=_age_human(age),
            autonomy_class="learning_loop",
            autonomy_verdict="needs_matt",
            verdict_source="class:learning_loop",
            why="Mining-pipeline proposal — Matt confirms before composite write or autonomy flip.",
            context_one_line=ctx,
            choices=choices,
            suggested_default="details",
            priority=priority,
            raw=r,
        )


# ---------- monthly self-improvement cadence (Phase C) ----------

SELF_IMPROVEMENT_MARKER = STATE_DIR / "self_improvement_last_run.txt"
SELF_IMPROVEMENT_INTERVAL_DAYS = 30


def from_self_improvement_cadence():
    """Emit ONE 'run /self-improvement' card when the monthly OS-audit is due
    (no marker, or last run > 30d). Stable id → idempotent across regens; the card
    self-clears once a run stamps the marker fresh (the autonomous job writes it,
    or Matt stamps it). The no-cost half of Phase C."""
    last = None
    try:
        if SELF_IMPROVEMENT_MARKER.exists():
            last = datetime.fromisoformat(
                SELF_IMPROVEMENT_MARKER.read_text().strip().replace("Z", "+00:00"))
    except Exception:
        last = None
    age = _age_days(last) if last is not None else 999.0
    if last is not None and age < SELF_IMPROVEMENT_INTERVAL_DAYS:
        return  # not due yet
    when = "never run" if last is None else f"{int(age)}d ago"
    yield DecisionItem(
        id="self-improvement-cadence",
        source="cadence",
        entity_path=str(SELF_IMPROVEMENT_MARKER),
        entity_id="self-improvement-monthly",
        age_days=(age if age < 900 else 0.0),
        age_human=("—" if last is None else _age_human(age)),
        autonomy_class="learning_loop",
        autonomy_verdict="needs_matt",
        verdict_source="class:learning_loop",
        why="Monthly OS self-improvement audit (5-agent fan-out → severity-ranked "
            "repair report) keeps the agent OS healthy. Run /self-improvement, or let "
            "the autonomous monthly job handle it.",
        context_one_line=f"OS self-improvement audit due (last: {when}) — run /self-improvement",
        choices=["run now", "defer-7d", "details"],
        suggested_default="run now",
        priority=60,
        raw={"kind": "self_improvement_cadence", "last_run": (last.isoformat() if last else None)},
    )


# ---------- pr-table (held branches awaiting Matt approval to push) ----------

# Defer for v1: pr-stage owns this and is read-only via its own commands.
# Surfaced via gtm-hub / morning-brief already.


# ---------- main ----------

# S1.3 — canonical-slug normalizer. zpub:pub-2026-X and gtm-hub:pub-2026-X (or
# anything that contains the same slug) are the same publishing artifact.
# Source priority: zpub (most specific) > inbox > pre-pr > gtm-hub > mining.
_SOURCE_RANK = {"zpub": 0, "inbox": 1, "pre-pr": 2, "gtm-hub": 3, "mining": 4}
_SLUG_RE = re.compile(r"([a-z0-9]+(?:-[a-z0-9]+){2,8})")


def _canonical_slug(it: DecisionItem) -> str | None:
    """Extract the publishing slug from id/entity_id/path. Returns None if
    the item is not slug-shaped (e.g. mining proposals)."""
    for cand in (it.entity_id, it.id, Path(it.entity_path).stem if it.entity_path else ""):
        cand = (cand or "").lower()
        # strip known prefixes
        for pfx in ("zpub:", "gtm:", "inbox:", "prep:", "mining:", "draft:", "skill_audit:",
                    "mtca:", "mtcb:"):
            if cand.startswith(pfx):
                cand = cand[len(pfx):]
        m = _SLUG_RE.search(cand)
        if m:
            return m.group(1)
    return None


def gather() -> list[DecisionItem]:
    items: list[DecisionItem] = []
    for src in (from_gtm_hub, from_zpub, from_inbox, from_pre_pr_packs, from_composite_proposals,
                from_self_improvement_cadence, from_personal_os, from_zhub_sweep):
        try:
            items.extend(src())
        except Exception as e:
            print(f"[aggregate] source {src.__name__} failed: {e}", file=sys.stderr)
    # De-dupe by id (exact match within source)
    seen_ids = set()
    items = [it for it in items if not (it.id in seen_ids or seen_ids.add(it.id))]

    # S1.3 — canonical-slug dedupe across sources. Group by slug; keep the
    # source-ranked-best item. Items with no slug (mining proposals) pass through.
    by_slug: dict[str, DecisionItem] = {}
    pass_through: list[DecisionItem] = []
    for it in items:
        slug = _canonical_slug(it)
        if not slug:
            pass_through.append(it)
            continue
        existing = by_slug.get(slug)
        if not existing:
            by_slug[slug] = it
            continue
        # Pick the better-ranked source; tie-break on priority
        rank_new = _SOURCE_RANK.get(it.source, 9)
        rank_old = _SOURCE_RANK.get(existing.source, 9)
        if (rank_new, -it.priority) < (rank_old, -existing.priority):
            by_slug[slug] = it
    deduped = list(by_slug.values()) + pass_through
    deduped.sort(key=lambda x: (-x.priority, -x.age_days))
    return deduped


# ---------- render ----------

def render_md(items: list[DecisionItem]) -> str:
    out = []
    now = _now().strftime("%Y-%m-%d %H:%M UTC")
    out.append("# Decisions pending — Matt input required\n")
    out.append(f"*Auto-regenerated: {now}* — `aggregate.py` reads gtm-hub, zpub, inbox.\n")
    out.append(f"**{len(items)} pending**\n")
    out.append("")
    out.append("Reply via Slack DM card, swipe app at `localhost:8788/swipe`, or SMS numbered queue.\n")
    out.append("")
    if not items:
        out.append("_No decisions pending. Autonomous lanes proceeding._\n")
        return "\n".join(out)
    out.append("| # | Source | Age | Class | One-liner | Default | Deadline |")
    out.append("|---|---|---|---|---|---|---|")
    for i, it in enumerate(items, start=1):
        cls = it.autonomy_class or "—"
        dl = it.deadline or "—"
        out.append(
            f"| {i} | `{it.source}` | {it.age_human} | `{cls}` | {it.context_one_line} | "
            f"`{it.suggested_default}` | {dl} |"
        )
    out.append("")
    out.append("---\n")
    out.append("## Per-item briefings\n")
    for i, it in enumerate(items, start=1):
        out.append(f"### {i}. `{it.id}`  — {it.context_one_line}\n")
        out.append(f"- **Source:** `{it.source}`  •  **Class:** `{it.autonomy_class}`  •  **Verdict:** `{it.autonomy_verdict}` (`{it.verdict_source}`)")
        out.append(f"- **Why this needs Matt:** {it.why}")
        out.append(f"- **Entity:** `{it.entity_path}`")
        if it.deadline:
            out.append(f"- **Deadline:** {it.deadline}")
        out.append(f"- **Choices:** {' / '.join(it.choices)} (default: `{it.suggested_default}`)")
        out.append("")
    return "\n".join(out)


def _strip_regen_stamp(text: str) -> str:
    return "\n".join(
        ln for ln in text.splitlines() if not ln.startswith("*Auto-regenerated:")
    )


def _vault_md_unchanged(rel: str, new_content: str) -> bool:
    """True when the vault copy already matches `new_content`, ignoring the
    Auto-regenerated timestamp line.

    Skipping the no-op rewrite matters: vault_flush must copy2 in place onto
    the iCloud file (TCC blocks tmp+rename there), and overwriting it every
    15-min regen cycle while iCloud syncs is what spawned the
    "decisions_pending 2.md" … "15.md" conflict copies (2026-06-10 audit).
    """
    from vault_path import WRITEBACK_ROOT
    # A staged-but-unflushed copy is the freshest committed intent — compare
    # against it first so back-to-back runs don't re-stage identical content.
    for candidate in (WRITEBACK_ROOT / rel, vault_path(rel)):
        try:
            current = candidate.read_text(encoding="utf-8")
        except OSError:
            continue
        return _strip_regen_stamp(current) == _strip_regen_stamp(new_content)
    return False


# External intake rows are seeded into the jsonl by their own tools
# (zpub/tools/gate_age_scan.py, portfolio_verdicts.py). A wholesale rewrite
# must carry them forward until they're answered (id appears in decisions_log).
EXTERNAL_INTAKE_PREFIXES = ("gateage:", "verdict:", "hygiene:")


def _preserved_external_rows(gathered_ids: set) -> list[dict]:
    if not DECISIONS_JSONL.exists():
        return []
    answered = set()
    log_path = STATE_DIR / "decisions_log.jsonl"
    if log_path.exists():
        for line in log_path.open():
            try:
                answered.add(json.loads(line).get("id"))
            except Exception:
                continue
    kept: list[dict] = []
    for line in DECISIONS_JSONL.open():
        try:
            rec = json.loads(line)
        except Exception:
            continue
        rid = str(rec.get("id", ""))
        if rid.startswith(EXTERNAL_INTAKE_PREFIXES) and rid not in answered and rid not in gathered_ids:
            kept.append(rec)
    return kept


def write_outputs(items: list[DecisionItem]) -> bool:
    """Write JSONL always; stage the vault markdown only when it changed.

    Returns True when the markdown was staged, False on a no-op skip.
    """
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    preserved = _preserved_external_rows({it.id for it in items})
    # JSONL → ~/.claude/state/ (local, no TCC issue)
    with DECISIONS_JSONL.open("w") as fh:
        for it in items:
            fh.write(json.dumps(asdict(it), default=str) + "\n")
        for rec in preserved:
            fh.write(json.dumps(rec, default=str) + "\n")
    # Markdown → staged vault write (flushed to iCloud by vault-flush LaunchAgent)
    md = render_md(items)
    if _vault_md_unchanged(DECISIONS_MD_REL, md):
        return False
    vault_write(DECISIONS_MD_REL, md)
    return True


def main() -> int:
    items = gather()
    staged = write_outputs(items)
    md_note = "decisions_pending.md" if staged else "decisions_pending.md unchanged (skipped)"
    print(f"[aggregate] {len(items)} pending → {md_note} + {DECISIONS_JSONL.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
