"""Claude API client for the Prompt Orchestrator."""

import os
from typing import Optional
import anthropic


class ClaudeClient:
    """Anthropic Claude client implementing the orchestrator LLM interface.

    Drop-in replacement for OllamaClient. Uses claude-opus-4-6 with a
    cached system prompt to reduce costs across repeated module calls
    within a session.

    Usage:
        llm = ClaudeClient()                        # reads ANTHROPIC_API_KEY from env
        llm = ClaudeClient(api_key="sk-ant-...")    # explicit key
        response = llm.generate("your prompt")      # returns str
    """

    _SYSTEM_PROMPT = (
        "You are a specialized AI assistant embedded in a multi-stage prompt orchestration pipeline. "
        "Each request you receive is one step in a structured workflow — GOLDEN analysis, domain "
        "adaptation, chain-of-thought reasoning, bias detection, or verification. "
        "Follow the output format specified in each prompt precisely. "
        "Be thorough but concise. Your output feeds directly into the next pipeline stage."
    )

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-opus-4-6"):
        self.model = model
        self.client = anthropic.Anthropic(
            api_key=api_key or os.environ["ANTHROPIC_API_KEY"]
        )
        self._tokens_used = 0
        self._cache_read_tokens = 0
        self._cache_write_tokens = 0
        self._call_count = 0

    def generate(self, prompt: str) -> str:
        """Generate a response from Claude.

        Implements the single-method LLM interface expected by all
        orchestrator modules. The system prompt is sent with
        cache_control so it is written to cache on the first call and
        read from cache (~10% cost) on every subsequent call.
        """
        with self.client.messages.stream(
            model=self.model,
            max_tokens=16000,
            system=[{
                "type": "text",
                "text": self._SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            message = stream.get_final_message()

        self._tokens_used += message.usage.input_tokens + message.usage.output_tokens
        self._cache_read_tokens += getattr(message.usage, "cache_read_input_tokens", 0) or 0
        self._cache_write_tokens += getattr(message.usage, "cache_creation_input_tokens", 0) or 0
        self._call_count += 1

        return next((b.text for b in message.content if b.type == "text"), "")

    def stats(self) -> dict:
        """Return token usage stats for the current session."""
        return {
            "calls": self._call_count,
            "tokens_used": self._tokens_used,
            "cache_read_tokens": self._cache_read_tokens,
            "cache_write_tokens": self._cache_write_tokens,
        }
