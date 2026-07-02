#!/usr/bin/env python3
"""
Slack Bridge - Real-time connection between Slack and Claude Code.

NOTE on imports: this module needs `from __future__ import annotations` to
support PEP 604 union syntax (`X | None`) on Python 3.9 (which is what's
installed at /Library/Developer/CommandLineTools). Without it, the type
hints on `run_claude_with_progress` and `finalize_progress_or_send` raise
TypeError at module-load time.
"""
from __future__ import annotations

# (original docstring continues for reference)
_ORIG_DOCSTRING = """
Slack Bridge - Socket Mode bridge between Slack and Claude Code.

Current responsibilities:
- Accept Slack DMs, app mentions, tracked thread replies, and confirmation reactions.
- Acknowledge Socket Mode events immediately, then run long Claude/dispatch work in bounded workers.
- De-dupe Slack events across processes with atomic marker files.
- Maintain per-thread Claude sessions, progress messages, stuck-work cleanup, and per-user rate limits.
- Support Phase F two-way DM intent confirmation in the Fake Matt -> Matt DM only:
  Claude proposes a structured action, the bridge validates/persists it, then Matt confirms by reaction
  or by replying in the proposal thread.

This file does not execute external write-actions directly. Confirmed actions are handed to
~/.claude/fakematt-today/dm_dispatch.py.

Setup and operations checklist: see SLACK_SETUP.md in this directory.

Usage:
    python slack_bridge.py              # Run the bridge (foreground)
    python slack_bridge.py --auto       # Auto-respond using Claude Code
    python slack_bridge.py --daemon     # Run in background
    python slack_bridge.py --status     # Check if running
    python slack_bridge.py --stop       # Stop the daemon
    python slack_bridge.py --cleanup    # Retry stuck work once
    python slack_bridge.py --scan       # Scan inbox for orphaned hourglasses
    python slack_bridge.py --inbox      # Show recent inbox messages
    python slack_bridge.py --reply CH TS "message"  # Reply to a message
"""

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from threading import BoundedSemaphore, Event, Lock, Thread

# Global config for auto-responder
AUTO_RESPOND = False
WORK_DIR = None
DEFAULT_ALLOWED_USERS = {"U04R0EJACMR", "U0AFSSPNB1N"}  # Idan + Matt
ALLOWED_USERS = set(DEFAULT_ALLOWED_USERS)
THREAD_SESSIONS = {}  # Track Claude Code session IDs per thread: {session_key: session_id}
ACTIVE_THREADS = {}  # Track threads we've posted to: {thread_ts: {channel, last_response_ts}}
PENDING_WORK = {}  # Track messages with hourglass: {(channel, ts): {"start_time": float, "text": str, ...}}
PENDING_WORK_FILE = None  # Set after SKILL_DIR is defined

# Emoji constants
EMOJI_WORKING = "hourglass_flowing_sand"
EMOJI_DONE = "white_check_mark"
EMOJI_ACK = "eyes"
EMOJI_ERROR = "x"
EMOJI_RETRY = "arrows_counterclockwise"

# No-response sentinel - Claude can return this to skip posting
NO_RESPONSE_SENTINEL = "[NO_RESPONSE]"
CLAUDE_BIN = os.environ.get("SLACK_BRIDGE_CLAUDE_BIN", str(Path.home() / ".config" / "zerg" / "zclaude"))
CLAUDE_RATE_WINDOW_SECONDS = int(os.environ.get("SLACK_BRIDGE_RATE_WINDOW_SECONDS", "300"))
CLAUDE_RATE_MAX_PER_WINDOW = int(os.environ.get("SLACK_BRIDGE_RATE_MAX_PER_WINDOW", "30"))
CLAUDE_RATE_HOUR_SECONDS = int(os.environ.get("SLACK_BRIDGE_RATE_HOUR_SECONDS", "3600"))
CLAUDE_RATE_MAX_PER_HOUR = int(os.environ.get("SLACK_BRIDGE_RATE_MAX_PER_HOUR", "100"))
CLAUDE_INVOCATION_LOG: dict[str, list[float]] = {}
CLAUDE_RATE_LOCK = Lock()
CLAUDE_WORKER_COUNT = int(os.environ.get("SLACK_BRIDGE_CLAUDE_WORKERS", os.environ.get("SLACK_BRIDGE_WORKERS", "2")))
DISPATCH_WORKER_COUNT = int(os.environ.get("SLACK_BRIDGE_DISPATCH_WORKERS", "4"))
CLAUDE_QUEUE_SIZE = int(os.environ.get("SLACK_BRIDGE_CLAUDE_QUEUE", str(CLAUDE_WORKER_COUNT)))
DISPATCH_QUEUE_SIZE = int(os.environ.get("SLACK_BRIDGE_DISPATCH_QUEUE", str(DISPATCH_WORKER_COUNT * 2)))
CLAUDE_WORKERS = ThreadPoolExecutor(max_workers=CLAUDE_WORKER_COUNT)
DISPATCH_WORKERS = ThreadPoolExecutor(max_workers=DISPATCH_WORKER_COUNT)
CLAUDE_WORK_SLOTS = BoundedSemaphore(CLAUDE_WORKER_COUNT + CLAUDE_QUEUE_SIZE)
DISPATCH_WORK_SLOTS = BoundedSemaphore(DISPATCH_WORKER_COUNT + DISPATCH_QUEUE_SIZE)

# Conservative scratchpad phrases: only match DMs that are unambiguously
# personal scratchpad notes. False negatives cost a Claude invocation and a
# rate-limit slot; false positives silently drop real requests. When extending,
# add patterns only after seeing repeated scratchpad phrasing in practice.
SELF_NOTE_PATTERNS = [
    re.compile(r"^\s*just\s+(?:sending|saving|dropping)\s+this\s+to\s+myself\b", re.I),
    re.compile(r"^\s*(?:just\s+)?(?:save|saving|drop|dropping)\s+this\s+for\s+me\b", re.I),
    re.compile(r"^\s*note\s+to\s+self\b", re.I),
]

# Check for required library
try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
    from slack_sdk.socket_mode import SocketModeClient
    from slack_sdk.socket_mode.request import SocketModeRequest
    from slack_sdk.socket_mode.response import SocketModeResponse
except ImportError:
    print("Error: slack_sdk not installed or missing socket mode support.")
    print("Install with: pip install 'slack_sdk[socket_mode]'")
    sys.exit(1)

# Paths
SKILL_DIR = Path(__file__).parent
CONFIG_FILE = SKILL_DIR / "config.json"
INBOX_FILE = SKILL_DIR / "inbox.jsonl"
PID_FILE = SKILL_DIR / ".bridge.pid"
HEALTH_FILE = SKILL_DIR / "bridge_health.json"
DISPATCH_AUDIT_FILE = SKILL_DIR / "dispatch_audit.jsonl"
PENDING_WORK_FILE = SKILL_DIR / "pending_work.json"  # For persistent pending work tracking
THREAD_SESSIONS_FILE = SKILL_DIR / "thread_sessions.json"  # For persistent thread session tracking
EVENT_DEDUPE_DIR = SKILL_DIR / ".event_dedupe"  # Atomic markers prevent duplicate Slack event processing
EVENT_DEDUPE_TTL = 48 * 3600

# --- Phase F: two-way DM intent confirmation ----------------------------------
# state_pending_actions.json = bridge ↔ dm_dispatch handoff. Keyed by the ts of
# the DM message FM posted to Matt with the proposal. Cleared on ✅/❌ reaction
# or yes/no/cancel text reply, or after 24h TTL.
FAKEMATT_TODAY_DIR = Path.home() / ".claude" / "fakematt-today"
PENDING_ACTIONS_FILE = FAKEMATT_TODAY_DIR / "state_pending_actions.json"
DM_DISPATCH_PATH = FAKEMATT_TODAY_DIR / "dm_dispatch.py"
DEFAULT_FM_DM_CHANNEL = "D0B0T0ETDR8"  # Fake Matt → Matt DM (the only channel where intent dispatch fires)
FM_DM_CHANNEL = DEFAULT_FM_DM_CHANNEL
PENDING_TTL_SECONDS = int(os.environ.get("SLACK_BRIDGE_PENDING_TTL_SECONDS", str(24 * 3600)))
WORK_TIMEOUT = int(os.environ.get("SLACK_BRIDGE_WORK_TIMEOUT", "900"))
CLEANUP_INTERVAL = int(os.environ.get("SLACK_BRIDGE_CLEANUP_INTERVAL", "300"))
HEALTH_INTERVAL = int(os.environ.get("SLACK_BRIDGE_HEALTH_INTERVAL", "10"))
HEALTH_STALE_SECONDS = int(os.environ.get("SLACK_BRIDGE_HEALTH_STALE_SECONDS", "30"))
PROGRESS_DELAY_SECONDS = float(os.environ.get("SLACK_BRIDGE_PROGRESS_DELAY_SECONDS", "20"))
PENDING_ACTIONS_LOCK = Lock()
PROMISE_ACTION_LOCK = Lock()
ACTIVE_PROMISE_ACTIONS: set[tuple[str, str]] = set()

# Reaction → action mapping for confirmation flow
REACTION_CONFIRM = {"white_check_mark", "+1", "ok", "heavy_check_mark"}
REACTION_CANCEL  = {"x", "no_entry", "negative_squared_cross_mark", "heavy_multiplication_x"}
REACTION_EDIT    = {"pencil2", "memo", "writing_hand"}
REACTION_SNOOZE  = {"zzz", "sleeping", "alarm_clock"}
ALLOWED_ACTION_KINDS = {
    "linear_issue",
    "zergboard_card",
    "gmail_draft",
    "calendar_event",
    "vault_note",
    "snooze_promise",
    "clear_promise",
}
PROPOSAL_REQUIRED_FIELDS = {
    "linear_issue": {"team", "title", "description"},
    "zergboard_card": {"board", "title", "description"},
    "gmail_draft": {"to", "task", "subject"},
    "calendar_event": {"title", "start", "end"},
    "vault_note": {"text"},
    "snooze_promise": {"promise_id"},
    "clear_promise": {"promise_id"},
}


def get_session_key(channel_id: str, thread_ts: str = None) -> str:
    """Generate a unique session key for a channel/thread combination.

    - DMs without thread: channel_id:main (one continuous conversation per DM)
    - DMs with thread: channel_id:thread_ts (isolated per thread)
    - Channel threads: channel_id:thread_ts (isolated per thread)
    - New channel mentions: channel_id:message_ts (starts fresh)
    """
    if thread_ts:
        return f"{channel_id}:{thread_ts}"
    return f"{channel_id}:main"


def load_thread_sessions():
    """Load thread sessions from file."""
    global THREAD_SESSIONS
    if THREAD_SESSIONS_FILE.exists():
        try:
            with open(THREAD_SESSIONS_FILE) as f:
                THREAD_SESSIONS = json.load(f)
                print(f"[STARTUP] Loaded {len(THREAD_SESSIONS)} thread sessions")
        except Exception as e:
            print(f"[STARTUP] Error loading thread sessions: {e}")
            THREAD_SESSIONS = {}


def save_thread_sessions():
    """Save thread sessions to file."""
    try:
        atomic_write_json(THREAD_SESSIONS_FILE, THREAD_SESSIONS)
    except Exception as e:
        print(f"[ERROR] Failed to save thread sessions: {e}")


def load_config():
    """Load configuration."""
    if not CONFIG_FILE.exists():
        print(json.dumps({"error": "No config file found"}))
        sys.exit(1)
    with open(CONFIG_FILE) as f:
        return json.load(f)


def get_workspace_config(workspace: str = "default") -> dict:
    """Get merged workspace config, falling back to default."""
    config = load_config()
    return config.get(workspace, config.get("default", {}))


def _load_zerg_secrets() -> None:
    """Populate os.environ from ~/.config/zerg/secrets.env (gitignored, chmod 600).
    Does not override already-set env vars. Fail-open."""
    try:
        p = Path.home() / ".config" / "zerg" / "secrets.env"
        if not p.exists():
            return
        for raw in p.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except Exception:
        pass


def get_tokens(workspace: str = "default"):
    """Get bot and app tokens for workspace (config.json, then secrets.env env vars)."""
    ws_config = get_workspace_config(workspace)
    _load_zerg_secrets()
    bot = ws_config.get("token") or os.environ.get("SLACK_TOKEN")
    app = ws_config.get("app_token") or os.environ.get("SLACK_APP_TOKEN")
    return bot, app


def apply_workspace_settings(workspace: str = "default") -> None:
    """Load non-secret bridge settings from config.json for this workspace."""
    global ALLOWED_USERS, FM_DM_CHANNEL
    ws_config = get_workspace_config(workspace)
    ALLOWED_USERS = set(ws_config.get("allowed_users", sorted(DEFAULT_ALLOWED_USERS)))
    FM_DM_CHANNEL = ws_config.get("fm_dm_channel", DEFAULT_FM_DM_CHANNEL)


def write_to_inbox(message: dict):
    """Append a message to the inbox file."""
    message["received_at"] = datetime.now().isoformat()
    with open(INBOX_FILE, "a") as f:
        f.write(json.dumps(message) + "\n")


def atomic_write_json(path: Path, data, *, indent: int | None = None) -> None:
    """Write JSON with tmp+replace so crashes do not leave truncated state."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    tmp.write_text(json.dumps(data, indent=indent))
    tmp.replace(path)


def read_json_file(path: Path, default=None):
    """Read JSON state, returning default on missing or invalid files."""
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def socket_connection_state(socket_client) -> bool | None:
    """Best-effort Socket Mode connection state without depending on one SDK version."""
    if socket_client is None:
        return None

    for attr in ("is_connected", "connected"):
        try:
            value = getattr(socket_client, attr, None)
            if callable(value):
                value = value()
            if value is not None:
                return bool(value)
        except Exception:
            pass

    for attr in ("current_session", "session"):
        try:
            session = getattr(socket_client, attr, None)
            if session is None:
                continue
            for session_attr in ("is_connected", "connected"):
                value = getattr(session, session_attr, None)
                if callable(value):
                    value = value()
                if value is not None:
                    return bool(value)
        except Exception:
            pass

    return None


def write_bridge_health(
    *,
    workspace: str,
    auto_respond: bool,
    work_dir: str | None,
    started_at: str,
    socket_client=None,
    running: bool = True,
    last_cleanup_at: str | None = None,
    stopped_at: str | None = None,
) -> None:
    """Persist daemon heartbeat and best-effort Socket Mode health."""
    previous = read_json_file(HEALTH_FILE, {}) or {}
    now = datetime.now().isoformat()
    if last_cleanup_at is None:
        last_cleanup_at = previous.get("last_cleanup_at")

    health = {
        "pid": os.getpid(),
        "running": running,
        "workspace": workspace,
        "auto_respond": auto_respond,
        "work_dir": work_dir,
        "started_at": started_at,
        "last_health_at": now,
        "socket_connected": socket_connection_state(socket_client),
        "allowed_users_count": len(ALLOWED_USERS),
        "fm_dm_channel": FM_DM_CHANNEL,
        "pending_work_count": len(PENDING_WORK),
        "thread_sessions_count": len(THREAD_SESSIONS),
    }
    if last_cleanup_at:
        health["last_cleanup_at"] = last_cleanup_at
    if stopped_at:
        health["stopped_at"] = stopped_at

    try:
        atomic_write_json(HEALTH_FILE, health, indent=2)
    except Exception as e:
        print(f"[HEALTH] Error writing bridge health: {e}")


def bridge_health_age_seconds(health: dict | None) -> float | None:
    """Return heartbeat age in seconds, or None when no usable timestamp exists."""
    if not health:
        return None
    last_health_at = health.get("last_health_at")
    if not last_health_at:
        return None
    try:
        return max(0.0, time.time() - datetime.fromisoformat(last_health_at).timestamp())
    except Exception:
        return None


def claim_pid_file() -> None:
    """Atomically claim the daemon PID file or exit if a bridge is alive."""
    while True:
        try:
            fd = os.open(str(PID_FILE), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            with os.fdopen(fd, "w") as f:
                f.write(str(os.getpid()))
            return
        except FileExistsError:
            try:
                existing_pid = int(PID_FILE.read_text().strip())
                if existing_pid != os.getpid():
                    os.kill(existing_pid, 0)
                    print(f"Error: bridge already running with PID {existing_pid}. Use --stop first.")
                    sys.exit(1)
                return
            except ProcessLookupError:
                try:
                    PID_FILE.unlink()
                except FileNotFoundError:
                    pass
            except ValueError:
                PID_FILE.unlink()


def cleanup_event_dedupe() -> None:
    """Best-effort cleanup for old de-dupe markers."""
    if not EVENT_DEDUPE_DIR.exists():
        return
    cutoff = time.time() - EVENT_DEDUPE_TTL
    try:
        for path in EVENT_DEDUPE_DIR.iterdir():
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
    except Exception as e:
        print(f"[DEDUPE] Cleanup failed: {e}")


def claim_slack_event(req: SocketModeRequest, event: dict) -> bool:
    """Return True only once per Slack event across bridge processes.

    Slack retries and accidental multiple bridge processes can otherwise produce
    duplicate responses. O_EXCL makes the claim atomic on the local filesystem.
    """
    event_id = req.payload.get("event_id")
    if not event_id:
        event_id = ":".join([
            str(event.get("type", "")),
            str(event.get("channel", "")),
            str(event.get("user", "")),
            str(event.get("ts", "")),
            str(event.get("thread_ts", "")),
            str(event.get("reaction", "")),
        ])
    if not event_id.strip(":"):
        return True

    EVENT_DEDUPE_DIR.mkdir(exist_ok=True)
    digest = hashlib.sha1(event_id.encode("utf-8")).hexdigest()
    marker = EVENT_DEDUPE_DIR / digest
    try:
        fd = os.open(str(marker), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps({
                "event_id": event_id,
                "claimed_at": time.time(),
                "event_type": event.get("type"),
                "channel": event.get("channel"),
                "ts": event.get("ts"),
            }))
        # About 1/256 events trigger cleanup, enough for low-volume DM traffic
        # while keeping the 48h TTL from accumulating marker files forever.
        if int(digest[:2], 16) == 0:
            cleanup_event_dedupe()
        return True
    except FileExistsError:
        print(f"  [DEDUPE] Already handled Slack event {event_id}; skipping")
        return False
    except Exception as e:
        print(f"  [DEDUPE] Could not claim event {event_id}: {e}; continuing")
        return True


def slack_turn_prompt(prompt: str, user_name: str, channel_name: str,
                      channel_for_upload: str, thread_ts: str | None,
                      proposal_contract: str, thread_flag: str,
                      first_turn: bool) -> str:
    """Build the per-turn instruction wrapper sent to Claude Code."""
    intro = (
        f"You are responding to Slack messages from {user_name}. "
        "Keep responses concise and conversational (Slack-appropriate)."
        if first_turn else
        f"Slack follow-up from {user_name} in {channel_name}."
    )
    return f"""{intro}

You have full access to this workspace including Obsidian vault, skills, and tools. You can read files, send emails, etc.

When the user gives feedback or asks why you behaved a certain way, answer directly, explain what happened, and adjust behavior in the current thread. Do not return an empty final result.

When the user confirms something (like "yes", "do it", "send it"), execute the action you proposed.{proposal_contract}

CHOOSING NOT TO RESPOND:
You do NOT need to respond to every message. If the message:
- Isn't directed at you or doesn't need your input
- Is just chatter between other people
- Is a statement that doesn't warrant a reply
- Would be better left alone
Then respond with EXACTLY: {NO_RESPONSE_SENTINEL}
Only respond when you genuinely have something useful to add. When in doubt, don't respond.
Do not respond with only a bare count, number, "ok", "done", or other acknowledgement unless the user explicitly asked for that exact value. If nothing changed state and there is no useful answer, return {NO_RESPONSE_SENTINEL}.

CRITICAL — NO DOUBLE-POSTING:
The bridge automatically posts your final output text to Slack. So:
- Pick ONE channel: either return your reply as final text (preferred), OR send it yourself via slack-skill / upload — never both.
- If you already posted to Slack via a tool (slack_skill.py send, upload, MCP slack tool, etc.), you MUST return EXACTLY {NO_RESPONSE_SENTINEL} as your final output. Do not add a recap, confirmation, or "done" message — the user can see what you posted.
- Never write a summary of what you just said or did. No "I sent X", no "Here's a recap", no "To summarize". The reply itself is the only message.

IMPORTANT CONTEXT:
- Channel name: {channel_name}
- Channel ID: {channel_for_upload}
- Thread TS: {thread_ts or "none (post to channel)"}
- ALWAYS respond in the same thread if one exists. Include -t {thread_ts} in upload commands when thread_ts is set.

IMAGE GENERATION: If the user asks for an image, picture, or visual:
1. Generate: python ~/.claude/skills/nano-banana-pro/generate_image.py "prompt" --output /tmp
2. Upload to Slack: python ~/.claude/skills/slack-skill/slack_skill.py upload {channel_for_upload} /tmp/generated_images/[filename].png -m "caption"{thread_flag}
3. After uploading, return EXACTLY {NO_RESPONSE_SENTINEL} — the upload's caption is the message; do NOT add a follow-up summary.

User message: {prompt}"""


def run_claude_code(prompt: str, user_name: str, channel_name: str, user_id: str,
                     channel_id: str = None, thread_ts: str = None) -> str:
    """Run Claude Code with a prompt and return the response.

    Each channel/thread gets its own isolated Claude Code session.
    Sessions are tracked and resumed so each thread maintains its own context.
    """
    global WORK_DIR, THREAD_SESSIONS

    # Compute session key for this channel/thread
    session_key = get_session_key(channel_id or "unknown", thread_ts)
    existing_session_id = THREAD_SESSIONS.get(session_key)

    # Build thread context for uploads
    thread_flag = f" -t {thread_ts}" if thread_ts else ""
    channel_for_upload = channel_id or "CHANNEL_ID"

    # Phase F: append the proposed_action contract for DM new-sessions only.
    # The bridge intercepts <proposed_action> blocks before posting and replaces
    # them with a clean human summary + reaction options. So Claude must
    # produce both the structured block AND a human summary in the same turn.
    is_dm_context = channel_id == FM_DM_CHANNEL
    proposal_contract = ""
    if is_dm_context:
        proposal_contract = """

PROPOSED-ACTION CONTRACT (DMs only):
When you intend to take a write-action (file Linear/Zergboard, draft Gmail, create calendar event, write vault note, snooze/clear a promise), do NOT execute the action directly. Instead, emit a fenced block followed by a one-line plain-English summary:

<proposed_action>
kind: linear_issue | zergboard_card | gmail_draft | calendar_event | vault_note | snooze_promise | clear_promise
payload: {"key": "value", ...}
</proposed_action>
[plain-English summary the user will read here]

The bridge replaces the fenced block with the summary + ✅/❌/✏️ reaction options. Wait for the user's reaction, or a yes/no/edit/snooze reply in the proposal thread, before assuming it ran.

`payload` requirements per kind:
- linear_issue:    {"team": "EPO", "title": "...", "description": "...", "priority": "urgent|high|medium|low", "project": "..."}
- zergboard_card:  {"board": "<board-uuid-or-slug>", "title": "...", "description": "...", "priority": "high"}
- gmail_draft:     {"to": "email@x.com", "task": "what the email should say", "subject": "..."}
- calendar_event:  {"title": "...", "start": "ISO-8601 with TZ", "end": "...", "attendees": "a@x.com,b@y.com"}
- vault_note:      {"text": "...", "tag": "todo|idea|note"}
- snooze_promise:  {"promise_id": "<sha1 from promise_state>", "days": 3}
- clear_promise:   {"promise_id": "<sha1 from promise_state>"}

If the user is just chatting / asking a question / not requesting a write-action, respond normally without a proposed_action block.
"""

    full_prompt = slack_turn_prompt(
        prompt, user_name, channel_name, channel_for_upload, thread_ts,
        proposal_contract, thread_flag, first_turn=not bool(existing_session_id)
    )

    # Heuristic timeout — bump from 10 min to 20 min when the prompt asks
    # for a substantive build (ship, open a PR, multi-file fix). These often
    # need >10 min once you factor in Anthropic 429 retries + file scans.
    # Short Q&A and "what is X" stays at 10 min.
    _long_run_markers = (
        "ship the fix", "ship the change", "open a pr", "open the pr",
        "open a pull request", "open the pull request", "land the fix",
        "implement and ship", "build and ship", "wire up and ship",
    )
    _claude_timeout = 1200 if any(m in prompt.lower() for m in _long_run_markers) else 600

    try:
        def invoke_claude(resume_session_id: str | None):
            cmd = [CLAUDE_BIN, "-p", "--output-format", "json", "--dangerously-skip-permissions"]
            if resume_session_id:
                cmd.extend(["--resume", resume_session_id])

            # Strip CLAUDECODE env var to avoid nested session detection
            env = os.environ.copy()
            env.pop("CLAUDECODE", None)
            env.pop("CLAUDE_CODE_SESSION", None)

            return subprocess.run(
                cmd,
                capture_output=True,
                input=full_prompt,
                text=True,
                cwd=WORK_DIR,
                env=env,
                timeout=_claude_timeout,
            )

        def parse_claude_result(stdout: str) -> tuple[str, str | None, bool]:
            raw = stdout.strip()
            try:
                response_data = json.loads(raw)
            except json.JSONDecodeError:
                return raw, None, True
            return response_data.get("result", ""), response_data.get("session_id"), False

        result = invoke_claude(existing_session_id)
        response, new_session_id, parse_failed = parse_claude_result(result.stdout)

        if existing_session_id and (parse_failed or result.returncode != 0 or not response):
            print(f"  [Session {existing_session_id[:12]}... may be stale, retrying fresh]")
            THREAD_SESSIONS.pop(session_key, None)
            save_thread_sessions()
            result = invoke_claude(None)
            response, new_session_id, parse_failed = parse_claude_result(result.stdout)

        if result.returncode != 0:
            response = format_claude_failure(result.returncode, result.stderr, result.stdout)
        elif parse_failed:
            # Non-JSON success output is unusual but still safe to post as stdout.
            response = response
        elif not response and result.stderr:
            print(f"  [Claude Code stderr without result: {result.stderr[:500]!r}]")
            response = "Claude Code returned an error without a response. Check the bridge log for details."
        elif new_session_id:
            THREAD_SESSIONS[session_key] = new_session_id
            save_thread_sessions()
            print(f"  [Session tracked: {session_key} -> {new_session_id[:12]}...]")

        # Strip thinking tags from response
        response = re.sub(r'<thinking>.*?</thinking>\s*', '', response, flags=re.DOTALL)
        response = response.strip()

        if not response:
            print("  [Claude returned an empty result; treating as no-response]")
            return NO_RESPONSE_SENTINEL
        return response
    except subprocess.TimeoutExpired as e:
        # Try to read whatever stdout/stderr Claude Code emitted before the
        # process was killed — these often contain "rate_limit_error" /
        # "429" when the bridge timed out waiting on Anthropic retries
        # rather than on a genuinely long job.
        partial_out = (getattr(e, "stdout", None) or b"")
        partial_err = (getattr(e, "stderr", None) or b"")
        if isinstance(partial_out, bytes):
            partial_out = partial_out.decode("utf-8", errors="replace")
        if isinstance(partial_err, bytes):
            partial_err = partial_err.decode("utf-8", errors="replace")
        combined = (partial_out + "\n" + partial_err).lower()
        rate_limited = any(
            m in combined for m in
            ("rate_limit_error", "rate limit", "429", "overloaded", "anthropic-billing")
        )
        mins = _claude_timeout // 60
        if rate_limited:
            return (
                f"⏰ *Bridge timeout — Anthropic rate-limited during the run*\n\n"
                f"Claude Code burned the {mins}-min window retrying 429s. Caps are still down. "
                f"Try again after the live account's 5h window rolls — or switch live via "
                f"`claude_account_router.py route` if another account has headroom."
            )
        return (
            f"⏰ *Bridge timeout — task didn't finish in {mins} min*\n\n"
            f"Likely too big for one bridge call. Try splitting into smaller asks, or "
            f"run this directly in a Claude Code terminal session for tasks that need "
            f"more than {mins} min of model time."
        )
    except Exception as e:
        return f"Error running Claude Code: {str(e)[:200]}"


def run_claude_with_progress(web_client: WebClient, channel: str, thread_ts: str,
                              prompt: str, user_name: str, channel_name: str, user_id: str) -> tuple[str, str | None]:
    """Run Claude Code with a single progress message that gets edited in place.

    Pattern (Matt-approved option 3):
    1. Start Claude immediately but defer the visible "⏳ Working..." message.
       Fast replies should arrive as the first visible bot message instead of
       appearing as an edit.
    2. If Claude is still running after PROGRESS_DELAY_SECONDS, post a progress
       message with a rough ETA and update it every 15s.
    3. When Claude returns after a progress post, send the final response as a
       separate message. The progress note is only a long-job status update.

    Returns (response_text, progress_ts). The caller can use progress_ts to
    clean up no-response progress notes. Final responses are always sent fresh.
    """
    start_time = time.time()
    progress_ts = None

    response = None
    error = None
    done = Event()

    def run_claude():
        nonlocal response, error
        try:
            response = run_claude_code(prompt, user_name, channel_name, user_id,
                                       channel_id=channel, thread_ts=thread_ts)
        except Exception as e:
            error = str(e)
        finally:
            done.set()

    worker = Thread(target=run_claude, daemon=True)
    worker.start()

    if done.wait(PROGRESS_DELAY_SECONDS):
        worker.join(timeout=0)
        final_text = f"Error: {error}" if error else (response or NO_RESPONSE_SENTINEL)
        return final_text, None

    try:
        result = web_client.chat_postMessage(
            channel=channel,
            text=(
                "⏳ Still working on this. It has taken more than 20s; "
                "larger requests often take a few minutes. I'll follow up here when it's ready."
            ),
            thread_ts=thread_ts,
        )
        progress_ts = result["ts"]
    except Exception as e:
        print(f"Error posting progress message: {e}")

    while not done.wait(15):
        elapsed = int(time.time() - start_time)
        mins, secs = divmod(elapsed, 60)
        time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
        if progress_ts:
            try:
                web_client.chat_update(
                        channel=channel,
                        ts=progress_ts,
                        text=(
                            f"⏳ Still working on this ({time_str} elapsed). "
                            "Larger requests often take a few minutes; I'll follow up here when it's ready."
                        ),
                    )
            except Exception as e:
                print(f"Error updating progress: {e}")
    worker.join(timeout=0)

    final_text = f"Error: {error}" if error else (response or NO_RESPONSE_SENTINEL)
    return final_text, progress_ts


def finalize_progress_or_send(web_client: WebClient, channel: str, progress_ts: str | None,
                              text: str, thread_ts: str = None) -> str | None:
    """Send the final response.

    If a long-job progress message exists, leave it as status history and post
    the final answer as a separate message. Fast jobs have no progress message
    and also post exactly one final message.

    Returns the timestamp of the LAST message (for thread tracking). Phase F
    appends the confirmation footer before chunking; pending-action storage
    intentionally uses this returned ts so reactions on the footer-bearing final
    chunk resolve back to the payload.
    """
    return send_slack_response(web_client, channel, text, thread_ts)


def send_slack_response(web_client: WebClient, channel: str, text: str, thread_ts: str = None) -> str:
    """Send a response back to Slack. Returns the message timestamp."""
    try:
        # Slack has a 4000 char limit per message, split if needed
        max_len = 3900
        result_ts = None
        if len(text) <= max_len:
            result = web_client.chat_postMessage(
                channel=channel,
                text=text,
                thread_ts=thread_ts,
            )
            result_ts = result["ts"]
        else:
            # Split into chunks
            chunks = [text[i:i+max_len] for i in range(0, len(text), max_len)]
            for i, chunk in enumerate(chunks):
                prefix = f"({i+1}/{len(chunks)}) " if len(chunks) > 1 else ""
                result = web_client.chat_postMessage(
                    channel=channel,
                    text=prefix + chunk,
                    thread_ts=thread_ts,
                )
                if i == 0:
                    result_ts = result["ts"]

        # Track this thread if we posted to one
        if thread_ts and result_ts:
            ACTIVE_THREADS[thread_ts] = {"channel": channel, "last_response_ts": result_ts}

        return result_ts
    except Exception as e:
        print(f"Error sending Slack response: {e}")
        return None


def add_reaction(web_client: WebClient, channel: str, ts: str, emoji: str):
    """Add an emoji reaction to a message."""
    try:
        web_client.reactions_add(channel=channel, timestamp=ts, name=emoji)
    except Exception as e:
        # Ignore "already_reacted" errors
        if "already_reacted" not in str(e):
            print(f"Error adding reaction: {e}")


def remove_reaction(web_client: WebClient, channel: str, ts: str, emoji: str):
    """Remove an emoji reaction from a message."""
    try:
        web_client.reactions_remove(channel=channel, timestamp=ts, name=emoji)
    except Exception as e:
        # Ignore "no_reaction" errors
        if "no_reaction" not in str(e):
            print(f"Error removing reaction: {e}")


# --- Phase F: pending-action persistence + helpers ----------------------------

def load_pending_actions() -> dict:
    if not PENDING_ACTIONS_FILE.exists():
        return {"pending": {}}
    try:
        data = json.loads(PENDING_ACTIONS_FILE.read_text())
    except Exception:
        return {"pending": {}}
    if "pending" not in data:
        return {"pending": {}}
    return data


def save_pending_actions(data: dict) -> None:
    atomic_write_json(PENDING_ACTIONS_FILE, data, indent=2)


def mutate_pending_actions(mutator) -> dict:
    """Serialize pending-action read-modify-write in this bridge process."""
    with PENDING_ACTIONS_LOCK:
        data = load_pending_actions()
        mutator(data)
        save_pending_actions(data)
        return data


def purge_expired_pending() -> None:
    """Drop entries older than PENDING_TTL_SECONDS. Safety bias — never
    auto-execute a pending action just because TTL elapsed."""
    with PENDING_ACTIONS_LOCK:
        data = load_pending_actions()
        now = time.time()
        keep = {}
        for ts, entry in data["pending"].items():
            created = float(entry.get("created_at", 0))
            if now - created < PENDING_TTL_SECONDS:
                keep[ts] = entry
        if len(keep) != len(data["pending"]):
            data["pending"] = keep
            save_pending_actions(data)


def pending_action_expired(entry: dict) -> bool:
    """Return True when a pending action is past its confirmation TTL."""
    if "created_at" not in entry:
        return False
    try:
        created = float(entry.get("created_at", 0))
    except Exception:
        created = 0
    return time.time() - created >= PENDING_TTL_SECONDS


def extract_proposed_action(claude_text: str) -> tuple[dict | None, str]:
    """If `<proposed_action> ... </proposed_action>` block is present, parse it
    and return (payload_dict, cleaned_text_for_user). Otherwise (None, claude_text).

    Inside the block we accept either YAML-ish lines or a JSON object after
    `payload:`. Malformed explicit JSON is rejected instead of reinterpreted
    with different semantics.
    """
    if len(re.findall(r"<proposed_action\b", claude_text, re.I)) > 1:
        print("  [Phase F: multiple proposed_action blocks rejected; ask Claude to propose one action]")
        return None, (
            "I found multiple proposed actions in one response, so I did not queue any action. "
            "Please ask me to propose one action at a time."
        )
    m = re.search(r"<proposed_action>\s*(.+?)\s*</proposed_action>", claude_text, re.DOTALL)
    if not m:
        return None, claude_text
    block = m.group(1)
    cleaned = (claude_text[:m.start()] + claude_text[m.end():]).strip()

    payload: dict = {}
    # Pull `kind: ...` and any `payload: { ... }` JSON
    kind_match = re.search(r"^\s*kind\s*:\s*([\w_]+)", block, re.MULTILINE)
    if kind_match:
        payload["kind"] = kind_match.group(1)
    payload_marker = re.search(r"payload\s*:", block)
    if payload_marker:
        payload_text = block[payload_marker.end():].lstrip()
        try:
            decoded, _ = json.JSONDecoder().raw_decode(payload_text)
            if not isinstance(decoded, dict):
                print(f"  [Phase F: proposed_action payload is not an object; payload={decoded!r}]")
                return None, claude_text
            payload.update(decoded)
        except json.JSONDecodeError as exc:
            print(f"  [Phase F: malformed proposed_action payload JSON: {exc}; block={block[:500]!r}]")
            return None, claude_text
    # Fallback: parse simple key:value lines outside payload JSON
    if "kind" in payload and len(payload) == 1:
        for line in block.splitlines():
            kv = re.match(r"^\s*([\w_]+)\s*:\s*(.+?)\s*$", line)
            if kv and kv.group(1) not in {"kind", "payload"}:
                payload[kv.group(1)] = kv.group(2).strip().strip("\"'")
    if "kind" not in payload:
        return None, claude_text  # malformed block — fall back to raw
    if payload["kind"] not in ALLOWED_ACTION_KINDS:
        print(f"  [Phase F: unknown proposed_action kind {payload['kind']!r}; falling back to raw]")
        return None, claude_text
    valid, error = validate_proposal_payload(payload["kind"], payload)
    if not valid:
        print(f"  [Phase F: invalid proposed_action payload: {error}; payload={payload!r}]")
        return None, claude_text
    return payload, cleaned or "(proposal posted with no summary — react ✅ to confirm or ❌ to cancel)"


def validate_proposal_payload(kind: str, payload: dict) -> tuple[bool, str | None]:
    """Validate the bridge-owned proposal contract before persistence."""
    required = PROPOSAL_REQUIRED_FIELDS.get(kind)
    if required is None:
        return False, f"unknown kind {kind}"
    missing = sorted(field for field in required if not str(payload.get(field, "")).strip())
    if missing:
        return False, f"missing required field(s): {', '.join(missing)}"
    return True, None


# Pre-Claude text grammar for confirming/cancelling a pending action
TEXT_CONFIRM_RE = re.compile(r"^\s*(yes|y|do it|ship it|confirm|go|send|approved?)\b", re.I)
TEXT_CANCEL_RE  = re.compile(r"^\s*(no|n|cancel|drop|nope|skip|stop)\b", re.I)
TEXT_EDIT_RE    = re.compile(r"^\s*(edit|change|revise|update|modify)\b", re.I)
TEXT_SNOOZE_RE  = re.compile(r"^\s*snooze(?:\s+(\d+)\s*d?)?\b", re.I)


def set_pending_action_status(ack_ts: str, status: str, **updates) -> None:
    def mutator(data):
        if ack_ts in data["pending"]:
            data["pending"][ack_ts]["status"] = status
            data["pending"][ack_ts].update(updates)

    mutate_pending_actions(mutator)


def claim_pending_action(ack_ts: str, decision: str) -> bool:
    """Atomically claim an open pending action before any external dispatch."""
    claimed = False

    def mutator(data):
        nonlocal claimed
        entry = data["pending"].get(ack_ts)
        if not entry or entry.get("status") != "open":
            return
        if pending_action_expired(entry):
            entry["status"] = "expired"
            entry["expired_at"] = time.time()
            return
        entry["status"] = "dispatching" if decision in {"confirm", "snooze"} else decision
        claimed = True

    mutate_pending_actions(mutator)
    return claimed


def append_dispatch_audit(record: dict) -> None:
    """Append a redacted dispatch audit record without storing full payload PII."""
    try:
        record = {"ts": datetime.now().isoformat(), **record}
        with open(DISPATCH_AUDIT_FILE, "a") as f:
            f.write(json.dumps(record, sort_keys=True) + "\n")
    except Exception as exc:
        print(f"  [Phase F: dispatch audit write failed: {exc}]")


def hash_dispatch_payload(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def dispatch_action(payload: dict, dry_run: bool = False, *, ack_ts: str | None = None,
                    user: str | None = None) -> dict:
    """Shell out to dm_dispatch.py to execute. Avoids importing across roots.

    This is synchronous by design for low-volume FM DMs; Socket Mode is already
    acked before this runs, so Slack retries are not blocked.
    """
    start = time.time()
    result = {"ok": False, "error": "unknown"}
    cmd = [
        sys.executable, str(DM_DISPATCH_PATH),
        "--kind", payload.get("kind", "unknown"),
        "--payload", json.dumps({k: v for k, v in payload.items() if k != "kind"}),
    ]
    if dry_run:
        cmd.append("--dry-run")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
        result = json.loads(res.stdout) if res.stdout.strip() else {"ok": False, "error": "no output"}
        if not isinstance(result, dict):
            result = {"ok": False, "error": "dispatch returned non-object JSON"}
    except Exception as exc:
        result = {"ok": False, "error": str(exc)[:200]}
    finally:
        append_dispatch_audit({
            "ack_ts": ack_ts,
            "user": user,
            "kind": payload.get("kind", "unknown"),
            "payload_hash": hash_dispatch_payload(payload),
            "dry_run": dry_run,
            "ok": bool(result.get("ok")),
            "error": result.get("error"),
            "summary": result.get("summary"),
            "duration_ms": int((time.time() - start) * 1000),
        })
    return result


def update_promise_status(promise_id: str, action: str, days: int = 3) -> dict:
    """Update promise_state.json without going through dm_dispatch (used for
    promise_sweep_announcement reactions where the bridge already knows the id)."""
    if action not in {"snooze", "clear"}:
        return {"ok": False, "error": f"unknown promise action: {action}"}
    payload = {"promise_id": promise_id}
    kind = "snooze_promise" if action == "snooze" else "clear_promise"
    if kind == "snooze_promise":
        payload["days"] = days
    payload["kind"] = kind
    return dispatch_action(payload)


def claim_promise_action(promise_id: str, action: str) -> bool:
    """Claim an in-flight promise action so double reactions do not dispatch twice."""
    key = (promise_id, action)
    with PROMISE_ACTION_LOCK:
        if key in ACTIVE_PROMISE_ACTIONS:
            return False
        ACTIVE_PROMISE_ACTIONS.add(key)
        return True


def release_promise_action(promise_id: str, action: str) -> None:
    with PROMISE_ACTION_LOCK:
        ACTIVE_PROMISE_ACTIONS.discard((promise_id, action))


def handle_confirmation(web_client: WebClient, channel: str, ack_ts: str,
                         pending_entry: dict, decision: str, source_ts: str = None,
                         snooze_days: int = 3) -> None:
    """Resolve a pending proposed_action.

    decision: confirm | cancel | edit | snooze
    `source_ts` is the ts of the user's confirming message (text path) or
    the reaction event (reaction path) — used for thread reply context.
    """
    payload = pending_entry.get("payload") or {}
    kind = payload.get("kind", "?")

    if not claim_pending_action(ack_ts, decision):
        web_client.chat_postMessage(channel=channel, thread_ts=ack_ts,
                                     text="_Already handled or expired._")
        return

    if decision == "cancel":
        web_client.chat_postMessage(channel=channel, thread_ts=ack_ts,
                                     text=f"_Cancelled — no `{kind}` action taken._")
        return
    if decision == "edit":
        web_client.chat_postMessage(channel=channel, thread_ts=ack_ts,
                                     text=f"_OK — send your revision and I'll re-propose._")
        return
    if decision == "snooze":
        # Snooze applies if this was a promise-related proposal; otherwise just dismiss
        promise_id = payload.get("promise_id")
        if promise_id:
            result = update_promise_status(promise_id, "snooze", days=snooze_days)
            if result.get("ok"):
                set_pending_action_status(ack_ts, "snooze")
                web_client.chat_postMessage(channel=channel, thread_ts=ack_ts,
                                             text=f"_Snoozed {snooze_days}d — {result.get('summary', 'ok')}._")
            else:
                set_pending_action_status(ack_ts, "open", last_error=result.get("error", "unknown"))
                web_client.chat_postMessage(channel=channel, thread_ts=ack_ts,
                                             text=f"❌ Snooze failed: {result.get('error', 'unknown')}. Still open; react again to retry.")
        else:
            set_pending_action_status(ack_ts, "snooze")
            web_client.chat_postMessage(channel=channel, thread_ts=ack_ts,
                                         text=f"_Dismissed — no promise to snooze._")
        return
    # confirm
    print(f"  [Phase F: dispatching {kind} payload={payload}]")
    result = dispatch_action(payload, ack_ts=ack_ts, user=pending_entry.get("user"))
    if result.get("ok"):
        set_pending_action_status(ack_ts, "confirm")
        web_client.chat_postMessage(channel=channel, thread_ts=ack_ts,
                                     text=f"✅ {result.get('summary', 'done')}")
    else:
        set_pending_action_status(ack_ts, "open", last_error=result.get("error", "unknown"))
        web_client.chat_postMessage(channel=channel, thread_ts=ack_ts,
                                     text=f"❌ Dispatch failed: {result.get('error', 'unknown')}. Still open; react again to retry.")


def get_message_metadata(web_client: WebClient, channel: str, ts: str) -> dict:
    """Read a single message's metadata (used to detect promise_sweep announcements)."""
    try:
        res = web_client.conversations_history(channel=channel, latest=ts, inclusive=True, limit=1)
        msgs = res.get("messages") or []
        if msgs:
            return msgs[0].get("metadata") or {}
    except Exception:
        pass
    return {}


def handle_reaction_event(web_client: WebClient, event: dict) -> None:
    """Resolve a reaction on a pending action OR a promise_sweep announcement."""
    user = event.get("user")
    if not is_allowed_user(user):
        return
    item = event.get("item") or {}
    if item.get("type") != "message":
        return
    channel = item.get("channel")
    ts = item.get("ts")
    reaction = event.get("reaction") or ""

    # Categorize reaction
    if reaction in REACTION_CONFIRM:
        decision = "confirm"
    elif reaction in REACTION_CANCEL:
        decision = "cancel"
    elif reaction in REACTION_EDIT:
        decision = "edit"
    elif reaction in REACTION_SNOOZE:
        decision = "snooze"
    else:
        return  # not a recognized signal

    # 1. Look up in pending_actions
    purge_expired_pending()
    data = load_pending_actions()
    if ts in data["pending"] and data["pending"][ts].get("status") == "open":
        handle_confirmation(web_client, channel, ts, data["pending"][ts], decision, ts)
        return

    # 2. Check for promise_sweep_announcement metadata
    meta = get_message_metadata(web_client, channel, ts)
    if meta.get("event_type") == "promise_sweep_announcement":
        promise_id = (meta.get("event_payload") or {}).get("promise_id")
        if not promise_id:
            return
        if decision == "confirm":
            if not claim_promise_action(promise_id, "clear"):
                web_client.chat_postMessage(channel=channel, thread_ts=ts,
                                             text="_Already handling this promise action._")
                return
            try:
                result = update_promise_status(promise_id, "clear")
                web_client.chat_postMessage(channel=channel, thread_ts=ts,
                                             text=f"✅ {result.get('summary', 'cleared')}")
            finally:
                release_promise_action(promise_id, "clear")
        elif decision == "snooze":
            if not claim_promise_action(promise_id, "snooze"):
                web_client.chat_postMessage(channel=channel, thread_ts=ts,
                                             text="_Already handling this promise action._")
                return
            try:
                result = update_promise_status(promise_id, "snooze", days=3)
                web_client.chat_postMessage(channel=channel, thread_ts=ts,
                                             text=f"💤 {result.get('summary', 'snoozed 3d')}")
            finally:
                release_promise_action(promise_id, "snooze")
        elif decision == "cancel":
            web_client.chat_postMessage(channel=channel, thread_ts=ts,
                                         text="❌ OK — keeping this promise open.")
        return


def is_no_response(response_text: str) -> bool:
    """Check if Claude chose not to respond.

    The sentinel must be the entire reply; a response that starts with the
    sentinel and then includes prose is still user-visible content.
    """
    stripped = response_text.strip()
    return stripped == NO_RESPONSE_SENTINEL


def prompt_explicitly_requests_scalar(prompt: str) -> bool:
    """Return True when a terse scalar could be the user's requested answer."""
    normalized = " ".join((prompt or "").lower().split())
    if not normalized:
        return False
    scalar_patterns = [
        r"\bhow many\b",
        r"\bcount\b",
        r"\bcalculate\b",
        r"\bcompute\b",
        r"\bwhat(?:'s| is)\b.*\b(number|count|total|sum|result|answer)\b",
        r"\brespond with\b",
        r"\breply with\b",
        r"\bsay\b.*\bonly\b",
    ]
    return any(re.search(pattern, normalized) for pattern in scalar_patterns)


def is_trivial_noise_response(response_text: str, prompt: str) -> bool:
    """Suppress no-op Slack clutter like a final edited message containing only `4`."""
    stripped = response_text.strip().strip("`")
    if not stripped or is_no_response(stripped):
        return False
    normalized = stripped.lower().rstrip(".!").strip()
    bare_ack = {
        "ok", "okay", "done", "ack", "acknowledged", "got it",
        "thanks", "thank you", "👍", "✅",
    }
    if normalized in bare_ack:
        return not prompt_explicitly_requests_scalar(prompt)
    if re.fullmatch(r"\d+", normalized):
        return not prompt_explicitly_requests_scalar(prompt)
    return False


def is_allowed_user(user: str) -> bool:
    """Return True only for explicitly allowed users; empty allowlist denies all."""
    return bool(ALLOWED_USERS) and user in ALLOWED_USERS


def allow_claude_invocation(user: str) -> tuple[bool, int]:
    """In-memory per-user rate limit for Slack-triggered Claude runs."""
    with CLAUDE_RATE_LOCK:
        now = time.time()
        history = CLAUDE_INVOCATION_LOG.setdefault(user or "unknown", [])
        history[:] = [ts for ts in history if now - ts < CLAUDE_RATE_HOUR_SECONDS]
        recent = [ts for ts in history if now - ts < CLAUDE_RATE_WINDOW_SECONDS]
        if len(recent) >= CLAUDE_RATE_MAX_PER_WINDOW:
            retry_after = int(CLAUDE_RATE_WINDOW_SECONDS - (now - min(recent)))
            return False, max(1, retry_after)
        if len(history) >= CLAUDE_RATE_MAX_PER_HOUR:
            retry_after = int(CLAUDE_RATE_HOUR_SECONDS - (now - min(history)))
            return False, max(1, retry_after)
        history.append(now)
        return True, 0


def is_self_note_message(text: str) -> bool:
    """Return True when a DM is clearly meant only as a personal scratchpad."""
    normalized = " ".join((text or "").split())
    if not normalized:
        return False
    return any(pattern.search(normalized) for pattern in SELF_NOTE_PATTERNS)


def format_claude_failure(returncode: int, stderr: str, stdout: str = "") -> str:
    """Convert Claude Code process failures into Slack-safe user messages."""
    if returncode == 0:
        raise ValueError("format_claude_failure should only be called for non-zero exits")
    detail = (stderr or stdout or "").strip()
    if returncode < 0:
        try:
            signal_name = signal.Signals(-returncode).name
        except ValueError:
            signal_name = f"signal {-returncode}"
        print(f"  [Claude Code terminated by {signal_name}; output={detail[:500]!r}]")
        if signal_name == "SIGKILL":
            return (
                "Claude Code was killed by the OS before it could finish. "
                "This is usually memory pressure or an external process cleanup, not a problem with your message."
            )
        return f"Claude Code was interrupted by {signal_name} before it could finish."

    if detail:
        print(f"  [Claude Code exited with status {returncode}; output={detail[:500]!r}]")
    return f"Claude Code exited with status {returncode}."


def should_respond_to_thread_reply(text: str, user_name: str) -> bool:
    """Decide whether to respond to a thread reply or just acknowledge it.

    Returns True if we should respond, False if we should just ack.
    Default to responding - only ack for clear "end of conversation" signals.
    """
    lower = text.lower().strip()

    # Only ACK (don't respond) for clear conversation-ending signals
    ack_only = [
        "thanks", "thank you", "thx", "ty", "cool", "nice", "great",
        "got it", "perfect", "awesome", "ok thanks", "okay thanks",
        "👍", "🙏", "✅"
    ]
    for signal in ack_only:
        if lower == signal or lower.rstrip("!.") == signal:
            return False

    # Respond to everything else in tracked threads
    return True


def load_pending_work():
    """Load pending work from file."""
    global PENDING_WORK
    if PENDING_WORK_FILE.exists():
        try:
            with open(PENDING_WORK_FILE) as f:
                data = json.load(f)
                # Convert string keys back to tuples
                PENDING_WORK = {tuple(k.split("|")): v for k, v in data.items()}
                print(f"[STARTUP] Loaded {len(PENDING_WORK)} pending work items")
        except Exception as e:
            print(f"[STARTUP] Error loading pending work: {e}")
            PENDING_WORK = {}


def save_pending_work():
    """Save pending work to file."""
    try:
        # Convert tuple keys to strings for JSON
        data = {f"{k[0]}|{k[1]}": v for k, v in PENDING_WORK.items()}
        atomic_write_json(PENDING_WORK_FILE, data)
    except Exception as e:
        print(f"[ERROR] Failed to save pending work: {e}")


def mark_work_started(channel: str, ts: str, text: str, user_id: str, thread_ts: str = None):
    """Track that we've started working on a message."""
    PENDING_WORK[(channel, ts)] = {
        "start_time": time.time(),
        "text": text,
        "user_id": user_id,
        "thread_ts": thread_ts,
        "channel": channel,
    }
    save_pending_work()


def mark_work_completed(channel: str, ts: str):
    """Mark work as completed (remove from pending)."""
    PENDING_WORK.pop((channel, ts), None)
    save_pending_work()


def cleanup_stuck_work(web_client: WebClient):
    """Check for and clean up stuck work items. Retries once before marking as error."""
    now = time.time()
    stuck_items = []

    for (channel, ts), info in list(PENDING_WORK.items()):
        elapsed = now - info["start_time"]
        if elapsed > WORK_TIMEOUT:
            stuck_items.append((channel, ts, info))

    for channel, ts, info in stuck_items:
        retry_count = info.get("retry_count", 0)

        if retry_count == 0:
            # First timeout - retry
            print(f"\n[CLEANUP] Retrying stuck work item: {info['text'][:50]}... (waited {WORK_TIMEOUT}s)")
            info["retry_count"] = 1
            info["start_time"] = time.time()  # Reset timer for retry
            save_pending_work()

            # Add retry emoji to show we're working on it
            add_reaction(web_client, channel, ts, EMOJI_RETRY)

            # Try to process again
            try:
                user_id = info.get("user_id", "unknown")
                thread_ts = info.get("thread_ts")
                reply_to_thread = thread_ts or ts

                response_text = run_claude_code(info["text"], user_id, channel, user_id,
                                                channel_id=channel, thread_ts=reply_to_thread)

                # Success - send response
                reply_to_thread = thread_ts or ts
                send_slack_response(web_client, channel, response_text, reply_to_thread)

                # Mark complete - remove working and retry emojis, add done
                remove_reaction(web_client, channel, ts, EMOJI_WORKING)
                remove_reaction(web_client, channel, ts, EMOJI_RETRY)
                add_reaction(web_client, channel, ts, EMOJI_DONE)
                mark_work_completed(channel, ts)
                print(f"[CLEANUP] Retry successful!")

            except Exception as e:
                print(f"[CLEANUP] Retry failed: {e}")
                # Remove retry emoji, will be caught on next cleanup cycle as retry_count=1
                remove_reaction(web_client, channel, ts, EMOJI_RETRY)
        else:
            # Already retried - give up
            print(f"\n[CLEANUP] Giving up on stuck work item after retry: {info['text'][:50]}...")
            remove_reaction(web_client, channel, ts, EMOJI_WORKING)
            remove_reaction(web_client, channel, ts, EMOJI_RETRY)
            add_reaction(web_client, channel, ts, EMOJI_ERROR)
            mark_work_completed(channel, ts)

            # Notify in thread
            try:
                thread = info.get("thread_ts") or ts
                web_client.chat_postMessage(
                    channel=channel,
                    text="Sorry, that request failed after retrying. Please try again later.",
                    thread_ts=thread,
                )
            except Exception as e:
                print(f"[CLEANUP] Error sending failure message: {e}")


def run_cleanup_loop(web_client: WebClient, stop_event: Event, health_context: dict | None = None):
    """Periodically check for stuck work items."""
    while not stop_event.is_set():
        try:
            cleanup_stuck_work(web_client)
            if health_context is not None:
                write_bridge_health(**health_context, last_cleanup_at=datetime.now().isoformat())
        except Exception as e:
            print(f"[CLEANUP] Error in cleanup loop: {e}")
        # Check every 5 minutes
        stop_event.wait(CLEANUP_INTERVAL)


def is_claude_work(label: str, func) -> bool:
    return func is process_claude_work or label.endswith("_claude") or "claude" in label


def notify_bridge_busy(label: str, func, args) -> None:
    """Post a visible busy response when a bounded worker queue is full."""
    try:
        if func is process_claude_work and len(args) >= 3:
            web_client, channel, ts = args[0], args[1], args[2]
            web_client.chat_postMessage(
                channel=channel,
                thread_ts=ts,
                text="I'm at capacity on Slack-triggered Claude work. Please try again in a minute.",
            )
            remove_reaction(web_client, channel, ts, EMOJI_WORKING)
            add_reaction(web_client, channel, ts, EMOJI_ERROR)
            mark_work_completed(channel, ts)
            return
        if func is handle_confirmation and len(args) >= 3:
            web_client, channel, ack_ts = args[0], args[1], args[2]
            web_client.chat_postMessage(
                channel=channel,
                thread_ts=ack_ts,
                text="I'm at capacity handling Slack actions. Please react or reply again in a minute.",
            )
            return
        if func is handle_reaction_event and len(args) >= 2:
            web_client, event = args[0], args[1]
            item = event.get("item") or {}
            channel, ts = item.get("channel"), item.get("ts")
            if channel and ts:
                web_client.chat_postMessage(
                    channel=channel,
                    thread_ts=ts,
                    text="I'm at capacity handling Slack reactions. Please try again in a minute.",
                )
    except Exception as exc:
        print(f"[WORKER:{label}] failed to post busy message: {exc}")


def submit_bridge_work(label: str, func, *args, **kwargs) -> None:
    """Run Slack work off the listener thread with separate bounded pools."""
    if is_claude_work(label, func):
        executor, slots = CLAUDE_WORKERS, CLAUDE_WORK_SLOTS
    else:
        executor, slots = DISPATCH_WORKERS, DISPATCH_WORK_SLOTS

    if not slots.acquire(blocking=False):
        print(f"[WORKER:{label}] queue full; rejecting work")
        notify_bridge_busy(label, func, args)
        return

    future = executor.submit(func, *args, **kwargs)

    def done_callback(done):
        try:
            done.result()
        except Exception as exc:
            print(f"[WORKER:{label}] failed: {exc}")
        finally:
            slots.release()

    future.add_done_callback(done_callback)


def process_claude_work(web_client: WebClient, channel: str, ts: str, prompt: str,
                        user: str, user_name: str, channel_name: str,
                        thread_ts: str | None, reply_thread_ts: str | None,
                        is_dm: bool, proposal_enabled: bool,
                        track_thread_parent: str | None) -> None:
    """Run Claude and post/update Slack responses from a bounded worker."""
    try:
        print(f"  [Auto-responding via Claude Code...]")
        response_text, progress_ts = run_claude_with_progress(
            web_client, channel, reply_thread_ts,
            prompt, user_name, channel_name, user
        )
        print(f"  Response: {response_text[:100]}{'...' if len(response_text) > 100 else ''}")

        if is_trivial_noise_response(response_text, prompt):
            print(f"  [Claude returned trivial no-op response {response_text!r}; treating as no-response]")
            response_text = NO_RESPONSE_SENTINEL

        if is_no_response(response_text):
            print(f"  [Claude chose not to respond - skipping]")
            if progress_ts:
                try:
                    web_client.chat_delete(channel=channel, ts=progress_ts)
                except Exception as e:
                    print(f"  chat_delete failed: {e}")
                    try:
                        web_client.chat_update(channel=channel, ts=progress_ts, text="_(no response needed)_")
                    except Exception as update_exc:
                        print(f"  chat_update fallback failed: {update_exc}")
            remove_reaction(web_client, channel, ts, EMOJI_WORKING)
            mark_work_completed(channel, ts)
            return

        proposal_payload = None
        if proposal_enabled:
            proposal_payload, response_text = extract_proposed_action(response_text)
            if proposal_payload:
                response_text = (
                    response_text + "\n\n_React ✅ to confirm · ❌ to cancel · ✏️ to edit, "
                    "or reply in this thread with 'yes' / 'no' / 'edit' / 'snooze'._"
                )

        response_ts = finalize_progress_or_send(
            web_client, channel, progress_ts, response_text, reply_thread_ts
        )

        if proposal_payload and response_ts:
            def mutator(data):
                data["pending"][response_ts] = {
                    "created_at": time.time(),
                    "channel": channel,
                    "trigger_msg_ts": ts,
                    "user": user,
                    "payload": proposal_payload,
                    "status": "open",
                }

            mutate_pending_actions(mutator)
            print(f"  [Phase F: stored pending action ts={response_ts} kind={proposal_payload.get('kind')}]")

        remove_reaction(web_client, channel, ts, EMOJI_WORKING)
        add_reaction(web_client, channel, ts, EMOJI_DONE)
        mark_work_completed(channel, ts)

        if response_ts and track_thread_parent:
            parent = response_ts if track_thread_parent == "response_ts" else track_thread_parent
            ACTIVE_THREADS[parent] = {"channel": channel, "last_response_ts": response_ts}
    except Exception as exc:
        print(f"  [Claude worker failed: {exc}]")
        remove_reaction(web_client, channel, ts, EMOJI_WORKING)
        add_reaction(web_client, channel, ts, EMOJI_ERROR)
        mark_work_completed(channel, ts)


def handle_message(client: SocketModeClient, req: SocketModeRequest, web_client: WebClient):
    """Handle incoming message events."""
    if req.type == "events_api":
        # Acknowledge the request immediately
        response = SocketModeResponse(envelope_id=req.envelope_id)
        client.send_socket_mode_response(response)

        event = req.payload.get("event", {})
        event_type = event.get("type")

        if event_type == "reaction_added" and not is_allowed_user(event.get("user")):
            return

        if not claim_slack_event(req, event):
            return

        # --- Phase F: reaction events on FM DM proposals + promise_sweep posts -
        if event_type == "reaction_added":
            submit_bridge_work("reaction_added", handle_reaction_event, web_client, event)
            return

        # Handle DMs and thread replies ONLY (not all channel messages)
        # @mentions are handled separately by app_mention event
        if event_type == "message" and "subtype" not in event:
            # Skip bot's own messages
            if event.get("bot_id"):
                return

            channel = event.get("channel")
            user = event.get("user")
            text = event.get("text", "")
            ts = event.get("ts")
            thread_ts = event.get("thread_ts")

            # Check if user is allowed before Slack lookups or inbox writes
            if not is_allowed_user(user):
                print(f"  [User {user} not in allowed list, ignoring]")
                return

            # Check if this is a DM (channel starts with D)
            is_dm = channel.startswith("D")

            # Check if this is a reply to a thread we're tracking
            is_tracked_thread_reply = thread_ts and thread_ts in ACTIVE_THREADS

            # IMPORTANT: Only process DMs and tracked thread replies
            # Ignore all other channel messages (those come via app_mention if directed at us)
            if not is_dm and not is_tracked_thread_reply:
                return

            # Get user info if possible
            user_name = user
            try:
                user_info = web_client.users_info(user=user)
                user_name = user_info["user"].get("real_name") or user_info["user"].get("name") or user
            except Exception:
                pass

            # Get channel info
            channel_name = channel
            try:
                if is_dm:
                    channel_name = f"DM:{user_name}"
                else:
                    channel_info = web_client.conversations_info(channel=channel)
                    channel_name = f"#{channel_info['channel']['name']}"
            except Exception:
                pass

            inbox_msg = {
                "type": "thread_reply" if is_tracked_thread_reply else "dm",
                "channel_id": channel,
                "channel": channel_name,
                "user_id": user,
                "user": user_name,
                "text": text,
                "ts": ts,
                "thread_ts": thread_ts,
            }

            write_to_inbox(inbox_msg)

            # Print to console
            print(f"\n{'='*60}")
            msg_type = "Thread reply" if is_tracked_thread_reply else "DM"
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg_type} from {user_name} in {channel_name}")
            print(f"  {text}")

            # Auto-respond if enabled
            if AUTO_RESPOND:
                # For thread replies, decide if we should respond or just ack
                if is_tracked_thread_reply and not should_respond_to_thread_reply(text, user_name):
                    print(f"  [Thread reply - acknowledging without response]")
                    add_reaction(web_client, channel, ts, EMOJI_ACK)
                    print(f"{'='*60}\n")
                    return

                if is_dm and is_self_note_message(text):
                    print("  [DM scratchpad note - logging without Claude response]")
                    add_reaction(web_client, channel, ts, EMOJI_ACK)
                    print(f"{'='*60}\n")
                    return

                # --- Phase F: pre-Claude text-grammar confirmation -----------
                # If this DM has an active pending action, check yes/no/edit/snooze
                # grammar BEFORE forwarding to Claude. Avoids round-tripping through
                # the LLM for a 1-token confirmation.
                if is_dm and channel == FM_DM_CHANNEL:
                    purge_expired_pending()
                    pending = load_pending_actions().get("pending", {})
                    # Find the most recent pending in this channel (single-DM context)
                    active = [(k, v) for k, v in pending.items() if v.get("channel") == channel and v.get("status") == "open"]
                    active.sort(key=lambda kv: float(kv[1].get("created_at", 0)), reverse=True)
                    if active and thread_ts == active[0][0]:
                        ack_ts, entry = active[0]
                        decision, days = None, 3
                        if TEXT_CONFIRM_RE.match(text):
                            decision = "confirm"
                        elif TEXT_CANCEL_RE.match(text):
                            decision = "cancel"
                        elif TEXT_EDIT_RE.match(text):
                            decision = "edit"
                        elif TEXT_SNOOZE_RE.match(text):
                            decision = "snooze"
                            sm = TEXT_SNOOZE_RE.match(text)
                            if sm and sm.group(1):
                                days = int(sm.group(1))
                        if decision:
                            print(f"  [Phase F: text-grammar match → {decision} on pending {ack_ts}]")
                            submit_bridge_work(
                                "text_confirmation",
                                handle_confirmation,
                                web_client,
                                channel,
                                ack_ts,
                                entry,
                                decision,
                                ts,
                                snooze_days=days,
                            )
                            print(f"{'='*60}\n")
                            return
                    elif active:
                        print("  [Phase F: pending action exists; text confirmation ignored outside proposal thread]")

                allowed_run, retry_after = allow_claude_invocation(user)
                if not allowed_run:
                    print(f"  [Rate limit hit for {user}; retry after {retry_after}s]")
                    add_reaction(web_client, channel, ts, EMOJI_ERROR)
                    web_client.chat_postMessage(
                        channel=channel,
                        thread_ts=thread_ts or ts,
                        text=f"Rate limit hit for Slack-triggered Claude runs. Try again in about {retry_after}s.",
                    )
                    print(f"{'='*60}\n")
                    return

                # Add working emoji and track pending work
                add_reaction(web_client, channel, ts, EMOJI_WORKING)
                mark_work_started(channel, ts, text, user, thread_ts)

                # Reply in thread if this was a thread reply, otherwise in channel.
                # For DMs, always preserve thread_ts — cron-initiated threads and
                # post-restart threads aren't in ACTIVE_THREADS but the user is
                # clearly continuing a thread, so honor it.
                if is_dm and thread_ts:
                    reply_thread_ts = thread_ts
                else:
                    reply_thread_ts = thread_ts if is_tracked_thread_reply else None

                track_thread_parent = None if reply_thread_ts else "response_ts"
                submit_bridge_work(
                    "message_claude",
                    process_claude_work,
                    web_client,
                    channel,
                    ts,
                    text,
                    user,
                    user_name,
                    channel_name,
                    thread_ts,
                    reply_thread_ts,
                    is_dm,
                    is_dm and channel == FM_DM_CHANNEL,
                    track_thread_parent,
                )
            else:
                print(f"  Reply: python slack_bridge.py --reply {channel} {ts} \"your message\"")

            print(f"{'='*60}\n")

        elif event_type == "app_mention":
            channel = event.get("channel")
            user = event.get("user")
            text = event.get("text", "")
            ts = event.get("ts")
            thread_ts = event.get("thread_ts")  # Will be set if mention is in a thread

            # Check if user is allowed before Slack lookups or inbox writes
            if not is_allowed_user(user):
                print(f"  [User {user} not in allowed list, rejecting]")
                add_reaction(web_client, channel, ts, "no_entry")
                return

            # Get user name
            user_name = user
            try:
                user_info = web_client.users_info(user=user)
                user_name = user_info["user"].get("real_name") or user_info["user"].get("name") or user
            except Exception:
                pass

            # Get channel name
            channel_name = channel
            try:
                channel_info = web_client.conversations_info(channel=channel)
                channel_name = f"#{channel_info['channel']['name']}"
            except Exception:
                pass

            # Strip the @mention from the text
            clean_text = text.split(">", 1)[-1].strip() if ">" in text else text

            inbox_msg = {
                "type": "mention",
                "channel_id": channel,
                "channel": channel_name,
                "user_id": user,
                "user": user_name,
                "text": clean_text,
                "ts": ts,
                "thread_ts": thread_ts,
            }

            write_to_inbox(inbox_msg)

            print(f"\n{'='*60}")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Mentioned by {user_name} in {channel_name}")
            print(f"  {clean_text}")

            # Auto-respond if enabled
            if AUTO_RESPOND and clean_text:
                allowed_run, retry_after = allow_claude_invocation(user)
                if not allowed_run:
                    print(f"  [Rate limit hit for {user}; retry after {retry_after}s]")
                    add_reaction(web_client, channel, ts, EMOJI_ERROR)
                    web_client.chat_postMessage(
                        channel=channel,
                        thread_ts=thread_ts or ts,
                        text=f"Rate limit hit for Slack-triggered Claude runs. Try again in about {retry_after}s.",
                    )
                    print(f"{'='*60}\n")
                    return

                # Add working emoji and track pending work
                add_reaction(web_client, channel, ts, EMOJI_WORKING)
                mark_work_started(channel, ts, clean_text, user, thread_ts)

                # If mention is in a thread, respond in that thread
                # Otherwise start a new thread from the mention
                reply_to_thread = thread_ts or ts

                submit_bridge_work(
                    "mention_claude",
                    process_claude_work,
                    web_client,
                    channel,
                    ts,
                    clean_text,
                    user,
                    user_name,
                    channel_name,
                    thread_ts,
                    reply_to_thread,
                    False,
                    False,
                    thread_ts or ts,
                )

            print(f"{'='*60}\n")


def _default_workdir(work_dir):
    """Resolve the bridge's working dir. An explicit --workdir wins; otherwise the CANONICAL
    vault via vault_path.vault_root() — NEVER os.getcwd(). A stale launch cwd (the retired
    iCloud vault) silently captured all bridge output for ~2 days before this fix. (2026-07-02.)"""
    if work_dir:
        return work_dir
    try:
        _lib = str(Path.home() / ".config" / "zerg" / "lib")
        if _lib not in sys.path:
            sys.path.insert(0, _lib)
        from vault_path import vault_root
        return str(vault_root())
    except Exception:
        return os.getcwd()


def run_bridge(workspace: str = "default", auto_respond: bool = False, work_dir: str = None):
    """Run the Socket Mode bridge."""
    global AUTO_RESPOND, WORK_DIR
    AUTO_RESPOND = auto_respond
    WORK_DIR = _default_workdir(work_dir)
    started_at = datetime.now().isoformat()

    claim_pid_file()
    apply_workspace_settings(workspace)

    # Load any pending work and thread sessions from previous session
    load_pending_work()
    load_thread_sessions()

    bot_token, app_token = get_tokens(workspace)

    if not app_token:
        print("Error: No app_token found in config. Add your xapp- token.")
        sys.exit(1)
    if not bot_token:
        print("Error: No bot token found in config. Add your xoxb- token.")
        sys.exit(1)

    web_client = WebClient(token=bot_token)
    try:
        auth = web_client.auth_test()
        if not auth.get("ok", False):
            print(f"Error: bot_token auth failed: {auth.get('error', 'unknown error')}")
            sys.exit(1)
    except SlackApiError as e:
        error = "unknown error"
        try:
            error = e.response.get("error") or error
        except Exception:
            pass
        print(f"Error: bot_token auth failed: {error}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: bot_token auth failed: {e}")
        sys.exit(1)

    app_client = WebClient(token=app_token)
    try:
        app_client.apps_connections_open(app_token=app_token)
    except SlackApiError as e:
        error = "unknown error"
        try:
            error = e.response.get("error") or error
        except Exception:
            pass
        print(f"Error: app_token socket connection validation failed: {error}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: app_token socket connection validation failed: {e}")
        sys.exit(1)

    socket_client = SocketModeClient(app_token=app_token, web_client=web_client)

    # Set up message handler
    def handler(client, req):
        handle_message(client, req, web_client)

    socket_client.socket_mode_request_listeners.append(handler)

    print(f"Slack Bridge started for workspace: {workspace}")
    print(f"Listening for messages... (PID: {os.getpid()})")
    print(f"Inbox: {INBOX_FILE}")
    if AUTO_RESPOND:
        print(f"Auto-respond: ENABLED (Claude Code in {WORK_DIR})")
    print("Press Ctrl+C to stop\n")

    # Keep running until interrupted
    stop_event = Event()

    def signal_handler(signum, frame):
        print("\nShutting down...")
        stop_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Connect and run
    socket_client.connect()
    health_context = {
        "workspace": workspace,
        "auto_respond": AUTO_RESPOND,
        "work_dir": WORK_DIR,
        "started_at": started_at,
        "socket_client": socket_client,
    }
    write_bridge_health(**health_context)

    # Start cleanup thread for stuck work items
    cleanup_thread = Thread(target=run_cleanup_loop, args=(web_client, stop_event, health_context), daemon=True)
    cleanup_thread.start()
    print("Cleanup thread started (checks every 5min, retries once before error)")

    last_health_at = 0.0
    while not stop_event.is_set():
        now = time.time()
        if now - last_health_at >= HEALTH_INTERVAL:
            write_bridge_health(**health_context)
            last_health_at = now
        time.sleep(1)

    try:
        socket_client.close()
    finally:
        write_bridge_health(**health_context, running=False, stopped_at=datetime.now().isoformat())
        CLAUDE_WORKERS.shutdown(wait=False, cancel_futures=False)
        DISPATCH_WORKERS.shutdown(wait=False, cancel_futures=False)
        if PID_FILE.exists():
            try:
                if PID_FILE.read_text().strip() == str(os.getpid()):
                    PID_FILE.unlink()
            except Exception as e:
                print(f"Could not remove PID file: {e}")


def show_inbox(limit: int = 10):
    """Show recent inbox messages."""
    if not INBOX_FILE.exists():
        print(json.dumps({"messages": [], "info": "No messages yet"}))
        return

    messages = []
    with open(INBOX_FILE) as f:
        for line in f:
            if line.strip():
                messages.append(json.loads(line))

    # Get last N messages
    recent = messages[-limit:]

    print(json.dumps({
        "messages": recent,
        "total": len(messages),
        "showing": len(recent),
    }, indent=2))


def reply_to_message(channel: str, thread_ts: str, text: str, workspace: str = "default"):
    """Reply to a message."""
    bot_token, _ = get_tokens(workspace)
    client = WebClient(token=bot_token)

    try:
        result = client.chat_postMessage(
            channel=channel,
            text=text,
            thread_ts=thread_ts,
        )
        print(json.dumps({
            "success": True,
            "channel": channel,
            "thread_ts": thread_ts,
            "message_ts": result["ts"],
            "text": text,
        }, indent=2))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))


def check_status():
    """Check if bridge is running and whether its heartbeat is fresh."""
    health = read_json_file(HEALTH_FILE, {}) or {}
    health_age = bridge_health_age_seconds(health)
    health_stale = health_age is None or health_age > HEALTH_STALE_SECONDS

    if PID_FILE.exists():
        try:
            with open(PID_FILE) as f:
                pid = int(f.read().strip())
        except Exception:
            pid = None
        try:
            if pid is None:
                raise ProcessLookupError
            os.kill(pid, 0)  # Check if process exists
            health_pid_matches = health.get("pid") == pid if health else False
            heartbeat_stale = health_stale or not health_pid_matches
            healthy = not heartbeat_stale and health.get("socket_connected") is not False
            print(json.dumps({
                "running": True,
                "healthy": healthy,
                "pid": pid,
                "health": health,
                "health_age_seconds": None if health_age is None else round(health_age, 1),
                "health_stale": heartbeat_stale,
                "health_pid_matches": health_pid_matches,
            }, indent=2))
            return healthy
        except ProcessLookupError:
            try:
                PID_FILE.unlink()
            except FileNotFoundError:
                pass

    print(json.dumps({
        "running": False,
        "healthy": False,
        "health": health,
        "health_age_seconds": None if health_age is None else round(health_age, 1),
        "health_stale": health_stale,
    }, indent=2))
    return False


def stop_bridge():
    """Stop the running bridge."""
    if PID_FILE.exists():
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
        try:
            os.kill(pid, signal.SIGTERM)
            print(json.dumps({"stopped": True, "pid": pid}))
            return
        except ProcessLookupError:
            PID_FILE.unlink()

    print(json.dumps({"stopped": False, "error": "Bridge not running"}))


def run_cleanup_now(workspace: str = "default"):
    """Run cleanup once and exit. Finds messages with hourglass and processes them."""
    bot_token, _ = get_tokens(workspace)
    web_client = WebClient(token=bot_token)

    # Load pending work from file
    load_pending_work()

    print(f"[CLEANUP] Checking for stuck work items...")
    print(f"[CLEANUP] Found {len(PENDING_WORK)} items in pending_work.json")

    if not PENDING_WORK:
        print("[CLEANUP] No pending work items found.")
        return

    # Run cleanup
    cleanup_stuck_work(web_client)
    print("[CLEANUP] Done.")


def scan_for_orphaned_hourglasses(workspace: str = "default", work_dir: str = None):
    """Scan inbox for messages with orphaned hourglass emoji and process them."""
    global WORK_DIR
    WORK_DIR = _default_workdir(work_dir)

    bot_token, _ = get_tokens(workspace)
    web_client = WebClient(token=bot_token)

    # Get bot's user ID
    try:
        auth_response = web_client.auth_test()
        bot_user_id = auth_response["user_id"]
        print(f"[SCAN] Bot user ID: {bot_user_id}")
    except Exception as e:
        print(f"[SCAN] Error getting bot ID: {e}")
        return

    # Read recent inbox messages
    if not INBOX_FILE.exists():
        print("[SCAN] No inbox file found.")
        return

    messages = []
    with open(INBOX_FILE) as f:
        for line in f:
            if line.strip():
                messages.append(json.loads(line))

    # Check last 50 messages for orphaned hourglasses
    recent = messages[-50:]
    print(f"[SCAN] Checking {len(recent)} recent messages for orphaned hourglasses...")

    orphaned = []
    for msg in recent:
        channel = msg.get("channel_id")
        ts = msg.get("ts")
        if not channel or not ts:
            continue

        # Check reactions on this message
        try:
            result = web_client.reactions_get(channel=channel, timestamp=ts)
            message_data = result.get("message", {})
            reactions = message_data.get("reactions", [])

            has_hourglass = False
            has_done = False
            has_error = False

            for r in reactions:
                if r["name"] == EMOJI_WORKING:
                    # Check if our bot added it
                    if bot_user_id in r.get("users", []):
                        has_hourglass = True
                elif r["name"] == EMOJI_DONE:
                    has_done = True
                elif r["name"] == EMOJI_ERROR:
                    has_error = True

            # Orphaned = has hourglass but no done/error
            if has_hourglass and not has_done and not has_error:
                orphaned.append(msg)
                print(f"[SCAN] Found orphaned: {msg.get('text', '')[:50]}...")

        except Exception as e:
            # Message may have been deleted or we don't have access
            continue

    if not orphaned:
        print("[SCAN] No orphaned hourglasses found.")
        return

    print(f"\n[SCAN] Processing {len(orphaned)} orphaned messages...")

    for msg in orphaned:
        channel = msg.get("channel_id")
        ts = msg.get("ts")
        text = msg.get("text", "")
        user_id = msg.get("user_id", "unknown")
        user_name = msg.get("user", user_id)
        thread_ts = msg.get("thread_ts")

        print(f"\n[SCAN] Processing: {text[:50]}...")

        # Add retry emoji
        add_reaction(web_client, channel, ts, EMOJI_RETRY)

        # Determine thread for response
        reply_to_thread = thread_ts or ts

        try:
            response_text = run_claude_code(text, user_name, channel, user_id,
                                            channel_id=channel, thread_ts=reply_to_thread)
            send_slack_response(web_client, channel, response_text, reply_to_thread)

            # Update emojis
            remove_reaction(web_client, channel, ts, EMOJI_WORKING)
            remove_reaction(web_client, channel, ts, EMOJI_RETRY)
            add_reaction(web_client, channel, ts, EMOJI_DONE)
            print(f"[SCAN] Success!")

        except Exception as e:
            print(f"[SCAN] Failed: {e}")
            remove_reaction(web_client, channel, ts, EMOJI_WORKING)
            remove_reaction(web_client, channel, ts, EMOJI_RETRY)
            add_reaction(web_client, channel, ts, EMOJI_ERROR)

    print("\n[SCAN] Done.")


def main():
    parser = argparse.ArgumentParser(description="Slack Bridge for Claude Code")
    parser.add_argument("--auto", "-a", action="store_true",
                        help="Auto-respond to messages using Claude Code")
    parser.add_argument("--workdir", type=str, default=None,
                        help="Working directory for Claude Code (default: current dir)")
    parser.add_argument("--daemon", "-d", action="store_true", help="Run in background")
    parser.add_argument("--status", "-s", action="store_true", help="Check if running")
    parser.add_argument("--stop", action="store_true", help="Stop the daemon")
    parser.add_argument("--cleanup", "-c", action="store_true", help="Run cleanup for stuck hourglasses once and exit")
    parser.add_argument("--scan", action="store_true", help="Scan inbox for orphaned hourglasses and process them")
    parser.add_argument("--inbox", "-i", action="store_true", help="Show inbox messages")
    parser.add_argument("--limit", "-l", type=int, default=10, help="Number of inbox messages")
    parser.add_argument("--reply", "-r", nargs=3, metavar=("CHANNEL", "TS", "MESSAGE"),
                        help="Reply to a message")
    parser.add_argument("--workspace", "-w", default="default", help="Workspace to use")

    args = parser.parse_args()

    if args.status:
        check_status()
    elif args.stop:
        stop_bridge()
    elif args.cleanup:
        run_cleanup_now(args.workspace)
    elif args.scan:
        scan_for_orphaned_hourglasses(args.workspace, args.workdir)
    elif args.inbox:
        show_inbox(args.limit)
    elif args.reply:
        channel, ts, message = args.reply
        reply_to_message(channel, ts, message, args.workspace)
    elif args.daemon:
        # Fork to background
        if os.fork() > 0:
            sys.exit(0)
        os.setsid()
        if os.fork() > 0:
            sys.exit(0)
        # Redirect stdout/stderr
        log_file = SKILL_DIR / "bridge.log"
        sys.stdout = open(log_file, "a")
        sys.stderr = sys.stdout
        run_bridge(args.workspace, args.auto, args.workdir)
    else:
        run_bridge(args.workspace, args.auto, args.workdir)


if __name__ == "__main__":
    main()
