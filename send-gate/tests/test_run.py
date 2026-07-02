#!/usr/bin/env python3
"""Tests for send-gate/run.py.

Pins the soft-gate's existing contract — anti-pattern scan, tier_map register
lookup, coauthor scrub, and skip-gate logging. send-gate is soft-by-design
(warn-not-block unless --strict, per feedback_gate_thresholds.md); these tests
document that behavior, they do not harden it. run.py is imported via
importlib (pattern: ~/.config/zerg/tests/test_zstate_paths.py).
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


RUN = _load("send_gate_run_under_test", Path(__file__).resolve().parent.parent / "run.py")


class AntiPatternScanTest(unittest.TestCase):
    def test_flags_known_template_phrase(self):
        body = "Hi Tom,\n\nI hope this email finds you well.\n\nBest,\nMatt\n"
        findings = RUN.scan_anti_patterns(body)
        self.assertTrue(findings)
        snippets = [s.lower() for s, _ in findings]
        self.assertTrue(any("hope this email finds you well" in s for s in snippets))

    def test_flags_formal_closer_and_all_caps(self):
        findings = RUN.scan_anti_patterns("PLEASE read this.\n\nKind regards,\n")
        reasons = " ".join(reason for _, reason in findings)
        self.assertIn("ALL-CAPS", reasons)
        self.assertIn("formal closers are off-voice", reasons)

    def test_clean_text_passes(self):
        body = ("Hi Tom,\n\nHope all is well! Let me know if you have any "
                "questions.\n\nBest,\nMatt\n")
        self.assertEqual(RUN.scan_anti_patterns(body), [])


TIER_FIXTURE = {
    "A": {"members": ["formal@example.com"]},
    "B": {"members": ["mid@example.com"]},
    "C": {"members": ["Casual@Example.com"]},
    "_excluded": {"members": ["family@example.com"]},
}


class TierMapTest(unittest.TestCase):
    def setUp(self):
        self._orig = RUN.TIER_MAP
        fd = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(TIER_FIXTURE, fd)
        fd.close()
        RUN.TIER_MAP = Path(fd.name)

    def tearDown(self):
        RUN.TIER_MAP.unlink(missing_ok=True)
        RUN.TIER_MAP = self._orig

    def test_register_lookup(self):
        self.assertEqual(RUN.lookup_register("formal@example.com"), "A")
        self.assertEqual(RUN.lookup_register("mid@example.com"), "B")
        # lookup is case-insensitive both ways
        self.assertEqual(RUN.lookup_register("casual@example.com"), "C")
        self.assertEqual(RUN.lookup_register("family@example.com"), "EXCLUDED")
        self.assertIsNone(RUN.lookup_register("stranger@example.com"))
        self.assertIsNone(RUN.lookup_register(None))

    def test_fixture_mirrors_live_schema(self):
        # Guard against fixture drift: the live tier_map must keep the
        # A/B/C/_excluded → members shape lookup_register depends on.
        if not self._orig.exists():
            self.skipTest(f"live tier_map missing at {self._orig}")
        live = json.loads(self._orig.read_text())
        for key in ("A", "B", "C", "_excluded"):
            self.assertIn(key, live)
            self.assertIsInstance(live[key]["members"], list)


class CoauthorScrubTest(unittest.TestCase):
    def test_scrubs_coauthor_lines(self):
        body = ("Hi Tom,\n\nHere's the doc.\n\n"
                "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>\n"
                "Generated with Claude Code\n\nBest,\nMatt\n")
        cleaned, count = RUN.scrub_coauthor(body)
        self.assertEqual(count, 2)
        self.assertNotIn("Co-Authored-By", cleaned)
        self.assertNotIn("Generated with Claude Code", cleaned)
        self.assertIn("Here's the doc.", cleaned)

    def test_clean_body_untouched(self):
        cleaned, count = RUN.scrub_coauthor("Hi Tom,\n\nBest,\nMatt\n")
        self.assertEqual(count, 0)
        self.assertIn("Hi Tom,", cleaned)


class SkipGateLogTest(unittest.TestCase):
    def test_skip_gate_dry_run_still_logs(self):
        # --dry-run keeps the test from shelling out to gmail-skill; the
        # log write happens before the dry-run/send branch either way.
        with tempfile.TemporaryDirectory() as tmp:
            orig_log, orig_argv = RUN.LOG, sys.argv
            try:
                RUN.LOG = Path(tmp) / "logs" / "sends.log"
                sys.argv = ["run.py", "--skip-gate", "--dry-run",
                            "--to", "someone@example.com", "--body", "hi"]
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    rc = RUN.main()
                self.assertEqual(rc, 0)
                records = [json.loads(line)
                           for line in RUN.LOG.read_text().splitlines() if line.strip()]
                self.assertEqual(len(records), 1)
                self.assertTrue(records[0]["skipped"])
                self.assertEqual(records[0]["to"], "someone@example.com")
            finally:
                RUN.LOG, sys.argv = orig_log, orig_argv


class StrictBlockTest(unittest.TestCase):
    """--strict is the gate's only blocking behavior — pin exit 1 + BLOCKED."""

    def test_strict_blocks_on_finding_before_any_send(self):
        orig_argv = sys.argv
        try:
            sys.argv = ["run.py", "--strict", "--dry-run",
                        "--to", "someone@example.com",
                        "--body", "Hi Tom, I hope this email finds you well."]
            err = io.StringIO()
            with redirect_stdout(io.StringIO()), redirect_stderr(err):
                rc = RUN.main()
            self.assertEqual(rc, 1)
            self.assertIn("BLOCKED", err.getvalue())
        finally:
            sys.argv = orig_argv


class CaptureAtSendRoundTripTest(unittest.TestCase):
    """capture_at_send rewrites sent-log.jsonl in place — the riskiest code
    path. Round-trips both branches: material edit (correction appended) and
    no-material-edit (marked checked, no correction)."""

    def _fixture_dir(self, tmp: str, generated: str) -> Path:
        import datetime as dt
        sdir = Path(tmp) / "fakematt-email"
        sdir.mkdir()
        record = {
            "ts": dt.datetime.now().strftime("%Y%m%dT%H%M%S"),
            "to": "tom@example.com",
            "generated_body": generated,
            "checked": False,
        }
        (sdir / "sent-log.jsonl").write_text(json.dumps(record) + "\n")
        return sdir

    def test_material_edit_appends_correction_and_marks_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            sdir = self._fixture_dir(tmp, "line one\nline two\nline three\nline four")
            orig = RUN.LEARN_SKILL_DIRS
            try:
                RUN.LEARN_SKILL_DIRS = [sdir]
                with redirect_stderr(io.StringIO()):
                    out = RUN.capture_at_send(
                        "tom@example.com",
                        "line one\nREWRITTEN two\nREWRITTEN three\nline four")
            finally:
                RUN.LEARN_SKILL_DIRS = orig
            self.assertIsNotNone(out)
            self.assertGreaterEqual(out["changed_lines"], 2)
            self.assertNotIn("no_material_edit", out)
            corrections = (sdir / "corrections.md").read_text()
            self.assertIn("Captured at send-time", corrections)
            self.assertIn("REWRITTEN two", corrections)
            rec = json.loads((sdir / "sent-log.jsonl").read_text().strip())
            self.assertTrue(rec["checked"])
            self.assertTrue(rec["manual_override"])
            self.assertEqual(rec["captured_by"], "send-gate")

    def test_no_material_edit_marks_checked_without_correction(self):
        with tempfile.TemporaryDirectory() as tmp:
            body = "line one\nline two\nline three"
            sdir = self._fixture_dir(tmp, body)
            orig = RUN.LEARN_SKILL_DIRS
            try:
                RUN.LEARN_SKILL_DIRS = [sdir]
                with redirect_stderr(io.StringIO()):
                    out = RUN.capture_at_send("tom@example.com", body)
            finally:
                RUN.LEARN_SKILL_DIRS = orig
            self.assertIsNotNone(out)
            self.assertTrue(out["no_material_edit"])
            self.assertFalse((sdir / "corrections.md").exists())
            rec = json.loads((sdir / "sent-log.jsonl").read_text().strip())
            self.assertTrue(rec["checked"])
            self.assertNotIn("manual_override", rec)


if __name__ == "__main__":
    unittest.main()
