from __future__ import annotations

import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from app.schemas.content import DocumentBatch, ExtractionIssue, FetchedPage, NormalizedDocument


class ContentExtractor:
    def __init__(
        self,
        *,
        min_chars: int = 700,
        chunk_chars: int = 3000,
        chunk_overlap: int = 300,
    ) -> None:
        self._min_chars = min_chars
        self._chunk_chars = max(500, chunk_chars)
        self._chunk_overlap = max(0, min(chunk_overlap, self._chunk_chars // 2))

    def extract_documents(self, pages: list[FetchedPage]) -> DocumentBatch:
        documents: list[NormalizedDocument] = []
        issues: list[ExtractionIssue] = []

        for page in pages:
            try:
                document = self._extract_single(page)
                if document:
                    documents.append(document)
                else:
                    issues.append(ExtractionIssue(url=str(page.final_url), reason="Insufficient text content"))
            except Exception as exc:
                issues.append(ExtractionIssue(url=str(page.final_url), reason=str(exc)))

        return DocumentBatch(documents=documents, issues=issues)

    def _extract_single(self, page: FetchedPage) -> NormalizedDocument | None:
        soup = BeautifulSoup(page.html, "html.parser")

        for selector in [
            "script",
            "style",
            "noscript",
            "svg",
            "canvas",
            "nav",
            "header",
            "footer",
            "aside",
            "form",
            "iframe",
        ]:
            for node in soup.select(selector):
                node.decompose()

        title = self._clean_text(soup.title.get_text()) if soup.title else "Untitled"

        main_node = soup.find("article") or soup.find("main") or soup.body or soup
        text = self._clean_text(main_node.get_text(separator=" "))
        if len(text) < self._min_chars:
            return None

        chunks = self._chunk_text(text)
        normalized_url = self._normalize_url(str(page.final_url))
        source_domain = self._source_domain(normalized_url)

        return NormalizedDocument(
            url=str(page.final_url),
            normalized_url=normalized_url,
            source_domain=source_domain,
            title=title or "Untitled",
            content=text,
            chunks=chunks,
            word_count=len(text.split()),
            char_count=len(text),
        )

    @staticmethod
    def _clean_text(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def _chunk_text(self, text: str) -> list[str]:
        if len(text) <= self._chunk_chars:
            return [text]

        chunks: list[str] = []
        start = 0
        step = self._chunk_chars - self._chunk_overlap
        while start < len(text):
            end = min(len(text), start + self._chunk_chars)
            chunks.append(text[start:end])
            if end == len(text):
                break
            start += step
        return chunks

    @staticmethod
    def _normalize_url(url: str) -> str:
        parsed = urlsplit(url)
        netloc = parsed.netloc.lower()
        path = parsed.path or "/"
        if path != "/" and path.endswith("/"):
            path = path[:-1]
        return f"{parsed.scheme.lower()}://{netloc}{path}"

    @staticmethod
    def _source_domain(url: str) -> str:
        domain = urlsplit(url).netloc.lower()
        if domain.startswith("www."):
            return domain[4:]
        return domain
