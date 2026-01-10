"""Ethical Bias Detection Module."""

from typing import Dict, Any, List
import sys
sys.path.append('../..')
from orchestrator.core import ModuleResult


class EthicalBiasDetector:
    """Detects harmful bias and unsafe content."""
    
    version = "v2.8"
    category = ["SAFETY", "ETHICS"]
    
    def __init__(self):
        self.bias_checks = [
            'gender bias', 'racial bias', 'age bias',
            'harmful stereotypes', 'discriminatory language',
            'unsafe recommendations', 'privacy violations'
        ]
        
        self.prompt_template = """Analyze the following content for ethical issues and bias:

Content to analyze:
{content}

Check for:
1. Gender, racial, age, or other discriminatory bias
2. Harmful stereotypes or prejudiced language
3. Unsafe or dangerous recommendations
4. Privacy or security concerns
5. Manipulation or deceptive patterns

Provide assessment:
**Status**: SAFE / FLAGGED
**Issues Found**: [List any problems]
**Severity**: Low / Medium / High
**Recommendations**: [How to fix if issues exist]"""
    
    def run(self, llm, input_data, context: Dict[str, Any]) -> ModuleResult:
        """Execute bias detection."""
        import time
        start = time.time()
        
        # Extract content
        content = str(input_data)
        
        # Build bias check prompt
        prompt = self.prompt_template.format(content=content)
        
        try:
            response = llm.generate(prompt)
            latency = time.time() - start
            
            # Check if content is safe
            response_lower = response.lower()
            is_safe = 'safe' in response_lower and 'flagged' not in response_lower[:100]
            
            # Extract severity if flagged
            severity = 'low'
            if 'high' in response_lower:
                severity = 'high'
            elif 'medium' in response_lower:
                severity = 'medium'
            
            metrics = {
                'success': is_safe,
                'latency': latency,
                'safe': is_safe,
                'severity': severity if not is_safe else 'none',
                'version': self.version
            }
            
            # If unsafe, block and return error
            if not is_safe:
                return ModuleResult(
                    output=f"[BIAS DETECTED - BLOCKED]\n\nOriginal content flagged for review.\n\nBias Analysis:\n{response}",
                    passed=False,
                    metrics=metrics
                )
            
            # If safe, pass through original content
            return ModuleResult(
                output=content,
                passed=True,
                metrics=metrics
            )
            
        except Exception as e:
            return ModuleResult(
                output=f"Bias detection failed: {str(e)}",
                passed=False,
                metrics={'error': str(e), 'version': self.version}
            )
