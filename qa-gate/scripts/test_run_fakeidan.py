#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

import run_fakeidan
import validate_manifest


FAKE_RUNNER = """#!/usr/bin/env python3
import argparse
from pathlib import Path

parser = argparse.ArgumentParser(usage='run.py [-h] [--mode MODE] [--out-dir OUT_DIR] artifact [artifact ...]')
parser.add_argument('artifact', nargs='+')
parser.add_argument('--mode')
parser.add_argument('--out-dir')
parser.add_argument('--quick', action='store_true')
parser.add_argument('--model')
parser.add_argument('--timeout')
args = parser.parse_args()

Path(args.out_dir).mkdir(parents=True, exist_ok=True)
(Path(args.out_dir) / 'review.md').write_text('# Fake Idan Review: demo\\n\\n**Verdict:** Approve\\n\\n## Concerns ranked\\n')
"""


BAD_RUNNER = """#!/usr/bin/env python3
import argparse
import sys

parser = argparse.ArgumentParser(usage='run.py [-h] [--mode MODE] [--out-dir OUT_DIR] artifact [artifact ...]')
parser.add_argument('artifact', nargs='+')
parser.add_argument('--mode')
parser.add_argument('--out-dir')
parser.add_argument('--quick', action='store_true')
parser.add_argument('--model')
parser.add_argument('--timeout')
parser.parse_args()
print('stdout detail')
print('stderr detail', file=sys.stderr)
sys.exit(2)
"""


EMPTY_RUNNER = """#!/usr/bin/env python3
import argparse
from pathlib import Path

parser = argparse.ArgumentParser(usage='run.py [-h] [--mode MODE] [--out-dir OUT_DIR] artifact [artifact ...]')
parser.add_argument('artifact', nargs='+')
parser.add_argument('--mode')
parser.add_argument('--out-dir')
parser.add_argument('--quick', action='store_true')
parser.add_argument('--model')
parser.add_argument('--timeout')
args = parser.parse_args()

Path(args.out_dir).mkdir(parents=True, exist_ok=True)
"""


ENV_RUNNER = """#!/usr/bin/env python3
import argparse
import os
from pathlib import Path

parser = argparse.ArgumentParser(usage='run.py [-h] [--mode MODE] [--out-dir OUT_DIR] artifact [artifact ...]')
parser.add_argument('artifact', nargs='+')
parser.add_argument('--mode')
parser.add_argument('--out-dir')
parser.add_argument('--quick', action='store_true')
parser.add_argument('--model')
parser.add_argument('--timeout')
args = parser.parse_args()

Path(args.out_dir).mkdir(parents=True, exist_ok=True)
(Path(args.out_dir) / 'review.md').write_text(
    '# Fake Idan Review: demo\\n\\n**Verdict:** Approve\\n\\n## Concerns ranked\\n\\n'
    f'FAKEIDAN_TIMEOUT={os.environ.get("FAKEIDAN_TIMEOUT")}\\n'
    f'CLI_TIMEOUT={args.timeout}\\n'
)
"""


class RunFakeidanTest(unittest.TestCase):
    def test_success_persists_manifest_and_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = root / "fakeidan.py"
            runner.write_text(FAKE_RUNNER)
            artifact = root / "artifact.md"
            artifact.write_text("hello")
            args = Namespace(
                artifact=[str(artifact)],
                mode="code",
                quick=True,
                model=None,
                runner=str(runner),
                artifact_root=str(root / "artifacts"),
                timeout=30,
                preflight_timeout=5,
                retain_artifacts=50,
                retain_failures=50,
            )

            payload = run_fakeidan.run(args)

            self.assertEqual(set(payload), run_fakeidan.MANIFEST_KEYS)
            self.assertEqual(payload["verdict"], "Approve")
            self.assertEqual(payload["status"], "PASSED")
            self.assertTrue(Path(payload["manifest_path"]).exists())
            self.assertEqual(len(payload["review_files"]), 1)
            self.assertEqual(payload["verdicts"], [{"path": payload["review_files"][0], "verdict": "Approve"}])
            self.assertTrue(Path(payload["review_files"][0]).exists())
            manifest = json.loads(Path(payload["manifest_path"]).read_text())
            self.assertEqual(validate_manifest.validate_manifest(manifest), [])

    def test_failure_normalizes_unable_to_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = root / "bad.py"
            runner.write_text(BAD_RUNNER)
            artifact = root / "artifact.md"
            artifact.write_text("hello")
            args = Namespace(
                artifact=[str(artifact)],
                mode="code",
                quick=False,
                model=None,
                runner=str(runner),
                artifact_root=str(root / "artifacts"),
                timeout=30,
                preflight_timeout=5,
                retain_artifacts=50,
                retain_failures=50,
            )

            payload = run_fakeidan.run(args)

            self.assertEqual(set(payload), run_fakeidan.MANIFEST_KEYS)
            self.assertEqual(payload["verdict"], "UNABLE_TO_RUN")
            self.assertEqual(payload["status"], "BLOCKED")
            self.assertTrue(Path(payload["manifest_path"]).exists())
            manifest = json.loads(Path(payload["manifest_path"]).read_text())
            self.assertEqual(set(manifest), run_fakeidan.MANIFEST_KEYS)
            self.assertEqual(manifest["verdict"], "UNABLE_TO_RUN")
            self.assertEqual(validate_manifest.validate_manifest(manifest), [])
            manifest_dir = Path(payload["manifest_path"]).parent
            stdout_path = manifest_dir / "fakeidan.stdout"
            stderr_path = manifest_dir / "fakeidan.stderr"
            self.assertEqual(stdout_path.read_text().strip(), "stdout detail")
            self.assertIn("stderr detail", stderr_path.read_text())
            self.assertEqual(stdout_path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(stderr_path.stat().st_mode & 0o777, 0o600)
            self.assertIn("fakeidan.stdout", manifest["error"])
            self.assertIn("fakeidan.stderr", manifest["error"])

    def test_success_with_no_reviews_normalizes_unable_to_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = root / "empty.py"
            runner.write_text(EMPTY_RUNNER)
            artifact = root / "artifact.md"
            artifact.write_text("hello")
            args = Namespace(
                artifact=[str(artifact)],
                mode="code",
                quick=False,
                model=None,
                runner=str(runner),
                artifact_root=str(root / "artifacts"),
                timeout=30,
                preflight_timeout=5,
                retain_artifacts=50,
                retain_failures=50,
            )

            payload = run_fakeidan.run(args)

            manifest = json.loads(Path(payload["manifest_path"]).read_text())
            self.assertEqual(payload["verdict"], "UNABLE_TO_RUN")
            self.assertEqual(payload["status"], "BLOCKED")
            self.assertEqual(payload["error"], "fakeidan produced no markdown review files")
            self.assertEqual(validate_manifest.validate_manifest(manifest), [])

    def test_main_run_timeout_normalizes_unable_to_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = root / "fakeidan.py"
            runner.write_text(FAKE_RUNNER)
            artifact = root / "artifact.md"
            artifact.write_text("hello")
            args = Namespace(
                artifact=[str(artifact)],
                mode="code",
                quick=False,
                model=None,
                runner=str(runner),
                artifact_root=str(root / "artifacts"),
                timeout=30,
                preflight_timeout=5,
                retain_artifacts=50,
                retain_failures=50,
            )
            help_result = run_fakeidan.subprocess.CompletedProcess(
                ["python3"],
                0,
                stdout="usage: artifact [artifact ...] --mode --out-dir --quick --model\n",
                stderr="",
            )
            timeout = run_fakeidan.subprocess.TimeoutExpired(["python3"], 30, output="partial", stderr="timed out")

            with mock.patch("run_fakeidan.subprocess.run", side_effect=[help_result, timeout]):
                payload = run_fakeidan.run(args)

            manifest = json.loads(Path(payload["manifest_path"]).read_text())
            self.assertEqual(payload["verdict"], "UNABLE_TO_RUN")
            self.assertIn("timed out after 30s", payload["error"])
            self.assertEqual(validate_manifest.validate_manifest(manifest), [])
            self.assertEqual((Path(payload["manifest_path"]).parent / "fakeidan.stdout").read_text(), "partial")
            self.assertEqual((Path(payload["manifest_path"]).parent / "fakeidan.stderr").read_text(), "timed out")

    def test_internal_error_returns_structured_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = Namespace(
                artifact=[str(root / "artifact.md")],
                mode="code",
                quick=False,
                model=None,
                runner=str(root / "fakeidan.py"),
                artifact_root=str(root / "artifacts"),
                timeout=30,
                preflight_timeout=5,
                retain_artifacts=50,
                retain_failures=50,
            )

            with mock.patch("run_fakeidan.run_once", side_effect=OSError("disk full")):
                payload = run_fakeidan.run(args)

            self.assertEqual(payload["verdict"], "UNABLE_TO_RUN")
            self.assertEqual(payload["status"], "BLOCKED")
            self.assertIn("qa-gate internal error: disk full", payload["error"])
            self.assertEqual(validate_manifest.validate_manifest(payload), [])

    def test_internal_error_returns_payload_when_manifest_write_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = Namespace(
                artifact=[str(root / "artifact.md")],
                mode="code",
                quick=False,
                model=None,
                runner=str(root / "fakeidan.py"),
                artifact_root=str(root / "artifacts"),
                timeout=30,
                preflight_timeout=5,
                retain_artifacts=50,
                retain_failures=50,
            )

            with mock.patch("run_fakeidan.run_once", side_effect=OSError("disk full")):
                with mock.patch("run_fakeidan.write_manifest", side_effect=OSError("still full")):
                    payload = run_fakeidan.run(args)

            self.assertEqual(payload["verdict"], "UNABLE_TO_RUN")
            self.assertIn("qa-gate internal error: disk full", payload["error"])

    def test_manifest_payload_rejects_unknown_keys(self) -> None:
        with self.assertRaises(ValueError):
            run_fakeidan.manifest_payload(verdic="Approve")

    def test_manifest_payload_rejects_status_verdict_mismatch(self) -> None:
        with self.assertRaises(ValueError):
            run_fakeidan.manifest_payload(verdict="Recommend changes", status="PASSED")
        with self.assertRaises(ValueError):
            run_fakeidan.manifest_payload(verdict="Approve", status="BLOCKED")

    def test_manifest_payload_rejects_invalid_verdict_or_status(self) -> None:
        with self.assertRaises(ValueError):
            run_fakeidan.manifest_payload(verdict="garbage", status="BLOCKED")
        with self.assertRaises(ValueError):
            run_fakeidan.manifest_payload(verdict="UNABLE_TO_RUN", status="UNKNOWN")

    def test_aggregate_verdict_uses_most_severe(self) -> None:
        self.assertEqual(run_fakeidan.aggregate_verdict([]), "UNABLE_TO_RUN")
        self.assertEqual(
            run_fakeidan.aggregate_verdict(["Approve", "Recommend changes"]),
            "Recommend changes",
        )
        self.assertEqual(
            run_fakeidan.aggregate_verdict(["Recommend changes", "Changes requested"]),
            "Changes requested",
        )
        with self.assertRaises(ValueError):
            run_fakeidan.aggregate_verdict(["Unexpected verdict"])

    def test_bundle_artifacts_keeps_single_artifact_as_is(self) -> None:
        self.assertEqual(run_fakeidan.bundle_artifacts(["one.py"], Path("/tmp/unused")), ["one.py"])

    def test_bundle_artifacts_expands_single_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_dir = root / "src"
            artifact_dir.mkdir()
            (artifact_dir / "keep.py").write_text("x = 1\n")
            [bundle_path] = run_fakeidan.bundle_artifacts([str(artifact_dir)], root / "bundle")
            text = Path(bundle_path).read_text()
            self.assertIn("## " + str(artifact_dir), text)
            self.assertIn("### keep.py", text)
            self.assertIn("x = 1", text)

    def test_verdict_parser_self_check_reports_failure(self) -> None:
        original = run_fakeidan.VERDICT_PARSER

        class BrokenParser:
            @staticmethod
            def parse_verdict(_text: str) -> str | None:
                return None

        try:
            run_fakeidan.VERDICT_PARSER = BrokenParser()
            self.assertEqual(
                run_fakeidan.verdict_parser_self_check(),
                "fakeidan verdict parser self-check failed: expected 'Approve', got None",
            )
        finally:
            run_fakeidan.VERDICT_PARSER = original

    def test_bundle_artifacts_combines_multiple_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first.py"
            second = root / "second.md"
            first.write_text("print('one')\n")
            second.write_text("# Two\n")

            result = run_fakeidan.bundle_artifacts([str(first), str(second)], root / "bundle")

            self.assertEqual(len(result), 1)
            bundle = Path(result[0])
            self.assertEqual(bundle.name, "qa-gate-artifact-bundle.md")
            text = bundle.read_text()
            self.assertIn("## " + str(first), text)
            self.assertIn("```python", text)
            self.assertIn("print('one')", text)
            self.assertIn("```markdown", text)
            self.assertIn("# Two", text)

    def test_materialize_review_artifacts_copies_bundle_for_shared_review_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first.py"
            second = root / "second.py"
            first.write_text("print('one')\n")
            second.write_text("print('two')\n")

            bundled = run_fakeidan.bundle_artifacts([str(first), str(second)], root / "tmp-input")
            materialized = run_fakeidan.materialize_review_artifacts(bundled, root / "stable-input")

            self.assertEqual(len(materialized), 1)
            materialized_path = Path(materialized[0])
            self.assertTrue(materialized_path.exists())
            self.assertEqual(materialized_path.parent, root / "stable-input")
            self.assertIn("qa-gate-artifact-bundle.md", materialized_path.name)
            self.assertEqual(materialized_path.read_text(), Path(bundled[0]).read_text())

    def test_bundle_artifacts_expands_supported_directory_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_dir = root / "artifact"
            artifact_dir.mkdir()
            (artifact_dir / "keep.py").write_text("x = 1\n")
            (artifact_dir / "skip.bin").write_bytes(b"\x00\x01")

            result = run_fakeidan.bundle_artifacts([str(artifact_dir), str(root / "missing.py")], root / "bundle")

            text = Path(result[0]).read_text()
            self.assertIn("### keep.py", text)
            self.assertIn("x = 1", text)
            self.assertNotIn("skip.bin", text)
            self.assertIn("Not found.", text)

    def test_bundle_directory_truncates_after_file_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index in range(run_fakeidan.MAX_BUNDLE_FILES + 1):
                (root / f"{index:03}.py").write_text(f"x = {index}\n")

            sections = run_fakeidan.bundle_directory(root)
            text = "\n".join(sections)

            self.assertIn(run_fakeidan.BUNDLE_FILE_COUNT_NOTE, text)
            self.assertIn("199.py", text)
            self.assertNotIn("200.py", text)

    def test_bundle_directory_truncates_large_file_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "large.py"
            path.write_text("a" * (run_fakeidan.MAX_FILE_BYTES + 10))

            sections = run_fakeidan.bundle_directory(root)
            text = "\n".join(sections)

            self.assertIn(run_fakeidan.BUNDLE_FILE_SIZE_NOTE, text)
            self.assertIn(f"{run_fakeidan.MAX_FILE_BYTES + 10} bytes", text)
            code = text.split("```python\n", 1)[1].split("\n```", 1)[0]
            self.assertEqual(len(code), run_fakeidan.MAX_FILE_BYTES)

    def test_bundle_directory_skips_symlinked_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.py"
            link = root / "link.py"
            target.write_text("x = 1\n")
            link.symlink_to(target)

            text = "\n".join(run_fakeidan.bundle_directory(root))

            self.assertIn("target.py", text)
            self.assertNotIn("link.py", text)

    def test_bundle_artifacts_skips_root_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target_dir = root / "target"
            target_dir.mkdir()
            (target_dir / "secret.py").write_text("x = 1\n")
            link_dir = root / "linked"
            link_dir.symlink_to(target_dir, target_is_directory=True)

            [bundle_path] = run_fakeidan.bundle_artifacts([str(link_dir), str(target_dir)], root / "bundle")
            text = Path(bundle_path).read_text()

            self.assertIn("Symlink - skipped.", text)
            self.assertIn("secret.py", text)

    def test_preflight_timeout_uses_timeout_expired(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runner = Path(tmp) / "runner.py"
            runner.write_text("")
            with mock.patch("run_fakeidan.subprocess.run", side_effect=run_fakeidan.subprocess.TimeoutExpired(["python3"], 1)):
                self.assertIn("timed out", run_fakeidan.preflight(runner, timeout=1))

    def test_preflight_error_includes_help_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runner = Path(tmp) / "runner.py"
            runner.write_text("")
            result = run_fakeidan.subprocess.CompletedProcess(["python3"], 0, stdout="usage: demo\n", stderr="missing args\n")
            with mock.patch("run_fakeidan.subprocess.run", return_value=result):
                error = run_fakeidan.preflight(runner, timeout=1)
            self.assertIsNotNone(error)
            self.assertIn("help output was", error)
            self.assertIn("usage: demo", error)

    def test_preflight_failure_prunes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_root = root / "artifacts"
            for index, timestamp in enumerate([10, 20, 30]):
                old_dir = artifact_root / f"old-{index}"
                old_dir.mkdir(parents=True)
                os.utime(old_dir, (timestamp, timestamp))
            missing_runner = root / "missing.py"
            args = Namespace(
                artifact=[str(root / "artifact.md")],
                mode="code",
                quick=False,
                model=None,
                runner=str(missing_runner),
                artifact_root=str(artifact_root),
                timeout=30,
                preflight_timeout=5,
                retain_artifacts=2,
                retain_failures=2,
            )

            payload = run_fakeidan.run(args)

            manifest = json.loads(Path(payload["manifest_path"]).read_text())
            self.assertEqual(validate_manifest.validate_manifest(manifest), [])
            self.assertEqual(len([path for path in artifact_root.iterdir() if path.is_dir()]), 2)

    def test_default_claude_bin_respects_env(self) -> None:
        with mock.patch.dict(os.environ, {"CLAUDE_BIN": "/tmp/custom"}, clear=True):
            self.assertIsNone(run_fakeidan.default_claude_bin())

    def test_default_claude_bin_prefers_env_over_zclaude(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            zclaude = home / ".config" / "zerg" / "zclaude"
            zclaude.parent.mkdir(parents=True)
            zclaude.write_text("#!/bin/sh\n")
            zclaude.chmod(0o755)
            with mock.patch.dict(os.environ, {"CLAUDE_BIN": "/tmp/custom"}, clear=True):
                self.assertIsNone(run_fakeidan.default_claude_bin(home))

    def test_default_claude_bin_finds_zclaude(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            zclaude = home / ".config" / "zerg" / "zclaude"
            zclaude.parent.mkdir(parents=True)
            zclaude.write_text("#!/bin/sh\n")
            zclaude.chmod(0o755)
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertEqual(run_fakeidan.default_claude_bin(home), str(zclaude))

    def test_resolve_claude_bin_reports_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            zclaude = home / ".config" / "zerg" / "zclaude"
            zclaude.parent.mkdir(parents=True)
            zclaude.write_text("#!/bin/sh\n")
            zclaude.chmod(0o755)
            with mock.patch.dict(os.environ, {"CLAUDE_BIN": "/tmp/custom"}, clear=True):
                self.assertEqual(run_fakeidan.resolve_claude_bin(home), (None, "inherited:/tmp/custom"))
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertEqual(run_fakeidan.resolve_claude_bin(home), (str(zclaude), f"set:{zclaude}"))

    def test_run_manifest_records_inherited_claude_bin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = root / "fakeidan.py"
            runner.write_text(FAKE_RUNNER)
            artifact = root / "artifact.md"
            artifact.write_text("hello")
            args = Namespace(
                artifact=[str(artifact)],
                mode="code",
                quick=True,
                model=None,
                runner=str(runner),
                artifact_root=str(root / "artifacts"),
                timeout=30,
                preflight_timeout=5,
                retain_artifacts=50,
                retain_failures=50,
            )

            with mock.patch.dict(os.environ, {"CLAUDE_BIN": "/tmp/custom"}, clear=True):
                payload = run_fakeidan.run(args)

            self.assertEqual(payload["claude_bin"], "inherited:/tmp/custom")

    def test_run_manifest_records_zclaude_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            zclaude = home / ".config" / "zerg" / "zclaude"
            zclaude.parent.mkdir(parents=True)
            zclaude.write_text("#!/bin/sh\n")
            zclaude.chmod(0o755)
            runner = root / "fakeidan.py"
            runner.write_text(FAKE_RUNNER)
            artifact = root / "artifact.md"
            artifact.write_text("hello")
            args = Namespace(
                artifact=[str(artifact)],
                mode="code",
                quick=True,
                model=None,
                runner=str(runner),
                artifact_root=str(root / "artifacts"),
                timeout=30,
                preflight_timeout=5,
                retain_artifacts=50,
                retain_failures=50,
            )

            with mock.patch.dict(os.environ, {}, clear=True):
                with mock.patch.object(run_fakeidan.Path, "home", return_value=home):
                    payload = run_fakeidan.run(args)

            self.assertEqual(payload["claude_bin"], f"set:{zclaude}")

    def test_run_sets_fakeidan_timeout_with_wrapper_margin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {}, clear=True):
            root = Path(tmp)
            runner = root / "fakeidan.py"
            runner.write_text(ENV_RUNNER)
            artifact = root / "artifact.md"
            artifact.write_text("hello")
            args = Namespace(
                artifact=[str(artifact)],
                mode="code",
                quick=True,
                model=None,
                runner=str(runner),
                artifact_root=str(root / "artifacts"),
                timeout=90,
                preflight_timeout=5,
                retain_artifacts=50,
                retain_failures=50,
            )

            payload = run_fakeidan.run(args)

            review_text = Path(payload["review_files"][0]).read_text()
            self.assertIn("FAKEIDAN_TIMEOUT=60", review_text)
            self.assertIn("CLI_TIMEOUT=60", review_text)

    def test_run_clamps_explicit_fakeidan_timeout_below_outer_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"FAKEIDAN_TIMEOUT": "777"}, clear=True):
            root = Path(tmp)
            runner = root / "fakeidan.py"
            runner.write_text(ENV_RUNNER)
            artifact = root / "artifact.md"
            artifact.write_text("hello")
            args = Namespace(
                artifact=[str(artifact)],
                mode="code",
                quick=True,
                model=None,
                runner=str(runner),
                artifact_root=str(root / "artifacts"),
                timeout=90,
                preflight_timeout=5,
                retain_artifacts=50,
                retain_failures=50,
            )

            payload = run_fakeidan.run(args)

            review_text = Path(payload["review_files"][0]).read_text()
            self.assertIn("FAKEIDAN_TIMEOUT=60", review_text)
            self.assertIn("CLI_TIMEOUT=60", review_text)

    def test_run_preserves_smaller_explicit_fakeidan_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"FAKEIDAN_TIMEOUT": "45"}, clear=True):
            root = Path(tmp)
            runner = root / "fakeidan.py"
            runner.write_text(ENV_RUNNER)
            artifact = root / "artifact.md"
            artifact.write_text("hello")
            args = Namespace(
                artifact=[str(artifact)],
                mode="code",
                quick=True,
                model=None,
                runner=str(runner),
                artifact_root=str(root / "artifacts"),
                timeout=90,
                preflight_timeout=5,
                retain_artifacts=50,
                retain_failures=50,
            )

            payload = run_fakeidan.run(args)

            review_text = Path(payload["review_files"][0]).read_text()
            self.assertIn("FAKEIDAN_TIMEOUT=45", review_text)
            self.assertIn("CLI_TIMEOUT=45", review_text)

    def test_default_claude_bin_missing_zclaude(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertIsNone(run_fakeidan.default_claude_bin(Path(tmp)))

    def test_prune_artifacts_keeps_newest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ["001", "002", "003"]:
                (root / name).mkdir()
            run_fakeidan.prune_artifacts(root, retain=2, retain_failures=2)
            self.assertEqual(sorted(path.name for path in root.iterdir()), ["002", "003"])

    def test_prune_artifacts_uses_mtime_not_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            older_by_mtime = root / "20260101-000000-000000-zzzzzzzz"
            newer_by_mtime = root / "20260101-000000-000000-aaaaaaaa"
            older_by_mtime.mkdir()
            newer_by_mtime.mkdir()
            os.utime(older_by_mtime, (10, 10))
            os.utime(newer_by_mtime, (20, 20))
            run_fakeidan.prune_artifacts(root, retain=1, retain_failures=1)
            self.assertEqual([path.name for path in root.iterdir()], [newer_by_mtime.name])

    def test_prune_artifacts_retention_classes_are_independent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            success = root / "success"
            failure_old = root / "failure-old"
            failure_new = root / "failure-new"
            for path in [success, failure_old, failure_new]:
                path.mkdir()
            (success / "manifest.json").write_text(json.dumps(run_fakeidan.manifest_payload(
                verdict="Approve",
                status="PASSED",
                manifest_path=str(success / "manifest.json"),
            )))
            (failure_old / "manifest.json").write_text(json.dumps(run_fakeidan.manifest_payload(
                error="old",
                manifest_path=str(failure_old / "manifest.json"),
            )))
            (failure_new / "manifest.json").write_text(json.dumps(run_fakeidan.manifest_payload(
                error="new",
                manifest_path=str(failure_new / "manifest.json"),
            )))
            os.utime(success, (10, 10))
            os.utime(failure_old, (20, 20))
            os.utime(failure_new, (30, 30))

            run_fakeidan.prune_artifacts(root, retain=0, retain_failures=1)

            self.assertEqual(sorted(path.name for path in root.iterdir()), ["failure-new", "success"])


if __name__ == "__main__":
    unittest.main()
