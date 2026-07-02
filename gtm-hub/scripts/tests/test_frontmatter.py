"""Tests for frontmatter parse/render roundtrip."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

THIS = Path(__file__).resolve()
sys.path.insert(0, str(THIS.parent.parent))

from lib import frontmatter  # noqa: E402


SAMPLE = """---
id: exp-001
type: experiment
title: Homepage hero — agent-native vs price-led
status: running
owner: matt
created: 2026-05-05
last_touch: 2026-05-09
kill_date: 2026-06-13
rice_score: 224
linked:
  zergboard_card: abc-123
  pr:
channels:
  - product-hunt
  - hacker-news
---

# body content
"""


class TestParse(unittest.TestCase):
    def test_basic_scalars(self) -> None:
        meta, body = frontmatter.parse(SAMPLE)
        self.assertEqual(meta["id"], "exp-001")
        self.assertEqual(meta["type"], "experiment")
        self.assertEqual(meta["status"], "running")
        self.assertEqual(meta["rice_score"], 224)
        self.assertEqual(meta["kill_date"], "2026-06-13")
        self.assertIn("body content", body)

    def test_nested_mapping(self) -> None:
        meta, _ = frontmatter.parse(SAMPLE)
        self.assertEqual(meta["linked"]["zergboard_card"], "abc-123")
        self.assertIsNone(meta["linked"]["pr"])

    def test_block_list(self) -> None:
        meta, _ = frontmatter.parse(SAMPLE)
        self.assertEqual(meta["channels"], ["product-hunt", "hacker-news"])

    def test_no_frontmatter(self) -> None:
        meta, body = frontmatter.parse("just a body")
        self.assertEqual(meta, {})
        self.assertEqual(body, "just a body")

    def test_dash_in_title_preserved(self) -> None:
        """em-dash should not be treated as a list marker."""
        meta, _ = frontmatter.parse(SAMPLE)
        self.assertIn("agent-native", meta["title"])


class TestRender(unittest.TestCase):
    def test_roundtrip(self) -> None:
        meta_in, body = frontmatter.parse(SAMPLE)
        rendered = frontmatter.render(meta_in) + body
        meta_out, _ = frontmatter.parse(rendered)
        # All scalar fields roundtrip.
        for k in ("id", "type", "title", "status", "owner", "created", "last_touch", "kill_date", "rice_score"):
            self.assertEqual(meta_in[k], meta_out[k], f"field {k!r} changed across roundtrip")

    def test_null_renders_empty(self) -> None:
        out = frontmatter.render({"id": "x", "value": None})
        self.assertIn("value:\n", out)

    def test_update_in_text(self) -> None:
        new = frontmatter.update_in_text(SAMPLE, {"status": "won", "verdict": "scale-B"})
        meta, _ = frontmatter.parse(new)
        self.assertEqual(meta["status"], "won")
        self.assertEqual(meta["verdict"], "scale-B")
        # Untouched fields preserved.
        self.assertEqual(meta["id"], "exp-001")


if __name__ == "__main__":
    unittest.main()
