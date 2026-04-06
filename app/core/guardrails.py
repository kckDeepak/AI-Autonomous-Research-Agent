from __future__ import annotations

from dataclasses import dataclass

from app.schemas.research_plan import PlanRequest
from app.settings import Settings


class GuardrailViolation(ValueError):
    """Raised when incoming run parameters violate hard runtime guardrails."""


@dataclass(slots=True)
class GuardrailPolicy:
    max_sources: int
    max_queries_per_plan: int
    max_llm_token_budget_per_run: int
    max_query_chars: int
    global_timeout_seconds: int

    @classmethod
    def from_settings(cls, settings: Settings) -> "GuardrailPolicy":
        return cls(
            max_sources=settings.hard_max_sources,
            max_queries_per_plan=settings.hard_max_queries_per_plan,
            max_llm_token_budget_per_run=settings.hard_llm_token_budget_per_run,
            max_query_chars=settings.request_max_chars,
            global_timeout_seconds=settings.global_run_timeout_minutes * 60,
        )

    def validate_request(self, request: PlanRequest) -> None:
        if len(request.query) > self.max_query_chars:
            raise GuardrailViolation(
                f"query length {len(request.query)} exceeds max_query_chars={self.max_query_chars}"
            )

        if request.max_sources is not None and request.max_sources > self.max_sources:
            raise GuardrailViolation(
                f"max_sources={request.max_sources} exceeds hard_max_sources={self.max_sources}"
            )

        if (
            request.max_queries_per_plan is not None
            and request.max_queries_per_plan > self.max_queries_per_plan
        ):
            raise GuardrailViolation(
                "max_queries_per_plan="
                f"{request.max_queries_per_plan} exceeds hard_max_queries_per_plan="
                f"{self.max_queries_per_plan}"
            )

        if (
            request.llm_token_budget_per_run is not None
            and request.llm_token_budget_per_run > self.max_llm_token_budget_per_run
        ):
            raise GuardrailViolation(
                "llm_token_budget_per_run="
                f"{request.llm_token_budget_per_run} exceeds hard_llm_token_budget_per_run="
                f"{self.max_llm_token_budget_per_run}"
            )
