"""Tests for aitr_exec — pick+execute+actuals, and the dormant cross-provider gate.

No network, no real model calls: _pick is monkeypatched and the anthropic executor
is a stub. The OpenRouter path is exercised only for its gating logic.
"""
import json
from pathlib import Path

import pytest

import aitr_exec
from aitr_exec import CrossProviderUnavailable, ExecResult, complete


@pytest.fixture
def anthropic_pick(monkeypatch):
    monkeypatch.setattr(aitr_exec, "_pick", lambda sig: {
        "decision_id": "aitr-test-anth",
        "model": "anthropic__claude-haiku-4-5",
        "provider": "anthropic",
    })


@pytest.fixture
def deepseek_pick(monkeypatch):
    monkeypatch.setattr(aitr_exec, "_pick", lambda sig: {
        "decision_id": "aitr-test-ds",
        "model": "deepseek__deepseek-v4-flash",
        "provider": "deepseek",
    })


@pytest.fixture
def actuals_to_tmp(monkeypatch, tmp_path):
    log = tmp_path / "actuals.log"
    monkeypatch.setattr(aitr_exec, "ACTUALS_LOG", log)
    return log


class TestAnthropicExecution:
    def test_runs_executor_and_logs_actuals(self, anthropic_pick, actuals_to_tmp):
        calls = []
        def fake_exec(model, prompt, system, max_tokens):
            calls.append((model, prompt, system, max_tokens))
            return ("hello world", 1200, 350)

        res = complete(
            "summarize this", task_kind="summarize", caller="test",
            quality_floor="cheap-ok", anthropic_executor=fake_exec, max_tokens=500,
        )
        assert isinstance(res, ExecResult)
        assert res.text == "hello world"
        assert res.model == "anthropic__claude-haiku-4-5"
        assert res.input_tokens == 1200 and res.output_tokens == 350
        # claude API name (not the aitr id) reaches the executor
        assert calls[0][0] == "claude-haiku-4-5"

        # actuals row written with the real token counts
        rows = [json.loads(l) for l in actuals_to_tmp.read_text().splitlines() if l.strip()]
        assert len(rows) == 1
        assert rows[0]["decision_id"] == "aitr-test-anth"
        assert rows[0]["input_tokens"] == 1200
        assert rows[0]["output_tokens"] == 350

    def test_anthropic_requires_executor(self, anthropic_pick, actuals_to_tmp):
        with pytest.raises(ValueError, match="anthropic_executor is required"):
            complete("x", task_kind="summarize", caller="test")


class TestCrossProviderGate:
    def test_non_anthropic_without_key_or_slug_raises(self, deepseek_pick, actuals_to_tmp, monkeypatch):
        monkeypatch.setattr(aitr_exec, "resolve_openrouter_key", lambda: None)
        monkeypatch.setattr(aitr_exec, "openrouter_slug", lambda mid: None)
        with pytest.raises(CrossProviderUnavailable):
            complete("x", task_kind="summarize", caller="test",
                     anthropic_executor=lambda *a: ("", 0, 0))

    def test_non_anthropic_with_key_but_no_slug_raises(self, deepseek_pick, actuals_to_tmp, monkeypatch):
        monkeypatch.setattr(aitr_exec, "resolve_openrouter_key", lambda: "sk-test")
        monkeypatch.setattr(aitr_exec, "openrouter_slug", lambda mid: None)
        with pytest.raises(CrossProviderUnavailable, match="no slug"):
            complete("x", task_kind="summarize", caller="test",
                     anthropic_executor=lambda *a: ("", 0, 0))

    def test_non_anthropic_executes_when_key_and_slug_present(self, deepseek_pick, actuals_to_tmp, monkeypatch):
        monkeypatch.setattr(aitr_exec, "resolve_openrouter_key", lambda: "sk-test")
        monkeypatch.setattr(aitr_exec, "openrouter_slug", lambda mid: "deepseek/deepseek-chat")
        monkeypatch.setattr(aitr_exec, "_openrouter_complete",
                            lambda slug, p, s, mt, key, **kw: ("ds answer", 900, 200))
        res = complete("x", task_kind="summarize", caller="test")
        assert res.text == "ds answer"
        assert res.provider == "deepseek"
        rows = [json.loads(l) for l in actuals_to_tmp.read_text().splitlines() if l.strip()]
        assert rows[0]["provider"] == "deepseek"


class TestActualCost:
    def test_uses_catalog_pricing(self):
        # haiku is $1/$5 per Mtok in the catalog
        cost = aitr_exec.actual_cost("anthropic__claude-haiku-4-5", 1_000_000, 0)
        assert cost == pytest.approx(1.0, rel=1e-3)

    def test_unknown_model_returns_none(self):
        assert aitr_exec.actual_cost("nonexistent__model", 1000, 1000) is None


class TestSlugMap:
    def test_empty_map_returns_none(self, monkeypatch, tmp_path):
        monkeypatch.setattr(aitr_exec, "SLUG_MAP_PATH", tmp_path / "absent.json")
        assert aitr_exec.openrouter_slug("deepseek__deepseek-v4-flash") is None

    def test_explicit_map_resolves(self, monkeypatch, tmp_path):
        p = tmp_path / "slugs.json"
        p.write_text(json.dumps({"deepseek__deepseek-v4-flash": "deepseek/deepseek-chat"}))
        monkeypatch.setattr(aitr_exec, "SLUG_MAP_PATH", p)
        assert aitr_exec.openrouter_slug("deepseek__deepseek-v4-flash") == "deepseek/deepseek-chat"
