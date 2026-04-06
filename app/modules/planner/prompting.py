from __future__ import annotations

from app.providers.llm.models import PlanLLMRequest

PLANNER_SYSTEM_PROMPT = (
    "You are a senior research planning assistant. "
    "Return strict JSON only with no markdown, no comments, and no additional keys."
)


def build_planner_user_prompt(request: PlanLLMRequest) -> str:
    return (
        "Generate a bounded, actionable research plan for the provided query.\n"
        "Follow all constraints exactly.\n\n"
        "Input:\n"
        f"- query: {request.query}\n"
        f"- depth: {request.depth}\n"
        f"- max_sources: {request.max_sources}\n"
        f"- max_queries_per_plan: {request.max_queries_per_plan}\n\n"
        "Output JSON schema:\n"
        "{\n"
        '  "subtopics": ["string"],\n'
        '  "search_queries": ["string"],\n'
        '  "depth_strategy": "string",\n'
        '  "estimated_source_count": 1,\n'
        '  "rationale": "string"\n'
        "}\n\n"
        "Rules:\n"
        "1) Produce focused subtopics only.\n"
        "2) search_queries must be specific and non-duplicate.\n"
        "3) estimated_source_count must not exceed max_sources.\n"
        "4) rationale must briefly explain breadth/depth choices.\n"
        "5) Return valid JSON object only."
    )
