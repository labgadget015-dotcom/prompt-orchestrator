"""Triage Agent — classifies items by priority and recommends actions.

Loads its system prompt from prompts/agent-instructions/triage-agent.md.
Uses Claude (via Anthropic SDK) when available; falls back to rule-based
classification so the agent is always runnable without an API key.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Optional LLM backend                                                         #
# --------------------------------------------------------------------------- #
try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    anthropic = None  # type: ignore[assignment]
    _ANTHROPIC_AVAILABLE = False
    logger.warning("anthropic package not installed — triage will use rule-based fallback")

_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "agent-instructions" / "triage-agent.md"


# --------------------------------------------------------------------------- #
# Data models                                                                  #
# --------------------------------------------------------------------------- #
class TriagePriority(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class TriageAction(str, Enum):
    REVIEW_NOW = "review_now"
    REVIEW_LATER = "review_later"
    MUTE = "mute"
    ARCHIVE = "archive"


@dataclass
class TriageItem:
    """A single item to be triaged."""
    id: str
    title: str
    reason: str  # e.g. "mention", "review_requested", "assign", "subscribed"
    repo: str
    author: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TriageResult:
    """Triage outcome for a single item."""
    id: str
    priority: TriagePriority
    action: TriageAction
    reason: str
    source: str = "llm"  # "llm" or "rules"


# --------------------------------------------------------------------------- #
# Rule-based fallback                                                          #
# --------------------------------------------------------------------------- #
_BOT_PATTERNS = re.compile(r"(dependabot|renovate|github-actions|snyk|codecov)\[bot\]", re.I)

_REASON_P1 = {"review_requested", "assign"}
_REASON_P2 = {"mention", "team_mention", "comment", "ci_activity"}


def _rule_based_triage(item: TriageItem) -> TriageResult:
    """Classify a single item using deterministic rules."""
    r = item.reason.lower()

    if r in _REASON_P1:
        priority = TriagePriority.P1
        action = TriageAction.REVIEW_NOW
        explanation = f"Reason '{item.reason}' requires immediate attention"
    elif _BOT_PATTERNS.search(item.author):
        priority = TriagePriority.P3
        action = TriageAction.ARCHIVE
        explanation = f"Bot author '{item.author}' — low signal"
    elif r in _REASON_P2:
        priority = TriagePriority.P2
        action = TriageAction.REVIEW_LATER
        explanation = f"Reason '{item.reason}' — participate when convenient"
    else:
        priority = TriagePriority.P3
        action = TriageAction.MUTE
        explanation = f"Subscribed/low-signal notification"

    return TriageResult(
        id=item.id,
        priority=priority,
        action=action,
        reason=explanation,
        source="rules",
    )


# --------------------------------------------------------------------------- #
# TriageAgent                                                                  #
# --------------------------------------------------------------------------- #
class TriageAgent:
    """Classifies a batch of items using the triage-agent system prompt.

    Usage::

        agent = TriageAgent(api_key="sk-ant-...")
        results = agent.triage([
            TriageItem(id="1", title="Fix auth bug", reason="review_requested",
                       repo="org/backend", author="alice"),
        ])
        for r in results:
            print(r.priority, r.action, r.reason)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-haiku-20241022",
        max_tokens: int = 1024,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self._system_prompt = self._load_system_prompt()

        self._client: Optional[Any] = None
        if _ANTHROPIC_AVAILABLE and api_key:
            self._client = anthropic.Anthropic(api_key=api_key)
            logger.info("TriageAgent: using Claude (%s)", model)
        else:
            logger.info("TriageAgent: using rule-based fallback")

    # ---------------------------------------------------------------------- #
    # Public API                                                               #
    # ---------------------------------------------------------------------- #
    def triage(self, items: List[TriageItem]) -> List[TriageResult]:
        """Triage a list of items. Returns one TriageResult per item."""
        if not items:
            return []
        if self._client is not None:
            try:
                return self._llm_triage(items)
            except Exception as exc:
                logger.warning("LLM triage failed (%s) — falling back to rules", exc)
        return [_rule_based_triage(item) for item in items]

    def triage_one(self, item: TriageItem) -> TriageResult:
        """Triage a single item."""
        return self.triage([item])[0]

    # ---------------------------------------------------------------------- #
    # LLM path                                                                 #
    # ---------------------------------------------------------------------- #
    def _llm_triage(self, items: List[TriageItem]) -> List[TriageResult]:
        user_msg = json.dumps(
            [
                {
                    "id": it.id,
                    "title": it.title,
                    "reason": it.reason,
                    "repo": it.repo,
                    "author": it.author,
                }
                for it in items
            ],
            indent=2,
        )

        response = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self._system_prompt,
            messages=[{"role": "user", "content": user_msg}],
        )

        raw = response.content[0].text
        parsed = json.loads(raw)

        results: List[TriageResult] = []
        for entry in parsed:
            results.append(
                TriageResult(
                    id=entry["id"],
                    priority=TriagePriority(entry["priority"]),
                    action=TriageAction(entry["action"]),
                    reason=entry.get("reason", ""),
                    source="llm",
                )
            )
        return results

    # ---------------------------------------------------------------------- #
    # Helpers                                                                  #
    # ---------------------------------------------------------------------- #
    @staticmethod
    def _load_system_prompt() -> str:
        if _PROMPT_PATH.exists():
            return _PROMPT_PATH.read_text(encoding="utf-8")
        logger.warning("triage-agent.md not found at %s — using minimal prompt", _PROMPT_PATH)
        return (
            "You are a notification triage assistant. "
            "Classify each item as P1/P2/P3 and recommend review_now, review_later, mute, or archive. "
            "Return a JSON array with id, priority, action, reason fields."
        )
