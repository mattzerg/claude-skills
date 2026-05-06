#!/usr/bin/env python3
"""
Queue runner — walks a list of (category, product, seeds) and runs the full
discover → scan → compare → rank → report pipeline for each, sequentially.

Usage:
    python3 run_queue.py [--start-at INDEX] [--only category]

Logs to ~/.claude/skills/competitive-review-skill/insights/queue.log
Skips cards phase (no interactive confirmation possible in batch).
Continues to next category on error; logs failures.

Categories are loaded from `categories.yaml` (edit there to add/remove/re-seed).
To resume a partial run: --start-at N.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

SKILL_DIR = Path(__file__).resolve().parent
PY = sys.executable
LOG_FILE = SKILL_DIR / "insights" / "queue.log"
STATUS_FILE = SKILL_DIR / "insights" / "queue_status.json"
CATEGORIES_YAML = SKILL_DIR / "categories.yaml"


def load_queue() -> list[tuple[str, str, list[str]]]:
    """Read categories.yaml and return [(slug, product, seeds), ...]."""
    if not CATEGORIES_YAML.exists():
        raise FileNotFoundError(f"missing {CATEGORIES_YAML}")
    cfg = yaml.safe_load(CATEGORIES_YAML.read_text(encoding="utf-8"))
    out = []
    for entry in cfg.get("categories", []):
        out.append((entry["slug"], entry["product"], list(entry["seeds"])))
    return out

# Categories live in categories.yaml — see load_queue() above.


def log(msg: str):
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def write_status(items: list[dict]):
    STATUS_FILE.write_text(json.dumps(items, indent=2), encoding="utf-8")


def run(*args: str, timeout: int = 3600) -> tuple[int, str, str]:
    """Run a script, return (rc, stdout_tail, stderr_tail)."""
    cmd = [PY, str(SKILL_DIR / args[0]), *args[1:]]
    log(f"  $ {' '.join(cmd)}")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        # Tail only — full output is verbose
        out_tail = "\n".join(r.stdout.splitlines()[-12:])
        err_tail = "\n".join(r.stderr.splitlines()[-12:])
        return r.returncode, out_tail, err_tail
    except subprocess.TimeoutExpired:
        return 124, "", f"TimeoutExpired after {timeout}s"


def process_category(category: str, product: str, seeds: list[str]) -> dict:
    started = datetime.now()
    status = {"category": category, "product": product, "started": started.isoformat(), "phases": {}}

    log(f"=== {category} (product={product}, {len(seeds)} seeds) ===")

    # Discover
    rc, out, err = run("discover.py", category, *seeds, "--product", product, "--n", "10", timeout=600)
    status["phases"]["discover"] = {"rc": rc, "err_tail": err if rc != 0 else ""}
    if rc != 0:
        log(f"  discover FAILED rc={rc}: {err[:300]}")
        return {**status, "ended": datetime.now().isoformat(), "ok": False, "stage_failed": "discover"}

    # Scan all candidates
    rc, out, err = run("scan.py", category, "--all", timeout=3600)
    status["phases"]["scan"] = {"rc": rc, "err_tail": err if rc != 0 else ""}
    if rc != 0:
        log(f"  scan FAILED rc={rc}: {err[:300]}")
        return {**status, "ended": datetime.now().isoformat(), "ok": False, "stage_failed": "scan"}

    # Compare
    rc, out, err = run("compare.py", category, "--product", product, timeout=2700)
    status["phases"]["compare"] = {"rc": rc, "err_tail": err if rc != 0 else ""}
    if rc != 0:
        log(f"  compare FAILED rc={rc}: {err[:300]}")
        # Try once more with --reuse-inventory if state has any matrix
        log(f"  retrying compare with --reuse-inventory")
        rc2, out2, err2 = run("compare.py", category, "--product", product, "--reuse-inventory", timeout=2700)
        status["phases"]["compare_retry"] = {"rc": rc2, "err_tail": err2 if rc2 != 0 else ""}
        if rc2 != 0:
            return {**status, "ended": datetime.now().isoformat(), "ok": False, "stage_failed": "compare"}

    # Rank with defaults (non-interactive)
    rc, out, err = run("rank.py", category, "--top", "10", timeout=120)
    status["phases"]["rank"] = {"rc": rc, "err_tail": err if rc != 0 else ""}

    # Report
    rc, out, err = run("report.py", category, "--product", product, timeout=900)
    status["phases"]["report"] = {"rc": rc, "err_tail": err if rc != 0 else ""}
    if rc != 0:
        log(f"  report FAILED rc={rc}: {err[:300]}")
        return {**status, "ended": datetime.now().isoformat(), "ok": False, "stage_failed": "report"}

    elapsed = (datetime.now() - started).total_seconds()
    log(f"  DONE in {elapsed:.0f}s")
    return {**status, "ended": datetime.now().isoformat(), "ok": True, "elapsed_seconds": elapsed}


def wait_for_existing_subprocess(prev_state_category: str | None = None):
    """If a prior compare/scan is still running (subprocess `claude` busy), wait a bit.
    Cheap heuristic: check `pgrep` for claude. If found, sleep and retry up to N minutes."""
    import time
    for _ in range(60):  # up to 30 min
        try:
            r = subprocess.run(["pgrep", "-f", "skills/competitive-review-skill"],
                               capture_output=True, text=True, timeout=5)
            other_pids = [p for p in r.stdout.split() if p and p != str(subprocess.os.getpid())]
            if not other_pids:
                return True
            log(f"  waiting for {len(other_pids)} other competitive-review processes ({other_pids[:3]}...)")
        except Exception as e:
            log(f"  pgrep err: {e}; assuming clear")
            return True
        time.sleep(30)
    log(f"  WARNING: still other processes after 30min — proceeding anyway")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-at", type=int, default=0)
    parser.add_argument("--only", help="Run only this category slug")
    parser.add_argument("--no-wait", action="store_true", help="Skip waiting for other processes")
    args = parser.parse_args()

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.touch()

    full_queue = load_queue()
    if args.only:
        queue = [q for q in full_queue if q[0] == args.only]
    else:
        queue = full_queue[args.start_at :]

    log(f"=== Queue runner starting: {len(queue)} categories ===")
    for cat, prod, seeds in queue:
        log(f"  - {cat} → {prod} ({len(seeds)} seeds)")

    if not args.no_wait:
        wait_for_existing_subprocess()

    results = []
    for category, product, seeds in queue:
        result = process_category(category, product, seeds)
        results.append(result)
        write_status(results)
        # Polite pause between categories
        time.sleep(5)

    # Summary
    log(f"\n=== Queue runner done ===")
    ok = sum(1 for r in results if r["ok"])
    log(f"  {ok}/{len(results)} successful")
    for r in results:
        marker = "✓" if r["ok"] else "✗"
        elapsed = f"{r.get('elapsed_seconds', 0):.0f}s" if r["ok"] else f"failed at {r.get('stage_failed','?')}"
        log(f"  {marker} {r['category']:<25s} {elapsed}")


if __name__ == "__main__":
    main()
