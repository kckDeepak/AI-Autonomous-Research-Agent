from __future__ import annotations

from pydantic import AnyHttpUrl, BaseModel, Field


class SearchCandidate(BaseModel):
    url: AnyHttpUrl
    normalized_url: str
    title: str = Field(min_length=1, max_length=500)
    snippet: str = Field(default="", max_length=4000)
    query: str = Field(min_length=1, max_length=500)
    source_domain: str = Field(min_length=1, max_length=255)
    query_rank: int = Field(ge=1)
    relevance_score: float = Field(ge=0.0, le=1.0)
    global_rank: int | None = Field(default=None, ge=1)


class CandidateCollection(BaseModel):
    candidates: list[SearchCandidate] = Field(default_factory=list)
    raw_result_count: int = Field(default=0, ge=0)
    deduped_result_count: int = Field(default=0, ge=0)
