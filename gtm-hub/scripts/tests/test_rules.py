"""Tests for the decision rule engine."""
from __future__ import annotations

import datetime as dt
import sys
import unittest
from pathlib import Path

THIS = Path(__file__).resolve()
sys.path.insert(0, str(THIS.parent.parent))

from lib.rules import derive, diversify  # noqa: E402


TODAY = dt.date(2026, 5, 10)


def row(**overrides) -> dict:
    base = {
        "id": "x",
        "type": "experiment",
        "title": "x",
        "status": "running",
        "path": "/tmp/x.md",
        "last_touch": "2026-05-10",
    }
    base.update(overrides)
    return base


class TestExperimentRules(unittest.TestCase):
    def test_kill_overdue_fires(self) -> None:
        rows = [row(id="exp-1", kill_date="2026-05-01")]
        out = derive(rows, today=TODAY, system_rules=False)
        rules = {d.rule for d in out}
        self.assertIn("experiment.kill_overdue", rules)

    def test_kill_approaching_fires(self) -> None:
        rows = [row(id="exp-2", kill_date="2026-05-15")]
        out = derive(rows, today=TODAY, system_rules=False)
        self.assertIn("experiment.kill_approaching", {d.rule for d in out})

    def test_kill_distant_silent(self) -> None:
        rows = [row(id="exp-3", kill_date="2026-07-01")]
        self.assertEqual(derive(rows, today=TODAY, system_rules=False), [])

    def test_concluded_silent(self) -> None:
        rows = [row(id="exp-4", status="won", kill_date="2026-05-01")]
        self.assertEqual(derive(rows, today=TODAY, system_rules=False), [])


class TestBDRules(unittest.TestCase):
    def test_stale_outreach_fires(self) -> None:
        rows = [row(type="bd_target", id="b1", status="outreach", last_touch="2026-04-01")]
        self.assertIn("bd.stale_touch", {d.rule for d in derive(rows, today=TODAY, system_rules=False)})

    def test_planned_silent(self) -> None:
        rows = [row(type="bd_target", id="b2", status="planned", last_touch="2026-04-01")]
        self.assertEqual(derive(rows, today=TODAY, system_rules=False), [])

    def test_recent_engaged_silent(self) -> None:
        rows = [row(type="bd_target", id="b3", status="engaged", last_touch="2026-05-08")]
        self.assertEqual(derive(rows, today=TODAY, system_rules=False), [])


class TestProspectRules(unittest.TestCase):
    def test_high_score_inbound_fires(self) -> None:
        rows = [row(type="prospect", id="p1", status="inbound", score=90, company="Acme")]
        rules = {d.rule for d in derive(rows, today=TODAY, system_rules=False)}
        self.assertIn("prospect.high_score_inbound", rules)

    def test_low_score_inbound_silent(self) -> None:
        rows = [row(type="prospect", id="p2", status="inbound", score=70, last_touch="2026-05-10")]
        self.assertEqual(derive(rows, today=TODAY, system_rules=False), [])

    def test_qualified_needs_proposal(self) -> None:
        rows = [row(type="prospect", id="p3", status="qualified", proposal_out_at=None)]
        self.assertIn("prospect.proposal_due", {d.rule for d in derive(rows, today=TODAY, system_rules=False)})

    def test_stale_inbound_fires(self) -> None:
        rows = [row(type="prospect", id="p4", status="inbound", score=50, last_touch="2026-04-01")]
        self.assertIn("prospect.inbound_stale", {d.rule for d in derive(rows, today=TODAY, system_rules=False)})


class TestContentRules(unittest.TestCase):
    def test_target_within_window_fires(self) -> None:
        rows = [row(type="content", id="c1", status="drafted", target_date="2026-05-19")]
        self.assertIn("content.target_near", {d.rule for d in derive(rows, today=TODAY, system_rules=False)})

    def test_published_silent(self) -> None:
        rows = [row(type="content", id="c2", status="published", target_date="2026-05-09")]
        self.assertEqual(derive(rows, today=TODAY, system_rules=False), [])

    def test_reviewed_no_schedule_fires(self) -> None:
        rows = [row(type="content", id="c3", status="reviewed", scheduled_date=None, target_date=None)]
        self.assertIn("content.schedule_or_publish", {d.rule for d in derive(rows, today=TODAY, system_rules=False)})


class TestLaunchRules(unittest.TestCase):
    def test_ready_no_ship_date_fires(self) -> None:
        rows = [row(type="launch", id="l1", status="ready", ship_date=None)]
        self.assertIn("launch.ship_date_missing", {d.rule for d in derive(rows, today=TODAY, system_rules=False)})

    def test_ship_near_fires(self) -> None:
        rows = [row(type="launch", id="l2", status="scheduled", ship_date="2026-05-19")]
        self.assertIn("launch.ship_near", {d.rule for d in derive(rows, today=TODAY, system_rules=False)})


class TestMetricRules(unittest.TestCase):
    def test_not_instrumented_fires(self) -> None:
        rows = [row(type="metric", id="m1", value=None, instrumentation_owner="matt", title="X")]
        self.assertIn("metric.not_instrumented", {d.rule for d in derive(rows, today=TODAY, system_rules=False)})

    def test_not_instrumented_tagged_backlog(self) -> None:
        """metric.not_instrumented is measurement debt — must be tagged kind=backlog
        so render.py routes it to the Measurement-debt panel, not the decisions
        triage panel."""
        rows = [row(type="metric", id="m1", value=None, instrumentation_owner="matt", title="X")]
        out = derive(rows, today=TODAY, system_rules=False)
        metric_decs = [d for d in out if d.rule == "metric.not_instrumented"]
        self.assertEqual(len(metric_decs), 1)
        self.assertEqual(metric_decs[0].kind, "backlog")

    def test_default_kind_is_decision(self) -> None:
        """Non-backlog rules default to kind='decision' so existing callers
        and the decisions panel keep firing for them."""
        rows = [row(id="exp-1", kill_date="2026-05-01")]
        out = derive(rows, today=TODAY, system_rules=False)
        self.assertTrue(out)
        self.assertEqual(out[0].kind, "decision")

    def test_instrumented_silent(self) -> None:
        rows = [row(type="metric", id="m2", value=12, instrumentation_owner="matt")]
        self.assertEqual(derive(rows, today=TODAY, system_rules=False), [])


class TestDiversify(unittest.TestCase):
    def _decs(self) -> list[dict]:
        return [
            {"rule": "a", "priority": 100, "entity_id": "1", "entity_type": "x", "entity_path": "", "message": ""},
            {"rule": "a", "priority": 90, "entity_id": "2", "entity_type": "x", "entity_path": "", "message": ""},
            {"rule": "a", "priority": 80, "entity_id": "3", "entity_type": "x", "entity_path": "", "message": ""},
            {"rule": "b", "priority": 70, "entity_id": "4", "entity_type": "y", "entity_path": "", "message": ""},
            {"rule": "c", "priority": 60, "entity_id": "5", "entity_type": "z", "entity_path": "", "message": ""},
        ]

    def test_one_per_rule(self) -> None:
        out = diversify(self._decs(), limit=5)
        rules = [d["rule"] for d, _, _ in out]
        self.assertEqual(rules, ["a", "b", "c"])

    def test_sibling_count(self) -> None:
        out = diversify(self._decs(), limit=5)
        for d, siblings, _names in out:
            if d["rule"] == "a":
                self.assertEqual(siblings, 2)
            else:
                self.assertEqual(siblings, 0)

    def test_sibling_names(self) -> None:
        """Rule `a` fires 3 times for entities 1, 2, 3; the visible row is 1, so
        the sibling names should be ['2', '3'] in priority order."""
        out = diversify(self._decs(), limit=5)
        a_row = next((row for row in out if row[0]["rule"] == "a"), None)
        self.assertIsNotNone(a_row)
        _d, _siblings, names = a_row
        self.assertEqual(names, ["2", "3"])

    def test_sibling_names_caps_at_n(self) -> None:
        """When ≥4 siblings, only top n_names (default 3) are returned."""
        many = [
            {"rule": "x", "priority": 100 - i, "entity_id": str(i), "entity_type": "z", "entity_path": "", "message": ""}
            for i in range(5)
        ]
        out = diversify(many, limit=5)
        self.assertEqual(len(out), 1)
        _d, siblings, names = out[0]
        self.assertEqual(siblings, 4)
        self.assertEqual(len(names), 3)

    def test_sibling_names_missing_entity_id(self) -> None:
        """Missing entity_id falls through to '?' rather than dropping the
        sibling row — locks in the lossy-fallback contract so a future refactor
        that removes `or "?"` is caught by tests."""
        decs = [
            {"rule": "x", "priority": 100, "entity_id": "first", "entity_type": "z", "entity_path": "", "message": ""},
            {"rule": "x", "priority": 90, "entity_id": None, "entity_type": "z", "entity_path": "", "message": ""},
            {"rule": "x", "priority": 80, "entity_id": "", "entity_type": "z", "entity_path": "", "message": ""},
        ]
        _d, siblings, names = diversify(decs, limit=5)[0]
        self.assertEqual(siblings, 2)
        self.assertEqual(names, ["?", "?"])

    def test_limit(self) -> None:
        out = diversify(self._decs(), limit=2)
        self.assertEqual(len(out), 2)


if __name__ == "__main__":
    unittest.main()
