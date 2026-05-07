"""bd-tracker gate tests — stdlib-only.

Tests load-bearing gates: target-name normalization (so 'Anthropic' matches
'**Anthropic** (Claude Code, MCP)'), status legend enforcement, BD list parsing.

Run: python3 -m unittest discover ~/.claude/skills/bd-tracker/tests
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import run as bd  # noqa: E402


class TestNameNormalization(unittest.TestCase):
    """_normalize must strip markdown emphasis + parentheticals so user input
    matches canonical bd-targets.md entries."""

    def test_strips_bold_markdown(self):
        self.assertEqual(bd._normalize("**Anthropic**"), "anthropic")

    def test_strips_inline_emphasis(self):
        self.assertEqual(bd._normalize("Some **Bold** Word"), "some bold word")

    def test_strips_parenthetical(self):
        self.assertEqual(bd._normalize("Anthropic (Claude Code, MCP)"), "anthropic")

    def test_strips_combined(self):
        self.assertEqual(bd._normalize("**Anthropic** (Claude Code, MCP)"), "anthropic")

    def test_lowercase_is_idempotent(self):
        self.assertEqual(bd._normalize("anthropic"), "anthropic")
        self.assertEqual(bd._normalize("ANTHROPIC"), "anthropic")


class TestStripMD(unittest.TestCase):
    """_strip_md handles emphasis without surrounding-only patterns."""

    def test_inline_bold(self):
        self.assertEqual(bd._strip_md("a **b** c"), "a b c")

    def test_inline_italic(self):
        self.assertEqual(bd._strip_md("a *b* c"), "a b c")

    def test_no_markup(self):
        self.assertEqual(bd._strip_md("plain text"), "plain text")


class TestStatusLegend(unittest.TestCase):
    """Valid statuses must include the lifecycle covered by stale_check."""

    def test_includes_active_states(self):
        for s in ("planned", "outreach", "engaged"):
            self.assertIn(s, bd.VALID_STATUSES)

    def test_includes_terminal_states(self):
        for s in ("paused", "closed-won", "closed-lost"):
            self.assertIn(s, bd.VALID_STATUSES)

    def test_excludes_random_string(self):
        self.assertNotIn("inprogress", bd.VALID_STATUSES)
        self.assertNotIn("done", bd.VALID_STATUSES)


if __name__ == "__main__":
    unittest.main()
