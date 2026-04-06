from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from app.schemas.delivery import DeliveryResult
from app.schemas.report import ReportArtifact


def build_delivery_key(run_id: str, recipient: str) -> str:
    return f"{run_id}:{recipient.strip().lower()}"


class GmailClientProtocol(Protocol):
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
        ...


class SlackClientProtocol(Protocol):
    def send_message(self, text: str) -> None:
        ...


class DeliveryService:
    def __init__(
        self,
        gmail_client: GmailClientProtocol,
        *,
        sender_email: str,
        registry_path: Path | None = None,
        slack_client: SlackClientProtocol | None = None,
    ) -> None:
        self._gmail_client = gmail_client
        self._sender_email = sender_email
        self._registry_path = registry_path or Path("run_artifacts") / "delivery_registry.json"
        self._slack_client = slack_client

    def deliver_report(
        self,
        *,
        run_id: str,
        recipient: str,
        query: str,
        report: ReportArtifact,
    ) -> DeliveryResult:
        delivery_key = build_delivery_key(run_id, recipient)
        registry = self._load_registry()
        existing = registry.get(delivery_key)
        if existing:
            return DeliveryResult(
                delivery_key=delivery_key,
                recipient=recipient,
                status="skipped_existing",
                message_id=existing.get("message_id"),
                slack_mirrored=bool(existing.get("slack_mirrored", False)),
            )

        subject = f"Research Report: {query[:100]}"
        text_body = self._build_text_fallback(report)

        try:
            message_id = self._gmail_client.send_email(
                recipient=recipient,
                subject=subject,
                html_body=report.html,
                text_body=text_body,
                delivery_key=delivery_key,
                run_id=run_id,
            )
        except Exception as exc:
            return DeliveryResult(
                delivery_key=delivery_key,
                recipient=recipient,
                status="failed",
                error=str(exc),
            )

        slack_mirrored = False
        slack_error = None
        if self._slack_client:
            try:
                self._slack_client.send_message(
                    f"Research report delivered for run {run_id} to {recipient}. Subject: {subject}"
                )
                slack_mirrored = True
            except Exception as exc:
                slack_error = str(exc)

        registry[delivery_key] = {
            "run_id": run_id,
            "recipient": recipient,
            "sender": self._sender_email,
            "message_id": message_id,
            "slack_mirrored": slack_mirrored,
        }
        self._save_registry(registry)

        return DeliveryResult(
            delivery_key=delivery_key,
            recipient=recipient,
            status="sent",
            message_id=message_id,
            slack_mirrored=slack_mirrored,
            slack_error=slack_error,
        )

    @staticmethod
    def _build_text_fallback(report: ReportArtifact) -> str:
        text = report.markdown.strip()
        if text:
            return text
        return f"TL;DR: {report.tldr}\n\nExecutive Summary:\n{report.executive_summary}"

    def _load_registry(self) -> dict[str, dict]:
        if not self._registry_path.exists():
            return {}
        try:
            return json.loads(self._registry_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_registry(self, registry: dict[str, dict]) -> None:
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        self._registry_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")
