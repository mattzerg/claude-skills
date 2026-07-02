#!/usr/bin/env python3
"""Validate the structured qa-gate Final Handoff block.

Expected markdown shape:

- Change: wire qa-gate into pr-gate
- Risk tier (initial): Medium, because the PR workflow changed
- Risk tier (final): Medium
- De-escalation evidence: none
- `fakeidan verdict`: Approve
- `fakeidan output paths`: /tmp/review.md
- `fakeidan findings addressed`: fixed validator issues:
  - multiline field values
  - none-ish evidence handling
- `fakeidan findings deferred / inapplicable`: none
- Tests after fixes: python3 test_run_fakeidan.py - OK
- Not run / not cleared: none
- `qa-gate status`: PASSED

Continuation lines inside a value must be indented. Unindented internal bullets
look like new fields and are rejected with a parse-boundary error.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


TIERS = {"Low": 1, "Medium": 2, "High": 3}
STATUSES = {"PASSED", "BLOCKED", "WAIVED_BY_USER"}
# UNABLE_TO_RUN is set when fakeidan cannot produce a structured review; it is
# compatible with BLOCKED handoffs and must never be paired with PASSED.
VERDICTS = {"Approve", "Recommend changes", "Changes requested", "UNABLE_TO_RUN"}
FIELD_LABELS = [
    "Change",
    "Risk tier (initial)",
    "Risk tier (final)",
    "De-escalation evidence",
    "`fakeidan verdict`",
    "`fakeidan output paths`",
    "`fakeidan findings addressed`",
    "`fakeidan findings deferred / inapplicable`",
    "Tests after fixes",
    "Not run / not cleared",
    "`qa-gate status`",
]
FIELD_LABEL_SET = set(FIELD_LABELS)


def field(text: str, label: str) -> str | None:
    """Extract `- Label: Value`, allowing continuation lines until the next bullet."""
    pattern = rf"^- {re.escape(label)}:[^\S\r\n]*(.*?)(?=^- [^\r\n]+:|\Z)"
    match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else None


def validate(text: str) -> list[str]:
    errors: list[str] = []
    errors.extend(parse_boundary_errors(text))
    change = field(text, "Change")
    initial = field(text, "Risk tier (initial)")
    final = field(text, "Risk tier (final)")
    evidence = field(text, "De-escalation evidence")
    verdict = field(text, "`fakeidan verdict`")
    output_paths = field(text, "`fakeidan output paths`")
    findings_addressed = field(text, "`fakeidan findings addressed`")
    findings_deferred = field(text, "`fakeidan findings deferred / inapplicable`")
    tests_after = field(text, "Tests after fixes")
    not_run = field(text, "Not run / not cleared")
    status = field(text, "`qa-gate status`")

    if is_missing_or_blank(change):
        errors.append("missing Change")
    if initial not in TIERS:
        errors.append("missing or invalid Risk tier (initial)")
    if final not in TIERS:
        errors.append("missing or invalid Risk tier (final)")
    if evidence is None:
        errors.append("missing De-escalation evidence")
    if verdict not in VERDICTS:
        errors.append("missing or invalid `fakeidan verdict`")
    if output_paths is None:
        errors.append("missing `fakeidan output paths`")
    if findings_addressed is None:
        errors.append("missing `fakeidan findings addressed`")
    if findings_deferred is None:
        errors.append("missing `fakeidan findings deferred / inapplicable`")
    if tests_after is None:
        errors.append("missing Tests after fixes")
    if not_run is None:
        errors.append("missing Not run / not cleared")
    if status not in STATUSES:
        errors.append("missing or invalid `qa-gate status`")

    if initial in TIERS and final in TIERS and TIERS[final] < TIERS[initial]:
        if is_missing_or_blank(evidence) or is_noneish_response(evidence):
            errors.append("risk tier de-escalated without evidence")

    if status == "PASSED" and verdict == "UNABLE_TO_RUN":
        errors.append("qa-gate cannot pass when fakeidan is UNABLE_TO_RUN")
    if status == "PASSED":
        if is_missing_or_blank(tests_after) or is_noneish_response(tests_after):
            errors.append("PASSED gate requires Tests after fixes evidence")
        if is_missing_or_blank(findings_addressed):
            errors.append("PASSED gate requires `fakeidan findings addressed`")
    return errors


def parse_boundary_errors(text: str) -> list[str]:
    errors: list[str] = []
    for line in text.splitlines():
        if not line.startswith("- "):
            continue
        label, sep, _value = line[2:].partition(":")
        if not sep:
            errors.append(f"unrecognized top-level handoff bullet `{line[2:]}`; indent internal bullets inside field values")
        elif label not in FIELD_LABEL_SET:
            errors.append(f"unrecognized top-level handoff field `{label}`; indent internal bullets inside field values")
    return errors


def is_missing_or_blank(value: str | None) -> bool:
    return value is None or value.strip() == ""


def is_noneish_response(value: str | None) -> bool:
    return value is not None and value.strip().lower() in {"none", "n/a", "na"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("handoff_file", help="Markdown file containing the qa-gate final handoff")
    args = parser.parse_args(argv)

    path = Path(args.handoff_file).expanduser()
    try:
        text = path.read_text()
    except OSError as exc:
        parser.error(f"could not read handoff file: {exc}")

    errors = validate(text)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("qa-gate handoff valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
