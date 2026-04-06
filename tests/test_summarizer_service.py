from __future__ import annotations

from app.modules.summarizer.service import SummarizerService
from app.providers.llm.base import LLMProvider
from app.providers.llm.models import (
    ComposeReportLLMRequest,
    ComposeReportLLMResponse,
    PlanLLMRequest,
    PlanLLMResponse,
    SummarizeLLMRequest,
    SummarizeLLMResponse,
)
from app.schemas.content import NormalizedDocument


class FakeLLMProvider(LLMProvider):
    def plan_research(self, request: PlanLLMRequest) -> PlanLLMResponse:
        raise NotImplementedError

    def summarize_source(self, request: SummarizeLLMRequest) -> SummarizeLLMResponse:
        if "weak" in request.content.lower():
            return SummarizeLLMResponse(
                summary="Weak source summary.",
                tags=["weak"],
                relevance_score=0.2,
                confidence=0.4,
                key_points=["Low signal"],
            )

        return SummarizeLLMResponse(
            summary="Strong source summary.",
            tags=["market", "policy"],
            relevance_score=0.8,
            confidence=0.85,
            key_points=["Demand growth", "Policy support"],
        )

    def compose_report(self, request: ComposeReportLLMRequest) -> ComposeReportLLMResponse:
        raise NotImplementedError


def test_summarizer_filters_low_relevance_findings() -> None:
    documents = [
        NormalizedDocument(
            url="https://example.com/strong",
            normalized_url="https://example.com/strong",
            source_domain="example.com",
            title="Strong",
            content="strong strong strong",
            chunks=["strong content chunk"],
            word_count=3,
            char_count=20,
        ),
        NormalizedDocument(
            url="https://example.com/weak",
            normalized_url="https://example.com/weak",
            source_domain="example.com",
            title="Weak",
            content="weak weak weak",
            chunks=["weak content chunk"],
            word_count=3,
            char_count=16,
        ),
    ]

    service = SummarizerService(FakeLLMProvider(), min_relevance_score=0.45, max_chunks_per_source=2)
    batch = service.summarize_documents(query="battery recycling market", documents=documents)

    assert len(batch.findings) == 1
    assert len(batch.rejected_findings) == 1
    assert batch.findings[0].relevance_score >= 0.45
    assert batch.rejected_findings[0].relevance_score < 0.45
