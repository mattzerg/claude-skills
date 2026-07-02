"""Tests for the realized-quality reputation loop (quality.py + ranker integration)."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import quality
from quality import (
    REP_CAP,
    compute_reputation,
    load_quality_events,
    outcome_to_signed,
    record_quality,
)
from ranker import rank

NOW = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)


def _decisions(model="anthropic__claude-sonnet-4-6", caller="t", task_kind="draft-prose"):
    return {"d1": {"decision_id": "d1", "caller": caller, "model": model,
                   "signal": {"caller": caller, "task_kind": task_kind}}}


def _event(outcome=None, score=None, ts="2026-06-04T00:00:00+00:00", did="d1"):
    e = {"decision_id": did, "source": "test", "ts": ts}
    if outcome:
        e["outcome"] = outcome
    if score is not None:
        e["score"] = score
    return e


class TestOutcomeToSigned:
    def test_good_bad_mixed(self):
        assert outcome_to_signed({"outcome": "good"}) == 1.0
        assert outcome_to_signed({"outcome": "bad"}) == -1.0
        assert outcome_to_signed({"outcome": "mixed"}) == 0.0

    def test_explicit_score_overrides(self):
        assert outcome_to_signed({"outcome": "good", "score": 0.0}) == -1.0
        assert outcome_to_signed({"score": 0.5}) == 0.0
        assert outcome_to_signed({"score": 1.0}) == 1.0

    def test_unknown_is_neutral(self):
        assert outcome_to_signed({}) == 0.0


class TestComputeReputation:
    def test_good_event_positive_bounded(self):
        rep = compute_reputation(_decisions(), [_event("good")], now=NOW)
        key = ("t", "draft-prose", "anthropic__claude-sonnet-4-6")
        assert 0 < rep[key] <= REP_CAP

    def test_bad_event_negative(self):
        rep = compute_reputation(_decisions(), [_event("bad")], now=NOW)
        key = ("t", "draft-prose", "anthropic__claude-sonnet-4-6")
        assert -REP_CAP <= rep[key] < 0

    def test_clamped_at_cap(self):
        events = [_event("good") for _ in range(100)]
        rep = compute_reputation(_decisions(), events, now=NOW)
        key = ("t", "draft-prose", "anthropic__claude-sonnet-4-6")
        assert rep[key] == pytest.approx(REP_CAP)

    def test_good_and_bad_cancel(self):
        rep = compute_reputation(_decisions(), [_event("good"), _event("bad")], now=NOW)
        key = ("t", "draft-prose", "anthropic__claude-sonnet-4-6")
        assert rep[key] == pytest.approx(0.0, abs=1e-9)

    def test_old_event_decayed_out(self):
        rep = compute_reputation(_decisions(), [_event("good", ts="2026-01-01T00:00:00+00:00")], now=NOW)
        assert rep == {}  # >90 days → dropped

    def test_event_without_matching_decision_skipped(self):
        rep = compute_reputation(_decisions(), [_event("good", did="nonexistent")], now=NOW)
        assert rep == {}


class TestRecordAndLoad:
    def test_record_appends_and_loads(self, tmp_path):
        log = tmp_path / "quality.log"
        record_quality("d1", "good", source="pr-gate", note="passed", log_path=log, now=NOW)
        record_quality("d2", "bad", source="fakeidan", score=0.2, log_path=log, now=NOW)
        events = load_quality_events(log)
        assert len(events) == 2
        assert events[0]["decision_id"] == "d1" and events[0]["outcome"] == "good"
        assert events[1]["score"] == 0.2


class TestRankerIntegration:
    """Reputation nudges composite but stays below penalty magnitude."""

    def _catalog(self):
        return {"models": [
            {"id": "anthropic__claude-sonnet-4-6", "provider": "anthropic", "model_class": "sonnet",
             "status": "ga", "context_window": 200000, "modalities": ["text"],
             "pricing": {"input_per_mtok": 3, "output_per_mtok": 15}, "tags": ["writing", "voice"]},
            {"id": "anthropic__claude-opus-4-8", "provider": "anthropic", "model_class": "opus",
             "status": "ga", "context_window": 200000, "modalities": ["text"],
             "pricing": {"input_per_mtok": 5, "output_per_mtok": 25}, "tags": ["writing", "voice"]},
        ]}

    def _rt(self):
        return {
            "composite_weights": {"capability": 0.5, "cost": 0.3, "latency": 0.2},
            "quality_floors": {"cheap-ok": 0.0, "medium": 0.5, "high-stakes": 0.75},
            "high_stakes_whitelist": ["opus"],
            "task_kinds": {"draft-prose": {"preferred_tags": ["writing", "voice"],
                                           "min_context": 1000, "latency_class": "medium"}},
        }

    def test_positive_reputation_lifts_score(self):
        sig = {"task_kind": "draft-prose", "caller": "t", "quality_floor": "cheap-ok",
               "artifact_size_tokens": 2000}
        base = rank(sig, self._catalog(), self._rt())
        rep = {("t", "draft-prose", "anthropic__claude-sonnet-4-6"): 0.15}
        lifted = rank(sig, self._catalog(), self._rt(), reputation=rep)
        base_sonnet = next(c.score for c in base if c.model_class == "sonnet")
        lifted_sonnet = next(c.score for c in lifted if c.model_class == "sonnet")
        assert lifted_sonnet > base_sonnet

    def test_reputation_appears_in_reason(self):
        sig = {"task_kind": "draft-prose", "caller": "t", "quality_floor": "cheap-ok",
               "artifact_size_tokens": 2000}
        rep = {("t", "draft-prose", "anthropic__claude-sonnet-4-6"): 0.12}
        out = rank(sig, self._catalog(), self._rt(), reputation=rep)
        sonnet = next(c for c in out if c.model_class == "sonnet")
        assert "quality reputation" in sonnet.reason

    def test_none_reputation_is_noop(self):
        sig = {"task_kind": "draft-prose", "caller": "t", "quality_floor": "cheap-ok",
               "artifact_size_tokens": 2000}
        a = rank(sig, self._catalog(), self._rt())
        b = rank(sig, self._catalog(), self._rt(), reputation=None)
        assert [c.score for c in a] == [c.score for c in b]


class TestLoadReputationSafety:
    def test_missing_logs_return_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(quality, "DEFAULT_DECISIONS_LOG", tmp_path / "none.log")
        assert quality.load_reputation(quality_log=tmp_path / "none2.log") == {}


class TestReputationCli:
    def test_reputation_verb_outputs_sorted_priors(self, tmp_path, monkeypatch, capsys):
        import pick
        decisions = tmp_path / "decisions.log"
        decisions.write_text(json.dumps({
            "decision_id": "d1", "caller": "competitive-review-skill",
            "model": "anthropic__claude-opus-4-8",
            "signal": {"caller": "competitive-review-skill", "task_kind": "research"},
        }) + "\n")
        qlog = tmp_path / "quality.log"
        monkeypatch.setattr(quality, "DEFAULT_DECISIONS_LOG", decisions)
        monkeypatch.setattr(quality, "DEFAULT_QUALITY_LOG", qlog)
        quality.record_quality("d1", "good", source="competitive-review-skill",
                               log_path=qlog, now=NOW)
        # pick._cmd_reputation calls load_reputation() with defaults → patched above
        monkeypatch.setattr(pick, "load_reputation",
                            lambda: quality.load_reputation(decisions_log=decisions, quality_log=qlog, now=NOW))
        rc = pick._cmd_reputation(object())
        out = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert out["count"] == 1
        assert out["reputation"][0]["caller"] == "competitive-review-skill"
        assert out["reputation"][0]["reputation"] > 0


class TestReputationInReport:
    def test_report_shows_learned_priors(self, tmp_path, monkeypatch):
        from datetime import datetime, timezone
        from weekly_report import build_report
        decisions = tmp_path / "decisions.log"
        decisions.write_text(json.dumps({
            "decision_id": "d1", "caller": "competitive-review-skill",
            "model": "anthropic__claude-opus-4-8", "capability": 0.8,
            "catalog_source": "live", "ts": "2026-06-04T00:00:00+00:00",
            "signal": {"caller": "competitive-review-skill", "task_kind": "research"},
        }) + "\n")
        qlog = tmp_path / "quality.log"
        monkeypatch.setattr(quality, "DEFAULT_DECISIONS_LOG", decisions)
        monkeypatch.setattr(quality, "DEFAULT_QUALITY_LOG", qlog)
        quality.record_quality("d1", "good", source="competitive-review-skill",
                               log_path=qlog, now=NOW)
        report = build_report(decisions_log=decisions, feedback_dirs=[tmp_path / "nf"],
                              days=365, now=datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc))
        assert "Learned reputation priors" in report
        assert "competitive-review-skill / research" in report
