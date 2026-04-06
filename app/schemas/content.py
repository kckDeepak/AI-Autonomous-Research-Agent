from __future__ import annotations

from pydantic import AnyHttpUrl, BaseModel, Field

from app.schemas.finding import Finding


class FetchFailure(BaseModel):
    requested_url: str
    error: str


class FetchedPage(BaseModel):
    requested_url: AnyHttpUrl
    final_url: AnyHttpUrl
    status_code: int = Field(ge=200, le=599)
    html: str


class FetchBatch(BaseModel):
    pages: list[FetchedPage] = Field(default_factory=list)
    failures: list[FetchFailure] = Field(default_factory=list)


class ExtractionIssue(BaseModel):
    url: str
    reason: str


class NormalizedDocument(BaseModel):
    url: AnyHttpUrl
    normalized_url: str
    source_domain: str
    title: str
    content: str
    chunks: list[str] = Field(default_factory=list)
    word_count: int = Field(ge=0)
    char_count: int = Field(ge=0)


class DocumentBatch(BaseModel):
    documents: list[NormalizedDocument] = Field(default_factory=list)
    issues: list[ExtractionIssue] = Field(default_factory=list)


class SummarizationIssue(BaseModel):
    url: str
    reason: str


class SummarizationBatch(BaseModel):
    findings: list[Finding] = Field(default_factory=list)
    rejected_findings: list[Finding] = Field(default_factory=list)
    issues: list[SummarizationIssue] = Field(default_factory=list)
