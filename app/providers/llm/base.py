from __future__ import annotations

from abc import ABC, abstractmethod

from app.providers.llm.models import (
    ComposeReportLLMRequest,
    ComposeReportLLMResponse,
    PlanLLMRequest,
    PlanLLMResponse,
    SummarizeLLMRequest,
    SummarizeLLMResponse,
)


class LLMProvider(ABC):
    @abstractmethod
    def plan_research(self, request: PlanLLMRequest) -> PlanLLMResponse:
        raise NotImplementedError

    @abstractmethod
    def summarize_source(self, request: SummarizeLLMRequest) -> SummarizeLLMResponse:
        raise NotImplementedError

    @abstractmethod
    def compose_report(self, request: ComposeReportLLMRequest) -> ComposeReportLLMResponse:
        raise NotImplementedError
