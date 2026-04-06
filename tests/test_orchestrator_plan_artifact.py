from __future__ import annotations

import json
from pathlib import Path

from app.orchestrator import ResearchOrchestrator
from app.providers.llm.base import LLMProvider
from app.providers.llm.models import (
    ComposeReportLLMRequest,
    ComposeReportLLMResponse,
    PlanLLMRequest,
    PlanLLMResponse,
    SummarizeLLMRequest,
    SummarizeLLMResponse,
)
from app.schemas.research_plan import PlanRequest
from app.settings import Settings


class FakeProvider(LLMProvider):
    def plan_research(self, request: PlanLLMRequest) -> PlanLLMResponse:
        return PlanLLMResponse(
            subtopics=["Market sizing", "Competitive dynamics"],
            search_queries=["battery recycling market size 2026", "battery recycling policy north america"],
            depth_strategy="balanced breadth and depth",
            estimated_source_count=10,
            rationale="Focuses on market size, regulation, and company landscape.",
        )

    def summarize_source(self, request: SummarizeLLMRequest) -> SummarizeLLMResponse:
        raise NotImplementedError

    def compose_report(self, request: ComposeReportLLMRequest) -> ComposeReportLLMResponse:
        raise NotImplementedError


def test_plan_only_persists_plan_artifact(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    settings = Settings(
        llm_provider="openai",
        openai_api_key="test-key",
        tavily_api_key="x",
        notion_token="x",
        notion_database_id="x",
        gmail_client_id="x",
        gmail_client_secret="x",
        gmail_refresh_token="x",
        gmail_sender_email="x",
    )

    orchestrator = ResearchOrchestrator(settings=settings, provider=FakeProvider())
    response = orchestrator.plan_only(
        PlanRequest(
            query="North America battery recycling market outlook",
            requester_email="analyst@example.com",
            depth="standard",
        )
    )

    artifact_path = Path(response.plan_artifact_path)
    assert artifact_path.exists()

    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == response.run_id
    assert payload["plan"]["search_queries"]
