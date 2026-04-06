from __future__ import annotations

from app.modules.reporting.service import ReportComposerService
from app.providers.llm.base import LLMProvider
from app.providers.llm.models import (
    ComposeReportLLMRequest,
    ComposeReportLLMResponse,
    PlanLLMRequest,
    PlanLLMResponse,
    SummarizeLLMRequest,
    SummarizeLLMResponse,
)
from app.schemas.finding import Finding


class FakeProvider(LLMProvider):
    def plan_research(self, request: PlanLLMRequest) -> PlanLLMResponse:
        raise NotImplementedError

    def summarize_source(self, request: SummarizeLLMRequest) -> SummarizeLLMResponse:
        raise NotImplementedError

    def compose_report(self, request: ComposeReportLLMRequest) -> ComposeReportLLMResponse:
        return ComposeReportLLMResponse(
            tldr="Strong momentum in battery recycling across demand and policy signals.",
            executive_summary="The source set indicates favorable economics and policy tailwinds.",
            markdown="",
            html="",
            references=[],
        )


class FailingReportProvider(LLMProvider):
    def plan_research(self, request: PlanLLMRequest) -> PlanLLMResponse:
        raise NotImplementedError

    def summarize_source(self, request: SummarizeLLMRequest) -> SummarizeLLMResponse:
        raise NotImplementedError

    def compose_report(self, request: ComposeReportLLMRequest) -> ComposeReportLLMResponse:
        raise RuntimeError("Request timed out.")


def test_report_composer_builds_citations_and_sections() -> None:
    findings = [
        Finding(
            title="Market Growth",
            url="https://example.com/a",
            summary="Growth remains strong.",
            tags=["market"],
            relevance_score=0.81,
            confidence=0.84,
            key_points=["Demand is expanding"],
        ),
        Finding(
            title="Policy Signals",
            url="https://example.com/b",
            summary="Policy support is improving.",
            tags=["policy"],
            relevance_score=0.77,
            confidence=0.79,
            key_points=["Regulatory support increasing"],
        ),
    ]

    composer = ReportComposerService(FakeProvider())
    report = composer.compose(
        query="Battery recycling outlook",
        run_id="run-1",
        findings=findings,
    )

    assert "## Key Findings" in report.markdown
    assert "## Deep Dives" in report.markdown
    assert "## References" in report.markdown
    assert "[1]" in report.markdown
    assert len(report.references) == 2
    assert len(report.citation_index) == 2
    assert len(report.claim_citations) >= 2
    assert "<h2>References</h2>" in report.html


def test_report_composer_falls_back_when_provider_times_out() -> None:
    findings = [
        Finding(
            title="Market Growth",
            url="https://example.com/a",
            summary="Growth remains strong.",
            tags=["market"],
            relevance_score=0.81,
            confidence=0.84,
            key_points=["Demand is expanding"],
        )
    ]

    composer = ReportComposerService(FailingReportProvider())
    report = composer.compose(
        query="Battery recycling outlook",
        run_id="run-timeout",
        findings=findings,
    )

    assert report.tldr.startswith("Top signal:")
    assert "The analysis for 'Battery recycling outlook'" in report.executive_summary
    assert "## Key Findings" in report.markdown
    assert report.references == ["https://example.com/a"]
