from __future__ import annotations

from app.modules.search.service import SearchService
from app.providers.mcp.tavily_search import TavilyWebResult


class FakeSearchClient:
    def search_web(self, *, query: str, count: int = 8) -> list[TavilyWebResult]:
        if "market" in query.lower():
            return [
                TavilyWebResult(
                    url="https://example.com/report?utm_source=newsletter",
                    title="Battery Recycling Market Report",
                    description="Market size and growth outlook.",
                ),
                TavilyWebResult(
                    url="https://example.com/report",
                    title="Battery Recycling Market Report",
                    description="Duplicate canonical URL.",
                ),
                TavilyWebResult(
                    url="https://news.site/analysis",
                    title="Policy and Regulation Analysis",
                    description="North America policy signals.",
                ),
            ]

        return [
            TavilyWebResult(
                url="https://research.org/insight",
                title="Technology and Capacity Insight",
                description="Capacity expansion and technology trends.",
            ),
            TavilyWebResult(
                url="https://news.site/analysis?gclid=abc",
                title="Policy and Regulation Analysis",
                description="Tracking-parameter duplicate.",
            ),
            TavilyWebResult(
                url="https://another.net/post",
                title="Competitive Landscape",
                description="Major players and partnerships.",
            ),
        ]


def test_collect_candidates_dedupes_and_ranks() -> None:
    service = SearchService(client=FakeSearchClient(), per_query_limit=5)

    result = service.collect_candidates(
        original_query="North America battery recycling market outlook",
        search_queries=[
            "battery recycling market north america",
            "battery recycling technology capacity",
        ],
        max_candidates=4,
    )

    assert result.raw_result_count == 6
    assert result.deduped_result_count < result.raw_result_count
    assert 1 <= len(result.candidates) <= 4

    normalized_urls = [candidate.normalized_url for candidate in result.candidates]
    assert len(normalized_urls) == len(set(normalized_urls))

    domains = {candidate.source_domain for candidate in result.candidates}
    assert len(domains) >= 2

    assert [candidate.global_rank for candidate in result.candidates] == list(
        range(1, len(result.candidates) + 1)
    )
