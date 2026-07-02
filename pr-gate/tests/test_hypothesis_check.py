#!/usr/bin/env python3
"""Unit tests for ~/.claude/skills/pr-gate/hypothesis_check.py.

Validates: trigger detection (file paths), valid/invalid hypothesis parsing,
placeholder rejection, end-to-end check() flow.
"""
from __future__ import annotations
import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path.home() / ".claude/skills/pr-gate/hypothesis_check.py"
spec = importlib.util.spec_from_file_location("hypothesis_check", SCRIPT)
assert spec and spec.loader
hc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc)


class TestNeedsHypothesis(unittest.TestCase):
    def test_triggers_on_agent_memory(self):
        self.assertTrue(hc.needs_hypothesis(["MattZerg/_agent_memory/shared/foo.md"]))

    def test_triggers_on_claude_skills(self):
        self.assertTrue(hc.needs_hypothesis([".claude/skills/pr-gate/run.py"]))

    def test_triggers_on_claude_agents(self):
        self.assertTrue(hc.needs_hypothesis([".claude/agents/feedback-regression.md"]))

    def test_triggers_on_claude_hooks(self):
        self.assertTrue(hc.needs_hypothesis([".claude/hooks/correction_capture_inline.py"]))

    def test_triggers_on_codex_memories(self):
        self.assertTrue(hc.needs_hypothesis([".codex/memories/feedback-shared.md"]))

    def test_triggers_on_config_zerg(self):
        self.assertTrue(hc.needs_hypothesis([".config/zerg/skill_fire_rates.py"]))

    def test_does_not_trigger_on_product_code(self):
        self.assertFalse(hc.needs_hypothesis(["src/foo.ts", "lib/bar.py", "README.md"]))

    def test_mixed_diff_triggers_if_any_match(self):
        self.assertTrue(hc.needs_hypothesis(["src/foo.ts", ".claude/hooks/x.py"]))


class TestParseHypothesis(unittest.TestCase):
    def test_empty_body_fails(self):
        valid, _ = hc.parse_hypothesis("")
        self.assertFalse(valid)

    def test_no_hypothesis_line_fails(self):
        valid, _ = hc.parse_hypothesis("## Summary\nFixed a bug.")
        self.assertFalse(valid)

    def test_valid_with_reduce_verb(self):
        valid, text = hc.parse_hypothesis("Hypothesis: this reduces corrections by 30% within 30 days")
        self.assertTrue(valid)
        self.assertIn("reduces", text)

    def test_valid_with_numeric_only(self):
        valid, _ = hc.parse_hypothesis("Hypothesis: change should affect 50 cases")
        self.assertTrue(valid)

    def test_rejects_placeholder(self):
        valid, reason = hc.parse_hypothesis("Hypothesis: <change> reduces <metric> by <amount>")
        self.assertFalse(valid)
        self.assertIn("measurable", reason.lower())

    def test_rejects_tbd(self):
        valid, _ = hc.parse_hypothesis("Hypothesis: TBD")
        self.assertFalse(valid)

    def test_case_insensitive(self):
        valid, _ = hc.parse_hypothesis("hypothesis: reduces foo by 50%")
        self.assertTrue(valid)

    def test_picks_first_valid_when_multiple(self):
        body = ("Hypothesis: TBD\n"
                "Hypothesis: reduces corrections by 30%\n"
                "Hypothesis: should be done")
        valid, text = hc.parse_hypothesis(body)
        self.assertTrue(valid)
        self.assertIn("30%", text)


class TestCheckEndToEnd(unittest.TestCase):
    def test_not_needed_returns_pass(self):
        needed, passed, finding = hc.check(["src/foo.ts"], "no hypothesis")
        self.assertFalse(needed)
        self.assertTrue(passed)
        self.assertEqual(finding, "")

    def test_needed_with_valid_hypothesis(self):
        needed, passed, _ = hc.check(
            [".claude/skills/foo/run.py"],
            "Hypothesis: reduces corrections by 30% within 30 days",
        )
        self.assertTrue(needed)
        self.assertTrue(passed)

    def test_needed_without_hypothesis_emits_high_finding(self):
        needed, passed, finding = hc.check(
            [".claude/hooks/x.py"],
            "no hypothesis line here",
        )
        self.assertTrue(needed)
        self.assertFalse(passed)
        self.assertIn("HIGH", finding)
        self.assertIn("Hypothesis", finding)

    def test_needed_with_placeholder_fails(self):
        needed, passed, finding = hc.check(
            [".claude/hooks/x.py"],
            "Hypothesis: <change> reduces <metric> by <amount>",
        )
        self.assertTrue(needed)
        self.assertFalse(passed)
        self.assertIn("HIGH", finding)


if __name__ == "__main__":
    unittest.main()
