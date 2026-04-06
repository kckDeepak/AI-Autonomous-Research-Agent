from __future__ import annotations

from pydantic import BaseModel, Field


class Finding(BaseModel):
    title: str
    url: str
    summary: str
    tags: list[str] = Field(default_factory=list)
    relevance_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    key_points: list[str] = Field(default_factory=list)
