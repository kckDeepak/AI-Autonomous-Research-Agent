"""Fetcher and extraction modules."""

from app.modules.fetcher.extractor import ContentExtractor
from app.modules.fetcher.service import AsyncFetcher

__all__ = ["AsyncFetcher", "ContentExtractor"]

