from __future__ import annotations

from app.providers.llm.anthropic_provider import AnthropicProviderStub
from app.providers.llm.factory import get_llm_provider
from app.providers.llm.openai_provider import OpenAIProvider
from app.settings import Settings


def test_factory_returns_openai_provider() -> None:
    settings = Settings(
        llm_provider="openai",
        openai_api_key="test-key",
        tavily_api_key="x",
        notion_token="x",
        notion_database_id="x",
        gmail_client_id="x",
        gmail_client_secret="x",
        gmail_refresh_token="x",
        gmail_sender_email="x",
    )
    provider = get_llm_provider(settings)
    assert isinstance(provider, OpenAIProvider)


def test_factory_returns_anthropic_stub() -> None:
    settings = Settings(
        llm_provider="anthropic",
        openai_api_key="test-key",
        tavily_api_key="x",
        notion_token="x",
        notion_database_id="x",
        gmail_client_id="x",
        gmail_client_secret="x",
        gmail_refresh_token="x",
        gmail_sender_email="x",
    )
    provider = get_llm_provider(settings)
    assert isinstance(provider, AnthropicProviderStub)
