#!/usr/bin/env python3
"""Unit tests for cross-model-check — covers deterministic logic only.

Live shell-outs to codex/claude are not tested here; the smoke tests in the
README cover those. Run: python3 -m unittest test_run.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILL_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))


def load_run_module():
    spec = importlib.util.spec_from_file_location("xrun", SKILL_DIR / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


xrun = load_run_module()
from detect_active_model import active_model, other_model  # noqa: E402
from invoke_codex import parse_codex_jsonl  # noqa: E402
from invoke_claude import parse_claude_json  # noqa: E402


class HighFindingsTest(unittest.TestCase):
    def test_high_with_bullets_detected(self) -> None:
        text = "## HIGH\n- Bug A\n- Bug B\n\n## MEDIUM\n- Nit\n"
        has, lines = xrun.has_high_findings(text)
        self.assertTrue(has)
        self.assertEqual(lines, ["- Bug A", "- Bug B"])

    def test_empty_high_section_no_findings(self) -> None:
        text = "## HIGH\n\n## MEDIUM\n- Nit\n"
        has, lines = xrun.has_high_findings(text)
        self.assertFalse(has)
        self.assertEqual(lines, [])

    def test_placeholder_bullet_ignored(self) -> None:
        text = "## HIGH\n- ...\n- none\n\n## MEDIUM\n"
        has, lines = xrun.has_high_findings(text)
        self.assertFalse(has)
        self.assertEqual(lines, [])

    def test_no_high_section(self) -> None:
        text = "Just some prose.\n\n## MEDIUM\n- something\n"
        has, lines = xrun.has_high_findings(text)
        self.assertFalse(has)
        self.assertEqual(lines, [])

    def test_star_bullets_also_recognized(self) -> None:
        text = "## HIGH\n* Bug A\n* Bug B\n\n## MEDIUM\n"
        has, lines = xrun.has_high_findings(text)
        self.assertTrue(has)
        self.assertEqual(lines, ["* Bug A", "* Bug B"])


class VerdictExtractTest(unittest.TestCase):
    def test_concur(self) -> None:
        self.assertEqual(xrun.extract_verdict("**Verdict:** Concur"), "Concur")

    def test_challenge(self) -> None:
        self.assertEqual(xrun.extract_verdict("**Verdict:** Challenge"), "Challenge")

    def test_mixed(self) -> None:
        self.assertEqual(xrun.extract_verdict("**Verdict:** Mixed"), "Mixed")

    def test_missing_returns_unknown(self) -> None:
        self.assertEqual(xrun.extract_verdict("no verdict here"), "Unknown")

    def test_case_insensitive(self) -> None:
        # The regex is re.I so lowercase still matches
        self.assertEqual(xrun.extract_verdict("**verdict:** concur"), "Concur")


class TruncateTest(unittest.TestCase):
    def test_short_text_unchanged(self) -> None:
        self.assertEqual(xrun._truncate("hi", 100, "x"), "hi")

    def test_long_text_truncated(self) -> None:
        text = "a" * 200
        out = xrun._truncate(text, 50, "diff")
        self.assertTrue(out.startswith("a" * 50))
        self.assertIn("TRUNCATED", out)
        self.assertIn("diff", out)


class BuildPromptTest(unittest.TestCase):
    def test_placeholders_substituted(self) -> None:
        out = xrun.build_prompt("code", primary="claude", reviewer="codex",
                                artifact="def foo(): pass",
                                diff="--- a\n+++ b\n",
                                primary_review="prior text")
        self.assertIn("**Codex**", out)
        self.assertIn("**Claude**", out)
        self.assertIn("def foo(): pass", out)
        self.assertIn("--- a", out)
        self.assertIn("prior text", out)

    def test_missing_diff_uses_placeholder(self) -> None:
        out = xrun.build_prompt("prose", primary="claude", reviewer="codex",
                                artifact="some prose", diff="", primary_review="")
        self.assertIn("<no prior review supplied>", out)

    def test_unknown_mode_falls_back_to_generic(self) -> None:
        out = xrun.build_prompt("nonexistent-mode", primary="claude", reviewer="codex",
                                artifact="x", diff="", primary_review="")
        self.assertIn("generic", out.lower())


class ActiveModelTest(unittest.TestCase):
    def test_claude_env(self) -> None:
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}, clear=True):
            self.assertEqual(active_model(), "claude")

    def test_codex_env(self) -> None:
        with mock.patch.dict(os.environ, {"CODEX_SESSION_ID": "abc"}, clear=True):
            self.assertEqual(active_model(), "codex")

    def test_unknown_when_no_hints(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(active_model(), "unknown")

    def test_other_model_inversion(self) -> None:
        self.assertEqual(other_model("claude"), "codex")
        self.assertEqual(other_model("codex"), "claude")
        with self.assertRaises(ValueError):
            other_model("unknown")


class ParseCodexJsonlTest(unittest.TestCase):
    def test_extracts_agent_message_text(self) -> None:
        line1 = json.dumps({"type": "thread.started", "thread_id": "abc"})
        line2 = json.dumps({"type": "item.completed", "item": {
            "id": "item_1", "type": "agent_message",
            "text": "**Verdict:** Concur\n\n## HIGH\n",
        }})
        line3 = json.dumps({"type": "turn.completed", "usage": {}})
        raw = "\n".join([line1, line2, line3])
        out = parse_codex_jsonl(raw)
        self.assertIn("**Verdict:** Concur", out)

    def test_surfaces_error_when_no_message(self) -> None:
        err = json.dumps({"type": "item.completed", "item": {
            "id": "item_0", "type": "error",
            "message": "rate limit reached",
        }})
        out = parse_codex_jsonl(err)
        self.assertIn("rate limit reached", out)
        self.assertIn("codex error", out)

    def test_empty_input(self) -> None:
        self.assertEqual(parse_codex_jsonl(""), "")

    def test_non_json_falls_back_to_raw(self) -> None:
        out = parse_codex_jsonl("not json at all")
        self.assertEqual(out, "not json at all")


class ParseClaudeJsonTest(unittest.TestCase):
    def test_result_key(self) -> None:
        raw = json.dumps({"result": "the review text", "is_error": False})
        self.assertEqual(parse_claude_json(raw), "the review text")

    def test_content_list_shape(self) -> None:
        raw = json.dumps({"content": [{"text": "part one"}, {"text": "part two"}]})
        out = parse_claude_json(raw)
        self.assertIn("part one", out)
        self.assertIn("part two", out)

    def test_plain_text_fallback(self) -> None:
        self.assertEqual(parse_claude_json("just text"), "just text")

    def test_empty_input(self) -> None:
        self.assertEqual(parse_claude_json(""), "")


class WriteReviewTest(unittest.TestCase):
    def test_review_file_has_header_and_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = xrun.write_review(
                Path(tmp), "sample.py",
                reviewer="codex", primary="claude", mode="code",
                model_output="**Verdict:** Concur\n\n## HIGH\n",
                status="ok",
            )
            text = out.read_text()
            self.assertIn("# Cross-Model Check — sample.py", text)
            self.assertIn("**Reviewer:** codex", text)
            self.assertIn("**Verdict:** Concur", text)

    def test_skip_review_has_empty_high(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = xrun.skip_review(
                Path(tmp), "sample.py",
                reviewer="codex", primary="claude", mode="code",
                reason="rate-limited",
            )
            text = out.read_text()
            self.assertIn("## HIGH\n\n", text)
            self.assertIn("rate-limited", text)
            # Skip files MUST NOT trigger pr-gate's HIGH detection
            has, lines = xrun.has_high_findings(text)
            self.assertFalse(has)
            self.assertEqual(lines, [])


if __name__ == "__main__":
    unittest.main()
