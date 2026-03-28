"""Content Synthesis Module.

Used in the creative chain to combine domain-adapted content into a
polished, cohesive final output.
"""

from typing import Dict, Any
import sys
sys.path.append('../..')
from orchestrator.core import ModuleResult


class ContentSynthesizer:
    """Synthesizes and refines content into a polished creative output."""

    version = "v1.0"
    category = ["CREATIVE", "SYNTHESIS"]

    def __init__(self):
        self.prompt_template = """Synthesize the following content into a polished, cohesive final output.

Your synthesis should:
1. **Unify**: Merge all ideas into a single, flowing narrative
2. **Elevate**: Strengthen weak sections and sharpen the core message
3. **Structure**: Ensure logical flow with a clear opening, body, and conclusion
4. **Refine**: Remove redundancy and tighten language without losing substance

Original task: {task}

Content to synthesize:
{content}

Produce the final synthesized output:"""

    def run(self, llm, input_data, context: Dict[str, Any]) -> ModuleResult:
        """Execute content synthesis."""
        import time
        start = time.time()

        content = str(input_data)
        task = context.get('original_task', 'Unknown')

        prompt = self.prompt_template.format(task=task, content=content)

        try:
            response = llm.generate(prompt)
            latency = time.time() - start

            # Success if output is substantive and distinct from input
            success = len(response.strip()) > 100 and response.strip() != content.strip()

            metrics = {
                'success': success,
                'latency': latency,
                'input_length': len(content),
                'output_length': len(response),
                'version': self.version,
            }

            return ModuleResult(output=response, passed=success, metrics=metrics)

        except Exception as e:
            return ModuleResult(
                output=f"Synthesis failed: {str(e)}",
                passed=False,
                metrics={'error': str(e), 'version': self.version},
            )
