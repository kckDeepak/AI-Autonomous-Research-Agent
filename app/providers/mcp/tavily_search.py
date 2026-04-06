from __future__ import annotations

from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential, wait_random

import httpx


class TavilyWebResult(BaseModel):
    url: str
    title: str = Field(default="")
    description: str = Field(default="")


class TavilySearchClient:
    def __init__(
        self,
        *,
        api_key: str,
        timeout_seconds: int = 20,
        base_url: str = "https://api.tavily.com",
    ) -> None:
        self._api_key = api_key
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout_seconds,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=8) + wait_random(0, 1),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _request(self, payload: dict[str, str | int | bool]) -> httpx.Response:
        response = self._client.post("/search", json=payload)
        response.raise_for_status()
        return response

    def search_web(self, *, query: str, count: int = 8) -> list[TavilyWebResult]:
        bounded_count = max(1, min(count, 20))
        response = self._request(
            {
                "api_key": self._api_key,
                "query": query,
                "max_results": bounded_count,
                "search_depth": "basic",
                "topic": "general",
                "include_answer": False,
                "include_raw_content": False,
                "include_images": False,
            }
        )
        payload = response.json()
        raw_results = payload.get("results", [])

        parsed: list[TavilyWebResult] = []
        for item in raw_results:
            url = item.get("url")
            if not url:
                continue
            parsed.append(
                TavilyWebResult(
                    url=url,
                    title=item.get("title") or "",
                    description=item.get("content") or item.get("description") or "",
                )
            )
        return parsed