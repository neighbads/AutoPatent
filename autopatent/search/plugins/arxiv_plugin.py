from __future__ import annotations

import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any

from autopatent.search.plugins.base import RequestSpec


class ArxivPlugin:
    _SOURCE = "ARXIV"
    _DEFAULT_ENDPOINT = "http://export.arxiv.org/api/query"

    def plugin_id(self) -> str:
        return "arxiv"

    def supports(self, query: str, topic: str) -> bool:
        return bool(str(query).strip() or str(topic).strip())

    def build_requests(self, query: str, topic: str, limit: int) -> list[RequestSpec]:
        _ = topic
        safe_limit = max(1, min(int(limit or 1), 20))
        url = (
            f"{self._DEFAULT_ENDPOINT}?search_query=all:{urllib.parse.quote_plus(query)}"
            f"&start=0&max_results={safe_limit}&sortBy=relevance&sortOrder=descending"
        )
        return [RequestSpec(method="GET", url=url, timeout_sec=20, meta={"query": query})]

    def parse_response(self, payload: str | bytes, request: RequestSpec) -> list[dict[str, Any]]:
        text = payload.decode("utf-8", errors="ignore") if isinstance(payload, bytes) else str(payload)
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return []
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        query = str(request.meta.get("query", "")).strip()
        hits: list[dict[str, Any]] = []
        for idx, entry in enumerate(root.findall("atom:entry", ns), start=1):
            title = _clean(entry.findtext("atom:title", default="", namespaces=ns))
            if not title:
                continue
            link = _clean(entry.findtext("atom:id", default="", namespaces=ns))
            published = _clean(entry.findtext("atom:published", default="", namespaces=ns))
            abstract = _clean(entry.findtext("atom:summary", default="", namespaces=ns))
            authors: list[str] = []
            for node in entry.findall("atom:author", ns):
                name = _clean(node.findtext("atom:name", default="", namespaces=ns))
                if name:
                    authors.append(name)
            year: Any = ""
            if len(published) >= 4 and published[:4].isdigit():
                year = int(published[:4])
            hits.append(
                {
                    "plugin_id": self.plugin_id(),
                    "source": self._SOURCE,
                    "endpoint": self._DEFAULT_ENDPOINT,
                    "query": query,
                    "title": title,
                    "url": link,
                    "year": year,
                    "abstract": abstract,
                    "authors": authors,
                    "rank": idx,
                }
            )
        return hits

    def fallback_urls(self, query: str, topic: str, limit: int) -> list[str]:
        _ = topic
        safe_limit = max(1, min(int(limit or 1), 20))
        return [
            (
                f"{self._DEFAULT_ENDPOINT}?search_query=all:{urllib.parse.quote_plus(query)}"
                f"&start=0&max_results={safe_limit}"
            )
        ]

    def parse_fallback(self, payload: str, url: str, query: str, source: str) -> list[dict[str, Any]]:
        return self.parse_response(payload, RequestSpec(method="GET", url=url, meta={"query": query}))


def _clean(text: str) -> str:
    return " ".join(str(text or "").strip().split())
