"""Self-Verification Loop Module."""

from typing import Dict, Any
import sys
sys.path.append('../..')
from orchestrator.core import ModuleResult


class SelfVerificationLoop:
    """Second-pass verification and critique module."""
    
    version = "v3.2"
    category = ["VALIDATION", "QUALITY"]
    
    def __init__(self):
        self.prompt_template = """Review and critique the following response for:

1. **Logical consistency**: Are there contradictions or gaps?
2. **Completeness**: Are all requirements addressed?
3. **Accuracy**: Are claims verifiable and correct?
4. **Clarity**: Is the response clear and well-structured?

Original task: {task}

Response to verify:
{response}

Provide verification:
- PASS/FAIL status
- Issues found (if any)
- Suggested corrections"""
    
    def run(self, llm, input_data, context: Dict[str, Any]) -> ModuleResult:
        """Execute verification loop."""
        import time
        start = time.time()
        
        # Extract task and response
        if isinstance(input_data, str):
            response = input_data
            task = context.get('original_task', 'Unknown')
        else:
            response = str(input_data)
            task = context.get('original_task', 'Unknown')
        
        # Build verification prompt
        prompt = self.prompt_template.format(task=task, response=response)
        
        try:
            verification = llm.generate(prompt)
            latency = time.time() - start
            
            # Check if passed
            verification_lower = verification.lower()
            passed = 'pass' in verification_lower and 'fail' not in verification_lower[:50]
            
            metrics = {
                'success': passed,
                'latency': latency,
                'version': self.version
            }
            
            # If failed, return original with verification notes
            output = response if passed else f"{response}\n\n[VERIFICATION FAILED]\n{verification}"
            
            return ModuleResult(
                output=output,
                passed=passed,
                metrics=metrics
            )
            
        except Exception as e:
            return ModuleResult(
                output=f"Verification failed: {str(e)}",
                passed=False,
                metrics={'error': str(e), 'version': self.version}
            )
