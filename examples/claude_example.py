#!/usr/bin/env python3
"""Complete example: Prompt Orchestrator with Claude API.

Runs the full analysis chain:
  GOLDEN → Domain → CoT → Verification → Bias

Requires ANTHROPIC_API_KEY in the environment.
"""

import sys
sys.path.append('..')

from dotenv import load_dotenv
from pathlib import Path
load_dotenv(dotenv_path=Path(__file__).parent.parent / '.env')

from orchestrator.core import PromptOrchestrator
from orchestrator.router import PromptRouter
from orchestrator.modules.golden import GOLDENAnalyzer
from orchestrator.modules.domain import DomainAdaptiveSpecialist
from orchestrator.modules.cot import ChainOfThoughtReasoner
from orchestrator.modules.bias import EthicalBiasDetector
from orchestrator.modules.verification import SelfVerificationLoop
from orchestrator.modules.synthesizer import ContentSynthesizer
from orchestrator.modules.feedback import FeedbackEvaluator
from orchestrator.analytics import AnalyticsHub
from orchestrator.claude_client import ClaudeClient


def main():
    print("🚀 Initializing Prompt Orchestrator with Claude...\n")

    # 1. Set up Claude client (reads ANTHROPIC_API_KEY from env)
    llm = ClaudeClient()

    # 2. Initialize orchestrator
    orchestrator = PromptOrchestrator(llm)
    orchestrator.router = PromptRouter()
    orchestrator.analytics = AnalyticsHub(log_file='analytics.jsonl')

    # 3. Register all modules
    orchestrator.register_module('golden', GOLDENAnalyzer())
    orchestrator.register_module('domain', DomainAdaptiveSpecialist())
    orchestrator.register_module('cot', ChainOfThoughtReasoner())
    orchestrator.register_module('bias', EthicalBiasDetector())
    orchestrator.register_module('verification', SelfVerificationLoop())
    orchestrator.register_module('synthesizer', ContentSynthesizer())
    orchestrator.register_module('feedback', FeedbackEvaluator())

    # 4. Task — router keyword-matches "analyze" → analysis chain
    task = """Analyze our SaaS business revenue optimization strategy.

    Current metrics:
    - MRR: $125K
    - Churn rate: 5.2%
    - CAC: $850
    - LTV: $3,200
    - Trial-to-paid: 18%

    Identify the highest-leverage improvements and create a structured action plan."""

    print("📋 Task:", task.strip()[:100], "...\n")

    try:
        print("⚙️  Executing analysis chain: GOLDEN → Domain → CoT → Verification → Bias\n")
        result = orchestrator.execute(task, context={
            'original_task': task,
            'domain': 'saas',
        })

        if result.passed:
            print("✅ Pipeline succeeded\n")
            print("📊 Output:\n")
            print(result.output[:1000], "...\n" if len(result.output) > 1000 else "")
        else:
            print("❌ Pipeline failed:", result.output)

        # Token usage
        print("\n💰 Token Usage:")
        for key, value in llm.stats().items():
            print(f"  {key}: {value:,}" if isinstance(value, int) else f"  {key}: {value}")

        # Module analytics
        print("\n📈 Module Analytics:")
        stats = orchestrator.analytics.get_all_stats()
        for module, metrics in stats.items():
            print(
                f"  {module}: "
                f"success_rate={metrics.get('success_rate', 0):.0%}, "
                f"avg_latency={metrics.get('avg_latency', 0):.2f}s"
            )

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
