"""Golden routing eval — canonical signals × expected model class.

Detects drift in routing behavior when the ranker or routing_table changes.
Pass when >= threshold of cases match.

When this fails, the user should either:
  1. Fix the regression in ranker.py or routing_table.json, OR
  2. Update golden_routing.json with the new intended behavior (write WHY)
"""
import json
from pathlib import Path

import pytest

from ranker import RankerError, rank

SNAPSHOT = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "snapshot" / "search.json").read_text()
)
ROUTING_TABLE = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "routing_table.json").read_text()
)
GOLDEN = json.loads(
    (Path(__file__).resolve().parent / "golden" / "golden_routing.json").read_text()
)


def _evaluate_case(case: dict) -> tuple[bool, str]:
    sig = case["signal"]
    # Ensure required fields
    sig.setdefault("artifact_size_tokens", 4000)
    sig.setdefault("quality_floor", "medium")
    sig.setdefault("provider_constraint", "any")
    expected = set(case["expected_classes"])
    active_provider = case.get("active_provider")

    # Delegate case: ranker should NOT be the routing decision; we check via routing_table
    if "_delegate_" in expected:
        task_rules = ROUTING_TABLE["task_kinds"].get(sig["task_kind"], {})
        if task_rules.get("delegate_to"):
            return True, f"delegates to {task_rules['delegate_to']}"
        return False, "expected delegation but routing_table has no delegate_to"

    try:
        out = rank(sig, SNAPSHOT, ROUTING_TABLE, active_provider=active_provider)
    except RankerError as exc:
        return False, f"ranker raised: {exc}"

    if not out:
        return False, "no candidates"
    top_class = out[0].model_class
    if top_class in expected:
        return True, f"picked {top_class} (top: {out[0].model})"
    return False, f"picked {top_class!r} (top: {out[0].model}); expected {sorted(expected)}"


def test_golden_routing_meets_threshold():
    threshold = float(GOLDEN["threshold"])
    cases = GOLDEN["cases"]
    results = [(c["name"], _evaluate_case(c)) for c in cases]

    passed = sum(1 for _, (ok, _) in results if ok)
    rate = passed / len(results)

    if rate < threshold:
        failures = [f"  - {name}: {detail}" for name, (ok, detail) in results if not ok]
        msg = (
            f"\nGolden routing drift: {passed}/{len(results)} ({rate:.0%}) "
            f"below threshold {threshold:.0%}.\n"
            "Failures:\n" + "\n".join(failures) + "\n\n"
            "Either fix the ranker/routing_table or update golden_routing.json "
            "(with a comment on WHY the new behavior is correct)."
        )
        pytest.fail(msg)


@pytest.mark.parametrize("case", GOLDEN["cases"], ids=lambda c: c["name"])
def test_individual_case_diagnostic(case):
    """Individual diagnostics — these MAY fail per case while the suite passes
    overall via the threshold test above. Useful for debugging drift."""
    ok, detail = _evaluate_case(case)
    if not ok:
        pytest.skip(f"{case['name']}: {detail}")
