from __future__ import annotations

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential, wait_random


class SlackTransientError(Exception):
    """Raised when Slack webhook returns a transient status."""


class SlackWebhookClient:
    def __init__(
        self,
        *,
        webhook_url: str,
        timeout_seconds: int = 10,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._webhook_url = webhook_url
        self._http = httpx.Client(timeout=timeout_seconds, transport=transport)

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError, SlackTransientError)),
        wait=wait_exponential(multiplier=1, min=1, max=8) + wait_random(0, 1),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def send_message(self, text: str) -> None:
        response = self._http.post(self._webhook_url, json={"text": text})
        if response.status_code in {429, 500, 502, 503, 504}:
            raise SlackTransientError(f"Transient Slack status {response.status_code}: {response.text}")
        if response.status_code >= 400:
            raise RuntimeError(f"Slack webhook failed ({response.status_code}): {response.text}")
