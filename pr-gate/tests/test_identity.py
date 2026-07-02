#!/usr/bin/env python3
"""Tests for pr-gate GitHub account routing."""

from __future__ import annotations

import importlib.util
import pathlib
import types
import unittest


RUN_PATH = pathlib.Path(__file__).resolve().parents[1] / "run.py"
SPEC = importlib.util.spec_from_file_location("pr_gate_run", RUN_PATH)
pr_gate_run = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(pr_gate_run)


def args(*, matt_personal=False, matt_led=False, ai_led=False):
    return types.SimpleNamespace(
        matt_personal=matt_personal,
        matt_led=matt_led,
        ai_led=ai_led,
    )


class GitHubIdentityRoutingTest(unittest.TestCase):
    def setUp(self):
        self.original_remote_owner = pr_gate_run.github_remote_owner

    def tearDown(self):
        pr_gate_run.github_remote_owner = self.original_remote_owner

    def set_remote_owner(self, owner):
        pr_gate_run.github_remote_owner = lambda: owner

    def test_matteisn_remote_is_personal(self):
        self.set_remote_owner("matteisn")

        account, reason = pr_gate_run.required_github_account(args())

        self.assertEqual(account, "matteisn")
        self.assertEqual(reason, "Matt personal project")

    def test_mattheweisner_remote_is_personal(self):
        self.set_remote_owner("mattheweisner")

        account, reason = pr_gate_run.required_github_account(args())

        self.assertEqual(account, "matteisn")
        self.assertEqual(reason, "Matt personal project")

    def test_matt_personal_flag_requires_matteisn(self):
        self.set_remote_owner("zerg-ai")

        account, reason = pr_gate_run.required_github_account(args(matt_personal=True))

        self.assertEqual(account, "matteisn")
        self.assertEqual(reason, "Matt personal project")

    def test_matt_led_flag_requires_matteisn(self):
        self.set_remote_owner("zerg-ai")

        account, reason = pr_gate_run.required_github_account(args(matt_led=True))

        self.assertEqual(account, "matteisn")
        self.assertEqual(reason, "Matt-led/heavily supervised PR")

    def test_ai_led_non_personal_requires_mattzerg(self):
        self.set_remote_owner("zerg-ai")

        account, reason = pr_gate_run.required_github_account(args(ai_led=True))

        self.assertEqual(account, "mattzerg")
        self.assertEqual(reason, "AI/Fake Matt-led PR")

    def test_default_non_personal_agent_path_requires_mattzerg(self):
        self.set_remote_owner("zerg-ai")

        account, reason = pr_gate_run.required_github_account(args())

        self.assertEqual(account, "mattzerg")
        self.assertEqual(reason, "default agent-led non-personal PR")


if __name__ == "__main__":
    unittest.main()
