#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import run_fakeidan
import validate_manifest as validator


def valid_manifest() -> dict:
    return {
        "schema_version": 3,
        "verdict": "Approve",
        "status": "PASSED",
        "review_files": ["/tmp/review.md"],
        "verdicts": [{"path": "/tmp/review.md", "verdict": "Approve"}],
        "manifest_path": "/tmp/manifest.json",
        "error": None,
        "claude_bin": "default",
        "xmodel_review": None,
        "xmodel_status": None,
    }


class ValidateManifestTest(unittest.TestCase):
    def test_schema_version_constants_are_synchronized(self) -> None:
        self.assertEqual(run_fakeidan.MANIFEST_SCHEMA_VERSION, validator.MANIFEST_SCHEMA_VERSION)

    def test_valid_manifest(self) -> None:
        self.assertEqual(validator.validate_manifest(valid_manifest()), [])

    def test_rejects_unknown_and_missing_keys(self) -> None:
        payload = valid_manifest()
        payload.pop("review_files")
        payload["extra"] = True
        errors = validator.validate_manifest(payload)
        self.assertTrue(
            any("missing manifest keys" in e and "review_files" in e for e in errors),
            f"expected a missing-keys error mentioning review_files; got {errors!r}",
        )
        self.assertIn("unknown manifest keys: extra", errors)

    def test_xmodel_status_validated(self) -> None:
        payload = valid_manifest()
        payload["xmodel_status"] = "garbage"
        errors = validator.validate_manifest(payload)
        self.assertTrue(any("invalid xmodel_status" in e for e in errors),
                        f"expected xmodel_status validation error; got {errors!r}")

    def test_passed_status_rejects_high_xmodel(self) -> None:
        payload = valid_manifest()
        payload["xmodel_status"] = "high"
        errors = validator.validate_manifest(payload)
        self.assertIn("PASSED manifests cannot have xmodel_status='high'", errors)

    def test_passed_requires_approve(self) -> None:
        payload = valid_manifest()
        payload["verdict"] = "Recommend changes"
        self.assertIn("PASSED manifests must have an Approve verdict", validator.validate_manifest(payload))

    def test_manifest_path_must_be_string(self) -> None:
        payload = valid_manifest()
        payload["manifest_path"] = None
        self.assertIn("manifest_path must be a string", validator.validate_manifest(payload))

    def test_error_must_be_string_or_null(self) -> None:
        payload = valid_manifest()
        payload["error"] = {"message": "bad"}
        self.assertIn("error must be a string or null", validator.validate_manifest(payload))

    def test_main_outputs_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps(valid_manifest()))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(validator.main([str(path)]), 0)


if __name__ == "__main__":
    unittest.main()
