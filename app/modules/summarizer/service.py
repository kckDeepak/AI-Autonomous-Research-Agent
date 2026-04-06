from __future__ import annotations

from collections import OrderedDict

from app.providers.llm.base import LLMProvider
from app.providers.llm.models import SummarizeLLMRequest
from app.schemas.content import NormalizedDocument, SummarizationBatch, SummarizationIssue
from app.schemas.finding import Finding


class SummarizerService:
    def __init__(
        self,
        provider: LLMProvider,
        *,
        min_relevance_score: float = 0.45,
        max_chunks_per_source: int = 4,
    ) -> None:
        self._provider = provider
        self._min_relevance_score = min_relevance_score
        self._max_chunks_per_source = max(1, max_chunks_per_source)

    def summarize_documents(self, *, query: str, documents: list[NormalizedDocument]) -> SummarizationBatch:
        findings: list[Finding] = []
        rejected: list[Finding] = []
        issues: list[SummarizationIssue] = []

        for document in documents:
            try:
                finding = self._summarize_document(query=query, document=document)
                if finding is None:
                    issues.append(
                        SummarizationIssue(
                            url=str(document.url),
                            reason="No chunk summaries produced",
                        )
                    )
                    continue
                if finding.relevance_score >= self._min_relevance_score:
                    findings.append(finding)
                else:
                    rejected.append(finding)
            except Exception as exc:
                issues.append(SummarizationIssue(url=str(document.url), reason=str(exc)))

        return SummarizationBatch(findings=findings, rejected_findings=rejected, issues=issues)

    def _summarize_document(self, *, query: str, document: NormalizedDocument) -> Finding | None:
        chunk_summaries = []
        for chunk in document.chunks[: self._max_chunks_per_source]:
            response = self._provider.summarize_source(
                SummarizeLLMRequest(
                    query=query,
                    url=str(document.url),
                    title=document.title,
                    content=chunk,
                )
            )
            chunk_summaries.append(response)

        if not chunk_summaries:
            return None

        avg_relevance = sum(item.relevance_score for item in chunk_summaries) / len(chunk_summaries)
        avg_confidence = sum(item.confidence for item in chunk_summaries) / len(chunk_summaries)

        ordered_tags: OrderedDict[str, None] = OrderedDict()
        ordered_points: OrderedDict[str, None] = OrderedDict()
        for item in chunk_summaries:
            for tag in item.tags:
                cleaned = tag.strip()
                if cleaned:
                    ordered_tags[cleaned] = None
            for point in item.key_points:
                cleaned = point.strip()
                if cleaned:
                    ordered_points[cleaned] = None

        summary_text = " ".join(item.summary.strip() for item in chunk_summaries[:2] if item.summary.strip())
        if not summary_text:
            summary_text = chunk_summaries[0].summary.strip()

        return Finding(
            title=document.title,
            url=str(document.url),
            summary=summary_text,
            tags=list(ordered_tags.keys())[:10],
            relevance_score=max(0.0, min(1.0, avg_relevance)),
            confidence=max(0.0, min(1.0, avg_confidence)),
            key_points=list(ordered_points.keys())[:12],
        )
