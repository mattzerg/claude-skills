#!/usr/bin/env python3
"""slack_card.py — post decision-queue items as Block Kit cards to FM-DM.

Two modes:
  digest    Post a single "N decisions ready" header with up to top-3 cards
  full      Post one card per item in the queue (use only when intent is clear)

Each card has 4 action buttons: ✅ yes / ❌ no / ⏸ defer-1d / 🔍 details.
Each button's value=item.id and action_id=answer string.

The Slack interactive webhook (decision-queue serve.py /slack/action) records
the answer to decisions_log.jsonl.

Usage:
  python3 slack_card.py digest                # default: post top 3 from queue
  python3 slack_card.py digest --limit 5
  python3 slack_card.py full                  # one card per pending item
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Reuse slack-skill's client/config helpers
SLACK_SKILL = Path(os.path.expanduser("~/.claude/skills/slack-skill"))
sys.path.insert(0, str(SLACK_SKILL))

try:
    from slack_sdk import WebClient  # type: ignore
    from slack_sdk.errors import SlackApiError  # type: ignore
except ImportError as e:
    print(json.dumps({"error": f"slack_sdk missing: {e}"}))
    sys.exit(1)

STATE_DIR = Path(os.path.expanduser("~/.claude/state"))
DECISIONS_JSONL = STATE_DIR / "decisions_pending.jsonl"


def load_queue() -> list[dict]:
    if not DECISIONS_JSONL.exists():
        return []
    items = []
    with DECISIONS_JSONL.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return items


def load_config() -> dict:
    cfg_path = SLACK_SKILL / "config.json"
    return json.loads(cfg_path.read_text())["default"]


def card_blocks(item: dict, position: int, total: int) -> list[dict]:
    """Return Block Kit blocks for one decision item."""
    src = item.get("source", "?")
    cls = item.get("autonomy_class", "—") or "—"
    age = item.get("age_human", "")
    ctx = item.get("context_one_line", "")
    why = item.get("why", "")
    deadline = item.get("deadline")
    item_id = item.get("id", "")
    choices = item.get("choices") or ["yes", "no", "defer-1d", "details"]

    # Use first 4 choices for buttons; fall back to canonical if fewer
    while len(choices) < 4:
        choices.append("details")
    yes_label, no_label, defer_label, details_label = choices[:4]

    header_ctx = f"*{position}/{total}* • `{src}` • `{cls}` • {age}"
    if deadline:
        header_ctx += f" • ⏰ {deadline}"

    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"{header_ctx}\n*{ctx}*"},
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"_{why}_"}],
        },
        {
            "type": "actions",
            "block_id": f"dq:{item_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": f"✅ {yes_label}", "emoji": True},
                    "style": "primary",
                    "value": item_id,
                    "action_id": "yes",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": f"❌ {no_label}", "emoji": True},
                    "style": "danger",
                    "value": item_id,
                    "action_id": "no",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": f"⏸ {defer_label}", "emoji": True},
                    "value": item_id,
                    "action_id": "defer-1d",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": f"🔍 {details_label}", "emoji": True},
                    "value": item_id,
                    "action_id": "details",
                },
            ],
        },
        {"type": "divider"},
    ]
    return blocks


def digest_message(items: list[dict], limit: int) -> tuple[str, list[dict]]:
    total = len(items)
    head_text = (
        f"*{total} decision{'s' if total != 1 else ''} ready.* "
        f"Reply via swipe app at http://127.0.0.1:8788/swipe or tap below for the top {min(limit, total)}."
    )
    blocks: list[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": "Decision queue", "emoji": True}},
        {"type": "section", "text": {"type": "mrkdwn", "text": head_text}},
        {"type": "divider"},
    ]
    for i, item in enumerate(items[:limit], start=1):
        blocks.extend(card_blocks(item, i, total))
    return head_text, blocks


def post(channel: str, text: str, blocks: list[dict]) -> dict:
    cfg = load_config()
    import sys as _zs, pathlib as _zp; _zs.path.insert(0, str(_zp.Path.home()/".config"/"zerg")); from slack_token import slack_token
    client = WebClient(token=slack_token())
    try:
        resp = client.chat_postMessage(channel=channel, text=text, blocks=blocks)
        return {"ok": True, "ts": resp["ts"], "channel": channel}
    except SlackApiError as e:
        return {"ok": False, "err": str(e)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["digest", "full", "dry-run"])
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--channel", default=None, help="override FM-DM channel from config")
    args = ap.parse_args()

    items = load_queue()
    if not items:
        print(json.dumps({"ok": True, "msg": "queue empty; nothing to post"}))
        return 0

    if args.mode == "dry-run":
        text, blocks = digest_message(items, args.limit)
        print(json.dumps({"text": text, "blocks": blocks}, indent=2))
        return 0

    cfg = load_config()
    channel = args.channel or cfg.get("fm_dm_channel")
    if not channel:
        print(json.dumps({"ok": False, "err": "no channel configured"}))
        return 1

    if args.mode == "digest":
        text, blocks = digest_message(items, args.limit)
        result = post(channel, text, blocks)
        print(json.dumps(result))
        return 0 if result["ok"] else 1

    if args.mode == "full":
        # One message per item — only when explicitly requested
        results = []
        for i, item in enumerate(items, start=1):
            blocks = card_blocks(item, i, len(items))
            text = f"Decision {i}/{len(items)}: {item.get('context_one_line', '')}"
            results.append(post(channel, text, blocks))
        print(json.dumps({"posted": len(results), "results": results}))
        return 0 if all(r["ok"] for r in results) else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
