from __future__ import annotations

from app.providers.llm.anthropic_provider import AnthropicProviderStub
from app.providers.llm.base import LLMProvider
from app.providers.llm.models import LLMConfig
from app.providers.llm.openai_provider import OpenAIProvider
from app.settings import Settings


def get_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        config = LLMConfig(
            planner_model=settings.openai_model_planner,
            summarizer_model=settings.openai_model_summarizer,
            reporter_model=settings.openai_model_reporter,
        )
        return OpenAIProvider(api_key=settings.openai_api_key, config=config)

    config = LLMConfig(
        planner_model=settings.anthropic_model_planner,
        summarizer_model=settings.anthropic_model_summarizer,
        reporter_model=settings.anthropic_model_reporter,
    )
    return AnthropicProviderStub(api_key=None, config=config)
