from __future__ import annotations

from hashlib import sha256
from typing import Protocol

from app.schemas.finding import Finding
from app.schemas.notion import NotionWriteBatch, NotionWriteFailure, NotionWriteReceipt


def build_source_key(run_id: str, finding_url: str) -> str:
    normalized = finding_url.strip().lower()
    url_hash = sha256(normalized.encode("utf-8")).hexdigest()
    return f"{run_id}:{url_hash}"


class NotionClientProtocol(Protocol):
    def find_page_by_source_key(self, source_key: str) -> str | None:
        ...

    def create_finding_page(
        self,
        *,
        run_id: str,
        query: str,
        source_key: str,
        finding: Finding,
    ) -> str:
        ...


class NotionPersistenceService:
    def __init__(self, client: NotionClientProtocol) -> None:
        self._client = client

    def persist_findings(self, *, run_id: str, query: str, findings: list[Finding]) -> NotionWriteBatch:
        receipts: list[NotionWriteReceipt] = []
        failures: list[NotionWriteFailure] = []

        for finding in findings:
            source_key = build_source_key(run_id, finding.url)
            try:
                existing_page_id = self._client.find_page_by_source_key(source_key)
                if existing_page_id:
                    receipts.append(
                        NotionWriteReceipt(
                            source_key=source_key,
                            finding_url=finding.url,
                            page_id=existing_page_id,
                            status="skipped_existing",
                        )
                    )
                    continue

                page_id = self._client.create_finding_page(
                    run_id=run_id,
                    query=query,
                    source_key=source_key,
                    finding=finding,
                )
                receipts.append(
                    NotionWriteReceipt(
                        source_key=source_key,
                        finding_url=finding.url,
                        page_id=page_id,
                        status="created",
                    )
                )
            except Exception as exc:
                failures.append(
                    NotionWriteFailure(
                        source_key=source_key,
                        finding_url=finding.url,
                        error=str(exc),
                        finding=finding,
                    )
                )

        return NotionWriteBatch(receipts=receipts, failures=failures)
