"""Domain-Adaptive Specialist Module."""

from typing import Dict, Any
import sys
sys.path.append('../..')
from orchestrator.core import ModuleResult


class DomainAdaptiveSpecialist:
    """Adapts tone, vocabulary, and approach by domain."""
    
    version = "v1.9"
    category = ["ADAPTATION", "SPECIALIZATION"]
    
    def __init__(self):
        self.domain_profiles = {
            'fintech': {
                'tone': 'professional, data-driven',
                'vocabulary': 'MRR, CAC, LTV, churn, cohort',
                'constraints': 'regulatory compliance, accuracy'
            },
            'healthcare': {
                'tone': 'empathetic, precise',
                'vocabulary': 'HIPAA, patient outcomes, clinical',
                'constraints': 'privacy, medical accuracy'
            },
            'cybersecurity': {
                'tone': 'technical, alert',
                'vocabulary': 'threat vector, CVE, exploit, SOC',
                'constraints': 'confidentiality, actionable intel'
            },
            'saas': {
                'tone': 'business-focused, growth-oriented',
                'vocabulary': 'ARR, retention, expansion, activation',
                'constraints': 'customer success, scalability'
            },
            'general': {
                'tone': 'clear, professional',
                'vocabulary': 'standard business language',
                'constraints': 'accuracy, clarity'
            }
        }
        
        self.prompt_template = """Adapt the following content for the {domain} domain.

Domain Profile:
- Tone: {tone}
- Key Vocabulary: {vocabulary}
- Constraints: {constraints}

Original content:
{content}

Provide domain-adapted version:"""
    
    def run(self, llm, task: str, context: Dict[str, Any]) -> ModuleResult:
        """Execute domain adaptation."""
        import time
        start = time.time()
        
        # Detect or use specified domain
        domain = context.get('domain', 'general')
        
        # Auto-detect domain if not specified
        if domain == 'general':
            task_lower = task.lower()
            for domain_key in self.domain_profiles.keys():
                if domain_key in task_lower:
                    domain = domain_key
                    break
        
        # Get domain profile
        profile = self.domain_profiles.get(domain, self.domain_profiles['general'])
        
        # Build adaptation prompt
        prompt = self.prompt_template.format(
            domain=domain,
            tone=profile['tone'],
            vocabulary=profile['vocabulary'],
            constraints=profile['constraints'],
            content=task
        )
        
        try:
            response = llm.generate(prompt)
            latency = time.time() - start
            
            # Validate response is non-empty and different from input
            success = len(response) > 50 and response != task
            
            metrics = {
                'success': success,
                'latency': latency,
                'domain': domain,
                'version': self.version
            }
            
            return ModuleResult(
                output=response,
                passed=success,
                metrics=metrics
            )
            
        except Exception as e:
            return ModuleResult(
                output=f"Domain adaptation failed: {str(e)}",
                passed=False,
                metrics={'error': str(e), 'version': self.version}
            )
