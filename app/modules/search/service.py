from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import ValidationError

from app.providers.mcp.tavily_search import TavilySearchClient, TavilyWebResult
from app.schemas.search import CandidateCollection, SearchCandidate

_TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "msclkid",
}


class TavilySearchClientProtocol(Protocol):
    def search_web(self, *, query: str, count: int = 8) -> list[TavilyWebResult]:
        ...


@dataclass(slots=True)
class _RawCandidate:
    url: str
    normalized_url: str
    title: str
    snippet: str
    query: str
    source_domain: str
    query_rank: int


class SearchService:
    def __init__(self, client: TavilySearchClientProtocol, per_query_limit: int = 8) -> None:
        self._client = client
        self._per_query_limit = max(1, per_query_limit)

    @classmethod
    def from_tavily(cls, tavily_client: TavilySearchClient, per_query_limit: int = 8) -> "SearchService":
        return cls(client=tavily_client, per_query_limit=per_query_limit)

    def collect_candidates(
        self,
        *,
        original_query: str,
        search_queries: list[str],
        max_candidates: int,
    ) -> CandidateCollection:
        bounded_max = max(1, max_candidates)
        deduped_queries = self._dedupe_queries(search_queries)

        raw_candidates: list[_RawCandidate] = []
        for query in deduped_queries:
            results = self._client.search_web(query=query, count=min(self._per_query_limit, bounded_max))
            for index, result in enumerate(results, start=1):
                normalized_url = self._normalize_url(result.url)
                if not normalized_url:
                    continue
                raw_candidates.append(
                    _RawCandidate(
                        url=result.url,
                        normalized_url=normalized_url,
                        title=self._normalize_text(result.title) or "Untitled",
                        snippet=self._normalize_text(result.description),
                        query=query,
                        source_domain=self._extract_domain(normalized_url),
                        query_rank=index,
                    )
                )

        deduped = self._dedupe_candidates(raw_candidates)
        scored = [self._to_scored_candidate(item, original_query) for item in deduped]
        ranked = self._rank_with_diversity(scored, max_candidates=bounded_max)
        return CandidateCollection(
            candidates=ranked,
            raw_result_count=len(raw_candidates),
            deduped_result_count=len(deduped),
        )

    @staticmethod
    def _dedupe_queries(search_queries: list[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for query in search_queries:
            cleaned = SearchService._normalize_text(query)
            if len(cleaned) < 3:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(cleaned)
        return deduped

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"\s+", " ", text.strip())

    @classmethod
    def _normalize_url(cls, url: str) -> str | None:
        try:
            parsed = urlsplit(url)
        except ValueError:
            return None

        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return None

        netloc = parsed.netloc.lower()
        if parsed.scheme == "http" and netloc.endswith(":80"):
            netloc = netloc[:-3]
        if parsed.scheme == "https" and netloc.endswith(":443"):
            netloc = netloc[:-4]

        path = parsed.path or "/"
        if path != "/" and path.endswith("/"):
            path = path[:-1]

        filtered_params = []
        for key, value in parse_qsl(parsed.query, keep_blank_values=False):
            lowered = key.lower()
            if lowered.startswith("utm_") or lowered in _TRACKING_QUERY_KEYS:
                continue
            filtered_params.append((key, value))
        filtered_params.sort(key=lambda pair: pair[0].lower())
        normalized_query = urlencode(filtered_params, doseq=True)
        return urlunsplit((parsed.scheme.lower(), netloc, path, normalized_query, ""))

    @staticmethod
    def _extract_domain(normalized_url: str) -> str:
        domain = urlsplit(normalized_url).netloc.lower()
        if domain.startswith("www."):
            return domain[4:]
        return domain

    @staticmethod
    def _dedupe_candidates(candidates: list[_RawCandidate]) -> list[_RawCandidate]:
        deduped: dict[str, _RawCandidate] = {}
        for candidate in candidates:
            existing = deduped.get(candidate.normalized_url)
            if not existing:
                deduped[candidate.normalized_url] = candidate
                continue

            is_better = (
                candidate.query_rank < existing.query_rank
                or len(candidate.title) > len(existing.title)
                or len(candidate.snippet) > len(existing.snippet)
            )
            if is_better:
                deduped[candidate.normalized_url] = candidate
        return list(deduped.values())

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2}

    @classmethod
    def _score(cls, candidate: _RawCandidate, original_query: str) -> float:
        query_tokens = cls._tokenize(original_query)
        text_tokens = cls._tokenize(f"{candidate.title} {candidate.snippet}")
        source_query_tokens = cls._tokenize(candidate.query)

        if not query_tokens:
            return 0.0

        overlap = len(query_tokens.intersection(text_tokens)) / len(query_tokens)
        source_query_overlap = len(query_tokens.intersection(source_query_tokens)) / len(query_tokens)
        rank_score = 1.0 / max(candidate.query_rank, 1)

        score = 0.65 * overlap + 0.20 * source_query_overlap + 0.15 * rank_score
        return max(0.0, min(1.0, score))

    @classmethod
    def _to_scored_candidate(cls, raw: _RawCandidate, original_query: str) -> SearchCandidate:
        score = cls._score(raw, original_query)
        try:
            return SearchCandidate(
                url=raw.url,
                normalized_url=raw.normalized_url,
                title=raw.title,
                snippet=raw.snippet,
                query=raw.query,
                source_domain=raw.source_domain,
                query_rank=raw.query_rank,
                relevance_score=score,
            )
        except ValidationError:
            return SearchCandidate(
                url=raw.normalized_url,
                normalized_url=raw.normalized_url,
                title=raw.title,
                snippet=raw.snippet,
                query=raw.query,
                source_domain=raw.source_domain,
                query_rank=raw.query_rank,
                relevance_score=score,
            )

    @staticmethod
    def _domain_bonus(domain_counts: dict[str, int], domain: str) -> float:
        seen_count = domain_counts.get(domain, 0)
        if seen_count == 0:
            return 0.10
        return max(0.0, 0.08 - (seen_count * 0.03))

    @classmethod
    def _rank_with_diversity(
        cls,
        candidates: list[SearchCandidate],
        *,
        max_candidates: int,
    ) -> list[SearchCandidate]:
        remaining = sorted(candidates, key=lambda c: (-c.relevance_score, c.query_rank))
        selected: list[SearchCandidate] = []
        domain_counts: dict[str, int] = {}

        while remaining and len(selected) < max_candidates:
            best_index = 0
            best_adjusted_score = -1.0
            for index, candidate in enumerate(remaining):
                adjusted = candidate.relevance_score + cls._domain_bonus(domain_counts, candidate.source_domain)
                if adjusted > best_adjusted_score:
                    best_index = index
                    best_adjusted_score = adjusted

            chosen = remaining.pop(best_index)
            domain_counts[chosen.source_domain] = domain_counts.get(chosen.source_domain, 0) + 1
            selected.append(chosen.model_copy(update={"global_rank": len(selected) + 1}))

        return selected
