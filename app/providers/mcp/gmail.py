from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential, wait_random


class GmailTransientError(Exception):
    """Raised when Gmail API returns a transient status code."""


class GmailMCPClient:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        sender_email: str,
        timeout_seconds: int = 20,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._sender_email = sender_email
        self._http = httpx.Client(timeout=timeout_seconds, transport=transport)

        self._access_token: str | None = None
        self._access_token_expiry: datetime | None = None

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
        message = EmailMessage()
        message["From"] = self._sender_email
        message["To"] = recipient
        message["Subject"] = subject
        message["X-Delivery-Key"] = delivery_key
        message["X-Run-ID"] = run_id
        message.set_content(text_body)
        message.add_alternative(html_body, subtype="html")

        raw_bytes = message.as_bytes()
        raw = base64.urlsafe_b64encode(raw_bytes).decode("ascii")
        payload = {"raw": raw}

        return self._send_with_retry(payload)

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError, GmailTransientError)),
        wait=wait_exponential(multiplier=1, min=1, max=10) + wait_random(0, 1),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _send_with_retry(self, payload: dict) -> str:
        token = self._get_valid_access_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        response = self._http.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            json=payload,
            headers=headers,
        )

        if response.status_code == 401:
            self._refresh_access_token(force=True)
            token = self._get_valid_access_token()
            headers["Authorization"] = f"Bearer {token}"
            response = self._http.post(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                json=payload,
                headers=headers,
            )

        if response.status_code in {429, 500, 502, 503, 504}:
            raise GmailTransientError(f"Transient Gmail status {response.status_code}: {response.text}")

        if response.status_code >= 400:
            raise RuntimeError(f"Gmail send failed ({response.status_code}): {response.text}")

        data = response.json()
        message_id = data.get("id")
        if not message_id:
            raise RuntimeError("Gmail send response missing id")
        return str(message_id)

    def _get_valid_access_token(self) -> str:
        now = datetime.now(UTC)
        if self._access_token and self._access_token_expiry and now < self._access_token_expiry:
            return self._access_token
        self._refresh_access_token(force=False)
        if not self._access_token:
            raise RuntimeError("Failed to obtain Gmail access token")
        return self._access_token

    def _refresh_access_token(self, force: bool) -> None:
        now = datetime.now(UTC)
        if (
            not force
            and self._access_token
            and self._access_token_expiry
            and now < self._access_token_expiry
        ):
            return

        response = self._http.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "refresh_token": self._refresh_token,
                "grant_type": "refresh_token",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Failed to refresh Gmail token ({response.status_code}): {response.text}")

        data = response.json()
        access_token = data.get("access_token")
        expires_in = int(data.get("expires_in", 3600))
        if not access_token:
            raise RuntimeError("OAuth token response missing access_token")

        self._access_token = str(access_token)
        self._access_token_expiry = now + timedelta(seconds=max(60, expires_in - 60))
