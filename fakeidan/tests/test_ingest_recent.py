#!/usr/bin/env python3
"""Hermetic tests for fakeidan/ingest_recent.

Feeds a synthetic gh_corpus fixture + a synthetic durable bar and asserts:
  - real-Idan comments are picked up; fake-idan ([fake idan]) and other authors excluded
  - comments cluster into the right safety classes
  - the auto-region is regenerated strictly between the markers
  - the hand-curated region (above BEGIN) is byte-identical before/after
  - provenance (repo#PR, date, idanbeck) is present in exemplars
  - idempotent + reproducible: same corpus + same cutoff → identical output
  - graceful degradation when there's too little signal

Pure stdlib + pytest. No network, no real corpus, no `gh` calls.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR))

import ingest_recent as ir  # noqa: E402
from corpus_reader import load_real_idan_comments  # noqa: E402

CUTOFF = dt.datetime(2026, 6, 9, 12, 0, 0, tzinfo=dt.timezone.utc)


def _write_pr(corpus_dir: Path, repo: str, pr: int, comments: list[dict]) -> None:
    d = corpus_dir / repo.replace("/", "__")
    d.mkdir(parents=True, exist_ok=True)
    lines = []
    for c in comments:
        rec = {
            "pr": pr,
            "kind": c.get("kind", "review-summary"),
            "author": c["author"],
            "ts": c["ts"],
            "body": c["body"],
            "state": c.get("state"),
        }
        lines.append(json.dumps(rec, ensure_ascii=False))
    (d / f"pr-{pr}.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_meta(corpus_dir: Path, last_pull: str) -> None:
    meta = {"Epoch-ML/zerg": {"prs": {}, "last_pull_at": last_pull}}
    (corpus_dir / "_meta.json").write_text(json.dumps(meta), encoding="utf-8")


@pytest.fixture
def corpus(tmp_path) -> Path:
    """Synthetic gh_corpus with a mix of real-Idan, fake-idan, and other-author."""
    cdir = tmp_path / "gh_corpus"
    cdir.mkdir()
    recent = "2026-06-02T00:48:20Z"   # in 30d window
    recent2 = "2026-05-26T00:45:26Z"  # in 30d window
    recent3 = "2026-05-20T01:00:59Z"  # in 30d window
    old = "2026-01-01T00:00:00Z"      # outside window

    _write_pr(cdir, "Epoch-ML/zerg", 393, [
        # real Idan, quota_money signal (runaway/max-turns/budget)
        {"author": "idanbeck", "ts": recent,
         "body": "Reviewed with runaway-prevention as the load-bearing concern. "
                 "The hard backstop holds: maxTurns defaults to 25, clamped to "
                 "MAX_MAX_TURNS=1000, so a goal with no --budget still terminates "
                 "by the turn cap. No unbounded path. Quota race closed."},
        # fake idan paste-back — MUST be excluded
        {"author": "idanbeck", "ts": recent, "kind": "issue-comment",
         "body": "## [fake idan] Review — webhook signing secret hmac auth login "
                 "session ssrf metadata 169.254 — all the keywords, but excluded."},
        # other author — MUST be excluded
        {"author": "mattzerg", "ts": recent, "kind": "issue-comment",
         "body": "Addressed the auth and webhook review items in abc123."},
    ])
    _write_pr(cdir, "Epoch-ML/zerg", 314, [
        # real Idan, auth + secrets signal
        {"author": "idanbeck", "ts": recent2, "kind": "issue-comment",
         "body": "Zergdesk owner bootstrap now reads env credentials; removed the "
                 "bundled auth.json credential seed. Added per-IP login rate "
                 "limiting and upgrade-time authorization for the WebSocket routes."},
    ])
    _write_pr(cdir, "Epoch-ML/zerg", 327, [
        # real Idan, ipc_mcp signal
        {"author": "idanbeck", "ts": recent3, "kind": "issue-comment",
         "body": "C2: ZTerm IPC sockets now chmod to 0600 immediately after bind. "
                 "Hardened the desktop IPC socket bridge."},
    ])
    _write_pr(cdir, "Epoch-ML/zerg", 999, [
        # real Idan, no safety signal → other_process
        {"author": "idanbeck", "ts": recent3, "kind": "review-summary",
         "body": "Great work — the response shape this round is exactly what makes "
                 "a re-review tractable. Ready to merge."},
        # old real Idan — outside the window, MUST be excluded
        {"author": "idanbeck", "ts": old, "kind": "review-summary",
         "body": "ancient auth webhook ssrf comment outside the window"},
    ])
    _write_meta(cdir, "2026-06-09T10:47:42Z")
    return cdir


HAND_CURATED = """\
---
name: Idan's PR review bar
type: feedback
---

# Idan's PR review bar — hand curated

1. Match the shape of the surrounding code.
2. Verify-then-parse ordering.
3. Constant-time comparison for secrets.

## Money-handling delta

Exceed sibling conventions on test coverage of gates.
"""


@pytest.fixture
def bar(tmp_path) -> Path:
    p = tmp_path / "feedback_idan_pr_review_bar.md"
    p.write_text(HAND_CURATED, encoding="utf-8")
    return p


def _run(corpus: Path, bar: Path, days: int = 30, cutoff=CUTOFF):
    comments = load_real_idan_comments(cutoff=cutoff, window_days=days, corpus_dir=corpus)
    region = ir.render_region(comments, cutoff=cutoff, window_days=days)
    existing = bar.read_text(encoding="utf-8")
    new_text = ir.splice_region(existing, region)
    bar.write_text(new_text, encoding="utf-8")
    return comments, region, new_text


# --------------------------------------------------------------------------- #


def test_real_idan_included_fake_and_others_excluded(corpus):
    comments = load_real_idan_comments(cutoff=CUTOFF, window_days=30, corpus_dir=corpus)
    bodies = "\n".join(c.body for c in comments)
    # 4 real-Idan, in-window comments (393, 314, 327, 999); old + fake + mattzerg dropped
    assert len(comments) == 4
    assert all(c.author == "idanbeck" for c in comments)
    assert "[fake idan]" not in bodies
    assert "Addressed the auth and webhook review items" not in bodies  # mattzerg
    assert "ancient auth webhook" not in bodies                          # outside window


def test_clusters_bucket_correctly(corpus):
    comments = load_real_idan_comments(cutoff=CUTOFF, window_days=30, corpus_dir=corpus)
    clusters = ir.build_clusters(comments)
    counts = clusters["counts"]
    assert counts.get("quota_money", 0) >= 1   # PR 393 runaway/maxTurns/budget
    assert counts.get("auth", 0) >= 1          # PR 314 bootstrap/authorization
    assert counts.get("secrets", 0) >= 1       # PR 314 credentials/rate-limit
    assert counts.get("ipc_mcp", 0) >= 1       # PR 327 IPC socket 0600
    assert counts.get("other_process", 0) >= 1  # PR 999 "ready to merge"


def test_classify_no_signal_goes_to_other():
    assert ir.classify("Ready to merge, great work.") == []


def test_region_regenerates_between_markers(corpus, bar):
    _comments, _region, text = _run(corpus, bar)
    assert ir.BEGIN_MARKER in text
    assert ir.END_MARKER in text
    assert text.index(ir.BEGIN_MARKER) < text.index(ir.END_MARKER)
    # marker block sits after the hand-curated content
    assert text.index("hand curated") < text.index(ir.BEGIN_MARKER)


def test_hand_curated_region_untouched(corpus, bar):
    before = bar.read_text(encoding="utf-8")
    head_before = before  # no markers yet → whole file is hand-curated
    _run(corpus, bar)
    after = bar.read_text(encoding="utf-8")
    head_after = after[: after.index(ir.BEGIN_MARKER)]
    # Everything up to the BEGIN marker must be byte-identical to the original.
    assert head_after.startswith(head_before.rstrip("\n"))
    # And no hand-curated line was mutated.
    for line in ("Verify-then-parse ordering.", "Money-handling delta",
                 "Constant-time comparison for secrets."):
        assert line in head_after


def test_provenance_present(corpus, bar):
    _comments, region, _text = _run(corpus, bar)
    # ref + date + author triple on at least one exemplar
    assert "Epoch-ML/zerg#393" in region
    assert "2026-06-02" in region
    assert "idanbeck)" in region


def test_freshness_header_present(corpus, bar):
    _comments, region, _text = _run(corpus, bar)
    assert "**Freshness:**" in region
    assert "cutoff `2026-06-09T12:00:00Z`" in region
    assert "30d" in region


def test_idempotent_and_reproducible(corpus, bar):
    _c1, _r1, text1 = _run(corpus, bar)
    # Re-run on the already-spliced file with same corpus + cutoff.
    _c2, _r2, text2 = _run(corpus, bar)
    assert text1 == text2, "second run must be byte-identical (idempotent)"
    # And re-deriving the region from scratch is reproducible.
    comments = load_real_idan_comments(cutoff=CUTOFF, window_days=30, corpus_dir=corpus)
    region_a = ir.render_region(comments, cutoff=CUTOFF, window_days=30)
    region_b = ir.render_region(comments, cutoff=CUTOFF, window_days=30)
    assert region_a == region_b


def test_splice_only_replaces_region(corpus, bar):
    _c1, _r1, text1 = _run(corpus, bar)
    head1 = text1[: text1.index(ir.BEGIN_MARKER)]
    _c2, _r2, text2 = _run(corpus, bar)
    head2 = text2[: text2.index(ir.BEGIN_MARKER)]
    assert head1 == head2  # hand-curated head stable across regenerations


def test_graceful_degradation_low_signal(tmp_path):
    cdir = tmp_path / "gh_corpus"
    cdir.mkdir()
    _write_pr(cdir, "Epoch-ML/zerg", 1, [
        {"author": "idanbeck", "ts": "2026-06-02T00:00:00Z",
         "kind": "review-summary", "body": "lgtm"},
    ])
    _write_meta(cdir, "2026-06-09T10:00:00Z")
    comments = load_real_idan_comments(cutoff=CUTOFF, window_days=30, corpus_dir=cdir)
    assert len(comments) < ir.MIN_SIGNAL
    region = ir.render_region(comments, cutoff=CUTOFF, window_days=30)
    assert "Insufficient recent review signal" in region
    assert "**Freshness:**" in region          # header still present
    assert "Safety-class distribution" not in region  # no fabricated table


def test_review_only_excludes_responses_and_issue_comments(tmp_path):
    """The A2 fast-follow: review_only keeps formal reviews, drops the response /
    follow-up issue-comments the idanbeck account also posts."""
    from corpus_reader import is_review
    cdir = tmp_path / "gh_corpus"
    cdir.mkdir()
    _write_pr(cdir, "Epoch-ML/zerg", 50, [
        # formal reviews — KEPT under review_only
        {"author": "idanbeck", "ts": "2026-06-02T00:00:00Z", "kind": "review-summary",
         "body": "Auth on the upgrade path isn't enforced server-side. Block."},
        {"author": "idanbeck", "ts": "2026-06-01T00:00:00Z", "kind": "review-comment",
         "body": "Verify-then-parse: validate the webhook signature before decoding."},
        # response / follow-up issue-comments — DROPPED under review_only
        {"author": "idanbeck", "ts": "2026-06-03T00:00:00Z", "kind": "issue-comment",
         "body": "Addressed the serialization-parity review item in def456."},
        {"author": "idanbeck", "ts": "2026-06-03T01:00:00Z", "kind": "issue-comment",
         "body": "Review follow-up: rebased onto development, PTAL."},
    ])
    _write_meta(cdir, "2026-06-09T10:00:00Z")

    all_c = load_real_idan_comments(cutoff=CUTOFF, window_days=30, corpus_dir=cdir)
    reviews = load_real_idan_comments(cutoff=CUTOFF, window_days=30, corpus_dir=cdir, review_only=True)
    assert len(all_c) == 4                      # everything by idanbeck in-window
    assert len(reviews) == 2                    # only the two formal reviews
    bodies = "\n".join(c.body for c in reviews)
    assert "Addressed the serialization-parity" not in bodies   # response dropped
    assert "Review follow-up" not in bodies                     # follow-up dropped
    # is_review predicate: kind gate + response-prefix guard
    assert is_review(reviews[0]) and is_review(reviews[1])


def test_cutoff_pinned_from_meta(corpus):
    picked = ir.pick_cutoff(None, corpus)
    assert picked == dt.datetime(2026, 6, 9, 10, 47, 42, tzinfo=dt.timezone.utc)


def test_explicit_cutoff_overrides(corpus):
    picked = ir.pick_cutoff("2026-05-01T00:00:00Z", corpus)
    assert picked == dt.datetime(2026, 5, 1, 0, 0, 0, tzinfo=dt.timezone.utc)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
