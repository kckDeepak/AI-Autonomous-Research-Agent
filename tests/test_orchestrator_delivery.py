from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.modules.delivery.service import DeliveryService
from app.modules.notion.service import NotionPersistenceService
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
from app.schemas.content import DocumentBatch, FetchBatch, FetchedPage, NormalizedDocument, SummarizationBatch
from app.schemas.finding import Finding
from app.schemas.research_plan import PlanRequest
from app.schemas.search import CandidateCollection, SearchCandidate
from app.settings import Settings


class FakeProvider(LLMProvider):
    def plan_research(self, request: PlanLLMRequest) -> PlanLLMResponse:
        return PlanLLMResponse(
            subtopics=["Market"],
            search_queries=["battery recycling market"],
            depth_strategy="standard",
            estimated_source_count=6,
            rationale="Focused on market coverage.",
        )

    def summarize_source(self, request: SummarizeLLMRequest) -> SummarizeLLMResponse:
        return SummarizeLLMResponse(
            summary="summary",
            tags=["tag"],
            relevance_score=0.8,
            confidence=0.8,
            key_points=["point"],
        )

    def compose_report(self, request: ComposeReportLLMRequest) -> ComposeReportLLMResponse:
        return ComposeReportLLMResponse(
            tldr="Momentum is improving.",
            executive_summary="Signals suggest positive demand and policy support.",
            markdown="",
            html="",
            references=[],
        )


class FakeSearchService:
    def collect_candidates(
        self,
        *,
        original_query: str,
        search_queries: list[str],
        max_candidates: int,
    ) -> CandidateCollection:
        return CandidateCollection(
            raw_result_count=1,
            deduped_result_count=1,
            candidates=[
                SearchCandidate(
                    url="https://example.com/report",
                    normalized_url="https://example.com/report",
                    title="Report",
                    snippet="snippet",
                    query=search_queries[0],
                    source_domain="example.com",
                    query_rank=1,
                    relevance_score=0.8,
                    global_rank=1,
                )
            ],
        )


class FakeFetcher:
    async def fetch_many(self, urls: list[str], max_concurrency: int = 8) -> FetchBatch:
        return FetchBatch(
            pages=[
                FetchedPage(
                    requested_url="https://example.com/report",
                    final_url="https://example.com/report",
                    status_code=200,
                    html="<html><head><title>Report</title></head><body><article>text</article></body></html>",
                )
            ],
            failures=[],
        )


class FakeExtractor:
    def extract_documents(self, pages: list[FetchedPage]) -> DocumentBatch:
        return DocumentBatch(
            documents=[
                NormalizedDocument(
                    url="https://example.com/report",
                    normalized_url="https://example.com/report",
                    source_domain="example.com",
                    title="Report",
                    content="content",
                    chunks=["chunk"],
                    word_count=1,
                    char_count=7,
                )
            ],
            issues=[],
        )


class FakeSummarizer:
    def summarize_documents(self, *, query: str, documents: list[NormalizedDocument]) -> SummarizationBatch:
        return SummarizationBatch(
            findings=[
                Finding(
                    title="Report",
                    url="https://example.com/report",
                    summary="Summary",
                    tags=["market"],
                    relevance_score=0.7,
                    confidence=0.8,
                    key_points=["Point"],
                )
            ],
            rejected_findings=[],
            issues=[],
        )


class FakeNotionClient:
    def find_page_by_source_key(self, source_key: str) -> str | None:
        return None

    def create_finding_page(
        self,
        *,
        run_id: str,
        query: str,
        source_key: str,
        finding: Finding,
    ) -> str:
        return "page-created"


class FakeGmailClient:
    def send_email(
        self,
        *,
        recipient: str,
        subject: str,
        html_body: str,
        text_body: str,
        delivery_key: str,
        run_id: str,
    ) -> str:
        return "message-123"


@pytest.mark.asyncio
async def test_p8_delivery_stage_writes_delivery_artifacts(tmp_path: Path, monkeypatch) -> None:
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
        gmail_sender_email="sender@example.com",
    )

    delivery_service = DeliveryService(
        FakeGmailClient(),
        sender_email="sender@example.com",
        registry_path=tmp_path / "delivery_registry.json",
    )

    orchestrator = ResearchOrchestrator(
        settings=settings,
        provider=FakeProvider(),
        search_service=FakeSearchService(),
        fetcher=FakeFetcher(),
        extractor=FakeExtractor(),
        summarizer=FakeSummarizer(),
        notion_service=NotionPersistenceService(FakeNotionClient()),
        delivery_service=delivery_service,
    )

    response = await orchestrator.plan_collect_compose_and_deliver_report(
        PlanRequest(
            query="Battery recycling market outlook",
            requester_email="analyst@example.com",
            depth="standard",
        )
    )

    assert response.delivery.status == "sent"
    assert response.delivery.message_id == "message-123"
    assert Path(response.delivery_artifact_path).exists()
    assert response.delivery_dead_letter_artifact_path is None

    payload = json.loads(Path(response.delivery_artifact_path).read_text(encoding="utf-8"))
    assert payload["delivery"]["status"] == "sent"
