from __future__ import annotations

import json
import urllib.parse
from typing import Any

from autopatent.search.plugins.base import RequestSpec


class OpenAlexPlugin:
    _SOURCE = "OPENALEX"
    _DEFAULT_ENDPOINT = "https://api.openalex.org/works"

    def plugin_id(self) -> str:
        return "openalex"

    def supports(self, query: str, topic: str) -> bool:
        return bool(str(query).strip() or str(topic).strip())

    def build_requests(self, query: str, topic: str, limit: int) -> list[RequestSpec]:
        safe_limit = max(1, min(int(limit or 1), 20))
        url = (
            self._DEFAULT_ENDPOINT
            + "?"
            + urllib.parse.urlencode(
                {
                    "search": query,
                    "per_page": safe_limit,
                    "select": "id,title,publication_year,doi,authorships,primary_location",
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
        items = data.get("results")
        if not isinstance(items, list):
            return []
        query = str(request.meta.get("query", "")).strip()
        hits: list[dict[str, Any]] = []
        for idx, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            if not title:
                continue
            location = item.get("primary_location")
            landing = ""
            if isinstance(location, dict):
                landing = str(location.get("landing_page_url", "")).strip()
            doi = str(item.get("doi", "")).strip()
            authors: list[str] = []
            raw_authors = item.get("authorships")
            if isinstance(raw_authors, list):
                for author in raw_authors[:10]:
                    if not isinstance(author, dict):
                        continue
                    author_info = author.get("author")
                    if not isinstance(author_info, dict):
                        continue
                    name = str(author_info.get("display_name", "")).strip()
                    if name:
                        authors.append(name)

            hits.append(
                {
                    "plugin_id": self.plugin_id(),
                    "source": self._SOURCE,
                    "endpoint": self._DEFAULT_ENDPOINT,
                    "query": query,
                    "title": title,
                    "url": landing or doi or str(item.get("id", "")).strip(),
                    "year": item.get("publication_year"),
                    "doi": doi,
                    "authors": authors,
                    "rank": idx,
                }
            )
        return hits

    def fallback_urls(self, query: str, topic: str, limit: int) -> list[str]:
        _ = topic
        safe_query = urllib.parse.quote_plus(query.strip())
        if not safe_query:
            return []
        return [f"https://api.openalex.org/works?search={safe_query}&per_page={max(1, min(limit, 5))}"]

    def parse_fallback(self, payload: str, url: str, query: str, source: str) -> list[dict[str, Any]]:
        text = str(payload or "").strip()
        if not text:
            return []
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        hits: list[dict[str, Any]] = []
        for idx, line in enumerate(lines[:5], start=1):
            title = line[:180]
            if len(title) < 8:
                continue
            hits.append(
                {
                    "plugin_id": self.plugin_id(),
                    "source": self._SOURCE,
                    "endpoint": url,
                    "query": query,
                    "title": title,
                    "url": url,
                    "rank": idx,
                    "via_fallback": True,
                    "fallback_source": source,
                }
            )
        return hits
