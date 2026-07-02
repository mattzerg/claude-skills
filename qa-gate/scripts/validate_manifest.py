#!/usr/bin/env python3
"""Validate a qa-gate fakeidan manifest JSON file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


# Must match run_fakeidan.py; update both when changing manifest shape.
MANIFEST_SCHEMA_VERSION = 3
MANIFEST_KEYS = {"schema_version", "verdict", "status", "review_files", "verdicts", "manifest_path", "error", "claude_bin", "xmodel_review", "xmodel_status"}
VERDICTS = {"Approve", "Recommend changes", "Changes requested", "UNABLE_TO_RUN"}
PER_REVIEW_VERDICTS = VERDICTS - {"UNABLE_TO_RUN"}
STATUSES = {"PASSED", "BLOCKED"}
XMODEL_STATUSES = {None, "ok", "high", "skipped"}


def validate_manifest(payload: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["manifest must be a JSON object"]

    keys = set(payload)
    missing = MANIFEST_KEYS - keys
    unknown = keys - MANIFEST_KEYS
    if missing:
        errors.append(f"missing manifest keys: {', '.join(sorted(missing))}")
    if unknown:
        errors.append(f"unknown manifest keys: {', '.join(sorted(unknown))}")

    if payload.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        errors.append("missing or invalid schema_version")
    if payload.get("verdict") not in VERDICTS:
        errors.append("missing or invalid verdict")
    if payload.get("status") not in STATUSES:
        errors.append("missing or invalid status")
    if payload.get("status") == "PASSED" and payload.get("verdict") != "Approve":
        errors.append("PASSED manifests must have an Approve verdict")
    if payload.get("status") == "PASSED" and payload.get("xmodel_status") == "high":
        errors.append("PASSED manifests cannot have xmodel_status='high'")

    review_files = payload.get("review_files")
    if not isinstance(review_files, list) or not all(isinstance(item, str) for item in review_files):
        errors.append("review_files must be a list of strings")

    verdicts = payload.get("verdicts")
    if not isinstance(verdicts, list):
        errors.append("verdicts must be a list")
    else:
        for index, item in enumerate(verdicts):
            if not isinstance(item, dict):
                errors.append(f"verdicts[{index}] must be an object")
                continue
            if set(item) != {"path", "verdict"}:
                errors.append(f"verdicts[{index}] must contain path and verdict only")
            if not isinstance(item.get("path"), str):
                errors.append(f"verdicts[{index}].path must be a string")
            if item.get("verdict") not in PER_REVIEW_VERDICTS:
                errors.append(f"verdicts[{index}].verdict is invalid")

    if not isinstance(payload.get("manifest_path"), str):
        errors.append("manifest_path must be a string")

    error = payload.get("error")
    if error is not None and not isinstance(error, str):
        errors.append("error must be a string or null")

    claude_bin = payload.get("claude_bin")
    if claude_bin is not None and not isinstance(claude_bin, str):
        errors.append("claude_bin must be a string or null")

    xmodel_review = payload.get("xmodel_review")
    if xmodel_review is not None and not isinstance(xmodel_review, str):
        errors.append("xmodel_review must be a string or null")

    if payload.get("xmodel_status") not in XMODEL_STATUSES:
        errors.append("invalid xmodel_status (must be null, 'ok', 'high', or 'skipped')")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest_file", help="qa-gate manifest JSON file")
    args = parser.parse_args(argv)

    path = Path(args.manifest_file).expanduser()
    try:
        payload = json.loads(path.read_text())
    except OSError as exc:
        parser.error(f"could not read manifest file: {exc}")
    except json.JSONDecodeError as exc:
        parser.error(f"could not parse manifest JSON: {exc}")

    errors = validate_manifest(payload)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("qa-gate manifest valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
