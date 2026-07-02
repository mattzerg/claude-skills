#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
import contextlib
import io
from pathlib import Path

import parse_fakeidan_verdict as parser


class ParseFakeidanVerdictTest(unittest.TestCase):
    def test_valid_review(self) -> None:
        text = "\n".join([
            "# Fake Idan Review: demo",
            "",
            "**Verdict:** Recommend changes",
            "",
            "## Concerns ranked",
        ])
        self.assertEqual(parser.parse_verdict(text), "Recommend changes")
        self.assertTrue(parser.has_concerns_section(text))

    def test_invalid_verdict(self) -> None:
        text = "# Fake Idan Review: demo\n\n**Verdict:** Looks good\n\n## Concerns ranked\n"
        self.assertIsNone(parser.parse_verdict(text))

    def test_invalid_verdict_prefix_words(self) -> None:
        self.assertIsNone(parser.parse_verdict("# Fake Idan Review: demo\n\n**Verdict:** Approveeeee\n\n## Concerns ranked\n"))
        self.assertIsNone(parser.parse_verdict("# Fake Idan Review: demo\n\n**Verdict:** Recommend changesblah\n\n## Concerns ranked\n"))

    def test_rejects_verdict_with_suffix(self) -> None:
        text = "# Fake Idan Review: demo\n\n**Verdict:** Recommend changes - see C1\n\n## Concerns ranked\n"
        self.assertIsNone(parser.parse_verdict(text))

    def test_main_accepts_utf8_bom(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "review.md"
            path.write_text("\ufeff# Fake Idan Review: demo\n\n**Verdict:** Approve\n\n## Concerns ranked\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(parser.main([str(path)]), 0)

    def test_rejects_missing_or_empty_review_heading(self) -> None:
        self.assertIsNone(parser.parse_verdict("**Verdict:** Approve\n\n## Concerns ranked\n"))
        self.assertIsNone(parser.parse_verdict("# Fake Idan Review:\n\n**Verdict:** Approve\n\n## Concerns ranked\n"))
        self.assertIn("heading", parser.verdict_error("**Verdict:** Approve\n\n## Concerns ranked\n") or "")

    def test_verdict_error_disambiguates_missing_verdict(self) -> None:
        error = parser.verdict_error("# Fake Idan Review: demo\n\n## Concerns ranked\n")
        self.assertIsNotNone(error)
        self.assertIn("Verdict", error)

    def test_ignores_quoted_verdict_before_review_header_verdict(self) -> None:
        text = "\n".join([
            "# Fake Idan Review: demo",
            "",
            "The artifact quotes an older line: **Verdict:** Approve",
            "",
            "**Verdict:** Changes requested",
            "",
            "## Concerns ranked",
        ])
        self.assertIsNone(parser.parse_verdict(text))

    def test_uses_second_non_empty_line_after_review_header(self) -> None:
        text = "\n".join([
            "# Fake Idan Review: demo",
            "",
            "**Verdict:** Changes requested",
            "",
            "A later quoted line says **Verdict:** Approve",
            "",
            "## Concerns ranked",
        ])
        self.assertEqual(parser.parse_verdict(text), "Changes requested")

    def test_main_outputs_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "review.md"
            path.write_text("# Fake Idan Review: demo\n\n**Verdict:** Approve\n\n## Concerns ranked\n")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(parser.main([str(path)]), 0)

    def test_main_exits_nonzero_without_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "review.md"
            path.write_text("## Concerns ranked\n")
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    parser.main([str(path)])
            self.assertNotEqual(raised.exception.code, 0)

    def test_main_exits_nonzero_with_invalid_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "review.md"
            path.write_text("# Fake Idan Review: demo\n\n**Verdict:** Looks good\n\n## Concerns ranked\n")
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    parser.main([str(path)])
            self.assertNotEqual(raised.exception.code, 0)

    def test_main_exits_nonzero_without_concerns_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "review.md"
            path.write_text("# Fake Idan Review: demo\n\n**Verdict:** Approve\n")
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    parser.main([str(path)])
            self.assertNotEqual(raised.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
