"""Tests for the Signal schema and parsing."""
import pytest

from task_signal import (
    Signal,
    SignalError,
    parse_kv_args,
    signal_from_json,
    signal_from_kv,
)


class TestSignalDataclass:
    def test_minimal_signal(self):
        s = Signal(task_kind="code-review", caller="pr-gate")
        assert s.task_kind == "code-review"
        assert s.caller == "pr-gate"
        assert s.artifact_size_tokens == 4000
        assert s.quality_floor == "medium"
        assert s.provider_constraint == "any"
        assert s.modality_required is None

    def test_full_signal(self):
        s = Signal(
            task_kind="refute",
            caller="cross-model-check",
            artifact_size_tokens=8000,
            latency_budget_seconds=30,
            cost_budget_usd=0.50,
            quality_floor="high-stakes",
            provider_constraint="openai-only",
            modality_required="vision",
            notes="context",
        )
        assert s.cost_budget_usd == 0.50
        assert s.modality_required == "vision"

    def test_missing_task_kind(self):
        with pytest.raises(SignalError, match="task_kind"):
            Signal(task_kind="", caller="foo")

    def test_unknown_task_kind(self):
        with pytest.raises(SignalError, match="unknown task_kind"):
            Signal(task_kind="not-a-real-kind", caller="foo")

    def test_missing_caller(self):
        with pytest.raises(SignalError, match="caller"):
            Signal(task_kind="code-review", caller="")

    def test_negative_artifact_size(self):
        with pytest.raises(SignalError, match="artifact_size_tokens"):
            Signal(task_kind="code-review", caller="x", artifact_size_tokens=-1)

    def test_zero_latency_budget(self):
        with pytest.raises(SignalError, match="latency_budget_seconds"):
            Signal(task_kind="code-review", caller="x", latency_budget_seconds=0)

    def test_negative_cost_budget(self):
        with pytest.raises(SignalError, match="cost_budget_usd"):
            Signal(task_kind="code-review", caller="x", cost_budget_usd=-1)

    def test_unknown_quality_floor(self):
        with pytest.raises(SignalError, match="quality_floor"):
            Signal(task_kind="code-review", caller="x", quality_floor="ultra")

    def test_unknown_provider_constraint(self):
        with pytest.raises(SignalError, match="provider_constraint"):
            Signal(task_kind="code-review", caller="x", provider_constraint="aws-only")

    def test_unknown_modality(self):
        with pytest.raises(SignalError, match="modality_required"):
            Signal(task_kind="code-review", caller="x", modality_required="smell")

    def test_to_dict_drops_nones(self):
        s = Signal(task_kind="code-review", caller="x")
        d = s.to_dict()
        assert d == {
            "task_kind": "code-review",
            "caller": "x",
            "artifact_size_tokens": 4000,
            "quality_floor": "medium",
            "provider_constraint": "any",
        }


class TestParseKvArgs:
    def test_basic(self):
        assert parse_kv_args(["a=1", "b=hello"]) == {"a": "1", "b": "hello"}

    def test_empty_input(self):
        assert parse_kv_args([]) == {}

    def test_strips_whitespace(self):
        assert parse_kv_args([" a = 1 ", " b=hello "]) == {"a": "1", "b": "hello"}

    def test_rejects_missing_equals(self):
        with pytest.raises(SignalError, match="key=value"):
            parse_kv_args(["just-a-key"])

    def test_rejects_empty_key(self):
        with pytest.raises(SignalError, match="empty key"):
            parse_kv_args(["=value"])

    def test_value_can_contain_equals(self):
        assert parse_kv_args(["url=https://x.com/y?a=1"]) == {"url": "https://x.com/y?a=1"}


class TestSignalFromKv:
    def test_minimal(self):
        s = signal_from_kv({"task_kind": "code-review", "caller": "pr-gate"})
        assert s.artifact_size_tokens == 4000
        assert s.quality_floor == "medium"

    def test_coerces_ints_and_floats(self):
        s = signal_from_kv({
            "task_kind": "code-review",
            "caller": "pr-gate",
            "artifact_size_tokens": "12000",
            "latency_budget_seconds": "30",
            "cost_budget_usd": "0.25",
        })
        assert s.artifact_size_tokens == 12000
        assert s.latency_budget_seconds == 30
        assert s.cost_budget_usd == 0.25

    def test_rejects_unknown_keys(self):
        with pytest.raises(SignalError, match="unknown signal fields"):
            signal_from_kv({"task_kind": "code-review", "caller": "x", "made_up": "1"})

    def test_rejects_non_int_artifact_size(self):
        with pytest.raises(SignalError, match="artifact_size_tokens.*integer"):
            signal_from_kv({
                "task_kind": "code-review",
                "caller": "x",
                "artifact_size_tokens": "not-a-number",
            })

    def test_rejects_non_numeric_cost_budget(self):
        with pytest.raises(SignalError, match="cost_budget_usd.*number"):
            signal_from_kv({
                "task_kind": "code-review",
                "caller": "x",
                "cost_budget_usd": "free",
            })

    def test_empty_optional_strings_become_none(self):
        s = signal_from_kv({
            "task_kind": "code-review",
            "caller": "x",
            "modality_required": "",
            "notes": "",
        })
        assert s.modality_required is None
        assert s.notes is None


class TestSignalFromJson:
    def test_basic(self):
        s = signal_from_json('{"task_kind":"code-review","caller":"pr-gate"}')
        assert s.task_kind == "code-review"

    def test_with_numerics(self):
        s = signal_from_json(
            '{"task_kind":"refute","caller":"cross-model-check",'
            '"artifact_size_tokens":12000,"cost_budget_usd":0.5,"latency_budget_seconds":30}'
        )
        assert s.artifact_size_tokens == 12000
        assert s.cost_budget_usd == 0.5
        assert s.latency_budget_seconds == 30

    def test_rejects_malformed_json(self):
        with pytest.raises(SignalError, match="invalid JSON"):
            signal_from_json("{not json")

    def test_rejects_non_object(self):
        with pytest.raises(SignalError, match="must be an object"):
            signal_from_json("[]")

    def test_rejects_missing_task_kind(self):
        with pytest.raises(SignalError, match="task_kind"):
            signal_from_json('{"caller":"x"}')

    def test_rejects_missing_caller(self):
        with pytest.raises(SignalError, match="caller"):
            signal_from_json('{"task_kind":"code-review"}')
