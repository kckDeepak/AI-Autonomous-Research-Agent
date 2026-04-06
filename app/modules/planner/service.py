from __future__ import annotations

import re

from app.providers.llm.base import LLMProvider
from app.providers.llm.models import PlanLLMRequest
from app.schemas.research_plan import ResearchPlan, RuntimeConstraints


class PlannerService:
    _MAX_SUBTOPICS_BY_DEPTH = {
        "quick": 3,
        "standard": 5,
        "deep": 8,
    }
    _MAX_QUERIES_BY_DEPTH = {
        "quick": 3,
        "standard": 6,
        "deep": 8,
    }
    _MIN_SOURCES_BY_DEPTH = {
        "quick": 6,
        "standard": 10,
        "deep": 12,
    }

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    def create_plan(self, query: str, depth: str, constraints: RuntimeConstraints) -> ResearchPlan:
        response = None
        try:
            response = self._provider.plan_research(
                PlanLLMRequest(
                    query=query,
                    depth=depth,
                    max_sources=constraints.max_sources,
                    max_queries_per_plan=constraints.max_queries_per_plan,
                )
            )
        except Exception:
            # Keep pipeline progress even when planner output parsing fails.
            response = None

        max_subtopics = self._MAX_SUBTOPICS_BY_DEPTH.get(depth, 5)
        max_queries = min(
            constraints.max_queries_per_plan,
            self._MAX_QUERIES_BY_DEPTH.get(depth, constraints.max_queries_per_plan),
        )
        min_sources = min(constraints.max_sources, self._MIN_SOURCES_BY_DEPTH.get(depth, 8))

        subtopics = self._normalize_and_dedupe(response.subtopics, max_items=max_subtopics) if response else []
        queries = self._normalize_and_dedupe(response.search_queries, max_items=max_queries) if response else []

        if not subtopics:
            subtopics = self._fallback_subtopics(query)

        if not queries:
            queries = self._fallback_queries(query, subtopics, max_queries)

        estimated_source_count = min(
            constraints.max_sources,
            max(min_sources, response.estimated_source_count if response else min_sources),
        )

        depth_strategy = (
            self._normalize_text(response.depth_strategy) if response else ""
        ) or f"{depth} coverage strategy"
        rationale = (
            self._normalize_text(response.rationale) if response else ""
        ) or "Plan generated with bounded defaults."

        return ResearchPlan(
            subtopics=subtopics,
            search_queries=queries,
            depth_strategy=depth_strategy,
            estimated_source_count=estimated_source_count,
            rationale=rationale,
        )

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"\s+", " ", text.strip())

    @classmethod
    def _normalize_and_dedupe(cls, items: list[str], max_items: int) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in items:
            cleaned = cls._normalize_text(item)
            if len(cleaned) < 4:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            normalized.append(cleaned)
            seen.add(key)
            if len(normalized) >= max_items:
                break
        return normalized

    @classmethod
    def _fallback_subtopics(cls, query: str) -> list[str]:
        return [
            cls._normalize_text(query),
            "Market landscape and key actors",
            "Near-term risks and opportunities",
        ]

    @classmethod
    def _fallback_queries(cls, query: str, subtopics: list[str], max_queries: int) -> list[str]:
        seeds = [query] + [f"{query} {topic}" for topic in subtopics[: max_queries - 1]]
        return cls._normalize_and_dedupe(seeds, max_items=max_queries)
