from __future__ import annotations

import json
from pathlib import Path

from app.modules.search.service import SearchService
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
from app.schemas.search import CandidateCollection, SearchCandidate
from app.settings import Settings


class FakeProvider(LLMProvider):
    def plan_research(self, request: PlanLLMRequest) -> PlanLLMResponse:
        return PlanLLMResponse(
            subtopics=["Market size", "Regulation", "Competition"],
            search_queries=[
                "battery recycling market size north america",
                "battery recycling policy north america",
            ],
            depth_strategy="balanced breadth and depth",
            estimated_source_count=10,
            rationale="Coverage balances market metrics with policy and competition.",
        )

    def summarize_source(self, request: SummarizeLLMRequest) -> SummarizeLLMResponse:
        raise NotImplementedError

    def compose_report(self, request: ComposeReportLLMRequest) -> ComposeReportLLMResponse:
        raise NotImplementedError


class FakeSearchService(SearchService):
    def __init__(self) -> None:
        pass

    def collect_candidates(
        self,
        *,
        original_query: str,
        search_queries: list[str],
        max_candidates: int,
    ) -> CandidateCollection:
        return CandidateCollection(
            raw_result_count=4,
            deduped_result_count=2,
            candidates=[
                SearchCandidate(
                    url="https://example.com/report",
                    normalized_url="https://example.com/report",
                    title="Battery Recycling Market Report",
                    snippet="Outlook and growth indicators.",
                    query=search_queries[0],
                    source_domain="example.com",
                    query_rank=1,
                    relevance_score=0.74,
                    global_rank=1,
                ),
                SearchCandidate(
                    url="https://news.site/analysis",
                    normalized_url="https://news.site/analysis",
                    title="Policy and Regulation Analysis",
                    snippet="Policy backdrop and timelines.",
                    query=search_queries[1],
                    source_domain="news.site",
                    query_rank=1,
                    relevance_score=0.68,
                    global_rank=2,
                ),
            ],
        )


def test_plan_and_collect_candidates_persists_artifacts(tmp_path: Path, monkeypatch) -> None:
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

    orchestrator = ResearchOrchestrator(
        settings=settings,
        provider=FakeProvider(),
        search_service=FakeSearchService(),
    )

    response = orchestrator.plan_and_collect_candidates(
        PlanRequest(
            query="North America battery recycling market outlook",
            requester_email="analyst@example.com",
            depth="standard",
        )
    )

    plan_artifact = Path(response.plan_artifact_path)
    candidate_artifact = Path(response.candidate_artifact_path)
    assert plan_artifact.exists()
    assert candidate_artifact.exists()
    assert len(response.candidates) == 2

    payload = json.loads(candidate_artifact.read_text(encoding="utf-8"))
    assert payload["run_id"] == response.run_id
    assert payload["candidate_count"] == 2
