#!/usr/bin/env python3
"""gmail-triage — classify inbox threads, write three digests, stage archive list.

Architecture:
- Classifier: pure (sender, subject, snippet, labels, sent_by_matt_last) -> bucket
- GmailTransport: subprocess wrapper for `gmail-skill` CLI (reads + mutations)
- DigestWriter: produces humans_awaiting_reply.md / my_follow_ups.md / actions_and_deals.md
- CLI verbs: triage / digest / apply-kill-list / learn

Inputs (all paths can be missing — degrade gracefully):
- ~/.claude/skills/fakematt-email/tier_map.json
- MattZerg/_agent_memory/feedback_email_kill_list.md
- MattZerg/_agent_memory/feedback_email_deal_watchlist.md
- MattZerg/_agent_memory/feedback_email_human_tier_overrides.md

Outputs:
- ~/Downloads/email_triage_<date>/{humans_awaiting_reply,my_follow_ups,actions_and_deals}.md
- ~/Downloads/email_triage_<date>/{kill_list_ids,inventory}.{txt,json}
- ~/.config/zerg/morning-brief-fixtures/email_triage_<date>.md
- ~/.claude/state/gmail_triage.jsonl (append-only audit)
- ~/.claude/state/gmail_triage_alerts.jsonl (deal-watch alert queue)
- MattZerg/Tasks/inbox.md (auto section "Email Follow-ups — auto" replaced)

Safety: defaults are DRY-RUN. Use --apply to actually mutate Gmail (archive, label).
Flags: --alert (fire notifications), --write-inbox (update Tasks/inbox.md).
"""
from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

HOME = Path.home()
VAULT = HOME / "Library/Mobile Documents/iCloud~md~obsidian/Documents/Zerg"
TIER_MAP = HOME / ".claude/skills/fakematt-email/tier_map.json"
KILL_LIST = VAULT / "MattZerg/_agent_memory/feedback_email_kill_list.md"
DEAL_WATCH = VAULT / "MattZerg/_agent_memory/feedback_email_deal_watchlist.md"
TIER_OVERRIDES = VAULT / "MattZerg/_agent_memory/feedback_email_human_tier_overrides.md"
GMAIL_SKILL = HOME / ".claude/skills/gmail-skill/gmail_skill.py"
MORNING_BRIEF_FIXTURES = HOME / ".config/zerg/morning-brief-fixtures"
STATE_LOG = HOME / ".claude/state/gmail_triage.jsonl"
ALERT_QUEUE = HOME / ".claude/state/gmail_triage_alerts.jsonl"
HEARTBEAT_FILE = HOME / ".claude/state/gmail_triage.heartbeat"
INBOX_MD = VAULT / "MattZerg/Tasks/inbox.md"
INBOX_AUTO_SECTION_MARK = "<!-- gmail-triage:auto-followups -->"

BUCKETS = (
    "HUMAN_IN",       # Tier A/B contact wrote me, needs reply
    "MINE_OUT",       # I sent last, no reply ≥5d
    "DEAL",           # allow-listed sender + threshold-meeting promo
    "PROJECT",        # action-required / final reminder / due / expires
    "RECEIPT",        # routine receipt/confirmation — label and archive
    "KILL",           # newsletter/promo/social — archive
    "KEEP_INBOX",     # leave alone, not covered by any rule
    "EXCLUDED",       # family / personal — never touch
)

ACTION_KEYWORDS = re.compile(
    r"\b(action required|final reminder|expires?|due\s+\d|deadline|past due|"
    r"verify your identity|payment failed|signature required)\b",
    re.I,
)

DEAL_SUBJECT = re.compile(
    r"(\d+%\s*off|\$\s*\d+\s*off|expires?\s+\w+\s*\d|tonight only|last chance|"
    r"price drop|points?\s+offer|earn\s+\d{2,3},?\d{3}\s+points)",
    re.I,
)

RECEIPT_DOMAINS = {
    "noreply@uber.com",
    "no-reply@gopuff.com",
    "no-reply@noreply.gopuff.com",
    "order-update@amazon.com",
    "shipment-tracking@amazon.com",
    "noreply@robinhood.com",
    "no_reply@post.applecard.apple",
    "noreply@service.paypal.com",
    "invoice+statements@mail.anthropic.com",
    "xfinity@account.xfinity.com",
    "noreply-billingpayment@notify.dteenergy.com",
    "AmericanExpress@welcome.americanexpress.com",
    "noreply@discord.com",
}

# Senders that always justify inbox attention (override KILL).
# Human contacts go via tier_map, not here — this is for system/automated senders only.
ALWAYS_KEEP = {
    "notifications@stripe.com",
    "sc-noreply@google.com",
    "messaging-service@post.xero.com",
}

# Domains/handles considered family / personal — never apply professional rules
EXCLUDED_SENDERS = {
    "dean.eisner@gmail.com",
    "christine@fromhopetohomefilm.com",
    "ce3136@gmail.com",
    "leutholdcat@hotmail.com",
    "seisner1234@gmail.com",
}


@dataclass
class Thread:
    id: str
    sender: str                # full "name <email>" or just email
    sender_email: str          # parsed lowercase email
    subject: str
    snippet: str
    labels: list[str] = field(default_factory=list)
    last_from_matt: bool = False
    last_msg_date: Optional[dt.datetime] = None
    days_since_last_message: int = 0

    @classmethod
    def from_mcp(cls, t: dict) -> "Thread":
        msgs = t.get("messages", [])
        if not msgs:
            return cls(id=t["id"], sender="", sender_email="", subject="", snippet="")
        last = msgs[-1]
        sender = last.get("sender", "")
        email = parse_email(sender)
        date_str = last.get("date", "")
        d = _parse_msg_date(date_str)
        last_from_matt = email.endswith("@gmail.com") and "matteisn" in email
        days = (dt.datetime.now(dt.timezone.utc) - d).days if d else 0
        return cls(
            id=t["id"],
            sender=sender,
            sender_email=email,
            subject=last.get("subject", ""),
            snippet=last.get("snippet", ""),
            labels=last.get("labelIds", []),
            last_from_matt=last_from_matt,
            last_msg_date=d,
            days_since_last_message=days,
        )


def _parse_msg_date(date_str: str) -> Optional[dt.datetime]:
    """Parse an email/message date into a tz-AWARE datetime, or None.

    Handles ISO-8601 (with 'Z', explicit offset, or naive) and RFC 2822 email
    dates. Naive results are assumed UTC so downstream `now(utc) - d` never mixes
    aware/naive datetimes — the bug that crashed triage at from_mcp() for 10 days
    (TypeError: can't subtract offset-naive and offset-aware datetimes).
    """
    if not date_str:
        return None
    s = date_str.strip()
    # ISO-8601 first (covers gmail-skill's normalized output).
    try:
        d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    except Exception:
        pass
    # RFC 2822 fallback (raw email headers, e.g. "Mon, 19 Jun 2026 07:00:00 -0400").
    try:
        from email.utils import parsedate_to_datetime

        d = parsedate_to_datetime(s)
        if d is None:
            return None
        return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None


def parse_email(raw: str) -> str:
    """Extract lowercase email from 'Name <email@x>' or 'email@x'."""
    m = re.search(r"<([^>]+)>", raw)
    if m:
        return m.group(1).strip().lower()
    return raw.strip().lower()


class TierMap:
    """Loads fakematt-email/tier_map.json and exposes register lookup."""

    def __init__(self, path: Path = TIER_MAP):
        self.path = path
        self.by_email: dict[str, str] = {}
        self.excluded: set[str] = set(EXCLUDED_SENDERS)
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        data = json.loads(self.path.read_text())
        for tier in ("A", "B", "C"):
            members = data.get(tier, {}).get("members", [])
            for m in members:
                self.by_email[m.lower()] = tier
        for x in data.get("_excluded", {}).get("members", []):
            self.excluded.add(x.lower())

    def register(self, email: str) -> Optional[str]:
        return self.by_email.get(email.lower())

    def is_excluded(self, email: str) -> bool:
        return email.lower() in self.excluded


class KillList:
    """Parses feedback_email_kill_list.md for the set of senders to archive on sight."""

    def __init__(self, path: Path = KILL_LIST):
        self.path = path
        self.senders: set[str] = set()
        self.domains: set[str] = set()
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        text = self.path.read_text()
        # Pull bullet items starting with `- ` and a backticked email/domain
        for m in re.finditer(r"^[-*]\s+`([^`]+)`", text, re.M):
            tok = m.group(1).strip().lower()
            if "@" in tok:
                self.senders.add(tok)
            elif tok.startswith("@") or "." in tok:
                self.domains.add(tok.lstrip("@"))

    def hits(self, email: str) -> bool:
        if email in self.senders:
            return True
        domain = email.split("@", 1)[-1] if "@" in email else email
        return domain in self.domains


class DealWatch:
    """Parses feedback_email_deal_watchlist.md for allow-list + thresholds."""

    def __init__(self, path: Path = DEAL_WATCH):
        self.path = path
        self.allow_brands: list[str] = []
        self.allow_flight_senders: set[str] = set()
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        text = self.path.read_text()
        # Allow-list — extract bullet-noted brands
        brand_section = re.search(
            r"Brands Matt has purchased.*?(?=\n##|\n---|\Z)", text, re.S
        )
        if brand_section:
            for m in re.finditer(r"\*\*([A-Z][\w\s&]+)\*\*", brand_section.group(0)):
                self.allow_brands.append(m.group(1).strip().lower())
        # Flight senders — explicit allow-list block
        flight_section = re.search(
            r"Allow-list \(always inbox.*?\n((?:- `[^`]+`\n?)+)", text
        )
        if flight_section:
            for m in re.finditer(r"`([^`]+)`", flight_section.group(1)):
                self.allow_flight_senders.add(m.group(1).strip().lower())

    def is_flight_sender(self, email: str) -> bool:
        return email.lower() in self.allow_flight_senders

    def matches_brand(self, sender: str) -> bool:
        s = sender.lower()
        return any(b in s for b in self.allow_brands)


class Classifier:
    """Pure classification — no I/O. Apply 8-rule chain in order."""

    def __init__(self, tier_map: TierMap, kill: KillList, deals: DealWatch):
        self.tier_map = tier_map
        self.kill = kill
        self.deals = deals

    def classify(self, t: Thread) -> tuple[str, str]:
        """Returns (bucket, rationale)."""
        e = t.sender_email
        # 1. Excluded (family/personal) — never touch
        if self.tier_map.is_excluded(e):
            return "EXCLUDED", "in tier_map _excluded"
        # 2. Tier A/B human reply needed — checked BEFORE system-sender shortcut
        #    so a human in the tier map always wins, regardless of domain.
        tier = self.tier_map.register(e)
        if tier in ("A", "B") and not t.last_from_matt:
            return "HUMAN_IN", f"tier {tier} contact wrote last"
        # 3. Always-keep system senders (Stripe action, search console, xero invoices)
        if e in ALWAYS_KEEP:
            if ACTION_KEYWORDS.search(t.subject) or ACTION_KEYWORDS.search(t.snippet):
                return "PROJECT", "system sender with action keywords"
            return "KEEP_INBOX", "system sender (no action keywords)"
        # 4. Mine-out (Matt sent last, ≥5 days silent)
        if t.last_from_matt and t.days_since_last_message >= 5:
            return "MINE_OUT", f"sent {t.days_since_last_message}d ago, no reply"
        # 5. Kill-list — archive on sight
        if self.kill.hits(e):
            return "KILL", "matched kill-list sender"
        # 6. Receipt — keep but archive + label
        if e in RECEIPT_DOMAINS:
            return "RECEIPT", "routine receipt"
        # 7. Deal — allow-list sender + threshold-meeting subject
        if self.deals.is_flight_sender(e):
            if DEAL_SUBJECT.search(t.subject) or DEAL_SUBJECT.search(t.snippet):
                return "DEAL", "flight allow-list + deal threshold"
            return "KEEP_INBOX", "flight allow-list, no deal threshold hit"
        if self.deals.matches_brand(t.sender):
            if DEAL_SUBJECT.search(t.subject):
                return "DEAL", "brand allow-list + deal threshold"
        # 8. Project-movement — generic action-required heuristic
        if ACTION_KEYWORDS.search(t.subject):
            return "PROJECT", "action keyword in subject"
        # 9. Tier C contact — keep but lower priority than A/B
        if tier == "C" and not t.last_from_matt:
            return "HUMAN_IN", "tier C contact wrote last"
        return "KEEP_INBOX", "no rule fired"


class GmailTransport:
    """subprocess wrapper around gmail-skill CLI. Reads + writes."""

    def __init__(self, gmail_skill: Path = GMAIL_SKILL):
        self.gmail_skill = gmail_skill

    def available(self) -> bool:
        if not self.gmail_skill.exists():
            return False
        # Quick probe — call with no args, expect non-zero (CLI prints help)
        try:
            r = subprocess.run(
                ["python3", str(self.gmail_skill), "accounts"],
                capture_output=True, text=True, timeout=10,
            )
            return r.returncode == 0
        except Exception:
            return False

    def list_inbox(self, max_results: int = 200) -> list[dict]:
        """List inbox threads via gmail-skill, normalized to thread-shape dicts.

        Always returns a list (possibly empty) of {"id", "messages": [...]}
        dicts, or raises RuntimeError. NEVER returns None — a None/unknown
        response shape is a loud failure, not a silent skip.
        """
        # Retry transient gmail-skill failures (e.g. ConnectionResetError to
        # Google surfaces as a non-zero exit) with backoff before giving up.
        cmd = ["python3", str(self.gmail_skill), "list",
               "--label", "INBOX", "--max-results", str(max_results)]
        r = None
        last_err = ""
        for attempt in range(3):
            if attempt:
                time.sleep(2 * attempt)  # 0s, 2s, 4s backoff
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            except subprocess.TimeoutExpired:
                last_err = "gmail-skill list timed out after 120s"
                continue
            if r.returncode == 0:
                break
            last_err = (f"gmail-skill list failed (exit {r.returncode}): "
                        f"{r.stderr.strip()[:300]}")
        if r is None or r.returncode != 0:
            raise RuntimeError(
                f"{last_err} (after 3 attempts — likely transient network/auth, "
                "e.g. ConnectionResetError to Google)"
            )
        try:
            raw = json.loads(r.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"gmail-skill list printed non-JSON stdout ({e}): {r.stdout[:300]!r}"
            )
        if isinstance(raw, dict):
            if raw.get("error"):
                raise RuntimeError(f"gmail-skill list returned error: {raw['error']}")
            if isinstance(raw.get("threads"), list):
                # Legacy MCP shape — already thread-shaped
                return raw["threads"]
            if isinstance(raw.get("results"), list):
                # Current gmail-skill CLI shape — flat message summaries
                return [self._cli_item_to_thread(item) for item in raw["results"]]
        elif isinstance(raw, list):
            return raw
        keys = sorted(raw.keys()) if isinstance(raw, dict) else type(raw).__name__
        raise RuntimeError(
            f"gmail-skill list returned unexpected shape ({keys}); "
            "expected dict with 'threads' or 'results' list, or a bare list. "
            "Refusing to continue silently."
        )

    @staticmethod
    def _cli_item_to_thread(item: dict) -> dict:
        """Adapt a flat gmail-skill CLI message item to the thread shape
        Thread.from_mcp expects ({"id", "messages": [{sender, date, ...}]})."""
        date_iso = ""
        raw_date = item.get("date", "")
        if raw_date:
            try:  # CLI emits RFC 2822 dates; from_mcp expects ISO
                date_iso = email.utils.parsedate_to_datetime(raw_date).isoformat()
            except Exception:
                date_iso = ""
        return {
            # message id, not threadId — mark-done / reply-to take message ids
            "id": item.get("id") or item.get("threadId", ""),
            "messages": [{
                "sender": item.get("from", ""),
                "subject": item.get("subject", ""),
                "snippet": item.get("snippet", ""),
                "date": date_iso,
                "labelIds": item.get("labels", []),
            }],
        }

    def mark_done(self, thread_id: str) -> bool:
        r = subprocess.run(
            ["python3", str(self.gmail_skill), "mark-done", thread_id],
            capture_output=True, text=True, timeout=30,
        )
        return r.returncode == 0


class DigestWriter:
    """Produces the three markdown digests + inventory + kill_list_ids."""

    def __init__(self, out_dir: Path, classifier: Classifier):
        self.out_dir = out_dir
        self.classifier = classifier
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def write(self, classified: list[tuple[Thread, str, str]]) -> dict:
        """Returns a summary dict with counts per bucket."""
        buckets: dict[str, list[Thread]] = {b: [] for b in BUCKETS}
        rationales: dict[str, str] = {}
        for t, bucket, rationale in classified:
            buckets[bucket].append(t)
            rationales[t.id] = rationale

        self._write_actions_and_deals(buckets)
        self._write_humans(buckets["HUMAN_IN"])
        self._write_follow_ups(buckets["MINE_OUT"])
        self._write_kill_list_ids(buckets["KILL"])
        self._write_inventory(buckets, rationales)
        return {b: len(v) for b, v in buckets.items()}

    def _write_actions_and_deals(self, buckets) -> None:
        lines = [f"# Actions & deals — {dt.date.today().isoformat()}\n"]
        if buckets["PROJECT"]:
            lines.append("## 🔴 Project-movement / action required\n")
            for t in buckets["PROJECT"]:
                lines.append(
                    f"- `{t.id}` — **{t.subject}** · from `{t.sender_email}` · "
                    f"{t.days_since_last_message}d ago"
                )
            lines.append("")
        if buckets["DEAL"]:
            lines.append("## 🟢 Time-bound deals\n")
            for t in buckets["DEAL"]:
                lines.append(
                    f"- `{t.id}` — **{t.subject}** · from `{t.sender_email}`"
                )
            lines.append("")
        (self.out_dir / "actions_and_deals.md").write_text("\n".join(lines))

    def _write_humans(self, threads) -> None:
        lines = [f"# Humans awaiting your reply — {dt.date.today().isoformat()}\n"]
        if not threads:
            lines.append("_None today._\n")
        for t in threads:
            tier = self.classifier.tier_map.register(t.sender_email) or "?"
            lines.append(
                f"## Tier {tier} — `{t.sender_email}`\n"
                f"- Thread: `{t.id}`\n"
                f"- Last: {t.days_since_last_message}d ago\n"
                f"- Subject: {t.subject}\n"
                f"- CLI: `python3 ~/.claude/skills/fakematt-email/run.py "
                f"--to {t.sender_email} --reply-to-id {t.id}`\n"
            )
        (self.out_dir / "humans_awaiting_reply.md").write_text("\n".join(lines))

    def _write_follow_ups(self, threads) -> None:
        lines = [f"# Threads where you sent last — {dt.date.today().isoformat()}\n"]
        if not threads:
            lines.append("_None silent today._\n")
        for t in threads:
            lines.append(
                f"- `{t.id}` — **{t.subject}** · {t.days_since_last_message}d silent · "
                f"last to: `{t.sender_email}`"
            )
        (self.out_dir / "my_follow_ups.md").write_text("\n".join(lines))

    def _write_kill_list_ids(self, threads) -> None:
        lines = [f"# Kill-list thread IDs — {dt.date.today().isoformat()}"]
        lines.append("# Generated by gmail-triage; pass to apply_kill_list.sh")
        for t in threads:
            lines.append(f"{t.id}  # {t.sender_email} — {t.subject[:60]}")
        (self.out_dir / "kill_list_ids.txt").write_text("\n".join(lines))

    def _write_inventory(self, buckets, rationales) -> None:
        inv = {
            "_generated": dt.datetime.now().isoformat(),
            "counts": {b: len(v) for b, v in buckets.items()},
            "threads": [
                {"id": t.id, "bucket": b, "sender": t.sender_email,
                 "subject": t.subject, "rationale": rationales[t.id]}
                for b, ts in buckets.items() for t in ts
            ],
        }
        (self.out_dir / "inventory.json").write_text(json.dumps(inv, indent=2))


def log_event(event: dict) -> None:
    STATE_LOG.parent.mkdir(parents=True, exist_ok=True)
    event["ts"] = dt.datetime.now().isoformat()
    with STATE_LOG.open("a") as f:
        f.write(json.dumps(event) + "\n")


# ─── P4: flight-deal alerter ────────────────────────────────────────────

PCT_OFF_RE = re.compile(r"(-?\d{2,3})\s*%\s*(?:off|cheaper)?", re.I)
DOLLAR_OFF_RE = re.compile(r"\$\s*(\d{2,4})\s*off", re.I)
POINTS_RE = re.compile(r"(\d{2,3}),?\s*000\s+points", re.I)


def deal_score(t: Thread) -> dict:
    """Extract score signals from a DEAL thread. Returns dict with int fields."""
    text = f"{t.subject} {t.snippet}"
    pct = 0
    m = PCT_OFF_RE.search(text)
    if m:
        try:
            pct = int(m.group(1).lstrip("-"))
        except Exception:
            pct = 0
    dollars = 0
    m = DOLLAR_OFF_RE.search(text)
    if m:
        try:
            dollars = int(m.group(1))
        except Exception:
            dollars = 0
    points = 0
    m = POINTS_RE.search(text)
    if m:
        try:
            points = int(m.group(1)) * 1000
        except Exception:
            points = 0
    return {"pct_off": pct, "dollars_off": dollars, "points": points}


def is_alert_worthy(t: Thread, dw: DealWatch, score: dict) -> bool:
    """Threshold check — only fire for flight senders + strong signal."""
    if not dw.is_flight_sender(t.sender_email):
        return False
    if score["pct_off"] >= 30:
        return True
    if score["dollars_off"] >= 100:
        return True
    if score["points"] >= 50000:
        return True
    return False


def notify_deal(t: Thread, score: dict, apply: bool = False) -> None:
    """Append to alert queue + (if apply) fire macOS notification."""
    payload = {
        "thread_id": t.id,
        "sender": t.sender_email,
        "subject": t.subject,
        "snippet": t.snippet[:120],
        "score": score,
        "ts": dt.datetime.now().isoformat(),
    }
    ALERT_QUEUE.parent.mkdir(parents=True, exist_ok=True)
    with ALERT_QUEUE.open("a") as f:
        f.write(json.dumps(payload) + "\n")
    if not apply:
        return
    # macOS native notification
    title = f"Flight deal — {t.sender_email}"
    body_parts = []
    if score["pct_off"]:
        body_parts.append(f"{score['pct_off']}% off")
    if score["dollars_off"]:
        body_parts.append(f"${score['dollars_off']} off")
    if score["points"]:
        body_parts.append(f"{score['points']:,} pts")
    body = " · ".join(body_parts) or "deal signal"
    subj = (t.subject or "")[:80].replace('"', '\\"')
    try:
        subprocess.run(
            ["osascript", "-e",
             f'display notification "{subj}" with title "{title}" subtitle "{body}"'],
            timeout=5, check=False,
        )
    except Exception:
        pass


# ─── P5: follow-up-prompter (MINE_OUT → Tasks/inbox.md) ────────────────

INBOX_SECTION_HEADER = "## Email Follow-ups — auto"


def render_followup_section(threads) -> str:
    """Render the auto-section. Atomically replaces prior content."""
    lines = [
        INBOX_AUTO_SECTION_MARK,
        INBOX_SECTION_HEADER,
        "",
        "_Generated by gmail-triage — do not hand-edit. Re-run gmail-triage to refresh._",
        f"_Last run: {dt.datetime.now().isoformat(timespec='minutes')}_",
        "",
    ]
    if not threads:
        lines.append("_None silent today._")
    else:
        lines.append("| Thread | Last to | Days silent | Subject | Nudge command |")
        lines.append("|---|---|---|---|---|")
        for t in threads:
            subj = (t.subject or "")[:60].replace("|", "/")
            lines.append(
                f"| `{t.id}` | `{t.sender_email}` | {t.days_since_last_message}d | "
                f"{subj} | `fakematt-email --reply-to-id {t.id}` |"
            )
    lines.append("")
    lines.append(INBOX_AUTO_SECTION_MARK)
    return "\n".join(lines)


def update_inbox_md(threads, path: Path = INBOX_MD, apply: bool = False) -> bool:
    """Replace (or append) the auto section in inbox.md. Returns True if changed."""
    if not path.exists():
        return False
    text = path.read_text()
    new_section = render_followup_section(threads)
    # Atomic section replace via the markers
    pat = re.compile(
        re.escape(INBOX_AUTO_SECTION_MARK) + r".*?" + re.escape(INBOX_AUTO_SECTION_MARK),
        re.S,
    )
    if pat.search(text):
        new_text = pat.sub(new_section, text)
    else:
        # First-time append: leave a clear gap before the section
        new_text = text.rstrip() + "\n\n---\n\n" + new_section + "\n"
    if new_text == text:
        return False
    if apply:
        path.write_text(new_text)
    return True


def cmd_triage(args) -> int:
    tier_map = TierMap()
    kill = KillList()
    deals = DealWatch()
    classifier = Classifier(tier_map, kill, deals)
    transport = GmailTransport()

    if not transport.available():
        print("ERROR: gmail-skill CLI not available. Install deps + re-auth.", file=sys.stderr)
        print("  pip3 install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client requests", file=sys.stderr)
        print(f"  python3 {GMAIL_SKILL} accounts", file=sys.stderr)
        return 2

    raw_threads = None
    last_err: Optional[Exception] = None
    for attempt in range(3):
        try:
            raw_threads = transport.list_inbox(max_results=args.max_results)
            break
        except (RuntimeError, OSError) as e:
            # OSError covers transient IMAP/SSL resets (ConnectionResetError
            # [Errno 54]) that were crashing the whole daily triage UNCAUGHT
            # (the old `except RuntimeError` missed them). Retry with backoff.
            last_err = e
            log_event({"action": "triage_retry", "attempt": attempt + 1, "error": str(e)})
            if attempt < 2:
                time.sleep(2 * (attempt + 1))  # 2s, 4s
    if raw_threads is None:  # all retries failed, or list_inbox returned None
        reason = last_err if last_err is not None else "list_inbox returned None"
        print(f"ERROR: gmail-triage inbox fetch failed — {reason}", file=sys.stderr)
        log_event({"action": "triage_error", "error": str(reason)})
        return 1
    threads = [Thread.from_mcp(t) for t in raw_threads]
    classified = [(t, *classifier.classify(t)) for t in threads]

    out_dir = Path.home() / f"Downloads/email_triage_{dt.date.today().isoformat()}"
    writer = DigestWriter(out_dir, classifier)
    counts = writer.write(classified)

    print(f"Triaged {len(threads)} threads → {out_dir}")
    for b, c in counts.items():
        if c:
            print(f"  {b}: {c}")

    # Fold into morning-brief
    if MORNING_BRIEF_FIXTURES.exists():
        brief_path = MORNING_BRIEF_FIXTURES / f"email_triage_{dt.date.today().isoformat()}.md"
        brief_path.write_text((out_dir / "actions_and_deals.md").read_text())
        print(f"  morning-brief fixture: {brief_path}")

    log_event({"action": "triage", "total": len(threads), "counts": counts})

    # P4 — flight-deal alerts
    deal_threads = [c[0] for c in classified if c[1] == "DEAL"]
    alerts_fired = 0
    for t in deal_threads:
        score = deal_score(t)
        if is_alert_worthy(t, deals, score):
            notify_deal(t, score, apply=args.alert)
            alerts_fired += 1
    if alerts_fired:
        print(f"  alerts queued: {alerts_fired} ({'fired' if args.alert else 'dry-run'})")

    # P5 — follow-up-prompter writes MINE_OUT to Tasks/inbox.md
    mine_out = [c[0] for c in classified if c[1] == "MINE_OUT"]
    changed = update_inbox_md(mine_out, apply=args.write_inbox)
    if changed:
        print(f"  follow-up section: {'WRITTEN' if args.write_inbox else 'dry-run, would change'}")

    # Apply phase — only if user passed --apply
    if args.apply:
        killed = 0
        for t in [c[0] for c in classified if c[1] == "KILL"]:
            if transport.mark_done(t.id):
                killed += 1
                log_event({"action": "archive", "thread": t.id, "sender": t.sender_email})
        print(f"  archived: {killed}")

    # Heartbeat — written ONLY on full success; cron_health_doctor watches this
    HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
    HEARTBEAT_FILE.write_text(dt.datetime.now().isoformat() + "\n")
    return 0


def cmd_apply_kill_list(args) -> int:
    path = Path(args.path).expanduser()
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 1
    transport = GmailTransport()
    if not transport.available():
        print("ERROR: gmail-skill CLI not available", file=sys.stderr)
        return 2
    killed = 0
    skipped = 0
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            skipped += 1
            continue
        thread_id = line.split()[0]
        if transport.mark_done(thread_id):
            killed += 1
            log_event({"action": "archive", "thread": thread_id, "src": str(path)})
        else:
            print(f"  FAILED {thread_id}", file=sys.stderr)
    print(f"Archived {killed}, skipped {skipped}")
    return 0


def cmd_classify_fixture(args) -> int:
    """Standalone classify of a single thread fixture — useful for testing."""
    tier_map = TierMap()
    kill = KillList()
    deals = DealWatch()
    classifier = Classifier(tier_map, kill, deals)
    payload = json.loads(Path(args.fixture).read_text())
    t = Thread.from_mcp(payload)
    bucket, rationale = classifier.classify(t)
    print(json.dumps({"bucket": bucket, "rationale": rationale, "thread": asdict(t)}, default=str, indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="gmail-triage — classify + archive Gmail inbox")
    sub = p.add_subparsers(dest="cmd")

    t = sub.add_parser("triage", help="full triage pass")
    t.add_argument("--apply", action="store_true", help="archive KILL threads (default dry-run)")
    t.add_argument("--alert", action="store_true", help="fire macOS notifications for flight deals (default queue-only)")
    t.add_argument("--write-inbox", action="store_true", help="write MINE_OUT section into Tasks/inbox.md (default dry-run)")
    t.add_argument("--max-results", type=int, default=200)
    t.set_defaults(func=cmd_triage)

    a = sub.add_parser("apply-kill-list", help="archive thread IDs from a file")
    a.add_argument("path", help="path to kill_list_ids.txt")
    a.set_defaults(func=cmd_apply_kill_list)

    c = sub.add_parser("classify-fixture", help="classify a single thread JSON (testing)")
    c.add_argument("fixture", help="path to thread JSON")
    c.set_defaults(func=cmd_classify_fixture)

    args = p.parse_args()
    if not getattr(args, "func", None):
        p.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
