#!/usr/bin/env python3
"""Fake Matt cross-channel intake bridge.

Scans explicit Fake Matt intake from:
- Slack bridge inbox JSONL
- Gmail messages matching an explicit Fake Matt query

Classifies packets into internal writes (tasks, reminders, memories) and
outbound proposals (reply drafts). External sends/posts are never performed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import importlib.util
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

PT = ZoneInfo("America/Los_Angeles")
HOME = Path.home()
SKILL_DIR = Path(__file__).resolve().parents[1]

# Shared Slack-message formatter (status emoji set + 15-line ceiling).
sys.path.insert(0, str(HOME / ".config" / "zerg"))
from slack_format import FYI, HOLD, INFO, OK, WARN, compose  # noqa: E402
CODEX_SKILLS = HOME / ".codex" / "skills"
ZERG_ROOT = Path(
    os.environ.get(
        "ZERG_ROOT",
        str(HOME / "Obsidian/Zerg"),
    )
)
TASKS_INBOX = ZERG_ROOT / "MattZerg/Tasks/inbox.md"
INTAKE_DIR = ZERG_ROOT / "MattZerg/Tasks/fakematt-intake"
IDEAS_DIR = ZERG_ROOT / "MattZerg/Ideas"
REPLY_QUEUE_DIR = INTAKE_DIR / "reply-queue"
# Canonical work-lane memory (post 2026-06-30 iCloud->Obsidian migration). The old
# ~/.claude/projects/<iCloud-slug>/memory is now just a symlink to this dir — depend on
# the canonical location directly so a stale-project-dir/symlink cleanup can't break memory.
_CANON_MEMORY = HOME / "Obsidian/Zerg/MattZerg/claude-memory"
_LEGACY_MEMORY = HOME / ".claude/projects/-Users-mattheweisner-Library-Mobile-Documents-iCloud-md-obsidian-Documents-Zerg/memory"
MEMORY_DIR = _CANON_MEMORY if _CANON_MEMORY.exists() else _LEGACY_MEMORY
MEMORY_INDEX = MEMORY_DIR / "MEMORY.md"
STATE_PATH = Path(os.environ.get("FAKEMATT_OPERATOR_STATE", str(INTAKE_DIR / "state.json"))).expanduser()
EVENTS_PATH = Path(
    os.environ.get(
        "FAKEMATT_OPERATOR_EVENTS",
        str(STATE_PATH.with_name("state_events.jsonl")),
    )
).expanduser()
SLACK_INBOX = CODEX_SKILLS / "slack-skill/inbox.jsonl"
GMAIL = CODEX_SKILLS / "gmail-skill/gmail_skill.py"
FAKEMATT_EMAIL = CODEX_SKILLS / "fakematt-email/run.py"
SLACK_CONFIG = CODEX_SKILLS / "slack-skill/config.json"
SLACK_SKILL = CODEX_SKILLS / "slack-skill/slack_skill.py"
SLACK_PYTHON = CODEX_SKILLS / "slack-skill/.venv/bin/python"
SLACK_VOICE = ZERG_ROOT / "MattZerg/_style/slack_voice.md"
VOICE_UNIVERSALS = ZERG_ROOT / "MattZerg/_style/voice_universals.md"
FM_DM_CHANNEL = "D0B0T0ETDR8"
MATT_SLACK_USER = "U0AFSSPNB1N"
GMAIL_ACCOUNTS = ["matteisn@gmail.com", "matthew@zergai.com"]

DEFAULT_GMAIL_QUERY = (
    '("FM intake" OR "Fake Matt intake" OR "to Fake Matt" OR "remember this" '
    'OR "add this to my tasks" OR "add to my tasks" OR "ingest this" OR "note to self" '
    'OR "capture this" OR "context for Fake Matt" OR "note for Fake Matt") '
    'newer_than:14d -from:notifications@github.com'
)
_FALLBACK_MODEL = "claude-sonnet-4-5"
_AITR_SCRIPTS = Path.home() / ".claude" / "skills" / "aitr" / "scripts"
_routed_cache: dict[str, str] = {}


def routed_model(task_kind: str) -> str:
    """Model for this task: FAKEMATT_OPERATOR_MODEL env override > aitr routing >
    hardcoded fallback (loud). Lazy + memoized — --no-llm runs never route.

    Two task shapes in this script: packet classification (task_kind=classify,
    cheap model is fine) and Slack voice drafting (task_kind=draft-prose, needs a
    voice-capable model)."""
    env_model = os.environ.get("FAKEMATT_OPERATOR_MODEL")
    if env_model:
        return env_model
    if task_kind in _routed_cache:
        return _routed_cache[task_kind]
    if str(_AITR_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_AITR_SCRIPTS))
    try:
        from skill_default import aitr_model_or
        model = aitr_model_or(
            _FALLBACK_MODEL,
            task_kind=task_kind,
            caller="fakematt-operator-intake",
            quality_floor="medium",
        )
    except ImportError:
        print(f"[aitr] unavailable — using fallback {_FALLBACK_MODEL}", file=sys.stderr)
        model = _FALLBACK_MODEL
    _routed_cache[task_kind] = model
    return model
IDEA_CATEGORIES = {
    "zerg-product",
    "zerg-content",
    "zerg-tooling",
    "personal-venture",
    "personal-life",
    "shopping",
    "research",
}

INTAKE_TRIGGERS = [
    "fake matt",
    "fakematt",
    "remember this",
    "remember that",
    "add this to my tasks",
    "add to my tasks",
    "add this to my task",
    "ingest this",
    "note to self",
    "follow up",
    "remind me",
    "turn this into",
    "save this",
    "capture this",
    "capture:",
    "context:",
    "note for fake matt",
    "context for fake matt",
]

GMAIL_NOISE_SUBJECTS = [
    "fm weekly",
    "pr run failed",
    "fakeidan + fakematt review",
    "fakematt review",
]


CLASSIFIER_SYSTEM = """You are Fake Matt Operator's intake classifier.

Classify source packets into a JSON object with this shape:

{
  "summary": "one short receipt",
  "actions": [
    {
      "type": "task",
      "bucket": "TO_DO|SHOULD_DO",
      "item": "verb-first task",
      "domain": "Finance|Zerg / ops|Tasks system|Personal|...",
      "why_now": "short reason",
      "source_id": "packet id"
    },
    {
      "type": "reminder",
      "item": "thing to remember",
      "trigger": "date or condition",
      "reminder_type": "Reminder|Alert|Opportunity",
      "domain": "domain",
      "source_id": "packet id"
    },
    {
      "type": "memory",
      "name": "short memory title",
      "description": "one-sentence future trigger",
      "memory_type": "feedback|project|preference|routing",
      "body": "1-4 paragraphs, source-backed, operational",
      "source_id": "packet id"
    },
    {
      "type": "reply_draft",
      "surface": "gmail|slack",
      "recipient": "name/email/channel if known",
      "task": "what the draft should accomplish",
      "source_id": "packet id"
    },
    {
      "type": "health_log",
      "raw": "exact health/workout/food text to parse later",
      "source_id": "packet id"
    },
    {
      "type": "idea",
      "item": "idea text",
      "domain": "domain",
      "source_id": "packet id"
    },
    {
      "type": "context_note",
      "context_type": "project|person|company|contact|general",
      "target": "optional person/project/company name",
      "body": "stable source-backed fact or context note",
      "source_id": "packet id"
    },
    {
      "type": "skip",
      "reason": "why no durable write",
      "source_id": "packet id"
    }
  ]
}

Rules:
- Only create memory when Matt explicitly says to remember/save a durable preference,
  correction, identity/routing rule, project fact, or recurring failure mode.
- Routine tasks belong in task/reminder actions, not memory.
- External replies are reply_draft actions only. Never ask to send/post.
- If a packet is just conversational or already handled, use skip.
- Preserve source IDs exactly.
- Output JSON only. No markdown fence.
"""


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {"seen_slack": [], "seen_gmail": []}
    try:
        return json.loads(STATE_PATH.read_text())
    except Exception:
        return {"seen_slack": [], "seen_gmail": []}


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))


def append_event(event: dict[str, Any]) -> None:
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with EVENTS_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, sort_keys=True) + "\n")
    except OSError as exc:
        print(f"[intake ledger: skipped - {exc}]", file=sys.stderr)


def read_events(days: int) -> list[dict[str, Any]]:
    if not EVENTS_PATH.exists():
        return []
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    events: list[dict[str, Any]] = []
    for raw in EVENTS_PATH.read_text().splitlines():
        if not raw.strip():
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        timestamp = event.get("timestamp_utc") or event.get("timestamp")
        try:
            parsed = dt.datetime.fromisoformat(timestamp)
        except (TypeError, ValueError):
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        if parsed >= cutoff:
            events.append(event)
    return events


def parse_json_from_stdout(out: str) -> dict[str, Any] | None:
    if "{" not in out:
        return None
    try:
        return json.loads(out[out.index("{") :])
    except json.JSONDecodeError:
        return None


def strip_html(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p\s*>", "\n\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def slugify(value: str, limit: int = 72) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return (value or "fakematt-intake")[:limit].strip("-")


def now_stamp() -> str:
    return dt.datetime.now(PT).strftime("%Y-%m-%d %H:%M %Z")


def packet_text(packet: dict[str, Any]) -> str:
    parts = [
        f"source_id: {packet['source_id']}",
        f"source: {packet['source']}",
        f"author: {packet.get('author', '')}",
        f"timestamp: {packet.get('timestamp', '')}",
        f"context: {packet.get('context', '')}",
        "",
        packet.get("text", ""),
    ]
    return "\n".join(p for p in parts if p is not None).strip()


def looks_like_intake(text: str) -> bool:
    lower = (text or "").lower()
    return any(trigger in lower for trigger in INTAKE_TRIGGERS)


def parse_received_at(value: str) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=PT)
        return parsed
    except ValueError:
        return None


def scan_slack(state: dict[str, Any], limit: int, since_days: int) -> list[dict[str, Any]]:
    if not SLACK_INBOX.exists():
        return []
    seen = set(state.get("seen_slack", []))
    cutoff = dt.datetime.now(PT) - dt.timedelta(days=since_days)
    rows: list[dict[str, Any]] = []
    for raw in SLACK_INBOX.read_text().splitlines()[-max(limit * 3, 50) :]:
        if not raw.strip():
            continue
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue
        key = f"{msg.get('channel_id')}:{msg.get('ts')}"
        if key in seen:
            continue
        received_at = parse_received_at(msg.get("received_at") or "")
        if received_at and received_at < cutoff:
            continue
        text = (msg.get("text") or "").strip()
        if not text:
            continue
        from_matt = msg.get("user_id") == MATT_SLACK_USER
        is_fm_dm = msg.get("channel_id") == FM_DM_CHANNEL
        if not from_matt:
            continue
        if not (is_fm_dm or looks_like_intake(text)):
            continue
        rows.append(
            {
                "source_id": f"slack:{key}",
                "source": "slack",
                "author": msg.get("user") or msg.get("user_id") or "unknown",
                "timestamp": msg.get("received_at") or msg.get("ts") or "",
                "context": f"{msg.get('channel') or msg.get('channel_id')} thread={msg.get('thread_ts') or ''}",
                "text": text,
                "_seen_key": key,
            }
        )
        if len(rows) >= limit:
            break
    return rows


def scan_gmail(state: dict[str, Any], query: str, max_results: int) -> list[dict[str, Any]]:
    seen = set(state.get("seen_gmail", []))
    packets: list[dict[str, Any]] = []
    for account in GMAIL_ACCOUNTS:
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(GMAIL),
                    "search",
                    query,
                    "--max-results",
                    str(max_results),
                    "--account",
                    account,
                ],
                capture_output=True,
                text=True,
                timeout=90,
            )
        except subprocess.TimeoutExpired:
            continue
        data = parse_json_from_stdout(result.stdout)
        if not data:
            continue
        for summary in data.get("results", []):
            msg_id = summary.get("id")
            if not msg_id or msg_id in seen:
                continue
            subject = (summary.get("subject") or "").lower()
            sender = (summary.get("from") or "").lower()
            if "notifications@github.com" in sender:
                continue
            if any(noise in subject for noise in GMAIL_NOISE_SUBJECTS):
                continue
            try:
                read = subprocess.run(
                    [
                        sys.executable,
                        str(GMAIL),
                        "read",
                        msg_id,
                        "--format",
                        "full",
                        "--account",
                        account,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=90,
                )
            except subprocess.TimeoutExpired:
                continue
            full = parse_json_from_stdout(read.stdout) or summary
            body = strip_html(full.get("body") or full.get("snippet") or "")
            text = body[:4000] if body else (full.get("snippet") or "")
            packets.append(
                {
                    "source_id": f"gmail:{account}:{msg_id}",
                    "source": "gmail",
                    "author": full.get("from") or "",
                    "timestamp": full.get("date") or "",
                    "context": f"account={account} subject={full.get('subject') or ''}",
                    "text": text,
                    "_seen_key": msg_id,
                }
            )
    return packets


def classify_packets(packets: list[dict[str, Any]], *, no_llm: bool = False) -> dict[str, Any]:
    if not packets:
        return {"summary": "No new Fake Matt intake packets.", "actions": []}
    deterministic: list[dict[str, Any]] = []
    remaining: list[dict[str, Any]] = []
    for packet in packets:
        actions = deterministic_actions(packet)
        if actions:
            deterministic.extend(actions)
        else:
            remaining.append(packet)

    if not remaining:
        return {
            "summary": f"{len(deterministic)} explicit intake command(s) parsed.",
            "actions": deterministic,
        }

    if no_llm:
        return {
            "summary": f"{len(packets)} packet(s) collected; classification skipped.",
            "actions": deterministic + [
                {"type": "skip", "reason": "classification skipped by --no-llm", "source_id": p["source_id"]}
                for p in remaining
            ],
        }

    try:
        make_client = load_make_client()
    except Exception as exc:
        result = heuristic_classify(remaining, f"LLM helper unavailable ({exc}); used conservative heuristics.")
        result["actions"] = deterministic + result.get("actions", [])
        if deterministic:
            result["summary"] = f"{len(deterministic)} explicit command(s) parsed. " + result["summary"]
        return result

    user_payload = "\n\n---\n\n".join(packet_text(p) for p in remaining)
    client = make_client(source="fakematt-operator")
    try:
        msg = client.messages.create(
            model=routed_model("classify"),
            max_tokens=4096,
            system=CLASSIFIER_SYSTEM,
            messages=[{"role": "user", "content": user_payload}],
        )
    except Exception as exc:
        summary = f"Classification retry later: {short_error(exc)}"
        return {
            "summary": summary,
            "_retry_later": is_transient_classifier_error(exc),
            "actions": deterministic + [
                {
                    "type": "skip",
                    "reason": "classification retry later",
                    "source_id": p["source_id"],
                }
                for p in remaining
            ],
        }
    text = msg.content[0].text.strip()
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        result = json.loads(match.group(0))
    result["actions"] = deterministic + result.get("actions", [])
    if deterministic:
        result["summary"] = f"{len(deterministic)} explicit command(s) parsed. " + (result.get("summary") or "")
    return result


def short_error(exc: Exception) -> str:
    text = str(exc) or repr(exc)
    text = re.sub(r"request_id':\s*'[^']+'", "request_id': '<redacted>'", text)
    text = re.sub(r'request_id":\s*"[^"]+"', 'request_id": "<redacted>"', text)
    return text[:240]


def is_transient_classifier_error(exc: Exception) -> bool:
    text = f"{type(exc).__name__} {exc}".lower()
    return any(marker in text for marker in ["429", "rate_limit", "rate limit", "overloaded", "timeout"])


def load_make_client():
    sys.path.insert(0, str(HOME / ".config" / "zerg"))
    try:
        from anthropic_client import make_client  # type: ignore

        return make_client
    except ModuleNotFoundError:
        pass

    max_client_dir = HOME / ".claude/skills/webpage-layout/_lib"
    sys.path.insert(0, str(max_client_dir))
    from max_client import make_client  # type: ignore

    return make_client


def remove_trigger_prefix(text: str) -> str:
    cleaned = text.strip()
    patterns = [
        r"^(?:fake matt[:,]?\s*)?",
        r"^(?:please\s+)?(?:add this to my tasks?|add to my tasks?|task[:,]?)\s*[:\-]?\s*",
        r"^(?:please\s+)?(?:remember this|remember that|remember|save this|note to self)\s*[:\-]?\s*",
        r"^(?:please\s+)?remind me\s*[:\-]?\s*",
    ]
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.I).strip()
    return cleaned or text.strip()


def deterministic_actions(packet: dict[str, Any]) -> list[dict[str, Any]]:
    action = deterministic_action(packet)
    if not action:
        return []
    if action.get("type") != "capture":
        return [action]
    return parse_capture_actions(action, packet)


def deterministic_action(packet: dict[str, Any]) -> dict[str, Any] | None:
    """Parse explicit one-line commands that are safe to apply without LLM.

    Supported forms:
    - task: <item>
    - todo: <item>
    - should: <item>
    - remind: <item> @ <trigger>
    - remember: <stable preference/fact/rule>
    - health: <zhealth-compatible text>
    - idea: <idea text>
    - note: <source-backed context>
    - context: <source-backed context>
    - capture: <multi-line command list>
    - reply: <drafting task>
    - reply: email to <email>: <drafting task>
    - reply: slack to <@person|#channel>: <drafting task>
    """
    text = packet.get("text", "").strip()
    if not text:
        return None
    m = re.match(r"^(?:fake\s*matt[:,]?\s*)?(task|todo|should|remind|remember|memory|health|idea|note|context|capture|reply)\s*:\s*(.+)$", text, re.I | re.S)
    if not m:
        return None
    kind = m.group(1).lower()
    body = m.group(2).strip()
    if not body:
        return None
    source_id = packet["source_id"]
    if kind in {"task", "todo"}:
        return {
            "type": "task",
            "bucket": "TO_DO",
            "item": body,
            "domain": "Tasks system",
            "why_now": "Explicit Fake Matt task command",
            "source_id": source_id,
            "safe_apply": True,
        }
    if kind == "should":
        return {
            "type": "task",
            "bucket": "SHOULD_DO",
            "item": body,
            "domain": "Tasks system",
            "why_now": "Explicit Fake Matt should-do command",
            "source_id": source_id,
            "safe_apply": True,
        }
    if kind == "remind":
        item, trigger = split_item_trigger(body)
        return {
            "type": "reminder",
            "item": item,
            "trigger": trigger or "Needs date/condition review",
            "reminder_type": "Reminder",
            "domain": "Personal",
            "source_id": source_id,
            "safe_apply": True,
        }
    if kind in {"remember", "memory"}:
        name = body.splitlines()[0][:80]
        return {
            "type": "memory",
            "name": name,
            "description": "Explicit Fake Matt memory command.",
            "memory_type": "feedback",
            "body": body,
            "source_id": source_id,
            "safe_apply": True,
        }
    if kind == "health":
        return {"type": "health_log", "raw": body, "source_id": source_id, "safe_apply": True}
    if kind == "idea":
        idea_item, category = parse_idea_body(body)
        action = {
            "type": "idea",
            "item": idea_item,
            "domain": "Ideas",
            "source_id": source_id,
            "safe_apply": True,
        }
        if category:
            action["category"] = category
        return action
    if kind in {"note", "context"}:
        context_type, target, context_body = parse_context_body(body)
        return {
            "type": "context_note",
            "context_type": context_type,
            "target": target,
            "body": context_body,
            "source_id": source_id,
            "safe_apply": True,
        }
    if kind == "capture":
        return {"type": "capture", "body": body, "source_id": source_id, "safe_apply": True}
    if kind == "reply":
        parsed = parse_reply_target(body, packet)
        parsed["safe_apply"] = parsed["surface"] in {"gmail", "slack"}
        return parsed
    return None


def parse_capture_actions(action: dict[str, Any], packet: dict[str, Any]) -> list[dict[str, Any]]:
    body = action.get("body") or ""
    items = split_capture_items(body)
    actions: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        child_packet = dict(packet)
        child_packet["text"] = item
        child_packet["source_id"] = f"{packet['source_id']}#{index}"
        child_action = deterministic_action(child_packet)
        if child_action and child_action.get("type") != "capture":
            actions.append(child_action)
        else:
            actions.append(
                {
                    "type": "skip",
                    "reason": "capture item needs explicit prefix",
                    "source_id": child_packet["source_id"],
                }
            )
    if not actions:
        return [
            {
                "type": "skip",
                "reason": "empty capture command",
                "source_id": packet["source_id"],
            }
        ]
    return actions


def split_capture_items(body: str) -> list[str]:
    lines = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        line = re.sub(r"^(?:[-*•]|\d+[.)])\s*", "", line).strip()
        if line:
            lines.append(line)
    if len(lines) <= 1:
        inline = re.split(r"\s*(?:;\s+|\s+\|\s+)\s*", body.strip())
        lines = [part.strip() for part in inline if part.strip()]
    return lines


def parse_reply_target(body: str, packet: dict[str, Any]) -> dict[str, Any]:
    source_id = packet["source_id"]
    email_match = re.match(r"^(?:email|gmail)\s+to\s+([^:\s]+)\s*:?\s*(.+)$", body, re.I | re.S)
    if email_match:
        return {
            "type": "reply_draft",
            "surface": "gmail",
            "recipient": email_match.group(1).strip(),
            "task": email_match.group(2).strip(),
            "source_id": source_id,
        }
    slack_match = re.match(r"^slack\s+to\s+([^:]+)\s*:?\s*(.+)$", body, re.I | re.S)
    if slack_match:
        return {
            "type": "reply_draft",
            "surface": "slack",
            "recipient": slack_match.group(1).strip(),
            "task": slack_match.group(2).strip(),
            "source_id": source_id,
        }
    return {
        "type": "reply_draft",
        "surface": packet.get("source", "unknown"),
        "recipient": packet.get("context", ""),
        "task": body,
        "source_id": source_id,
    }


def parse_idea_body(body: str) -> tuple[str, str | None]:
    category_match = re.match(r"^\[([a-z-]+)\]\s*(.+)$", body, re.I | re.S)
    if category_match:
        category = category_match.group(1).lower()
        if category in IDEA_CATEGORIES:
            return category_match.group(2).strip(), category
    colon_match = re.match(r"^([a-z-]+)\s*:\s*(.+)$", body, re.I | re.S)
    if colon_match:
        category = colon_match.group(1).lower()
        if category in IDEA_CATEGORIES:
            return colon_match.group(2).strip(), category
    return body.strip(), None


def parse_context_body(body: str) -> tuple[str, str, str]:
    body = body.strip()
    bracket_match = re.match(r"^\[(project|person|company|contact|general):\s*([^\]]+)\]\s*(.+)$", body, re.I | re.S)
    if bracket_match:
        return (
            bracket_match.group(1).lower(),
            bracket_match.group(2).strip(),
            bracket_match.group(3).strip(),
        )
    prefix_match = re.match(r"^(project|person|company|contact|general)\s+([^:]{1,100})\s*:\s*(.+)$", body, re.I | re.S)
    if prefix_match:
        return (
            prefix_match.group(1).lower(),
            prefix_match.group(2).strip(),
            prefix_match.group(3).strip(),
        )
    return "general", "", body


def split_item_trigger(body: str) -> tuple[str, str | None]:
    if " @ " in body:
        item, trigger = body.split(" @ ", 1)
        return item.strip(), trigger.strip()
    return body.strip(), None


def heuristic_classify(packets: list[dict[str, Any]], summary: str) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    for packet in packets:
        text = packet.get("text", "").strip()
        lower = text.lower()
        source_id = packet["source_id"]
        content = remove_trigger_prefix(text)
        if "remind me" in lower:
            actions.append(
                {
                    "type": "reminder",
                    "item": content,
                    "trigger": "Needs date/condition review",
                    "reminder_type": "Reminder",
                    "domain": "Personal",
                    "source_id": source_id,
                    "safe_apply": False,
                }
            )
        elif "add this to my task" in lower or "add to my task" in lower or lower.startswith("task:"):
            actions.append(
                {
                    "type": "task",
                    "bucket": "TO_DO",
                    "item": content,
                    "domain": "Tasks system",
                    "why_now": "Explicit Fake Matt task intake",
                    "source_id": source_id,
                    "safe_apply": False,
                }
            )
        elif any(k in lower for k in ["remember this", "remember that", "note to self", "save this"]):
            actions.append(
                {
                    "type": "memory",
                    "name": content[:80],
                    "description": "User-provided Fake Matt memory intake.",
                    "memory_type": "feedback",
                    "body": content,
                    "source_id": source_id,
                    "safe_apply": False,
                }
            )
        elif re.search(r"\b(pushups?|situps?|cal|calories|carbs?|weight|workout)\b", lower):
            actions.append({"type": "health_log", "raw": text, "source_id": source_id, "safe_apply": False})
        else:
            actions.append({"type": "skip", "reason": "No obvious safe heuristic action.", "source_id": source_id})
    return {"summary": summary, "actions": actions}


def find_section_bounds(lines: list[str], header: str) -> tuple[int, int]:
    start = next((i for i, line in enumerate(lines) if line.strip() == header), -1)
    if start < 0:
        raise ValueError(f"section {header!r} not found")
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## ") or (header == "## To Do" and lines[i].strip() == "---"):
            end = i
            break
    return start, end


def next_table_number(lines: list[str], start: int, end: int) -> int:
    nums = []
    for line in lines[start:end]:
        m = re.match(r"\|\s*(\d+)\s*\|", line)
        if m:
            nums.append(int(m.group(1)))
    return (max(nums) + 1) if nums else 1


def insert_table_row(path: Path, header: str, row: str) -> None:
    lines = path.read_text().splitlines()
    start, end = find_section_bounds(lines, header)
    insert_at = None
    for i in range(end - 1, start, -1):
        if lines[i].startswith("|") and not re.match(r"\|\s*-", lines[i]):
            insert_at = i + 1
            break
    if insert_at is None:
        insert_at = end
    lines.insert(insert_at, row)
    path.write_text("\n".join(lines) + "\n")


def append_task(action: dict[str, Any]) -> str:
    header = "## To Do" if action.get("bucket") == "TO_DO" else "## Should Do"
    lines = TASKS_INBOX.read_text().splitlines()
    start, end = find_section_bounds(lines, header)
    number = next_table_number(lines, start, end)
    item = clean_cell(action.get("item") or "Untitled task")
    if item and item.lower() in TASKS_INBOX.read_text().lower():
        return f"Skipped duplicate task: {item}"
    domain = clean_cell(action.get("domain") or "Tasks system")
    source = clean_cell(action.get("source_id") or "fakematt-operator")
    if header == "## To Do":
        why = clean_cell(action.get("why_now") or f"Captured from {source}")
        row = f"| {number} | {item} | {domain} | {why} (source: {source}) |"
    else:
        row = f"| {number} | {item} | {domain} (source: {source}) |"
    insert_table_row(TASKS_INBOX, header, row)
    return f"{header}: {item}"


def append_reminder(action: dict[str, Any]) -> str:
    lines = TASKS_INBOX.read_text().splitlines()
    start, end = find_section_bounds(lines, "## Reminders / Alerts / Opportunities")
    number = next_table_number(lines, start, end)
    item = clean_cell(action.get("item") or "Untitled reminder")
    if item and item.lower() in TASKS_INBOX.read_text().lower():
        return f"Skipped duplicate reminder: {item}"
    trigger = clean_cell(action.get("trigger") or "When relevant")
    typ = clean_cell(action.get("reminder_type") or "Reminder")
    domain = clean_cell(action.get("domain") or "Personal")
    source = clean_cell(action.get("source_id") or "fakematt-operator")
    row = f"| {number} | {item} | {trigger} | {typ} | {domain} (source: {source}) |"
    insert_table_row(TASKS_INBOX, "## Reminders / Alerts / Opportunities", row)
    return f"Reminder: {item}"


def clean_cell(value: str) -> str:
    return str(value).replace("|", "/").replace("\n", " ").strip()


def write_memory(action: dict[str, Any]) -> str:
    name = clean_cell(action.get("name") or "Fake Matt intake")
    description = clean_cell(action.get("description") or "Captured by fakematt-operator.")
    mem_type = clean_cell(action.get("memory_type") or "feedback")
    if mem_type not in {"feedback", "project", "preference", "routing"}:
        mem_type = "feedback"
    prefix = "project" if mem_type == "project" else "feedback"
    filename = f"{prefix}_{slugify(name)}.md"
    path = MEMORY_DIR / filename
    if path.exists():
        stem = path.stem
        path = MEMORY_DIR / f"{stem}_{dt.datetime.now(PT).strftime('%Y%m%d%H%M%S')}.md"
        filename = path.name
    body = (action.get("body") or "").strip()
    source = action.get("source_id") or "fakematt-operator"
    content = (
        "---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        f"type: {mem_type}\n"
        f"origin: {source}\n"
        "---\n"
        f"{body}\n\n"
        f"Source: `{source}`. Captured by `fakematt-operator` on {now_stamp()}.\n"
    )
    path.write_text(content)
    index_line = f"- [{name}]({filename}) — {description}"
    index = MEMORY_INDEX.read_text()
    if filename not in index:
        lines = index.splitlines()
        insert_at = 1 if lines and lines[0].startswith("# ") else 0
        lines.insert(insert_at, index_line)
        MEMORY_INDEX.write_text("\n".join(lines) + "\n")
    return f"Memory: {filename}"


def intake_note_path() -> Path:
    INTAKE_DIR.mkdir(parents=True, exist_ok=True)
    return INTAKE_DIR / f"{dt.datetime.now(PT).strftime('%Y-%m-%d')}.md"


def append_intake_note(title: str, body: str) -> str:
    path = intake_note_path()
    if not path.exists():
        path.write_text(f"# Fake Matt Intake — {dt.datetime.now(PT).strftime('%Y-%m-%d')}\n")
    with path.open("a", encoding="utf-8") as f:
        f.write(f"\n## {title}\n\n{body.strip()}\n")
    return str(path)


def context_note_path() -> Path:
    out_dir = INTAKE_DIR / "context"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{dt.datetime.now(PT).strftime('%Y-%m-%d')}.md"


def write_context_note(action: dict[str, Any]) -> str:
    body = (action.get("body") or "").strip()
    if not body:
        return "Skipped empty context note"
    context_type = clean_cell(action.get("context_type") or "general").lower()
    if context_type not in {"project", "person", "company", "contact", "general"}:
        context_type = "general"
    target = clean_cell(action.get("target") or "")
    source = clean_cell(action.get("source_id") or "fakematt-operator")
    path = context_note_path()
    if path.exists():
        existing = path.read_text()
        if source in existing and body in existing:
            return f"Skipped duplicate context note: {path}"
    else:
        path.write_text(f"# Fake Matt Context Notes - {dt.datetime.now(PT).strftime('%Y-%m-%d')}\n")
    title_target = f": {target}" if target else ""
    with path.open("a", encoding="utf-8") as f:
        f.write(
            f"\n## {dt.datetime.now(PT).strftime('%H:%M')} - {context_type.title()}{title_target}\n\n"
            f"Source: `{source}`\n\n"
            f"{body}\n"
        )
    return f"Context note: {context_type}{title_target} -> {path}"


def apply_health_log(action: dict[str, Any]) -> str:
    raw = action.get("raw") or ""
    if not raw:
        return "Skipped empty health log"
    sys.path.insert(0, str(HOME / ".claude/fakematt-today"))
    try:
        import health_parser  # type: ignore
    except Exception as exc:
        path = append_intake_note("Deferred Health Log", f"Could not load health parser: {exc}\n\n```text\n{raw}\n```")
        return f"Deferred health log: {path}"
    acks: list[str] = []
    try:
        handled = health_parser.handle_message(raw, lambda text: acks.append(text))
    except Exception as exc:
        path = append_intake_note("Deferred Health Log", f"Health parser failed: {exc}\n\n```text\n{raw}\n```")
        return f"Deferred health log: {path}"
    if not handled:
        path = append_intake_note("Deferred Health Log", f"Unrecognized health log:\n\n```text\n{raw}\n```")
        return f"Deferred health log: {path}"
    return "Health log: " + ("; ".join(acks) if acks else "recorded")


def apply_reply_draft(action: dict[str, Any]) -> str:
    surface = (action.get("surface") or "").lower()
    queue_path = write_reply_queue_item(action, status="pending")
    if surface == "gmail":
        result = create_gmail_draft(action)
        write_reply_queue_item(action, status=reply_status_from_result(result), draft_result=result, queue_path=queue_path)
        return result
    if surface == "slack":
        result = create_slack_draft(action)
        write_reply_queue_item(action, status=reply_status_from_result(result), draft_result=result, queue_path=queue_path)
        return result
    path = append_intake_note("Deferred Reply Draft", f"Unsupported reply surface:\n\n```json\n{json.dumps(action, indent=2)}\n```")
    write_reply_queue_item(action, status="unsupported", draft_result=f"Deferred reply draft: {path}", queue_path=queue_path)
    return f"Deferred reply draft: {path}"


def reply_status_from_result(result: str) -> str:
    lower = result.lower()
    if lower.startswith("deferred"):
        return "deferred"
    if lower.startswith("skipped"):
        return "skipped"
    if "failed" in lower or "timed out" in lower:
        return "deferred"
    return "drafted"


def reply_queue_id(action: dict[str, Any]) -> str:
    source = action.get("source_id") or ""
    surface = action.get("surface") or "reply"
    recipient = action.get("recipient") or "unknown"
    basis = source or f"{surface}-{recipient}-{action.get('task') or ''}"
    return f"reply-{slugify(str(basis), limit=80)}"


def write_reply_queue_item(
    action: dict[str, Any],
    *,
    status: str,
    draft_result: str | None = None,
    queue_path: Path | None = None,
) -> Path:
    REPLY_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    item_id = reply_queue_id(action)
    path = queue_path or (REPLY_QUEUE_DIR / f"{item_id}.md")
    created = dt.datetime.now(PT).strftime("%Y-%m-%d")
    existing = path.read_text() if path.exists() else ""
    created_match = re.search(r"^created:\s*(.+)$", existing, re.M)
    if created_match:
        created = created_match.group(1).strip()
    surface = clean_cell(action.get("surface") or "unknown")
    recipient = clean_cell(action.get("recipient") or "")
    source = clean_cell(action.get("source_id") or "fakematt-operator")
    task = (action.get("task") or "").strip()
    artifact = draft_result or extract_reply_artifact(existing) or ""
    content = (
        "---\n"
        f"id: {item_id}\n"
        f"status: {status}\n"
        f"surface: {surface}\n"
        f"recipient: {yaml_string(recipient)}\n"
        f"source: {yaml_string(source)}\n"
        f"created: {created}\n"
        f"last_touched: {dt.datetime.now(PT).strftime('%Y-%m-%d')}\n"
        "---\n\n"
        f"# Reply Queue - {recipient or surface}\n\n"
        "## Task\n\n"
        f"{task or '(missing task)'}\n\n"
        "## Draft Artifact\n\n"
        f"{artifact or '(not generated yet)'}\n\n"
        "## Safety\n\n"
        "- Review before sending or posting.\n"
        "- Gmail draft sends require exact queue confirmation.\n"
        "- Slack posts require exact queue confirmation.\n"
    )
    path.write_text(content)
    return path


def extract_reply_artifact(text: str) -> str:
    match = re.search(r"^## Draft Artifact\s*\n+(.*?)(?:\n## |\Z)", text, re.S | re.M)
    if not match:
        return ""
    artifact = match.group(1).strip()
    return "" if artifact == "(not generated yet)" else artifact


def infer_idea_category(text: str, requested: str | None = None) -> str:
    if requested in IDEA_CATEGORIES:
        return requested
    lower = text.lower()
    if re.search(r"\b(fakematt|fake matt|slack|gmail|calendar|automation|script|skill|parser|intake|daemon|cron|launchagent|vault|workflow)\b", lower):
        return "zerg-tooling"
    if re.search(r"\b(blog|post|thread|newsletter|content|launch|case study|social|copy|essay)\b", lower):
        return "zerg-content"
    if re.search(r"\b(product|feature|app|saas|pricing|onboarding|dashboard|api|zergboard|zergmail|zergcal|zergwallet)\b", lower):
        return "zerg-product"
    if re.search(r"\b(research|study|paper|experiment|hypothesis|benchmark|eval|metric)\b", lower):
        return "research"
    if re.search(r"\b(travel|family|health|meal|workout|home|house|gift|hobby|personal)\b", lower):
        return "personal-life"
    if re.search(r"\b(buy|purchase|shopping|vendor|compare|comparison)\b", lower):
        return "shopping"
    return "personal-venture"


def idea_title(text: str) -> str:
    first = text.strip().splitlines()[0] if text.strip() else "Untitled idea"
    first = re.sub(r"^[#*\-\s]+", "", first)
    first = re.sub(r"\s+", " ", first).strip()
    return first[:96].strip(" .") or "Untitled idea"


def idea_tags(text: str, category: str) -> list[str]:
    lower = text.lower()
    candidates = [
        "fakematt",
        "intake",
        "automation",
        "slack",
        "gmail",
        "ideas",
        "parser",
        "memory",
        "tasks",
        "zergboard",
        "content",
        "research",
        "health",
        "personal",
        "product",
    ]
    tags = [tag for tag in candidates if tag in lower]
    if "fake matt" in lower and "fakematt" not in tags:
        tags.insert(0, "fakematt")
    tags.append(category)
    deduped: list[str] = []
    for tag in tags:
        clean = slugify(tag, limit=32)
        if clean and clean not in deduped:
            deduped.append(clean)
    return deduped[:8] or [category]


def yaml_string(value: str) -> str:
    return json.dumps(str(value))


def yaml_list(values: list[str]) -> str:
    if not values:
        return "[]"
    return "\n".join(f"- {yaml_string(value)}" for value in values)


def write_idea(action: dict[str, Any]) -> str:
    item = (action.get("item") or "").strip()
    if not item:
        return "Skipped empty idea"
    existing = IDEAS_DIR
    if existing.exists():
        lower_item = item.lower()
        for path in existing.rglob("*.md"):
            if "_archive" in path.parts:
                continue
            try:
                text = path.read_text(errors="ignore")
            except Exception:
                continue
            if lower_item and lower_item in text.lower():
                return f"Skipped duplicate idea: {path}"

    category = infer_idea_category(item, action.get("category"))
    title = idea_title(item)
    today = dt.datetime.now(PT).strftime("%Y-%m-%d")
    slug = slugify(title, limit=72)
    out_dir = IDEAS_DIR / "_inbox" / category
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{slug}.md"
    if out_path.exists():
        out_path = out_dir / f"{slug}-{dt.datetime.now(PT).strftime('%H%M%S')}.md"
    source = action.get("source_id") or "fakematt-operator"
    tags = idea_tags(item, category)
    content = (
        "---\n"
        f"id: idea-{today}-{slug}\n"
        f"title: {yaml_string(title)}\n"
        f"category: {category}\n"
        "subcategory: fakematt-intake\n"
        "tags:\n"
        f"{yaml_list(tags)}\n"
        "status: raw\n"
        "conviction: unknown\n"
        "effort: unknown\n"
        "time_estimate: unknown\n"
        "cost_estimate: unknown\n"
        f"created: {today}\n"
        f"last_touched: {today}\n"
        "sources:\n"
        f"- {yaml_string(source)}\n"
        "related: []\n"
        "task_link: null\n"
        "---\n\n"
        "## Idea\n"
        f"{item}\n\n"
        "## Why interesting\n"
        "Captured via Fake Matt intake. Needs triage before promotion.\n\n"
        "## Open questions\n"
        "- Is this worth promoting from raw capture?\n"
        "- What category, tags, and priority should it keep after triage?\n\n"
        "## Source excerpt\n"
        f"> {item.replace(chr(10), chr(10) + '> ')}\n"
    )
    out_path.write_text(content)
    return f"Idea: {out_path}"


def create_gmail_draft(action: dict[str, Any]) -> str:
    recipient = (action.get("recipient") or "").strip()
    task = (action.get("task") or "").strip()
    if not recipient or not task:
        path = append_intake_note("Deferred Gmail Draft", f"Missing recipient or task:\n\n```json\n{json.dumps(action, indent=2)}\n```")
        return f"Deferred Gmail draft: {path}"
    out_dir = INTAKE_DIR / "email-drafts"
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(FAKEMATT_EMAIL),
        "--to",
        recipient,
        "--task",
        task,
        "--out-dir",
        str(out_dir),
        "--create-draft",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    except subprocess.TimeoutExpired:
        path = append_intake_note("Deferred Gmail Draft", f"Timed out creating draft for `{recipient}`:\n\n```text\n{task}\n```")
        return f"Deferred Gmail draft: {path}"
    if result.returncode != 0:
        path = append_intake_note(
            "Deferred Gmail Draft",
            f"Draft command failed for `{recipient}`:\n\n```text\n{result.stderr[-2000:] or result.stdout[-2000:]}\n```\n\nTask:\n\n```text\n{task}\n```",
        )
        return f"Deferred Gmail draft: {path}"
    draft_id = None
    for line in result.stdout.splitlines():
        if line.startswith("[gmail draft]"):
            payload = parse_json_from_stdout(line)
            if payload:
                draft_id = payload.get("draft_id")
    return f"Gmail draft to {recipient}" + (f" ({draft_id})" if draft_id else "")


def create_slack_draft(action: dict[str, Any]) -> str:
    recipient = (action.get("recipient") or "").strip() or "Slack"
    task = (action.get("task") or "").strip()
    if not task:
        path = append_intake_note("Deferred Slack Draft", f"Missing Slack drafting task:\n\n```json\n{json.dumps(action, indent=2)}\n```")
        return f"Deferred Slack draft: {path}"
    draft = generate_slack_draft(recipient, task)
    slug = slugify(recipient)
    out_dir = INTAKE_DIR / "drafts"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"slack-{dt.datetime.now(PT).strftime('%Y%m%d-%H%M%S')}-{slug}.md"
    out_path.write_text(
        f"# Slack Draft — {recipient}\n\n"
        f"Source: `{action.get('source_id')}`\n\n"
        "## Draft\n\n"
        f"{draft.strip()}\n\n"
        "## Original Task\n\n"
        f"```text\n{task}\n```\n"
    )
    return f"Slack draft for {recipient}: {out_path}"


def generate_slack_draft(recipient: str, task: str) -> str:
    try:
        make_client = load_make_client()
        anchors = []
        if VOICE_UNIVERSALS.exists():
            anchors.append("# Voice universals\n\n" + VOICE_UNIVERSALS.read_text()[:6000])
        if SLACK_VOICE.exists():
            anchors.append("# Slack voice\n\n" + SLACK_VOICE.read_text()[:8000])
        system = (
            "Draft one Slack message in Matt's Slack voice. "
            "Return only the message text, no headings, no markdown fence. "
            "Never claim it was sent."
        )
        prompt = "\n\n---\n\n".join(anchors + [f"Recipient/surface: {recipient}\nTask: {task}"])
        client = make_client(source="fakematt-operator-slack-draft")
        msg = client.messages.create(
            model=routed_model("draft-prose"),
            max_tokens=700,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception:
        # Safe fallback: preserve Matt's exact requested content as the draft.
        return task.strip()


def apply_actions(actions: list[dict[str, Any]], *, safe_only: bool = False) -> list[str]:
    applied: list[str] = []
    deferred: list[str] = []
    for action in actions:
        if safe_only and not action.get("safe_apply"):
            if action.get("type") != "skip":
                deferred.append(json.dumps(action, indent=2))
            continue
        typ = action.get("type")
        if typ == "task":
            applied.append(append_task(action))
        elif typ == "reminder":
            applied.append(append_reminder(action))
        elif typ == "memory":
            applied.append(write_memory(action))
        elif typ == "health_log":
            applied.append(apply_health_log(action))
        elif typ == "reply_draft":
            applied.append(apply_reply_draft(action))
        elif typ == "idea":
            applied.append(write_idea(action))
        elif typ == "context_note":
            applied.append(write_context_note(action))
        elif typ == "skip":
            continue
        else:
            deferred.append(json.dumps(action, indent=2))
    if deferred:
        path = append_intake_note("Deferred Actions", "\n\n".join(f"```json\n{x}\n```" for x in deferred))
        applied.append(f"Deferred proposals: {path}")
    return applied


def receipt(result: dict[str, Any], packets: list[dict[str, Any]], applied: list[str] | None = None) -> str:
    """Compact per-run intake receipt — slack_voice.md longform shape.

    Hide-healthy: 0 packets collapses to silence (caller should skip posting).
    All-failed (rate-limit / classifier error): action-led headline names the
    root cause; no raw source_ids dumped to Slack.
    """
    from datetime import datetime as _dt

    actions = result.get("actions", [])
    summary = (result.get("summary") or "").strip()
    timestamp = _dt.now(PT).strftime("%-I:%M%p").lower()

    if not packets:
        return f"✅ *intake {timestamp} — no new packets*"

    # Detect classifier failures so we surface ONE root cause line instead of
    # one "skip — classification failed" per packet.
    skip_actions = [a for a in actions if a.get("type") == "skip"]
    skip_reasons = " ".join(str(a.get("reason") or "") for a in skip_actions).lower()
    classifier_failed = (
        "classification failed" in summary.lower()
        or "classification retry later" in summary.lower()
        or "rate_limit" in summary.lower()
        or "classification failed" in skip_reasons
        or "classification retry later" in skip_reasons
    )

    if classifier_failed:
        if "429" in summary or "rate_limit" in summary.lower():
            cause = "rate-limited (Anthropic 429)"
            hint = "retry after caps roll · `claude_account_router status`"
        else:
            cause = "classifier failed"
            hint = summary[:80] if summary else "no classifier output"
        headline = f"🚨 *intake {timestamp} — {len(packets)} packets blocked: {cause}*"
        rows: list[tuple[str, str, str]] = [
            (WARN, "classification", f"all {len(packets)} skipped, retry after caps roll"),
            (FYI, "hint", hint),
        ]
        applied_list = applied or []
        if applied_list:
            applied_counts = Counter(applied_item_type(item) for item in applied_list)
            applied_summary = " · ".join(f"{k} {v}" for k, v in applied_counts.most_common(3))
            rows.append((OK, "applied", applied_summary))
        return compose(headline, rows, close_line="", max_lines=15)

    # Normal path: count actions + applied by type, no per-item dumps.
    action_counts = Counter(a.get("type") or "unknown" for a in actions if a.get("type") != "skip")
    applied_counts = Counter(applied_item_type(item) for item in (applied or []))

    if not action_counts and not applied_counts:
        return f"✅ *intake {timestamp} — {len(packets)} packet(s), nothing to apply*"

    applied_total = sum(applied_counts.values())
    deferred_count = sum(1 for a in actions if a.get("type") == "deferred")
    skipped_count = len(skip_actions)
    head_bits: list[str] = []
    if applied_total:
        head_bits.append(f"{applied_total} applied")
    if deferred_count:
        head_bits.append(f"{deferred_count} deferred")
    if skipped_count:
        head_bits.append(f"{skipped_count} skipped")
    headline = f"📥 *intake {timestamp} — {len(packets)} packet(s) · {' · '.join(head_bits) or 'classified only'}*"

    rows = []
    for kind, n in applied_counts.most_common(4):
        rows.append((OK, kind, str(n)))
    for kind, n in action_counts.most_common(3):
        if kind not in applied_counts:
            rows.append((INFO, f"classified {kind}", str(n)))
    if deferred_count:
        rows.append((HOLD, "deferred", f"{deferred_count} · run `--review-deferred`"))

    for n in range(len(rows), -1, -1):
        try:
            return compose(headline, rows[:n], close_line="", max_lines=15)
        except ValueError:
            continue
    return compose(headline, [], close_line="", max_lines=15)


def post_to_slack(text: str) -> tuple[bool, str]:
    try:
        from slack_sdk import WebClient
    except ImportError:
        return False, "slack_sdk not installed"
    try:
        cfg = json.loads(SLACK_CONFIG.read_text())
        import sys as _zs, pathlib as _zp; _zs.path.insert(0, str(_zp.Path.home()/".config"/"zerg")); from slack_token import slack_token
        token = slack_token()
        WebClient(token=token).chat_postMessage(channel=FM_DM_CHANNEL, text=text, mrkdwn=True)
        return True, "posted"
    except Exception as exc:
        return False, str(exc)


def applied_item_type(item: str) -> str:
    lower = item.lower()
    if lower.startswith("## to do") or lower.startswith("## should do"):
        return "task"
    if lower.startswith("reminder:"):
        return "reminder"
    if lower.startswith("memory:"):
        return "memory"
    if lower.startswith("health log:"):
        return "health_log"
    if lower.startswith("gmail draft") or lower.startswith("slack draft"):
        return "reply_draft"
    if lower.startswith("idea:"):
        return "idea"
    if lower.startswith("context note:"):
        return "context_note"
    if lower.startswith("deferred"):
        return "deferred"
    if lower.startswith("skipped"):
        return "skipped"
    return "other"


RECEIPT_DEDUP_GAP = dt.timedelta(hours=4)
RECEIPT_DEDUP_STATE = HOME / ".config" / "zerg" / "fakematt-intake" / "last_receipt.json"


def _receipt_signature(
    *,
    packets: list[dict[str, Any]],
    result: dict[str, Any],
    applied: list[str] | None,
    errors: list[dict[str, str]],
) -> str:
    """Stable shape-fingerprint for receipt dedup. Identical state in two
    consecutive runs collapses to one Slack post per dedup gap.

    Error-only states (rate_limit, classifier_error with 0 applied) collapse
    to a constant signature regardless of packet count — pre-2026-05-12 the
    5/11 rate-limit storm produced 17 essentially-identical DMs because
    packets=1/2/7 interleaved as new packets arrived during the cap window,
    each generating a fresh signature and bypassing the 4h gap. Matt
    👎-reacted to 3 of them before the storm ended. The fix: when the run
    is dominated by the same error class with no progress, drop the
    packets/errors counts from the signature. Real progress (any applied)
    or a different error class still produces a distinct signature and
    posts immediately.
    """
    summary = (result.get("summary") or "").lower()
    error_class = ""
    if "rate_limit" in summary or "429" in summary:
        error_class = "rate_limit"
    elif errors:
        error_class = "classifier_error"
    elif "classification failed" in summary:
        error_class = "classifier_error"
    applied_count = len(applied or [])
    if error_class and applied_count == 0:
        # Error-dominant state — collapse N→1 across interleaved retries.
        return f"err_only|err_class={error_class}"
    return "|".join([
        f"packets={len(packets)}",
        f"applied={applied_count}",
        f"errors={len(errors)}",
        f"err_class={error_class}",
    ])


def _load_last_receipt_post() -> dict[str, Any]:
    try:
        return json.loads(RECEIPT_DEDUP_STATE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _save_last_receipt_post(signature: str) -> None:
    RECEIPT_DEDUP_STATE.parent.mkdir(parents=True, exist_ok=True)
    payload = {"signature": signature, "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    try:
        RECEIPT_DEDUP_STATE.write_text(json.dumps(payload))
    except OSError:
        pass


def should_post_receipt(
    *,
    args: argparse.Namespace,
    packets: list[dict[str, Any]],
    result: dict[str, Any],
    applied: list[str] | None,
    errors: list[dict[str, str]],
) -> bool:
    if not args.post:
        return False
    if not packets:
        return bool(args.post_empty)
    decision = False
    if errors or result.get("_retry_later"):
        decision = True
    applied_items = applied or []
    meaningful_applied = [
        item
        for item in applied_items
        if applied_item_type(item) not in {"skipped", "other"} and not item.lower().startswith("skipped")
    ]
    if meaningful_applied:
        decision = True
    actions = result.get("actions", [])
    if planned_deferred_count(actions, "apply_safe" if args.apply_safe else "preview") > 0:
        decision = True
    if not decision:
        return False

    # Dedup: skip when the run signature matches the last post within
    # RECEIPT_DEDUP_GAP (avoids spamming Matt every 15 min with the same
    # "1 packet blocked: rate-limited" message). Real progress / recovery /
    # state change always re-posts.
    signature = _receipt_signature(packets=packets, result=result, applied=applied, errors=errors)
    last = _load_last_receipt_post()
    if last.get("signature") == signature:
        try:
            last_at = dt.datetime.fromisoformat(last.get("at", ""))
            if last_at.tzinfo is None:
                last_at = last_at.replace(tzinfo=dt.timezone.utc)
            if (dt.datetime.now(dt.timezone.utc) - last_at) < RECEIPT_DEDUP_GAP:
                return False
        except ValueError:
            pass
    _save_last_receipt_post(signature)
    return True


def source_counter(packets: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(packet.get("source") or "unknown" for packet in packets))


def action_counter(actions: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(action.get("type") or "unknown" for action in actions))


def planned_deferred_count(actions: list[dict[str, Any]], mode: str) -> int:
    if mode == "preview":
        return sum(1 for action in actions if action.get("type") != "skip")
    if mode == "apply_safe":
        return sum(1 for action in actions if action.get("type") != "skip" and not action.get("safe_apply"))
    return sum(1 for action in actions if action.get("type") in {"idea"} or not action.get("type"))


def action_display(action: dict[str, Any]) -> str:
    value = (
        action.get("item")
        or action.get("name")
        or action.get("task")
        or action.get("body")
        or action.get("raw")
        or action.get("reason")
        or ""
    )
    return re.sub(r"\s+", " ", str(value)).strip()[:180]


def action_route(action: dict[str, Any]) -> str:
    parts = [action.get("type") or "unknown"]
    for key in ["bucket", "surface", "category", "context_type", "memory_type", "reminder_type", "domain"]:
        if action.get(key):
            parts.append(str(action[key]))
    return "/".join(parts)


def action_summary(action: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": action.get("type") or "unknown",
        "route": action_route(action),
        "label": action_display(action),
        "source_id": action.get("source_id"),
        "safe_apply": bool(action.get("safe_apply")),
        "reason": action.get("reason"),
    }


def deferred_action_summaries(actions: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    if mode == "preview":
        return [action_summary(action) for action in actions if action.get("type") != "skip"]
    if mode == "apply_safe":
        return [
            action_summary(action)
            for action in actions
            if action.get("type") != "skip" and not action.get("safe_apply")
        ]
    return [
        action_summary(action)
        for action in actions
        if action.get("type") in {"idea"} or not action.get("type")
    ]


def build_run_event(
    *,
    mode: str,
    args: argparse.Namespace,
    packets: list[dict[str, Any]],
    result: dict[str, Any],
    applied: list[str] | None,
    errors: list[dict[str, str]],
    post_status: dict[str, Any] | None,
) -> dict[str, Any]:
    actions = result.get("actions", [])
    applied_items = applied or []
    applied_types = Counter(applied_item_type(item) for item in applied_items)
    skipped_actions = [action for action in actions if action.get("type") == "skip"]
    deferred_actions = deferred_action_summaries(actions, mode)
    return {
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "timestamp_pt": now_stamp(),
        "mode": mode,
        "flags": {
            "apply": args.apply,
            "apply_safe": args.apply_safe,
            "no_llm": args.no_llm,
            "mark_seen": args.mark_seen,
            "post": args.post,
        },
        "packets_total": len(packets),
        "sources": source_counter(packets),
        "packet_ids": [packet.get("source_id") for packet in packets],
        "summary": result.get("summary") or "",
        "actions_total": len(actions),
        "actions": action_counter(actions),
        "applied_count": sum(count for typ, count in applied_types.items() if typ not in {"deferred", "skipped"}),
        "applied_types": dict(applied_types),
        "applied": applied_items,
        "deferred_count": len(deferred_actions),
        "deferred_actions": deferred_actions,
        "skipped_count": len(skipped_actions) + applied_types.get("skipped", 0),
        "skipped_actions": [action_summary(action) for action in skipped_actions],
        "skip_reasons": [action.get("reason") for action in skipped_actions if action.get("reason")],
        "errors_count": len(errors),
        "errors": errors,
        "post_status": post_status,
    }


def format_counter(counter: Counter[str]) -> list[str]:
    if not counter:
        return ["- none"]
    return [f"- {key}: {value}" for key, value in counter.most_common()]


def build_report(days: int) -> str:
    events = read_events(days)
    non_empty = [event for event in events if event.get("packets_total", 0) > 0]
    sources: Counter[str] = Counter()
    actions: Counter[str] = Counter()
    applied: Counter[str] = Counter()
    skip_reasons: Counter[str] = Counter()
    errors: list[str] = []
    deferred_count = 0
    skipped_count = 0
    packets_total = 0
    for event in events:
        packets_total += int(event.get("packets_total") or 0)
        sources.update(event.get("sources") or {})
        actions.update(event.get("actions") or {})
        applied.update(event.get("applied_types") or {})
        skip_reasons.update(reason for reason in event.get("skip_reasons", []) if reason)
        deferred_count += int(event.get("deferred_count") or 0)
        skipped_count += int(event.get("skipped_count") or 0)
        for error in event.get("errors", []):
            if isinstance(error, dict):
                errors.append(f"{error.get('stage', 'unknown')}: {error.get('error', '')}")
            else:
                errors.append(str(error))

    applied_clean = Counter({k: v for k, v in applied.items() if k not in {"deferred", "skipped"} and v})

    # Hide-healthy: when nothing happened, collapse the whole report to one line.
    if packets_total == 0 and not errors and deferred_count == 0 and skipped_count == 0:
        return f"✅ *intake — last {days}d quiet* · {len(events)} runs · 0 packets · 0 errors"

    headline_bits: list[str] = [f"{packets_total} packet{'s' if packets_total != 1 else ''}"]
    if errors:
        headline_bits.append(f"{len(errors)} error{'s' if len(errors) != 1 else ''}")
    if deferred_count:
        headline_bits.append(f"{deferred_count} deferred")
    headline = f"📥 *intake — last {days}d · {' · '.join(headline_bits)}*"

    rows: list[tuple[str, str, str]] = []
    for kind, n in applied_clean.most_common(3):
        rows.append((OK, f"applied {kind}", str(n)))
    classified_pending = Counter({k: v for k, v in actions.items() if k not in applied})
    for kind, n in classified_pending.most_common(2):
        rows.append((INFO, f"classified {kind}", str(n)))
    if errors:
        rows.append((WARN, "last error", errors[-1][:60]))
    if deferred_count or skipped_count:
        rows.append((HOLD, "deferred / skipped", f"{deferred_count} / {skipped_count}"))
    if sources:
        top_sources = " · ".join(f"{s} {c}" for s, c in sources.most_common(3))
        rows.append((FYI, "sources", top_sources))

    close_bits: list[str] = []
    if deferred_count:
        close_bits.append(f"run `--review-deferred` ({deferred_count})")
    if skip_reasons:
        reason, _ = skip_reasons.most_common(1)[0]
        close_bits.append(f"parser gap: {reason[:50]}")
    close_line = " · ".join(close_bits)

    for n in range(len(rows), -1, -1):
        try:
            return compose(headline, rows[:n], close_line=close_line, max_lines=15)
        except ValueError:
            continue
    return compose(headline, [], close_line="", max_lines=15)


def normalize_pattern_label(value: str) -> str:
    value = value.lower()
    value = re.sub(r"https?://\S+", "<url>", value)
    value = re.sub(r"[\w.+-]+@[\w.-]+\.\w+", "<email>", value)
    value = re.sub(r"\b\d{1,2}:\d{2}\b", "<time>", value)
    value = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "<date>", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()[:90] or "unspecified"


def candidate_for_deferred(route: str, count: int, sample: str) -> str:
    typ = route.split("/", 1)[0]
    if typ == "idea":
        return "Decide whether `idea:` should auto-route to a durable ideas file instead of deferred notes."
    if typ == "reply_draft":
        return "Add a stricter target parser for repeated reply requests, then keep send/post gated."
    if typ == "reminder":
        return "Add a date/condition parser for this reminder wording if it repeats."
    if typ == "task":
        return "Promote this wording to an explicit task parser only if Matt uses it repeatedly."
    if typ == "memory":
        return "Add a memory parser only for durable preference/correction wording, not transcript dumps."
    if count > 1:
        return f"Add a deterministic parser for repeated `{route}` packets like `{sample[:80]}`."
    return f"Watch `{route}` for repeats before adding code."


def build_deferred_review(days: int, *, write_note: bool = False) -> tuple[str, Path | None]:
    events = read_events(days)
    deferred_patterns: Counter[tuple[str, str]] = Counter()
    deferred_samples: dict[tuple[str, str], dict[str, Any]] = {}
    skip_patterns: Counter[str] = Counter()
    skip_samples: dict[str, dict[str, Any]] = {}
    errors: Counter[str] = Counter()

    for event in events:
        for action in event.get("deferred_actions", []):
            if not isinstance(action, dict):
                continue
            route = action.get("route") or action.get("type") or "unknown"
            label = normalize_pattern_label(action.get("label") or "")
            key = (route, label)
            deferred_patterns[key] += 1
            deferred_samples.setdefault(key, action)
        for action in event.get("skipped_actions", []):
            if not isinstance(action, dict):
                continue
            reason = action.get("reason") or action.get("label") or "unknown skip"
            skip_patterns[reason] += 1
            skip_samples.setdefault(reason, action)
        for error in event.get("errors", []):
            if isinstance(error, dict):
                errors[f"{error.get('stage', 'unknown')}: {error.get('error', '')[:120]}"] += 1
            else:
                errors[str(error)[:120]] += 1

    lines = [f"*Fake Matt deferred review - last {days}d*", ""]
    lines += ["*Totals*", f"- runs: {len(events)}", f"- deferred classes: {len(deferred_patterns)}", f"- skip reasons: {len(skip_patterns)}"]
    lines += ["", "*Top Deferred Classes*"]
    if deferred_patterns:
        for (route, label), count in deferred_patterns.most_common(8):
            sample = deferred_samples[(route, label)]
            source = sample.get("source_id") or "unknown source"
            lines.append(f"- {route}: {count} - {label} (sample: {source})")
    else:
        lines.append("- none")
    lines += ["", "*Top Skips*"]
    if skip_patterns:
        for reason, count in skip_patterns.most_common(8):
            source = skip_samples.get(reason, {}).get("source_id") or "unknown source"
            lines.append(f"- {reason}: {count} (sample: {source})")
    else:
        lines.append("- none")
    lines += ["", "*Parser Candidates*"]
    candidates: list[str] = []
    for (route, label), count in deferred_patterns.most_common(5):
        if count > 1 or route.split("/", 1)[0] in {"idea", "reply_draft", "reminder"}:
            candidates.append(candidate_for_deferred(route, count, label))
    if skip_patterns:
        reason, count = skip_patterns.most_common(1)[0]
        if count > 1:
            candidates.append(f"Investigate repeated skip reason `{reason}` and either narrow Gmail/Slack intake filters or add an explicit command form.")
    if errors:
        candidates.append("Fix recurring bridge/runtime errors before adding new intake surfaces.")
    if candidates:
        for candidate in dict.fromkeys(candidates):
            lines.append(f"- {candidate}")
    else:
        lines.append("- none yet; keep collecting ledger data.")
    lines += ["", "*Errors*"]
    if errors:
        for error, count in errors.most_common(5):
            lines.append(f"- {error}: {count}")
    else:
        lines.append("- none")
    lines += ["", f"Ledger: `{EVENTS_PATH}`"]

    note_path = None
    text = "\n".join(lines)
    if write_note:
        out_dir = INTAKE_DIR / "reviews"
        out_dir.mkdir(parents=True, exist_ok=True)
        note_path = out_dir / f"deferred-review-{dt.datetime.now(PT).strftime('%Y-%m-%d')}.md"
        note_path.write_text(text + "\n")
    return text, note_path


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}
    meta: dict[str, str] = {}
    for raw in text[4:end].splitlines():
        if ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        meta[key.strip()] = value.strip().strip("\"'")
    return meta


def extract_section(text: str, heading: str) -> str:
    pattern = rf"^## {re.escape(heading)}\s*\n+(.*?)(?:\n## |\Z)"
    match = re.search(pattern, text, re.S | re.M)
    return match.group(1).strip() if match else ""


def read_reply_queue_items(days: int) -> list[dict[str, Any]]:
    if not REPLY_QUEUE_DIR.exists():
        return []
    cutoff = dt.datetime.now(PT).date() - dt.timedelta(days=days)
    items: list[dict[str, Any]] = []
    for path in sorted(REPLY_QUEUE_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        text = path.read_text(errors="ignore")
        meta = parse_frontmatter(text)
        created_raw = meta.get("created") or ""
        try:
            created_date = dt.date.fromisoformat(created_raw[:10])
        except ValueError:
            created_date = dt.datetime.fromtimestamp(path.stat().st_mtime, PT).date()
        if created_date < cutoff:
            continue
        task = extract_section(text, "Task")
        artifact = extract_section(text, "Draft Artifact")
        if artifact == "(not generated yet)":
            artifact = ""
        items.append(
            {
                "path": path,
                "id": meta.get("id") or path.stem,
                "status": meta.get("status") or "unknown",
                "surface": meta.get("surface") or "unknown",
                "recipient": meta.get("recipient") or "",
                "source": meta.get("source") or "",
                "created": created_raw,
                "task": task,
                "artifact": artifact,
            }
        )
    return items


def read_reply_queue_item(queue_id: str) -> dict[str, Any] | None:
    if not REPLY_QUEUE_DIR.exists():
        return None
    wanted = queue_id.strip()
    for path in sorted(REPLY_QUEUE_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        text = path.read_text(errors="ignore")
        meta = parse_frontmatter(text)
        item_id = meta.get("id") or path.stem
        if wanted not in {item_id, path.stem}:
            continue
        artifact = extract_section(text, "Draft Artifact")
        if artifact == "(not generated yet)":
            artifact = ""
        return {
            "path": path,
            "id": item_id,
            "status": meta.get("status") or "unknown",
            "surface": meta.get("surface") or "unknown",
            "recipient": meta.get("recipient") or "",
            "source": meta.get("source") or "",
            "created": meta.get("created") or "",
            "task": extract_section(text, "Task"),
            "artifact": artifact,
        }
    return None


def build_reply_review(days: int, *, write_note: bool = False) -> tuple[str, Path | None]:
    items = read_reply_queue_items(days)
    status_counts = Counter(item["status"] for item in items)
    surface_counts = Counter(item["surface"] for item in items)
    pending = [item for item in items if item["status"] not in {"drafted", "sent", "posted", "closed"}]
    drafted = [item for item in items if item["status"] == "drafted"]

    lines = [f"*Fake Matt reply review - last {days}d*", ""]
    lines += ["*Totals*", f"- queue items: {len(items)}", f"- pending review: {len(pending)}", f"- drafted: {len(drafted)}"]
    lines += ["", "*By Status*"]
    lines.extend(format_counter(status_counts))
    lines += ["", "*By Surface*"]
    lines.extend(format_counter(surface_counts))
    lines += ["", "*Queue*"]
    if items:
        for item in items[:15]:
            task = re.sub(r"\s+", " ", item["task"]).strip()[:140] or "(missing task)"
            recipient = item["recipient"] or "(unknown recipient)"
            rel = item["path"]
            try:
                rel = item["path"].relative_to(ZERG_ROOT)
            except ValueError:
                pass
            artifact = item["artifact"]
            lines.append(f"- {item['status']} / {item['surface']} / {recipient}: {task}")
            lines.append(f"  queue: `{rel}`")
            if artifact:
                lines.append(f"  draft: {artifact[:180]}")
    else:
        lines.append("- none")
    lines += ["", "*Next Actions*"]
    if pending:
        lines.append("- Generate or review drafts for pending queue items; keep Slack/Gmail sends gated.")
    if drafted:
        lines.append("- Review drafted items in Gmail or the Slack draft artifacts before any send/post.")
    if not items:
        lines.append("- none; no reply requests have entered the queue yet.")
    lines.append("- Send/post commands require exact per-item confirmation.")
    lines += ["", f"Reply queue: `{REPLY_QUEUE_DIR}`"]

    text = "\n".join(lines)
    note_path = None
    if write_note:
        out_dir = INTAKE_DIR / "reviews"
        out_dir.mkdir(parents=True, exist_ok=True)
        note_path = out_dir / f"reply-review-{dt.datetime.now(PT).strftime('%Y-%m-%d')}.md"
        note_path.write_text(text + "\n")
    return text, note_path


def reply_action_from_queue_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "reply_draft",
        "surface": item.get("surface") or "unknown",
        "recipient": item.get("recipient") or "",
        "task": item.get("task") or "",
        "source_id": item.get("source") or item.get("id") or "fakematt-reply-queue",
        "safe_apply": True,
    }


def generate_reply_drafts(
    days: int,
    *,
    limit: int = 5,
    surface: str = "all",
) -> str:
    items = read_reply_queue_items(days)
    candidates = [
        item
        for item in items
        if item["status"] == "pending"
        and item.get("task")
        and (surface == "all" or item["surface"] == surface)
    ]
    selected = candidates[: max(0, limit)]
    rows: list[str] = []
    generated = 0
    deferred = 0
    unsupported = 0

    for item in selected:
        action = reply_action_from_queue_item(item)
        item_surface = (action.get("surface") or "").lower()
        if item_surface == "gmail":
            result = create_gmail_draft(action)
            status = reply_status_from_result(result)
        elif item_surface == "slack":
            result = create_slack_draft(action)
            status = reply_status_from_result(result)
        else:
            result = f"Unsupported reply surface: {item_surface or 'unknown'}"
            status = "unsupported"

        write_reply_queue_item(action, status=status, draft_result=result, queue_path=item["path"])
        if status == "drafted":
            generated += 1
        elif status == "unsupported":
            unsupported += 1
        else:
            deferred += 1
        recipient = action.get("recipient") or "(unknown recipient)"
        rows.append(f"- {status} / {item_surface or 'unknown'} / {recipient}: {result[:180]}")

    skipped = len(candidates) - len(selected)
    lines = [
        f"*Fake Matt reply draft generation - last {days}d*",
        "",
        "*Totals*",
        f"- candidates: {len(candidates)}",
        f"- processed: {len(selected)}",
        f"- drafted: {generated}",
        f"- deferred: {deferred}",
        f"- unsupported: {unsupported}",
    ]
    if skipped > 0:
        lines.append(f"- skipped by limit: {skipped}")
    lines += ["", "*Results*"]
    lines.extend(rows or ["- none"])
    lines += [
        "",
        "*Safety*",
        "- No email was sent.",
        "- No Slack message was posted.",
        "- Review Gmail drafts or Slack draft artifacts before any send/post.",
        "- Send/post commands require exact per-item confirmation.",
        "",
        f"Reply queue: `{REPLY_QUEUE_DIR}`",
    ]
    return "\n".join(lines)


def extract_gmail_draft_id(artifact: str) -> str:
    patterns = [
        r"\(([A-Za-z0-9_-]{8,})\)",
        r"draft_id['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9_-]{8,})",
    ]
    for pattern in patterns:
        match = re.search(pattern, artifact)
        if match:
            return match.group(1)
    return ""


def send_gmail_queue_draft(
    queue_id: str,
    *,
    confirm: str,
    dry_run: bool = False,
    account: str | None = None,
) -> tuple[str, int]:
    item = read_reply_queue_item(queue_id)
    if not item:
        return f"Refused: reply queue item not found: `{queue_id}`", 1
    item_id = item["id"]
    required = f"SEND {item_id}"
    if item["surface"] != "gmail":
        return f"Refused: `{item_id}` is a `{item['surface']}` item, not gmail.", 1
    if item["status"] != "drafted":
        return f"Refused: `{item_id}` status is `{item['status']}`, not `drafted`.", 1
    draft_id = extract_gmail_draft_id(item.get("artifact") or "")
    if not draft_id:
        return f"Refused: `{item_id}` has no Gmail draft id in its artifact.", 1

    preview = "\n".join(
        [
            f"*Gmail draft send gate*",
            "",
            f"- queue: `{item_id}`",
            f"- recipient: `{item.get('recipient') or '(unknown)'}`",
            f"- draft_id: `{draft_id}`",
            f"- source: `{item.get('source') or '(unknown)'}`",
            "",
            f"Required confirmation: `{required}`",
        ]
    )
    if dry_run:
        return preview + "\n\nDry run only. No email sent.", 0
    if confirm != required:
        return preview + "\n\nRefused: confirmation phrase did not match. No email sent.", 1

    try:
        spec = importlib.util.spec_from_file_location("gmail_skill", GMAIL)
        if not spec or not spec.loader:
            raise RuntimeError("could not load gmail_skill")
        gmail_skill = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gmail_skill)
        service = gmail_skill.get_gmail_service(account)
        result = service.users().drafts().send(userId="me", body={"id": draft_id}).execute()
    except Exception as exc:
        return f"Failed to send Gmail draft for `{item_id}`: {short_error(exc)}", 1

    action = reply_action_from_queue_item(item)
    write_reply_queue_item(
        action,
        status="sent",
        draft_result=f"Sent Gmail draft {draft_id}; message_id={result.get('id')}; thread_id={result.get('threadId')}",
        queue_path=item["path"],
    )
    return (
        f"Sent Gmail draft for `{item_id}`.\n"
        f"message_id: `{result.get('id')}`\n"
        f"thread_id: `{result.get('threadId')}`"
    ), 0


def extract_slack_draft_path(artifact: str) -> Path | None:
    match = re.search(r":\s*(/.+?\.md)\s*$", artifact.strip())
    if not match:
        return None
    return Path(match.group(1)).expanduser()


def read_slack_draft_body(path: Path) -> str:
    text = path.read_text(errors="ignore")
    return extract_section(text, "Draft").strip()


def post_slack_queue_draft(
    queue_id: str,
    *,
    confirm: str,
    dry_run: bool = False,
    workspace: str | None = None,
) -> tuple[str, int]:
    item = read_reply_queue_item(queue_id)
    if not item:
        return f"Refused: reply queue item not found: `{queue_id}`", 1
    item_id = item["id"]
    required = f"POST {item_id}"
    if item["surface"] != "slack":
        return f"Refused: `{item_id}` is a `{item['surface']}` item, not slack.", 1
    if item["status"] != "drafted":
        return f"Refused: `{item_id}` status is `{item['status']}`, not `drafted`.", 1
    draft_path = extract_slack_draft_path(item.get("artifact") or "")
    if not draft_path or not draft_path.exists():
        return f"Refused: `{item_id}` has no readable Slack draft artifact.", 1
    message = read_slack_draft_body(draft_path)
    if not message:
        return f"Refused: `{item_id}` Slack draft artifact has no draft body.", 1
    recipient = item.get("recipient") or ""
    if not recipient:
        return f"Refused: `{item_id}` has no Slack recipient.", 1

    preview = "\n".join(
        [
            "*Slack draft post gate*",
            "",
            f"- queue: `{item_id}`",
            f"- recipient: `{recipient}`",
            f"- draft: `{draft_path}`",
            f"- source: `{item.get('source') or '(unknown)'}`",
            "",
            "Message:",
            "```text",
            message,
            "```",
            "",
            f"Required confirmation: `{required}`",
        ]
    )
    if dry_run:
        return preview + "\n\nDry run only. No Slack message posted.", 0
    if confirm != required:
        return preview + "\n\nRefused: confirmation phrase did not match. No Slack message posted.", 1

    python_bin = str(SLACK_PYTHON if SLACK_PYTHON.exists() else Path(sys.executable))
    cmd = [python_bin, str(SLACK_SKILL), "send", recipient, "-m", message]
    if workspace:
        cmd += ["--workspace", workspace]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return f"Failed to post Slack draft for `{item_id}`: timed out", 1
    if result.returncode != 0:
        return f"Failed to post Slack draft for `{item_id}`:\n```text\n{(result.stderr or result.stdout)[-2000:]}\n```", 1

    action = reply_action_from_queue_item(item)
    write_reply_queue_item(
        action,
        status="posted",
        draft_result=f"Posted Slack draft to {recipient}: {(result.stdout or '').strip()[:300]}",
        queue_path=item["path"],
    )
    return f"Posted Slack draft for `{item_id}` to `{recipient}`.", 0


def read_context_entries(days: int) -> list[dict[str, Any]]:
    context_dir = INTAKE_DIR / "context"
    if not context_dir.exists():
        return []
    cutoff = dt.datetime.now(PT).date() - dt.timedelta(days=days)
    entries: list[dict[str, Any]] = []
    for path in sorted(context_dir.glob("*.md")):
        try:
            file_date = dt.date.fromisoformat(path.stem)
        except ValueError:
            continue
        if file_date < cutoff:
            continue
        current: dict[str, Any] | None = None
        body: list[str] = []
        for raw in path.read_text().splitlines():
            heading = re.match(r"^##\s+(\d{2}:\d{2})\s+-\s+([^:]+?)(?::\s*(.+))?\s*$", raw)
            if heading:
                if current is not None:
                    current["body"] = "\n".join(body).strip()
                    entries.append(current)
                current = {
                    "date": file_date.isoformat(),
                    "time": heading.group(1),
                    "context_type": heading.group(2).strip().lower(),
                    "target": (heading.group(3) or "").strip(),
                    "source": "",
                    "path": str(path),
                }
                body = []
                continue
            if current is None:
                continue
            source = re.match(r"^Source:\s+`([^`]+)`\s*$", raw)
            if source:
                current["source"] = source.group(1)
                continue
            if raw.strip() or body:
                body.append(raw)
        if current is not None:
            current["body"] = "\n".join(body).strip()
            entries.append(current)
    return entries


def context_destination(context_type: str) -> str:
    if context_type in {"person", "contact"}:
        return "People/"
    if context_type == "company":
        return "Companies/ or Firms/"
    if context_type == "project":
        return "project source-of-truth note"
    return "manual triage"


def build_context_review(days: int, *, write_note: bool = False) -> tuple[str, Path | None]:
    entries = read_context_entries(days)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for entry in entries:
        key = (entry.get("context_type") or "general", entry.get("target") or "untargeted")
        grouped.setdefault(key, []).append(entry)

    type_counts = Counter(entry.get("context_type") or "general" for entry in entries)
    lines = [f"*Fake Matt context review - last {days}d*", ""]
    lines += ["*Totals*", f"- entries: {len(entries)}", f"- targets: {len(grouped)}"]
    lines += ["", "*By Type*"]
    lines.extend(format_counter(type_counts))
    lines += ["", "*Reconciliation Candidates*"]
    if grouped:
        sorted_groups = sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0][0], item[0][1].lower()))
        for (context_type, target), rows in sorted_groups[:12]:
            destination = context_destination(context_type)
            label = f"{context_type}: {target}" if target != "untargeted" else context_type
            lines.append(f"- {label}: {len(rows)} -> {destination}")
            for row in rows[:2]:
                body = re.sub(r"\s+", " ", row.get("body") or "").strip()
                source = row.get("source") or "unknown source"
                lines.append(f"  source `{source}`: {body[:160]}")
    else:
        lines.append("- none")
    lines += ["", "*Suggested Actions*"]
    if grouped:
        has_people = any(key[0] in {"person", "contact"} for key in grouped)
        has_companies = any(key[0] == "company" for key in grouped)
        has_projects = any(key[0] == "project" for key in grouped)
        if has_people:
            lines.append("- Reconcile contact/person entries into matching `People/` notes after checking for existing files.")
        if has_companies:
            lines.append("- Reconcile company entries into `Companies/` or `Firms/` with source links.")
        if has_projects:
            lines.append("- Reconcile project entries into the relevant project source-of-truth pages.")
        if not any([has_people, has_companies, has_projects]):
            lines.append("- Review general context entries and either promote them to memory/project notes or leave them as session context.")
    else:
        lines.append("- none; no context notes collected yet.")
    lines += ["", f"Context inbox: `{INTAKE_DIR / 'context'}`"]

    text = "\n".join(lines)
    note_path = None
    if write_note:
        out_dir = INTAKE_DIR / "context" / "reviews"
        out_dir.mkdir(parents=True, exist_ok=True)
        note_path = out_dir / f"context-review-{dt.datetime.now(PT).strftime('%Y-%m-%d')}.md"
        note_path.write_text(text + "\n")
    return text, note_path


def context_candidate_roots(context_type: str) -> list[Path]:
    if context_type in {"person", "contact"}:
        return [ZERG_ROOT / "MattZerg/People", ZERG_ROOT / "MHE/People"]
    if context_type == "company":
        return [ZERG_ROOT / "MattZerg/Companies", ZERG_ROOT / "MattZerg/Firms"]
    if context_type == "project":
        return [ZERG_ROOT / "MattZerg/Projects"]
    return []


def find_context_target_files(context_type: str, target: str, limit: int = 5) -> list[Path]:
    if not target:
        return []
    target_slug = slugify(target)
    target_words = {word for word in re.split(r"[^a-z0-9]+", target.lower()) if len(word) > 1}
    candidates: list[tuple[int, Path]] = []
    for root in context_candidate_roots(context_type):
        if not root.exists():
            continue
        for path in root.rglob("*.md"):
            stem_slug = slugify(path.stem)
            score = 0
            if stem_slug == target_slug:
                score += 100
            elif target_slug and (target_slug in stem_slug or stem_slug in target_slug):
                score += 50
            path_text = str(path.relative_to(ZERG_ROOT)).lower()
            score += sum(5 for word in target_words if word in path_text)
            if score:
                candidates.append((score, path))
    candidates.sort(key=lambda item: (-item[0], len(str(item[1]))))
    return [path for _score, path in candidates[:limit]]


def proposed_context_append(context_type: str, target: str, rows: list[dict[str, Any]]) -> str:
    today = dt.datetime.now(PT).strftime("%Y-%m-%d")
    heading_target = f" - {target}" if target and target != "untargeted" else ""
    lines = [f"## Fake Matt context intake{heading_target} - {today}", ""]
    for row in rows:
        body = (row.get("body") or "").strip()
        source = row.get("source") or "unknown source"
        stamp = f"{row.get('date', '')} {row.get('time', '')}".strip()
        lines.append(f"- {body} (source: `{source}`; captured: {stamp})")
    lines.append("")
    return "\n".join(lines)


def build_context_reconciliation_stage(days: int, *, write_stage: bool = False) -> tuple[str, Path | None]:
    entries = read_context_entries(days)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for entry in entries:
        key = (entry.get("context_type") or "general", entry.get("target") or "untargeted")
        grouped.setdefault(key, []).append(entry)

    lines = [f"# Fake Matt Context Reconciliation Stage - last {days}d", ""]
    lines += [
        "This is a staging file only. It proposes exact append blocks for review; it does not edit People, Companies, Firms, or Projects.",
        "",
        f"Entries: {len(entries)}",
        f"Targets: {len(grouped)}",
        "",
    ]
    if not grouped:
        lines.append("No context entries to stage.")
    for (context_type, target), rows in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1].lower())):
        label = f"{context_type}: {target}" if target != "untargeted" else context_type
        candidates = find_context_target_files(context_type, "" if target == "untargeted" else target)
        lines += [f"## {label}", "", f"Destination type: {context_destination(context_type)}"]
        if candidates:
            lines.append("Candidate files:")
            for path in candidates:
                lines.append(f"- `{path.relative_to(ZERG_ROOT)}`")
        else:
            lines.append("Candidate files: none found; create or choose target manually.")
        lines += ["", "Proposed append:", "", "```markdown"]
        lines.append(proposed_context_append(context_type, target, rows).rstrip())
        lines += ["```", ""]

    text = "\n".join(lines).rstrip() + "\n"
    stage_path = None
    if write_stage:
        out_dir = INTAKE_DIR / "context" / "reconciliations"
        out_dir.mkdir(parents=True, exist_ok=True)
        stage_path = out_dir / f"context-reconciliation-stage-{dt.datetime.now(PT).strftime('%Y-%m-%d')}.md"
        stage_path.write_text(text)
    return text, stage_path


def build_command_reference() -> str:
    return "\n".join(
        [
            "*Fake Matt intake commands*",
            "",
            "`python3 .../intake_bridge.py --self-test`",
            "",
            "`task: <committed task>`",
            "`should: <soft task>`",
            "`remind: <thing> @ <date or condition>`",
            "`remember: <durable preference/correction/rule>`",
            "`idea: [zerg-tooling] <raw idea>`",
            "`note: <general source-backed context>`",
            "`context: [project: ZTC] <source-backed fact>`",
            "`reply: email to name@example.com: <drafting task>`",
            "`reply: slack to @name: <drafting task>`",
            "`python3 .../intake_bridge.py --review-replies`",
            "`python3 .../intake_bridge.py --generate-reply-drafts`",
            "`python3 .../intake_bridge.py --send-gmail-draft <queue-id> --dry-run`",
            "`python3 .../intake_bridge.py --post-slack-draft <queue-id> --dry-run`",
            "",
            "*Mixed packet*",
            "```text",
            "capture:",
            "- task: Review the launch checklist",
            "- remind: renew passport @ June 1",
            "- idea: [zerg-tooling] parser backlog from repeated skips",
            "- context: [contact: Jane Doe] Jane owns beta onboarding",
            "- reply: slack to @idan: ask for PR review",
            "```",
            "",
            "*Rules*",
            "- Ambiguous `capture:` lines are skipped, not guessed.",
            "- Email/Slack replies are drafts only; no sends/posts to others.",
            "- Ideas go to `Ideas/_inbox`; context goes to `Tasks/fakematt-intake/context`.",
        ]
    )


def self_test_cases() -> list[dict[str, Any]]:
    return [
        {
            "name": "task command",
            "text": "task: Review the launch checklist",
            "expect": {"type": "task", "bucket": "TO_DO", "item": "Review the launch checklist"},
        },
        {
            "name": "should command",
            "text": "should: Revisit Fake Matt command syntax",
            "expect": {"type": "task", "bucket": "SHOULD_DO", "item": "Revisit Fake Matt command syntax"},
        },
        {
            "name": "reminder command",
            "text": "remind: renew passport @ June 1",
            "expect": {"type": "reminder", "item": "renew passport", "trigger": "June 1"},
        },
        {
            "name": "memory command",
            "text": "remember: I prefer terse intake receipts",
            "expect": {"type": "memory", "body": "I prefer terse intake receipts"},
        },
        {
            "name": "idea category command",
            "text": "idea: [zerg-tooling] Add parser self-tests",
            "expect": {"type": "idea", "category": "zerg-tooling", "item": "Add parser self-tests"},
        },
        {
            "name": "context command",
            "text": "context: [project: Fake Matt] Intake accepts explicit command packets",
            "expect": {
                "type": "context_note",
                "context_type": "project",
                "target": "Fake Matt",
                "body": "Intake accepts explicit command packets",
            },
        },
        {
            "name": "email reply command",
            "text": "reply: email to jane@example.com: ask for beta notes",
            "expect": {"type": "reply_draft", "surface": "gmail", "recipient": "jane@example.com"},
        },
        {
            "name": "slack reply command",
            "text": "reply: slack to @idan: ask for PR review",
            "expect": {"type": "reply_draft", "surface": "slack", "recipient": "@idan"},
        },
        {
            "name": "mixed capture command",
            "text": "\n".join(
                [
                    "capture:",
                    "- task: Review the launch checklist",
                    "- remind: renew passport @ June 1",
                    "- idea: [zerg-tooling] parser backlog from repeated skips",
                    "- context: [contact: Jane Doe] Jane owns beta onboarding",
                    "- reply: slack to @idan: ask for PR review",
                    "- loose ambiguous line",
                ]
            ),
            "expect_actions": [
                {"type": "task", "bucket": "TO_DO", "item": "Review the launch checklist"},
                {"type": "reminder", "item": "renew passport", "trigger": "June 1"},
                {"type": "idea", "category": "zerg-tooling"},
                {"type": "context_note", "context_type": "contact", "target": "Jane Doe"},
                {"type": "reply_draft", "surface": "slack", "recipient": "@idan"},
                {"type": "skip", "reason": "capture item needs explicit prefix"},
            ],
        },
    ]


def action_matches(action: dict[str, Any], expected: dict[str, Any]) -> bool:
    return all(action.get(key) == value for key, value in expected.items())


def run_self_test() -> int:
    rows: list[str] = []
    failures: list[str] = []
    for index, case in enumerate(self_test_cases(), start=1):
        packet = {
            "source_id": f"self-test:{index}",
            "source": "debug",
            "author": "self-test",
            "timestamp": now_stamp(),
            "context": case["name"],
            "text": case["text"],
            "_seen_key": f"self-test:{index}",
        }
        result = classify_packets([packet], no_llm=True)
        actions = result.get("actions", [])
        expected_actions = case.get("expect_actions") or [case["expect"]]
        ok = len(actions) == len(expected_actions) and all(
            action_matches(action, expected)
            for action, expected in zip(actions, expected_actions, strict=True)
        )
        marker = "OK" if ok else "FAIL"
        rows.append(f"[{marker}] {case['name']}: {len(actions)} action(s)")
        if not ok:
            failures.append(
                json.dumps(
                    {
                        "case": case["name"],
                        "expected": expected_actions,
                        "actual": actions,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )

    print("Fake Matt intake self-test")
    print("\n".join(rows))
    if failures:
        print("\nFailures:")
        print("\n\n".join(failures))
        return 1
    print("\nAll parser checks passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan explicit Fake Matt intake from Slack/Gmail.")
    parser.add_argument("--apply", action="store_true", help="apply internal vault writes")
    parser.add_argument("--apply-safe", action="store_true", help="apply only deterministic explicit commands")
    parser.add_argument("--post", action="store_true", help="post receipt to Fake Matt DM when packets exist")
    parser.add_argument("--post-empty", action="store_true", help="post even when no packets are found")
    parser.add_argument("--no-gmail", action="store_true", help="skip Gmail scan")
    parser.add_argument("--no-slack", action="store_true", help="skip Slack inbox scan")
    parser.add_argument("--no-llm", action="store_true", help="collect packets but skip LLM classification")
    parser.add_argument("--gmail-query", default=DEFAULT_GMAIL_QUERY)
    parser.add_argument("--gmail-max", type=int, default=10)
    parser.add_argument("--slack-limit", type=int, default=25)
    parser.add_argument("--slack-since-days", type=int, default=7)
    parser.add_argument("--mark-seen", action="store_true", help="persist seen packet IDs even without --apply")
    parser.add_argument("--packet-json", help="single synthetic packet JSON for tests/debugging")
    parser.add_argument("--report", action="store_true", help="summarize the intake event ledger instead of scanning")
    parser.add_argument("--report-days", type=int, default=7, help="days of event history to include in --report")
    parser.add_argument("--review-deferred", action="store_true", help="analyze deferred/skipped ledger patterns instead of scanning")
    parser.add_argument("--review-days", type=int, default=14, help="days of event history to include in --review-deferred")
    parser.add_argument("--write-review-note", action="store_true", help="write --review-deferred output under the intake reviews folder")
    parser.add_argument("--review-replies", action="store_true", help="summarize pending/generated reply queue items instead of scanning")
    parser.add_argument("--reply-days", type=int, default=14, help="days of reply queue history to include in --review-replies")
    parser.add_argument("--write-reply-review", action="store_true", help="write --review-replies output under the intake reviews folder")
    parser.add_argument("--generate-reply-drafts", action="store_true", help="generate drafts for pending reply queue items without sending/posting")
    parser.add_argument("--reply-limit", type=int, default=5, help="maximum pending reply queue items to process with --generate-reply-drafts")
    parser.add_argument("--reply-surface", choices=["all", "gmail", "slack"], default="all", help="surface filter for --generate-reply-drafts")
    parser.add_argument("--send-gmail-draft", metavar="QUEUE_ID", help="send a drafted Gmail queue item; requires --confirm 'SEND <queue-id>'")
    parser.add_argument("--post-slack-draft", metavar="QUEUE_ID", help="post a drafted Slack queue item; requires --confirm 'POST <queue-id>'")
    parser.add_argument("--confirm", default="", help="exact confirmation phrase required for send/post actions")
    parser.add_argument("--dry-run", action="store_true", help="preview send/post action without performing it")
    parser.add_argument("--account", help="Gmail account override for --send-gmail-draft")
    parser.add_argument("--workspace", help="Slack workspace override for --post-slack-draft")
    parser.add_argument("--review-context", action="store_true", help="summarize context inbox notes instead of scanning")
    parser.add_argument("--context-days", type=int, default=14, help="days of context notes to include in --review-context")
    parser.add_argument("--write-context-review", action="store_true", help="write --review-context output under the context reviews folder")
    parser.add_argument("--stage-context-reconciliation", action="store_true", help="draft target-note append blocks from context inbox notes")
    parser.add_argument("--write-context-stage", action="store_true", help="write --stage-context-reconciliation output under the context reconciliations folder")
    parser.add_argument("--print-command-reference", action="store_true", help="print Fake Matt intake command examples instead of scanning")
    parser.add_argument("--self-test", action="store_true", help="run deterministic intake parser checks without scanning or writing")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if args.print_command_reference:
        out = build_command_reference()
        print(out)
        if args.post:
            ok, status = post_to_slack(out)
            print(f"\n[slack: {'posted' if ok else 'failed'} - {status}]", file=sys.stderr)
        return 0

    if args.report:
        out = build_report(args.report_days)
        print(out)
        if args.post:
            ok, status = post_to_slack(out)
            print(f"\n[slack: {'posted' if ok else 'failed'} - {status}]", file=sys.stderr)
        return 0

    if args.review_deferred:
        out, note_path = build_deferred_review(args.review_days, write_note=args.write_review_note)
        print(out)
        if note_path:
            print(f"\n[review note: {note_path}]")
        if args.post:
            ok, status = post_to_slack(out)
            print(f"\n[slack: {'posted' if ok else 'failed'} - {status}]", file=sys.stderr)
        return 0

    if args.review_replies:
        out, note_path = build_reply_review(args.reply_days, write_note=args.write_reply_review)
        print(out)
        if note_path:
            print(f"\n[reply review: {note_path}]")
        if args.post:
            ok, status = post_to_slack(out)
            print(f"\n[slack: {'posted' if ok else 'failed'} - {status}]", file=sys.stderr)
        return 0

    if args.generate_reply_drafts:
        out = generate_reply_drafts(args.reply_days, limit=args.reply_limit, surface=args.reply_surface)
        print(out)
        if args.post:
            ok, status = post_to_slack(out)
            print(f"\n[slack: {'posted' if ok else 'failed'} - {status}]", file=sys.stderr)
        return 0

    if args.send_gmail_draft:
        out, code = send_gmail_queue_draft(
            args.send_gmail_draft,
            confirm=args.confirm,
            dry_run=args.dry_run,
            account=args.account,
        )
        print(out)
        return code

    if args.post_slack_draft:
        out, code = post_slack_queue_draft(
            args.post_slack_draft,
            confirm=args.confirm,
            dry_run=args.dry_run,
            workspace=args.workspace,
        )
        print(out)
        return code

    if args.review_context:
        out, note_path = build_context_review(args.context_days, write_note=args.write_context_review)
        print(out)
        if note_path:
            print(f"\n[context review: {note_path}]")
        if args.post:
            ok, status = post_to_slack(out)
            print(f"\n[slack: {'posted' if ok else 'failed'} - {status}]", file=sys.stderr)
        return 0

    if args.stage_context_reconciliation:
        out, stage_path = build_context_reconciliation_stage(args.context_days, write_stage=args.write_context_stage)
        print(out)
        if stage_path:
            print(f"\n[context stage: {stage_path}]")
        if args.post:
            ok, status = post_to_slack(out[:3500])
            print(f"\n[slack: {'posted' if ok else 'failed'} - {status}]", file=sys.stderr)
        return 0

    state = load_state()
    packets: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    if args.packet_json:
        packet = json.loads(args.packet_json)
        packet.setdefault("source_id", "debug:packet")
        packet.setdefault("source", "debug")
        packet.setdefault("author", "debug")
        packet.setdefault("timestamp", now_stamp())
        packet.setdefault("context", "debug")
        packet.setdefault("_seen_key", packet["source_id"])
        packets.append(packet)
    if not args.packet_json and not args.no_slack:
        packets.extend(scan_slack(state, args.slack_limit, args.slack_since_days))
    if not args.packet_json and not args.no_gmail:
        packets.extend(scan_gmail(state, args.gmail_query, args.gmail_max))

    try:
        result = classify_packets(packets, no_llm=args.no_llm)
    except Exception as exc:
        errors.append({"stage": "classify", "error": repr(exc)})
        result = {
            "summary": f"Classification failed: {exc}",
            "_retry_later": is_transient_classifier_error(exc),
            "actions": [
                {"type": "skip", "reason": "classification failed", "source_id": packet.get("source_id")}
                for packet in packets
            ],
        }
    applied = None
    mode = "preview"
    if args.apply:
        mode = "apply"
        try:
            applied = apply_actions(result.get("actions", []))
        except Exception as exc:
            errors.append({"stage": "apply", "error": repr(exc)})
            applied = []
    elif args.apply_safe:
        mode = "apply_safe"
        try:
            applied = apply_actions(result.get("actions", []), safe_only=True)
        except Exception as exc:
            errors.append({"stage": "apply_safe", "error": repr(exc)})
            applied = []
    out = receipt(result, packets, applied)
    print(out)

    post_status = None
    if should_post_receipt(args=args, packets=packets, result=result, applied=applied, errors=errors):
        ok, status = post_to_slack(out)
        post_status = {"ok": ok, "status": status}
        print(f"\n[slack: {'posted' if ok else 'failed'} - {status}]", file=sys.stderr)

    append_event(
        build_run_event(
            mode=mode,
            args=args,
            packets=packets,
            result=result,
            applied=applied,
            errors=errors,
            post_status=post_status,
        )
    )

    if (args.apply or args.apply_safe or args.mark_seen) and not result.get("_retry_later"):
        seen_slack = set(state.get("seen_slack", []))
        seen_gmail = set(state.get("seen_gmail", []))
        for packet in packets:
            if packet["source"] == "slack":
                seen_slack.add(packet["_seen_key"])
            elif packet["source"] == "gmail":
                seen_gmail.add(packet["_seen_key"])
        state["seen_slack"] = list(seen_slack)[-1000:]
        state["seen_gmail"] = list(seen_gmail)[-1000:]
        state["last_run"] = dt.datetime.now(dt.timezone.utc).isoformat()
        save_state(state)
    elif result.get("_retry_later"):
        print("[mark-seen: skipped because classifier asked to retry later]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
