"""pr-gate sub-skill result cache.

30-min TTL keyed on (branch, diff_sha256, subskill, mode). Matches the
iteration pattern where Matt fixes findings and re-runs `pr-gate` minutes
later against an only-slightly-different (or identical) diff. Without the
cache every re-run pays the full fakeidan + cross-model price even when
nothing changed.

Cached payload is the review_text (str) returned by each run_X(). We do NOT
cache the temp review files themselves — they live in tempfiles that get
torn down. has_high_findings() runs against the text, not the files.

FAIL-CLOSED / error sentinels are never cached so a transient tool failure
doesn't lock in a stale fail.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path

CACHE_DIR = Path(__file__).parent / "cache"
TTL_SEC = 1800  # 30 min

_FAIL_MARKERS = (
    "FAIL-CLOSED",
    "DIFF TRUNCATED",
    "runner missing",
    "timeout",
)


def current_diff_hash(base: str) -> str | None:
    """sha256 of `git diff origin/<base>...HEAD`. None on failure."""
    try:
        r = subprocess.run(
            ["git", "diff", f"origin/{base}...HEAD"],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if r.returncode != 0:
        return None
    return hashlib.sha256(r.stdout.encode("utf-8", errors="replace")).hexdigest()[:16]


def diff_hash_of(diff_text: str) -> str:
    return hashlib.sha256(diff_text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _key_path(branch: str, diff_hash: str, subskill: str, mode: str | None) -> Path:
    safe_branch = branch.replace("/", "-").replace("\\", "-")
    mode_part = f"-{mode}" if mode else ""
    return CACHE_DIR / f"{safe_branch}-{diff_hash}-{subskill}{mode_part}.json"


def get(branch: str, diff_hash: str | None, subskill: str, mode: str | None = None) -> str | None:
    """Return cached review_text if a fresh hit exists, else None."""
    if not diff_hash:
        return None
    p = _key_path(branch, diff_hash, subskill, mode)
    if not p.exists():
        return None
    try:
        payload = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    ts = payload.get("ts", 0)
    if (time.time() - ts) > TTL_SEC:
        return None
    return payload.get("text")


def put(branch: str, diff_hash: str | None, subskill: str, text: str, mode: str | None = None) -> None:
    """Persist review_text to cache. Skip on tool failures."""
    if not diff_hash or not text:
        return
    if any(marker in text for marker in _FAIL_MARKERS):
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p = _key_path(branch, diff_hash, subskill, mode)
    try:
        p.write_text(json.dumps({"ts": time.time(), "text": text, "subskill": subskill, "mode": mode}))
    except OSError:
        pass


def prune_old(max_age_sec: int = 24 * 3600) -> int:
    """Drop entries older than max_age_sec. Returns count removed."""
    if not CACHE_DIR.exists():
        return 0
    cutoff = time.time() - max_age_sec
    n = 0
    for p in CACHE_DIR.glob("*.json"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
                n += 1
        except OSError:
            continue
    return n
