"""Tests for the feedback-driven penalty system (penalties.py + ranker integration)."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from penalties import (
    PENALTY_CAP,
    PENALTY_PER_CORRECTION,
    compute_penalties,
    load_decisions,
    load_penalties,
    load_wrong_model_feedback,
)
from ranker import rank

NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=timezone.utc)

SNAPSHOT = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "snapshot" / "search.json").read_text()
)
ROUTING_TABLE = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "routing_table.json").read_text()
)


def make_decision(decision_id="aitr-20260601-120000-abc123", caller="fakematt-copyedit",
                  task_kind="prose-review", model="anthropic__claude-opus-4-8",
                  ts="2026-06-01T12:00:00+00:00"):
    return {
        "decision_id": decision_id,
        "caller": caller,
        "model": model,
        "ts": ts,
        "signal": {"task_kind": task_kind, "caller": caller},
    }


def make_feedback(decision_id="aitr-20260601-120000-abc123", when="2026-06-01T13:00:00",
                  bucket="wrong-model-picked"):
    return {
        "id": "2026-06-01-001",
        "when": when,
        "bucket": bucket,
        "feedback": "sonnet would have been fine for this",
        "aitr_decision_id": decision_id,
    }


class TestLoadDecisions:
    def test_loads_jsonl(self, tmp_path):
        log = tmp_path / "decisions.log"
        log.write_text(
            json.dumps(make_decision("aitr-1-a")) + "\n" +
            json.dumps(make_decision("aitr-2-b")) + "\n"
        )
        out = load_decisions(log)
        assert set(out.keys()) == {"aitr-1-a", "aitr-2-b"}

    def test_skips_malformed_lines(self, tmp_path):
        log = tmp_path / "decisions.log"
        log.write_text("not json\n" + json.dumps(make_decision("aitr-ok")) + "\n{broken\n")
        out = load_decisions(log)
        assert list(out.keys()) == ["aitr-ok"]

    def test_missing_file_returns_empty(self, tmp_path):
        assert load_decisions(tmp_path / "nope.log") == {}


class TestLoadFeedback:
    def test_filters_to_wrong_model_bucket(self, tmp_path):
        d = tmp_path / "feedback"
        d.mkdir()
        (d / "a.json").write_text(json.dumps(make_feedback(bucket="wrong-model-picked")))
        (d / "b.json").write_text(json.dumps(make_feedback(bucket="new-rule")))
        (d / "c.json").write_text("broken json")
        out = load_wrong_model_feedback([d])
        assert len(out) == 1
        assert out[0]["bucket"] == "wrong-model-picked"

    def test_missing_dir_returns_empty(self, tmp_path):
        assert load_wrong_model_feedback([tmp_path / "nope"]) == []


class TestComputePenalties:
    def test_single_correction(self):
        decisions = {"aitr-1": make_decision("aitr-1", ts="2026-06-01T12:00:00+00:00")}
        feedback = [make_feedback("aitr-1", when="2026-06-02T11:00:00")]
        out = compute_penalties(decisions, feedback, now=NOW)
        key = ("fakematt-copyedit", "prose-review", "anthropic__claude-opus-4-8")
        assert key in out
        # ~1 day old → decay factor ~ (1 - 1/60) ≈ 0.983
        assert out[key] == pytest.approx(PENALTY_PER_CORRECTION * (1 - (1 / 60)), abs=0.005)

    def test_cap_at_three_corrections(self):
        decisions = {"aitr-1": make_decision("aitr-1")}
        feedback = [
            make_feedback("aitr-1", when="2026-06-02T10:00:00"),
            make_feedback("aitr-1", when="2026-06-02T10:30:00"),
            make_feedback("aitr-1", when="2026-06-02T11:00:00"),
            make_feedback("aitr-1", when="2026-06-02T11:30:00"),
        ]
        out = compute_penalties(decisions, feedback, now=NOW)
        key = ("fakematt-copyedit", "prose-review", "anthropic__claude-opus-4-8")
        assert out[key] == PENALTY_CAP

    def test_old_corrections_fully_decayed(self):
        decisions = {"aitr-1": make_decision("aitr-1")}
        # 61 days old → outside decay window
        feedback = [make_feedback("aitr-1", when="2026-04-02T12:00:00")]
        out = compute_penalties(decisions, feedback, now=NOW)
        assert out == {}

    def test_decay_reduces_penalty(self):
        decisions = {"aitr-1": make_decision("aitr-1")}
        # 30 days old → half decayed
        feedback = [make_feedback("aitr-1", when="2026-05-03T12:00:00")]
        out = compute_penalties(decisions, feedback, now=NOW)
        key = ("fakematt-copyedit", "prose-review", "anthropic__claude-opus-4-8")
        assert out[key] == pytest.approx(PENALTY_PER_CORRECTION * 0.5, abs=0.01)

    def test_correction_without_decision_id_skipped(self):
        decisions = {"aitr-1": make_decision("aitr-1")}
        fb = make_feedback("aitr-1")
        fb["aitr_decision_id"] = None
        out = compute_penalties(decisions, [fb], now=NOW)
        assert out == {}

    def test_correction_with_unknown_decision_skipped(self):
        decisions = {"aitr-1": make_decision("aitr-1")}
        feedback = [make_feedback("aitr-UNKNOWN")]
        out = compute_penalties(decisions, feedback, now=NOW)
        assert out == {}


class TestLoadPenaltiesEndToEnd:
    def test_full_path(self, tmp_path):
        log = tmp_path / "decisions.log"
        log.write_text(json.dumps(make_decision("aitr-1")) + "\n")
        fb_dir = tmp_path / "feedback"
        fb_dir.mkdir()
        (fb_dir / "a.json").write_text(json.dumps(make_feedback("aitr-1", when="2026-06-02T11:00:00")))

        out = load_penalties(decisions_log=log, feedback_dirs=[fb_dir], now=NOW)
        assert len(out) == 1

    def test_never_raises_on_garbage(self, tmp_path):
        log = tmp_path / "decisions.log"
        log.write_text("complete garbage")
        out = load_penalties(decisions_log=log, feedback_dirs=[tmp_path], now=NOW)
        assert out == {}


class TestRankerWithPenalties:
    # code-review/medium/anthropic-only leaves multiple survivors (opus 4.7/4.8 +
    # sonnet all clear the 0.5 capability floor via the humaneval benchmark boost),
    # so penalty-driven re-ranking is observable. prose-review/medium leaves only
    # sonnet standing — nothing to flip to.
    CODE_REVIEW_SIG = {
        "task_kind": "code-review",
        "caller": "pr-gate",
        "artifact_size_tokens": 4000,
        "quality_floor": "medium",
        "provider_constraint": "anthropic-only",
    }

    def test_multiple_survivors_premise(self):
        """Sanity: the signal used by these tests has >1 candidate."""
        baseline = rank(self.CODE_REVIEW_SIG, SNAPSHOT, ROUTING_TABLE)
        assert len(baseline) >= 2

    def test_penalty_demotes_model(self):
        """A penalized model should rank lower than it would without the penalty."""
        baseline = rank(self.CODE_REVIEW_SIG, SNAPSHOT, ROUTING_TABLE)
        baseline_top = baseline[0].model

        # Penalize the baseline winner hard
        penalties = {("pr-gate", "code-review", baseline_top): -0.30}
        penalized = rank(self.CODE_REVIEW_SIG, SNAPSHOT, ROUTING_TABLE, penalties=penalties)

        assert penalized[0].model != baseline_top
        # The penalized model should mention the penalty in its reason
        penalized_entry = next((c for c in penalized if c.model == baseline_top), None)
        if penalized_entry:
            assert "feedback penalty" in penalized_entry.reason

    def test_penalty_only_applies_to_matching_caller(self):
        """Penalty keyed to a different caller must not affect this caller's ranking."""
        baseline = rank(self.CODE_REVIEW_SIG, SNAPSHOT, ROUTING_TABLE)
        penalties = {("OTHER-caller", "code-review", baseline[0].model): -0.30}
        out = rank(self.CODE_REVIEW_SIG, SNAPSHOT, ROUTING_TABLE, penalties=penalties)
        assert out[0].model == baseline[0].model
