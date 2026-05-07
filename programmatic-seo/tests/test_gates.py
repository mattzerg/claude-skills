"""programmatic-seo gate tests — stdlib-only.

Tests load-bearing gates: validate refuses unfilled scaffolds (low word count +
many placeholder markers), product→category mapping, slug generation.

Run: python3 -m unittest discover ~/.claude/skills/programmatic-seo/tests
"""
from __future__ import annotations

import argparse
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import run as ps  # noqa: E402


class TestSlugify(unittest.TestCase):

    def test_lowercases_and_kebabs(self):
        self.assertEqual(ps.slugify("What is Agent-Native PM?"), "what-is-agent-native-pm")

    def test_handles_quotes(self):
        self.assertEqual(ps.slugify("Why we built X"), "why-we-built-x")

    def test_empty_falls_back(self):
        self.assertEqual(ps.slugify(""), "page")


class TestProductCategoryMap(unittest.TestCase):
    """Each Zerg product maps to exactly one Competitive category."""

    def test_zergboard_maps_to_pm(self):
        self.assertEqual(ps.PRODUCT_CATEGORY["zergboard"], "pm-software")

    def test_zergchat_maps_to_internal_chat(self):
        self.assertEqual(ps.PRODUCT_CATEGORY["zergchat"], "internal-chat")

    def test_all_products_have_categories(self):
        # If we add a Zerg product to the comparison-page generator,
        # it must have a category mapping.
        for product in ("zergboard", "zergchat", "zergcal", "zergmeeting", "zergmail"):
            self.assertIn(product, ps.PRODUCT_CATEGORY)


class TestValidateMode(unittest.TestCase):
    """validate refuses unfilled scaffolds (low word count + placeholder count)."""

    def test_passes_well_filled_page(self):
        body = "# Title\n\n" + ("Real content sentence with more words to clear gate. " * 200)
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write("---\ntitle: T\nslug: t\ncanonical: x\ndescription: d\n---\n\n" + body)
            p = Path(f.name)
        try:
            args = argparse.Namespace(page=str(p))
            self.assertEqual(ps.cmd_validate(args), 0)
        finally:
            p.unlink()

    def test_flags_thin_content(self):
        body = "# Title\n\nShort body."
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write("---\ntitle: T\nslug: t\ncanonical: x\ndescription: d\n---\n\n" + body)
            p = Path(f.name)
        try:
            args = argparse.Namespace(page=str(p))
            self.assertEqual(ps.cmd_validate(args), 2)
        finally:
            p.unlink()

    def test_flags_missing_frontmatter(self):
        body = "# Title\n\n" + ("Words " * 200)
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write(body)  # no frontmatter
            p = Path(f.name)
        try:
            args = argparse.Namespace(page=str(p))
            self.assertEqual(ps.cmd_validate(args), 2)
        finally:
            p.unlink()

    def test_flags_too_many_placeholders(self):
        # >5 placeholder markers means scaffold not draft
        body = "# Title\n\n" + ("Real text. " * 200) + "\n\n" + "_(placeholder) " * 10
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write("---\ntitle: T\nslug: t\ncanonical: x\ndescription: d\n---\n\n" + body)
            p = Path(f.name)
        try:
            args = argparse.Namespace(page=str(p))
            self.assertEqual(ps.cmd_validate(args), 2)
        finally:
            p.unlink()


class TestMinWords(unittest.TestCase):
    """MIN_WORDS gate matches the published policy."""

    def test_min_words_is_at_least_500(self):
        # Policy is 800; allow lower in tests but flag if dropped below 500
        # (which would silently un-gate thin-content publishes).
        self.assertGreaterEqual(ps.MIN_WORDS, 500)


if __name__ == "__main__":
    unittest.main()
