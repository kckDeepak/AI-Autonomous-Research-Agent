from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


RunStatus = Literal["accepted", "planned", "running", "failed", "completed"]


class RunState(BaseModel):
    run_id: str
    status: RunStatus
    stage: str
    started_at: datetime
    completed_at: datetime | None = None
    error: str | None = None
