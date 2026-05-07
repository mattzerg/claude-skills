"""email-drip gate tests — stdlib-only.

Tests the load-bearing gates: raw-zerg-link rejection, YAML block-literal parsing,
template substitution. If these regress, broadcast sends could go out with
un-instrumented links (dashboard lies) or with un-substituted placeholders.

Run: python3 -m unittest discover ~/.claude/skills/email-drip/tests
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import run as ed  # noqa: E402


class TestRawLinkGate(unittest.TestCase):
    """find_raw_zerg_links must catch un-instrumented zerg domain links."""

    def test_catches_zergai_no_utm(self):
        body = "Visit https://zergai.com/zergboard for more."
        self.assertEqual(len(ed.find_raw_zerg_links(body)), 1)

    def test_catches_subdomain(self):
        body = "Visit https://app.zergai.com/x for more."
        self.assertEqual(len(ed.find_raw_zerg_links(body)), 1)

    def test_passes_zergai_with_utm(self):
        body = "Visit https://zergai.com/zergboard?utm_source=email for more."
        self.assertEqual(ed.find_raw_zerg_links(body), [])

    def test_ignores_external_domain(self):
        body = "Visit https://linear.app/pricing for comparison."
        self.assertEqual(ed.find_raw_zerg_links(body), [])

    def test_handles_multiple_links_in_body(self):
        body = (
            "https://zergai.com/x — bad\n"
            "https://zergai.com/y?utm_source=email — good\n"
            "https://google.com/z — external, ignored\n"
        )
        raw = ed.find_raw_zerg_links(body)
        self.assertEqual(len(raw), 1)
        self.assertIn("zergai.com/x", raw[0])


class TestTemplateSubstitution(unittest.TestCase):
    """render_template must substitute {{key}} from context."""

    def test_substitutes_known_keys(self):
        out = ed.render_template(
            "Hi {{first_name}}, welcome.", {"first_name": "Matt"}
        )
        self.assertEqual(out, "Hi Matt, welcome.")

    def test_leaves_unknown_keys_alone(self):
        out = ed.render_template("Hi {{first_name}}.", {})
        self.assertEqual(out, "Hi {{first_name}}.")

    def test_handles_whitespace_in_braces(self):
        out = ed.render_template(
            "Hi {{ first_name }}.", {"first_name": "Matt"}
        )
        self.assertEqual(out, "Hi Matt.")


class TestSimpleYAML(unittest.TestCase):
    """parse_simple_yaml must handle '|' literal blocks for multi-line bodies."""

    def test_flat_keys(self):
        meta = ed.parse_simple_yaml("name: foo\nsubject: bar\n")
        self.assertEqual(meta["name"], "foo")
        self.assertEqual(meta["subject"], "bar")

    def test_quoted_value(self):
        meta = ed.parse_simple_yaml('subject: "Welcome, {{first_name}}"\n')
        self.assertEqual(meta["subject"], "Welcome, {{first_name}}")

    def test_block_literal(self):
        text = (
            "subject: Hi\n"
            "body: |\n"
            "  Line 1\n"
            "  Line 2\n"
        )
        meta = ed.parse_simple_yaml(text)
        self.assertEqual(meta["subject"], "Hi")
        self.assertEqual(meta["body"], "Line 1\nLine 2")

    def test_list_values(self):
        text = "steps:\n  - one\n  - two\n  - three\n"
        meta = ed.parse_simple_yaml(text)
        self.assertEqual(meta["steps"], ["one", "two", "three"])


if __name__ == "__main__":
    unittest.main()
