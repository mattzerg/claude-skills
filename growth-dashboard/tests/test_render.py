"""growth-dashboard render tests — stdlib-only.

Run: python3 -m unittest discover ~/.claude/skills/growth-dashboard/tests

Tests structural invariants of the weekly dashboard render. If these regress,
Monday's auto-post would silently miss sections. Anti-drift contract: dashboard
should ALWAYS produce all 11 lines, populated or stubbed — never skip a line.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import run as gd  # noqa: E402


class TestRenderStructure(unittest.TestCase):
    """Render must always produce all 11 dashboard lines, populated or stubbed."""

    def setUp(self):
        self.report = gd.render_dashboard("2099-W01", verbose=False)

    def test_has_north_star_section(self):
        self.assertIn("North Star", self.report)
        self.assertIn("WAPW", self.report)
        self.assertIn("QPV", self.report)

    def test_has_all_11_lines(self):
        for n in range(1, 12):
            self.assertIn(f"\n{n}.", self.report, msg=f"line {n} missing")

    def test_line_5_active_experiments_section(self):
        self.assertIn("Active experiments", self.report)

    def test_line_6_solutions_pipeline(self):
        self.assertIn("Solutions pipeline", self.report)

    def test_line_7_case_study_status(self):
        self.assertIn("Case-study-in-flight", self.report)

    def test_has_red_and_green_sections(self):
        self.assertIn("What moves to red", self.report)
        self.assertIn("What's GREEN", self.report)

    def test_week_label_appears(self):
        self.assertIn("2099-W01", self.report)


class TestExperimentsRead(unittest.TestCase):
    """read_experiments handles missing dir + empty dir gracefully."""

    def test_returns_list(self):
        result = gd.read_experiments()
        self.assertIsInstance(result, list)

    def test_days_until_handles_empty_string(self):
        self.assertIsNone(gd.days_until(""))

    def test_days_until_handles_invalid_format(self):
        self.assertIsNone(gd.days_until("not-a-date"))

    def test_days_until_returns_int_for_valid(self):
        result = gd.days_until("2099-12-31")
        self.assertIsInstance(result, int)


class TestYAMLFrontmatterParse(unittest.TestCase):
    """parse_yaml_frontmatter handles malformed input without crashing."""

    def test_no_frontmatter_returns_empty(self):
        self.assertEqual(gd.parse_yaml_frontmatter("# Hello\nbody"), {})

    def test_unterminated_frontmatter_returns_empty(self):
        self.assertEqual(gd.parse_yaml_frontmatter("---\nfoo: bar\nno-end"), {})

    def test_well_formed_frontmatter_parses(self):
        text = "---\nid: exp-001\nstatus: running\n---\n\nbody"
        meta = gd.parse_yaml_frontmatter(text)
        self.assertEqual(meta.get("id"), "exp-001")
        self.assertEqual(meta.get("status"), "running")


if __name__ == "__main__":
    unittest.main()
