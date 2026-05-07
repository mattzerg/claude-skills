"""utm-attribution gate tests — stdlib-only.

Run: python3 -m unittest discover ~/.claude/skills/utm-attribution/tests

Tests the load-bearing gates: zerg-domain-only, kebab-case enforcement, PII
detection, required-fields enforcement. If any of these regress, the dashboard
lies (UTM ledger gets non-Zerg or PII-bearing rows).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from run import build_url, kebab_check, is_zerg_domain, validate_url, UTMError  # noqa: E402


class TestZergDomainGate(unittest.TestCase):
    """Refuses non-Zerg destinations. Important so we don't track outbound."""

    def test_accepts_zergai_com(self):
        self.assertTrue(is_zerg_domain("https://zergai.com/zergboard"))
        self.assertTrue(is_zerg_domain("https://www.zergai.com/x"))
        self.assertTrue(is_zerg_domain("https://app.zergai.com/x"))
        self.assertTrue(is_zerg_domain("https://zerglytics.fly.dev"))

    def test_rejects_non_zerg(self):
        self.assertFalse(is_zerg_domain("https://linear.app"))
        self.assertFalse(is_zerg_domain("https://zergai.example.com"))
        self.assertFalse(is_zerg_domain(""))

    def test_build_refuses_non_zerg_destination(self):
        with self.assertRaises(UTMError):
            build_url(
                destination="https://linear.app/pricing",
                source="twitter", medium="social", campaign="welcome-drip",
                content=None, term=None, register_campaign=True, register_source=True,
            )


class TestKebabCaseGate(unittest.TestCase):
    """Refuses non-kebab-case values. Prevents inconsistent UTM analytics."""

    def test_accepts_kebab(self):
        kebab_check("welcome-drip", "campaign")  # no raise
        kebab_check("variant-a-step-1", "content")
        kebab_check("twitter", "source")

    def test_rejects_camel_or_underscore(self):
        for bad in ("welcomeDrip", "welcome_drip", "WELCOME-DRIP", "welcome drip", "welcome--drip"):
            with self.assertRaises(UTMError, msg=f"should reject {bad!r}"):
                kebab_check(bad, "campaign")


class TestPIIGate(unittest.TestCase):
    """Refuses email-shaped or whitespace-bearing values (rough PII guard)."""

    def test_rejects_at_sign(self):
        with self.assertRaises(UTMError):
            kebab_check("matt@zergai.com", "content")

    def test_rejects_whitespace(self):
        with self.assertRaises(UTMError):
            kebab_check("welcome drip", "campaign")


class TestRequiredFields(unittest.TestCase):
    """Build refuses missing required fields. Without it, dashboard lies."""

    def test_refuses_empty_source(self):
        with self.assertRaises(UTMError):
            build_url(
                destination="https://zergai.com/zergboard",
                source="", medium="social", campaign="welcome-drip",
                content=None, term=None, register_campaign=True, register_source=True,
            )

    def test_refuses_invalid_medium(self):
        with self.assertRaises(UTMError):
            build_url(
                destination="https://zergai.com/zergboard",
                source="twitter", medium="bogus-medium", campaign="welcome-drip",
                content=None, term=None, register_campaign=True, register_source=True,
            )

    def test_accepts_valid_minimum(self):
        url = build_url(
            destination="https://zergai.com/zergboard",
            source="twitter", medium="social", campaign="welcome-drip",
            content=None, term=None, register_campaign=True, register_source=True,
        )
        self.assertIn("utm_source=twitter", url)
        self.assertIn("utm_medium=social", url)
        self.assertIn("utm_campaign=welcome-drip", url)


class TestValidateMode(unittest.TestCase):
    """validate_url surfaces missing utm params + non-zerg domain."""

    def test_validate_clean_link(self):
        result = validate_url(
            "https://zergai.com/x?utm_source=twitter&utm_medium=social&utm_campaign=welcome-drip"
        )
        self.assertEqual(result["errors"], [])

    def test_validate_missing_required(self):
        result = validate_url("https://zergai.com/x?utm_source=twitter")
        self.assertTrue(any("utm_medium" in e for e in result["errors"]))
        self.assertTrue(any("utm_campaign" in e for e in result["errors"]))

    def test_validate_non_zerg_domain(self):
        result = validate_url(
            "https://linear.app?utm_source=x&utm_medium=social&utm_campaign=y"
        )
        self.assertTrue(any("not a Zerg domain" in e for e in result["errors"]))


if __name__ == "__main__":
    unittest.main()
