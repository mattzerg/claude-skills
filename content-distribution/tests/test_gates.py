"""Smoke tests for content-distribution after the 2026-05-28 17-surface rewrite.
Run with: python3 -m unittest content-distribution/tests/test_gates.py
"""
import importlib.util
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "content_distribution",
    str(Path(__file__).resolve().parents[1] / "run.py"),
)
cd = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cd)


class SurfaceCountTest(unittest.TestCase):
    def test_seventeen_canonical_surfaces(self):
        self.assertEqual(len(cd.SURFACES), 17)

    def test_surfaces_are_named(self):
        # SURFACES is a list of (name, description, medium) tuples.
        for s in cd.SURFACES:
            self.assertEqual(len(s), 3, f"surface tuple wrong shape: {s}")
            name, description, medium = s
            self.assertTrue(name, f"surface missing name: {s}")
            self.assertTrue(medium, f"surface missing medium: {s}")


class UtmBuilderTest(unittest.TestCase):
    def test_build_utm_link_basic(self):
        base = "https://test-zerg.com/"
        url = cd.build_utm_link(
            base=base,
            source="twitter",
            medium="social",
            campaign="test-zerg-launch-T0",
        )
        self.assertIn("utm_source=twitter", url)
        self.assertIn("utm_medium=social", url)
        self.assertIn("utm_campaign=test-zerg-launch-T0", url)


if __name__ == "__main__":
    unittest.main()
