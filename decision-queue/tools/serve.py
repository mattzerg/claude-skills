#!/usr/bin/env python3
"""serve.py — Flask server for decision-queue.

Routes:
  GET  /              — index, links to /swipe + status
  GET  /swipe         — vanilla-JS Tinder-style card stack UI
  GET  /api/queue     — JSON list of pending decisions
  POST /api/decide    — record an answer; updates source entity; appends log
  POST /slack/action  — Slack Block Kit interactive webhook (signed)
  GET  /health        — health check
  POST /api/regen     — trigger aggregate.py re-run

Binds 127.0.0.1:8788 by default. Set DECISION_QUEUE_BIND=0.0.0.0 to accept LAN
(needed for phone access over local network / Tailscale).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request, Response

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
TEMPLATES_DIR = SKILL_DIR / "templates"
LIB_DIR = SKILL_DIR / "lib"
sys.path.insert(0, str(LIB_DIR))

STATE_DIR = Path(os.path.expanduser("~/.claude/state"))
DECISIONS_JSONL = STATE_DIR / "decisions_pending.jsonl"
DECISIONS_LOG = STATE_DIR / "decisions_log.jsonl"

app = Flask(__name__)


def _load_queue() -> list[dict]:
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


def _append_log(record: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with DECISIONS_LOG.open("a") as fh:
        fh.write(json.dumps(record) + "\n")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trigger_aggregate() -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["/usr/bin/python3", str(SCRIPT_DIR / "aggregate.py")],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0, (result.stdout + result.stderr).strip()
    except Exception as e:
        return False, str(e)


# --- Routes ---

@app.route("/health")
def health():
    items = _load_queue()
    return jsonify({"ok": True, "pending": len(items), "ts": _now_iso()})


@app.route("/")
def index():
    items = _load_queue()
    return Response(f"""<!doctype html><html><head>
<title>Decision Queue</title>
<meta name=viewport content="width=device-width, initial-scale=1">
<style>
body {{ font-family: -apple-system, sans-serif; max-width: 640px; margin: 32px auto; padding: 0 16px; color: #1a1a1a; }}
h1 {{ font-size: 28px; }}
.stat {{ font-size: 18px; color: #444; margin: 16px 0; }}
.btn {{ display: inline-block; padding: 14px 22px; background: #1a1a1a; color: white; border-radius: 10px;
       text-decoration: none; font-weight: 600; margin-right: 8px; }}
.btn.secondary {{ background: #eee; color: #1a1a1a; }}
.list {{ margin-top: 24px; }}
.item {{ padding: 12px 0; border-bottom: 1px solid #eee; font-size: 14px; }}
.item .src {{ color: #888; font-size: 12px; }}
</style></head><body>
<h1>Decision Queue</h1>
<p class=stat><b>{len(items)}</b> pending</p>
<p>
  <a class=btn href="/swipe">Open swipe UI →</a>
  <a class=btn secondary href="/api/queue">JSON</a>
</p>
<div class=list>
  {"".join(f'<div class=item><div class=src>[{i["source"]}] {i["age_human"]} • {i.get("autonomy_class","")}</div><div>{i["context_one_line"]}</div></div>' for i in items[:30])}
</div>
</body></html>""", mimetype="text/html")


@app.route("/swipe")
def swipe():
    tpl = TEMPLATES_DIR / "swipe.html"
    if not tpl.exists():
        return Response("swipe.html template missing", status=500)
    return Response(tpl.read_text(), mimetype="text/html")


@app.route("/api/queue")
def api_queue():
    items = _load_queue()
    return jsonify({"count": len(items), "items": items, "ts": _now_iso()})


@app.route("/api/regen", methods=["POST"])
def api_regen():
    ok, msg = _trigger_aggregate()
    return jsonify({"ok": ok, "msg": msg, "ts": _now_iso()}), (200 if ok else 500)


@app.route("/api/decide", methods=["POST"])
def api_decide():
    """Record a decision. Body: {id, answer, channel, note?, briefing?}.

    answer ∈ {yes, no, defer-1d, defer-3d, details, skip, ...}
    """
    data = request.get_json(silent=True) or {}
    item_id = data.get("id")
    answer = data.get("answer")
    if not item_id or not answer:
        return jsonify({"ok": False, "err": "id+answer required"}), 400
    items = _load_queue()
    target = next((it for it in items if it.get("id") == item_id), None)
    if not target:
        return jsonify({"ok": False, "err": f"unknown id {item_id}"}), 404
    record = {
        "ts": _now_iso(),
        "id": item_id,
        "answer": answer,
        "channel": data.get("channel", "unknown"),
        "note": data.get("note"),
        "briefing_snapshot": target,  # full context at decision time → learning corpus
        "source": target.get("source"),
        "autonomy_class": target.get("autonomy_class"),
    }
    _append_log(record)
    # NOTE: v1 does not mutate source entities (zpub frontmatter, inbox.md).
    # The decision log is the source of truth; a follow-up agent reads the log
    # and proposes the actual file edits via the decision-queue. This keeps
    # the webhook surface read-only at the OS level.
    return jsonify({"ok": True, "logged": record["ts"]})


def _slack_signing_secret() -> str | None:
    """Read Slack signing secret from config (preferred) or env."""
    try:
        cfg = json.loads(
            (Path.home() / ".claude/skills/slack-skill/config.json").read_text()
        )
        s = (cfg.get("default") or {}).get("signing_secret")
        if s:
            return s
    except Exception:
        pass
    return os.environ.get("SLACK_SIGNING_SECRET")


def _verify_slack_signature(body: bytes, ts_header: str, sig_header: str, secret: str) -> bool:
    """Verify Slack's v0 HMAC-SHA256 signature.

    https://api.slack.com/authentication/verifying-requests-from-slack
    """
    if not ts_header or not sig_header or not secret:
        return False
    try:
        ts_int = int(ts_header)
    except ValueError:
        return False
    # Reject replays older than 5min
    if abs(time.time() - ts_int) > 300:
        return False
    basestring = f"v0:{ts_header}:".encode() + body
    expected = "v0=" + hmac.new(
        secret.encode(), basestring, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, sig_header)


@app.route("/slack/action", methods=["POST"])
def slack_action():
    """Slack interactive Block Kit webhook.

    Verification (Q0.4):
      - If a signing secret is configured AND the request carries Slack's
        signature headers, verify HMAC. Reject 401 on mismatch.
      - If no secret configured AND we're bound to 127.0.0.1 only, accept
        unverified (local-loopback trust mode).
      - If bound to non-loopback (LAN/Tailscale) AND no secret, reject 401
        unconditionally — fail-closed beats fail-open on a public surface.
    """
    secret = _slack_signing_secret()
    bind = os.environ.get("DECISION_QUEUE_BIND", "127.0.0.1")
    is_loopback = bind in ("127.0.0.1", "::1", "localhost")
    ts_h = request.headers.get("X-Slack-Request-Timestamp", "")
    sig_h = request.headers.get("X-Slack-Signature", "")

    if secret:
        if not _verify_slack_signature(request.get_data(), ts_h, sig_h, secret):
            return jsonify({"ok": False, "err": "bad signature"}), 401
    else:
        if not is_loopback:
            return jsonify({
                "ok": False,
                "err": "no signing secret configured + non-loopback bind; refusing"
            }), 401
        # else: loopback + no secret — fall through (local trust)

    payload_raw = request.form.get("payload")
    if not payload_raw:
        return jsonify({"ok": False, "err": "missing payload"}), 400
    try:
        payload = json.loads(payload_raw)
    except json.JSONDecodeError:
        return jsonify({"ok": False, "err": "bad payload"}), 400
    actions = payload.get("actions", [])
    if not actions:
        return jsonify({"ok": False, "err": "no action"}), 400
    action = actions[0]
    item_id = action.get("value")  # we encode the item id in value
    answer = action.get("action_id")  # we encode the answer in action_id
    # Look up item
    items = _load_queue()
    target = next((it for it in items if it.get("id") == item_id), None)
    if not target:
        return jsonify({
            "text": f"Couldn't find item `{item_id}` — may have been cleared. Re-run aggregate.",
        })
    record = {
        "ts": _now_iso(),
        "id": item_id,
        "answer": answer,
        "channel": "slack",
        "note": None,
        "briefing_snapshot": target,
        "source": target.get("source"),
        "autonomy_class": target.get("autonomy_class"),
        "slack_user": payload.get("user", {}).get("name"),
    }
    _append_log(record)
    return jsonify({
        "response_action": "update",
        "text": f"✅ Recorded `{answer}` for `{item_id}`",
    })


def main() -> int:
    bind = os.environ.get("DECISION_QUEUE_BIND", "127.0.0.1")
    port = int(os.environ.get("DECISION_QUEUE_PORT", "8788"))
    debug = os.environ.get("DECISION_QUEUE_DEBUG", "") == "1"
    app.run(host=bind, port=port, debug=debug, use_reloader=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
