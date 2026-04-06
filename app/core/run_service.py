from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Awaitable, Callable, Protocol

from app.core.alerts import AlertService
from app.core.guardrails import GuardrailPolicy, GuardrailViolation
from app.core.run_store import RunStore
from app.schemas.delivery import DeliveryResult
from app.schemas.research_plan import PlanRequest
from app.schemas.run import RunAcceptedResponse, RunStatusResponse


class DeliverResultProtocol(Protocol):
    report_artifact_path: str
    delivery_artifact_path: str
    delivery: DeliveryResult


class RunnerProtocol(Protocol):
    def __call__(self, request: PlanRequest, run_id: str | None = None) -> Awaitable[DeliverResultProtocol]:
        ...


Runner = RunnerProtocol


class RunService:
    def __init__(
        self,
        *,
        store: RunStore,
        runner: Runner,
        guardrail_policy: GuardrailPolicy,
        alert_service: AlertService | None = None,
    ) -> None:
        self._store = store
        self._runner = runner
        self._guardrail_policy = guardrail_policy
        self._alert_service = alert_service

    def validate_request(self, request: PlanRequest) -> None:
        self._guardrail_policy.validate_request(request)

    def create_run(self, run_id: str) -> RunAcceptedResponse:
        record = self._store.create(run_id)
        return RunAcceptedResponse(
            run_id=run_id,
            status="accepted",
            status_url=f"/v1/research/runs/{run_id}",
            submitted_at=record.submitted_at,
        )

    async def execute_run(self, run_id: str, request: PlanRequest) -> DeliverResultProtocol | None:
        try:
            self._guardrail_policy.validate_request(request)
        except GuardrailViolation as exc:
            self._store.mark_failed(run_id, error=str(exc), stage="guardrails")
            return None

        self._store.mark_running(run_id, stage="pipeline")
        try:
            response = await asyncio.wait_for(
                self._runner(request, run_id=run_id),
                timeout=self._guardrail_policy.global_timeout_seconds,
            )
            delivery: DeliveryResult = response.delivery

            if delivery.status == "failed":
                error = delivery.error or "delivery failed"
                self._store.mark_failed(run_id, error=error, stage="delivery")
                if self._alert_service:
                    self._alert_service.alert_delivery_failure(run_id, error)
                    self._alert_service.alert_repeated_failures(run_id, stage="delivery")
                return response

            self._store.mark_completed(
                run_id,
                report_artifact_path=response.report_artifact_path,
                delivery_artifact_path=response.delivery_artifact_path,
                delivery_message_id=delivery.message_id,
            )
            return response
        except TimeoutError:
            message = (
                f"Run exceeded global timeout of {self._guardrail_policy.global_timeout_seconds} seconds"
            )
            self._store.mark_failed(run_id, error=message, stage="timeout")
            if self._alert_service:
                self._alert_service.alert_repeated_failures(run_id, stage="timeout")
            return None
        except Exception as exc:
            self._store.mark_failed(run_id, error=str(exc), stage="pipeline")
            if self._alert_service:
                self._alert_service.alert_repeated_failures(run_id, stage="pipeline")
            return None

    def get_status(self, run_id: str) -> RunStatusResponse | None:
        return self._store.get_status_response(run_id)

    async def run_now(self, run_id: str, request: PlanRequest) -> tuple[RunStatusResponse, DeliverResultProtocol | None]:
        self.create_run(run_id)
        response = await self.execute_run(run_id, request)
        status = self.get_status(run_id)
        if not status:
            status = RunStatusResponse(
                run_id=run_id,
                status="failed",
                stage="pipeline",
                submitted_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                error="Run status record missing after execution",
            )
        return status, response
