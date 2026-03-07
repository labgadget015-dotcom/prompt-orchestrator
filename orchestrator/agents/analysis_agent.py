"""Analysis Agent — analyzes structured datasets and produces business insights.

Loads its system prompt from prompts/agent-instructions/analysis-agent.md.
Primary path: routes data through CoreAnalysisBridge (ai-analyze-think-act-core).
Secondary path: sends data directly to Claude when core is unavailable.
Fallback: returns descriptive statistics when neither is available.
"""

from __future__ import annotations

import json
import logging
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    anthropic = None  # type: ignore[assignment]
    _ANTHROPIC_AVAILABLE = False

from orchestrator.core_bridge import CoreAnalysisBridge, BridgeUnavailableError, _CORE_AVAILABLE

_PROMPT_PATH = (
    Path(__file__).parent.parent.parent / "prompts" / "agent-instructions" / "analysis-agent.md"
)


# --------------------------------------------------------------------------- #
# Data models                                                                  #
# --------------------------------------------------------------------------- #
@dataclass
class AnalysisInsight:
    finding: str
    evidence: str
    confidence: float = 1.0


@dataclass
class AnalysisRecommendation:
    action: str
    priority: str  # "high" | "medium" | "low"
    impact: str


@dataclass
class DataQuality:
    issues: List[str] = field(default_factory=list)
    completeness: float = 1.0


@dataclass
class AnalysisResult:
    """Structured output from AnalysisAgent."""
    summary: str
    insights: List[AnalysisInsight] = field(default_factory=list)
    recommendations: List[AnalysisRecommendation] = field(default_factory=list)
    data_quality: DataQuality = field(default_factory=DataQuality)
    source: str = "core"  # "core" | "llm" | "stats"


# --------------------------------------------------------------------------- #
# Statistical fallback                                                         #
# --------------------------------------------------------------------------- #
def _stats_fallback(data: List[Dict[str, Any]]) -> AnalysisResult:
    """Return basic descriptive stats when no LLM/core is available."""
    if not data:
        return AnalysisResult(
            summary="No data provided.",
            source="stats",
            data_quality=DataQuality(issues=["Empty dataset"], completeness=0.0),
        )

    numeric_cols: Dict[str, List[float]] = {}
    null_counts: Dict[str, int] = {}
    total = len(data)

    for row in data:
        for k, v in row.items():
            null_counts.setdefault(k, 0)
            numeric_cols.setdefault(k, [])
            if v is None:
                null_counts[k] += 1
            else:
                try:
                    numeric_cols[k].append(float(v))
                except (TypeError, ValueError):
                    pass

    insights = []
    for col, vals in numeric_cols.items():
        if len(vals) < 2:
            continue
        mean = statistics.mean(vals)
        stdev = statistics.stdev(vals)
        insights.append(
            AnalysisInsight(
                finding=f"{col}: mean={mean:.2f}, stdev={stdev:.2f}, n={len(vals)}",
                evidence=f"Computed from {len(vals)}/{total} non-null rows",
                confidence=1.0,
            )
        )

    quality_issues = [
        f"{col}: {cnt} nulls ({cnt/total:.0%})"
        for col, cnt in null_counts.items()
        if cnt > 0
    ]
    completeness = 1.0 - (sum(null_counts.values()) / max(total * len(null_counts), 1))

    return AnalysisResult(
        summary=f"Descriptive statistics for {total} rows, {len(numeric_cols)} numeric columns.",
        insights=insights,
        data_quality=DataQuality(issues=quality_issues, completeness=completeness),
        source="stats",
    )


# --------------------------------------------------------------------------- #
# AnalysisAgent                                                                #
# --------------------------------------------------------------------------- #
class AnalysisAgent:
    """Analyzes datasets and produces structured business insights.

    Priority order:
    1. CoreAnalysisBridge (ai-analyze-think-act-core) when available
    2. Direct Claude call when core unavailable but API key present
    3. Descriptive statistics fallback

    Usage::

        agent = AnalysisAgent(api_key="sk-ant-...")
        result = agent.analyze(
            data=[{"date": "2024-01", "revenue": 50000}, ...],
            analysis_type="ecommerce",
        )
        print(result.summary)
        for rec in result.recommendations:
            print(rec.priority, rec.action)
    """

    ANALYSIS_TYPES = ("ecommerce", "forecast", "segmentation", "anomaly")

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-haiku-20241022",
        max_tokens: int = 2048,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self._system_prompt = self._load_system_prompt()
        self._bridge = CoreAnalysisBridge()

        self._client: Optional[Any] = None
        if _ANTHROPIC_AVAILABLE and api_key:
            self._client = anthropic.Anthropic(api_key=api_key)
            logger.info("AnalysisAgent: LLM path available (%s)", model)

        if _CORE_AVAILABLE:
            logger.info("AnalysisAgent: CoreAnalysisBridge available")
        else:
            logger.info("AnalysisAgent: core unavailable, will use LLM or stats fallback")

    # ---------------------------------------------------------------------- #
    # Public API                                                               #
    # ---------------------------------------------------------------------- #
    def analyze(
        self,
        data: Union[List[Dict[str, Any]], str],
        analysis_type: str = "ecommerce",
        focus: Optional[str] = None,
    ) -> AnalysisResult:
        """Analyze data and return structured insights.

        Args:
            data: List of dicts, JSON string, or CSV string.
            analysis_type: One of ecommerce/forecast/segmentation/anomaly.
            focus: Optional specific question to answer.

        Returns:
            AnalysisResult with summary, insights, recommendations, data_quality.
        """
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                data = self._parse_csv(data)

        if not data:
            return AnalysisResult(
                summary="No data to analyze.",
                source="stats",
                data_quality=DataQuality(issues=["Empty dataset"], completeness=0.0),
            )

        # 1. Try CoreAnalysisBridge
        if _CORE_AVAILABLE:
            try:
                return self._core_analyze(data, analysis_type, focus)
            except (BridgeUnavailableError, Exception) as exc:
                logger.warning("CoreAnalysisBridge failed (%s) — trying LLM path", exc)

        # 2. Try direct LLM
        if self._client is not None:
            try:
                return self._llm_analyze(data, analysis_type, focus)
            except Exception as exc:
                logger.warning("LLM analysis failed (%s) — using stats fallback", exc)

        # 3. Stats fallback
        return _stats_fallback(data)

    # ---------------------------------------------------------------------- #
    # Core path                                                                #
    # ---------------------------------------------------------------------- #
    def _core_analyze(self, data, analysis_type, focus):
        import pandas as pd
        df = pd.DataFrame(data)
        raw = self._bridge.execute(data=df, analysis_type=analysis_type)
        # CoreAnalysisBridge returns a dict; map to AnalysisResult
        insights = [
            AnalysisInsight(
                finding=i.get("finding", str(i)),
                evidence=i.get("evidence", ""),
                confidence=float(i.get("confidence", 1.0)),
            )
            for i in raw.get("insights", [])
        ]
        recommendations = [
            AnalysisRecommendation(
                action=r.get("action", str(r)),
                priority=r.get("priority", "medium"),
                impact=r.get("impact", ""),
            )
            for r in raw.get("recommendations", [])
        ]
        return AnalysisResult(
            summary=raw.get("summary", "Analysis complete."),
            insights=insights,
            recommendations=recommendations,
            data_quality=DataQuality(
                issues=raw.get("data_quality", {}).get("issues", []),
                completeness=raw.get("data_quality", {}).get("completeness", 1.0),
            ),
            source="core",
        )

    # ---------------------------------------------------------------------- #
    # LLM path                                                                 #
    # ---------------------------------------------------------------------- #
    def _llm_analyze(self, data, analysis_type, focus):
        user_content = f"Analysis type: {analysis_type}\n"
        if focus:
            user_content += f"Focus: {focus}\n"
        user_content += f"\nData ({len(data)} rows):\n{json.dumps(data[:50], indent=2)}"
        if len(data) > 50:
            user_content += f"\n... ({len(data) - 50} more rows truncated)"

        response = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self._system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        raw = json.loads(response.content[0].text)

        insights = [
            AnalysisInsight(
                finding=i["finding"],
                evidence=i.get("evidence", ""),
                confidence=float(i.get("confidence", 1.0)),
            )
            for i in raw.get("insights", [])
        ]
        recommendations = [
            AnalysisRecommendation(
                action=r["action"],
                priority=r.get("priority", "medium"),
                impact=r.get("impact", ""),
            )
            for r in raw.get("recommendations", [])
        ]
        return AnalysisResult(
            summary=raw.get("summary", ""),
            insights=insights,
            recommendations=recommendations,
            data_quality=DataQuality(
                issues=raw.get("data_quality", {}).get("issues", []),
                completeness=float(raw.get("data_quality", {}).get("completeness", 1.0)),
            ),
            source="llm",
        )

    # ---------------------------------------------------------------------- #
    # Helpers                                                                  #
    # ---------------------------------------------------------------------- #
    @staticmethod
    def _parse_csv(text: str) -> List[Dict[str, Any]]:
        import csv, io
        reader = csv.DictReader(io.StringIO(text.strip()))
        return list(reader)

    @staticmethod
    def _load_system_prompt() -> str:
        if _PROMPT_PATH.exists():
            return _PROMPT_PATH.read_text(encoding="utf-8")
        logger.warning("analysis-agent.md not found at %s — using minimal prompt", _PROMPT_PATH)
        return (
            "You are a data analysis assistant. Analyze the provided data and return "
            "a JSON object with keys: summary (string), insights (array of {finding, evidence, confidence}), "
            "recommendations (array of {action, priority, impact}), "
            "data_quality ({issues: [], completeness: float})."
        )
