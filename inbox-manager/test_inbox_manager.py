#!/usr/bin/env python3
"""Tests for inbox-manager. Run: python3 test_inbox_manager.py

Covers the risk-tier matrix, the decision-queue batching rule, and — most
importantly — a static guard that fails if the read-only guarantee is ever
broken by adding a mailbox-mutation call to the scanner.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
import inbox_scan as scan            # noqa: E402
import inbox_to_decisions as adapter  # noqa: E402


def _rec(**kw):
    base = dict(id="x", account="a@b.com", sender="S <s@x.com>", sender_email="s@x.com",
                sender_domain="x.com", subject="hi", snippet="", body="",
                days_since_last_message=1, last_from_matt=False, bucket="KEEP_INBOX",
                tier=None, scam={"label": "SAFE", "score": 0, "reasons": []},
                recommended_action="keep", risk_tier="low", autonomy_verdict="auto",
                rationale="", status="observed", ts="")
    base.update(kw)
    return base


def test_derive_risk_matrix():
    d = scan.derive
    # scam overrides bucket entirely
    assert d("KILL", "PHISH", None) == ("review_scam", "high", "needs_matt")
    assert d("HUMAN_IN", "SUSPICIOUS", "A") == ("review_scam", "medium", "needs_matt")
    # buckets
    assert d("HUMAN_IN", "SAFE", "A") == ("draft_reply", "medium", "auto")
    assert d("EXCLUDED", "SAFE", None) == ("none", "low", "never")
    assert d("KILL", "SAFE", None) == ("archive", "medium", "needs_matt")
    assert d("RECEIPT", "SAFE", None) == ("archive", "medium", "needs_matt")
    assert d("PROJECT", "SAFE", None) == ("surface_action", "medium", "needs_matt")
    assert d("DEAL", "SAFE", None) == ("surface_deal", "low", "auto")
    assert d("MINE_OUT", "SAFE", None) == ("follow_up", "low", "auto")
    assert d("KEEP_INBOX", "SAFE", None) == ("keep", "low", "auto")


def test_humans_never_auto_archive():
    # A human bucket must never resolve to an archive action, at any tier.
    for tier in ("A", "B", "C"):
        action, _, verdict = scan.derive("HUMAN_IN", "SAFE", tier)
        assert action != "archive"
        assert verdict != "never"  # excluded is 'never'; humans are actionable


def test_bulk_archives_collapse_to_one_card():
    recs = [_rec(id=str(i), bucket="KILL") for i in range(20)] + [_rec(id="r", bucket="RECEIPT")]
    cards = adapter.build_inbox_cards(recs)
    batch = [c for c in cards if c["autonomy_class"] == "inbox_archive_batch"]
    assert len(batch) == 1, "bulk cleanup must be ONE card, not N"
    assert batch[0]["raw"]["count"] == 21
    assert all(c["autonomy_class"] != "inbox_archive" for c in cards)


def test_human_and_scam_cards():
    recs = [_rec(id="h", bucket="HUMAN_IN", tier="A"),
            _rec(id="s", bucket="KEEP_INBOX",
                 scam={"label": "PHISH", "score": 9, "reasons": ["x"]})]
    cards = adapter.build_inbox_cards(recs)
    reply = next(c for c in cards if c["autonomy_class"] == "inbox_reply")
    assert reply["priority"] == 90  # tier A
    assert "draft reply" in reply["choices"]
    scamc = next(c for c in cards if c["autonomy_class"] == "inbox_scam")
    assert scamc["priority"] == 85


def test_spotcheck_sample_size():
    recs = [_rec(id=str(i), bucket=b) for i, b in
            enumerate(["KILL", "HUMAN_IN", "DEAL", "KEEP_INBOX", "RECEIPT", "PROJECT"])]
    assert len(scan.spot_check_sample(recs, 5)) == 5
    assert len(scan.spot_check_sample(recs[:2], 5)) == 2  # fewer than n available


def test_read_only_guarantee():
    """Regression guard: the scanner must contain NO mailbox-mutation call."""
    src = (HERE / "inbox_scan.py").read_text()
    for bad in ("mark_done(", ".send(", "--apply", "label_message", "unarchive(",
                "mark-done", "create_draft("):
        assert bad not in src, f"READ-ONLY VIOLATION: found `{bad}` in inbox_scan.py"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        t()
        print(f"  ✓ {t.__name__}")
        passed += 1
    print(f"\n{passed}/{len(tests)} passed")
