"""content-distribution gate tests — stdlib-only.

Tests load-bearing gates: raw-link detection, post parsing, surface count.
Regression here means blog publishes ship without 14-surface checklist or with
un-instrumented links — both break the dashboard line #8.

Run: python3 -m unittest discover ~/.claude/skills/content-distribution/tests
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import run as cd  # noqa: E402


class TestRawLinkGate(unittest.TestCase):
    """find_raw_zerg_links: same shape as email-drip gate."""

    def test_catches_zergai_no_utm(self):
        self.assertEqual(len(cd.find_raw_zerg_links("Visit https://zergai.com/x")), 1)

    def test_passes_with_utm(self):
        self.assertEqual(cd.find_raw_zerg_links("Visit https://zergai.com/x?utm_source=blog"), [])

    def test_ignores_external_domain(self):
        self.assertEqual(cd.find_raw_zerg_links("Visit https://linear.app"), [])


class TestParsePost(unittest.TestCase):
    """parse_post must extract title + slug + body from frontmatter or H1."""

    def test_extracts_title_from_frontmatter(self):
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write("---\ntitle: My Post\n---\n\n# Heading\n\nBody.")
            p = Path(f.name)
        try:
            title, slug, body = cd.parse_post(p)
            self.assertEqual(title, "My Post")
            self.assertEqual(slug, p.stem)
            self.assertIn("Body.", body)
        finally:
            p.unlink()

    def test_falls_back_to_h1_when_no_frontmatter(self):
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write("# My H1 Title\n\nBody.")
            p = Path(f.name)
        try:
            title, slug, body = cd.parse_post(p)
            self.assertEqual(title, "My H1 Title")
        finally:
            p.unlink()


class TestSurfaceCount(unittest.TestCase):
    """The 14-surface playbook must be enforced. If this drops below 14,
    the distribution checklist gets coverage gaps."""

    def test_exactly_14_surfaces(self):
        self.assertEqual(len(cd.SURFACES), 14)

    def test_each_surface_has_three_fields(self):
        for s in cd.SURFACES:
            self.assertEqual(len(s), 3, f"surface {s} should be (name, desc, tool)")

    def test_no_duplicate_surface_names(self):
        names = [s[0] for s in cd.SURFACES]
        self.assertEqual(len(names), len(set(names)))


class TestSlugify(unittest.TestCase):
    """Slug normalization."""

    def test_lowercases(self):
        self.assertEqual(cd.slugify("My Post"), "my-post")

    def test_collapses_spaces(self):
        self.assertEqual(cd.slugify("a  b   c"), "a-b-c")

    def test_handles_punctuation(self):
        self.assertEqual(cd.slugify("Hello, World!"), "hello-world")

    def test_empty_falls_back(self):
        self.assertEqual(cd.slugify(""), "post")


if __name__ == "__main__":
    unittest.main()
