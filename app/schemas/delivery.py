from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class DeliveryResult(BaseModel):
    delivery_key: str
    recipient: str
    status: Literal["sent", "skipped_existing", "failed"]
    message_id: str | None = None
    error: str | None = None
    slack_mirrored: bool = False
    slack_error: str | None = None
