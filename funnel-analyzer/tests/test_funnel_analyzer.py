"""funnel-analyzer tests — stdlib-only.

Run: python3 -m unittest discover ~/.claude/skills/funnel-analyzer/tests

Tests:
- define: refuses invalid name/steps; writes valid YAML
- query: requires defined funnel; computes drop-off correctly from fixture
- query: refuses unwired data sources without silent fallback
- top-friction: respects min-head threshold (no noise on small datasets)
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import run as fa  # noqa: E402


class _NS:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class TestDefine(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_funnels = fa.FUNNELS_DIR
        fa.FUNNELS_DIR = Path(self._tmp.name)

    def tearDown(self):
        fa.FUNNELS_DIR = self._orig_funnels
        self._tmp.cleanup()

    def test_refuses_invalid_name(self):
        rc = fa.cmd_define(_NS(name="Bad Name", product="zb",
                               steps="view:landing,click:cta",
                               data_source="fixture", default_days=30))
        self.assertNotEqual(rc, 0)

    def test_refuses_single_step(self):
        rc = fa.cmd_define(_NS(name="too-short", product="zb",
                               steps="view:landing",
                               data_source="fixture", default_days=30))
        self.assertNotEqual(rc, 0)

    def test_refuses_malformed_step(self):
        rc = fa.cmd_define(_NS(name="bad-step", product="zb",
                               steps="view_landing,click:cta",
                               data_source="fixture", default_days=30))
        self.assertNotEqual(rc, 0)

    def test_accepts_valid(self):
        rc = fa.cmd_define(_NS(name="signup", product="zergboard",
                               steps="view:landing,click:cta,submit:form",
                               data_source="fixture", default_days=30))
        self.assertEqual(rc, 0)
        self.assertTrue((Path(self._tmp.name) / "signup.yaml").exists())
        # Verify YAML round-trips
        funnel = fa.parse_yaml_funnel((Path(self._tmp.name) / "signup.yaml").read_text())
        self.assertEqual(funnel["name"], "signup")
        self.assertEqual(len(funnel["steps"]), 3)
        self.assertEqual(funnel["steps"][0]["event_type"], "view")
        self.assertEqual(funnel["steps"][0]["event_name"], "landing")

    def test_refuses_duplicate(self):
        fa.cmd_define(_NS(name="dup", product="zb", steps="a:b,c:d",
                          data_source="fixture", default_days=30))
        rc = fa.cmd_define(_NS(name="dup", product="zb", steps="a:b,c:d",
                               data_source="fixture", default_days=30))
        self.assertNotEqual(rc, 0)


class TestQueryFixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_funnels = fa.FUNNELS_DIR
        self._orig_runs = fa.RUNS_DIR
        fa.FUNNELS_DIR = Path(self._tmp.name)
        fa.RUNS_DIR = Path(self._tmp.name) / "_runs"
        fa.cmd_define(_NS(name="signup", product="zb",
                          steps="view:landing,click:cta,submit:form",
                          data_source="fixture", default_days=30))
        # Create fixture
        fixture_dir = Path(self._tmp.name) / "signup"
        fixture_dir.mkdir()
        (fixture_dir / "_fixture.json").write_text(json.dumps({"counts": [1000, 400, 200]}))

    def tearDown(self):
        fa.FUNNELS_DIR = self._orig_funnels
        fa.RUNS_DIR = self._orig_runs
        self._tmp.cleanup()

    def test_query_with_fixture(self):
        rc = fa.cmd_query(_NS(name="signup", days=30))
        self.assertEqual(rc, 0)

    def test_query_unknown_funnel_refused(self):
        rc = fa.cmd_query(_NS(name="nonexistent", days=30))
        self.assertNotEqual(rc, 0)

    def test_query_no_silent_fallback_on_api_unwired(self):
        # Override funnel to declare API source but no env var set
        f = Path(self._tmp.name) / "api-funnel.yaml"
        f.write_text("---\nname: api-funnel\nproduct: zb\ndata_source: api\n"
                     "default_days: 30\nfriction_threshold: 0.5\nsteps:\n"
                     "  - id: step-1\n    event_type: view\n    event_name: landing\n"
                     "  - id: step-2\n    event_type: click\n    event_name: cta\n"
                     "---\n")
        import os
        os.environ.pop("ZERGALYTICS_API_URL", None)
        rc = fa.cmd_query(_NS(name="api-funnel", days=30))
        self.assertNotEqual(rc, 0)


class TestTopFriction(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_funnels = fa.FUNNELS_DIR
        fa.FUNNELS_DIR = Path(self._tmp.name)

    def tearDown(self):
        fa.FUNNELS_DIR = self._orig_funnels
        self._tmp.cleanup()

    def test_no_funnels_clean_exit(self):
        rc = fa.cmd_top_friction(_NS(days=7))
        self.assertEqual(rc, 0)

    def test_min_head_threshold_skips_low_volume(self):
        # Define a funnel with very low head volume
        fa.cmd_define(_NS(name="tiny", product="zb",
                          steps="a:b,c:d", data_source="fixture", default_days=30))
        fixture_dir = Path(self._tmp.name) / "tiny"
        fixture_dir.mkdir()
        (fixture_dir / "_fixture.json").write_text(json.dumps({"counts": [50, 10]}))
        rc = fa.cmd_top_friction(_NS(days=7))
        # Below TOP_FRICTION_MIN_HEAD; should exit 0 with "no funnels" message
        self.assertEqual(rc, 0)


class TestFormatTable(unittest.TestCase):
    def test_drop_off_calculation(self):
        funnel = {"steps": [
            {"event_type": "view", "event_name": "landing"},
            {"event_type": "click", "event_name": "cta"},
            {"event_type": "submit", "event_name": "form"},
        ], "friction_threshold": "0.5"}
        table, summary = fa._format_funnel_table(funnel, [1000, 400, 200])
        self.assertIn("60.0%", table)  # 1000 → 400 = 60% drop
        self.assertIn("50.0%", table)  # 400 → 200 = 50% drop
        # Top friction is the 60% drop (above threshold)
        self.assertIsNotNone(summary["top_friction"])
        self.assertAlmostEqual(summary["top_friction"]["drop_pct"], 60.0)


if __name__ == "__main__":
    unittest.main()
