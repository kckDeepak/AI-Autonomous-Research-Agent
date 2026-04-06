from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from app.core.guardrails import GuardrailPolicy
from app.core.run_service import RunService
from app.core.run_store import RunStore
from app.schemas.delivery import DeliveryResult
from app.schemas.research_plan import PlanRequest


@dataclass
class FakeRunResult:
    report_artifact_path: str
    delivery_artifact_path: str
    delivery: DeliveryResult


@pytest.mark.asyncio
async def test_run_service_marks_completed(tmp_path: Path) -> None:
    observed_run_id: dict[str, str | None] = {"value": None}

    async def runner(request: PlanRequest, run_id: str | None = None) -> FakeRunResult:
        observed_run_id["value"] = run_id
        return FakeRunResult(
            report_artifact_path="run_artifacts/run-1/report.json",
            delivery_artifact_path="run_artifacts/run-1/delivery.json",
            delivery=DeliveryResult(
                delivery_key="run-1:analyst@example.com",
                recipient="analyst@example.com",
                status="sent",
                message_id="msg-1",
            ),
        )

    service = RunService(
        store=RunStore(tmp_path / "run_status"),
        runner=runner,
        guardrail_policy=GuardrailPolicy(
            max_sources=50,
            max_queries_per_plan=12,
            max_llm_token_budget_per_run=120000,
            max_query_chars=1000,
            global_timeout_seconds=60,
        ),
    )
    run_id = "run-1"
    request = PlanRequest(
        query="Battery recycling market outlook",
        requester_email="analyst@example.com",
        depth="standard",
    )

    accepted = service.create_run(run_id)
    assert accepted.status == "accepted"
    await service.execute_run(run_id, request)
    status = service.get_status(run_id)
    assert status is not None
    assert status.status == "completed"
    assert status.delivery_message_id == "msg-1"
    assert observed_run_id["value"] == run_id


@pytest.mark.asyncio
async def test_run_service_marks_failed(tmp_path: Path) -> None:
    async def runner(request: PlanRequest, run_id: str | None = None) -> FakeRunResult:
        raise RuntimeError("simulated pipeline crash")

    service = RunService(
        store=RunStore(tmp_path / "run_status"),
        runner=runner,
        guardrail_policy=GuardrailPolicy(
            max_sources=50,
            max_queries_per_plan=12,
            max_llm_token_budget_per_run=120000,
            max_query_chars=1000,
            global_timeout_seconds=60,
        ),
    )
    run_id = "run-2"
    request = PlanRequest(
        query="Battery recycling market outlook",
        requester_email="analyst@example.com",
        depth="standard",
    )

    service.create_run(run_id)
    response = await service.execute_run(run_id, request)
    assert response is None
    status = service.get_status(run_id)
    assert status is not None
    assert status.status == "failed"
    assert "simulated pipeline crash" in (status.error or "")


@pytest.mark.asyncio
async def test_run_service_rejects_guardrail_violation_before_runner(tmp_path: Path) -> None:
    runner_called = {"value": False}

    async def runner(request: PlanRequest, run_id: str | None = None) -> FakeRunResult:
        runner_called["value"] = True
        return FakeRunResult(
            report_artifact_path="run_artifacts/run-3/report.json",
            delivery_artifact_path="run_artifacts/run-3/delivery.json",
            delivery=DeliveryResult(
                delivery_key="run-3:analyst@example.com",
                recipient="analyst@example.com",
                status="sent",
                message_id="msg-3",
            ),
        )

    service = RunService(
        store=RunStore(tmp_path / "run_status"),
        runner=runner,
        guardrail_policy=GuardrailPolicy(
            max_sources=5,
            max_queries_per_plan=4,
            max_llm_token_budget_per_run=10000,
            max_query_chars=1000,
            global_timeout_seconds=60,
        ),
    )

    run_id = "run-3"
    request = PlanRequest(
        query="Battery recycling market outlook",
        requester_email="analyst@example.com",
        depth="standard",
        max_sources=6,
    )

    service.create_run(run_id)
    response = await service.execute_run(run_id, request)
    status = service.get_status(run_id)

    assert response is None
    assert status is not None
    assert status.status == "failed"
    assert status.stage == "guardrails"
    assert runner_called["value"] is False


@pytest.mark.asyncio
async def test_run_service_marks_delivery_failed_and_emits_alerts(tmp_path: Path) -> None:
    class FakeAlertService:
        def __init__(self) -> None:
            self.delivery_alerts: list[tuple[str, str]] = []
            self.repeated_alerts: list[tuple[str, str]] = []

        def alert_delivery_failure(self, run_id: str, error: str) -> bool:
            self.delivery_alerts.append((run_id, error))
            return True

        def alert_repeated_failures(self, run_id: str, stage: str) -> bool:
            self.repeated_alerts.append((run_id, stage))
            return True

    async def runner(request: PlanRequest, run_id: str | None = None) -> FakeRunResult:
        return FakeRunResult(
            report_artifact_path="run_artifacts/run-4/report.json",
            delivery_artifact_path="run_artifacts/run-4/delivery.json",
            delivery=DeliveryResult(
                delivery_key="run-4:analyst@example.com",
                recipient="analyst@example.com",
                status="failed",
                error="smtp timeout",
            ),
        )

    fake_alert_service = FakeAlertService()
    service = RunService(
        store=RunStore(tmp_path / "run_status"),
        runner=runner,
        guardrail_policy=GuardrailPolicy(
            max_sources=50,
            max_queries_per_plan=12,
            max_llm_token_budget_per_run=120000,
            max_query_chars=1000,
            global_timeout_seconds=60,
        ),
        alert_service=fake_alert_service,
    )

    run_id = "run-4"
    request = PlanRequest(
        query="Battery recycling market outlook",
        requester_email="analyst@example.com",
        depth="standard",
    )

    service.create_run(run_id)
    response = await service.execute_run(run_id, request)
    status = service.get_status(run_id)

    assert response is not None
    assert status is not None
    assert status.status == "failed"
    assert status.stage == "delivery"
    assert "smtp timeout" in (status.error or "")
    assert fake_alert_service.delivery_alerts == [(run_id, "smtp timeout")]
    assert fake_alert_service.repeated_alerts == [(run_id, "delivery")]
