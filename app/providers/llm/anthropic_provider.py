from __future__ import annotations

from app.providers.llm.base import LLMProvider
from app.providers.llm.models import (
    ComposeReportLLMRequest,
    ComposeReportLLMResponse,
    LLMConfig,
    PlanLLMRequest,
    PlanLLMResponse,
    SummarizeLLMRequest,
    SummarizeLLMResponse,
)


class AnthropicProviderStub(LLMProvider):
    """Compatibility placeholder to keep provider boundaries stable.

    This stub exists so orchestration and business logic do not need to change when
    Anthropic is re-enabled in a future phase.
    """

    def __init__(self, api_key: str | None, config: LLMConfig) -> None:
        self._api_key = api_key
        self._config = config

    def plan_research(self, request: PlanLLMRequest) -> PlanLLMResponse:
        raise NotImplementedError("Anthropic adapter is intentionally stubbed in P2.")

    def summarize_source(self, request: SummarizeLLMRequest) -> SummarizeLLMResponse:
        raise NotImplementedError("Anthropic adapter is intentionally stubbed in P2.")

    def compose_report(self, request: ComposeReportLLMRequest) -> ComposeReportLLMResponse:
        raise NotImplementedError("Anthropic adapter is intentionally stubbed in P2.")
