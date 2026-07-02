#!/usr/bin/env python3
"""autoresearch — measure a skill's quality+cost on golden cases, and A/B a
candidate edit, keeping only validated improvements.

Adapted from karpathy/autoresearch (frozen eval + keep-only-wins + a log of
everything tried) for *skill improvement*: the "training target" is a SKILL.md,
the "eval harness" is a frozen set of golden cases, the metric is pass-rate
(primary) + cost (tokens/wall, tiebreak).

Pure-ish stdlib (+ optional PyYAML for .yaml cases). No secrets, writes only
under this skill's experiments/ dir (and swaps the target SKILL.md only with
--apply on a confirmed KEEP).

Usage:
    run.py eval  --skill NAME --cases FILE [--runner echo|claude|zclaude]
    run.py ab    --skill NAME --cases FILE --variant SKILL.md [--apply]
                 [--runner ...] [--tol 0.02]

Runners:
    echo   - smoke mode: agent output = the prompt echoed (no spend). Verifies
             the harness end-to-end; assertions on prompt text still work.
    claude - `claude -p` headless (real spend).
    zclaude- Matt's account-routed `zclaude -p` (real spend).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
SKILL_DIR = Path(__file__).resolve().parent
EXP_DIR = SKILL_DIR / "experiments"
# Stack-relative: the skills/ dir of whichever stack this copy lives in
# (~/.claude/skills or ~/.codex/skills), so the Codex copy A/Bs Codex skills.
SKILLS_ROOT = SKILL_DIR.parent


def load_cases(path: Path) -> list:
    text = path.read_text()
    if path.suffix.lower() in (".yaml", ".yml"):
        import yaml  # available in env
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    cases = data["cases"] if isinstance(data, dict) and "cases" in data else data
    if not isinstance(cases, list):
        raise SystemExit("cases file must be a list (or {cases: [...]})")
    return cases


def run_agent(prompt: str, runner: str, timeout: int = 240) -> tuple[str, float]:
    """Return (output_text, wall_seconds)."""
    if runner == "echo":
        return prompt, 0.0
    cmd = {
        "claude": ["claude", "-p", prompt],
        "zclaude": ["zclaude", "-p", prompt],
    }.get(runner)
    if cmd is None:
        raise SystemExit(f"unknown runner: {runner}")
    t0 = time.monotonic()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = proc.stdout or proc.stderr
    except subprocess.TimeoutExpired:
        out = "<TIMEOUT>"
    return out, time.monotonic() - t0


def score_case(case: dict, output: str) -> tuple[bool, str]:
    """Assertion-based scoring. Returns (passed, reason)."""
    low = output.lower()
    if "expect" in case:  # substring(s), all must be present
        needles = case["expect"]
        needles = [needles] if isinstance(needles, str) else needles
        missing = [n for n in needles if n.lower() not in low]
        return (not missing, "ok" if not missing else f"missing: {missing}")
    if "expect_regex" in case:
        ok = re.search(case["expect_regex"], output, re.I | re.S) is not None
        return ok, "regex ok" if ok else "regex no-match"
    if "expect_absent" in case:
        bad = [n for n in ([case["expect_absent"]] if isinstance(case["expect_absent"], str)
                           else case["expect_absent"]) if n.lower() in low]
        return (not bad, "clean" if not bad else f"contains: {bad}")
    return True, "no-assertion (counted as pass)"


def est_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def measure(skill: str, cases: list, runner: str) -> dict:
    rows = []
    for c in cases:
        prompt = c["prompt"]
        out, wall = run_agent(prompt, runner)
        passed, reason = score_case(c, out)
        rows.append({"id": c.get("id", prompt[:32]), "passed": passed,
                     "reason": reason, "wall_s": round(wall, 2),
                     "est_tokens": est_tokens(out)})
    n = len(rows) or 1
    return {
        "skill": skill, "runner": runner, "n": len(rows),
        "pass_rate": round(sum(r["passed"] for r in rows) / n, 4),
        "mean_wall_s": round(sum(r["wall_s"] for r in rows) / n, 2),
        "mean_tokens": round(sum(r["est_tokens"] for r in rows) / n, 1),
        "rows": rows,
    }


def skill_md_path(skill: str) -> Path:
    p = SKILLS_ROOT / skill / "SKILL.md"
    if not p.exists():
        raise SystemExit(f"skill not found: {p}")
    return p


def write_log(tag: str, payload: dict) -> Path:
    EXP_DIR.mkdir(parents=True, exist_ok=True)
    # Deterministic-ish name from content hash of rows (no Date.now in scripts ok here,
    # but we avoid wall-clock filenames to keep reruns idempotent under same input).
    stamp = payload.get("stamp") or "latest"
    path = EXP_DIR / f"{tag}-{stamp}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def cmd_eval(args):
    cases = load_cases(Path(args.cases))
    res = measure(args.skill, cases, args.runner)
    res["stamp"] = args.stamp
    log = write_log(f"eval-{args.skill}", res)
    print(f"[eval] {args.skill} via {args.runner}: pass_rate={res['pass_rate']} "
          f"mean_wall={res['mean_wall_s']}s mean_tokens={res['mean_tokens']} (n={res['n']})")
    for r in res["rows"]:
        print(f"   {'PASS' if r['passed'] else 'FAIL'}  {r['id']}  — {r['reason']}")
    print(f"   log: {log}")
    return 0


def cmd_ab(args):
    cases = load_cases(Path(args.cases))
    target = skill_md_path(args.skill)
    variant = Path(args.variant)
    if not variant.exists():
        raise SystemExit(f"variant not found: {variant}")

    base = measure(args.skill, cases, args.runner)

    backup = target.with_suffix(".md.autoresearch-bak")
    shutil.copy2(target, backup)
    try:
        shutil.copy2(variant, target)
        cand = measure(args.skill, cases, args.runner)
    finally:
        shutil.copy2(backup, target)  # always restore first
        backup.unlink(missing_ok=True)

    better_quality = cand["pass_rate"] > base["pass_rate"] + 1e-9
    equal_quality = abs(cand["pass_rate"] - base["pass_rate"]) <= 1e-9
    cheaper = cand["mean_tokens"] < base["mean_tokens"] * (1 - args.tol)
    keep = better_quality or (equal_quality and cheaper)
    verdict = "KEEP" if keep else "REVERT"

    if keep and args.apply:
        shutil.copy2(variant, target)
        applied = True
    else:
        applied = False

    payload = {"skill": args.skill, "runner": args.runner, "tol": args.tol,
               "baseline": base, "candidate": cand, "verdict": verdict,
               "applied": applied, "variant": str(variant), "stamp": args.stamp}
    log = write_log(f"ab-{args.skill}", payload)
    print(f"[ab] {args.skill}: baseline pass={base['pass_rate']} tok={base['mean_tokens']} "
          f"| candidate pass={cand['pass_rate']} tok={cand['mean_tokens']}")
    print(f"   VERDICT: {verdict}  (applied={applied})")
    print(f"   reason: quality {'+' if better_quality else ('=' if equal_quality else '-')}"
          f", cost {'cheaper' if cheaper else 'not-cheaper'}")
    print(f"   log: {log}")
    if keep and not args.apply:
        print("   (re-run with --apply to write the variant over the live SKILL.md)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Measure/A-B a skill on frozen golden cases.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    common = dict()
    for name in ("eval", "ab"):
        sp = sub.add_parser(name)
        sp.add_argument("--skill", required=True)
        sp.add_argument("--cases", required=True)
        sp.add_argument("--runner", default="echo", choices=["echo", "claude", "zclaude"])
        sp.add_argument("--stamp", default="latest", help="suffix for the log filename")
        if name == "ab":
            sp.add_argument("--variant", required=True, help="candidate SKILL.md")
            sp.add_argument("--apply", action="store_true", help="on KEEP, write variant live")
            sp.add_argument("--tol", type=float, default=0.02, help="cost-tiebreak tolerance")
    args = ap.parse_args(argv)
    return {"eval": cmd_eval, "ab": cmd_ab}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
