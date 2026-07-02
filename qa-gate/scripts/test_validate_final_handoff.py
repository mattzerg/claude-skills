#!/usr/bin/env python3
from __future__ import annotations

import unittest

import validate_final_handoff as validator


def handoff(**overrides: str) -> str:
    values = {
        "change": "wire qa-gate into pr-gate",
        "initial": "Medium",
        "final": "Medium",
        "evidence": "none",
        "verdict": "Approve",
        "output_paths": "/tmp/review.md",
        "findings_addressed": "none",
        "findings_deferred": "none",
        "tests_after": "python3 test_validate_final_handoff.py - OK",
        "not_run": "none",
        "status": "PASSED",
    }
    values.update(overrides)
    return "\n".join(
        [
            f"- Change: {values['change']}",
            f"- Risk tier (initial): {values['initial']}",
            f"- Risk tier (final): {values['final']}",
            f"- De-escalation evidence: {values['evidence']}",
            f"- `fakeidan verdict`: {values['verdict']}",
            f"- `fakeidan output paths`: {values['output_paths']}",
            f"- `fakeidan findings addressed`: {values['findings_addressed']}",
            f"- `fakeidan findings deferred / inapplicable`: {values['findings_deferred']}",
            f"- Tests after fixes: {values['tests_after']}",
            f"- Not run / not cleared: {values['not_run']}",
            f"- `qa-gate status`: {values['status']}",
        ]
    )


class ValidateFinalHandoffTest(unittest.TestCase):
    def test_valid_handoff(self) -> None:
        self.assertEqual(validator.validate(handoff()), [])

    def test_deescalation_requires_evidence(self) -> None:
        errors = validator.validate(handoff(initial="High", final="Low", evidence="none"))
        self.assertIn("risk tier de-escalated without evidence", errors)

    def test_deescalation_rejects_na_evidence(self) -> None:
        errors = validator.validate(handoff(initial="High", final="Low", evidence="na"))
        self.assertIn("risk tier de-escalated without evidence", errors)

    def test_valid_deescalation_with_evidence(self) -> None:
        errors = validator.validate(
            handoff(initial="High", final="Low", evidence="see commit abc123: narrower scope")
        )
        self.assertEqual(errors, [])

    def test_deescalation_evidence_can_contain_colon(self) -> None:
        errors = validator.validate(handoff(initial="High", final="Medium", evidence="see commit abc123: narrower scope"))
        self.assertEqual(errors, [])

    def test_multiline_field_values_are_captured_until_next_bullet(self) -> None:
        text = handoff(
            initial="High",
            final="Low",
            evidence="see commit abc123:\n  - narrowed scope\n  - added tests",
        )
        self.assertEqual(validator.field(text, "De-escalation evidence"), "see commit abc123:\n  - narrowed scope\n  - added tests")
        self.assertEqual(validator.validate(text), [])

    def test_unindented_internal_bullet_reports_parse_boundary_error(self) -> None:
        text = handoff(
            evidence="see commit abc123:\n- but kept item validation",
        )
        errors = validator.validate(text)
        self.assertIn(
            "unrecognized top-level handoff bullet `but kept item validation`; indent internal bullets inside field values",
            errors,
        )

    def test_handoff_helper_allows_braces_in_values(self) -> None:
        text = handoff(change="fix parser for {braced} values")
        self.assertIn("fix parser for {braced} values", text)

    def test_unable_to_run_cannot_pass(self) -> None:
        errors = validator.validate(handoff(verdict="UNABLE_TO_RUN", status="PASSED"))
        self.assertIn("qa-gate cannot pass when fakeidan is UNABLE_TO_RUN", errors)

    def test_unable_to_run_can_be_blocked(self) -> None:
        errors = validator.validate(handoff(verdict="UNABLE_TO_RUN", status="BLOCKED"))
        self.assertEqual(errors, [])

    def test_change_is_required(self) -> None:
        errors = validator.validate(handoff(change=""))
        self.assertIn("missing Change", errors)

    def test_passed_gate_requires_tests_after_fixes(self) -> None:
        errors = validator.validate(handoff(tests_after="none"))
        self.assertIn("PASSED gate requires Tests after fixes evidence", errors)

    def test_passed_gate_requires_findings_addressed_field(self) -> None:
        text = handoff().replace("- `fakeidan findings addressed`: none\n", "")
        errors = validator.validate(text)
        self.assertIn("missing `fakeidan findings addressed`", errors)

    def test_blocked_gate_allows_missing_test_evidence_but_requires_field(self) -> None:
        errors = validator.validate(handoff(status="BLOCKED", verdict="Recommend changes", tests_after="none"))
        self.assertEqual(errors, [])

    def test_blocked_gate_still_requires_findings_addressed_field(self) -> None:
        text = handoff(status="BLOCKED", verdict="Recommend changes").replace(
            "- `fakeidan findings addressed`: none\n", ""
        )
        errors = validator.validate(text)
        self.assertIn("missing `fakeidan findings addressed`", errors)


if __name__ == "__main__":
    unittest.main()
