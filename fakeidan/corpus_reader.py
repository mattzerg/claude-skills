#!/usr/bin/env python3
"""fakeidan/corpus_reader — shared read-only access to the local gh_corpus.

Single source of truth for "read the already-ingested GitHub corpus" so that
`ingest_recent.py` (durable-bar refresh) and `run.py` (live review signal) don't
duplicate corpus-walking + real-vs-fake-Idan filtering logic.

The corpus is produced by `gh_corpus.py update` (launchd, ~15-min refresh):

    ~/.claude/state/gh_corpus/
        <repo__slug>/pr-<N>.jsonl   — one JSON line per comment, FULL body
        _index.jsonl                — flat {ts,repo,pr,author,kind,snippet}
        _meta.json                  — {repo: {prs: {...}, last_pull_at: ISO}}

Per-PR files carry the full `body`; `_index.jsonl` snippets are truncated to
~120 chars. For clustering we want the full body, so this module reads the
per-PR files. Pure stdlib.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

HOME = Path.home()
CORPUS_DIR = HOME / ".claude/state/gh_corpus"
META_PATH = CORPUS_DIR / "_meta.json"

IDAN_GITHUB = "idanbeck"
# Mirror run.py's load_live_corpus_signal() filter: exclude bot/[fake idan]
# paste-backs so only genuine Idan utterances survive.
FAKE_IDAN_PREFIX = re.compile(r"\[fake idan\]", re.I)

# A genuine *review-bar* signal is a formal review (summary or inline comment),
# NOT a conversational issue-comment. The idanbeck account also posts PR-response
# / follow-up issue-comments ("Addressed the serialization-parity review item",
# "Review follow-up: …") which are the author answering review feedback, not Idan
# setting the bar. Clustering those inflates the durable bar with topic-noise, so
# `review_only=True` keeps just the formal review kinds.
REVIEW_KINDS = {"review-summary", "review-comment"}
# Belt-and-suspenders for any response that slips through mis-kinded as a review.
_RESPONSE_PREFIX = re.compile(
    r"^\s*(addressed|done[.! ]|fixed|updated per|resolved|review follow-?up\b|"
    r"per your review|as requested|good catch|ptal\b)", re.I)


def is_review(comment: CorpusComment) -> bool:
    """True iff this is a formal review (bar-setting), not a conversational
    issue-comment or a PR-response/follow-up post."""
    if comment.kind not in REVIEW_KINDS:
        return False
    if _RESPONSE_PREFIX.search(comment.body or ""):
        return False
    return True


@dataclass(frozen=True)
class CorpusComment:
    ts: str            # ISO-8601 string as stored (UTC, e.g. "2026-06-02T00:48:20Z")
    repo: str          # e.g. "Epoch-ML/zerg"
    pr: int
    kind: str          # review-summary | review-comment | issue-comment
    author: str
    body: str
    state: Optional[str] = None

    @property
    def ref(self) -> str:
        """`repo#PR` ref, mirroring run.py's formatting (`{repo}#{pr}`)."""
        return f"{self.repo}#{self.pr}"

    @property
    def date(self) -> str:
        """YYYY-MM-DD slice of the timestamp (for provenance)."""
        return (self.ts or "")[:10]

    def parsed_ts(self) -> Optional[dt.datetime]:
        return parse_iso_timestamp(self.ts)


def parse_iso_timestamp(raw: str | None) -> Optional[dt.datetime]:
    """Parse an ISO-8601 timestamp to an aware UTC datetime (or None)."""
    if not raw:
        return None
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def corpus_last_update(corpus_dir: Path = CORPUS_DIR) -> Optional[dt.datetime]:
    """Newest `last_pull_at` across all repos in _meta.json (UTC), or None."""
    meta_path = corpus_dir / "_meta.json"
    if not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text(errors="ignore"))
    except (OSError, json.JSONDecodeError):
        return None
    newest: Optional[dt.datetime] = None
    for repo_meta in meta.values():
        if not isinstance(repo_meta, dict):
            continue
        parsed = parse_iso_timestamp(repo_meta.get("last_pull_at"))
        if parsed and (newest is None or parsed > newest):
            newest = parsed
    return newest


def iter_corpus_comments(
    corpus_dir: Path = CORPUS_DIR,
) -> Iterator[CorpusComment]:
    """Yield every comment from the per-PR jsonl files (full bodies)."""
    if not corpus_dir.exists():
        return
    for pr_file in sorted(corpus_dir.glob("*/pr-*.jsonl")):
        # <repo__slug>/pr-N.jsonl  →  repo = "owner/name"
        repo = pr_file.parent.name.replace("__", "/")
        try:
            text = pr_file.read_text(errors="ignore")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            pr = r.get("pr")
            try:
                pr_int = int(pr)
            except (TypeError, ValueError):
                continue
            yield CorpusComment(
                ts=r.get("ts") or "",
                repo=repo,
                pr=pr_int,
                kind=r.get("kind") or "",
                author=r.get("author") or "",
                body=r.get("body") or "",
                state=r.get("state"),
            )


def is_real_idan(comment: CorpusComment) -> bool:
    """True iff this is a genuine Idan utterance (author idanbeck, NOT a
    `[fake idan]` paste-back). Mirrors run.py's filter."""
    if comment.author != IDAN_GITHUB:
        return False
    if FAKE_IDAN_PREFIX.search(comment.body or ""):
        return False
    return True


def load_real_idan_comments(
    *,
    cutoff: dt.datetime,
    window_days: int,
    corpus_dir: Path = CORPUS_DIR,
    require_body: bool = True,
    review_only: bool = False,
) -> list[CorpusComment]:
    """Real-Idan comments whose ts is within (cutoff - window_days, cutoff].

    `cutoff` is a single pinned UTC datetime supplied by the caller so counts
    are reproducible despite the live ~15-min corpus refresh. Comments are
    returned sorted oldest→newest.

    `review_only=True` restricts to formal review kinds (`is_review`), excluding
    conversational issue-comments and PR-response/follow-up posts — the clean
    signal for the durable review-bar (see REVIEW_KINDS rationale above).
    """
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=dt.timezone.utc)
    start = cutoff - dt.timedelta(days=window_days)
    out: list[CorpusComment] = []
    for c in iter_corpus_comments(corpus_dir):
        if not is_real_idan(c):
            continue
        if review_only and not is_review(c):
            continue
        if require_body and not (c.body or "").strip():
            continue
        ts = c.parsed_ts()
        if ts is None or ts <= start or ts > cutoff:
            continue
        out.append(c)
    out.sort(key=lambda c: c.ts)
    return out
