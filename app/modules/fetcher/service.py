from __future__ import annotations

import asyncio

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential, wait_random

from app.schemas.content import FetchBatch, FetchFailure, FetchedPage


class AsyncFetcher:
    def __init__(
        self,
        *,
        timeout_seconds: int = 20,
        user_agent: str = "AutonomousResearchAgent/0.1 (+internal)",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._user_agent = user_agent
        self._transport = transport

    async def fetch_many(self, urls: list[str], max_concurrency: int = 8) -> FetchBatch:
        semaphore = asyncio.Semaphore(max(1, max_concurrency))

        async with httpx.AsyncClient(
            timeout=self._timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": self._user_agent, "Accept": "text/html,application/xhtml+xml"},
            transport=self._transport,
        ) as client:
            tasks = [self._fetch_single_with_semaphore(client, semaphore, url) for url in urls]
            results = await asyncio.gather(*tasks)

        pages: list[FetchedPage] = []
        failures: list[FetchFailure] = []
        for page, failure in results:
            if page:
                pages.append(page)
            if failure:
                failures.append(failure)
        return FetchBatch(pages=pages, failures=failures)

    async def _fetch_single_with_semaphore(
        self,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        url: str,
    ) -> tuple[FetchedPage | None, FetchFailure | None]:
        async with semaphore:
            try:
                page = await self._fetch_with_retry(client, url)
                return page, None
            except Exception as exc:
                return None, FetchFailure(requested_url=url, error=str(exc))

    async def _fetch_with_retry(self, client: httpx.AsyncClient, url: str) -> FetchedPage:
        retryable_exceptions = (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError)
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type(retryable_exceptions),
            wait=wait_exponential(multiplier=1, min=1, max=8) + wait_random(0, 1),
            stop=stop_after_attempt(3),
            reraise=True,
        ):
            with attempt:
                response = await client.get(url)
                if response.status_code >= 500:
                    raise httpx.NetworkError(
                        f"Retryable server status {response.status_code} for {url}"
                    )
                if response.status_code >= 400:
                    raise ValueError(f"Non-retryable status {response.status_code} for {url}")

                return FetchedPage(
                    requested_url=url,
                    final_url=str(response.url),
                    status_code=response.status_code,
                    html=response.text,
                )

        raise RuntimeError("Fetcher retry loop exhausted unexpectedly")
