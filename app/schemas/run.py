from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


RunLifecycleStatus = Literal["accepted", "running", "completed", "failed"]


class RunAcceptedResponse(BaseModel):
    run_id: str
    status: Literal["accepted"]
    status_url: str
    submitted_at: datetime


class RunStatusResponse(BaseModel):
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
