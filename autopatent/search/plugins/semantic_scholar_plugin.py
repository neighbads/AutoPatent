from __future__ import annotations

import json
import urllib.parse
from typing import Any

from autopatent.search.plugins.base import RequestSpec


class SemanticScholarPlugin:
    _SOURCE = "SEMANTIC_SCHOLAR"
    _DEFAULT_ENDPOINT = "https://api.semanticscholar.org/graph/v1/paper/search"

    def plugin_id(self) -> str:
        return "semantic_scholar"

    def supports(self, query: str, topic: str) -> bool:
        return bool(str(query).strip() or str(topic).strip())

    def build_requests(self, query: str, topic: str, limit: int) -> list[RequestSpec]:
        _ = topic
        safe_limit = max(1, min(int(limit or 1), 20))
        url = (
            self._DEFAULT_ENDPOINT
            + "?"
            + urllib.parse.urlencode(
                {
                    "query": query,
                    "limit": safe_limit,
                    "fields": "title,year,abstract,url,authors,externalIds",
                }
            )
        )
        return [RequestSpec(method="GET", url=url, timeout_sec=20, meta={"query": query})]

    def parse_response(self, payload: str | bytes, request: RequestSpec) -> list[dict[str, Any]]:
        text = payload.decode("utf-8", errors="ignore") if isinstance(payload, bytes) else str(payload)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return []
        rows = data.get("data")
        if not isinstance(rows, list):
            return []
        query = str(request.meta.get("query", "")).strip()
        hits: list[dict[str, Any]] = []
        for idx, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                continue
            title = str(row.get("title", "")).strip()
            if not title:
                continue
            authors: list[str] = []
            raw_authors = row.get("authors")
            if isinstance(raw_authors, list):
                for author in raw_authors[:10]:
                    if not isinstance(author, dict):
                        continue
                    name = str(author.get("name", "")).strip()
                    if name:
                        authors.append(name)
            external_ids = row.get("externalIds")
            doi = ""
            if isinstance(external_ids, dict):
                doi = str(external_ids.get("DOI", "")).strip()
            hits.append(
                {
                    "plugin_id": self.plugin_id(),
                    "source": self._SOURCE,
                    "endpoint": self._DEFAULT_ENDPOINT,
                    "query": query,
                    "title": title,
                    "url": str(row.get("url", "")).strip() or doi,
                    "year": row.get("year"),
                    "doi": doi,
                    "abstract": str(row.get("abstract", "")).strip(),
                    "authors": authors,
                    "rank": idx,
                }
            )
        return hits

    def fallback_urls(self, query: str, topic: str, limit: int) -> list[str]:
        _ = topic, limit
        return [f"https://www.semanticscholar.org/search?q={urllib.parse.quote_plus(query)}"]

    def parse_fallback(self, payload: str, url: str, query: str, source: str) -> list[dict[str, Any]]:
        lines = [line.strip() for line in str(payload or "").splitlines() if line.strip()]
        hits: list[dict[str, Any]] = []
        for idx, line in enumerate(lines[:5], start=1):
            if len(line) < 10:
                continue
            hits.append(
                {
                    "plugin_id": self.plugin_id(),
                    "source": self._SOURCE,
                    "endpoint": url,
                    "query": query,
                    "title": line[:200],
                    "url": url,
                    "rank": idx,
                    "via_fallback": True,
                    "fallback_source": source,
                }
            )
        return hits
