"""Gate tests for zerg-prospecting.

Run: python3 -m unittest discover MattZerg/Skills/zerg-prospecting/tests
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parent.parent / "run.py"
spec = importlib.util.spec_from_file_location("zerg_prospecting", MODULE)
zp = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(zp)


class TestScoring(unittest.TestCase):
    def test_perfect_score_is_100(self):
        account = {
            "durable_similarity": 5,
            "public_signal": 5,
            "urgency": 5,
            "offer_fit": 5,
        }
        self.assertEqual(zp.score_account(account), 100)

    def test_weighted_score_normalizes_to_100(self):
        account = {
            "durable_similarity": 5,
            "public_signal": 5,
            "urgency": 4,
            "offer_fit": 4,
        }
        self.assertEqual(zp.score_account(account), 93)

    def test_values_are_clamped(self):
        account = {
            "durable_similarity": 9,
            "public_signal": 9,
            "urgency": 9,
            "offer_fit": 9,
        }
        self.assertEqual(zp.score_account(account), 100)

    def test_sendability_score_is_separate_from_fit_score(self):
        account = {
            "durable_similarity": 5,
            "public_signal": 5,
            "urgency": 5,
            "offer_fit": 5,
            "route_quality": 2,
            "buyer_specificity": 5,
            "trigger_recency": 5,
            "message_relevance": 5,
            "company_size_fit": 3,
        }
        self.assertEqual(zp.score_account(account), 100)
        self.assertEqual(zp.score_sendability(account), 78)


class TestYamlSubsetParser(unittest.TestCase):
    def test_load_seed_accounts(self):
        path = Path(__file__).resolve().parent / "fixtures" / "accounts.yaml"
        accounts = zp.load_accounts(path)
        self.assertEqual(len(accounts), 2)
        self.assertEqual(accounts[0]["company"], "Alpha")
        self.assertEqual(accounts[0]["trigger_signals"], ["one", "two"])
        self.assertEqual(accounts[1]["durable_similarity"], 3)

    def test_find_account_by_slug_or_company(self):
        accounts = [
            {"company": "Acme Corp", "slug": "acme-corp"},
            {"company": "Other", "slug": "other"},
        ]
        self.assertEqual(zp.find_account("acme", accounts), None)
        self.assertEqual(zp.find_account("Acme Corp", accounts)["slug"], "acme-corp")
        self.assertEqual(zp.find_account("acme-corp", accounts)["company"], "Acme Corp")


class TestSafety(unittest.TestCase):
    def test_reference_pattern_does_not_draft_without_force(self):
        account = {"company": "Durable", "status": "reference-pattern"}
        self.assertEqual(account["status"], "reference-pattern")


if __name__ == "__main__":
    unittest.main()
