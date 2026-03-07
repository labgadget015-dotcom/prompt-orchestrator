"""Consulting Agent — e-commerce business advisor.

Loads its system prompt from prompts/agent-instructions/consulting-agent.md.
Synthesizes metrics (conversion rate, cart abandonment, LTV:CAC, forecast MAPE)
into a structured Situation / Complication / Recommendation / Next-steps report.

Priority chain: Claude LLM → rule-based benchmarks fallback.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    anthropic = None  # type: ignore[assignment]
    _ANTHROPIC_AVAILABLE = False

_PROMPT_PATH = (
    Path(__file__).parent.parent.parent
    / "prompts" / "agent-instructions" / "consulting-agent.md"
)

# Industry benchmarks
_BENCHMARKS = {
    "conversion_rate": {"low": 0.01, "high": 0.08, "avg": 0.03},
    "cart_abandonment": {"warn": 0.80, "avg": 0.70},
    "ltv_cac_ratio": {"min_healthy": 3.0},
    "forecast_mape": {"max_reliable": 0.20},
}


# --------------------------------------------------------------------------- #
# Data models                                                                  #
# --------------------------------------------------------------------------- #
@dataclass
class EcommerceMetrics:
    """Input metrics for the consulting agent."""
    revenue: Optional[float] = None
    orders: Optional[int] = None
    conversion_rate: Optional[float] = None      # 0.0–1.0
    cart_abandonment_rate: Optional[float] = None  # 0.0–1.0
    ltv: Optional[float] = None                  # customer lifetime value
    cac: Optional[float] = None                  # customer acquisition cost
    forecast_mape: Optional[float] = None        # forecast error 0.0–1.0
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def ltv_cac_ratio(self) -> Optional[float]:
        if self.ltv and self.cac and self.cac > 0:
            return self.ltv / self.cac
        return None


@dataclass
class ConsultingRecommendation:
    action: str
    type: str  # "quick_win" | "strategic"
    metric: str
    expected_impact: str
    priority: str  # "high" | "medium" | "low"


@dataclass
class ConsultingReport:
    """Structured consulting output."""
    situation: str
    complication: str
    recommendations: List[ConsultingRecommendation] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)  # metrics needing attention
    source: str = "llm"  # "llm" | "rules"


# --------------------------------------------------------------------------- #
# Rule-based fallback                                                          #
# --------------------------------------------------------------------------- #
def _benchmark_report(metrics: EcommerceMetrics) -> ConsultingReport:
    """Generate a report using industry benchmark comparisons."""
    flags: List[str] = []
    recs: List[ConsultingRecommendation] = []
    situation_parts: List[str] = []
    complication_parts: List[str] = []

    if metrics.conversion_rate is not None:
        cr = metrics.conversion_rate
        situation_parts.append(f"Conversion rate: {cr:.1%}")
        b = _BENCHMARKS["conversion_rate"]
        if cr < b["low"]:
            flags.append(f"conversion_rate={cr:.1%} (critically below industry avg {b['avg']:.0%})")
            complication_parts.append("Conversion rate is critically low — most visitors leave without buying.")
            recs.append(ConsultingRecommendation(
                action="Audit checkout UX and reduce form fields",
                type="quick_win", metric="conversion_rate",
                expected_impact="0.5–1% lift in conversions", priority="high",
            ))
        elif cr > b["high"]:
            flags.append(f"conversion_rate={cr:.1%} (unusually high — verify tracking)")
            complication_parts.append("Conversion rate is unusually high; verify analytics tracking is correct.")

    if metrics.cart_abandonment_rate is not None:
        ca = metrics.cart_abandonment_rate
        situation_parts.append(f"Cart abandonment: {ca:.1%}")
        if ca > _BENCHMARKS["cart_abandonment"]["warn"]:
            flags.append(f"cart_abandonment={ca:.1%} (above 80% threshold)")
            complication_parts.append("Cart abandonment exceeds 80% — UX or pricing friction suspected.")
            recs.append(ConsultingRecommendation(
                action="Implement cart abandonment email sequence (3-email, 1h/24h/72h)",
                type="quick_win", metric="cart_abandonment_rate",
                expected_impact="5–15% cart recovery", priority="high",
            ))

    ratio = metrics.ltv_cac_ratio
    if ratio is not None:
        situation_parts.append(f"LTV:CAC = {ratio:.1f}x")
        if ratio < _BENCHMARKS["ltv_cac_ratio"]["min_healthy"]:
            flags.append(f"ltv_cac_ratio={ratio:.1f} (below healthy 3:1)")
            complication_parts.append(f"LTV:CAC of {ratio:.1f}x is below the 3:1 minimum — acquisition costs too high or retention too low.")
            recs.append(ConsultingRecommendation(
                action="Launch retention program: loyalty points, post-purchase email nurture",
                type="strategic", metric="ltv_cac_ratio",
                expected_impact="Improve LTV by 20–30% over 6 months", priority="high",
            ))

    if metrics.forecast_mape is not None:
        mape = metrics.forecast_mape
        situation_parts.append(f"Forecast MAPE: {mape:.1%}")
        if mape > _BENCHMARKS["forecast_mape"]["max_reliable"]:
            flags.append(f"forecast_mape={mape:.1%} (above 20% — unreliable)")
            complication_parts.append("Forecast accuracy is below threshold — inventory planning may be unreliable.")
            recs.append(ConsultingRecommendation(
                action="Collect more historical data or add external regressors to forecast model",
                type="strategic", metric="forecast_mape",
                expected_impact="Reduce MAPE below 15%", priority="medium",
            ))

    if not situation_parts:
        situation_parts.append("Insufficient metrics provided for full analysis.")
    if not complication_parts:
        complication_parts.append("No critical issues detected based on available metrics.")

    next_steps = [
        "Review flagged metrics weekly",
        "A/B test highest-priority recommendation first",
        "Re-run analysis after 30 days of changes",
    ]

    return ConsultingReport(
        situation=" | ".join(situation_parts),
        complication=" ".join(complication_parts),
        recommendations=recs,
        next_steps=next_steps,
        flags=flags,
        source="rules",
    )


# --------------------------------------------------------------------------- #
# ConsultingAgent                                                              #
# --------------------------------------------------------------------------- #
class ConsultingAgent:
    """E-commerce consulting advisor.

    Usage::

        agent = ConsultingAgent(api_key="sk-ant-...")
        report = agent.advise(EcommerceMetrics(
            revenue=125000,
            conversion_rate=0.018,
            cart_abandonment_rate=0.83,
            ltv=450, cac=180,
        ))
        print(report.situation)
        print(report.complication)
        for rec in report.recommendations:
            print(f"[{rec.type}] {rec.action}")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-haiku-20241022",
        max_tokens: int = 2048,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self._system_prompt = self._load_system_prompt()

        self._client: Optional[Any] = None
        if _ANTHROPIC_AVAILABLE and api_key:
            self._client = anthropic.Anthropic(api_key=api_key)
            logger.info("ConsultingAgent: using Claude (%s)", model)
        else:
            logger.info("ConsultingAgent: using benchmark-based fallback")

    def advise(self, metrics: EcommerceMetrics) -> ConsultingReport:
        """Generate a consulting report for the given metrics."""
        if self._client is not None:
            try:
                return self._llm_advise(metrics)
            except Exception as exc:
                logger.warning("LLM advise failed (%s) — using benchmark fallback", exc)
        return _benchmark_report(metrics)

    def _llm_advise(self, metrics: EcommerceMetrics) -> ConsultingReport:
        data = {
            "revenue": metrics.revenue,
            "orders": metrics.orders,
            "conversion_rate": f"{metrics.conversion_rate:.1%}" if metrics.conversion_rate else None,
            "cart_abandonment_rate": f"{metrics.cart_abandonment_rate:.1%}" if metrics.cart_abandonment_rate else None,
            "ltv": metrics.ltv,
            "cac": metrics.cac,
            "ltv_cac_ratio": f"{metrics.ltv_cac_ratio:.2f}" if metrics.ltv_cac_ratio else None,
            "forecast_mape": f"{metrics.forecast_mape:.1%}" if metrics.forecast_mape else None,
            **metrics.extra,
        }
        user_msg = (
            "Here are the current e-commerce metrics. Provide your consulting report.\n\n"
            + json.dumps({k: v for k, v in data.items() if v is not None}, indent=2)
        )

        response = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self._system_prompt + "\n\nRespond as JSON with keys: situation, complication, recommendations (array of {action, type, metric, expected_impact, priority}), next_steps (array of strings), flags (array of strings).",
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = json.loads(response.content[0].text)

        recs = [
            ConsultingRecommendation(
                action=r["action"],
                type=r.get("type", "strategic"),
                metric=r.get("metric", ""),
                expected_impact=r.get("expected_impact", ""),
                priority=r.get("priority", "medium"),
            )
            for r in raw.get("recommendations", [])
        ]
        return ConsultingReport(
            situation=raw.get("situation", ""),
            complication=raw.get("complication", ""),
            recommendations=recs,
            next_steps=raw.get("next_steps", []),
            flags=raw.get("flags", []),
            source="llm",
        )

    @staticmethod
    def _load_system_prompt() -> str:
        if _PROMPT_PATH.exists():
            return _PROMPT_PATH.read_text(encoding="utf-8")
        logger.warning("consulting-agent.md not found — using minimal prompt")
        return (
            "You are an e-commerce consulting assistant. Analyze the provided metrics "
            "and give a structured Situation/Complication/Recommendation/Next-steps report."
        )
