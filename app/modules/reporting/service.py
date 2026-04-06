from __future__ import annotations

import html
from collections import OrderedDict

from app.providers.llm.base import LLMProvider
from app.providers.llm.models import ComposeReportLLMRequest
from app.schemas.finding import Finding
from app.schemas.report import CitationEntry, ClaimCitation, ReportArtifact


class ReportComposerService:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    def compose(self, query: str, run_id: str, findings: list[Finding]) -> ReportArtifact:
        ranked_findings = sorted(findings, key=lambda finding: finding.relevance_score, reverse=True)
        citation_index = self._build_citation_index(ranked_findings)
        citation_lookup = {entry.url: entry.reference_number for entry in citation_index}

        response = None
        try:
            response = self._provider.compose_report(
                ComposeReportLLMRequest(query=query, findings=ranked_findings, run_id=run_id)
            )
        except Exception:
            # Do not fail entire runs when report LLM generation times out.
            response = None

        tldr = (response.tldr.strip() if response else "") or self._fallback_tldr(ranked_findings)
        executive_summary = (
            response.executive_summary.strip() if response else ""
        ) or self._fallback_executive_summary(query, ranked_findings)

        markdown, claim_citations = self._render_markdown(
            query=query,
            tldr=tldr,
            executive_summary=executive_summary,
            findings=ranked_findings,
            citation_lookup=citation_lookup,
            citation_index=citation_index,
        )
        html_report = self._render_html(
            query=query,
            tldr=tldr,
            executive_summary=executive_summary,
            findings=ranked_findings,
            citation_lookup=citation_lookup,
            citation_index=citation_index,
        )

        return ReportArtifact(
            tldr=tldr,
            executive_summary=executive_summary,
            markdown=markdown,
            html=html_report,
            references=[entry.url for entry in citation_index],
            citation_index=citation_index,
            claim_citations=claim_citations,
        )

    @staticmethod
    def _fallback_tldr(findings: list[Finding]) -> str:
        if not findings:
            return "Insufficient high-confidence findings were available for a detailed conclusion."
        top = findings[0]
        return (
            f"Top signal: {top.title} (relevance {top.relevance_score:.2f}, "
            f"confidence {top.confidence:.2f})."
        )

    @staticmethod
    def _fallback_executive_summary(query: str, findings: list[Finding]) -> str:
        if not findings:
            return f"No strong findings were produced for query: {query}."

        avg_relevance = sum(item.relevance_score for item in findings) / len(findings)
        avg_confidence = sum(item.confidence for item in findings) / len(findings)
        return (
            f"The analysis for '{query}' synthesized {len(findings)} findings with average relevance "
            f"{avg_relevance:.2f} and confidence {avg_confidence:.2f}."
        )

    @staticmethod
    def _build_citation_index(findings: list[Finding]) -> list[CitationEntry]:
        unique: OrderedDict[str, Finding] = OrderedDict()
        for finding in findings:
            if finding.url not in unique:
                unique[finding.url] = finding

        citation_index: list[CitationEntry] = []
        for i, (url, finding) in enumerate(unique.items(), start=1):
            citation_index.append(
                CitationEntry(reference_number=i, url=url, finding_title=finding.title)
            )
        return citation_index

    def _render_markdown(
        self,
        *,
        query: str,
        tldr: str,
        executive_summary: str,
        findings: list[Finding],
        citation_lookup: dict[str, int],
        citation_index: list[CitationEntry],
    ) -> tuple[str, list[ClaimCitation]]:
        claim_citations: list[ClaimCitation] = []

        lines: list[str] = []
        lines.append("# Autonomous Research Report")
        lines.append("")
        lines.append(f"**Query:** {query}")
        lines.append("")
        lines.append("## TL;DR")
        lines.append(tldr)
        lines.append("")
        lines.append("## Executive Summary")
        lines.append(executive_summary)
        lines.append("")
        lines.append("## Key Findings")

        for finding in findings:
            citation_number = citation_lookup.get(finding.url)
            citation_suffix = f" [{citation_number}]" if citation_number else ""
            claim = f"{finding.title}: {finding.summary}"
            lines.append(f"- **{finding.title}**: {finding.summary}{citation_suffix}")
            lines.append(
                f"  - Relevance: {finding.relevance_score:.2f}, Confidence: {finding.confidence:.2f}"
            )
            claim_citations.append(
                ClaimCitation(
                    claim=claim,
                    citation_numbers=[citation_number] if citation_number else [],
                    source_urls=[finding.url],
                )
            )
            for point in finding.key_points[:3]:
                point_claim = point.strip()
                if not point_claim:
                    continue
                lines.append(f"  - {point_claim}{citation_suffix}")
                claim_citations.append(
                    ClaimCitation(
                        claim=point_claim,
                        citation_numbers=[citation_number] if citation_number else [],
                        source_urls=[finding.url],
                    )
                )

        lines.append("")
        lines.append("## Deep Dives")
        for index, finding in enumerate(findings[:3], start=1):
            citation_number = citation_lookup.get(finding.url)
            citation_suffix = f" [{citation_number}]" if citation_number else ""
            lines.append(f"### {index}. {finding.title}{citation_suffix}")
            lines.append(finding.summary)
            if finding.tags:
                lines.append(f"Tags: {', '.join(finding.tags[:8])}")
            lines.append(
                f"Signal score: relevance {finding.relevance_score:.2f}, confidence {finding.confidence:.2f}."
            )
            lines.append("")

        lines.append("## References")
        for entry in citation_index:
            lines.append(f"[{entry.reference_number}] {entry.url}")

        return "\n".join(lines), claim_citations

    def _render_html(
        self,
        *,
        query: str,
        tldr: str,
        executive_summary: str,
        findings: list[Finding],
        citation_lookup: dict[str, int],
        citation_index: list[CitationEntry],
    ) -> str:
        parts: list[str] = []
        parts.append("<html><body>")
        parts.append("<h1>Autonomous Research Report</h1>")
        parts.append(f"<p><strong>Query:</strong> {html.escape(query)}</p>")
        parts.append("<h2>TL;DR</h2>")
        parts.append(f"<p>{html.escape(tldr)}</p>")
        parts.append("<h2>Executive Summary</h2>")
        parts.append(f"<p>{html.escape(executive_summary)}</p>")

        parts.append("<h2>Key Findings</h2><ul>")
        for finding in findings:
            citation_number = citation_lookup.get(finding.url)
            citation_html = f" <sup>[{citation_number}]</sup>" if citation_number else ""
            parts.append(
                "<li>"
                f"<strong>{html.escape(finding.title)}</strong>: {html.escape(finding.summary)}{citation_html}"
                f"<br/><em>Relevance {finding.relevance_score:.2f}, Confidence {finding.confidence:.2f}</em>"
                "</li>"
            )
        parts.append("</ul>")

        parts.append("<h2>Deep Dives</h2>")
        for index, finding in enumerate(findings[:3], start=1):
            citation_number = citation_lookup.get(finding.url)
            citation_html = f" <sup>[{citation_number}]</sup>" if citation_number else ""
            parts.append(f"<h3>{index}. {html.escape(finding.title)}{citation_html}</h3>")
            parts.append(f"<p>{html.escape(finding.summary)}</p>")
            if finding.tags:
                parts.append(f"<p><strong>Tags:</strong> {html.escape(', '.join(finding.tags[:8]))}</p>")

        parts.append("<h2>References</h2><ol>")
        for entry in citation_index:
            parts.append(
                f"<li><a href=\"{html.escape(entry.url)}\">{html.escape(entry.url)}</a></li>"
            )
        parts.append("</ol>")
        parts.append("</body></html>")
        return "".join(parts)
