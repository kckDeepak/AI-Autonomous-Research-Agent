from __future__ import annotations

import pytest

from app.core.guardrails import GuardrailPolicy, GuardrailViolation
from app.schemas.research_plan import PlanRequest


def _base_request() -> PlanRequest:
    return PlanRequest(
        query="Battery recycling market outlook",
        requester_email="analyst@example.com",
        depth="standard",
    )


def test_guardrail_policy_accepts_in_bounds_request() -> None:
    policy = GuardrailPolicy(
        max_sources=20,
        max_queries_per_plan=8,
        max_llm_token_budget_per_run=40000,
        max_query_chars=1000,
        global_timeout_seconds=600,
    )

    request = _base_request()
    policy.validate_request(request)


@pytest.mark.parametrize(
    "field_name, override, expected",
    [
        ("max_sources", 25, "hard_max_sources"),
        ("max_queries_per_plan", 10, "hard_max_queries_per_plan"),
        ("llm_token_budget_per_run", 50000, "hard_llm_token_budget_per_run"),
    ],
)
def test_guardrail_policy_rejects_excessive_overrides(
    field_name: str,
    override: int,
    expected: str,
) -> None:
    policy = GuardrailPolicy(
        max_sources=20,
        max_queries_per_plan=8,
        max_llm_token_budget_per_run=40000,
        max_query_chars=1000,
        global_timeout_seconds=600,
    )

    request = _base_request().model_copy(update={field_name: override})

    with pytest.raises(GuardrailViolation, match=expected):
        policy.validate_request(request)


def test_guardrail_policy_rejects_long_query() -> None:
    policy = GuardrailPolicy(
        max_sources=20,
        max_queries_per_plan=8,
        max_llm_token_budget_per_run=40000,
        max_query_chars=20,
        global_timeout_seconds=600,
    )
    request = PlanRequest(
        query="Battery recycling market outlook",
        requester_email="analyst@example.com",
        depth="standard",
    )

    with pytest.raises(GuardrailViolation, match="max_query_chars"):
        policy.validate_request(request)
