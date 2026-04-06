from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.finding import Finding


class NotionWriteReceipt(BaseModel):
    source_key: str
    finding_url: str
    page_id: str | None = None
    status: Literal["created", "skipped_existing"]


class NotionWriteFailure(BaseModel):
    source_key: str
    finding_url: str
    error: str
    finding: Finding


class NotionWriteBatch(BaseModel):
    receipts: list[NotionWriteReceipt] = Field(default_factory=list)
    failures: list[NotionWriteFailure] = Field(default_factory=list)

    @property
    def created_count(self) -> int:
        return sum(1 for receipt in self.receipts if receipt.status == "created")

    @property
    def skipped_count(self) -> int:
        return sum(1 for receipt in self.receipts if receipt.status == "skipped_existing")

    @property
    def failed_count(self) -> int:
        return len(self.failures)
