#!/usr/bin/env python3
"""ship-gate mechanical check runner.

Thin fail-closed orchestrator over tools/check_*.py. The model still owns the
judgment rubric in SKILL.md; this runs the mechanical brand-discipline checks
and refuses to let silence pass as approval. Posture mirrors pr-gate/run.py's
has_high_findings rule: a tool crash, timeout, or unparseable output becomes
a synthetic HIGH finding and the verdict goes RED.

Usage:
    python3 run.py <artifact-path-or-url> [--type page|pdf|image|launch|blog]
                   [--json] [--timeout SECS]

Artifact-type → checks map (tool contracts documented in tools/README.md):
    page/launch  URL        → check_richness.py <url> · check_palette.py audit <url>
    page/launch  local path → check_palette.py classify <path> · check_brand_hex_literals.py <path>
    blog         .md path   → check_blog_imagery_coherence.py <md> · check_metadata_drift.py <md>
    pdf / image  local path → check_palette.py classify <path>

Severity mapping (tools emit 0 green / 1 yellow / 2 red + a `# <name> — <STATUS>`
first line on stdout):
    exit 0 + parseable header → pass
    exit 1 + parseable header → MEDIUM finding
    exit 2 + parseable header → HIGH finding
    anything else (64/70/signal/timeout/crash/missing header) → synthetic HIGH, fail-closed

Verdict: any HIGH → RED · any MEDIUM → YELLOW · else GREEN.
Exit codes (gate contract, NOT the tools' own convention): 0 GREEN, 1 RED, 2 YELLOW.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_TIMEOUT = 30
# First line every tools/check_*.py prints: `# <check name> — <STATUS>`
HEADER_RE = re.compile(r"^#\s+.+?\s+[—–-]\s+(\S.*)$")
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}


def tools_dir() -> Path:
    # Env override exists for tests (inject a crashing tool without touching
    # the real tools/), never for routine invocation.
    override = os.environ.get("SHIP_GATE_TOOLS_DIR")
    return Path(override) if override else Path(__file__).resolve().parent / "tools"


def is_url(artifact: str) -> bool:
    return artifact.startswith(("http://", "https://"))


def infer_type(artifact: str) -> str:
    if is_url(artifact):
        return "page"
    suffix = Path(artifact).suffix.lower()
    if suffix == ".md":
        return "blog"
    if suffix == ".pdf":
        return "pdf"
    if suffix in IMAGE_EXTS:
        return "image"
    return "page"


def checks_for(artifact: str, atype: str) -> list[tuple[str, str, list[str]]]:
    """(check name, tool filename, tool args) — applicability per SKILL.md gate classes."""
    if atype in ("page", "launch"):
        if is_url(artifact):
            return [
                ("visual-richness", "check_richness.py", [artifact]),
                ("palette-audit", "check_palette.py", ["audit", artifact]),
            ]
        return [
            ("palette-classify", "check_palette.py", ["classify", artifact]),
            ("brand-hex-literals", "check_brand_hex_literals.py", [artifact]),
        ]
    if atype == "blog":
        return [
            ("blog-imagery-coherence", "check_blog_imagery_coherence.py", [artifact]),
            ("metadata-drift", "check_metadata_drift.py", [artifact]),
        ]
    # pdf / image assets: palette routing at render time (SKILL.md gate class 5;
    # also resolves the 2026-05-09 landing-page/one-pager deferred wiring —
    # their rendered outputs land here, see SKILL.md → History).
    return [("palette-classify", "check_palette.py", ["classify", artifact])]


def synthetic_high(name: str, cmd: str, reason: str, stdout: str = "",
                   stderr: str = "", exit_code: int | None = None,
                   duration: float = 0.0) -> dict:
    return {
        "check": name,
        "cmd": cmd,
        "exit_code": exit_code,
        "status": "FAIL-CLOSED",
        "severity": "HIGH",
        "synthetic": True,
        "finding": f"gate FAIL-CLOSED: {reason}",
        "stdout": stdout[-2000:],
        "stderr": stderr[-2000:],
        "duration_s": round(duration, 2),
    }


def run_check(name: str, tool: Path, args: list[str], timeout: int) -> dict:
    cmd = [sys.executable, str(tool)] + args
    cmd_str = " ".join(cmd)
    if not tool.exists():
        return synthetic_high(name, cmd_str, f"tool missing at {tool}")
    started = time.monotonic()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return synthetic_high(name, cmd_str, f"timed out after {timeout}s",
                              duration=time.monotonic() - started)
    except OSError as exc:
        return synthetic_high(name, cmd_str, f"could not launch: {exc}",
                              duration=time.monotonic() - started)
    duration = time.monotonic() - started
    stdout, stderr = proc.stdout or "", proc.stderr or ""
    first = next((line for line in stdout.splitlines() if line.strip()), "")
    header = HEADER_RE.match(first.strip())
    if proc.returncode not in (0, 1, 2) or not header:
        # An unhandled Python exception exits 1 with an empty stdout — same
        # code as a legit yellow. The status header is what disambiguates:
        # no header means crash/contract-drift, never a reviewed result.
        if proc.returncode in (0, 1, 2):
            reason = (f"exit {proc.returncode} with no parseable `# <check> — <STATUS>` "
                      f"header (crash or output-contract drift)")
        else:
            reason = f"exit {proc.returncode} (usage/tool error or signal)"
        return synthetic_high(name, cmd_str, reason, stdout, stderr,
                              proc.returncode, duration)
    status = header.group(1).strip()
    severity = {0: None, 1: "MEDIUM", 2: "HIGH"}[proc.returncode]
    # Cross-validate the header against the exit code: a tool that PRINTS a
    # red/error status but exits clean (e.g. a future edit drops sys.exit(main()))
    # must never pass as GREEN — that's silence-as-approval, the one failure
    # this runner exists to block. Statuses are free-form, so only the
    # dangerous direction is keyword-checked.
    if severity != "HIGH" and re.search(r"\b(RED|ERROR|FAIL)", status, re.IGNORECASE):
        return synthetic_high(
            name, cmd_str,
            f"header/exit-code mismatch: status {status!r} with exit {proc.returncode}",
            stdout, stderr, proc.returncode, duration)
    return {
        "check": name,
        "cmd": cmd_str,
        "exit_code": proc.returncode,
        "status": status,
        "severity": severity,
        "synthetic": False,
        "finding": f"{name}: {status} (exit {proc.returncode})" if severity else None,
        "stdout": stdout[-4000:],
        "stderr": stderr[-2000:],
        "duration_s": round(duration, 2),
    }


def print_summary(manifest: dict) -> None:
    print(f"# ship-gate — {manifest['verdict']}")
    print()
    print(f"**Artifact**: {manifest['artifact']}  ·  **Type**: {manifest['artifact_type']}")
    print()
    for r in manifest["checks"]:
        mark = {None: "✓", "MEDIUM": "!", "HIGH": "✗"}[r["severity"]]
        syn = " (synthetic, fail-closed)" if r["synthetic"] else ""
        print(f"- {mark} {r['check']} — {r['status']}{syn} [{r['duration_s']}s]")
    if manifest["findings"]:
        print()
        print("## Findings")
        for f in manifest["findings"]:
            print(f"- **{f['severity']}** {f['text']}")
    print()
    print("Exit codes: 0 GREEN · 1 RED · 2 YELLOW. Rubric judgment still per SKILL.md.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="ship-gate/run.py",
        description="Fail-closed runner for ship-gate's mechanical brand-discipline checks.",
    )
    ap.add_argument("artifact", help="artifact path or URL to gate")
    ap.add_argument("--type", dest="atype",
                    choices=["page", "pdf", "image", "launch", "blog"],
                    help="artifact type (default: inferred from the artifact)")
    ap.add_argument("--json", action="store_true", help="emit manifest JSON instead of a summary")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                    help="per-check timeout in seconds (visual-richness on slow pages may need 180)")
    args = ap.parse_args(argv)

    artifact = args.artifact
    atype = args.atype or infer_type(artifact)

    results: list[dict] = []
    if not is_url(artifact) and not Path(artifact).expanduser().exists():
        results.append(synthetic_high("artifact-exists", "", f"artifact not found: {artifact}"))
    else:
        tdir = tools_dir()
        for name, tool_file, tool_args in checks_for(artifact, atype):
            results.append(run_check(name, tdir / tool_file, tool_args, args.timeout))

    findings = [r for r in results if r["severity"]]
    if any(r["severity"] == "HIGH" for r in results):
        verdict, exit_code = "RED", 1
    elif findings:
        verdict, exit_code = "YELLOW", 2
    else:
        verdict, exit_code = "GREEN", 0

    manifest = {
        "gate": "ship-gate",
        "artifact": artifact,
        "artifact_type": atype,
        "verdict": verdict,
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "checks": results,
        "findings": [
            {"severity": r["severity"], "check": r["check"], "text": r["finding"]}
            for r in findings
        ],
    }
    if args.json:
        print(json.dumps(manifest, indent=2))
    else:
        print_summary(manifest)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
