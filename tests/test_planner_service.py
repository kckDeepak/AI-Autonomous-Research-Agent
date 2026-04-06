from __future__ import annotations

from app.modules.planner.service import PlannerService
from app.providers.llm.base import LLMProvider
from app.providers.llm.models import (
    ComposeReportLLMRequest,
    ComposeReportLLMResponse,
    PlanLLMRequest,
    PlanLLMResponse,
    SummarizeLLMRequest,
    SummarizeLLMResponse,
)
from app.schemas.research_plan import RuntimeConstraints


class FakePlannerProvider(LLMProvider):
    def plan_research(self, request: PlanLLMRequest) -> PlanLLMResponse:
        return PlanLLMResponse(
            subtopics=[" AI agents ", "ai agents", "x"],
            search_queries=["   ", "AI agent architecture patterns", "AI agent architecture patterns"],
            depth_strategy="   ",
            estimated_source_count=99,
            rationale="            ",
        )

    def summarize_source(self, request: SummarizeLLMRequest) -> SummarizeLLMResponse:
        raise NotImplementedError

    def compose_report(self, request: ComposeReportLLMRequest) -> ComposeReportLLMResponse:
        raise NotImplementedError


class FailingPlannerProvider(LLMProvider):
    def plan_research(self, request: PlanLLMRequest) -> PlanLLMResponse:
        raise RuntimeError("simulated planner parsing failure")

    def summarize_source(self, request: SummarizeLLMRequest) -> SummarizeLLMResponse:
        raise NotImplementedError

    def compose_report(self, request: ComposeReportLLMRequest) -> ComposeReportLLMResponse:
        raise NotImplementedError


def test_planner_service_applies_caps_and_fallbacks() -> None:
    service = PlannerService(FakePlannerProvider())
    constraints = RuntimeConstraints(max_sources=12, max_queries_per_plan=5, llm_token_budget_per_run=25000)

    plan = service.create_plan(
        query="Enterprise autonomous research agent architecture",
        depth="standard",
        constraints=constraints,
    )

    assert plan.estimated_source_count == 12
    assert len(plan.search_queries) <= 5
    assert plan.depth_strategy == "standard coverage strategy"
    assert plan.rationale == "Plan generated with bounded defaults."
    assert len(plan.subtopics) >= 1
    assert all(len(item) >= 4 for item in plan.subtopics)


def test_planner_service_gracefully_falls_back_when_provider_fails() -> None:
    service = PlannerService(FailingPlannerProvider())
    constraints = RuntimeConstraints(max_sources=12, max_queries_per_plan=5, llm_token_budget_per_run=25000)

    plan = service.create_plan(
        query="Enterprise autonomous research agent architecture",
        depth="standard",
        constraints=constraints,
    )

    assert plan.estimated_source_count == 10
    assert plan.depth_strategy == "standard coverage strategy"
    assert plan.rationale == "Plan generated with bounded defaults."
    assert len(plan.search_queries) <= 5
    assert len(plan.search_queries) >= 1
