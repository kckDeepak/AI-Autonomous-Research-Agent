from __future__ import annotations

import json

from openai import OpenAI
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from app.modules.planner.prompting import PLANNER_SYSTEM_PROMPT, build_planner_user_prompt
from app.providers.llm.base import LLMProvider
from app.providers.llm.models import (
    ComposeReportLLMRequest,
    ComposeReportLLMResponse,
    LLMConfig,
    PlanLLMRequest,
    PlanLLMResponse,
    SummarizeLLMRequest,
    SummarizeLLMResponse,
)


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, config: LLMConfig) -> None:
        self._client = OpenAI(api_key=api_key)
        self._config = config

    def plan_research(self, request: PlanLLMRequest) -> PlanLLMResponse:
        return self._json_completion(
            response_model=PlanLLMResponse,
            model=self._config.planner_model,
            system_prompt=PLANNER_SYSTEM_PROMPT,
            user_prompt=build_planner_user_prompt(request),
            temperature=0.2,
        )

    def summarize_source(self, request: SummarizeLLMRequest) -> SummarizeLLMResponse:
        system_prompt = (
            "You summarize extracted webpage content for analysts. Return strict JSON only. "
            "Do not include markdown formatting."
        )
        user_prompt = (
            f"Original query: {request.query}\n"
            f"Source title: {request.title}\n"
            f"Source url: {request.url}\n"
            "Create a compact 3-sentence summary, tags, relevance score, confidence, and key points. "
            "Return JSON with keys: summary, tags, relevance_score, confidence, key_points.\n\n"
            f"Source text:\n{request.content[:12000]}"
        )
        return self._json_completion(
            response_model=SummarizeLLMResponse,
            model=self._config.summarizer_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
        )

    def compose_report(self, request: ComposeReportLLMRequest) -> ComposeReportLLMResponse:
        findings_json = [
            {
                "title": finding.title,
                "url": str(finding.url),
                "summary": finding.summary,
                "relevance_score": finding.relevance_score,
                "confidence": finding.confidence,
                "key_points": finding.key_points[:3],
            }
            for finding in request.findings[:8]
        ]
        system_prompt = (
            "You compose concise executive summaries from provided findings. Return strict JSON only."
        )
        user_prompt = (
            f"Run id: {request.run_id}\n"
            f"Query: {request.query}\n"
            "Return JSON keys: tldr, executive_summary, markdown, html, references.\n"
            "Use only provided findings. Keep tldr to one sentence and executive_summary under 120 words.\n"
            "Set markdown and html to empty strings, and references to an empty list.\n"
            f"Findings JSON:\n{json.dumps(findings_json)[:12000]}"
        )
        return self._json_completion(
            response_model=ComposeReportLLMResponse,
            model=self._config.reporter_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
        )

    @retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3), reraise=True)
    def _json_completion(
        self,
        *,
        response_model: type[BaseModel],
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ) -> BaseModel:
        request_payload: dict[str, object] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "timeout": self._config.timeout_seconds,
            "temperature": temperature,
        }

        try:
            response = self._client.chat.completions.create(**request_payload)
        except Exception as exc:
            # Some models reject explicit temperature values; retry once without temperature.
            if not self._is_temperature_unsupported_error(exc):
                raise
            request_payload.pop("temperature", None)
            response = self._client.chat.completions.create(**request_payload)

        content = response.choices[0].message.content
        if not content:
            raise ValueError("OpenAI returned empty content for JSON response")
        return response_model.model_validate_json(content)

    @staticmethod
    def _is_temperature_unsupported_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return "temperature" in message and (
            "unsupported value" in message
            or "does not support" in message
            or "unsupported parameter" in message
        )
