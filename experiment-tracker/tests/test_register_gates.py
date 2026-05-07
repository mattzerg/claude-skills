"""experiment-tracker register gate tests — stdlib-only.

Run: python3 -m unittest discover ~/.claude/skills/experiment-tracker/tests

Tests the load-bearing gate: register refuses without kill_date + kill_threshold +
success_metric + success_threshold (the anti-drift contract). If this regresses,
experiments would register without kill criteria — the program failure mode named
in the plan as "30 days quietly become 'shipped a lot, can't tell if it worked'".
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import run as et  # noqa: E402


class _NS:
    """Stdlib-only stand-in for argparse.Namespace."""
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def _good_args(**overrides):
    """Default 'happy path' args for register. Override fields per-test."""
    base = dict(
        name="test-exp",
        hypothesis="If we change X, then Y will rise because Z",
        variant_a="control",
        variant_b="treatment",
        traffic_split="50/50",
        success_metric="signup-rate",
        success_threshold="+15%",
        kill_threshold="below +3%",
        kill_date="2099-12-31",
        sample_size=500,
        rice="100",
        problem="P2",
        owner="Matt",
        start=False,
    )
    base.update(overrides)
    return _NS(**base)


class TestRegisterGate(unittest.TestCase):
    """The anti-drift contract: refuse without kill criteria."""

    def setUp(self):
        # Redirect EXPERIMENTS_DIR to a tmp dir so tests don't pollute the vault.
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_dir = et.EXPERIMENTS_DIR
        et.EXPERIMENTS_DIR = Path(self._tmp.name)

    def tearDown(self):
        et.EXPERIMENTS_DIR = self._orig_dir
        self._tmp.cleanup()

    def test_refuses_missing_hypothesis(self):
        rc = et.cmd_register(_good_args(hypothesis=""))
        self.assertNotEqual(rc, 0)

    def test_refuses_missing_kill_date(self):
        rc = et.cmd_register(_good_args(kill_date=""))
        self.assertNotEqual(rc, 0)

    def test_refuses_missing_kill_threshold(self):
        rc = et.cmd_register(_good_args(kill_threshold=""))
        self.assertNotEqual(rc, 0)

    def test_refuses_missing_success_metric(self):
        rc = et.cmd_register(_good_args(success_metric=""))
        self.assertNotEqual(rc, 0)

    def test_refuses_missing_success_threshold(self):
        rc = et.cmd_register(_good_args(success_threshold=""))
        self.assertNotEqual(rc, 0)

    def test_refuses_invalid_kill_date(self):
        rc = et.cmd_register(_good_args(kill_date="not-a-date"))
        self.assertNotEqual(rc, 0)

    def test_refuses_invalid_problem(self):
        rc = et.cmd_register(_good_args(problem="P9"))
        self.assertNotEqual(rc, 0)

    def test_accepts_valid_full(self):
        rc = et.cmd_register(_good_args())
        self.assertEqual(rc, 0)
        # File should exist with id exp-001 since tmp dir was empty
        self.assertTrue((Path(self._tmp.name) / "exp-001.md").exists())


class TestStartGate(unittest.TestCase):
    """The start command flips proposed → running. Concurrent-limit enforced."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_dir = et.EXPERIMENTS_DIR
        et.EXPERIMENTS_DIR = Path(self._tmp.name)
        # Pre-register one
        et.cmd_register(_good_args())

    def tearDown(self):
        et.EXPERIMENTS_DIR = self._orig_dir
        self._tmp.cleanup()

    def test_start_flips_proposed_to_running(self):
        rc = et.cmd_start(_NS(id="exp-001"))
        self.assertEqual(rc, 0)
        meta, _ = et.parse_yaml_frontmatter((Path(self._tmp.name) / "exp-001.md").read_text())
        self.assertEqual(meta.get("status"), "running")

    def test_start_refuses_unknown_id(self):
        rc = et.cmd_start(_NS(id="exp-999"))
        self.assertNotEqual(rc, 0)


class TestConcludeGate(unittest.TestCase):
    """conclude refuses invalid verdicts; updates status correctly."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_dir = et.EXPERIMENTS_DIR
        et.EXPERIMENTS_DIR = Path(self._tmp.name)
        et.cmd_register(_good_args())

    def tearDown(self):
        et.EXPERIMENTS_DIR = self._orig_dir
        self._tmp.cleanup()

    def test_refuses_invalid_verdict(self):
        rc = et.cmd_conclude(_NS(id="exp-001", verdict="bogus", learning="x"))
        self.assertNotEqual(rc, 0)

    def test_kill_verdict_sets_killed_status(self):
        rc = et.cmd_conclude(_NS(id="exp-001", verdict="kill", learning="not enough lift"))
        self.assertEqual(rc, 0)
        meta, _ = et.parse_yaml_frontmatter((Path(self._tmp.name) / "exp-001.md").read_text())
        self.assertEqual(meta.get("status"), "killed")
        self.assertEqual(meta.get("verdict"), "kill")


if __name__ == "__main__":
    unittest.main()
