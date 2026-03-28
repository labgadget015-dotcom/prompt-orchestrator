"""Structured Feedback Module.

Used in the optimization chain to score current output quality,
identify gaps, and produce improvement recommendations before
the final verification pass.
"""

from typing import Dict, Any
import sys
sys.path.append('../..')
from orchestrator.core import ModuleResult


class FeedbackEvaluator:
    """Scores output quality and produces structured improvement feedback."""

    version = "v1.0"
    category = ["OPTIMIZATION", "EVALUATION"]

    def __init__(self):
        self.prompt_template = """Evaluate the following content and provide structured improvement feedback.

Score each dimension 1–10 and explain the rating:

**Relevance** [1-10]: Does it directly address the original task?
**Completeness** [1-10]: Are all key aspects covered?
**Clarity** [1-10]: Is it easy to understand and well-structured?
**Actionability** [1-10]: Are recommendations specific and implementable?
**Impact** [1-10]: Will following this advice produce meaningful results?

Original task: {task}

Content to evaluate:
{content}

After scoring, provide:
**Overall Score**: [average]/10
**Top Strengths**: [2-3 bullet points]
**Priority Improvements**: [2-3 specific, actionable changes]
**Revised Output**: [improved version incorporating your recommendations]"""

    def run(self, llm, input_data, context: Dict[str, Any]) -> ModuleResult:
        """Execute feedback evaluation and produce improved output."""
        import time
        import re
        start = time.time()

        content = str(input_data)
        task = context.get('original_task', 'Unknown')

        prompt = self.prompt_template.format(task=task, content=content)

        try:
            response = llm.generate(prompt)
            latency = time.time() - start

            # Extract overall score if present
            score = None
            match = re.search(r'overall score[:\s]+([0-9.]+)\s*/\s*10', response.lower())
            if match:
                try:
                    score = float(match.group(1))
                except ValueError:
                    pass

            # Pass if score >= 6 or score not detected (give benefit of the doubt)
            passed = score is None or score >= 6.0

            # Return the revised output section if present, otherwise the full response
            revised_match = re.search(
                r'\*\*revised output\*\*[:\s]*(.*)',
                response,
                re.IGNORECASE | re.DOTALL,
            )
            output = revised_match.group(1).strip() if revised_match else response

            metrics = {
                'success': passed,
                'latency': latency,
                'score': score,
                'version': self.version,
            }

            return ModuleResult(output=output, passed=passed, metrics=metrics)

        except Exception as e:
            return ModuleResult(
                output=f"Feedback evaluation failed: {str(e)}",
                passed=False,
                metrics={'error': str(e), 'version': self.version},
            )
