from __future__ import annotations

import argparse
import asyncio
import json
from uuid import uuid4

from pydantic import ValidationError

from app.core.guardrails import GuardrailPolicy, GuardrailViolation
from app.core.run_service import RunService
from app.core.run_store import RunStore
from app.orchestrator import ResearchOrchestrator
from app.schemas.research_plan import PlanRequest
from app.settings import get_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Autonomous Research Agent CLI")
    parser.add_argument("--query", required=True, help="Research question or topic")
    parser.add_argument("--email", required=True, help="Requester email")
    parser.add_argument(
        "--depth", choices=["quick", "standard", "deep"], default="standard", help="Run depth"
    )
    parser.add_argument("--max-sources", type=int, default=None)
    parser.add_argument("--max-queries-per-plan", type=int, default=None)
    parser.add_argument("--llm-token-budget-per-run", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    orchestrator = ResearchOrchestrator(settings)
    run_service = RunService(
        store=RunStore(),
        runner=orchestrator.plan_collect_compose_and_deliver_report,
        guardrail_policy=GuardrailPolicy.from_settings(settings),
    )

    run_id = str(uuid4())
    try:
        request = PlanRequest(
            query=args.query,
            requester_email=args.email,
            depth=args.depth,
            max_sources=args.max_sources,
            max_queries_per_plan=args.max_queries_per_plan,
            llm_token_budget_per_run=args.llm_token_budget_per_run,
        )
    except ValidationError as exc:
        print(
            json.dumps(
                {
                    "error": "Invalid CLI inputs",
                    "details": exc.errors(),
                    "example": (
                        'python -m app.cli --query "North America battery recycling market outlook" '
                        '--email "analyst@example.com" --depth standard'
                    ),
                },
                indent=2,
            )
        )
        return

    try:
        run_service.validate_request(request)
    except GuardrailViolation as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return

    status, response = asyncio.run(run_service.run_now(run_id, request))
    payload = {
        "status": status.model_dump(mode="json"),
        "result": response.model_dump(mode="json") if response else None,
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
