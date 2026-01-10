"""GOLDEN Framework Analyzer Module.

Goal - Output - Limits - Data - Evaluation - Next steps
"""

from typing import Dict, Any
import sys
sys.path.append('..')
from core import ModuleResult


class GOLDENAnalyzer:
    """Analyzes tasks using GOLDEN framework."""
    
    version = "v2.1"
    category = ["FOUNDATION", "ANALYSIS"]
    
    def __init__(self):
        self.prompt_template = """Analyze the following task using the GOLDEN framework:

**Goal**: What is the specific objective?
**Output**: What should the final deliverable look like?
**Limits**: What constraints or boundaries exist?
**Data**: What information is available or needed?
**Evaluation**: How will success be measured?
**Next steps**: What actions should follow?

Task: {task}

Provide a structured GOLDEN analysis:"""
    
    def run(self, llm, task: str, context: Dict[str, Any]) -> ModuleResult:
        """Execute GOLDEN analysis."""
        import time
        start = time.time()
        
        # Build prompt
        prompt = self.prompt_template.format(task=task)
        
        # Execute LLM
        try:
            response = llm.generate(prompt)
            latency = time.time() - start
            
            # Validate response has all GOLDEN components
            required = ['goal', 'output', 'limits', 'data', 'evaluation', 'next']
            response_lower = response.lower()
            success = all(comp in response_lower for comp in required)
            
            metrics = {
                'success': success,
                'latency': latency,
                'token_count': len(response.split()),
                'version': self.version
            }
            
            return ModuleResult(
                output=response,
                passed=success,
                metrics=metrics
            )
            
        except Exception as e:
            return ModuleResult(
                output=f"GOLDEN analysis failed: {str(e)}",
                passed=False,
                metrics={'error': str(e), 'version': self.version}
            )
