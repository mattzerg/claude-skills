#!/usr/bin/env python3
"""Run fakeidan through the qa-gate contract and emit a durable manifest."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path


# Must match validate_manifest.py; update both when changing manifest shape.
MANIFEST_SCHEMA_VERSION = 3
MANIFEST_KEYS = {"schema_version", "verdict", "status", "review_files", "verdicts", "manifest_path", "error", "claude_bin", "xmodel_review", "xmodel_status"}
# xmodel_status values: null (didn't run), "ok" (ran, no HIGH), "high" (HIGH findings), "skipped" (other model unavailable)
XMODEL_STATUSES = {None, "ok", "high", "skipped"}
CROSS_MODEL_CHECK = Path.home() / ".claude/skills/cross-model-check/run.py"
# UNABLE_TO_RUN is emitted by this wrapper, not parsed from fakeidan reviews.
SEVERITY = {"Approve": 0, "Recommend changes": 1, "Changes requested": 2}
STATUSES = {"PASSED", "BLOCKED"}
TEXT_SUFFIXES = {
    ".bash",
    ".c",
    ".cpp",
    ".css",
    ".go",
    ".h",
    ".html",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".kt",
    ".md",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".sql",
    ".swift",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".vue",
    ".xml",
    ".yaml",
    ".yml",
}
MAX_BUNDLE_FILES = 200
MAX_FILE_BYTES = 512_000
BUNDLE_FILE_COUNT_NOTE = f"(bundle truncated: more than {MAX_BUNDLE_FILES} supported files)"
BUNDLE_FILE_SIZE_NOTE = f"(content truncated: file exceeded {MAX_FILE_BYTES} bytes)"


def load_verdict_parser():
    parser_path = Path(__file__).with_name("parse_fakeidan_verdict.py")
    spec = importlib.util.spec_from_file_location("qa_gate_parse_fakeidan_verdict", parser_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load verdict parser from {parser_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VERDICT_PARSER = load_verdict_parser()


def verdict_parser_self_check() -> str | None:
    for expected in ("Approve", "Recommend changes", "Changes requested"):
        got = VERDICT_PARSER.parse_verdict(f"# Fake Idan Review: demo\n\n**Verdict:** {expected}\n\n## Concerns ranked\n")
        if got != expected:
            return f"fakeidan verdict parser self-check failed: expected {expected!r}, got {got!r}"
    if not VERDICT_PARSER.has_concerns_section("# Fake Idan Review: demo\n\n**Verdict:** Approve\n\n## Concerns ranked\n"):
        return "fakeidan verdict parser self-check failed: expected concerns heading to be detected"
    if VERDICT_PARSER.has_concerns_section("# Fake Idan Review: demo\n\n**Verdict:** Approve\n"):
        return "fakeidan verdict parser self-check failed: missing concerns heading was accepted"
    if VERDICT_PARSER.parse_verdict("# Fake Idan Review: demo\n\n**Verdict:** Recommend changes - see C1\n\n## Concerns ranked\n") is not None:
        return "fakeidan verdict parser self-check failed: annotated verdict line was accepted"
    return None


def default_runner() -> Path:
    return Path(os.environ.get("FAKEIDAN_RUNNER", str(Path.home() / ".claude/skills/fakeidan/run.py"))).expanduser()


def default_artifact_root() -> Path:
    return Path(os.environ.get("QA_GATE_ARTIFACT_ROOT", str(Path.home() / ".codex/artifacts/qa-gate"))).expanduser()


def default_claude_bin(home: Path | None = None) -> str | None:
    claude_bin, _ = resolve_claude_bin(home)
    return claude_bin


def resolve_claude_bin(home: Path | None = None) -> tuple[str | None, str]:
    if os.environ.get("CLAUDE_BIN"):
        return None, f"inherited:{os.environ['CLAUDE_BIN']}"
    zclaude = (home or Path.home()) / ".config" / "zerg" / "zclaude"
    if zclaude.exists() and os.access(zclaude, os.X_OK):
        return str(zclaude), f"set:{zclaude}"
    return None, "default"


def write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def write_private_log(path: Path, content: str | bytes | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        text = content.decode(errors="replace")
    else:
        text = content or ""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(text)


def persist_fakeidan_logs(stable_dir: Path, stdout: str | bytes | None, stderr: str | bytes | None) -> tuple[Path, Path]:
    stdout_path = stable_dir / "fakeidan.stdout"
    stderr_path = stable_dir / "fakeidan.stderr"
    write_private_log(stdout_path, stdout)
    write_private_log(stderr_path, stderr)
    return stdout_path, stderr_path


def inner_fakeidan_timeout(outer_timeout: int) -> int:
    max_inner = max(1, outer_timeout - 30)
    raw = os.environ.get("FAKEIDAN_TIMEOUT")
    if raw is None:
        return max_inner
    try:
        requested = int(raw)
    except ValueError:
        return max_inner
    return min(max(1, requested), max_inner)


def manifest_status(path: Path) -> str | None:
    manifest_path = path / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        payload = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    status = payload.get("status")
    return status if isinstance(status, str) else None


def prune_artifacts(root: Path, retain: int, retain_failures: int) -> None:
    if not root.exists():
        return
    dirs = [path for path in root.iterdir() if path.is_dir()]
    successes = sorted([path for path in dirs if manifest_status(path) == "PASSED"], key=lambda path: path.stat().st_mtime)
    failures = sorted([path for path in dirs if manifest_status(path) != "PASSED"], key=lambda path: path.stat().st_mtime)
    protected_successes = successes[-retain:] if retain >= 1 else successes
    protected_failures = failures[-retain_failures:] if retain_failures >= 1 else failures
    protected = set(protected_successes) | set(protected_failures)
    for path in dirs:
        if path in protected:
            continue
        shutil.rmtree(path, ignore_errors=True)


def manifest_payload(**kwargs: object) -> dict:
    payload = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "verdict": "UNABLE_TO_RUN",
        "status": "BLOCKED",
        "review_files": [],
        "verdicts": [],
        "manifest_path": None,
        "error": None,
        "claude_bin": None,
        "xmodel_review": None,
        "xmodel_status": None,
    }
    unknown = set(kwargs) - MANIFEST_KEYS
    if unknown:
        raise ValueError(f"unknown manifest keys: {', '.join(sorted(unknown))}")
    payload.update(kwargs)
    if payload["verdict"] not in {*SEVERITY, "UNABLE_TO_RUN"}:
        raise ValueError(f"invalid manifest verdict: {payload['verdict']!r}")
    if payload["status"] not in STATUSES:
        raise ValueError(f"invalid manifest status: {payload['status']!r}")
    if (payload["status"] == "PASSED") and (payload["verdict"] != "Approve" or payload.get("xmodel_status") == "high"):
        raise ValueError("manifest status/verdict mismatch: PASSED requires Approve verdict AND xmodel not high")
    if payload["verdict"] == "Approve" and payload["status"] != "PASSED" and payload.get("xmodel_status") != "high":
        raise ValueError("manifest status/verdict mismatch: Approve verdict requires PASSED unless xmodel blocks")
    if payload.get("xmodel_status") not in XMODEL_STATUSES:
        raise ValueError(f"invalid xmodel_status: {payload.get('xmodel_status')!r}")
    return payload


def preflight(runner: Path, timeout: int) -> str | None:
    if not runner.exists():
        return f"fakeidan runner not found: {runner}"
    try:
        result = subprocess.run(["python3", str(runner), "--help"], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return f"fakeidan preflight timed out after {timeout}s"
    help_text = f"{result.stdout}\n{result.stderr}"
    for token in ("artifact", "--mode", "--out-dir", "--quick", "--model"):
        if token not in help_text:
            return f"fakeidan help output missing `{token}`; help output was:\n{help_text}"
    return None


def run_cross_model(
    artifacts: list[str],
    out_dir: Path,
    mode: str,
    timeout: int = 300,
) -> tuple[Path | None, str]:
    """Run cross-model-check on the qa-gate artifact. Returns (review_path, status).

    status is one of: "ok" (ran, no HIGH), "high" (HIGH findings present),
    "skipped" (other model unavailable), "missing" (xmodel runner not installed).
    """
    if not CROSS_MODEL_CHECK.exists():
        return None, "missing"

    # qa-gate may bundle multiple artifacts — review the first existing one;
    # xmodel's diff context comes from the file content itself in qa-gate mode.
    artifact: Path | None = None
    for raw in artifacts:
        candidate = Path(raw).expanduser()
        if candidate.exists():
            artifact = candidate
            break
    if artifact is None:
        return None, "skipped"

    out_dir.mkdir(parents=True, exist_ok=True)
    # qa-gate's fakeidan modes are {prose, code, video, product, spec}.
    # xmodel modes are {code, prose, launch, email, generic}. Map them.
    xmodel_mode_map = {"code": "code", "prose": "prose", "video": "generic",
                       "product": "generic", "spec": "generic"}
    xmodel_mode = xmodel_mode_map.get(mode, "generic")
    try:
        proc = subprocess.run(
            [
                "python3", str(CROSS_MODEL_CHECK), str(artifact),
                "--mode", xmodel_mode,
                "--from", "codex",
                "--out-dir", str(out_dir),
                "--timeout", str(timeout),
            ],
            capture_output=True, text=True, timeout=timeout + 30,
        )
    except subprocess.TimeoutExpired:
        return None, "skipped"
    except FileNotFoundError:
        return None, "missing"

    # Exit codes: 0 clean / 2 HIGH / 3 skipped / 1 usage error
    if proc.returncode == 1:
        return None, "skipped"

    out_path_str = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
    review_path = Path(out_path_str) if out_path_str else None
    if review_path is None or not review_path.exists():
        candidates = sorted(out_dir.glob("*.xmodel.*.md"))
        review_path = candidates[-1] if candidates else None

    if review_path is None:
        return None, "skipped"

    if proc.returncode == 3:
        return review_path, "skipped"
    if proc.returncode == 2:
        return review_path, "high"
    return review_path, "ok"


def aggregate_verdict(verdicts: list[str]) -> str:
    if not verdicts:
        return "UNABLE_TO_RUN"
    invalid = [verdict for verdict in verdicts if verdict not in SEVERITY]
    if invalid:
        raise ValueError(f"invalid verdicts: {', '.join(invalid)}")
    return max(verdicts, key=lambda item: SEVERITY[item])


def bundle_artifacts(artifacts: list[str], bundle_dir: Path) -> list[str]:
    if len(artifacts) == 1:
        path = Path(artifacts[0]).expanduser()
        if not path.is_symlink() and path.is_dir():
            bundle_dir.mkdir(parents=True, exist_ok=True)
            bundle_path = bundle_dir / "qa-gate-artifact-bundle.md"
            sections = ["# qa-gate artifact bundle", "", f"## {path}"]
            sections.extend(bundle_directory(path))
            bundle_path.write_text("\n".join(sections))
            return [str(bundle_path)]
        return artifacts
    bundle_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = bundle_dir / "qa-gate-artifact-bundle.md"
    sections = ["# qa-gate artifact bundle", ""]
    for raw in artifacts:
        path = Path(raw).expanduser()
        sections.append(f"## {path}")
        if path.is_symlink():
            sections.append("Symlink - skipped.")
        elif path.is_dir():
            sections.extend(bundle_directory(path))
        elif path.exists():
            sections.extend(render_file_section(path, f"## {path}"))
        else:
            sections.append("Not found.")
        sections.append("")
    bundle_path.write_text("\n".join(sections))
    return [str(bundle_path)]


def materialize_review_artifacts(artifacts: list[str], dest_dir: Path) -> list[str]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    materialized: list[str] = []
    for index, raw in enumerate(artifacts):
        path = Path(raw).expanduser()
        if not path.exists() or not path.is_file():
            materialized.append(raw)
            continue
        target = dest_dir / f"{index:02d}-{path.name}"
        shutil.copy2(path, target)
        materialized.append(str(target))
    return materialized


def bundle_directory(path: Path) -> list[str]:
    sections: list[str] = []
    file_count = 0
    for dirpath, dirnames, filenames in os.walk(path, followlinks=False):
        dirnames.sort()
        for filename in sorted(filenames):
            child = Path(dirpath) / filename
            if child.is_symlink() or child.suffix.lower() not in TEXT_SUFFIXES:
                continue
            if file_count >= MAX_BUNDLE_FILES:
                sections.append(BUNDLE_FILE_COUNT_NOTE)
                return sections
            file_count += 1
            sections.extend(render_file_section(child, f"### {child.relative_to(path)}"))
            sections.append("")
    return sections or ["No supported text files found."]


def render_file_section(path: Path, heading: str) -> list[str]:
    text, truncated, size = read_text_limited(path)
    lines = [heading]
    if truncated:
        lines.append(f"{BUNDLE_FILE_SIZE_NOTE}: {size} bytes")
    lines.append(f"```{fence_language(path)}")
    lines.append(text)
    lines.append("```")
    return lines


def read_text_limited(path: Path) -> tuple[str, bool, int]:
    size = path.stat().st_size
    with path.open("rb") as fh:
        data = fh.read(MAX_FILE_BYTES + 1)
    truncated = len(data) > MAX_FILE_BYTES
    if truncated:
        data = data[:MAX_FILE_BYTES]
    return data.decode(errors="replace"), truncated, size


def fence_language(path: Path) -> str:
    return {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "jsx",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".md": "markdown",
        ".sh": "bash",
        ".bash": "bash",
        ".go": "go",
        ".rs": "rust",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".java": "java",
        ".rb": "ruby",
        ".css": "css",
        ".html": "html",
        ".xml": "xml",
        ".swift": "swift",
        ".kt": "kotlin",
        ".sql": "sql",
    }.get(path.suffix.lower(), "")


def run(args: argparse.Namespace) -> dict:
    runner = Path(args.runner).expanduser() if args.runner else default_runner()
    artifact_root = Path(args.artifact_root).expanduser() if args.artifact_root else default_artifact_root()
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    stable_dir = artifact_root / f"{stamp}-{uuid.uuid4().hex[:8]}"
    manifest_path = stable_dir / "manifest.json"
    claude_bin, claude_bin_label = resolve_claude_bin()

    try:
        return run_once(args, runner, stable_dir, manifest_path, claude_bin, claude_bin_label)
    except Exception as exc:
        payload = manifest_payload(
            error=f"qa-gate internal error: {exc}",
            manifest_path=str(manifest_path),
            claude_bin=claude_bin_label,
        )
        try:
            write_manifest(manifest_path, payload)
        except Exception:
            pass
        return payload
    finally:
        try:
            prune_artifacts(artifact_root, args.retain_artifacts, args.retain_failures)
        except Exception as exc:
            print(f"[qa-gate] warning: artifact pruning failed: {exc}", file=sys.stderr)


def run_once(
    args: argparse.Namespace,
    runner: Path,
    stable_dir: Path,
    manifest_path: Path,
    claude_bin: str | None,
    claude_bin_label: str,
) -> dict:
    stable_dir.mkdir(parents=True, exist_ok=True)
    preflight_error = preflight(runner, args.preflight_timeout)
    if preflight_error:
        payload = manifest_payload(error=preflight_error, manifest_path=str(manifest_path), claude_bin=claude_bin_label)
        write_manifest(manifest_path, payload)
        return payload

    with tempfile.TemporaryDirectory(prefix="fakeidan.") as tmp:
        tmp_path = Path(tmp)
        fakeidan_out = tmp_path / "out"
        review_artifacts = materialize_review_artifacts(
            bundle_artifacts(args.artifact, tmp_path / "input"),
            stable_dir / "input",
        )
        inner_timeout = inner_fakeidan_timeout(args.timeout)
        cmd = [
            "python3", str(runner), *review_artifacts,
            "--mode", args.mode,
            "--out-dir", str(fakeidan_out),
            "--timeout", str(inner_timeout),
        ]
        if args.quick:
            cmd.append("--quick")
        if args.model:
            cmd.extend(["--model", args.model])

        env = os.environ.copy()
        if claude_bin:
            env["CLAUDE_BIN"] = claude_bin
        env["FAKEIDAN_TIMEOUT"] = str(inner_timeout)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=args.timeout)
        except subprocess.TimeoutExpired as exc:
            stdout_path, stderr_path = persist_fakeidan_logs(
                stable_dir,
                exc.stdout,
                exc.stderr or f"fakeidan timed out after {args.timeout}s\n",
            )
            payload = manifest_payload(
                error=f"fakeidan timed out after {args.timeout}s; logs written to {stdout_path} and {stderr_path}",
                manifest_path=str(manifest_path),
                claude_bin=claude_bin_label,
            )
            write_manifest(manifest_path, payload)
            return payload
        if result.returncode != 0:
            stdout_path, stderr_path = persist_fakeidan_logs(stable_dir, result.stdout, result.stderr)
            payload = manifest_payload(
                error=f"fakeidan failed with return code {result.returncode}; logs written to {stdout_path} and {stderr_path}",
                manifest_path=str(manifest_path),
                claude_bin=claude_bin_label,
            )
            write_manifest(manifest_path, payload)
            return payload

        review_paths = sorted(fakeidan_out.glob("*.md"))
        if not review_paths:
            payload = manifest_payload(
                error="fakeidan produced no markdown review files",
                manifest_path=str(manifest_path),
                claude_bin=claude_bin_label,
            )
            write_manifest(manifest_path, payload)
            return payload

        copied: list[str] = []
        for review_path in review_paths:
            target = stable_dir / review_path.name
            shutil.copy2(review_path, target)
            copied.append(str(target))

        verdicts: list[str] = []
        per_review_verdicts: list[dict[str, str]] = []
        for target_path in copied:
            target = Path(target_path)
            try:
                text = target.read_text()
            except OSError:
                payload = manifest_payload(error=f"could not read copied review: {target}", manifest_path=str(manifest_path), review_files=copied, claude_bin=claude_bin_label)
                write_manifest(manifest_path, payload)
                return payload
            verdict = VERDICT_PARSER.parse_verdict(text)
            if verdict is None or not VERDICT_PARSER.has_concerns_section(text):
                payload = manifest_payload(error=f"malformed fakeidan review: {target}", manifest_path=str(manifest_path), review_files=copied, claude_bin=claude_bin_label)
                write_manifest(manifest_path, payload)
                return payload
            verdicts.append(verdict)
            per_review_verdicts.append({"path": str(target), "verdict": verdict})

    verdict = aggregate_verdict(verdicts)

    # Cross-model-check fan-out: skip when caller (e.g. pr-gate) sets QA_GATE_SKIP_XMODEL=1
    # or when the user passes --no-cross-model. Also auto-skip during unit/test runs
    # so we don't burn real API tokens on synthetic fixtures.
    xmodel_review_path: Path | None = None
    xmodel_status: str | None = None
    in_test_run = (
        os.environ.get("PYTEST_CURRENT_TEST")
        or os.environ.get("QA_GATE_TEST_RUN")
        or "pytest" in sys.argv[0]
        or "unittest" in sys.argv[0]
        or Path(sys.argv[0]).name.startswith("test_")
    )
    if not getattr(args, "no_cross_model", False) and not os.environ.get("QA_GATE_SKIP_XMODEL") and not in_test_run:
        xmodel_out_dir = stable_dir / "xmodel"
        try:
            xmodel_review_path, xmodel_status = run_cross_model(
                review_artifacts, xmodel_out_dir, mode=args.mode,
                timeout=max(60, args.timeout - 30),
            )
        except Exception as exc:
            print(f"[qa-gate] xmodel error (non-blocking): {exc}", file=sys.stderr)
            xmodel_status = "skipped"
        if xmodel_status == "missing":
            xmodel_status = None  # treat missing runner as "not run" rather than skip-with-record
        if xmodel_status == "high":
            print(f"[qa-gate] cross-model-check found HIGH findings — review: {xmodel_review_path}", file=sys.stderr)
        elif xmodel_status:
            print(f"[qa-gate] cross-model-check status: {xmodel_status}", file=sys.stderr)

    # Status: BLOCKED if fakeidan says so OR if xmodel found HIGH
    status = "PASSED" if (verdict == "Approve" and xmodel_status != "high") else "BLOCKED"

    payload = manifest_payload(
        verdict=verdict,
        status=status,
        review_files=copied,
        verdicts=per_review_verdicts,
        manifest_path=str(manifest_path),
        claude_bin=claude_bin_label,
        error=None,
        xmodel_review=str(xmodel_review_path) if xmodel_review_path else None,
        xmodel_status=xmodel_status,
    )
    write_manifest(manifest_path, payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    self_check_error = verdict_parser_self_check()
    if self_check_error is not None:
        print(self_check_error, file=sys.stderr)
        return 1

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", nargs="+", help="Artifact path(s) to review")
    parser.add_argument("--mode", default="code", choices=["prose", "code", "video", "product", "spec"])
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--model")
    parser.add_argument("--runner", help="Override fakeidan runner path")
    parser.add_argument("--artifact-root", help="Override durable artifact root")
    parser.add_argument("--timeout", type=int, default=600, help="Timeout in seconds for the fakeidan run")
    parser.add_argument("--preflight-timeout", type=int, default=10, help="Timeout in seconds for fakeidan --help")
    parser.add_argument("--retain-artifacts", type=int, default=50, help="Number of qa-gate artifact directories to retain")
    parser.add_argument("--retain-failures", type=int, default=50, help="Number of blocked qa-gate artifact directories to retain")
    parser.add_argument("--no-cross-model", action="store_true",
                        help="skip cross-model-check (claude second-opinion). Off by default — "
                             "always-on cross-model verification is the whole point of the skill. "
                             "Also honors env var QA_GATE_SKIP_XMODEL=1 (used by pr-gate to avoid "
                             "double-firing when pr-gate runs its own xmodel pass).")
    args = parser.parse_args(argv)

    payload = run(args)
    print(json.dumps(payload, indent=2, sort_keys=True))
    # Exit 0 means fakeidan ran and parsed; callers must inspect payload["verdict"].
    # Exit 1 means fakeidan could not produce a structured review verdict.
    return 0 if payload["verdict"] != "UNABLE_TO_RUN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
