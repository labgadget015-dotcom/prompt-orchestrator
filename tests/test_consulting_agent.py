"""Tests for ConsultingAgent."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from orchestrator.agents.consulting_agent import (
    ConsultingAgent,
    ConsultingReport,
    EcommerceMetrics,
    _benchmark_report,
)


def make_metrics(**kwargs) -> EcommerceMetrics:
    return EcommerceMetrics(**kwargs)


def make_llm_client(situation="Revenue strong"):
    payload = {
        "situation": situation,
        "complication": "Cart abandonment elevated.",
        "recommendations": [
            {"action": "Run A/B test", "type": "quick_win", "metric": "conversion_rate",
             "expected_impact": "2% lift", "priority": "high"}
        ],
        "next_steps": ["Monitor weekly"],
        "flags": ["cart_abandonment=82%"],
    }
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json.dumps(payload))]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg
    return mock_client


class TestBenchmarkReport:
    def test_low_conversion_flagged(self):
        report = _benchmark_report(make_metrics(conversion_rate=0.005))
        assert any("conversion_rate" in f for f in report.flags)
        assert any(r.metric == "conversion_rate" for r in report.recommendations)

    def test_high_cart_abandonment_flagged(self):
        report = _benchmark_report(make_metrics(cart_abandonment_rate=0.85))
        assert any("cart_abandonment" in f for f in report.flags)

    def test_low_ltv_cac_flagged(self):
        report = _benchmark_report(make_metrics(ltv=200, cac=150))
        ratio = 200 / 150
        assert any("ltv_cac" in f for f in report.flags)

    def test_high_mape_flagged(self):
        report = _benchmark_report(make_metrics(forecast_mape=0.35))
        assert any("forecast_mape" in f for f in report.flags)

    def test_healthy_metrics_no_flags(self):
        report = _benchmark_report(make_metrics(
            conversion_rate=0.03, cart_abandonment_rate=0.68,
            ltv=600, cac=150, forecast_mape=0.12,
        ))
        assert len(report.flags) == 0

    def test_empty_metrics_returns_report(self):
        report = _benchmark_report(make_metrics())
        assert report.situation
        assert report.source == "rules"

    def test_ltv_cac_ratio_property(self):
        m = make_metrics(ltv=900, cac=300)
        assert m.ltv_cac_ratio == 3.0

    def test_ltv_cac_ratio_none_when_missing(self):
        assert make_metrics().ltv_cac_ratio is None


class TestConsultingAgentRules:
    def setup_method(self):
        self.agent = ConsultingAgent()  # no api_key → rules

    def test_advise_returns_report(self):
        report = self.agent.advise(make_metrics(conversion_rate=0.02))
        assert isinstance(report, ConsultingReport)

    def test_advise_high_abandonment(self):
        report = self.agent.advise(make_metrics(cart_abandonment_rate=0.90))
        assert report.source == "rules"
        assert any("cart" in r.action.lower() for r in report.recommendations)

    def test_next_steps_present(self):
        report = self.agent.advise(make_metrics(ltv=100, cac=200))
        assert len(report.next_steps) > 0

    def test_system_prompt_loaded(self):
        assert "consulting" in self.agent._system_prompt.lower() or "e-commerce" in self.agent._system_prompt.lower()


class TestConsultingAgentLLM:
    def test_llm_path_used(self):
        agent = ConsultingAgent()
        agent._client = make_llm_client("Revenue is strong")
        report = agent.advise(make_metrics(conversion_rate=0.025))
        assert report.source == "llm"
        assert "Revenue" in report.situation

    def test_llm_fallback_on_error(self):
        agent = ConsultingAgent()
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("timeout")
        agent._client = mock_client
        report = agent.advise(make_metrics(conversion_rate=0.005))
        assert report.source == "rules"


def test_exports():
    from orchestrator.agents import ConsultingAgent, ConsultingReport, EcommerceMetrics
    assert ConsultingAgent is not None
