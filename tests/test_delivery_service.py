from __future__ import annotations

from pathlib import Path

from app.modules.delivery.service import DeliveryService
from app.schemas.report import ReportArtifact


class FakeGmailClient:
    def __init__(self) -> None:
        self.send_count = 0

    def send_email(
        self,
        *,
        recipient: str,
        subject: str,
        html_body: str,
        text_body: str,
        delivery_key: str,
        run_id: str,
    ) -> str:
        self.send_count += 1
        return f"msg-{self.send_count}"


def test_delivery_service_is_idempotent(tmp_path: Path) -> None:
    gmail = FakeGmailClient()
    service = DeliveryService(
        gmail,
        sender_email="sender@example.com",
        registry_path=tmp_path / "delivery_registry.json",
    )

    report = ReportArtifact(
        tldr="TLDR",
        executive_summary="Exec",
        markdown="# Report",
        html="<html><body>Report</body></html>",
        references=["https://example.com"],
    )

    first = service.deliver_report(
        run_id="run-1",
        recipient="analyst@example.com",
        query="Battery recycling",
        report=report,
    )
    second = service.deliver_report(
        run_id="run-1",
        recipient="analyst@example.com",
        query="Battery recycling",
        report=report,
    )

    assert first.status == "sent"
    assert second.status == "skipped_existing"
    assert gmail.send_count == 1
    assert second.message_id == first.message_id
