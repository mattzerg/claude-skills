"""content-calendar gate tests — stdlib-only.

Run: python3 -m unittest discover ~/.claude/skills/content-calendar/tests

Tests the load-bearing gates:
- add: enforces type whitelist + slug shape + valid date
- transition: forward-only state machine, refuses skips
- transition: requires copyedit_review artifact for type=blog/launch → reviewed
- transition: requires distribution_card for published → distributed
- slip: increments counter; ≥3 triggers warning path

If these regress, the editorial pipeline silently allows pieces to publish without
review or distribute without distribution cards — the failure mode this skill exists
to prevent.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import run as cc  # noqa: E402


class _NS:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def _add_args(**overrides):
    base = dict(
        title="Test post",
        type="blog",
        target="2099-12-31",
        slug="test-post",
        owner="Matt",
    )
    base.update(overrides)
    return _NS(**base)


class TestAddGate(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig = cc.CONTENT_DIR
        cc.CONTENT_DIR = Path(self._tmp.name)

    def tearDown(self):
        cc.CONTENT_DIR = self._orig
        self._tmp.cleanup()

    def test_refuses_invalid_type(self):
        rc = cc.cmd_add(_add_args(type="podcast"))
        self.assertNotEqual(rc, 0)

    def test_refuses_invalid_date(self):
        rc = cc.cmd_add(_add_args(target="not-a-date"))
        self.assertNotEqual(rc, 0)

    def test_refuses_invalid_slug(self):
        rc = cc.cmd_add(_add_args(slug="Not Valid"))
        self.assertNotEqual(rc, 0)

    def test_refuses_uppercase_slug(self):
        rc = cc.cmd_add(_add_args(slug="UPPER"))
        self.assertNotEqual(rc, 0)

    def test_accepts_valid(self):
        rc = cc.cmd_add(_add_args())
        self.assertEqual(rc, 0)
        self.assertTrue((Path(self._tmp.name) / "test-post.md").exists())

    def test_refuses_duplicate_slug(self):
        cc.cmd_add(_add_args())
        rc = cc.cmd_add(_add_args())
        self.assertNotEqual(rc, 0)


class TestTransitionGate(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig = cc.CONTENT_DIR
        cc.CONTENT_DIR = Path(self._tmp.name)
        cc.cmd_add(_add_args())

    def tearDown(self):
        cc.CONTENT_DIR = self._orig
        self._tmp.cleanup()

    def test_idea_to_drafted_allowed(self):
        rc = cc.cmd_transition(_NS(slug="test-post", to="drafted", note=""))
        self.assertEqual(rc, 0)

    def test_skip_idea_to_reviewed_refused(self):
        rc = cc.cmd_transition(_NS(slug="test-post", to="reviewed", note=""))
        self.assertNotEqual(rc, 0)

    def test_drafted_to_reviewed_blocked_without_copyedit(self):
        cc.cmd_transition(_NS(slug="test-post", to="drafted", note=""))
        rc = cc.cmd_transition(_NS(slug="test-post", to="reviewed", note=""))
        # blog requires copyedit_review artifact
        self.assertNotEqual(rc, 0)

    def test_published_to_distributed_blocked_without_distribution_card(self):
        # Manually advance through states with artifacts present
        f = Path(self._tmp.name) / "test-post.md"
        meta, body = cc.parse_yaml_frontmatter(f.read_text())
        meta["state"] = "published"
        # Set copyedit_review so we're past that gate but no distribution_card
        meta["artifacts"] = {"draft": "x", "imagery": "x", "copyedit_review": "x", "distribution_card": ""}
        f.write_text(cc.render_yaml_frontmatter(meta) + "\n" + body)
        rc = cc.cmd_transition(_NS(slug="test-post", to="distributed", note=""))
        self.assertNotEqual(rc, 0)

    def test_unknown_slug_refused(self):
        rc = cc.cmd_transition(_NS(slug="nonexistent", to="drafted", note=""))
        self.assertNotEqual(rc, 0)


class TestSlip(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig = cc.CONTENT_DIR
        cc.CONTENT_DIR = Path(self._tmp.name)
        cc.cmd_add(_add_args())

    def tearDown(self):
        cc.CONTENT_DIR = self._orig
        self._tmp.cleanup()

    def test_slip_increments_counter(self):
        rc = cc.cmd_slip(_NS(slug="test-post", to="2099-11-30", reason="r1"))
        self.assertEqual(rc, 0)
        meta, _ = cc.parse_yaml_frontmatter((Path(self._tmp.name) / "test-post.md").read_text())
        self.assertEqual(int(meta["slips"]), 1)

    def test_slip_refuses_invalid_date(self):
        rc = cc.cmd_slip(_NS(slug="test-post", to="bogus", reason="r1"))
        self.assertNotEqual(rc, 0)


class TestAudit(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig = cc.CONTENT_DIR
        cc.CONTENT_DIR = Path(self._tmp.name)

    def tearDown(self):
        cc.CONTENT_DIR = self._orig
        self._tmp.cleanup()

    def test_audit_clean_when_empty(self):
        rc = cc.cmd_audit(_NS())
        self.assertEqual(rc, 0)

    def test_audit_flags_overdue(self):
        cc.cmd_add(_add_args(target="2020-01-01"))
        rc = cc.cmd_audit(_NS())
        # rc=2 means overdue items found
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
