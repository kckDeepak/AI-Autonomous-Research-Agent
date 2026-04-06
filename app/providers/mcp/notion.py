from __future__ import annotations

from datetime import UTC, datetime

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential, wait_random

from app.schemas.finding import Finding


class NotionTransientError(Exception):
    """Raised when a Notion request fails with a transient status."""


class NotionMCPClient:
    def __init__(
        self,
        *,
        token: str,
        database_id: str,
        timeout_seconds: int = 20,
        notion_version: str = "2022-06-28",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._database_id = database_id
        self._client = httpx.Client(
            base_url="https://api.notion.com",
            timeout=timeout_seconds,
            transport=transport,
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": notion_version,
                "Content-Type": "application/json",
            },
        )

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError, NotionTransientError)),
        wait=wait_exponential(multiplier=1, min=1, max=10) + wait_random(0, 1),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _post(self, path: str, payload: dict) -> dict:
        response = self._client.post(path, json=payload)
        if response.status_code in {429, 500, 502, 503, 504}:
            raise NotionTransientError(f"Transient Notion status {response.status_code}: {response.text}")
        if response.status_code >= 400:
            raise RuntimeError(f"Notion request failed ({response.status_code}): {response.text}")
        return response.json()

    def find_page_by_source_key(self, source_key: str) -> str | None:
        payload = {
            "filter": {
                "property": "SourceKey",
                "rich_text": {"equals": source_key},
            },
            "page_size": 1,
        }
        data = self._post(f"/v1/databases/{self._database_id}/query", payload)
        results = data.get("results", [])
        if not results:
            return None
        return results[0].get("id")

    def create_finding_page(
        self,
        *,
        run_id: str,
        query: str,
        source_key: str,
        finding: Finding,
    ) -> str:
        timestamp = datetime.now(UTC).isoformat()
        payload = {
            "parent": {"database_id": self._database_id},
            "properties": {
                "Title": {
                    "title": [
                        {
                            "text": {
                                "content": finding.title[:2000],
                            }
                        }
                    ]
                },
                "Summary": {
                    "rich_text": [
                        {
                            "text": {
                                "content": finding.summary[:2000],
                            }
                        }
                    ]
                },
                "URL": {"url": finding.url},
                "Relevance": {"number": round(finding.relevance_score, 4)},
                "Confidence": {"number": round(finding.confidence, 4)},
                "Tags": {
                    "multi_select": [{"name": tag[:100]} for tag in finding.tags[:10]],
                },
                "Query": {
                    "rich_text": [
                        {
                            "text": {
                                "content": query[:2000],
                            }
                        }
                    ]
                },
                "RunID": {
                    "rich_text": [
                        {
                            "text": {
                                "content": run_id,
                            }
                        }
                    ]
                },
                "SourceKey": {
                    "rich_text": [
                        {
                            "text": {
                                "content": source_key,
                            }
                        }
                    ]
                },
                "Timestamp": {"date": {"start": timestamp}},
            },
        }
        data = self._post("/v1/pages", payload)
        page_id = data.get("id")
        if not page_id:
            raise RuntimeError("Notion create page response did not include id")
        return str(page_id)
