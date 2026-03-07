"""Bridge module connecting PromptOrchestrator to ai-analyze-think-act-core.

Soft-imports the core library so that the orchestrator starts correctly even
when the package is not installed.  When the package is absent every call to
``CoreAnalysisBridge.execute`` raises ``BridgeUnavailableError`` instead of
crashing at import time.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    from core.analysis import analyze, AnalysisRequest
    from core.recommendations import recommend, RecommendationRequest
    _CORE_AVAILABLE = True
except ImportError:
    # Keep names defined so tests can patch them without create=True
    analyze = None  # type: ignore[assignment]
    AnalysisRequest = None  # type: ignore[assignment]
    recommend = None  # type: ignore[assignment]
    RecommendationRequest = None  # type: ignore[assignment]
    _CORE_AVAILABLE = False
    logger.warning(
        "ai-analyze-think-act-core is not installed — CoreAnalysisBridge "
        "will be unavailable.  Install with: "
        "pip install git+https://github.com/labgadget015-dotcom/"
        "ai-analyze-think-act-core.git@main"
    )


class BridgeUnavailableError(RuntimeError):
    """Raised when ai-analyze-think-act-core is not installed."""


class CoreAnalysisBridge:
    """Wraps the ai-analyze-think-act-core ingest→analyze→recommend pipeline
    as a prompt module compatible with :class:`~orchestrator.core.PromptOrchestrator`.

    Registration example::

        from orchestrator.core_bridge import CoreAnalysisBridge

        bridge = CoreAnalysisBridge()
        orchestrator.register_module("core_analysis", bridge)

    The orchestrator will call ``bridge.run(llm, prompt, context)`` which
    internally delegates to :meth:`execute`.
    """

    MODULE_NAME = "core_analysis"
    VERSION = "v1.0"

    # ------------------------------------------------------------------
    # PromptOrchestrator module interface
    # ------------------------------------------------------------------

    def run(self, llm, input_data: Any, context: Dict[str, Any]):
        """Adapter so CoreAnalysisBridge can be registered as a standard module.

        ``llm`` is accepted for API compatibility but not used — the core
        library manages its own LLM calls.

        Returns a :class:`~orchestrator.core.ModuleResult`.
        """
        from orchestrator.core import ModuleResult  # local import avoids circular dep
        import time

        start = time.time()
        prompt = str(input_data)

        try:
            result = self.execute(prompt, context)
            latency = time.time() - start
            return ModuleResult(
                output=result,
                passed=True,
                metrics={"success": True, "latency": latency, "version": self.VERSION},
            )
        except BridgeUnavailableError as exc:
            return ModuleResult(
                output=str(exc),
                passed=False,
                metrics={"error": "bridge_unavailable", "version": self.VERSION},
            )
        except Exception as exc:
            logger.exception("CoreAnalysisBridge.run failed")
            return ModuleResult(
                output=str(exc),
                passed=False,
                metrics={"error": str(exc), "version": self.VERSION},
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run analyze → recommend pipeline against a prompt and optional context.

        The bridge avoids requiring a real :class:`pandas.DataFrame` by
        passing the prompt text via the ``context`` field of
        :class:`~core.analysis.AnalysisRequest` and supplying an empty
        DataFrame as a no-data sentinel.

        Parameters
        ----------
        prompt:
            The user prompt / task description.
        context:
            Optional supplementary context dict.  Recognised keys:

            * ``goal`` (str) — analysis goal forwarded to ``core.analyze``
              (default: ``"general"``).
            * ``constraints`` (dict) — passed through to ``AnalysisRequest``
              (default: ``{}``).
            * ``budget`` (float) — budget for the recommend step
              (default: ``0.0``).
            * ``llm_model`` (str) — LLM model name
              (default: ``"gpt-4o"``).

        Returns
        -------
        dict
            ``{"analysis": <AnalysisResult as dict>, "recommendations": [...]}``.

        Raises
        ------
        BridgeUnavailableError
            When ai-analyze-think-act-core is not installed.
        """
        if not _CORE_AVAILABLE:
            raise BridgeUnavailableError(
                "ai-analyze-think-act-core is not installed.  "
                "Install with: pip install "
                "git+https://github.com/labgadget015-dotcom/"
                "ai-analyze-think-act-core.git@main"
            )

        context = context or {}
        goal = context.get("goal", "general")
        constraints = context.get("constraints", {})
        budget = float(context.get("budget", 0.0))
        llm_model = context.get("llm_model", "gpt-4o")

        # DataFrame-less call: empty DataFrame + prompt forwarded as ``context``
        import pandas as pd

        analysis_request = AnalysisRequest(
            dataset=pd.DataFrame(),
            goal=goal,
            constraints=constraints,
            llm_model=llm_model,
            context=prompt,
        )

        analysis_result = analyze(analysis_request)

        analysis_dict = {
            "goal": analysis_result.goal,
            "trends": analysis_result.trends,
            "anomalies": analysis_result.anomalies,
            "rankings": analysis_result.rankings,
            "predictions": analysis_result.predictions,
            "diagnosis": analysis_result.diagnosis,
            "metrics_to_watch": analysis_result.metrics_to_watch,
        }

        recommendation_request = RecommendationRequest(
            insights=analysis_dict,
            goal=goal,
            budget=budget,
            llm_model=llm_model,
        )

        recommendations = recommend(recommendation_request)

        recs_serialized = [
            {
                "id": r.id,
                "description": r.description,
                "priority": r.priority.value if hasattr(r.priority, "value") else str(r.priority),
                "effort": r.effort.value if hasattr(r.effort, "value") else str(r.effort),
                "expected_impact_metric": r.expected_impact_metric,
                "rationale": r.rationale,
                "budget_required": r.budget_required,
                "implementation_steps": r.implementation_steps,
            }
            for r in recommendations
        ]

        return {
            "analysis": analysis_dict,
            "recommendations": recs_serialized,
        }

    def get_status(self) -> Dict[str, Any]:
        """Return bridge availability and version metadata.

        Returns
        -------
        dict
            Keys: ``available`` (bool), ``module`` (str), ``version`` (str).
        """
        return {
            "available": _CORE_AVAILABLE,
            "module": self.MODULE_NAME,
            "version": self.VERSION,
        }
