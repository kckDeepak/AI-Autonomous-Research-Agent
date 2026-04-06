from __future__ import annotations

import pytest

from app.settings import Settings


def test_missing_secrets_fails_fast() -> None:
    settings = Settings(
        openai_api_key=None,
        tavily_api_key=None,
        notion_token=None,
        notion_database_id=None,
        gmail_client_id=None,
        gmail_client_secret=None,
        gmail_refresh_token=None,
        gmail_sender_email=None,
    )
    with pytest.raises(RuntimeError):
        settings.assert_required_secrets()
