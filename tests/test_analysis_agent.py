"""Tests for AnalysisAgent."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from orchestrator.agents.analysis_agent import (
    AnalysisAgent,
    AnalysisResult,
    DataQuality,
    _stats_fallback,
)


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
SAMPLE_DATA = [
    {"date": "2024-01", "revenue": "50000", "orders": "120"},
    {"date": "2024-02", "revenue": "62000", "orders": "145"},
    {"date": "2024-03", "revenue": "58000", "orders": "130"},
]


def make_llm_response(summary="Test summary"):
    payload = {
        "summary": summary,
        "insights": [{"finding": "Revenue up", "evidence": "3 months data", "confidence": 0.9}],
        "recommendations": [{"action": "Expand", "priority": "high", "impact": "10% growth"}],
        "data_quality": {"issues": [], "completeness": 1.0},
    }
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json.dumps(payload))]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg
    return mock_client


# --------------------------------------------------------------------------- #
# Stats fallback                                                               #
# --------------------------------------------------------------------------- #
class TestStatsFallback:
    def test_empty_data(self):
        result = _stats_fallback([])
        assert result.source == "stats"
        assert "No data" in result.summary

    def test_numeric_columns_summarized(self):
        result = _stats_fallback(SAMPLE_DATA)
        assert result.source == "stats"
        assert len(result.insights) > 0
        assert any("revenue" in i.finding.lower() for i in result.insights)

    def test_null_values_flagged(self):
        data = [{"val": "1"}, {"val": None}, {"val": "3"}]
        result = _stats_fallback(data)
        assert result.data_quality.completeness < 1.0
        assert len(result.data_quality.issues) > 0

    def test_completeness_full_data(self):
        result = _stats_fallback(SAMPLE_DATA)
        assert result.data_quality.completeness == 1.0


# --------------------------------------------------------------------------- #
# AnalysisAgent — stats fallback mode (no client, no core)                    #
# --------------------------------------------------------------------------- #
class TestAnalysisAgentStats:
    def setup_method(self):
        self.agent = AnalysisAgent()  # no api_key

    def test_analyze_returns_result(self):
        result = self.agent.analyze(SAMPLE_DATA)
        assert isinstance(result, AnalysisResult)
        assert result.summary

    def test_analyze_empty_data(self):
        result = self.agent.analyze([])
        assert "No data" in result.summary

    def test_analyze_json_string(self):
        result = self.agent.analyze(json.dumps(SAMPLE_DATA))
        assert isinstance(result, AnalysisResult)

    def test_analyze_csv_string(self):
        csv_data = "date,revenue\n2024-01,50000\n2024-02,62000"
        result = self.agent.analyze(csv_data)
        assert isinstance(result, AnalysisResult)

    def test_analysis_type_accepted(self):
        for atype in AnalysisAgent.ANALYSIS_TYPES:
            result = self.agent.analyze(SAMPLE_DATA, analysis_type=atype)
            assert result is not None

    def test_system_prompt_loaded(self):
        assert "analysis" in self.agent._system_prompt.lower()


# --------------------------------------------------------------------------- #
# AnalysisAgent — LLM path (mocked)                                           #
# --------------------------------------------------------------------------- #
class TestAnalysisAgentLLM:
    def test_llm_path_used_when_client_set(self):
        agent = AnalysisAgent()
        agent._client = make_llm_response("Revenue trending up")

        with patch("orchestrator.agents.analysis_agent._CORE_AVAILABLE", False):
            result = agent.analyze(SAMPLE_DATA)

        assert result.source == "llm"
        assert "Revenue" in result.summary
        assert len(result.insights) == 1
        assert len(result.recommendations) == 1

    def test_llm_fallback_to_stats_on_error(self):
        agent = AnalysisAgent()
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("timeout")
        agent._client = mock_client

        with patch("orchestrator.agents.analysis_agent._CORE_AVAILABLE", False):
            result = agent.analyze(SAMPLE_DATA)

        assert result.source == "stats"

    def test_large_data_truncated_in_prompt(self):
        agent = AnalysisAgent()
        large_data = [{"val": str(i)} for i in range(100)]
        agent._client = make_llm_response()

        with patch("orchestrator.agents.analysis_agent._CORE_AVAILABLE", False):
            result = agent.analyze(large_data)

        call_kwargs = agent._client.messages.create.call_args
        user_msg = call_kwargs[1]["messages"][0]["content"]
        assert "truncated" in user_msg


# --------------------------------------------------------------------------- #
# __init__ exports                                                             #
# --------------------------------------------------------------------------- #
def test_exports():
    from orchestrator.agents import AnalysisAgent, AnalysisResult, AnalysisInsight, AnalysisRecommendation
    assert AnalysisAgent is not None
    assert AnalysisResult is not None
