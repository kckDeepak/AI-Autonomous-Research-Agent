from __future__ import annotations

import httpx
import pytest

from app.modules.fetcher.extractor import ContentExtractor
from app.modules.fetcher.service import AsyncFetcher
from app.schemas.content import FetchedPage


@pytest.mark.asyncio
async def test_async_fetcher_collects_pages_and_failures() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/ok":
            return httpx.Response(
                status_code=200,
                text="<html><head><title>OK</title></head><body><main>content</main></body></html>",
            )
        return httpx.Response(status_code=404, text="not found")

    fetcher = AsyncFetcher(timeout_seconds=5, transport=httpx.MockTransport(handler))
    batch = await fetcher.fetch_many(["https://example.test/ok", "https://example.test/missing"])

    assert len(batch.pages) == 1
    assert len(batch.failures) == 1
    assert batch.pages[0].status_code == 200


def test_content_extractor_extracts_and_chunks() -> None:
    long_text = " ".join(["Battery recycling market outlook"] * 120)
    html = (
        "<html><head><title>Market</title></head><body>"
        "<nav>menu</nav><article>"
        f"{long_text}"
        "</article><script>ignored()</script></body></html>"
    )

    extractor = ContentExtractor(min_chars=200, chunk_chars=400, chunk_overlap=50)
    batch = extractor.extract_documents(
        [
            FetchedPage(
                requested_url="https://example.com/report",
                final_url="https://example.com/report",
                status_code=200,
                html=html,
            )
        ]
    )

    assert len(batch.documents) == 1
    assert len(batch.issues) == 0
    assert batch.documents[0].title == "Market"
    assert len(batch.documents[0].chunks) > 1
