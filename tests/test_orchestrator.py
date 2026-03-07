"""Smoke tests for the prompt-orchestrator package."""

import os
import tempfile
import pytest

from orchestrator.analytics import AnalyticsHub
from orchestrator.router import PromptRouter
from orchestrator.core import ModuleResult, PromptOrchestrator


# ---------------------------------------------------------------------------
# AnalyticsHub
# ---------------------------------------------------------------------------

class TestAnalyticsHub:
    def test_instantiation(self, tmp_path):
        hub = AnalyticsHub(log_file=str(tmp_path / "analytics.jsonl"))
        assert hub is not None
        assert hub.session_data == []

    def test_log_creates_record(self, tmp_path):
        log_file = str(tmp_path / "analytics.jsonl")
        hub = AnalyticsHub(log_file=log_file)
        hub.log("test_module", {"success": True, "latency": 0.5})
        assert len(hub.session_data) == 1
        assert hub.session_data[0]["module"] == "test_module"
        assert os.path.exists(log_file)

    def test_get_performance_no_file(self, tmp_path):
        hub = AnalyticsHub(log_file=str(tmp_path / "nonexistent.jsonl"))
        result = hub.get_performance("missing_module")
        assert result == {}

    def test_get_performance_with_data(self, tmp_path):
        log_file = str(tmp_path / "analytics.jsonl")
        hub = AnalyticsHub(log_file=log_file)
        hub.log("mod_a", {"success": True, "latency": 1.0})
        hub.log("mod_a", {"success": False, "latency": 2.0})
        perf = hub.get_performance("mod_a")
        assert perf["total_runs"] == 2
        assert perf["success_count"] == 1
        assert perf["avg_latency"] == 1.5

    def test_get_all_stats_no_file(self, tmp_path):
        hub = AnalyticsHub(log_file=str(tmp_path / "nonexistent.jsonl"))
        assert hub.get_all_stats() == {}

    def test_get_all_stats_returns_module_keys(self, tmp_path):
        log_file = str(tmp_path / "analytics.jsonl")
        hub = AnalyticsHub(log_file=log_file)
        hub.log("alpha", {"success": True, "latency": 0.1})
        hub.log("beta", {"success": True, "latency": 0.2})
        stats = hub.get_all_stats()
        assert "alpha" in stats
        assert "beta" in stats


# ---------------------------------------------------------------------------
# PromptRouter
# ---------------------------------------------------------------------------

class TestPromptRouter:
    def test_instantiation(self):
        router = PromptRouter()
        assert router is not None
        assert isinstance(router.chain_patterns, dict)

    def test_select_chain_returns_list(self):
        router = PromptRouter()
        chain = router.select_chain("Please analyze the data")
        assert isinstance(chain, list)
        assert len(chain) > 0

    def test_select_chain_analysis_keywords(self):
        router = PromptRouter()
        chain = router.select_chain("Please analyze and evaluate this report")
        assert chain == router.chain_patterns["analysis"]

    def test_select_chain_creative_keywords(self):
        router = PromptRouter()
        chain = router.select_chain("Create and design a new feature")
        assert chain == router.chain_patterns["creative"]

    def test_select_chain_validation_keywords(self):
        router = PromptRouter()
        chain = router.select_chain("verify and validate the output")
        assert chain == router.chain_patterns["validation"]

    def test_select_chain_defaults_to_simple(self):
        router = PromptRouter()
        chain = router.select_chain("hello world")
        assert chain == router.chain_patterns["simple"]

    def test_select_chain_context_override(self):
        router = PromptRouter()
        custom = ["cot", "bias"]
        chain = router.select_chain("anything", context={"chain": custom})
        assert chain == custom

    def test_register_chain(self):
        router = PromptRouter()
        router.register_chain("custom", ["mod_a", "mod_b"])
        assert router.chain_patterns["custom"] == ["mod_a", "mod_b"]

    def test_register_keywords(self):
        router = PromptRouter()
        router.register_keywords("analysis", ["inspect", "probe"])
        assert "inspect" in router.keywords["analysis"]
        assert "probe" in router.keywords["analysis"]

    def test_register_keywords_new_chain_type(self):
        router = PromptRouter()
        router.register_keywords("custom_type", ["foo", "bar"])
        assert router.keywords["custom_type"] == ["foo", "bar"]


# ---------------------------------------------------------------------------
# ModuleResult
# ---------------------------------------------------------------------------

class TestModuleResult:
    def test_instantiation(self):
        result = ModuleResult(output="hello", passed=True, metrics={"latency": 0.1})
        assert result.output == "hello"
        assert result.passed is True
        assert result.metrics == {"latency": 0.1}
        assert result.timestamp is not None

    def test_failed_result(self):
        result = ModuleResult(output="error msg", passed=False, metrics={})
        assert result.passed is False


# ---------------------------------------------------------------------------
# PromptOrchestrator
# ---------------------------------------------------------------------------

class MockLLM:
    """Minimal offline LLM stub."""
    def generate(self, prompt: str) -> str:
        return "mock response"


class MockModule:
    """Minimal offline module stub that always passes."""
    def run(self, llm, task, context):
        return ModuleResult(output=f"processed: {task}", passed=True, metrics={"success": True})


class TestPromptOrchestrator:
    def test_instantiation(self):
        orch = PromptOrchestrator(llm_client=MockLLM())
        assert orch is not None
        assert orch.modules == {}

    def test_register_module(self):
        orch = PromptOrchestrator(llm_client=MockLLM())
        mod = MockModule()
        orch.register_module("my_mod", mod)
        assert "my_mod" in orch.modules

    def test_execute_with_registered_module(self):
        orch = PromptOrchestrator(llm_client=MockLLM())
        orch.register_module("verification", MockModule())
        # No router set → uses default chain ["verification"]
        result = orch.execute("test task")
        assert isinstance(result, ModuleResult)
        assert result.passed is True

    def test_execute_missing_module_raises(self):
        orch = PromptOrchestrator(llm_client=MockLLM())
        with pytest.raises(ValueError, match="not registered"):
            orch.execute("test task")

    def test_execute_with_router(self):
        orch = PromptOrchestrator(llm_client=MockLLM())
        router = PromptRouter()
        orch.router = router
        orch.register_module("cot", MockModule())
        orch.register_module("verification", MockModule())
        # "hello" → simple chain: ["cot", "verification"]
        result = orch.execute("hello world")
        assert isinstance(result, ModuleResult)

    def test_execute_logs_to_analytics(self, tmp_path):
        log_file = str(tmp_path / "analytics.jsonl")
        orch = PromptOrchestrator(llm_client=MockLLM())
        orch.analytics = AnalyticsHub(log_file=log_file)
        orch.register_module("verification", MockModule())
        orch.execute("test task")
        assert os.path.exists(log_file)

    def test_execute_chain_failure_returns_failed_result(self):
        class FailingModule:
            def run(self, llm, task, context):
                return ModuleResult(output="bad", passed=False, metrics={})

        orch = PromptOrchestrator(llm_client=MockLLM())
        orch.register_module("verification", FailingModule())
        result = orch.execute("test task")
        assert result.passed is False
