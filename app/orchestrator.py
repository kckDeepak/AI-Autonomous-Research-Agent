from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.core.tracing import RunTracer
from app.modules.delivery.service import DeliveryService
from app.modules.fetcher.extractor import ContentExtractor
from app.modules.fetcher.service import AsyncFetcher
from app.modules.notion.service import NotionPersistenceService
from app.modules.planner.service import PlannerService
from app.modules.reporting.service import ReportComposerService
from app.modules.search.service import SearchService
from app.modules.summarizer.service import SummarizerService
from app.providers.mcp.gmail import GmailMCPClient
from app.providers.mcp.notion import NotionMCPClient
from app.providers.mcp.slack import SlackWebhookClient
from app.providers.mcp.tavily_search import TavilySearchClient
from app.providers.llm.base import LLMProvider
from app.providers.llm.factory import get_llm_provider
from app.schemas.research_plan import (
    CandidateCollectionResponse,
    DeliveredReportResponse,
    FindingsResponse,
    PlanRequest,
    PlanResponse,
    PersistedFindingsResponse,
    ReportResponse,
    RuntimeConstraints,
)
from app.settings import Settings
from app.utils.artifacts import (
    persist_candidate_artifact,
    persist_document_artifact,
    persist_delivery_artifact,
    persist_delivery_dead_letter_artifact,
    persist_findings_artifact,
    persist_notion_dead_letter_artifact,
    persist_notion_persistence_artifact,
    persist_plan_artifact,
    persist_report_artifact,
)


class ResearchOrchestrator:
    def __init__(
        self,
        settings: Settings,
        provider: LLMProvider | None = None,
        search_service: SearchService | None = None,
        fetcher: AsyncFetcher | None = None,
        extractor: ContentExtractor | None = None,
        summarizer: SummarizerService | None = None,
        notion_service: NotionPersistenceService | None = None,
        report_composer: ReportComposerService | None = None,
        delivery_service: DeliveryService | None = None,
    ) -> None:
        self._settings = settings
        self._provider = provider or get_llm_provider(settings)
        self._planner = PlannerService(self._provider)
        self._search_service = search_service or self._build_default_search_service()
        self._fetcher = fetcher or self._build_default_fetcher()
        self._extractor = extractor or self._build_default_extractor()
        self._summarizer = summarizer or self._build_default_summarizer()
        self._notion_service = notion_service
        self._report_composer = report_composer or self._build_default_report_composer()
        self._delivery_service = delivery_service

    @staticmethod
    def _resolve_run_id(run_id: str | None) -> str:
        return run_id or str(uuid4())

    @staticmethod
    def _estimate_tokens_from_text(text: str) -> int:
        if not text:
            return 0
        return max(1, len(text) // 4)

    def _build_default_search_service(self) -> SearchService:
        if not self._settings.tavily_api_key:
            raise RuntimeError("TAVILY_API_KEY is required for search collection")
        tavily_client = TavilySearchClient(
            api_key=self._settings.tavily_api_key,
            timeout_seconds=self._settings.per_url_timeout_seconds,
        )
        return SearchService.from_tavily(tavily_client=tavily_client)

    def _build_default_fetcher(self) -> AsyncFetcher:
        return AsyncFetcher(timeout_seconds=self._settings.per_url_timeout_seconds)

    def _build_default_extractor(self) -> ContentExtractor:
        return ContentExtractor(
            min_chars=self._settings.extraction_min_chars,
            chunk_chars=self._settings.summary_chunk_chars,
            chunk_overlap=self._settings.summary_chunk_overlap,
        )

    def _build_default_summarizer(self) -> SummarizerService:
        return SummarizerService(
            self._provider,
            min_relevance_score=self._settings.min_relevance_score,
            max_chunks_per_source=self._settings.max_summary_chunks_per_source,
        )

    def _build_default_report_composer(self) -> ReportComposerService:
        return ReportComposerService(self._provider)

    def _build_default_notion_service(self) -> NotionPersistenceService:
        if not self._settings.notion_token or not self._settings.notion_database_id:
            raise RuntimeError("NOTION_TOKEN and NOTION_DATABASE_ID are required for Notion persistence")

        client = NotionMCPClient(
            token=self._settings.notion_token,
            database_id=self._settings.notion_database_id,
            timeout_seconds=self._settings.notion_request_timeout_seconds,
            notion_version=self._settings.notion_version,
        )
        return NotionPersistenceService(client)

    def _build_default_delivery_service(self) -> DeliveryService:
        missing = [
            key
            for key, value in {
                "GMAIL_CLIENT_ID": self._settings.gmail_client_id,
                "GMAIL_CLIENT_SECRET": self._settings.gmail_client_secret,
                "GMAIL_REFRESH_TOKEN": self._settings.gmail_refresh_token,
                "GMAIL_SENDER_EMAIL": self._settings.gmail_sender_email,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError(f"Missing Gmail settings for delivery: {', '.join(missing)}")

        gmail_client = GmailMCPClient(
            client_id=self._settings.gmail_client_id or "",
            client_secret=self._settings.gmail_client_secret or "",
            refresh_token=self._settings.gmail_refresh_token or "",
            sender_email=self._settings.gmail_sender_email or "",
            timeout_seconds=self._settings.gmail_request_timeout_seconds,
        )

        slack_client = None
        if self._settings.slack_webhook_url:
            slack_client = SlackWebhookClient(
                webhook_url=self._settings.slack_webhook_url,
                timeout_seconds=self._settings.slack_request_timeout_seconds,
            )

        return DeliveryService(
            gmail_client,
            sender_email=self._settings.gmail_sender_email or "",
            slack_client=slack_client,
        )

    def _get_notion_service(self) -> NotionPersistenceService:
        if self._notion_service is None:
            self._notion_service = self._build_default_notion_service()
        return self._notion_service

    def _get_delivery_service(self) -> DeliveryService:
        if self._delivery_service is None:
            self._delivery_service = self._build_default_delivery_service()
        return self._delivery_service

    def _build_constraints(self, request: PlanRequest) -> RuntimeConstraints:
        return RuntimeConstraints(
            max_sources=request.max_sources or self._settings.max_sources_default,
            max_queries_per_plan=request.max_queries_per_plan
            or self._settings.max_queries_per_plan,
            llm_token_budget_per_run=request.llm_token_budget_per_run
            or self._settings.llm_token_budget_per_run,
        )

    def plan_only(
        self,
        request: PlanRequest,
        *,
        run_id: str | None = None,
        tracer: RunTracer | None = None,
    ) -> PlanResponse:
        resolved_run_id = self._resolve_run_id(run_id)
        created_tracer = tracer is None
        tracer = tracer or RunTracer(run_id=resolved_run_id)

        try:
            constraints = self._build_constraints(request)
            with tracer.stage("planner"):
                plan = self._planner.create_plan(
                    query=request.query,
                    depth=request.depth,
                    constraints=constraints,
                )

            with tracer.stage("persist_plan"):
                artifact_path = persist_plan_artifact(
                    run_id=resolved_run_id,
                    request=request,
                    constraints=constraints,
                    plan=plan,
                    root_dir=Path("run_artifacts"),
                )

            response = PlanResponse(
                run_id=resolved_run_id,
                status="planned",
                plan=plan,
                plan_artifact_path=artifact_path,
            )
            if created_tracer:
                tracer.flush(extra={"status": "completed", "stage": "plan_only"})
            return response
        except Exception as exc:
            if created_tracer:
                tracer.flush(extra={"status": "failed", "stage": "plan_only", "error": str(exc)})
            raise

    def plan_and_collect_candidates(
        self,
        request: PlanRequest,
        *,
        run_id: str | None = None,
        tracer: RunTracer | None = None,
    ) -> CandidateCollectionResponse:
        resolved_run_id = self._resolve_run_id(run_id)
        created_tracer = tracer is None
        tracer = tracer or RunTracer(run_id=resolved_run_id)

        try:
            constraints = self._build_constraints(request)

            with tracer.stage("planner"):
                plan = self._planner.create_plan(
                    query=request.query,
                    depth=request.depth,
                    constraints=constraints,
                )
            with tracer.stage("persist_plan"):
                plan_artifact_path = persist_plan_artifact(
                    run_id=resolved_run_id,
                    request=request,
                    constraints=constraints,
                    plan=plan,
                    root_dir=Path("run_artifacts"),
                )

            with tracer.stage("search"):
                candidate_collection = self._search_service.collect_candidates(
                    original_query=request.query,
                    search_queries=plan.search_queries,
                    max_candidates=constraints.max_sources,
                )
            with tracer.stage("persist_candidates"):
                candidate_artifact_path = persist_candidate_artifact(
                    run_id=resolved_run_id,
                    query=request.query,
                    search_queries=plan.search_queries,
                    candidates=candidate_collection.candidates,
                    raw_result_count=candidate_collection.raw_result_count,
                    deduped_result_count=candidate_collection.deduped_result_count,
                    root_dir=Path("run_artifacts"),
                )

            tracer.record_metric("raw_result_count", candidate_collection.raw_result_count)
            tracer.record_metric("deduped_result_count", candidate_collection.deduped_result_count)

            response = CandidateCollectionResponse(
                run_id=resolved_run_id,
                status="planned",
                plan=plan,
                plan_artifact_path=plan_artifact_path,
                candidate_artifact_path=candidate_artifact_path,
                candidates=candidate_collection.candidates,
                raw_result_count=candidate_collection.raw_result_count,
                deduped_result_count=candidate_collection.deduped_result_count,
            )
            if created_tracer:
                tracer.flush(extra={"status": "completed", "stage": "plan_and_collect_candidates"})
            return response
        except Exception as exc:
            if created_tracer:
                tracer.flush(
                    extra={
                        "status": "failed",
                        "stage": "plan_and_collect_candidates",
                        "error": str(exc),
                    }
                )
            raise

    async def plan_collect_and_summarize_findings(
        self,
        request: PlanRequest,
        *,
        run_id: str | None = None,
        tracer: RunTracer | None = None,
    ) -> FindingsResponse:
        resolved_run_id = self._resolve_run_id(run_id)
        created_tracer = tracer is None
        tracer = tracer or RunTracer(run_id=resolved_run_id)

        try:
            constraints = self._build_constraints(request)

            with tracer.stage("planner"):
                plan = self._planner.create_plan(
                    query=request.query,
                    depth=request.depth,
                    constraints=constraints,
                )
            with tracer.stage("persist_plan"):
                plan_artifact_path = persist_plan_artifact(
                    run_id=resolved_run_id,
                    request=request,
                    constraints=constraints,
                    plan=plan,
                    root_dir=Path("run_artifacts"),
                )

            with tracer.stage("search"):
                candidate_collection = self._search_service.collect_candidates(
                    original_query=request.query,
                    search_queries=plan.search_queries,
                    max_candidates=constraints.max_sources,
                )
            with tracer.stage("persist_candidates"):
                candidate_artifact_path = persist_candidate_artifact(
                    run_id=resolved_run_id,
                    query=request.query,
                    search_queries=plan.search_queries,
                    candidates=candidate_collection.candidates,
                    raw_result_count=candidate_collection.raw_result_count,
                    deduped_result_count=candidate_collection.deduped_result_count,
                    root_dir=Path("run_artifacts"),
                )

            with tracer.stage("fetch"):
                fetch_batch = await self._fetcher.fetch_many(
                    [str(candidate.url) for candidate in candidate_collection.candidates],
                    max_concurrency=self._settings.fetch_max_concurrency,
                )
            with tracer.stage("extract"):
                document_batch = self._extractor.extract_documents(fetch_batch.pages)
            with tracer.stage("persist_documents"):
                document_artifact_path = persist_document_artifact(
                    run_id=resolved_run_id,
                    fetch_batch=fetch_batch,
                    document_batch=document_batch,
                    root_dir=Path("run_artifacts"),
                )

            # Approximate token cost and cap document summarization scope to token budget.
            estimated_tokens_per_document = max(
                200,
                (self._settings.summary_chunk_chars * self._settings.max_summary_chunks_per_source) // 4 + 100,
            )
            docs_allowed_by_budget = max(
                1,
                constraints.llm_token_budget_per_run // estimated_tokens_per_document,
            )
            summarized_documents = document_batch.documents[:docs_allowed_by_budget]

            with tracer.stage(
                "summarize",
                metadata={
                    "documents_total": len(document_batch.documents),
                    "documents_summarized": len(summarized_documents),
                },
            ):
                summarization_batch = self._summarizer.summarize_documents(
                    query=request.query,
                    documents=summarized_documents,
                )

            with tracer.stage("persist_findings"):
                findings_artifact_path = persist_findings_artifact(
                    run_id=resolved_run_id,
                    query=request.query,
                    summarization_batch=summarization_batch,
                    min_relevance_score=self._settings.min_relevance_score,
                    root_dir=Path("run_artifacts"),
                )

            estimated_summary_tokens = sum(
                self._estimate_tokens_from_text(
                    finding.summary + " " + " ".join(finding.key_points)
                )
                for finding in summarization_batch.findings
            )
            tracer.record_metric("raw_result_count", candidate_collection.raw_result_count)
            tracer.record_metric("deduped_result_count", candidate_collection.deduped_result_count)
            tracer.record_metric("fetched_count", len(fetch_batch.pages))
            tracer.record_metric("fetch_failures_count", len(fetch_batch.failures))
            tracer.record_metric("extracted_count", len(document_batch.documents))
            tracer.record_metric("documents_summarized", len(summarized_documents))
            tracer.record_metric("estimated_llm_tokens_summarization", estimated_summary_tokens)
            tracer.record_metric("llm_token_budget_per_run", constraints.llm_token_budget_per_run)

            response = FindingsResponse(
                run_id=resolved_run_id,
                status="planned",
                plan=plan,
                plan_artifact_path=plan_artifact_path,
                candidate_artifact_path=candidate_artifact_path,
                document_artifact_path=document_artifact_path,
                findings_artifact_path=findings_artifact_path,
                raw_result_count=candidate_collection.raw_result_count,
                deduped_result_count=candidate_collection.deduped_result_count,
                fetched_count=len(fetch_batch.pages),
                fetch_failures_count=len(fetch_batch.failures),
                extracted_count=len(document_batch.documents),
                extraction_issues_count=len(document_batch.issues),
                finding_count=len(summarization_batch.findings),
                filtered_out_count=len(summarization_batch.rejected_findings),
                findings=summarization_batch.findings,
            )
            if created_tracer:
                tracer.flush(extra={"status": "completed", "stage": "plan_collect_and_summarize_findings"})
            return response
        except Exception as exc:
            if created_tracer:
                tracer.flush(
                    extra={
                        "status": "failed",
                        "stage": "plan_collect_and_summarize_findings",
                        "error": str(exc),
                    }
                )
            raise

    async def plan_collect_summarize_and_persist_findings(
        self,
        request: PlanRequest,
        *,
        run_id: str | None = None,
        tracer: RunTracer | None = None,
    ) -> PersistedFindingsResponse:
        resolved_run_id = self._resolve_run_id(run_id)
        created_tracer = tracer is None
        tracer = tracer or RunTracer(run_id=resolved_run_id)

        try:
            findings_response = await self.plan_collect_and_summarize_findings(
                request,
                run_id=resolved_run_id,
                tracer=tracer,
            )

            notion_service = self._get_notion_service()
            with tracer.stage("notion_persist"):
                write_batch = notion_service.persist_findings(
                    run_id=findings_response.run_id,
                    query=request.query,
                    findings=findings_response.findings,
                )

            with tracer.stage("persist_notion_receipts"):
                notion_persist_artifact_path = persist_notion_persistence_artifact(
                    run_id=findings_response.run_id,
                    query=request.query,
                    write_batch=write_batch,
                    root_dir=Path("run_artifacts"),
                )
                notion_dead_letter_artifact_path = persist_notion_dead_letter_artifact(
                    run_id=findings_response.run_id,
                    query=request.query,
                    write_batch=write_batch,
                    root_dir=Path("run_artifacts"),
                )

            tracer.record_metric("notion_created_count", write_batch.created_count)
            tracer.record_metric("notion_skipped_count", write_batch.skipped_count)
            tracer.record_metric("notion_failed_count", write_batch.failed_count)

            response = PersistedFindingsResponse(
                **findings_response.model_dump(mode="json"),
                notion_persist_artifact_path=notion_persist_artifact_path,
                notion_dead_letter_artifact_path=notion_dead_letter_artifact_path,
                notion_created_count=write_batch.created_count,
                notion_skipped_count=write_batch.skipped_count,
                notion_failed_count=write_batch.failed_count,
                notion_write_receipts=write_batch.receipts,
                notion_write_failures=write_batch.failures,
            )
            if created_tracer:
                tracer.flush(
                    extra={"status": "completed", "stage": "plan_collect_summarize_and_persist_findings"}
                )
            return response
        except Exception as exc:
            if created_tracer:
                tracer.flush(
                    extra={
                        "status": "failed",
                        "stage": "plan_collect_summarize_and_persist_findings",
                        "error": str(exc),
                    }
                )
            raise

    async def plan_collect_persist_and_compose_report(
        self,
        request: PlanRequest,
        *,
        run_id: str | None = None,
        tracer: RunTracer | None = None,
    ) -> ReportResponse:
        resolved_run_id = self._resolve_run_id(run_id)
        created_tracer = tracer is None
        tracer = tracer or RunTracer(run_id=resolved_run_id)

        try:
            persisted_response = await self.plan_collect_summarize_and_persist_findings(
                request,
                run_id=resolved_run_id,
                tracer=tracer,
            )

            with tracer.stage("report_compose"):
                report = self._report_composer.compose(
                    query=request.query,
                    run_id=persisted_response.run_id,
                    findings=persisted_response.findings,
                )
            with tracer.stage("persist_report"):
                report_artifact_path = persist_report_artifact(
                    run_id=persisted_response.run_id,
                    query=request.query,
                    report=report,
                    root_dir=Path("run_artifacts"),
                )

            estimated_report_tokens = self._estimate_tokens_from_text(report.markdown)
            tracer.record_metric("estimated_llm_tokens_report", estimated_report_tokens)

            response = ReportResponse(
                **persisted_response.model_dump(mode="json"),
                report_artifact_path=report_artifact_path,
                report=report,
            )
            if created_tracer:
                tracer.flush(extra={"status": "completed", "stage": "plan_collect_persist_and_compose_report"})
            return response
        except Exception as exc:
            if created_tracer:
                tracer.flush(
                    extra={
                        "status": "failed",
                        "stage": "plan_collect_persist_and_compose_report",
                        "error": str(exc),
                    }
                )
            raise

    async def plan_collect_compose_and_deliver_report(
        self,
        request: PlanRequest,
        *,
        run_id: str | None = None,
        tracer: RunTracer | None = None,
    ) -> DeliveredReportResponse:
        resolved_run_id = self._resolve_run_id(run_id)
        created_tracer = tracer is None
        tracer = tracer or RunTracer(run_id=resolved_run_id)

        try:
            report_response = await self.plan_collect_persist_and_compose_report(
                request,
                run_id=resolved_run_id,
                tracer=tracer,
            )

            delivery_service = self._get_delivery_service()
            with tracer.stage("delivery"):
                delivery = delivery_service.deliver_report(
                    run_id=report_response.run_id,
                    recipient=str(request.requester_email),
                    query=request.query,
                    report=report_response.report,
                )

            with tracer.stage("persist_delivery"):
                delivery_artifact_path = persist_delivery_artifact(
                    run_id=report_response.run_id,
                    query=request.query,
                    delivery=delivery,
                    root_dir=Path("run_artifacts"),
                )
                delivery_dead_letter_artifact_path = persist_delivery_dead_letter_artifact(
                    run_id=report_response.run_id,
                    query=request.query,
                    delivery=delivery,
                    root_dir=Path("run_artifacts"),
                )

            tracer.record_metric("delivery_status", delivery.status)

            response = DeliveredReportResponse(
                **report_response.model_dump(mode="json"),
                delivery_artifact_path=delivery_artifact_path,
                delivery_dead_letter_artifact_path=delivery_dead_letter_artifact_path,
                delivery=delivery,
            )
            if created_tracer:
                tracer.flush(extra={"status": "completed", "stage": "plan_collect_compose_and_deliver_report"})
            return response
        except Exception as exc:
            if created_tracer:
                tracer.flush(
                    extra={
                        "status": "failed",
                        "stage": "plan_collect_compose_and_deliver_report",
                        "error": str(exc),
                    }
                )
            raise



