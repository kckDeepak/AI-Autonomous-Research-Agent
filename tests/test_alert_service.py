from __future__ import annotations

import json
from pathlib import Path

from app.core.alerts import AlertService
from app.core.run_store import RunStore


class FakeSlackClient:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def send_message(self, text: str) -> None:
        self.messages.append(text)


def test_alert_service_emits_delivery_failure_to_log_and_slack(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "run_status")
    slack = FakeSlackClient()
    alert_service = AlertService(
        store=store,
        failure_threshold=3,
        window_minutes=60,
        slack_client=slack,
        log_path=tmp_path / "logs" / "alerts.jsonl",
    )

    emitted = alert_service.alert_delivery_failure("run-delivery-1", "smtp timeout")

    assert emitted is True
    assert len(slack.messages) == 1
    assert "Delivery failure for run run-delivery-1" in slack.messages[0]

    lines = [
        line
        for line in (tmp_path / "logs" / "alerts.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["kind"] == "delivery_failure"
    assert payload["run_id"] == "run-delivery-1"


def test_alert_service_repeated_failure_threshold(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "run_status")
    for run_id in ("run-1", "run-2"):
        store.create(run_id)
        store.mark_failed(run_id, error="pipeline error", stage="pipeline")

    alert_service = AlertService(
        store=store,
        failure_threshold=2,
        window_minutes=60,
        log_path=tmp_path / "logs" / "alerts.jsonl",
    )

    emitted = alert_service.alert_repeated_failures("run-2", stage="pipeline")

    assert emitted is True
    lines = [
        line
        for line in (tmp_path / "logs" / "alerts.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["kind"] == "repeated_failures"
    assert payload["run_id"] == "run-2"
    assert "2 failed runs" in payload["message"]


def test_alert_service_does_not_emit_if_threshold_not_met(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "run_status")
    store.create("run-1")
    store.mark_failed("run-1", error="pipeline error", stage="pipeline")

    alert_service = AlertService(
        store=store,
        failure_threshold=2,
        window_minutes=60,
        log_path=tmp_path / "logs" / "alerts.jsonl",
    )

    emitted = alert_service.alert_repeated_failures("run-1", stage="pipeline")

    assert emitted is False
    assert not (tmp_path / "logs" / "alerts.jsonl").exists()
