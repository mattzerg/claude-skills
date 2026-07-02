#!/usr/bin/env python3
"""Tests for aitr_select — model selection via aitr for cross-model-check.

Run: python3 -m unittest scripts.test_aitr_select -v
Unit subprocess calls are faked. LiveIntegrationTest makes one real offline
aitr invocation and is skipped when aitr is absent.
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

import aitr_select  # noqa: E402
from aitr_select import (  # noqa: E402
    aitr_pick_for_reviewer,
    record_review_outcome,
    MODE_TO_TASK_KIND,
    AITR_TO_CLAUDE_MODEL,
)


class FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def make_runner(returncode=0, stdout="", stderr="", raise_exc=None, capture=None):
    """Build a fake subprocess.run. If `capture` is a list, the cmd is appended to it."""
    def runner(cmd, **kwargs):
        if capture is not None:
            capture.append(cmd)
        if raise_exc:
            raise raise_exc
        return FakeProc(returncode=returncode, stdout=stdout, stderr=stderr)
    return runner


def aitr_json(model="anthropic__claude-opus-4-7", model_class="opus",
              reason="strong tag fit", decision_id="aitr-test-123"):
    return json.dumps({
        "decision_id": decision_id,
        "model": model,
        "model_class": model_class,
        "provider": model.split("__")[0],
        "reason": reason,
    })


class ModeMappingTest(unittest.TestCase):
    def test_code_maps_to_code_review(self):
        self.assertEqual(MODE_TO_TASK_KIND["code"], "code-review")

    def test_prose_launch_email_map_to_prose_review(self):
        for mode in ("prose", "launch", "email"):
            self.assertEqual(MODE_TO_TASK_KIND[mode], "prose-review")

    def test_generic_maps_to_refute(self):
        self.assertEqual(MODE_TO_TASK_KIND["generic"], "refute")


class ClaudeReviewerTest(unittest.TestCase):
    def test_known_opus_maps_to_alias(self):
        runner = make_runner(stdout=aitr_json("anthropic__claude-opus-4-7", "opus"))
        with mock.patch.object(aitr_select, "AITR_PICK", Path(__file__)):
            model, effort, note, decision_id = aitr_pick_for_reviewer("code", "claude", 8000, runner=runner)
        self.assertEqual(model, "opus")
        self.assertIsNone(effort)
        self.assertIn("anthropic__claude-opus-4-7", note)
        self.assertIn("aitr-test-123", note)

    def test_known_sonnet_maps_to_alias(self):
        runner = make_runner(stdout=aitr_json("anthropic__claude-sonnet-4-6", "sonnet"))
        with mock.patch.object(aitr_select, "AITR_PICK", Path(__file__)):
            model, effort, note, decision_id = aitr_pick_for_reviewer("prose", "claude", 4000, runner=runner)
        self.assertEqual(model, "sonnet")

    def test_unknown_anthropic_model_passes_bare_name(self):
        runner = make_runner(stdout=aitr_json("anthropic__claude-future-5-0", "future"))
        with mock.patch.object(aitr_select, "AITR_PICK", Path(__file__)):
            model, effort, note, decision_id = aitr_pick_for_reviewer("code", "claude", 4000, runner=runner)
        self.assertEqual(model, "claude-future-5-0")

    def test_non_anthropic_pick_for_claude_reviewer_is_ignored(self):
        # Constraint mismatch: aitr returned an openai model for a claude reviewer
        runner = make_runner(stdout=aitr_json("openai__gpt-5-5", "gpt-5"))
        with mock.patch.object(aitr_select, "AITR_PICK", Path(__file__)):
            model, effort, note, decision_id = aitr_pick_for_reviewer("code", "claude", 4000, runner=runner)
        self.assertIsNone(model)
        self.assertIn("constraint mismatch", note)


class CodexReviewerTest(unittest.TestCase):
    def test_pro_class_maps_to_xhigh(self):
        runner = make_runner(stdout=aitr_json("openai__gpt-5-5-pro", "gpt-5.5-pro"))
        with mock.patch.object(aitr_select, "AITR_PICK", Path(__file__)):
            model, effort, note, decision_id = aitr_pick_for_reviewer("code", "codex", 8000, runner=runner)
        self.assertIsNone(model)
        self.assertEqual(effort, "xhigh")
        self.assertIn("effort=xhigh", note)

    def test_non_pro_class_maps_to_high(self):
        runner = make_runner(stdout=aitr_json("openai__gpt-5-5", "gpt-5"))
        with mock.patch.object(aitr_select, "AITR_PICK", Path(__file__)):
            model, effort, note, decision_id = aitr_pick_for_reviewer("code", "codex", 8000, runner=runner)
        self.assertEqual(effort, "high")

    def test_non_openai_pick_for_codex_reviewer_is_ignored(self):
        runner = make_runner(stdout=aitr_json("anthropic__claude-opus-4-8", "opus"))
        with mock.patch.object(aitr_select, "AITR_PICK", Path(__file__)):
            model, effort, note, decision_id = aitr_pick_for_reviewer("code", "codex", 8000, runner=runner)
        self.assertIsNone(model)
        self.assertIsNone(effort)
        self.assertIn("constraint mismatch", note)


class SignalConstructionTest(unittest.TestCase):
    def test_claude_reviewer_constrains_to_anthropic(self):
        captured = []
        runner = make_runner(stdout=aitr_json(), capture=captured)
        with mock.patch.object(aitr_select, "AITR_PICK", Path(__file__)):
            aitr_pick_for_reviewer("code", "claude", 8000, runner=runner)
        cmd = captured[0]
        self.assertIn("provider_constraint=anthropic-only", cmd)
        self.assertIn("task_kind=code-review", cmd)
        self.assertIn("caller=cross-model-check", cmd)
        self.assertIn("quality_floor=high-stakes", cmd)
        self.assertIn("billing_mode=flat", cmd)

    def test_codex_reviewer_constrains_to_openai(self):
        captured = []
        runner = make_runner(stdout=aitr_json("openai__gpt-5-5", "gpt-5"), capture=captured)
        with mock.patch.object(aitr_select, "AITR_PICK", Path(__file__)):
            aitr_pick_for_reviewer("prose", "codex", 8000, runner=runner)
        cmd = captured[0]
        self.assertIn("provider_constraint=openai-only", cmd)
        self.assertIn("task_kind=prose-review", cmd)

    def test_artifact_chars_become_tokens(self):
        captured = []
        runner = make_runner(stdout=aitr_json(), capture=captured)
        with mock.patch.object(aitr_select, "AITR_PICK", Path(__file__)):
            aitr_pick_for_reviewer("code", "claude", 40000, runner=runner)
        cmd = captured[0]
        self.assertIn("artifact_size_tokens=10000", cmd)

    def test_minimum_token_floor(self):
        captured = []
        runner = make_runner(stdout=aitr_json(), capture=captured)
        with mock.patch.object(aitr_select, "AITR_PICK", Path(__file__)):
            aitr_pick_for_reviewer("code", "claude", 10, runner=runner)
        cmd = captured[0]
        self.assertIn("artifact_size_tokens=100", cmd)


class FailurePostureTest(unittest.TestCase):
    """aitr failures must NEVER block the cross-check — only annotate loudly."""

    def test_aitr_not_installed(self):
        with mock.patch.object(aitr_select, "AITR_PICK", Path("/nonexistent/pick.py")):
            model, effort, note, decision_id = aitr_pick_for_reviewer("code", "claude", 8000)
        self.assertIsNone(model)
        self.assertIsNone(effort)
        self.assertIn("not installed", note)

    def test_exit_3_catalog_unreachable(self):
        runner = make_runner(returncode=3, stderr="catalog unreachable")
        with mock.patch.object(aitr_select, "AITR_PICK", Path(__file__)):
            model, effort, note, decision_id = aitr_pick_for_reviewer("code", "claude", 8000, runner=runner)
        self.assertIsNone(model)
        self.assertIn("exit 3", note)
        self.assertIn("LOUD", note)

    def test_exit_2_no_candidate(self):
        runner = make_runner(returncode=2)
        with mock.patch.object(aitr_select, "AITR_PICK", Path(__file__)):
            model, effort, note, decision_id = aitr_pick_for_reviewer("code", "claude", 8000, runner=runner)
        self.assertIsNone(model)
        self.assertIn("exit 2", note)

    def test_exit_1_usage_error(self):
        runner = make_runner(returncode=1, stderr="bad signal")
        with mock.patch.object(aitr_select, "AITR_PICK", Path(__file__)):
            model, effort, note, decision_id = aitr_pick_for_reviewer("code", "claude", 8000, runner=runner)
        self.assertIsNone(model)
        self.assertIn("exit 1", note)

    def test_timeout(self):
        runner = make_runner(raise_exc=subprocess.TimeoutExpired(cmd="aitr", timeout=30))
        with mock.patch.object(aitr_select, "AITR_PICK", Path(__file__)):
            model, effort, note, decision_id = aitr_pick_for_reviewer("code", "claude", 8000, runner=runner)
        self.assertIsNone(model)
        self.assertIn("timed out", note)

    def test_launch_failure(self):
        runner = make_runner(raise_exc=OSError("permission denied"))
        with mock.patch.object(aitr_select, "AITR_PICK", Path(__file__)):
            model, effort, note, decision_id = aitr_pick_for_reviewer("code", "claude", 8000, runner=runner)
        self.assertIsNone(model)
        self.assertIn("failed to launch", note)

    def test_unparseable_json(self):
        runner = make_runner(stdout="this is not json")
        with mock.patch.object(aitr_select, "AITR_PICK", Path(__file__)):
            model, effort, note, decision_id = aitr_pick_for_reviewer("code", "claude", 8000, runner=runner)
        self.assertIsNone(model)
        self.assertIn("unparseable", note)

    def test_note_is_always_non_empty(self):
        """Every code path must return a non-empty note for the review header."""
        scenarios = [
            make_runner(stdout=aitr_json()),
            make_runner(returncode=1),
            make_runner(returncode=2),
            make_runner(returncode=3),
            make_runner(stdout="garbage"),
            make_runner(raise_exc=subprocess.TimeoutExpired(cmd="x", timeout=1)),
            make_runner(raise_exc=OSError("boom")),
        ]
        for runner in scenarios:
            with mock.patch.object(aitr_select, "AITR_PICK", Path(__file__)):
                _, _, note, _ = aitr_pick_for_reviewer("code", "claude", 8000, runner=runner)
            self.assertTrue(note and note.strip())


class DecisionIdTest(unittest.TestCase):
    """The 4th return element carries the decision_id only when a pick was applied."""

    def test_applied_claude_pick_returns_decision_id(self):
        runner = make_runner(stdout=aitr_json(decision_id="aitr-d-1"))
        with mock.patch.object(aitr_select, "AITR_PICK", Path(__file__)):
            _, _, _, decision_id = aitr_pick_for_reviewer("code", "claude", 8000, runner=runner)
        self.assertEqual(decision_id, "aitr-d-1")

    def test_failure_paths_return_none_decision_id(self):
        for runner in (
            make_runner(returncode=2),
            make_runner(returncode=3),
            make_runner(stdout="garbage"),
            make_runner(raise_exc=subprocess.TimeoutExpired(cmd="x", timeout=1)),
        ):
            with mock.patch.object(aitr_select, "AITR_PICK", Path(__file__)):
                _, _, _, decision_id = aitr_pick_for_reviewer("code", "claude", 8000, runner=runner)
            self.assertIsNone(decision_id)

    def test_constraint_mismatch_returns_none_decision_id(self):
        runner = make_runner(stdout=aitr_json("openai__gpt-5-5", "gpt-5"))
        with mock.patch.object(aitr_select, "AITR_PICK", Path(__file__)):
            _, _, _, decision_id = aitr_pick_for_reviewer("code", "claude", 8000, runner=runner)
        self.assertIsNone(decision_id)


class RecordReviewOutcomeTest(unittest.TestCase):
    """Outcome recording is best-effort and never raises."""

    def test_noop_without_decision_id(self):
        captured = []
        record_review_outcome(None, "good", runner=make_runner(capture=captured))
        self.assertEqual(captured, [])

    def test_records_quality(self):
        captured = []
        runner = make_runner(stdout="{}", capture=captured)
        record_review_outcome("aitr-d-1", "good", note="review delivered", runner=runner)
        self.assertEqual(len(captured), 1)
        cmd = captured[0]
        self.assertIn("record-quality", cmd)
        self.assertIn("aitr-d-1", cmd)
        self.assertIn("good", cmd)
        self.assertIn("cross-model-check", cmd)

    def test_records_actuals_when_tokens_present(self):
        captured = []

        def runner(cmd, **kwargs):
            captured.append(cmd)
            if "replay" in cmd:
                return FakeProc(stdout=json.dumps({"model": "anthropic__claude-opus-4-8"}))
            return FakeProc(stdout="{}")

        record_review_outcome("aitr-d-2", "good", input_tokens=1200, output_tokens=300,
                              runner=runner)
        verbs = [c[2] for c in captured]
        self.assertIn("record-quality", verbs)
        self.assertIn("replay", verbs)
        self.assertIn("record-actuals", verbs)
        actuals_cmd = captured[verbs.index("record-actuals")]
        self.assertIn("--input-tokens", actuals_cmd)
        self.assertIn("1200", actuals_cmd)

    def test_never_raises_on_subprocess_failure(self):
        record_review_outcome(
            "aitr-d-3", "bad",
            runner=make_runner(raise_exc=OSError("boom")),
        )  # must not raise


class LiveIntegrationTest(unittest.TestCase):
    """One real subprocess call against the actual aitr skill (offline mode).
    Skipped if aitr isn't installed at the expected location."""

    def test_real_aitr_pick_offline(self):
        if not aitr_select.AITR_PICK.exists():
            self.skipTest("aitr not installed")
        # Build a runner that injects --offline so this test never hits the network.
        def offline_runner(cmd, **kwargs):
            return subprocess.run([*cmd, "--offline"], **kwargs)
        model, effort, note, decision_id = aitr_pick_for_reviewer(
            "code", "claude", 8000, runner=offline_runner, timeout=60,
        )
        # With the bundled snapshot, a claude reviewer should get an anthropic alias.
        self.assertIn(model, ("opus", "sonnet", "haiku"))
        self.assertIn("aitr →", note)


if __name__ == "__main__":
    unittest.main()
