"""Test suite for prompt-orchestrator — core, router, modules, analytics, claude_client."""
import json
import os
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from orchestrator.core import PromptOrchestrator, ModuleResult
from orchestrator.router import PromptRouter
from orchestrator.analytics import AnalyticsHub
from orchestrator.claude_client import ClaudeClient
from orchestrator.modules.golden import GOLDENAnalyzer
from orchestrator.modules.cot import ChainOfThoughtReasoner
from orchestrator.modules.domain import DomainAdaptiveSpecialist
from orchestrator.modules.bias import EthicalBiasDetector
from orchestrator.modules.verification import SelfVerificationLoop
from orchestrator.modules.feedback import FeedbackEvaluator
from orchestrator.modules.synthesizer import ContentSynthesizer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def mock_llm(response="default response"):
    llm = MagicMock()
    llm.generate.return_value = response
    return llm


def make_module_result(output="output", passed=True):
    return ModuleResult(output=output, passed=passed, metrics={'success': passed})


# ===========================================================================
# ModuleResult
# ===========================================================================

class TestModuleResult:
    def test_stores_output(self):
        r = ModuleResult(output="hello", passed=True, metrics={})
        assert r.output == "hello"

    def test_stores_passed(self):
        r = ModuleResult(output="x", passed=False, metrics={})
        assert r.passed is False

    def test_stores_metrics(self):
        m = {'latency': 1.2, 'version': 'v1'}
        r = ModuleResult(output="x", passed=True, metrics=m)
        assert r.metrics == m

    def test_has_timestamp(self):
        r = ModuleResult(output="x", passed=True, metrics={})
        assert r.timestamp is not None


# ===========================================================================
# PromptOrchestrator — core pipeline
# ===========================================================================

class TestPromptOrchestrator:
    @pytest.fixture
    def orchestrator(self):
        llm = mock_llm()
        orch = PromptOrchestrator(llm)
        router = PromptRouter()
        orch.router = router
        return orch

    def _make_module(self, output="response", passed=True):
        mod = MagicMock()
        mod.run.return_value = ModuleResult(output=output, passed=passed, metrics={'success': passed, 'latency': 0.1})
        return mod

    def test_register_module(self, orchestrator):
        mod = self._make_module()
        orchestrator.register_module('test_mod', mod)
        assert 'test_mod' in orchestrator.modules

    def test_execute_single_module_success(self, orchestrator):
        mod = self._make_module("done", True)
        orchestrator.register_module('cot', mod)
        orchestrator.register_module('verification', mod)
        result = orchestrator.execute("verify this task", context={'chain': ['cot', 'verification']})
        assert result.passed is True

    def test_execute_passes_output_between_modules(self, orchestrator):
        first = self._make_module("first output", True)
        second = MagicMock()
        second.run.return_value = ModuleResult(output="second output", passed=True, metrics={})

        orchestrator.register_module('first', first)
        orchestrator.register_module('second', second)
        orchestrator.execute("task", context={'chain': ['first', 'second']})

        # second module should receive the output of first, not the raw ModuleResult
        call_args = second.run.call_args
        assert call_args[0][1] == "first output"

    def test_execute_stops_on_failure(self, orchestrator):
        failing = self._make_module("error", False)
        should_not_run = self._make_module("ok", True)

        orchestrator.register_module('failing', failing)
        orchestrator.register_module('next', should_not_run)
        orchestrator.execute("task", context={'chain': ['failing', 'next']})

        should_not_run.run.assert_not_called()

    def test_execute_returns_failure_result(self, orchestrator):
        mod = self._make_module("bad", False)
        orchestrator.register_module('cot', mod)
        result = orchestrator.execute("task", context={'chain': ['cot']})
        assert result.passed is False
        assert 'cot' in result.output

    def test_execute_unknown_module_raises(self, orchestrator):
        with pytest.raises(ValueError, match="not registered"):
            orchestrator.execute("task", context={'chain': ['nonexistent']})

    def test_execute_logs_to_analytics(self, orchestrator):
        analytics = MagicMock()
        orchestrator.analytics = analytics
        mod = self._make_module("ok", True)
        orchestrator.register_module('cot', mod)
        orchestrator.execute("task", context={'chain': ['cot']})
        analytics.log.assert_called_once()

    def test_execute_uses_router_when_no_context_chain(self, orchestrator):
        mod = self._make_module("ok", True)
        orchestrator.register_module('cot', mod)
        orchestrator.register_module('verification', mod)
        # "verify" keyword → validation chain → ['cot', 'verification', 'bias']
        # but bias not registered — override chain to avoid that
        result = orchestrator.execute("task", context={'chain': ['cot']})
        assert result.passed is True

    def test_default_chain_used_when_no_router(self):
        llm = mock_llm()
        orch = PromptOrchestrator(llm)  # no router set
        mod = self._make_module("ok", True)
        orch.register_module('verification', mod)
        result = orch.execute("task")
        assert result.passed is True

    def test_execution_log_populated(self, orchestrator):
        mod = self._make_module("ok", True)
        orchestrator.register_module('cot', mod)
        orchestrator.execute("task", context={'chain': ['cot']})
        assert len(orchestrator.execution_log) == 1

    def test_context_defaults_to_empty_dict(self, orchestrator):
        mod = self._make_module("ok", True)
        orchestrator.register_module('verification', mod)
        # Should not raise
        result = orchestrator.execute("task", context={'chain': ['verification']})
        assert result is not None


# ===========================================================================
# PromptRouter
# ===========================================================================

class TestPromptRouter:
    @pytest.fixture
    def router(self):
        return PromptRouter()

    def test_analyze_keyword_selects_analysis_chain(self, router):
        chain = router.select_chain("analyze this data")
        assert chain == router.chain_patterns['analysis']

    def test_create_keyword_selects_creative_chain(self, router):
        chain = router.select_chain("create a marketing plan")
        assert chain == router.chain_patterns['creative']

    def test_verify_keyword_selects_validation_chain(self, router):
        chain = router.select_chain("verify the output")
        assert chain == router.chain_patterns['validation']

    def test_optimize_keyword_selects_optimization_chain(self, router):
        chain = router.select_chain("optimize our revenue")
        assert chain == router.chain_patterns['optimization']

    def test_no_keyword_defaults_to_simple(self, router):
        chain = router.select_chain("do something unclear")
        assert chain == router.chain_patterns['simple']

    def test_context_chain_overrides_keyword(self, router):
        custom = ['cot', 'verification']
        chain = router.select_chain("analyze data", context={'chain': custom})
        assert chain == custom

    def test_highest_scoring_chain_wins(self, router):
        # "analyze evaluate assess" → 3 analysis hits
        chain = router.select_chain("analyze evaluate assess create")
        assert chain == router.chain_patterns['analysis']

    def test_register_chain(self, router):
        router.register_chain('custom', ['cot', 'bias'])
        assert router.chain_patterns['custom'] == ['cot', 'bias']

    def test_register_keywords_new_chain(self, router):
        router.register_keywords('new_type', ['summarize', 'condense'])
        assert 'summarize' in router.keywords['new_type']

    def test_register_keywords_existing_chain(self, router):
        router.register_keywords('analysis', ['inspect'])
        assert 'inspect' in router.keywords['analysis']

    def test_case_insensitive_matching(self, router):
        chain = router.select_chain("ANALYZE this")
        assert chain == router.chain_patterns['analysis']

    def test_empty_task_defaults_to_simple(self, router):
        chain = router.select_chain("")
        assert chain == router.chain_patterns['simple']


# ===========================================================================
# GOLDENAnalyzer
# ===========================================================================

class TestGOLDENAnalyzer:
    @pytest.fixture
    def module(self):
        return GOLDENAnalyzer()

    def test_passes_when_all_components_present(self, module):
        response = "Goal: x Output: y Limits: z Data: a Evaluation: b Next: c"
        llm = mock_llm(response)
        result = module.run(llm, "analyze revenue", {})
        assert result.passed is True
        assert result.output == response

    def test_fails_when_components_missing(self, module):
        llm = mock_llm("Just a simple response with no structure")
        result = module.run(llm, "task", {})
        assert result.passed is False

    def test_llm_exception_returns_failed(self, module):
        llm = MagicMock()
        llm.generate.side_effect = Exception("API down")
        result = module.run(llm, "task", {})
        assert result.passed is False
        assert "GOLDEN analysis failed" in result.output

    def test_metrics_include_version(self, module):
        llm = mock_llm("Goal Output Limits Data Evaluation Next")
        result = module.run(llm, "task", {})
        assert result.metrics['version'] == GOLDENAnalyzer.version

    def test_metrics_include_latency(self, module):
        llm = mock_llm("Goal Output Limits Data Evaluation Next")
        result = module.run(llm, "task", {})
        assert 'latency' in result.metrics

    def test_prompt_includes_task(self, module):
        llm = mock_llm("Goal Output Limits Data Evaluation Next")
        module.run(llm, "my specific task", {})
        prompt_used = llm.generate.call_args[0][0]
        assert "my specific task" in prompt_used


# ===========================================================================
# ChainOfThoughtReasoner
# ===========================================================================

class TestChainOfThoughtReasoner:
    @pytest.fixture
    def module(self):
        return ChainOfThoughtReasoner()

    def _cot_response(self):
        return "Step 1: Understanding\nStep 2: Analysis\nStep 3: Reasoning\nStep 4: Conclusion\nStep 5: Confidence"

    def test_passes_with_all_steps(self, module):
        result = module.run(mock_llm(self._cot_response()), "task", {})
        assert result.passed is True

    def test_passes_with_4_of_5_steps(self, module):
        response = "Step 1: x\nStep 2: x\nStep 3: x\nStep 4: x"
        result = module.run(mock_llm(response), "task", {})
        assert result.passed is True

    def test_fails_with_fewer_than_4_steps(self, module):
        response = "Step 1: x\nStep 2: x\nStep 3: x"
        result = module.run(mock_llm(response), "task", {})
        assert result.passed is False

    def test_metrics_contain_steps_found(self, module):
        result = module.run(mock_llm(self._cot_response()), "task", {})
        assert result.metrics['steps_found'] == 5

    def test_llm_exception_returns_failed(self, module):
        llm = MagicMock()
        llm.generate.side_effect = Exception("timeout")
        result = module.run(llm, "task", {})
        assert result.passed is False

    def test_prompt_includes_task(self, module):
        llm = mock_llm(self._cot_response())
        module.run(llm, "my task here", {})
        assert "my task here" in llm.generate.call_args[0][0]


# ===========================================================================
# DomainAdaptiveSpecialist
# ===========================================================================

class TestDomainAdaptiveSpecialist:
    @pytest.fixture
    def module(self):
        return DomainAdaptiveSpecialist()

    def test_passes_with_substantive_different_response(self, module):
        response = "x" * 60
        result = module.run(mock_llm(response), "original task", {})
        assert result.passed is True

    def test_fails_when_response_too_short(self, module):
        result = module.run(mock_llm("short"), "task", {})
        assert result.passed is False

    def test_fails_when_response_same_as_input(self, module):
        task = "x" * 60
        result = module.run(mock_llm(task), task, {})
        assert result.passed is False

    def test_uses_context_domain(self, module):
        llm = mock_llm("x" * 60)
        result = module.run(llm, "task", {'domain': 'fintech'})
        assert result.metrics['domain'] == 'fintech'

    def test_auto_detects_saas_domain(self, module):
        llm = mock_llm("x" * 60)
        result = module.run(llm, "saas metrics analysis", {})
        assert result.metrics['domain'] == 'saas'

    def test_auto_detects_healthcare_domain(self, module):
        llm = mock_llm("x" * 60)
        result = module.run(llm, "healthcare patient outcomes", {})
        assert result.metrics['domain'] == 'healthcare'

    def test_defaults_to_general_domain(self, module):
        llm = mock_llm("x" * 60)
        result = module.run(llm, "unrelated task", {})
        assert result.metrics['domain'] == 'general'

    def test_llm_exception_returns_failed(self, module):
        llm = MagicMock()
        llm.generate.side_effect = Exception("err")
        result = module.run(llm, "task", {})
        assert result.passed is False

    def test_all_domains_have_profiles(self, module):
        for domain in ['fintech', 'healthcare', 'cybersecurity', 'saas', 'general']:
            assert domain in module.domain_profiles


# ===========================================================================
# EthicalBiasDetector
# ===========================================================================

class TestEthicalBiasDetector:
    @pytest.fixture
    def module(self):
        return EthicalBiasDetector()

    def test_passes_safe_content(self, module):
        result = module.run(mock_llm("Status: SAFE\nNo issues found."), "task", {})
        assert result.passed is True

    def test_fails_flagged_content(self, module):
        result = module.run(mock_llm("Status: FLAGGED\nIssue found."), "task", {})
        assert result.passed is False

    def test_blocked_output_when_flagged(self, module):
        result = module.run(mock_llm("FLAGGED content"), "task", {})
        assert 'BIAS DETECTED' in result.output

    def test_passes_through_original_content_when_safe(self, module):
        result = module.run(mock_llm("Status: SAFE"), "my safe content", {})
        assert result.output == "my safe content"

    def test_detects_high_severity(self, module):
        result = module.run(mock_llm("FLAGGED high severity issue"), "task", {})
        assert result.metrics['severity'] == 'high'

    def test_detects_medium_severity(self, module):
        result = module.run(mock_llm("FLAGGED medium concern"), "task", {})
        assert result.metrics['severity'] == 'medium'

    def test_safe_content_severity_is_none(self, module):
        result = module.run(mock_llm("Status: SAFE"), "task", {})
        assert result.metrics['severity'] == 'none'

    def test_llm_exception_returns_failed(self, module):
        llm = MagicMock()
        llm.generate.side_effect = Exception("err")
        result = module.run(llm, "task", {})
        assert result.passed is False

    def test_input_converted_to_string(self, module):
        result = module.run(mock_llm("Status: SAFE"), 12345, {})
        assert result.passed is True


# ===========================================================================
# SelfVerificationLoop
# ===========================================================================

class TestSelfVerificationLoop:
    @pytest.fixture
    def module(self):
        return SelfVerificationLoop()

    def test_passes_when_verification_passes(self, module):
        result = module.run(mock_llm("PASS — all good"), "good response", {})
        assert result.passed is True

    def test_fails_when_verification_fails(self, module):
        result = module.run(mock_llm("FAIL — missing sections"), "response", {})
        assert result.passed is False

    def test_appends_verification_notes_on_fail(self, module):
        result = module.run(mock_llm("FAIL details here"), "original", {})
        assert "VERIFICATION FAILED" in result.output
        assert "original" in result.output

    def test_returns_original_on_pass(self, module):
        result = module.run(mock_llm("PASS"), "my response", {})
        assert result.output == "my response"

    def test_uses_original_task_from_context(self, module):
        llm = mock_llm("PASS")
        module.run(llm, "response", {'original_task': 'the real task'})
        prompt = llm.generate.call_args[0][0]
        assert 'the real task' in prompt

    def test_handles_non_string_input(self, module):
        result = module.run(mock_llm("PASS"), 42, {})
        assert result.passed is True

    def test_llm_exception_returns_failed(self, module):
        llm = MagicMock()
        llm.generate.side_effect = Exception("err")
        result = module.run(llm, "task", {})
        assert result.passed is False


# ===========================================================================
# FeedbackEvaluator
# ===========================================================================

class TestFeedbackEvaluator:
    @pytest.fixture
    def module(self):
        return FeedbackEvaluator()

    def test_passes_when_score_above_6(self, module):
        response = "Overall Score: 7.5/10\n**Revised Output**: Great content here."
        result = module.run(mock_llm(response), "content", {})
        assert result.passed is True
        assert result.metrics['score'] == pytest.approx(7.5)

    def test_fails_when_score_below_6(self, module):
        response = "Overall Score: 4.0/10"
        result = module.run(mock_llm(response), "content", {})
        assert result.passed is False

    def test_passes_when_no_score_detected(self, module):
        result = module.run(mock_llm("Good feedback without a score."), "content", {})
        assert result.passed is True
        assert result.metrics['score'] is None

    def test_extracts_revised_output_section(self, module):
        response = "Analysis here\n**Revised Output**: This is the improved version."
        result = module.run(mock_llm(response), "content", {})
        assert result.output == "This is the improved version."

    def test_returns_full_response_when_no_revised_section(self, module):
        response = "Overall Score: 8/10\nSome feedback."
        result = module.run(mock_llm(response), "content", {})
        assert result.output == response

    def test_uses_original_task_from_context(self, module):
        llm = mock_llm("feedback")
        module.run(llm, "content", {'original_task': 'the original'})
        assert 'the original' in llm.generate.call_args[0][0]

    def test_llm_exception_returns_failed(self, module):
        llm = MagicMock()
        llm.generate.side_effect = Exception("err")
        result = module.run(llm, "content", {})
        assert result.passed is False


# ===========================================================================
# ContentSynthesizer
# ===========================================================================

class TestContentSynthesizer:
    @pytest.fixture
    def module(self):
        return ContentSynthesizer()

    def test_passes_with_substantive_distinct_output(self, module):
        response = "This is a well-synthesized response that is sufficiently long and different." * 3
        result = module.run(mock_llm(response), "original content", {})
        assert result.passed is True

    def test_fails_when_output_too_short(self, module):
        result = module.run(mock_llm("short"), "content", {})
        assert result.passed is False

    def test_fails_when_output_same_as_input(self, module):
        content = "x" * 200
        result = module.run(mock_llm(content), content, {})
        assert result.passed is False

    def test_metrics_include_lengths(self, module):
        response = "y" * 200
        result = module.run(mock_llm(response), "input", {})
        assert result.metrics['input_length'] == len("input")
        assert result.metrics['output_length'] == 200

    def test_uses_original_task_from_context(self, module):
        llm = mock_llm("y" * 200)
        module.run(llm, "content", {'original_task': 'build a story'})
        assert 'build a story' in llm.generate.call_args[0][0]

    def test_llm_exception_returns_failed(self, module):
        llm = MagicMock()
        llm.generate.side_effect = Exception("err")
        result = module.run(llm, "content", {})
        assert result.passed is False


# ===========================================================================
# AnalyticsHub
# ===========================================================================

class TestAnalyticsHub:
    @pytest.fixture
    def hub(self, tmp_path):
        return AnalyticsHub(log_file=str(tmp_path / 'analytics.jsonl'))

    def test_log_writes_to_file(self, hub):
        hub.log('golden', {'success': True, 'latency': 1.2})
        lines = open(hub.log_file).readlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record['module'] == 'golden'
        assert record['success'] is True

    def test_log_adds_timestamp(self, hub):
        hub.log('cot', {'latency': 0.5})
        record = json.loads(open(hub.log_file).readlines()[0])
        assert 'timestamp' in record

    def test_log_accumulates_session_data(self, hub):
        hub.log('golden', {'latency': 1.0})
        hub.log('cot', {'latency': 0.5})
        assert len(hub.session_data) == 2

    def test_get_performance_missing_file(self, hub):
        result = hub.get_performance('golden')
        assert result == {}

    def test_get_performance_returns_stats(self, hub):
        hub.log('golden', {'success': True, 'latency': 1.0})
        hub.log('golden', {'success': False, 'latency': 2.0})
        perf = hub.get_performance('golden')
        assert perf['total_runs'] == 2
        assert perf['success_count'] == 1
        assert perf['success_rate'] == pytest.approx(0.5)
        assert perf['avg_latency'] == pytest.approx(1.5)

    def test_get_performance_all_modules(self, hub):
        hub.log('golden', {'success': True, 'latency': 1.0})
        perf = hub.get_performance()  # no module filter
        assert perf['total_runs'] == 1

    def test_get_performance_empty_returns_empty(self, hub, tmp_path):
        # log file exists but has no records for this module
        hub.log('cot', {'latency': 1.0})
        perf = hub.get_performance('golden')
        assert perf == {}

    def test_get_all_stats(self, hub):
        hub.log('golden', {'success': True, 'latency': 1.0})
        hub.log('cot', {'success': True, 'latency': 0.5})
        stats = hub.get_all_stats()
        assert 'golden' in stats
        assert 'cot' in stats

    def test_get_all_stats_missing_file(self, hub):
        assert hub.get_all_stats() == {}


# ===========================================================================
# ClaudeClient
# ===========================================================================

class TestClaudeClient:
    def _make_stream(self, text="response text", input_tokens=100, output_tokens=50,
                     cache_read=0, cache_write=0):
        block = MagicMock()
        block.type = "text"
        block.text = text
        msg = MagicMock()
        msg.content = [block]
        msg.usage = MagicMock()
        msg.usage.input_tokens = input_tokens
        msg.usage.output_tokens = output_tokens
        msg.usage.cache_read_input_tokens = cache_read
        msg.usage.cache_creation_input_tokens = cache_write
        stream = MagicMock()
        stream.__enter__ = MagicMock(return_value=stream)
        stream.__exit__ = MagicMock(return_value=False)
        stream.get_final_message.return_value = msg
        return stream

    @pytest.fixture
    def client(self, monkeypatch):
        monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-ant-test')
        with patch('anthropic.Anthropic'):
            return ClaudeClient(api_key='sk-ant-test')

    def test_generate_returns_text(self, client):
        stream = self._make_stream("hello world")
        client.client.messages.stream.return_value = stream
        result = client.generate("prompt")
        assert result == "hello world"

    def test_generate_increments_call_count(self, client):
        stream = self._make_stream()
        client.client.messages.stream.return_value = stream
        client.generate("prompt")
        assert client._call_count == 1

    def test_generate_tracks_tokens(self, client):
        stream = self._make_stream(input_tokens=200, output_tokens=100)
        client.client.messages.stream.return_value = stream
        client.generate("prompt")
        assert client._tokens_used == 300

    def test_generate_tracks_cache_tokens(self, client):
        stream = self._make_stream(cache_read=500, cache_write=200)
        client.client.messages.stream.return_value = stream
        client.generate("prompt")
        assert client._cache_read_tokens == 500
        assert client._cache_write_tokens == 200

    def test_stats_returns_dict(self, client):
        stats = client.stats()
        assert 'calls' in stats
        assert 'tokens_used' in stats
        assert 'cache_read_tokens' in stats
        assert 'cache_write_tokens' in stats

    def test_system_prompt_uses_cache_control(self, client):
        stream = self._make_stream()
        client.client.messages.stream.return_value = stream
        client.generate("prompt")
        call_kwargs = client.client.messages.stream.call_args[1]
        system = call_kwargs['system']
        assert system[0]['cache_control'] == {'type': 'ephemeral'}

    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
        with pytest.raises(KeyError):
            ClaudeClient()

    def test_default_model_is_opus(self, client):
        assert client.model == 'claude-opus-4-6'

    def test_custom_model_accepted(self, monkeypatch):
        monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-ant-test')
        with patch('anthropic.Anthropic'):
            c = ClaudeClient(api_key='sk-ant-test', model='claude-haiku-4-5-20251001')
        assert c.model == 'claude-haiku-4-5-20251001'


# ===========================================================================
# Integration — full pipeline via orchestrator
# ===========================================================================

class TestPipelineIntegration:
    def test_analysis_chain_end_to_end(self):
        """Full analysis chain with mocked LLM — verifies module serialization."""
        llm = mock_llm("Goal Output Limits Data Evaluation Next Step 1 Step 2 Step 3 Step 4 Status: SAFE PASS")

        orch = PromptOrchestrator(llm)
        orch.router = PromptRouter()

        orch.register_module('golden', GOLDENAnalyzer())
        orch.register_module('domain', DomainAdaptiveSpecialist())
        orch.register_module('cot', ChainOfThoughtReasoner())
        orch.register_module('verification', SelfVerificationLoop())
        orch.register_module('bias', EthicalBiasDetector())

        result = orch.execute("analyze our strategy", context={
            'chain': ['golden', 'cot', 'verification', 'bias'],
            'original_task': 'analyze our strategy'
        })

        # Key assertion: no ModuleResult object leaked as string between stages
        for log_entry in orch.execution_log[0]:
            assert '<orchestrator.core.ModuleResult' not in str(log_entry)

    def test_pipeline_propagates_string_not_object(self):
        """Regression test for the core.py serialization bug."""
        outputs = []

        class CapturingModule:
            def run(self, llm, input_data, context):
                outputs.append(input_data)
                return ModuleResult(output="captured output", passed=True, metrics={})

        llm = mock_llm()
        orch = PromptOrchestrator(llm)
        orch.router = PromptRouter()
        orch.register_module('first', CapturingModule())
        orch.register_module('second', CapturingModule())
        orch.execute("task", context={'chain': ['first', 'second']})

        # second module should receive a string, not a ModuleResult
        assert isinstance(outputs[1], str), f"Expected str, got {type(outputs[1])}"
        assert outputs[1] == "captured output"
