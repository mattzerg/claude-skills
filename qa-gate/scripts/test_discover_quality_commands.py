#!/usr/bin/env python3
from __future__ import annotations

import json
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import discover_quality_commands as discover


class DiscoverQualityCommandsTest(unittest.TestCase):
    def test_mixed_repo_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".github" / "workflows").mkdir(parents=True)
            (root / "tests").mkdir()
            (root / "package.json").write_text(
                json.dumps(
                    {
                        "packageManager": "pnpm@9.0.0",
                        "scripts": {
                            "build": "vite build",
                            "lint": "eslint .",
                            "test": "vitest run",
                            "typecheck": "tsc --noEmit",
                        },
                    }
                )
            )
            (root / "pyproject.toml").write_text(
                "\n".join(
                    [
                        "[tool.pytest.ini_options]",
                        "testpaths = ['tests']",
                        "[tool.ruff]",
                        "line-length = 100",
                        "[tool.mypy]",
                        "python_version = '3.11'",
                    ]
                )
            )
            (root / "Makefile").write_text(
                "\n".join(
                    [
                        ".PHONY: test build lint",
                        "test build: deps",
                        "\techo run",
                        "lint:",
                        "\techo lint",
                        "VALUE := not-a-target",
                    ]
                )
            )

            package_candidates, package_warnings = discover.discover_package_json(root)
            python_candidates, python_warnings = discover.discover_python(root)
            commands = [
                item.command
                for item in discover.dedupe(
                    [
                        *package_candidates,
                        *python_candidates,
                        *discover.discover_make(root),
                    ]
                )
            ]

            self.assertEqual(package_warnings, [])
            self.assertEqual(python_warnings, [])
            self.assertIn("pnpm run test", commands)
            self.assertIn("pnpm run typecheck", commands)
            self.assertIn("pytest", commands)
            self.assertIn("ruff check .", commands)
            self.assertIn("mypy .", commands)
            self.assertIn("make test", commands)
            self.assertIn("make lint", commands)
            self.assertNotIn("make .PHONY", commands)
            self.assertEqual(discover.discover_ci(root), [".github/workflows"])

    def test_make_phony_only_targets_are_discovered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Makefile").write_text(".PHONY: test lint\n")
            commands = [item.command for item in discover.discover_make(root)]
            self.assertIn("make test", commands)
            self.assertIn("make lint", commands)
            self.assertNotIn("make .PHONY", commands)

    def test_make_backslash_continuation_phony_is_not_parsed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Makefile").write_text(".PHONY: test \\\n  lint\n")
            commands = [item.command for item in discover.discover_make(root)]
            self.assertIn("make test", commands)
            self.assertNotIn("make lint", commands)

    def test_package_runner_defaults_to_npm_when_missing(self) -> None:
        runner, warning = discover.package_runner({})
        self.assertEqual(runner, "npm")
        self.assertIsNotNone(warning)
        self.assertIn("packageManager unset", warning.message)

    def test_package_runner_normalizes_known_manager(self) -> None:
        runner, warning = discover.package_runner({"packageManager": "  PNPM@9.0.0"})
        self.assertEqual(runner, "pnpm")
        self.assertIsNone(warning)

    def test_package_runner_warns_on_unrecognized_manager(self) -> None:
        runner, warning = discover.package_runner({"packageManager": "@scope/custom-runner@1.0"})
        self.assertIsNone(runner)
        self.assertIsNotNone(warning)
        self.assertIn("unrecognized packageManager", warning.message)

    def test_non_dict_scripts_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(json.dumps({"scripts": []}))
            self.assertEqual(discover.discover_package_json(root), ([], []))

    def test_python_discovery_ignores_comment_only_mentions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "setup.cfg").write_text("# pytest ruff mypy pyright were removed\n")
            self.assertEqual(discover.discover_python(root), ([], []))

    def test_python_discovery_attributes_to_specific_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "setup.cfg").write_text("[metadata]\nname = demo\n")
            (root / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n")
            candidates, warnings = discover.discover_python(root)
            self.assertEqual(candidates, [
                discover.Candidate("ruff check .", "pyproject.toml", "[tool.ruff] found")
            ])
            self.assertEqual(warnings, [])

    def test_pyproject_discovery_skips_when_tomllib_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pyproject.toml"
            path.write_text("[tool.ruff]\nline-length = 100\n")
            original = discover.tomllib
            try:
                discover.tomllib = None
                candidates, warnings = discover.discover_pyproject(path)
                self.assertEqual(candidates, [])
                self.assertEqual(warnings, [
                    discover.WarningItem(
                        "pyproject.toml",
                        "tomllib unavailable on Python < 3.11; pyproject.toml discovery skipped",
                    )
                ])
            finally:
                discover.tomllib = original

    def test_discover_surfaces_pyproject_warning_when_tomllib_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n")
            original = discover.tomllib
            try:
                discover.tomllib = None
                result = discover.discover(root)
                self.assertEqual(result.commands, [])
                self.assertEqual(result.warnings[0].source, "pyproject.toml")
                self.assertIn("Python < 3.11", result.warnings[0].message)
            finally:
                discover.tomllib = original

    def test_json_output_shape_includes_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                json.dumps({
                    "packageManager": "@scope/custom-runner@1.0",
                    "scripts": {"test": "echo test"},
                })
            )
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(discover.main([str(root), "--json"]), 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(set(payload), {"root", "commands", "warnings", "ci"})
            self.assertEqual(payload["commands"], [])
            self.assertEqual(payload["warnings"][0]["source"], "package.json")


if __name__ == "__main__":
    unittest.main()
