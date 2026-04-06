from __future__ import annotations

import json

from app.providers.llm.models import LLMConfig, PlanLLMRequest
from app.providers.llm.openai_provider import OpenAIProvider


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletionsWithTempFailure:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> _FakeResponse:
        self.calls.append(kwargs)
        if "temperature" in kwargs and len(self.calls) == 1:
            raise RuntimeError(
                "Error code: 400 - {'error': {'message': \"Unsupported value: 'temperature' does "
                "not support 0.2 with this model. Only the default (1) value is supported.\"}}"
            )
        payload = {
            "subtopics": ["a"],
            "search_queries": ["query one"],
            "depth_strategy": "balanced",
            "estimated_source_count": 5,
            "rationale": "Good enough rationale text.",
        }
        return _FakeResponse(json.dumps(payload))


class _FakeCompletionsSuccess:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> _FakeResponse:
        self.calls.append(kwargs)
        payload = {
            "subtopics": ["a"],
            "search_queries": ["query one"],
            "depth_strategy": "balanced",
            "estimated_source_count": 5,
            "rationale": "Good enough rationale text.",
        }
        return _FakeResponse(json.dumps(payload))


class _FakeChat:
    def __init__(self, completions: object) -> None:
        self.completions = completions


class _FakeClient:
    def __init__(self, completions: object) -> None:
        self.chat = _FakeChat(completions)


def test_openai_provider_retries_without_temperature_when_unsupported() -> None:
    provider = OpenAIProvider(
        api_key="test-key",
        config=LLMConfig(
            planner_model="gpt-5-mini",
            summarizer_model="gpt-5-mini",
            reporter_model="gpt-5",
        ),
    )

    fake_completions = _FakeCompletionsWithTempFailure()
    provider._client = _FakeClient(fake_completions)  # type: ignore[assignment]

    response = provider.plan_research(
        PlanLLMRequest(
            query="North America battery recycling market outlook",
            depth="standard",
            max_sources=10,
            max_queries_per_plan=6,
        )
    )

    assert response.search_queries
    assert len(fake_completions.calls) == 2
    assert "temperature" in fake_completions.calls[0]
    assert "temperature" not in fake_completions.calls[1]


def test_openai_provider_keeps_temperature_when_supported() -> None:
    provider = OpenAIProvider(
        api_key="test-key",
        config=LLMConfig(
            planner_model="gpt-4o-mini",
            summarizer_model="gpt-4o-mini",
            reporter_model="gpt-4o",
        ),
    )

    fake_completions = _FakeCompletionsSuccess()
    provider._client = _FakeClient(fake_completions)  # type: ignore[assignment]

    response = provider.plan_research(
        PlanLLMRequest(
            query="North America battery recycling market outlook",
            depth="standard",
            max_sources=10,
            max_queries_per_plan=6,
        )
    )

    assert response.search_queries
    assert len(fake_completions.calls) == 1
    assert fake_completions.calls[0].get("temperature") == 0.2
