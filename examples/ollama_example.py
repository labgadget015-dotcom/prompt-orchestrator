#!/usr/bin/env python3
"""Complete example: Prompt Orchestrator with Ollama integration.

This demonstrates the full autonomous system with:
- Ollama LLM integration
- GOLDEN framework analysis
- Self-verification loop
- Analytics tracking
- Revenue optimization use case
"""

import sys
sys.path.append('..')

from orchestrator.core import PromptOrchestrator, ModuleResult
from orchestrator.router import PromptRouter
from orchestrator.modules.golden import GOLDENAnalyzer
from orchestrator.modules.verification import SelfVerificationLoop
from orchestrator.analytics import AnalyticsHub


# Simple Ollama client wrapper
class OllamaClient:
    """Lightweight Ollama client for local LLM inference."""
    
    def __init__(self, model: str = 'llama3.2', host: str = 'http://localhost:11434'):
        self.model = model
        self.host = host
    
    def generate(self, prompt: str) -> str:
        """Generate response from Ollama."""
        import requests
        
        response = requests.post(
            f"{self.host}/api/generate",
            json={
                'model': self.model,
                'prompt': prompt,
                'stream': False
            }
        )
        
        if response.status_code == 200:
            return response.json().get('response', '')
        else:
            raise Exception(f"Ollama error: {response.status_code}")


def main():
    """Run complete orchestrated workflow."""
    
    print("🚀 Initializing Prompt Orchestrator with Ollama...\n")
    
    # 1. Set up LLM client
    llm = OllamaClient(model='llama3.2')
    
    # 2. Initialize orchestrator
    orchestrator = PromptOrchestrator(llm)
    
    # 3. Register components
    orchestrator.router = PromptRouter()
    orchestrator.analytics = AnalyticsHub(log_file='analytics.jsonl')
    
    # 4. Register modules
    orchestrator.register_module('golden', GOLDENAnalyzer())
    orchestrator.register_module('verification', SelfVerificationLoop())
    
    # 5. Define revenue optimization task
    task = """Analyze our SaaS business revenue optimization strategy.
    
    Current metrics:
    - MRR: $125K
    - Churn rate: 5.2%
    - CAC: $850
    - LTV: $3,200
    - Trial-to-paid: 18%
    
    Create a structured revenue optimization plan."""
    
    print("📋 Task:", task[:100], "...\n")
    
    # 6. Execute orchestrated chain
    try:
        print("⚙️  Executing chain: GOLDEN → Verification\n")
        result = orchestrator.execute(task, context={'original_task': task})
        
        if result.passed:
            print("✅ Execution succeeded\n")
            print("📊 Output:", result.output[:500], "...\n")
        else:
            print("❌ Execution failed\n")
            print("Error:", result.output)
        
        # 7. Show analytics
        print("\n📈 Analytics:")
        stats = orchestrator.analytics.get_all_stats()
        for module, metrics in stats.items():
            print(f"\n{module}:")
            for key, value in metrics.items():
                print(f"  {key}: {value}")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
