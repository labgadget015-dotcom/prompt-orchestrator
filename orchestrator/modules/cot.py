"""Chain-of-Thought Reasoning Module."""

from typing import Dict, Any
import sys
sys.path.append('../..')
from orchestrator.core import ModuleResult


class ChainOfThoughtReasoner:
    """Forces explicit step-by-step reasoning."""
    
    version = "v3.5"
    category = ["REASONING", "TRANSPARENCY"]
    
    def __init__(self):
        self.prompt_template = """Think through this task step-by-step. Show your reasoning explicitly.

Task: {task}

Provide your response in this format:

**Step 1: Understanding**
[What is the core problem or question?]

**Step 2: Analysis**
[Break down the key components]

**Step 3: Reasoning**
[Walk through the logic]

**Step 4: Conclusion**
[Final answer or recommendation]

**Step 5: Confidence**
[Rate your confidence: High/Medium/Low and explain why]"""
    
    def run(self, llm, task: str, context: Dict[str, Any]) -> ModuleResult:
        """Execute chain-of-thought reasoning."""
        import time
        start = time.time()
        
        # Build CoT prompt
        prompt = self.prompt_template.format(task=task)
        
        try:
            response = llm.generate(prompt)
            latency = time.time() - start
            
            # Validate all steps are present
            required_steps = ['step 1', 'step 2', 'step 3', 'step 4', 'step 5']
            response_lower = response.lower()
            steps_present = sum(1 for step in required_steps if step in response_lower)
            
            # Success if at least 4/5 steps present
            success = steps_present >= 4
            
            metrics = {
                'success': success,
                'latency': latency,
                'steps_found': steps_present,
                'total_steps': len(required_steps),
                'version': self.version
            }
            
            return ModuleResult(
                output=response,
                passed=success,
                metrics=metrics
            )
            
        except Exception as e:
            return ModuleResult(
                output=f"CoT reasoning failed: {str(e)}",
                passed=False,
                metrics={'error': str(e), 'version': self.version}
            )
