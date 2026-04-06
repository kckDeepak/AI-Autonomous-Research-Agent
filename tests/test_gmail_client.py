from __future__ import annotations

import json

import httpx

from app.providers.mcp.gmail import GmailMCPClient


def test_gmail_client_refreshes_and_sends() -> None:
    calls = {"token": 0, "send": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            calls["token"] += 1
            return httpx.Response(
                status_code=200,
                json={"access_token": "access-token", "expires_in": 3600},
            )

        if request.url.host == "gmail.googleapis.com":
            calls["send"] += 1
            auth = request.headers.get("Authorization")
            if auth != "Bearer access-token":
                return httpx.Response(status_code=401, text="unauthorized")

            body = json.loads(request.content.decode("utf-8"))
            assert "raw" in body
            return httpx.Response(status_code=200, json={"id": "gmail-message-id"})

        return httpx.Response(status_code=404)

    client = GmailMCPClient(
        client_id="cid",
        client_secret="secret",
        refresh_token="refresh",
        sender_email="sender@example.com",
        transport=httpx.MockTransport(handler),
    )

    message_id = client.send_email(
        recipient="user@example.com",
        subject="Subject",
        html_body="<html><body>hello</body></html>",
        text_body="hello",
        delivery_key="run:user@example.com",
        run_id="run",
    )

    assert message_id == "gmail-message-id"
    assert calls["token"] >= 1
    assert calls["send"] == 1
