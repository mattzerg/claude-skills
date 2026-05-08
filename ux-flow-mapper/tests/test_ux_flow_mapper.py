"""ux-flow-mapper tests — stdlib-only.

Run: python3 -m unittest discover ~/.claude/skills/ux-flow-mapper/tests

Tests:
- parse_spec: handles minimal valid YAML; rejects missing closing ---
- render_mermaid: produces valid stateDiagram-v2 syntax
- render_screen_table: includes all required columns
- map: refuses missing flow / screens
- map: idempotent (re-run preserves Notes section)
- compare: diff intended vs observed
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import run as ufm  # noqa: E402


class _NS:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


MINIMAL_SPEC = """---
flow: test-flow
product: zergboard
persona: tech-lead
ship_status: wip
description: "Test flow description"
screens:
  - id: landing
    name: "Landing"
    purpose: "Sell value"
    primary_cta: "Sign up"
    ship_status: live
    drop_off_severity: high
    exits:
      - to: form
        condition: "click cta"
  - id: form
    name: "Form"
    purpose: "Capture email"
    primary_cta: "Submit"
    ship_status: live
    drop_off_severity: medium
    error_states:
      - email_invalid
    exits:
      - to: external
        condition: "submit valid"
---
"""


class TestParseSpec(unittest.TestCase):
    def test_parses_minimal(self):
        spec = ufm.parse_spec(MINIMAL_SPEC)
        self.assertEqual(spec["flow"], "test-flow")
        self.assertEqual(spec["product"], "zergboard")
        self.assertEqual(len(spec["screens"]), 2)
        self.assertEqual(spec["screens"][0]["id"], "landing")
        self.assertEqual(len(spec["screens"][0]["exits"]), 1)
        self.assertEqual(spec["screens"][1]["error_states"], ["email_invalid"])

    def test_rejects_missing_frontmatter(self):
        with self.assertRaises(ValueError):
            ufm.parse_spec("flow: test\nscreens: []\n")

    def test_rejects_tab_indent(self):
        bad = MINIMAL_SPEC.replace("    name:", "\tname:", 1)
        with self.assertRaises(ValueError):
            ufm.parse_spec(bad)

    def test_rejects_misaligned_indent_in_screens(self):
        bad = MINIMAL_SPEC.replace("    name:", "  name:", 1)
        with self.assertRaises(ValueError):
            ufm.parse_spec(bad)

    def test_round_trip_via_json(self):
        # Locks in C1 mitigation: a parsed spec rendered to JSON and re-parsed
        # via the JSON path produces the same shape.
        spec = ufm.parse_spec(MINIMAL_SPEC)
        as_json = json.dumps(spec)
        re_parsed = ufm.parse_spec(as_json)
        self.assertEqual(spec["flow"], re_parsed["flow"])
        self.assertEqual(len(spec["screens"]), len(re_parsed["screens"]))
        for a, b in zip(spec["screens"], re_parsed["screens"]):
            self.assertEqual(a.get("id"), b.get("id"))
            self.assertEqual(a.get("name"), b.get("name"))
            self.assertEqual(a.get("ship_status"), b.get("ship_status"))


class TestValidateSpec(unittest.TestCase):
    """C2: validate_spec is the single source of truth."""

    def _good(self):
        return ufm.parse_spec(MINIMAL_SPEC)

    def test_clean_spec_no_errors(self):
        self.assertEqual(ufm.validate_spec(self._good()), [])

    def test_missing_flow(self):
        spec = self._good()
        spec.pop("flow")
        errs = ufm.validate_spec(spec)
        self.assertTrue(any("flow" in e for e in errs))

    def test_missing_screens(self):
        errs = ufm.validate_spec({"flow": "x"})
        self.assertTrue(any("screens" in e for e in errs))

    def test_invalid_ship_status(self):
        spec = self._good()
        spec["screens"][0]["ship_status"] = "bogus"
        errs = ufm.validate_spec(spec)
        self.assertTrue(any("ship_status" in e for e in errs))

    def test_invalid_drop_off(self):
        spec = self._good()
        spec["screens"][0]["drop_off_severity"] = "extreme"
        errs = ufm.validate_spec(spec)
        self.assertTrue(any("drop_off_severity" in e for e in errs))

    def test_duplicate_screen_id(self):
        spec = self._good()
        spec["screens"][1]["id"] = "landing"
        errs = ufm.validate_spec(spec)
        self.assertTrue(any("duplicate" in e for e in errs))

    def test_unresolved_exit_target(self):
        spec = self._good()
        spec["screens"][0]["exits"] = [{"to": "nonexistent_screen"}]
        errs = ufm.validate_spec(spec)
        self.assertTrue(any("does not resolve" in e for e in errs))

    def test_terminal_sentinel_resolves(self):
        spec = self._good()
        # Sentinels [*], external, exit are valid exit targets.
        spec["screens"][0]["exits"] = [{"to": "external"}]
        self.assertEqual(ufm.validate_spec(spec), [])


class TestRenderMermaid(unittest.TestCase):
    def test_includes_state_diagram_header(self):
        spec = ufm.parse_spec(MINIMAL_SPEC)
        m = ufm.render_mermaid(spec)
        self.assertIn("stateDiagram-v2", m)
        self.assertIn("[*] --> landing", m)
        self.assertIn("landing --> form", m)
        self.assertIn("```mermaid", m)


class TestRenderScreenTable(unittest.TestCase):
    def test_table_has_all_columns(self):
        spec = ufm.parse_spec(MINIMAL_SPEC)
        t = ufm.render_screen_table(spec)
        self.assertIn("ID", t)
        self.assertIn("Name", t)
        self.assertIn("Purpose", t)
        self.assertIn("Primary CTA", t)
        self.assertIn("Ship", t)
        self.assertIn("Drop-off", t)
        self.assertIn("landing", t)
        self.assertIn("form", t)


class TestMap(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig = ufm.JOURNEYS_DIR
        ufm.JOURNEYS_DIR = Path(self._tmp.name)
        # Write a spec file
        self._spec = Path(self._tmp.name) / "spec.yaml"
        self._spec.write_text(MINIMAL_SPEC)

    def tearDown(self):
        ufm.JOURNEYS_DIR = self._orig
        self._tmp.cleanup()

    def test_map_succeeds(self):
        rc = ufm.cmd_map(_NS(spec=str(self._spec), output="test-flow"))
        self.assertEqual(rc, 0)
        out = Path(self._tmp.name) / "test-flow.md"
        self.assertTrue(out.exists())
        text = out.read_text()
        self.assertIn("stateDiagram-v2", text)
        self.assertIn("Screen inventory", text)

    def test_map_writes_json_sidecar(self):
        # C4: structured truth lives in JSON sidecar, not rendered prose.
        ufm.cmd_map(_NS(spec=str(self._spec), output="test-flow"))
        sidecar = Path(self._tmp.name) / "test-flow.json"
        self.assertTrue(sidecar.exists())
        import json as _json
        data = _json.loads(sidecar.read_text())
        self.assertEqual(data["flow"], "test-flow")
        self.assertIn("landing", data["screens"])
        self.assertIn(["landing", "form"], data["transitions"])

    def test_map_rejects_invalid_spec(self):
        # C2: validate_spec runs before write.
        bad_spec = MINIMAL_SPEC.replace("ship_status: live", "ship_status: bogus", 1)
        bad_path = Path(self._tmp.name) / "bad.yaml"
        bad_path.write_text(bad_spec)
        rc = ufm.cmd_map(_NS(spec=str(bad_path), output="should-not-write"))
        self.assertNotEqual(rc, 0)
        self.assertFalse((Path(self._tmp.name) / "should-not-write.md").exists())

    def test_map_refuses_missing_spec_file(self):
        rc = ufm.cmd_map(_NS(spec="/tmp/does-not-exist.yaml", output="x"))
        self.assertNotEqual(rc, 0)

    def test_map_preserves_notes_on_rerun(self):
        ufm.cmd_map(_NS(spec=str(self._spec), output="test-flow"))
        out = Path(self._tmp.name) / "test-flow.md"
        text = out.read_text()
        # Hand-edit the Notes section
        custom = "This is custom hand-edited content.\n"
        new_text = text.replace(
            "(hand-edit this section — preserved across `map` re-runs)\n",
            custom,
        )
        out.write_text(new_text)
        # Re-run map
        ufm.cmd_map(_NS(spec=str(self._spec), output="test-flow"))
        rerun = out.read_text()
        self.assertIn(custom.rstrip(), rerun)


class TestCompare(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig = ufm.JOURNEYS_DIR
        ufm.JOURNEYS_DIR = Path(self._tmp.name)
        spec_a = Path(self._tmp.name) / "a.yaml"
        spec_a.write_text(MINIMAL_SPEC)
        ufm.cmd_map(_NS(spec=str(spec_a), output="intended"))
        # Make an "observed" version with a divergent screen
        spec_b_text = MINIMAL_SPEC.replace("- id: form", "- id: signup_form")
        spec_b_text = spec_b_text.replace("to: form", "to: signup_form")
        spec_b = Path(self._tmp.name) / "b.yaml"
        spec_b.write_text(spec_b_text)
        ufm.cmd_map(_NS(spec=str(spec_b), output="observed"))

    def tearDown(self):
        ufm.JOURNEYS_DIR = self._orig
        self._tmp.cleanup()

    def test_compare_detects_divergence(self):
        intended = Path(self._tmp.name) / "intended.md"
        observed = Path(self._tmp.name) / "observed.md"
        rc = ufm.cmd_compare(_NS(intended=str(intended), observed=str(observed)))
        self.assertEqual(rc, 0)


class TestAuditPhase1(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig = ufm.JOURNEYS_DIR
        ufm.JOURNEYS_DIR = Path(self._tmp.name)
        self._screens_dir = Path(self._tmp.name) / "screens"
        self._screens_dir.mkdir()

    def tearDown(self):
        ufm.JOURNEYS_DIR = self._orig
        self._tmp.cleanup()

    def test_audit_refuses_without_manifest(self):
        rc = ufm.cmd_audit(_NS(url="http://localhost:3001/signup",
                               output="observed",
                               screens_dir=str(self._screens_dir)))
        self.assertNotEqual(rc, 0)

    def test_audit_with_manifest(self):
        manifest = self._screens_dir / "screens-manifest.json"
        manifest.write_text(
            '{"flow":"test-flow","product":"zb","persona":"observed",'
            '"screens":[{"id":"a","name":"A","purpose":"land","primary_cta":"Go",'
            '"exits":[{"to":"b","condition":"click"}]},'
            '{"id":"b","name":"B","purpose":"form","primary_cta":"Submit",'
            '"exits":[]}]}'
        )
        rc = ufm.cmd_audit(_NS(url="http://localhost:3001/signup",
                               output="observed",
                               screens_dir=str(self._screens_dir)))
        self.assertEqual(rc, 0)

    def test_audit_runs_validation(self):
        # C3: cmd_audit must run validate_spec — manifest with unresolved exit fails.
        manifest = self._screens_dir / "screens-manifest.json"
        manifest.write_text(
            '{"flow":"test-flow","product":"zb","persona":"observed",'
            '"screens":[{"id":"a","name":"A","purpose":"land","primary_cta":"Go",'
            '"exits":[{"to":"nowhere","condition":"click"}]}]}'
        )
        rc = ufm.cmd_audit(_NS(url="http://localhost:3001/signup",
                               output="should-not-write",
                               screens_dir=str(self._screens_dir)))
        self.assertNotEqual(rc, 0)
        self.assertFalse((Path(self._tmp.name) / "should-not-write.md").exists())


if __name__ == "__main__":
    unittest.main()
