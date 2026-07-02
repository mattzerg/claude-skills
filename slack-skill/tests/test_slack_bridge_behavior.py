#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import threading
import tempfile
import time
import types
import unittest
from unittest import mock
from pathlib import Path


BRIDGE_PATH = Path(__file__).resolve().parents[1] / "slack_bridge.py"


def load_bridge():
    spec = importlib.util.spec_from_file_location("slack_bridge_under_test", BRIDGE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeSocketClient:
    def __init__(self):
        self.acks = []
        self.connected = True

    def send_socket_mode_response(self, response):
        self.acks.append(type(response).__name__)


class FakeWebClient:
    def __init__(self):
        self.posts = []
        self.updates = []
        self.deletes = []
        self.reactions = []

    def users_info(self, user):
        return {"user": {"real_name": "Matthew Eisner"}}

    def chat_postMessage(self, **kwargs):
        self.posts.append(kwargs)
        return {"ts": f"posted.{len(self.posts)}"}

    def chat_update(self, **kwargs):
        self.updates.append(kwargs)
        return {"ts": kwargs.get("ts", "updated.1")}

    def chat_delete(self, **kwargs):
        self.deletes.append(kwargs)
        return {"ok": True}

    def reactions_add(self, **kwargs):
        self.reactions.append(kwargs)

    def reactions_remove(self, **kwargs):
        self.reactions.append({"remove": kwargs})


class SlackBridgeBehaviorTest(unittest.TestCase):
    # Each test imports a fresh bridge module with its own globals. Tests still
    # restore temp-file path mutations that matter before their worker exits.
    def test_self_note_detection_is_narrow(self):
        bridge = load_bridge()

        positives = [
            "just sending this to myself: http://192.168.1.162:8766/MattZerg/MatthewZerg/builds/duck-eye-mobile/index.html",
            "note to self: look at this later",
            "saving this for me: https://example.com",
        ]
        negatives = [
            "can you review this link for me?",
            "can you send this to me as an email?",
            "as a note to self, can you draft the agenda?",
            "<http://192.168.1.162:8766/x|192.168.1.162:8766/x>",
            'Matt said: "note to self: revisit this" - what do you think?',
            "",
        ]

        for text in positives:
            with self.subTest(text=text):
                self.assertTrue(bridge.is_self_note_message(text))
        for text in negatives:
            with self.subTest(text=text):
                self.assertFalse(bridge.is_self_note_message(text))

    def test_multi_proposed_action_blocks_are_rejected(self):
        bridge = load_bridge()

        raw = """<proposed_action>
kind: linear_issue
payload: {"team": "EPO", "title": "One"}
</proposed_action>
<proposed_action>
kind: linear_issue
payload: {"team": "EPO", "title": "Two"}
</proposed_action>"""

        payload, cleaned = bridge.extract_proposed_action(raw)
        self.assertIsNone(payload)
        self.assertIn("multiple proposed actions", cleaned)
        self.assertNotIn("<proposed_action>", cleaned)

    def test_promise_action_claim_blocks_concurrent_duplicate(self):
        bridge = load_bridge()
        original_active = bridge.ACTIVE_PROMISE_ACTIONS
        try:
            bridge.ACTIVE_PROMISE_ACTIONS = set()
            self.assertTrue(bridge.claim_promise_action("promise-1", "clear"))
            self.assertFalse(bridge.claim_promise_action("promise-1", "clear"))
            bridge.release_promise_action("promise-1", "clear")
            self.assertTrue(bridge.claim_promise_action("promise-1", "clear"))
        finally:
            bridge.ACTIVE_PROMISE_ACTIONS = original_active

    def test_claude_failure_formatting(self):
        bridge = load_bridge()

        sigkill = bridge.format_claude_failure(-9, "")
        self.assertIn("killed by the OS", sigkill)
        self.assertNotIn("exited -9", sigkill)

        stdout_error = bridge.format_claude_failure(1, "", "quota exhausted")
        self.assertIn("status 1", stdout_error)
        self.assertNotIn("quota exhausted", stdout_error)

    def test_no_response_sentinel_must_be_exact(self):
        bridge = load_bridge()

        self.assertTrue(bridge.is_no_response("[NO_RESPONSE]"))
        self.assertFalse(bridge.is_no_response("[NO_RESPONSE] earlier - here is the answer"))
        self.assertFalse(bridge.is_no_response("Here is the answer: [NO_RESPONSE]"))

    def test_fast_claude_response_skips_progress_message(self):
        bridge = load_bridge()
        web_client = FakeWebClient()
        original_run = bridge.run_claude_code
        original_delay = bridge.PROGRESS_DELAY_SECONDS
        try:
            bridge.PROGRESS_DELAY_SECONDS = 0.05
            bridge.run_claude_code = lambda *args, **kwargs: "4"

            response, progress_ts = bridge.run_claude_with_progress(
                web_client, "D1", None, "Please reply with exactly: 4", "Matt", "DM:Matt", "U1"
            )

            self.assertEqual(response, "4")
            self.assertIsNone(progress_ts)
            self.assertEqual(web_client.posts, [])
            self.assertEqual(web_client.updates, [])
        finally:
            bridge.run_claude_code = original_run
            bridge.PROGRESS_DELAY_SECONDS = original_delay

    def test_fast_claude_work_posts_exactly_one_final_message(self):
        bridge = load_bridge()
        web_client = FakeWebClient()
        original_run = bridge.run_claude_with_progress
        original_remove = bridge.remove_reaction
        original_add = bridge.add_reaction
        original_mark_completed = bridge.mark_work_completed
        try:
            bridge.run_claude_with_progress = lambda *args, **kwargs: ("4", None)
            bridge.remove_reaction = lambda *args, **kwargs: None
            bridge.add_reaction = lambda *args, **kwargs: None
            bridge.mark_work_completed = lambda *args, **kwargs: None

            bridge.process_claude_work(
                web_client,
                "D1",
                "111.222",
                "Please reply with exactly: 4",
                "U1",
                "Matt",
                "DM:Matt",
                None,
                None,
                True,
                False,
                None,
            )

            self.assertEqual(len(web_client.posts), 1)
            self.assertEqual(web_client.posts[0]["text"], "4")
            self.assertEqual(web_client.updates, [])
        finally:
            bridge.run_claude_with_progress = original_run
            bridge.remove_reaction = original_remove
            bridge.add_reaction = original_add
            bridge.mark_work_completed = original_mark_completed

    def test_slow_claude_response_posts_progress_then_posts_final(self):
        bridge = load_bridge()
        web_client = FakeWebClient()
        original_run = bridge.run_claude_code
        original_delay = bridge.PROGRESS_DELAY_SECONDS
        try:
            bridge.PROGRESS_DELAY_SECONDS = 0.001

            def slow_run(*args, **kwargs):
                time.sleep(0.03)
                return "slow answer"

            bridge.run_claude_code = slow_run

            response, progress_ts = bridge.run_claude_with_progress(
                web_client, "D1", "123.456", "slow", "Matt", "DM:Matt", "U1"
            )
            response_ts = bridge.finalize_progress_or_send(web_client, "D1", progress_ts, response, "123.456")

            self.assertEqual(response, "slow answer")
            self.assertEqual(progress_ts, "posted.1")
            self.assertEqual(response_ts, "posted.2")
            self.assertEqual(len(web_client.posts), 2)
            self.assertIn("working", web_client.posts[0]["text"])
            self.assertEqual(web_client.posts[1]["text"], "slow answer")
            self.assertEqual(web_client.updates, [])
        finally:
            bridge.run_claude_code = original_run
            bridge.PROGRESS_DELAY_SECONDS = original_delay

    def test_no_response_after_progress_deletes_working_message(self):
        bridge = load_bridge()
        web_client = FakeWebClient()
        original_run = bridge.run_claude_with_progress
        original_remove = bridge.remove_reaction
        original_mark_completed = bridge.mark_work_completed
        try:
            bridge.run_claude_with_progress = lambda *args, **kwargs: (bridge.NO_RESPONSE_SENTINEL, "posted.1")
            bridge.remove_reaction = lambda *args, **kwargs: None
            bridge.mark_work_completed = lambda *args, **kwargs: None

            bridge.process_claude_work(
                web_client, "D1", "111.222", "prompt", "U1", "Matt", "DM:Matt", None, None, True, False, None
            )

            self.assertEqual(web_client.deletes, [{"channel": "D1", "ts": "posted.1"}])
            self.assertEqual(web_client.posts, [])
        finally:
            bridge.run_claude_with_progress = original_run
            bridge.remove_reaction = original_remove
            bridge.mark_work_completed = original_mark_completed

    def test_trivial_noise_response_is_suppressed_unless_requested(self):
        bridge = load_bridge()

        self.assertTrue(bridge.is_trivial_noise_response("4", "this should not require a reply"))
        self.assertTrue(bridge.is_trivial_noise_response("done", "please update this"))
        self.assertFalse(bridge.is_trivial_noise_response("4", "what is the count?"))
        self.assertFalse(bridge.is_trivial_noise_response("[NO_RESPONSE]", "anything"))

    def test_proposed_action_parser_rejects_malformed_payload_json(self):
        bridge = load_bridge()

        raw = """<proposed_action>
kind: linear_issue
payload: {"team": "EPO", "title": "missing quote}
</proposed_action>
Create the issue."""

        payload, cleaned = bridge.extract_proposed_action(raw)
        self.assertIsNone(payload)
        self.assertEqual(cleaned, raw)

    def test_proposed_action_parser_rejects_unknown_kind(self):
        bridge = load_bridge()

        raw = """<proposed_action>
kind: unknown_tool
payload: {"title": "x"}
</proposed_action>
Run it."""

        payload, cleaned = bridge.extract_proposed_action(raw)
        self.assertIsNone(payload)
        self.assertEqual(cleaned, raw)

    def test_proposed_action_parser_validates_required_fields(self):
        bridge = load_bridge()

        missing_title = """<proposed_action>
kind: linear_issue
payload: {"team": "EPO", "description": "Needs a title"}
</proposed_action>
Create the issue."""
        payload, cleaned = bridge.extract_proposed_action(missing_title)
        self.assertIsNone(payload)
        self.assertEqual(cleaned, missing_title)

        valid = """<proposed_action>
kind: linear_issue
payload: {"team": "EPO", "title": "Bug", "description": "Fix it"}
</proposed_action>
Create the issue."""
        payload, cleaned = bridge.extract_proposed_action(valid)
        self.assertEqual(payload["kind"], "linear_issue")
        self.assertEqual(payload["title"], "Bug")
        self.assertEqual(cleaned, "Create the issue.")

    def test_proposed_action_parser_allows_nested_braces_in_strings(self):
        bridge = load_bridge()

        raw = """<proposed_action>
kind: linear_issue
payload: {"team": "EPO", "title": "Bug", "description": "snippet: {a: 1}"}
</proposed_action>
Create the issue."""

        payload, cleaned = bridge.extract_proposed_action(raw)
        self.assertEqual(payload["description"], "snippet: {a: 1}")
        self.assertEqual(cleaned, "Create the issue.")

    def test_allowed_user_gate_fails_closed(self):
        bridge = load_bridge()
        original = bridge.ALLOWED_USERS
        try:
            bridge.ALLOWED_USERS = set()
            self.assertFalse(bridge.is_allowed_user("U0AFSSPNB1N"))
            bridge.ALLOWED_USERS = {"U0AFSSPNB1N"}
            self.assertTrue(bridge.is_allowed_user("U0AFSSPNB1N"))
            self.assertFalse(bridge.is_allowed_user("UOTHER"))
        finally:
            bridge.ALLOWED_USERS = original

    def test_workspace_settings_load_from_config(self):
        bridge = load_bridge()
        original_allowed = bridge.ALLOWED_USERS
        original_channel = bridge.FM_DM_CHANNEL
        original_get_config = bridge.get_workspace_config
        try:
            bridge.get_workspace_config = lambda workspace="default": {
                "allowed_users": ["UALLOWED"],
                "fm_dm_channel": "DFAKE",
            }
            bridge.apply_workspace_settings("default")
            self.assertEqual(bridge.ALLOWED_USERS, {"UALLOWED"})
            self.assertEqual(bridge.FM_DM_CHANNEL, "DFAKE")
            self.assertTrue(bridge.is_allowed_user("UALLOWED"))
            self.assertFalse(bridge.is_allowed_user("U0AFSSPNB1N"))
        finally:
            bridge.ALLOWED_USERS = original_allowed
            bridge.FM_DM_CHANNEL = original_channel
            bridge.get_workspace_config = original_get_config

    def test_bridge_health_records_socket_state_and_counts(self):
        bridge = load_bridge()
        original_health_file = bridge.HEALTH_FILE
        original_allowed = bridge.ALLOWED_USERS
        original_pending = bridge.PENDING_WORK
        original_sessions = bridge.THREAD_SESSIONS
        try:
            with tempfile.TemporaryDirectory() as tmp:
                bridge.HEALTH_FILE = Path(tmp) / "bridge_health.json"
                bridge.ALLOWED_USERS = {"U0AFSSPNB1N"}
                bridge.PENDING_WORK = {("D1", "1.1"): {"text": "x"}}
                bridge.THREAD_SESSIONS = {"D1:main": "session"}

                bridge.write_bridge_health(
                    workspace="default",
                    auto_respond=True,
                    work_dir="/tmp/work",
                    started_at="2026-05-11T00:00:00",
                    socket_client=FakeSocketClient(),
                    last_cleanup_at="2026-05-11T00:01:00",
                )

                data = json.loads(bridge.HEALTH_FILE.read_text())
                self.assertTrue(data["running"])
                self.assertTrue(data["socket_connected"])
                self.assertEqual(data["allowed_users_count"], 1)
                self.assertEqual(data["pending_work_count"], 1)
                self.assertEqual(data["thread_sessions_count"], 1)
                self.assertEqual(data["last_cleanup_at"], "2026-05-11T00:01:00")
                self.assertIsInstance(bridge.bridge_health_age_seconds(data), float)
        finally:
            bridge.HEALTH_FILE = original_health_file
            bridge.ALLOWED_USERS = original_allowed
            bridge.PENDING_WORK = original_pending
            bridge.THREAD_SESSIONS = original_sessions

    def test_expired_pending_action_cannot_be_claimed(self):
        bridge = load_bridge()
        original_pending_file = bridge.PENDING_ACTIONS_FILE
        try:
            with tempfile.TemporaryDirectory() as tmp:
                bridge.PENDING_ACTIONS_FILE = Path(tmp) / "pending.json"
                bridge.save_pending_actions(
                    {
                        "pending": {
                            "123.456": {
                                "status": "open",
                                "created_at": time.time() - bridge.PENDING_TTL_SECONDS - 1,
                                "payload": {"kind": "linear_issue", "title": "x"},
                            }
                        }
                    }
                )

                self.assertFalse(bridge.claim_pending_action("123.456", "confirm"))
                data = bridge.load_pending_actions()
                self.assertEqual(data["pending"]["123.456"]["status"], "expired")
        finally:
            bridge.PENDING_ACTIONS_FILE = original_pending_file

    def test_dispatch_action_writes_redacted_audit_record(self):
        bridge = load_bridge()
        original_audit_file = bridge.DISPATCH_AUDIT_FILE
        original_dispatch_path = bridge.DM_DISPATCH_PATH
        try:
            with tempfile.TemporaryDirectory() as tmp:
                bridge.DISPATCH_AUDIT_FILE = Path(tmp) / "dispatch_audit.jsonl"
                bridge.DM_DISPATCH_PATH = Path(tmp) / "dm_dispatch.py"

                result = types.SimpleNamespace(
                    stdout=json.dumps({"ok": True, "summary": "created"}),
                    stderr="",
                    returncode=0,
                )
                with mock.patch.object(bridge.subprocess, "run", return_value=result):
                    out = bridge.dispatch_action(
                        {"kind": "linear_issue", "title": "Secret title"},
                        ack_ts="123.456",
                        user="U0AFSSPNB1N",
                    )

                self.assertTrue(out["ok"])
                line = bridge.DISPATCH_AUDIT_FILE.read_text().strip()
                audit = json.loads(line)
                self.assertEqual(audit["kind"], "linear_issue")
                self.assertEqual(audit["ack_ts"], "123.456")
                self.assertEqual(audit["user"], "U0AFSSPNB1N")
                self.assertTrue(audit["ok"])
                self.assertIn("payload_hash", audit)
                self.assertNotIn("Secret title", line)
        finally:
            bridge.DISPATCH_AUDIT_FILE = original_audit_file
            bridge.DM_DISPATCH_PATH = original_dispatch_path

    def test_self_note_dm_acks_without_spawning_claude(self):
        bridge = load_bridge()
        events = []

        def fail_run_claude(*args, **kwargs):
            raise AssertionError("run_claude_with_progress should not be called for self-note DMs")

        bridge.AUTO_RESPOND = True
        bridge.ALLOWED_USERS = {"U0AFSSPNB1N"}
        bridge.claim_slack_event = lambda req, event: True
        bridge.write_to_inbox = lambda msg: events.append(("inbox", msg["text"]))
        bridge.add_reaction = lambda web_client, channel, ts, emoji: events.append(("reaction", emoji))
        bridge.run_claude_with_progress = fail_run_claude

        req = types.SimpleNamespace(
            type="events_api",
            envelope_id="env-test",
            payload={
                "event": {
                    "type": "message",
                    "channel": "D0B0T0ETDR8",
                    "user": "U0AFSSPNB1N",
                    "text": "just sending this to myself: http://192.168.1.162:8766/x",
                    "ts": "123.456",
                }
            },
        )

        socket_client = FakeSocketClient()
        bridge.handle_message(socket_client, req, FakeWebClient())

        self.assertIn("SocketModeResponse", socket_client.acks)
        self.assertIn(("reaction", bridge.EMOJI_ACK), events)
        inbox_events = [event for event in events if event[0] == "inbox"]
        self.assertEqual(len(inbox_events), 1)
        self.assertIn("http://192.168.1.162:8766/x", inbox_events[0][1])

    def test_empty_allowlist_denies_dm_without_spawning_claude(self):
        bridge = load_bridge()
        events = []

        def fail_run_claude(*args, **kwargs):
            raise AssertionError("run_claude_with_progress should not be called when allowlist is empty")

        bridge.AUTO_RESPOND = True
        bridge.ALLOWED_USERS = set()
        bridge.claim_slack_event = lambda req, event: True
        bridge.write_to_inbox = lambda msg: events.append(("inbox", msg["text"]))
        bridge.run_claude_with_progress = fail_run_claude

        req = types.SimpleNamespace(
            type="events_api",
            envelope_id="env-test",
            payload={
                "event": {
                    "type": "message",
                    "channel": "D0B0T0ETDR8",
                    "user": "U0AFSSPNB1N",
                    "text": "please review this",
                    "ts": "123.456",
                }
            },
        )

        bridge.handle_message(FakeSocketClient(), req, FakeWebClient())
        self.assertFalse(any(event[0] == "inbox" for event in events))

    def test_dm_claude_work_runs_off_listener_thread(self):
        bridge = load_bridge()
        started = threading.Event()
        release = threading.Event()
        original_pending_work = bridge.PENDING_WORK
        original_save_pending_work = bridge.save_pending_work

        def blocking_run_claude(*args, **kwargs):
            started.set()
            release.wait(2)
            return "done", None

        web_client = FakeWebClient()
        bridge.AUTO_RESPOND = True
        bridge.ALLOWED_USERS = {"U0AFSSPNB1N"}
        bridge.claim_slack_event = lambda req, event: True
        bridge.write_to_inbox = lambda msg: None
        bridge.run_claude_with_progress = blocking_run_claude
        bridge.PENDING_WORK = {}
        bridge.save_pending_work = lambda: None

        try:
            req = types.SimpleNamespace(
                type="events_api",
                envelope_id="env-test",
                payload={
                    "event": {
                        "type": "message",
                        "channel": "D0B0T0ETDR8",
                        "user": "U0AFSSPNB1N",
                        "text": "please answer this",
                        "ts": "123.456",
                    }
                },
            )

            socket_client = FakeSocketClient()
            before = time.monotonic()
            bridge.handle_message(socket_client, req, web_client)
            elapsed = time.monotonic() - before

            self.assertTrue(started.wait(1))
            self.assertFalse(release.is_set())
            release.set()
            deadline = time.time() + 2
            while time.time() < deadline and bridge.PENDING_WORK:
                time.sleep(0.02)
            self.assertEqual(bridge.PENDING_WORK, {})
            self.assertIn("SocketModeResponse", socket_client.acks)
            self.assertLess(elapsed, 1.5)
        finally:
            bridge.PENDING_WORK = original_pending_work
            bridge.save_pending_work = original_save_pending_work

    def test_promise_sweep_cancel_keeps_promise_open(self):
        bridge = load_bridge()
        web_client = FakeWebClient()

        bridge.ALLOWED_USERS = {"U0AFSSPNB1N"}
        bridge.load_pending_actions = lambda: {"pending": {}}
        bridge.get_message_metadata = lambda web_client, channel, ts: {
            "event_type": "promise_sweep_announcement",
            "event_payload": {"promise_id": "promise-1"},
        }

        def fail_update(*args, **kwargs):
            raise AssertionError("cancel should not clear or snooze a promise")

        bridge.update_promise_status = fail_update

        bridge.handle_reaction_event(
            web_client,
            {
                "user": "U0AFSSPNB1N",
                "reaction": "x",
                "item": {"type": "message", "channel": "D0B0T0ETDR8", "ts": "123.456"},
            },
        )

        self.assertEqual(len(web_client.posts), 1)
        self.assertIn("keeping this promise open", web_client.posts[0]["text"])

    def test_failed_confirm_dispatch_keeps_pending_action_retryable(self):
        bridge = load_bridge()
        web_client = FakeWebClient()

        with tempfile.TemporaryDirectory() as tmp:
            bridge.PENDING_ACTIONS_FILE = Path(tmp) / "pending.json"
            bridge.FAKEMATT_TODAY_DIR = Path(tmp)
            bridge.save_pending_actions(
                {
                    "pending": {
                        "123.456": {
                            "status": "open",
                            "payload": {"kind": "linear_issue", "title": "x"},
                        }
                    }
                }
            )
            bridge.dispatch_action = lambda payload, **kwargs: {"ok": False, "error": "boom"}

            bridge.handle_confirmation(
                web_client,
                "D0B0T0ETDR8",
                "123.456",
                {"payload": {"kind": "linear_issue", "title": "x"}},
                "confirm",
            )

            data = bridge.load_pending_actions()
            self.assertEqual(data["pending"]["123.456"]["status"], "open")
            self.assertIn("react again to retry", web_client.posts[0]["text"])

    def test_stale_claude_session_retries_without_resume(self):
        bridge = load_bridge()
        original_sessions = bridge.THREAD_SESSIONS
        original_save = bridge.save_thread_sessions
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            if "--resume" in cmd:
                return types.SimpleNamespace(
                    stdout='{"result": "", "session_id": "stale"}',
                    stderr="/tmp/private/session missing",
                    returncode=1,
                )
            return types.SimpleNamespace(
                stdout='{"result": "fresh ok", "session_id": "fresh"}',
                stderr="",
                returncode=0,
            )

        try:
            bridge.WORK_DIR = "/tmp"
            bridge.THREAD_SESSIONS = {"D1:main": "stale"}
            bridge.save_thread_sessions = lambda: None

            with mock.patch.object(bridge.subprocess, "run", side_effect=fake_run):
                response = bridge.run_claude_code("hello", "Matt", "DM:Matt", "U0AFSSPNB1N", channel_id="D1")

            self.assertEqual(response, "fresh ok")
            self.assertEqual(len(calls), 2)
            self.assertIn("--resume", calls[0])
            self.assertNotIn("--resume", calls[1])
            self.assertEqual(bridge.THREAD_SESSIONS["D1:main"], "fresh")
        finally:
            bridge.THREAD_SESSIONS = original_sessions
            bridge.save_thread_sessions = original_save


if __name__ == "__main__":
    unittest.main()
