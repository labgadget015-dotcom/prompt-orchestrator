"""Tests for TriageAgent."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from orchestrator.agents.triage_agent import (
    TriageAction,
    TriageAgent,
    TriageItem,
    TriagePriority,
    TriageResult,
    _rule_based_triage,
)


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #
def make_item(**kwargs) -> TriageItem:
    defaults = dict(id="1", title="Test notification", reason="subscribed", repo="org/repo", author="")
    defaults.update(kwargs)
    return TriageItem(**defaults)


# --------------------------------------------------------------------------- #
# Rule-based triage                                                            #
# --------------------------------------------------------------------------- #
class TestRuleBasedTriage:
    def test_review_requested_is_p1(self):
        result = _rule_based_triage(make_item(reason="review_requested"))
        assert result.priority == TriagePriority.P1
        assert result.action == TriageAction.REVIEW_NOW
        assert result.source == "rules"

    def test_assign_is_p1(self):
        result = _rule_based_triage(make_item(reason="assign"))
        assert result.priority == TriagePriority.P1

    def test_mention_is_p2(self):
        result = _rule_based_triage(make_item(reason="mention"))
        assert result.priority == TriagePriority.P2
        assert result.action == TriageAction.REVIEW_LATER

    def test_team_mention_is_p2(self):
        result = _rule_based_triage(make_item(reason="team_mention"))
        assert result.priority == TriagePriority.P2

    def test_bot_author_is_p3_archive(self):
        result = _rule_based_triage(make_item(author="dependabot[bot]", reason="subscribed"))
        assert result.priority == TriagePriority.P3
        assert result.action == TriageAction.ARCHIVE

    def test_renovate_bot_is_p3(self):
        result = _rule_based_triage(make_item(author="renovate[bot]", reason="comment"))
        assert result.priority == TriagePriority.P3

    def test_subscribed_unknown_is_p3_mute(self):
        result = _rule_based_triage(make_item(reason="subscribed"))
        assert result.priority == TriagePriority.P3
        assert result.action == TriageAction.MUTE

    def test_result_id_preserved(self):
        result = _rule_based_triage(make_item(id="abc123"))
        assert result.id == "abc123"


# --------------------------------------------------------------------------- #
# TriageAgent — no API key (rule-based mode)                                  #
# --------------------------------------------------------------------------- #
class TestTriageAgentRules:
    def setup_method(self):
        self.agent = TriageAgent()  # no api_key → rules mode

    def test_empty_list_returns_empty(self):
        assert self.agent.triage([]) == []

    def test_triage_one_review_requested(self):
        item = make_item(reason="review_requested", id="x1")
        result = self.agent.triage_one(item)
        assert result.priority == TriagePriority.P1
        assert result.id == "x1"

    def test_triage_batch(self):
        items = [
            make_item(id="1", reason="review_requested"),
            make_item(id="2", reason="mention"),
            make_item(id="3", reason="subscribed", author="dependabot[bot]"),
        ]
        results = self.agent.triage(items)
        assert len(results) == 3
        priorities = {r.id: r.priority for r in results}
        assert priorities["1"] == TriagePriority.P1
        assert priorities["2"] == TriagePriority.P2
        assert priorities["3"] == TriagePriority.P3

    def test_system_prompt_loaded(self):
        # Should have loaded from prompts/agent-instructions/triage-agent.md
        assert "P1" in self.agent._system_prompt
        assert "P2" in self.agent._system_prompt


# --------------------------------------------------------------------------- #
# TriageAgent — LLM path (mocked)                                             #
# --------------------------------------------------------------------------- #
class TestTriageAgentLLM:
    def _make_mock_client(self, payload):
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=json.dumps(payload))]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg
        return mock_client

    def test_llm_path_used_when_client_set(self):
        agent = TriageAgent()
        llm_response = [
            {"id": "1", "priority": "P1", "action": "review_now", "reason": "Review requested"}
        ]
        agent._client = self._make_mock_client(llm_response)

        item = make_item(id="1", reason="review_requested")
        result = agent.triage_one(item)

        assert result.priority == TriagePriority.P1
        assert result.source == "llm"

    def test_llm_fallback_on_exception(self):
        agent = TriageAgent()
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("API timeout")
        agent._client = mock_client

        item = make_item(id="1", reason="assign")
        result = agent.triage_one(item)

        # Should fall back to rules, still get P1
        assert result.priority == TriagePriority.P1
        assert result.source == "rules"

    def test_llm_passes_all_items(self):
        agent = TriageAgent()
        items = [make_item(id=str(i)) for i in range(5)]
        llm_response = [
            {"id": str(i), "priority": "P2", "action": "review_later", "reason": "test"}
            for i in range(5)
        ]
        agent._client = self._make_mock_client(llm_response)

        results = agent.triage(items)
        assert len(results) == 5
        # Verify the client was called once with all 5 items
        agent._client.messages.create.assert_called_once()


# --------------------------------------------------------------------------- #
# System prompt loading                                                        #
# --------------------------------------------------------------------------- #
class TestSystemPromptLoading:
    def test_loads_from_file(self, tmp_path):
        prompt_dir = tmp_path / "prompts" / "agent-instructions"
        prompt_dir.mkdir(parents=True)
        (prompt_dir / "triage-agent.md").write_text("Custom prompt P1 P2 P3")

        with patch(
            "orchestrator.agents.triage_agent._PROMPT_PATH",
            prompt_dir / "triage-agent.md",
        ):
            agent = TriageAgent()
            assert "Custom prompt" in agent._system_prompt

    def test_fallback_when_file_missing(self, tmp_path):
        with patch(
            "orchestrator.agents.triage_agent._PROMPT_PATH",
            tmp_path / "nonexistent.md",
        ):
            agent = TriageAgent()
            assert "triage" in agent._system_prompt.lower()
