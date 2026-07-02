#!/usr/bin/env python3
"""Smoke tests for ship-gate/run.py's fail-closed contract.

Pins the three load-bearing behaviors: a missing artifact can never pass, a
crashing tool becomes a synthetic HIGH (silence isn't approval), and the happy
path emits a parseable manifest. Mirrors qa-gate's in-skill stdlib-unittest
test style.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RUN = Path(__file__).resolve().parent.parent / "run.py"

# Fake tool that dies with an unhandled exception: exit 1, traceback on
# stderr, NO status header on stdout — the exact shape run.py must refuse
# to read as a legit yellow finding.
CRASHING_TOOL = "raise RuntimeError('boom')\n"

# Fake tool that PRINTS a red status but exits clean — the silence-as-approval
# shape (a future edit dropping sys.exit(main())) that the header/exit-code
# cross-validation must catch.
LYING_TOOL = 'print("# check — RED (3 hex literals)")\n'

# Fake tool with a legit yellow finding: header + exit 1 → MEDIUM → YELLOW.
# Pins the most confusable part of the contract (tool exit 1 → gate exit 2).
YELLOW_TOOL = 'import sys\nprint("# check — YELLOW (1 soft finding)")\nsys.exit(1)\n'

# Fake tool that exits 0 with NO header — contract drift, not a clean pass.
SILENT_TOOL = 'pass\n'


def run_gate(*args: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(RUN), *args],
        capture_output=True, text=True, env=env, timeout=120,
    )


class MissingArtifactTest(unittest.TestCase):
    def test_missing_artifact_is_red_exit_1(self):
        proc = run_gate("/nonexistent/ship-gate-smoke/page.html", "--json")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        manifest = json.loads(proc.stdout)
        self.assertEqual(manifest["verdict"], "RED")
        self.assertTrue(any(c["synthetic"] for c in manifest["checks"]))
        self.assertTrue(any(f["severity"] == "HIGH" for f in manifest["findings"]))


class FailClosedTest(unittest.TestCase):
    def test_crashing_tool_yields_synthetic_high_and_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            tools = Path(tmp) / "tools"
            tools.mkdir()
            for name in ("check_palette.py", "check_brand_hex_literals.py"):
                (tools / name).write_text(CRASHING_TOOL)
            fixture = Path(tmp) / "page.html"
            fixture.write_text("<main><h1>hello</h1></main>\n")
            proc = run_gate(str(fixture), "--type", "page", "--json",
                            env_extra={"SHIP_GATE_TOOLS_DIR": str(tools)})
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            manifest = json.loads(proc.stdout)
            self.assertEqual(manifest["verdict"], "RED")
            self.assertTrue(all(c["synthetic"] for c in manifest["checks"]), manifest)
            self.assertTrue(
                any("FAIL-CLOSED" in (c["finding"] or "") for c in manifest["checks"]),
                manifest,
            )
            self.assertTrue(any(f["severity"] == "HIGH" for f in manifest["findings"]))


class HeaderExitMismatchTest(unittest.TestCase):
    def test_red_header_with_exit_0_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tools = Path(tmp) / "tools"
            tools.mkdir()
            for name in ("check_palette.py", "check_brand_hex_literals.py"):
                (tools / name).write_text(LYING_TOOL)
            fixture = Path(tmp) / "page.html"
            fixture.write_text("<main><h1>hello</h1></main>\n")
            proc = run_gate(str(fixture), "--type", "page", "--json",
                            env_extra={"SHIP_GATE_TOOLS_DIR": str(tools)})
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            manifest = json.loads(proc.stdout)
            self.assertEqual(manifest["verdict"], "RED")
            self.assertTrue(
                any("header/exit-code mismatch" in (c["finding"] or "")
                    for c in manifest["checks"]),
                manifest,
            )


class YellowPathTest(unittest.TestCase):
    def test_tool_exit_1_maps_to_medium_yellow_gate_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            tools = Path(tmp) / "tools"
            tools.mkdir()
            for name in ("check_palette.py", "check_brand_hex_literals.py"):
                (tools / name).write_text(YELLOW_TOOL)
            fixture = Path(tmp) / "page.html"
            fixture.write_text("<main><h1>hello</h1></main>\n")
            proc = run_gate(str(fixture), "--type", "page", "--json",
                            env_extra={"SHIP_GATE_TOOLS_DIR": str(tools)})
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            manifest = json.loads(proc.stdout)
            self.assertEqual(manifest["verdict"], "YELLOW")
            self.assertTrue(all(c["severity"] == "MEDIUM" for c in manifest["checks"]))
            self.assertFalse(any(c["synthetic"] for c in manifest["checks"]))


class SilentToolTest(unittest.TestCase):
    def test_exit_0_with_no_header_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tools = Path(tmp) / "tools"
            tools.mkdir()
            for name in ("check_palette.py", "check_brand_hex_literals.py"):
                (tools / name).write_text(SILENT_TOOL)
            fixture = Path(tmp) / "page.html"
            fixture.write_text("<main><h1>hello</h1></main>\n")
            proc = run_gate(str(fixture), "--type", "page", "--json",
                            env_extra={"SHIP_GATE_TOOLS_DIR": str(tools)})
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            manifest = json.loads(proc.stdout)
            self.assertEqual(manifest["verdict"], "RED")
            self.assertTrue(all(c["synthetic"] for c in manifest["checks"]), manifest)
            self.assertTrue(
                any("no parseable" in (c["finding"] or "") for c in manifest["checks"]),
                manifest,
            )


class HappyPathTest(unittest.TestCase):
    def test_clean_fixture_emits_parseable_green_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "page.html"
            fixture.write_text('<main class="bg-cream"><h1>hello</h1></main>\n')
            proc = run_gate(str(fixture), "--type", "page", "--json")
            manifest = json.loads(proc.stdout)
            self.assertEqual(manifest["verdict"], "GREEN", manifest)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            # local page → palette-classify + brand-hex-literals, both real tools
            self.assertEqual(len(manifest["checks"]), 2)
            self.assertFalse(any(c["synthetic"] for c in manifest["checks"]))

    def test_human_summary_mode_runs_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "page.html"
            fixture.write_text("<main><h1>hello</h1></main>\n")
            proc = run_gate(str(fixture), "--type", "page")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("ship-gate — GREEN", proc.stdout)


if __name__ == "__main__":
    unittest.main()
