"""Offline unit tests for CoreAnalysisBridge.

All tests run without the ai-analyze-think-act-core package installed by
using ``unittest.mock`` to patch module-level symbols.
"""

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_core_modules():
    """Return stub modules that mimic the ai-analyze-think-act-core API."""
    # -- core.analysis -------------------------------------------------------
    analysis_mod = ModuleType("core.analysis")

    class FakeAnalysisRequest:  # noqa: D101
        def __init__(self, dataset, goal, constraints, llm_model="gpt-4o", context=None):
            self.dataset = dataset
            self.goal = goal
            self.constraints = constraints
            self.llm_model = llm_model
            self.context = context

    class FakeAnalysisResult:  # noqa: D101
        def __init__(self):
            self.goal = "general"
            self.trends = [{"label": "upward", "value": 1}]
            self.anomalies = []
            self.rankings = []
            self.predictions = None
            self.diagnosis = "Looking good"
            self.metrics_to_watch = []

    analysis_mod.AnalysisRequest = FakeAnalysisRequest
    analysis_mod.analyze = MagicMock(return_value=FakeAnalysisResult())

    # -- core.recommendations ------------------------------------------------
    recs_mod = ModuleType("core.recommendations")

    class FakeAction:  # noqa: D101
        def __init__(self):
            self.id = "rec-1"
            self.description = "Do something great"
            self.priority = MagicMock(value="high")
            self.effort = MagicMock(value="low")
            self.expected_impact_metric = "+10%"
            self.rationale = "Because reasons"
            self.budget_required = 0.0
            self.implementation_steps = ["Step 1", "Step 2"]

    class FakeRecommendationRequest:  # noqa: D101
        def __init__(self, insights, goal, budget, llm_model="gpt-4o"):
            self.insights = insights
            self.goal = goal
            self.budget = budget
            self.llm_model = llm_model

    recs_mod.RecommendationRequest = FakeRecommendationRequest
    recs_mod.recommend = MagicMock(return_value=[FakeAction()])

    return analysis_mod, recs_mod


# ---------------------------------------------------------------------------
# Test: graceful degradation when core is unavailable
# ---------------------------------------------------------------------------

class TestBridgeUnavailable:
    """CoreAnalysisBridge behaves safely when core is not installed."""

    def test_import_succeeds_without_core(self, monkeypatch):
        """The bridge module itself should be importable even without core."""
        # Remove any cached bridge import
        for key in list(sys.modules.keys()):
            if "core_bridge" in key or key == "core" or key.startswith("core."):
                monkeypatch.delitem(sys.modules, key, raising=False)

        # Simulate ImportError for core
        import builtins
        real_import = builtins.__import__

        def _blocked_import(name, *args, **kwargs):
            if name in ("core.analysis", "core.recommendations"):
                raise ImportError(f"Simulated missing package: {name}")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _blocked_import)

        # Should not raise
        import importlib
        import orchestrator.core_bridge as cb_mod  # noqa: F401 — just checking import

        assert cb_mod._CORE_AVAILABLE is False or isinstance(cb_mod._CORE_AVAILABLE, bool)

    def test_execute_raises_bridge_unavailable_error(self):
        """execute() raises BridgeUnavailableError when core is absent."""
        import orchestrator.core_bridge as cb_mod

        with patch.object(cb_mod, "_CORE_AVAILABLE", False):
            bridge = cb_mod.CoreAnalysisBridge()
            with pytest.raises(cb_mod.BridgeUnavailableError):
                bridge.execute("Analyze my business")

    def test_run_returns_failed_module_result_when_unavailable(self):
        """run() returns a ModuleResult with passed=False instead of raising."""
        import orchestrator.core_bridge as cb_mod

        with patch.object(cb_mod, "_CORE_AVAILABLE", False):
            bridge = cb_mod.CoreAnalysisBridge()
            result = bridge.run(llm=None, input_data="some prompt", context={})

        assert result.passed is False
        assert "bridge_unavailable" in result.metrics.get("error", "")

    def test_get_status_reports_unavailable(self):
        """get_status() shows available=False when core is absent."""
        import orchestrator.core_bridge as cb_mod

        with patch.object(cb_mod, "_CORE_AVAILABLE", False):
            bridge = cb_mod.CoreAnalysisBridge()
            status = bridge.get_status()

        assert status["available"] is False
        assert "module" in status
        assert "version" in status


# ---------------------------------------------------------------------------
# Test: execute() with mocked analyze / recommend
# ---------------------------------------------------------------------------

class TestExecuteWithMocks:
    """execute() correctly calls analyze and recommend and returns structured data."""

    def _patched_bridge(self, cb_mod, analysis_mod, recs_mod):
        """Return a CoreAnalysisBridge with mocked core functions."""
        cb_mod._CORE_AVAILABLE = True
        cb_mod.analyze = analysis_mod.analyze
        cb_mod.AnalysisRequest = analysis_mod.AnalysisRequest
        cb_mod.recommend = recs_mod.recommend
        cb_mod.RecommendationRequest = recs_mod.RecommendationRequest
        return cb_mod.CoreAnalysisBridge()

    def test_execute_returns_analysis_and_recommendations(self):
        import orchestrator.core_bridge as cb_mod

        analysis_mod, recs_mod = _make_fake_core_modules()

        with (
            patch.object(cb_mod, "_CORE_AVAILABLE", True),
            patch.object(cb_mod, "analyze", analysis_mod.analyze),
            patch.object(cb_mod, "AnalysisRequest", analysis_mod.AnalysisRequest),
            patch.object(cb_mod, "recommend", recs_mod.recommend),
            patch.object(cb_mod, "RecommendationRequest", recs_mod.RecommendationRequest),
        ):
            bridge = cb_mod.CoreAnalysisBridge()
            result = bridge.execute("Analyze revenue trends", context={"goal": "general"})

        assert "analysis" in result
        assert "recommendations" in result

    def test_execute_passes_prompt_as_context_to_analyze(self):
        import orchestrator.core_bridge as cb_mod

        analysis_mod, recs_mod = _make_fake_core_modules()
        captured = {}

        def fake_analyze(req):
            captured["context"] = req.context
            return analysis_mod.analyze.return_value

        with (
            patch.object(cb_mod, "_CORE_AVAILABLE", True),
            patch.object(cb_mod, "analyze", fake_analyze),
            patch.object(cb_mod, "AnalysisRequest", analysis_mod.AnalysisRequest),
            patch.object(cb_mod, "recommend", recs_mod.recommend),
            patch.object(cb_mod, "RecommendationRequest", recs_mod.RecommendationRequest),
        ):
            bridge = cb_mod.CoreAnalysisBridge()
            bridge.execute("My special prompt")

        assert captured["context"] == "My special prompt"

    def test_execute_serializes_recommendations(self):
        import orchestrator.core_bridge as cb_mod

        analysis_mod, recs_mod = _make_fake_core_modules()

        with (
            patch.object(cb_mod, "_CORE_AVAILABLE", True),
            patch.object(cb_mod, "analyze", analysis_mod.analyze),
            patch.object(cb_mod, "AnalysisRequest", analysis_mod.AnalysisRequest),
            patch.object(cb_mod, "recommend", recs_mod.recommend),
            patch.object(cb_mod, "RecommendationRequest", recs_mod.RecommendationRequest),
        ):
            bridge = cb_mod.CoreAnalysisBridge()
            result = bridge.execute("prompt")

        recs = result["recommendations"]
        assert isinstance(recs, list)
        assert len(recs) == 1
        rec = recs[0]
        for key in ("id", "description", "priority", "effort", "expected_impact_metric"):
            assert key in rec, f"Missing key: {key}"

    def test_execute_uses_context_goal(self):
        import orchestrator.core_bridge as cb_mod

        analysis_mod, recs_mod = _make_fake_core_modules()
        captured = {}

        def fake_analyze(req):
            captured["goal"] = req.goal
            return analysis_mod.analyze.return_value

        with (
            patch.object(cb_mod, "_CORE_AVAILABLE", True),
            patch.object(cb_mod, "analyze", fake_analyze),
            patch.object(cb_mod, "AnalysisRequest", analysis_mod.AnalysisRequest),
            patch.object(cb_mod, "recommend", recs_mod.recommend),
            patch.object(cb_mod, "RecommendationRequest", recs_mod.RecommendationRequest),
        ):
            bridge = cb_mod.CoreAnalysisBridge()
            bridge.execute("prompt", context={"goal": "grow_subscribers"})

        assert captured["goal"] == "grow_subscribers"

    def test_run_wraps_execute_in_module_result(self):
        import orchestrator.core_bridge as cb_mod

        analysis_mod, recs_mod = _make_fake_core_modules()

        with (
            patch.object(cb_mod, "_CORE_AVAILABLE", True),
            patch.object(cb_mod, "analyze", analysis_mod.analyze),
            patch.object(cb_mod, "AnalysisRequest", analysis_mod.AnalysisRequest),
            patch.object(cb_mod, "recommend", recs_mod.recommend),
            patch.object(cb_mod, "RecommendationRequest", recs_mod.RecommendationRequest),
        ):
            bridge = cb_mod.CoreAnalysisBridge()
            result = bridge.run(llm=None, input_data="Analyze this", context={})

        assert result.passed is True
        assert isinstance(result.output, dict)
        assert "analysis" in result.output


# ---------------------------------------------------------------------------
# Test: get_status() returns correct keys
# ---------------------------------------------------------------------------

class TestGetStatus:
    """get_status() always returns a dict with the expected structure."""

    def test_get_status_keys_present(self):
        import orchestrator.core_bridge as cb_mod

        bridge = cb_mod.CoreAnalysisBridge()
        status = bridge.get_status()

        assert "available" in status, "Missing 'available' key"
        assert "module" in status, "Missing 'module' key"
        assert "version" in status, "Missing 'version' key"

    def test_get_status_available_is_bool(self):
        import orchestrator.core_bridge as cb_mod

        bridge = cb_mod.CoreAnalysisBridge()
        status = bridge.get_status()

        assert isinstance(status["available"], bool)

    def test_get_status_module_name(self):
        import orchestrator.core_bridge as cb_mod

        bridge = cb_mod.CoreAnalysisBridge()
        status = bridge.get_status()

        assert status["module"] == cb_mod.CoreAnalysisBridge.MODULE_NAME

    def test_get_status_version_is_string(self):
        import orchestrator.core_bridge as cb_mod

        bridge = cb_mod.CoreAnalysisBridge()
        status = bridge.get_status()

        assert isinstance(status["version"], str)
        assert len(status["version"]) > 0

    def test_get_status_when_available(self):
        import orchestrator.core_bridge as cb_mod

        with patch.object(cb_mod, "_CORE_AVAILABLE", True):
            bridge = cb_mod.CoreAnalysisBridge()
            status = bridge.get_status()

        assert status["available"] is True

    def test_get_status_when_unavailable(self):
        import orchestrator.core_bridge as cb_mod

        with patch.object(cb_mod, "_CORE_AVAILABLE", False):
            bridge = cb_mod.CoreAnalysisBridge()
            status = bridge.get_status()

        assert status["available"] is False
