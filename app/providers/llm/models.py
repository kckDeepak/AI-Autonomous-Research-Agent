from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.finding import Finding


class LLMConfig(BaseModel):
    planner_model: str
    summarizer_model: str
    reporter_model: str
    timeout_seconds: int = Field(default=45, ge=1, le=180)
    max_retries: int = Field(default=2, ge=0, le=5)


class PlanLLMRequest(BaseModel):
    query: str
    depth: Literal["quick", "standard", "deep"]
    max_sources: int
    max_queries_per_plan: int


class PlanLLMResponse(BaseModel):
    subtopics: list[str] = Field(min_length=1, max_length=20)
    search_queries: list[str] = Field(min_length=1, max_length=30)
    depth_strategy: str = Field(min_length=3, max_length=500)
    estimated_source_count: int = Field(ge=1, le=100)
    rationale: str = Field(min_length=10, max_length=2000)


class SummarizeLLMRequest(BaseModel):
    query: str
    url: str
    title: str
    content: str


class SummarizeLLMResponse(BaseModel):
    summary: str
    tags: list[str]
    relevance_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    key_points: list[str]

    def to_finding(self, title: str, url: str) -> Finding:
        return Finding(
            title=title,
            url=url,
            summary=self.summary,
            tags=self.tags,
            relevance_score=self.relevance_score,
            confidence=self.confidence,
            key_points=self.key_points,
        )


class ComposeReportLLMRequest(BaseModel):
    query: str
    findings: list[Finding]
    run_id: str


class ComposeReportLLMResponse(BaseModel):
    tldr: str
    executive_summary: str
    markdown: str
    html: str
    references: list[str]
