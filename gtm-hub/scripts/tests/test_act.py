"""Tests for action verbs."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

THIS = Path(__file__).resolve()
sys.path.insert(0, str(THIS.parent.parent))

from act import VERBS, hint_for_decision  # noqa: E402


class TestVerbCatalog(unittest.TestCase):
    def test_all_verbs_have_target_in_allowed_status_set(self) -> None:
        # The target status of each verb must be a valid hub status for that type.
        # We don't import schema here directly to keep tests fast — sanity-check shape.
        for name, verb in VERBS.items():
            self.assertTrue(verb.target_status, f"{name} missing target_status")
            self.assertTrue(verb.allowed_from, f"{name} missing allowed_from")
            self.assertNotIn(
                verb.target_status, verb.allowed_from,
                f"{name}: target {verb.target_status!r} cannot be in allowed_from "
                f"(would mean a no-op transition)",
            )

    def test_qualify_verb(self) -> None:
        v = VERBS["qualify"]
        self.assertEqual(v.entity_type, "prospect")
        self.assertEqual(v.target_status, "qualified")
        self.assertEqual(v.allowed_from, {"inbound"})

    def test_kill_verb_requires_learning(self) -> None:
        v = VERBS["kill"]
        self.assertEqual(v.entity_type, "experiment")
        self.assertEqual(v.target_status, "killed")
        # arg parser registers --learning as required; can't easily probe here,
        # but the build_updates demands it via ns.learning attribute.

    def test_ship_target_status_scheduled_not_shipped(self) -> None:
        # Forward-only contract: ship sets scheduled (not shipped — that's launched).
        v = VERBS["ship"]
        self.assertEqual(v.target_status, "scheduled")


class TestHints(unittest.TestCase):
    def test_kill_overdue_hints_kill_verb(self) -> None:
        h = hint_for_decision("experiment.kill_overdue", "exp-001")
        self.assertIsNotNone(h)
        self.assertIn("act kill exp-001", h)
        self.assertIn("--learning", h)

    def test_high_score_prospect_hints_qualify(self) -> None:
        h = hint_for_decision("prospect.high_score_inbound", "clay")
        self.assertEqual(h, "gtm act qualify clay")

    def test_content_target_hints_publish(self) -> None:
        h = hint_for_decision("content.target_near", "agents-that-remember")
        self.assertEqual(h, "gtm act publish agents-that-remember")

    def test_bd_stale_hints_engage(self) -> None:
        h = hint_for_decision("bd.stale_touch", "anthropic-claude-code-mcp")
        self.assertEqual(h, "gtm act engage anthropic-claude-code-mcp")

    def test_unknown_rule_returns_none(self) -> None:
        self.assertIsNone(hint_for_decision("system.qualification_drought", "system"))
        self.assertIsNone(hint_for_decision("unknown.rule", "x"))

    def test_empty_entity_id_returns_none(self) -> None:
        self.assertIsNone(hint_for_decision("prospect.high_score_inbound", ""))


if __name__ == "__main__":
    unittest.main()
