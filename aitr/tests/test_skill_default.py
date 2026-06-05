"""Tests for skill_default — aitr-backed model defaulting for script skills."""
import json
import subprocess

import pytest

import skill_default
from skill_default import aitr_model_or, _to_claude_model_name


class FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def make_runner(returncode=0, stdout="", raise_exc=None, capture=None):
    def runner(cmd, **kwargs):
        if capture is not None:
            capture.append(cmd)
        if raise_exc:
            raise raise_exc
        return FakeProc(returncode=returncode, stdout=stdout)
    return runner


def pick_json(model="anthropic__claude-opus-4-8"):
    return json.dumps({
        "decision_id": "aitr-test-1",
        "model": model,
        "model_class": "opus",
        "provider": "anthropic",
        "reason": "test",
    })


class TestModelNameMapping:
    def test_anthropic_id_strips_prefix(self):
        assert _to_claude_model_name("anthropic__claude-opus-4-8") == "claude-opus-4-8"
        assert _to_claude_model_name("anthropic__claude-haiku-4-5") == "claude-haiku-4-5"

    def test_non_anthropic_returns_none(self):
        assert _to_claude_model_name("openai__gpt-5-5") is None
        assert _to_claude_model_name("google__gemini-3-1-pro") is None

    def test_bare_name_returns_none(self):
        assert _to_claude_model_name("claude-opus-4-8") is None


class TestAitrModelOr:
    def test_successful_pick(self):
        runner = make_runner(stdout=pick_json("anthropic__claude-sonnet-4-6"))
        out = aitr_model_or("claude-opus-4-7", task_kind="prose-review",
                            caller="test", runner=runner)
        assert out == "claude-sonnet-4-6"

    def test_signal_includes_anthropic_constraint(self):
        captured = []
        runner = make_runner(stdout=pick_json(), capture=captured)
        aitr_model_or("fallback", task_kind="prose-review", caller="fakematt-copyedit",
                      quality_floor="high-stakes", runner=runner)
        cmd = captured[0]
        assert "provider_constraint=anthropic-only" in cmd
        assert "task_kind=prose-review" in cmd
        assert "caller=fakematt-copyedit" in cmd
        assert "quality_floor=high-stakes" in cmd

    def test_billing_mode_defaults_flat_and_passes_through(self):
        captured = []
        runner = make_runner(stdout=pick_json(), capture=captured)
        aitr_model_or("fb", task_kind="classify", caller="t", runner=runner)
        assert "billing_mode=flat" in captured[0]

    def test_billing_mode_metered_passed(self):
        captured = []
        runner = make_runner(stdout=pick_json(), capture=captured)
        aitr_model_or("fb", task_kind="classify", caller="t",
                      billing_mode="metered", runner=runner)
        assert "billing_mode=metered" in captured[0]


class TestDetectBillingMode:
    def test_metered_when_api_key_set(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        assert skill_default.detect_billing_mode() == "metered"

    def test_flat_when_no_api_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert skill_default.detect_billing_mode() == "flat"

    def test_artifact_size_included_when_given(self):
        captured = []
        runner = make_runner(stdout=pick_json(), capture=captured)
        aitr_model_or("fallback", task_kind="prose-review", caller="test",
                      artifact_size_tokens=12000, runner=runner)
        assert "artifact_size_tokens=12000" in captured[0]

    def test_artifact_size_floor(self):
        captured = []
        runner = make_runner(stdout=pick_json(), capture=captured)
        aitr_model_or("fallback", task_kind="prose-review", caller="test",
                      artifact_size_tokens=5, runner=runner)
        assert "artifact_size_tokens=100" in captured[0]

    def test_modality_required_included_when_given(self):
        captured = []
        runner = make_runner(stdout=pick_json(), capture=captured)
        aitr_model_or("fallback", task_kind="prose-review", caller="fakematt-feedback",
                      modality_required="vision", runner=runner)
        assert "modality_required=vision" in captured[0]

    def test_modality_omitted_when_not_given(self):
        captured = []
        runner = make_runner(stdout=pick_json(), capture=captured)
        aitr_model_or("fallback", task_kind="prose-review", caller="test", runner=runner)
        assert not any("modality_required" in arg for arg in captured[0])

    def test_fallback_on_nonzero_exit(self):
        for code in (1, 2, 3):
            runner = make_runner(returncode=code)
            out = aitr_model_or("my-fallback", task_kind="prose-review",
                                caller="test", runner=runner)
            assert out == "my-fallback"

    def test_fallback_on_timeout(self):
        runner = make_runner(raise_exc=subprocess.TimeoutExpired(cmd="x", timeout=30))
        out = aitr_model_or("my-fallback", task_kind="prose-review",
                            caller="test", runner=runner)
        assert out == "my-fallback"

    def test_fallback_on_oserror(self):
        runner = make_runner(raise_exc=OSError("boom"))
        out = aitr_model_or("my-fallback", task_kind="prose-review",
                            caller="test", runner=runner)
        assert out == "my-fallback"

    def test_fallback_on_garbage_output(self):
        runner = make_runner(stdout="not json at all")
        out = aitr_model_or("my-fallback", task_kind="prose-review",
                            caller="test", runner=runner)
        assert out == "my-fallback"

    def test_fallback_on_non_anthropic_pick(self):
        # Shouldn't happen given the constraint, but defensive
        runner = make_runner(stdout=pick_json("openai__gpt-5-5"))
        out = aitr_model_or("my-fallback", task_kind="prose-review",
                            caller="test", runner=runner)
        assert out == "my-fallback"

    def test_fallback_when_aitr_missing(self, monkeypatch, tmp_path):
        monkeypatch.setattr(skill_default, "AITR_PICK", tmp_path / "missing.py")
        out = aitr_model_or("my-fallback", task_kind="prose-review", caller="test")
        assert out == "my-fallback"


class TestLiveIntegration:
    def test_real_offline_pick(self):
        """One real call against the bundled snapshot. Validates the full loop."""
        if not skill_default.AITR_PICK.exists():
            pytest.skip("aitr not installed")

        def offline_runner(cmd, **kwargs):
            return subprocess.run([*cmd, "--offline"], **kwargs)

        out = aitr_model_or("claude-opus-4-7", task_kind="prose-review",
                            caller="test-live", quality_floor="high-stakes",
                            runner=offline_runner, timeout=60)
        # Bundled snapshot should give an anthropic model for prose-review high-stakes
        assert out.startswith("claude-")
