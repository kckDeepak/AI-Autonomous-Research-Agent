from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from app.core.run_store import RunStore


class SlackAlertProtocol(Protocol):
    def send_message(self, text: str) -> None:
        ...


class AlertService:
    def __init__(
        self,
        *,
        store: RunStore,
        failure_threshold: int,
        window_minutes: int,
        slack_client: SlackAlertProtocol | None = None,
        log_path: Path | None = None,
    ) -> None:
        self._store = store
        self._failure_threshold = max(1, failure_threshold)
        self._window_minutes = max(1, window_minutes)
        self._slack_client = slack_client
        self._log_path = log_path or Path("logs") / "alerts.jsonl"

    def alert_delivery_failure(self, run_id: str, error: str) -> bool:
        message = f"Delivery failure for run {run_id}: {error}"
        return self._emit("delivery_failure", run_id, message)

    def alert_repeated_failures(self, run_id: str, stage: str) -> bool:
        since = datetime.now(UTC) - timedelta(minutes=self._window_minutes)
        failed_records = self._store.list_failed_since(since)
        if len(failed_records) < self._failure_threshold:
            return False
        message = (
            f"Repeated failures detected: {len(failed_records)} failed runs within "
            f"{self._window_minutes} minutes. Latest run={run_id}, stage={stage}."
        )
        return self._emit("repeated_failures", run_id, message)

    def _emit(self, kind: str, run_id: str, message: str) -> bool:
        payload = {
            "kind": kind,
            "run_id": run_id,
            "message": message,
            "created_at": datetime.now(UTC).isoformat(),
        }
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._log_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(payload, ensure_ascii=True) + "\n")

        if not self._slack_client:
            return True
        try:
            self._slack_client.send_message(f"[P10 Alert] {message}")
            return True
        except Exception:
            return False
