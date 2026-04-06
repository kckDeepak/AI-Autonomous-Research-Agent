from __future__ import annotations

from app.modules.notion.service import NotionPersistenceService, build_source_key
from app.schemas.finding import Finding


class FakeNotionClient:
    def __init__(self) -> None:
        self._existing: dict[str, str] = {}
        self._created: dict[str, str] = {}

    def set_existing(self, source_key: str, page_id: str) -> None:
        self._existing[source_key] = page_id

    def find_page_by_source_key(self, source_key: str) -> str | None:
        return self._existing.get(source_key) or self._created.get(source_key)

    def create_finding_page(
        self,
        *,
        run_id: str,
        query: str,
        source_key: str,
        finding: Finding,
    ) -> str:
        if "fail" in finding.url:
            raise RuntimeError("simulated Notion write failure")
        page_id = f"page-{len(self._created) + 1}"
        self._created[source_key] = page_id
        return page_id


def test_notion_persistence_idempotency_and_failures() -> None:
    run_id = "run-123"
    findings = [
        Finding(
            title="Existing",
            url="https://example.com/existing",
            summary="summary",
            tags=["tag"],
            relevance_score=0.8,
            confidence=0.9,
            key_points=["point"],
        ),
        Finding(
            title="Created",
            url="https://example.com/new",
            summary="summary",
            tags=["tag"],
            relevance_score=0.7,
            confidence=0.8,
            key_points=["point"],
        ),
        Finding(
            title="Fails",
            url="https://example.com/fail",
            summary="summary",
            tags=["tag"],
            relevance_score=0.6,
            confidence=0.7,
            key_points=["point"],
        ),
    ]

    client = FakeNotionClient()
    existing_key = build_source_key(run_id, findings[0].url)
    client.set_existing(existing_key, "page-existing")

    service = NotionPersistenceService(client)
    batch = service.persist_findings(run_id=run_id, query="battery recycling", findings=findings)

    assert batch.created_count == 1
    assert batch.skipped_count == 1
    assert batch.failed_count == 1
