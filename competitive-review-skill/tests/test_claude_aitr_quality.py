import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path.home() / ".claude" / "skills" / "competitive-review-skill" / "lib" / "claude.py"


@pytest.fixture()
def claude_module():
    spec = importlib.util.spec_from_file_location("competitive_review_claude_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_routed_call_records_good_outcome(monkeypatch, claude_module):
    events = []

    monkeypatch.setattr(claude_module, "_routed_default_choice", lambda: ("claude-sonnet-4-6", "aitr-decision-1"))
    monkeypatch.setattr(claude_module, "_sdk_available", lambda: False)
    monkeypatch.setattr(claude_module, "_call_cli", lambda *args, **kwargs: "usable output")
    monkeypatch.setattr(claude_module, "_record_outcome", lambda *args: events.append(args))

    assert claude_module.call_claude("prompt", timeout=30) == "usable output"

    assert events == [("aitr-decision-1", "good", "completed")]


def test_routed_empty_output_records_bad_outcome(monkeypatch, claude_module):
    events = []

    monkeypatch.setattr(claude_module, "_routed_default_choice", lambda: ("claude-sonnet-4-6", "aitr-decision-2"))
    monkeypatch.setattr(claude_module, "_sdk_available", lambda: False)
    monkeypatch.setattr(claude_module, "_call_cli", lambda *args, **kwargs: "")
    monkeypatch.setattr(claude_module, "_record_outcome", lambda *args: events.append(args))

    assert claude_module.call_claude("prompt", timeout=30) == ""

    assert events == [("aitr-decision-2", "bad", "empty output")]


def test_explicit_model_does_not_record_against_cached_routed_decision(monkeypatch, claude_module):
    events = []

    monkeypatch.setattr(claude_module, "_routed_default_choice", lambda: ("claude-sonnet-4-6", "old-routed-decision"))
    monkeypatch.setattr(claude_module, "_sdk_available", lambda: False)
    monkeypatch.setattr(claude_module, "_call_cli", lambda *args, **kwargs: "explicit output")
    monkeypatch.setattr(claude_module, "_record_outcome", lambda *args: events.append(args))

    assert claude_module.call_claude("prompt", model="claude-opus-4-8", timeout=30) == "explicit output"

    assert events == []


def test_routed_calls_scope_outcomes_to_each_decision(monkeypatch, claude_module):
    events = []
    picks = iter([
        ("claude-sonnet-4-6", "aitr-decision-1"),
        ("claude-sonnet-4-6", "aitr-decision-2"),
    ])

    monkeypatch.setattr(claude_module, "_routed_default_choice", lambda: next(picks))
    monkeypatch.setattr(claude_module, "_sdk_available", lambda: False)
    monkeypatch.setattr(claude_module, "_call_cli", lambda *args, **kwargs: "usable output")
    monkeypatch.setattr(claude_module, "_record_outcome", lambda *args: events.append(args))

    assert claude_module.call_claude("first", timeout=30) == "usable output"
    assert claude_module.call_claude("second", timeout=30) == "usable output"

    assert events == [
        ("aitr-decision-1", "good", "completed"),
        ("aitr-decision-2", "good", "completed"),
    ]


def test_routed_default_model_falls_back_when_aitr_raises(monkeypatch, claude_module, capsys):
    def broken_import(name, *args, **kwargs):
        if name == "skill_default":
            raise RuntimeError("catalog parse failed")
        return real_import(name, *args, **kwargs)

    real_import = __import__
    monkeypatch.setattr("builtins.__import__", broken_import)

    assert claude_module._routed_default_model() == claude_module.DEFAULT_MODEL
    assert "falling back" in capsys.readouterr().err
