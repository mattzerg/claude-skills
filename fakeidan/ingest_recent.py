#!/usr/bin/env python3
"""fakeidan/ingest_recent — refresh the durable Idan PR-review bar from the corpus.

Initiative I1+I2 of Matt's system roadmap (the "mine GitHub/Slack to build out
fakeidan" ask). REWRITE of the old flat-keyword version.

What changed vs the old version:
  - Reads the ALREADY-INGESTED `~/.claude/state/gh_corpus` (per-PR jsonl, full
    bodies) instead of making its own ad-hoc `gh` calls. Reuses the shared
    `corpus_reader` helper that `run.py`'s live signal also conceptually mirrors.
  - Pins a SINGLE cutoff timestamp (read once, stamped into output) so counts are
    reproducible despite the live ~15-min corpus refresh.
  - Clusters real-Idan review comments by the 7 SAFETY CLASSES from
    `composite_adversarial_review.md` (auth, webhook, url-fetch/SSRF,
    input-parser, IPC/MCP, cookies/sessions/secrets, quota/money) plus an
    "other/process" bucket — not flat keyword categories.
  - Regenerates a MACHINE-MANAGED region in the durable bar between
    `<!-- BEGIN auto-clusters -->` / `<!-- END auto-clusters -->` markers, placed
    AFTER the hand-curated patterns. Everything above BEGIN is never touched.

Filter: author `idanbeck`, EXCLUDING `[fake idan]` paste-backs (mirrors run.py).

Run modes:
  ingest_recent.py                 — default: last 30d, rewrite the auto-region
  ingest_recent.py --days 14
  ingest_recent.py --dry-run       — print the region + stats, don't write
  ingest_recent.py --cutoff ISO    — pin an explicit cutoff (for reproducibility)
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from corpus_reader import (  # noqa: E402
    CORPUS_DIR,
    CorpusComment,
    corpus_last_update,
    load_real_idan_comments,
)

HOME = Path.home()
# Canonical vault resolver — not the hardcoded iCloud-project symlink (twin of run.py).
sys.path.insert(0, str(HOME / ".config" / "zerg" / "lib"))
from vault_path import vault_root  # noqa: E402
MEMORY_RULE = vault_root() / "claude-memory" / "feedback_idan_pr_review_bar.md"

BEGIN_MARKER = "<!-- BEGIN auto-clusters -->"
END_MARKER = "<!-- END auto-clusters -->"

# Below this many clusterable real-Idan comments, the corpus can't support a
# meaningful per-safety-class distribution; the region degrades gracefully
# (freshness header + an honest "insufficient recent signal" note) rather than
# fabricating buckets.
MIN_SIGNAL = 3

# --- The 7 safety classes (from composite_adversarial_review.md) + a fallback.
# Ordered; "other_process" is the catch-all for genuine Idan comments that carry
# no safety-class signal (process/discipline/follow-up notes).
SAFETY_CLASSES: list[tuple[str, str, re.Pattern]] = [
    (
        "auth",
        "Auth / authorization / access-control",
        re.compile(
            r"\b(auth(?:n|z|orization|enticat\w*)?|login|session(?: row)?|"
            r"permission|owner(?:ship)?|membership|access[- ]?control|rbac|"
            r"privilege|bootstrap owner|workspace member|upgrade-time auth)\b",
            re.I,
        ),
    ),
    (
        "webhook",
        "Webhook receivers / delivery / retries",
        re.compile(
            r"\b(webhook|retry worker|delivery|2xx|ack(?:nowledge)?|"
            r"event_id|dedup|signing secret|signature|hmac|callback)\b",
            re.I,
        ),
    ),
    (
        "url_fetch_ssrf",
        "URL fetch / SSRF / outbound HTTP",
        re.compile(
            r"\b(ssrf|outbound (?:http|fetch|request)|metadata (?:ip|endpoint|"
            r"service)|169\.254|rfc ?1918|dns rebind\w*|loopback|link-local|"
            r"fetch-from-customer|arbitrary[- ]?url|imds)\b",
            re.I,
        ),
    ),
    (
        "input_parser",
        "User-input parsers / serialization / validation",
        re.compile(
            r"\b(parser?|parse|deserializ\w*|serializ\w*|sanitiz\w*|escape|"
            r"injection|validat\w*|untrusted input|user[- ]?supplied|"
            r"to_dict|manifest|cgroup parser|markdown-strip\w*)\b",
            re.I,
        ),
    ),
    (
        "ipc_mcp",
        "IPC / MCP / sockets / streams",
        re.compile(
            r"\b(ipc|mcp|socket|chmod 0600|0600|unix domain|bridge socket|"
            r"stream (?:disconnect|abort)|websocket|ws endpoint|sse|"
            r"named pipe|stdio)\b",
            re.I,
        ),
    ),
    (
        "secrets",
        "Cookies / sessions / secrets / credentials",
        re.compile(
            r"\b(secret|credential|token(?:_id)?|api[- ]?key|password|cookie|"
            r"keystore|encrypt(?:ion|-at-rest)?|plaintext|kms|redact\w*|"
            r"rotate|session_secret|signing-secret)\b",
            re.I,
        ),
    ),
    (
        "quota_money",
        "Quota / money / rate-limit / billing",
        re.compile(
            r"\b(quota|rate[- ]?limit|429|retry-after|money|currency|amount|"
            r"charge|invoice|transfer|ledger|double-entry|daily[- ]?spend|"
            r"budget|max-?turns|runaway|cap(?: edge| applied)?|"
            r"select.*for update|policy (?:gate|evaluator)|spend)\b",
            re.I,
        ),
    ),
]

OTHER_KEY = "other_process"
OTHER_LABEL = "Other / process / discipline"


def pick_cutoff(explicit: Optional[str], corpus_dir: Path = CORPUS_DIR) -> dt.datetime:
    """Pin the single reproducibility cutoff (UTC), read once.

    Priority: explicit --cutoff > corpus last_pull_at > now(). Using the corpus's
    own last-update time means the cutoff doesn't drift mid-run as the launchd
    refresh appends data.
    """
    if explicit:
        from corpus_reader import parse_iso_timestamp

        parsed = parse_iso_timestamp(explicit)
        if parsed is None:
            raise SystemExit(f"--cutoff not parseable as ISO-8601: {explicit!r}")
        return parsed
    last = corpus_last_update(corpus_dir)
    if last is not None:
        return last
    return dt.datetime.now(dt.timezone.utc)


def classify(body: str) -> list[str]:
    """Return the safety-class keys this comment body matches (possibly many).

    Empty list means no safety-class signal → caller buckets it as other_process.
    """
    hits = [key for key, _label, rx in SAFETY_CLASSES if rx.search(body or "")]
    return hits


def _exemplar(comment: CorpusComment) -> str:
    """One-line provenance-tagged exemplar pattern from a comment body."""
    flat = re.sub(r"\s+", " ", comment.body or "").strip()
    quote = flat[:160].rstrip()
    if len(flat) > 160:
        quote += "…"
    return f"{quote}  ({comment.ref}, {comment.date}, idanbeck)"


def build_clusters(comments: list[CorpusComment]) -> dict:
    """Cluster comments by safety class. Returns counts + up to 3 exemplars each.

    A comment matching multiple classes counts toward each. A comment matching
    none lands in other_process. Exemplars are ordered newest-first (more recent
    signal is more representative of Idan's current bar) and deduped per class.
    """
    counts: Counter = Counter()
    exemplars: dict[str, list[str]] = defaultdict(list)
    seen_ref: dict[str, set] = defaultdict(set)

    # newest-first so the (≤3) exemplars we keep are the freshest
    for c in sorted(comments, key=lambda x: x.ts, reverse=True):
        keys = classify(c.body)
        if not keys:
            keys = [OTHER_KEY]
        for key in keys:
            counts[key] += 1
            if len(exemplars[key]) < 3 and c.ref not in seen_ref[key]:
                exemplars[key].append(_exemplar(c))
                seen_ref[key].add(c.ref)
    return {"counts": dict(counts), "exemplars": dict(exemplars)}


def render_region(
    comments: list[CorpusComment],
    *,
    cutoff: dt.datetime,
    window_days: int,
) -> str:
    """Render the machine-managed region body (between, but not including, markers)."""
    cutoff_str = cutoff.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    refs = sorted({c.ref for c in comments})
    n_comments = len(comments)
    k_prs = len(refs)
    window_start = (cutoff - dt.timedelta(days=window_days)).strftime("%Y-%m-%d")
    window_end = cutoff.strftime("%Y-%m-%d")

    lines: list[str] = []
    lines.append("")
    lines.append(
        "## Auto-clustered Idan signal (machine-managed — do not hand-edit)"
    )
    lines.append("")
    lines.append(
        "_This region is regenerated by `ingest_recent.py` from the local "
        "`gh_corpus`. Everything ABOVE the BEGIN marker is hand-curated and never "
        "touched by the script._"
    )
    lines.append("")
    # Freshness header
    lines.append(
        f"**Freshness:** generated {today} · cutoff `{cutoff_str}` · "
        f"window {window_start} → {window_end} ({window_days}d) · "
        f"{n_comments} real-Idan **review** comments across {k_prs} PRs "
        "(formal reviews only — issue-comments + PR responses excluded)."
    )
    lines.append("")

    if n_comments < MIN_SIGNAL:
        lines.append(
            f"> **Insufficient recent review signal** ({n_comments} formal-review "
            f"comment(s) in the window, below the {MIN_SIGNAL}-comment clustering "
            "floor). Idan's recent `idanbeck` activity is mostly PR-response / "
            "follow-up issue-comments, not bar-setting reviews — and those are "
            "deliberately excluded. The hand-curated patterns above remain the "
            "authoritative bar; this region intentionally does NOT fabricate a "
            "distribution. Re-run after the next real review lands (or pass "
            "`--all-comments` for the noisier topic view)."
        )
        lines.append("")
        return "\n".join(lines)

    clusters = build_clusters(comments)
    counts = clusters["counts"]
    exemplars = clusters["exemplars"]

    # Distribution table (safety classes in canonical order, then other_process)
    lines.append("### Safety-class distribution")
    lines.append("")
    lines.append("| Safety class | Real-Idan comments in window |")
    lines.append("|---|---|")
    for key, label, _rx in SAFETY_CLASSES:
        lines.append(f"| {label} | {counts.get(key, 0)} |")
    lines.append(f"| {OTHER_LABEL} | {counts.get(OTHER_KEY, 0)} |")
    lines.append("")

    # Per-class exemplars
    lines.append("### Exemplars per safety class (newest first, with provenance)")
    lines.append("")
    any_exemplar = False
    for key, label, _rx in SAFETY_CLASSES + [(OTHER_KEY, OTHER_LABEL, None)]:
        cnt = counts.get(key, 0)
        if cnt == 0:
            continue
        any_exemplar = True
        lines.append(f"#### {label} — {cnt}")
        lines.append("")
        for ex in exemplars.get(key, []):
            lines.append(f"- {ex}")
        lines.append("")
    if not any_exemplar:
        lines.append("_(No clusterable comments — see freshness header.)_")
        lines.append("")
    return "\n".join(lines)


def splice_region(existing_text: str, region_body: str) -> str:
    """Replace (or append) the auto-region in the durable bar.

    - If both markers exist, replace everything strictly BETWEEN them.
    - If absent, append the marker block at the END of the file (after all
      hand-curated content).
    Content above BEGIN is always byte-identical before/after.
    """
    block = f"{BEGIN_MARKER}\n{region_body}\n{END_MARKER}\n"
    begin_idx = existing_text.find(BEGIN_MARKER)
    end_idx = existing_text.find(END_MARKER)
    if begin_idx != -1 and end_idx != -1 and end_idx > begin_idx:
        head = existing_text[:begin_idx]
        tail = existing_text[end_idx + len(END_MARKER):]
        # Drop a single leading newline on the tail to avoid blank-line drift.
        if tail.startswith("\n"):
            tail = tail[1:]
        return f"{head}{block}{tail}"
    # Append: ensure exactly one blank line before the block.
    base = existing_text.rstrip("\n")
    return f"{base}\n\n{block}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30, help="window in days (default 30)")
    parser.add_argument("--cutoff", default=None, help="pin cutoff (ISO-8601 UTC) for reproducibility")
    parser.add_argument("--dry-run", action="store_true", help="print region, don't write")
    parser.add_argument("--bar-path", default=str(MEMORY_RULE), help="durable bar path (override for tests)")
    parser.add_argument("--corpus-dir", default=str(CORPUS_DIR), help="gh_corpus dir (override for tests)")
    parser.add_argument("--all-comments", action="store_true",
                        help="include issue-comments + PR responses (default: formal reviews only — "
                             "the clean review-bar signal)")
    args = parser.parse_args()

    corpus_dir = Path(args.corpus_dir)
    bar_path = Path(args.bar_path)

    cutoff = pick_cutoff(args.cutoff, corpus_dir)
    # Default to review_only: the durable bar should reflect Idan's formal reviews,
    # not the response/follow-up issue-comments the idanbeck account also posts.
    comments = load_real_idan_comments(
        cutoff=cutoff, window_days=args.days, corpus_dir=corpus_dir,
        review_only=not args.all_comments,
    )
    region_body = render_region(comments, cutoff=cutoff, window_days=args.days)

    print(
        f"[ingest] cutoff={cutoff.strftime('%Y-%m-%dT%H:%M:%SZ')} window={args.days}d "
        f"real-Idan comments={len(comments)}",
        file=sys.stderr,
    )

    if args.dry_run:
        print(BEGIN_MARKER)
        print(region_body)
        print(END_MARKER)
        return 0

    if not bar_path.exists():
        print(f"[ingest] ERROR: durable bar not found at {bar_path}", file=sys.stderr)
        return 1

    existing = bar_path.read_text(encoding="utf-8")
    new_text = splice_region(existing, region_body)
    if new_text == existing:
        print("[ingest] auto-region unchanged (idempotent no-op)")
        return 0
    bar_path.write_text(new_text, encoding="utf-8")
    print(f"[ingest] regenerated auto-region in {bar_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
