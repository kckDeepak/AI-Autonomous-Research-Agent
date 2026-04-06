from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.schemas.delivery import DeliveryResult
from app.schemas.finding import Finding
from app.schemas.notion import NotionWriteFailure, NotionWriteReceipt
from app.schemas.report import ReportArtifact
from app.schemas.search import SearchCandidate


class ResearchPlan(BaseModel):
    subtopics: list[str] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list)
    depth_strategy: str
    estimated_source_count: int = Field(ge=1, le=100)
    rationale: str


class RuntimeConstraints(BaseModel):
    max_sources: int = Field(default=20, ge=1, le=50)
    max_queries_per_plan: int = Field(default=6, ge=1, le=12)
    llm_token_budget_per_run: int = Field(default=25_000, ge=1_000)


class PlanRequest(BaseModel):
    query: str = Field(min_length=10, max_length=1000)
    requester_email: EmailStr
    depth: Literal["quick", "standard", "deep"] = "standard"
    max_sources: int | None = Field(default=None, ge=1, le=50)
    max_queries_per_plan: int | None = Field(default=None, ge=1, le=12)
    llm_token_budget_per_run: int | None = Field(default=None, ge=1_000)


class PlanResponse(BaseModel):
    run_id: str
    status: Literal["accepted", "planned"]
    plan: ResearchPlan
    plan_artifact_path: str


class CandidateCollectionResponse(BaseModel):
    run_id: str
    status: Literal["planned"]
    plan: ResearchPlan
    plan_artifact_path: str
    candidate_artifact_path: str
    candidates: list[SearchCandidate] = Field(default_factory=list)
    raw_result_count: int = Field(ge=0)
    deduped_result_count: int = Field(ge=0)


class FindingsResponse(BaseModel):
    run_id: str
    status: Literal["planned"]
    plan: ResearchPlan
    plan_artifact_path: str
    candidate_artifact_path: str
    document_artifact_path: str
    findings_artifact_path: str
    raw_result_count: int = Field(ge=0)
    deduped_result_count: int = Field(ge=0)
    fetched_count: int = Field(ge=0)
    fetch_failures_count: int = Field(ge=0)
    extracted_count: int = Field(ge=0)
    extraction_issues_count: int = Field(ge=0)
    finding_count: int = Field(ge=0)
    filtered_out_count: int = Field(ge=0)
    findings: list[Finding] = Field(default_factory=list)


class PersistedFindingsResponse(FindingsResponse):
    notion_persist_artifact_path: str
    notion_dead_letter_artifact_path: str | None = None
    notion_created_count: int = Field(ge=0)
    notion_skipped_count: int = Field(ge=0)
    notion_failed_count: int = Field(ge=0)
    notion_write_receipts: list[NotionWriteReceipt] = Field(default_factory=list)
    notion_write_failures: list[NotionWriteFailure] = Field(default_factory=list)


class ReportResponse(PersistedFindingsResponse):
    report_artifact_path: str
    report: ReportArtifact


class DeliveredReportResponse(ReportResponse):
    delivery_artifact_path: str
    delivery_dead_letter_artifact_path: str | None = None
    delivery: DeliveryResult



