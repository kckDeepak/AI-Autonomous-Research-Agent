from __future__ import annotations

from pydantic import BaseModel, Field


class CitationEntry(BaseModel):
    reference_number: int = Field(ge=1)
    url: str
    finding_title: str


class ClaimCitation(BaseModel):
    claim: str
    citation_numbers: list[int] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)


class ReportArtifact(BaseModel):
    tldr: str
    executive_summary: str
    markdown: str
    html: str
    references: list[str] = Field(default_factory=list)
    citation_index: list[CitationEntry] = Field(default_factory=list)
    claim_citations: list[ClaimCitation] = Field(default_factory=list)
