from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from app.schemas.run import RunLifecycleStatus, RunStatusResponse


class RunRecord(BaseModel):
    run_id: str
    status: RunLifecycleStatus
    stage: str
    submitted_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    report_artifact_path: str | None = None
    delivery_artifact_path: str | None = None
    delivery_message_id: str | None = None


class RunStore:
    def __init__(self, root_dir: Path | None = None) -> None:
        self._root_dir = root_dir or Path("run_artifacts") / "run_status"
        self._root_dir.mkdir(parents=True, exist_ok=True)

    def create(self, run_id: str) -> RunRecord:
        now = datetime.now(UTC)
        record = RunRecord(
            run_id=run_id,
            status="accepted",
            stage="accepted",
            submitted_at=now,
        )
        self._write_record(record)
        return record

    def mark_running(self, run_id: str, stage: str = "pipeline") -> RunRecord:
        record = self._require_record(run_id)
        if record.started_at is None:
            record.started_at = datetime.now(UTC)
        record.status = "running"
        record.stage = stage
        self._write_record(record)
        return record

    def mark_completed(
        self,
        run_id: str,
        *,
        report_artifact_path: str | None,
        delivery_artifact_path: str | None,
        delivery_message_id: str | None,
    ) -> RunRecord:
        record = self._require_record(run_id)
        record.status = "completed"
        record.stage = "completed"
        record.completed_at = datetime.now(UTC)
        record.report_artifact_path = report_artifact_path
        record.delivery_artifact_path = delivery_artifact_path
        record.delivery_message_id = delivery_message_id
        self._write_record(record)
        return record

    def mark_failed(self, run_id: str, error: str, stage: str = "failed") -> RunRecord:
        record = self._require_record(run_id)
        record.status = "failed"
        record.stage = stage
        record.error = error
        record.completed_at = datetime.now(UTC)
        self._write_record(record)
        return record

    def get(self, run_id: str) -> RunRecord | None:
        path = self._record_path(run_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return RunRecord.model_validate(data)

    def get_status_response(self, run_id: str) -> RunStatusResponse | None:
        record = self.get(run_id)
        if not record:
            return None
        return RunStatusResponse(**record.model_dump(mode="json"))

    def list_failed_since(self, since: datetime) -> list[RunRecord]:
        failed: list[RunRecord] = []
        for path in self._root_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                record = RunRecord.model_validate(data)
            except Exception:
                continue
            if record.status != "failed":
                continue
            reference_time = record.completed_at or record.started_at or record.submitted_at
            if reference_time >= since:
                failed.append(record)
        return failed

    def _require_record(self, run_id: str) -> RunRecord:
        record = self.get(run_id)
        if not record:
            raise RuntimeError(f"Run {run_id} does not exist")
        return record

    def _write_record(self, record: RunRecord) -> None:
        path = self._record_path(record.run_id)
        path.write_text(json.dumps(record.model_dump(mode="json"), indent=2), encoding="utf-8")

    def _record_path(self, run_id: str) -> Path:
        return self._root_dir / f"{run_id}.json"
